-- Automated FE8 playtest harness for mGBA 0.11+ (--script).
--
-- Launched by run.sh via a generated wrapper that sets:
--   PLAYTEST_DIR      -- this directory (for dofile of symbols.lua)
--   PLAYTEST_SCENARIO -- "win" | "gameover" | "retreat" | "titlecard"
--   PLAYTEST_LOG      -- log file path (runner polls it for "RESULT:")
--   PLAYTEST_SHOTDIR  -- screenshot directory for milestone/debug captures
--
-- Design: one coroutine resumed once per emulated frame; every wait is a
-- yield loop over real memory state (closed loop, no frame-perfect timing).
-- Asserts read the decomp's own structs; UI is driven only where the event
-- engine demands real combat (deaths must go through battle, not HP pokes).

dofile(PLAYTEST_DIR .. "/symbols.lua")

-- Struct offsets, from the decomp headers (stable; addresses are not):
--   include/types.h  struct PlaySt: +0x0E chapterIndex, +0x0F faction
--                    (0x00 player / 0x40 NPC / 0x80 enemy), +0x10 turn
--   include/types.h  struct BmSt:   +0x14 playerCursor (s16 x, s16 y)
--   include/bmunit.h struct Unit (0x48 bytes): +0x00 pCharacterData,
--                    +0x0C state, +0x10 x, +0x11 y, +0x12 maxHP, +0x13 curHP,
--                    +0x14 pow, +0x16 spd, +0x17 def, +0x18 res, +0x19 lck
--   CharacterData: +0x04 = character id (include/bmunit.h)
--   src/proc.c sProcArray: 64 procs x 0x6C; +0x00 = proc_script
local UNIT_SIZE = 0x48
local US_DEAD = 4 -- include/bmunit.h (1 << 2)
local CHAR_HLIN, CHAR_SCRAMSAX, CHAR_SEPHEK = 0x0D, 0x11, 0x68 -- NATASHA/KYLE/ONEILL slots
local HOST_CHAPTER = 1 -- prologue is hosted on chapter slot 1; MNC2(0x2) on win

local logfile = io.open(PLAYTEST_LOG, "w")
local function log(s)
    logfile:write(string.format("[f%06d] %s\n", emu:currentFrame(), s))
    logfile:flush()
end
local function result(verdict, why)
    log("RESULT: " .. verdict .. " -- " .. why)
end
local nshot = 0
local function shot(tag)
    nshot = nshot + 1
    local p = string.format("%s/%02d-%s.png", PLAYTEST_SHOTDIR, nshot, tag)
    pcall(function() emu:screenshot(p) end)
    log("screenshot: " .. p)
end

-- ---------------------------------------------------------------- primitives
local function yield() coroutine.yield() end
local function wait(n) for _ = 1, n do yield() end end
local function press(key, holdFrames)
    emu:addKey(key)
    wait(holdFrames or 4)
    emu:clearKey(key)
    wait(4)
end
local K = C.GBA_KEY

local function ru8(a) return emu:read8(a) end
local function ru16(a) return emu:read16(a) end
local function ru32(a) return emu:read32(a) end
local function rs16(a)
    local v = emu:read16(a)
    if v >= 0x8000 then v = v - 0x10000 end
    return v
end

local function chapter() return ru8(SYM.gPlaySt + 0x0E) end
local function faction() return ru8(SYM.gPlaySt + 0x0F) end
local function turn() return ru16(SYM.gPlaySt + 0x10) end
local function cursor() return rs16(SYM.gBmSt + 0x14), rs16(SYM.gBmSt + 0x16) end

local function procActive(scriptAddr)
    for i = 0, 63 do
        if ru32(SYM.sProcArray + i * 0x6C) == scriptAddr then return true end
    end
    return false
end
local function menuOpen() return procActive(SYM.sProc_Menu) end
local function gameOverActive() return procActive(SYM.ProcScr_GameOverScreen) end

-- Event flag state (src/eventinfo.c): < 100 chapter flag bit (flag-1),
-- > 100 permanent flag bit (flag-101). EVFLAG_GAMEOVER=0x65, DEFEAT_BOSS=2.
local function eventFlag(flag)
    local base, idx
    if flag < 100 then base, idx = SYM.gChapterFlagBits, flag - 1
    else base, idx = SYM.gPermanentFlagBits, flag - 101 end
    return (ru8(base + math.floor(idx / 8)) & (1 << (idx % 8))) ~= 0
end

-- ---------------------------------------------------------------- unit access
local function unitAt(base, i)
    local a = base + i * UNIT_SIZE
    local chptr = ru32(a)
    if chptr == 0 then return nil end
    return {
        addr = a,
        charId = ru8(chptr + 4),
        x = ru8(a + 0x10), y = ru8(a + 0x11),
        hp = ru8(a + 0x13),
        state = ru32(a + 0x0C),
    }
