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
-- Lord select (#42): menu order = classed cast order (build_campaign PORTRAIT_MAP);
-- the LAST candidate (pinky, NEIMI slot) is benched by default under the 4-slot
-- deploy cap, so choosing them is the visible force-deploy differential.
local LORD_CANDIDATES = 8
local LORDSEL_FLAG_BASE = 0xF0
local CHAR_PINKY, CHAR_CHIEF = 0x08, 0x46 -- NEIMI slot / BREGUET slot (ch01 boss)

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
local function pokeFastConfig() -- many-combat phases: map-anim battles + fast speed
    -- PlaySt config (gPlaySt+0x40, include/types.h PlaySt_OptionBits):
    -- bit 7 gameSpeed (1 = fast), bits 17-18 animationType (1 = OFF -> map combat)
    local a = SYM.gPlaySt + 0x40
    local c = ru32(a)
    c = (c & ~(3 << 17)) | (1 << 17)
    c = c | (1 << 7)
    emu:write32(a, c)
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
local function marchToward(u, tx, ty, maxx, maxy)
    maxx, maxy = maxx or 14, maxy or 9 -- default = ch00 map; ch01 is 25x16
    -- Select the unit. The A press can be eaten (phase-banner interlude still
    -- animating), leaving a STALE movement map that reads cost 0 everywhere --
    -- the scan would then "reach" any tile and the follow-up A on it opens the
    -- map menu, whose UP-wrapped last entry is End (a wasted turn, the
    -- ch01win bug). A real movement map always has unreachable tiles, so
    -- demand some before trusting it.
    local selected = false
    for attempt = 1, 4 do
        if not cursorTo(u.x, u.y) then return false end
        press(K.A)
        wait(12) -- selection computes the move-range map
        if menuOpen() then press(K.B); wait(10); return false end -- unit exhausted
        local unreachable = 0
        for y = 0, maxy do
            for x = 0, maxx do
                if reachCost(x, y) >= 120 then unreachable = unreachable + 1 end
            end
        end
        if unreachable > 0 then selected = true break end
        log("  march: movement map stale (eaten A press?); reselecting")
        press(K.B)
        wait(40)
    end
    if selected then
        local best, bestd = nil, 999
        for y = 0, maxy do
            for x = 0, maxx do
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
local function endTurn(tile)
    tile = tile or EMPTY_TILE
    cursorTo(tile.x, tile.y)
    press(K.A)
    if not waitFor(menuOpen, 40) then press(K.B); return false end
    press(K.UP) -- map menu: UP from the top wraps to End (last entry)
    press(K.A)
    return true
end

-- End turn, then ride out the enemy phase. Returns "gameover" the moment the
-- game-over screen proc appears, "player" when control comes back, or nil.
local function runEnemyPhase(tile)
    if not endTurn(tile) then return nil end
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

-- Play ch00 to the boss kill and wait out the ending scene. Returns true once
-- the chapter has advanced past the host slot, nil/false (with its own FAIL
-- result already logged) otherwise. Shared by the win and ch01 scenarios.
local function winCh00()
    if not bootToMap() then result("FAIL", "never reached the map") return false end
    local sephek = red(CHAR_SEPHEK)
    if not sephek then result("FAIL", "Sephek not found in red array") return false end
    pokeFrail(sephek)
    log(string.format("Sephek at (%d,%d) poked to 1 HP", sephek.x, sephek.y))
    for t = 1, 6 do
        local scram = blue(CHAR_SCRAMSAX)
        if isDead(scram) then result("FAIL", "Scramsax died in the win run") return false end
        -- adjacent tile next to the boss, then attack (steel sword, range 1)
        local tx, ty = sephek.x, sephek.y + 1
        if tileOccupied(tx, ty) then tx, ty = sephek.x - 1, sephek.y end
        if moveUnit(scram.x, scram.y, tx, ty) then
            shot("attacking-sephek")
            chooseAttack(scram.addr)
        end
        if not isDead(red(CHAR_SEPHEK)) then
            log("Sephek alive after turn " .. t .. " (miss?); ending turn and retrying")
            local phase = runEnemyPhase()
            if phase == "gameover" then
                result("FAIL", "unexpected game over in win run")
                return false
            end
        end
        if isDead(red(CHAR_SEPHEK)) then
            log("Sephek dead; waiting for the chapter to end")
            shot("sephek-dead")
            local ended = waitFor(function() return chapter() ~= HOST_CHAPTER end, 3600, true)
            shot("after-boss-kill")
            if ended then return true end
            result("FAIL", "Sephek died but the chapter never ended")
            return false
        end
    end
    shot("win-timeout")
    result("FAIL", "could not kill Sephek in 6 turns")
    return false
end

-- WIN: kill Sephek -> DefeatBoss -> ending scene -> chapter advances.
scenarios.win = function()
    if winCh00() then
        result("PASS", string.format(
            "DefeatBoss fired; chapter advanced %d -> %d", HOST_CHAPTER, chapter()))
    end
end

-- GOODBERRY: boot to the ch00 map, open Hlin's Item menu (she carries a Hand Axe +
-- a Goodberry, the reflavored Vulnerary), and screenshot the item list + the
-- highlighted Goodberry so the new name + blueberry icon can be eyeballed in-game.
scenarios.goodberry = function()
    if not bootToMap() then return result("FAIL", "never reached the map") end
    local hlin = blue(CHAR_HLIN)
    if not hlin then return result("FAIL", "Hlin not found in blue array") end
    log(string.format("Hlin at (%d,%d)", hlin.x, hlin.y))
    -- select Hlin and re-confirm her own tile -> action menu (no move).
    if not moveUnit(hlin.x, hlin.y, hlin.x, hlin.y) then
        return result("FAIL", "action menu never opened for Hlin")
    end
    shot("action-menu")
    -- No enemy is in handaxe range at turn 1, so the command menu is [Item, Wait];
    -- A picks Item (top). Screenshot shows both items with icons + names.
    press(K.A)
    wait(40)
    shot("item-list")
    -- inventory order is Hand Axe (slot 1) then Goodberry (slot 2): DOWN highlights
    -- the Goodberry, refreshing the name/description panel.
    press(K.DOWN)
    wait(30)
    shot("goodberry-highlighted")
    -- open the item submenu (Use/Trade/Discard) -> shows the item description too.
    press(K.A)
    wait(40)
    shot("goodberry-detail")
    result("PASS", "Goodberry item menu captured (see screenshots)")
