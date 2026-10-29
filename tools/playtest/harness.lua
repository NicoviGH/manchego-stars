-- Automated FE8 playtest harness for mGBA 0.11+ (--script).
--
-- Launched by run.sh via a generated wrapper that sets:
--   PLAYTEST_DIR      -- this directory
--   PLAYTEST_SYMDIR   -- where gen_symbols.py wrote symbols.lua and procscr.lua (PT_SYMDIR)
--   PLAYTEST_SCENARIO -- which `scenarios.<name>` to run (the table below is the
--                        authoritative list; run.sh's header groups the main ones)
--   PLAYTEST_ENTRY    -- the function that runs it, when a chapter case's `lua:` binds a
--                        generic probe (`INSPECT.redStats`) instead of a same-named scenario
--   PLAYTEST_LOG      -- log file path (runner polls it for "RESULT:")
--   PLAYTEST_SHOTDIR  -- screenshot directory for milestone/debug captures
--   PLAYTEST_STATEDIR -- save-state checkpoint dir (ckpt_*/record* scenarios)
--   PLAYTEST_SEED     -- fuzz/llm seed (PT_SEED)
--   PLAYTEST_LLMDIR   -- #63 sidecar handshake dir (PT_LLM_DIR)
--
-- Design: one coroutine resumed once per emulated frame; every wait is a
-- yield loop over real memory state (closed loop, no frame-perfect timing).
-- Asserts read the decomp's own structs; UI is driven only where the event
-- engine demands real combat (deaths must go through battle, not HP pokes).

dofile(PLAYTEST_SYMDIR .. "/symbols.lua")
-- PROCSCR: proc-script address -> exact symbol. Proc identity must never come from the
-- PROC_NAME string at proc+0x10 -- the decomp reuses those (E_FACE twice, bmenu three
-- times), which is why freeze reports could not say which proc was waiting (#236).
dofile(PLAYTEST_SYMDIR .. "/procscr.lua")
-- It is generated (gitignored, written by gen_symbols.py from the ELF), so a stale or
-- half-written table is a total outage with a confusing error much later. Say so here.
assert(type(PROCSCR) == "table" and next(PROCSCR) ~= nil,
    "procscr.lua defined no PROCSCR table -- regenerate it: tools/playtest/gen_symbols.py")
-- The proc pool, read once per frame instead of once per question (procmemo.lua, #531).
-- Installed before anything touches `emu`: from here on the global is a guard that drops the
-- memo on every harness write, and PROCS.raw is the real emulator the hot reads bind to.
local PROCS = dofile(PLAYTEST_DIR .. "/procmemo.lua").install(_G,
    { base = SYM.sProcArray, stride = 0x6C, count = 64 })
local Controller = dofile(PLAYTEST_DIR .. "/controller.lua")
local Recorder = dofile(PLAYTEST_DIR .. "/recorder.lua")

-- Struct offsets, from the decomp headers (stable; addresses are not):
--   include/types.h  struct PlaySt: +0x0E chapterIndex, +0x0F faction
--                    (0x00 player / 0x40 NPC / 0x80 enemy), +0x10 turn
--   include/types.h  struct BmSt:   +0x14 playerCursor (s16 x, s16 y)
--   include/bmunit.h struct Unit (0x48 bytes): +0x00 pCharacterData,
--                    +0x0C state, +0x10 x, +0x11 y, +0x12 maxHP, +0x13 curHP,
--                    +0x14 pow, +0x16 spd, +0x17 def, +0x18 res, +0x19 lck
--   CharacterData: +0x04 = character id (include/bmunit.h)
--   src/proc.c sProcArray: 64 procs x 0x6C; +0x00 = proc_script
-- (Unit/Item/CharacterData reads live in board.lua, the one board reader.)
-- Harness tuning, in ONE table rather than one local apiece: harness.lua is a single Lua
-- chunk and Lua caps a function at 200 locals (`check_lua_local_headroom` measures what is
-- left), so enough new top-level locals stop the WHOLE FILE loading and every scenario dies
-- at once (#232).
local TUNE = {
    sandboxHeartbeat = 600,   -- a log line every this many sandbox frames: a long think shows progress
    -- How many times one guarded input may be re-pressed into an unchanged, still-legal
    -- state before failing closed. FE8 drops input during window fade-ins, so a single
    -- press can be lost outright -- see guardedInput.
    inputAttempts = 3,
    -- Frames a RETRY waits. Only ever reached after the caller's own budget has already
    -- elapsed, so this lengthens failures -- it never shortens a success.
    retrySettle = 60,
    -- How long one attack may take before the combat wait gives up. Measured: an
    -- UNSKIPPED ch00 boss animation is 1238 frames, and vanilla's worst cases (crit, a
    -- double, a level-up, a promotion) run well past that -- see chooseAttack.
    combatFrames = 3600,
    -- How long an ENEMY PHASE may run before it is called wedged. A phase is not only units
    -- stepping: ch04's parley phase plays a full CUTSCENE and then the chapter's own ending
    -- inside it, and it was still running -- chapter unchanged, faction still red -- 3,768
    -- frames in, with the chapter not flipping until past 9,800. The old flat 3,600 therefore
    -- gave up mid-scene and reported a phase timeout on a chapter clear_ch04_parley cleared
    -- and chained out of (#335). Sibling of the budget bug awaitControllerState had: both
    -- assumed a fixed cadence for something that legitimately contains a scene.
    --
    -- This is a WEDGE-CATCHER, not an estimate of a phase's length. In a healthy run it is
    -- never reached -- the loop returns the moment control comes back, or the moment the
    -- chapter ends under it -- so a generous value costs a passing run nothing and only bounds
    -- how long a genuinely stuck phase takes to report itself. Staying inside run.sh's
    -- deadline is what keeps that report a NAMED trace rather than a killed run.
    enemyPhaseFrames = 20000,
    -- How many times a wait may back out of an unwanted screen before failing closed.
    stuckRecoveries = 2,
    -- A save slot takes TWO confirms; the prompt must be gone within this allowance.
    saveConfirms = 4,
    -- Steps a boot/scene loop may take before it gives up. This must NOT be the thing
    -- that decides failure: a cap that expires mid-scene reports a timeout naming nothing,
    -- which is exactly how ch01 stayed open through #232 (it was still advancing dialogue
    -- 263 frames before the old 12000-step cap ran out). INSPECT.watch is the failure oracle
    -- -- it speaks in stallFrames -- so this only has to be larger than any real scene.
    bootSteps = 36000,
    -- Frames between the two proc-pool samples an inspector snapshot takes. One sample
    -- cannot tell a frozen proc from a live one; two, a gap apart, can.
    inspectGap = 90,
    -- Frames cancelToPlayerMap may spend watching a screen TEAR DOWN before it gives up.
    -- Separate from the cancel count on purpose: a fading screen is progress, and a cap that
    -- counts it is a cap that decides failure.
    cancelFrames = 900,
    -- How long an UNCLASSIFIED transition may hold a byte-identical proc pool before the
    -- inspector calls it a stalled input wait. 600 frames is 10s of wall clock at 60fps --
    -- longer than any fade or animation, and far cheaper than the 12000-iteration boot
    -- loop that used to time out saying nothing (#232 ch01, #236).
    stallFrames = 600,
}
-- prologue/sandbox host on chapter slot 1; a chapter load-test (e.g. --ch03-boot on slot 4)
-- overrides via PT_HOST_CHAPTER so bootToMap/inChapter recognize the right slot.
local HOST_CHAPTER = PLAYTEST_HOST_CHAPTER or 1
-- Which difficulty mode a run selects on the New Game menu (PT_DIFFICULTY), defaulting to
-- NORMAL -- the mode that ships to most players and the one `difficulty.py` grades by
-- default. It has to be a declared default rather than "whatever the menu highlights":
-- FE8 initialises the menu to option 0 (TUTORIAL) and the harness only pressed A, so every
-- verdict this project produced before #303 graded the EASIEST mode while reading as
-- general. A scenario that genuinely wants another mode names it.
-- Hung off TUNE rather than taking two top-level locals: a top-level local spends the chunk's
-- shared local budget (`check_lua_local_headroom` guards it).
TUNE.difficultyIndex = { tutorial = 0, normal = 1, difficult = 2 }
TUNE.difficultyWant = (function()
    -- run.sh owns the default and always sends a value; this fallback only covers entry
    -- points that bypass it, and must agree with run.sh (pinned by test_playtest_harness).
    local requested = (PLAYTEST_DIFFICULTY ~= nil and PLAYTEST_DIFFICULTY ~= "")
        and PLAYTEST_DIFFICULTY or "normal"
    local index = TUNE.difficultyIndex[requested]
    if index == nil then
        error(string.format("PT_DIFFICULTY=%q is not one of tutorial, normal, difficult",
                            tostring(requested)))
    end
    return index
end)()
-- The inverse, DERIVED so the two cannot drift apart.
TUNE.difficultyName = (function()
    local out = {}
    for name, index in pairs(TUNE.difficultyIndex) do out[index] = name end
    return out
end)()
-- Lord select (#42): menu order = classed cast order (build_campaign PORTRAIT_MAP);
-- the LAST candidate (pinky, NEIMI slot) is benched by default under the 4-slot
-- deploy cap, so choosing them is the visible force-deploy differential.

local logfile = io.open(PLAYTEST_LOG, "w")
local controllerFault
-- The #236 state inspector, as ONE table rather than three top-level locals: Lua caps a
-- main chunk at 200 locals, this file is one main chunk, and crossing the cap stops the whole
-- harness loading (every scenario dies at once). Hang new helpers and runtime state off
-- INSPECT (TUNE holds tuning knobs only) or put the logic in controller.lua, which has a
-- unit suite and no such ceiling. HOW MUCH ROOM IS LEFT IS NEVER WRITTEN DOWN HERE: `check.py
-- check_lua_local_headroom` measures it and prints it on every `make check`, because the
-- hand-maintained number said "two free slots" in three files at once and was wrong in
-- all three within one PR (#241). `check_lua_chunks_load` fails the build on a crossing.
-- Most fields are assigned further down, next to the proc-pool reader they build on (the
-- frame counters right below). Declared this early so every scenario can reach it: a helper
-- hung on a table declared LATER (VISIT, line ~7400) is out of scope in any scenario written
-- above that line, which is why the shared R-on-a-name reader is INSPECT.helpAt and not
-- VISIT.help (#493).
local INSPECT = {}
-- Frames emulated so far, the sight sandbox's included, and never going back: a sandbox's load
-- rewinds the counter, so its frames are counted into INSPECT.sandboxFrames, and while one runs
-- the stamp holds at the frame it started from (INSPECT.sandboxAt). run.sh's progress and frame
-- budget read these stamps. On INSPECT, declared here for it: log() is the first reader.
INSPECT.sandboxFrames = 0
INSPECT.costs = { calls = 0, save = 0, load = 0, run = 0 }   -- the sandbox's spend (botApi costs)
INSPECT.framesRun = function()
    return (INSPECT.sandboxAt or emu:currentFrame()) + INSPECT.sandboxFrames
end
local function log(s)
    logfile:write(string.format("[f%06d] %s\n", INSPECT.framesRun(), s))
    logfile:flush()
end
local function result(verdict, why)
    if verdict == "PASS" and controllerFault then
        verdict = "FAIL"
        why = "controller fault: " .. controllerFault .. " (scenario reached: " .. why .. ")"
    end
    log("RESULT: " .. verdict .. " -- " .. why)
end
-- PLAYTEST_HEADLESS is set by run.sh when the scenario runs under mgba-headless, which
-- attaches NO video renderer: emu:screenshot() then null-derefs inside PNGWritePixels
-- (mCore_screenshot -> PNGWritePixels -> KERN_INVALID_ADDRESS at 0x0). That is a C
-- segfault, so the pcall below cannot catch it -- the call has to not happen at all.
-- This is the designed split, not a workaround: a `kind: verdict` scenario asserts on
-- MEMORY (INSPECT.units, activeMsg) and needs no pixels, while `record` and `diagnostic`
-- scenarios stay headed precisely because their output IS the picture.
-- Read as a GLOBAL, deliberately: this file is one Lua chunk with a 200-local cap
-- (decisions.md -> "`harness.lua` is ONE Lua chunk"), and binding this to a top-level local
-- would spend a shared slot for no benefit.
local nshot = 0
local function shot(tag)
    nshot = nshot + 1
    local p = string.format("%s/%04d-%s.png", PLAYTEST_SHOTDIR, nshot, tag)
    if PLAYTEST_HEADLESS == "1" then
        log("screenshot SKIPPED (headless): " .. p)
        return
    end
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

-- Straight to the real emulator: a read cannot change the proc pool, so it skips the guard.
local function ru8(a) return PROCS.raw:read8(a) end
local function rs8(a)
    local v = PROCS.raw:read8(a)
    if v >= 0x80 then v = v - 0x100 end
    return v
end
local function ru16(a) return PROCS.raw:read16(a) end
local function ru32(a) return PROCS.raw:read32(a) end
local function rs16(a)
    local v = PROCS.raw:read16(a)
    if v >= 0x8000 then v = v - 0x10000 end
    return v
end

local function chapter() return ru8(SYM.gPlaySt + 0x0E) end
local function faction() return ru8(SYM.gPlaySt + 0x0F) end
local function turn() return ru16(SYM.gPlaySt + 0x10) end
local function cursor() return rs16(SYM.gBmSt + 0x14), rs16(SYM.gBmSt + 0x16) end

local function procActive(scriptAddr) return PROCS.find(scriptAddr) ~= nil end
-- The menu taking input. A submenu (StartMenuAt with a parent menu: an item's Use/Equip/
-- Trade/Discard, uimenu.c) LOCKS its parent (+0x28) and reads the keys itself, and the pool
-- gives it whichever slot is free, so it can sit ABOVE the parent. The lowest-slot menu is
-- then the locked parent, the observer saw "menu is locked" for as long as the submenu was up,
-- and goodberry FAILed on a submenu that had opened on the first frame (#531, item 10). So
-- when the lowest menu is locked, an unlocked menu proc that DESCENDS from it wins (Proc.proc_parent
-- at +0x14, proc.h; a few hops, for a submenu of a submenu) -- never an unrelated menu that merely
-- happens to be unlocked. With none, the lowest.
local function anyMenuProc()
    local lowest = PROCS.find(SYM.sProc_MenuMain) or PROCS.find(SYM.sProc_Menu)
    if not lowest or ru8(lowest + 0x28) == 0 then return lowest end
    for _, script in ipairs({ SYM.sProc_MenuMain, SYM.sProc_Menu }) do
        for _, p in ipairs(PROCS.live()) do
            if p.script == script and ru8(p.addr + 0x28) == 0 then
                local up, pool = ru32(p.addr + 0x14), PROCS.pool
                for _ = 1, 4 do
                    if up == lowest then return p.addr end
                    -- Only a slot of the proc pool (src/proc.c sProcArray) is a proc to step
                    -- up from. A root proc's parent is its tree index 0-7 (proc.c:
                    -- `proc_parent = (ProcPtr) rootIndex`), and any other word is not ours
                    -- to dereference: either way, not a descendant.
                    local off = up - pool.base
                    if off < 0 or off >= pool.count * pool.stride or off % pool.stride ~= 0 then
                        break
                    end
                    up = ru32(up + 0x14)
                end
            end
        end
    end
    return lowest
end
local function activeMenuProc()
    local addr = anyMenuProc()
    if not addr or ru8(addr + 0x28) ~= 0 or (ru8(addr + 0x63) & 0xC4) ~= 0 then return nil end
    return addr
end
local function menuOpen() return anyMenuProc() ~= nil end
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
-- board.lua is the ONE board reader (#510 step 9): unitAt, the clear-bot's enemy tables and
-- the LLM export all read through it. Bound once here so it costs one top-level local.
local BOARD = dofile(PLAYTEST_DIR .. "/board.lua").bind(
    { u8 = ru8, s8 = rs8, u16 = ru16, u32 = ru32 }, SYM)
-- One array slot, LEAN (board.lua's leanAt: addr, slot, charId, x, y, onMap, onField, hp,
-- maxhp, level, pow, def, state, dead, acted), or nil for an empty slot. ~100 callers, many
-- inside per-frame waits, so it never pays for the item/boss reads: those are BOARD.read's.
local function unitAt(base, i) return BOARD.leanAt(base, i) end
-- Lookup by character id is board.lua's (Board.find), LEAN, over the faction's whole array.
-- Array bounds are the DECOMP's, not the roster size of the day (bmunit.h: blue[62] /
-- red[50] / green[20]). `blue` searched 8 for as long as the cast WAS 8; the TESTCH sandbox
-- then deployed 11 and a unit standing on the map read as "not deployed". A scan bound is a
-- property of the engine, never of the current content.
local function blue(charId) return BOARD.find("blue", charId) end
local function red(charId) return BOARD.find("red", charId) end
local function isDead(u) return u == nil or u.dead end

-- A loss: the game-over screen, or the title it falls back to without the chapter advancing.
INSPECT.chapterLost = function()
    return gameOverActive() or procActive(SYM.gProcScr_TitleScreen)
end

-- A unit's attack reach, read LIVE from u.addr (a caller may hold `u` across a trade): the
-- weapon FE8 has equipped (GetUnitEquippedWeapon, run in sight.lua's sandbox) and its range,
-- as (minRange, maxRange), or nil for a staff / non-attacker. INSPECT.attackRange is filled in
-- below, beside the sandbox's api (INSPECT.sightApi).
local function unitAttackRange(u) return INSPECT.attackRange(u) end

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
    -- Every call site discards this return, and a checkpoint builder that "succeeds"
    -- while writing nothing is the worst shape of failure here: run.sh stamps the
    -- .romhash on the builder's PASS, so a dead state then looks FRESH forever and the
    -- scenario that needs it fails on every future run. mgba-headless does exactly this
    -- (returns false, writes 397312 bytes of zeros), which is why run.sh keeps checkpoint
    -- builders headed -- but the guard belongs here too, where the failure is visible.
    if not ok then
        -- Deliberately does NOT contain the word "pass": run.sh classifies a verdict by
        -- matching the RESULT line, and this message travels inside it.
        controllerFault = "saveStateFile failed for '" .. name .. "' -- no state was written"
    end
    return ok
end
local function loadState(name)
    local ok = false
    pcall(function() ok = emu:loadStateFile(statePath(name)) end)
    log("loadState " .. name .. " -> " .. tostring(ok))
    return ok
end

-- ============================================================================
-- GENERIC CUTSCENE RECORDER (record-tooling generalized 2026-07-09)
-- Every dialogue-cutscene record* scenario is the SAME loop with different params:
-- load a pre-built save-state, set text speed, take an optional pre-step, then
-- screenshot on a cadence while advancing observed dialogue waits, until a terminal proc (or a
-- frame cap). `recordCutscene` is that loop; the `recordscene` scenario (far below)
-- exposes it to PT_* env vars so ANY cutscene can be recorded with no new Lua.
-- Defined HERE, well above recordscene -- a Lua local is only visible lexically after its
-- definition, so it must precede every scenario that uses it.
--   opts:
--     state      save-state to load (nil/"" = record from the current position)
--     tag        frame filename tag (default "scene")
--     until_     terminal condition: a function, or "prep" (-> Preparations),
--                "title" (-> title screen), "chapter" (-> chapter advanced), or
--                nil/"" (frame cap only)
--     speed      "normal" (typewriter + face fades animate; default) | "fast"
--     maxFrames  safety cap (default 6000)
--     shotEvery  screenshot cadence in frames (default 4)
--     pressEvery legacy compatibility flag: >0 enables state-gated dialogue advance;
--                0 disables it. Its numeric cadence is intentionally ignored.
--     pre        optional fn run once after load, before the loop; return false, reason to fail
--     afterPre   optional cleanup fn, guaranteed after pre returns or raises
--     post       optional fn(reachedEnd) run once after the loop (e.g. a final "title" shot)
local controllerState, guardedInput, freezeReport
local function recordCutscene(o)
    o = o or {}
    local tag = o.tag or "scene"
    wait(o.settle or 30)   -- let the core settle past boot before loading
    if o.state and o.state ~= "" then
        if not loadState(o.state) then
            return result("FAIL", "no '" .. o.state .. "' checkpoint (run.sh builds it)")
        end
        wait(20)
    end
    if o.speed == "fast" then pokeFastConfig() else pokeNormalConfig() end
    if o.pre then
        local preOk, preWhy = Recorder.runSetup(o.pre, o.afterPre)
        if preOk == false then
            return result("FAIL", tag .. " setup failed: " .. tostring(preWhy or "unknown failure"))
        end
    elseif o.afterPre then
        o.afterPre()
    end
    local startCh = chapter()
    local doneFn
    if type(o.until_) == "function" then doneFn = o.until_
    elseif o.until_ == "prep" then doneFn = function() return procActive(SYM.gProcScr_SALLYCURSOR) end
    elseif o.until_ == "title" then doneFn = function() return procActive(SYM.gProcScr_TitleScreen) end
    elseif o.until_ == "chapter" then doneFn = function() return chapter() ~= startCh end
    else doneFn = function() return false end end
    local maxFrames = o.maxFrames or 6000
    -- PT_SHOTEVERY overrides any scenario's cadence; 0 films nothing.
    local shotEvery = tonumber(PLAYTEST_SHOTEVERY or "") or o.shotEvery or 4
    local autoAdvanceDialogue = ((o.pressEvery ~= nil) and o.pressEvery or 60) > 0
    local reached, fr = false, 0
    while fr < maxFrames do
        fr = fr + 1
        if shotEvery > 0 and fr % shotEvery == 0 then shot(tag) end
        -- Let a function terminal observe the frame before the recorder consumes an
        -- input state.  #260's turn-event proof remembers that dialogue_wait occurred;
        -- checking only after the guarded A press made a good four-box scene time out.
        if doneFn() then reached = true break end
        if autoAdvanceDialogue and controllerState() == "dialogue_wait" then
            if not INSPECT.advanceDialogue(120) then
                return result("FAIL", tag .. " dialogue input postcondition failed")
            end
        end
        yield()
    end
    shot(tag)
    if o.post then o.post(reached) end
    local hasEnd = (type(o.until_) == "function") or (o.until_ and o.until_ ~= "")
    if hasEnd and not reached then
        return result("FAIL", tag .. " cutscene never reached its end (" .. tostring(o.until_) .. ")")
    end
    return result("PASS", tag .. " cutscene recorded")
end

-- A live unit of any faction stands on (x, y), over the decomp's array bounds (#531: this
-- scanned 24 slots per faction, so red 24-49 and blue 24-61 never occupied anything).
local function tileOccupied(x, y) return BOARD.occupied(x, y) end

-- Live map state used by both scenarios and the controller observer.
local function mapUnitRow(y) return ru32(ru32(SYM.gBmMapUnit) + y * 4) end
local function mapUnitAt(x, y) return ru8(mapUnitRow(y) + x) end
local function setMapUnit(x, y, v) emu:write8(mapUnitRow(y) + x, v) end
local function mapSize() return rs16(SYM.gBmMapSize), rs16(SYM.gBmMapSize + 2) end

-- THE ONE PLACE A UNIT IS STOOD ON A TILE (#531 audit 4; the logic is board.lua's Board.place).
-- Bounds come from the LIVE map size, never a literal, and an off-map tile is REFUSED: it logs,
-- latches a controller fault (so a later PASS reports FAIL naming the tile) and returns false.
-- Declared here, on INSPECT, because a helper hung on a table declared further down (VISIT) is
-- out of scope in every scenario above it. `o.grid` / `o.vacate` are Board.place's.
INSPECT.io = {
    rs8 = function(a) return rs8(a) end, write8 = function(a, v) emu:write8(a, v) end,
    grid = mapUnitAt, setGrid = setMapUnit,
}
-- Refill a unit to full HP and no further: its max is what the engine and the AI read it at.
function INSPECT.fullHeal(u) emu:write8(u.addr + 0x13, u.maxhp) end

function INSPECT.place(u, x, y, o)
    local w, h = mapSize()
    local ok, why = BOARD.place(INSPECT.io, u.addr, x, y, w, h, o)
    if not ok then
        log("place REFUSED: " .. why)
        controllerFault = controllerFault or ("place refused: " .. why)
    end
    return ok
end
-- First tile beside `anchor` ({x, y}) in `o.order` (default E, W, S, N) that is on the map, empty
-- in the grid and passes `o.passable(x, y)`. Returns x, y or nil.
INSPECT.EWSN = { { 1, 0 }, { -1, 0 }, { 0, 1 }, { 0, -1 } }
function INSPECT.freeBeside(anchor, o)
    o = o or {}
    local w, h = mapSize()
    return BOARD.freeBeside(INSPECT.io, anchor.x, anchor.y, o.order or INSPECT.EWSN, w, h, o.passable)
end

-- ---------------------------------------------------------------- state-driven controller
-- Function pointers in Proc fields are Thumb pointers; nm emits the even symbol address.
local function codeAddr(a) return a & 0xFFFFFFFE end
local CALLBACK_NAMES = {
    [SYM.GameIntroHealthSafetyWaitButton] = "health_safety_wait",
    [SYM.Title_IDLE] = "title_idle",
    [SYM.SameMenu_CtrlLoop] = "save_menu_input",
    [SYM.SaveMenu_SaveSlotSelectLoop] = "save_slot_input",
    [SYM.DifficultySelect_Loop_KeyHandler] = "difficulty_input",
    [SYM.ChapterIntro_KeyListen_Loop] = "chapter_intro_input",
    [SYM.TalkWaitForInput_OnIdle] = "talk_wait_input",
    [SYM.YesNoChoice_Loop_KeyHandler] = "yes_no_input",
    [SYM.TalkChoice_OnIdle] = "talk_choice_input",
    [SYM.Menu_OnIdle] = "menu_input",
    [SYM.PrepMenu_CtrlLoop] = "prep_menu_input",
    [SYM.ProcPrepUnit_Idle] = "prep_units_input",
    [SYM.PlayerPhase_MainIdle] = "player_main_idle",
    [SYM.PlayerPhase_RangeDisplayIdle] = "player_range_idle",
    [SYM.PlayerPhase_WaitForUnitMovement] = "player_move_wait",
    [SYM.TargetSelection_Loop] = "target_selection_input",
    [SYM.BattleForecast_LoopDisplay] = "battle_forecast_display",
    [SYM.sub_8091AEC] = "unit_list_input",
    [SYM.PrepItemSupply_Loop_GiveTakeKeyHandler] = "supply_input",
    [SYM.StatScreen_OnIdle] = "stat_screen_input",
    [SYM.HbMoveCtrl_OnIdle] = "help_box_input",
    [SYM.Shop_Loop_BuyKeyHandler] = "shop_buy_input",
    [SYM.WorldMap_Loop] = "world_map_input",
}
local PREP_CALLBACK_NAMES = {
    [SYM.PrepScreenMenu_OnStartPress] = "prep_main_fight",
    [SYM.PrepScreenMenu_OnBPress] = "prep_main_check_map",
    [SYM.PrepScreenMenu_OnPickUnits] = "prep_pick_units",
    [SYM.PrepMapMenu_OnStartPress] = "prep_map_fight",
    [SYM.PrepMapMenu_OnBPress] = "prep_map_back",
}
local function callbackName(a, names)
    if a == 0 then return nil end
    a = codeAddr(a)
    return (names or CALLBACK_NAMES)[a] or string.format("0x%08X", a)
end
local function observedProc(script, idleName)
    local addr = PROCS.find(script)
    if not addr then return nil end
    return { addr = addr, idle = idleName or callbackName(ru32(addr + 0x0C)) }
end
local function observeMenu(observation)
    local addr = activeMenuProc()
    if not addr then return end
    local count = ru8(addr + 0x60)
    if count == 0 or count > 11 then
        observation.error = string.format("malformed MenuProc itemCount=%d", count)
        return
    end
    local menuDef = ru32(addr + 0x30)
    local menu = {
        current = ru8(addr + 0x61), items = {},
        on_b = menuDef ~= 0 and callbackName(ru32(menuDef + 0x18)) or nil,
    }
    if menu.current >= count then
        observation.error = string.format("malformed MenuProc current=%d count=%d", menu.current, count)
        return
    end
    for slot = 0, count - 1 do
        local item = ru32(addr + 0x34 + slot * 4)
        local def = item ~= 0 and ru32(item + 0x30) or 0
        if item == 0 or def == 0 then
            observation.error = string.format("malformed MenuProc item[%d]", slot)
            return
        end
        menu.items[#menu.items + 1] = {
            slot = slot,
            override_id = ru8(def + 0x09),
            availability = ru8(item + 0x3D),
            on_selected = callbackName(ru32(def + 0x14)),
        }
    end
    observation.menu = menu
end
local function observePrep(observation)
    local addr = PROCS.find(SYM.ProcScr_PrepMenu)
    if not addr then return end
    local count = ru8(addr + 0x2B)
    -- 0 rows is a menu being built, not a broken one: PrepMenu_OnInit zeroes max_index and the
    -- rows follow a frame later (vanilla Ch6, after Pick Units: one frame at 0, then 5).
    if count == 0 then return end
    if count > 8 then
        observation.error = string.format("malformed ProcPrepMenu max_index=%d", count)
        return
    end
    local prep = {
        current = ru8(addr + 0x2A),
        help_open = ru8(addr + 0x29) ~= 0,
        items = {},
        on_b = callbackName(ru32(addr + 0x58), PREP_CALLBACK_NAMES),
        on_start = callbackName(ru32(addr + 0x5C), PREP_CALLBACK_NAMES),
    }
    if prep.current >= count then
        observation.error = string.format("malformed ProcPrepMenu current=%d count=%d", prep.current, count)
        return
    end
    for slot = 0, count - 1 do
        local item = ru32(addr + 0x38 + slot * 4)
        if item == 0 then
            observation.error = string.format("malformed ProcPrepMenu cmd[%d]", slot)
            return
        end
        prep.items[#prep.items + 1] = {
            slot = slot,
            effect = callbackName(ru32(item + 0x2C), PREP_CALLBACK_NAMES),
            color = ru8(item + 0x38),
            index = ru8(item + 0x39),
        }
    end
    observation.prep = prep
end
local function observeTarget(observation)
    local addr = PROCS.find(SYM.gProcScr_TargetSelection)
    if not addr then return end
    local current = ru32(addr + 0x30)
    local routines = ru32(addr + 0x2C)
    if current == 0 then
        observation.error = "malformed SelectTargetProc currentTarget=NULL"
        return
    end
    local kind
    if routines == SYM.gSelectInfo_Attack then kind = "attack"
    elseif routines == SYM.gSelectInfo_Talk then kind = "talk"
    elseif routines == SYM.gSelectInfo_Heal then kind = "heal"
    else kind = string.format("0x%08X", routines) end
    observation.target = {
        kind = kind,
        x = rs8(current), y = rs8(current + 1), uid = ru8(current + 2),
        extra = ru8(current + 3), frozen = (ru8(addr + 0x34) & 0x40) ~= 0,
    }
end
local function observedUnit(unitId)
    if unitId == 0 or unitId >= 0xC0 then return nil end
    local unit = ru32(SYM.gUnitLookup + unitId * 4)
    if unit == 0 then return nil end
    local character = ru32(unit)
    local class = ru32(unit + 4)
    return {
        state = ru32(unit + 0x0C),
        status = ru8(unit + 0x30) & 0xF,
        attributes = (character ~= 0 and ru32(character + 0x28) or 0)
            | (class ~= 0 and ru32(class + 0x28) or 0),
    }
end
local function unitSelectKind(unitId, unit)
    if unitId == 0 then return "no_unit" end
    if not unit then return nil end
    if (unitId & 0xC0) ~= faction() then return "no_control" end
    if (unit.state & 0x2) ~= 0 or (unit.attributes & 0x100000) ~= 0 then return "turn_ended" end
    if unit.status == 2 or unit.status == 4 then return "no_control" end
    return "control"
end
local function observeController()
    local observation = {
        procs = {}, raw_procs = {},
        world = { chapter = chapter(), faction = faction(), turn = turn(), host_chapter = HOST_CHAPTER },
    }
    for _, proc in ipairs(PROCS.live()) do
        local addr = proc.addr
        observation.raw_procs[#observation.raw_procs + 1] = {
            -- scrCur is the script command the proc sits on (include/proc.h). It is the
            -- liveness signal the stall detector keys on: a pool whose every proc holds
            -- the same command, idle and lock for TUNE.stallFrames is not slow, it is
            -- waiting for an input nothing will send (#236).
            -- sleepTime (+0x24) is in there because those three fields are CONSTANT
            -- under PROC_REPEAT -- which is how every long-running FE8 proc is written
            -- -- so without it a proc counting down a timed wait reads as frozen (#241).
            slot = proc.slot, script = proc.script, scr_cur = ru32(addr + 0x04),
            idle = ru32(addr + 0x0C), sleep = rs16(addr + 0x24), lock = ru8(addr + 0x28),
        }
    end
    local function put(name, value) if value then observation.procs[name] = value end end
    put("game_control", observedProc(SYM.gProcScr_GameControl, "game_control_root"))
    put("game_early_start", observedProc(SYM.ProcScr_GameEarlyStartUI))
    put("title", observedProc(SYM.gProcScr_TitleScreen))
    -- Two different proc scripts draw a save screen: the New Game one and the
    -- between-chapters prompt. They share SaveMenu_SaveSlotSelectLoop, so classify()
    -- needs no new state -- but watching only the first left the post-chapter prompt
    -- invisible, and the ch00 -> ch01 flow sat on it until it timed out (#232).
    put("save_menu", observedProc(SYM.ProcScr_SaveMenu)
        or observedProc(SYM.gProcScr_SaveMenuPostChapter))
    local diffProc = observedProc(SYM.ProcScr_NewGameDifficultySelect)
    put("difficulty", diffProc)
    if diffProc then
        -- struct DifficultyMenuProc.current_selection is a u8 @ +0x30 (savemenu.h:178).
        -- 0 = Tutorial, 1 = Normal, 2 = Difficult -- SaveMenuWriteNewGame maps those to
        -- (isTutorial, isDifficult) = (0,0)/(1,0)/(1,1) -> config.controller + PLAY_FLAG_HARD.
        observation.difficulty = {
            current = ru8(diffProc.addr + 0x30),
            want = TUNE.difficultyWant,
        }
    end
    local introKey = observedProc(SYM.ProcScr_ChapterIntro_KeyListen)
    put("chapter_intro", introKey or observedProc(SYM.gProcScr_ChapterIntro))
    put("talk_wait", observedProc(SYM.gProcScr_TalkWaitForInput))
    local yesNo = observedProc(SYM.gProcScr_YesNoChoice)
    local talkChoice = observedProc(SYM.gProcScr_TalkChoice)
    put("yes_no", yesNo)
    put("talk_choice", talkChoice)
    if yesNo or talkChoice then
        -- Both struct YesNoChoiceProc.currentChoice (include/cgtext.h) and struct
        -- TalkChoiceProc.selectedChoice (include/scene.h) are s16 @ +0x2A;
        -- TALK_CHOICE_YES = 1 / TALK_CHOICE_NO = 2.
        local choiceProc = yesNo or talkChoice
        local choice = rs16(choiceProc.addr + 0x2A)
        observation.choice = {
            current = (choice == 1 and "yes") or (choice == 2 and "no") or nil,
            raw = choice,
        }
        if not observation.choice.current then
            observation.error = string.format("malformed choice proc currentChoice=%d", choice)
        end
    end
    local rawMenu = anyMenuProc()
    put("menu", rawMenu and { addr = rawMenu, idle = callbackName(ru32(rawMenu + 0x0C)),
        locked = ru8(rawMenu + 0x28) ~= 0, frozen = (ru8(rawMenu + 0x63) & 0x40) ~= 0,
        ending = (ru8(rawMenu + 0x63) & 0x04) ~= 0,
        doomed = (ru8(rawMenu + 0x63) & 0x80) ~= 0 })
    put("at_menu", observedProc(SYM.ProcScr_AtMenu, "at_menu_idle"))
    put("prep_menu", observedProc(SYM.ProcScr_PrepMenu))
    put("sally", observedProc(SYM.gProcScr_SALLYCURSOR, "sally_idle"))
    local pickUnits = observedProc(SYM.ProcScr_PrepUnitScreen)
    put("prep_units", pickUnits)
    if pickUnits then
        -- struct ProcPrepUnit (include/prepscreen.h). list_num_cur is where the cursor IS,
        -- list_num_pre where it has settled -- ProcPrepUnit_Idle reads no keys at all while
        -- they differ. count is the live roster length (gPrepUnitList.max_num, what
        -- PrepGetUnitAmount returns), which is what bounds a RIGHT or DOWN off the end.
        observation.prep_units = {
            cursor = ru16(pickUnits.addr + 0x2E),
            settled = ru16(pickUnits.addr + 0x2C) == ru16(pickUnits.addr + 0x2E),
            deployed = ru8(pickUnits.addr + 0x29), cap = ru8(pickUnits.addr + 0x2A),
            count = ru32(SYM.gPrepUnitList + 0x100),
        }
    end
    put("supply_screen", observedProc(SYM.ProcScr_BmSupplyScreen))
    local shop = observedProc(SYM.gProcScr_Shop)
    put("shop", shop)
    if shop then
        -- struct ShopState (bmshop.h): the list's hand is head_loc; IsShopPageScrolling is
        -- bg2_off ~= hand_loc * px_per_line. ProcShop.shopItemCount is +0x5A.
        local st = SYM.sShopState
        observation.shop = {
            cursor = ru16(st), count = ru8(shop.addr + 0x5A),
            scrolling = ru16(st + 0x0C) ~= ru16(st + 0x06) * ru16(st + 0x08),
        }
    end
    local worldMap = observedProc(SYM.ProcScr_WorldMapMain)
    put("world_map", worldMap)
    if worldMap then observation.world_map = INSPECT.worldMap() end
    put("stat_screen", observedProc(SYM.gProcScr_StatScreen))
    local helpBox = observedProc(SYM.gProcScr_HelpBoxMoveCtrl)
    put("help_box", helpBox)
    if helpBox then
        -- struct HelpBoxProc (statscreen.h): +0x2C is the HelpBoxInfo the box points at, whose
        -- +0x08 is adjLeft -- the entry LEFT moves to, NULL where LEFT goes nowhere.
        local info = ru32(helpBox.addr + 0x2C)
        observation.help_box = { info = info, left = info ~= 0 and ru32(info + 0x08) ~= 0 }
    end
    local unitList = observedProc(SYM.ProcScr_UnitListScreen_Field)
    put("unit_list", unitList)
    if unitList then
        -- struct UnitListScreenProc (include/unitlistscreen.h). unk_30 is the ROSTER index
        -- the key handler moves; unk_2c is only where that lands on screen, and it clamps
        -- while the list scrolls under it. unk_29 != 0 means a scroll is animating and
        -- sub_809144C is not running, so no D-pad press would be read.
        -- `count` is gUnknown_0200F158, the number of units the screen actually sorted, and
        -- it is what sub_809144C bounds DOWN against. The proc's OWN allyCount (+0x3A) is
        -- deliberately not used: StartUnitListScreenField writes only `mode`, so on the
        -- map-menu list that field holds whatever was in the proc slot -- it read 0 in the
        -- TESTCH sandbox, and a roster walk sized off it stops before it starts (#238).
        observation.unit_list = {
            row = ru8(unitList.addr + 0x30), screen_row = ru8(unitList.addr + 0x2C),
            page = ru8(unitList.addr + 0x2F), count = ru8(SYM.gUnknown_0200F158),
            scrolling = ru8(unitList.addr + 0x29) ~= 0,
        }
        -- screen_row and page are not read by controller.lua. They are kept because every
        -- observation is written into the trace record, so they are what a failed roster walk
        -- is diagnosed FROM -- "row moved but screen_row clamped" is the whole story of the
        -- bug this replaced. Unused-by-the-classifier is not unused.
        -- allyCount (+0x3A) and deployedCount (+0x3B) are deliberately NOT observed. They are
        -- written by StartUnitListScreenPrepMenu only, so on this list they are whatever the
        -- proc slot held -- and an untrustworthy field in the observation is how the walk
        -- above came to be sized off a roster of "0".
    end
    put("map_fade", observedProc(SYM.sProcScr_BMXFADE, "map_fade"))
    put("player_phase", observedProc(SYM.gProcScr_PlayerPhase))
    put("target_selection", observedProc(SYM.gProcScr_TargetSelection))
    put("battle_forecast", observedProc(SYM.gProcScr_BKSEL))
    put("std_event", observedProc(SYM.ProcScr_StdEventEngine, "event_engine"))
    put("battle", observedProc(SYM.gProc_ekrBattle, "battle_loop")
        or observedProc(SYM.ProcScr_BattleEventEngine, "battle_event"))
    observeMenu(observation)
    observePrep(observation)
    observeTarget(observation)
    local x, y = cursor()
    local w, h = mapSize()
    if w > 0 and h > 0 and x >= 0 and y >= 0 and x < w and y < h then
        local unit = mapUnitAt(x, y)
        local rows = ru32(SYM.gBmMapMovement)
        local reachable = false
        if rows ~= 0 then
            local row = ru32(rows + y * 4)
            reachable = row ~= 0 and ru8(row + x) < 120
        end
        local unitFaction
        if unit ~= 0 then
            unitFaction = unit < 0x40 and "blue" or (unit < 0x80 and "green" or "red")
        end
        local unitData = observedUnit(unit)
        local selectKind = unitSelectKind(unit, unitData)
        if unit > 0 and unit < 0xC0 and not unitData then
            observation.error = string.format("gBmMapUnit id 0x%02X has no gUnitLookup entry", unit)
        end
        observation.cursor = {
            x = x, y = y, width = w, height = h, unit = unit,
            unit_faction = unitFaction, unit_state = unitData and unitData.state or nil,
            unit_status = unitData and unitData.status or nil,
            unit_attributes = unitData and unitData.attributes or nil,
            unit_select_kind = selectKind, unit_selectable = selectKind == "control",
            reachable = reachable,
        }
    end
    return observation
end
controllerState = function(observation)
    local state, why = Controller.classify(observation or observeController())
    return state, why
end
local function legalNames(actions)
    local names = {}
    for _, action in ipairs(actions or {}) do names[#names + 1] = action.intention end
    return names
end
local function traceInput(before, actions, intention, key, expected, verdict, after)
    local state, why = controllerState(before)
    before.classification = state or "unsupported"
    before.classification_error = why
    after = after or before
    local afterState, afterWhy = controllerState(after)
    after.classification = afterState or "unsupported"
    after.classification_error = afterWhy
    if verdict == "pass" then
        before.raw_procs = nil
        after.raw_procs = nil
    end
    log(Controller.formatTrace({
        state = state or "unsupported", legal = legalNames(actions), intention = intention,
        input = key or "none", expected = expected, result = verdict,
        before = before, after = after,
    }))
    if verdict:match("^fail:") then
        controllerFault = controllerFault or (intention .. ": " .. verdict)
    end
end
local function traceFailure(intention, expected, verdict, observation, tag)
    observation = observation or observeController()
    local actions = Controller.legalActions(observation)
    traceInput(observation, actions, intention, "none", expected, verdict, observation)
    shot(tag or "controller-failure")
    -- Every terminal controller failure carries its inspector snapshot, so diagnosing one
    -- costs a log read instead of another build-and-run cycle (#236).
    INSPECT.snapshot(tag or "controller-failure")
end
guardedInput = function(intention, key, expected, predicate, frames)
    local before = observeController()
    local actions, why = Controller.legalActions(before)
    local chosen = actions and Controller.findAction(actions, intention) or nil
    if not chosen or chosen.key ~= key then
        traceInput(before, actions, intention, "none", expected, "fail:not-legal:" .. tostring(why), before)
        shot("controller-illegal-input")
        return false
    end
    -- FE8 drops input while a window is still animating in -- a battle forecast, a menu
    -- fading up. A single press that lands in that window is simply LOST, and the wait
    -- then burns its whole budget on a state nothing will ever move (#232: attacks that
    -- never committed, and the run wedged in target_selection from then on). So re-press,
    -- but only while this is still the SAME state offering the SAME legal action -- every
    -- attempt is re-observed and re-authorised, and the postcondition is unchanged. That
    -- is a bounded retry of one verified input, not the blind cadence #220 retired.
    -- The FIRST attempt keeps the caller's whole budget, so every input that already
    -- worked behaves exactly as before; a retry only happens where the old code had
    -- already failed. (Getting this wrong -- splitting the budget across attempts -- made
    -- the first press give up early and fire a second real action, which walked Marty off
    -- his parley tile and broke ch04packmath.)
    local budget = frames or 60
    local after, passed = before, false
    for attempt = 1, TUNE.inputAttempts do
        press(K[key], 3)
        after = observeController()
        passed = predicate(after, before)
        for _ = 1, (attempt == 1 and budget or TUNE.retrySettle) do
            if passed then break end
            yield()
            after = observeController()
            passed = predicate(after, before)
        end
        if passed or attempt == TUNE.inputAttempts then break end
        -- Only retry into an unchanged, still-legal state; anything else means the input
        -- DID land and the postcondition is simply wrong, which must stay a failure.
        local now = observeController()
        local nowActions = Controller.legalActions(now)
        if controllerState(now) ~= controllerState(before) then break end
        if not (nowActions and Controller.findAction(nowActions, intention)) then break end
    end
    traceInput(before, actions, intention, key, expected, passed and "pass" or "fail:postcondition", after)
    if not passed then shot("controller-postcondition") end
    return passed
end
local function selectSemantic(intention, expected, predicate, frames)
    for _ = 1, 12 do
        local observation = observeController()
        local actions, why = Controller.legalActions(observation)
        local wanted = actions and Controller.findAction(actions, intention) or nil
        if not wanted then
            traceInput(observation, actions, intention, "none", expected, "fail:not-legal:" .. tostring(why), observation)
            shot("controller-command-missing")
            return false
        end
        if wanted.key == "A" then return guardedInput(intention, "A", expected, predicate, frames) end
        -- A yes/no answer that is not highlighted moves with LEFT/RIGHT, not menu rows.
        -- Without this, `answer_no` was advertised as legal-but-select-it-first and NO
        -- driver could act on it -- the first scenario needing "No" would have failed on
        -- fail:no-live-target with the contract technically correct (#241).
        if intention == "answer_yes" or intention == "answer_no" then
            local move = Controller.findAction(
                actions, intention == "answer_no" and "select_no" or "select_yes")
            if not (move and move.key) then
                traceInput(observation, actions, intention, "none", expected,
                    "fail:no-choice-navigation", observation)
                return false
            end
            if not guardedInput(move.intention, move.key, "the live choice moves",
                function(after)
                    return after.choice ~= nil and after.choice.current ~= observation.choice.current
                end, 30) then return false end
        else
            local count = observation.menu and #observation.menu.items or 0
            if not wanted.target or count < 2 then
                traceInput(observation, actions, intention, "none", expected, "fail:no-live-target", observation)
                return false
            end
            local current = observation.menu.current
            local down = (wanted.target - current) % count
            local nav = down <= count - down and "menu_next" or "menu_previous"
            local key = nav == "menu_next" and "DOWN" or "UP"
            if not guardedInput(nav, key, "live menu selection changes", function(after)
                return after.menu ~= nil and after.menu.current ~= current
            end, 30) then return false end
        end
    end
    traceFailure(intention, expected, "fail:menu-navigation-budget", nil,
        "controller-menu-navigation")
    return false
end

-- ---------------------------------------------------------------- UI driving
-- The #220/#238 contract vets the INPUT -- is this press legal in this state -- but it cannot
-- vet the DESTINATION a caller asks for. Handed an off-map tile, this walked the cursor to the
-- wall and then reported "cursor_left is not legal", which is true and points at nothing: the
-- defect is upstream, in whatever chose the target. A clear-bot read one off a unit that was not
-- on the map and drove at (-1,8) on a 25-wide map (#335). Refuse it here, by name, so the trace
-- names the caller's mistake instead of the wall it ended up against.
local function cursorTo(tx, ty)
    local w, h = mapSize()
    if w > 0 and h > 0 and (tx < 0 or ty < 0 or tx >= w or ty >= h) then
        traceFailure("cursor_to", string.format("destination (%d,%d) is on the %dx%d map",
            tx, ty, w, h), "fail:off-map-destination", nil, "controller-off-map-destination")
        return false
    end
    for _ = 1, 120 do
        local cx, cy = cursor()
        if cx == tx and cy == ty then return true end
        local intention, key
        if cx < tx then intention, key = "cursor_right", "RIGHT"
        elseif cx > tx then intention, key = "cursor_left", "LEFT"
        elseif cy < ty then intention, key = "cursor_down", "DOWN"
        else intention, key = "cursor_up", "UP" end
        if not guardedInput(intention, key, string.format("cursor advances toward (%d,%d)", tx, ty),
            function()
                local nx, ny = cursor()
                return nx ~= cx or ny ~= cy
        end, 30) then return false end
    end
    traceFailure("cursor_to", string.format("cursor reaches (%d,%d)", tx, ty),
        "fail:cursor-navigation-budget", nil, "controller-cursor-navigation")
    return false
end

local function waitFor(pred, frames, tapA)
    for _ = 1, frames do
        if pred() then return true end
        local pressed = nil
        if tapA then pressed = INSPECT.answerWait(controllerState()) end
        if pressed == false then return false end
        if pressed == nil then yield() end
    end
    return false
end

-- Answer a wait the game puts to the player outside any menu the caller drives: a dialogue
-- box, or the full-bag chooser when the bot set INSPECT.onFullBag (a scenario without one
-- waits as before). FE8 raises the chooser in the ENEMY phase too, when a kill's drop lands on
-- a full bag (vanilla Ch3 t7, Colm's counter). true = answered, false = the press failed,
-- nil = nothing to answer here (the caller yields).
function INSPECT.answerWait(state)
    if state == "dialogue_wait" then return INSPECT.advanceDialogue(60) end
    if state == "send_to_convoy" and INSPECT.onFullBag then return INSPECT.onFullBag() end
    return nil
end

-- One guarded A on a dialogue box (#238: the only way a scenario presses through a box).
-- `frames` is the SITE's budget for the box to clear (60 / 120 / 300 are all in use and are
-- deliberately not unified); `expected` is the trace label; `clears` is the postcondition
-- when it is not "no longer dialogue_wait" (the arena's welcome page clears into a choice).
function INSPECT.advanceDialogue(frames, expected, clears)
    return guardedInput("advance_dialogue", "A", expected or "dialogue input wait clears",
        clears or function(after) return controllerState(after) ~= "dialogue_wait" end, frames)
end

-- "FE8 is back in player control", at five strengths. `phase` is the player phase with no
-- menu; `event` also waits out a turn/location event (StdEventEngine); `battle` also waits
-- out a battle event (BattleEventEngine); `idle` is `event` plus the controller classing
-- the map as player_map_idle -- a location event's tail still holds the controller when an
-- item lands, and moving then dies as "cursor could not reach" (ch05reliquaries). `fight`
-- is `phase` plus the battle animation proc being gone (a kill resolving).
function INSPECT.settled(level)
    if faction() ~= 0 or menuOpen() then return false end
    if level == "phase" then return true end
    if level == "fight" then return not procActive(SYM.gProc_ekrBattle) end
    if procActive(SYM.ProcScr_StdEventEngine) then return false end
    if level == "event" then return true end
    if level == "battle" then return not procActive(SYM.ProcScr_BattleEventEngine) end
    if level == "idle" then return controllerState() == "player_map_idle" end
    error("INSPECT.settled: unknown level " .. tostring(level))
end

-- Wait for `level` for at most `frames`; `tapA` is waitFor's own flag, passed through as the
-- site gave it (the kill-resolving `fight` waits are the sites that pass none).
function INSPECT.settle(level, frames, tapA)
    return waitFor(function() return INSPECT.settled(level) end, frames, tapA)
end

-- The "advance every box until done()" loop. `done` is polled each frame BEFORE the box test;
-- `o.tick(i)` runs before `done` (shots/snaps keyed to the frame); `o.onBox()` runs on each
-- dialogue_wait just before its press; `o.label` / `o.press` are advanceDialogue's label and
-- budget (default 120). Returns true when `done()` held, or false, "advance" when a press
-- did not clear its box, or false, "budget" when `budget` frames ran out.
function INSPECT.talkUntil(done, budget, o)
    o = o or {}
    for i = 1, budget do
        if o.tick then o.tick(i) end
        if done() then return true end
        if controllerState() == "dialogue_wait" then
            if o.onBox then o.onBox() end
            if not INSPECT.advanceDialogue(o.press or 120, o.label) then return false, "advance" end
        else
            yield()
        end
    end
    return false, "budget"
end

-- Wait until FE8 reaches `want`. `frames` bounds how long we tolerate NOTHING HAPPENING;
-- it is not a wall-clock cap, because waiting for the map to become playable routinely
-- spans a scene -- a chapter opening, a turn event, an enemy phase -- and no fixed budget
-- fits every one (#232: the ch01 opening outran 300 frames, so ch01win/lordfloor logged a
-- controller fault on a chapter they went on to clear; #335: clear_ch02's turn 1 did the
-- same on a ~2100-frame enemy phase of seven raiders). Controller.engineIsWorking owns what
-- counts as the engine working -- it is tested there, against observations, rather than
-- asserted here -- and STALL_CEILING keeps a genuinely wedged engine failing closed here
-- rather than at run.sh's wall-clock deadline.
local STALL_CEILING = 40
local function awaitControllerState(want, frames)
    local budget = frames or 300
    local idle, total, recoveries = 0, 0, 0
    local last
    while idle < budget and total < budget * STALL_CEILING do
        total = total + 1
        last = observeController()
        local state = controllerState(last)
        if state == want then return true end
        if not Controller.engineIsWorking(last) then idle = idle + 1 end
        -- Dialogue is never what a caller waits AT -- the targets are player_map_idle,
        -- unit_selected or a menu -- and FE8 interleaves text with play constantly: a
        -- turn event, a village line, a post-combat quote. Advancing it is a CLASSIFIED
        -- state with a legal action, driven through the same guarded single input as
        -- everything else, so this is the #220 contract, not the blind cadence #220
        -- retired. Without it every ch01 flow bailed on the first line of text (#232).
        if state == "dialogue_wait" and want ~= "dialogue_wait" then
            if not INSPECT.advanceDialogue(60) then return false end
        elseif state ~= "transition" then
            -- Nicolas's call, and it is how studios keep a suite moving: if we are parked
            -- somewhere the caller did not want, BACK OUT rather than die here -- a menu or
            -- a target selector we cannot commit is recoverable, and one wedged screen used
            -- to cost the entire remaining run (#232). This is not a blanket rescue: the
            -- cancel is a legal enumerated action, every recovery is TRACED so a real defect
            -- cannot hide behind it, and the allowance is small so a genuinely stuck screen
            -- still fails closed. (A silent version of this is precisely what let five
            -- defects sit unnoticed behind the old blind cadence.)
            -- Every enumerated way OUT of a screen, including the ones #238 named. Leaving
            -- close_supply/close_list off this list would mean a run that wandered into the
            -- convoy or the Character screen could not recover from it, even though the
            -- controller offers the exit.
            local legal = Controller.legalActions(last)
            local cancel = Controller.findAction(legal, "cancel_menu")
                or Controller.findAction(legal, "cancel_target")
                or Controller.findAction(legal, "cancel_selection")
                or Controller.findAction(legal, "close_supply")
                or Controller.findAction(legal, "close_list")
            if cancel and recoveries < TUNE.stuckRecoveries then
                recoveries = recoveries + 1
                traceInput(last, Controller.legalActions(last), cancel.intention, cancel.key,
                    "backing out of an unwanted " .. tostring(state), "recovered", last)
                press(K[cancel.key], 3)
            else
                traceFailure("await_state", want, "fail:unexpected-state:" .. tostring(state), last,
                    "controller-unexpected-state")
                return false
            end
        else
            yield()
        end
    end
    traceFailure("await_state", want, "fail:state-timeout", last, "controller-state-timeout")
    return false
end

-- The live movement map's cost for a tile; >= 120 means the selected unit cannot stand there.
local function reachCost(x, y)
    local row = ru32(ru32(SYM.gBmMapMovement) + y * 4)
    return ru8(row + x)
end

-- Select unit at (fx,fy), move to (tx,ty). True when the action menu opened.
--
-- False also means the plain, legal answer "this unit cannot reach that tile", and that is NOT a
-- controller fault. ch01's clear loop offers the seize tile to every unit in turn once the boss
-- dies; the ones out of range used to drive the cursor there and press A anyway, and FE8 --
-- correctly -- offers no confirm on an unreachable tile, so each attempt logged
-- `confirm_move: fail:not-legal` and the sticky fault failed a run that went on to WIN (#335).
-- The movement map is already on screen once the unit is selected, so ask it before pressing.
local function moveUnit(fx, fy, tx, ty)
    if not awaitControllerState("player_map_idle", 300) then return false end
    if not cursorTo(fx, fy) then return false end
    if not guardedInput("select_unit", "A", "PlayerPhase enters movement-range input", function(after)
        return controllerState(after) == "unit_selected"
    end, 120) then return false end
    if reachCost(tx, ty) >= 120 then
        -- Back out through the enumerated cancel, so the next unit starts from a clean map.
        guardedInput("cancel_selection", "B", "selection returns to the live map", function(after)
            return controllerState(after) == "player_map_idle"
        end, 120)
        return false
    end
    if not cursorTo(tx, ty) then return false end
    return guardedInput("confirm_move", "A", "live unit command menu opens", function(after)
        return controllerState(after) == "unit_command_menu"
    end, 180)
end

local function chooseWait()
    return selectSemantic("wait", "Wait closes the unit command menu", function(after)
        return after.menu == nil
    end, 120)
end

-- `targetId` (optional): the unit to talk to, the selector stepped to it (INSPECT.stepTarget).
local function chooseTalk(targetId)
    if not selectSemantic("talk", "Talk opens its live target selector", function(after)
        return controllerState(after) == "target_selection"
            and after.target and after.target.kind == "talk"
    end, 300) then return false end
    if not INSPECT.stepTarget(targetId, nil) then return false end
    return guardedInput("confirm_target", "A", "Talk reaches FE8's dialogue input wait", function(after)
        return controllerState(after) == "dialogue_wait"
    end, 600)
end

-- The open target selector stepped to the wanted target: `targetId` a unit's index byte, or
-- `targetTile` an obstacle by its tile (bmtarget.c TryAddTrapsToTargetList lists it with uid 0);
-- neither = the selector's first. At most one step per target the selector can hold (bmunit.h:
-- red[50]); a target it never reaches is a fault.
INSPECT.stepTarget = function(targetId, targetTile)
    local function wanted(t)
        if targetTile then return t ~= nil and t.x == targetTile.x and t.y == targetTile.y end
        return not targetId or (t ~= nil and t.uid == targetId)
    end
    for _ = 1, 50 do
        if wanted(observeController().target) then return true end
        if not guardedInput("next_target", "RIGHT", "the selector steps to its next target",
            function(after, before)
                return after.target ~= nil and before.target ~= nil
                    and (after.target.uid ~= before.target.uid or after.target.x ~= before.target.x
                         or after.target.y ~= before.target.y)
            end, 30) then return false end
    end
    if wanted(observeController().target) then return true end
    traceFailure("select_target", targetTile
        and string.format("the selector reaches the obstacle at (%d,%d)", targetTile.x, targetTile.y)
        or string.format("the selector reaches unit 0x%02X", targetId),
        "fail:target-not-offered", nil, "controller-target-not-offered")
    return false
end

-- Confirm the selector's target, then wait until the act resolved: the actor greyed out, or
-- `stopWhen`. Commit proof has to be mode-agnostic. procs.battle is gProc_ekrBattle, the battle
-- ANIMATION proc: a scenario that called pokeFastConfig() runs MAP combat, where it never
-- spawns, so requiring it alone fails an attack that in fact resolved (#232 -- it took out
-- ch04packmath/ch04snag/clear_ch04 while the attacks all landed). The target selector closing
-- is the signal common to both modes; the wait below is what proves the act resolved.
INSPECT.commitTarget = function(actorAddr, stopWhen, what)
    if not guardedInput("confirm_target", "A", "target selection commits the " .. what, function(after)
        return after.procs.battle ~= nil or controllerState(after) ~= "target_selection"
    end, 300) then return false end
    return INSPECT.awaitActed(actorAddr, stopWhen)
end

-- An act (combat, a staff, an item) ends when the actor is greyed out. The budget has to fit
-- an animation NOBODY IS SKIPPING: the old 1200 was sized when waitFor still mashed A on a
-- 50-frame cadence, which advanced the in-battle quote text. #220 retired that cadence on
-- principle, and the ch00 boss animation then measured 1238 frames -- 38 over, so every
-- ch00/ch01 combat scenario timed out on a fight it had already won (#232). Vanilla's real
-- worst cases are far longer than one clean round (crit, a double, a level-up, a promotion),
-- so size this for those, not for the measurement.
-- A unit with Canto gets its move back after any act but combat and a staff (playerphase.c
-- PlayPhaseForceActiveUnitCanto): the game is back in move selection, and the act is only done
-- once that move is spent. It is spent where the unit stands -- A on its own tile, then Wait
-- if the command menu opens -- since nothing the bot decided asks it to move again.
INSPECT.awaitActed = function(actorAddr, stopWhen)
    local function acted()
        return (ru32(actorAddr + 0x0C) & 0x2) ~= 0 -- US_UNSELECTABLE
            or (stopWhen ~= nil and stopWhen())
    end
    local done = waitFor(function()
        return acted() or controllerState() == "unit_selected"
    end, TUNE.combatFrames, true)
    if done and not acted() then
        if not guardedInput("confirm_move", "A", "Canto ends where the unit stands", function(after)
            return controllerState(after) ~= "unit_selected"
        end, 120) then return false end
        if controllerState() == "unit_command_menu" and not chooseWait() then return false end
        done = waitFor(acted, TUNE.combatFrames, true)
    end
    if not done then
        traceFailure("await_combat", "actor becomes unavailable or scenario terminal fires",
            "fail:combat-timeout", nil, "controller-combat-timeout")
        freezeReport("controller combat timeout")
        return false
    end
    wait(30)
    return true
end

-- Select Attack, an enabled weapon, and the current engine-selected target from live semantic
-- structures. `stopWhen` is an optional second exit for the combat wait. A kill that ENDS the
-- chapter starts the win event on the spot, which can keep the actor from ever being greyed out.
-- Dialogue advances only at TalkWaitForInput; a combat timeout fails closed without rescue input.
-- `targetId` / `targetTile` (optional): INSPECT.stepTarget's, so a caller that chose its target
-- strikes that one and not the selector's first.
local function chooseAttack(actorAddr, stopWhen, targetId, targetTile)
    if not selectSemantic("attack", "Attack opens the live weapon menu", function(after)
        return controllerState(after) == "weapon_menu"
    end, 300) then return false end
    if not selectSemantic("select_weapon", "weapon opens the live attack target selector", function(after)
        return controllerState(after) == "target_selection"
            and after.target and after.target.kind == "attack"
    end, 300) then return false end
    if not INSPECT.stepTarget(targetId, targetTile) then return false end
    return INSPECT.commitTarget(actorAddr, stopWhen, "attack")
end

-- From the open menu `state`, the row whose override id is `id`: DOWN until it is current.
INSPECT.menuTo = function(state, id)
    for _ = 1, 8 do
        local o = observeController()
        if controllerState(o) ~= state then return false end
        local cur = o.menu.current
        for _, item in ipairs(o.menu.items) do
            if item.slot == cur and item.override_id == id then return true end
        end
        if not guardedInput("menu_next", "DOWN", "the menu cursor moves", function(after)
            return after.menu ~= nil and after.menu.current ~= cur
        end, 30) then return false end
    end
    return false
end

-- Staff -> the staff in inventory `slot` (0-based; gStaffItemSelectMenuItems lists it as row
-- 0x3E + slot) -> the heal selector, stepped to unit `targetId` -> commit, until it resolved.
INSPECT.chooseStaff = function(actorAddr, slot, targetId, stopWhen)
    if not selectSemantic("staff", "Staff opens the staff list", function(after)
        return controllerState(after) == "staff_menu"
    end, 120) then return false end
    if not INSPECT.menuTo("staff_menu", INSPECT.MENU_STAFF_SLOT + slot) then return false end
    if not selectSemantic("select_staff", "the staff opens its target selector", function(after)
        return controllerState(after) == "target_selection"
    end, 300) then return false end
    if not INSPECT.stepTarget(targetId, nil) then return false end
    return INSPECT.commitTarget(actorAddr, stopWhen, "staff")
end
INSPECT.MENU_STAFF_SLOT, INSPECT.MENU_ITEM_SLOT = 0x3E, 0x43   -- menu_def.c, slot 0's row

-- Item -> inventory `slot` (0-based; gItemSelectMenuItems row 0x43 + slot) -> its submenu.
INSPECT.itemSubmenu = function(slot)
    if not selectSemantic("open_items", "the Item command opens the inventory", function(after)
        return controllerState(after) == "item_list"
    end, 120) then return nil, "no Item command" end
    if not INSPECT.menuTo("item_list", INSPECT.MENU_ITEM_SLOT + slot) then
        return nil, "the inventory never reached slot " .. slot
    end
    if not guardedInput("select_item", "A", "the item's submenu opens", function(after)
        return controllerState(after) == "item_submenu"
    end, 120) then return nil, "the item offered no submenu" end
    return true
end

-- March a unit toward (tx,ty) using the game's own pathing: selecting the
-- unit fills gBmMapMovement (include/bmmap.h; cost < 120 = reachable this
-- turn), so we read it and pick the reachable free tile closest to the target.
local function marchToward(u, tx, ty, maxx, maxy)
    maxx, maxy = maxx or 14, maxy or 9 -- default = ch00 map; ch01 is 25x16
    if not awaitControllerState("player_map_idle", 300) then return false end
    if not cursorTo(u.x, u.y) then return false end
    if not guardedInput("select_unit", "A", "PlayerPhase enters movement-range input", function(after)
        return controllerState(after) == "unit_selected"
    end, 120) then return false end
    local best, bestd = nil, 999
    for y = 0, maxy do
        for x = 0, maxx do
            if reachCost(x, y) < 120 and not tileOccupied(x, y)
                and not (x == u.x and y == u.y) then
                local d = BOARD.distance(tx, ty, x, y)
                if d < bestd then best, bestd = { x = x, y = y }, d end
            end
        end
    end
    if not best or not cursorTo(best.x, best.y) then return false end
    if not guardedInput("confirm_move", "A", "live unit command menu opens", function(after)
        return controllerState(after) == "unit_command_menu"
    end, 180) then return false end
    return chooseWait()
end

-- A tile with NO unit on it, resolved against the live map. endTurn presses A to open the
-- map menu, and A on an occupied tile SELECTS that unit instead -- no menu, so the turn can
-- never be ended. A hardcoded tile cannot express this: (2,2) was empty on ch00 but is a
-- deploy slot on ch04, which is also the smallest map so far. Reads the engine's own
-- tile->unit grid (what cursor-selection itself consults), so green/NPC bodies count too.
local function emptyTile()
    local w, h = mapSize()
    for y = 0, h - 1 do
        for x = 0, w - 1 do
            if mapUnitAt(x, y) == 0 then return { x = x, y = y } end
        end
    end
    return nil
end

-- `alreadyWon` is an optional predicate for callers that end a turn in order to FIRE a win
-- condition. A clear-bot that kills the final enemy can fire DefeatAll with that kill, and the
-- ending then plays INSIDE the old chapter slot -- so the caller's `chapter() ~= start` guard
-- is still false while the map is already gone. Ending the turn there makes the wait below
-- chase a player_map_idle this chapter will never show again: it meets the post-chapter save
-- prompt and the next chapter's title card and fails the run on those, on a chapter it just
-- cleared (#335). The precondition this function actually needs is that the PLAYER HAS THE
-- MAP, so ask that rather than the chapter number -- after settling, because right after the
-- last kill FE8 is mid-transition either way and an instant reading would skip a turn that
-- genuinely still needs ending.
--
-- phaseTurn (optional; the clear loop passes it): the turn whose player phase the caller is
-- ending. "The player map is idle" alone cannot tell that phase from the NEXT one, so with it
-- the phase only still needs ending while BOARD.inPhase(header, phaseTurn) holds -- FE8 may
-- have ended it by itself (every unit acted), and it may already be turn N+1's, which must not
-- be ended unacted. Dialogue is advanced while waiting: an open text box is neither "ended"
-- nor "idle". Callers without phaseTurn keep the older alreadyWon behaviour unchanged.
local function endTurn(tile, alreadyWon, phaseTurn)
    if phaseTurn then
        local function over()
            return (alreadyWon ~= nil and alreadyWon()) or not BOARD.inPhase(BOARD.header(), phaseTurn)
        end
        local function noTurnLeft()
            log("the phase or the chapter already ended under the last action -- no turn left to end")
            return true
        end
        waitFor(function()
            return over() or controllerState(observeController()) == "player_map_idle"
        end, 600, true)
        if over() then return noTurnLeft() end
        -- awaitControllerState advances dialogue itself (a classified dialogue_wait).
        if not awaitControllerState("player_map_idle", 300) then return false end
        if over() then return noTurnLeft() end
    elseif alreadyWon then
        waitFor(function()
            return alreadyWon() or controllerState(observeController()) == "player_map_idle"
        end, 600)
        if alreadyWon() or controllerState(observeController()) ~= "player_map_idle" then
            log("the phase or the chapter already ended under the last action -- no turn left to end")
            return true
        end
    end
    if not awaitControllerState("player_map_idle", 300) then return false end
    tile = tile or emptyTile()
    if not tile then
        traceFailure("end_phase", "live map has an empty tile from which to open its menu",
            "fail:no-empty-map-tile", nil, "controller-no-empty-tile")
        return false
    end
    if not cursorTo(tile.x, tile.y) then return false end
    if not guardedInput("open_map_menu", "A", "live map command menu opens", function(after)
        return controllerState(after) == "map_command_menu"
    end, 120) then return false end
    return selectSemantic("end_phase", "End Phase leaves the player phase", function()
        return faction() ~= 0
    end, 900)
end

-- End turn, then ride out the enemy phase. Returns "gameover" the moment the game-over
-- screen proc appears, "player" when control comes back, "ended" if the chapter itself
-- finished during the phase, or nil if the phase wedged (which leaves a controller fault).
-- alreadyWon / phaseTurn are endTurn's, for a caller whose last action may already have
-- ended the phase (FE8 ends it by itself once every unit has acted) or the chapter.
local function runEnemyPhase(tile, alreadyWon, phaseTurn)
    if not endTurn(tile, alreadyWon, phaseTurn) then return nil end
    -- Won while endTurn waited: chapter() below would already be the NEXT chapter's, and no
    -- player phase of this one is coming back to wait for.
    if alreadyWon and alreadyWon() then return "ended" end
    local startedIn = chapter()
    for _ = 1, TUNE.enemyPhaseFrames do
        if gameOverActive() then return "gameover" end
        -- The chapter can END during the enemy phase: a DefeatAll win fires the ending right
        -- there, and from it FE8 goes to the post-chapter save prompt and then the next
        -- chapter. No player phase is ever coming back, so waiting for one spends the whole
        -- budget and then reports a PHASE TIMEOUT on a chapter that was cleared -- which is
        -- what failed clear_ch04_parley, a run that went on to reach chapter 6 (#335).
        -- A chapter ending under us is a normal exit, not a wedge, so it returns its own
        -- value and leaves no controller fault behind for the verdict to trip over.
        if chapter() ~= startedIn then return "ended" end
        -- One observation per frame, classified once: nothing runs between the two questions.
        local state = controllerState()
        if faction() == 0 and not menuOpen() and state == "player_map_idle" then
            return "player"
        end
        local pressed = INSPECT.answerWait(state)
        if pressed == false then return nil end
        if pressed == nil then yield() end
    end
    traceFailure("enemy_phase", "enemy phase reaches game over or returns player control",
        "fail:phase-timeout", nil, "controller-enemy-phase-timeout")
    return nil
end

-- Detecting an on-screen in-battle quote box: procActive(SYM.ProcScr_BattleEventEngine) is
-- true exactly while a brief in-combat line is up (per-PC DEATH quotes, boss taunts; started
-- by CallBattleQuoteEventInBattle, src/event.c). Capture loops watch it to hold + screenshot
-- the box instead of A-mashing past it. NOTE: ProcScr_StdEventEngine is live
-- during ALL normal map/turn event processing, so it must NOT be used to gate "a quote is up".

-- ---------------------------------------------------------------- boot
-- `want` is the chapter slot this boot is trying to REACH; it defaults to HOST_CHAPTER, the
-- slot the scenario is ultimately about. They are the same thing for a scenario that boots
-- straight onto its own map, and DIFFERENT for every chain that walks through chapters to get
-- there -- winCh00 plays the prologue on the way to ch02, and must wait for the prologue.
--
-- Conflating them cost a run: ch02's cases carry host_chapter 3 (declared.py injects the
-- chapter's own slot), so ckpt_ch02start -- which replays ch00 -> ch01 -> ch02 from New Game --
-- booted the PROLOGUE and then waited for chapter 3 there until the deadline. It had only ever
-- worked because ch02's older matrix.yaml rows named no host_chapter and defaulted to 1.
local function inChapter(want)
    return chapter() == (want or HOST_CHAPTER) and faction() == 0 and turn() >= 1
        and unitAt(SYM.gUnitArrayBlue, 0) ~= nil
end

-- Drive OUT of the Preparations screen via Fight! (PrepScreenMenu_OnStartPress), if it is
-- open. Real PREP chapters (ch03, #23 item 3) interpose Preparations between the beginning
-- scene and the map; FE8 auto-fills deployment to the cap, so a plain Fight! fields the
-- roster. No-op (returns true) when no prep proc is up (the TESTCH sandbox / static boots).
local function driveThroughPrep()
    if not procActive(SYM.ProcScr_AtMenu) and not procActive(SYM.gProcScr_SALLYCURSOR) then return true end
    if not awaitControllerState("prep_main", 900) then
        local state, why = controllerState()
        log("controller: preparations never reached main input: " .. tostring(state or why))
        return false
    end
    shot("prep-menu")
    return guardedInput("fight", "START", "main Preparations exits directly to chapter flow", function(after)
        local state = controllerState(after)
        return state ~= "prep_main" and state ~= "prep_map_menu" and state ~= "prep_pick_units"
            and not procActive(SYM.ProcScr_AtMenu)
            and not procActive(SYM.gProcScr_SALLYCURSOR)
            and not procActive(SYM.ProcScr_PrepMenu)
    end, 1800)
end

-- Execute at most one input for a recognized boot state. `nil` means the state is unsupported;
-- false means a guarded input failed; true means one input passed or a transition yielded.
-- A save slot takes TWO confirms: A picks the slot, then a Save/Cancel bar appears and a
-- second A commits it. Both presses are the same legal action on the same classified state
-- (SaveMenu_SaveSlotSelectLoop stays the idle callback throughout), so one guardedInput
-- cannot verify the first press -- there is no state change to check it against. Verify the
-- OUTCOME instead: legality is re-checked before every press, the loop stops the instant the
-- save menu is gone, and it fails closed if the prompt outlives the allowance. Bounded and
-- outcome-verified, so this is not the blind cadence #220 retired.
-- Without it the ch00 -> ch01 hand-off parked on the post-chapter prompt forever (#232).
local function driveSaveSlot()
    for _ = 1, TUNE.saveConfirms do
        local observation = observeController()
        if not observation.procs.save_menu then return true end
        local actions = Controller.legalActions(observation)
        local chosen = actions and Controller.findAction(actions, "select_save_slot") or nil
        if not chosen or chosen.key ~= "A" then
            traceInput(observation, actions, "select_save_slot", "none",
                "the save prompt offers its slot-confirm input", "fail:not-legal", observation)
            shot("controller-illegal-input")
            return false
        end
        press(K.A, 3)
        if waitFor(function() return observeController().procs.save_menu == nil end, 240) then
            return true
        end
    end
    traceFailure("select_save_slot", "the save prompt closes within its confirm allowance",
        "fail:postcondition", nil, "controller-save-prompt")
    return false
end

-- The stall oracle: the DECISION lives in controller.lua (pure, unit-tested in
-- test_controller.lua -- it decides FAIL for whole suites, so it may not live where
-- nothing can load it), and this only reports it. Returns a per-loop closure: call it
-- with each observation, and act on the first true.
INSPECT.watch = function(what)
    local stalled = Controller.stallWatch(TUNE.stallFrames)
    return function(observation, state)
        local explanation = stalled(observation, state)
        if not explanation then return false end
        log(string.format("STALL: %s held an unclassified wait for %d frames -- %s",
            what, TUNE.stallFrames, tostring(explanation.detail)))
        INSPECT.snapshot(what .. "-stall", explanation)
        return true
    end
end

local function advanceBootState(observation, state)
    if state == "health_safety_wait" then
        return guardedInput("continue", "A", "health/safety wait clears", function(after)
            return controllerState(after) ~= "health_safety_wait"
        end, 300)
    elseif state == "title_idle" then
        return guardedInput("new_game", "START", "title idle exits", function(after)
            return controllerState(after) ~= "title_idle"
        end, 600)
    elseif state == "save_menu_input" then
        return guardedInput("new_game", "A", "New Game leaves save-menu input", function(after)
            return controllerState(after) ~= "save_menu_input"
        end, 600)
    elseif state == "save_slot_input" then
        return driveSaveSlot()
    elseif state == "difficulty_input" then
        -- Move onto the requested mode before committing. The postcondition is the
        -- highlight MOVING, not the state clearing -- the menu is still up afterwards.
        local d = observeController().difficulty
        if d and d.want ~= nil and d.current ~= nil and d.current ~= d.want then
            local from = d.current
            return guardedInput("select_difficulty_down", "DOWN", "difficulty highlight moves",
                function(after)
                    return after.difficulty and after.difficulty.current ~= from
                end, 120)
        end
        return guardedInput("confirm_difficulty", "A", "difficulty input clears", function(after)
            return controllerState(after) ~= "difficulty_input"
        end, 600)
    elseif state == "chapter_intro_input" then
        return guardedInput("continue_chapter_intro", "A", "chapter intro input clears", function(after)
            return controllerState(after) ~= "chapter_intro_input"
        end, 600)
    elseif state == "dialogue_wait" then
        return INSPECT.advanceDialogue(120)
    elseif state == "transition" then
        yield()
        return true
    end
    return nil
end

-- The mode the ROM is ACTUALLY in, from the two bits SaveMenuWriteNewGame sets:
--   chapterStateBits +0x14, PLAY_FLAG_HARD = 1<<6 (types.h:187,246)
--   config +0x40, controller = bit 21 (PlaySt_OptionBits; pokeFastConfig pins the packing)
-- TUTORIAL_MODE() is `!HARD && controller ~= 1` (eventinfo.h:107).
INSPECT.liveDifficulty = function()
    local hard = (ru8(SYM.gPlaySt + 0x14) & 0x40) ~= 0
    local controller = (ru32(SYM.gPlaySt + 0x40) >> 21) & 1
    return hard and "difficult" or (controller == 1 and "normal" or "tutorial"), hard, controller
end

-- nil when the run is in the mode it was asked for, else the failure text.
INSPECT.difficultyMismatch = function()
    local want = TUNE.difficultyName[TUNE.difficultyWant]
    local actual, hard, controller = INSPECT.liveDifficulty()
    if actual == want then return nil end
    return string.format(
        "difficulty mode is %s but this run wants %s (HARD=%s controller=%d) -- a save state "
        .. "minted in another mode, or a menu selection that never committed. Set "
        .. "PT_DIFFICULTY, or delete the checkpoint so it re-mints.",
        actual, want, tostring(hard), controller)
end

-- `want`: the chapter slot to stop on, for a chain leg that is not the scenario's own (see
-- inChapter). Omit it and the boot waits for HOST_CHAPTER, which is what every direct-boot
-- scenario means.
-- `opts.strictCheckpoint`: the row's checkpoint is the ONLY route to this map (ch02 has no
-- debug boot), so a missing, unloadable or stale one returns false plus a reason naming it,
-- at once, instead of falling through to a New Game boot that sits on the prologue and FAILs
-- late and vaguely. The caller FAILs with that reason.
local function bootToMap(stopAtPrep, want, opts)
    -- A declared CHECKPOINT is the correct route to this chapter's map, not a shortcut past
    -- it. Chapters with a debug boot (ch03-ch05) land on their map from New Game, so driving
    -- the boot IS the route; ch02 has no such boot and reaches its map only down the
    -- ch00 -> ch01 -> ch02 chain, which is exactly what its checkpoint holds. Without this,
    -- "boot to the map" quietly means "boot to the map IF this chapter has a debug boot", and
    -- every ch02 case that did not hand-roll a loadState sat on the prologue until it timed
    -- out -- which is how `given: [on_map]` failed for ch02visit while passing everywhere else.
    --
    -- A ckpt_* builder is excluded: it is the thing that MINTS the state, so loading it would
    -- either restore a stale one over the run that was meant to replace it, or load nothing.
    local ckpt = PLAYTEST_CHECKPOINT
    local strict = opts and opts.strictCheckpoint
    if strict and (not ckpt or ckpt == "") then
        return false, "the row declares no checkpoint, and this map has no other route"
    end
    if ckpt and ckpt ~= "" and not string.match(PLAYTEST_SCENARIO or "", "^ckpt_") then
        if loadState(ckpt) then
            wait(90)
            if inChapter(want) then
                log(string.format("checkpoint %s -> chapter %d turn %d", ckpt, chapter(), turn()))
                shot("map-loaded")
                return true
            end
            local stale = string.format("checkpoint %s loaded but chapter=%d (want %d)",
                ckpt, chapter(), want or HOST_CHAPTER)
            if strict then return false, stale .. " -- delete it so run.sh re-mints it" end
            -- Loaded, but not where it claims to be: fall through and boot honestly rather
            -- than assert against whatever map the stale state happens to hold.
            log(stale .. " -- booting instead")
        elseif strict then
            return false, "no " .. ckpt .. " checkpoint (run.sh builds it)"
        end
    end
    log("booting to map with observed FE8 states")
    local stalled = INSPECT.watch("boot")
    -- TUNE.bootSteps, never a literal: a cap that expires mid-scene reports a timeout that
    -- names nothing, which is how #232 stayed misdiagnosed for three sessions. The cap is
    -- sized above any real scene and INSPECT.watch is what decides failure.
    for _ = 1, TUNE.bootSteps do
        if TUNE.bootHook then TUNE.bootHook() end   -- a scenario's per-step poke (vanillagold)
        local observation = observeController()
        local state, why = controllerState(observation)
        if stalled(observation, state) then
            result("FAIL", "boot parked on an unclassified wait (see the inspect snapshot)")
            return false
        end
        if state == "player_map_idle" then
            if inChapter(want) then
                -- Assert the MODE on every boot, not only in the difficulty probe. A
                -- checkpoint reload or a silent revert to the menu default would otherwise
                -- run the whole gate in a mode nobody asked for and nothing would say so.
                local wrong = INSPECT.difficultyMismatch()
                if wrong then
                    result("FAIL", wrong)
                    return false
                end
                log(string.format("in chapter %d turn %d", chapter(), turn()))
                shot("map-loaded")
                return true
            end
            yield()
        elseif state == "prep_main" then
            if stopAtPrep then return true end
            if not driveThroughPrep() then return false end
        elseif state == "prep_map_menu" or state == "prep_pick_units" then
            local actions = Controller.legalActions(observation)
            traceInput(observation, actions, "boot", "none", "supported boot state", "fail:unsupported-prep-state", observation)
            shot("boot-prep-unsupported")
            return false
        else
            local advanced = advanceBootState(observation, state)
            if advanced == true then
                -- Continue observing; the next input must be independently legal.
            elseif advanced == false then
                return false
            else
            local actions = Controller.legalActions(observation)
            traceInput(observation, actions, "boot", "none", "recognized boot state",
                "fail:" .. tostring(why), observation)
            shot("boot-unsupported")
            return false
            end
        end
    end
    log(string.format("boot stuck: chapter=%d host=%d faction=0x%02X turn=%d blue0=%s prep=%s",
        chapter(), HOST_CHAPTER, faction(), turn(), tostring(unitAt(SYM.gUnitArrayBlue, 0) ~= nil),
        tostring(procActive(SYM.gProcScr_SALLYCURSOR))))
    traceFailure("boot", "recognized boot state reaches requested chapter",
        "fail:boot-timeout", nil, "boot-stuck")
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
    for _, faction in ipairs({ "blue", "red" }) do
        for _, u in ipairs(BOARD.leanList(faction)) do
            if not u.dead then s = s + u.hp end
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

-- ---- freeze report: name WHAT is stuck, not just THAT something is (#24).
-- A soft-lock is never a stopped CPU -- it is the proc scheduler still running while one
-- proc stops advancing. The proc pool carries its own diagnosis (include/proc.h): scrCur
-- is the script command it sits on, lockCnt is the wait semaphore (nonzero = blocked by a
-- child//other proc that never released it), and sleepTime is a timed wait. Sampling the
-- pool TWICE across a gap separates "this proc is frozen" from "the whole scheduler is
-- spinning", which is the first fork in the diagnosis. Identity comes from the script
-- ADDRESS via PROCSCR, never from the PROC_NAME string the decomp reuses (#236).
local PROC_STRIDE = 0x6C
local function readCStr(addr, maxLen)
    if addr == 0 then return nil end
    local out = {}
    for i = 0, (maxLen or 24) - 1 do
        local c = ru8(addr + i)
        if c == 0 or c < 0x20 or c > 0x7E then break end
        out[#out + 1] = string.char(c)
    end
    if #out == 0 then return nil end
    return table.concat(out)
end

-- Every live proc as a stable one-line signature, keyed by pool index.
local function procPool()
    local pool = {}
    for i = 0, 63 do
        local a = SYM.sProcArray + i * PROC_STRIDE
        local scr = ru32(a)
        if scr ~= 0 then
            pool[i] = {
                script = scr,
                scrCur = ru32(a + 0x04),
                idleCb = ru32(a + 0x0C),
                name = readCStr(ru32(a + 0x10)),
                sleep = rs16(a + 0x24),
                mark = ru8(a + 0x26),
                flags = ru8(a + 0x27),
                lock = ru8(a + 0x28),
            }
        end
    end
    return pool
end

-- Exact-match only. A script address that matches no symbol is reported as unknown:
-- a confidently wrong name (the old PROC_NAME string, where three distinct scripts all
-- read as "E_FACE") cost #232 its last failure, and silence would have been cheaper.
INSPECT.scriptName = function(addr)
    return PROCSCR[addr] or string.format("unknown@0x%08X", addr)
end

-- WHICH message a scene actually showed. `GetStringFromIndex` (src/msg.c) caches the index it
-- last decoded in `sActiveMsg`, so reading it WHILE a box is up names the message id on screen.
-- Box counting is the witness everywhere else in ch05 and it is strictly weaker: two arms of one
-- branch can render to the same number of A-presses, which the Talk recruit does exactly (its
-- locked box 8 wraps in two; its substitute is two authored boxes). Read it during a dialogue
-- wait -- unit names and menus decode through the same function and overwrite it.
INSPECT.activeMsg = function() return ru32(SYM.sActiveMsg) end

local function procLine(i, p, prev)
    -- scrCur as an offset from the script head: the exact PROC_* command it sits on.
    local step = (p.scrCur >= p.script) and ((p.scrCur - p.script) // 12) or -1
    local moved = ""
    if prev then
        moved = (prev.scrCur == p.scrCur and prev.sleep == p.sleep and prev.lock == p.lock)
            and " FROZEN" or " moving"
    end
    return string.format(
        "  [%02d] %-34s cmd#%-3d idle=%08X sleep=%-4d mark=%-3d flags=%02X lock=%d%s",
        i, INSPECT.scriptName(p.script), step, p.idleCb, p.sleep, p.mark, p.flags, p.lock, moved)
end

-- The BattleUnit pair the engine is resolving/animating right now.
local function battleSide(base)
    if base == nil or base == 0 then return "(null)" end
    local chptr = ru32(base)
    if chptr == 0 then return "(none)" end
    return string.format("pid=0x%02X class=0x%02X hp=%d at(%d,%d) terrain=0x%02X weapon=0x%02X",
        ru8(chptr + 4), ru8(ru32(base + 4) + 4), ru8(base + 0x13),
        rs8(base + 0x10), rs8(base + 0x11), ru8(base + 0x55), ru16(base + 0x48) & 0xFF)
end

-- Dump everything that localizes a freeze. Sampled twice, `gap` frames apart.
freezeReport = function(tag, gap)
    local before = procPool()
    wait(gap or 90)
    local after = procPool()
    log(string.format("== FREEZE REPORT (%s) ch=%d turn=%d faction=0x%02X ==",
        tag, chapter(), turn(), faction()))
    log(string.format("  battleActor: %s", battleSide(SYM.gBattleActor)))
    log(string.format("  battleTarget: %s", battleSide(SYM.gBattleTarget)))
    log(string.format("  gBanimTerrain: L=0x%02X R=0x%02X   ekrBattle=%s",
        ru8(SYM.gBanimTerrain), ru8(SYM.gBanimTerrain + 1),
        tostring(procActive(SYM.gProc_ekrBattle))))
    -- The wait condition itself: ekrBattleInRoundIdle spins until BOTH done flags are set.
    log(string.format("  gBanimDoneFlag: [0]=%d [1]=%d   gEkrDistanceType=%d",
        ru32(SYM.gBanimDoneFlag), ru32(SYM.gBanimDoneFlag + 4), rs16(SYM.gEkrDistanceType)))
    log(string.format("  ekrBattleUnit: left=%s", battleSide(ru32(SYM.gpEkrBattleUnitLeft))))
    log(string.format("  ekrBattleUnit: right=%s", battleSide(ru32(SYM.gpEkrBattleUnitRight))))
    for i = 0, 3 do
        local an = ru32(SYM.gAnims + i * 4)
        if an ~= 0 then
            log(string.format("  gAnims[%d]=%08X roundType=0x%02X state=%04X state2=%04X "
                .. "state3=%04X nextRound=%d timer=%d scr=%08X (+%d) queue=%d",
                i, an, ru8(an + 0x12), ru16(an), ru16(an + 0x0C), ru16(an + 0x10),
                ru16(an + 0x0E), rs16(an + 0x06), ru32(an + 0x20),
                ru32(an + 0x20) - ru32(an + 0x24), ru8(an + 0x14)))
        end
    end
    for i = 0, 63 do
        if after[i] then log(procLine(i, after[i], before[i])) end
    end
    -- Hand over the pair sampled above: the report and the snapshot then describe the same
    -- two moments, and the freeze costs one gap instead of two.
    INSPECT.snapshot(tag, nil, { before = before, after = after })
end

-- ---- state inspector (#236): one machine-readable snapshot of what FE8 is doing.
-- The controller observer already builds the semantic state; this formats it, adds the
-- reasoning behind the classification, and pairs it with the raw proc inventory named by
-- exact symbol. Rendered by tools/playtest/inspect_state.py, which resolves the idle-callback
-- addresses (ordinary functions -- ~35k of them, too many for a Lua table) out of the ELF.
-- `sampled` lets a caller that has ALREADY sampled the pool twice hand its pair over
-- (freezeReport does): re-sampling costs another TUNE.inspectGap frames and reports a
-- different moment than the report around it (#241).
-- Every live unit's faction, charId and TILE. A screenshot proves units exist; only this
-- proves WHERE, and the two disagree more often than they look like they could: FE8 draws a
-- map sprite taller than its tile and offset upward, so a unit reads a row high, and the
-- camera row has to be recovered before any pixel can be assigned a coordinate at all.
-- Placement questions get answered from here, never off a frame (decisions.md: verify via
-- data, not pixels). Hung off INSPECT so it costs no top-level local (`check_lua_local_headroom`).
INSPECT.units = function(tag)
    local factions = { { "blue", SYM.gUnitArrayBlue, 62 }, { "green", SYM.gUnitArrayGreen, 20 },
                       { "red", SYM.gUnitArrayRed, 50 } }
    for _, f in ipairs(factions) do
        local name, base, count = f[1], f[2], f[3]
        for i = 0, count - 1 do
            local u = unitAt(base, i)
            if u and not u.dead then
                log(string.format(
                    '{"event":"unit","tag":"%s","faction":"%s","char":"0x%02x",'
                    .. '"x":%d,"y":%d,"hp":%d}', tag, name, u.charId, u.x, u.y, u.hp))
            end
        end
    end
end

INSPECT.snapshot = function(tag, explanation, sampled)
    local observation = observeController()
    explanation = explanation or Controller.explain(observation)
    local before, after = (sampled or {}).before, (sampled or {}).after
    if not (before and after) then
        before = procPool()
        wait(TUNE.inspectGap)
        after = procPool()
    end
    local procs = {}
    for i = 0, 63 do
        local p = after[i]
        if p then
            local prev = before[i]
            procs[#procs + 1] = {
                slot = i,
                script = string.format("0x%08X", p.script),
                script_name = INSPECT.scriptName(p.script),
                -- The decomp's PROC_NAME string: colour only, never identity.
                proc_name = p.name,
                step = (p.scrCur >= p.script) and ((p.scrCur - p.script) // 12) or -1,
                idle = string.format("0x%08X", codeAddr(p.idleCb)),
                sleep = p.sleep, mark = p.mark, flags = p.flags, lock = p.lock,
                frozen = prev ~= nil and prev.scrCur == p.scrCur and prev.sleep == p.sleep
                    and prev.lock == p.lock,
            }
        end
    end
    -- raw_procs is the stall detector's signature source; the named inventory supersedes it.
    observation.raw_procs = nil
    log(Controller.encode({
        event = "inspect",
        tag = tag,
        scenario = PLAYTEST_SCENARIO,
        state = explanation.state or "unsupported",
        classification_error = explanation.error,
        matched_rule = explanation.matched,
        detail = explanation.detail,
        unclassified_wait = explanation.unclassified_wait,
        considered = explanation.considered,
        world = observation.world,
        cursor = observation.cursor,
        menu = observation.menu,
        prep = observation.prep,
        target = observation.target,
        procs = procs,
    }))
    shot(tag)
end


-- CONTROLLER_TURN (#220): the compact live contract gate on the normal no-prep boot.
-- It proves a real unit move closes through semantic Wait, then semantic End Phase reaches
-- an enemy phase and returns to a fresh player turn. The scenario owns those assertions;
-- move/menu/phase mechanics remain shared controller operations.
scenarios.controller_turn = function()
    if not bootToMap() then return result("FAIL", "controller did not reach the no-prep map") end
    local actor
    for i = 0, 61 do
        local candidate = unitAt(SYM.gUnitArrayBlue, i)
        if candidate and not isDead(candidate) and (candidate.state & 0xB) == 0
            and candidate.onMap then
            actor = candidate
            break
        end
    end
    if not actor then return result("FAIL", "no selectable blue unit on the live map") end
    if not moveUnit(actor.x, actor.y, actor.x, actor.y) then
        return result("FAIL", "controller could not move a live unit in place")
    end
    if not chooseWait() then return result("FAIL", "live unit menu did not expose semantic Wait") end
    if not waitFor(function() return (ru32(actor.addr + 0x0C) & 0x2) ~= 0 end, 300) then
        return result("FAIL", "Wait did not mark the acting unit unselectable")
    end
    for i = 0, 49 do
        local enemy = unitAt(SYM.gUnitArrayRed, i)
        if enemy and not isDead(enemy) then pokeHarmless(enemy) end
    end
    local beforeTurn = turn()
    if runEnemyPhase() ~= "player" then
        return result("FAIL", "semantic End Phase did not return from the enemy phase")
    end
    if faction() ~= 0 or turn() <= beforeTurn then
        return result("FAIL", string.format(
            "enemy-phase return postcondition failed (turn %d->%d faction=0x%02X)",
            beforeTurn, turn(), faction()))
    end
    result("PASS", string.format(
        "no-prep boot -> move -> semantic Wait -> semantic End Phase -> player turn %d",
        turn()))
end

-- ---- greedy clear-bot (#60): real-combat chapter completion. Generic boss detection
-- (no hardcoded char ids) + bot.lua's pure greedy core (pickTarget/pickMove); the scenario owns
-- the driving.
local BOT = dofile(PLAYTEST_DIR .. "/bot.lua")
INSPECT.Planner = dofile(PLAYTEST_DIR .. "/planner.lua")   -- the bot's planner (#510 step 9)
local CH02 = dofile(PLAYTEST_DIR .. "/ch02check.lua")   -- pure charm-delivery check (#22)
local PATHING = dofile(PLAYTEST_DIR .. "/pathing.lua")  -- pure BFS distance field (#60 march)
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

-- The on-field boss in the red array (the first unit whose character carries CA_BOSS), or
-- nil. From `board` (a BOARD.read snapshot) when given, else a LEAN scan -- a combat wait's
-- stop condition calls this once a frame.
local function findBoss(board)
    if not board then return BOARD.liveBoss() end
    for _, u in ipairs(BOARD.live(board, "red")) do
        if u.onField and u.isBoss then return u end
    end
    return nil
end

-- On-field red units as plain {x,y,hp,is_boss} tables for the pure pickTarget core, from
-- `board` when given. onField, not just alive: an enemy off the map, hidden or carried is not
-- a place to walk to or a target to strike.
local function liveEnemies(board)
    local out = {}
    for _, u in ipairs(BOARD.live(board or BOARD.read(), "red")) do
        if u.onField then out[#out + 1] = { x = u.x, y = u.y, hp = u.hp, is_boss = u.isBoss } end
    end
    return out
end

-- Select unit u and return the tiles it can move to this turn (cost < 120, free, plus its
-- own tile -- attack-from-here), leaving it selected with the move range shown. Every input
-- is controller-guarded; an invalid/stale movement map is a terminal mechanical failure.
local function selectAndReach(u, maxx, maxy)
    maxx, maxy = maxx or 14, maxy or 9
    if not awaitControllerState("player_map_idle", 300) then return nil end
    if not cursorTo(u.x, u.y) then return nil end
    if not guardedInput("select_unit", "A", "PlayerPhase enters movement-range input", function(after)
        return controllerState(after) == "unit_selected"
    end, 120) then return nil end
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
    if unreachable > 0 then return reach end
    traceFailure("read_movement", "live movement map contains bounded unreachable tiles",
        "fail:stale-movement-map", nil, "controller-stale-movement")
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
    -- Trace every turn/phase transition: a freeze report is only readable next to the
    -- phase it happened in ("turn 4 enemy phase" vs "turn 4 player phase").
    local lastPhase = nil
    for _ = 1, 100000 do
        local phase = string.format("t%d/f%02X", turn(), faction())
        if phase ~= lastPhase then
            log(string.format("phase -> turn %d faction 0x%02X (hpsum %d)",
                turn(), faction(), hpSum()))
            lastPhase = phase
        end
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
            shot("smoke-softlock")
            freezeReport("smoke soft-lock")
            return result("FAIL", "soft-lock -- " .. v.why)
        end
        if turn() > budgetTurns then
            shot("smoke-budget")
            return result("PASS", string.format(
                "survived %d turns, no crash/soft-lock (no terminal)", budgetTurns))
        end
        -- Drive one semantic step. Enemy phases and event transitions receive no input;
        -- dialogue advances only at TalkWaitForInput.
        local observation = observeController()
        local state, why = controllerState(observation)
        if state == "player_map_idle" and faction() == 0 and turn() >= 1 then
            if not endTurn() then return result("FAIL", "smoke could not end the player phase") end
        elseif state == "dialogue_wait" then
            if not INSPECT.advanceDialogue(120) then return result("FAIL", "smoke dialogue did not advance") end
        elseif state == "transition" then
            yield()
        else
            traceFailure("smoke_drive", "player map, dialogue wait, or passive transition",
                "fail:" .. tostring(why or state), observation, "smoke-unsupported")
            return result("FAIL", "smoke reached unsupported controller state")
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

-- Play ch00 to the boss kill and wait out the ending scene. Returns true once the chapter
-- has advanced past THE PROLOGUE'S slot, nil/false (with its own FAIL result already logged)
-- otherwise. Shared by the win and ch01 scenarios, and by every checkpoint that replays the
-- chain.
--
-- Every chapter test here is explicitly the PROLOGUE's slot, never HOST_CHAPTER. This
-- function is a chain LEG: callers reach it on the way somewhere else, and a caller aiming at
-- ch02 carries host_chapter 3, which would make "the chapter advanced" read false forever and
-- the boot wait for a slot the prologue can never be. `reachCh01` already names ch01's slot
-- as a literal (chapter() == 2) for the same reason; this is the other half of that.
local function winCh00()
    local PROLOGUE = 1        -- ch00 hosts on chapter slot 1 (inject/hosts.py)
    if not bootToMap(nil, PROLOGUE) then
        result("FAIL", "never reached the map") return false
    end
    local sephek = red(CAMPAIGN.PROLOGUE.sephek)
    if not sephek then result("FAIL", "Sephek not found in red array") return false end
    pokeFrail(sephek)
    log(string.format("Sephek at (%d,%d) poked to 1 HP", sephek.x, sephek.y))
    for t = 1, 6 do
        local scram = blue(CAMPAIGN.PROLOGUE.scramsax)
        if isDead(scram) then result("FAIL", "Scramsax died in the win run") return false end
        -- adjacent tile next to the boss, then attack (range 1)
        local tx, ty = sephek.x, sephek.y + 1
        if tileOccupied(tx, ty) then tx, ty = sephek.x - 1, sephek.y end
        if not moveUnit(scram.x, scram.y, tx, ty) then
            result("FAIL", "could not reach Sephek through guarded movement")
            return false
        end
        shot("attacking-sephek")
        -- Stop on the OUTCOME, not on the actor. Sephek's death fires DefeatBoss on the
        -- spot, so the chapter tears the map down and Scramsax never becomes
        -- US_UNSELECTABLE -- the win succeeds and the combat wait times out anyway
        -- (#232). chooseAttack takes stopWhen for exactly this case.
        if not chooseAttack(scram.addr, function()
            return isDead(red(CAMPAIGN.PROLOGUE.sephek)) or chapter() ~= PROLOGUE
        end) then
            result("FAIL", "combat did not reach its verified postcondition")
            return false
        end
        if not isDead(red(CAMPAIGN.PROLOGUE.sephek)) then
            log("Sephek alive after turn " .. t .. " (miss?); ending turn and retrying")
            local phase = runEnemyPhase()
            if phase == "gameover" then
                result("FAIL", "unexpected game over in win run")
                return false
            end
            if phase ~= "player" then
                result("FAIL", "enemy phase did not return verified player control")
                return false
            end
        end
        if isDead(red(CAMPAIGN.PROLOGUE.sephek)) then
            log("Sephek dead; waiting for the chapter to end")
            shot("sephek-dead")
            local ended = waitFor(function() return chapter() ~= PROLOGUE end, 3600, true)
            shot("after-boss-kill")
            if ended then return true end
            traceFailure("win_ch00", "boss death advances beyond the hosted chapter",
                "fail:chapter-advance-timeout", nil, "ch00-win-timeout")
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
        -- The prologue's own slot, not HOST_CHAPTER: `win` runs with host_chapter 1 today, but
        -- the number being reported is "the chapter we just left", which is ch00's regardless
        -- of who asked. (PROLOGUE is winCh00's local; naming it here would read a nil global.)
        result("PASS", string.format(
            "DefeatBoss fired; chapter advanced %d -> %d", 1, chapter()))
    end
end

-- VANILLAGOLD: RETAIL FE8 (PT_VANILLA=1), never our build. Does vanilla's Ch1 "Escape!" pay
-- the 5,000 gold the Fire Emblem Wiki lists? No Ch1 event, world-map script or C gold path in
-- the decomp grants it, so this reads the party's gold (gPlaySt+0x08) at each chapter's map
-- and after each chapter change. Measured 2026-10-15: 0 through the Prologue and Ch1, then
-- 5,000 inside chapter 0x38 (Castle Frelia, the decomp's `lordsplit`), so Ch2 starts at 5,000. Prologue: Seth kills a 1-HP O'Neill (DefeatBoss). Ch1: Seth
-- kills a 1-HP Breguet off the gate and Eirika seizes (2,2). Vanilla's own chapter indices,
-- Prologue 0, Ch1 1, Ch2 2 -- never our hosting slots (inject/hosts.py), which are ours.
-- Retail boots at text speed 1 (bmio.c:950); our build plays its scenes at max. Hold
-- textSpeed 3 (no typewriter delay, GetTextDisplaySpeed) and gameSpeed fast, or the
-- Prologue's narration outlasts TUNE.bootSteps. New Game rewrites the config, hence every step.
INSPECT.retailFastText = function()
    TUNE.bootHook = function()
        local a = SYM.gPlaySt + 0x40
        emu:write32(a, (ru32(a) & ~(3 << 5)) | (3 << 5) | (1 << 7))
    end
end

scenarios.vanillagold = function()
    local PROLOGUE, CH1, CH2 = 0, 1, 2
    INSPECT.retailFastText()
    local EIRIKA, SETH, ONEILL, BREGUET = 0x01, 0x02, 0x68, 0x46
    local function gold() return ru32(SYM.gPlaySt + 0x08) end
    local seen = {}
    local function note(tag)
        local line = string.format("%s: chapter %d, gold %d", tag, chapter(), gold())
        seen[#seen + 1] = line
        log("vanillagold: " .. line)
    end
    -- Seth strikes a 1-HP boss from a free adjacent tile; `stop` is the chapter's own outcome.
    local function killBoss(pid, here)
        for t = 1, 6 do
            local boss = red(pid)
            if isDead(boss) then return true end
            pokeFrail(boss)
            local seth = blue(SETH)
            local sx, sy = INSPECT.freeBeside(boss,
                { order = { { 0, 1 }, { 1, 0 }, { -1, 0 }, { 0, -1 } } })
            if not sx or not INSPECT.place(seth, sx, sy) then return false end
            seth = blue(SETH)
            if not moveUnit(seth.x, seth.y, seth.x, seth.y) then return false end
            chooseAttack(seth.addr, function() return isDead(red(pid)) or chapter() ~= here end)
            if isDead(red(pid)) or chapter() ~= here then return true end
            if runEnemyPhase() ~= "player" then return false end
        end
        return false
    end

    if not bootToMap(nil, PROLOGUE) then return result("FAIL", "never reached the Prologue map") end
    note("Prologue map")
    if not killBoss(ONEILL, PROLOGUE) then return result("FAIL", "could not kill O'Neill") end
    waitFor(function() return chapter() ~= PROLOGUE end, 3600, true)
    note("after the Prologue")
    if not bootToMap(nil, CH1) then return result("FAIL", "never reached Ch1's map") end
    note("Ch1 map")
    if not killBoss(BREGUET, CH1) then return result("FAIL", "could not kill Breguet") end
    local eirika = blue(EIRIKA)
    if not INSPECT.place(eirika, 2, 2) then return result("FAIL", "could not stand Eirika on the gate") end
    eirika = blue(EIRIKA)
    if not moveUnit(eirika.x, eirika.y, eirika.x, eirika.y) then
        return result("FAIL", "no live command menu for Eirika on the gate")
    end
    if not selectSemantic("seize", "Seize starts Ch1's win event", function()
        return chapter() ~= CH1 or procActive(SYM.ProcScr_StdEventEngine)
    end, 900) then return result("FAIL", "Eirika's menu offered no Seize on (2,2)") end
    waitFor(function() return chapter() ~= CH1 end, 9000, true)
    note("after Ch1")
    -- Ch1 ends with MoveToChapter(0x38): a world-map interlude the controller does not
    -- classify. Press through it (START skips, A advances) and note every change in gold, so
    -- a grant inside the interlude is caught where it happens.
    local last = gold()
    for step = 1, 4000 do
        if chapter() == CH2 then break end
        press(step % 3 == 0 and K.START or K.A, 2)
        wait(8)
        if gold() ~= last then last = gold(); note("gold changed during the interlude") end
    end
    if chapter() ~= CH2 then return result("FAIL", "the interlude never handed over to Ch2") end
    note("Ch2 begins")
    return result("PASS", table.concat(seen, " | "))
end

-- GOODBERRY: boot to the ch00 map, open Hlin's Item menu (one of her items is a Goodberry,
-- the reflavored Vulnerary), and screenshot the item list + the highlighted Goodberry so the
-- new name + blueberry icon can be eyeballed in-game.
scenarios.goodberry = function()
    if not bootToMap() then return result("FAIL", "never reached the map") end
    local hlin = blue(CAMPAIGN.PROLOGUE.hlin)
    if not hlin then return result("FAIL", "Hlin not found in blue array") end
    log(string.format("Hlin at (%d,%d)", hlin.x, hlin.y))
    -- select Hlin and re-confirm her own tile -> action menu (no move).
    if not moveUnit(hlin.x, hlin.y, hlin.x, hlin.y) then
        return result("FAIL", "action menu never opened for Hlin")
    end
    shot("action-menu")
    -- Resolve the live Item command rather than pressing the row it is expected to occupy
    -- (#238). "No enemy is in handaxe range at turn 1, so the menu is [Item, Wait] and A
    -- picks the top" was true, but it is a claim about turn 1's enemy placement -- move a
    -- goblin and the blind press opens Attack and the capture silently shoots the wrong
    -- screen.
    if not selectSemantic("open_items", "the Item command opens Hlin's inventory", function(after)
        return controllerState(after) == "item_list"
    end, 120) then
        return result("FAIL", "Hlin's command menu offered no live Item command")
    end
    wait(20)
    shot("item-list")
    -- Find the Goodberry's ROW by its item id, never by its place in the bag: it was "one row
    -- down" until ch00 gave Hlin a Killer Axe first (#430), and from then on that one DOWN
    -- highlighted her Hand Axe and every shot below showed the wrong item (#531 item 10).
    -- 0x6C = ITEM_VULNERARY (include/constants/items.h), which the Goodberry reflavors.
    local GOODBERRY = 0x6C
    local row
    for k = 0, 4 do
        if (ru16(hlin.addr + 0x1E + k * 2) & 0xFF) == GOODBERRY then row = k break end
    end
    if not row then return result("FAIL", "Hlin carries no Goodberry (item 0x6C)") end
    local list = observeController().menu
    if not (list and #list.items > row) then
        return result("FAIL", "the inventory list did not come up with Hlin's Goodberry row")
    end
    -- Each step refreshes the name/description panel; the postcondition is the live highlight
    -- moving one row. From either side (DOWN below, UP above), bounded by the bag's five slots,
    -- and the row is asserted after: the shots below must show the Goodberry or the run FAILs.
    for _ = 1, 5 do
        if list.current == row then break end
        local from = list.current
        local down = from < row
        if not guardedInput(down and "menu_next" or "menu_previous", down and "DOWN" or "UP",
            "the inventory highlight moves toward the Goodberry",
            function(after)
                return after.menu ~= nil and after.menu.current ~= from
            end, 60) then
            return result("FAIL", "could not move the inventory highlight onto the Goodberry")
        end
        list = observeController().menu
        if not list then return result("FAIL", "the inventory list closed on the way to the Goodberry") end
    end
    if list.current ~= row then
        return result("FAIL", string.format("the inventory highlight is on row %d, not the Goodberry's %d",
            list.current, row))
    end
    wait(20)
    shot("goodberry-highlighted")
    -- Open the Use/Equip/Trade/Discard submenu on the HIGHLIGHTED item -- which also shows
    -- its description. gItemSubMenuItems carry override ids 0x34-0x37 against the inventory
    -- rows' 0x43-0x47, so "a different menu is up" is a fact we can read rather than a wait
    -- to guess. Note the Goodberry is GREYED at full HP (ItemSelectMenu_Usability returns
    -- MENU_DISABLED for an item that cannot be used) -- and still opens its submenu, because
    -- Menu_OnIdle's A path does not consult availability.
    local open = observeController().menu
    if not (open and open.items[1]) then
        return result("FAIL", "the inventory list closed before the Goodberry could be opened")
    end
    local before = open.items[1].override_id
    if not guardedInput("select_item", "A", "the Goodberry's item submenu opens",
        function(after)
            return after.menu ~= nil and after.menu.items[1].override_id ~= before
        end, 120) then
        return result("FAIL", "the Goodberry row did not open its item submenu")
    end
    wait(20)
    shot("goodberry-detail")
    result("PASS", "Goodberry item menu captured (see screenshots)")
end

-- The lead menu (ADR 0062, ch01): commit row `want` -- "default" (the highlighted lead), "last"
-- (the final candidate) or a NUMBER (that row of the LIVE menu, 0-based). Returns the row it
-- committed on, or nil, why. No row is guessed and no candidate count is assumed: the walk
-- counts the live item list, and the landing is asserted, because nothing downstream re-checks
-- which lead was taken (#241). reachCh01 and the campaign's arrive both answer the menu here.
INSPECT.pickLead = function(want, observation)
    local rows = observation.menu and #observation.menu.items or 0
    if want == "last" then want = rows - 1 end
    if type(want) == "number" then
        if want < 0 or want >= rows then
            return nil, string.format("lead row %d is not in the live menu of %d candidates", want, rows)
        end
        -- Walk off the LIVE cursor and stop when it ARRIVES, rather than pressing a fixed
        -- count: a fixed count reaches the wanted row only if the menu opened on row 0, which
        -- nothing guarantees, and FE8 menus WRAP -- so being wrong picks a different lead and
        -- passes anyway.
        for _ = 1, rows do
            local at = observeController()
            if at.menu and at.menu.current == want then break end
            if not guardedInput("menu_next", "DOWN", "the lead menu selection moves",
                function(after, before)
                    return after.menu ~= nil and before.menu ~= nil
                        and after.menu.current ~= before.menu.current
                end, 60) then
                return nil, "could not walk the lead menu to the chosen candidate"
            end
        end
        local landed = observeController()
        if not (landed.menu and landed.menu.current == want) then
            shot("ch01-lord-walk-lost")
            return nil, string.format("lead menu walk landed on row %s of %d, not row %d",
                tostring(landed.menu and landed.menu.current), rows, want)
        end
    end
    local committing = observeController().menu
    local picked = committing and committing.current or want
    if not guardedInput("select_current_menu_item", "A", "lead menu selection closes", function(after)
        return after.menu == nil
    end, 300) then
        return nil, "could not choose the highlighted lead"
    end
    log(string.format("lead committed on menu row %s of %d", tostring(picked), rows))
    return picked
end

-- Reach ch01: ride the ch00 win into chapter slot 2, drive the post-chapter save + Beat-1
-- scene + lord select on OBSERVED state, then Fight! into the phase. Returns true at the
-- destination; false with its own FAIL logged otherwise.
--
-- opts.stopAtPrep  stop with Preparations open instead of driving through it
-- opts.lord        "default" (accept the highlighted lead) | "last" (the final candidate --
--                  Pinky) | a NUMBER (that row of the live lead menu, 0-based)
-- opts.picked      OUT: the row the lead menu was actually committed on. Read it instead of
--                  recomputing a row from LORD_CANDIDATES -- a scenario that assumes a roster
--                  size asserts against a constant rather than against what it did (#241).
--
-- One driver, every destination (#238). Two prep lead-ins, lordfloor, ch01lord and an RBG
-- battle-anim lead-in were five copies of this route on a blind A-cadence; a copy that mashes A
-- cannot tell "the scene advanced" from "the input was swallowed", which is how ch01win rode
-- straight through the lord-select Yes/No prompt that cost #232 three sessions.
local function reachCh01(opts)
    opts = opts or {}
    if not winCh00() then return false end
    if not waitFor(function() return chapter() == 2 end, 1800) then
        result("FAIL", "chapter slot 2 never loaded after the ch00 win"); return false
    end
    log("in ch01 (chapter slot 2); observing post-chapter flow to Preparations")
    -- The Beat-1 Northlook scene is 29 script lines -> 67 text pages, and at normal speed
    -- it costs ~170 frames a page. Nothing here is looked at, so set gameSpeed (gPlaySt
    -- +0x40 bit 7) and type it fast. Written inline, not as a helper: a helper would spend a shared
    -- top-level slot (check_lua_local_headroom prints what is actually left -- never
    -- write that number down, it went stale in three places at once). Only gameSpeed --
    -- animationType is left alone so winCh00's combat is unaffected.
    -- DELIBERATELY NOT RESTORED: ckpt_lordpinky saves AFTER this, so recordsupply, which
    -- loads it, inherits fast text. That IS a property of the checkpoint rather than an
    -- accident (#241).
    emu:write32(SYM.gPlaySt + 0x40, ru32(SYM.gPlaySt + 0x40) | (1 << 7))
    local stalled = INSPECT.watch("reach_ch01")
    for _ = 1, TUNE.bootSteps do
        local observation = observeController()
        local state, why = controllerState(observation)
        if stalled(observation, state) then
            result("FAIL", "ch01 parked on an unclassified wait (see the inspect snapshot)")
            return false
        end
        if state == "prep_main" then
            shot("ch01-prep-menu")
            if opts.stopAtPrep then return true end
            if not driveThroughPrep() then
                result("FAIL", "could not leave preparations via semantic Fight"); return false
            end
        elseif state == "player_map_idle" then
            -- The map is up but the chapter has not handed the player turn 1 yet (opening
            -- events still running). That is a WAIT, not an unsupported state -- bootToMap
            -- yields on the same case, and falling through to advanceBootState here would
            -- hard-FAIL a healthy run (#241).
            if faction() == 0 and turn() >= 1 then
                wait(120)
                shot("ch01-map")
                return true
            end
            yield()
        elseif state == "generic_menu" then
            local picked, why = INSPECT.pickLead(opts.lord, observation)
            if picked == nil then result("FAIL", why); return false end
            opts.picked = picked
        elseif state == "yes_no_choice" then
            -- Lord select confirms the pick with "Will <lead> lead the party?". Same
            -- scenario policy as the menu above -- accept the default -- and Yes is the
            -- highlighted answer, so the controller offers it directly on A.
            if not guardedInput("answer_yes", "A", "the yes/no prompt closes", function(after)
                return after.procs.yes_no == nil
            end, 300) then
                result("FAIL", "could not answer the lord-select prompt"); return false
            end
        else
            local advanced = advanceBootState(observation, state)
            if advanced == false then return false end
            if advanced == nil then
                traceFailure("reach_ch01", "post-chapter flow reaches Preparations",
                    "fail:" .. tostring(why or state), observation, "ch01-unsupported")
                result("FAIL", "unsupported state before ch01 Preparations"); return false
            end
        end
    end
    traceFailure("reach_ch01", "post-chapter flow reaches Preparations",
        "fail:chapter-flow-timeout", nil, "ch01-no-prep")
    result("FAIL", "prep screen never opened (PREP event cmd)")
    return false
end

-- The three destinations on that one route. Kept as named wrappers so every call site
-- reads as an intention rather than an options table.
local function reachCh01Map() return reachCh01() end

-- CH01: reach the ch01 map, then assert the entry invariants -- the ch00 guests left
-- the party (DISA), and the deployed count equals the 4-slot field-parity cap.
scenarios.ch01 = function()
    if not reachCh01Map() then return end
    if blue(CAMPAIGN.PROLOGUE.hlin) or blue(CAMPAIGN.PROLOGUE.scramsax) then
        return result("FAIL", "ch00 guests still in the party in ch01")
    end
    local party, deployed = 0, 0
    for _, u in BOARD.each("blue") do
        party = party + 1
        -- on the field = not US_HIDDEN (1<<0) and not US_NOT_DEPLOYED (1<<3)
        if (u.state & 0x9) == 0 and u.onMap then deployed = deployed + 1 end
    end
    log(string.format("party=%d deployed=%d turn=%d", party, deployed, turn()))
    -- Blue + red unit tables for the post-run eyeball, each at its own decomp bound.
    for i, u in BOARD.each("blue") do
        log(string.format("blue[%02d] char=0x%02X pos=(%d,%d) state=0x%08X",
            i, u.charId, u.x, u.y, u.state))
    end
    for i, r in BOARD.each("red") do
        log(string.format("red[%02d]  char=0x%02X pos=(%d,%d) state=0x%08X",
            i, r.charId, r.x, r.y, r.state))
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

-- ch01guide (#21, #135 finding 8): the turn-1 terrain-heal beat sets the Guide's "Fortresses &
-- Castle Gates" flag (0xCE), and with it the Guide command (override id 0x74, menu_def.c) shows in
-- the map menu. Before it, no Guide flag was ever set in ch01-ch04 and IsGuideLocked() hid the
-- command outright -- so this asserts both the flag and the menu the player actually sees.
scenarios.ch01guide = function()
    if not reachCh01Map() then return end
    if not awaitControllerState("player_map_idle", 900) then
        return result("FAIL", "turn-1 events never handed control back")
    end
    if not eventFlag(0xCE) then
        return result("FAIL", "turn 1 played but the Guide flag 0xCE is not set")
    end
    local tile = emptyTile()
    if not tile or not cursorTo(tile.x, tile.y) then return result("FAIL", "no reachable empty map tile") end
    if not guardedInput("open_map_menu", "A", "live map command menu opens", function(after)
        return controllerState(after) == "map_command_menu"
    end, 120) then return result("FAIL", "map menu never opened") end
    local menu = observeController().menu
    local ids = {}
    for _, item in ipairs(menu and menu.items or {}) do ids[#ids + 1] = string.format("0x%02X", item.override_id) end
    log("map menu override ids: " .. table.concat(ids, " "))
    for _, item in ipairs(menu and menu.items or {}) do
        if item.override_id == 0x74 then
            return result("PASS", "Guide flag 0xCE set on turn 1; the Guide command is in the map menu")
        end
    end
    return result("FAIL", "Guide flag is set but the map menu has no Guide command (0x74)")
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
-- it commits through a semantic Attack/Wait. Mechanical failures terminate without rescue input.
local function clearUnitAct(u, field, goal, blocked, claimed, maxx, maxy, stopWhen, enemies)
    -- thread the REAL map bounds through: selectAndReach defaults to a 15x10
    -- window, which clipped every reach list at x=14 on ch01's 25x16 map -- the
    -- probable root cause of the #60 stall at exactly (14,8)
    local reach = selectAndReach(u, maxx, maxy)
    if not reach then return nil, true end
    local mn, mx = unitAttackRange(u)
    enemies = enemies or liveEnemies()
    local pick = mn and BOT.pickTarget(reach, enemies, { range = mx, min_range = mn }) or nil
    local tile = pick and pick.tile
    if not tile then
        -- no target in range: march (pure decision core -- field-first with a
        -- Manhattan tiebreak, claimed-tile avoidance, and the chokepoint-jam
        -- fallback that pushes at the nearest enemy cork; #60 last-mile breach)
        tile = BOT.pickMove(reach, { field = field, cur = { x = u.x, y = u.y },
                                          goal = goal, blocked = blocked,
                                          enemies = enemies })
    end
    if not tile then
        traceFailure("clear_policy", "clear policy chooses a reachable destination",
            "fail:no-destination", nil, "controller-clear-no-destination")
        return nil, true
    end
    if not cursorTo(tile.x, tile.y) then return tile, true end
    if not guardedInput("confirm_move", "A", "live unit command menu opens", function(after)
        return controllerState(after) == "unit_command_menu"
    end, 180) then return tile, true end
    local committed
    -- stopWhen: won, or the boss dead. A killing blow on a DefeatBoss boss tears the map down
    -- before the actor ever greys out (the Sephek case chooseAttack documents), and without
    -- the dead-boss half the wait runs out all of combatFrames and the loop reports stuck.
    if pick then committed = chooseAttack(u.addr, stopWhen) else committed = chooseWait() end
    if not committed then return tile, true end
    if claimed then claimed[BOT.tileKey(tile.x, tile.y)] = true end
    return tile, false
end

local function cancelUnitActionMenu()
    if not guardedInput("cancel_menu", "B", "unit menu returns to movement selection", function(after)
        return controllerState(after) == "unit_selected"
    end, 120) then return false end
    return guardedInput("cancel_selection", "B", "movement selection returns to player map", function(after)
        return controllerState(after) == "player_map_idle"
    end, 120)
end

local function cancelToPlayerMap()
    -- The budget counts CANCELS, not iterations. A transition here is a screen tearing itself
    -- down -- the convoy's fade-out runs for hundreds of frames after its key handler lets go
    -- -- and charging those to an 8-step loop made the CAP the thing that decided failure,
    -- which is the trap #232 spent three sessions in. Transitions get their own frame ceiling
    -- so a genuinely wedged screen still fails closed (#238).
    local cancels, frames = 0, 0
    while cancels < 8 and frames < TUNE.cancelFrames do
        local observation = observeController()
        local state = controllerState(observation)
        if state == "player_map_idle" then return true end
        if state ~= "transition" then cancels = cancels + 1 end
        if state == "unit_selected" then
            if not guardedInput("cancel_selection", "B", "movement selection returns to player map",
                function(after) return controllerState(after) == "player_map_idle" end, 120) then
                return false
            end
        elseif state == "unit_command_menu" or state == "weapon_menu" or state == "generic_menu"
            or state == "item_list" or state == "send_to_convoy" then
            -- item_list and send_to_convoy USED to classify as generic_menu, so naming them
            -- would have quietly cost this function the ability to back out of either -- and
            -- this is the recovery path #238 put behind ch01win's post-seize "menu surprise".
            -- A new classified screen has to teach the drivers about itself in the same
            -- change, or it narrows what the harness can escape from.
            if not guardedInput("cancel_menu", "B", "live menu closes one semantic level",
                function(after) return after.menu == nil or controllerState(after) ~= state end, 120) then
                return false
            end
        elseif state == "supply_screen" or state == "unit_list_screen" then
            -- Full-screen states with their own B intention rather than a MenuProc cancel.
            local leave = state == "supply_screen" and "close_supply" or "close_list"
            if not guardedInput(leave, "B", "the full-screen state closes",
                function(after) return controllerState(after) ~= state end, 300) then
                return false
            end
        elseif state == "transition" then
            frames = frames + 1
            yield()
        else
            traceFailure("cancel_to_map", "player map after semantic cancellation",
                "fail:unsupported-cancel-state:" .. tostring(state), observation,
                "controller-cancel-unsupported")
            return false
        end
    end
    traceFailure("cancel_to_map", "player map after semantic cancellation",
        "fail:cancel-budget", nil, "controller-cancel-timeout")
    return false
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
    local lost = INSPECT.chapterLost
    -- progress = the nearest candidate's path-distance to the target (lower is better): the
    -- boss while it lives, then the seize tile, measured only from units the game lets Seize.
    -- Move a unit that cannot Seize off the throne's approach and Wait there (BOT.stepOffTile):
    -- parked on or beside a single-approach throne it would block the lord for good.
    local function stepOffSeize(u)
        local reach = selectAndReach(u, maxx, maxy)
        if not reach then return false end
        local tile = BOT.stepOffTile(reach, u, seizeTile)
        if not tile then return cancelToPlayerMap() end   -- boxed in beside it: nothing helps
        if not cursorTo(tile.x, tile.y) then return false end
        if not guardedInput("confirm_move", "A", "live unit command menu opens", function(after)
            return controllerState(after) == "unit_command_menu"
        end, 180) then return false end
        return chooseWait()
    end
    local lastDist, lastEnemies, stall = math.huge, math.huge, 0
    local lastKey = "boss:0"
    for t = 1, budgetTurns do
        INSPECT.settle("phase", 6000, true)
        wait(60) -- let the player-phase banner finish (it eats key presses)
        if not awaitControllerState("player_map_idle", 300) then return "stuck", t end
        local b = findBoss()
        -- The target field: the boss's tile while it lives, else the seize tile (its last tile).
        local field = bossDistanceField(b or seizeTile, maxx, maxy)
        local claimed = {}                       -- destinations committed this phase
        -- The turn whose player phase this is. FE8 ends the phase by itself once every unit
        -- has acted, so "the map is idle" later on may be the NEXT turn's phase: everything
        -- below that waits asks BOARD.inPhase against this, never the idle state alone.
        local phaseTurn = turn()
        local function ourPhase() return BOARD.inPhase(BOARD.header(), phaseTurn) end
        local function bossDownOrWon() return won() or not findBoss() end
        -- The phase's roster (decomp bounds, not the first 8 slots), LEAN; each unit is judged
        -- from ONE full board snapshot taken just before it acts, since earlier actions move
        -- the board -- one read per acting unit, not one per question asked about it.
        for _, slotUnit in ipairs(BOARD.leanList("blue")) do
            if won() then return "won", t end
            if lost() then return "gameover", t end
            if not ourPhase() then break end
            local board = BOARD.read()
            local u = BOARD.at(board, "blue", slotUnit.slot)
            -- onField: an undeployed, hidden or carried unit is alive and unacted but has no
            -- tile to select.
            if u and u.onField and not u.acted then   -- live, on the field, not yet acted
                b = findBoss(board)
                if b then
                    seizeTile = { x = b.x, y = b.y }
                    -- other live units' CURRENT tiles are unstandable too
                    local blocked = {}
                    for k in pairs(claimed) do blocked[k] = true end
                    for _, o in ipairs(BOARD.live(board, "blue")) do
                        if o.onField and o.slot ~= u.slot then
                            blocked[BOT.tileKey(o.x, o.y)] = true
                        end
                    end
                    local tile, failed = clearUnitAct(u, field, b, blocked, claimed,
                                                      maxx, maxy, bossDownOrWon,
                                                      liveEnemies(board))
                    if failed then
                        if tile then
                            log(string.format("clear: unit (%d,%d) chose (%d,%d) but the "
                                .. "move didn't commit", u.x, u.y, tile.x, tile.y))
                        end
                        return "stuck", t
                    end
                    -- The strike killed the boss. On a DefeatBoss map its death runs the
                    -- ending straight into the post-chapter save menu, and the next thing this
                    -- loop does (another unit, or endTurn) waits for the player map and meets
                    -- that menu as an unexpected state. Wait out the outcome the way winCh00
                    -- does -- chapter advanced -- or, on a Seize map, control coming back IN
                    -- THIS PHASE (a later phase's idle map is not ours to act in).
                    if bossDownOrWon() then
                        waitFor(function()
                            return won() or not ourPhase()
                                or controllerState() == "player_map_idle"
                        end, TUNE.combatFrames, true)
                        if won() then return "won", t end
                    end
                elseif not INSPECT.canSeize(u) then
                    -- The game's CanUnitSeize says no: it does not march on the throne, and if
                    -- it stands on or beside it, it clears the way.
                    if BOT.needsToStepOff(u, seizeTile) and not stepOffSeize(u) then
                        return "stuck", t
                    end
                elseif moveUnit(u.x, u.y, seizeTile.x, seizeTile.y) then
                    -- Boss dead, not yet won: this unit may Seize (CanUnitSeize), so the menu
                    -- offers it on the seize tile.
                    shot("clear-seize-try")
                    local actions = Controller.legalActions(observeController())
                    if Controller.findAction(actions, "seize") then
                        if not selectSemantic("seize", "Seize starts the chapter win event", function()
                            return won() or procActive(SYM.ProcScr_StdEventEngine)
                        end, 900) then return "stuck", t end
                        if waitFor(won, 9000, true) then return "won", t end
                        traceFailure("seize", "chapter advances after the Seize event",
                            "fail:chapter-advance-timeout", nil, "controller-seize-timeout")
                        return "stuck", t
                    else
                        -- The game's CanUnitSeize allowed it and the menu offers no Seize: this
                        -- tile is not the seize tile (the boss's tile is this loop's guess).
                        traceFailure("seize", "the menu offers Seize to a unit CanUnitSeize allows",
                            "fail:no-seize-command", nil, "controller-no-seize-command")
                        return "stuck", t
                    end
                elseif ourPhase() and not won() then
                    -- The seize tile is out of this unit's reach this turn (moveUnit backed
                    -- out). Close the distance instead of standing still: a lord left far off
                    -- when someone else killed the boss otherwise never reaches the throne,
                    -- and clear_ch01 stalls with every enemy dead. marchToward only takes a
                    -- REACHABLE tile, and this branch only runs when the seize tile is not
                    -- one, so a unit that cannot seize never parks on it.
                    if not marchToward(u, seizeTile.x, seizeTile.y, maxx, maxy)
                        and not cancelToPlayerMap() then
                        return "stuck", t
                    end
                end
            end
        end
        if won() then return "won", t end
        if lost() then return "gameover", t end
        -- won, as endTurn's alreadyWon: when the last unit acts FE8 ends the player phase by
        -- itself, and the boss can die on the enemy phase that follows (a counter) with the
        -- ending running straight into the save menu. Waiting for the player map there met that
        -- menu as an unexpected state and failed a won `clear`.
        local phase = runEnemyPhase(park, won, phaseTurn)
        if phase == "gameover" then return "gameover", t end
        -- "ended" = the phase carried the chapter out (a DefeatAll win fires the ending from
        -- inside it). Ask won() rather than calling it stuck: the bot did its job (#335).
        if phase == "ended" then return won() and "won" or "ended", t end
        if phase ~= "player" then return "stuck", t end
        -- stall watchdog: bail cleanly if no progress (nearer the boss OR fewer foes) for 3 turns,
        -- instead of grinding the full budget on a wedged bot.
        -- Once the boss is dead only a unit that can Seize is closing on anything: measure from
        -- those (the game's CanUnitSeize), or a non-lord standing near the throne masks the
        -- lord's march.
        local blueUnits, excluded = BOARD.leanList("blue"), {}
        if not findBoss() then
            for _, o in ipairs(blueUnits) do
                if not INSPECT.canSeize(o) then
                    excluded[o.slot] = true
                end
            end
        end
        local dist = BOT.seizeDistance(blueUnits, field, excluded)
        local enemies = BOARD.liveCount("red")
        local key = findBoss() and "boss" or "seize"   -- what the distance is measured to
        if BOT.madeProgress({ dist = lastDist, enemies = lastEnemies, key = lastKey },
                                 { dist = dist, enemies = enemies, key = key }) then
            stall = 0
        else
            stall = stall + 1
        end
        if key ~= lastKey then lastDist = dist end   -- a new question starts a new best
        lastDist, lastEnemies, lastKey = math.min(dist, lastDist), math.min(enemies, lastEnemies), key
        log(string.format("clear turn %d: targetDist=%s enemies=%d stall=%d",
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
                for _, u in ipairs(BOARD.leanList("blue")) do
                    if not u.dead then log(string.format("  unit (%d,%d) fd=%s",
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

-- ---- the bot plays the game (#510 step 9 PR D). botrun.lua and sight.lua are their own
-- chunks; everything here is the `api` they talk over (ADR 0369), built on the drivers above.
-- The sandbox's CPU. A call runs as ordinary emulation: `frames` yields this coroutine a frame
-- at a time until the call is back in its loop. Every write, save and load goes through the
-- memo guard (`emu`, procmemo.lua, ADR 0366): a load rewinds the frame counter, and a write may
-- land anywhere, so the proc-pool memo is dropped with each. Register reads/writes are the
-- CPU's, never memory, and go to the real emulator.
INSPECT.sightApi = function()
    local raw = PROCS.raw
    INSPECT.Sight = INSPECT.Sight or dofile(PLAYTEST_DIR .. "/sight.lua")
    return {
        mem = { u8 = ru8, s8 = rs8, u16 = ru16, s16 = rs16, u32 = ru32 },
        write8 = function(a, v) emu:write8(a, v) end,
        write16 = function(a, v) emu:write16(a, v) end,
        write32 = function(a, v) emu:write32(a, v) end,
        SYM = SYM,
        Board = BOARD,
        cpu = {
            read = function(r) return raw:readRegister(r) end,
            write = function(r, v) raw:writeRegister(r, v) end,
            -- The frame a sandbox starts from holds log()'s stamps still while it runs (the
            -- calls' frames are counted into INSPECT.sandboxFrames instead). The save sets it only
            -- once the state is taken and the load clears it first, so a save or load that
            -- raises cannot leave the stamps frozen.
            save = function()
                local at, t0 = emu:currentFrame(), os.clock()
                local st = emu:saveStateBuffer()
                INSPECT.sandboxAt = at
                INSPECT.costs.calls = INSPECT.costs.calls + 1
                INSPECT.costs.save = INSPECT.costs.save + os.clock() - t0
                return st
            end,
            load = function(st)
                local t0 = os.clock()
                INSPECT.sandboxAt = nil
                emu:loadStateBuffer(st)
                INSPECT.costs.load = INSPECT.costs.load + os.clock() - t0
            end,
            write16 = function(a, v) emu:write16(a, v) end,
            write32 = function(a, v) emu:write32(a, v) end,
            -- Each frame a call runs is real emulation, though the load rewinds the counter:
            -- INSPECT.sandboxFrames keeps it, and log() stamps lines with it added, so a run's
            -- cost, run.sh's frame budget and its stall watch all see what the sight spent. A
            -- heartbeat line every TUNE.sandboxHeartbeat frames keeps a long think visible.
            frames = function(done, max)
                local t0 = os.clock()
                local function spent() INSPECT.costs.run = INSPECT.costs.run + os.clock() - t0 end
                for _ = 1, max do
                    yield()
                    INSPECT.sandboxFrames = INSPECT.sandboxFrames + 1
                    if INSPECT.sandboxFrames % TUNE.sandboxHeartbeat == 0 then
                        log(string.format("sight: %d frames of game code run so far",
                            INSPECT.sandboxFrames))
                    end
                    if done() then spent() return true end
                end
                spent()
                return false
            end,
        },
        map = mapSize,
        chapter = chapter,
        turn = turn,
        board = BOARD.read,
    }
end

-- The game's answers the hand-written scenarios ask outside a bot run: a unit's attack reach
-- (unitAttackRange, far above) and who may Seize (the clear loop).
INSPECT.attackRange = function(u)
    local api = INSPECT.sightApi()
    local r = INSPECT.Sight.range(api, u)
    if r then return r.min, r.max end
    return nil
end
INSPECT.canSeize = function(u) return INSPECT.Sight.canSeize(INSPECT.sightApi(), u) end

-- Every unit that falls during an enemy phase, with the fighter it fell to: a frame callback
-- for the phase's length that watches both arrays (lean) and, the frame one goes down, reads
-- who is fighting -- gBattleActor/gBattleTarget +0x0B is the unit index, +0x00 the character.
INSPECT.watchDeaths = function()
    local alive, deaths = {}, {}
    for _, f in ipairs({ "blue", "red" }) do
        for _, u in ipairs(BOARD.leanList(f)) do
            if u.onField then alive[ru8(u.addr + 0x0B)] = { charId = u.charId, faction = f } end
        end
    end
    local function charOf(bu) return ru8(ru32(bu) + 4) end
    local id = callbacks:add("frame", function()
        for uid, who in pairs(alive) do
            local addr = ru32(SYM.gUnitLookup + uid * 4)
            if addr == 0 or ru8(addr + 0x13) == 0 or (ru32(addr + 0x0C) & BOARD.US_DEAD) ~= 0 then
                local killer
                if ru8(SYM.gBattleActor + 0x0B) == uid then killer = charOf(SYM.gBattleTarget)
                elseif ru8(SYM.gBattleTarget + 0x0B) == uid then
                    killer = charOf(SYM.gBattleActor)
                end
                deaths[#deaths + 1] = { id = uid, charId = who.charId, faction = who.faction,
                                        killer = killer }
                alive[uid] = nil
            end
        end
    end)
    return function() callbacks:remove(id); return deaths end
end

-- Each act of an enemy (or green) phase, as the game records it, for the run's trace. Every
-- act the AI performs starts with UnitBeginAction (bmunit.c): gActionData +0C subjectIndex = the
-- unit, +11 unitActionType = 0, gActiveUnitMoveOrigin = its tile; CpPerform then sets the type
-- (AiStartCombatAction: COMBAT and +0D targetIndex; AiStaffAction: STAFF and +0D; AiPickAction:
-- PICK, the village or chest at
-- +13/+14 xOther/yOther). A frame watch follows that record. The act's battle is read once the
-- type is COMBAT and gBattleStats says REAL after the act began on a simulation: the AI simulates
-- every attack it weighs (AiComputeCombatScore) before it performs one, so a REAL flag seen
-- only after that is this act's own battle, never one left from an earlier phase.
INSPECT.watchEnemyActs = function()
    local acts, cur = {}, nil
    local AD = SYM.gActionData
    local prev = ru8(AD + 0x0C)
    local function real() return (ru16(SYM.gBattleStats) & BOARD.BATTLE_REAL) ~= 0 end
    local function close()
        if not cur then return end
        local addr = ru32(SYM.gUnitLookup + cur.id * 4)
        if addr ~= 0 then cur.to, cur.hp = { x = rs8(addr + 0x10), y = rs8(addr + 0x11) }, ru8(addr + 0x13) end
        cur.sim = nil
        acts[#acts + 1] = cur
        cur = nil
    end
    local id = callbacks:add("frame", function()
        local uid = ru8(AD + 0x0C)
        if uid ~= prev then
            prev = uid
            close()
            local addr = uid >= 0x40 and ru32(SYM.gUnitLookup + uid * 4) or 0
            if addr ~= 0 and ru32(addr) ~= 0 then
                cur = { id = uid, charId = ru8(ru32(addr) + 4), battles = {},
                        from = { x = rs16(SYM.gActiveUnitMoveOrigin), y = rs16(SYM.gActiveUnitMoveOrigin + 2) },
                        sim = not real() }
            end
        end
        if not cur then return end
        local kind = ru8(AD + 0x11)
        if kind ~= 0 then
            cur.act = BOARD.ACTIONS[kind] or string.format("0x%02X", kind)
            -- only AiStartCombatAction and AiStaffAction set +0D: any other act leaves the
            -- last one's target there
            if kind == BOARD.ACTION_PICK then
                cur.tile = { x = ru8(AD + 0x13), y = ru8(AD + 0x14) }
            elseif kind == BOARD.ACTION_COMBAT or kind == BOARD.ACTION_STAFF then
                cur.targetId = ru8(AD + 0x0D)
            end
        end
        if not real() then
            cur.sim = true
        elseif cur.sim and kind == BOARD.ACTION_COMBAT and #cur.battles == 0 then
            cur.battles[1] = BOARD.battle()
        end
    end)
    return function() close(); callbacks:remove(id); return acts end
end

-- Botrun's api over this harness. `info.game` is "ours" or "vanilla".
INSPECT.botApi = function(game)
    local Json = dofile(PLAYTEST_DIR .. "/json.lua")
    local sightApi = INSPECT.sightApi()
    local Sight = INSPECT.Sight
    local start = chapter()
    local function won() return chapter() ~= start end
    local lost = INSPECT.chapterLost
    local function decode(s, default)
        if s == nil or s == "" then return default end
        return Json.decode(s)
    end
    local style = decode(PLAYTEST_STYLE, { aggression = "careful", deploy = {}, claims = {} })
    local api = {
        Bot = BOT, Json = Json, Planner = INSPECT.Planner,
        info = { game = game, rom_hash = PLAYTEST_ROMHASH, chapter = start,
                 mode = TUNE.difficultyName[TUNE.difficultyWant],
                 seed = tonumber(PLAYTEST_SEED) or 1 },
        style = style,
        claims = decode(PLAYTEST_CLAIMS, {}),
        board = BOARD.read,
        won = won,
        lost = lost,
        -- Emulated frames, the sandbox's included (sightApi's cpu.frames counts them).
        frames = INSPECT.framesRun,
        -- What the run spent, for the record: CPU seconds in all, and in the sandbox's saves,
        -- loads and game frames, with its call count (os.clock: CPU time, the cost that
        -- matters on a busy machine).
        costs = function()
            local c = INSPECT.costs
            local names, by = {}, {}
            for name, addr in pairs(SYM) do
                if type(addr) == "number" then names[addr & ~1] = name end
            end
            for addr, n in pairs(INSPECT.Sight.calls) do
                by[names[addr & ~1] or string.format("0x%08X", addr)] = n
            end
            return { cpu_s = os.clock(), sandbox_calls = c.calls, save_s = c.save,
                     load_s = c.load, run_s = c.run, game_calls = by }
        end,
        emit = function(line) log(line); io.stdout:write(line .. "\n"); io.stdout:flush() end,
        log = log,
        battle = BOARD.battle,
        -- every full-bag answer since the last call (INSPECT.answerFullBag's log)
        bag = function()
            local out, n = {}, INSPECT.bagSeen or 0
            for i = n + 1, #INSPECT.bagLog do out[#out + 1] = INSPECT.bagLog[i] end
            INSPECT.bagSeen = #INSPECT.bagLog
            return out
        end,
    }
    INSPECT.onFullBag = INSPECT.answerFullBag
    -- The run's trace (botrun.lua): one JSON line per event in the run dir, a file per chapter
    -- attempt, named in the record (montecarlo.py files it in the store).
    local traceFile
    api.trace = function(ev)
        if not traceFile then
            api.info.trace = string.format("trace-%s-%d-a%d.jsonl", game, api.info.chapter,
                                           api.info.attempt or 1)
            traceFile = assert(io.open(PLAYTEST_SHOTDIR .. "/" .. api.info.trace, "w"))
        end
        traceFile:write(Json.encode(ev), "\n")
        if ev.t == "end" then traceFile:close(); traceFile = nil end
    end
    api.seed = function(s) return Sight.seed(sightApi, s) end
    api.sight = function() return Sight.new(sightApi) end
    -- A failed act returns false and, where the driver knows it, why (the crash record says it).
    -- One action of Bot.decide's or the planner's: move, then attack the chosen enemy, wait,
    -- Talk, open a door, heal, use an item, Visit, open a chest, or Seize.
    api.act = function(a)
        local u = BOARD.find("blue", a.unit)
        if not u then return false, "the unit is not on the board" end
        if not moveUnit(u.x, u.y, a.move.x, a.move.y) then return false, "the move failed" end
        if a.act == "attack" then
            -- The actor can die in its own attack: a dead unit is never greyed out, so its
            -- death is an exit of the combat wait too. So is the event engine taking over: a
            -- kill that ends the chapter (vanilla Ch2's DefeatAll, a Defeat Boss boss) plays
            -- the ending from there, the actor never greyed out, and ~1,700 frames of it ran
            -- the combat budget out. What follows is waited out on the enemy phase's
            -- wedge-catcher budget, until the chapter advances or control comes back.
            local dead = function() return (ru32(u.addr + 0x0C) & BOARD.US_DEAD) ~= 0 end
            local function settled()
                return won() or lost() or dead() or (ru32(u.addr + 0x0C) & 0x2) ~= 0
            end
            if not chooseAttack(u.addr, function()
                return won() or lost() or dead() or procActive(SYM.ProcScr_StdEventEngine)
            end, a.targetId, a.obstacle) then
                return false, a.obstacle and "the strike on the wall did not play out"
                    or "the attack did not play out"
            end
            if not settled() and not waitFor(function()
                return settled() or controllerState() == "player_map_idle"
            end, TUNE.enemyPhaseFrames, true) then
                return false, "an event began in the attack, and the game never came back"
            end
            return true
        elseif a.act == "talk" then
            if not chooseTalk(a.targetId) then return false end
            return INSPECT.awaitActed(u.addr, function() return won() or lost() end)
        elseif a.act == "door" then
            if not selectSemantic("open_door", "the Door command opens the door", function(after)
                return after.menu == nil
            end, 120) then return false end
            return INSPECT.awaitActed(u.addr, function() return won() or lost() end)
        elseif a.act == "visit" or a.act == "chest" then
            -- the village's lines are pressed through until the unit is greyed out (awaitActed
            -- taps each box, as VISIT.run's talkUntil does); a full inventory's send-or-discard
            -- menu is not driven, so it ends the run as a crash that names the act
            local cmd = a.act == "visit" and "visit" or "open_chest"
            if not selectSemantic(cmd, "the " .. a.act .. " command starts the tile's event",
                function(after) return after.menu == nil end, 120) then return false end
            return INSPECT.awaitActed(u.addr, function() return won() or lost() end)
        elseif a.act == "staff" then
            return INSPECT.chooseStaff(u.addr, a.slot, a.targetId, function() return won() or lost() end)
        elseif a.act == "item" then
            local opened, why = INSPECT.itemSubmenu(a.slot)
            if not opened then return false, why end
            if not selectSemantic("use_item", "Use starts the item's effect", function(after)
                return controllerState(after) ~= "item_submenu"
            end, 120) then return false, "the item's submenu offered no Use" end
            if INSPECT.awaitActed(u.addr, function() return won() or lost() end) then return true end
            return false, "the unit never finished using the item"
        elseif a.act == "seize" then
            if not Controller.findAction(Controller.legalActions(observeController()), "seize") then
                return cancelUnitActionMenu() and "noseize"
            end
            if not selectSemantic("seize", "Seize starts the chapter win event", function()
                return won() or procActive(SYM.ProcScr_StdEventEngine)
            end, 900) then return false end
            return waitFor(won, 9000, true)
        end
        return chooseWait()
    end
    api.endPhase = function()
        local phaseTurn = turn()
        local stop, stopActs = INSPECT.watchDeaths(), INSPECT.watchEnemyActs()
        local phase = runEnemyPhase(nil, won, phaseTurn)
        local deaths, acts = stop(), stopActs()
        if phase == "player" then INSPECT.settle("phase", 6000, true); wait(60) end
        return phase, deaths, acts
    end
    return api
end

-- ---- the bot plays chapter to chapter (#510 step 9 PR E). campaign.lua is its own chunk;
-- this is its api over the drivers above (ADR 0370). Every rule is the game's: the Pick Units
-- screen, the shop screen (StartShopScreen, a kept call), the world map's own cursor, and the
-- game's checks run in sight.lua's sandbox -- CanUnitUseWeapon, CanUnitUsePromotionItem,
-- IsCharacterForceDeployed, MakeNewItem + GetItemPurchasePrice, GetNextUnclearedNode.
INSPECT.CAMPAIGN = {
    VULNERARY = 0x6C,                           -- constants/items.h ITEM_VULNERARY
    SHOP_TYPE = { armory = 0, vendor = 1 },     -- bmshop.h SHOP_TYPE_ARMORY / _VENDOR
    -- worldmap.h: GMapData ix/iy +08/+0C (<<8), units[0].location +11, nodes[0x1C] +30 (bit 0
    -- GM_NODE_STATE_VALID; a GMNode is padded to 4 bytes: the next field sits at +A0);
    -- GMapNodeData stride 0x20, armory +0C, vendor +10, x +18, y +1A.
    NODES = 0x1C, NODE_OPEN = 1, GM_IX = 0x08, GM_IY = 0x0C, GM_LORD = 0x11, GM_NODES = 0x30,
    GM_NODE_STRIDE = 4,
    NODE_STRIDE = 0x20, NODE_SHOP = { armory = 0x0C, vendor = 0x10 }, NODE_X = 0x18, NODE_Y = 0x1A,
    SHOP_LIST_MAX = 20,                         -- bmshop.h SHOP_ITEMS_MAX_AMT + 1
    -- bmitem.h ItemData +07 weaponType, +08 attributes; IA_WEAPON. The type is a name only so
    -- bot.lua can group by it.
    ITEM_TYPE = 0x07, ITEM_ATTRIBUTES = 0x08, IA_WEAPON = 1,
    WEAPON_TYPES = { [0] = "sword", "lance", "axe", "bow", "staff", "anima", "light", "dark" },
    PREP_COUNT = 0x100,                         -- PrepUnitList.max_num, after units[0x40]
    PLAY_GOLD = 0x08,                           -- PlaySt +08 partyGoldAmount
    shopSteps = 4000,                           -- frames one purchase may take, fades included
}

-- A full bag (INSPECT.answerFullBag): include/bmitem.h ItemData +10 pEffectiveness, +19
-- encodedRange (max in the low nibble), +1C weaponRank, +1E useEffectId; IA_STAFF; include/
-- types.h BmSt +2C um_tmp_item (the item that found no room); Unit +1E items[5] (bmunit.h);
-- menu_def.c's
-- convoy chooser rows. Keys: what GetUnitKeyItemSlotForTerrain looks for (bmunit.c). Passive:
-- the items the engine tests by id or attribute while carried -- the Member Card (eventinfo.c),
-- the Silver Card (bmshop.c), the Delphi and Hoplon Shields (IA_NEGATE_FLYING / _CRIT).
INSPECT.BAG = {
    ITEM_EFFECTIVE = 0x10, ITEM_RANGE = 0x19, ITEM_RANK = 0x1C, ITEM_USE_EFFECT = 0x1E,
    IA_STAFF = 4, BMST_TMP_ITEM = 0x2C, UNIT_ITEM_LIST = 0x1E, UNIT_ITEMS = 5,
    CHAR_NUMBER = 0x04,                         -- CharacterData +04 number (bmunit.h)
    MENU_DISCARD_FIRST = 0x24, MENU_SEND_FIRST = 0x2A,
    KEYS = { [0x69] = "ITEM_CHESTKEY", [0x6A] = "ITEM_DOORKEY", [0x6B] = "ITEM_LOCKPICK",
             [0x79] = "ITEM_CHESTKEY_BUNDLE" },
    PASSIVE = { [0x71] = "ITEM_DELPHISHIELD", [0x72] = "ITEM_MEMBERCARD",
                [0x73] = "ITEM_SILVERCARD", [0x7C] = "ITEM_HOPLON_SHIELD" },
}
INSPECT.bagLog = {}

-- The world map's cursor and lord, for the observer: the open nodes, the node the cursor sits
-- on (sub_80B961C, the L jump, puts ix/iy exactly on a node's x/y << 8), the lord's node.
INSPECT.worldMap = function()
    local C, gm = INSPECT.CAMPAIGN, SYM.gGMData
    local cx, cy = ru32(gm + C.GM_IX) >> 8, ru32(gm + C.GM_IY) >> 8
    local wm = { lord_node = ru8(gm + C.GM_LORD), open = {} }
    for n = 0, C.NODES - 1 do
        if (ru8(gm + C.GM_NODES + n * C.GM_NODE_STRIDE) & C.NODE_OPEN) ~= 0 then
            wm.open[#wm.open + 1] = n
            local node = SYM.gWMNodeData + n * C.NODE_STRIDE
            if rs16(node + C.NODE_X) == cx and rs16(node + C.NODE_Y) == cy then wm.cursor_node = n end
        end
    end
    return wm
end

-- Run game functions in sight.lua's sandbox (keep = false: everything is loaded back) or kept
-- (keep = true: what they wrote stays, the registers are put back).
INSPECT.gameCalls = function(fn, keep)
    local api = INSPECT.sightApi()
    return INSPECT.Sight.machine(api.cpu, keep)(fn)
end

-- An item's facts for bot.lua: the weapon type of a weapon, and which item is the Vulnerary.
INSPECT.itemFacts = function(id)
    local C = INSPECT.CAMPAIGN
    local data = SYM.gItemData + id * BOARD.ITEMDATA_STRIDE
    local facts = { id = id }
    if (ru32(data + C.ITEM_ATTRIBUTES) & C.IA_WEAPON) ~= 0 then
        facts.type = C.WEAPON_TYPES[ru8(data + C.ITEM_TYPE)]
    end
    if id == C.VULNERARY then facts.kind = "vulnerary" end
    return facts
end

-- What Bot.fullBag weighs about one item for one unit, every fact the game's (#510 step 9,
-- Nicolas 2026-10-28). `call` is a sandbox's (INSPECT.gameCalls); `item` = { id, uses }.
-- kind: a weapon or staff (IA_WEAPON | IA_STAFF; usable = CanUnitUseWeapon / CanUnitUseStaff;
-- rank, the reach's max and the effectiveness list from its ItemData), a key (what
-- GetUnitKeyItemSlotForTerrain looks for), a passive item (each one the engine tests by id),
-- a heal (GetUnitItemHealAmount > 0), money (no use effect at all: gems, gold), else other
-- (seals, boosters, Pure Water...).
INSPECT.unitItemFacts = function(call, unitAddr, item)
    local C, K = INSPECT.CAMPAIGN, INSPECT.BAG
    local f = INSPECT.itemFacts(item.id)
    local data = SYM.gItemData + item.id * BOARD.ITEMDATA_STRIDE
    local attr, value = ru32(data + C.ITEM_ATTRIBUTES), item.id | (item.uses << 8)
    f.uses = item.uses
    if (attr & (C.IA_WEAPON | K.IA_STAFF)) ~= 0 then
        f.kind = "weapon"
        f.type = C.WEAPON_TYPES[ru8(data + C.ITEM_TYPE)]
        f.rank = ru8(data + K.ITEM_RANK)
        f.maxRange = ru8(data + K.ITEM_RANGE) & 0xF
        local eff = ru32(data + K.ITEM_EFFECTIVE)
        f.effective = eff ~= 0 and eff or nil
        local check = (attr & K.IA_STAFF) ~= 0 and SYM.CanUnitUseStaff or SYM.CanUnitUseWeapon
        f.usable = call(check, { unitAddr, value }) ~= 0
    elseif K.KEYS[item.id] then
        f.kind = "key"
    elseif K.PASSIVE[item.id] then
        f.kind = "passive"
    elseif call(SYM.GetUnitItemHealAmount, { unitAddr, value }) > 0 then
        f.kind = "heal"
    elseif ru8(data + K.ITEM_USE_EFFECT) == 0 then
        f.kind = "money"
    else
        f.kind = "other"
    end
    return f
end

-- A unit handed an item it has no room for (convoymenu.c HandleNewItemGetFromDrop): FE8's
-- chooser, answered by Bot.fullBag. With room in the convoy the rows send (0x2A-0x2E the
-- unit's items, 0x2F the new one); a full convoy's rows discard (0x24-0x29) and ask Yes/No
-- first. Every answer is kept in INSPECT.bagLog for the run's record.
INSPECT.answerFullBag = function()
    local K = INSPECT.BAG
    local o = observeController()
    local base = o.menu.items[1].override_id
    local discard = base < K.MENU_SEND_FIRST
    if discard then base = K.MENU_DISCARD_FIRST else base = K.MENU_SEND_FIRST end
    local unitAddr = ru32(SYM.gActiveUnit)
    local newId = ru16(SYM.gBmSt + K.BMST_TMP_ITEM)
    local held = {}
    for k = 0, K.UNIT_ITEMS - 1 do
        local raw = ru16(unitAddr + K.UNIT_ITEM_LIST + k * 2)
        if (raw & 0xFF) ~= 0 then held[#held + 1] = { id = raw & 0xFF, uses = raw >> 8 } end
    end
    local facts = INSPECT.gameCalls(function(call)
        local out = { held = {} }
        for _, it in ipairs(held) do out.held[#out.held + 1] = INSPECT.unitItemFacts(call, unitAddr, it) end
        out.new = INSPECT.unitItemFacts(call, unitAddr, { id = newId & 0xFF, uses = newId >> 8 })
        return out
    end)
    local slot, why = BOT.fullBag(facts.held, facts.new, discard)
    local row = base + (slot == 0 and K.UNIT_ITEMS or slot - 1)
    local entry = { charId = ru8(ru32(unitAddr) + K.CHAR_NUMBER), item = facts.new.id,
                    sent = slot == 0 and facts.new.id or facts.held[slot].id, discard = discard,
                    why = why }
    INSPECT.bagLog[#INSPECT.bagLog + 1] = entry
    log(string.format("bag: unit 0x%X gets item 0x%X; %s 0x%X (%s)", entry.charId, entry.item,
        discard and "discards" or "sends", entry.sent, why))
    if not INSPECT.menuTo("send_to_convoy", row) then return false end
    if not guardedInput("send_item", "A", "the chooser takes the row", function(after)
        return controllerState(after) ~= "send_to_convoy" or after.choice ~= nil
    end, 120) then return false end
    if controllerState() == "yes_no_choice" then
        return selectSemantic("answer_yes", "the discard is confirmed", function(after)
            return controllerState(after) ~= "yes_no_choice"
        end, 120)
    end
    return true
end

-- The shops a set of world map nodes holds: { node, kind, list (the stock's address), items }.
INSPECT.nodeShops = function(nodes)
    local C, out = INSPECT.CAMPAIGN, {}
    for _, n in ipairs(nodes) do
        local node = SYM.gWMNodeData + n * C.NODE_STRIDE
        for _, kind in ipairs({ "armory", "vendor" }) do
            local list = ru32(node + C.NODE_SHOP[kind])
            local items = {}
            for i = 0, C.SHOP_LIST_MAX - 1 do
                local it = list ~= 0 and ru16(list + i * 2) or 0
                if it == 0 then break end
                items[#items + 1] = it
            end
            if #items > 0 then out[#out + 1] = { node = n, kind = kind, list = list, items = items } end
        end
    end
    return out
end

-- Campaign.run's api (campaign.lua's contract). `game` is "ours" or "vanilla".
INSPECT.campaignApi = function(game)
    local C = INSPECT.CAMPAIGN
    local Json = dofile(PLAYTEST_DIR .. "/json.lua")
    local Botrun = dofile(PLAYTEST_DIR .. "/botrun.lua")
    local cfg = (PLAYTEST_CAMPAIGN ~= nil and PLAYTEST_CAMPAIGN ~= "") and Json.decode(PLAYTEST_CAMPAIGN)
        or {}
    local seed = tonumber(PLAYTEST_SEED) or 1
    local mode = TUNE.difficultyName[TUNE.difficultyWant]
    local id = cfg.id or string.format("%s-s%d", mode, seed)
    local dir = PLAYTEST_SIMDIR .. "/states/" .. id
    local states, played, shops, leadPicked = {}, nil, nil, nil
    math.randomseed(seed)
    local function gold() return ru32(SYM.gPlaySt + C.PLAY_GOLD) end

    -- The world map shops open now: vanilla's from its own world map; ours has none yet, so
    -- the twin's at the same point, as the vanilla campaign recorded them (cfg.shops).
    local function openNodes(ch)
        if game == "vanilla" then return INSPECT.worldMap().open end
        return (cfg.shops or {})[tostring(ch)] or {}
    end
    -- The stock of every open shop; an item two shops sell is bought at the first. Unpriced:
    -- api.stock prices it.
    local function stockItems(ch)
        local list, seen = {}, {}
        for _, shop in ipairs(INSPECT.nodeShops(openNodes(ch))) do
            for _, it in ipairs(shop.items) do
                if not seen[it] then
                    seen[it] = true
                    local e = INSPECT.itemFacts(it)
                    list[#list + 1] = { item = it, type = e.type, kind = e.kind, shop = shop }
                end
            end
        end
        return list
    end
    -- The units the player could field: the Pick Units list while Preparations is up (its
    -- owner, ProcScr_AtMenu, which stays alive under Pick Units; the command list's proc does
    -- not), else the blue units on the field. gPrepUnitList is an EWRAM overlay other prep
    -- screens reuse, so it is built here, in the sandbox, by the game's own MakePrepUnitList
    -- (what Pick Units runs when it opens).
    local function units()
        local all, out = BOARD.read().units, {}
        if PROCS.find(SYM.ProcScr_AtMenu) then
            local byAddr = {}
            for _, u in ipairs(all) do byAddr[u.addr] = u end
            local listed = INSPECT.gameCalls(function(call)
                call(SYM.MakePrepUnitList, {})
                local addrs = {}
                for i = 0, ru32(SYM.gPrepUnitList + C.PREP_COUNT) - 1 do
                    addrs[#addrs + 1] = ru32(SYM.gPrepUnitList + i * 4)
                end
                return addrs
            end)
            for _, a in ipairs(listed) do
                if byAddr[a] then out[#out + 1] = byAddr[a] end
            end
            return out
        end
        for _, u in ipairs(all) do
            if u.faction == "blue" and u.onField then out[#out + 1] = u end
        end
        return out
    end

    local api = { Bot = BOT, Json = Json,
        info = { game = game, rom_hash = PLAYTEST_ROMHASH, mode = mode, seed = seed, campaign = id,
                 route = cfg.route },
        random = math.random,
        -- What the party may spend is the game's answer, not the PlaySt field: GetPartyGoldAmount
        -- is 0 in Ch5x (bmgold.c), where the shop refuses every purchase.
        gold = function()
            return INSPECT.gameCalls(function(call) return call(SYM.GetPartyGoldAmount, {}) end)
        end,
        emit = function(line) log(line); io.stdout:write(line .. "\n"); io.stdout:flush() end,
        log = log,
    }
    api.claims = function(ch) return (cfg.claims or {})[tostring(ch)] or {} end
    -- cfg.attempt: play that one attempt from cfg.from's start and stop (campaign.lua; the pool)
    if cfg.attempt ~= nil and not (cfg.from and math.type(cfg.attempt) == "integer" and cfg.attempt >= 1) then
        error("PT_CAMPAIGN: attempt must be an integer >= 1, with from")
    end
    api.only = cfg.attempt
    -- Priced by the game for the first fielded unit, on the map: GetItemPurchasePrice charges
    -- half again while BM_FLAG_PREPSCREEN is set, and the bot buys on the map.
    api.stock = function()
        if shops then return shops end
        local lord = BOARD.read().units[1]
        local list = stockItems(chapter())
        INSPECT.gameCalls(function(call)
            for _, s in ipairs(list) do
                s.price = call(SYM.GetItemPurchasePrice, { lord.addr, call(SYM.MakeNewItem, { s.item }) })
            end
        end)
        shops = list
        return shops
    end
    api.roster = function()
        local us, stock = units(), stockItems(chapter())
        return INSPECT.gameCalls(function(call)
            local out = {}
            for _, u in ipairs(us) do
                local e = { id = u.id, charId = u.charId, classId = u.classId, level = u.level,
                            canUse = {}, items = {},
                            forced = call(SYM.IsCharacterForceDeployed, { u.charId }) ~= 0 }
                for _, s in ipairs(stock) do
                    if call(SYM.CanUnitUseWeapon, { u.addr, call(SYM.MakeNewItem, { s.item }) }) ~= 0 then
                        e.canUse[s.item] = true
                    end
                end
                for _, held in ipairs(u.items) do
                    local f = INSPECT.itemFacts(held.id)
                    f.promotes = call(SYM.CanUnitUsePromotionItem,
                        { u.addr, held.id | (held.uses << 8) }) ~= 0 or nil
                    e.items[#e.items + 1] = f
                end
                out[#out + 1] = e
            end
            return out
        end)
    end

    -- What the map asks of a team and how each roster unit answers it, read at the prep screen
    -- by sight.lua (the game's own checks). A demand's `rep` (a board unit) is dropped before it
    -- is returned: the record keeps the demand's id.
    api.needs = function(roster)
        local sight = INSPECT.Sight.new(INSPECT.sightApi())
        local demands, byChar = sight.demands(), {}
        for _, u in ipairs(units()) do byChar[u.charId] = u end
        local answers, strength = {}, {}
        for _, e in ipairs(roster) do
            answers[e.charId], strength[e.charId] = {}, {}
            for _, d in ipairs(demands) do
                answers[e.charId][d.id], strength[e.charId][d.id] = sight.answer(byChar[e.charId], d)
            end
        end
        for _, d in ipairs(demands) do d.rep = nil end
        return { demands = demands, answers = answers, strength = strength }
    end
    -- The team caps (team_groups.py, carried in PT_CAMPAIGN): class id -> group, and maxima.
    api.teamGroups = function() return cfg.groups or {}, cfg.maxima or {} end

    -- Ride the game to the next chapter's start: its prep screen, else its first player phase.
    -- The world map walks the lord to the game's next story node (GetNextUnclearedNode) by its
    -- own L and A; it never enters any other node.
    api.arrive = function(route)
        for _, last in ipairs(cfg.last or {}) do
            if played == last then return "end" end
        end
        shops = nil
        -- cfg.from: resume at that chapter's start as an earlier run of this campaign id saved
        -- it, rather than replaying every chapter before it. The state holds the game's RNG, so
        -- nothing is seeded; no team is carried (a resumed pick has no last clear to keep).
        if played == nil and cfg.from then
            local f = io.open(string.format("%s/%d.ss", dir, cfg.from), "rb")
            if not f then return nil, string.format("no saved start for chapter %d in %s", cfg.from, dir) end
            emu:loadStateBuffer(f:read("a"))
            f:close()
            wait(2)
            played = cfg.from
            log(string.format("campaign: chapter %d resumes (%s)", played, controllerState()))
            return { chapter = played }
        end
        local stalled = INSPECT.watch("arrive")
        for _ = 1, TUNE.bootSteps do
            if TUNE.bootHook then TUNE.bootHook() end
            local obs = observeController()
            local state, why = controllerState(obs)
            if stalled(obs, state) then
                return nil, "parked on an unclassified wait (see the inspect snapshot)"
            end
            local ch = chapter()
            if ch ~= played and (state == "prep_main"
                    or (state == "player_map_idle" and inChapter(ch))) then
                if played == nil then
                    local sapi = INSPECT.sightApi()
                    INSPECT.Sight.seed(sapi, seed)
                end
                played = ch
                log(string.format("campaign: chapter %d starts (%s)", ch, state))
                return { chapter = ch }
            end
            if state == "world_map_idle" then
                local target = INSPECT.gameCalls(function(call)
                    return call(SYM.GetNextUnclearedNode, { SYM.gGMData })
                end)
                if target >= 0x80 then return nil, "the world map has no next story node" end
                local wm = obs.world_map
                local ok
                if wm.cursor_node ~= target then
                    ok = guardedInput("wm_next_node", "L", "the cursor moves to another open node",
                        function(after)
                            return after.world_map == nil or after.world_map.cursor_node ~= wm.cursor_node
                        end, 120)
                else
                    ok = guardedInput("wm_select", "A", "A on the story node walks or enters",
                        function(after) return controllerState(after) ~= "world_map_idle" end, 120)
                end
                if not ok then return nil, "the world map refused its input (see the trace)" end
            elseif state == "generic_menu" and game == "ours" then
                -- ch01's lead menu (ADR 0062): the campaign's `lord` row, else the highlighted lead.
                local picked, pwhy = INSPECT.pickLead(cfg.lord or "default", obs)
                if picked == nil then return nil, "lead menu: " .. pwhy end
                leadPicked = picked
            elseif state == "yes_no_choice" and leadPicked ~= nil then
                -- the pick's confirmation, "Will <lead> lead the party?"
                if not selectSemantic("answer_yes", "the lead prompt takes Yes", function(after)
                    return controllerState(after) ~= "yes_no_choice"
                end, 120) then
                    return nil, "the lead prompt refused Yes"
                end
                leadPicked = nil
            elseif state ~= "player_map_idle" then
                local advanced = advanceBootState(obs, state)
                if advanced == false then return nil, "a guarded input failed in " .. tostring(state) end
                if advanced == nil then
                    return nil, "unsupported state between chapters: " .. tostring(state or why)
                end
            else
                yield()
            end
        end
        return nil, "no chapter start within the boot allowance"
    end

    -- The chapter-start state, kept in memory for the restarts and written beside what the game
    -- gave (party, gold, items, the open shop nodes) under references/sim.
    api.save = function(ch)
        local st = emu:saveStateBuffer()
        states[ch] = st
        os.execute(string.format('mkdir -p "%s"', dir))
        local f = io.open(string.format("%s/%d.ss", dir, ch), "wb")
        if not f then return nil, "cannot write " .. dir end
        f:write(st)
        f:close()
        local party = {}
        for _, u in ipairs(units()) do
            local items = {}
            for _, it in ipairs(u.items) do items[#items + 1] = it.id end
            party[#party + 1] = { charId = u.charId, classId = u.classId, level = u.level, items = items }
        end
        f = io.open(string.format("%s/%d.json", dir, ch), "w")
        if not f then return nil, "cannot write " .. dir end
        f:write(Json.encode({ game = game, chapter = ch, gold = gold(), party = party,
                              shops = openNodes(ch) }))
        f:close()
        return true
    end
    api.load = function(ch)
        if not states[ch] then return nil, "no state for chapter " .. ch end
        emu:loadStateBuffer(states[ch])
        shops = nil
        wait(2)
        return true
    end

    -- The prep screen's cap, read off Pick Units itself (ProcPrepUnit.max_counter): opening it
    -- is the first half of the deploy, which follows at once. nil = no prep screen.
    api.cap = function()
        local state = controllerState()
        if state == "prep_main" then
            if not guardedInput("pick_units", "A", "Pick Units opens", function(after)
                return controllerState(after) ~= "prep_main"
            end, 120) then return nil end
            if not awaitControllerState("prep_pick_units", 900) then return nil end
        elseif state ~= "prep_pick_units" then
            return nil
        end
        return observeController().prep_units.cap
    end

    -- Pick exactly `ids` on Pick Units (bench the others first, so the cap is never in the way),
    -- then Fight!, then the first player phase.
    api.deploy = function(ids)
        local want = {}
        for _, c in ipairs(ids) do want[c] = true end
        local function moveTo(i)
            for _ = 1, 80 do
                local o = observeController()
                if controllerState(o) == "prep_pick_units" then
                    local c, cr, tr = o.prep_units.cursor, o.prep_units.cursor // 2, i // 2
                    if c == i then return true end
                    local intention, key
                    if c % 2 == 1 and i % 2 == 0 then intention, key = "pick_left", "LEFT"
                    elseif cr < tr then intention, key = "pick_next", "DOWN"
                    elseif cr > tr then intention, key = "pick_previous", "UP"
                    else intention, key = "pick_right", "RIGHT" end
                    if not guardedInput(intention, key, "the deploy cursor moves", function(after)
                        return after.prep_units ~= nil and after.prep_units.cursor ~= c
                    end, 60) then return false end
                else
                    yield()
                end
            end
            return false
        end
        local function fielded(addr) return (ru32(addr + 0x0C) & BOARD.US_NOT_DEPLOYED) == 0 end
        for pass = 1, 2 do
            for i = 0, ru32(SYM.gPrepUnitList + C.PREP_COUNT) - 1 do
                local addr = ru32(SYM.gPrepUnitList + i * 4)
                local should = want[ru8(ru32(addr) + 4)] == true
                if (pass == 1 and fielded(addr) and not should)
                    or (pass == 2 and not fielded(addr) and should) then
                    if not moveTo(i) then return nil, "the deploy cursor never reached row " .. i end
                    local was = fielded(addr)
                    if not guardedInput("toggle_deploy", "A", "the unit's deploy flips", function()
                        return fielded(addr) ~= was
                    end, 60) then
                        local pid = ru8(ru32(addr) + 4)
                        return nil, string.format("row %d (char 0x%02X, game says forced=%s) would not toggle",
                            i, pid, tostring(INSPECT.gameCalls(function(call)
                                return call(SYM.IsCharacterForceDeployed, { pid }) ~= 0
                            end)))
                    end
                end
            end
        end
        if not guardedInput("cancel_pick", "B", "Pick Units closes", function(after)
            return controllerState(after) ~= "prep_pick_units"
        end, 120) or not awaitControllerState("prep_main", 900) then
            return nil, "Pick Units never handed back the prep menu"
        end
        if not driveThroughPrep() then return nil, "Fight! did not leave the prep screen" end
        if not INSPECT.settle("idle", 9000, true) then return nil, "no player phase after Fight!" end
        return true
    end

    -- One purchase through the game's own shop screen: StartShopScreen(unit, the shop's stock,
    -- its type) as a kept call, then its list, prompts and exit by their keys. ORPHANED (no
    -- parent, PROC_TREE_3), as the game's own map shops start it (eventinfo.c,
    -- StartArmoryScreenOrphaned): the shop's first act is LockGame, and a locked game stops
    -- running tree 2, so a shop parented to the player phase froze itself (vanilla Ch5).
    api.buy = function(p)
        local s
        for _, e in ipairs(api.stock()) do if e.item == p.item then s = e end end
        local u = s and BOARD.find("blue", p.unit)
        if not u then return nil, string.format("no stock entry or unit for %d:%d", p.unit, p.item) end
        local row
        for i, it in ipairs(s.shop.items) do if it == p.item then row = i - 1 end end
        local startGold = gold()
        INSPECT.gameCalls(function(call)
            call(SYM.StartShopScreen, { u.addr, s.shop.list, C.SHOP_TYPE[s.shop.kind], 0 })
        end, true)
        local stalled = INSPECT.watch("shop")
        for _ = 1, C.shopSteps do
            local obs = observeController()
            local state = controllerState(obs)
            if stalled(obs, state) then return nil, "the shop stalled (see the inspect snapshot)" end
            local bought = gold() < startGold
            local ok = true
            if state == "player_map_idle" and not PROCS.find(SYM.gProcScr_Shop) then
                if bought then return true end
                return nil, "the shop closed before the purchase"
            elseif state == "dialogue_wait" then
                ok = INSPECT.advanceDialogue(120)
            elseif state == "yes_no_choice" then
                -- Before the purchase every prompt is a yes: Buy, the price, send to storage.
                -- After it, the greeting's B leaves.
                if bought then
                    ok = guardedInput("cancel_choice", "B", "the shop's prompt closes", function(after)
                        return controllerState(after) ~= "yes_no_choice"
                    end, 120)
                elseif obs.choice.current ~= "yes" then
                    ok = guardedInput("select_yes", "LEFT", "Yes is highlighted", function(after)
                        return after.choice ~= nil and after.choice.current == "yes"
                    end, 60)
                else
                    ok = guardedInput("answer_yes", "A", "the prompt takes Yes", function(after)
                        return controllerState(after) ~= "yes_no_choice"
                    end, 120)
                end
            elseif state == "shop_buy" then
                local c = obs.shop.cursor
                if bought then
                    ok = guardedInput("shop_leave", "B", "the list closes", function(after)
                        return controllerState(after) ~= "shop_buy"
                    end, 120)
                elseif c ~= row then
                    local down = c < row
                    ok = guardedInput(down and "shop_next" or "shop_previous", down and "DOWN" or "UP",
                        "the hand moves", function(after)
                            return after.shop ~= nil and after.shop.cursor ~= c
                        end, 60)
                else
                    ok = guardedInput("shop_buy", "A", "the price is asked", function(after)
                        return controllerState(after) ~= "shop_buy"
                    end, 120)
                end
            else
                yield()
            end
            if not ok then return nil, "the shop refused an input in " .. tostring(state) end
        end
        return nil, "the purchase did not finish within its allowance"
    end

    -- Spend a seal as the player does: the unit's Item command, the seal's row, Use. A branched
    -- promotion takes the first class the game's menu offers, and every prompt after it a yes;
    -- done when the unit's class has changed and the map is back.
    api.promote = function(entry)
        local slot
        for i, it in ipairs(entry.items) do
            if it.promotes then slot = i - 1; break end
        end
        local u = BOARD.find("blue", entry.charId)
        if not (slot and u) then return nil, "no seal or no unit for 0x" .. entry.charId end
        local function classOf() return ru8(ru32(u.addr + 4) + 4) end
        local before = classOf()
        if not moveUnit(u.x, u.y, u.x, u.y) then return nil, "no command menu for the unit" end
        local opened, why = INSPECT.itemSubmenu(slot)
        if not opened then return nil, why end
        if not selectSemantic("use_item", "Use starts the promotion", function(after)
            return controllerState(after) ~= "item_submenu"
        end, 120) then return nil, "the seal could not be used" end
        local stalled = INSPECT.watch("promote")
        for _ = 1, TUNE.bootSteps do
            local obs = observeController()
            local state = controllerState(obs)
            if stalled(obs, state) then return nil, "the promotion stalled (see the inspect snapshot)" end
            local ok = true
            if state == "player_map_idle" and classOf() ~= before then return true
            elseif state == "dialogue_wait" then ok = INSPECT.advanceDialogue(120)
            elseif state == "yes_no_choice" then
                ok = selectSemantic("answer_yes", "the promotion's prompt takes Yes", function(after)
                    return controllerState(after) ~= "yes_no_choice"
                end, 120)
            elseif state == "generic_menu" then
                ok = guardedInput("select_current_menu_item", "A", "the first class is chosen",
                    function(after) return controllerState(after) ~= "generic_menu" end, 120)
            else
                yield()
            end
            if not ok then return nil, "the promotion refused an input in " .. tostring(state) end
        end
        return nil, "the promotion did not finish within its allowance"
    end

    api.play = function(style, claims, attempt)
        local b = INSPECT.botApi(game)
        b.style, b.claims = style, claims
        b.info.campaign, b.info.attempt = id, attempt
        b.seed = function() end   -- seeded once, at the first chapter: FE8 never re-seeds
        pokeFastConfig()
        INSPECT.settle("phase", 6000, true)
        wait(60)
        local _, _, rec = Botrun.run(b)
        return rec
    end
    return api
end

-- bot: the bot plays one chapter, seeded by PT_SEED, styled by PT_STYLE (JSON), following
-- PT_CLAIMS (JSON, resolved). Ours: ch01 (reached as clear_ch01 reaches it). PT_VANILLA=1:
-- retail Ch1, reached by the bot playing the Prologue first (its record is emitted too). The
-- verdict is PASS for any finished run (won, lost, stuck): the record IS the result.
scenarios.bot = function()
    local Botrun = dofile(PLAYTEST_DIR .. "/botrun.lua")
    local function play(game)
        pokeFastConfig()
        INSPECT.settle("phase", 6000, true)
        wait(60)
        return Botrun.run(INSPECT.botApi(game))
    end
    if PLAYTEST_VANILLA == "1" then
        INSPECT.retailFastText()
        if not bootToMap(nil, 0) then return result("FAIL", "never reached the Prologue map") end
        local ok, why, rec = play("vanilla")
        if not ok or rec.outcome ~= "won" then
            return result("FAIL", "the bot did not win the Prologue on the way to Ch1: " .. why)
        end
        if not bootToMap(nil, 1) then return result("FAIL", "never reached Ch1's map") end
        ok, why, rec = play("vanilla")
        return result(ok and "PASS" or "FAIL", string.format("Ch1 %s: %s", rec.outcome, why))
    end
    if not reachCh01Map() then return end
    local ok, why, rec = play("ours")
    return result(ok and "PASS" or "FAIL", string.format("ch01 %s: %s", rec.outcome, why))
end

-- campaign: the bot plays chapter to chapter (campaign.lua), from New Game, restarting a chapter
-- from its start state until it clears with everyone alive. PT_SEED seeds the game's RNG once;
-- PT_CAMPAIGN is JSON (campaign_env.py builds it): { id, last = {chapter indices it ends after},
-- shops = { [chapter] = {world map nodes} } (ours: the twin's, from the vanilla campaign's
-- record), claims = { [chapter] = resolved claims }, from = a chapter index to resume at, from
-- the start state this id saved, attempt = k: only the k-th attempt from `from`'s start (the
-- pool, campaign.lua) }. Each chapter prints a `CAMPAIGN <json>` line and each
-- attempt its `BOTRUN <json>`. PASS = the campaign reached its end.
scenarios.campaign = function()
    local Campaign = dofile(PLAYTEST_DIR .. "/campaign.lua")
    if PLAYTEST_VANILLA == "1" then INSPECT.retailFastText() end
    local ok, why = Campaign.run(INSPECT.campaignApi(PLAYTEST_VANILLA == "1" and "vanilla" or "ours"))
    return result(ok and "PASS" or "FAIL", why)
end

-- sightprobe: what the sight reads at the chapter's start, printed for a check by eye against
-- the map (#510 step 9 PR D): the danger grid, the objective, the lead's reach, every enemy's
-- own strike on the lead (its AI's pick of weapon and tile), and one attack of ours in range.
-- Ours: ch01. PT_VANILLA=1: the retail Prologue, the first map New Game reaches (Ch1 is only
-- reached by playing it, which `bot` does).
scenarios.sightprobe = function()
    if PLAYTEST_VANILLA == "1" then
        INSPECT.retailFastText()
        if not bootToMap(nil, 0) then return result("FAIL", "never reached the Prologue map") end
    elseif not reachCh01Map() then return end
    INSPECT.settle("phase", 6000, true)
    local sapi = INSPECT.sightApi()
    local sight = INSPECT.Sight.new(sapi)
    local w, h = mapSize()
    for y = 0, h - 1 do
        local row = {}
        for x = 0, w - 1 do row[#row + 1] = tostring(sight.danger(x, y)) end
        log(string.format("danger y=%02d %s", y, table.concat(row, "")))
    end
    local o = sight.objective
    log(string.format("objective kind=%s tile=%s turnsLeft=%s", tostring(o.kind),
        o.tile and (o.tile.x .. "," .. o.tile.y) or "-", tostring(o.turnsLeft)))
    local lead = sight.fieldUnit()
    if not lead then return result("FAIL", "no blue unit on the field") end
    local reach = sight.reach(lead)
    local tiles = {}
    for _, t in ipairs(reach) do tiles[#tiles + 1] = t.x .. "," .. t.y end
    log(string.format("reach of 0x%02X at (%d,%d): %d tiles: %s", lead.charId, lead.x, lead.y,
        #reach, table.concat(tiles, " ")))
    -- Neither probed map fields an enemy with two weapons, so on retail the probe hands the boss
    -- a Steel Axe, a Silver Axe and a Hand Axe behind its own (constants/items.h 0x20, 0x21,
    -- 0x28; 20 uses): its AI's pick is then a real choice of weapon and tile.
    local board = BOARD.read()
    local boss = BOARD.liveBoss()
    if PLAYTEST_VANILLA == "1" and boss then
        for i, item in ipairs({ 0x20, 0x21, 0x28 }) do
            sapi.write16(boss.addr + 0x1E + i * 2, item | (20 << 8))
        end
        board = BOARD.read()
        sight.refresh()
    end
    -- Each enemy's strike, asked on the tile of the lead's reach nearest it that its own threat
    -- covers (else where the lead stands): an enemy that cannot strike there has no pick.
    local foe
    for _, e in ipairs(BOARD.live(board, "red")) do
        if e.onField then
            local covers, at, best = sight.threat(e), { x = lead.x, y = lead.y }, nil
            for _, t in ipairs(reach) do
                local d = BOARD.distance(t.x, t.y, e.x, e.y)
                if covers(t.x, t.y) > 0 and (not best or d < best) then at, best = t, d end
            end
            local g = sight.strike(lead, e, at.x, at.y)
            local items = {}
            for _, it in ipairs(e.items or {}) do
                items[#items + 1] = string.format("%02X", it.id)
            end
            log(string.format("strike 0x%02X@(%d,%d) on lead@(%d,%d) items=%s -> slot %s from %s: "
                .. "hit=%d dmg=%d crit=%d hits=%d", e.charId, e.x, e.y, at.x, at.y,
                table.concat(items, ","), tostring(g.takenSlot),
                g.takenTile and (g.takenTile.x .. "," .. g.takenTile.y) or "-",
                g.takenHit, g.takenDmg, g.takenCrit, g.takenHits))
            if e.isBoss or not foe then foe = e end
        end
    end
    if not foe then return result("FAIL", "no enemy on the field") end
    -- One attack of ours where it is in range, with the enemy's counter to it.
    local r = sight.range(lead)
    for _, t in ipairs(reach) do
        local d = BOARD.distance(t.x, t.y, foe.x, foe.y)
        if r and d >= r.min and d <= r.max then
            local g = sight.attack(lead, foe, t.x, t.y, nil)
            log(string.format("attack 0x%02X from (%d,%d) on 0x%02X: hit=%d dmg=%d crit=%d hits=%d "
                .. "kills=%s | counter hit=%d dmg=%d crit=%d hits=%d (counters=%s)", lead.charId,
                t.x, t.y, foe.charId, g.hit, g.dmg, g.crit, g.hits, tostring(g.killsTarget),
                g.counterHit, g.counterDmg, g.counterCrit, g.counterHits, tostring(g.counters)))
            break
        end
    end
    log(string.format("canSeize 0x%02X = %s", lead.charId, tostring(sight.canSeize(lead))))
    return result("PASS", "sight read; check the log by eye against the map")
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
    local startFrame = emu:currentFrame()
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
        -- A random Suspend can legitimately leave the battle map. That is a clean fuzz terminal;
        -- never inject recovery inputs into an unrelated UI state.
        if not liveOnMap() then
            shot("fuzz-left-map")
            return result("PASS", string.format(
                "left the battle map cleanly on seed %d, no crash/soft-lock", seed))
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
-- -- those fail closed before any later order or phase input. Timeout / malformed
-- response -> FAIL, like every brick.
local JSONF = dofile(PLAYTEST_DIR .. "/json.lua")
local LLMDIR = (type(PLAYTEST_LLMDIR) == "string" and PLAYTEST_LLMDIR) or "/tmp/playtest-llm-handshake"

-- Exported unit ids must be UNIQUE and stable across the run, so both factions use the
-- ARRAY SLOT: blue = slot, red = 1000+slot. A charId is not unique -- generics share one, and
-- over all 62 blue slots a recruited generic can repeat one too.
local LLM_RED_ID_BASE = 1000

local function llmExportBoard(objective, maxx, maxy)
    -- One board.lua snapshot: selecting a unit for its reach and cancelling changes nothing
    -- on the board. Off-field units (off the map, hidden, carried, undeployed) are left out --
    -- there is no tile to select or to attack.
    local board, units = BOARD.read(), {}
    for _, u in ipairs(BOARD.live(board, "blue")) do
        if u.onField then
            local canAct = not u.acted
            local reach = {}
            if canAct then
                local r = selectAndReach(u, maxx, maxy)
                if not r then return nil, "controller could not enumerate live movement" end
                if not guardedInput("cancel_selection", "B",
                    "board export returns movement selection to player map", function(after)
                        return controllerState(after) == "player_map_idle"
                    end, 120) then return nil, "controller could not close movement selection" end
                for _, t in ipairs(r) do reach[#reach + 1] = { t.x, t.y } end
            end
            units[#units + 1] = {
                id = u.slot, faction = "blue", x = u.x, y = u.y,
                hp = u.hp, maxhp = u.maxhp, can_act = canAct,
                boss = false, reach = reach,
                range = u.minRange and { u.minRange, u.maxRange } or nil,
            }
        end
    end
    for _, u in ipairs(BOARD.live(board, "red")) do
        if u.onField then
            units[#units + 1] = {
                id = LLM_RED_ID_BASE + u.slot, faction = "red", x = u.x, y = u.y,
                hp = u.hp, maxhp = u.maxhp, can_act = false,
                boss = u.isBoss, reach = {},
                range = u.minRange and { u.minRange, u.maxRange } or nil,
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

-- Resolve an exported unit id back to a live unit: blue = slot, red = 1000+slot (see
-- llmExportBoard).
local function llmUnitById(id)
    if type(id) ~= "number" or id < 0 or id ~= math.floor(id) then return nil end
    if id >= LLM_RED_ID_BASE then return unitAt(SYM.gUnitArrayRed, id - LLM_RED_ID_BASE) end
    if id >= 62 then return nil end
    return unitAt(SYM.gUnitArrayBlue, id)
end

-- Execute one validated order with the existing primitives. M2 limitation (noted in
-- decisions.md): chooseAttack fires on the UI's default target, which is the intended
-- one whenever a single enemy is in range of the strike tile; multi-target
-- disambiguation is an M3 refinement.
local function llmExecOrder(o)
    local function reject(why)
        traceFailure("llm_order", "sidecar order remains legal in the live FE8 state",
            "fail:" .. why, nil, "controller-llm-order-rejected")
        return false
    end
    if type(o.unit) ~= "number" or type(o.move_to) ~= "table" then
        return reject("malformed-order")
    end
    local u = o.unit < LLM_RED_ID_BASE and llmUnitById(o.unit) or nil
    if not u or isDead(u) or (u.state & 0x2) ~= 0 then return reject("unit-cannot-act") end
    -- the sidecar validated against the REQUEST board; re-check what can have changed
    -- since (an earlier order killed the target) before any UI input. With no live
    -- target the order is rejected rather than replaced by an unrelated action.
    local action = o.action
    if action == "attack" then
        local tgt = llmUnitById(o.target)
        if not tgt or isDead(tgt) then return reject("attack-target-not-live") end
    elseif action ~= "seize" and action ~= "wait" then
        return reject("unsupported-action-" .. tostring(action))
    end
    if not moveUnit(u.x, u.y, o.move_to.x, o.move_to.y) then return false end
    if action == "attack" then
        if not chooseAttack(u.addr) then return false end
    elseif action == "seize" then
        local actions = Controller.legalActions(observeController())
        if not Controller.findAction(actions, "seize") then
            return reject("seize-not-legal")
        end
        if not selectSemantic("seize", "Seize starts the chapter win event", function()
            return procActive(SYM.ProcScr_StdEventEngine) or chapter() ~= HOST_CHAPTER
        end, 900) then return false end
    elseif action == "wait" then
        if not chooseWait() then return false end
    end
    if menuOpen() then
        traceFailure("llm_order", "committed order closes its live menu",
            "fail:menu-remained-open", nil, "controller-llm-menu-open")
        return false
    end
    return true
end

-- The LLM-commander loop body (no verdict): per player phase export the board, ask the
-- sidecar, execute the orders, end the turn. Same terminal detection as the clear-bot.
local function llmUntilAdvance(startChapter, objective, maxx, maxy, park)
    local function won() return chapter() ~= startChapter end
    local lost = INSPECT.chapterLost
    local budgetTurns = 18
    local seed = math.floor(tonumber(PLAYTEST_SEED) or 1)
    local n = 0
    for t = 1, budgetTurns do
        INSPECT.settle("phase", 6000, true)
        wait(60)              -- let the player-phase banner finish (it eats key presses)
        if not awaitControllerState("player_map_idle", 300) then return "controller state", t end
        n = n + 1
        local board, exportWhy = llmExportBoard(objective, maxx, maxy)
        if not board then return "controller export: " .. exportWhy, t end
        local req = { seed = seed, chapter = startChapter, turn = turn(), faction = "blue",
                      board = board }
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
                return "controller order: " .. tostring(controllerFault or "rejected"), t
            end
        end
        if won() then return "won", t end
        if lost() then return "gameover", t end
        local phase = runEnemyPhase(park)
        if phase == "gameover" then return "gameover", t end
        if phase ~= "player" then return "controller phase", t end
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

-- The ch01 chief-march (#531 audit 7): frail the chief, then each player phase frail+harmless
-- the escort, attack the chief if the lord is adjacent else march toward the seize tile, and once
-- the chief is down hand the seize to `opts.onSeize`. Its two callers (ch01win,
-- seizeCh01ToCh02) differ in HOW they sync, how strictly they treat a failed input and what
-- the seize does, so those are parameters, never unified:
--   sync(t)             -> nil to go on, or a status string to return (the per-turn sync)
--   onTurn(t)           optional, after the banner wait, before the pokes (logging)
--   onAttack()          optional, between the in-place move and chooseAttack
--   onMarch(moved)      optional, after marchToward
--   onSeize(lord, goal) -> nil to fall through to the enemy phase, or a status to return
--   startLog            optional format taking the chief's x, y
--   lordId              the unit that marches (required: the caller names it, from CAMPAIGN.CAST)
--   strict              a failed move/attack/march or a non-"player" phase ends "controller"
-- Returns "noboss" | "dead" | "gameover" | "controller" | "timeout" | a status from sync/onSeize.
function INSPECT.ch01MarchOnChief(opts)
    assert(opts.lordId, "INSPECT.ch01MarchOnChief: opts.lordId is required")
    local chief = red(CAMPAIGN.CH01_CHIEF)
    if not chief then return "noboss" end
    local goal = { x = chief.x, y = chief.y } -- chief holds the seize tile
    pokeFrail(chief)
    if opts.startLog then log(string.format(opts.startLog, goal.x, goal.y)) end
    for t = 1, 18 do
        local early = opts.sync(t)
        if early then return early end
        wait(100) -- let the PLAYER PHASE banner finish (it eats key presses)
        if opts.onTurn then opts.onTurn(t) end
        -- every other goblin dies to the first counter (frail) and deals no damage
        -- (harmless): the escort can't kill anyone OR bodyblock the trail for long.
        for _, r in BOARD.each("red") do
            if r.charId ~= CAMPAIGN.CH01_CHIEF and not isDead(r) then
                pokeFrail(r)
                pokeHarmless(r)
            end
        end
        local lord = blue(opts.lordId)
        if isDead(lord) then return "dead" end
        chief = red(CAMPAIGN.CH01_CHIEF)
        if chief and not isDead(chief) then
            if BOARD.distance(lord.x, lord.y, chief.x, chief.y) == 1 then
                -- adjacent: attack in place (move onto own tile opens the menu)
                if moveUnit(lord.x, lord.y, lord.x, lord.y) then
                    if opts.onAttack then opts.onAttack() end
                    if not chooseAttack(lord.addr) and opts.strict then return "controller" end
                elseif opts.strict then
                    return "controller"
                end
            else
                local mw, mh = mapSize()
                local moved = marchToward(lord, goal.x, goal.y + 1, mw - 1, mh - 1)
                if opts.onMarch then opts.onMarch(moved) end
                if not moved and opts.strict then return "controller" end
            end
        else
            local status = opts.onSeize(lord, goal)
            if status then return status end
        end
        local phase = runEnemyPhase(CH01_PARK)
        if phase == "gameover" then return "gameover" end
        if opts.strict and phase ~= "player" then return "controller" end
    end
    return "timeout"
end

-- CH01WIN: the default lord (blind A-taps pick Braulo) marches on the camp,
-- kills the chief, and SEIZES -- in-game proof of the lord-gated Seize
-- (CanUnitSeize hook, #42) and the win hand-off (Seize macro -> EVFLAG_WIN ->
-- ending scene -> MNC2 into the hosted ch02). (CH01_PARK is defined up by the
-- clear-bot.)
scenarios.ch01win = function()
    -- Reaching the ch01 map is the SHARED semantic path (#238). This used to be 33 lines
    -- of blind cadence -- an A-tap loop over the save prompt, the Beat-1 Northlook scene,
    -- the lord prompt and the lord menu, then a B/START/A flail at Preparations. It
    -- passed, but for the wrong reason: it mashed straight through the lord-select Yes/No
    -- prompt that #232 spent three sessions on, verifying none of it. reachCh01Map drives
    -- the same route on observed state and verified postconditions, so a state nothing can
    -- classify now FAILS here instead of being papered over.
    if not reachCh01Map() then return end
    pokeFastConfig() -- 10-goblin enemy phases: map combat + fast speed
    local status = INSPECT.ch01MarchOnChief{
        lordId = CAMPAIGN.CAST.braulo,
        startLog = "chief frail on the seize tile (%d,%d); marching Braulo",
        sync = function()
            -- sync to the player phase; the A-taps also clear stray textboxes
            -- (road-sign AREA event, defeat quotes)
            INSPECT.settle("phase", 6000, true)
        end,
        onTurn = function(t)
            local b0 = blue(0x01)
            log(string.format("loop %d: turn=%d faction=0x%02X braulo=(%d,%d) chiefdead=%s",
                t, turn(), faction(), b0 and b0.x or -1, b0 and b0.y or -1,
                tostring(isDead(red(CAMPAIGN.CH01_CHIEF)))))
        end,
        onAttack = function() shot("ch01win-attack-chief") end,
        onMarch = function(moved)
            local b0 = blue(0x01)
            log(string.format("  march -> %s, braulo=(%d,%d)", tostring(moved), b0.x, b0.y))
        end,
        onSeize = function(braulo, goal)
            -- chief down: Braulo onto the seize tile, then Seize by its semantic id.
            -- `press(K.A)` used to stand in for this on the assumption that Seize tops
            -- the menu -- a guess about menu ORDER, which is exactly the class of thing
            -- the controller reads from the live menu instead (#238).
            if moveUnit(braulo.x, braulo.y, goal.x, goal.y) then
                shot("ch01win-seize-menu")
                selectSemantic("seize", "Seize starts the chapter win event", function()
                    return procActive(SYM.ProcScr_StdEventEngine) or chapter() ~= 2
                end, 900)
            end
            -- generous budget: post-seize plays the full ending cutscene before
            -- MNC2 chains into the hosted ch02 (longer than the old 3600).
            local won = waitFor(function()
                return chapter() ~= 2 or procActive(SYM.gProcScr_TitleScreen)
            end, 9000, true)
            shot("ch01win-after-seize")
            if won then return "won" end
            -- The seize did not end the chapter, so back out to the map on ENUMERATED
            -- cancels and retry next turn (#238). Two blind B's used to stand in for this:
            -- they could not tell how many levels deep the surprise was, so one too few left
            -- the run parked on a menu and one too many cancelled the unit selection as well.
            if not cancelToPlayerMap() then return "stuck" end
        end,
    }
    if status == "noboss" then return result("FAIL", "chief not in the red array") end
    if status == "dead" then return result("FAIL", "Braulo died on the march") end
    if status == "won" then
        return result("PASS", "Braulo seized the camp; ending + dev placeholder played -> title")
    end
    if status == "stuck" then return result("FAIL", "could not back out of the post-seize screen") end
    if status == "gameover" then return result("FAIL", "unexpected game over in the win run") end
    shot("ch01win-timeout")
    result("FAIL", "could not seize the camp in 14 turns")
end

-- ---- CHECKPOINTS (#21): build a slow scene's lead-up ONCE at top speed (ckpt_*), then
-- run just the scene off the save state. run.sh orchestrates: it runs the ckpt_* builder at
-- 240fps if the state is missing/stale, then the scenario that loads it. The lead-up drivers
-- are shared here so the checkpoint and a from-scratch run stay in lock-step.

-- Drive ch00 win -> ch01 prep screen OPEN, picking the LAST lord candidate (Pinky, not the
-- default Braulo) so the convoy/force-deploy lord-select fixes can be exercised for a
-- NON-Braulo lord. The walk to the last row counts the LIVE menu instead of the
-- LORD_CANDIDATES constant -- the old copy would silently pick the wrong lord the day the
-- roster changed.
local function reachPrepPinky() return reachCh01({ stopAtPrep = true, lord = "last" }) end

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
-- floor bakes in exactly ONCE -- +10 maxHP / +4 def at ch01 turn 1 -- and does NOT re-apply
-- on later player phases. ch02 isn't a playable map yet, so the within-chapter multi-phase
-- stability + the permanent applied-flag (0xFA) stand in for "carries into ch02 with no
-- double-apply": both ride the identical BmMain_StartPhase -> LordFloor_ApplyOnce
-- early-return once the flag is set. make-green can't prove this -- only a real run can.
scenarios.lordfloor = function()
    local MARTY = 0x02                 -- marty rides CHARACTER_SETH
    local MARTY_ROW = 1                -- ...at row 1 of the lead menu (row 0 is Braulo)
    local BASE_HP, FLOOR_HP = 18, 28   -- base maxHP 18, floor +10 (inject.chapters.ch01.lord_floor_rows;
                                       -- +7 until ch01's goblins took vanilla's levels, ADR 0373)
    local BASE_DEF, FLOOR_DEF = 2, 6   -- base def 2, floor +4
    local APPLIED = 0xFA               -- LORDFLOOR_APPLIED_FLAG (permanent)
    local FOUNDING_EXP = 72            -- exp_curve.founding_grant()['marty'] (#430 step 4)
    local FOUNDING_APPLIED = 0xFB      -- FOUNDING_EXP_FLAG (engine patch 0015)

    -- Ride the shared, migrated ch01 route and take MARTY as the lead: the save menu, the
    -- Northlook scene, the lead menu, its Yes/No confirm and Preparations are all driven on
    -- observed state (#238). This scenario used to carry its own blind-A copy of that route,
    -- which could not tell a swallowed input from an advanced scene -- and which would have
    -- ridden straight through the lord-select prompt exactly as ch01win did.
    local route = { lord = MARTY_ROW }
    if not reachCh01(route) then return end
    if route.picked ~= MARTY_ROW then
        return result("FAIL", string.format("lead committed on row %s, not Marty's row %d",
            tostring(route.picked), MARTY_ROW)) end
    wait(60)

    -- marty must be force-deployed (the chosen lord) and floored at turn 1.
    local marty = blue(MARTY)
    if not marty then return result("FAIL", "marty (chosen lord) not on the field at ch01 t1") end
    local hp1, df1 = ru8(marty.addr + 0x12), ru8(marty.addr + 0x17)
    shot("lordfloor-t1")
    -- DIAGNOSTIC (#45 3c debug): dump pick flags + marty stats + applied flag at t1.
    local pickset = "none"
    for i = 0, CAMPAIGN.LORD_CANDIDATES - 1 do
        if eventFlag(CAMPAIGN.LORDSEL_FLAG_BASE + i) then pickset = string.format("0x%X (idx %d)", CAMPAIGN.LORDSEL_FLAG_BASE + i, i) end
    end
    log(string.format("t%d: pick flag set=%s; marty maxHP=%d def=%d; applied(0xFA)=%s",
        turn(), pickset, hp1, df1, tostring(eventFlag(APPLIED))))
    if not eventFlag(APPLIED) then
        return result("FAIL", string.format("applied flag 0x%X clear at ch01 t1 -- floor not "
            .. "baked in by player-phase start (maxHP=%d, want %d)", APPLIED, hp1, FLOOR_HP)) end
    if hp1 ~= FLOOR_HP then
        return result("FAIL", string.format(
            "marty maxHP=%d at ch01 t1, want %d (base %d +%d floor)", hp1, FLOOR_HP, BASE_HP,
            FLOOR_HP - BASE_HP)) end
    if df1 ~= FLOOR_DEF then
        return result("FAIL", string.format(
            "marty def=%d at ch01 t1, want %d (base %d +4 floor)", df1, FLOOR_DEF, BASE_DEF)) end
    -- the founding party carries the prologue's pay into ch01 (engine patch 0015)
    local exp1 = ru8(marty.addr + 0x09)
    if not eventFlag(FOUNDING_APPLIED) or exp1 ~= FOUNDING_EXP then
        return result("FAIL", string.format("marty exp=%d at ch01 t1 (flag 0x%X %s), want %d "
            .. "-- the founding grant did not land", exp1, FOUNDING_APPLIED,
            tostring(eventFlag(FOUNDING_APPLIED)), FOUNDING_EXP)) end

    -- advance two player phases; the floor must NOT stack (flag-gated apply-once = the same
    -- early-return that protects the carry into ch02). Enemies poked harmless so marty lives.
    for _ = 1, 2 do
        for _, r in BOARD.each("red") do
            if not isDead(r) then pokeHarmless(r) end
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
        "marty floored ONCE: maxHP %d->%d (+%d), def %d->%d (+%d), flag 0x%X set at t1, stable "
        .. "across 3 player phases", BASE_HP, FLOOR_HP, FLOOR_HP - BASE_HP, BASE_DEF, FLOOR_DEF,
        FLOOR_DEF - BASE_DEF, APPLIED))
end

-- RECORDSUPPLY (#2/#3): with PINKY as lord, bench Braulo + deploy 3 non-Braulo in prep,
-- then on the map have Pinky (the chosen lord) open the convoy via the Supply command --
-- the cross-character behavioural proof that force-deploy + supply follow the chosen lead.
local US_NOT_DEPLOYED = 0x08
local function isDeployedInPrep(charId)
    local u = blue(charId)
    return u and (u.state & US_NOT_DEPLOYED) == 0
end
local function countDeployedPrep()
    local n = 0
    for _, u in BOARD.each("blue") do
        if u.charId ~= 0 and (u.state & US_NOT_DEPLOYED) == 0 then n = n + 1 end
    end
    return n
end
scenarios.recordsupply = function()
    wait(30)
    if not loadState("lordpinky") then return result("FAIL", "no lordpinky checkpoint (run.sh builds it)") end
    wait(60)
    shot("supply")                                        -- prep main, Pinky as lord
    -- Enter Pick Units through the live prep command, not a bare A on the top row (#238).
    if not awaitControllerState("prep_main", 600) then
        shot("supply-no-prep"); return result("FAIL", "the prep main menu never took input") end
    if not selectSemantic("pick_units", "the Pick Units deploy screen opens", function(after)
        return after.procs.prep_units ~= nil
    end, 300) then
        shot("supply-no-pickunits")
        return result("FAIL", "Pick Units screen never opened")
    end
    if not awaitControllerState("prep_pick_units", 600) then
        return result("FAIL", "the deploy list never reached its key handler") end
    shot("supply")
    -- The deploy list is a TWO-COLUMN grid and the cursor starts on the lead (index 0):
    --   0 Pinky | 1 Braulo / 2 Marty | 3 Wolfram / 4 Mees | 5 RBG / 6 Rootis | 7 Sclorbo
    -- Bench Braulo (index 1): step RIGHT to him, then toggle only if he is deployed.
    --
    -- Every one of these moves used to be a blind press against that map of the roster. The
    -- moves are now enumerated from the LIVE list -- the controller mirrors
    -- ProcPrepUnit_Idle's own bounds -- so a RIGHT or DOWN that FE8 would refuse is not
    -- offered at all, instead of silently leaving the cursor where it was and toggling
    -- whoever happened to be under it.
    local function pickStep(intention, key, where)
        local at = observeController().prep_units
        if not at then return false end
        -- SETTLED, not merely moved: ProcPrepUnit_Idle reads no keys while the list scrolls,
        -- so returning on the cursor alone leaves the next guarded input to race the scroll
        -- and fail its own legality pre-check. That it works today rests on press() costing
        -- more frames than a 16px scroll at scroll_val=4 -- which holding L (8) or a roster
        -- long enough to make ShouldPrepUnitMenuScroll true would take away.
        return guardedInput(intention, key, "the deploy cursor moves " .. where, function(after)
            return after.prep_units ~= nil and after.prep_units.cursor ~= at.cursor
                and after.prep_units.settled
        end, 60)
    end
    if not pickStep("pick_right", "RIGHT", "onto the second column") then
        return result("FAIL", "could not step the deploy cursor onto Braulo's column") end
    if isDeployedInPrep(CAMPAIGN.CAST.braulo) then
        local before = countDeployedPrep()
        if not guardedInput("toggle_deploy", "A", "Braulo leaves the deployed count", function()
            return not isDeployedInPrep(CAMPAIGN.CAST.braulo) and countDeployedPrep() < before
        end, 120) then return result("FAIL", "could not bench Braulo") end
    end
    shot("supply")
    -- Top up to 4 with non-Braulo units: walk down the second column (RBG at 5, Sclorbo at 7)
    -- and deploy the benched ones until the cap is full.
    for _ = 1, 2 do
        if countDeployedPrep() >= 4 then break end
        for _ = 1, 2 do
            if not pickStep("pick_next", "DOWN", "down a row") then
                return result("FAIL", "could not walk the deploy list down a row") end
        end
        local before = countDeployedPrep()
        if not guardedInput("toggle_deploy", "A", "the deployed count rises", function()
            return countDeployedPrep() > before
        end, 120) then return result("FAIL", "could not deploy the benched unit under the cursor") end
        shot("supply")
    end
    log(string.format("prep: brauloDeployed=%s deployedCount=%d",
        tostring(isDeployedInPrep(CAMPAIGN.CAST.braulo)), countDeployedPrep()))
    -- Launch straight from Pick Units. START is a legal action here only because someone is
    -- deployed -- on an empty field FE8 just buzzes, and the old blind START could not tell
    -- that apart from a launch, so it went on to A-mash at a screen that had not moved.
    -- guardedInput, not selectSemantic: selectSemantic navigates a menu to reach a row and
    -- then presses A, and Fight is a START action with no row to walk to (it reported
    -- fail:no-live-target). driveThroughPrep drives the main prep menu's Fight the same way.
    if not guardedInput("fight", "START", "Pick Units launches the chapter", function(after)
        return after.procs.prep_units == nil
    end, 600) then
        shot("supply-no-launch")
        return result("FAIL", "START did not launch the chapter from Pick Units")
    end
    if not awaitControllerState("player_map_idle", 900) then
        shot("supply-no-map")
        return result("FAIL", "never reached the player-phase map")
    end
    if not waitFor(function()
        return faction() == 0 and turn() >= 1
            and not procActive(SYM.gProcScr_SALLYCURSOR)
    end, 1200) then
        shot("supply-no-map")
        return result("FAIL", "the map came up but turn 1 never began")
    end
    wait(120); shot("supply")                             -- the deployed field
    -- Map-side assertions: Braulo benched (not on field), Pinky deployed, exactly 4 out.
    local braulo = blue(CAMPAIGN.CAST.braulo)
    local braOnField = braulo and (braulo.state & 0x9) == 0 and braulo.onMap
    local pinky = blue(CAMPAIGN.CAST.pinky)
    local pinkyOnField = pinky and (pinky.state & 0x9) == 0 and pinky.onMap
    local onField = 0
    for _, u in BOARD.each("blue") do
        if (u.state & 0x9) == 0 and u.onMap then onField = onField + 1 end
    end
    log(string.format("map: braulo=%s pinky=%s field=%d",
        tostring(braOnField), tostring(pinkyOnField), onField))
    if braOnField then return result("FAIL", "Braulo is on the field (should be benched)") end
    if not pinkyOnField then return result("FAIL", "Pinky (lord) not deployed") end
    -- Open Pinky's action menu (select + no-move) and screenshot it to find the Supply row.
    INSPECT.settle("phase", 3000, true)
    wait(60)
    local usedSupply = false
    pinky = blue(CAMPAIGN.CAST.pinky)
    if moveUnit(pinky.x, pinky.y, pinky.x, pinky.y) then
        wait(40); shot("supply")                          -- Pinky's menu: Rescue/Item/Trade/Supply/Wait
        -- Resolve the live Supply command. Three blind DOWNs used to walk to "row 3 (Rescue0
        -- Item1 Trade2 Supply3 Wait4)" -- a claim about which of Rescue and Trade happen to
        -- be available, both of which depend on who is standing next to Pinky. Park an ally
        -- beside her and the walk lands on Wait, the run opens no convoy, and the failure
        -- reads as "Supply is broken" (#238).
        usedSupply = selectSemantic("open_supply", "Supply opens the convoy screen", function(after)
            return controllerState(after) == "supply_screen"
        end, 300)
        shot("supply")                                    -- the convoy screen -> Pinky USING Supply
        log("pinky opened convoy=" .. tostring(usedSupply))
        if usedSupply then
            -- Leave the convoy on its own enumerated cancel. Two blind B's stood in for this,
            -- and the second had nothing to close: SupplyCommandEffect returns MENU_ACT_END,
            -- so the unit menu is already gone by the time the convoy is up -- that press went
            -- into the map. The postcondition is the convoy PROC being gone, not merely the
            -- state changing: its key handler lets go while the screen is still fading out.
            if not guardedInput("close_supply", "B", "the convoy screen closes", function(after)
                return after.procs.supply_screen == nil
            end, 600) then return result("FAIL", "could not leave the convoy screen") end
            if not awaitControllerState("player_map_idle", 600) then
                return result("FAIL", "the map never came back after the convoy")
            end
        end
    else
        shot("supply-no-menu")
    end
    -- Contrast: a deployed unit that is neither the lead nor STANDING NEXT TO them has no
    -- Supply row. The adjacency clause is not a detail -- SupplyUsability (bmmenu.c) returns
    -- MENU_ENABLED for the lead OR for anyone IsAdjacentForSupply finds orthogonally beside
    -- them, so "a non-lord has no Supply" is simply false for a neighbour, and asserting it
    -- fails on a correct engine. This scenario's own comment claimed the stronger rule; the
    -- first deployed non-lord turned out to spawn right next to Pinky, and the assertion
    -- caught the CLAIM rather than a defect (#238).
    INSPECT.settle("phase", 1500, true)
    pinky = blue(CAMPAIGN.CAST.pinky)
    for _, u in BOARD.each("blue") do
        local beside = pinky and BOARD.distance(u.x, u.y, pinky.x, pinky.y) == 1
        -- onField: this loop MOVES the unit, and a rescued one is not standing on a tile.
        if u.charId ~= CAMPAIGN.CAST.pinky and not beside and u.onField then
            if moveUnit(u.x, u.y, u.x, u.y) then
                wait(40); shot("supply")
                -- The CONTRAST is the point of this half, so assert it rather than leaving
                -- it to the screenshot: a non-lord's live command menu must offer no Supply
                -- at all. The old code just backed out on two blind B's and asserted nothing.
                -- Assert the STATE first. legalActions returns nil when classify finds no
                -- state, and findAction(nil, ...) is nil -- so without this, a fade, a menu
                -- that never opened, or any state we cannot name reads as "Supply correctly
                -- absent" and the scenario passes. That is green-for-the-wrong-reason inside
                -- the assertion added to stop green-for-the-wrong-reason.
                local menu = observeController()
                if controllerState(menu) ~= "unit_command_menu" then
                    return result("FAIL", string.format(
                        "expected a live command menu for char 0x%02X, got %s",
                        u.charId, tostring(controllerState(menu))))
                end
                if Controller.findAction(Controller.legalActions(menu), "open_supply") then
                    return result("FAIL", string.format(
                        "char 0x%02X is neither the lead nor beside them, but was offered Supply",
                        u.charId))
                end
                if not cancelToPlayerMap() then
                    return result("FAIL", "could not back out of the non-lord's command menu")
                end
            end
            break
        end
    end
    if not usedSupply then
        return result("FAIL", "Pinky (lord) could not open the convoy via Supply")
    end
    result("PASS", string.format(
        "Braulo benched (field=%d, no Braulo); Pinky the chosen lord opened the convoy via Supply", onField))
end

-- CH01LORD (#42): pick the LAST lord candidate -- benched by default under the
-- 4-slot deploy cap -- and assert the choice is real: the permanent flag is
-- set, the pick is force-deployed onto the field (cap intact), and their death
-- ends in the game-over screen (UnitKill hook -> EVFLAG_GAMEOVER -> AFEV).
scenarios.ch01lord = function()
    -- The shared migrated route takes the LAST lead candidate and asserts where the walk
    -- landed, so "which lead did we actually pick" is verified rather than assumed (#238).
    -- The lead menu is a StartMenu(MenuDef_LordSelect) over a scenic BG (BG_DARKLING_WOODS)
    -- BEFORE the battle map loads -- so the chief is NOT in the red array during it, and the
    -- classifier sees it as a generic_menu (every enabled row carries an on_selected).
    local route = { lord = "last" }
    if not reachCh01(route) then return end
    shot("ch01lord-map")
    -- The permanent flag is indexed off the row the route REPORTS committing on, not off
    -- LORD_CANDIDATES: a constant that outlives a roster change asserts the wrong flag and
    -- the scenario's whole premise goes unchecked.
    if not eventFlag(CAMPAIGN.LORDSEL_FLAG_BASE + route.picked) then
        return result("FAIL", string.format(
            "lord-choice permanent flag 0x%X (row %d) not set after confirm",
            CAMPAIGN.LORDSEL_FLAG_BASE + route.picked, route.picked))
    end
    local lord = blue(CAMPAIGN.CAST.pinky)
    if not lord or (lord.state & 0x9) ~= 0 or not lord.onMap then
        return result("FAIL", "chosen lord (char 0x08) is not force-deployed")
    end
    local deployed = 0
    for _, u in BOARD.each("blue") do
        if (u.state & 0x9) == 0 and u.onMap then deployed = deployed + 1 end
    end
    if deployed ~= 4 then
        return result("FAIL", string.format(
            "deploy cap broken with forced lord: %d on the field (want 4)", deployed))
    end
    log(string.format("chosen lord fielded at (%d,%d), deployed=%d; feeding them to the goblins",
        lord.x, lord.y, deployed))
    pokeFrail(lord)
    for t = 1, 8 do
        lord = blue(CAMPAIGN.CAST.pinky)
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
        tostring(eventFlag(CAMPAIGN.LORDSEL_FLAG_BASE + route.picked)),
        tostring(isDead(blue(CAMPAIGN.CAST.pinky)))))
    if isDead(blue(CAMPAIGN.CAST.pinky)) then
        return result("FAIL", "chosen lord died but NO game over followed")
    end
    result("FAIL", "could not get the chosen lord killed in 8 turns")
end

-- MAPSHOT: boot to the map and screenshot the deployed field -- the generic "see the
-- units on the map" chapter load-test (any hosted chapter reachable from New Game, e.g.
-- a --ch03-boot fast-boot ROM). bootToMap already shoots "map-loaded"; add a few settle
-- frames for a clean capture. Reusable smoke-look for every new chapter host.
scenarios.mapshot = function()
    if not bootToMap() then return result("FAIL", "never reached the map") end
    -- SETTLE BEFORE READING THE ROSTER. bootToMap returns on player_map_idle, which can be
    -- true while the chapter's beginning script is still running -- and on a chapter whose
    -- opening is a bare LOMA/LOAD/prep spine there is almost nothing between the Fight press
    -- and that state. INSPECT.units walks gUnitArrayBlue directly, so reading it there
    -- reports the party PREP has not finished redeploying yet: ch06 dumped 2 of 10 while its
    -- own screenshots, 120 frames later, showed the lord standing on the map. That is a
    -- diagnostic that lies, and the runbook tells people to trust this dump over a screenshot
    -- ("verify placement from INSPECT.units, never from a screenshot"), so it has to be true.
    INSPECT.settle("battle", 900, true)
    INSPECT.units("mapshot")
    for i = 1, 6 do
        wait(20)
        shot(string.format("mapshot-%02d-ch%d-turn%d", i, chapter(), turn()))
    end
    return result("PASS", "map deployed; screenshots taken")
end

-- TITLECARD: open the map menu -> Status screen, which decompresses the
-- chapter title card (chap_title_data[chapTitleId]) -- the artifact screenshot
-- is how a recomposed title gets eyeballed without a manual run. Pinned to the canonical ROM;
-- a chapter whose card is new binds it to the build that hosts it (`lua: titlecard`).
scenarios.titlecard = function()
    if not bootToMap() then return result("FAIL", "never reached the map") end
    local tile = emptyTile()
    if not tile or not cursorTo(tile.x, tile.y) then return result("FAIL", "no reachable empty map tile") end
    if not guardedInput("open_map_menu", "A", "live map command menu opens", function(after)
        return controllerState(after) == "map_command_menu"
    end, 120) then return result("FAIL", "map menu never opened") end
    local ok = selectSemantic("status", "Status screen proc starts", function()
        return procActive(SYM.gProcScr_ChapterStatusScreen)
    end, 240)
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
-- What the ROM loaded each red unit with: the full struct Unit stat line, so the parity model
-- (difficulty.py) and the wiki's load path (unit_load.py) can both be held to it (#490, #508).
-- struct Unit (bmunit.h): +04 pClassData (class number at +04), +08 level, +12 maxHP, +14 pow,
-- +15 skl, +16 spd, +17 def, +18 res, +19 lck. Run once per PT_DIFFICULTY.
INSPECT.redStats = function()
    if not bootToMap() then return result("FAIL", "never reached the map") end
    local actual = INSPECT.liveDifficulty()
    local n = 0
    for i = 0, 49 do
        local u = unitAt(SYM.gUnitArrayRed, i)
        if u and not u.dead then
            n = n + 1
            log(string.format(
                '{"event":"red_stats","mode":"%s","char":"0x%02x","class":"0x%02x","level":%d,'
                .. '"hp":%d,"pow":%d,"skl":%d,"spd":%d,"def":%d,"res":%d,"lck":%d}',
                actual, u.charId, ru8(ru32(u.addr + 0x04) + 0x04), u.level, u.maxhp, u.pow,
                ru8(u.addr + 0x15), ru8(u.addr + 0x16), u.def, ru8(u.addr + 0x18),
                ru8(u.addr + 0x19)))
        end
    end
    if n == 0 then return result("FAIL", "no red units on the map") end
    return result("PASS", string.format("mode=%s: %d red units logged", actual, n))
end

-- When each red unit first attacks while the party holds its deploy tiles (#510 step 7, the
-- in-engine proof of `timeline.engagements`). The parity model reads a pursuer's WAVE as the
-- enemy phase it first stands in weapon range of a deploy tile, with nobody moving and
-- nothing dying. This plays exactly that: every deployed unit ends its turn where prep put
-- it, every unit on both sides held at full HP every frame so nothing falls, for eight
-- enemy phases (`timeline.HORIZON`). Each red unit is logged the phase it is first seen (its
-- tile, the key the model's body is matched on) and the phase it first attacks, read off
-- gAiDecision the frame the AI makes it.
INSPECT.firstAttacks = function()
    local phases = 8 -- timeline.HORIZON
    if not bootToMap() then return result("FAIL", "never reached the map") end
    pokeFastConfig()
    INSPECT.settle("event", 6000, true)
    local seen, attacked = {}, {}
    -- Every frame, not once a phase: four attackers in one phase can drop a unit a once-a-phase
    -- refill missed, and a weapon's Mt still counters at 0 Pow. The first run without this
    -- lost six reds by phase 8, each freeing a tile the model's held front never frees.
    local function hold()
        for i = 0, 61 do
            local u = unitAt(SYM.gUnitArrayBlue, i)
            if u and u.onMap and not isDead(u) then
                emu:write8(u.addr + 0x12, 60); emu:write8(u.addr + 0x13, 60)
                pokeHarmless(u)
            end
        end
        for i = 0, 49 do
            local u = unitAt(SYM.gUnitArrayRed, i)
            if u and u.onMap and not isDead(u) then INSPECT.fullHeal(u) end
        end
    end
    local function look(phase)
        for i = 0, 49 do
            local u = unitAt(SYM.gUnitArrayRed, i)
            if u and u.onMap and not isDead(u) and not seen[ru8(u.addr + 0x0B)] then
                seen[ru8(u.addr + 0x0B)] = true
                log(string.format('{"event":"red_seen","phase":%d,"unit":"0x%02x","char":"0x%02x",'
                    .. '"x":%d,"y":%d}', phase, ru8(u.addr + 0x0B), u.charId, u.x, u.y))
            end
        end
    end
    look(1)
    local holding = callbacks:add("frame", hold)
    for phase = 1, phases do
        emu:write8(SYM.gAiDecision + 0x00, 0)
        local decided = {}
        local watch = callbacks:add("frame", function()
            local who, act = ru8(SYM.gAiDecision + 0x01), ru8(SYM.gAiDecision + 0x00)
            -- struct AiDecision (cp_common.h): +00 actionId, +01 unitId, +02/+03 the tile it
            -- moves to, +06 targetId. Every unit's decision once a phase, so a late striker
            -- can be traced to where it stood and whom it went for.
            if who ~= 0 and decided[who] ~= act then
                decided[who] = act
                log(string.format('{"event":"ai_decision","phase":%d,"unit":"0x%02x","action":%d,'
                    .. '"x":%d,"y":%d,"target":"0x%02x"}', phase, who, act,
                    ru8(SYM.gAiDecision + 0x02), ru8(SYM.gAiDecision + 0x03),
                    ru8(SYM.gAiDecision + 0x06)))
            end
            if act == 1 and not attacked[who] then
                attacked[who] = phase
                log(string.format('{"event":"first_attack","phase":%d,"unit":"0x%02x",'
                    .. '"target":"0x%02x"}', phase, who, ru8(SYM.gAiDecision + 0x06)))
            end
        end)
        -- A reinforcement loads during the turn change, before the enemy acts: look again
        -- once the phase has begun, so its first-seen tile is where it arrived.
        local look_watch = callbacks:add("frame", function()
            if faction() == 0x80 then look(phase) end
        end)
        local back = runEnemyPhase()
        callbacks:remove(watch)
        callbacks:remove(look_watch)
        if back ~= "player" then
            callbacks:remove(holding)
            return result("FAIL", string.format("enemy phase %d returned %s", phase, tostring(back)))
        end
        for i = 0, 49 do
            local u = unitAt(SYM.gUnitArrayRed, i)
            if u and u.onMap and not isDead(u) then
                log(string.format('{"event":"red_pos","phase":%d,"unit":"0x%02x","x":%d,"y":%d}',
                    phase, ru8(u.addr + 0x0B), u.x, u.y))
            end
        end
        for i = 0, 61 do
            local u = unitAt(SYM.gUnitArrayBlue, i)
            if phase == 1 and u and u.onMap and not isDead(u) then
                log(string.format('{"event":"blue_pos","unit":"0x%02x","x":%d,"y":%d}',
                    ru8(u.addr + 0x0B), u.x, u.y))
            end
        end
    end
    callbacks:remove(holding)
    local n, hit, alive = 0, 0, 0
    for _ in pairs(seen) do n = n + 1 end
    for _ in pairs(attacked) do hit = hit + 1 end
    for i = 0, 49 do
        local u = unitAt(SYM.gUnitArrayRed, i)
        if u and u.onMap and not isDead(u) then alive = alive + 1 end
    end
    -- A death is a broken hold, not the model being wrong: 0 Pow still counters through weapon
    -- Mt, so a run where something died says nothing about a model in which nothing does.
    if alive ~= n then
        return result("FAIL", string.format("%d of %d red units died: the held front must "
            .. "kill nothing", n - alive, n))
    end
    return result("PASS", string.format("%d red units seen, %d attacked within %d enemy phases",
                                        n, hit, phases))
end

-- The blue unit table in slot order once prep has deployed: the order FE8's AI breaks a
-- target tie in (cp_battle.c, `>=`: the later slot wins), which SortPlayerUnitsForPrepScreen
-- (prepscreen.c) sets to force-deployed units first, then the rest in their existing order.
-- The parity model's `_map_order` claims that order (#510 step 5).
INSPECT.blueOrder = function()
    if not bootToMap() then return result("FAIL", "never reached the map") end
    local n, deployed = 0, 0
    for i = 0, 61 do
        local u = unitAt(SYM.gUnitArrayBlue, i)
        if u and u.charId ~= 0 then
            n = n + 1
            local on = (u.state & US_NOT_DEPLOYED) == 0
            if on then deployed = deployed + 1 end
            log(string.format('{"event":"blue_slot","slot":%d,"char":"0x%02x","deployed":%s}',
                i, u.charId, on and "true" or "false"))
        end
    end
    if n == 0 then return result("FAIL", "no blue units in the table") end
    return result("PASS", string.format("%d blue units logged in slot order, %d deployed", n,
                                        deployed))
end

-- GAMEOVER: Hlin (the lord-analog) dies -> EVFLAG_GAMEOVER quote -> game over.
scenarios.gameover = function()
    if not bootToMap() then return result("FAIL", "never reached the map") end
    local hlin = blue(CAMPAIGN.PROLOGUE.hlin)
    if not hlin then return result("FAIL", "Hlin not found in blue array") end
    pokeFrail(hlin)
    log(string.format("Hlin at (%d,%d) poked frail; marching her at the enemy", hlin.x, hlin.y))
    local sephek = red(CAMPAIGN.PROLOGUE.sephek)
    local tx, ty = sephek.x, sephek.y + 1 -- adjacent: he attacks in range
    for t = 1, 8 do
        hlin = blue(CAMPAIGN.PROLOGUE.hlin)
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
    if isDead(blue(CAMPAIGN.PROLOGUE.hlin)) then
        return result("FAIL", "Hlin died but NO game over followed")
    end
    result("FAIL", "could not get Hlin killed in 8 turns (no verdict on game over)")
end

-- RETREAT: Scramsax dies -> flag-less quote -> battle CONTINUES (no game over).
scenarios.retreat = function()
    if not bootToMap() then return result("FAIL", "never reached the map") end
    local scram = blue(CAMPAIGN.PROLOGUE.scramsax)
    if not scram then return result("FAIL", "Scramsax not found in blue array") end
    pokeFrail(scram)
    pokeHarmless(scram) -- his counters must not kill the boss mid-test
    local sephek = red(CAMPAIGN.PROLOGUE.sephek)
    log("Scramsax poked frail+harmless; parking him next to Sephek")
    for t = 1, 6 do
        scram = blue(CAMPAIGN.PROLOGUE.scramsax)
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
    if not isDead(blue(CAMPAIGN.PROLOGUE.scramsax)) then
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
-- Shoot frames across ANY combat that runs through gProc_ekrBattle -- attack, heal-cast and
-- defend all funnel through the same proc, so one loop serves every combat. Success = the battle proc actually ran AND real ANIM frames were
-- captured -- robust whether the actor survives, dies in the counter, or kills + triggers a
-- level-up that outlasts the budget. A stall before combat starts never sets sawAnim -> FAIL.
--
-- A talky foe (boss taunt / per-PC line) raises an in-battle QUOTE box during gProc_ekrBattle
-- (ProcScr_BattleEventEngine) that WAITS for A and would otherwise eat the whole budget before
-- the attack draws -- the bug that once made every battle-anim film show only the quote, never the
-- hit/damage. So: tap A WHILE the quote box is up to dismiss it (it only blocks here, the pure
-- anim takes no input), and screenshot ONLY when no quote box is up -- those are the real
-- draw/fire/impact/HP-drain frames. Never tap during the pure anim (that would skip it); the
-- quote-proc gate guarantees we only press while a text box holds.
--
-- doneFn (optional) is an early-stop signal checked only OUTSIDE combat, e.g. the actor's own
-- "finished acting" flag for an attacker/caster, or "control is back with the player" for a
-- defender that has no such flag of its own to poll.
local function shootCombatFrames(tag, doneFn)
    local sawCombat, sawAnim = false, false
    for f = 1, 900 do
        local inCombat = procActive(SYM.gProc_ekrBattle)
        if inCombat then sawCombat = true
        elseif sawCombat then break end                        -- combat played and finished
        if doneFn and doneFn() and not inCombat then break end
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

-- Relocate the unit straight onto a free tile within [mn,mx] of a live enemy, so a unit that
-- SPAWNS far from the fight doesn't have to march across the map (6 phases can't cross it -- a
-- far spawn timed out). Writes xPos/yPos AND moves the unit's entry in gBmMapUnit (vacate old
-- tile, occupy new) so the engine can still select it from the new tile. Attack availability
-- depends only on an enemy being in weapon range of the unit's TILE, not the terrain under it,
-- so any in-range, grid-free, in-bounds tile works. Prefers the farthest in-range tile (e.g. a
-- bow at exactly 2). Returns true if relocated.
local function teleportToFiringTile(u, mn, mx)
    if mapUnitAt(u.x, u.y) == 0 then      -- this unit's id in the grid (preserves faction bits)
        log(string.format("  teleportToFiringTile: (%d,%d) not tracked in gBmMapUnit -- bailing", u.x, u.y))
        return false
    end
    local mw, mh = mapSize()   -- the LIVE footprint: a hardcoded 25x16 parks units off a 15x15
                               -- map (ch04), where the cursor can never reach them (#204)
    for _, e in ipairs(liveEnemies()) do
        for r = mx, mn, -1 do
            for dx = -r, r do
                local ady = r - math.abs(dx)
                for _, dy in ipairs(ady == 0 and { 0 } or { ady, -ady }) do
                    local tx, ty = e.x + dx, e.y + dy
                    if tx >= 0 and tx < mw and ty >= 0 and ty < mh and mapUnitAt(tx, ty) == 0 then
                        -- vacate the old tile, occupy the new; `tracked` keeps the bail above
                        -- true at the moment of the write, which reads the LIVE old tile
                        if not INSPECT.place(u, tx, ty, { tracked = true }) then return false end
                        log(string.format("  teleported to (%d,%d) [range %d of enemy (%d,%d)]", tx, ty, r, e.x, e.y))
                        return true
                    end
                end
            end
        end
    end
    log(string.format("  teleportToFiringTile: no free tile within [%d,%d] of any of %d live enemies", mn, mx, BOARD.liveCount("red")))
    return false
end

-- True when the ENGINE would offer this unit an Attack command from its current tile: a hostile
-- sits within [mn,mx] of it in gBmMapUnit. The clear-bot asks first so its policy chooses Wait
-- when Attack will not appear; chooseAttack independently resolves the live semantic command.
local function canAttackFromHere(u, mn, mx)
    local w, h = mapSize()
    return BOT.gridHostileInReach(function(x, y)
        if x < 0 or x >= w or y < 0 or y >= h then return nil end
        return mapUnitAt(x, y)
    end, u.x, u.y, mn, mx)
end

-- Turn fog OFF for a clear-bot run -- GRID AND ALL (#204). Zeroing gPlaySt.chapterVisionRange
-- disables bmtarget.c's targeting gate, but it does NOT put the enemies on the map: the tile->unit
-- grid is written by RefreshUnitsOnBmMap (bmmap.c), which skips a red standing in fog and files it
-- under gBmMapHidden instead. Until the engine's next refresh, gBmMapUnit therefore holds NO reds
-- at all -- every enemy unattackable, every tile they stand on reading "free". So lift the fog and
-- then force one RefreshEntityBmMaps by spending a single unit's Wait (MapMain_ResumeFromAction,
-- bmio.c); the refresh also refills gBmMapFog itself (BmMapFill(gBmMapFog, !visionRange)), so the
-- fog map needs no poking. Returns the number of live reds now ON the grid -- 0 means it did not
-- take, and the caller must not go on to swing at enemies the engine cannot see.
local function liftFogOntoTheGrid()
    emu:write8(SYM.gPlaySt + 0x0D, 0)
    local onGrid = function()
        local n = 0
        for _, r in BOARD.each("red") do
            if not isDead(r) and r.onMap and mapUnitAt(r.x, r.y) ~= 0 then n = n + 1 end
        end
        return n
    end
    for _, u in BOARD.each("blue") do
        if onGrid() > 0 then break end
        if u.onField and (u.state & 0x2) == 0 then
            if moveUnit(u.x, u.y, u.x, u.y) then
                chooseWait()
                INSPECT.settle("phase", 300)
            end
        end
    end
    local n = onGrid()
    log(string.format("  fog lifted: %d live reds now on gBmMapUnit", n))
    return n
end

-- Like teleportToFiringTile but relocates u onto a free tile adjacent (range exactly 1) to one
-- of `targets` (live ALLY units, not enemies) -- stages the heal capture: put the staff user
-- within Heal's range of a wounded teammate. Same grid-write structure as teleportToFiringTile
-- (#191); kept separate because the search set is allies, not liveEnemies().
local function teleportAdjacentTo(u, targets)
    if mapUnitAt(u.x, u.y) == 0 then return false end
    -- INSPECT.freeBeside bounds the search by the LIVE footprint, as teleportToFiringTile (#204).
    for _, t in ipairs(targets) do
        local tx, ty = INSPECT.freeBeside(t, { order = { { 0, -1 }, { 0, 1 }, { 1, 0 }, { -1, 0 } } })
        if tx then
            if not INSPECT.place(u, tx, ty, { tracked = true }) then return false end
            log(string.format("  teleported to (%d,%d) [adjacent to ally (%d,%d)]", tx, ty, t.x, t.y))
            return true
        end
    end
    return false
end

-- R on the name of the unit at (x, y), from the map: open its status screen, open help, move
-- onto the name and wait (up to 120 frames) for help to decode `want`. Returns true, {msg,
-- line1} (the message help ended on and its first line), or false and why. Leaves the map as
-- it found it, each step undone only where its state is live. `casthelp` and the declared
-- `help:` step (cases.lua) both read help through this.
INSPECT.helpAt = function(x, y, want)
    local function now() return Controller.classify(observeController()) end
    local ok, why = true, nil
    if not cursorTo(x, y) then
        ok, why = false, string.format("(%d,%d) never under the cursor", x, y)
    elseif not guardedInput("open_stat_screen", "R", "the status screen opens",
            function() return now() == "stat_screen" end, 240) then
        ok, why = false, "status screen never opened"
    elseif not guardedInput("open_help", "R", "the help box opens",
            function() return now() == "stat_screen_help" end, 120) then
        ok, why = false, "help never opened"
    else
        guardedInput("help_left", "LEFT", "help moves onto the name",
            function() return INSPECT.activeMsg() == want end, 120)
        local msg = INSPECT.activeMsg()
        local line, at = {}, SYM.sMsgString
        while #line < 64 do
            local b = ru8(at + #line)
            if b < 0x20 then break end
            line[#line + 1] = string.char(b)
        end
        why = {msg = msg, line1 = table.concat(line)}
    end
    if now() == "stat_screen_help" then
        guardedInput("close_help", "B", "the help box closes",
            function() return now() == "stat_screen" end, 120)
    end
    if now() == "stat_screen" then
        guardedInput("close_stat_screen", "B", "back on the map",
            function() return now() == "player_map_idle" end, 240)
    end
    return ok, why
end

-- CASTHELP (ADR 0346): R on a cast member's name reads ITS OWN help text, never its slot's
-- vanilla character's. A verdict on memory, so it runs headless: for every classed cast member
-- on the TESTCH sandbox it opens the status screen (R), opens help (R, which lands on Str), steps
-- LEFT onto the name/portrait entry (HbPopulate_SSCharacter fills it from the unit's descTextId)
-- and asserts `sActiveMsg` is that unit's message AND that its decoded first line (sMsgString's
-- buffer1) is the unit's own: the id alone is the one vanilla used. A member missing FAILs: a
-- check that skipped the unit it could not find would pass on nothing.
scenarios.casthelp = function()
    if not bootToMap() then return result("FAIL", "never reached the sandbox map") end
    -- One name per pid: CAST carries short aliases (`rbg`) beside the full ids.
    local names, byPid = {}, {}
    for name, pid in pairs(CAMPAIGN.CAST) do
        if CAMPAIGN.HELP[pid] and (not byPid[pid] or #name > #byPid[pid]) then byPid[pid] = name end
    end
    for _, name in pairs(byPid) do names[#names + 1] = name end
    table.sort(names)
    local bad = {}
    for _, name in ipairs(names) do
        local want = CAMPAIGN.HELP[CAMPAIGN.CAST[name]]
        local u = blue(CAMPAIGN.CAST[name])
        if not u then
            bad[#bad + 1] = name .. " not deployed"
        else
            local ok, got = INSPECT.helpAt(u.x, u.y, want.msg)
            if not ok then
                bad[#bad + 1] = name .. ": " .. got
            elseif got.msg ~= want.msg then
                bad[#bad + 1] = string.format("%s: help read MSG_%03X, want MSG_%03X",
                    name, got.msg, want.msg)
            elseif got.line1 ~= want.line1 then
                bad[#bad + 1] = string.format("%s: help reads %q, want %q",
                    name, got.line1, want.line1)
            end
        end
    end
    if #bad > 0 then return result("FAIL", table.concat(bad, "; ")) end
    return result("PASS", string.format("%d cast members: R on the name reads their own help text",
        #names))
end


-- ================================================================ unit list / SMS budget (#218)
-- The map-menu "Unit" screen (Character list) draws every roster unit's MAP SPRITE at a 16px
-- row pitch (unitlistscreen.c: PutUnitSprite(4, 8, 56 + i*16 + r8, ...)). Two things can make
-- that render wrong and only the ROM can tell them apart:
--
--   1. GEOMETRY -- PutUnitSprite (bmudisp.c) switches on unit_icon_wait_table[id].size and draws
--      a 16x32 at y-16 and a 32x32 at (x-8, y-16). A 32x32 entry therefore reaches a full 16px
--      into the row above, which no vanilla PLAYER unit ever does (vanilla's 32x32 sheets are
--      monsters, and monsters are never on your roster).
--   2. VRAM BUDGET -- UseUnitSprite hands out one shared 0x40-slot space: gSMS16xGfxIndexCounter
--      walks DOWN from 0x3F one slot per 16x16, gSMS32xGfxIndexCounter walks UP from 0 by 2 per
--      16x32 and 4 per 32x32. They are not checked against each other, so once they cross, later
--      sprites overwrite earlier ones and the whole list goes wrong at once.
--
-- Both are read here, before and after the screen opens: the list allocates sprites for roster
-- units that are NOT on the map, so it can push the counters well past what the map needed.
local UNITLIST_ROWS = 6                -- visible rows per page (the draw loop's `i < 6`)
local SMS_SLOT_SPACE = 0x40            -- ResetUnitSprites: 16x counter starts at 0x40-1, 32x at 0
local SMS_SIZE_NAME = { [0] = "16x16", [1] = "16x32", [2] = "32x32" }

-- unit_icon_wait_table[] is UnitIconWait {u16 pattern, u16 size, char *sheet} -- 8 bytes.
local function smsSize(id) return ru16(SYM.unit_icon_wait_table + id * 8 + 2) end

-- Everything UseUnitSprite has handed out so far, plus the two counters that ration it. A slot
-- of 0xFF means "never allocated on this map"; anything else is a live chr index.
local function dumpSmsBudget(when)
    local c32 = ru32(SYM.gSMS32xGfxIndexCounter)
    local c16 = ru32(SYM.gSMS16xGfxIndexCounter)
    log(string.format("SMS budget %s: 32x counter=%d (grows up from 0), 16x counter=%d "
        .. "(grows down from %d), headroom=%d slots%s",
        when, c32, c16, SMS_SLOT_SPACE - 1, c16 - c32,
        c32 >= c16 and "  <-- EXHAUSTED: the two counters have CROSSED" or ""))
    local live = {}
    for id = 0, 0xCF do
        local slot = ru8(SYM.gUnitSpriteSlots + id)
        if slot ~= 0xFF then
            live[#live + 1] = string.format("%d(%s)@chr%d", id, SMS_SIZE_NAME[smsSize(id)] or "?", slot * 2)
        end
    end
    log(string.format("SMS allocated %s (%d sprites): %s", when, #live, table.concat(live, " ")))
    return c32, c16
end

-- RECORDUNITLIST (#218): open the Character list on a `make TESTCH=1` ROM -- New Game boots
-- STRAIGHT into the Ch1 sandbox with the whole classed cast deployed, so the screen a player
-- opens constantly is ~30s from boot instead of a playthrough per capture. Shoots every page
-- of the roster and dumps the SMS geometry + VRAM budget on both sides of the transition.
scenarios.recordunitlist = function()
    if not bootToMap() then return result("FAIL", "never reached the map") end
    wait(60)
    local mapC32, mapC16 = dumpSmsBudget("on the map, before the list opens")

    local tile = emptyTile()
    if not tile then return result("FAIL", "live map has no empty tile to open its menu from") end
    if not cursorTo(tile.x, tile.y) then return result("FAIL", "cursor never reached the empty tile") end
    if not guardedInput("open_map_menu", "A", "live map command menu opens", function(after)
        return controllerState(after) == "map_command_menu"
    end, 120) then return result("FAIL", "the map command menu never opened") end
    if not selectSemantic("unit_list", "the Character (unit list) screen starts", function()
        return procActive(SYM.ProcScr_UnitListScreen_Field)
    end, 300) then return result("FAIL", "the map menu's Unit command never reached the list screen") end

    wait(90)                                   -- let the screen settle before the first frame
    shot("unitlist-page1")
    local listC32, listC16 = dumpSmsBudget("with the unit list open")

    -- Walk the roster on the classified Character screen (#238). Each DOWN is a guarded input
    -- whose postcondition is the ROSTER index moving; arriving at the last entry is the one
    -- case where it legitimately does not, so that is checked FIRST and ends the walk.
    --
    -- The old loop pressed DOWN blind and stopped when the on-screen row AND `proc+0x38` both
    -- held. Neither is the roster position: sub_809144C moves unk_30 (+0x30), while unk_2c
    -- (+0x2C) CLAMPS as the list scrolls beneath it, and +0x38 is not touched by the D-pad at
    -- all. So the walk could stop a few rows in, capture a fraction of the roster, and still
    -- report PASS -- a green light that did not mean what it said, which is the whole defect
    -- #238 exists for.
    if not awaitControllerState("unit_list_screen", 300) then
        return result("FAIL", "the unit list never reached its key handler")
    end
    local listed = observeController().unit_list
    log(string.format("unit list: %d units sorted onto the roster, %d visible rows per page",
        listed.count, UNITLIST_ROWS))
    -- A roster the screen reports as empty means the count is not being read from where the
    -- engine keeps it. Fail rather than "walk" a zero-length list and report a green capture
    -- of one frame -- which is exactly what the old allyCount read did.
    if listed.count < 1 then
        return result("FAIL", "the Character screen reports an empty roster")
    end
    local shots = 1
    for _ = 1, listed.count do
        local at = observeController()
        if not at.unit_list then break end
        local row = at.unit_list.row
        if row >= listed.count - 1 then break end         -- the end of the roster, not a stall
        if not guardedInput("list_next", "DOWN", "the roster selection advances", function(after)
            -- Settled for the same reason as the deploy walk: sub_809144C reads no D-pad
            -- while unk_29 says the rows are still scrolling under the cursor.
            return after.unit_list ~= nil and after.unit_list.row ~= row
                and not after.unit_list.scrolling
        end, 60) then
            return result("FAIL", string.format(
                "the roster walk stalled on entry %d of %d", row, listed.count))
        end
        shots = shots + 1
        shot(string.format("unitlist-row%02d", shots))
    end
    -- The capture is only worth anything if the walk actually reached the last entry.
    local ended = observeController().unit_list
    if not (ended and ended.row == listed.count - 1) then
        return result("FAIL", string.format(
            "the roster walk stopped on entry %s of %d without reaching the end",
            tostring(ended and ended.row), listed.count))
    end
    wait(20); shot("unitlist-end")
    dumpSmsBudget("after scrolling the whole roster")

    -- The verdict is the BUDGET, which is a fact the ROM can state. How the pixels read is
    -- Nicolas's call off the frames, so it is reported, never asserted.
    local oversize = {}
    for id = 107, 0xCF do
        if ru8(SYM.gUnitSpriteSlots + id) ~= 0xFF and smsSize(id) == 2 then
            oversize[#oversize + 1] = id
        end
    end
    log(string.format("custom SMS ids drawn as 32x32 in a 16px-pitch list: %s",
        #oversize > 0 and table.concat(oversize, ",") or "none"))
    if listC32 >= listC16 then
        return result("FAIL", string.format(
            "SMS VRAM exhausted: the unit list drove the 32x counter to %d past the 16x counter at %d "
            .. "(map alone reached %d/%d) -- later sprites overwrote earlier ones",
            listC32, listC16, mapC32, mapC16))
    end
    return result("PASS", string.format(
        "walked the whole %d-entry roster; SMS budget held (32x=%d < 16x=%d, %d slots spare); "
        .. "%d custom id(s) draw 32x32 into a 16px row pitch",
        shots, listC32, listC16, listC16 - listC32, #oversize))
end


-- ================================================================ ch02 load-test (#22)
-- The structural half of the Ch2 "Cold Welcome" load-test: does ch02 LOAD off the real
-- ch01->ch02 chain (MNC2(0x3)), not soft-lock, and is it winnable -- with the 3 GREEN chwinga
-- protect layer present and their per-survivor charm-gifts (CHECK_ALIVE -> GIVEITEMTO) actually
-- landing. The PACING half (judging the 5 cutscenes in motion) stays a human-at-mGBA pass.
-- Built on a "ch02start" save-state checkpoint (ckpt_ch02start plays the whole chain ONCE at
-- top speed); ch02 / smoke_ch02 / clear_ch02 LOAD it so each is fast. Char/class/item ids from
-- the decomp + the ch02 build (CH02_CHWINGA in inject/chapter_ids.py, the gift enums from inject.decomp.ITEM_ENUM).
-- The chwinga ON THE FIELD. Glimmerfrost (MANSEL, 0xC8) is not among them since 2026-08-30:
-- she inhabits the (1,12) hut and hands her charm over on the visit, so she is never a unit.
local CH02_PARK = { x = 0, y = 0 }                -- NW corner end-turn tile (15x15 map; deploy is row 3+)

-- Directed ch01 seize (the generic clear-bot is too slow to seize ch01's 25x16 map reliably):
-- march the lord onto the chief's throne, poking the chief + escort frail/harmless so the march
-- can't be blocked or killed. Modeled on scenarios.ch01win; reachCh02Map only needs to REACH
-- ch02, not fairly test ch01 balance. Returns "won" once ch01 hands off, else "timeout"/"gameover".
local function seizeCh01ToCh02()
    pokeFastConfig()   -- 10-goblin enemy phases: map combat + fast speed
    local status = INSPECT.ch01MarchOnChief{
        strict = true,
        lordId = CAMPAIGN.CAST.braulo,
        startLog = "ch01 seize: chief frail on (%d,%d); marching the lord",
        sync = function()
            if chapter() ~= 2 then return "won" end
            if not INSPECT.settle("phase", 6000, true) then
                traceFailure("ch01_seize", "player phase returns before the next move",
                    "fail:player-phase-timeout", nil, "ch01-seize-phase-timeout")
                return "controller"
            end
        end,
        onSeize = function(lord, goal)
            if not moveUnit(lord.x, lord.y, goal.x, goal.y) then return "controller" end
            local actions = Controller.legalActions(observeController())
            if not Controller.findAction(actions, "seize") then
                traceFailure("seize", "live unit menu exposes semantic Seize",
                    "fail:seize-not-legal", nil, "ch01-seize-missing")
                return "controller"
            end
            if not selectSemantic("seize", "Seize starts the ch01 win event", function()
                return procActive(SYM.ProcScr_StdEventEngine) or chapter() ~= 2
            end, 900) then return "controller" end
            if waitFor(function() return chapter() ~= 2 end, 9000, true) then return "won" end
            traceFailure("seize", "ch01 advances after the Seize event",
                "fail:chapter-advance-timeout", nil, "ch01-seize-timeout")
            return "controller"
        end,
    }
    -- This caller's contract names a lost/missing lord "gameover" (reachCh02Map logs the word).
    if status == "dead" then return "gameover" end
    return status
end

-- Reach the ch02 map off the REAL chain: clear ch00, seize ch01, then observe the ch01
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
    -- Observe the ending, save/lead menus, opening, Preparations, and turn-1 tutorial until the
    -- map is fully LIVE: enemies loaded,
    -- the party deployed, player control, no cutscene. Units/enemies/green chwinga load here -- the
    -- earlier "faction 0 + turn 1" fired during the opening cutscene, before any of them existed.
    local function partyDeployed()
        for _, u in BOARD.each("blue") do
            if (u.state & 0x9) == 0 and u.onMap then return true end end
        return false
    end
    for _ = 1, 16000 do
        if chapter() == CAMPAIGN.HOST.ch02 and faction() == 0 and turn() >= 1
            and unitAt(SYM.gUnitArrayRed, 0) ~= nil and partyDeployed()
            and not procActive(SYM.ProcScr_StdEventEngine) and not procActive(SYM.gProcScr_SALLYCURSOR)
            and not menuOpen() and controllerState() == "player_map_idle" then
            wait(120)
            shot("ch02-map")
            return true
        end
        local observation = observeController()
        local state, why = controllerState(observation)
        if state == "prep_main" then
            if not driveThroughPrep() then
                result("FAIL", "could not leave ch02 Preparations via semantic Fight"); return false
            end
        elseif state == "generic_menu" then
            -- Scenario policy: accept the live menu's highlighted default choice.
            if not guardedInput("select_current_menu_item", "A", "lead menu selection closes",
                function(after) return after.menu == nil end, 300) then
                result("FAIL", "could not choose the highlighted ch02 lead"); return false
            end
        else
            local advanced = advanceBootState(observation, state)
            if advanced == false then return false end
            if advanced == nil then
                traceFailure("reach_ch02", "post-chapter flow reaches the live ch02 map",
                    "fail:" .. tostring(why or state), observation, "ch02-unsupported")
                result("FAIL", "unsupported state before the ch02 map"); return false
            end
        end
    end
    traceFailure("reach_ch02", "post-chapter flow reaches the live ch02 map",
        "fail:chapter-flow-timeout", nil, "ch02-map-not-live")
    result("FAIL", "ch02 map never became live (party/enemies never loaded)")
    return false
end

-- ckpt_ch02start: build the ch02start checkpoint once (run.sh runs this at 240fps when the
-- state is missing/stale), so the deep ch00->ch01->ch02 chain is paid once per ROM build.
scenarios.ckpt_ch02start = function()
    if not reachCh02Map() then return end   -- reachCh02Map already set a FAIL verdict
    saveState("ch02start")
    result("PASS", "ch02start checkpoint saved (on the ch02 map, turn 1)")
end

-- ch01gold (#495): vanilla Ch2 starts at 5,000 gold, paid in Castle Frelia's scene after Ch1
-- (`lordsplit`; measured on retail by `vanillagold`). ch01 pays it in its ending through
-- `economy.scene_gold`. This plays the real chain -- seize, ending, save, ch02's opening and
-- Preparations -- and reads gPlaySt.partyGoldAmount (+0x08, include/types.h) on ch02's map.
-- Nothing else on that path pays or spends gold, so the reading is the scene's amount exactly.
scenarios.ch01gold = function()
    if not reachCh02Map() then return end   -- reachCh02Map already set a FAIL verdict
    local gold, want = ru32(SYM.gPlaySt + 0x08), CAMPAIGN.CH01_SCENE_GOLD
    log(string.format("ch01gold: ch02 opens with %d gold; ch01's scene_gold declares %d", gold, want))
    if gold ~= want then
        return result("FAIL", string.format("ch02 opens with %d gold, not the %d ch01's ending "
            .. "declares (vanilla Ch2 opens with 5,000)", gold, want))
    end
    result("PASS", string.format("ch02 opens with %d gold, paid by ch01's ending", gold))
end

-- Read every collected item id (low byte) from all blue inventories + the convoy -- where a
-- charm-gift lands (leader's inventory, overflow -> convoy).
local function collectedItems()
    local items = {}
    -- The WHOLE blue array, the same bound blue() uses. Slots 0-7 was fine while a chapter
    -- fielded eight; ch05 deploys nine plus Basil, so an item handed to a unit at index >= 8 --
    -- including CHAR_EVT_PLAYER_LEADER, if the leader is not slot 0 -- read as "never arrived".
    for i = 0, 61 do
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
    for _, pid in ipairs(CAMPAIGN.CH02_CHWINGA_PIDS) do
        local g = BOARD.find("green", pid)
        if g and not isDead(g) then
            emu:write8(g.addr + 0x13, 60)   -- curHP
            emu:write8(g.addr + 0x17, 30)   -- def
            emu:write8(g.addr + 0x18, 30)   -- res
        end
    end
end

-- CH03MIDMAP (#23 item 1): kill the Icewind Brute (the mid-map MINIBOSS) -> its FLAGGED silent
-- defeat quote sets EVFLAG_TMP(10) -> the Ch4 Misc AFEV(EVFLAG_TMP(11), midmap, EVFLAG_TMP(10))
-- runs the on-map RBG-execution cutscene ONCE. Proves the midmap trigger fires and the chapter
-- KEEPS GOING (unlike the boss WIN). The Brute rides a unique raw pid (0xb6, distinct from the
-- 0xaa generics + the grell's own pid) so its flagged death keys the trigger to it alone. Same
-- park-adjacent-and-strike trick (park the target beside a live blue unit, then strike); the Brute is a melee Brigand, so poke it frail (1 HP)
-- and hit at range 1 -- a dead defender throws no counter. Must NOT touch the grell (that would end
-- the chapter). Definitive assertion: EVFLAG_TMP(10) (Brute defeated) then EVFLAG_TMP(11) (the AFEV
-- guard, set AFTER the midmap script runs). Run: PT_HOST_CHAPTER=4 run.sh ch03midmap (needs CH03BOOT=1).
scenarios.ch03midmap = function()
    if not bootToMap() then return result("FAIL", "never reached the ch03 map") end
    if not red(0xb6) then return result("FAIL", "Icewind Brute (pid 0xb6) not found in the red array") end
    if not blue(0x01) then return result("FAIL", "leader (braulo, pid 0x01) not deployed") end
    -- Force an Iron Axe into items[0] so the scripted kill has a guaranteed in-range melee weapon.
    emu:write16(blue(0x01).addr + 0x1E, 0x2D1F)
    log("leader given an Iron Axe (guaranteed in-range weapon for the scripted kill)")
    -- Bring the Brute TO braulo's isolated left-entrance spawn so it is the ONLY unit in range
    -- (the (14,6) enforcer sits amid the grell + kobolds). Up to 3 player turns, enemy phase
    -- between, re-frailing + re-parking each turn against a whiff or an AI move.
    for turn = 1, 3 do
        local b = red(0xb6)
        if isDead(b) or eventFlag(10) then break end
        local leader = blue(0x01)
        pokeFrail(b)
        b = red(0xb6)
        local tx, ty = INSPECT.freeBeside(leader)
        local parked = tx ~= nil and INSPECT.place(b, tx, ty)
        if parked then
            log(string.format("turn %d: Brute parked at (%d,%d) next to braulo (%d,%d)",
                turn, tx, ty, leader.x, leader.y))
        end
        if not parked then return result("FAIL", "no free tile adjacent to braulo to park the Brute") end
        if moveUnit(leader.x, leader.y, leader.x, leader.y) then
            shot("attacking-brute")
            chooseAttack(leader.addr)
        end
        if isDead(red(0xb6)) or eventFlag(10) then break end
        log("Brute survived turn " .. turn .. " (miss?); running enemy phase to retry")
        if runEnemyPhase() == "gameover" then return result("FAIL", "unexpected game over in ch03midmap") end
    end
    if not (isDead(red(0xb6)) or eventFlag(10)) then
        shot("brute-alive")
        return result("FAIL", "could not kill the Brute in 3 turns")
    end
    -- The silent (msg=0) quote sets EVFLAG_TMP(10) on death (SetPidDefeatedFlag, no portrait to render).
    log("Brute dead; polling EVFLAG_TMP(10) (the AFEV's watched flag)")
    if not waitFor(function() return eventFlag(10) end, 600, true) then
        shot("brute-dead-no-flag")
        return result("FAIL", "Brute died but EVFLAG_TMP(10) never set (defeat quote did not fire)")
    end
    -- Flag 10 set -> at the next event scan the Misc AFEV runs the on-map execution cutscene (3
    -- Text() beats). Let the first beat render, screenshot it, then tap A through while polling the
    -- guard flag EVFLAG_TMP(11), which the AFEV sets ONLY after its script completes.
    wait(90)
    shot("ch03-midmap-beat")
    local fired = waitFor(function() return eventFlag(11) end, 3600, true)
    log(string.format("debug: EVFLAG_TMP(10)=%s EVFLAG_TMP(11)=%s chapter=%d (host=%d)",
        tostring(eventFlag(10)), tostring(eventFlag(11)), chapter(), HOST_CHAPTER))
    if not fired then
        shot("midmap-no-guard")
        return result("FAIL", "EVFLAG_TMP(10) set but the midmap AFEV never ran (EVFLAG_TMP(11) unset)")
    end
    -- The chapter must KEEP GOING (the midmap is not a win): assert we're still on the ch03 map.
    wait(60)
    shot("ch03-midmap-done")
    if chapter() ~= HOST_CHAPTER then
        return result("FAIL", string.format("midmap ended the chapter (%d != host %d)", chapter(), HOST_CHAPTER))
    end
    result("PASS", "Brute killed -> EVFLAG_TMP(10) -> midmap AFEV ran (EVFLAG_TMP(11)) -> chapter continues (ch03 midmap wired)")
end

-- CH03TALK (#23 item 2): prove Trex's TALK-RECRUIT flips him GREEN -> BLUE (the CUSA fires). Boot
-- the ch03 map, PARK the leader on a free tile adjacent to green Trex (the setMapUnit dance keeps
-- the occupancy grid in sync, so cursor-select + Talk-adjacency both work with no phase cycle --
-- same park-beside-a-blue-unit trick), then drive the Talk command and assert Trex leaves
-- the green array and joins the blue one. Run: PT_HOST_CHAPTER=4 run.sh ch03talk (needs CH03BOOT=1).
scenarios.ch03talk = function()
    if not bootToMap() then return result("FAIL", "never reached the ch03 map") end
    local CHAR_TREX = 0x1C -- CHARACTER_RENNAC (Trex rides the Rennac slot)
    -- ch03 deploys 9+ blue units, so scan the full blue array (blue() only checks the ch00
    -- 8-slot party -> a recruit at a higher index would be missed).
    local function blueTrex() return blue(CHAR_TREX) end
    local trex = BOARD.find("green", CHAR_TREX)
    if not trex then return result("FAIL", "green Trex (0x1C) not found in the green array") end
    if blueTrex() then return result("FAIL", "Trex is already blue before any talk") end
    local rec = blue(0x01) -- the leader is always deployed and is a recruit candidate
    if not rec then return result("FAIL", "leader (0x01) not deployed") end
    log(string.format("green Trex at (%d,%d); recruiter at (%d,%d)", trex.x, trex.y, rec.x, rec.y))
    shot("ch03talk-green")
    -- Park the recruiter on a free tile orthogonally adjacent to Trex.
    local tx, ty = INSPECT.freeBeside(trex)
    local parked = tx ~= nil and INSPECT.place(rec, tx, ty)
    if parked then
        log(string.format("recruiter parked at (%d,%d), adjacent to Trex (%d,%d)", tx, ty, trex.x, trex.y))
    end
    if not parked then return result("FAIL", "no free tile adjacent to Trex to park the recruiter") end
    -- Select the recruiter (no move) -> command menu. Parked next to ISOLATED green Trex in the
    -- galleries (no enemy in weapon range), Talk is the first command row -- no Attack precedes it.
    rec = blue(0x01)
    INSPECT.settle("phase", 300, true)
    if not moveUnit(rec.x, rec.y, rec.x, rec.y) then
        shot("ch03talk-no-menu")
        return result("FAIL", "could not open the recruiter's command menu")
    end
    wait(30); shot("ch03talk-menu")
    if not chooseTalk() then return result("FAIL", "live command menu did not expose a working Talk") end
    shot("ch03talk-dialogue-1") -- Trex's migrated talk lines rendering in-engine
    local pages = 1
    -- advance only when FE8 exposes TalkWaitForInput
    local _, why = INSPECT.talkUntil(blueTrex, 3600, {onBox = function()
        pages = pages + 1
        if pages <= 5 then shot(string.format("ch03talk-dialogue-p%d", pages)) end
    end})
    if why == "advance" then return result("FAIL", "Talk dialogue input did not advance") end
    wait(30); shot("ch03talk-after")
    for i, u in BOARD.each("blue") do   -- dump the full blue roster so the flip is unambiguous
        log(string.format("  blue[%02d] char=0x%02X pos=(%d,%d)", i, u.charId, u.x, u.y))
    end
    local nowBlue = blueTrex() ~= nil
    local stillGreen = BOARD.find("green", CHAR_TREX) ~= nil
    log(string.format("post-talk: Trex blue=%s stillGreen=%s", tostring(nowBlue), tostring(stillGreen)))
    if not nowBlue then
        return result("FAIL", "Trex did not join the blue army after Talk -- CUSA did not fire")
    end
    return result("PASS", "Talk -> CUSA: Trex flipped GREEN -> BLUE (talk-recruit wired, #23 item 2)")
end

-- CH03PREP (#23 item 3): prove the REAL PREP deploy. Boot toward the chapter and assert the
-- Preparations screen OPENS (the CALL(EventScr_08591FD8) fired), then Fight! into the phase and
-- assert the field roster deployed at the cap (9 = cast_available_at(3): 8 founding + Baxby) --
-- Trex is NOT among them (he joins mid-map, green, via Talk). Run: PT_HOST_CHAPTER=4 run.sh
-- ch03prep (needs a CH03BOOT=1 ROM). The boot LOADs an armed party seed so PREP has a roster.
scenarios.ch03prep = function()
    if not bootToMap(true) or controllerState() ~= "prep_main" then
        shot("ch03prep-no-prep")
        return result("FAIL", "Preparations screen never opened (PREP CALL did not fire)")
    end
    log("Preparations screen opened; Fight! into the phase")
    shot("ch03prep-open")
    if not driveThroughPrep() then
        shot("ch03prep-stuck")
        return result("FAIL", "could not Fight! out of Preparations")
    end
    wait(120) -- phase intro
    shot("ch03prep-map")
    local party, deployed = 0, 0
    for i, u in BOARD.each("blue") do
        party = party + 1
        -- on the field = not US_HIDDEN (1<<0) and not US_NOT_DEPLOYED (1<<3), real tile
        if (u.state & 0x9) == 0 and u.onMap then deployed = deployed + 1 end
        log(string.format("  blue[%02d] char=0x%02X pos=(%d,%d) state=0x%08X",
            i, u.charId, u.x, u.y, u.state))
    end
    local CHAR_TREX = 0x1C
    if blue(CHAR_TREX) then
        return result("FAIL", "Trex is on the prep roster -- he must join mid-map (green), not deploy")
    end
    log(string.format("party=%d deployed=%d turn=%d", party, deployed, turn()))
    if deployed ~= 9 then
        return result("FAIL", string.format(
            "PREP deploy cap broken: %d units on the field (want 9)", deployed))
    end
    result("PASS", string.format(
        "ch03 Preparations opened -> Fight! fielded %d units (cap 9), Trex held green", deployed))
end

-- gBmMapBaseTiles (u16**): the metatile grid a chest/door tile-change writes (ApplyMapChangesById,
-- bmtrick.c). Unlike the other gBmMap* grids this one lives in FE8's ROM .data and is never
-- reassigned, holding a constant pointer to the sBmBaseTilesPool row-pointer array in EWRAM.
-- So: read the pointer from ROM, index the row array, read the tile.
--
-- The address comes from SYM, never a literal. It WAS a literal (0x085AF5DC), the engine grew
-- out from under it, and that address came to hold 0x000004AB -- so ch03door and ch03chest
-- failed on their PRECONDITION, before driving any input, and read for all the world like
-- broken doors and chests. Nothing about the tile-change wiring was wrong (#238).
local function baseTile(x, y)
    local grid = ru32(SYM.gBmMapBaseTiles)   -- u16** value = &sBmBaseTilesPool
    return ru16(ru32(grid + y * 4) + x * 2)
end

-- CH03WALLS (#495): Borgo's three cracked walls stand on the ch03 map the way vanilla Ch3's do.
-- Each cell reads TERRAIN_WALL_DAMAGED, and InitMapObstacles (bmtrick.c) has given it a
-- TRAP_OBSTACLE whose HP (`extra`) is vanilla Ch3's mapCrackedWallHeath, 25 -- host slot 4 would
-- have said 50. sTrapPool is file-static, so SYM finds it through the linker map (gen_symbols).
-- What a broken wall becomes is the MapChange array's job, held to vanilla's by
-- test_map_tileset's Ch03FlipsPlayLikeVanillaCh3. Run: PT_HOST_CHAPTER=4 run.sh ch03walls.
scenarios.ch03walls = function()
    if not SYM.sTrapPool then
        return result("FAIL", "SYM.sTrapPool is missing -- gen_symbols found no linker map beside the ELF")
    end
    if not bootToMap() then return result("FAIL", "never reached the ch03 map") end
    local WALL_DAMAGED, TRAP_OBSTACLE, HP = 0x1B, 2, 25
    local WALLS = { { x = 8, y = 8 }, { x = 4, y = 9 }, { x = 4, y = 12 } }
    for _, w in ipairs(WALLS) do
        if terrainAt(w.x, w.y) ~= WALL_DAMAGED then
            return result("FAIL", string.format("(%d,%d) is terrain 0x%02X, not a cracked wall",
                w.x, w.y, terrainAt(w.x, w.y)))
        end
        local found
        -- Every slot: RemoveTrap frees one in place (type 0), so a hole is not the end.
        for i = 0, 63 do
            local t = SYM.sTrapPool + i * 8
            if emu:read8(t + 2) ~= 0 and emu:read8(t) == w.x and emu:read8(t + 1) == w.y then
                found = t break
            end
        end
        if not found then
            return result("FAIL", string.format("(%d,%d) has no trap -- nothing to break", w.x, w.y))
        end
        if emu:read8(found + 2) ~= TRAP_OBSTACLE or emu:read8(found + 3) ~= HP then
            return result("FAIL", string.format("(%d,%d) trap is type %d with %d HP, want %d / %d",
                w.x, w.y, emu:read8(found + 2), emu:read8(found + 3), TRAP_OBSTACLE, HP))
        end
    end
    return result("PASS", "all three cracked walls are WALL_DAMAGED obstacles with 25 HP")
end

-- CH03DOOR (#23 chests/doors): prove the door tile-change wiring end-to-end in-engine. Boot to the
-- ch03 map, hand a deployed unit a Door Key (and strip its weapon so the command menu is [Door,
-- Item, Wait] -- Door at row 0, deterministic), park it beside the (2,3) door, drive Door, and
-- assert gBmMapBaseTiles[3][2] flips from the closed door (812<<2) to the floor tile below it
-- (per Nicolas's "the tile directly below"): 92<<2, the FLOOR twin of 492's art -- 492 itself
-- plays as PLAINS since #495, and vanilla's opened door is FLOOR. Run: PT_HOST_CHAPTER=4 run.sh ch03door
-- (needs a CH03BOOT=1 ROM). The chest path shares this MapChange array -- verifying the door proves
-- both mechanisms (GetMapChangeIdAt -> CallTileChangeEvent -> ApplyMapChangesById).
scenarios.ch03door = function()
    if not bootToMap() then return result("FAIL", "never reached the ch03 map") end
    local DX, DY = 2, 3
    local CLOSED, OPEN_T = 812 * 4, 92 * 4    -- gBmMapBaseTiles holds metatile<<2
    local pre = baseTile(DX, DY)
    log(string.format("door (%d,%d) tile before = %d (want closed %d)", DX, DY, pre, CLOSED))
    if pre ~= CLOSED then
        return result("FAIL", string.format(
            "door (%d,%d) reads %d, not the closed-door tile %d -- placement or gBmMapBaseTiles addr wrong",
            DX, DY, pre, CLOSED))
    end
    -- Grab the first deployed blue unit (on the field: not US_HIDDEN|US_NOT_DEPLOYED, real tile).
    local u
    for _, c in BOARD.each("blue") do
        if (c.state & 0x9) == 0 and c.onMap then u = c break end
    end
    if not u then return result("FAIL", "no deployed blue unit to open the door") end
    -- Door Key in slot 0 (0x6A, 1 use), zero the rest -> no weapon -> no Attack row.
    emu:write16(u.addr + 0x1E, 0x6A | (0x01 << 8))
    for s = 1, 4 do emu:write16(u.addr + 0x1E + s * 2, 0) end
    -- Park orthogonally adjacent to the door on a known-passable floor cell ((2,2) floor / (2,4) road;
    -- the door's left/right are wall frame). Vacate the old tile, occupy the new -- cursor-select
    -- reads gBmMapUnit, not xPos (cf. the ch03talk park trick).
    local parked
    local tx, ty = INSPECT.freeBeside({ x = DX, y = DY }, { order = { { 0, -1 }, { 0, 1 } } })
    if tx and INSPECT.place(u, tx, ty) then parked = { tx, ty } end
    if not parked then return result("FAIL", "no free tile adjacent to the (2,3) door to park a unit") end
    log(string.format("parked opener at (%d,%d), adjacent to the door", parked[1], parked[2]))
    shot("ch03door-before")
    -- Select (no move) -> command menu, then resolve the live Door command (#238). This used
    -- to press A on "Door (row 0)" and then a SECOND A to "confirm the door target" -- but
    -- DoorCommandEffect (bmmenu.c) returns MENU_ACT_END: it sets gActionData and the menu is
    -- gone, there is no target step. So the first press depended on Door happening to be the
    -- top row, and the second went into whatever the map put up next.
    INSPECT.settle("phase", 300, true)
    if not moveUnit(parked[1], parked[2], parked[1], parked[2]) then
        shot("ch03door-no-menu")
        return result("FAIL", "could not open the opener's command menu")
    end
    wait(20); shot("ch03door-menu")
    if not selectSemantic("open_door", "the Door command closes the unit menu", function(after)
        return after.menu == nil
    end, 120) then
        return result("FAIL", "the command menu offered no live Door command to the key-holder")
    end
    local flipped = waitFor(function() return baseTile(DX, DY) == OPEN_T end, 400, true)
    wait(20); shot("ch03door-after")
    local post = baseTile(DX, DY)
    log(string.format("door (%d,%d) tile after = %d (want open %d)", DX, DY, post, OPEN_T))
    if not flipped then
        return result("FAIL", string.format(
            "door did not open: tile stayed %d (want %d = 492<<2, the floor below)", post, OPEN_T))
    end
    return result("PASS", string.format(
        "Door opened: gBmMapBaseTiles[%d][%d] flipped %d -> %d (812->492, the tile below) (#23)",
        DY, DX, pre, post))
end

-- CH03CHEST (#23 chests/doors): prove the chest tile-change + item grant in-engine. Boot to the ch03
-- map, hand a deployed unit a Chest Key (strip its weapon -> menu is [Chest, Item, Wait], Chest at row
-- 0), teleport it ONTO the (6,3) chest tile (chests open from the tile, not adjacent -- TERRAIN_CHEST_FULL),
-- drive Chest, and assert (a) gBmMapBaseTiles[3][6] flips 17<<2 -> 29<<2 (closed FF5 chest -> open) AND
-- (b) the chest's Iron Lance lands in the opener's inventory. Run: PT_HOST_CHAPTER=4 run.sh ch03chest
-- (needs a CH03BOOT=1 ROM). Shares the MS_Ch03MapChanges array + code path with ch03door.
scenarios.ch03chest = function()
    if not bootToMap() then return result("FAIL", "never reached the ch03 map") end
    local CX, CY = 6, 3
    local CLOSED, OPEN_T = 17 * 4, 29 * 4     -- FF5 navy chest: closed 17 / open 29, metatile<<2
    local IRON_LANCE = 0x14                    -- the (6,3) chest's Iron Lance (ch03 YAML)
    local pre = baseTile(CX, CY)
    log(string.format("chest (%d,%d) tile before = %d (want closed %d)", CX, CY, pre, CLOSED))
    if pre ~= CLOSED then
        return result("FAIL", string.format(
            "chest (%d,%d) reads %d, not the closed-chest tile %d -- placement/addr wrong", CX, CY, pre, CLOSED))
    end
    local u
    for _, c in BOARD.each("blue") do
        if (c.state & 0x9) == 0 and c.onMap then u = c break end
    end
    if not u then return result("FAIL", "no deployed blue unit to open the chest") end
    -- Chest Key in slot 0 (0x69, 1 use), zero the rest -> no weapon (no Attack) + free slots for the loot.
    emu:write16(u.addr + 0x1E, 0x69 | (0x01 << 8))
    for s = 1, 4 do emu:write16(u.addr + 0x1E + s * 2, 0) end
    -- Chests open from ON the tile: teleport the opener onto (6,3) (vacate old tile, occupy the chest).
    if mapUnitAt(CX, CY) ~= 0 then return result("FAIL", "the (6,3) chest tile is already occupied") end
    -- grid = 1: blue army slot-1 grid marker isn't needed; any non-zero registers occupancy
    if not INSPECT.place(u, CX, CY, { grid = 1 }) then
        return result("FAIL", "could not stand the opener on the (6,3) chest tile")
    end
    shot("ch03chest-before")
    INSPECT.settle("phase", 300, true)
    if not moveUnit(CX, CY, CX, CY) then
        shot("ch03chest-no-menu")
        return result("FAIL", "could not open the opener's command menu on the chest tile")
    end
    wait(20); shot("ch03chest-menu")
    -- Resolve the live Chest command instead of pressing an assumed row 0 (#238).
    -- ChestCommandEffect returns MENU_ACT_END, so the postcondition is the menu going away;
    -- the open animation and the "got Iron Lance" fanfare follow on their own. That fanfare
    -- was being cleared by eight blind A's -- which is a text box, i.e. a CLASSIFIED
    -- dialogue_wait, so the waitFor below already advances it through the guarded input and
    -- stops the instant the tile flips. Eight unconditional presses could not tell the two
    -- apart, and any that overran the box went into the map.
    if not selectSemantic("open_chest", "the Chest command closes the unit menu", function(after)
        return after.menu == nil
    end, 120) then
        return result("FAIL", "the command menu offered no live Chest command on the chest tile")
    end
    local flipped = waitFor(function() return baseTile(CX, CY) == OPEN_T end, 400, true)
    -- The two halves of "the chest opened" do NOT land on the same frame: the tile flips
    -- first, and the Iron Lance arrives at the end of the grant sequence with its own fanfare
    -- in between. So WAIT for the loot rather than reading the inventory the instant the tile
    -- moves -- that raced, and reported a chest that had in fact opened as one that granted
    -- nothing. (tapA advances the "got Iron Lance" box through the guarded dialogue input;
    -- the eight blind A's this replaces papered over the race by taking ~160 frames.)
    -- Re-find the opener (its array index is stable; read items[0..4] for the loot).
    local function hasLance()
        for s = 0, 4 do
            if (ru16(u.addr + 0x1E + s * 2) & 0xFF) == IRON_LANCE then return true end
        end
        return false
    end
    local got = waitFor(hasLance, 400, true)
    wait(20); shot("ch03chest-after")
    local post = baseTile(CX, CY)
    log(string.format("chest (%d,%d) tile after = %d (want %d); iron-lance in inventory = %s",
        CX, CY, post, OPEN_T, tostring(got)))
    if not flipped then
        return result("FAIL", string.format("chest tile did not flip: stayed %d (want %d)", post, OPEN_T))
    end
    if not got then
        return result("FAIL", "chest opened (tile flipped) but the Iron Lance did not land in the opener's inventory")
    end
    return result("PASS", string.format(
        "Chest opened: tile flipped %d -> %d (17->29) AND the Iron Lance was granted (#23)", pre, post))
end

-- CH03TOURMALINE (#23 art): SHOW the pink Tourmaline icon in-engine. Give a deployed unit the
-- Tourmaline (ITEM_REDGEM, drawn from reserved BG bank 15 via the DrawIcon hook) alongside pal-0 gems (Blue Gem,
-- Vulnerary/Goodberry) so the shot proves BOTH the pink renders AND the pal-0 items are unaffected.
-- All three are non-weapons, so the command menu is [Item, Wait] -- Item at row 0. Run:
-- PT_HOST_CHAPTER=4 tools/playtest/run.sh ch03tourmaline (needs a CH03BOOT=1 ROM).
scenarios.ch03tourmaline = function()
    if not bootToMap() then return result("FAIL", "never reached the ch03 map") end
    local u
    for _, c in BOARD.each("blue") do
        if (c.state & 0x9) == 0 and c.onMap then u = c break end
    end
    if not u then return result("FAIL", "no deployed unit to hold the Tourmaline") end
    -- items[0..2] = Tourmaline (0x76, custom pal), Blue Gem (0x75, pal 0), Goodberry/Vulnerary (0x6C, pal 0).
    emu:write16(u.addr + 0x1E + 0, 0x76 | (0x01 << 8))
    emu:write16(u.addr + 0x1E + 2, 0x75 | (0x01 << 8))
    emu:write16(u.addr + 0x1E + 4, 0x6C | (0x01 << 8))
    for s = 3, 4 do emu:write16(u.addr + 0x1E + s * 2, 0) end
    -- Relocate to an ISOLATED floor tile (no orthogonally-adjacent ally) so the command menu is just
    -- [Item, Wait] -- otherwise a nearby deployed unit adds Rescue at row 0 and A opens the wrong submenu.
    local function terr(x, y) return ru8(ru32(ru32(SYM.gBmMapTerrain) + y * 4) + x) end
    local FLOOR = { [0x01] = true, [0x02] = true, [0x17] = true, [0x2a] = true, [0x2d] = true }
    local moved = false
    for y = 1, 14 do
        for x = 1, 15 do
            if FLOOR[terr(x, y)] and mapUnitAt(x, y) == 0
                and mapUnitAt(x - 1, y) == 0 and mapUnitAt(x + 1, y) == 0
                and mapUnitAt(x, y - 1) == 0 and mapUnitAt(x, y + 1) == 0 then
                if not INSPECT.place(u, x, y) then
                    return result("FAIL", string.format("could not relocate the holder to (%d,%d)", x, y))
                end
                log(string.format("relocated the holder to the isolated tile (%d,%d)", x, y))
                moved = true
                break
            end
        end
        if moved then break end
    end
    if not moved then return result("FAIL", "no isolated floor tile found to open a clean Item menu") end
    u = unitAt(SYM.gUnitArrayBlue, 0) and u   -- addr stable
    INSPECT.settle("phase", 300, true)
    local ux, uy = ru8(u.addr + 0x10), ru8(u.addr + 0x11)
    if not moveUnit(ux, uy, ux, uy) then
        shot("ch03tourmaline-no-menu")
        return result("FAIL", "could not open the command menu")
    end
    wait(20); shot("ch03tourmaline-cmdmenu")
    -- Resolve the live Item command (#238). The isolation trick above exists precisely
    -- because the old blind A assumed Item sat at row 0 -- a neighbouring ally added Rescue
    -- above it and the press opened the wrong submenu. Naming the command makes that an
    -- observation rather than a staging assumption; the isolation stays, because the SHOT
    -- wants a clean two-item menu.
    if not selectSemantic("open_items", "the Item command opens the inventory list", function(after)
        return controllerState(after) == "item_list"
    end, 120) then
        return result("FAIL", "the command menu offered no live Item command to the holder")
    end
    wait(20)
    shot("ch03tourmaline-inventory")   -- the money shot: Tourmaline (pink) above two pal-0 items
    -- Diagnostic for the custom-bank reservation: inventory remains over the battle map, so inspect
    -- every enabled BG tilemap's palette nibbles before selecting a dedicated icon bank.
    local dispcnt = ru16(0x04000000)
    for bg = 0, 3 do
        if (dispcnt & (1 << (8 + bg))) ~= 0 then
            local cnt = ru16(0x04000008 + bg * 2)
            local blocks = ({1, 2, 2, 4})[(cnt >> 14) + 1]
            local base = 0x06000000 + (((cnt >> 8) & 0x1F) * 0x800)
            local used = {}
            for i = 0, blocks * 1024 - 1 do
                local bank = ru16(base + i * 2) >> 12
                used[bank] = (used[bank] or 0) + 1
            end
            local banks = {}
            for bank = 0, 15 do if used[bank] then banks[#banks + 1] = bank end end
            log(string.format("item-menu BG%d palette banks: %s", bg, table.concat(banks, ",")))
            -- The custom 16x16 icon itself occupies four BG0 tilemap entries. Any additional
            -- bank-15 entries mean another screen element shares the reservation.
            if (used[15] or 0) > 4 then
                return result("FAIL", string.format(
                    "reserved custom palette bank 15 has %d entries on BG%d (want the Tourmaline's 4 only)",
                    used[15], bg))
            end
        end
    end
    -- LoadIconPalettes(4) must preserve vanilla bank 5 (whose second colour is 0x7FDE) and load
    -- the custom Tourmaline palette in reserved bank 15 (second colour = white, 0x7FFF). The old destructive
    -- path repainted bank 5, which made regular map/UI text pink.
    local pal5_second = ru16(0x05000000 + 5 * 32 + 2)
    local pal15_second = ru16(0x05000000 + 15 * 32 + 2)
    if pal5_second ~= 0x7FDE or pal15_second ~= 0x7FFF then
        return result("FAIL", string.format(
            "item palette banks wrong (bank5[1]=0x%04X, bank15[1]=0x%04X)", pal5_second, pal15_second))
    end
    -- Data-side confirm: the item is really in slot 0 (the pixels are the deliverable; assert the item).
    local held = ru16(u.addr + 0x1E) & 0xFF
    if held ~= 0x76 then
        return result("FAIL", string.format("Tourmaline not in slot 0 (got 0x%02X)", held))
    end
    return result("PASS", "Tourmaline (ITEM_REDGEM) held + Item menu opened -- see ch03tourmaline-inventory.png for the pink icon")
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
    for i, u in BOARD.each("blue") do
        log(string.format("blue[%02d] char=0x%02X pos=(%d,%d) state=0x%08X",
            i, u.charId, u.x, u.y, u.state))
        if (u.state & 0x9) == 0 and u.onMap then deployed = deployed + 1 end
        if u.charId == BAXBY and not isDead(u) then baxby = true end
    end
    local trexGreen = BOARD.find("green", TREX)
    if trexGreen then log(string.format("green Trex(0x1C) @ (%d,%d)", trexGreen.x, trexGreen.y)) end
    log(string.format("ch03 entry: bluedeployed=%d baxby(0x10)=%s trex_green=%s",
        deployed, tostring(baxby), tostring(trexGreen ~= nil)))
    shot("ch03-entry")
    if not baxby then return result("FAIL", "Baxby (Forde 0x11) not on the ch03 blue roster") end
    if not trexGreen then return result("FAIL", "Trex (Rennac 0x1C) not placed green (talk-recruit) on the map") end
    return result("PASS", string.format(
        "ch03 entered: %d blue (incl Baxby), Trex green talk-recruit on the map", deployed))
end

-- smoke_ch03: stability net on the ch03 map (#23) -- boot the CH03BOOT map (bootToMap drives
-- through PREP) and idle-drive to a clean terminal, catching a crash/soft-lock on load or during
-- the opening/entrance/midmap cutscenes. Mirrors smoke_ch01/smoke_ch02.
-- Run: PT_HOST_CHAPTER=4 tools/playtest/run.sh smoke_ch03 (needs a CH03BOOT=1 ROM).
scenarios.smoke_ch03 = function()
    if not bootToMap() then return result("FAIL", "never reached the ch03 map") end
    return smokeDrive(chapter())
end

-- smoke_ch04: stability net on the ch04 map (#24 Stage 5) -- boot the CH04BOOT map (bootToMap
-- drives through the two-BG Lonelywood opening and PREP) and idle-drive to a clean terminal.
-- This is the net for the Stage 4 cutscene wiring specifically: a second BACG that fails to
-- re-arm its load mode, or a branch that never converges, shows up here as a soft-lock.
-- Run: PT_HOST_CHAPTER=5 tools/playtest/run.sh smoke_ch04 (needs a CH04BOOT=1 ROM).
scenarios.smoke_ch04 = function()
    if not bootToMap() then return result("FAIL", "never reached the ch04 map") end
    return smokeDrive(chapter())
end

-- ch02: entry assertions on the ch02 map (mirrors scenarios.ch01). The 3 green chwinga are on
-- the field, the party deploys to the cap, and the archer + boss are present.
scenarios.ch02 = function()
    -- Off the row's declared checkpoint, strictly: bootToMap's opts.strictCheckpoint.
    local booted, why = bootToMap(nil, nil, {strictCheckpoint = true})
    if not booted then return result("FAIL", why or "never reached the ch02 map") end
    -- diagnostic: dump every non-null green slot (and the blue/red char ids) so a missing-chwinga
    -- failure shows whether they are absent, on another faction, or under unexpected char ids.
    for i, g in BOARD.each("green") do
        log(string.format("green[%02d] char=0x%02X pos=(%d,%d) hp=%d state=0x%08X",
            i, g.charId, g.x, g.y, g.hp, g.state))
    end
    local blueids, redids = {}, {}
    for _, u in BOARD.each("blue") do blueids[#blueids+1] = string.format("0x%02X", u.charId) end
    for _, r in BOARD.each("red") do redids[#redids+1] = string.format("0x%02X", r.charId) end
    log("blue=" .. table.concat(blueids, ",") .. " | red=" .. table.concat(redids, ","))
    local chwinga = 0
    for _, pid in ipairs(CAMPAIGN.CH02_CHWINGA_PIDS) do
        local g = BOARD.find("green", pid)
        if g and not isDead(g) then chwinga = chwinga + 1
            log(string.format("chwinga 0x%02X at (%d,%d) hp=%d", pid, g.x, g.y, g.hp)) end
    end
    local deployed = 0
    for _, u in BOARD.each("blue") do
        if (u.state & 0x9) == 0 and u.onMap then deployed = deployed + 1 end
    end
    local archer, boss = false, false
    for _, r in BOARD.each("red") do
        if not isDead(r) then
            if ru8(ru32(r.addr + 0x04) + 0x04) == CAMPAIGN.CH02_ARCHER_CLASS then archer = true end
            if BOARD.isBoss(r.addr) then boss = true end
        end
    end
    log(string.format("ch02 entry: chwinga=%d deployed=%d archer=%s boss=%s",
        chwinga, deployed, tostring(archer), tostring(boss)))
    shot("ch02-entry")
    if chwinga ~= 2 then return result("FAIL", string.format("want 2 green chwinga, found %d", chwinga)) end
    -- All four Targos huts must be VILLAGE terrain at entry. They are the decoy the raid walks
    -- toward, and pillage reads terrain: a hut painted as anything else is a hut no raider
    -- targets, which puts the whole force back on the chwinga (#26). (4,2) and (7,2) were
    -- ruins until #495.
    for _, hut in ipairs({ {1, 12}, {12, 3}, {4, 2}, {7, 2} }) do
        if terrainAt(hut[1], hut[2]) ~= 0x03 then
            return result("FAIL", string.format(
                "hut (%d,%d) is terrain 0x%02X at entry, not a village -- nothing raids it and "
                .. "nothing visits it", hut[1], hut[2], terrainAt(hut[1], hut[2])))
        end
    end
    if deployed ~= 5 then return result("FAIL", string.format("deploy cap broken: %d on field (want 5)", deployed)) end
    if not archer then return result("FAIL", "no enemy archer (fliers-vs-bows debut) on the field") end
    if not boss then return result("FAIL", "no boss on the field") end
    result("PASS", string.format(
        "ch02 entered: 2 chwinga green, %d deployed, archer + boss present, all four huts standing",
        deployed))
end

-- smoke_ch02: stability net on the ch02 map -- idle-drive to a clean terminal, catching a
-- crash / soft-lock on load or during the 5 cutscenes.
scenarios.smoke_ch02 = function()
    local booted, why = bootToMap(nil, nil, {strictCheckpoint = true})
    if not booted then return result("FAIL", why or "never reached the ch02 map") end
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
scenarios.ch02baxby = function()
    local booted, why = bootToMap(nil, nil, {strictCheckpoint = true})
    if not booted then return result("FAIL", why or "never reached the ch02 map") end
    -- 1. PREP-ROSTER proof: Baxby must be a real party member. Search the whole blue array (the
    --    roster is 9 deep: 8 founding 0x01..0x08 + Baxby), at the decomp's bound.
    local baxby, bidx
    for i, u in BOARD.each("blue") do
        log(string.format("blue[%02d] char=0x%02X pos=(%d,%d) state=0x%08X", i, u.charId, u.x, u.y, u.state))
        if u.charId == CAMPAIGN.CAST.baxby then baxby, bidx = u, i end
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
    if (baxby.state & 0x9) ~= 0 or not baxby.onMap then
        local idx = ru8(baxby.addr + 0x0B)                    -- unit->index = its map-grid id
        emu:write32(baxby.addr + 0x0C, baxby.state & ~0x9)    -- clear US_HIDDEN | US_NOT_DEPLOYED
        local placed = false
        for _, t in ipairs({ { 0, 3 }, { 0, 4 }, { 1, 4 }, { 2, 3 }, { 1, 3 }, { 0, 5 } }) do
            if mapUnitAt(t[1], t[2]) == 0 and INSPECT.place(baxby, t[1], t[2], { grid = idx, vacate = false }) then
                placed = true
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
    -- The engine only spawns a unit's STANDING map sprite during a sprite refresh
    -- (RefreshUnitSprites, fired on phase transitions / menu exits, bmio.c) -- a memory-poked
    -- deploy sets his position but never creates the sprite object. So make every enemy
    -- frail+harmless (a safe enemy phase) and cycle ONE enemy phase back to player: that refresh
    -- draws Baxby's real, injected map sprite (the same one ch03 renders) so the still shows him.
    pokeFastConfig()   -- map-anim + fast so the refresh phase is quick
    for _, r in BOARD.each("red") do
        if not isDead(r) then pokeFrail(r); pokeHarmless(r) end
    end
    cursorTo(baxby.x, baxby.y); wait(20); shot("ch02baxby-deployed-presprite")
    if runEnemyPhase(CH02_PARK) == "gameover" then
        return result("FAIL", "unexpected game over during the sprite-refresh phase")
    end
    baxby = unitAt(SYM.gUnitArrayBlue, bidx)
    if not baxby or isDead(baxby) then return result("FAIL", "Baxby was lost on the refresh phase") end
    cursorTo(baxby.x, baxby.y); wait(40); shot("ch02baxby-on-map")   -- his sprite now renders
    log(string.format("Baxby on the ch02 map with his sprite at (%d,%d)", baxby.x, baxby.y))
    -- 3. COMBAT proof: teleport him onto a tile within weapon reach of a live raider and attack.
    --    Frail+harmless every enemy first (1 HP, no counter power) so whichever foe he strikes is a
    --    clean, deterministic one-round kill he can't die to -- this is a WIRING proof (Baxby fights
    --    on the ch02 map), not a balance test. PASS = an enemy died to his strike AND he took his
    --    action (US_UNSELECTABLE), i.e. a real battle round resolved on the map.
    pokeAnimsOn()   -- full battle anim for the showcase strike
    local mn, mx = unitAttackRange(baxby)
    if not mn then return result("FAIL", "Baxby has no attacking weapon equipped") end
    for _, r in BOARD.each("red") do
        if not isDead(r) then pokeFrail(r); pokeHarmless(r) end
    end
    local liveBefore = BOARD.liveCount("red")
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
    local liveAfter = BOARD.liveCount("red")
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

-- The ch02 deterministic rout (#531 audit 10), clear_ch02's. The
-- generic clear-bot is unreliable on ch02 (fumbles into item menus), so each player phase frails
-- + harmlesses every enemy (1 HP, no power) and teleports a party unit to a firing tile on each
-- live foe to one-shot it via REAL combat -- the kill goes through the death hook that fires the
-- DefeatAll win check (a raw US_DEAD poke would NOT). The chwinga are kept alive so their
-- charm-gifts play in the ending. `advanced()` says the chapter has moved on; `tag` prefixes the
-- per-turn log line; `afterEnemyPhase` (optional) runs after each enemy phase.
-- Returns "routed" | "advanced" | "gameover" | "exhausted", and the turn it stopped on.
function INSPECT.routCh02(advanced, tag, afterEnemyPhase)
    for t = 1, 12 do
        if advanced() then return "advanced", t end
        INSPECT.settle("phase", 6000, true)
        wait(60)
        protectChwinga()
        for _, r in BOARD.each("red") do
            if not isDead(r) then pokeFrail(r); pokeHarmless(r) end
        end
        for _, u in BOARD.each("blue") do
            if advanced() or BOARD.liveCount("red") == 0 then break end
            if u.onField and (u.state & 0x2) == 0 then
                local mn, mx = unitAttackRange(u)
                if mn and teleportToFiringTile(u, mn, mx) then
                    u = blue(u.charId)   -- refresh after the teleport relocates it
                    if u and moveUnit(u.x, u.y, u.x, u.y) then
                        chooseAttack(u.addr)
                        INSPECT.settle("fight", 600)   -- let the kill resolve
                    end
                end
            end
        end
        log(string.format("%s turn %d: liveEnemies=%d chapter=%d", tag, t, BOARD.liveCount("red"), chapter()))
        if BOARD.liveCount("red") == 0 then return "routed", t end
        if advanced() then return "advanced", t end
        if runEnemyPhase(CH02_PARK) == "gameover" then return "gameover", t end
        if afterEnemyPhase then afterEnemyPhase() end
    end
    return "exhausted", 12
end

-- clear_ch02: the completability + chain + charm-delivery proof. Rout the raider band (DefeatAll)
-- while keeping the chwinga alive, then watch the ending scene gift their charms to the leader /
-- convoy. PASS = routed, chained, and both SURVIVOR charms delivered.
--
-- TWO, not three, since 2026-08-30: Glimmerfrost moved into the (1,12) hut and pays on the
-- visit rather than at the ending, so her Pure Water is ch02visit's to prove (and ch02raid's
-- to prove LOST). This bot never detours to a door -- it routs -- so counting three here would
-- fail a chapter that is working exactly as designed.
scenarios.clear_ch02 = function()
    local booted, why = bootToMap(nil, nil, {strictCheckpoint = true})
    if not booted then return result("FAIL", why or "never reached the ch02 map") end
    pokeFastConfig()
    local start = chapter()
    local function advanced() return chapter() ~= start or procActive(SYM.gProcScr_TitleScreen) end
    local best = {}
    local function snapCharms()
        local d = CH02.deliveredCharms(collectedItems(), CAMPAIGN.CH02_CHARMS)
        if #d > #best then best = d end
    end
    -- Deterministic rout (INSPECT.routCh02). clear_ch02 verifies the win->ending->charm
    -- WIRING, not ch02 balance (that's the human pacing pass + the difficulty gate).
    local rout, t = INSPECT.routCh02(advanced, "clear_ch02", snapCharms)
    if rout == "gameover" then
        shot("clear-ch02-gameover")
        return result("FAIL", string.format("game over on turn %d -- party lost", t))
    end
    local routed = rout == "routed"
    shot("clear-ch02-routed")
    log(string.format("rout=%s; ending the turn to fire the DefeatAll win check", tostring(routed)))
    -- Routed: force the phase-end DefeatAll check, then FINE-GRAINED poll the ending scene so the
    -- charm-gifts (CHECK_ALIVE -> GIVEITEMTO) are captured before the MNC2(0x4) chain reloads into
    -- ch03 (slot 4) and PREP re-picks the convoy/inventory. (Coarse polling skipped the charm window.)
    -- The ch02->ch03 chain (#23) replaced the old dev-placeholder->title landing: the ending now
    -- MNC2s straight into ch03, so we A-mash through it until chapter() == 4 (ch03), not the title.
    if routed then endTurn(nil, advanced) end
    local reachedCh03 = false
    local watchEnding = INSPECT.watch("clear_ch02_ending")
    for _ = 1, TUNE.bootSteps do
        snapCharms()
        if chapter() == CAMPAIGN.HOST.ch03 then reachedCh03 = true; snapCharms(); break end
        if procActive(SYM.gProcScr_TitleScreen) then snapCharms(); break end  -- fallback: chain broken -> old landing
        -- Drive the ending on OBSERVED state rather than an A cadence (#238). The cadence
        -- pressed A every 10 frames whatever was on screen, so it could not tell "this page
        -- is waiting for me" from "this input is being swallowed", and a scene that wedged
        -- just ran the cap out and reported a timeout naming nothing.
        --
        -- advanceBootState, NOT a dialogue-only check: the ch02 -> ch03 chain is not one long
        -- conversation. MNC2(0x4) runs the ending, then the post-chapter SAVE prompt, then
        -- ch03's chapter-intro card -- three different classified input waits. Advancing only
        -- dialogue_wait yielded forever at the save prompt, burned the whole step budget and
        -- reported 2/3 charms on a chapter that had never left slot 3. This is the same
        -- driver reachCh01 uses for the identical hand-off one chapter earlier.
        local observation = observeController()
        local state = controllerState(observation)
        if watchEnding(observation, state) then
            return result("FAIL", "the ch02 ending parked on an unclassified wait (see the snapshot)")
        end
        snapCharms()
        -- The third charm-gift lands on a FULL inventory, so FE8 raises its "which item goes
        -- to the convoy" chooser and the whole chain stops until it is answered. Answering it
        -- is scenario policy -- send whatever is highlighted; the charm reaching the leader OR
        -- the convoy is what this scenario asserts either way. The old A-mash answered this
        -- prompt by ACCIDENT, which is the only reason its "3/3 charms delivered" verdict was
        -- reachable: a blind press was doing load-bearing work nothing had named (#238).
        if state == "send_to_convoy" then
            if not guardedInput("send_item", "A", "the convoy chooser closes", function(after)
                return after.menu == nil or controllerState(after) ~= "send_to_convoy"
            end, 300) then break end
        else
            -- Named `drove`, not `advanced`: this scope already has an advanced() predicate
            -- for "the chapter moved on", and shadowing it with a boolean would make a later
            -- `if advanced() then` read as the check it looks like while calling a boolean.
            local drove = advanceBootState(observation, state)
            if drove == false then break end
            -- nil = a state it has no input for (the map is up mid-scene). Wait it out; the
            -- step budget and the stall watch above bound this, never a tight spin.
            if drove == nil then yield() end
        end
    end
    shot("clear-ch02-ending")
    -- TWO, matching CH02_CHARMS: Glimmerfrost moved into the (1,12) hut on 2026-08-30 and pays
    -- on the visit, so only Mote's and Rime's charms arrive at the ending. The count stayed at
    -- three through that rework, which no longer HAD a third to find -- an assertion no working
    -- build could satisfy.
    log(string.format("charms delivered: %d/%d; reached ch03=%s (chapter=%d)",
        #best, #CAMPAIGN.CH02_CHARMS, tostring(reachedCh03), chapter()))
    if #best < #CAMPAIGN.CH02_CHARMS then
        return result("FAIL", string.format(
            "ch02 charm-gift broken: only %d/%d chwinga charms reached the leader/convoy",
            #best, #CAMPAIGN.CH02_CHARMS)) end
    if not reachedCh03 then
        return result("FAIL", "ch02->ch03 chain broken: ending did not MNC2 into ch03 (slot 4)") end
    result("PASS", "ch02 routed + chained into ch03; both SURVIVOR chwinga charms delivered (CHECK_ALIVE -> GIVEITEMTO)")
end

-- ckpt_ch02intro: stop at the very start of ch02 (slot 3), BEFORE the opening cutscene plays,
-- so recordscene (PT_STATE=ch02intro) can film the title card + Vellynne/chwinga beats.
scenarios.ckpt_ch02intro = function()
    if not reachCh01Map() then return end
    local status = seizeCh01ToCh02()
    if status ~= "won" then return result("FAIL", "ch01 seize failed (" .. status .. ")") end
    if not waitFor(function() return chapter() == CAMPAIGN.HOST.ch02 end, 600) then
        return result("FAIL", "ch02 never began") end
    -- Advance past the title-card transition into the first STABLE opening dialogue beat before
    -- saving -- a state grabbed mid-transition crashes on resume (mGBA exited early). Wait for the
    -- map event engine to be running, then let the scene settle on a dialogue box.
    waitFor(function() return procActive(SYM.ProcScr_StdEventEngine) end, 600)
    wait(180)
    saveState("ch02intro")
    result("PASS", "ch02intro checkpoint saved (ch02 opening, first beat)")
end

-- recordscene: record ANY dialogue cutscene without writing new Lua -- point it at a
-- pre-built save-state + a terminal condition via env vars. run.sh builds the checkpoint
-- named by PT_STATE (builder ckpt_<PT_STATE>) if it's missing/stale. Examples:
--   PT_STATE=ch02intro PT_TAG=intro PT_UNTIL=prep                   tools/playtest/run.sh recordscene
scenarios.recordscene = function()
    -- Config arrives as PLAYTEST_* wrapper globals (run.sh maps PT_* -> PLAYTEST_*), so the
    -- harness reads one place; the wrapper itself takes the JSON knobs from os.getenv.
    local function g(v) return (v ~= nil and v ~= "") and v or nil end
    return recordCutscene({
        state = g(PLAYTEST_STATE),
        tag = g(PLAYTEST_TAG) or "scene",
        until_ = g(PLAYTEST_UNTIL),
        speed = g(PLAYTEST_SPEED),
        maxFrames = tonumber(PLAYTEST_MAXFRAMES or ""),
        shotEvery = tonumber(PLAYTEST_SHOTEVERY or ""),
        pressEvery = tonumber(PLAYTEST_PRESSEVERY or ""),
    })
end

-- marchPartyToward: walk the party at (cx, cy) over up to `turns` player phases, stopping the
-- moment `stop()` goes true. ch04moose's march into the clearing. The move is a REAL move (marchToward drives the game's own movement
-- map and finishes on Wait): an AREA is checked when an action ENDS, so a position poke would
-- never trigger it. Returns true if `stop()` fired, false if the turn budget ran out.
local function marchPartyToward(cx, cy, turns, stop, maxx, maxy)
    for _ = 1, turns do
        INSPECT.settle("phase", 900, true)
        for _, u in BOARD.each("blue") do
            if stop() then return true end
            if u.onField and (u.state & 0x2) == 0 then
                marchToward(u, cx, cy, maxx or 14, maxy or 14)
                INSPECT.settle("phase", 300, true)
            end
        end
        if stop() then return true end
        if runEnemyPhase() ~= "player" then return false end
    end
    return stop()
end

-- ch04moose: the moose-sighting AREA is PLAYER-ONLY, and still fires for the party (#24).
-- Both halves, because the guard's failure modes point opposite ways:
--   1. idle turn 1 -- after the monsters have moved, the moose must NOT have loaded. FE8 polls
--      the Misc list at the end of EVERY unit's action (playerphase.c AND cp_perform.c) and
--      EvCheck0B_AREA reads gActiveUnit with no faction check, so an unguarded AREA over the
--      clearing plays RBG's "After it!" to nobody on turn 1 -- and burns the one-shot.
--   2. then walk a party unit INTO the clearing -- the moose must load, hold, and be gone.
-- The move is a REAL move (moveUnit), not a position poke: the AREA is checked when an action
-- ENDS, so a teleported unit would never trigger it and the test would pass vacuously.
-- Run: PT_HOST_CHAPTER=5 tools/playtest/run.sh ch04moose (needs a CH04BOOT=1 ROM).
scenarios.ch04moose = function()
    local MOOSE_PID = CAMPAIGN.CH04_MOOSE_PID
    local X1, Y1, X2, Y2 = 8, 2, 14, 7   -- CH04_MOOSE_AREA
    local function moose() return BOARD.find("green", MOOSE_PID) end
    if not bootToMap() then return result("FAIL", "never reached the ch04 map") end
    pokeFastConfig()
    if moose() then return result("FAIL", "the moose is on the map at chapter start") end
    INSPECT.settle("event", 900, true)

    -- 1. the negative half: idle a whole turn, monsters move, nobody of ours is in the clearing.
    if runEnemyPhase() ~= "player" then
        shot("ch04moose-no-turn2")
        return result("FAIL", "turn 1 never handed control back")
    end
    if moose() then
        shot("ch04moose-fired-on-enemy-phase")
        return result("FAIL", "the moose beat fired on the ENEMY phase -- the AREA is unguarded")
    end
    log("ch04moose: turn 1's enemy phase did NOT trigger the sighting (guard holds)")

    -- 2. the positive half: MARCH the party into the clearing. marchToward drives the game's
    -- own movement map and finishes on Wait, so this is a real action end (the AREA is checked
    -- when an action ENDS -- a position poke would never trigger it and would pass vacuously).
    -- The clearing is 4+ tiles off the deploy flank, so allow a few turns to close.
    local CX, CY = 11, 4                 -- the clearing's middle
    local function anyoneInClearing()
        for _, u in BOARD.each("blue") do
            if u.onField and u.x >= X1 and u.x <= X2 and u.y >= Y1 and u.y <= Y2 then
                return true
            end
        end
        return false
    end
    -- The march itself is marchPartyToward. The check this scenario adds on top is the one
    -- that makes a non-firing AREA legible: standing IN the clearing with no moose is a real
    -- failure, while merely not having arrived yet is not.
    -- Stop on the MOOSE only, never on "someone is in the clearing": the AREA is polled when an
    -- action ENDS, so a unit standing on the tile is a state the beat has not answered yet, not
    -- a verdict. Stopping there raced the event and failed a chapter that works. The
    -- in-the-clearing check is the DIAGNOSTIC afterwards, once the budget really is spent.
    marchPartyToward(CX, CY, 5, function() return moose() ~= nil end)
    if not moose() and anyoneInClearing() then
        shot("ch04moose-never-fired")
        return result("FAIL",
            "a party unit stands in the clearing and the sighting never fired")
    end
    if not moose() then
        shot("ch04moose-unreachable")
        return result("FAIL", "the party never reached the clearing within the turn budget")
    end
    shot("ch04moose-sighted")
    -- ...and it is uncatchable by design: the beat must not leave it standing there. Poll in
    -- slices with a heartbeat log, so a run that stops here says WHICH kind of stop it was: no
    -- heartbeats at all means the emulator wedged, ticking heartbeats mean the beat really is
    -- leaving the moose standing on the map.
    local cleared = false
    for i = 1, 12 do
        if waitFor(function() return moose() == nil end, 150, true) then cleared = true break end
        log(string.format("ch04moose: moose still on the map %d frames after the sighting", i * 150))
    end
    if not cleared then
        freezeReport("ch04moose-disa")
        shot("ch04moose-still-there")
        return result("FAIL", "the moose loaded but was never DISA'd -- it can be attacked")
    end
    return result("PASS", "the sighting is player-only: skipped the enemy phase, fired for the party")
end

-- ch04Parley(opts) -- drive Marty's Talk on the wolf pack: the chapter's mercy/recruit hook and
-- the switch that picks which ENDING plays. Shared by recordch04parley (which films it) and
-- clear_ch04_parley (which needs the flag set before routing), so semantic Talk selection, re-parking,
-- and the outcome check exist once (#204). Assumes the map is already booted and turn 1 is live.
--   opts.shots  -- frame-tag to screenshot into while the exchange plays; nil films nothing
-- Returns false plus a reason string, or true plus (nil, pack) once Lupin is blue -- where
-- `pack` is { before, after }: the wolves' tiles going into the Talk and coming out of it.
-- The five generic wolves, one pid each (build_campaign.CH04_PACK_PIDS -- #203). They used to
-- share 0xb3, which is exactly why the parley could not convert them one at a time.

-- Where the pack is standing, keyed by pid: { [pid] = {x, y} } over one faction array. One pid
-- per wolf is what makes this readable at all, and it is how the parley's two claims are checked
-- from DATA -- how many came over (count) and that each converted where it stood (tiles).
local function ch04PackTiles(array, slots)
    local at = {}
    for i = 0, slots - 1 do
        local u = unitAt(array, i)
        if u and not isDead(u) and CAMPAIGN.CH04_PACK_PIDS[u.charId] then at[u.charId] = { u.x, u.y } end
    end
    return at
end
local function ch04Parley(opts)
    opts = opts or {}
    local LUPIN, MARTY = CAMPAIGN.CAST.lupin, CAMPAIGN.CAST.marty
    local function redLupin() return red(LUPIN) end
    local function blueLupin() return blue(LUPIN) end
    local function snap() if opts.shots then shot(opts.shots) end end
    INSPECT.settle("event", 900, true)
    -- The pack (and Lupin) only exist from turn 2.
    if turn() < 2 then
        if not endTurn() then return false, "could not end turn 1" end
    end
    if not waitFor(function() return turn() >= 2 and redLupin() ~= nil end, 5400) then
        snap()
        return false, "the wolf pack never arrived on turn 2"
    end
    INSPECT.settle("event", 3600, true)
    local marty = blue(MARTY)
    if not marty then return false, "Marty (0x02) is not deployed -- he owns the Talk" end
    -- Park Marty orthogonally adjacent to Lupin. setMapUnit keeps the engine's tile->unit grid
    -- in sync, so Talk-adjacency reads immediately with no phase cycle (the ch03talk trick) --
    -- the point here is filming the SCENE, not pathing a cavalier across a fog map.
    local lup = redLupin()
    local tx, ty = INSPECT.freeBeside(lup)       -- order E, W, S, N, as before
    local parked = tx ~= nil and INSPECT.place(marty, tx, ty)
    if not parked then return false, "no free tile adjacent to Lupin to park Marty" end
    -- Where the pack stands going IN. Sampled after the parking, before the Talk: no enemy or
    -- green phase runs between here and the conversion, so any tile that changes changed
    -- because of the parley itself.
    local packBefore = ch04PackTiles(SYM.gUnitArrayRed, 24)
    marty = blue(MARTY)
    if not marty or not moveUnit(marty.x, marty.y, marty.x, marty.y) then
        return false, "no live command menu for Marty"
    end
    if not chooseTalk() then return false, "Marty's live command menu did not expose Talk" end
    local _, why = INSPECT.talkUntil(blueLupin, 3600, {tick = function(i)
        if i % 3 == 0 then snap() end
    end})
    if why == "advance" then return false, "parley dialogue input did not advance" end
    if not blueLupin() then
        snap()
        return false, "Lupin never flipped blue (the CUSA did not fire)"
    end
    -- Read the converted pack HERE, while the tiles still mean something: the phase cycle below
    -- hands the greens their own turn, and an aggressive ally that walks off to fight would
    -- look exactly like a wolf the parley had relocated.
    local info = { before = packBefore, after = ch04PackTiles(SYM.gUnitArrayGreen, 20) }
    -- The CUSA changes his FACTION; the standing sprite only redraws to the party palette on a
    -- RefreshUnitSprites (phase transition). Cycle one phase, then linger on the green pack.
    runEnemyPhase()
    for f = 1, 90 do if f % 3 == 0 then snap() end yield() end
    return true, nil, info
end

-- The wolves that came over: live units in the GREEN array wearing a pack pid. Counting the pack
-- by pid rather than counting the whole green array keeps the white moose (a scripted green
-- neutral) out of the tally -- and one pid per wolf is what makes that possible (#203).
local function greenPackCount()
    local n = 0
    for _ in pairs(ch04PackTiles(SYM.gUnitArrayGreen, 20)) do n = n + 1 end   -- gUnitArrayGreen[20]
    return n
end

-- recordch04parley: Marty's Talk on the wolf pack, in motion (#24 Stage 5) -- the chapter's
-- mercy/recruit hook and Marty's secondary signature beat. Films the whole exchange, then the
-- conversion: each surviving Mauthe Doog is CUSN'd GREEN WHERE IT STANDS, and Lupin CUSAs
-- red -> blue. The pack arrives on turn 2, so the lead-up is driven (boot -> prep -> idle
-- turn 1) before the recruiter is parked next to the leader.
--
-- It also ASSERTS the "where it stands" half of #203 from data rather than from the film: the
-- pack's tiles are read before the Talk and again after, and a wolf that moved means the old
-- clear-and-reload is back (it put the pack down on its SPAWN tiles, teleporting it home
-- mid-fight). No enemy phase runs in between, so nothing else can move them.
-- Run: PT_HOST_CHAPTER=5 tools/playtest/run.sh recordch04parley (needs a CH04BOOT=1 ROM).
scenarios.recordch04parley = function()
    if not bootToMap() then return result("FAIL", "never reached the ch04 map") end
    pokeNormalConfig()          -- reading speed: this scenario exists to be WATCHED
    local ok, why, pack = ch04Parley({ shots = "ch04parley" })
    if not ok then return result("FAIL", why) end
    for pid, xy in pairs(pack.before) do
        local now = pack.after[pid]
        if not now then
            return result("FAIL", string.format(
                "wolf 0x%02X was red at (%d,%d) but never arrived in the green array", pid, xy[1], xy[2]))
        end
        log(string.format("  wolf 0x%02X: red (%d,%d) -> green (%d,%d)", pid, xy[1], xy[2], now[1], now[2]))
        if now[1] ~= xy[1] or now[2] ~= xy[2] then
            return result("FAIL", string.format(
                "wolf 0x%02X moved on the parley: (%d,%d) -> (%d,%d). The pack must convert "
                .. "where it stands, not reload onto its spawn tiles", pid, xy[1], xy[2], now[1], now[2]))
        end
    end
    return result("PASS", string.format(
        "parley filmed: Lupin is blue and %d wolves came over green, each on its own tile",
        greenPackCount()))
end

-- ch04packmath: the REGRESSION GATE for "parleying early is the reward" (#203). It began as a
-- question -- does mercy pay the same after you have already shot at the pack? -- and the answer
-- was yes: the old parley DISA'd the generics and LOAD1'd a FIXED five-wolf green table, so the
-- dead wolves came back and shooting first cost nothing. In-place conversion answers it the other
-- way for free: CUSN can only convert wolves that still exist. Kill KILL of them, parley, and the
-- green count must be exactly the number left standing.
-- Run: PT_HOST_CHAPTER=5 tools/playtest/run.sh ch04packmath (needs a CH04BOOT=1 ROM).
scenarios.ch04packmath = function()
    local KILL = 2      -- generic wolves to shoot before talking; Lupin (0x1D) is not one
    if not bootToMap() then return result("FAIL", "never reached the ch04 map") end
    pokeFastConfig()
    INSPECT.settle("event", 6000, true)
    if liftFogOntoTheGrid() == 0 then
        return result("FAIL", "fog lifted but no enemy reached gBmMapUnit")
    end
    -- The pack only exists from turn 2. Wait for LUPIN, not merely for the turn counter: it ticks
    -- the moment the player phase ends, well before the reveal event LOAD1s the wave (waiting on
    -- the counter alone found an empty field).
    if not endTurn() then return result("FAIL", "could not end turn 1") end
    if not waitFor(function()
        return turn() >= 2 and red(CAMPAIGN.CAST.lupin) ~= nil
    end, 5400) then
        return result("FAIL", "the wolf pack never arrived on turn 2")
    end
    INSPECT.settle("event", 3600, true)
    for i, r in BOARD.each("red") do
        if not isDead(r) then
            log(string.format("  red[%02d] char=0x%02X at (%d,%d)%s", i, r.charId, r.x, r.y,
                r.charId == CAMPAIGN.CAST.lupin and "   <- LUPIN" or ""))
        end
    end
    local function packAlive()
        local n = 0
        for _, r in BOARD.each("red") do
            if not isDead(r) and CAMPAIGN.CH04_PACK_PIDS[r.charId] then n = n + 1 end
        end
        return n
    end
    local function firstWolf()
        for _, r in BOARD.each("red") do
            if not isDead(r) and CAMPAIGN.CH04_PACK_PIDS[r.charId] then return r end
        end
        return nil
    end
    local spawned = packAlive()
    log(string.format("ch04packmath: %d generic wolves (one pid each) on the field at turn 2",
        spawned))
    if spawned == 0 then return result("FAIL", "the wolf pack never arrived on turn 2") end
    -- Shoot KILL of them. Marty (the recruiter) is skipped -- he owns the Talk.
    local killed = 0
    for _ = 1, KILL do
        local wolf = firstWolf()
        if not wolf then break end
        for _, r in BOARD.each("red") do
            if not isDead(r) then pokeFrail(r); pokeHarmless(r) end
        end
        wolf = firstWolf()
        for i, u in BOARD.each("blue") do
            if u.onField and (u.state & 0x2) == 0 and u.charId ~= CAMPAIGN.CAST.marty then
                local mn, mx = unitAttackRange(u)
                if mn and mn <= 1 and teleportAdjacentTo(u, { wolf }) then
                    u = unitAt(SYM.gUnitArrayBlue, i)
                    if u and canAttackFromHere(u, mn, mx) and moveUnit(u.x, u.y, u.x, u.y) then
                        local was = packAlive()
                        chooseAttack(u.addr)
                        INSPECT.settle("fight", 600)
                        if packAlive() < was then killed = killed + 1 end
                        break
                    end
                end
            end
        end
    end
    log(string.format("ch04packmath: killed %d of %d generics -- %d left standing before the parley",
        killed, spawned, packAlive()))
    if killed == 0 then return result("FAIL", "could not kill a single pack wolf before the parley") end
    local left = packAlive()
    local ok, why = ch04Parley()
    if not ok then return result("FAIL", "parley after the kills: " .. why) end
    local greens = greenPackCount()
    log(string.format("ch04packmath: %d killed, %d generics left, parley -> %d GREEN allies",
        killed, left, greens))
    shot("ch04packmath")
    -- The gate: the allies you get are the wolves you did not kill. More than that means the
    -- pack is being reloaded from a table again (the #203 defect); fewer means a CUSN is not
    -- landing -- and a CUSN on a wiped slot is EVC_ERROR, so check the guard before the pids.
    if greens ~= left then
        return result("FAIL", string.format(
            "killed %d of %d wolves, %d left standing, but the parley yielded %d green allies "
            .. "-- the ally count must scale with survivors", killed, spawned, left, greens))
    end
    return result("PASS", string.format(
        "killed %d of %d wolves first, then parleyed -> %d green allies: mercy scales with "
        .. "who survived, so talking early is the reward", killed, spawned, greens))
end

-- ch05recruit: the REGRESSION GATE for ch05's two-stage recruit (#25). It exists because the
-- half that is easiest to get wrong produces NO symptom: Basil is LOADed GREEN and flipped BLUE
-- by the opening's own CUSA, and if that CUSA never fires the chapter still boots, still runs
-- PREP, still passes ch05village -- you simply have a green shrub nobody can give an order to,
-- and therefore a Talk that can never happen. `ch05village` cannot see any of that; it exits
-- Preparations with START and walks a different unit to a door.
-- So this asserts the CHAIN, in the order the player experiences it:
--   1. Basil is BLUE and commandable at turn 1        (the opening join CUSA landed)
--   2. Sahnar is RED on the arena at turn 1           (scene 6's LOAD1 landed)
--   3. The eruption still speaks its four boxes       (the turn-2 warning, now Sahnar-free)
--   4. Basil's Talk flips Sahnar BLUE                 (the CHAR entry + MS_Ch05SahnarTalk)
-- Steps 1-2 are the ones with no other witness. Steps 3-4 are ch04Parley's shape with no pack.
-- Step 2 USED TO BE "Sahnar rises RED on turn 2", and it moved with the chapter (#25,
-- 2026-08-14): Ravisin raises her on screen in scene 3 and she LOADs after the prep CALL, so
-- she is on the board before the player ever acts. That also split step 2 from step 3 -- the
-- old loop broke on `turn() >= 2 and redSahnar()`, and with her red from turn 1 that condition
-- is satisfied the instant the counter ticks, BEFORE Ravisin says a word. Left alone this gate
-- would have failed on 0 eruption boxes and blamed the warning.
-- Run: PT_HOST_CHAPTER=6 tools/playtest/run.sh ch05recruit (needs a CH05BOOT=1 ROM).
scenarios.ch05recruit = function(opts)
    local CH05 = dofile(PLAYTEST_DIR .. "/ch05.lua")     -- ch05's shared facts (#314)
    local BASIL, SAHNAR, LUPIN = CH05.PID.BASIL, CH05.PID.SAHNAR, CH05.PID.LUPIN
    -- A-presses the recruit renders to -- now exactly the number of AUTHORED boxes: 16 on the
    -- locked arm, 17 on the substituted one. Nothing pages itself any more, because the wrapper
    -- measures PIXELS at vanilla's own width instead of counting to 29 (`decisions.md` -> "We
    -- wrapped on-map talk at 29 CHARACTERS"). It used to be 21 for BOTH arms -- the locked box 8
    -- paged in two while the substitute was two authored boxes -- and that collision is why
    -- `ARM` below, not this number, is what says which scene actually played.
    -- `opts.lupin` is the ROSTER STATE to put the wolf in before the Talk, and `opts.arm` the
    -- message id that state must produce. Default: no Lupin on the roster at all, which is what
    -- the plain `ch05boot` ROM is (he is not in the boot seed), so the Talk takes its no-Lupin
    -- arm. The two named states are #25's last two owed CHECK_ALIVE cases and ride
    -- `ch05lupinboot`, whose LOAD1 is the only way any of these ROMs gets a Lupin at all.
    opts = opts or {}
    local ARM = opts.arm or CH05.MSG.RECRUIT_NO_LUPIN
    local RECRUIT_BOXES = (ARM == 0x9E8) and 16 or 17
    local function blueBasil() return blue(BASIL) end
    local function redSahnar() return red(SAHNAR) end
    local function blueSahnar() return blue(SAHNAR) end
    if not bootToMap() then return result("FAIL", "never reached the ch05 map") end
    pokeFastConfig()
    INSPECT.settle("event", 6000, true)

    -- 0. The wolf, in whatever roster state this run is about. CHECK_ALIVE reads the ROSTER and
    --    not the field (eventscr.c:3212 -- missing OR US_DEAD gives slot C = 0, while
    --    US_NOT_DEPLOYED is CHECK_DEPLOYED's business alone), so these two pokes are the whole
    --    experiment: a benched Lupin must still take the wolf's arm, a dead one must not.
    if opts.lupin then
        local wolf = blue(LUPIN)
        if not wolf then
            return result("FAIL", "no Lupin on the roster -- this scenario needs the "
                .. "ch05lupinboot ROM, whose LOAD1 is the only thing that puts him there")
        end
        if opts.lupin == "benched" then
            -- Recruited, alive, LEFT AT HOME. ch05 deploys 9 of a 10-unit pool, so this is
            -- ordinary play, and it is exactly where a field-presence test would have failed.
            -- The ROM cannot produce it -- --ch05-lupin LOAD1s him ONTO the map -- so the state
            -- is written here: off the tile grid, off the map, and flagged not-deployed, which
            -- is what a unit the player never placed looks like to both CHECK_ commands.
            -- US_HIDDEN IS NOT OPTIONAL, and leaving it off is not merely untidy:
            -- `RefreshUnitsOnBmMap` (bmmap.c:523) skips a unit on US_HIDDEN and on NOTHING
            -- ELSE, so on the next phase transition it would write this unit's index to
            -- gBmMapUnit[-1][-1] -- off the map array entirely. The engine always sets the
            -- pair (bmio.c:1260 and bmsave.c:417 both write US_HIDDEN | US_NOT_DEPLOYED).
            setMapUnit(wolf.x, wolf.y, 0)
            emu:write8(wolf.addr + 0x10, 0xFF)          -- xPos -1: nowhere on the map
            emu:write8(wolf.addr + 0x11, 0xFF)
            emu:write32(wolf.addr + 0x0C, wolf.state | 8 | 1)  -- US_NOT_DEPLOYED | US_HIDDEN
        elseif opts.lupin == "killed" then
            -- Recruited, then LOST. Collapses onto the no-Lupin arm on purpose: a dead wolf is
            -- no more "out there now, with travelers" than one who was never won.
            -- Same pairing, same reason: without US_HIDDEN the refresh puts the corpse
            -- back on the tile grid at its old position. bmsave.c:414 writes the dead
            -- state as US_HIDDEN | US_DEAD.
            setMapUnit(wolf.x, wolf.y, 0)
            emu:write32(wolf.addr + 0x0C, wolf.state | BOARD.US_DEAD | 1)  -- ... | US_HIDDEN
        else
            return result("FAIL", "unknown lupin state " .. tostring(opts.lupin))
        end
        log(string.format("ch05recruit: Lupin (0x%X) put in the %s state before the Talk",
            LUPIN, opts.lupin))
    end

    -- 1. The join. A GREEN Basil here means the CUSA after CALL(Preparations) did not land --
    --    which is invisible to every other scenario, so name the faction we actually found.
    local basil = blueBasil()
    if not basil then
        local green = BOARD.find("green", BASIL)
        shot("ch05recruit")
        return result("FAIL", green
            and "Basil is still GREEN at turn 1 -- the opening join CUSA never fired, so she "
                .. "takes no orders and the Talk can never happen"
            or "Basil (0x13) is on no unit array at turn 1 -- the green LOAD1 did not run")
    end
    log(string.format("ch05recruit: Basil is BLUE at turn 1 on (%d,%d) -- the opening join landed",
        basil.x, basil.y))

    -- 2. The summon. Sahnar is on the arena tile at TURN 1 -- Ravisin raised her on screen in
    --    scene 3, and scene 6 LOAD1s her after the prep CALL where vanilla LOADs Joshua (#25).
    --    Nothing else witnesses that LOAD1: the chapter boots, PREP runs and every other ch05
    --    scenario passes with an empty arena, and the first symptom would be a Talk with no
    --    target. Her TILE is asserted too, because a Sahnar who exists somewhere else is a
    --    different escort puzzle -- (9,7) is what assert_green_recruit_placement measures.
    local sahnar = redSahnar()
    if not sahnar then
        shot("ch05recruit")
        return result("FAIL", "Sahnar is not RED at turn 1 -- scene 6's LOAD1 never fired, so "
            .. "the arena is empty and the Talk has no target")
    end
    -- Her POST, not her load tile. She rises on the arena (12,6) during scene 6 and walks
    -- straight off it to (9,7) -- the chapter YAML's `walks_to`, and vanilla's own
    -- `MOVE(0x0, CHARACTER_JOSHUA, 9, 7)`. Asserting the load tile here is wrong twice over: it
    -- is not where she stands, and it would PASS in precisely the broken state ch05arena
    -- exists to catch (a duelist squatting on the arena trigger all chapter).
    if sahnar.x ~= 9 or sahnar.y ~= 7 then
        shot("ch05recruit")
        return result("FAIL", string.format(
            "Sahnar is RED on (%d,%d), not her post (9,7) -- %s", sahnar.x, sahnar.y,
            (sahnar.x == 12 and sahnar.y == 6)
                and "she never walked off the arena tile, which locks the arena all chapter"
                or "the escort distance Basil is measured against has moved"))
    end
    log(string.format("ch05recruit: Sahnar is RED on (%d,%d) at turn 1 -- the scene-3 summon "
        .. "put her on the board", sahnar.x, sahnar.y))

    -- 3. The eruption, which no longer carries her. Count the warning's own boxes: reaching
    --    turn 2 never proved the locked text played, and now that Sahnar is red from turn 1 it
    --    proves even less -- there is no unit arrival left to wait on, so the BOXES are the
    --    whole witness. Wait on them, not on the counter (ch04packmath's lesson, restated).
    if not endTurn() then return result("FAIL", "could not end turn 1") end
    local eruptionBoxes = 0
    local _, why = INSPECT.talkUntil(function() return turn() >= 2 and eruptionBoxes >= 4 end, 7200, {
        onBox = function() eruptionBoxes = eruptionBoxes + 1 end,
        label = "eruption dialogue wait clears"})
    if why == "advance" then return result("FAIL", "eruption dialogue input did not advance") end
    if eruptionBoxes ~= 4 then
        shot("ch05recruit")
        return result("FAIL", string.format(
            "eruption warning showed %d boxes, expected the four locked Ravisin boxes",
            eruptionBoxes))
    end
    INSPECT.settle("event", 3600, true)

    -- 4. The Talk. Park Basil orthogonally adjacent (setMapUnit keeps the tile->unit grid in
    --    sync, so adjacency reads with no phase cycle -- the ch03talk/ch04Parley trick); the
    --    point is the recruit landing, not walking a 5-MOV healer across the depression.
    -- Re-read her: the waits above can span an enemy phase, so the handle from the arrival check
    -- is stale by here. A nil deref would abort the scenario with a Lua error instead of the
    -- clean verdict the rest of this function is built to produce.
    local sah = redSahnar()
    if not sah then
        shot("ch05recruit")
        return result("FAIL", "Sahnar left the red array before the Talk -- killed by the AI, "
            .. "or she never settled on the map")
    end
    local tx, ty = INSPECT.freeBeside(sah)
    local parked = tx ~= nil and INSPECT.place(basil, tx, ty)
    if not parked then return result("FAIL", "no free tile adjacent to Sahnar to park Basil") end
    basil = blueBasil()
    if not basil or not moveUnit(basil.x, basil.y, basil.x, basil.y) then
        return result("FAIL", "no live command menu for Basil")
    end
    -- The gate on the RECRUITER, not just the recruit: if the CHAR list named the wrong talker
    -- (or nobody), the menu simply has no Talk and the chapter looks fine until a player tries.
    if not chooseTalk() then
        shot("ch05recruit")
        return result("FAIL", "Basil's live command menu did not expose Talk -- the CHAR entry "
            .. "does not name her as Sahnar's recruiter")
    end
    -- The budget must clear the WHOLE scene. It now shows OUR locked recruit (0x9E8, sixteen
    -- authored boxes that wrap to 21 A-presses) rather than vanilla's 32-box 0x9CC -- while the
    -- CUSA is the last thing MS_Ch05SahnarTalk does, after TEXTEND. The first cut of this loop
    -- capped at 3600 and expired 18 boxes in, then reported "the CUSA did not fire" about a
    -- script that had simply not reached it yet. A LOOP CAP MUST NEVER BE WHAT DECIDES FAILURE
    -- (decisions.md): hence a budget with real headroom AND, below, two distinguishable verdicts.
    local BUDGET, boxes, playedMsg = 20000, 0, nil
    local _, why = INSPECT.talkUntil(blueSahnar, BUDGET, {onBox = function()
        boxes = boxes + 1
        -- WHICH message is on screen, sampled while the FIRST box of the scene is up.
        -- After the scene ends every menu and unit name decodes through the same buffer
        -- and overwrites it, so this cannot be read from the verdict at the bottom.
        playedMsg = playedMsg or INSPECT.activeMsg()
    end})
    if why == "advance" then return result("FAIL", "recruit dialogue input did not advance") end
    if not blueSahnar() then
        shot("ch05recruit")
        -- Still mid-scene means the harness ran out of road; a FINISHED scene with a red Sahnar
        -- is the real defect. Reporting one as the other is how a wiring bug gets invented.
        local running = controllerState() == "dialogue_wait"
            or procActive(SYM.ProcScr_StdEventEngine)
        return result("FAIL", running
            and string.format("the recruit scene was STILL RUNNING after %d frames (%d boxes) "
                .. "-- the budget expired, not the wiring", BUDGET, boxes)
            or string.format("the scene finished (%d boxes) and Sahnar is still RED -- "
                .. "MS_Ch05SahnarTalk's CUSA did not fire", boxes))
    end
    -- 4. WHOSE scene played. The flip above proves the wiring and says nothing about the prose:
    --    a Talk pointed at vanilla's 0x9CC recruits Sahnar just as well, and that is exactly the
    --    bug this chapter shipped with for months -- Hlin Trollbane's bust talking to vanilla
    --    Joshua, with every text decoder green. Box COUNT is the cheapest in-engine witness to
    --    which message id the script actually showed: ours is 21 A-presses, vanilla's is 32.
    log(string.format("ch05recruit: the recruit scene ran %d boxes, message 0x%X",
        boxes, playedMsg or 0))
    if boxes ~= RECRUIT_BOXES then
        shot("ch05recruit")
        return result("FAIL", string.format(
            "the recruit scene ran %d boxes, expected %d -- %s", boxes, RECRUIT_BOXES,
            boxes >= 30 and "that is vanilla's 0x9CC, so the Talk is pointed at the twin's "
                .. "scene again and plays it in Natasha's and Joshua's faces"
                or "the recruit scene changed underneath this gate"))
    end
    -- WHICH ARM. Both arms recruit her and both run 21 boxes, so everything above passes on
    -- either one -- that is the whole hazard #25 names, and a gate that only watched the flip
    -- would be green with the wrong scene on screen. `sActiveMsg` is the only thing here that
    -- can tell 0x9E8 (Basil proves it with the wolf) from 0x9D1 (Basil proves it with herself).
    if playedMsg ~= ARM then
        shot("ch05recruit")
        return result("FAIL", string.format(
            "the Talk played message 0x%X, expected 0x%X -- %s", playedMsg or 0, ARM,
            ARM == 0x9E8
                and "CHECK_ALIVE did not find the wolf on the roster, so a player who WON him "
                    .. "is being told he does not exist"
                or "CHECK_ALIVE found a wolf this run does not have, so the scene proves "
                    .. "itself with a unit the player never recruited"))
    end
    runEnemyPhase()      -- the sprite only repaints to the party palette on a phase transition
    shot("ch05recruit")
    return result("PASS", string.format(
        "Basil joined blue in the opening, Sahnar stood red on the arena from turn 1, the "
        .. "eruption spoke its four, and Basil's Talk brought her over in %d boxes of message "
        .. "0x%X -- the whole ch05 recruit chain, on the arm this roster earns", boxes, playedMsg))
end

-- ch05lupinbenched: RECRUITED, ALIVE, BENCHED -> the wolf's arm (#25). The case that matters
-- most and the last one owed: ch05 deploys 9 of a 10-unit pool, so a player can win Lupin in
-- ch04 and leave him home here in ordinary play. If the Talk asked the FIELD instead of the
-- roster, this run is where that shows -- the player would be told the wolf does not exist by
-- a scene proving its point with him. `eventscr.c` says CHECK_ALIVE cannot see the bench; this
-- is the run that says our build agrees.
-- Run: PT_HOST_CHAPTER=6 tools/playtest/run.sh ch05lupinbenched (needs CH05BOOT=1 CH05LUPIN=1).
scenarios.ch05lupinbenched = function()
    return scenarios.ch05recruit({ lupin = "benched", arm = 0x9E8 })
end

-- ch05lupinkilled: RECRUITED, THEN LOST -> the no-Lupin arm, deliberately (#25). `eventscr.c`
-- writes slot C = 0 for US_DEAD exactly as it does for a unit that was never found, and the
-- prose wants that collapse: a dead wolf is no more "out there now, with travelers" than one
-- the player never won.
-- Run: PT_HOST_CHAPTER=6 tools/playtest/run.sh ch05lupinkilled (needs CH05BOOT=1 CH05LUPIN=1).
scenarios.ch05lupinkilled = function()
    return scenarios.ch05recruit({ lupin = "killed", arm = 0x9D1 })
end

-- ch05escort: Sahnar will not swing at Basil, the way vanilla Joshua will not swing at Natasha
-- (#493). That refusal is AI_A_07's do-not-attack list, which holds a literal character id;
-- `repoint_escort_safe_ai_list` points it at Basil, and test_inject_ch05 proves the SOURCE
-- edit. This proves the ROM obeys it. Two enemy phases, one run:
--   1. Basil is the only blue unit in Sahnar's reach  -> her Killing Edge keeps its uses.
--   2. Control: another blue unit takes Basil's tile  -> the Killing Edge loses a use.
-- The witness is her WEAPON'S USES, not Basil's HP: only Sahnar's own swing spends them, so
-- the other enemies' turns cannot make phase 1 fail or pass. Phase 2 is what keeps phase 1
-- from passing vacuously -- a Sahnar whose AI never acts at all would also "spare" Basil.
-- Run: PT_HOST_CHAPTER=6 tools/playtest/run.sh ch05escort (needs a CH05BOOT=1 ROM).
scenarios.ch05escort = function()
    local CH05 = dofile(PLAYTEST_DIR .. "/ch05.lua")     -- ch05's shared facts (#314)
    local BASIL, SAHNAR = CH05.PID.BASIL, CH05.PID.SAHNAR
    local function edgeUses(u) return ru16(u.addr + 0x1E) >> 8 end   -- items[0]: id | uses<<8
    if not bootToMap() then return result("FAIL", "never reached the ch05 map") end
    pokeFastConfig()
    INSPECT.settle("event", 6000, true)

    local sah, basil = red(SAHNAR), blue(BASIL)
    if not sah then return result("FAIL", "Sahnar is not RED at turn 1") end
    if not basil then return result("FAIL", "Basil is not BLUE at turn 1") end
    local post = { x = sah.x, y = sah.y }
    log(string.format("ch05escort: Sahnar runs AI %d/%d (vanilla Joshua: 7/3)",
        ru8(sah.addr + 0x42), ru8(sah.addr + 0x44)))

    -- Sahnar must be the only enemy who acts, or a raider kills Basil before her turn comes
    -- and the phase proves nothing (the first run of this did exactly that). Every other red
    -- unit gets AI_A_06 (do nothing) and AI_B_03 (never move); Sahnar's own AI is untouched.
    for i = 0, 49 do
        local u = unitAt(SYM.gUnitArrayRed, i)
        if u and u.charId ~= SAHNAR then
            emu:write8(u.addr + 0x42, 0x06)    -- ai1 -> gAiScript_DoNothing
            emu:write8(u.addr + 0x43, 0)       -- ai_a_pc: restart the script
            emu:write8(u.addr + 0x44, 0x03)    -- ai2 -> AiScr_AiB_NeverMove
            emu:write8(u.addr + 0x45, 0)
        end
    end

    -- Put `u` on the first free tile orthogonally adjacent to Sahnar, and refuse to go on if
    -- any OTHER blue unit already stands in her reach (a sword reaches one tile, and her
    -- AI_B_03 never moves): the phase must offer her exactly one target.
    local function parkAdjacent(u)
        -- The reach check reads only on-map neighbours (an off-map one has no grid cell), and
        -- the tile comes from freeBeside, so an off-map neighbour is SKIPPED here as it is
        -- everywhere else, never refused.
        local w, h = mapSize()
        for _, d in ipairs(INSPECT.EWSN) do
            local tx, ty = post.x + d[1], post.y + d[2]
            local idx = BOARD.inMap(tx, ty, w, h) and mapUnitAt(tx, ty) or 0
            if idx ~= 0 and idx < 0x40 and not (tx == u.x and ty == u.y) then
                return nil, string.format("another blue unit already stands at (%d,%d)", tx, ty)
            end
        end
        local sx, sy = INSPECT.freeBeside(post)
        if not sx then return nil, "no free tile adjacent to Sahnar" end
        if not INSPECT.place(u, sx, sy) then return nil, "could not stand the unit beside Sahnar" end
        return { x = sx, y = sy }
    end
    local function moveTo(u, x, y) return INSPECT.place(u, x, y) end

    -- 1. Basil alone in reach.
    local home = { x = basil.x, y = basil.y }
    local spot, why = parkAdjacent(basil)
    if not spot then return result("FAIL", "setup: " .. why) end
    local before = edgeUses(sah)
    log(string.format("ch05escort: Basil parked on (%d,%d) beside Sahnar (%d,%d); Killing Edge "
        .. "at %d uses", spot.x, spot.y, post.x, post.y, before))
    local phase = runEnemyPhase()
    if phase ~= "player" then return result("FAIL", "enemy phase 1 ended in " .. tostring(phase)) end
    sah, basil = red(SAHNAR), blue(BASIL)
    if not sah then return result("FAIL", "Sahnar left the red array during enemy phase 1") end
    if sah.x ~= post.x or sah.y ~= post.y then
        return result("FAIL", string.format("Sahnar moved off her post to (%d,%d)", sah.x, sah.y))
    end
    local after = edgeUses(sah)
    if after ~= before then
        shot("ch05escort")
        return result("FAIL", string.format("Sahnar SWUNG at Basil: Killing Edge %d -> %d uses "
            .. "-- AI_A_07's list does not name our escort", before, after))
    end
    if isDead(basil) then
        return result("FAIL", "Basil died in enemy phase 1 with every other enemy idled -- "
            .. "inconclusive, find who reached her")
    end
    log(string.format("ch05escort: phase 1 -- Sahnar held her Killing Edge at %d uses with Basil "
        .. "beside her", after))

    -- 2. Control: Basil goes home, another blue unit takes her tile.
    if not moveTo(basil, home.x, home.y) then return result("FAIL", "could not send Basil home") end
    -- Not slot 0, the lord: the first run of this control lost her to the Killing Edge and
    -- ended in a game over. The HP poke is so the control survives the crit it is there to
    -- invite; it changes nothing about whether Sahnar picks it.
    local other
    for slot, u in BOARD.each("blue") do
        -- On the field: a benched roster unit is US_HIDDEN | US_NOT_DEPLOYED at (-1,-1).
        if slot >= 1 and u.charId ~= BASIL and u.onField then other = u; break end
    end
    if not other then return result("FAIL", "setup: no second blue unit for the control phase") end
    spot, why = parkAdjacent(other)
    if not spot then return result("FAIL", "setup (control): " .. why) end
    emu:write8(other.addr + 0x12, 80); emu:write8(other.addr + 0x13, 80)   -- maxHP, curHP
    phase = runEnemyPhase()
    if phase ~= "player" then return result("FAIL", "enemy phase 2 ended in " .. tostring(phase)) end
    sah = red(SAHNAR)
    if not sah then return result("FAIL", "Sahnar left the red array during enemy phase 2") end
    local control = edgeUses(sah)
    if control >= after then
        shot("ch05escort")
        return result("FAIL", string.format("control: Sahnar did not swing at unit 0x%X either "
            .. "(Killing Edge still %d uses) -- phase 1 proved nothing", other.charId, control))
    end
    return result("PASS", string.format("Sahnar spared Basil (Killing Edge held at %d uses) and "
        .. "struck unit 0x%X when it took Basil's place (%d -> %d)", after, other.charId,
        after, control))
end

-- THE VISIT HELPERS (one table, not five locals: a top-level local spends harness.lua's
-- shared 200-local budget, #327).
local VISIT = {}

-- A visit is a unit standing on a tile and using it -- a village door, an
-- Armory or Vendor, the Arena, a unit to Talk to from that tile. `VISIT.place` stands the unit
-- there, `VISIT.open` also takes the tile's command, `VISIT.run` also plays the event out,
-- `VISIT.shop` opens an Armory/Vendor and reads its stock.
--
-- VISIT.place: stand a unit on the tile it will use, skipping the walk. Keeps the engine's
-- tile->unit grid in sync, so the command check reads the new position at once (the
-- ch03talk/parley trick). Reads the unit's position LIVE: a scenario that places the same unit
-- twice holds a table whose x/y went stale.
function VISIT.place(u, x, y) return INSPECT.place(u, x, y) end

-- Take one command off the unit menu by its semantic name ("visit", "armory", "vendor").
function VISIT.command(semantic)
    return function()
        if not selectSemantic(semantic, semantic .. " starts the site's own proc", function(after)
            return after.menu == nil
        end, 600) then return false, "live command menu did not expose " .. semantic end
        return true
    end
end

-- VISIT.open: stand an unexhausted blue unit on the tile and take its command, stopping the
-- moment the tile's own proc starts. One opener for every visit, so the picking and placing
-- cannot drift between villages, shops and talks. Split from the dialogue-advancing half so the
-- RECORDER can own the filmed part: `VISIT.open` is the unfilmed walk-in (a `pre`).
-- Returns ok, reason.
-- `choose` (optional) replaces the Visit command: `talk` passes a Talk (ch06's hulls),
-- `VISIT.shop` an Armory or Vendor.
function VISIT.open(x, y, choose)
    local u
    for _, c in BOARD.each("blue") do
        -- On the field, not merely alive (`onField`, as every other scan asks): a capped chapter
        -- leaves party members off it at x = -1, where parking one writes outside the grid row,
        -- and a rescued unit is carried, not standing on a tile. 0x2 = US_UNSELECTABLE (acted).
        if c.onField and (c.state & 0x2) == 0 then
            u = c break
        end
    end
    if not u then return false, "no unexhausted deployed blue unit to send" end
    if not VISIT.place(u, x, y) then return false, "could not stand the unit on the site" end
    if not cursorTo(x, y) then return false, "cursor could not reach the site" end
    if not moveUnit(x, y, x, y) then
        return false, "could not select the unit standing on the site"
    end
    return (choose or VISIT.command("visit"))()
end

-- Walk in, then advance the line to its end. Shared by ch04's two villages (#205, #24): the
-- doors differ only in what SETTLES them -- an item in the party's hands for the axe village, a
-- closed door for the cottage whose reward is its line -- so `done` is the caller's
-- postcondition and this owns only the getting-there.
-- Returns ok, reason, spoke (whether the visit actually opened a text box at all).
-- `onBox` (optional) fires each time a box is up and WAITING, before the A that clears it --
-- the only moment the line and the speaker's face are both on screen. Review captures need it:
-- a shot taken after the visit returns catches the map, because `done` fires when the ITEM
-- lands and the box is long gone by then.
function VISIT.run(x, y, done, onBox, choose)
    local ok, why = VISIT.open(x, y, choose)
    if not ok then return false, why end
    local spoke = false
    local _, stopped = INSPECT.talkUntil(done, 3600, {onBox = function()
        spoke = true
        if onBox then onBox() end
    end})
    if stopped == "advance" then return false, "village dialogue input did not advance" end
    return true, nil, spoke
end

-- Open the Armory or Vendor on (x, y) and read what it stocks, from the live shop proc
-- (ProcShop.shopItems at +0x30, bmshop.h), then leave it. Returns ok, reason, {item ids}.
-- The stock comes off the proc the command started, so a shop wired to the wrong list, or a
-- tile whose command opens nothing, fails here rather than in a playtest.
function VISIT.shop(x, y, kind)
    local ok, why = VISIT.open(x, y, VISIT.command(kind))
    if not ok then return false, why end
    local proc
    if not waitFor(function()
        proc = PROCS.find(SYM.gProcScr_Shop)
        return proc ~= nil
    end, 600) then return false, kind .. " command started no shop" end
    local stock = {}
    for i = 0, 19 do
        local id = ru16(proc + 0x30 + i * 2) & 0xFF
        if id == 0 then break end
        stock[#stock + 1] = id
    end
    -- Leave: B through the greeting, the buy/sell choice and the farewell line.
    for _ = 1, 60 do
        if not procActive(SYM.gProcScr_Shop) then break end
        press(K.B)
        wait(16)
    end
    if procActive(SYM.gProcScr_Shop) then return false, "the shop never closed on B", stock end
    -- Leaving a shop hands back the unit's command menu, not the map: back out of it too, or
    -- the next step waits forever for player control (ch05shops' Vendor, after its Armory).
    for _ = 1, 20 do
        if controllerState() == "player_map_idle" then break end
        press(K.B)
        wait(12)
    end
    if controllerState() ~= "player_map_idle" then
        return false, "the map never came back after the shop closed", stock
    end
    return true, nil, stock
end

-- ch05arena (#264): the active onboarding ledger claims a tutorial on the real arena tile.
-- Park the leader one step away, take the engine's real move+Wait path onto (12,6), and count
-- the six authored pages. Then step off and back on during the same turn (manually clearing its
-- acted/moved bits between legal actions) to prove EVFLAG_TMP(13) makes it one-shot. Run:
-- PT_HOST_CHAPTER=6 tools/playtest/run.sh ch05arena (needs a CH05BOOT=1 ROM).
scenarios.ch05arena = function()
    local ARENA_X, ARENA_Y, GUARD, REARM_MASK = 12, 6, 13, 0x42
    if not bootToMap() then return result("FAIL", "never reached the ch05 map") end
    pokeFastConfig()
    if not INSPECT.settle("idle", 6000, true) then
        return result("FAIL", "ch05 never settled at player control")
    end
    if eventFlag(GUARD) then
        return result("FAIL", "arena tutorial guard 13 is already set before the tile is entered")
    end
    -- The arena tile must be EMPTY, and since #25 that is a live risk rather than bookkeeping:
    -- Sahnar LOADs on (12,6) in scene 6 and walks off to her post. If that MOVE is ever dropped
    -- again she stands here for the whole chapter, the AREA(12,6,12,6) trigger can never fire,
    -- and the arena is unreachable -- which is what this check now catches on its own.
    local squatter = mapUnitAt(ARENA_X, ARENA_Y)
    if squatter ~= 0 then
        return result("FAIL", string.format(
            "arena tile (12,6) is occupied (grid %d) -- most likely Sahnar never walked off it "
            .. "after her scene-6 LOAD1, which locks the arena for the whole chapter", squatter))
    end
    local hero = blue(0x01)
    if not hero then return result("FAIL", "leader (0x01) is not deployed") end
    if not VISIT.place(hero, ARENA_X, ARENA_Y) then
        return result("FAIL", "could not stand the leader on the arena tile")
    end
    if not cursorTo(ARENA_X, ARENA_Y)
        or not guardedInput("select_unit", "A", "arena staging reach map is generated", function(after)
            return controllerState(after) == "unit_selected"
        end, 120) then
        return result("FAIL", "could not generate the arena staging reach map")
    end
    local fromX, fromY
    for _, d in ipairs({ { -1, 0 }, { 1, 0 }, { 0, -1 }, { 0, 1 } }) do
        local x, y = ARENA_X + d[1], ARENA_Y + d[2]
        if mapUnitAt(x, y) == 0 and reachCost(x, y) < 120 then
            fromX, fromY = x, y; break
        end
    end
    if not guardedInput("cancel_selection", "B", "arena staging selection returns to the map",
        function(after) return controllerState(after) == "player_map_idle" end, 120) then
        return result("FAIL", "could not close the arena staging reach map")
    end
    if not fromX then return result("FAIL", "no reachable empty tile beside the arena") end
    if not VISIT.place(hero, fromX, fromY) then
        return result("FAIL", "could not stand the leader beside the arena")
    end
    -- Raw placement updates the unit/grid but not FE8's standing-map-sprite pool. Make the
    -- engine select and cancel the staged unit once so PlayerPhase's normal cancel path calls
    -- RefreshUnitSprites before the proof frame; otherwise the old SMS and the live MU can both
    -- be drawn and make one Braulo look like two.
    if not cursorTo(fromX, fromY)
        or not guardedInput("select_unit", "A", "staged unit enters the live reach map",
            function(after) return controllerState(after) == "unit_selected" end, 120)
        or not guardedInput("cancel_selection", "B", "staged unit refreshes back to the map",
            function(after) return controllerState(after) == "player_map_idle" end, 120) then
        return result("FAIL", "could not refresh the arena staging placement through PlayerPhase")
    end

    if not moveUnit(fromX, fromY, ARENA_X, ARENA_Y) or not chooseWait() then
        return result("FAIL", "could not take the live move+Wait path onto the arena")
    end
    local pages = 0
    for _ = 1, 3600 do
        local state = controllerState()
        if state == "dialogue_wait" then
            pages = pages + 1
            if pages == 1 then
                INSPECT.units("ch05arena-tutorial")
                shot("ch05arena")
            end
            if not INSPECT.advanceDialogue(120, "arena tutorial page advances") then
                return result("FAIL", "arena tutorial dialogue did not advance")
            end
        elseif eventFlag(GUARD) and not procActive(SYM.ProcScr_StdEventEngine)
            and state == "player_map_idle" then
            break
        else
            yield()
        end
    end
    if pages ~= 6 then
        return result("FAIL", string.format(
            "arena tile fired %d tutorial pages, expected the locked 1+5 anatomy", pages))
    end
    if not eventFlag(GUARD) then
        return result("FAIL", "arena tutorial finished but EVFLAG_TMP(13) stayed unset")
    end
    wait(20)
    shot("ch05arena-after-tutorial")

    -- Re-arm only this unit so we can exercise the same tile twice without advancing to turn 2,
    -- when Sahnar legitimately occupies it. Every move still goes through FE8's live command menu.
    hero = blue(0x01)
    -- Wait sets both US_UNSELECTABLE (0x02) and US_HAS_MOVED (0x40). Clear both: clearing only
    -- the former makes the unit selectable but leaves every destination outside its own tile.
    emu:write32(hero.addr + 0x0C, hero.state & (~REARM_MASK))
    if not moveUnit(ARENA_X, ARENA_Y, fromX, fromY) or not chooseWait() then
        return result("FAIL", "could not step off the arena for the replay check")
    end
    waitFor(function() return controllerState() == "player_map_idle" end, 600, true)
    hero = blue(0x01)
    emu:write32(hero.addr + 0x0C, hero.state & (~REARM_MASK))
    if not moveUnit(fromX, fromY, ARENA_X, ARENA_Y) or not chooseWait() then
        return result("FAIL", "could not step back onto the arena for the replay check")
    end
    local replayed = false
    for _ = 1, 300 do
        if controllerState() == "dialogue_wait" then replayed = true; break end
        if controllerState() == "player_map_idle"
            and not procActive(SYM.ProcScr_StdEventEngine) then break end
        yield()
    end
    if replayed then
        return result("FAIL", "arena tutorial replayed after EVFLAG_TMP(13) was set")
    end

    -- Now exercise the tile's real command rather than stopping at the onboarding event. FE8's
    -- Arena command is only offered before a unit moves, so re-arm Braulo in place. Seed enough
    -- money to accept whatever matchup vanilla generates, then prove the accepted wager is
    -- deducted and a live opponent is built before the instructions page appears.
    hero = blue(0x01)
    emu:write32(hero.addr + 0x0C, hero.state & (~REARM_MASK))
    local beforeGold = 5000
    emu:write32(SYM.gPlaySt + 0x08, beforeGold)
    pokeAnimsOn()
    if not moveUnit(ARENA_X, ARENA_Y, ARENA_X, ARENA_Y) then
        return result("FAIL", "could not open Braulo's command menu on the arena")
    end
    if not selectSemantic("arena", "Arena opens its welcome dialogue", function(after)
        return controllerState(after) == "dialogue_wait"
    end, 600) then
        return result("FAIL", "the live arena tile offered no Arena command")
    end
    -- Presentation proof (#265), on the same real Arena flow as the wager assertions below.
    -- The cold campaign palette occupies BG banks 12..15. One distinctive anchor per bank
    -- proves all four generated banks reached palette RAM; the screenshot remains the visual
    -- review artifact. FaceProc.faceId (+0x3E, include/face.h) proves the visible attendant is
    -- the chapter override dressed onto Glen (FID 0x4B), not vanilla's human FID 0x67.
    -- Like the combat anchors below, half of these are VANILLA on purpose. The welcome screen
    -- changes only its weather and its awnings; the coliseum's warm sandstone is deliberately
    -- untouched, and an earlier pass that cooled the whole building held luminance perfectly
    -- while crushing the stone's saturation, so only a "this stayed vanilla" assertion catches
    -- it. Banks 12..15 (uiarena.c: ApplyPalettes(..., 0xC, 4)).
    local paletteAnchors = {
        { bank = 15, index = 3, want = 0x779B, what = "overcast sky" },
        { bank = 13, index = 4, want = 0x3127, what = "blue awning" },
        { bank = 12, index = 12, want = 0x3F19, what = "VANILLA sandstone" },
        { bank = 12, index = 13, want = 0x194B, what = "VANILLA stone shadow" },
        { bank = 12, index = 3, want = 0x4B9D, what = "VANILLA bright stone" },
    }
    for _, anchor in ipairs(paletteAnchors) do
        local got = ru16(0x05000000 + anchor.bank * 32 + anchor.index * 2)
        if got ~= anchor.want then
            return result("FAIL", string.format(
                "Arena welcome %s (bank %d idx %d) was 0x%04X, expected 0x%04X",
                anchor.what, anchor.bank, anchor.index, got, anchor.want))
        end
    end
    local skeletonFace = false
    for slot = 0, 3 do
        local face = ru32(SYM.gFaces + slot * 4)
        if face ~= 0 and ru16(face + 0x3E) == 0x4B then skeletonFace = true break end
    end
    if not skeletonFace then
        return result("FAIL", "Arena welcome opened without the Ch05 skeleton face FID 0x4B")
    end
    shot("ch05arena-welcome")
    if ru32(SYM.gArenaState) ~= hero.addr then
        return result("FAIL", "Arena command opened without binding Braulo as the entrant")
    end
    local wager = ru16(SYM.gArenaState + 0x08)
    if wager <= 0 or wager > beforeGold then
        return result("FAIL", string.format("arena generated unusable wager %d", wager))
    end
    if not INSPECT.advanceDialogue(300, "welcome advances to the live wager choice",
        function(after) return controllerState(after) == "yes_no_choice" end) then
        return result("FAIL", "arena welcome never reached its wager choice")
    end
    shot("ch05arena-wager")
    if not selectSemantic("answer_yes", "accepting the wager shows opponent instructions",
        function(after) return controllerState(after) == "dialogue_wait" end, 300) then
        return result("FAIL", "could not accept the arena wager")
    end
    if ru32(SYM.gPlaySt + 0x08) ~= beforeGold - wager then
        return result("FAIL", string.format(
            "accepted wager %d but gold changed %d -> %d", wager, beforeGold,
            ru32(SYM.gPlaySt + 0x08)))
    end
    if ru32(SYM.gArenaState + 0x04) == 0 then
        return result("FAIL", "accepted wager reached instructions without a generated opponent")
    end
    shot("ch05arena-opponent")
    -- TWO blocking dialogue pages stand between the accepted wager and the fight:
    -- ArenaUi_InstructionsDialogue (0x8D5) then ArenaUi_GoodLuckDialogue (0x8D3), both
    -- PROC_CALLs of gProcScr_ArenaUiMain before ArenaUi_StartArenaBattle (src/uiarena.c).
    -- So COUNT them, one guarded press per page, same as the tutorial loop above (#269).
    -- The predecessor sent a single press on a 1800-frame budget and reached combat only
    -- through guardedInput's lost-input re-press -- a pass by accident, and #255 is about
    -- to start caching passes. Pressing three times in a row does not work either: between
    -- the pages the talk proc is still PRINTING, there is no TalkWaitForInput to advance,
    -- and the classifier correctly reads `transition`. Waiting for each page to reach its
    -- own input wait is what makes each press guarded. `arenaTrail` records every state
    -- change across the whole stretch, so if this ever fails the log already carries the
    -- anatomy and nobody has to spend a second run to see it.
    -- The trail compares STRINGS, and `arenaLast` starts at `false` rather than nil, because
    -- classify() returns nil for a state it has no rule for -- and an UNCLASSIFIED park right
    -- after a press is exactly the #232/#241 failure this trail exists to name. Comparing raw
    -- values would make `nil ~= nil` false and drop it silently, logging a trail that stops
    -- before the press and a FAIL naming nothing.
    local arenaPages, arenaTrail, arenaLast, arenaFought = 0, {}, false, false
    for _ = 1, 3600 do
        local observation = observeController()
        local state = controllerState(observation)
        local seen = tostring(state)
        if seen ~= arenaLast then
            arenaLast = seen
            arenaTrail[#arenaTrail + 1] = string.format("%s(%s)", seen,
                tostring(Controller.explain(observation).detail))
        end
        if observation.procs.battle then arenaFought = true break end
        if state == "dialogue_wait" then
            arenaPages = arenaPages + 1
            if not INSPECT.advanceDialogue(300, string.format(
                "Arena dialogue page %d advances toward combat", arenaPages)) then
                log("ARENA TRAIL: " .. table.concat(arenaTrail, " -> "))
                return result("FAIL", string.format(
                    "Arena dialogue page %d refused to advance toward combat", arenaPages))
            end
            arenaLast = false       -- re-record whatever the press landed in, nil included
        else
            yield()
        end
    end
    log("ARENA TRAIL: " .. table.concat(arenaTrail, " -> "))
    if not arenaFought then
        return result("FAIL", string.format(
            "accepted Arena wager never launched its battle (advanced %d pages)", arenaPages))
    end
    if arenaPages ~= 2 then
        return result("FAIL", string.format(
            "Arena ran %d dialogue pages between the accepted wager and the fight, expected the 2 authored (0x8D5, 0x8D3)",
            arenaPages))
    end
    -- The special Arena image owns the ENTIRE visible coliseum, floor included, in BG banks
    -- 6..9. Arena mode skips the normal terrain-platform loader (EfxClearScreenFx clears BG2),
    -- so these are the only combat-background palettes that can prove the winter treatment.
    -- Observe them while gProc_ekrBattle is live; shootCombatFrames returns after combat and
    -- the palette would already be restored.
    --
    -- HALF OF THESE ANCHORS ARE VANILLA ON PURPOSE. The first attempt at this feature was a
    -- cold ramp across all 64 words per phase; it passed every data check and was rejected on
    -- sight because the coliseum's stone, wood, gold and crowd went with it. Proving only that
    -- the new colours arrived would have proved that pass correct too. The floor and the
    -- banners must change, and everything else must NOT -- so the scenario reads both.
    -- All three phases share these words, so the ten-frame cycle cannot make them flicker.
    local combatPaletteAnchors = {
        { bank = 9, index = 3, want = 0x7FFF, what = "snow floor" },
        { bank = 8, index = 8, want = 0x45A9, what = "blue banner" },
        { bank = 7, index = 5, want = 0x473D, what = "VANILLA crowd gold" },
        { bank = 6, index = 5, want = 0x4AD8, what = "VANILLA upper stone" },
        { bank = 9, index = 15, want = 0x292A, what = "VANILLA pillar grey" },
    }
    local combatPaletteReady = false
    for _ = 1, 240 do
        local allWinter = true
        for _, anchor in ipairs(combatPaletteAnchors) do
            local got = ru16(0x05000000 + anchor.bank * 32 + anchor.index * 2)
            if got ~= anchor.want then allWinter = false break end
        end
        if allWinter then combatPaletteReady = true break end
        yield()
    end
    if not combatPaletteReady then
        for _, anchor in ipairs(combatPaletteAnchors) do
            local got = ru16(0x05000000 + anchor.bank * 32 + anchor.index * 2)
            if got ~= anchor.want then
                return result("FAIL", string.format(
                    "Arena combat BG %s (bank %d idx %d) was 0x%04X, expected 0x%04X",
                    anchor.what, anchor.bank, anchor.index, got, anchor.want))
            end
        end
        return result("FAIL", "Arena combat BG palettes never reached their winter state")
    end
    if not shootCombatFrames("ch05arena-combat") then
        return result("FAIL", "Arena battle launched without a capturable full animation")
    end
    return result("PASS", string.format(
        "arena (12,6) taught once, blocked replay, loaded winter palette + skeleton, accepted %dG, generated its opponent, and entered combat",
        wager))
end

-- ch05crest (#25): the other half of the race -- saving all four PAYS OUT. Vanilla Ch5 gates a
-- Guiding Ring on four CHECK_EVENTIDs at its ending and hands it to the player leader, outside
-- the Village macro, because no single tile knows about the other three. ch05 awarded nothing at
-- all while its YAML claimed the payout was "wired at inject_ch05".
--
-- The boss kill parks Ravisin next to a blue unit and pokes her frail (
-- strike) rather than routed: DefeatBoss means exactly one death has to land, and this scenario
-- is about the PAYOUT wiring, not about whether the fight is winnable.
-- Run: PT_HOST_CHAPTER=6 tools/playtest/run.sh ch05crest (needs a CH05BOOT=1 ROM).
scenarios.ch05crest = function()
    -- ch05's shared facts, from the chapter's own chunk (#314). Function-scoped, so it
    -- costs harness.lua no top-level local slot. The four sites were typed here AND in
    -- ch05reliquaries before the chapter owned them.
    local CH05 = dofile(PLAYTEST_DIR .. "/ch05.lua")
    local SITES = CH05.RELIQUARIES
    local RAVISIN, GUIDING_RING = CH05.PID.RAVISIN, CH05.REWARD.GUIDING_RING
    if not bootToMap() then return result("FAIL", "never reached the ch05 map") end
    pokeFastConfig()
    -- Take the tomb's teeth out for the duration. Saving all four sites scatters four units to
    -- four corners of a map holding sixteen guardians plus the waves, and the first run died to
    -- an enemy phase on turn 1 -- the party wiped, the game reached the title, and the scenario
    -- reported "Ravisin is not in the red array", which is a true statement about a chapter that
    -- was already over. This proves the PAYOUT WIRING, not that the race is survivable; whether
    -- it is belongs to `make difficulty` and the human pass. Same class of shortcut as
    -- clear_ch04's pokeHarmless, and it has to be re-applied because waves keep arriving.
    local function disarmTheTomb()
        for i = 0, 49 do
            local r = unitAt(SYM.gUnitArrayRed, i)
            if r and not isDead(r) then pokeHarmless(r) end
        end
    end
    local function heldRing()
        for _, got in ipairs(collectedItems()) do
            if got == GUIDING_RING then return true end
        end
        return false
    end
    local function settle()
        return INSPECT.settle("idle", 3000, true)
    end
    INSPECT.settle("event", 6000, true)
    -- Save all four. Raiders are on the board now, so this is a race the scenario has to WIN;
    -- if a site falls first its flag never sets and the payout is correctly withheld, which
    -- would read here as a failure to visit rather than as a payout bug.
    for _, site in ipairs(SITES) do
        if not settle() then
            return result("FAIL", "the map never returned to player control before " .. site.name)
        end
        disarmTheTomb()
        local ok, why = VISIT.run(site.x, site.y, function()
            return eventFlag(site.flag)
        end)
        if not ok then
            return result("FAIL", string.format("%s (%d,%d): %s", site.name, site.x, site.y, why))
        end
    end
    for _, site in ipairs(SITES) do
        if not eventFlag(site.flag) then
            return result("FAIL", string.format(
                "%s was visited but event id %d never set -- the Village macro is still on "
                .. "flag 0, so the payout can never count it", site.name, site.flag))
        end
    end
    log("ch05crest: all four reliquaries saved; killing Ravisin for the ending")
    -- She has to be ON THE MAP for any of this to mean anything, and that is asserted ONCE, here,
    -- while the chapter is definitely still live. Inside the loop a missing Ravisin means the
    -- opposite thing -- she died and the map tore down -- and conflating the two is what made the
    -- first run report a setup error for a chapter it had already won.
    if red(RAVISIN) == nil then
        return result("FAIL", "Ravisin (pid 0xb8) is not in the red array")
    end
    -- Kill the boss: park her beside a live blue unit so chooseAttack
    -- cannot pick a nearer target by mistake, and re-frail her each attempt in case of a whiff.
    for t = 1, 4 do
        local boss = red(RAVISIN)
        if isDead(boss) or eventFlag(2) or heldRing() then break end   -- isDead(nil) is true
        disarmTheTomb()
        -- US_HIDDEN as well as US_UNSELECTABLE, and the extra bit is the whole lesson. Every
        -- other scenario picks a mover with `state & 0x2` alone, which is right when the party
        -- is standing still. Here the LAST village visit is still running when we go looking:
        -- TILE_COMMAND_VISIT hides the visitor and writes its character number into gBmMapUnit
        -- (eventinfo.c), so that unit is on the grid and in the array and cannot be selected.
        -- Pressing A on it is an illegal input, which fails the run even though the payout it
        -- was driving toward lands correctly -- exactly what the first two runs reported.
        -- ...and they need an equipped MELEE WEAPON, or parking the boss next to them proves
        -- nothing: unitAttackRange returns nil for a staff, and ch05 deploys two healers.
        local hero, hmin, hmax = nil, nil, nil
        for _, u in BOARD.each("blue") do
            if not isDead(u) and (u.state & 0x3) == 0 and mapUnitAt(u.x, u.y) ~= 0 then
                local mn, mx = unitAttackRange(u)
                if mn and mn <= 1 and mx >= 1 then hero, hmin, hmax = u, mn, mx; break end
            end
        end
        if hero == nil then
            return result("FAIL", "no selectable blue unit with a melee weapon left to strike the boss")
        end
        pokeFrail(boss)
        boss = red(RAVISIN)
        local tx, ty = INSPECT.freeBeside(hero)
        if not (tx and INSPECT.place(boss, tx, ty)) then
            return result("FAIL", "no free tile beside a blue unit to park Ravisin")
        end
        hero = blue(hero.charId) or hero        -- re-read: parking rewrote the grid around them
        -- The engine's GRID, not our arithmetic, decides whether row 0 of the command menu is
        -- Attack (#204). Pressing it anyway opens Item and Uses a vulnerary at full HP, which
        -- is both an illegal input and a wasted turn.
        if not canAttackFromHere(hero, hmin, hmax) then
            log(string.format("ch05crest: attempt %d -- Ravisin parked at (%d,%d) is not in "
                .. "[%d,%d] of the striker on (%d,%d) per gBmMapUnit; not pressing Attack",
                t, red(RAVISIN) and red(RAVISIN).x or -1, red(RAVISIN) and red(RAVISIN).y or -1,
                hmin, hmax, hero.x, hero.y))
        elseif moveUnit(hero.x, hero.y, hero.x, hero.y) then
            -- The second exit is not optional here. Ravisin's death IS the win (DefeatBoss on
            -- her flagged defeat quote), so the ending starts on the killing blow and the actor
            -- is never greyed out -- chooseAttack's default combat wait would sit there until it
            -- timed out, and fail the run for the thing it was trying to cause.
            chooseAttack(hero.addr, function() return eventFlag(2) or heldRing() end)
        end
        if isDead(red(RAVISIN)) or eventFlag(2) or heldRing() then break end
        log(string.format("ch05crest: Ravisin survived attempt %d; running the enemy phase", t))
        if runEnemyPhase() == "gameover" then
            return result("FAIL", "the party died before Ravisin did")
        end
    end
    if not (isDead(red(RAVISIN)) or eventFlag(2) or heldRing()) then
        shot("ch05crest-boss-alive")
        return result("FAIL", "could not kill Ravisin in 4 attempts")
    end
    -- The ring lands DURING the ending -- GIVEITEMTO runs three commands in, well before the dev
    -- placeholder's MNTS wipes the unit arrays for the title -- so poll for it from the moment
    -- she falls rather than reading the party once at the end.
    local paid = heldRing() or waitFor(heldRing, 5400, true)
    shot("ch05crest")
    if not paid then
        return result("FAIL", "all four reliquaries survived and Ravisin fell, but no Guiding "
            .. "Ring reached the party -- the save-all payout never ran")
    end
    return result("PASS", "all four reliquaries saved -> the ending paid out its Guiding Ring")
end

-- ch04cottage (#24): the SECOND village at (1,11), whose reward is its line.
-- The shipped bug was not a bad reward, it was NO VISIT: the tile was visitable-capable but had
-- no Location entry, and FE8 runs the village off that event -- so the player saw a cottage they
-- could not enter. An item check cannot settle this one, so the evidence is the door itself:
-- FE8 flips a visited village to TERRAIN_VILLAGE_CLOSED via the chapter's MapChange, which only
-- happens if the Visit was offered AND its event ran to the end. The line having actually opened
-- a text box is asserted separately, or a wired-but-empty message would pass on the door alone.
-- Run: PT_HOST_CHAPTER=5 tools/playtest/run.sh ch04cottage (needs a CH04BOOT=1 ROM).
scenarios.ch04cottage = function()
    local DOOR_X, DOOR_Y = 1, 11
    local VILLAGE_REGULAR, VILLAGE_CLOSED = 0x03, 0x04
    if not bootToMap() then return result("FAIL", "never reached the ch04 map") end
    pokeFastConfig()
    INSPECT.settle("event", 6000, true)
    local before = terrainAt(DOOR_X, DOOR_Y)
    log(string.format("ch04cottage: door (%d,%d) terrain=0x%02X before visiting",
        DOOR_X, DOOR_Y, before))
    if before ~= VILLAGE_REGULAR then
        return result("FAIL", string.format(
            "(%d,%d) is terrain 0x%02X, not a visitable village (0x%02X) -- FE8 gates the Visit "
            .. "menu item on the TERRAIN before it ever consults the location event (bmmenu.c)",
            DOOR_X, DOOR_Y, before, VILLAGE_REGULAR))
    end
    local ok, why, spoke = VISIT.run(DOOR_X, DOOR_Y, function()
        return terrainAt(DOOR_X, DOOR_Y) == VILLAGE_CLOSED
    end)
    if not ok then return result("FAIL", why) end
    shot("ch04cottage")
    local after = terrainAt(DOOR_X, DOOR_Y)
    if after ~= VILLAGE_CLOSED then
        return result("FAIL", string.format(
            "visited (%d,%d) but its terrain is still 0x%02X, not a closed village (0x%02X) -- "
            .. "the visit event never ran to the end", DOOR_X, DOOR_Y, after, VILLAGE_CLOSED))
    end
    if not spoke then
        return result("FAIL", string.format(
            "the door at (%d,%d) closed but no text box ever opened -- the village is wired to "
            .. "an empty message", DOOR_X, DOOR_Y))
    end
    return result("PASS", string.format(
        "the forest cottage at (%d,%d) offered Visit, played its line and shut behind you "
        .. "(terrain 0x%02X -> 0x%02X)", DOOR_X, DOOR_Y, before, after))
end

-- ch04snag (#214): the Iron Axe's whole purpose. Vanilla Ch4's village hands you the axe to chop
-- a snag into a bridge, and the retile kept the snag at (4,8) with the river at (4,9). Snags are
-- natively attackable -- bmtrick.c auto-adds a 20 HP TRAP_OBSTACLE on every TERRAIN_SNAG tile --
-- but the BRIDGE half is a MapChange the chapter has to register, and hosted chapters get their
-- changeLayerId zeroed. So this asserts the payoff by TERRAIN, which is what actually decides
-- whether a unit can cross: (4,9) is impassable river before, and a crossing after.
-- Run: PT_HOST_CHAPTER=5 tools/playtest/run.sh ch04snag (needs a CH04BOOT=1 ROM).
-- Swings with the first armed unit, at fast speed.
scenarios.ch04snag = function()
    local tag = "ch04snag"
    local SNAG_X, SNAG_Y = 4, 8
    local CROSS_X, CROSS_Y = 4, 9        -- the river row the trunk falls across
    -- TERRAIN_BRIDGE_SNAG (constants/terrains.h). snowy-bern now paints this native terrain with
    -- the winterized center of vanilla's downed-log composition, replacing the old generic-bridge
    -- workaround (#24).
    local T_CROSSING = 0x34
    if not bootToMap() then return result("FAIL", "never reached the ch04 map") end
    pokeFastConfig()
    INSPECT.settle("event", 6000, true)
    log(string.format(tag .. ": before -- snag(%d,%d) terrain=0x%02X  crossing(%d,%d) terrain=0x%02X",
        SNAG_X, SNAG_Y, terrainAt(SNAG_X, SNAG_Y), CROSS_X, CROSS_Y, terrainAt(CROSS_X, CROSS_Y)))
    if terrainAt(CROSS_X, CROSS_Y) == T_CROSSING then
        return result("FAIL", "the crossing is already a bridge before the snag was touched")
    end
    -- Any armed unit will do; the axe is the fiction, not a requirement (a snag is an obstacle
    -- and takes damage from anything that can reach it).
    local u
    for _, c in BOARD.each("blue") do
        if c.onField and (c.state & 0x2) == 0 and unitAttackRange(c) then u = c break end
    end
    if not u then return result("FAIL", "no armed blue unit to swing at the snag") end
    -- Park adjacent to the snag and hit it until the obstacle dies. Its HP is the trap's `extra`,
    -- so the only signal that matters is the TERRAIN flipping underneath.
    for swing = 1, 12 do
        if terrainAt(CROSS_X, CROSS_Y) == T_CROSSING then break end
        local m = blue(u.charId)
        if not m then break end
        if (m.state & 0x2) ~= 0 then
            runEnemyPhase()
            INSPECT.settle("phase", 900, true)
            m = blue(u.charId)
            if not m then break end
        end
        if not INSPECT.place(m, SNAG_X, SNAG_Y - 1) then break end
        m = blue(u.charId)
        if not cursorTo(m.x, m.y) then break end
        if moveUnit(m.x, m.y, m.x, m.y) then
            chooseAttack(m.addr)
            INSPECT.settle("fight", 900)
        end
        log(string.format("  swing %d: crossing terrain=0x%02X", swing, terrainAt(CROSS_X, CROSS_Y)))
    end
    shot(tag)
    local after = terrainAt(CROSS_X, CROSS_Y)
    log(string.format(tag .. ": after -- snag(%d,%d) terrain=0x%02X  crossing(%d,%d) terrain=0x%02X",
        SNAG_X, SNAG_Y, terrainAt(SNAG_X, SNAG_Y), CROSS_X, CROSS_Y, after))
    if after ~= T_CROSSING then
        return result("FAIL", string.format(
            "the snag broke but (%d,%d) is terrain 0x%02X, not a crossing (0x%02X) -- the "
            .. "MapChange did not apply", CROSS_X, CROSS_Y, after, T_CROSSING))
    end
    return result("PASS", string.format(
        "the snag fell: (%d,%d) is now a bridge -- the river is crossable", CROSS_X, CROSS_Y))
end


-- clear_ch04 / clear_ch04_parley: the WIN, and both arms of the branched ending (#24 Stage 5).
-- ch04 is DefeatAll, and its ending is CHECK_EVENTID'd on the parley flag -- so the two runs
-- exercise genuinely different endings, not the same scene twice:
--   clear_ch04         -- rout the pack too; the no-Lupin FALLBACK ending (Pinky reads the trail,
--                         Meesmickle takes the dread). This is the path the difficulty model
--                         explicitly prices, and the one whose boxes had no speaker before #24.
--   clear_ch04_parley  -- parley first, THEN rout; the authored Lupin ending.
-- Like clear_ch02 this is a DETERMINISTIC rout through REAL combat (frail + harmless
-- every foe, then teleport onto a firing tile and one-shot it) -- it proves the win -> ending
-- WIRING, not ch04 balance. Kills go through the death hook; a raw US_DEAD poke would not.
-- Run: PT_HOST_CHAPTER=5 tools/playtest/run.sh clear_ch04 (needs a CH04BOOT=1 ROM).
local function clearCh04(parley)
    local tag = parley and "clear-ch04-parley" or "clear-ch04"
    if not bootToMap() then return result("FAIL", "never reached the ch04 map") end
    pokeFastConfig()
    -- LIFT THE FOG for the duration of the rout, and make it reach the GRID (#204). Fog does two
    -- separate things to a clear-bot: bmtarget.c refuses to target a unit on a fogged tile, AND
    -- RefreshUnitsOnBmMap leaves a fogged red out of gBmMapUnit entirely. Zeroing the vision range
    -- alone only fixes the first -- which is why this scenario still stalled at 10 live enemies for
    -- 16 turns after that "fix". liftFogOntoTheGrid does both and reports what landed. This
    -- scenario exists to prove the win -> ending WIRING, not to play the hunt honestly, so lifting
    -- fog is the same class of shortcut as pokeFrail/pokeHarmless. The fog itself is covered by
    -- ch04moose and smoke_ch04.
    INSPECT.settle("event", 6000, true)
    if liftFogOntoTheGrid() == 0 then
        shot(tag .. "-fog-stuck")
        return result("FAIL", "fog lifted but no enemy reached gBmMapUnit -- nothing is attackable")
    end
    local start = chapter()
    -- ch05 is not hosted, so ch04's ending chains into dev_placeholder_scene(), whose MNTS(0x0)
    -- lands on the TITLE -- the chapter index never changes. Gating the win on chapter() alone
    -- therefore FAILs a run that ended perfectly (#204); the title is the terminal here, exactly
    -- as clear_ch02 treats it. A game-over also reaches the title, so that stays checked first.
    local function won() return chapter() ~= start or procActive(SYM.gProcScr_TitleScreen) end
    -- The PARLEY arm: Marty talks the pack down FIRST, which raises the recruit flag the ending's
    -- CHECK_EVENTID reads -- so the rout that follows lands on the AUTHORED Lupin ending instead of
    -- the no-Lupin fallback. Same rout either way; the flag is the whole difference between the two
    -- scenes, which is why both arms are worth running (#204).
    if parley then
        local ok, why = ch04Parley()
        if not ok then
            shot(tag .. "-no-parley")
            return result("FAIL", "parley arm: " .. why)
        end
        log(string.format("%s: Lupin is blue, %d green pack members -- routing for the AUTHORED ending",
            tag, greenPackCount()))
    end
    for t = 1, 16 do
        if won() then break end
        INSPECT.settle("event", 6000, true)
        for _, r in BOARD.each("red") do
            if not isDead(r) then pokeFrail(r); pokeHarmless(r) end
        end
        -- Stage-by-stage logging (#204): a clear-bot that stalls must say WHICH stage failed --
        -- no weapon / no firing tile / no command menu / no kill. The first run of this scenario
        -- reported only "liveEnemies=10" for 16 turns, which named none of them.
        local mw, mh = mapSize()
        log(string.format("%s iter %d: gameTurn=%d map=%dx%d liveEnemies=%d",
            tag, t, turn(), mw, mh, BOARD.liveCount("red")))
        for i, u in BOARD.each("blue") do
            if won() or BOARD.liveCount("red") == 0 then break end
            if u.onField and (u.state & 0x2) == 0 then
                local mn, mx = unitAttackRange(u)
                if not mn then
                    log(string.format("  blue[%d] pid=0x%02X (%d,%d): no weapon in slot 0 -- skipped",
                        i, u.charId, u.x, u.y))
                elseif not teleportToFiringTile(u, mn, mx) then
                    log(string.format("  blue[%d] pid=0x%02X (%d,%d): no firing tile [%d,%d]",
                        i, u.charId, u.x, u.y, mn, mx))
                elseif not canAttackFromHere(unitAt(SYM.gUnitArrayBlue, i), mn, mx) then
                    -- The engine's grid, not the unit array, decides whether row 0 is Attack.
                    -- Pressing anyway opens Item and Uses a vulnerary at full HP (#204).
                    u = unitAt(SYM.gUnitArrayBlue, i)
                    log(string.format("  blue[%d] pid=0x%02X on (%d,%d): no hostile in [%d,%d] on "
                        .. "gBmMapUnit -- NOT pressing Attack", i, u.charId, u.x, u.y, mn, mx))
                else
                    u = unitAt(SYM.gUnitArrayBlue, i)
                    if not (u and moveUnit(u.x, u.y, u.x, u.y)) then
                        log(string.format("  blue[%d] pid=0x%02X: command menu never opened", i, u.charId))
                    else
                        local before = BOARD.liveCount("red")
                        chooseAttack(u.addr, function() return BOARD.liveCount("red") == 0 end)
                        -- Break the settle the moment the kill empties the map: DefeatAll fires
                        -- on that death and the ending starts playing at once, so a blind
                        -- 600-frame wait here spends the victory fanfare and half the treeline
                        -- scene before the capture loop below gets its first frame (#204).
                        waitFor(function() return BOARD.liveCount("red") == 0
                            or INSPECT.settled("fight") end, 600)
                        log(string.format("  blue[%d] pid=0x%02X attacked from (%d,%d): liveEnemies %d -> %d",
                            i, u.charId, u.x, u.y, before, BOARD.liveCount("red")))
                    end
                end
            end
        end
        log(string.format("%s turn %d: liveEnemies=%d chapter=%d", tag, t, BOARD.liveCount("red"), chapter()))
        if won() then break end
        if gameOverActive() then shot(tag .. "-gameover")
            return result("FAIL", string.format("game over on turn %d -- party lost", t)) end
        if BOARD.liveCount("red") == 0 then break end
        if runEnemyPhase() == "gameover" then shot(tag .. "-gameover")
            return result("FAIL", "game over on the enemy phase") end
    end
    shot(tag .. "-routed")
    -- DefeatAll fires once the last red dies; then the branched ending plays over its BG and
    -- chains to the dev placeholder (ch05 is not hosted yet). Film it WITHOUT mashing A past
    -- the end -- a stray press on "Press START" starts a spurious New Game (the clear_ch02
    -- lesson), and the run then films ch04's OPENING under the ending's name. So stop pressing
    -- the moment the title is up, and stop the loop with it. Shoot densely: motion is the point.
    -- NOTE: `f` counts ITERATIONS, not frames. It did before too, but every iteration was one
    -- yield, so the two matched; an iteration can now carry a whole guarded input. The cap and
    -- the screenshot cadence are therefore both looser than they read. That is fine for a
    -- bounded recording -- won() is what ends this, never the cap -- but do not read 5400 as
    -- a frame budget (#238).
    -- Advance the ending only where FE8 is CLASSIFIED as waiting for it (#238). The
    -- every-90-frames A this replaces was the "stray press on Press START" hazard the
    -- comment above worries about, made structural: a cadence cannot see what is on
    -- screen, so the guard against it was a frame count chosen to be slow enough. A
    -- guarded input on dialogue_wait cannot fire on the title at all.
    local ended = INSPECT.talkUntil(won, 5400, {tick = function(f)
        if f % 4 == 0 then shot(tag) end
    end, label = "the ending's dialogue wait clears"})
    log(string.format("%s: liveEnemies=%d chapter=%d (host=%d)",
        tag, BOARD.liveCount("red"), chapter(), HOST_CHAPTER))
    if not ended then
        shot(tag .. "-no-ending")
        return result("FAIL", "routed but the DefeatAll ending never advanced off the host slot")
    end
    return result("PASS", string.format(
        "ch04 cleared (%s path) -> DefeatAll ending ran -> chapter=%d",
        parley and "parley" or "no-parley", chapter()))
end

scenarios.clear_ch04 = function() return clearCh04(false) end
scenarios.clear_ch04_parley = function() return clearCh04(true) end

-- ch06clock (#26): the run #360 could not do, because ch06 had no debug boot when it landed.
--
-- WHAT IT SETTLES. ch06's two hulls sit in POCKETS: an impassable TILE_2E body plus ONE
-- ground cell you can stand on to swing at them (decisions.md -> "ch06's boats sit in
-- POCKETS"). That is a claim about the ENGINE'S pathing, not about our map data, and no
-- static tool can answer it -- a turn-1 screenshot cannot, and the question needs several
-- enemy phases. So this drives the enemy phases and reads memory:
--
--   * neither pursuer STALLS -- it closes on its hull every phase until it is in range,
--     rather than parking because the approach is one tile wide;
--   * the range-1 crab, once in range of the west hull, is standing on the DOOR and nowhere
--     else. That is the pocket's whole promise: exactly one melee tile;
--   * the range-2 thrower reaches the east hull ANYWAY -- FE8 has no line of sight, so the
--     wall never stops a javelin. Its throwing tile is logged, because that is placement
--     evidence rather than a pass/fail;
--   * nothing touches a hull on turn 1, which is vanilla Ch6's own placement claim.
--
-- WHAT IT DELIBERATELY DOES NOT ASSERT: the sink TURN. The chapter YAML declares turns 7 and
-- 8, but a fuse made of attacks is a hit RATE, not a turn number -- the crab shows a 47
-- displayed hit into the hull's forest cover and needs four connections, so "turn 8" is a
-- distribution and one run is one sample of it. Asserting it would make this a coin-flip
-- verdict. It is measured and LOGGED against the declared turn instead, and a run that
-- disagrees is a finding for the chapter's balance, not a broken scenario.
--
-- The party is held at full HP every turn. That is isolation, not a cheat: a dead PC ends
-- the run in a game over long before the clock resolves, and the subject here is the two
-- pursuers rather than whether the fight is winnable.
--
-- CONTENTION for the door -- two units wanting the same single tile -- does NOT exist on
-- normal, where the only pursuers are these two and they want different hulls. It exists on
-- DIFFICULT, whose turn-4 cavalry trio also pursues from the west edge. Declared cases
-- run on normal, so that arm is not covered here and is not claimed to be.
scenarios.ch06clock = function()
    local CH06 = dofile(PLAYTEST_DIR .. "/ch06.lua")     -- ch06's shared facts (#314)
    local TURNS = 12                                     -- past both declared fuses, with slack
    if not bootToMap() then return result("FAIL", "never reached the ch06 map") end
    pokeFastConfig()
    INSPECT.settle("event", 6000, true)

    local dist = BOARD.distance
    local function indexOf(base, count, match)
        for i = 0, count - 1 do
            local u = unitAt(base, i)
            if u and not isDead(u) and match(u) then return i, u end
        end
        return nil
    end

    -- The hulls, by the raw pid each boat owns (CH06_BOAT_PIDS). Tracked by INDEX and
    -- re-read every phase: a unit snapshot is a copy, and the whole subject is what changes.
    local hulls = {}
    for _, b in ipairs(CH06.BOATS) do
        local i, u = indexOf(SYM.gUnitArrayGreen, 20, function(g) return g.charId == b.pid end)
        if not i then
            return result("FAIL", string.format(
                "%s (pid 0x%02X) is not on the map -- the chapter's clock is two GREEN units "
                .. "and one of them never loaded", b.id, b.pid))
        end
        if u.x ~= b.x or u.y ~= b.y then
            return result("FAIL", string.format(
                "%s loaded at (%d,%d), not the pocket cell (%d,%d) its chapter YAML declares",
                b.id, u.x, u.y, b.x, b.y))
        end
        hulls[b.id] = { boat = b, index = i, hp = u.hp, maxhp = u.maxhp, sank = nil }
        log(string.format("ch06clock: %s hull at (%d,%d) %d/%d HP, door (%d,%d), declared "
            .. "fuse turn %d", b.id, u.x, u.y, u.hp, u.maxhp, b.doorX, b.doorY, b.sinks_on))
    end

    -- The pursuers. Every ch06 enemy shares one generic pid, so a pursuer is identified by
    -- the tile it STARTS on and then tracked by its stable index in gUnitArrayRed.
    local chase = {}
    for _, p in ipairs(CH06.PURSUERS) do
        local i, u = indexOf(SYM.gUnitArrayRed, 50,
            function(r) return r.x == p.x and r.y == p.y end)
        if not i then
            return result("FAIL", string.format(
                "no living enemy on (%d,%d) at turn 1 -- %s is the pursuer that makes the %s "
                .. "clock exist, and the placement this scenario reads is gone",
                p.x, p.y, p.id, p.boat))
        end
        local lo, hi = unitAttackRange(u)
        chase[#chase + 1] = { spec = p, index = i, x = u.x, y = u.y, arrived = nil }
        log(string.format("ch06clock: %s at (%d,%d), weapon range %s-%s (declared max %d), "
            .. "chasing %s -- %d tiles from its door",
            p.id, u.x, u.y, tostring(lo), tostring(hi), p.range, p.boat,
            dist(u.x, u.y, hulls[p.boat].boat.doorX, hulls[p.boat].boat.doorY)))
    end

    -- The turn-1 red roster, once. The first run of this scenario measured an 11-damage hit
    -- on a hull during enemy phase 1 and could not name what threw it: nothing in the EMITTED
    -- unit table (`MS_Ch06Line`) is within weapon range of that hull at load, and the only
    -- mover near it was still three tiles out. A scenario that watches two units cannot tell
    -- "the AI did something surprising" from "the loaded map is not the table we emitted", so
    -- it dumps what actually LOADED -- which is the reading the next run needs and the one
    -- this scenario was too narrow to take (AGENTS.md's playtest block: spend ONE instrumented
    -- run that dumps what your next three hypotheses need, not one run per guess).
    for i = 0, 49 do
        local u = unitAt(SYM.gUnitArrayRed, i)
        if u and not isDead(u) and u.onMap then
            local lo, hi = unitAttackRange(u)
            log(string.format("ch06clock: roster red[%02d] (%2d,%2d) lvl %2d hp %2d range %s-%s",
                i, u.x, u.y, u.level, u.hp, tostring(lo), tostring(hi)))
        end
    end

    -- Findings are COLLECTED, not returned on sight. This is the one run ch06 gets for the
    -- question (decisions.md -> "Playtest runs are the most expensive thing in this repo"), so
    -- a turn-1 contact must not abandon the pathing evidence the same run was going to
    -- produce. Only a wedged phase or a game over ends it early, because neither leaves
    -- anything left to read.
    local stalls, offdoor, early = {}, {}, {}
    for t = 1, TURNS do
        -- Isolation: the party is not the subject, and a game over ends the run before the
        -- clock resolves. Never visits, never fights -- it only gives the turns back.
        for i = 0, 61 do
            local u = unitAt(SYM.gUnitArrayBlue, i)
            if u and not isDead(u) then INSPECT.fullHeal(u) end
        end
        local phase = runEnemyPhase()
        if phase == nil then
            return result("FAIL", string.format("the enemy phase never returned on turn %d", t))
        end
        if phase == "gameover" then
            return result("FAIL", string.format(
                "game over on turn %d despite the party being held at full HP", t))
        end

        for _, b in ipairs(CH06.BOATS) do
            local h = hulls[b.id]
            local u = unitAt(SYM.gUnitArrayGreen, h.index)
            local hp = (u and not isDead(u)) and u.hp or 0
            if hp == 0 and not h.sank then h.sank = t end
            -- Name the attacker. A hull losing HP with no pursuer in range is the reading the
            -- first run could not explain, so every red that could plausibly have reached it
            -- is dumped at the moment the damage lands rather than reconstructed afterwards.
            if hp < h.hp then
                log(string.format("ch06clock: %s took %d on enemy phase %d -- reds within 3:",
                    b.id, h.hp - hp, t))
                -- Put the CAMERA on the hull before the frame. Headless this is a no-op and
                -- the roster dump below is the whole reading; headed (PT_HEADED=1 PT_FPS=60)
                -- it photographs who is actually standing around the boat, which is the
                -- question the emitted unit table could not answer.
                cursorTo(b.x, b.y)
                wait(90)                -- the map scrolls to the cursor; shooting before it
                                        -- arrives photographs wherever the fight happened to be
                shot(string.format("%s-hit-turn%d", b.id, t))
                for i = 0, 49 do
                    local r = unitAt(SYM.gUnitArrayRed, i)
                    if r and not isDead(r) and r.onMap and dist(r.x, r.y, b.x, b.y) <= 3 then
                        local lo, hi = unitAttackRange(r)
                        log(string.format("ch06clock:   red[%02d] (%2d,%2d) d=%d range %s-%s",
                            i, r.x, r.y, dist(r.x, r.y, b.x, b.y), tostring(lo), tostring(hi)))
                    end
                end
            end
            if t == 1 and hp < h.maxhp then
                early[#early + 1] = string.format("%s took %d on enemy phase 1", b.id,
                                                  h.maxhp - hp)
            end
            h.hp = hp
        end

        for _, c in ipairs(chase) do
            local h = hulls[c.spec.boat]
            local u = unitAt(SYM.gUnitArrayRed, c.index)
            local x, y = (u and not isDead(u)) and u.x or -1, (u and not isDead(u)) and u.y or -1
            local d = (x >= 0) and dist(x, y, h.boat.x, h.boat.y) or -1
            local inRange = d >= 0 and d <= c.spec.range
            log(string.format(
                "ch06clock: turn %2d (engine %2d)  %-16s (%2d,%2d) d=%2d %-9s | %-9s %2d/%2d HP",
                t, turn(), c.spec.id, x, y, d, inRange and "IN RANGE" or "closing",
                c.spec.boat, h.hp, h.maxhp))
            if h.hp > 0 and x >= 0 then
                if inRange then
                    if not c.arrived then c.arrived = t end
                    -- The pocket's whole promise. A range-1 attacker in range of the hull is
                    -- standing on the door or the pocket does not shape melee at all.
                    if c.spec.range == 1 and not (x == h.boat.doorX and y == h.boat.doorY) then
                        offdoor[#offdoor + 1] = string.format(
                            "%s reached %s from (%d,%d) on turn %d, not the door (%d,%d)",
                            c.spec.id, c.spec.boat, x, y, t, h.boat.doorX, h.boat.doorY)
                    end
                elseif x == c.x and y == c.y then
                    stalls[#stalls + 1] = string.format(
                        "%s did not move on turn %d -- still (%d,%d), %d tiles from %s",
                        c.spec.id, t, x, y, d, c.spec.boat)
                end
            end
            c.x, c.y = x, y
        end
    end

    if #early > 0 then
        return result("FAIL", "something reached a hull on enemy phase 1. ch06's whole "
            .. "travel-time budget is measured from vanilla Ch6's claim that nothing can: "
            .. table.concat(early, "; "))
    end
    if #stalls > 0 then
        return result("FAIL", "a pursuer STALLED short of its hull, so the one-tile approach "
            .. "is not pathable for it: " .. table.concat(stalls, "; "))
    end
    if #offdoor > 0 then
        return result("FAIL", "a melee pursuer attacked a hull from outside its pocket door, "
            .. "so the pocket is not one tile wide: " .. table.concat(offdoor, "; "))
    end
    for _, c in ipairs(chase) do
        if not c.arrived then
            return result("FAIL", string.format(
                "%s never came within %d of %s in %d turns -- it retargeted or the pocket has "
                .. "no path, and that boat has no clock",
                c.spec.id, c.spec.range, c.spec.boat, TURNS))
        end
    end

    -- The fuse: measured, reported, not asserted. See the header.
    local told = {}
    for _, b in ipairs(CH06.BOATS) do
        local h = hulls[b.id]
        local got = h.sank and string.format("turn %d", h.sank)
            or string.format("still afloat at turn %d on %d HP", TURNS, h.hp)
        told[#told + 1] = string.format("%s declared turn %d, measured %s", b.id, b.sinks_on, got)
        if h.sank ~= b.sinks_on then
            log(string.format("ch06clock: FUSE DIFFERS -- %s", told[#told]))
        end
    end
    log("ch06clock: " .. table.concat(told, " | "))
    return result("PASS", string.format(
        "both pursuers pathed to their hull and neither stalled (%s); the melee pursuer "
        .. "attacked only from its pocket door. Fuse measured, not asserted: %s",
        table.concat({ chase[1].spec.id .. " in range turn " .. chase[1].arrived,
                       chase[2].spec.id .. " in range turn " .. chase[2].arrived }, ", "),
        table.concat(told, " | ")))
end

-- ch06halberd (#495): vanilla Ch6's Halberd lesson, on our lance-carrying dropper.
--
-- Vanilla's Fighter carries {Iron Axe, Halberd} and drops his LAST item. The AI equips the
-- weapon it swings (cp_perform.c), so once he attacks with the Halberd it moves to the front
-- and he drops the Iron Axe: rush him before he attacks. Ours is a Cavalier carrying
-- {Iron Lance, Horseslayer}. The AI scores a weapon by damage x hit (cp_battle.c), so against
-- a foot unit it swings the Iron Lance (equal Mt, +10 Hit) and the drop stays the Horseslayer;
-- against a mounted unit the Horseslayer's triple Mt wins and the drop flips. Two arms, one run:
--
--   * FOOT: a foot unit stands beside him until he attacks it. His inventory is unchanged.
--   * MOUNTED: a unit of a class on the Horseslayer's own effectiveness list (read from
--     gItemData, never a hand list) stands beside him until he attacks it. The Horseslayer is
--     now first and the Iron Lance is the drop.
--
-- Each target is held at 60 HP with 0 Pow, so nobody dies and nothing counter-kills him, and
-- at 0 Def with 4 Spd and Lck. The AI breaks a score tie toward the LATER slot, so a target
-- both weapons hit 100% (or both deal 0) would flip the foot arm for a reason that is not the
-- lesson; pinning them keeps Iron Lance's +10 Hit the only difference. The attack is read off gAiDecision as he makes it, because an HP drop cannot say who
-- dealt it. An arm allows four enemy phases.
scenarios.ch06halberd = function()
    local CH06 = dofile(PLAYTEST_DIR .. "/ch06.lua")
    local D, ITEMS, DROP = CH06.DROPPER, CAMPAIGN.CH06_DROPPER_ITEMS, CAMPAIGN.CH06_DROPPER_DROP
    if not bootToMap() then return result("FAIL", "never reached the ch06 map") end
    pokeFastConfig()
    INSPECT.settle("event", 6000, true)

    local function inventory(u)
        local out = {}
        for k = 0, 4 do
            local it = ru16(u.addr + 0x1E + 2 * k)
            if it == 0 then break end
            out[#out + 1] = { id = it & 0xFF, uses = it >> 8 }
        end
        return out
    end
    local function ids(inv)
        local s = {}
        for _, it in ipairs(inv) do s[#s + 1] = string.format("0x%02X/%d", it.id, it.uses) end
        return "{" .. table.concat(s, ", ") .. "}"
    end
    local function classOf(u) return ru8(ru32(u.addr + 0x04) + 0x04) end

    local ri
    for i = 0, 49 do
        local r = unitAt(SYM.gUnitArrayRed, i)
        if r and not isDead(r) and r.x == D.x and r.y == D.y then ri = i break end
    end
    if not ri then
        return result("FAIL", string.format("no enemy on (%d,%d), where the YAML places %s",
            D.x, D.y, D.id))
    end
    local function dropper() return unitAt(SYM.gUnitArrayRed, ri) end
    local inv = inventory(dropper())
    log(string.format("ch06halberd: %s at (%d,%d) carries %s, drop flag %s", D.id, D.x, D.y,
        ids(inv), (dropper().state & 0x1000) ~= 0 and "set" or "CLEAR"))
    if #inv ~= #ITEMS or inv[1].id ~= ITEMS[1] or inv[#inv].id ~= DROP then
        local want = {}
        for _, id in ipairs(ITEMS) do want[#want + 1] = string.format("0x%02X", id) end
        return result("FAIL", string.format("%s loaded with %s; the YAML declares {%s} "
            .. "dropping 0x%02X", D.id, ids(inv), table.concat(want, ", "), DROP))
    end
    if (dropper().state & 0x1000) == 0 then
        return result("FAIL", D.id .. " loaded without US_DROP_ITEM, so he drops nothing")
    end

    -- The classes his second weapon is effective against: gItemData[id].pEffectiveness (+0x10),
    -- a 0-terminated class list (data_itemuse.c's ItemEffectiveness_Horse).
    local mounted, eff = {}, ru32(SYM.gItemData + DROP * BOARD.ITEMDATA_STRIDE + 0x10)
    while eff ~= 0 and ru8(eff) ~= 0 do mounted[ru8(eff)] = true eff = eff + 1 end

    local foot, horse
    for i = 0, 61 do
        local u = unitAt(SYM.gUnitArrayBlue, i)
        if u and not isDead(u) and u.onMap then
            if mounted[classOf(u)] then horse = horse or u else foot = foot or u end
        end
    end
    if not foot or not horse then
        return result("FAIL", string.format("the boot deployed no %s unit, so an arm cannot run",
            foot and "mounted" or "foot"))
    end

    -- One arm: park `u` beside him, hold both units, run enemy phases until he attacks, then
    -- move `u` off so the next arm's target is the only one beside him.
    local function arm(name, u)
        local idx, home = (u.addr - SYM.gUnitArrayBlue) // BOARD.UNIT_SIZE, { x = u.x, y = u.y }
        local function me() return unitAt(SYM.gUnitArrayBlue, idx) end
        if not teleportAdjacentTo(u, { { x = D.x, y = D.y } }) then
            return nil, name .. ": no free tile beside him"
        end
        -- His own decision, caught the frame the AI makes it: an HP drop alone cannot say
        -- WHO hit the target, and enemy weapons spend no uses to tell on him.
        local mine, theirs = ru8(dropper().addr + 0x0B), ru8(me().addr + 0x0B)
        for t = 1, 4 do
            -- 60 HP and 0 Pow: nobody dies, nothing counter-kills him. Def 0 and 4 Spd/Lck
            -- (12 Avoid before terrain) keep both weapons dealing damage at a Hit strictly
            -- between 0 and 100, so the scores cannot tie. 20/20 tied them at ~0 Hit.
            local a = me().addr
            emu:write8(a + 0x12, 60); emu:write8(a + 0x13, 60)
            emu:write8(a + 0x14, 0); emu:write8(a + 0x17, 0)
            emu:write8(a + 0x16, 4); emu:write8(a + 0x19, 4)
            emu:write8(dropper().addr + 0x13, dropper().maxhp)
            local swung
            emu:write8(SYM.gAiDecision + 0x00, 0)   -- last phase's decision must not match
            local watch = callbacks:add("frame", function()
                if ru8(SYM.gAiDecision + 0x01) == mine and ru8(SYM.gAiDecision + 0x00) == 1 then
                    swung = { target = ru8(SYM.gAiDecision + 0x06),
                              slot = ru8(SYM.gAiDecision + 0x07) }
                end
            end)
            local phase = runEnemyPhase()
            callbacks:remove(watch)
            if phase ~= "player" then
                return nil, string.format("%s: the enemy phase returned %s", name, tostring(phase))
            end
            local now, m = inventory(dropper()), me()
            log(string.format("ch06halberd: %s phase %d -- target class 0x%02X at (%d,%d) "
                .. "%d/60 HP, his decision %s, his inventory %s", name, t, classOf(m), m.x, m.y,
                m.hp, swung and string.format("slot %d at unit 0x%02X", swung.slot, swung.target)
                or "none", ids(now)))
            if swung and swung.target ~= theirs then
                return nil, string.format("%s: he attacked unit 0x%02X, not the target 0x%02X",
                    name, swung.target, theirs)
            end
            if swung then
                -- Home if it is still free, else the free tile nearest it that is out of his
                -- reach: an enemy may have stepped onto home while the arm ran.
                local mw, mh = mapSize()
                local best, bx, by
                for y = 0, mh - 1 do
                    for x = 0, mw - 1 do
                        local d = BOARD.distance(x, y, home.x, home.y)
                        if mapUnitAt(x, y) == 0 and BOARD.distance(x, y, D.x, D.y) > 1
                            and (not best or d < best) then best, bx, by = d, x, y end
                    end
                end
                if not best then return nil, name .. ": no free tile to move the target off to" end
                if not INSPECT.place(m, bx, by) then
                    return nil, name .. ": could not move the target off its tile"
                end
                return now
            end
        end
        return nil, string.format("%s: he attacked no one in four enemy phases", name)
    end

    local after, why = arm("foot", foot)
    if not after then return result("FAIL", why) end
    if after[1].id ~= ITEMS[1] or after[#after].id ~= DROP then
        return result("FAIL", string.format("against a foot unit he swung his second weapon: "
            .. "inventory is now %s, so the drop flipped without a mounted target", ids(after)))
    end

    after, why = arm("mounted", horse)
    if not after then return result("FAIL", why) end
    if after[1].id ~= DROP or after[#after].id ~= ITEMS[1] then
        return result("FAIL", string.format("against a mounted unit his inventory is %s; the "
            .. "lesson needs 0x%02X first and 0x%02X as the drop", ids(after), DROP, ITEMS[1]))
    end
    return result("PASS", string.format("vs a foot unit he swings the Iron Lance and still drops "
        .. "0x%02X; vs a mounted unit he swings 0x%02X and now drops 0x%02X (%s)",
        DROP, DROP, ITEMS[1], ids(after)))
end

-- ---------------------------------------------------------------- runner
-- A DECLARED case (#314) has no function here: its chapter YAML declares what it proves,
-- `declared.py` emits it as a Lua table into the run directory, and cases.lua runs it. The
-- api table below is the whole interface -- cases.lua never touches emu, SYM or any global
-- in this chunk, which is what lets test_cases.lua drive it with a fake.
--
-- Declared INSIDE the runner coroutine, not beside it: `harness.lua` is one Lua chunk
-- under Lua's 200-local cap, and a top-level `local function` here would spend a shared slot
-- (`check_lua_local_headroom`) on the very mechanism that exists to stop chapters spending them.
local co = coroutine.create(function()
  local function runDeclaredCase(path)
    local api = {
        bootToMap = bootToMap,
        fastConfig = pokeFastConfig,
        collectedItems = collectedItems,
        eventFlag = eventFlag,
        result = result,
        log = log,
        shot = shot,
        -- Weak (post-boot) and strong (pre-visit) settle, matching what the hand-written
        -- preambles actually waited on. The strong one adds `player_map_idle`, which is the
        -- lesson ch05reliquaries paid for: a location event's tail still holds the
        -- controller when the item lands, and moving then dies as "cursor could not reach".
        settle = function(strong)
            return INSPECT.settle(strong and "idle" or "event", strong and 3000 or 6000, true)
        end,
        -- `done` is generic here where a hand-written scenario passed its own item test: the
        -- step does not know what the case asserts (assertions are order-free), so it stops
        -- on ANY item arriving and lets the `gained_item` assertion decide whether it was
        -- the right one. A site that hands over the WRONG item now reads as a wrong item
        -- rather than as a timeout.
        visitVillage = function(x, y)
            local before = 0
            for _ in ipairs(collectedItems()) do before = before + 1 end
            return VISIT.run(x, y, function()
                local now = 0
                for _ in ipairs(collectedItems()) do now = now + 1 end
                return now ~= before
            end)
        end,
        -- `help`: R on a unit's name (INSPECT.helpAt), what the build gives its pid, and the pid
        -- standing on a tile, whatever its faction.
        helpAt = INSPECT.helpAt,
        helpFor = function(pid) return CAMPAIGN.HELP[pid] end,
        pidAt = function(x, y)
            local id = mapUnitAt(x, y)
            local unit = id ~= 0 and ru32(SYM.gUnitLookup + id * 4) or 0
            local character = unit ~= 0 and ru32(unit) or 0
            return character ~= 0 and ru8(character + 4) or nil
        end,
        -- `idle` and `raided`: give the turns back, hold the party, and read the sites a raid
        -- takes. A site is CAMPAIGN.VILLAGES's (gen_symbols: tile, flag and gift by YAML id).
        enemyPhase = function() return runEnemyPhase() end,
        holdParty = function()
            -- Full HP, never past it: the AI weighs a target by whether it can kill it, and
            -- a unit at 60/18 is one it never can, so over-cap HP would bend the raiders'
            -- routing, which is what a held raid is testing.
            for _, u in BOARD.each("blue") do
                if not u.dead then INSPECT.fullHeal(u) end
            end
        end,
        turn = turn,
        terrainAt = terrainAt,
        village = function(id) return CAMPAIGN.VILLAGES[id] end,
        showTile = function(x, y)
            cursorTo(x, y)
            wait(90)    -- the map scrolls to the cursor; a shot before it arrives misses the site
        end,
        -- `shop`: the visit path with Armory/Vendor as the command; returns the stock it opened.
        shopAt = function(x, y, kind)
            return VISIT.shop(x, y, kind)
        end,
        -- `talk`: the visit path with Talk as the command; done once the scene has ended.
        -- A missing Talk command is the failure this catches (a CHAR naming the wrong pair).
        talkFrom = function(x, y)
            return VISIT.run(x, y, function()
                return controllerState() ~= "dialogue_wait"
                    and not procActive(SYM.ProcScr_StdEventEngine)
            end, nil, function()
                if chooseTalk() then return true end
                return false, "the command menu offered no Talk -- no CHAR pairs this unit "
                    .. "with a neighbour"
            end)
        end,
    }
    return dofile(PLAYTEST_DIR .. "/cases.lua").run(dofile(path), api)
  end

    log("scenario: " .. PLAYTEST_SCENARIO)
    -- A chapter case's `lua:` may bind a generic probe to its chapter's ROM (#531), so the
    -- function is looked up by ENTRY. Only `scenarios` and `INSPECT` are searched, and that is
    -- a chosen scope, not a cache constraint: `INSPECT` is where chapter-generic probes live,
    -- and `VISIT.*`-style helpers take arguments a binding cannot pass.
    local entry = (PLAYTEST_ENTRY ~= nil and PLAYTEST_ENTRY ~= "") and PLAYTEST_ENTRY
        or PLAYTEST_SCENARIO
    local probe = entry:match("^INSPECT%.([%w_]+)$")
    local fn = probe and INSPECT[probe] or scenarios[entry]
    if entry ~= PLAYTEST_SCENARIO then log("entry: " .. entry) end
    if not fn then
        if PLAYTEST_CASE ~= nil and PLAYTEST_CASE ~= "" then
            runDeclaredCase(PLAYTEST_CASE)
            log("declared case returned")
            return
        end
        return result("ERROR", "unknown scenario " .. tostring(PLAYTEST_SCENARIO)
            .. (entry ~= PLAYTEST_SCENARIO and (" (entry " .. entry .. ")") or ""))
    end
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
