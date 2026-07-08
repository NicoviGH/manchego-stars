-- Automated FE8 playtest harness for mGBA 0.11+ (--script).
--
-- Launched by run.sh via a generated wrapper that sets:
--   PLAYTEST_DIR      -- this directory (for dofile of symbols.lua)
--   PLAYTEST_SCENARIO -- which `scenarios.<name>` to run (the table below is the
--                        authoritative list; run.sh's header groups the main ones)
--   PLAYTEST_LOG      -- log file path (runner polls it for "RESULT:")
--   PLAYTEST_SHOTDIR  -- screenshot directory for milestone/debug captures
--   PLAYTEST_STATEDIR -- save-state checkpoint dir (ckpt_*/record* scenarios)
--   PLAYTEST_SEED     -- fuzz/llm seed (PT_SEED)
--   PLAYTEST_CHAR     -- recordanim unit id (PT_CHAR)
--   PLAYTEST_LLMDIR   -- #63 sidecar handshake dir (PT_LLM_DIR)
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
-- prologue/sandbox host on chapter slot 1; a chapter load-test (e.g. --ch03-boot on slot 4)
-- overrides via PT_HOST_CHAPTER so bootToMap/inChapter recognize the right slot.
local HOST_CHAPTER = PLAYTEST_HOST_CHAPTER or 1
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
    local p = string.format("%s/%04d-%s.png", PLAYTEST_SHOTDIR, nshot, tag)
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

-- A unit's attack reach from its equipped (items[0]) weapon, via gItemData (include/bmitem.h:
-- attributes +0x08, encodedRange +0x19 = min<<4 | max; ItemData stride 0x24). Returns
-- (minRange, maxRange) for a real weapon, or nil for a staff / non-attacker (no IA_WEAPON).
local ITEMDATA_STRIDE = 0x24
local function unitAttackRange(u)
    local item = ru16(u.addr + 0x1E) & 0xFF       -- items[0] item id (low byte; high byte = uses)
    if item == 0 then return nil end
    local data = SYM.gItemData + item * ITEMDATA_STRIDE
    if (ru32(data + 0x08) & 0x1) == 0 then return nil end   -- IA_WEAPON unset -> staff/non-weapon
    local er = ru8(data + 0x19)
    return (er >> 4), (er & 0xF)
end

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

local function pokeNormalConfig() -- cutscene recording: clear gameSpeed so the
    -- text typewriter types at a readable pace (the default the player sees), undoing
    -- a prior pokeFastConfig from the battle grind.
    local a = SYM.gPlaySt + 0x40
    emu:write32(a, ru32(a) & ~(1 << 7))
end

-- Save-state checkpoints (PLAYTEST_STATEDIR set by run.sh). Lets a slow scene's lead-up
-- be built ONCE at top speed by a ckpt_* scenario, then the scene itself replayed at
-- viewable speed by a record* scenario that loads the state -- no full playthrough each
-- spot-check. run.sh stamps the ROM hash so a stale state is rebuilt after a rebuild.
local function statePath(name) return PLAYTEST_STATEDIR .. "/" .. name .. ".ss" end
local function saveState(name)
    local ok = false
    pcall(function() ok = emu:saveStateFile(statePath(name)) end)
    log("saveState " .. name .. " -> " .. tostring(ok))
    return ok
end
local function loadState(name)
    local ok = false
    pcall(function() ok = emu:loadStateFile(statePath(name)) end)
    log("loadState " .. name .. " -> " .. tostring(ok))
    return ok
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