end

-- CH01: ride the ch00 win into chapter slot 2 and smoke the ch01 entry:
-- the ch00 guests leave the party (DISA), the prep screen opens (SALLYCURSOR,
-- via the PREP event command), Fight! hands over control, and the deployed
-- count equals the 4-slot field-parity cap (the ally UnitDefinition template).
scenarios.ch01 = function()
    if not winCh00() then return end
    if not waitFor(function() return chapter() == 2 end, 1800) then
        return result("FAIL", "chapter slot 2 never loaded after the ch00 win")
    end
    log("in ch01 (chapter slot 2); clicking through the post-chapter save menu")
    -- The post-chapter save menu sits between MNC2 and the ch01 beginning
    -- scene: A-tap through the Beat-1 Northlook scene (#21, ~22 dialogue pages +
    -- the lord-select prompt/menu/confirm) until the prep screen proc appears,
    -- then stop -- further A's would toggle Pick Units entries.
    local prep = false
    for i = 1, 200 do
        if procActive(SYM.gProcScr_SALLYCURSOR) then prep = true break end
        if i % 12 == 0 then
            shot(string.format("ch01-wait-%02d", i))
            log(string.format("waiting: chapter=%d faction=0x%02X turn=%d",
                chapter(), faction(), turn()))
        end
        press(K.A, 4)
        wait(36)
    end
    if not prep then
        shot("ch01-no-prep")
        for i = 0, 63 do -- dump live procs for post-mortem (nm the addresses)
            local a = SYM.sProcArray + i * 0x6C
            local p = ru32(a)
            if p ~= 0 then
                -- EventEngineProc: +0x30 pEventStart, +0x38 pEventCurrent
                log(string.format("proc[%02d] script=0x%08X evStart=0x%08X evCur=0x%08X",
                    i, p, ru32(a + 0x30), ru32(a + 0x38)))
            end
        end
        return result("FAIL", "prep screen never opened (PREP event cmd)")
    end
    wait(180) -- let the preparations menu draw
    shot("ch01-prep-menu")
    -- START = Fight! (PrepScreenMenu_OnStartPress). B first backs out of any
    -- state a boot keypress may have left; A every few tries clicks through a
    -- confirm if one appears.
    for i = 1, 40 do
        if not procActive(SYM.gProcScr_SALLYCURSOR) then break end
        press(K.B, 4)
        wait(10)
        press(K.START, 4)
        wait(40)
        if i % 4 == 0 and procActive(SYM.gProcScr_SALLYCURSOR) then press(K.A, 4) wait(20) end
    end
    local fighting = waitFor(function()
        return not procActive(SYM.gProcScr_SALLYCURSOR)
            and faction() == 0 and turn() >= 1
    end, 1200)
    if not fighting then
        shot("ch01-prep-stuck")
        return result("FAIL", "could not leave preparations via Fight!")
    end
    wait(120) -- phase intro
    shot("ch01-map")
    if blue(CHAR_HLIN) or blue(CHAR_SCRAMSAX) then
        return result("FAIL", "ch00 guests still in the party in ch01")
    end
    local party, deployed = 0, 0
    for i = 0, 50 do
        local u = unitAt(SYM.gUnitArrayBlue, i)
        if u then
            party = party + 1
            -- on the field = not US_HIDDEN (1<<0) and not US_NOT_DEPLOYED (1<<3)
            if (u.state & 0x9) == 0 and u.x ~= 0xFF then deployed = deployed + 1 end
        end
    end
    log(string.format("party=%d deployed=%d turn=%d", party, deployed, turn()))
    for i = 0, 50 do -- blue + red unit tables for the post-run eyeball
        local u = unitAt(SYM.gUnitArrayBlue, i)
        if u then log(string.format("blue[%02d] char=0x%02X pos=(%d,%d) state=0x%08X",
            i, u.charId, u.x, u.y, u.state)) end
        local r = unitAt(SYM.gUnitArrayRed, i)
        if r then log(string.format("red[%02d]  char=0x%02X pos=(%d,%d) state=0x%08X",
            i, r.charId, r.x, r.y, r.state)) end
    end
    if deployed ~= 4 then
        return result("FAIL", string.format(
            "deploy cap broken: %d units on the field (want 4)", deployed))
    end
    if party <= 4 then
        return result("FAIL", string.format(
            "party is only %d units -- the cast join LOAD did not run", party))
    end
    result("PASS", string.format(
        "ch01 entered: preps shown, guests gone, %d-unit party fields exactly 4", party))