end
local function findUnit(base, count, charId)
    for i = 0, count - 1 do
        local u = unitAt(base, i)
        if u and u.charId == charId then return u end
    end
    return nil
end
local function blue(charId) return findUnit(SYM.gUnitArrayBlue, 8, charId) end
local function red(charId) return findUnit(SYM.gUnitArrayRed, 24, charId) end
local function isDead(u) return u == nil or (u.state & US_DEAD) ~= 0 end

local function pokeFrail(u) -- 1 HP, no def/res/spd/lck: next clean hit kills
    emu:write8(u.addr + 0x13, 1) -- curHP
    emu:write8(u.addr + 0x16, 0) -- spd
    emu:write8(u.addr + 0x17, 0) -- def
    emu:write8(u.addr + 0x18, 0) -- res
    emu:write8(u.addr + 0x19, 0) -- lck
end
local function pokeHarmless(u) -- can't counter-kill (keeps the boss alive)
    emu:write8(u.addr + 0x14, 0) -- pow
end

local function tileOccupied(x, y)
    for _, base in ipairs({ SYM.gUnitArrayBlue, SYM.gUnitArrayRed }) do
        for i = 0, 23 do
            local u = unitAt(base, i)
            if u and not isDead(u) and u.x == x and u.y == y then return true end
        end
    end
    return false
end

-- ---------------------------------------------------------------- UI driving
local function cursorTo(tx, ty)
    for _ = 1, 120 do
        local cx, cy = cursor()
        if cx == tx and cy == ty then return true end
        if cx < tx then press(K.RIGHT, 3)
        elseif cx > tx then press(K.LEFT, 3)
        elseif cy < ty then press(K.DOWN, 3)
        else press(K.UP, 3) end
    end
    return false
end

local function waitFor(pred, frames, tapA)
    for f = 1, frames do
        if pred() then return true end
        -- advance any dialogue (death quotes etc. wait for A)
        if tapA and f % 50 == 0 then press(K.A, 3) end
        yield()
    end
    return false
end

-- Select unit at (fx,fy), move to (tx,ty). True when the action menu opened.
local function moveUnit(fx, fy, tx, ty)
    if not cursorTo(fx, fy) then return false end
    press(K.A)
    wait(10) -- movement range now shown
    if not cursorTo(tx, ty) then press(K.B); return false end
    press(K.A)
    if waitFor(menuOpen, 40) then return true end
    press(K.B); press(K.B)
    return false
end

local function chooseWait() -- action menu: Wait is last; UP wraps to it
    press(K.UP)
    press(K.A)
    waitFor(function() return not menuOpen() end, 60)
end

-- Action menu with an enemy in range: Attack is first. A -> weapon list
-- (first weapon) -> A -> target (sole in-range target) -> A -> combat.
local function chooseAttack(actorAddr)
    press(K.A); wait(20)
    press(K.A); wait(20)
    press(K.A)
    -- combat (with battle anims) ends when the actor is greyed out
    local done = waitFor(function()
        return (ru32(actorAddr + 0x0C) & 0x2) ~= 0 -- US_UNSELECTABLE
    end, 1200, true)
    wait(30)
    return done
end

-- March a unit toward (tx,ty) using the game's own pathing: selecting the
-- unit fills gBmMapMovement (include/bmmap.h; cost < 120 = reachable this
-- turn), so we read it and pick the reachable free tile closest to the target.
local function reachCost(x, y)
    local row = ru32(ru32(SYM.gBmMapMovement) + y * 4)
    return ru8(row + x)
end
local function marchToward(u, tx, ty)
    if not cursorTo(u.x, u.y) then return false end
    press(K.A)
    wait(12) -- selection computes the move-range map
    if not menuOpen() then -- selected a unit, not opened the map menu
        local best, bestd = nil, 999
        for y = 0, 9 do
            for x = 0, 14 do
                if reachCost(x, y) < 120 and not tileOccupied(x, y)
                    and not (x == u.x and y == u.y) then
                    local d = math.abs(tx - x) + math.abs(ty - y)
                    if d < bestd then best, bestd = { x = x, y = y }, d end
                end
            end
        end
        if best and cursorTo(best.x, best.y) then
            press(K.A)
            if waitFor(menuOpen, 40) then
                chooseWait()
                return true
            end
        end
    end
    press(K.B); press(K.B)
    return false
end