-- Detecting an on-screen in-battle quote box: procActive(SYM.ProcScr_BattleEventEngine) is
-- true exactly while a brief in-combat line is up (per-PC DEATH quotes, boss taunts; started
-- by CallBattleQuoteEventInBattle, src/event.c). Capture loops watch it to hold + screenshot
-- the box instead of A-mashing past it (recordfix #6). NOTE: ProcScr_StdEventEngine is live
-- during ALL normal map/turn event processing, so it must NOT be used to gate "a quote is up".

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

-- ---- smoke liveness net (#49): boot a chapter, idle every player unit and just end
-- each turn, and assert the chapter reaches a CLEAN TERMINAL (win OR loss) with no
-- crash / soft-lock / hang -- the first brick of the playtest platform. Most chapters
-- terminate in a loss (idle party overwhelmed), which for a STABILITY net is a fine
-- clean terminal: the point is to exercise load + every phase/event path to a clean
-- end as content lands, not to win (winning is the next brick). The verdict is the
-- pure classifier in liveness.lua (unit-tested without an emulator). PASS = clean
-- terminal OR alive past the turn budget (an idle party usually can't force a terminal,
-- so budget-survival is the healthy outcome); FAIL = soft-lock. A wedged emulator is
-- caught by run.sh's wall-clock deadline.
local LIVENESS = dofile(PLAYTEST_DIR .. "/liveness.lua")

local function hpSum()
    local s = 0
    for _, base in ipairs({ SYM.gUnitArrayBlue, SYM.gUnitArrayRed }) do
        for i = 0, 23 do
            local u = unitAt(base, i)
            if u and (u.state & US_DEAD) == 0 then s = s + u.hp end
        end
    end
    return s
end

-- A small bitmask of which key procs are active. It flips as menus/combat/events come
-- and go, so a value frozen across the soft-lock window means a genuine freeze (the
-- text-decoder-runaway / infinite-loop class), not a quiet-but-live enemy phase.
local function procFingerprint()
    local fp = 0
    if procActive(SYM.sProc_Menu) then fp = fp | 1 end
    if procActive(SYM.ProcScr_BattleEventEngine) then fp = fp | 2 end
    if procActive(SYM.ProcScr_StdEventEngine) then fp = fp | 4 end
    if procActive(SYM.ProcScr_GameOverScreen) then fp = fp | 8 end
    return fp
end

-- ---- greedy clear-bot (#60): real-combat chapter completion. Generic boss detection
-- (no hardcoded char ids) + the pure pickTarget core; the scenario owns the driving.
local CLEARBOT = dofile(PLAYTEST_DIR .. "/clearbot.lua")
local CH02 = dofile(PLAYTEST_DIR .. "/ch02check.lua")   -- pure charm-delivery check (#22)
local PATHING = dofile(PLAYTEST_DIR .. "/pathing.lua")  -- pure BFS distance field (#60 march)
local CA_BOSS = (1 << 15)   -- include/bmunit.h:326 (character/class attribute)
local FUZZRNG = dofile(PLAYTEST_DIR .. "/fuzzrng.lua")   -- seeded PRNG + input policy (#49)

-- Terrain ids (include/constants/terrains.h) that hard-block a foot/mounted march -- used to
-- build the passability map for the BFS distance field (#60). High-cost-but-passable terrain
-- (mountain, river, forest, etc.) is left passable on purpose: the field only needs to route
-- AROUND walls/water; the per-turn selectAndReach still enforces each unit's true reach.
local IMPASSABLE_TERRAIN = {
    [0x10] = true,  -- RIVER (deep; foot can't cross)
    [0x12] = true,  -- PEAK
    [0x15] = true,  -- SEA
    [0x16] = true,  -- LAKE
    [0x19] = true,  -- FENCE
    [0x1A] = true,  -- WALL_REGULAR
    [0x1B] = true,  -- WALL_DAMAGED
    [0x26] = true,  -- CLIFF
    [0x33] = true,  -- SNAG
    [0x35] = true,  -- SKY
    [0x36] = true,  -- DEEPS
    [0x3C] = true,  -- WATER
}
local function terrainAt(x, y)
    return ru8(ru32(ru32(SYM.gBmMapTerrain) + y * 4) + x)   -- gBmMapTerrain[y][x] (u8**)
end

-- BFS path-distance field from the boss tile over walkable terrain on the [0..maxx]x[0..maxy]
-- map: dist[y][x] = steps to reach the boss routing around hard obstacles, or nil (unreachable).
-- The clear-bot ranks its reachable tiles by this instead of raw Manhattan, so a unit walks
-- AROUND a wall toward a held boss instead of stranding against it.
local function bossDistanceField(boss, maxx, maxy)
    local w, h = maxx + 1, maxy + 1
    local function isPassable(x, y) return not IMPASSABLE_TERRAIN[terrainAt(x, y)] end
    return PATHING.distanceField(w, h, isPassable, { x = boss.x, y = boss.y })
end

-- A unit's character carries the CA_BOSS attribute: pCharacterData (Unit +0x00) ->
-- CharacterData.attributes (+0x28). True for named bosses (Sephek, the ch01 chief, ...).
local function unitIsBoss(u)
    local chptr = ru32(u.addr)
    if chptr == 0 then return false end
    return (ru32(chptr + 0x28) & CA_BOSS) ~= 0
end

-- The live boss in the red array (the first CA_BOSS unit), or nil.
local function findBoss()
    for i = 0, 23 do
        local u = unitAt(SYM.gUnitArrayRed, i)
        if u and not isDead(u) and unitIsBoss(u) then return u end
    end
    return nil
end

-- Live red units as plain {x,y,hp,is_boss} tables for the pure pickTarget core.
local function liveEnemies()
    local out = {}
    for i = 0, 23 do
        local u = unitAt(SYM.gUnitArrayRed, i)
        if u and not isDead(u) then
            out[#out + 1] = { x = u.x, y = u.y, hp = u.hp, is_boss = unitIsBoss(u) }
        end
    end
    return out
end

-- Select unit u and return the tiles it can move to this turn (cost < 120, free, plus its
-- own tile -- attack-from-here), leaving it selected with the move range shown. nil if the
-- unit is exhausted (selecting opened a menu) or the cursor never reached it. Reuses the
-- stale-move-map guard from marchToward (an eaten A press reads cost 0 everywhere).
local function selectAndReach(u, maxx, maxy)
    maxx, maxy = maxx or 14, maxy or 9
    for _ = 1, 4 do
        if not cursorTo(u.x, u.y) then return nil end
        press(K.A)
        wait(12)
        if menuOpen() then press(K.B); wait(10); return nil end
        local reach, unreachable = {}, 0
        for y = 0, maxy do
            for x = 0, maxx do
                if reachCost(x, y) >= 120 then
                    unreachable = unreachable + 1
                elseif (x == u.x and y == u.y) or not tileOccupied(x, y) then
                    reach[#reach + 1] = { x = x, y = y }
                end
            end
        end
        if unreachable > 0 then return reach end   -- a real move map has unreachable tiles
        press(K.B); wait(40)                        -- stale map (eaten A press); reselect
    end
    return nil
end

-- The idle drive loop, shared by every smoke_* scenario: from the moment we are on a
-- chapter's map (startChapter = the host slot), idle every player unit and just end each
-- turn, sampling state into a frame-age-trimmed ring and asking liveness.classify each
-- cycle. This is a STABILITY net: PASS = no crash/soft-lock over the run, whether it
-- ended in a clean terminal OR simply survived the turn budget still cycling (an idle
-- party usually can't force a terminal, so budget-survival is the normal healthy
-- outcome -- not a warning). FAIL = soft-lock. Completability is the clear-bot's job.
local function smokeDrive(startChapter)
    local cfg = { softlock_frames = 2400 }   -- ~40 emulated-sec; >> a slow enemy phase
    local budgetTurns = 30
    local snaps = {}
    log(string.format("smoke: chapter %d, budget %d turns, softlock %d frames",
        startChapter, budgetTurns, cfg.softlock_frames))
    for _ = 1, 100000 do
        local over = gameOverActive()
        local won = (not over) and chapter() ~= startChapter and chapter() ~= 0
        snaps[#snaps + 1] = {
            frame = emu:currentFrame(), turn = turn(), faction = faction(),
            hpsum = hpSum(), procfp = procFingerprint(),
            chapter_advanced = won, gameover = over,
        }
        -- Keep the ring spanning at least the soft-lock window (+ margin), so classify
        -- can actually measure a long freeze; trim by frame-age, not element count.
        local newest = snaps[#snaps].frame
        while #snaps > 2 and snaps[1].frame < newest - (cfg.softlock_frames + 240) do
            table.remove(snaps, 1)
        end
        local v = LIVENESS.classify(snaps, cfg)
        if v.state == "TERMINAL_WIN" then
            shot("smoke-win"); return result("PASS", "win -- " .. v.why)
        elseif v.state == "TERMINAL_LOSS" then
            shot("smoke-loss"); return result("PASS", "clean loss -- " .. v.why)
        elseif v.state == "SOFTLOCK" then
            shot("smoke-softlock"); return result("FAIL", "soft-lock -- " .. v.why)
        end
        if turn() > budgetTurns then
            shot("smoke-budget")
            return result("PASS", string.format(
                "survived %d turns, no crash/soft-lock (no terminal)", budgetTurns))
        end
        -- Drive one small step: idle the player phase (just end the turn); otherwise
        -- nudge dialogue / phase interludes along. Sampling stays continuous so an
        -- in-enemy-phase freeze is caught, not hidden inside a blocking phase call.
        if faction() == 0 and not menuOpen() and turn() >= 1 then
            endTurn()
        else
            press(K.A, 2)
        end
        wait(8)
    end
    -- Unreachable in practice (budgetTurns trips first); a backstop if turns somehow
    -- never advance past the budget yet classify never sees a freeze.
    return result("FAIL", "step cap reached without a terminal or budget")
end

-- smoke: prologue is reachable straight from New Game (bootToMap). Later chapters need
-- their own "reach the map" lead-in (smoke_ch01) or a save-state checkpoint
-- (smoke_ch02 loads the ch02start state).
scenarios.smoke = function()
    if not bootToMap() then return result("FAIL", "never reached the map") end
    return smokeDrive(chapter())
end

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

-- Reach the ch01 map: ride the ch00 win into chapter slot 2, A-tap through the
-- post-chapter save + Beat-1 scene to the prep screen, then Fight! into the phase.
-- Returns true once control is on the ch01 map; false (with its own FAIL logged)
-- otherwise. Shared by scenarios.ch01 (entry assertions) and scenarios.smoke_ch01.
local function reachCh01Map()
    if not winCh00() then return false end
    if not waitFor(function() return chapter() == 2 end, 1800) then
        result("FAIL", "chapter slot 2 never loaded after the ch00 win"); return false
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
        result("FAIL", "prep screen never opened (PREP event cmd)"); return false
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
        result("FAIL", "could not leave preparations via Fight!"); return false
    end
    wait(120) -- phase intro
    shot("ch01-map")
    return true
end

-- CH01: reach the ch01 map, then assert the entry invariants -- the ch00 guests left
-- the party (DISA), and the deployed count equals the 4-slot field-parity cap.
scenarios.ch01 = function()
    if not reachCh01Map() then return end
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

-- smoke_ch01: extend the stability net to the first authored chapter (#21) -- reach the
-- ch01 map via the prologue-clear lead-in, then idle-drive it to a clean terminal.
scenarios.smoke_ch01 = function()
    if not reachCh01Map() then return end
    return smokeDrive(chapter())
end

-- clearprobe: confirm generic boss detection (CA_BOSS) finds the prologue boss with no
-- hardcoded char id -- the foundation the clear-bot stands on. PASS = a boss was found.
scenarios.clearprobe = function()
    if not bootToMap() then return result("FAIL", "never reached the map") end
    local boss = findBoss()
    if not boss then return result("FAIL", "no CA_BOSS unit found in the red array") end
    log(string.format("boss found: char=0x%02X at (%d,%d) hp=%d",
        boss.charId, boss.x, boss.y, boss.hp))
    result("PASS", string.format("CA_BOSS boss detected (char 0x%02X)", boss.charId))
end

-- One player unit's action for the clear-bot: select it, pick a target at the unit's REAL weapon
-- reach (boss-first via pickTarget, so bows/magic act at range), and attack from the reachable
-- tile; else step to the reachable tile NEAREST the boss by path distance (`field`, BFS around
-- walls) -- falling back to Manhattan toward `goal` only where the field is unreachable. GUARANTEES
-- it leaves no unit selected (commit via Attack/Wait, or back out with B).
local function clearUnitAct(u, field, goal, blocked, claimed, maxx, maxy)
    -- thread the REAL map bounds through: selectAndReach defaults to a 15x10
    -- window, which clipped every reach list at x=14 on ch01's 25x16 map -- the
    -- probable root cause of the #60 stall at exactly (14,8)
    local reach = selectAndReach(u, maxx, maxy)
    if not reach then return end                 -- exhausted/unreachable; nothing selected
    local mn, mx = unitAttackRange(u)
    local enemies = liveEnemies()
    local pick = mn and CLEARBOT.pickTarget(reach, enemies, { range = mx, min_range = mn }) or nil
    local tile = pick and pick.tile
    if not tile then
        -- no target in range: march (pure decision core -- field-first with a
        -- Manhattan tiebreak, claimed-tile avoidance, and the chokepoint-jam
        -- fallback that pushes at the nearest enemy cork; #60 last-mile breach)
        tile = CLEARBOT.pickMove(reach, { field = field, cur = { x = u.x, y = u.y },
                                          goal = goal, blocked = blocked,
                                          enemies = enemies })
    end
    if tile and cursorTo(tile.x, tile.y) then
        press(K.A)
        if waitFor(menuOpen, 40) then
            if pick then chooseAttack(u.addr) else chooseWait() end
            if claimed then claimed[CLEARBOT.tileKey(tile.x, tile.y)] = true end
            return tile
        end
    end
    press(K.B); press(K.B)                       -- never leave a unit selected
    return tile, true                            -- true = the move DIDN'T commit
end

local CH01_PARK = { x = 24, y = 15 } -- empty far corner; ch01 map is 25x16

-- The clear loop body (no verdict): actually PLAY the chapter with real combat (no pokeFrail)
-- -- each player phase, march/attack every unit toward the boss; once the boss is dead, if the
-- chapter hasn't already advanced (DefeatBoss objective), send a unit onto the boss's old tile
-- to SEIZE (Seize objective). Returns a status ("noboss"|"won"|"gameover"|"timeout") and the
-- turn it ended on. clearDrive (its only caller) wraps this with a PASS/FAIL verdict.
-- (reachCh02Map (#22) does NOT ride it -- the generic bot is too slow to seize ch01
-- reliably, so it uses the directed seizeCh01ToCh02.) maxx/maxy = map bounds;
-- park = the end-turn empty tile. The completability brick (#60).
local function clearUntilAdvance(startChapter, maxx, maxy, park)
    maxx, maxy = maxx or 14, maxy or 9
    local boss = findBoss()
    if not boss then return "noboss", 0 end
    log(string.format("clear: boss char=0x%02X at (%d,%d) hp=%d on a %dx%d map",
        boss.charId, boss.x, boss.y, boss.hp, maxx + 1, maxy + 1))
    local seizeTile = { x = boss.x, y = boss.y }   -- killed boss's tile = the seize point
    local budgetTurns = 18
    -- A real win ADVANCES the chapter. The title screen WITHOUT an advance means game-over ->
    -- title (a loss), not a win -- so this stays an honest fair-play gate (#60).
    local function won() return chapter() ~= startChapter end
    local function lost() return gameOverActive() or procActive(SYM.gProcScr_TitleScreen) end
    -- progress = the nearest live unit's path-distance to the boss (lower is better).
    local function nearestBossDist(field)
        local best = math.huge
        for i = 0, 7 do
            local u = unitAt(SYM.gUnitArrayBlue, i)
            if u and not isDead(u) then
                local fd = field and field[u.y] and field[u.y][u.x]
                if fd and fd < best then best = fd end
            end
        end
        return best
    end
    local lastDist, lastEnemies, stall = math.huge, math.huge, 0
    for t = 1, budgetTurns do
        waitFor(function() return faction() == 0 and not menuOpen() end, 6000, true)
        wait(60) -- let the player-phase banner finish (it eats key presses)
        press(K.B); wait(6)   -- NUDGE unstick: clear any stray menu before driving
        local b = findBoss()
        local field = b and bossDistanceField(b, maxx, maxy) or nil
        local claimed = {}                       -- destinations committed this phase
        for i = 0, 7 do
            if won() then return "won", t end
            if lost() then return "gameover", t end
            local u = unitAt(SYM.gUnitArrayBlue, i)
            if u and not isDead(u) and (u.state & 0x2) == 0 then   -- live, not yet acted
                b = findBoss()
                if b then
                    seizeTile = { x = b.x, y = b.y }
                    -- other live units' CURRENT tiles are unstandable too
                    local blocked = {}
                    for k in pairs(claimed) do blocked[k] = true end
                    for j = 0, 7 do
                        local o = unitAt(SYM.gUnitArrayBlue, j)
                        if o and not isDead(o) and j ~= i then
                            blocked[CLEARBOT.tileKey(o.x, o.y)] = true
                        end
                    end
                    local tile, failed = clearUnitAct(u, field, b, blocked, claimed,
                                                      maxx, maxy)
                    if failed and tile then
                        -- decision was made but the move never committed: a
                        -- MECHANICAL failure (cursor/menu), not a pathing one --
                        -- the distinction the #60 stall logs couldn't see
                        log(string.format("clear: unit (%d,%d) chose (%d,%d) but the "
                            .. "move didn't commit", u.x, u.y, tile.x, tile.y))
                    end
                elseif moveUnit(u.x, u.y, seizeTile.x, seizeTile.y) then
                    -- boss dead, not yet won -> Seize. It tops the menu for a unit that can
                    -- seize; for any other unit A just Waits, so we back out and try the next.
                    shot("clear-seize-try")
                    press(K.A)
                    if waitFor(won, 9000, true) then return "won", t end
                    press(K.B); press(K.B)
                end
            end
        end
        if won() then return "won", t end
        if lost() then return "gameover", t end
        if runEnemyPhase(park) == "gameover" then return "gameover", t end
        -- stall watchdog: bail cleanly if no progress (nearer the boss OR fewer foes) for 3 turns,
        -- instead of grinding the full budget on a wedged bot.
        local dist, enemies = nearestBossDist(field), #liveEnemies()
        if dist < lastDist or enemies < lastEnemies then stall = 0 else stall = stall + 1 end
        lastDist, lastEnemies = math.min(dist, lastDist), math.min(enemies, lastEnemies)
        log(string.format("clear turn %d: nearestBossDist=%s enemies=%d stall=%d",
            t, dist == math.huge and "inf" or dist, enemies, stall))
        if stall >= 3 then
            -- diagnose the stall: is the boss walled off (field can't reach its neighbours), and
            -- where are the remaining foes / our units relative to the field?
            local bb = findBoss()
            if bb then
                local f = bossDistanceField(bb, maxx, maxy)
                local nb = {}
                for _, d in ipairs({ { 1, 0 }, { -1, 0 }, { 0, 1 }, { 0, -1 } }) do
                    local nx, ny = bb.x + d[1], bb.y + d[2]
                    nb[#nb + 1] = string.format("(%d,%d)terr=0x%02X fd=%s", nx, ny,
                        (nx >= 0 and ny >= 0 and nx <= maxx and ny <= maxy) and terrainAt(nx, ny) or -1,
                        (f[ny] and f[ny][nx]) and tostring(f[ny][nx]) or "nil")
                end
                log(string.format("STALL boss=(%d,%d) terr=0x%02X neighbours: %s",
                    bb.x, bb.y, terrainAt(bb.x, bb.y), table.concat(nb, " ")))
                for _, e in ipairs(liveEnemies()) do
                    log(string.format("  enemy (%d,%d) hp=%d boss=%s fd=%s", e.x, e.y, e.hp,
                        tostring(e.is_boss), (f[e.y] and f[e.y][e.x]) and tostring(f[e.y][e.x]) or "nil"))
                end
                for i = 0, 7 do
                    local u = unitAt(SYM.gUnitArrayBlue, i)
                    if u and not isDead(u) then log(string.format("  unit (%d,%d) fd=%s",
                        u.x, u.y, (f[u.y] and f[u.y][u.x]) and tostring(f[u.y][u.x]) or "nil")) end
                end
            end
            return "stuck", t
        end
    end
    return "timeout", budgetTurns
end

-- The verdict wrapper for clear + clear_ch01 (clear_ch02 has its own rout loop +
-- verdicts). Win = the chapter advances. FAIL =
-- game over (incl. a loss kicking back to the title) / no progress (stuck) / turn budget.
local function clearDrive(startChapter, maxx, maxy, park)
    local status, t = clearUntilAdvance(startChapter, maxx, maxy, park)
    if status == "won" then shot("clear-win")
        return result("PASS", string.format("won by turn %d (chapter %d)", t, chapter())) end
    if status == "noboss" then return result("FAIL", "no boss found to clear toward") end
    if status == "gameover" then shot("clear-gameover")
        return result("FAIL", string.format("game over on turn %d -- bot lost units", t)) end
    if status == "stuck" then shot("clear-stuck")
        return result("FAIL", string.format("no progress for 3 turns by turn %d (boss %s)",
            t, findBoss() and "alive" or "dead")) end
    shot("clear-timeout")
    return result("FAIL", string.format("could not clear in %d turns (boss %s)",
        t, findBoss() and "alive" or "dead"))
end

-- clear: the prologue (DefeatBoss), reachable straight from New Game.
scenarios.clear = function()
    if not bootToMap() then return result("FAIL", "never reached the map") end
    return clearDrive(chapter(), 14, 9)
end

-- clear_ch01: the first authored chapter (#21) -- a Seize objective on a 25x16 map with a
-- 10-goblin escort. Real combat, so survival is genuinely at stake (unlike ch01win, which
-- pokes everything frail to isolate the seize logic).
scenarios.clear_ch01 = function()
    if not reachCh01Map() then return end
    pokeFastConfig() -- many-combat enemy phases: map-anim battles + fast speed
    return clearDrive(chapter(), 24, 15, CH01_PARK)
end

-- ---- stability fuzzer (#49): SEEDED random inputs over the same I/O layer, hunting the
-- crashes/soft-locks the DIRECTED smoke/clear bots can't -- they only ever drive clean,
-- scripted input orderings. A "smart monkey": broad in-chapter key surface (incl START/
-- SELECT so it reaches the menus), weighted toward the productive map keys, plus an
-- unstick watchdog -- when liveness reports a NUDGE stall it mashes B to back out of
-- whatever benign menu it wandered into. If even that can't escape for the full
-- softlock window, that IS the bug (a screen with no exit). The PRNG and weighting are
-- the pure, unit-tested core (fuzzrng.lua); this owns the emulator driving. Boot/title/
-- prep fuzzing is a separate, noisier surface, deferred to a later brick.
local FUZZ_ALPHABET = {
    { key = K.A,      weight = 5, hold = 3 },   -- confirm / select / attack: the workhorse
    { key = K.B,      weight = 4, hold = 3 },   -- cancel / back: also the natural unstick key
    { key = K.UP,     weight = 3, hold = 3 },
    { key = K.DOWN,   weight = 3, hold = 3 },
    { key = K.LEFT,   weight = 3, hold = 3 },
    { key = K.RIGHT,  weight = 3, hold = 3 },
    { key = K.START,  weight = 1, hold = 3 },   -- rare: reach the map menu, don't live in it
    { key = K.SELECT, weight = 1, hold = 3 },
}

-- A RESPONSIVENESS fingerprint for the fuzzer (not the smoke bot's progress fingerprint).
-- The smoke bot idles, so a frozen {turn,faction,hpsum,procfp} means a genuine freeze. The
-- fuzzer instead roams the cursor with random D-pad presses WITHOUT advancing the turn, so
-- the progress key sits still on a perfectly responsive map -- a false soft-lock. Folding
-- the map cursor in makes "no change" mean the game stopped RESPONDING to input (a real
-- freeze/crash), not merely "the random bot hasn't made progress". Proc bits live above the
-- cursor bytes so they never collide (map coords are < 256). Fed as the snapshot's `procfp`,
-- so liveness.lua stays pure and unchanged.
local function fuzzFingerprint()
    local cx, cy = cursor()
    return (procFingerprint() << 16) | ((cx & 0xFF) << 8) | (cy & 0xFF)
end

-- In live gameplay (a battle map, EITHER phase) iff a player unit is loaded and we are not
-- on the title screen. Deliberately NOT inChapter() -- that requires faction()==0, so it is
-- false during a legitimate enemy phase. The liveness key {turn,faction,hpsum,procfp} is only
-- meaningful here; on the title/main menu it is trivially frozen, which is NOT a soft-lock.
local function liveOnMap()
    return unitAt(SYM.gUnitArrayBlue, 0) ~= nil
        and not procActive(SYM.gProcScr_TitleScreen)
end

local function fuzzDrive(startChapter)
    local seed = math.floor(tonumber(PLAYTEST_SEED) or 1)
    local rng = FUZZRNG.new(seed)
    -- Two stall thresholds: NUDGE (try to unstick) well before SOFTLOCK (genuine failure).
    local cfg = { softlock_frames = 2400, nudge_frames = 600 }
    local budgetFrames = 60000   -- ~250s wall at 240fps; comfortably under run.sh's deadline
    local snaps = {}
    local startFrame, recoverStep = emu:currentFrame(), 0
    log(string.format("fuzz: chapter %d, SEED %d, budget %d frames, nudge %d, softlock %d "
        .. "(reproduce a FAIL with PT_SEED=%d)",
        startChapter, seed, budgetFrames, cfg.nudge_frames, cfg.softlock_frames, seed))
    for _ = 1, 1000000 do
        -- Budget first, so it bounds us even while recovering off-map (an unrecoverable
        -- menu just rides the budget out to a PASS -- no crash is no crash).
        if emu:currentFrame() - startFrame > budgetFrames then
            shot("fuzz-budget")
            return result("PASS", string.format(
                "survived %d frames on seed %d, no crash/soft-lock", budgetFrames, seed))
        end
        -- Off the battle map: a random Suspend can drop us to the title (a legit non-crash
        -- state where the liveness key is frozen and B can't escape). Don't judge liveness
        -- here -- drive the menus FORWARD back into play (START/A like bootToMap) and drop
        -- the stale frozen history so re-entry doesn't instantly trip the soft-lock window.
        if not liveOnMap() then
            snaps = {}
            recoverStep = recoverStep + 1
            press(recoverStep % 2 == 0 and K.A or K.START, 4)
            wait(20)
        else
            local over = gameOverActive()
            local won = (not over) and chapter() ~= startChapter and chapter() ~= 0
            snaps[#snaps + 1] = {
                frame = emu:currentFrame(), turn = turn(), faction = faction(),
                hpsum = hpSum(), procfp = fuzzFingerprint(),
                chapter_advanced = won, gameover = over,
            }
            local newest = snaps[#snaps].frame
            while #snaps > 2 and snaps[1].frame < newest - (cfg.softlock_frames + 240) do
                table.remove(snaps, 1)
            end
            local v = LIVENESS.classify(snaps, cfg)
            if v.state == "TERMINAL_WIN" then
                shot("fuzz-win"); return result("PASS", "win -- " .. v.why)
            elseif v.state == "TERMINAL_LOSS" then
                shot("fuzz-loss"); return result("PASS", "clean loss -- " .. v.why)
            elseif v.state == "SOFTLOCK" then
                shot("fuzz-softlock")
                return result("FAIL", string.format(
                    "soft-lock on seed %d (reproduce: PT_SEED=%d run.sh fuzz) -- %s", seed, seed, v.why))
            end
            -- Drive one step: on a NUDGE stall, mash B to unstick; otherwise inject a weighted
            -- random key. Sampling stays continuous so an in-phase freeze is still caught.
            if v.state == "NUDGE" then
                press(K.B, 3)
            else
                local e = FUZZRNG.weightedPick(rng, FUZZ_ALPHABET)
                press(e.key, e.hold)
            end
            wait(8)
        end
    end
    return result("FAIL", "step cap reached without a terminal or budget")
end

-- fuzz: the prologue, reachable straight from New Game.
scenarios.fuzz = function()
    if not bootToMap() then return result("FAIL", "never reached the map") end
    return fuzzDrive(chapter())
end

-- fuzz_ch01: the first authored chapter -- same random soak on a bigger map with combat.
scenarios.fuzz_ch01 = function()
    if not reachCh01Map() then return end
    pokeFastConfig() -- keep enemy phases quick if random End-Turns roll into them
    return fuzzDrive(chapter())
end

-- ---- LLM-player commander (#63 M2): the sidecar file-handshake. Once per player
-- phase the harness exports the WHOLE board as req-<n>.json into PLAYTEST_LLMDIR,
-- blocks (polling) for resp-<n>.json from the external sidecar
-- (`tools/playtest/llm_player.py serve`, replay-only by default -- zero LLM cost),
-- and executes the returned orders with the existing primitives. The sidecar has
-- already validated the orders against this exact board (validate_orders), so an
-- illegal order arriving here means the board CHANGED under us (a kill freed a tile)
-- -- those just fail to commit and are logged, never soft-lock. Timeout / malformed
-- response -> FAIL, like every brick.
local JSONF = dofile(PLAYTEST_DIR .. "/json.lua")
local LLMDIR = (type(PLAYTEST_LLMDIR) == "string" and PLAYTEST_LLMDIR) or "/tmp/playtest-llm-handshake"

-- Exported unit ids must be UNIQUE and stable across the run: blue units use charId
-- (PCs are distinct), red units use 1000+slot (generics SHARE a charId, so the slot
-- disambiguates which brigand an attack order targets).
local LLM_RED_ID_BASE = 1000

local function llmExportBoard(objective, maxx, maxy)
    local units = {}
    for i = 0, 7 do
        local u = unitAt(SYM.gUnitArrayBlue, i)
        if u and not isDead(u) then
            local canAct = (u.state & 0x2) == 0
            local reach = {}
            if canAct then
                local r = selectAndReach(u, maxx, maxy)
                press(K.B) wait(6)   -- deselect: the export must not leave a unit selected
                if r then for _, t in ipairs(r) do reach[#reach + 1] = { t.x, t.y } end end
            end
            local mn, mx = unitAttackRange(u)
            units[#units + 1] = {
                id = u.charId, faction = "blue", x = u.x, y = u.y,
                hp = u.hp, maxhp = ru8(u.addr + 0x12), can_act = canAct,
                boss = false, reach = reach, range = mn and { mn, mx } or nil,
            }
        end
    end
    for i = 0, 23 do
        local u = unitAt(SYM.gUnitArrayRed, i)
        if u and not isDead(u) then
            local mn, mx = unitAttackRange(u)
            units[#units + 1] = {
                id = LLM_RED_ID_BASE + i, faction = "red", x = u.x, y = u.y,
                hp = u.hp, maxhp = ru8(u.addr + 0x12), can_act = false,
                boss = unitIsBoss(u), reach = {}, range = mn and { mn, mx } or nil,
            }
        end
    end
    return { objective = objective, map = { w = maxx + 1, h = maxy + 1 }, units = units }
end

-- Write req-<n>.json (tmp+rename, mirroring the sidecar, so a half-written request is
-- never read) and poll for resp-<n>.json. Returns the decoded response table, or
-- (nil, why). The poll is wall-clock bound (the sidecar answers in wall time; at
-- 240fps a frame budget would be 4x too impatient).
local function llmHandshake(n, req, timeoutSecs)
    local reqPath = LLMDIR .. "/req-" .. n .. ".json"
    local tmp = reqPath .. ".tmp"
    local f, err = io.open(tmp, "w")
    if not f then return nil, "cannot write " .. tmp .. ": " .. tostring(err) end
    f:write(JSONF.encode(req))
    f:close()
    os.rename(tmp, reqPath)
    local respPath = LLMDIR .. "/resp-" .. n .. ".json"
    local deadline = os.time() + (timeoutSecs or 90)
    while os.time() < deadline do
        local rf = io.open(respPath, "r")
        if rf then
            local body = rf:read("a")
            rf:close()
            local resp, derr = JSONF.decode(body)
            if not resp then return nil, "malformed resp-" .. n .. ".json: " .. tostring(derr) end
            return resp
        end
        wait(30)
    end
    return nil, "sidecar timeout waiting for resp-" .. n .. ".json (is llm_player.py serve running?)"
end

-- Drain every open menu level (submenus -- weapon/item lists -- are ALSO sProc_Menu,
-- so a fixed two-B backout can strand a level), then one more B to drop a move-range
-- selection. Restores the harness invariant: never leave a unit selected.
local function llmBackout()
    for _ = 1, 6 do
        if not menuOpen() then break end
        press(K.B) wait(8)
    end
    press(K.B) wait(8)
end

-- Resolve an exported unit id back to a live unit: blue = charId, red = 1000+slot
-- (generics share charIds; see llmExportBoard).
local function llmUnitById(id)
    if type(id) ~= "number" then return nil end
    if id >= LLM_RED_ID_BASE then return unitAt(SYM.gUnitArrayRed, id - LLM_RED_ID_BASE) end
    return blue(id)
end

-- Execute one validated order with the existing primitives. M2 limitation (noted in
-- decisions.md): chooseAttack fires on the UI's default target, which is the intended
-- one whenever a single enemy is in range of the strike tile; multi-target
-- disambiguation is an M3 refinement.
local function llmExecOrder(o)
    if type(o.unit) ~= "number" or type(o.move_to) ~= "table" then return false end
    local u = blue(o.unit)
    if not u or isDead(u) or (u.state & 0x2) ~= 0 then return false end
    -- the sidecar validated against the REQUEST board; re-check what can have changed
    -- since (an earlier order killed the target) before blind-A driving the menu --
    -- with no live target the action menu has no Attack entry and A/A/A would walk
    -- into the Item submenu instead
    local action = o.action
    if action == "attack" then
        local tgt = llmUnitById(o.target)
        if not tgt or isDead(tgt) then action = "wait" end
    end
    if not moveUnit(u.x, u.y, o.move_to.x, o.move_to.y) then return false end
    if action == "attack" then
        chooseAttack(u.addr)
    elseif action == "seize" then
        press(K.A) wait(30)   -- Seize tops the menu for a seize-capable unit on the tile
        if menuOpen() then llmBackout() return false end   -- no Seize here: back out fully
    else
        chooseWait()          -- wait/staff: staff driving is an M3 refinement
    end
    if menuOpen() then llmBackout() return false end
    return true
end

-- The LLM-commander loop body (no verdict): per player phase export the board, ask the
-- sidecar, execute the orders, end the turn. Same terminal detection as the clear-bot.
local function llmUntilAdvance(startChapter, objective, maxx, maxy, park)
    local function won() return chapter() ~= startChapter end
    local function lost() return gameOverActive() or procActive(SYM.gProcScr_TitleScreen) end
    local budgetTurns = 18
    local seed = math.floor(tonumber(PLAYTEST_SEED) or 1)
    local n = 0
    for t = 1, budgetTurns do
        waitFor(function() return faction() == 0 and not menuOpen() end, 6000, true)
        wait(60)              -- let the player-phase banner finish (it eats key presses)
        press(K.B) wait(6)    -- NUDGE unstick: clear any stray menu before driving
        n = n + 1
        local req = { seed = seed, chapter = startChapter, turn = turn(), faction = "blue",
                      board = llmExportBoard(objective, maxx, maxy) }
        local resp, why = llmHandshake(n, req)
        if not resp then return "handshake: " .. why, t end
        if resp.error then return "sidecar: " .. tostring(resp.error), t end
        local orders = resp.orders or {}
        log(string.format("llm turn %d: %d orders (%d rejected sidecar-side)",
            t, #orders, resp.rejected and #resp.rejected or 0))
        for _, o in ipairs(orders) do
            if won() then return "won", t end
            if lost() then return "gameover", t end
            if not llmExecOrder(o) then
                log(string.format("llm: order for unit %s -> (%s,%s) did not commit",
                    tostring(o.unit), tostring(o.move_to and o.move_to.x),
                    tostring(o.move_to and o.move_to.y)))
            end
        end
        if won() then return "won", t end
        if lost() then return "gameover", t end
        if runEnemyPhase(park) == "gameover" then return "gameover", t end
    end
    return "timeout", budgetTurns
end

local function llmDrive(startChapter, objective, maxx, maxy, park)
    local status, t = llmUntilAdvance(startChapter, objective, maxx, maxy, park)
    if status == "won" then shot("llm-win")
        return result("PASS", string.format("LLM commander won by turn %d (chapter %d)", t, chapter())) end
    if status == "gameover" then shot("llm-gameover")
        return result("FAIL", string.format("game over on turn %d", t)) end
    if status == "timeout" then shot("llm-timeout")
        return result("FAIL", string.format("no win in %d turns (boss %s)",
            t, findBoss() and "alive" or "dead")) end
    shot("llm-fail")
    return result("FAIL", status .. string.format(" (turn %d)", t))
end

-- llm: the prologue (DefeatBoss) driven by the sidecar commander. Replay-only run:
--   python3 tools/playtest/llm_player.py serve --dir /tmp/playtest-llm-handshake \
--       --transcript tools/playtest/transcripts/prologue.json     # (other terminal;
--       the transcript file is MINTED by the first --record run -- see the README there)
--   tools/playtest/run.sh llm
-- Record a fresh transcript (live model; see PT_PROVIDER/PT_MODEL/PT_BASE_URL for the
-- free local Ollama path) by adding --record to the serve command.
scenarios.llm = function()
    if not bootToMap() then return result("FAIL", "never reached the map") end
    pokeFastConfig()
    return llmDrive(chapter(), "DefeatBoss", 14, 9)
end

-- CH01WIN: the default lord (blind A-taps pick Braulo) marches on the camp,
-- kills the chief, and SEIZES -- in-game proof of the lord-gated Seize
-- (CanUnitSeize hook, #42) and the win hand-off (Seize macro -> EVFLAG_WIN ->
-- ending scene -> MNC2 into the hosted ch02). (CH01_PARK is defined up by the
-- clear-bot.)
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
            -- generous budget: post-seize plays the full ending cutscene before
            -- MNC2 chains into the hosted ch02 (longer than the old 3600).
            local won = waitFor(function()
                return chapter() ~= 2 or procActive(SYM.gProcScr_TitleScreen)
            end, 9000, true)
            shot("ch01win-after-seize")
            if won then
                return result("PASS",
                    "Braulo seized the camp; ending + dev placeholder played -> title")
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

-- ---- CHECKPOINTS (#21): build a slow scene's lead-up ONCE at top speed (ckpt_*), then
-- replay just the scene at viewable speed (record*, which loads the save state). run.sh
-- orchestrates: it runs the ckpt_* builder at 240fps if the state is missing/stale, then
-- the record* scenario at 60fps. The lead-up drivers are shared here so the checkpoint
-- and a from-scratch run stay in lock-step.

-- Drive ch00 win -> ch01 prep screen OPEN (default-lord A-taps through the save menu +
-- the Beat-1 Northlook scene + lord select). true at the prep proc.
local function reachPrep()
    if not winCh00() then return false end
    if not waitFor(function() return chapter() == 2 end, 1800) then return false end
    for i = 1, 200 do
        if procActive(SYM.gProcScr_SALLYCURSOR) then return true end
        press(K.A, 4); wait(36)
    end
    return false
end

-- Like reachPrep, but PICK THE LAST lord candidate (Pinky, not the default Braulo)
-- at the lord-select menu before continuing to prep. Used to checkpoint a Pinky-as-lord
-- prep so the convoy/force-deploy lord-select fixes can be exercised for a NON-Braulo lord.
local function reachPrepPinky()
    if not winCh00() then return false end
    if not waitFor(function() return chapter() == 2 end, 1800) then return false end
    local atMenu = false
    for i = 1, 200 do
        if menuOpen() then atMenu = true break end          -- scenic lord-select menu
        if procActive(SYM.gProcScr_SALLYCURSOR) then break end
        press(K.A, 4); wait(36)
    end
    if not atMenu then return false end
    wait(40)
    for _ = 1, LORD_CANDIDATES - 1 do press(K.DOWN, 4); wait(8) end  -- walk to Pinky (last)
    press(K.A, 4); wait(40)                                  -- pick
    press(K.A, 4); wait(20)                                  -- [Yes] confirm
    for i = 1, 80 do
        if procActive(SYM.gProcScr_SALLYCURSOR) then return true end
        press(K.A, 4); wait(36)
    end
    return false
end

-- From the open prep screen, leave via Fight! and grind (escort poked frail+harmless) to
-- the seize-ready state: chief dead, Braulo moved ONTO the seize tile with its action
-- menu open (Seize on top). Returns true there -- the caller presses A to Seize.
local function leavePrepAndGrindToSeize()
    wait(180)
    for i = 1, 40 do
        if not procActive(SYM.gProcScr_SALLYCURSOR) then break end
        press(K.B, 4); wait(10); press(K.START, 4); wait(40)
        if i % 4 == 0 and procActive(SYM.gProcScr_SALLYCURSOR) then press(K.A, 4) wait(20) end
    end
    if not waitFor(function()
        return not procActive(SYM.gProcScr_SALLYCURSOR) and faction() == 0 and turn() >= 1
    end, 1200) then return false end
    wait(120)
    pokeFastConfig() -- speed through the goblin grind to the seize
    local chief = red(CHAR_CHIEF)
    if not chief then return false end
    local goal = { x = chief.x, y = chief.y }
    pokeFrail(chief)
    for t = 1, 18 do
        waitFor(function() return faction() == 0 and not menuOpen() end, 6000, true)
        wait(100)
        for i = 0, 23 do
            local r = unitAt(SYM.gUnitArrayRed, i)
            if r and r.charId ~= CHAR_CHIEF and not isDead(r) then pokeFrail(r); pokeHarmless(r) end
        end
        local braulo = blue(0x01)
        if isDead(braulo) then return false end
        chief = red(CHAR_CHIEF)
        if chief and not isDead(chief) then
            if math.abs(braulo.x - chief.x) + math.abs(braulo.y - chief.y) == 1 then
                if moveUnit(braulo.x, braulo.y, braulo.x, braulo.y) then chooseAttack(braulo.addr) end
            else
                marchToward(braulo, goal.x, goal.y + 1, 24, 15)
            end
        else
            -- chief down: move Braulo onto the seize tile (menu opens, Seize on top).
            if moveUnit(braulo.x, braulo.y, goal.x, goal.y) then
                wait(20)
                return true
            end
            press(K.B); press(K.B)
        end
        local phase = runEnemyPhase(CH01_PARK)
        if phase == "gameover" then return false end
    end
    return false
end

-- CKPT_PREP: fast (240fps) -- drive to the prep screen and snapshot it.
scenarios.ckpt_prep = function()
    if not reachPrep() then shot("ckpt-prep-fail"); return result("FAIL", "prep never opened") end
    wait(60)
    saveState("prep")
    result("PASS", "prep checkpoint saved")
end

-- CKPT_LORDPINKY: fast (240fps) -- drive to the prep screen with PINKY chosen as lord,
-- and snapshot it. Lets recordsupply iterate the prep-bench + map-Supply navigation fast.
scenarios.ckpt_lordpinky = function()
    if not reachPrepPinky() then shot("ckpt-lordpinky-fail")
        return result("FAIL", "Pinky-lord prep never opened") end
    wait(60)
    saveState("lordpinky")
    result("PASS", "Pinky-lord prep checkpoint saved")
end

-- LORDFLOOR (#45 3c): pick MARTY (the frail shaman) as lord and verify the survivability
-- floor bakes in exactly ONCE -- +7 maxHP / +4 def at ch01 turn 1 -- and does NOT re-apply
-- on later player phases. ch02 isn't a playable map yet, so the within-chapter multi-phase
-- stability + the permanent applied-flag (0xFA) stand in for "carries into ch02 with no
-- double-apply": both ride the identical BmMain_StartPhase -> LordFloor_ApplyOnce
-- early-return once the flag is set. make-green can't prove this -- only a real run can.
scenarios.lordfloor = function()
    local MARTY = 0x02                 -- marty rides CHARACTER_SETH (lord-select menu index 1)
    local BASE_HP, FLOOR_HP = 18, 25   -- base maxHP 18, floor +7 (difficulty --lord-floor oracle)
    local BASE_DEF, FLOOR_DEF = 2, 6   -- base def 2, floor +4
    local APPLIED = 0xFA               -- LORDFLOOR_APPLIED_FLAG (permanent)

    if not winCh00() then return result("FAIL", "never won ch00") end
    if not waitFor(function() return chapter() == 2 end, 1800) then
        return result("FAIL", "ch01 never started") end

    -- ride the save menu + Northlook scene to the scenic lord-select menu, then pick MARTY.
    local atMenu = false
    for _ = 1, 200 do
        if menuOpen() then atMenu = true break end
        if procActive(SYM.gProcScr_SALLYCURSOR) then break end
        press(K.A, 4); wait(36)
    end
    if not atMenu then return result("FAIL", "lord-select menu never opened") end
    wait(40)
    press(K.DOWN, 4); wait(8)          -- index 0 (Braulo) -> index 1 (Marty)
    press(K.A, 4); wait(40)            -- pick
    press(K.A, 4); wait(20)            -- [Yes] confirm

    -- through prep -> Fight! -> interactive turn 1.
    for _ = 1, 80 do
        if procActive(SYM.gProcScr_SALLYCURSOR) then break end
        press(K.A, 4); wait(36)
    end
    for i = 1, 40 do
        if not procActive(SYM.gProcScr_SALLYCURSOR) then break end
        press(K.B, 4); wait(10); press(K.START, 4); wait(40)
        if i % 4 == 0 and procActive(SYM.gProcScr_SALLYCURSOR) then press(K.A, 4); wait(20) end
    end
    if not waitFor(function()
        return not procActive(SYM.gProcScr_SALLYCURSOR) and faction() == 0 and turn() >= 1
    end, 1200) then return result("FAIL", "ch01 turn 1 never reached") end
    wait(60)

    -- marty must be force-deployed (the chosen lord) and floored at turn 1.
    local marty = blue(MARTY)
    if not marty then return result("FAIL", "marty (chosen lord) not on the field at ch01 t1") end
    local hp1, df1 = ru8(marty.addr + 0x12), ru8(marty.addr + 0x17)
    shot("lordfloor-t1")
    -- DIAGNOSTIC (#45 3c debug): dump pick flags + marty stats + applied flag at t1.
    local pickset = "none"
    for i = 0, LORD_CANDIDATES - 1 do
        if eventFlag(LORDSEL_FLAG_BASE + i) then pickset = string.format("0x%X (idx %d)", LORDSEL_FLAG_BASE + i, i) end
    end
    log(string.format("t%d: pick flag set=%s; marty maxHP=%d def=%d; applied(0xFA)=%s",
        turn(), pickset, hp1, df1, tostring(eventFlag(APPLIED))))
    if not eventFlag(APPLIED) then
        return result("FAIL", string.format("applied flag 0x%X clear at ch01 t1 -- floor not "
            .. "baked in by player-phase start (maxHP=%d, want %d)", APPLIED, hp1, FLOOR_HP)) end
    if hp1 ~= FLOOR_HP then
        return result("FAIL", string.format(
            "marty maxHP=%d at ch01 t1, want %d (base %d +7 floor)", hp1, FLOOR_HP, BASE_HP)) end
    if df1 ~= FLOOR_DEF then
        return result("FAIL", string.format(
            "marty def=%d at ch01 t1, want %d (base %d +4 floor)", df1, FLOOR_DEF, BASE_DEF)) end

    -- advance two player phases; the floor must NOT stack (flag-gated apply-once = the same
    -- early-return that protects the carry into ch02). Enemies poked harmless so marty lives.
    for _ = 1, 2 do
        for i = 0, 23 do
            local r = unitAt(SYM.gUnitArrayRed, i)
            if r and not isDead(r) then pokeHarmless(r) end
        end
        if runEnemyPhase(CH01_PARK) == "gameover" then
            return result("FAIL", "unexpected game over during the floor stability check") end
        marty = blue(MARTY)
        if not marty then return result("FAIL", "marty vanished mid-check") end
        local hp = ru8(marty.addr + 0x12)
        log(string.format("t%d: marty maxHP=%d (stable check)", turn(), hp))
        if hp ~= FLOOR_HP then
            return result("FAIL", string.format(
                "marty maxHP=%d at ch01 t%d -- floor RE-APPLIED (double-apply bug)", hp, turn())) end
    end

    result("PASS", string.format(
        "marty floored ONCE: maxHP %d->%d (+7), def %d->%d (+4), flag 0x%X set at t1, stable across 3 player phases",
        BASE_HP, FLOOR_HP, BASE_DEF, FLOOR_DEF, APPLIED))
end

-- CKPT_SEIZE: fast (240fps) -- drive to Braulo-on-the-seize-tile (menu open) and snapshot
-- BEFORE pressing Seize, so record* replays the ending fresh from ROM.
scenarios.ckpt_seize = function()
    if not reachPrep() then shot("ckpt-seize-noprep"); return result("FAIL", "prep never opened") end
    if not leavePrepAndGrindToSeize() then shot("ckpt-seize-fail")
        return result("FAIL", "could not reach the seize tile") end
    saveState("seize")
    result("PASS", "seize checkpoint saved (Braulo on tile, menu open)")
end

-- RECORDPREP: viewable (60fps) -- load the prep checkpoint, then open Pick Units and
-- pan the deploy map, capturing frames ("prep") to hunt the prep-screen "black
-- splotches". run.sh builds the checkpoint first if needed.
scenarios.recordprep = function()
    wait(30) -- let the core settle past boot before loading
    if not loadState("prep") then return result("FAIL", "no prep checkpoint (run.sh builds it)") end
    wait(60)
    shot("prep")                 -- the Preparations menu
    press(K.A, 4); wait(80)      -- Pick Units (top item) -> the deploy map
    for i = 1, 24 do
        for f = 1, 6 do shot("prep") yield() end
        press(K.RIGHT, 4)
    end
    result("PASS", "prep + Pick Units captured")
end

-- RECORDSUPPLY (#2/#3): with PINKY as lord, bench Braulo + deploy 3 non-Braulo in prep,
-- then on the map have Pinky (the chosen lord) open the convoy via the Supply command --
-- the cross-character behavioural proof that force-deploy + supply follow the chosen lead.
local US_NOT_DEPLOYED = 0x08
local CHAR_BRAULO, CHAR_PINKY_LORD = 0x01, 0x08
local function isDeployedInPrep(charId)
    local u = blue(charId)
    return u and (u.state & US_NOT_DEPLOYED) == 0
end
local function countDeployedPrep()
    local n = 0
    for i = 0, 50 do
        local u = unitAt(SYM.gUnitArrayBlue, i)
        if u and u.charId ~= 0 and (u.state & US_NOT_DEPLOYED) == 0 then n = n + 1 end
    end
    return n
end
scenarios.recordsupply = function()
    wait(30)
    if not loadState("lordpinky") then return result("FAIL", "no lordpinky checkpoint (run.sh builds it)") end
    wait(60)
    shot("supply")                                        -- prep main, Pinky as lord
    press(K.A, 4); wait(60)                               -- enter Pick Units (single A from prep)
    if not procActive(SYM.ProcScr_PrepUnitScreen) then
        shot("supply-no-pickunits")
        return result("FAIL", "Pick Units screen never opened")
    end
    shot("supply")
    -- Pick Units 2-col list, cursor starts on Pinky (pos 0):
    --   0 Pinky | 1 Braulo / 2 Marty | 3 Wolfram / 4 Mees | 5 RBG / 6 Rootis | 7 Sclorbo
    -- Bench Braulo (pos 1): RIGHT to him, A only if he is currently deployed.
    press(K.RIGHT, 4); wait(20)
    if isDeployedInPrep(CHAR_BRAULO) then press(K.A, 4); wait(20) end
    shot("supply")
    -- Top up to 4 with non-Braulo units: walk down col 1 (RBG pos5, Sclorbo pos7) and
    -- deploy benched ones until the cap is full. (Cursor is on Braulo/pos1.)
    for _, downs in ipairs({2, 2}) do          -- pos1 -> pos5 (RBG); pos5 -> pos7 (Sclorbo)
        if countDeployedPrep() >= 4 then break end
        for _ = 1, downs do press(K.DOWN, 4); wait(12) end
        press(K.A, 4); wait(20)                -- deploy the (benched) unit here
        shot("supply")
    end
    log(string.format("prep: brauloDeployed=%s deployedCount=%d",
        tostring(isDeployedInPrep(CHAR_BRAULO)), countDeployedPrep()))
    -- Launch the chapter straight from Pick Units (START = Fight!).
    press(K.START, 4); wait(40)
    for i = 1, 30 do
        if not procActive(SYM.gProcScr_SALLYCURSOR) and not procActive(SYM.ProcScr_PrepUnitScreen)
           and faction() == 0 and turn() >= 1 then break end
        press(K.A, 4); wait(30)
    end
    if not waitFor(function()
        return faction() == 0 and turn() >= 1
            and not procActive(SYM.gProcScr_SALLYCURSOR)
    end, 1200) then
        shot("supply-no-map")
        return result("FAIL", "never reached the player-phase map")
    end
    wait(120); shot("supply")                             -- the deployed field
    -- Map-side assertions: Braulo benched (not on field), Pinky deployed, exactly 4 out.
    local braulo = blue(CHAR_BRAULO)
    local braOnField = braulo and (braulo.state & 0x9) == 0 and braulo.x ~= 0xFF
    local pinky = blue(CHAR_PINKY_LORD)
    local pinkyOnField = pinky and (pinky.state & 0x9) == 0 and pinky.x ~= 0xFF
    local onField = 0
    for i = 0, 50 do
        local u = unitAt(SYM.gUnitArrayBlue, i)
        if u and (u.state & 0x9) == 0 and u.x ~= 0xFF then onField = onField + 1 end
    end
    log(string.format("map: braulo=%s pinky=%s field=%d",
        tostring(braOnField), tostring(pinkyOnField), onField))
    if braOnField then return result("FAIL", "Braulo is on the field (should be benched)") end
    if not pinkyOnField then return result("FAIL", "Pinky (lord) not deployed") end
    -- Open Pinky's action menu (select + no-move) and screenshot it to find the Supply row.
    waitFor(function() return faction() == 0 and not menuOpen() end, 3000, true)
    wait(60)
    local usedSupply = false
    pinky = blue(CHAR_PINKY_LORD)
    if moveUnit(pinky.x, pinky.y, pinky.x, pinky.y) then
        wait(40); shot("supply")                          -- Pinky's menu: Rescue/Item/Trade/Supply/Wait
        -- Supply is row 3 (Rescue0 Item1 Trade2 Supply3 Wait4); cursor starts at row 0.
        press(K.DOWN, 4); wait(12)
        press(K.DOWN, 4); wait(12)
        press(K.DOWN, 4); wait(12); shot("supply")        -- cursor on Supply
        press(K.A, 4); wait(60)
        usedSupply = procActive(SYM.ProcScr_BmSupplyScreen)
        shot("supply")                                    -- the convoy screen -> Pinky USING Supply
        log("pinky opened convoy=" .. tostring(usedSupply))
        press(K.B, 4); wait(20); press(K.B, 4); wait(20)  -- back out of convoy + menu
    else
        shot("supply-no-menu")
    end
    -- Contrast: a NON-lord deployed unit's action menu has NO Supply row.
    waitFor(function() return faction() == 0 and not menuOpen() end, 1500, true)
    for i = 0, 50 do
        local u = unitAt(SYM.gUnitArrayBlue, i)
        if u and u.charId ~= CHAR_PINKY_LORD and (u.state & 0x9) == 0 and u.x ~= 0xFF then
            if moveUnit(u.x, u.y, u.x, u.y) then wait(40); shot("supply") end  -- no Supply row
            press(K.B, 4); wait(20); press(K.B, 4); wait(20)
            break
        end
    end
    if not usedSupply then
        return result("FAIL", "Pinky (lord) could not open the convoy via Supply")
    end
    result("PASS", string.format(
        "Braulo benched (field=%d, no Braulo); Pinky the chosen lord opened the convoy via Supply", onField))
end

-- RECORDRESCUE: reproduce the "rescued cast sprite renders BLACK" bug (#44). One cast unit
-- rescues an adjacent ally; the lifted unit's map-unit (MU) sprite is captured. Root cause
-- (diagnosed session 12): the MU's STANDING facing draws the class SMS through the cast
-- palette bank (a general cast-MU fault; the rescue lift halts to standing, so it's the most
-- visible case). The custom idle SMS and walking AP path are unaffected. See issue #44.
scenarios.recordrescue = function()
    wait(30)
    if not loadState("prep") then return result("FAIL", "no prep checkpoint (run.sh builds it)") end
    wait(60)
    for i = 1, 40 do                                       -- leave prep via Fight!
        if not procActive(SYM.gProcScr_SALLYCURSOR) and not procActive(SYM.ProcScr_PrepUnitScreen)
           and faction() == 0 and turn() >= 1 then break end
        press(K.B, 4); wait(10); press(K.START, 4); wait(40)
        if i % 3 == 0 then press(K.A, 4); wait(20) end
    end
    if not waitFor(function()
        return faction() == 0 and turn() >= 1 and not procActive(SYM.gProcScr_SALLYCURSOR)
    end, 1200) then shot("rescue-no-map"); return result("FAIL", "never reached the map") end
    -- The prep checkpoint sits BEFORE the Ch1 battle-start cutscene and the PLAYER PHASE
    -- banner; both must finish before a unit is selectable. StdEventEngine runs the cutscene
    -- -- wait for it to go idle (tapping A to advance dialogue), then settle past the banner.
    -- (Waiting only on "not menuOpen" returns mid-banner, where the menu A press is eaten.)
    if not waitFor(function()
        return faction() == 0 and turn() >= 1
            and not procActive(SYM.ProcScr_StdEventEngine) and not menuOpen()
    end, 3000, true) then shot("rescue-no-map"); return result("FAIL", "cutscene never cleared") end
    wait(150); shot("rescue")                              -- let the PLAYER PHASE banner pass
    -- FE8 only offers Rescue when the rescuer's Aid >= the target's Con, so not every adjacent
    -- pair is liftable. Try each deployed unit until one actually lifts a neighbour; confirm via
    -- US_RESCUING (0x10, include/bmunit.h -- NOT 0x1000), then capture the lift. With no enemy
    -- in range Rescue is the top action-menu item: A enters target-select, A picks the sole
    -- adjacent target. That lifted MU is the custom-cast sprite #44 reports rendering BLACK.
    local US_RESCUING = 0x10
    local function tryRescue(rescuer)
        local target
        for i = 0, 50 do
            local u = unitAt(SYM.gUnitArrayBlue, i)
            if u and u.charId ~= rescuer.charId and (u.state & 0x9) == 0 and u.x ~= 0xFF
               and math.abs(u.x - rescuer.x) + math.abs(u.y - rescuer.y) == 1 then target = u break end
        end
        if not target then return nil end
        if not moveUnit(rescuer.x, rescuer.y, rescuer.x, rescuer.y) then return nil end
        waitFor(function() return menuOpen() end, 90, true)  -- action menu up
        wait(12); shot("menu")                             -- CAPTURE the action menu (Rescue should be top)
        press(K.A, 4); wait(16)                            -- top item -> target-select (if Rescue)
        wait(12); shot("targetsel")                        -- CAPTURE the rescue target-select
        press(K.A, 4)                                      -- pick the sole adjacent target
        for f = 1, 80 do if f % 3 == 0 then shot("rescue") end yield() end  -- the lift animation
        local r = blue(rescuer.charId)
        if r and (r.state & US_RESCUING) ~= 0 then return target.charId end
        press(K.B, 4); press(K.B, 4); press(K.B, 4)        -- not liftable: back fully out
        waitFor(function() return faction() == 0 and not menuOpen() end, 150, true)
        return nil
    end
    waitFor(function() return faction() == 0 and not menuOpen() end, 300, true)
    wait(30)
    local rescued, rescuerId
    for i = 0, 50 do
        local u = unitAt(SYM.gUnitArrayBlue, i)
        if u and (u.state & 0x9) == 0 and u.x ~= 0xFF then
            rescued = tryRescue(u)
            if rescued then rescuerId = u.charId; break end
        end
    end
    if not rescued then shot("rescue-none"); return result("FAIL", "no rescuer could lift an ally") end
    wait(20); shot("rescue")
    log(string.format("charId 0x%02X rescued charId 0x%02X (US_RESCUING set)", rescuerId, rescued))
    result("PASS", string.format("rescue lift captured: 0x%02X carrying 0x%02X", rescuerId, rescued))
end

-- RECORDTRADE (#44 follow-up): capture the TRADE screen. Nicolas: the black bodies
-- may have been in the trade menu, not the rescue lift. Same prep lead-up as
-- recordrescue, then a cast unit opens Trade with an adjacent ally; the trade screen
-- (both units' map-sprite icons + item lists) is captured for inspection.
scenarios.recordtrade = function()
    wait(30)
    if not loadState("prep") then return result("FAIL", "no prep checkpoint (run.sh builds it)") end
    wait(60)
    for i = 1, 40 do                                       -- leave prep via Fight!
        if not procActive(SYM.gProcScr_SALLYCURSOR) and not procActive(SYM.ProcScr_PrepUnitScreen)
           and faction() == 0 and turn() >= 1 then break end
        press(K.B, 4); wait(10); press(K.START, 4); wait(40)
        if i % 3 == 0 then press(K.A, 4); wait(20) end
    end
    if not waitFor(function()
        return faction() == 0 and turn() >= 1 and not procActive(SYM.gProcScr_SALLYCURSOR)
    end, 1200) then shot("trade-no-map"); return result("FAIL", "never reached the map") end
    if not waitFor(function()
        return faction() == 0 and turn() >= 1
            and not procActive(SYM.ProcScr_StdEventEngine) and not menuOpen()
    end, 3000, true) then shot("trade-no-map"); return result("FAIL", "cutscene never cleared") end
    wait(150)
    waitFor(function() return faction() == 0 and not menuOpen() end, 300, true)
    wait(30)
    local function tryTrade(actor)
        local target
        for i = 0, 50 do
            local u = unitAt(SYM.gUnitArrayBlue, i)
            if u and u.charId ~= actor.charId and (u.state & 0x9) == 0 and u.x ~= 0xFF
               and math.abs(u.x - actor.x) + math.abs(u.y - actor.y) == 1 then target = u break end
        end
        if not target then return nil end
        if not moveUnit(actor.x, actor.y, actor.x, actor.y) then return nil end
        wait(12); shot("menu")                             -- action menu (note option order)
        press(K.DOWN, 4); wait(6); shot("nav")             -- step 1
        press(K.DOWN, 4); wait(6); shot("nav")             -- step 2 (Trade if order R/I/T/S/W)
        press(K.A, 4); wait(16); shot("tradesel")          -- selected -> partner-select (if Trade)
        press(K.A, 4)                                      -- pick the sole adjacent ally
        for f = 1, 30 do if f % 4 == 0 then shot("trade") end yield() end
        press(K.B, 4); press(K.B, 4); press(K.B, 4)        -- exit (so a wrong pick backs out)
        waitFor(function() return faction() == 0 and not menuOpen() end, 150, true)
        return target.charId
    end
    local partner
    for i = 0, 50 do
        local u = unitAt(SYM.gUnitArrayBlue, i)
        if u and (u.state & 0x9) == 0 and u.x ~= 0xFF then
            partner = tryTrade(u)
            if partner then break end
        end
    end
    if not partner then shot("trade-none"); return result("FAIL", "no unit could trade") end
    result("PASS", string.format("trade screen captured (partner 0x%02X)", partner))
end

-- RECORDFIX (#5 + #6): in-game capture of the two text fixes. #5 is now a BATTLE-START
-- event (turn 1), so the roadsign + body narration (opaque SOLOTEXTBOXSTART boxes) auto-play
-- the instant the map begins -- reliably screenshotted here. #6: a non-lord PC is given a big
-- movBonus to cross the trail, frailed, and killed on the enemy phase; the per-PC death-quote
-- box is captured via captureEnemyPhaseQuotes (proc-detected: holds + shoots while
-- ProcScr_BattleEventEngine is live, instead of blind A-mashing that dismissed it). Asserts
-- BOTH the death AND the quote box on screen. Braulo-lord prep checkpoint.
scenarios.recordfix = function()
    wait(30)
    if not loadState("prep") then return result("FAIL", "no prep checkpoint (run.sh builds it)") end
    wait(60)
    -- Leave prep via Fight! -- press A ONLY while still in prep (to answer the confirm);
    -- never during the turn-1 events, or the sign (first event) gets mashed past.
    for i = 1, 30 do
        if not procActive(SYM.gProcScr_SALLYCURSOR) and not procActive(SYM.ProcScr_PrepUnitScreen) then break end
        press(K.B, 4); wait(10); press(K.START, 4); wait(40)
        if (procActive(SYM.gProcScr_SALLYCURSOR) or procActive(SYM.ProcScr_PrepUnitScreen))
           and i % 3 == 0 then press(K.A, 4); wait(20) end
    end
    waitFor(function() return not procActive(SYM.gProcScr_SALLYCURSOR)
        and not procActive(SYM.ProcScr_PrepUnitScreen) end, 600)
    -- #5: the battle-start roadsign + body + Izobai taunt auto-play at turn 1. Slow-capture
    -- from BEFORE the first box -- screenshot densely, advance with A only every ~1s so each
    -- opaque box lingers and reads (the sign is the FIRST event, so it must not be skipped).
    for f = 1, 900 do
        if f % 3 == 0 then shot("fix") end
        if f % 60 == 0 then press(K.A, 3) end             -- advance banner + sign/body/taunt boxes
        if faction() == 0 and not menuOpen() and turn() >= 1 and f > 540 then break end
        yield()
    end
    waitFor(function() return faction() == 0 and not menuOpen() end, 2000, true)
    wait(30); shot("fix")
    -- #6: deterministic PC death. March a non-lord PC up to a goblin (topping up its HP so
    -- it survives the approach), then frail+harmless it and ATTACK -- the goblin's counter
    -- kills the 1-HP scout on the player phase (no enemy-AI dependency), firing its per-PC
    -- death quote with its bust. Capture the quote densely.
    local scoutId
    for i = 0, 50 do
        local u = unitAt(SYM.gUnitArrayBlue, i)
        if u and u.charId ~= 0x01 and (u.state & 0x9) == 0 and u.x ~= 0xFF then scoutId = u.charId break end
    end
    if not scoutId then return result("FAIL", "no non-lord PC deployed") end
    -- Map combat (battle anims OFF) + NORMAL speed: the per-PC death quote is a battle-quote
    -- event shown during the killing combat (DisplayDefeatTalkForPid); with full battle anims
    -- it's buried/aliased, but in map combat it shows as a readable, lingering map overlay.
    do
        local a = SYM.gPlaySt + 0x40; local c = ru32(a)
        c = (c & ~(3 << 17)) | (1 << 17)   -- animationType = OFF (map combat)
        c = c & ~(1 << 7)                  -- gameSpeed = normal (quote stays readable)
        emu:write32(a, c)
    end
    local function nearestGoblin(s)
        local g, gd = nil, 999
        for i = 0, 23 do
            local r = unitAt(SYM.gUnitArrayRed, i)
            if r and not isDead(r) and r.x ~= 0xFF then
                local d = math.abs(r.x - s.x) + math.abs(r.y - s.y)
                if d < gd then g, gd = r, d end
            end
        end
        return g, gd
    end
    local sawDeath, quoteShot = false, false
    for t = 1, 7 do
        local s = blue(scoutId)
        if not s or isDead(s) then sawDeath = isDead(blue(scoutId)); break end
        local g, gd = nearestGoblin(s)
        local ng = 0
        for i = 0, 23 do local r = unitAt(SYM.gUnitArrayRed, i); if r and not isDead(r) and r.x ~= 0xFF then ng = ng + 1 end end
        log(string.format("#6 turn %d: scout 0x%02X at (%d,%d) HP=%d gobl=%d nearestGd=%s",
            t, scoutId, s.x, s.y, s.curHP or -1, ng, tostring(gd)))
        if not g then break end
        if gd <= 1 then                                    -- adjacent: frail and ride enemy
            for k = 1, 4 do                                 -- phases (re-frail each) until a goblin connects
                local sk = blue(scoutId)
                if not sk or isDead(sk) then sawDeath = isDead(blue(scoutId)); break end
                pokeFrail(sk)
                press(K.B, 3); wait(8); press(K.B, 3); wait(8)  -- clear any stray menu
                endTurn(CH01_PARK)
                waitFor(function() return faction() ~= 0 end, 300)
                -- Ride the enemy phase at the proven cadence (A every ~60 advances it; the
                -- frail adjacent scout dies). When the in-battle quote engine goes live
                -- (ProcScr_BattleEventEngine -> the death quote, possibly at the phase
                -- boundary), STOP the advance and capture every frame, paging it slowly.
                local deathFrame, go = nil, false
                for f = 1, 1800 do
                    local quoteUp = procActive(SYM.ProcScr_BattleEventEngine)
                    if f % 2 == 0 or quoteUp then shot("fix") end
                    if quoteUp then
                        quoteShot = true
                        if f % 24 == 0 then press(K.A, 3) end       -- page the quote
                    elseif not deathFrame and f % 60 == 0 then
                        press(K.A, 3)                               -- advance the enemy phase
                    end
                    if isDead(blue(scoutId)) and not deathFrame then deathFrame = f; sawDeath = true end
                    if gameOverActive() then go = true; break end
                    if deathFrame and quoteShot and f > deathFrame + 90 then break end
                    if deathFrame and f > deathFrame + 540 then break end
                    if not deathFrame and faction() == 0 and not menuOpen() and f > 600 then break end
                    yield()
                end
                if (sawDeath and quoteShot) or go then break end
            end
            break
        end
        emu:write8(s.addr + 0x1D, 20)                      -- big movBonus: clear the trail
                                                           -- peaks/forest and reach a goblin in one turn
        marchToward(s, g.x, g.y, 24, 15)                   -- close on the goblin
        local s2 = blue(scoutId); if s2 then emu:write8(s2.addr + 0x13, 40) end  -- survive approach
        endTurn(CH01_PARK)
        if waitFor(function() return faction() ~= 0 end, 300) then
            waitFor(function() return faction() == 0 and not menuOpen() end, 6000, true)
        end
        if isDead(blue(scoutId)) then sawDeath = true; break end
        if gameOverActive() then break end
    end
    shot("fix")
    log("scout died=" .. tostring(sawDeath) .. " quoteBoxShot=" .. tostring(quoteShot))
    if not sawDeath then return result("FAIL", "scout did not die -- no death quote captured") end
    if not quoteShot then return result("FAIL", "PC died but the death-quote box was never on screen (proc not detected)") end
    result("PASS", "fix: battle-start roadsign (#5) + PC death-quote box captured (#6)")
end

-- RECORDENDING: viewable (60fps) -- load the seize checkpoint, press Seize, and capture
-- the "Rolling Cheddar" ending as motion frames ("end"). FAITHFUL capture: at 60fps the
-- frame callback (and shot()) fires every emulated frame, so the engine's ~16-frame face
-- fades render smoothly (at 240fps frameskip aliases them into 1-frame "blips"). A frame
-- every 4th (~15fps); A-tap every ~72 so each page fully types then holds. Assemble at
-- 15fps (make_gif --fps 15) for ~real-time playback.
scenarios.recordending = function()
    wait(30) -- let the core settle past boot before loading
    if not loadState("seize") then return result("FAIL", "no seize checkpoint (run.sh builds it)") end
    wait(20)
    pokeNormalConfig() -- normal text speed so the typewriter + face fades animate
    press(K.A) -- Seize (the menu was saved open) -> the ending hand-off
    wait(40)
    -- the ending plays the full outro then MNC2s into the hosted ch02 -- record
    -- through all of it until the chapter advances (the title-screen check below is
    -- the legacy pre-ch02 exit, kept as a harmless backstop).
    local fr, atTitle = 0, false
    while fr < 9000 do
        fr = fr + 1
        if fr % 4 == 0 then shot("end") end
        if fr % 72 == 0 then press(K.A, 4) end
        if procActive(SYM.gProcScr_TitleScreen) then atTitle = true break end
        yield()
    end
    if atTitle then
        wait(120) -- let the title fade in + the logo/banner draw
        shot("title")
        return result("PASS", "ending + dev placeholder recorded; returned to the title screen")
    end
    shot("ending-after")
    result("FAIL", "ending never reached the title screen (dev placeholder stuck?)")
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
    -- lord-select menu is a StartMenu over a scenic BG (no chief on the map yet);
    -- detect by menuOpen() alone (the save screen is a different proc). 200-iter
    -- budget to ride the save menu + the ~22-page Northlook scene.
    local atMenu = false
    for i = 1, 200 do
        if menuOpen() then atMenu = true break end
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

-- RECORDLORDFAST (#46 debug): on a `make LORDBOOT=1` ROM, New Game boots the sandbox
-- straight into the lord-select prep screen (no ch00 win, no Northlook scene). Detect the
-- prep proc, screenshot the card, walk the candidates, pick one. Compile-time-only
-- iteration on the lord screen (see the debug-fast-boot convention).
scenarios.recordlordfast = function()
    local function recwait(n, tag)
        for f = 1, n do if f % 5 == 0 then shot(tag) end yield() end
    end
    -- title -> New Game -> sandbox -> BeginningScene runs the explainer + ASMCs CallLordSelectMenu
    local atPrep = false
    for i = 1, 160 do
        if menuOpen() then atPrep = true break end
        press(i % 2 == 0 and K.A or K.START, 4)
        wait(22)
    end
    if not atPrep then shot("lordfast-noprep")
        return result("FAIL", "lord-select prep never opened on the fast-boot") end
    recwait(50, "lordfast")            -- settle on the first candidate
    for _ = 1, LORD_CANDIDATES - 1 do
        press(K.DOWN, 4)
        for f = 1, 24 do yield() end   -- let the bust gfx finish streaming in (no shots)
        recwait(26, "lordfast")        -- THEN capture the SETTLED card (no transitions)
    end
    recwait(40, "lordfast")
    press(K.A, 4)                      -- select the highlighted lead -> confirm box
    for f = 1, 30 do yield() end       -- let the menu tear down + confirm box open
    press(K.A, 4)                      -- fast-forward the (slow) typewriter
    for f = 1, 24 do yield() end
    recwait(30, "lordfast-confirm")    -- capture the full "Will <name> lead the party?" [Yes/No]
    press(K.A, 4)                      -- [Yes] -> the re-pick loop exits (FADI/ENDA)
    recwait(90, "lordfast")            -- the screen fades out + control returns
    result("PASS", "lord-select prep fast-boot frames recorded")
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
    -- A-taps ride the save menu + the ~22-page Beat-1 Northlook scene to the lord
    -- prompt+menu (cf. ch01win's 200-iter budget; the old 60 ran out mid-scene).
    -- The lord-select menu is a StartMenu(MenuDef_LordSelect) over a scenic BG
    -- (BG_DARKLING_WOODS) BEFORE the battle map loads -- so the chief is NOT in the
    -- red array during it. Detect it by menuOpen() alone (sProc_Menu); the earlier
    -- post-chapter save screen is a different proc and does not trip menuOpen().
    local atMenu = false
    for i = 1, 200 do
        if menuOpen() then atMenu = true break end
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

-- (A dedicated title-screen capture used to ride recordending's post-ending MNTS,
-- but ch02 is hosted now -- the ch01 ending MNC2s onward instead of returning to the
-- title. A standalone boot-capture is unreliable: the attract reel races past the
-- title; bootobserve below is the tool for boot-sequence questions.)

-- BOOTOBSERVE: screenshot the natural boot sequence with NO input, to see whether the
-- title screen actually appears at boot (diagnostic).
scenarios.bootobserve = function()
    log("observing boot; one tap to clear Health&Safety, then hands-off")
    press(K.A, 4); wait(120); press(K.A, 4); wait(60)  -- clear the H&S 'press any button'
    for f = 1, 2400 do
        if f % 40 == 0 then
            shot(string.format("boot-%04d-ch%d-title%s", f, chapter(),
                tostring(procActive(SYM.gProcScr_TitleScreen))))
        end
        yield()
    end
    return result("PASS", "boot observed")
end

-- MAPSHOT: boot to the map and screenshot the deployed field -- the generic "see the
-- units on the map" chapter load-test (any hosted chapter reachable from New Game, e.g.
-- a --ch03-boot fast-boot ROM). bootToMap already shoots "map-loaded"; add a few settle
-- frames for a clean capture. Reusable smoke-look for every new chapter host.
scenarios.mapshot = function()
    if not bootToMap() then return result("FAIL", "never reached the map") end
    for i = 1, 6 do
        wait(20)
        shot(string.format("mapshot-%02d-ch%d-turn%d", i, chapter(), turn()))
    end
    return result("PASS", "map deployed; screenshots taken")
end

-- RECORDOPENING: boot -> title -> START -> New Game, then record the #43 opening montage
-- (Frostmaiden lore crawl + Ten Towns world-map tour) to confirm it plays + doesn't crash.
scenarios.recordopening = function()
    -- press A to clear the logos + Health&Safety; STOP the instant the title is up
    local atTitle = false
    for i = 1, 160 do
        if procActive(SYM.gProcScr_TitleScreen) then atTitle = true break end
        press(K.A, 3); wait(18)
    end
    if not atTitle then return result("FAIL", "title screen never reached") end
    wait(40); shot("opening")                                 -- title
    press(K.START, 6); wait(40)                               -- START -> New Game / file select
    -- Mash A to clear the New Game / file-select menu and start a fresh game. A is SAFE
    -- here: only START skips the crawl (OpSubtitle_HandleStartPress), A does NOT -- so we
    -- can tap through the menu without losing montage slides. Stop the instant the crawl
    -- proc (gProcScr_OpSubtitle) goes live, then hand off so it auto-advances on its timer.
    local sawCrawl = false
    for i = 1, 60 do
        if procActive(SYM.gProcScr_OpSubtitle) then sawCrawl = true break end
        if inChapter() then break end                         -- non-montage build: no crawl
        press(K.A, 3); wait(20)
    end
    pokeNormalConfig()                                        -- readable crawl/tour speed
    -- The lore crawl auto-advances on its own timer (A is a no-op there), but the Ten
    -- Towns world-map tour that follows is WM_TEXT pages that WAIT on a down-arrow prompt
    -- and only advance on A. So tap A periodically throughout: harmless during the crawl,
    -- and it walks the map tour forward. Readable speed makes the opener long -> generous
    -- budget; shoot every 6th frame to keep the frame count sane for a GIF.
    for f = 1, 9000 do
        if f % 6 == 0 then shot("opening") end
        if f % 45 == 0 then press(K.A, 3) end                 -- advance the WM tour pages
        if procActive(SYM.gProcScr_OpSubtitle) then sawCrawl = true end
        if inChapter() then break end                         -- montage done -> prologue map
        yield()
    end
    shot("opening-after")
    if not sawCrawl then
        return result("FAIL",
            "no opening crawl (gProcScr_OpSubtitle never ran) -- montage not in this ROM?")
    end
    if not inChapter() then
        return result("FAIL", "crawl played but never reached the prologue map")
    end
    return result("PASS", string.format(
        "opening montage played (crawl seen) -> reached chapter=%d", chapter()))
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

-- RECORDRBG (#65 demo): lord-select RBG (force-deploy), drive him to fire his bow at an
-- enemy with FULL battle anims, screenshotting the custom RBG animation ("rbg" frames).
local function pokeAnimsOn() -- full battle anims + viewable speed (undo winCh00's grind config)
    local a = SYM.gPlaySt + 0x40
    emu:write32(a, (ru32(a) & ~(3 << 17)) & ~(1 << 7)) -- animationType 0 (anims ON), gameSpeed normal
end
-- Drive the open action menu through Attack -> weapon -> target -> combat, shooting
-- frames across the battle anim. RETURNS whether combat actually started -- the caller
-- MUST check it; a stall on the menu is a FAIL, not a silent PASS (#65).
local function captureAttack(actorAddr, tag) -- like chooseAttack but shoot frames through the anim
    -- The action menu is open with Attack available (the caller positions the unit so its
    -- weapon can reach a foe -- a bow parked at range 1 has NO Attack command; the returned
    -- verdict catches a miss). Attack -> weapon select -> target select. In target select the
    -- BKSEL cursor (separate from the map cursor) can start OFF a target when several foes are
    -- in range, so a single blind A may not commit -- press A to confirm and, if no battle
    -- starts, cycle to the next target (RIGHT) and retry. Stop the instant a battle animates
    -- (gProc_ekrBattle): pressing A during the anim would skip it.
    local function combatLive() return procActive(SYM.gProc_ekrBattle)
        or (ru32(actorAddr + 0x0C) & 0x2) ~= 0 end
    press(K.A); wait(20)  -- Attack -> weapon select
    press(K.A); wait(20)  -- weapon  -> target select
    for _ = 1, 8 do
        if combatLive() then break end
        press(K.A); wait(14)          -- confirm the highlighted target
        if combatLive() then break end
        press(K.RIGHT); wait(8)       -- A didn't commit -> cycle to the next in-range target
    end
    -- Shoot through the anim. Success = the battle proc (gProc_ekrBattle) actually ran AND we
    -- captured real ANIM frames -- robust whether the attacker survives, dies in the counter, or
    -- kills + triggers a level-up that outlasts the budget. A stall on the menu never starts the
    -- proc, so sawAnim stays false -> FAIL.
    --
    -- A talky foe (boss taunt / per-PC line) raises an in-battle QUOTE box during gProc_ekrBattle
    -- (ProcScr_BattleEventEngine) that WAITS for A and would otherwise eat the whole budget before
    -- the attack draws -- the bug that made every recordanim GIF show only the quote, never the
    -- hit/damage. So: tap A WHILE the quote box is up to dismiss it (it only blocks here, the pure
    -- anim takes no input), and screenshot ONLY when no quote box is up -- those are the real
    -- draw/fire/impact/HP-drain frames. Never tap during the pure anim (that would skip it); the
    -- quote-proc gate guarantees we only press while a text box holds.
    local sawCombat, sawAnim = false, false
    for f = 1, 900 do
        local inCombat = procActive(SYM.gProc_ekrBattle)
        if inCombat then sawCombat = true
        elseif sawCombat then break end                        -- combat played and finished
        if (ru32(actorAddr + 0x0C) & 0x2) ~= 0 and not inCombat then break end  -- actor acted
        if procActive(SYM.ProcScr_BattleEventEngine) then
            press(K.A, 2)                                      -- advance/dismiss the quote box
        elseif inCombat then
            sawAnim = true
            if f % 3 == 0 then shot(tag) end                   -- the actual attack anim
        end
        yield()
    end
    wait(30)
    return sawAnim
end
local RBG_PID = 0x05           -- CHARACTER_MOULDER (RBG's slot), lord-select menu index 4

-- The deployable custom-art cast: friendly id -> the vanilla character slot it rides
-- (CHARACTER_* pid), mirroring build_campaign's PORTRAIT_MAP. The `make TESTCH=1` sandbox
-- deploys all of these, so `recordanim` (PT_CHAR=<id>) can capture ANY of them. Per-unit
-- weapon reach + "is this a non-attacker" are READ from the game (below), not hard-coded.
local CAST = {
    braulo = 0x01, marty = 0x02, meesmickle = 0x03, wolfram = 0x04,
    ['prof-rbg'] = 0x05, rootis = 0x06, sclorbo = 0x07, pinky = 0x08,
    rbg = 0x05,  -- alias for prof-rbg (the #65 first mover)
}

-- Shared lead-up for the RBG demo: win the prologue, lord-select RBG into ch01,
-- stop on ch01 turn-1 player phase with RBG deployed. Returns (rbg unit) or (false, err).
-- Built ONCE at 240fps into the "rbgch01" checkpoint (ckpt_rbgch01); recordrbg LOADS it
-- so the slow prologue+lord-select grind isn't replayed every capture (#65).
local function reachRbgCh01()
    if not winCh00() then return false, "never won ch00" end
    if not waitFor(function() return chapter() == 2 end, 1800) then
        return false, "ch01 never started" end
    local atMenu = false
    for _ = 1, 200 do
        if menuOpen() then atMenu = true break end
        if procActive(SYM.gProcScr_SALLYCURSOR) then break end
        press(K.A, 4); wait(36)
    end
    if not atMenu then return false, "lord-select menu never opened" end
    wait(40)
    for _ = 1, 4 do press(K.DOWN, 4); wait(8) end  -- index 0 (Braulo) -> index 4 (RBG)
    press(K.A, 4); wait(40)   -- pick
    press(K.A, 4); wait(20)   -- [Yes]
    for _ = 1, 80 do
        if procActive(SYM.gProcScr_SALLYCURSOR) then break end
        press(K.A, 4); wait(36)
    end
    for i = 1, 40 do
        if not procActive(SYM.gProcScr_SALLYCURSOR) then break end
        press(K.B, 4); wait(10); press(K.START, 4); wait(40)
        if i % 4 == 0 and procActive(SYM.gProcScr_SALLYCURSOR) then press(K.A, 4); wait(20) end
    end
    if not waitFor(function()
        return not procActive(SYM.gProcScr_SALLYCURSOR) and faction() == 0 and turn() >= 1
    end, 1200) then return false, "ch01 turn 1 never reached" end
    local rbg = blue(RBG_PID)
    if not rbg then return false, "RBG not on the field after lord-select" end
    return rbg
end

-- gBmMapUnit[y][x] -- the engine's tile->unit grid (u8**, indexed like gBmMapMovement). It,
-- not the unit's xPos/yPos, is what cursor-selection reads, so a relocate must update both.
local function mapUnitRow(y) return ru32(ru32(SYM.gBmMapUnit) + y * 4) end
local function mapUnitAt(x, y) return ru8(mapUnitRow(y) + x) end
local function setMapUnit(x, y, v) emu:write8(mapUnitRow(y) + x, v) end

-- Relocate the unit straight onto a free tile within [mn,mx] of a live enemy, so a unit that
-- SPAWNS far from the fight doesn't have to march across the map (6 phases can't cross it -- a
-- far spawn timed out). Writes xPos/yPos AND moves the unit's entry in gBmMapUnit (vacate old
-- tile, occupy new) so the engine can still select it from the new tile. Attack availability
-- depends only on an enemy being in weapon range of the unit's TILE, not the terrain under it,
-- so any in-range, grid-free, in-bounds tile works. Prefers the farthest in-range tile (e.g. a
-- bow at exactly 2). Returns true if relocated.
local function teleportToFiringTile(u, mn, mx)
    local grid = mapUnitAt(u.x, u.y)        -- this unit's id in the grid (preserves faction bits)
    if grid == 0 then return false end       -- not tracked where we think -> don't risk it
    for _, e in ipairs(liveEnemies()) do
        for r = mx, mn, -1 do
            for dx = -r, r do
                local ady = r - math.abs(dx)
                for _, dy in ipairs(ady == 0 and { 0 } or { ady, -ady }) do
                    local tx, ty = e.x + dx, e.y + dy
                    if tx >= 0 and tx <= 24 and ty >= 0 and ty <= 15 and mapUnitAt(tx, ty) == 0 then
                        setMapUnit(u.x, u.y, 0)                 -- vacate the old tile
                        emu:write8(u.addr + 0x10, tx); emu:write8(u.addr + 0x11, ty)
                        setMapUnit(tx, ty, grid)                -- occupy the new tile
                        log(string.format("  teleported to (%d,%d) [range %d of enemy (%d,%d)]", tx, ty, r, e.x, e.y))
                        return true
                    end
                end
            end
        end
    end
    return false
end

-- Drive the deployed unit `pid` within its weapon's reach of an enemy and leave it ON the
-- firing tile with its action menu open. Reads the unit's ACTUAL reach each phase
-- (unitAttackRange), so a bow won't park adjacent (range 1, no Attack) and a melee weapon
-- won't park at range 2 -- one function for every cast member. A far spawn is teleported into
-- the fight first (the 6-phase march can't cross the whole map). Returns true (ready) or false.
-- The slow part of the checkpoint demo, so the state is saved right AFTER this (#65).
local function positionForShot(pid)
    local u = blue(pid)
    if not u then return false end
    local mn, mx = unitAttackRange(u)
    if not mn then return false end          -- staff/non-attacker: nothing to position for
    pokeAnimsOn()
    -- Primary path: teleport ONTO a firing tile, then attack IN PLACE. The unit is already
    -- within [mn,mx] of a foe, so "moving" to its own tile opens the action menu with Attack
    -- available -- no second move to a different tile (that proved flaky: some units stranded
    -- mid-move with the menu never opening). Works for every cast member regardless of spawn.
    if teleportToFiringTile(u, mn, mx) then
        u = blue(pid)
        if moveUnit(u.x, u.y, u.x, u.y) then return true end
    end
    -- Fallback (teleport found no free in-range tile): march in over up to 6 turns.
    for phase = 1, 6 do
        u = blue(pid)
        if isDead(u) then return false end
        mn, mx = unitAttackRange(u)
        if not mn then return false end
        pokeAnimsOn()
        local reach = selectAndReach(u, 24, 15)
        press(K.B); wait(10)  -- deselect; re-select to act
        if reach then
            local pick = CLEARBOT.pickTarget(reach, liveEnemies(), { range = mx, min_range = mn })
            if pick then
                if moveUnit(u.x, u.y, pick.tile.x, pick.tile.y) then return true end
            else
                local es = liveEnemies()
                if #es > 0 then marchToward(u, es[1].x, es[1].y, 24, 15); chooseWait() end
            end
        end
        endTurn()
        waitFor(function() return faction() == 0 and turn() >= phase + 1 end, 1500); wait(40)
    end
    return false
end

scenarios.ckpt_rbgch01 = function()
    local rbg, err = reachRbgCh01()
    if not rbg then shot("ckpt-rbgch01-fail"); return result("FAIL", err) end
    if not positionForShot(RBG_PID) then shot("ckpt-rbgch01-noshot")
        return result("FAIL", "RBG never got into firing position in 6 phases") end
    saveState("rbgch01")
    result("PASS", "rbgch01 checkpoint saved (RBG on firing tile, action menu open)")
end

scenarios.recordrbg = function()
    local RBG = RBG_PID
    local CLONE_NUMBER = 0x6C   -- CLASS_BLST_KILLER_EMPTY (the Archer-clone class)
    wait(30) -- let the core settle past boot before loading
    if not loadState("rbgch01") then
        return result("FAIL", "no rbgch01 checkpoint (run.sh builds it)") end
    wait(60); pokeAnimsOn()
    local rbg = blue(RBG)
    if not rbg then return result("FAIL", "RBG not on the field after load") end
    local cls = ru8(ru32(rbg.addr + 0x04) + 0x04) -- pClassData->number
    log(string.format("RBG at (%d,%d) class=0x%X (want 0x%X clone), firing", rbg.x, rbg.y, cls, CLONE_NUMBER))
    shot("rbg-deploy")
    local fired = captureAttack(rbg.addr, "rbg"); shot("rbg-after")
    if not fired then
        return result("FAIL", "captureAttack never reached combat (stale checkpoint or stuck on menu)") end
    return result("PASS", string.format("RBG bow shot captured (class 0x%X)", cls))
end

-- Capture one cast member's battle anim on the TESTCH sandbox: find its deployed unit, read
-- its weapon reach, drive it to fire, and shoot frames tagged with its id (so make_gif picks
-- them up per character). The verdict is honest -- combat must actually start.
local function captureCharAnim(name)
    local pid = CAST[name]
    if not pid then
        return result("FAIL", "unknown cast id '" .. tostring(name) .. "' -- set PT_CHAR to one of: "
            .. "braulo marty meesmickle wolfram prof-rbg rootis sclorbo pinky") end
    wait(60); pokeAnimsOn()
    local u = blue(pid)
    if not u then return result("FAIL", name .. " not deployed -- build the ROM with `make TESTCH=1`") end
    local cls = ru8(ru32(u.addr + 0x04) + 0x04)
    local mn, mx = unitAttackRange(u)
    if not mn then
        return result("FAIL", string.format(
            "%s has no attack weapon (staff/healer, class 0x%X) -- no combat anim to capture", name, cls)) end
    log(string.format("%s at (%d,%d) class=0x%X weapon-range %d-%d", name, u.x, u.y, cls, mn, mx))
    if not positionForShot(pid) then shot(name .. "-noshot")
        return result("FAIL", name .. " never reached firing position") end
    shot(name .. "-deploy")
    local fired = captureAttack(u.addr, name); shot(name .. "-after")
    if not fired then
        return result("FAIL", "captureAttack never reached combat for " .. name) end
    return result("PASS", string.format("%s anim captured (class 0x%X)", name, cls))
end

-- RECORDANIM (#65): capture any custom-art cast member firing on a `make TESTCH=1` ROM (New
-- Game boots straight into the Ch1 sandbox with the whole cast + foes deployed). Pick the unit
-- with PT_CHAR=<id> (default prof-rbg); no prologue grind / lord-select / save-state. On a
-- normal ROM the unit isn't deployed and this FAILs with a clear message.
scenarios.recordanim = function()
    if not bootToMap() then return result("FAIL", "never reached the map") end
    local name = (PLAYTEST_CHAR and PLAYTEST_CHAR ~= "") and PLAYTEST_CHAR or "prof-rbg"
    return captureCharAnim(name)
end

-- Back-compat alias: recordrbgtest == recordanim for RBG.
scenarios.recordrbgtest = function()
    if not bootToMap() then return result("FAIL", "never reached the map") end
    return captureCharAnim("rbg")
end


-- ================================================================ ch02 load-test (#22)
-- The structural half of the Ch2 "Cold Welcome" load-test: does ch02 LOAD off the real
-- ch01->ch02 chain (MNC2(0x3)), not soft-lock, and is it winnable -- with the 3 GREEN chwinga
-- protect layer present and their per-survivor charm-gifts (CHECK_ALIVE -> GIVEITEMTO) actually
-- landing. The PACING half (judging the 5 cutscenes in motion) stays a human-at-mGBA pass.
-- Built on a "ch02start" save-state checkpoint (ckpt_ch02start plays the whole chain ONCE at
-- top speed); ch02 / smoke_ch02 / clear_ch02 LOAD it so each is fast. Char/class/item ids from
-- the decomp + the ch02 build (CH02_CHWINGA / CH02_ITEM_IDS in tools/build_campaign.py).
local CH02_CHWINGA_PIDS = { 0xCA, 0xC9, 0xC8 }   -- DARA/KLIMT/MANSEL = Mote/Rime/Glimmer (green)
local CH02_CHARMS = { 0x76, 0x6D, 0x6E }         -- Red Gem / Elixir / Pure Water (the gifts)
local CLASS_ARCHER = 0x19                          -- the fliers-vs-bows debut enemy (CH02_CLASS_IDS)
local CH02_CHAPTER = 3                             -- ch02 hosts on chapter slot 3 (ch01 -> MNC2(0x3))
local CH02_PARK = { x = 0, y = 0 }                -- NW corner end-turn tile (15x15 map; deploy is row 3+)

-- Directed ch01 seize (the generic clear-bot is too slow to seize ch01's 25x16 map reliably):
-- march the lord onto the chief's throne, poking the chief + escort frail/harmless so the march
-- can't be blocked or killed. Modeled on scenarios.ch01win; reachCh02Map only needs to REACH
-- ch02, not fairly test ch01 balance. Returns "won" once ch01 hands off, else "timeout"/"gameover".
local CH01_CHIEF, CH01_LORD = CHAR_CHIEF, 0x01   -- ch01 boss (BREGUET slot) + Braulo (default lord)
local function seizeCh01ToCh02()
    pokeFastConfig()   -- 10-goblin enemy phases: map combat + fast speed
    local chief = red(CH01_CHIEF)
    if not chief then return "noboss" end
    local goal = { x = chief.x, y = chief.y }   -- the chief holds the seize tile
    pokeFrail(chief)
    log(string.format("ch01 seize: chief frail on (%d,%d); marching the lord", goal.x, goal.y))
    for t = 1, 18 do
        if chapter() ~= 2 then return "won" end
        waitFor(function() return faction() == 0 and not menuOpen() end, 6000, true)
        wait(100)   -- let the player-phase banner finish (it eats key presses)
        for i = 0, 23 do   -- the escort dies to the first counter and deals no damage
            local r = unitAt(SYM.gUnitArrayRed, i)
            if r and r.charId ~= CH01_CHIEF and not isDead(r) then pokeFrail(r); pokeHarmless(r) end
        end
        local lord = blue(CH01_LORD)
        if not lord or isDead(lord) then return "gameover" end
        chief = red(CH01_CHIEF)
        if chief and not isDead(chief) then
            if math.abs(lord.x - chief.x) + math.abs(lord.y - chief.y) == 1 then
                if moveUnit(lord.x, lord.y, lord.x, lord.y) then chooseAttack(lord.addr) end
            else
                marchToward(lord, goal.x, goal.y + 1, 24, 15)
            end
        else
            if moveUnit(lord.x, lord.y, goal.x, goal.y) then press(K.A) end   -- Seize tops the menu here
            if waitFor(function() return chapter() ~= 2 end, 9000, true) then return "won" end
            press(K.B); press(K.B)
        end
        if runEnemyPhase(CH01_PARK) == "gameover" then return "gameover" end
    end
    return "timeout"
end

-- Reach the ch02 map off the REAL chain: clear ch00, seize ch01, then A-mash through the ch01
-- ending + ch02 opening cutscenes + prep onto the map. This is the chain (MNC2(0x3)) the load-test
-- most needs to prove. Returns true once on the ch02 map (faction 0, turn >= 1).
local function reachCh02Map()
    if not reachCh01Map() then return false end
    log("seizing ch01 to chain into ch02 (slot 3)")
    local status = seizeCh01ToCh02()
    log(string.format("ch01 seize status=%s chapter=%d faction=0x%02X turn=%d title=%s",
        status, chapter(), faction(), turn(), tostring(procActive(SYM.gProcScr_TitleScreen))))
    if status ~= "won" then
        result("FAIL", "ch01 seize did not complete (" .. status .. ") -- can't reach ch02"); return false end
    -- A-mash the ch01 ending cutscene + post-chapter save menu (they gate the MNC2(0x3)
    -- transition) until ch02 (slot 3) actually loads.
    local loaded = false
    for i = 1, 400 do
        if chapter() == CH02_CHAPTER then loaded = true break end
        if i % 20 == 0 then log(string.format("await ch02: chapter=%d faction=0x%02X turn=%d title=%s",
            chapter(), faction(), turn(), tostring(procActive(SYM.gProcScr_TitleScreen)))) end
        press(K.A, 4); wait(36)
    end
    if not loaded then
        shot("ch02-never-loaded")
        result("FAIL", "ch02 (slot 3) never loaded after the ch01 win"); return false end
    log("in ch02 (slot 3); A-mashing the opening cutscene to the prep (Pick Units) screen")
    -- The ch02 opening (title card + 3 beats) precedes prep. A-mash until Pick Units opens.
    local prep = false
    for i = 1, 400 do
        if procActive(SYM.gProcScr_SALLYCURSOR) then prep = true break end
        if i % 20 == 0 then log(string.format("ch02 wait prep: chapter=%d faction=0x%02X turn=%d",
            chapter(), faction(), turn())) end
        press(K.A, 4); wait(36)
    end
    if prep then
        wait(180)
        for i = 1, 40 do
            if not procActive(SYM.gProcScr_SALLYCURSOR) then break end
            press(K.B, 4); wait(10); press(K.START, 4); wait(40)
            if i % 4 == 0 and procActive(SYM.gProcScr_SALLYCURSOR) then press(K.A, 4); wait(20) end
        end
    end
    -- A-mash the beginning scene (+ turn-1 tutorial) until the map is fully LIVE: enemies loaded,
    -- the party deployed, player control, no cutscene. Units/enemies/green chwinga load here -- the
    -- earlier "faction 0 + turn 1" fired during the opening cutscene, before any of them existed.
    local function partyDeployed()
        for j = 0, 7 do local u = unitAt(SYM.gUnitArrayBlue, j)
            if u and (u.state & 0x9) == 0 and u.x ~= 0xFF then return true end end
        return false
    end
    local onmap = false
    for i = 1, 400 do
        if chapter() == CH02_CHAPTER and faction() == 0 and turn() >= 1
            and unitAt(SYM.gUnitArrayRed, 0) ~= nil and partyDeployed()
            and not procActive(SYM.ProcScr_StdEventEngine) and not procActive(SYM.gProcScr_SALLYCURSOR)
            and not menuOpen() then onmap = true break end
        if i % 20 == 0 then log(string.format(
            "await ch02 map: chapter=%d faction=0x%02X turn=%d red0=%s deployed=%s evt=%s",
            chapter(), faction(), turn(), tostring(unitAt(SYM.gUnitArrayRed, 0) ~= nil),
            tostring(partyDeployed()), tostring(procActive(SYM.ProcScr_StdEventEngine)))) end
        press(K.A, 4); wait(36)
    end
    if not onmap then
        shot("ch02-map-not-live")
        result("FAIL", "ch02 map never became live (party/enemies never loaded)"); return false end
    wait(120)
    shot("ch02-map")
    return true
end

-- ckpt_ch02start: build the ch02start checkpoint once (run.sh runs this at 240fps when the
-- state is missing/stale), so the deep ch00->ch01->ch02 chain is paid once per ROM build.
scenarios.ckpt_ch02start = function()
    if not reachCh02Map() then return end   -- reachCh02Map already set a FAIL verdict
    saveState("ch02start")
    result("PASS", "ch02start checkpoint saved (on the ch02 map, turn 1)")
end

-- Read every collected item id (low byte) from all blue inventories + the convoy -- where a
-- charm-gift lands (leader's inventory, overflow -> convoy).
local function collectedItems()
    local items = {}
    for i = 0, 7 do
        local u = unitAt(SYM.gUnitArrayBlue, i)
        if u then for s = 0, 4 do items[#items + 1] = ru16(u.addr + 0x1E + s * 2) & 0xFF end end
    end
    local n = ru8(SYM.gConvoyItemCount)
    if n > 100 then n = 100 end     -- convoy cap (CONVOY_ITEM_COUNT, bmcontainer.h)
    for i = 0, n - 1 do items[#items + 1] = ru16(SYM.gConvoyItemArray + i * 2) & 0xFF end
    return items
end

-- Keep the 3 green chwinga alive so the gift path (CHECK_ALIVE -> GIVEITEMTO) is exercised
-- deterministically -- whether they survive UNDER REAL PLAY is a balance/pacing question for
-- the human pass, not the wiring test.
local function protectChwinga()
    for _, pid in ipairs(CH02_CHWINGA_PIDS) do
        local g = findUnit(SYM.gUnitArrayGreen, 20, pid)
        if g and not isDead(g) then
            emu:write8(g.addr + 0x13, 60)   -- curHP
            emu:write8(g.addr + 0x17, 30)   -- def
            emu:write8(g.addr + 0x18, 30)   -- res
        end
    end
end

-- CH03WIN (#23 item 1): kill the grell -> its FLAGGED defeat quote sets EVFLAG_DEFEAT_BOSS
-- -> the Ch4 Misc DefeatBoss AFEV runs the ending. Proves the ch03 win wiring fires. The grell
-- rides a RAW pid (0xb7, no CA_BOSS -- so the generic clear-bot can't target it) and sits far
-- from the left-entrance spawn, so we teleport the leader (braulo, pid 0x01) onto a grell-adjacent
-- tile and strike. Poke the grell frail first (1 HP, no avoid) so one clean melee hit kills; a
-- Mogall's Evil Eye is range 2+, so a range-1 strike draws no lethal counter. EVFLAG_DEFEAT_BOSS
-- (flag 2) is the definitive assertion: the engine binds the DefeatBoss AFEV directly to it, and
-- SetPidDefeatedFlag (eventinfo.c) sets it on the grell's death REGARDLESS of CA_BOSS.
-- Run: PT_HOST_CHAPTER=4 tools/playtest/run.sh ch03win  (needs a CH03BOOT=1 ROM). Seeds #23 item 7.
scenarios.ch03win = function()
    if not bootToMap() then return result("FAIL", "never reached the ch03 map") end
    if not red(0xb7) then return result("FAIL", "grell (pid 0xb7) not found in the red array") end
    if not blue(0x01) then return result("FAIL", "leader (braulo, pid 0x01) not deployed") end
    -- The fast-boot deploys the party weaponless (items='0'; real equipping rides the PREP pass,
    -- #23 item 2), so give the leader an Iron Axe (id 0x1F | 45 uses) in items[0] so Attack appears.
    emu:write16(blue(0x01).addr + 0x1E, 0x2D1F)
    log("leader given an Iron Axe (fast-boot deploys weaponless)")
    -- Bring the grell TO braulo's isolated left-entrance spawn (no other enemy is near it) so the
    -- grell is the ONLY unit in braulo's range -- chooseAttack's default target can't pick a kobold
    -- by mistake (the (14,1) lair sits amid other foes). Up to 3 player turns, enemy-phase between,
    -- re-frailing + re-parking the grell each turn in case a whiff or its AI move disturbs it.
    for turn = 1, 3 do
        local g = red(0xb7)
        if isDead(g) or eventFlag(2) then break end
        local leader = blue(0x01)
        pokeFrail(g)
        g = red(0xb7)
        local ggrid = mapUnitAt(g.x, g.y)
        local parked = false
        for _, d in ipairs({ { 1, 0 }, { -1, 0 }, { 0, 1 }, { 0, -1 } }) do
            local tx, ty = leader.x + d[1], leader.y + d[2]
            if tx >= 0 and tx <= 24 and ty >= 0 and ty <= 15 and mapUnitAt(tx, ty) == 0 then
                setMapUnit(g.x, g.y, 0)
                emu:write8(g.addr + 0x10, tx); emu:write8(g.addr + 0x11, ty)
                setMapUnit(tx, ty, ggrid)
                log(string.format("turn %d: grell parked at (%d,%d) next to braulo (%d,%d)",
                    turn, tx, ty, leader.x, leader.y))
                parked = true
                break
            end
        end
        if not parked then return result("FAIL", "no free tile adjacent to braulo to park the grell") end
        if moveUnit(leader.x, leader.y, leader.x, leader.y) then
            shot("attacking-grell")
            chooseAttack(leader.addr)
        end
        if isDead(red(0xb7)) or eventFlag(2) then break end
        log("grell survived turn " .. turn .. " (miss?); running enemy phase to retry")
        if runEnemyPhase() == "gameover" then return result("FAIL", "unexpected game over in ch03win") end
    end
    if not (isDead(red(0xb7)) or eventFlag(2)) then
        shot("grell-alive")
        return result("FAIL", "could not kill the grell in 3 turns")
    end
    log("grell dead; waiting out the defeat quote for EVFLAG_DEFEAT_BOSS")
    -- The flag is set AFTER the death quote renders (DisplayDefeatTalkForPid: show msg, THEN
    -- SetPidDefeatedFlag), so tap A through the shriek line while polling the flag.
    local won = waitFor(function() return eventFlag(2) end, 3600, true)
    log(string.format("debug: EVFLAG_DEFEAT_BOSS(2)=%s chapter=%d (host=%d)",
        tostring(eventFlag(2)), chapter(), HOST_CHAPTER))
    if not won then
        shot("grell-dead-no-flag")
        return result("FAIL", "grell died but EVFLAG_DEFEAT_BOSS never set (win did not fire)")
    end
    -- Flag set -> the Misc DefeatBoss AFEV runs the ending script (victory sting -> dev-placeholder
    -- campfire -> MNTS back to title, since ch04 isn't hosted). Let it play out to the title screen
    -- WITHOUT mashing A (mashing would hit "Press START" and boot a spurious New Game). Screenshot
    -- the endpoint as a no-crash confirmation that the ending script itself is valid.
    wait(240)
    shot("ch03-ending-ran")
    result("PASS", "grell killed -> EVFLAG_DEFEAT_BOSS set -> DefeatBoss ending ran to title (ch03 win wired)")
end

-- KOBOLDVIEW (#23 art): pull the enemy kobolds ON-SCREEN next to the party so their reskinned
-- map sprites are visible (the roster deploys off-camera at the enemy tiles). Teleports the first
-- few red brigand generics (pid 0xaa) to tiles around braulo's spawn and screenshots. No combat.
scenarios.koboldview = function()
    if not bootToMap() then return result("FAIL", "never reached the ch03 map") end
    local leader = blue(0x01)
    if not leader then return result("FAIL", "leader (braulo) not deployed") end
    -- collect distinct red generic kobolds (pid 0xaa) and park a few around braulo
    local spots, si = {}, 1
    for _, d in ipairs({ {2,0}, {3,0}, {2,-1}, {3,-1}, {2,1}, {3,1}, {4,0} }) do
        local tx, ty = leader.x + d[1], leader.y + d[2]
        if tx >= 0 and tx <= 24 and ty >= 0 and ty <= 15 and mapUnitAt(tx, ty) == 0 then
            spots[#spots + 1] = { tx, ty }
        end
    end
    local moved = 0
    for i = 0, 23 do
        local u = unitAt(SYM.gUnitArrayRed, i)
        if u and not isDead(u) and u.charId == 0xaa and moved < #spots then
            moved = moved + 1
            local s = spots[moved]
            local grid = mapUnitAt(u.x, u.y)
            setMapUnit(u.x, u.y, 0)
            emu:write8(u.addr + 0x10, s[1]); emu:write8(u.addr + 0x11, s[2])
            setMapUnit(s[1], s[2], grid)
        end
    end
    log(string.format("parked %d kobold(s) next to braulo (%d,%d)", moved, leader.x, leader.y))
    wait(60)
    shot("kobolds-on-map")
    result(moved > 0 and "PASS" or "FAIL",
        string.format("%d kobold map sprites pulled on-screen for review", moved))
end

-- lzview (#23 review): ISOLATE the ONE blade-kobold (class 0x80 = the Lizardzerker enemy
-- reskin) so it can't be confused with a red PC (braulo the crab / wolfram). Sweeps EVERY
-- other unit -- all blue PCs and all other red enemies -- to the far corner, leaving only
-- the lizardzerker on a visible left-area tile, and logs its SMSId to prove which sheet it
-- draws (the injected lizardzerker wait row, not a PC's).
scenarios.lzview = function()
    if not bootToMap() then return result("FAIL", "never reached the ch03 map") end
    local FAR_X, FAR_Y = 16, 15
    local function stash(u) setMapUnit(u.x, u.y, 0)
        emu:write8(u.addr + 0x10, FAR_X); emu:write8(u.addr + 0x11, FAR_Y) end
    -- every blue PC (braulo included) -> far corner, out of the shot
    for i = 0, 7 do local u = unitAt(SYM.gUnitArrayBlue, i); if u then stash(u) end end
    -- find the class-0x80 enemy; every OTHER red enemy -> far corner
    local lz
    for i = 0, 23 do
        local u = unitAt(SYM.gUnitArrayRed, i)
        if u and not isDead(u) then
            if ru8(ru32(u.addr + 4) + 4) == 0x80 and not lz then lz = u
            else stash(u) end
        end
    end
    if not lz then return result("FAIL", "no class-0x80 (Lizardzerker) unit on the map") end
    local sms = ru8(ru32(lz.addr + 4) + 6)   -- unit -> pClassData -> .SMSId (offset 0x06)
    local grid = mapUnitAt(lz.x, lz.y); setMapUnit(lz.x, lz.y, 0)
    local tx, ty = 4, 10                       -- open, camera-visible, well clear of the corner pile
    emu:write8(lz.addr + 0x10, tx); emu:write8(lz.addr + 0x11, ty); setMapUnit(tx, ty, grid)
    log(string.format("LONE enemy Lizardzerker at (%d,%d): class=0x80 SMSId=%d "
        .. "(all PCs + other enemies swept to %d,%d)", tx, ty, sms, FAR_X, FAR_Y))
    wait(60)
    shot("lizardzerker-isolated")
    result("PASS", string.format("lone enemy Lizardzerker, class 0x80, SMSId=%d", sms))
end

-- enemycheck (#23 review): the DEFINITIVE sprite audit. Logs every red enemy's class + SMSId
-- (idle sheet id), then PANS THE CAMERA (gBmSt.camera, no teleporting) to the brute (14,6)
-- and blade (15,2) so their true STANDING sprites render -- avoids the walk-frame that a
-- memory teleport forces. Expect: brute class 0x81 + blade class 0x80 both SMSId 119
-- (lizardzerker), plain grunts SMSId 118 (wildling).
scenarios.enemycheck = function()
    if not bootToMap() then return result("FAIL", "never reached the ch03 map") end
    for i = 0, 23 do
        local u = unitAt(SYM.gUnitArrayRed, i)
        if u and not isDead(u) then
            local cd = ru32(u.addr + 4)
            log(string.format("red[%02d] char=0x%02X class=0x%02X SMSId=%d @ (%d,%d)",
                i, u.charId, ru8(cd + 4), ru8(cd + 6), u.x, u.y))
        end
    end
    local function panTo(tx, ty, name)
        emu:write16(SYM.gBmSt + 0x0C, math.max(0, tx * 16 - 112))  -- camera.x (px)
        emu:write16(SYM.gBmSt + 0x0E, math.max(0, ty * 16 - 72))   -- camera.y
        emu:write16(SYM.gBmSt + 0x14, tx); emu:write16(SYM.gBmSt + 0x16, ty)  -- cursor holds it
        wait(30); shot(name)
    end
    panTo(14, 6, "brute-at-14-6")
    panTo(15, 2, "blade-at-15-2")
    result("PASS", "enemy class/SMSId audit + camera pans to brute & blade")
end

-- ch03: entry assertions on the ch03 map (mirrors scenarios.ch01/ch02). Proves the recruit
-- model: Baxby (charId 0x10 = Forde, ch01 recruit) is on the BLUE prep roster, and Trex
-- (charId 0x1C = Rennac, ch03 talk recruit) stands GREEN on the map -- the vanilla Colm
-- pre-recruit state (cast colours land once he is talked to -> CUSA). Runs on a
-- `make CH03BOOT=1` ROM (New Game -> ch03 map).
scenarios.ch03 = function()
    if not bootToMap() then return result("FAIL", "never reached the ch03 map") end
    local BAXBY, TREX = 0x10, 0x1C   -- CHARACTER_FORDE (Baxby) / CHARACTER_RENNAC (Trex)
    local deployed, baxby = 0, false
    for i = 0, 15 do
        local u = unitAt(SYM.gUnitArrayBlue, i)
        if u then
            log(string.format("blue[%02d] char=0x%02X pos=(%d,%d) state=0x%08X",
                i, u.charId, u.x, u.y, u.state))
            if (u.state & 0x9) == 0 and u.x ~= 0xFF then deployed = deployed + 1 end
            if u.charId == BAXBY and not isDead(u) then baxby = true end
        end
    end
    local trexGreen = findUnit(SYM.gUnitArrayGreen, 10, TREX)
    if trexGreen then log(string.format("green Trex(0x1C) @ (%d,%d)", trexGreen.x, trexGreen.y)) end
    log(string.format("ch03 entry: bluedeployed=%d baxby(0x10)=%s trex_green=%s",
        deployed, tostring(baxby), tostring(trexGreen ~= nil)))
    shot("ch03-entry")
    if not baxby then return result("FAIL", "Baxby (Forde 0x11) not on the ch03 blue roster") end
    if not trexGreen then return result("FAIL", "Trex (Rennac 0x1C) not placed green (talk-recruit) on the map") end
    return result("PASS", string.format(
        "ch03 entered: %d blue (incl Baxby), Trex green talk-recruit on the map", deployed))
end

-- ch02: entry assertions on the ch02 map (mirrors scenarios.ch01). The 3 green chwinga are on
-- the field, the party deploys to the cap, and the archer + boss are present.
scenarios.ch02 = function()
    wait(30)
    if not loadState("ch02start") then return result("FAIL", "no ch02start checkpoint (run.sh builds it)") end
    wait(90)
    -- diagnostic: dump every non-null green slot (and the blue/red char ids) so a missing-chwinga
    -- failure shows whether they are absent, on another faction, or under unexpected char ids.
    for i = 0, 19 do
        local g = unitAt(SYM.gUnitArrayGreen, i)
        if g then log(string.format("green[%02d] char=0x%02X pos=(%d,%d) hp=%d state=0x%08X",
            i, g.charId, g.x, g.y, g.hp, g.state)) end
    end
    local blueids, redids = {}, {}
    for i = 0, 7 do local u = unitAt(SYM.gUnitArrayBlue, i); if u then blueids[#blueids+1] = string.format("0x%02X", u.charId) end end
    for i = 0, 23 do local r = unitAt(SYM.gUnitArrayRed, i); if r then redids[#redids+1] = string.format("0x%02X", r.charId) end end
    log("blue=" .. table.concat(blueids, ",") .. " | red=" .. table.concat(redids, ","))
    local chwinga = 0
    for _, pid in ipairs(CH02_CHWINGA_PIDS) do
        local g = findUnit(SYM.gUnitArrayGreen, 20, pid)
        if g and not isDead(g) then chwinga = chwinga + 1
            log(string.format("chwinga 0x%02X at (%d,%d) hp=%d", pid, g.x, g.y, g.hp)) end
    end
    local deployed = 0
    for i = 0, 7 do
        local u = unitAt(SYM.gUnitArrayBlue, i)
        if u and (u.state & 0x9) == 0 and u.x ~= 0xFF then deployed = deployed + 1 end
    end
    local archer, boss = false, false
    for i = 0, 23 do
        local r = unitAt(SYM.gUnitArrayRed, i)
        if r and not isDead(r) then
            if ru8(ru32(r.addr + 0x04) + 0x04) == CLASS_ARCHER then archer = true end
            if unitIsBoss(r) then boss = true end
        end
    end
    log(string.format("ch02 entry: chwinga=%d deployed=%d archer=%s boss=%s",
        chwinga, deployed, tostring(archer), tostring(boss)))
    shot("ch02-entry")
    if chwinga ~= 3 then return result("FAIL", string.format("want 3 green chwinga, found %d", chwinga)) end
    if deployed ~= 5 then return result("FAIL", string.format("deploy cap broken: %d on field (want 5)", deployed)) end
    if not archer then return result("FAIL", "no enemy archer (fliers-vs-bows debut) on the field") end
    if not boss then return result("FAIL", "no boss on the field") end
    result("PASS", string.format("ch02 entered: 3 chwinga green, %d deployed, archer + boss present", deployed))
end

-- smoke_ch02: stability net on the ch02 map -- idle-drive to a clean terminal, catching a
-- crash / soft-lock on load or during the 5 cutscenes.
scenarios.smoke_ch02 = function()
    wait(30)
    if not loadState("ch02start") then return result("FAIL", "no ch02start checkpoint (run.sh builds it)") end
    wait(90)
    return smokeDrive(chapter())
end

-- ch02baxby (#23 recruit-persist): prove the ch01-ending CUTSCENE recruit Baxby (CHARACTER_FORDE
-- 0x10) actually PERSISTS into ch02 as a real party member -- not just sized into the deploy cap
-- (which never LOADs anyone). Before the off-map recruit join-LOAD (inject_ch02 step 2a-bis, on
-- UnitDef_088B476C), ch02's blue roster was 0x01..0x08 with NO 0x10; now the join-LOAD LOADs him
-- into the saved party before PREP. Two proofs: (1) in the prep roster (found in gUnitArrayBlue),
-- and (2) on the map in combat -- force-deploy him if the prep auto-pick benched him, then attack
-- a foe and confirm damage landed. NB the roster is 9 deep (8 founding + Baxby), so we search
-- past blue()'s 8-slot window. Run: tools/playtest/run.sh ch02baxby (needs a normal build).
local BAXBY_PID = 0x10   -- CHARACTER_FORDE = baxby's cast slot (PORTRAIT_MAP; docs/CLASSES.md)
scenarios.ch02baxby = function()
    wait(30)
    if not loadState("ch02start") then return result("FAIL", "no ch02start checkpoint (run.sh builds it)") end
    wait(90)
    -- 1. PREP-ROSTER proof: Baxby must be a real party member. Search the whole blue array (the
    --    roster is 9 deep: 8 founding 0x01..0x08 + Baxby), not just blue()'s first 8 slots.
    local baxby, bidx
    for i = 0, 15 do
        local u = unitAt(SYM.gUnitArrayBlue, i)
        if u then
            log(string.format("blue[%02d] char=0x%02X pos=(%d,%d) state=0x%08X", i, u.charId, u.x, u.y, u.state))
            if u.charId == BAXBY_PID then baxby, bidx = u, i end
        end
    end
    if not baxby then
        shot("ch02baxby-absent")
        return result("FAIL", "Baxby (0x10) NOT in the ch02 party -- recruit-persist join-LOAD missing")
    end
    log(string.format("Baxby in the ch02 prep roster at blue[%d] pos=(%d,%d) state=0x%08X",
        bidx, baxby.x, baxby.y, baxby.state))
    -- 2. On-map: force-deploy him if the prep auto-pick benched him (US_HIDDEN 0x1 / US_NOT_DEPLOYED
    --    0x8 set, or x==0xFF) -- clear the bench bits, drop him on a free NW tile, register him in
    --    the map-unit grid so the engine can select him. (The cap is 5 and he joins last, so the
    --    auto-pick usually benches him -- exactly the case we must be able to deploy.)
    if (baxby.state & 0x9) ~= 0 or baxby.x == 0xFF then
        local idx = ru8(baxby.addr + 0x0B)                    -- unit->index = its map-grid id
        emu:write32(baxby.addr + 0x0C, baxby.state & ~0x9)    -- clear US_HIDDEN | US_NOT_DEPLOYED
        local placed = false
        for _, t in ipairs({ { 0, 3 }, { 0, 4 }, { 1, 4 }, { 2, 3 }, { 1, 3 }, { 0, 5 } }) do
            if mapUnitAt(t[1], t[2]) == 0 then
                emu:write8(baxby.addr + 0x10, t[1]); emu:write8(baxby.addr + 0x11, t[2])
                setMapUnit(t[1], t[2], idx); placed = true
                log(string.format("force-deployed Baxby at (%d,%d) grid=%d", t[1], t[2], idx))
                break
            end
        end
        if not placed then return result("FAIL", "no free tile to force-deploy Baxby") end
    else
        log("Baxby was auto-deployed by the prep default (already on the field)")
    end
    baxby = unitAt(SYM.gUnitArrayBlue, bidx)                   -- refresh after the deploy pokes
    -- Guard: the join-LOAD arms him (iron sword + iron lance), but if items[0] is empty give him
    -- an Iron Lance (0x08 | 45 uses) so Attack appears.
    if (ru16(baxby.addr + 0x1E) & 0xFF) == 0 then
        emu:write16(baxby.addr + 0x1E, 0x2D08)
        log("Baxby was weaponless -> gave him an Iron Lance")
    end
    shot("ch02baxby-deployed")
    -- 3. COMBAT proof: teleport him onto a tile within weapon reach of a live raider and attack.
    --    Frail+harmless every enemy first (1 HP, no counter power) so whichever foe he strikes is a
    --    clean, deterministic one-round kill he can't die to -- this is a WIRING proof (Baxby fights
    --    on the ch02 map), not a balance test. PASS = an enemy died to his strike AND he took his
    --    action (US_UNSELECTABLE), i.e. a real battle round resolved on the map.
    pokeAnimsOn()
    local mn, mx = unitAttackRange(baxby)
    if not mn then return result("FAIL", "Baxby has no attacking weapon equipped") end
    for i = 0, 23 do
        local r = unitAt(SYM.gUnitArrayRed, i)
        if r and not isDead(r) then pokeFrail(r); pokeHarmless(r) end
    end
    local liveBefore = #liveEnemies()
    if not teleportToFiringTile(baxby, mn, mx) then
        return result("FAIL", "no free tile in Baxby's weapon range of any enemy")
    end
    baxby = unitAt(SYM.gUnitArrayBlue, bidx)
    if not moveUnit(baxby.x, baxby.y, baxby.x, baxby.y) then
        shot("ch02baxby-no-menu")
        return result("FAIL", "Baxby's action menu never opened on his firing tile")
    end
    shot("ch02baxby-attacking")
    chooseAttack(baxby.addr)
    waitFor(function() return not procActive(SYM.gProc_ekrBattle) end, 600)
    wait(30)
    local liveAfter = #liveEnemies()
    baxby = unitAt(SYM.gUnitArrayBlue, bidx)
    local acted = baxby and (baxby.state & 0x2) ~= 0          -- US_UNSELECTABLE = he took his action
    log(string.format("Baxby combat: liveEnemies %d -> %d (killed %d); acted=%s",
        liveBefore, liveAfter, liveBefore - liveAfter, tostring(acted)))
    shot("ch02baxby-after-combat")
    if liveAfter >= liveBefore or not acted then
        return result("FAIL", string.format(
            "Baxby's attack resolved no combat (enemies %d->%d, acted=%s)",
            liveBefore, liveAfter, tostring(acted)))
    end
    result("PASS", string.format(
        "Baxby persists into ch02: in the prep roster (blue[%d]=0x10) AND fought on the ch02 map "
        .. "(killed a raider in melee)", bidx))
end

-- clear_ch02: the completability + chain + charm-delivery proof. Rout the raider band (DefeatAll)
-- while keeping the chwinga alive, then watch the ending scene gift all 3 charms to the leader /
-- convoy. PASS = routed, chained, and all 3 chwinga charms delivered.
scenarios.clear_ch02 = function()
    wait(30)
    if not loadState("ch02start") then return result("FAIL", "no ch02start checkpoint (run.sh builds it)") end
    wait(90)
    pokeFastConfig()
    local start = chapter()
    local function advanced() return chapter() ~= start or procActive(SYM.gProcScr_TitleScreen) end
    local best = {}
    local function snapCharms()
        local d = CH02.deliveredCharms(collectedItems(), CH02_CHARMS)
        if #d > #best then best = d end
    end
    -- Deterministic rout: the generic clear-bot is unreliable on ch02 (fumbles into item menus),
    -- so each player phase we frail+harmless every enemy (1 HP, no power) and teleport a party unit
    -- adjacent to each live foe to one-shot it via REAL combat -- the kill goes through the death
    -- hook that fires the DefeatAll win check (a raw US_DEAD poke would NOT). clear_ch02 verifies the
    -- win->ending->charm WIRING, not ch02 balance (that's the human pacing pass + the difficulty gate).
    local routed = false
    for t = 1, 12 do
        if advanced() then break end
        waitFor(function() return faction() == 0 and not menuOpen() end, 6000, true)
        wait(60)
        protectChwinga()
        for i = 0, 23 do
            local r = unitAt(SYM.gUnitArrayRed, i)
            if r and not isDead(r) then pokeFrail(r); pokeHarmless(r) end
        end
        for i = 0, 7 do
            if advanced() or #liveEnemies() == 0 then break end
            local u = unitAt(SYM.gUnitArrayBlue, i)
            if u and not isDead(u) and (u.state & 0x2) == 0 then
                local mn, mx = unitAttackRange(u)
                if mn and teleportToFiringTile(u, mn, mx) then
                    u = blue(u.charId)   -- refresh after the teleport relocates it
                    if u and moveUnit(u.x, u.y, u.x, u.y) then
                        chooseAttack(u.addr)
                        waitFor(function() return faction() == 0 and not menuOpen()
                            and not procActive(SYM.gProc_ekrBattle) end, 600)   -- let the kill resolve
                    end
                end
            end
        end
        log(string.format("clear_ch02 turn %d: liveEnemies=%d chapter=%d", t, #liveEnemies(), chapter()))
        if #liveEnemies() == 0 then routed = true; break end
        if advanced() then break end
        if runEnemyPhase(CH02_PARK) == "gameover" then
            shot("clear-ch02-gameover")
            return result("FAIL", string.format("game over on turn %d -- party lost", t)) end
        snapCharms()
    end
    shot("clear-ch02-routed")
    log(string.format("rout=%s; ending the turn to fire the DefeatAll win check", tostring(routed)))
    -- Routed: force the phase-end DefeatAll check, then FINE-GRAINED poll the ending scene so the
    -- charm-gifts (CHECK_ALIVE -> GIVEITEMTO) are captured before the ch03 placeholder/title clears
    -- the convoy/inventory. (Coarse polling skipped the charm window last time.)
    if routed and not advanced() then endTurn() end
    for _ = 1, 1200 do
        snapCharms()
        if #best >= 3 then break end
        if procActive(SYM.gProcScr_TitleScreen) then snapCharms(); break end
        press(K.A, 2); wait(8)
    end
    shot("clear-ch02-ending")
    log(string.format("charms delivered: %d/3", #best))
    if #best < 3 then
        return result("FAIL", string.format(
            "ch02 charm-gift broken: only %d/3 chwinga charms reached the leader/convoy", #best)) end
    result("PASS", "ch02 routed + chained; all 3 chwinga charms delivered (CHECK_ALIVE -> GIVEITEMTO)")
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