end

-- CH01WIN: the default lord (blind A-taps pick Braulo) marches on the camp,
-- kills the chief, and SEIZES -- in-game proof of the lord-gated Seize
-- (CanUnitSeize hook, #42) and the win hand-off (Seize macro -> EVFLAG_WIN ->
-- ending scene -> MNC2(0x3) -> next chapter slot).
local CH01_PARK = { x = 24, y = 15 } -- empty far corner; ch01 map is 25x16
scenarios.ch01win = function()
    if not winCh00() then return end
    if not waitFor(function() return chapter() == 2 end, 1800) then
        return result("FAIL", "chapter slot 2 never loaded after the ch00 win")
    end
    -- default-lord entry: A-taps ride the save menu + the Beat-1 Northlook scene
    -- (#21, ~22 pages) + the lord prompt + lord menu (item 0 = Braulo) + [Yes]
    -- confirm all the way to the prep screen
    local prep = false
    for i = 1, 200 do
        if procActive(SYM.gProcScr_SALLYCURSOR) then prep = true break end
        press(K.A, 4)
        wait(36)
    end
    if not prep then
        shot("ch01win-no-prep")
        return result("FAIL", "prep screen never opened")
    end
    wait(180)
    for i = 1, 40 do
        if not procActive(SYM.gProcScr_SALLYCURSOR) then break end
        press(K.B, 4)
        wait(10)
        press(K.START, 4)
        wait(40)
        if i % 4 == 0 and procActive(SYM.gProcScr_SALLYCURSOR) then press(K.A, 4) wait(20) end
    end
    if not waitFor(function()
        return not procActive(SYM.gProcScr_SALLYCURSOR)
            and faction() == 0 and turn() >= 1
    end, 1200) then
        shot("ch01win-prep-stuck")
        return result("FAIL", "could not leave preparations via Fight!")
    end
    wait(120)
    shot("ch01win-map")
    pokeFastConfig() -- 10-goblin enemy phases: map combat + fast speed
    local chief = red(CHAR_CHIEF)
    if not chief then return result("FAIL", "chief not in the red array") end
    local goal = { x = chief.x, y = chief.y } -- chief holds the seize tile
    pokeFrail(chief)
    log(string.format("chief frail on the seize tile (%d,%d); marching Braulo",
        goal.x, goal.y))
    for t = 1, 18 do
        -- sync to the player phase; the A-taps also clear stray textboxes
        -- (road-sign AREA event, defeat quotes)
        waitFor(function() return faction() == 0 and not menuOpen() end, 6000, true)
        wait(100) -- let the PLAYER PHASE banner finish (it eats key presses)
        local b0 = blue(0x01)
        log(string.format("loop %d: turn=%d faction=0x%02X braulo=(%d,%d) chiefdead=%s",
            t, turn(), faction(), b0 and b0.x or -1, b0 and b0.y or -1,
            tostring(isDead(red(CHAR_CHIEF)))))
        -- every other goblin dies to the first counter (frail) and deals no
        -- damage (harmless): the escort can't kill anyone OR bodyblock the
        -- trail for long. This run asserts seize logic, not combat survival.
        for i = 0, 23 do
            local r = unitAt(SYM.gUnitArrayRed, i)
            if r and r.charId ~= CHAR_CHIEF and not isDead(r) then
                pokeFrail(r)
                pokeHarmless(r)
            end
        end
        local braulo = blue(0x01)
        if isDead(braulo) then return result("FAIL", "Braulo died on the march") end
        chief = red(CHAR_CHIEF)
        if chief and not isDead(chief) then
            if math.abs(braulo.x - chief.x) + math.abs(braulo.y - chief.y) == 1 then
                -- adjacent: attack in place (move onto own tile opens the menu)
                if moveUnit(braulo.x, braulo.y, braulo.x, braulo.y) then
                    shot("ch01win-attack-chief")
                    chooseAttack(braulo.addr)
                end
            else
                local moved = marchToward(braulo, goal.x, goal.y + 1, 24, 15)
                b0 = blue(0x01)
                log(string.format("  march -> %s, braulo=(%d,%d)",
                    tostring(moved), b0.x, b0.y))
            end
        else
            -- chief down: Braulo onto the seize tile; Seize tops the menu there
            if moveUnit(braulo.x, braulo.y, goal.x, goal.y) then
                shot("ch01win-seize-menu")
                press(K.A) -- Seize
            end
            local won = waitFor(function() return chapter() ~= 2 end, 3600, true)
            shot("ch01win-after-seize")
            if won then
                return result("PASS", string.format(
                    "Braulo seized the camp; chapter advanced 2 -> %d", chapter()))
            end
            press(K.B); press(K.B) -- menu surprise: back out, retry next turn
        end
        local phase = runEnemyPhase(CH01_PARK)
        if phase == "gameover" then
            return result("FAIL", "unexpected game over in the win run")
        end
    end
    shot("ch01win-timeout")
    result("FAIL", "could not seize the camp in 14 turns")
end

-- RECORDCH01TRAIL (#21): capture the in-battle trail beats as motion for review --
-- Izobai's turn-1 taunt and her death quote, both over the snowy map with her custom
-- bust. Rides the ch00 win -> ch01 prep -> fight, then captures frames ("trail").
scenarios.recordch01trail = function()
    if not winCh00() then return end
    if not waitFor(function() return chapter() == 2 end, 1800) then
        return result("FAIL", "chapter slot 2 never loaded after the ch00 win")
    end
    local prep = false
    for i = 1, 200 do
        if procActive(SYM.gProcScr_SALLYCURSOR) then prep = true break end
        press(K.A, 4); wait(36)
    end
    if not prep then shot("trail-no-prep"); return result("FAIL", "prep never opened") end
    wait(180)
    for i = 1, 40 do
        if not procActive(SYM.gProcScr_SALLYCURSOR) then break end
        press(K.B, 4); wait(10); press(K.START, 4); wait(40)
        if i % 4 == 0 and procActive(SYM.gProcScr_SALLYCURSOR) then press(K.A, 4) wait(20) end
    end
    if not waitFor(function()
        return not procActive(SYM.gProcScr_SALLYCURSOR) and faction() == 0 and turn() >= 1
    end, 1200) then return result("FAIL", "could not leave preparations") end
    local function recwait(n, tag)
        for f = 1, n do if f % 5 == 0 then shot(tag) end yield() end
    end
    -- turn 1: Izobai's taunt auto-fires at the player-phase start (normal text speed
    -- so the typewriter + her face read in motion); A-tap slowly to advance it.
    for i = 1, 12 do recwait(24, "trail"); press(K.A, 4) end
    pokeFastConfig()
    local chief = red(CHAR_CHIEF)
    if not chief then return result("FAIL", "chief not found") end
    local goal = { x = chief.x, y = chief.y }
    for t = 1, 18 do
        waitFor(function() return faction() == 0 and not menuOpen() end, 6000, true)
        wait(60)
        for i = 0, 23 do
            local r = unitAt(SYM.gUnitArrayRed, i)
            if r and not isDead(r) then pokeFrail(r); pokeHarmless(r) end
        end
        local braulo = blue(0x01)
        if isDead(braulo) then return result("FAIL", "Braulo died on the march") end
        chief = red(CHAR_CHIEF)
        if chief and not isDead(chief) then
            if math.abs(braulo.x - chief.x) + math.abs(braulo.y - chief.y) == 1 then
                if moveUnit(braulo.x, braulo.y, braulo.x, braulo.y) then
                    chooseAttack(braulo.addr)
                    recwait(70, "trail") -- the death quote
                end
            else
                marchToward(braulo, goal.x, goal.y + 1, 24, 15)
            end
        else
            recwait(30, "trail")
            return result("PASS", "ch01 trail beats recorded (taunt + death)")
        end
        local phase = runEnemyPhase(CH01_PARK)
        if phase == "gameover" then return result("FAIL", "unexpected game over") end
    end
    result("FAIL", "could not reach Izobai")
end

-- RECORDLORD (#42): continuous frame capture of the lord-select flow for the
-- review GIF -- prompt, menu, cursor walk to the last candidate, confirm text
-- typing out, Yes, and the hand-off into the prep screen. Frames tagged "lord"
-- (every 5th frame) are assembled offline.
scenarios.recordlord = function()
    local function recwait(n, tag)
        for f = 1, n do
            if f % 5 == 0 then shot(tag) end
            yield()
        end
    end
    if not winCh00() then return end
    if not waitFor(function() return chapter() == 2 end, 1800) then
        return result("FAIL", "chapter slot 2 never loaded after the ch00 win")
    end
    local atMenu = false
    for i = 1, 60 do
        if menuOpen() and red(CHAR_CHIEF) then atMenu = true break end
        if procActive(SYM.gProcScr_SALLYCURSOR) then break end
        press(K.A, 4)
        recwait(36, "lord")
    end
    if not atMenu then return result("FAIL", "lord-select menu never opened") end
    recwait(90, "lord") -- linger on the freshly opened menu
    for _ = 1, LORD_CANDIDATES - 1 do
        press(K.DOWN, 4)
        recwait(20, "lord") -- visible cursor walk down the cast
    end
    recwait(60, "lord")
    press(K.A, 4)
    recwait(200, "lord") -- confirm text types out in full
    press(K.A, 4)        -- Yes
    for i = 1, 40 do
        if procActive(SYM.gProcScr_SALLYCURSOR) then break end
        press(K.A, 4)
        recwait(36, "lord")
    end
    recwait(300, "lord") -- a beat of the prep screen
    result("PASS", "lord-select flow frames recorded")
end

-- CH01LORD (#42): pick the LAST lord candidate -- benched by default under the
-- 4-slot deploy cap -- and assert the choice is real: the permanent flag is
-- set, the pick is force-deployed onto the field (cap intact), and their death
-- ends in the game-over screen (UnitKill hook -> EVFLAG_GAMEOVER -> AFEV).
scenarios.ch01lord = function()
    if not winCh00() then return end
    if not waitFor(function() return chapter() == 2 end, 1800) then
        return result("FAIL", "chapter slot 2 never loaded after the ch00 win")
    end
    log("in ch01; riding the save menu to the lord-select menu")
    -- The lord menu is the first generic menu while the beginning scene's
    -- goblins are on the map (the post-chapter save screen runs before any
    -- LOAD; the prep screen comes after the menu).
    local atMenu = false
    for i = 1, 60 do
        if menuOpen() and red(CHAR_CHIEF) then atMenu = true break end
        if procActive(SYM.gProcScr_SALLYCURSOR) then break end -- overshot it
        press(K.A, 4)
        wait(36)
    end
    if not atMenu then
        shot("ch01lord-no-menu")
        return result("FAIL", "lord-select menu never opened before preps")
    end
    shot("lord-menu")
    for _ = 1, LORD_CANDIDATES - 1 do press(K.DOWN, 4) wait(8) end
    shot("lord-menu-last")
    press(K.A, 4)
    wait(40)
    shot("lord-confirm")
    -- A answers the [Yes] confirm; then A-tap to the prep screen.
    local prep = false
    for i = 1, 40 do
        if procActive(SYM.gProcScr_SALLYCURSOR) then prep = true break end
        press(K.A, 4)
        wait(36)
    end
    if not prep then
        shot("ch01lord-no-prep")
        return result("FAIL", "prep screen never opened after the lord pick")
    end
    if not eventFlag(LORDSEL_FLAG_BASE + LORD_CANDIDATES - 1) then
        return result("FAIL", "lord-choice permanent flag not set after confirm")
    end
    wait(180)
    shot("ch01lord-prep")
    for i = 1, 40 do
        if not procActive(SYM.gProcScr_SALLYCURSOR) then break end
        press(K.B, 4)
        wait(10)
        press(K.START, 4)
        wait(40)
        if i % 4 == 0 and procActive(SYM.gProcScr_SALLYCURSOR) then press(K.A, 4) wait(20) end
    end
    local fighting = waitFor(function()
        return not procActive(SYM.gProcScr_SALLYCURSOR)
            and faction() == 0 and turn() >= 1
    end, 1200)
    if not fighting then
        shot("ch01lord-prep-stuck")
        return result("FAIL", "could not leave preparations via Fight!")
    end
    wait(120)
    shot("ch01lord-map")
    local lord = blue(CHAR_PINKY)
    if not lord or (lord.state & 0x9) ~= 0 or lord.x == 0xFF then
        return result("FAIL", "chosen lord (char 0x08) is not force-deployed")
    end
    local deployed = 0
    for i = 0, 50 do
        local u = unitAt(SYM.gUnitArrayBlue, i)
        if u and (u.state & 0x9) == 0 and u.x ~= 0xFF then deployed = deployed + 1 end
    end
    if deployed ~= 4 then
        return result("FAIL", string.format(
            "deploy cap broken with forced lord: %d on the field (want 4)", deployed))
    end
    log(string.format("chosen lord fielded at (%d,%d), deployed=%d; feeding them to the goblins",
        lord.x, lord.y, deployed))
    pokeFrail(lord)
    for t = 1, 8 do
        lord = blue(CHAR_PINKY)
        if isDead(lord) or gameOverActive() then break end
        marchToward(lord, 14, 9) -- adjacent to the (14,8) hold-and-attack soldier
        shot("lord-march-turn" .. t)
        local phase = runEnemyPhase()
        if phase == "gameover" then break end
    end
    if waitFor(gameOverActive, 1800, true) then
        shot("lord-game-over")
        return result("PASS",
            "chosen lord: flag set, force-deployed under the 4-cap, death = game over")
    end
    shot("ch01lord-no-gameover")
    log(string.format("debug: EVFLAG_GAMEOVER=%s lordflag=%s dead=%s",
        tostring(eventFlag(0x65)),
        tostring(eventFlag(LORDSEL_FLAG_BASE + LORD_CANDIDATES - 1)),
        tostring(isDead(blue(CHAR_PINKY)))))
    if isDead(blue(CHAR_PINKY)) then
        return result("FAIL", "chosen lord died but NO game over followed")
    end
    result("FAIL", "could not get the chosen lord killed in 8 turns")
end

-- SCENESCH01 (#21): contact-sheet capture of the ch01 Beat-1 Northlook scene --
-- the scenic bg_Fireplace opening, the 4-face roll-call choreography (one face per
-- line via _script_to_message's eviction), and the lord-select hand-off. Wins ch00,
-- rides into slot 2, then drops a screenshot once each page has finished typing,
-- right before the advance press, so every dialogue page + its staged face is on a
-- still. Stops at the prep proc (further A's would toggle Pick Units).
scenarios.scenesch01 = function()
    if not winCh00() then return end
    if not waitFor(function() return chapter() == 2 end, 1800) then
        return result("FAIL", "chapter slot 2 never loaded after the ch00 win")
    end
    log("ch01 Beat-1 scene capture: shot before every advance")
    pokeFastConfig() -- fast text so each A reliably advances one page (cleaner stills)
    for i = 1, 120 do
        if procActive(SYM.gProcScr_SALLYCURSOR) then
            shot("ch01scene-prep")
            return result("PASS", "ch01 Beat-1 scene contact sheet captured")
        end
        wait(40) -- let the (now fast) page finish typing before the still
        shot("ch01scene")
        press(K.A, 4)
    end
    shot("scenesch01-timeout")
    result("FAIL", "prep never opened during ch01 scene capture")
end

-- RECORDCH01 (#21): continuous frame capture (every 6th emulated frame) through the
-- ch01 Beat-1 Northlook scene -> roll-call choreography -> lord-select, so the face
-- fades and the post-scene map reveal can be reviewed as MOTION (a GIF, assembled
-- offline). Default text speed (no pokeFastConfig) so the pacing is what a player sees.
scenarios.recordch01 = function()
    if not winCh00() then return end
    if not waitFor(function() return chapter() == 2 end, 1800) then
        return result("FAIL", "chapter slot 2 never loaded after the ch00 win")
    end
    log("recording ch01 Beat-1 scene frames (op)")
    local prep = false
    for i = 1, 200 do
        if procActive(SYM.gProcScr_SALLYCURSOR) then prep = true break end
        for f = 1, 48 do
            if f % 6 == 0 then shot("op") end
            yield()
        end
        press(K.A, 4)
    end
    if not prep then
        shot("recordch01-no-prep")
        return result("FAIL", "prep never opened (record)")
    end
    return result("PASS", "ch01 Beat-1 scene frames recorded (op)")
end

-- SCENES: contact-sheet capture of every dialogue page (opening card + briefing,
-- boss battle quote, death quote, ending scene). A-only boot -- START would SKIP
-- the Text_BG cutscene wholesale; A merely advances pages -- and a screenshot
-- lands before every advance press so each text page is on at least one frame.
scenarios.scenes = function()
    log("scene capture: A-only boot, shot before every advance")
    local booted = false
    for i = 1, 160 do
        if inChapter() then booted = true; break end
        wait(60) -- let the current page finish typing before the shot
        shot("boot")
        press(K.A, 4)
    end
    if not booted then return result("FAIL", "never reached the map (A-only boot)") end
    wait(120); press(K.B); press(K.B)
    shot("map-loaded")
    local sephek = red(CHAR_SEPHEK)
    if not sephek then return result("FAIL", "Sephek not found in red array") end
    pokeFrail(sephek)
    local scram = blue(CHAR_SCRAMSAX)
    if not scram then return result("FAIL", "Scramsax not found") end
    local tx, ty = sephek.x, sephek.y + 1
    if tileOccupied(tx, ty) then tx, ty = sephek.x - 1, sephek.y end
    if not moveUnit(scram.x, scram.y, tx, ty) then
        return result("FAIL", "could not move Scramsax to the boss")
    end
    press(K.A); wait(20)  -- Attack
    press(K.A); wait(20)  -- target
    press(K.A)            -- confirm -> battle quote -> combat -> death quote -> ending
    for f = 1, 3600 do
        if f % 80 == 0 then shot("fight") end
        if f % 85 == 0 then press(K.A, 3) end
        if chapter() ~= HOST_CHAPTER then
            shot("chapter-advanced")
            return result("PASS", "scene contact sheet captured through the ending")
        end
        yield()
    end
    shot("scenes-timeout")
    result("FAIL", "chapter never ended during scene capture")
end

-- RECORD: continuous frame capture (every 5th emulated frame) through the
-- opening scene ("op" frames), then the boss fight + ending ("bt" frames) --
-- assembled into GIFs offline so dialogue pacing can be reviewed as motion,
-- not single mid-typewriter screenshots. A-only boot like `scenes`.
scenarios.record = function()
    log("recording continuous video frames")
    local function recwait(n, tag)
        for f = 1, n do
            if f % 5 == 0 then shot(tag) end
            yield()
        end
    end
    local booted = false
    for i = 1, 200 do
        if inChapter() then booted = true; break end
        recwait(60, "op")
        press(K.A, 4)
    end
    if not booted then return result("FAIL", "never reached the map (record)") end
    recwait(150, "op")
    press(K.B); press(K.B)
    local sephek = red(CHAR_SEPHEK)
    if not sephek then return result("FAIL", "Sephek not found in red array") end
    pokeFrail(sephek)
    local scram = blue(CHAR_SCRAMSAX)
    if not scram then return result("FAIL", "Scramsax not found") end
    local tx, ty = sephek.x, sephek.y + 1
    if tileOccupied(tx, ty) then tx, ty = sephek.x - 1, sephek.y end
    if not moveUnit(scram.x, scram.y, tx, ty) then
        return result("FAIL", "could not move Scramsax to the boss")
    end
    press(K.A); wait(20)  -- Attack
    press(K.A); wait(20)  -- target
    press(K.A)            -- confirm -> battle quote -> combat -> quotes -> ending
    for f = 1, 4500 do
        if f % 5 == 0 then shot("bt") end
        if f % 110 == 0 then press(K.A, 3) end
        if chapter() ~= HOST_CHAPTER then break end
        yield()
    end
    recwait(40, "bt")
    return result("PASS", "video frames recorded (op + bt)")
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