local EMPTY_TILE = { x = 2, y = 2 } -- far from both rosters on ch00
local function endTurn()
    cursorTo(EMPTY_TILE.x, EMPTY_TILE.y)
    press(K.A)
    if not waitFor(menuOpen, 40) then press(K.B); return false end
    press(K.UP) -- map menu: UP from the top wraps to End (last entry)
    press(K.A)
    return true
end

-- End turn, then ride out the enemy phase. Returns "gameover" the moment the
-- game-over screen proc appears, "player" when control comes back, or nil.
local function runEnemyPhase()
    if not endTurn() then return nil end
    waitFor(function() return faction() ~= 0 end, 300)
    for f = 1, 3600 do
        if gameOverActive() then return "gameover" end
        if faction() == 0 and not menuOpen() then return "player" end
        if f % 50 == 0 then press(K.A, 3) end -- advance quotes/dialogue
        yield()
    end
    return nil
end

-- ---------------------------------------------------------------- boot
local function inChapter()
    return chapter() == HOST_CHAPTER and faction() == 0 and turn() >= 1
        and unitAt(SYM.gUnitArrayBlue, 0) ~= nil
end

local function bootToMap()
    log("booting to map (fresh save -> New Game)")
    for i = 1, 90 do
        if inChapter() then
            wait(120) -- let deploy events settle
            press(K.B); press(K.B)
            log(string.format("in chapter %d turn %d", chapter(), turn()))
            shot("map-loaded")
            return true
        end
        press(i % 2 == 0 and K.A or K.START, 4)
        wait(26)
    end
    shot("boot-stuck")
    return false
end

-- ---------------------------------------------------------------- scenarios
local scenarios = {}

-- WIN: kill Sephek -> DefeatBoss -> ending scene -> chapter advances.
scenarios.win = function()
    if not bootToMap() then return result("FAIL", "never reached the map") end
    local sephek = red(CHAR_SEPHEK)
    if not sephek then return result("FAIL", "Sephek not found in red array") end
    pokeFrail(sephek)
    log(string.format("Sephek at (%d,%d) poked to 1 HP", sephek.x, sephek.y))
    for t = 1, 6 do
        local scram = blue(CHAR_SCRAMSAX)
        if isDead(scram) then return result("FAIL", "Scramsax died in the win run") end
        -- adjacent tile next to the boss, then attack (steel sword, range 1)
        local tx, ty = sephek.x, sephek.y + 1
        if tileOccupied(tx, ty) then tx, ty = sephek.x - 1, sephek.y end
        if moveUnit(scram.x, scram.y, tx, ty) then
            shot("attacking-sephek")
            chooseAttack(scram.addr)
        end
        if isDead(red(CHAR_SEPHEK)) then
            log("Sephek dead; waiting for the chapter to end")
            shot("sephek-dead")
            local ended = waitFor(function() return chapter() ~= HOST_CHAPTER end, 3600, true)
            shot("after-boss-kill")
            if ended then
                return result("PASS", string.format(
                    "DefeatBoss fired; chapter advanced %d -> %d", HOST_CHAPTER, chapter()))
            end
            return result("FAIL", "Sephek died but the chapter never ended")
        end
        log("Sephek alive after turn " .. t .. " (miss?); ending turn and retrying")
        local phase = runEnemyPhase()
        if phase == "gameover" then return result("FAIL", "unexpected game over in win run") end
        if isDead(red(CHAR_SEPHEK)) then -- counter-kill on enemy phase also wins
            local ended = waitFor(function() return chapter() ~= HOST_CHAPTER end, 3600, true)
            shot("after-boss-kill")
            if ended then return result("PASS", "DefeatBoss fired (counter-kill); chapter advanced") end
            return result("FAIL", "Sephek died but the chapter never ended")
        end
    end
    shot("win-timeout")
    result("FAIL", "could not kill Sephek in 6 turns")
end

-- TITLECARD: open the map menu -> Status screen, which decompresses the
-- chapter title card (chap_title_data[chapTitleId]) -- the artifact screenshot
-- is how a recomposed title gets eyeballed without a manual run.
scenarios.titlecard = function()
    if not bootToMap() then return result("FAIL", "never reached the map") end
    for try = 1, 5 do
        press(K.A)
        if waitFor(menuOpen, 40) then break end
        press(K.B); press(K.B) -- cursor was on a unit; nudge off and retry
        press(K.DOWN, 3)
        if try == 5 then return result("FAIL", "map menu never opened") end
    end
    press(K.DOWN) -- map menu: Unit, [Status], Options, Suspend, End
    press(K.A)
    local ok = waitFor(function()
        return procActive(SYM.gProcScr_ChapterStatusScreen)
    end, 120)
    wait(90) -- let the banner/turn/funds panes finish drawing
    shot("chapter-status")
    -- dump palette RAM (BG + OBJ banks): traces which palette row owns an
    -- on-screen color (used to find what ApplyPalette call feeds the banner art)
    for row = 0, 31 do
        local bank = row < 16 and "BGPAL" or "OBJPAL"
        local t = {}
        for c = 0, 15 do
            t[#t + 1] = string.format("%04X", ru16(0x05000000 + row * 32 + c * 2))
        end
        log(string.format("%s %02d: %s", bank, row % 16, table.concat(t, " ")))
    end
    if ok then
        result("PASS", "Status screen open; title card screenshot taken")
    else
        result("FAIL", "Status screen proc never appeared")
    end
end

-- GAMEOVER: Hlin (the lord-analog) dies -> EVFLAG_GAMEOVER quote -> game over.
scenarios.gameover = function()
    if not bootToMap() then return result("FAIL", "never reached the map") end
    local hlin = blue(CHAR_HLIN)
    if not hlin then return result("FAIL", "Hlin not found in blue array") end
    pokeFrail(hlin)
    log(string.format("Hlin at (%d,%d) poked frail; marching her at the enemy", hlin.x, hlin.y))
    local sephek = red(CHAR_SEPHEK)
    local tx, ty = sephek.x, sephek.y + 1 -- adjacent: he attacks in range
    for t = 1, 8 do
        hlin = blue(CHAR_HLIN)
        if isDead(hlin) or gameOverActive() then break end
        marchToward(hlin, tx, ty)
        shot("hlin-turn" .. t)
        local phase = runEnemyPhase()
        if phase == "gameover" then break end
    end
    if waitFor(gameOverActive, 1800, true) then
        shot("game-over-screen")
        return result("PASS", "Hlin died and the game-over screen proc is live")
    end
    shot("gameover-timeout")
    log(string.format("debug: EVFLAG_GAMEOVER(0x65)=%s EVFLAG_DEFEAT_BOSS(2)=%s chapter=%d faction=0x%02X",
        tostring(eventFlag(0x65)), tostring(eventFlag(2)), chapter(), faction()))
    if isDead(blue(CHAR_HLIN)) then
        return result("FAIL", "Hlin died but NO game over followed")
    end
    result("FAIL", "could not get Hlin killed in 8 turns (no verdict on game over)")
end

-- RETREAT: Scramsax dies -> flag-less quote -> battle CONTINUES (no game over).
scenarios.retreat = function()
    if not bootToMap() then return result("FAIL", "never reached the map") end
    local scram = blue(CHAR_SCRAMSAX)
    if not scram then return result("FAIL", "Scramsax not found in blue array") end
    pokeFrail(scram)
    pokeHarmless(scram) -- his counters must not kill the boss mid-test
    local sephek = red(CHAR_SEPHEK)
    log("Scramsax poked frail+harmless; parking him next to Sephek")
    for t = 1, 6 do
        scram = blue(CHAR_SCRAMSAX)
        if isDead(scram) then break end
        local tx, ty = sephek.x, sephek.y + 1
        if tileOccupied(tx, ty) then tx, ty = sephek.x - 1, sephek.y end
        if moveUnit(scram.x, scram.y, tx, ty) then chooseWait() end
        shot("scram-turn" .. t)
        local phase = runEnemyPhase()
        if phase == "gameover" then
            shot("unexpected-game-over")
            return result("FAIL", "game over fired on Scramsax's death (must be Hlin-only)")
        end
    end
    if not isDead(blue(CHAR_SCRAMSAX)) then
        shot("retreat-timeout")
        return result("FAIL", "could not get Scramsax killed in 6 turns (no verdict)")
    end
    shot("scram-dead-battle-on")
    -- he is dead; the battle must still be running on the same chapter
    wait(300)
    if gameOverActive() then
        return result("FAIL", "game over fired on Scramsax's death (must be Hlin-only)")
    end
    if chapter() ~= HOST_CHAPTER then
        return result("FAIL", "chapter ended on Scramsax's death")
    end
    result("PASS", "Scramsax died; quote path ran with no game over; battle continues")
end

-- ---------------------------------------------------------------- runner
local co = coroutine.create(function()
    log("scenario: " .. PLAYTEST_SCENARIO)
    local fn = scenarios[PLAYTEST_SCENARIO]
    if not fn then return result("ERROR", "unknown scenario " .. tostring(PLAYTEST_SCENARIO)) end
    fn()
    log("scenario function returned")
end)

callbacks:add("frame", function()
    if coroutine.status(co) == "dead" then return end
    local ok, err = coroutine.resume(co)
    if not ok then
        log("LUA ERROR: " .. tostring(err))
        result("ERROR", tostring(err))
    end
end)
