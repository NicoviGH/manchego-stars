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
-- PROCSCR: proc-script address -> exact symbol. Proc identity must never come from the
-- PROC_NAME string at proc+0x10 -- the decomp reuses those (E_FACE twice, bmenu three
-- times), which is why freeze reports could not say which proc was waiting (#236).
dofile(PLAYTEST_DIR .. "/procscr.lua")
-- It is generated (gitignored, written by gen_symbols.py from the ELF), so a stale or
-- half-written table is a total outage with a confusing error much later. Say so here.
assert(type(PROCSCR) == "table" and next(PROCSCR) ~= nil,
    "procscr.lua defined no PROCSCR table -- regenerate it: tools/playtest/gen_symbols.py")
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
local UNIT_SIZE = 0x48
local US_DEAD = 4 -- include/bmunit.h (1 << 2)
-- Harness tuning, in ONE table rather than one local apiece: harness.lua is a single Lua
-- chunk and its main function sits near Lua's 200-local ceiling, so a handful of new
-- top-level locals stops the WHOLE FILE loading and every scenario dies at once (#232).
local TUNE = {
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
local CHAR_HLIN, CHAR_SCRAMSAX, CHAR_SEPHEK = 0x0D, 0x11, 0x68 -- NATASHA/KYLE/ONEILL slots
-- prologue/sandbox host on chapter slot 1; a chapter load-test (e.g. --ch03-boot on slot 4)
-- overrides via PT_HOST_CHAPTER so bootToMap/inChapter recognize the right slot.
local HOST_CHAPTER = PLAYTEST_HOST_CHAPTER or 1
-- Which difficulty mode a run selects on the New Game menu (PT_DIFFICULTY), defaulting to
-- NORMAL -- the mode that ships to most players and the one `difficulty.py` grades by
-- default. It has to be a declared default rather than "whatever the menu highlights":
-- FE8 initialises the menu to option 0 (TUTORIAL) and the harness only pressed A, so every
-- verdict this project produced before #303 graded the EASIEST mode while reading as
-- general. A scenario that genuinely wants another mode names it.
-- Hung off TUNE rather than taking two top-level locals: harness.lua sits AT Lua's 200-local
-- ceiling, and the next top-level local stops the whole chunk loading (check.py guards it).
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
local LORD_CANDIDATES = 8
local LORDSEL_FLAG_BASE = 0xF0
local CHAR_PINKY, CHAR_CHIEF = 0x08, 0x46 -- NEIMI slot / BREGUET slot (ch01 boss)

local logfile = io.open(PLAYTEST_LOG, "w")
local controllerFault
local function log(s)
    logfile:write(string.format("[f%06d] %s\n", emu:currentFrame(), s))
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
-- Read as a GLOBAL, deliberately: this file is one Lua chunk against a 200-local ceiling
-- (decisions.md -> "`harness.lua` is ONE Lua chunk, at the 200-local ceiling"), and binding
-- this to a top-level local spent one of the last free slots for no benefit.
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

local function ru8(a) return emu:read8(a) end
local function rs8(a)
    local v = emu:read8(a)
    if v >= 0x80 then v = v - 0x100 end
    return v
end
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

local function findProc(scriptAddr)
    for i = 0, 63 do
        local addr = SYM.sProcArray + i * 0x6C
        if ru32(addr) == scriptAddr then return addr end
    end
    return nil
end
local function procActive(scriptAddr) return findProc(scriptAddr) ~= nil end
local function anyMenuProc()
    return findProc(SYM.sProc_MenuMain) or findProc(SYM.sProc_Menu)
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
local function unitAt(base, i)
    local a = base + i * UNIT_SIZE
    local chptr = ru32(a)
    if chptr == 0 then return nil end
    return {
        addr = a,
        charId = ru8(chptr + 4),
        x = ru8(a + 0x10), y = ru8(a + 0x11),
        hp = ru8(a + 0x13),
        -- struct Unit (bmunit.h): +08 level, +12 maxHP, +14 pow, +17 def. The difficulty
        -- shift re-projects these off class growths, so they are what a mode probe reads
        -- (+0x13 curHP happens to match maxHP at load, but is not the field that moved).
        level = ru8(a + 0x08),
        maxhp = ru8(a + 0x12), pow = ru8(a + 0x14), def = ru8(a + 0x17),
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
-- Array bounds are the DECOMP's, not the roster size of the day (bmunit.h: blue[62] /
-- red[50] / green[20]). `blue` searched 8 for as long as the cast WAS 8; the TESTCH sandbox
-- now deploys 11, so `PT_CHAR=lupin` reported "not deployed" for a unit that was standing on
-- the map. A scan bound is a property of the engine, never of the current content.
local function blue(charId) return findUnit(SYM.gUnitArrayBlue, 62, charId) end
local function red(charId) return findUnit(SYM.gUnitArrayRed, 50, charId) end
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
-- exposes it to PT_* env vars so ANY cutscene can be recorded with no new Lua, and the
-- named recorders (recordch02intro, recordending) are one-line presets over it.
-- Defined HERE, above its first caller (recordending) -- a Lua local is only visible
-- lexically after its definition, so it must precede every scenario that uses it.
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
-- The #236 state inspector, as ONE table rather than three top-level locals: this file
-- is against Lua's 200-local ceiling for a main chunk, and crossing it stops the whole
-- harness loading (every scenario dies at once). Hang new helpers off an existing table
-- (INSPECT, TUNE) or put the logic in controller.lua, which has a unit suite and no such
-- ceiling. HOW MUCH ROOM IS LEFT IS NEVER WRITTEN DOWN HERE: `check.py
-- check_lua_local_headroom` measures it and prints it on every `make check`, because the
-- hand-maintained number said "two free slots" in three files at once and was wrong in
-- all three within one PR (#241). `check_lua_chunks_load` fails the build on a crossing.
-- Fields are assigned further down, next to the proc-pool reader they build on.
local INSPECT = {}
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
    local shotEvery = o.shotEvery or 4
    local autoAdvanceDialogue = ((o.pressEvery ~= nil) and o.pressEvery or 60) > 0
    local reached, fr = false, 0
    while fr < maxFrames do
        fr = fr + 1
        if fr % shotEvery == 0 then shot(tag) end
        -- Let a function terminal observe the frame before the recorder consumes an
        -- input state.  #260's turn-event proof remembers that dialogue_wait occurred;
        -- checking only after the guarded A press made a good four-box scene time out.
        if doneFn() then reached = true break end
        if autoAdvanceDialogue and controllerState() == "dialogue_wait" then
            if not guardedInput("advance_dialogue", "A", "dialogue input wait clears", function(after)
                return controllerState(after) ~= "dialogue_wait"
            end, 120) then
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

local function tileOccupied(x, y)
    for _, base in ipairs({ SYM.gUnitArrayBlue, SYM.gUnitArrayGreen, SYM.gUnitArrayRed }) do
        for i = 0, 23 do
            local u = unitAt(base, i)
            if u and not isDead(u) and u.x == x and u.y == y then return true end
        end
    end
    return false
end

-- Live map state used by both scenarios and the controller observer.
local function mapUnitRow(y) return ru32(ru32(SYM.gBmMapUnit) + y * 4) end
local function mapUnitAt(x, y) return ru8(mapUnitRow(y) + x) end
local function setMapUnit(x, y, v) emu:write8(mapUnitRow(y) + x, v) end
local function mapSize() return rs16(SYM.gBmMapSize), rs16(SYM.gBmMapSize + 2) end

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
    local addr = findProc(script)
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
    local addr = findProc(SYM.ProcScr_PrepMenu)
    if not addr then return end
    local count = ru8(addr + 0x2B)
    if count == 0 or count > 8 then
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
    local addr = findProc(SYM.gProcScr_TargetSelection)
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
    for i = 0, 63 do
        local addr = SYM.sProcArray + i * 0x6C
        local script = ru32(addr)
        if script ~= 0 then
            observation.raw_procs[#observation.raw_procs + 1] = {
                -- scrCur is the script command the proc sits on (include/proc.h). It is the
                -- liveness signal the stall detector keys on: a pool whose every proc holds
                -- the same command, idle and lock for TUNE.stallFrames is not slow, it is
                -- waiting for an input nothing will send (#236).
                -- sleepTime (+0x24) is in there because those three fields are CONSTANT
                -- under PROC_REPEAT -- which is how every long-running FE8 proc is written
                -- -- so without it a proc counting down a timed wait reads as frozen (#241).
                slot = i, script = script, scr_cur = ru32(addr + 0x04),
                idle = ru32(addr + 0x0C), sleep = rs16(addr + 0x24), lock = ru8(addr + 0x28),
            }
        end
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
local function observationEvidence(observation)
    local state, why = controllerState(observation)
    local cursorPart = observation.cursor and string.format(" cursor=(%d,%d) unit=0x%02X",
        observation.cursor.x, observation.cursor.y, observation.cursor.unit or 0) or ""
    local menuPart = ""
    if observation.menu then
        local ids = {}
        for _, item in ipairs(observation.menu.items) do ids[#ids + 1] = string.format("0x%02X", item.override_id) end
        menuPart = string.format(" menu=[%s]@%d", table.concat(ids, ","), observation.menu.current)
    end
    return (state or ("unsupported:" .. tostring(why))) .. cursorPart .. menuPart
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
local function cursorTo(tx, ty)
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
        if tapA and controllerState() == "dialogue_wait" then
            if not guardedInput("advance_dialogue", "A", "dialogue input wait clears", function(after)
                return controllerState(after) ~= "dialogue_wait"
            end, 60) then return false end
        else
            yield()
        end
    end
    return false
end

-- Wait until FE8 reaches `want`. `frames` bounds how long we tolerate NOTHING HAPPENING;
-- it is not a wall-clock cap, because waiting for the map to become playable routinely
-- spans a scene -- a chapter opening, a turn event -- and no fixed budget fits every
-- cutscene (#232: the ch01 opening outran 300 frames, so ch01win/lordfloor logged a
-- controller fault on a chapter they went on to clear). The event engine running is
-- productive work, so it does not burn the budget; STALL_CEILING keeps a genuinely
-- wedged engine failing closed here rather than at run.sh's wall-clock deadline.
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
        if not (last.procs and last.procs.std_event) then idle = idle + 1 end
        -- Dialogue is never what a caller waits AT -- the targets are player_map_idle,
        -- unit_selected or a menu -- and FE8 interleaves text with play constantly: a
        -- turn event, a village line, a post-combat quote. Advancing it is a CLASSIFIED
        -- state with a legal action, driven through the same guarded single input as
        -- everything else, so this is the #220 contract, not the blind cadence #220
        -- retired. Without it every ch01 flow bailed on the first line of text (#232).
        if state == "dialogue_wait" and want ~= "dialogue_wait" then
            if not guardedInput("advance_dialogue", "A", "dialogue input wait clears", function(after)
                return controllerState(after) ~= "dialogue_wait"
            end, 60) then return false end
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

-- Select unit at (fx,fy), move to (tx,ty). True when the action menu opened.
local function moveUnit(fx, fy, tx, ty)
    if not awaitControllerState("player_map_idle", 300) then return false end
    if not cursorTo(fx, fy) then return false end
    if not guardedInput("select_unit", "A", "PlayerPhase enters movement-range input", function(after)
        return controllerState(after) == "unit_selected"
    end, 120) then return false end
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

local function chooseTalk()
    if not selectSemantic("talk", "Talk opens its live target selector", function(after)
        return controllerState(after) == "target_selection"
            and after.target and after.target.kind == "talk"
    end, 300) then return false end
    return guardedInput("confirm_target", "A", "Talk reaches FE8's dialogue input wait", function(after)
        return controllerState(after) == "dialogue_wait"
    end, 600)
end

-- Select Attack, an enabled weapon, and the current engine-selected target from live semantic
-- structures. `stopWhen` is an optional second exit for the combat wait. A kill that ENDS the
-- chapter starts the win event on the spot, which can keep the actor from ever being greyed out.
-- Dialogue advances only at TalkWaitForInput; a combat timeout fails closed without rescue input.
local function chooseAttack(actorAddr, stopWhen)
    if not selectSemantic("attack", "Attack opens the live weapon menu", function(after)
        return controllerState(after) == "weapon_menu"
    end, 300) then return false end
    if not selectSemantic("select_weapon", "weapon opens the live attack target selector", function(after)
        return controllerState(after) == "target_selection"
            and after.target and after.target.kind == "attack"
    end, 300) then return false end
    -- Commit proof has to be mode-agnostic. procs.battle is gProc_ekrBattle, the battle
    -- ANIMATION proc: a scenario that called pokeFastConfig() runs MAP combat, where it
    -- never spawns, so requiring it alone fails an attack that in fact resolved (#232 --
    -- it took out ch04packmath/ch04snag/clear_ch04 while the attacks all landed). The
    -- target selector closing is the signal common to both modes; the combat wait below
    -- is what proves the attack actually resolved, so this stays honest.
    if not guardedInput("confirm_target", "A", "target selection commits the attack", function(after)
        return after.procs.battle ~= nil or controllerState(after) ~= "target_selection"
    end, 300) then return false end
    -- Combat (with battle anims) ends when the actor is greyed out. The budget has to fit
    -- an animation NOBODY IS SKIPPING: the old 1200 was sized when waitFor still mashed A
    -- on a 50-frame cadence, which advanced the in-battle quote text. #220 retired that
    -- cadence on principle, and the ch00 boss animation then measured 1238 frames -- 38
    -- over, so every ch00/ch01 combat scenario timed out on a fight it had already won
    -- (#232). Vanilla's real worst cases are far longer than one clean round (crit, a
    -- double, a level-up, a promotion), so size this for those, not for the measurement.
    local done = waitFor(function()
        return (ru32(actorAddr + 0x0C) & 0x2) ~= 0 -- US_UNSELECTABLE
            or (stopWhen ~= nil and stopWhen())
    end, TUNE.combatFrames, true)
    if not done then
        traceFailure("await_combat", "actor becomes unavailable or scenario terminal fires",
            "fail:combat-timeout", nil, "controller-combat-timeout")
        freezeReport("controller combat timeout")
        return false
    end
    wait(30)
    return true
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
                local d = math.abs(tx - x) + math.abs(ty - y)
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

local function endTurn(tile)
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

-- End turn, then ride out the enemy phase. Returns "gameover" the moment the
-- game-over screen proc appears, "player" when control comes back, or nil.
local function runEnemyPhase(tile)
    if not endTurn(tile) then return nil end
    for _ = 1, 3600 do
        if gameOverActive() then return "gameover" end
        if faction() == 0 and not menuOpen() and controllerState() == "player_map_idle" then
            return "player"
        end
        if controllerState() == "dialogue_wait" then
            if not guardedInput("advance_dialogue", "A", "dialogue input wait clears", function(after)
                return controllerState(after) ~= "dialogue_wait"
            end, 60) then return nil end
        else
            yield()
        end
    end
    traceFailure("enemy_phase", "enemy phase reaches game over or returns player control",
        "fail:phase-timeout", nil, "controller-enemy-phase-timeout")
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
        return guardedInput("advance_dialogue", "A", "dialogue input wait clears", function(after)
            return controllerState(after) ~= "dialogue_wait"
        end, 120)
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

local function bootToMap(stopAtPrep)
    log("booting to map with observed FE8 states")
    local stalled = INSPECT.watch("boot")
    -- TUNE.bootSteps, never a literal: a cap that expires mid-scene reports a timeout that
    -- names nothing, which is how #232 stayed misdiagnosed for three sessions. The cap is
    -- sized above any real scene and INSPECT.watch is what decides failure.
    for _ = 1, TUNE.bootSteps do
        local observation = observeController()
        local state, why = controllerState(observation)
        if stalled(observation, state) then
            result("FAIL", "boot parked on an unclassified wait (see the inspect snapshot)")
            return false
        end
        if state == "player_map_idle" then
            if inChapter() then
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
        ru8(base + 0x10), ru8(base + 0x11), ru8(base + 0x55), ru16(base + 0x48) & 0xFF)
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
-- data, not pixels). Hung off INSPECT because harness.lua sits at Lua's 200-local ceiling.
INSPECT.units = function(tag)
    local factions = { { "blue", SYM.gUnitArrayBlue, 62 }, { "green", SYM.gUnitArrayGreen, 20 },
                       { "red", SYM.gUnitArrayRed, 50 } }
    for _, f in ipairs(factions) do
        local name, base, count = f[1], f[2], f[3]
        for i = 0, count - 1 do
            local u = unitAt(base, i)
            if u and (u.state & US_DEAD) == 0 then
                log(string.format(
                    '{"event":"unit","tag":"%s","faction":"%s","char":"0x%02x",'
                    .. '"x":%d,"y":%d,"hp":%d}', tag, name, u.charId, u.x, u.y, u.hp))
            end
        end
    end
end

-- The difficulty-mode oracle (#303). FE8 applies a mode as a per-chapter STAT
-- re-projection at unit-load time (UnitApplyBonusLevels, bmunit.c), gated on RED units
-- with pCharacterData->number >= 0x3C (eventscr.c:2328) -- so the proof that a mode
-- actually landed is the red force's stats, read on the map, not the menu we clicked.
-- Level is logged too and is expected NOT to move: UnitAutolevelPenalty restores
-- unit->level after re-autoleveling, so a shifted enemy displays its authored level
-- while carrying different stats. That is the trap this probe exists to make visible.
INSPECT.difficultyProbe = function(tag)
    local total = 0
    for i = 0, 49 do
        local u = unitAt(SYM.gUnitArrayRed, i)
        if u and (u.state & US_DEAD) == 0 then
            total = total + u.maxhp
            log(string.format(
                '{"event":"difficulty_unit","tag":"%s","char":"0x%02x","level":%d,'
                .. '"maxhp":%d,"pow":%d,"def":%d}',
                tag, u.charId, u.level, u.maxhp, u.pow, u.def))
        end
    end
    log(string.format('{"event":"difficulty_total","tag":"%s","red_maxhp":%d}', tag, total))
    return total
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
            and candidate.x ~= 0xFF then
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
            if not guardedInput("advance_dialogue", "A", "dialogue input wait clears", function(after)
                return controllerState(after) ~= "dialogue_wait"
            end, 120) then return result("FAIL", "smoke dialogue did not advance") end
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
-- The in-engine oracle for #303: does picking a difficulty mode actually change the
-- enemies? Boots to the map and reads the RED force's stats. Run once per mode --
--   PT_DIFFICULTY=tutorial|normal|difficult tools/playtest/run.sh difficulty
-- -- and compare the reported red maxHP totals: tutorial < normal < difficult, by the
-- three numbers the chapter DECLARES in its YAML `difficulty:` block. Reading the map
-- rather than the menu is the point: the menu only proves we clicked something.
scenarios.difficulty = function()
    if not bootToMap() then return result("FAIL", "never reached the map") end
    local actual, hard, controller = INSPECT.liveDifficulty()
    local total = INSPECT.difficultyProbe(actual)
    shot("difficulty-" .. actual)
    return result("PASS", string.format(
        "mode=%s (HARD=%s controller=%d) chapter=%d red maxHP total=%d",
        actual, tostring(hard), controller, chapter(), total))
end

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
            return isDead(red(CHAR_SEPHEK)) or chapter() ~= HOST_CHAPTER
        end) then
            result("FAIL", "combat did not reach its verified postcondition")
            return false
        end
        if not isDead(red(CHAR_SEPHEK)) then
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
        if isDead(red(CHAR_SEPHEK)) then
            log("Sephek dead; waiting for the chapter to end")
            shot("sephek-dead")
            local ended = waitFor(function() return chapter() ~= HOST_CHAPTER end, 3600, true)
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
    -- Inventory order is Hand Axe then Goodberry: one row down highlights the Goodberry and
    -- refreshes the name/description panel. The postcondition is the live highlight moving.
    local list = observeController().menu
    if not (list and #list.items >= 2) then
        return result("FAIL", "the inventory list did not come up with both of Hlin's items")
    end
    if not guardedInput("menu_next", "DOWN", "the inventory highlight moves to the Goodberry",
        function(after)
            return after.menu ~= nil and after.menu.current ~= list.current
        end, 60) then
        return result("FAIL", "could not move the inventory highlight onto the Goodberry")
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
-- One driver, every destination (#238). reachPrep, reachPrepPinky, lordfloor, ch01lord and
-- reachRbgCh01 were five copies of this route on a blind A-cadence; a copy that mashes A
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
    -- +0x40 bit 7) and type it fast. Written inline, not as a helper: harness.lua is at
    -- the 200-local ceiling (check_lua_local_headroom prints what is actually left -- never
    -- write that number down, it went stale in three places at once). Only gameSpeed --
    -- animationType is left alone so winCh00's combat is unaffected.
    -- DELIBERATELY NOT RESTORED: ckpt_prep/ckpt_lordpinky save AFTER this, so every record*
    -- scenario loading them inherits fast text. That is what we want for capture runs, but
    -- it IS a property of those checkpoints rather than an accident (#241).
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
            -- Scenario policy: which lead to take. The controller owns the live menu
            -- callback and the guarded input either way; no row is guessed and no
            -- candidate count is assumed -- the walk counts the LIVE item list.
            local rows = observation.menu and #observation.menu.items or 0
            local want = opts.lord
            if want == "last" then want = rows - 1 end
            if type(want) == "number" then
                if want < 0 or want >= rows then
                    result("FAIL", string.format(
                        "lead row %d is not in the live menu of %d candidates", want, rows))
                    return false
                end
                -- Walk off the LIVE cursor and stop when it ARRIVES, rather than pressing a
                -- fixed count: a fixed count reaches the wanted row only if the menu opened
                -- on row 0, which nothing guarantees, and FE8 menus WRAP -- so being wrong
                -- picks a different lead and passes anyway. The landing is asserted below
                -- either way, because nothing downstream re-checks which lead was taken
                -- (ckpt_lordpinky just saves the state) (#241).
                for _ = 1, rows do
                    local at = observeController()
                    if at.menu and at.menu.current == want then break end
                    if not guardedInput("menu_next", "DOWN", "the lead menu selection moves",
                        function(after, before)
                            return after.menu ~= nil and before.menu ~= nil
                                and after.menu.current ~= before.menu.current
                        end, 60) then
                        result("FAIL", "could not walk the lead menu to the chosen candidate")
                        return false
                    end
                end
                local landed = observeController()
                if not (landed.menu and landed.menu.current == want) then
                    result("FAIL", string.format(
                        "lead menu walk landed on row %s of %d, not row %d",
                        tostring(landed.menu and landed.menu.current), rows, want))
                    shot("ch01-lord-walk-lost")
                    return false
                end
            end
            local committing = observeController().menu
            opts.picked = committing and committing.current or want
            if not guardedInput("select_current_menu_item", "A", "lead menu selection closes", function(after)
                return after.menu == nil
            end, 300) then
                result("FAIL", "could not choose the highlighted lead"); return false
            end
            log(string.format("lead committed on menu row %s of %d", tostring(opts.picked), rows))
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
-- it commits through a semantic Attack/Wait. Mechanical failures terminate without rescue input.
local function clearUnitAct(u, field, goal, blocked, claimed, maxx, maxy)
    -- thread the REAL map bounds through: selectAndReach defaults to a 15x10
    -- window, which clipped every reach list at x=14 on ch01's 25x16 map -- the
    -- probable root cause of the #60 stall at exactly (14,8)
    local reach = selectAndReach(u, maxx, maxy)
    if not reach then return nil, true end
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
    if pick then committed = chooseAttack(u.addr) else committed = chooseWait() end
    if not committed then return tile, true end
    if claimed then claimed[CLEARBOT.tileKey(tile.x, tile.y)] = true end
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
        if not awaitControllerState("player_map_idle", 300) then return "stuck", t end
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
                    if failed then
                        if tile then
                            log(string.format("clear: unit (%d,%d) chose (%d,%d) but the "
                                .. "move didn't commit", u.x, u.y, tile.x, tile.y))
                        end
                        return "stuck", t
                    end
                elseif moveUnit(u.x, u.y, seizeTile.x, seizeTile.y) then
                    -- Boss dead, not yet won: select semantic Seize when this unit owns it.
                    -- A non-lead unit is cancelled through two independently legal B actions.
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
                    elseif not cancelUnitActionMenu() then
                        return "stuck", t
                    end
                end
            end
        end
        if won() then return "won", t end
        if lost() then return "gameover", t end
        local phase = runEnemyPhase(park)
        if phase == "gameover" then return "gameover", t end
        if phase ~= "player" then return "stuck", t end
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
                if not r then return nil, "controller could not enumerate live movement" end
                if r and not guardedInput("cancel_selection", "B",
                    "board export returns movement selection to player map", function(after)
                        return controllerState(after) == "player_map_idle"
                    end, 120) then return nil, "controller could not close movement selection" end
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
    local function reject(why)
        traceFailure("llm_order", "sidecar order remains legal in the live FE8 state",
            "fail:" .. why, nil, "controller-llm-order-rejected")
        return false
    end
    if type(o.unit) ~= "number" or type(o.move_to) ~= "table" then
        return reject("malformed-order")
    end
    local u = blue(o.unit)
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
    local function lost() return gameOverActive() or procActive(SYM.gProcScr_TitleScreen) end
    local budgetTurns = 18
    local seed = math.floor(tonumber(PLAYTEST_SEED) or 1)
    local n = 0
    for t = 1, budgetTurns do
        waitFor(function() return faction() == 0 and not menuOpen() end, 6000, true)
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
            if won then
                return result("PASS",
                    "Braulo seized the camp; ending + dev placeholder played -> title")
            end
            -- The seize did not end the chapter, so back out to the map on ENUMERATED
            -- cancels and retry next turn (#238). Two blind B's used to stand in for this:
            -- they could not tell how many levels deep the surprise was, so one too few left
            -- the run parked on a menu and one too many cancelled the unit selection as well.
            if not cancelToPlayerMap() then
                return result("FAIL", "could not back out of the post-seize screen")
            end
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

-- Drive ch00 win -> ch01 prep screen OPEN, default lord. true at the prep proc.
local function reachPrep() return reachCh01({ stopAtPrep = true }) end

-- Like reachPrep, but PICK THE LAST lord candidate (Pinky, not the default Braulo) so the
-- convoy/force-deploy lord-select fixes can be exercised for a NON-Braulo lord. The walk
-- to the last row now counts the LIVE menu instead of the LORD_CANDIDATES constant -- the
-- old copy would silently pick the wrong lord the day the roster changed.
local function reachPrepPinky() return reachCh01({ stopAtPrep = true, lord = "last" }) end

-- From the open prep screen, leave via Fight! and grind (escort poked frail+harmless) to
-- the seize-ready state: chief dead, Braulo moved ONTO the seize tile with its action
-- menu open (Seize on top). Returns true there -- the caller presses A to Seize.
local function leavePrepAndGrindToSeize()
    wait(180)
    -- Leave via the live Fight callback. The B/START/A flail this replaces was guessing
    -- at which key the prep screen would accept, and its `i % 4 == 0` A-press could
    -- commit whatever happened to be under the cursor (#238).
    if not driveThroughPrep() then return false end
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
            -- The move onto the seize tile did not open the menu; back out on enumerated
            -- cancels rather than two blind B's and retry on the next phase (#238).
            if not cancelToPlayerMap() then return false end
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
    local MARTY = 0x02                 -- marty rides CHARACTER_SETH
    local MARTY_ROW = 1                -- ...at row 1 of the lead menu (row 0 is Braulo)
    local BASE_HP, FLOOR_HP = 18, 25   -- base maxHP 18, floor +7 (difficulty --lord-floor oracle)
    local BASE_DEF, FLOOR_DEF = 2, 6   -- base def 2, floor +4
    local APPLIED = 0xFA               -- LORDFLOOR_APPLIED_FLAG (permanent)

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
    if isDeployedInPrep(CHAR_BRAULO) then
        local before = countDeployedPrep()
        if not guardedInput("toggle_deploy", "A", "Braulo leaves the deployed count", function()
            return not isDeployedInPrep(CHAR_BRAULO) and countDeployedPrep() < before
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
        tostring(isDeployedInPrep(CHAR_BRAULO)), countDeployedPrep()))
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
    waitFor(function() return faction() == 0 and not menuOpen() end, 1500, true)
    pinky = blue(CHAR_PINKY_LORD)
    for i = 0, 50 do
        local u = unitAt(SYM.gUnitArrayBlue, i)
        local beside = pinky and u and math.abs(u.x - pinky.x) + math.abs(u.y - pinky.y) == 1
        if u and u.charId ~= CHAR_PINKY_LORD and not beside
            and (u.state & 0x9) == 0 and u.x ~= 0xFF then
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
-- recordending: the ch01 "Rolling Cheddar" outro -> title. Named preset over recordCutscene:
-- load the seize checkpoint, tap Seize (the menu was saved open), then record the outro until
-- the title screen comes up (a final "title" shot once it does).
scenarios.recordending = function()
    -- The ch01 outro now MNC2s into the hosted ch02 (chapter advances); older builds landed
    -- on a dev placeholder -> title screen. Accept EITHER so the terminal isn't stale.
    local base
    return recordCutscene({
        state = "seize", tag = "end", maxFrames = 9000, pressEvery = 72,
        pre = function() press(K.A); wait(40) end,   -- Seize (menu saved open) -> the ending hand-off
        until_ = function()
            base = base or chapter()
            return procActive(SYM.gProcScr_TitleScreen) or chapter() ~= base
        end,
        post = function(reached)
            if reached and procActive(SYM.gProcScr_TitleScreen) then wait(120); shot("title") end
        end,
    })
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
    for _ = 1, 5000 do
        if menuOpen() then atPrep = true break end
        local observation = observeController()
        local state, why = controllerState(observation)
        local advanced = advanceBootState(observation, state)
        if advanced ~= true then
            local actions = Controller.legalActions(observation)
            traceInput(observation, actions, "recordlordfast_boot", "none", "lord selection menu",
                "fail:" .. tostring(why or "guarded boot input"), observation)
            break
        end
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
    if not eventFlag(LORDSEL_FLAG_BASE + route.picked) then
        return result("FAIL", string.format(
            "lord-choice permanent flag 0x%X (row %d) not set after confirm",
            LORDSEL_FLAG_BASE + route.picked, route.picked))
    end
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
        tostring(eventFlag(LORDSEL_FLAG_BASE + route.picked)),
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
    INSPECT.units("mapshot")
    for i = 1, 6 do
        wait(20)
        shot(string.format("mapshot-%02d-ch%d-turn%d", i, chapter(), turn()))
    end
    return result("PASS", "map deployed; screenshots taken")
end

-- MAPFULL: capture the WHOLE chapter map + units at their starting positions by panning the cursor
-- over a grid of tiles and screenshotting at each camera clamp; the camera pixel-scroll (gBmSt.camera
-- @ +0x0C/+0x0E) is baked into each frame's tag so make_gif/stitch_map.py can paste each 240x160
-- shot at its exact map offset. Fresh CH03BOOT New Game; clears the turn-1 entrance cutscene first.
scenarios.mapfull = function()
    if not bootToMap() then return result("FAIL", "never reached the map") end
    waitFor(function()
        return faction() == 0 and not menuOpen()
           and not procActive(SYM.ProcScr_StdEventEngine)
           and not procActive(SYM.ProcScr_BattleEventEngine)
    end, 900, true)
    -- The grid is DERIVED from the map, not written down. It used to be the literals
    -- {0,8,15} x {0,8,16}, which is ch03's 17x16 -- and this scenario is described as
    -- chapter-generic, so the constants were a chapter's shape wearing a generic name. On
    -- ch05 (15x21) they walked the cursor to x=16, off the map, and the run FAILED on an
    -- illegal input AFTER capturing every tile it needed: a verdict accusing the chapter of
    -- something the scenario did to itself (decisions.md -> "A scenario can FAIL on success").
    -- They also missed rows 16-20 entirely, so the "full map" would have been three-quarters
    -- of it, silently.
    -- One screen holds 15x10 tiles. Step the CURSOR by that and always finish on the far
    -- edge -- the camera follows the cursor and clamps itself, so cursor stops are what this
    -- has to generate, not camera offsets. (A first cut clamped EVERY stop to size-span and
    -- collapsed the tail: ch05's 21 rows came out as {0,10,11}, three shots of the top half
    -- that reported "full-map grid captured" all the same.)
    local mw, mh = mapSize()
    -- Cursor stops, not camera offsets: the camera follows and clamps itself, so the far EDGE
    -- has to be visited for the last screenful to come into shot. A map no bigger than one
    -- screen therefore needs exactly ONE stop -- appending `size-1` unconditionally made
    -- ch05's 15 columns two shots of the identical camera position, and ch03's 17 three.
    local function stops(size, span)
        if size <= span then return { 0 } end
        local out, p = { 0 }, span
        while p <= size - 1 do
            if p > size - span then p = size - 1 end   -- the far edge, visited once
            if p ~= out[#out] then table.insert(out, p) end
            if p == size - 1 then break end
            p = p + span
        end
        return out
    end
    local n = 0
    for _, cy in ipairs(stops(mh, 10)) do
        for _, cx in ipairs(stops(mw, 15)) do
            cursorTo(cx, cy)
            wait(24) -- let the camera glide + clamp settle
            local camx = ru16(SYM.gBmSt + 0x0C)
            local camy = ru16(SYM.gBmSt + 0x0E)
            n = n + 1
            shot(string.format("mapfull-%02d-cx%03d-cy%03d", n, camx, camy))
        end
    end
    return result("PASS", "full-map grid captured (" .. n .. " tiles of " .. mw .. "x" .. mh .. ")")
end

-- mapfullch05 (#25): the same pan against the ch05boot ROM, which is where the chapter's four
-- SKELETON enemy reskins can actually be judged -- sixteen risen tomb-guard standing on the
-- winter tileset, at the size and palette the player meets them at. A contact sheet of the
-- sheets cannot answer that: the enemy faction palette is applied by the ENGINE at runtime, so
-- the vendored blue is not the colour they wear, and the four have to read apart from EACH
-- OTHER at 16x16 as well as apart from the terrain.
-- One routine, two ROMs -- the pan is chapter-generic and the map decides what is in shot.
-- Delegates rather than aliases so matrix.py can attribute a body to the name (verdict cache).
scenarios.mapfullch05 = function()
    -- NO pokeFastConfig() here, and the absence is the note. It was added claiming to fix two
    -- timeouts, and it cannot: `bootToMap` goes through New Game, and `InitPlayConfig`
    -- (bmio.c:936) CpuFill16s gPlaySt to zero and sets textSpeed = 1, so any config poked
    -- before the boot is wiped. The run that passed after adding it passed for another reason
    -- -- an earlier run had already passed WITHOUT it (22s), so the timeouts are flake or
    -- something else, and are NOT root-caused. Do not re-add this believing it speeds the boot.
    return scenarios.mapfull()
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
-- Shoot frames across ANY combat that runs through gProc_ekrBattle -- attack, heal-cast, or
-- defend all funnel through the same proc, so this ONE loop serves all three capture paths
-- (#191 pulled it out of captureAttack so captureHeal/captureDefend can reuse it verbatim
-- instead of re-deriving it). Success = the battle proc actually ran AND real ANIM frames were
-- captured -- robust whether the actor survives, dies in the counter, or kills + triggers a
-- level-up that outlasts the budget. A stall before combat starts never sets sawAnim -> FAIL.
--
-- A talky foe (boss taunt / per-PC line) raises an in-battle QUOTE box during gProc_ekrBattle
-- (ProcScr_BattleEventEngine) that WAITS for A and would otherwise eat the whole budget before
-- the attack draws -- the bug that made every recordanim GIF show only the quote, never the
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
    return shootCombatFrames(tag, function() return (ru32(actorAddr + 0x0C) & 0x2) ~= 0 end)
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
    -- The recruits ride vanilla slots further down the table: Lupin the beast-cavalier is
    -- CHARACTER_DUESSEL. Read it off PORTRAIT_MAP, NOT off STAT_DONOR -- his stats come from
    -- Kyle (0x11) and his SLOT from Duessel (0x1D), and taking the donor for the slot puts
    -- `PT_CHAR=lupin` on a unit that is not on the map.
    lupin = 0x1D,
    -- Baxby the axe-beak: SLOT = Forde (0x10), stats from Franz (0x11's neighbour, CHARACTER_FRANZ)
    -- -- the same slot-vs-donor trap, so again this is PORTRAIT_MAP's value, not STAT_DONOR's.
    baxby = 0x10,
    -- ch05's pair (#25), and the slot-vs-donor trap one more time: Basil's stats come from
    -- Natasha and Sahnar's from Joshua, but their SLOTS are Artur and Marisa. Taking the
    -- donor here would aim PT_CHAR at a unit that is not on the sandbox map.
    basil = 0x13,   -- CHARACTER_ARTUR
    sahnar = 0x16,  -- CHARACTER_MARISA
}

-- Shared lead-up for the RBG demo: win the prologue, lord-select RBG into ch01,
-- stop on ch01 turn-1 player phase with RBG deployed. Returns (rbg unit) or (false, err).
-- Built ONCE at 240fps into the "rbgch01" checkpoint (ckpt_rbgch01); recordrbg LOADS it
-- so the slow prologue+lord-select grind isn't replayed every capture (#65).
local function reachRbgCh01()
    -- The shared migrated route again (#238), taking RBG's row as the lead. This was the
    -- fifth hand-rolled copy of the same save-menu/Northlook/lead-menu/prep walk; the blind
    -- version could not tell an input that landed from one FE8 swallowed, and its four
    -- literal DOWN presses assumed both the roster order and that the menu opened on row 0.
    -- Function-scoped, not a new top-level `local`: harness.lua is AT Lua's 200-local
    -- ceiling for the main chunk, and crossing it stops the whole file loading (#236).
    local RBG_ROW = 4
    local route = { lord = RBG_ROW }
    if not reachCh01(route) then return false, "could not reach ch01 with RBG as the lead" end
    if route.picked ~= RBG_ROW then
        return false, string.format("lead committed on row %s, not RBG's row %d",
            tostring(route.picked), RBG_ROW) end
    local rbg = blue(RBG_PID)
    if not rbg then return false, "RBG not on the field after lord-select" end
    return rbg
end

-- Relocate the unit straight onto a free tile within [mn,mx] of a live enemy, so a unit that
-- SPAWNS far from the fight doesn't have to march across the map (6 phases can't cross it -- a
-- far spawn timed out). Writes xPos/yPos AND moves the unit's entry in gBmMapUnit (vacate old
-- tile, occupy new) so the engine can still select it from the new tile. Attack availability
-- depends only on an enemy being in weapon range of the unit's TILE, not the terrain under it,
-- so any in-range, grid-free, in-bounds tile works. Prefers the farthest in-range tile (e.g. a
-- bow at exactly 2). Returns true if relocated.
local function teleportToFiringTile(u, mn, mx)
    local grid = mapUnitAt(u.x, u.y)        -- this unit's id in the grid (preserves faction bits)
    if grid == 0 then
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
    log(string.format("  teleportToFiringTile: no free tile within [%d,%d] of any of %d live enemies", mn, mx, #liveEnemies()))
    return false
end

-- True when the ENGINE would offer this unit an Attack command from its current tile: a hostile
-- sits within [mn,mx] of it in gBmMapUnit. The clear-bot asks first so its policy chooses Wait
-- when Attack will not appear; chooseAttack independently resolves the live semantic command.
local function canAttackFromHere(u, mn, mx)
    local w, h = mapSize()
    return CLEARBOT.gridHostileInReach(function(x, y)
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
        for i = 0, 23 do
            local r = unitAt(SYM.gUnitArrayRed, i)
            if r and not isDead(r) and mapUnitAt(r.x, r.y) ~= 0 then n = n + 1 end
        end
        return n
    end
    for i = 0, 19 do
        if onGrid() > 0 then break end
        local u = unitAt(SYM.gUnitArrayBlue, i)
        if u and not isDead(u) and (u.state & 0x2) == 0 then
            if moveUnit(u.x, u.y, u.x, u.y) then
                chooseWait()
                waitFor(function() return faction() == 0 and not menuOpen() end, 300)
            end
        end
    end
    local n = onGrid()
    log(string.format("  fog lifted: %d live reds now on gBmMapUnit", n))
    return n
end

-- Live blue units (excluding `excludePid`) as unitAt() tables, mirroring liveEnemies -- used by
-- the heal capture (#191) to find a wounded-ally target for a staff user.
local function liveAllies(excludePid)
    local out = {}
    for i = 0, 7 do
        local u = unitAt(SYM.gUnitArrayBlue, i)
        if u and not isDead(u) and u.charId ~= excludePid then out[#out + 1] = u end
    end
    return out
end

-- Halve the HP of the first other live ally so Heal has a valid (wounded) target (#191). Returns
-- the wounded unit, or nil if the healer has no other live ally in the sandbox.
local function woundAnAlly(healerPid)
    for _, a in ipairs(liveAllies(healerPid)) do
        local maxhp = ru8(a.addr + 0x12)
        emu:write8(a.addr + 0x13, math.max(1, math.floor(maxhp / 2)))
        return a
    end
    return nil
end

-- Like teleportToFiringTile but relocates u onto a free tile adjacent (range exactly 1) to one
-- of `targets` (live ALLY units, not enemies) -- stages the heal capture: put the staff user
-- within Heal's range of a wounded teammate. Same grid-write structure as teleportToFiringTile
-- (#191); kept separate because the search set is allies, not liveEnemies().
local function teleportAdjacentTo(u, targets)
    local grid = mapUnitAt(u.x, u.y)
    if grid == 0 then return false end
    for _, t in ipairs(targets) do
        for _, d in ipairs({ { 0, -1 }, { 0, 1 }, { 1, 0 }, { -1, 0 } }) do
            local tx, ty = t.x + d[1], t.y + d[2]
            if tx >= 0 and tx <= 24 and ty >= 0 and ty <= 15 and mapUnitAt(tx, ty) == 0 then
                setMapUnit(u.x, u.y, 0)
                emu:write8(u.addr + 0x10, tx); emu:write8(u.addr + 0x11, ty)
                setMapUnit(tx, ty, grid)
                log(string.format("  teleported to (%d,%d) [adjacent to ally (%d,%d)]", tx, ty, t.x, t.y))
                return true
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
        if reach and not guardedInput("cancel_selection", "B",
            "firing-position probe returns to player map", function(after)
                return controllerState(after) == "player_map_idle"
            end, 120) then return false end
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
    -- RBG deploys as its PLAIN vanilla class + a per-character _u25 anim (the clone-class
    -- path was retired in #65 M-B); this scenario just captures the shot, so class is logged
    -- for eyeballing, not asserted.
    wait(30) -- let the core settle past boot before loading
    if not loadState("rbgch01") then
        return result("FAIL", "no rbgch01 checkpoint (run.sh builds it)") end
    wait(60); pokeAnimsOn()
    local rbg = blue(RBG)
    if not rbg then return result("FAIL", "RBG not on the field after load") end
    local cls = ru8(ru32(rbg.addr + 0x04) + 0x04) -- pClassData->number
    log(string.format("RBG at (%d,%d) class=0x%X, firing", rbg.x, rbg.y, cls))
    shot("rbg-deploy")
    local fired = captureAttack(rbg.addr, "rbg"); shot("rbg-after")
    if not fired then
        return result("FAIL", "captureAttack never reached combat (stale checkpoint or stuck on menu)") end
    return result("PASS", string.format("RBG bow shot captured (class 0x%X)", cls))
end

-- Heal-cast capture (#191): the action menu is already open, positioned in Heal range of a
-- wounded ally. For a staff-only unit "Staff" sits at menu row 1 where "Attack" normally would,
-- and the staff list works exactly like the weapon list -- one A drills in, the Heal staff is
-- the sole/first entry -- so captureAttack's drill-in + target-confirm-cycle + frame-capture
-- shape applies completely unchanged; this wrapper just names the call for the heal path.
local function captureHeal(actorAddr, tag)
    return captureAttack(actorAddr, tag)
end

local TESTCH_PARK_TILE = { x = 24, y = 15 } -- empty far corner of the TESTCH sandbox's ch1 map
                                             -- (same corner CH01_PARK reuses later for the real ch01 seize)

-- Defend/dodge capture (#191): ride out the enemy phase watching gProc_ekrBattle, screenshotting
-- with the SAME shootCombatFrames loop as captureAttack/captureHeal -- but there is no menu to
-- drive and no actor-exhaustion flag to poll (the defender never acts), so stop once combat has
-- played and finished, or once control returns to the player with nothing having happened. The
-- caller decides whether a miss here is fatal (it isn't -- best-effort).
local function captureDefend(tag)
    if not endTurn(TESTCH_PARK_TILE) then return false end
    if not waitFor(function() return faction() ~= 0 end, 300) then return false end
    return shootCombatFrames(tag, function() return faction() == 0 end)
end

-- captureCharAnim's dispatch target when the cast member has no attack weapon (a staff-only
-- healer -- currently just Sclorbo, #191). Captures BOTH halves of the healer's battle anim:
--   1. heal-cast -- wound another ally, teleport the healer adjacent, open the menu, Heal them.
--   2. defend    -- full-heal the healer, neuter every live foe's pow, teleport him adjacent to
--                   one, end the turn, and let the enemy phase hit him (idle/dodge, no counter).
-- PASS requires the heal-cast to have animated; the defend is best-effort (logged, not fatal) --
-- e.g. no free tile next to a live enemy is a sandbox-composition problem, not a regression here.
local function captureHealerAnim(name, pid, cls)
    local u = blue(pid)
    local ally = woundAnAlly(pid)
    if not ally then
        return result("FAIL", name .. " has no other live ally to wound/heal (sandbox composition)") end
    log(string.format("%s: wounded ally char 0x%X at (%d,%d) to heal", name, ally.charId, ally.x, ally.y))
    if not teleportAdjacentTo(u, { ally }) then shot(name .. "-heal-noshot")
        return result("FAIL", name .. " never got adjacent to the wounded ally") end
    u = blue(pid)
    if not moveUnit(u.x, u.y, u.x, u.y) then shot(name .. "-heal-nomenu")
        return result("FAIL", name .. " action menu never opened next to the wounded ally") end
    shot(name .. "-heal-deploy")
    local healed = captureHeal(u.addr, name .. "-heal")
    shot(name .. "-heal-after")
    if not healed then
        return result("FAIL", string.format("captureHeal never reached combat for %s (class 0x%X)", name, cls)) end
    log(name .. ": heal-cast captured; staging the defend")

    local defended = false
    -- The heal-cast leaves the healer with US_HIDDEN (bmunit.c UnitBeginAction) still set for a
    -- few frames after combat ends -- it clears once MoveActiveUnit finalizes his post-battle
    -- position, which RefreshUnitsOnBmMap (bmmap.c) needs to re-place him in gBmMapUnit. A
    -- second raw teleport (below) reads mapUnitAt(u.x,u.y) as this unit's own grid id first --
    -- attempted too early it reads 0 (still hidden, not yet re-placed) and teleportToFiringTile
    -- bails, so wait for the bit to clear first (#191).
    local US_HIDDEN = 1
    waitFor(function()
        local uu = blue(pid)
        return uu and (uu.state & US_HIDDEN) == 0
    end, 180)
    u = blue(pid)
    if u and not isDead(u) then
        emu:write8(u.addr + 0x13, ru8(u.addr + 0x12))  -- full heal: survive whatever hits him
        for i = 0, 23 do
            local r = unitAt(SYM.gUnitArrayRed, i)
            if r and not isDead(r) then pokeHarmless(r) end  -- no death risk from any attacker
        end
        if teleportToFiringTile(u, 1, 1) then
            shot(name .. "-defend-deploy")
            defended = captureDefend(name .. "-defend")
            shot(name .. "-defend-after")
        else
            log(name .. ": no free tile adjacent to a live enemy -- defend can't be staged")
        end
    else
        log(name .. ": no longer live after the heal -- defend can't be staged")
    end
    if not defended then
        log(name .. ": defend NOT captured (best-effort; heal-cast alone is a PASS)")
    end

    return result("PASS", string.format(
        "%s heal-cast captured (class 0x%X); defend %s", name, cls, defended and "captured" or "NOT captured"))
end

-- Capture one cast member's battle anim on the TESTCH sandbox: find its deployed unit, read
-- its weapon reach, drive it to fire, and shoot frames tagged with its id (so make_gif picks
-- them up per character). Staff-only units (no attack weapon) dispatch to captureHealerAnim
-- instead (#191). The verdict is honest -- combat must actually start.
local function captureCharAnim(name)
    local pid = CAST[name]
    if not pid then
        return result("FAIL", "unknown cast id '" .. tostring(name) .. "' -- set PT_CHAR to one of: "
            .. "braulo marty meesmickle wolfram prof-rbg rootis sclorbo pinky lupin baxby") end
    wait(60); pokeAnimsOn()
    local u = blue(pid)
    if not u then return result("FAIL", name .. " not deployed -- build the ROM with `make TESTCH=1`") end
    local cls = ru8(ru32(u.addr + 0x04) + 0x04)
    local mn, mx = unitAttackRange(u)
    if not mn then
        return captureHealerAnim(name, pid, cls)
    end
    log(string.format("%s at (%d,%d) class=0x%X weapon-range %d-%d", name, u.x, u.y, cls, mn, mx))
    -- PT_ROUNDS>1 films SEVERAL engagements back to back (#25). One round shows one attack
    -- body, which is a thin look at a 12-mode imported animation -- the counter-attack, the
    -- dodge and (with a crit-capable weapon) the critical mode only appear across repeated
    -- exchanges. Rounds after the first are BEST-EFFORT: the sandbox foe can die, leaving
    -- nothing in reach, and a capture that already has usable footage must not be thrown
    -- away over that. So the FIRST round decides the verdict and the rest only add frames.
    local rounds = tonumber(PLAYTEST_ROUNDS) or 1
    if rounds < 1 then rounds = 1 end
    local done = 0
    for i = 1, rounds do
        -- A benign extra round must not cost the capture its verdict. `result()` rewrites a
        -- PASS into FAIL whenever controllerFault is latched, and a round that simply ran out
        -- of live foes latches one through endTurn/positionForShot -- so the loop's own
        -- "best-effort" promise was a lie until this line: 1/4 rounds reported FAIL while
        -- holding perfectly good footage. Snapshot the fault before each OPTIONAL round and
        -- restore it if that round bows out; round 1's faults are untouched and still fail.
        local faultBefore = controllerFault
        -- A unit that has attacked is SPENT for the rest of the player phase, so the second
        -- round has to start on a new turn -- not on a poked state bit. End the phase and let
        -- the enemy phase run; the unit comes back refreshed the way the game refreshes it,
        -- and the foes get to act, which is also what puts a COUNTER (and so her dodge mode)
        -- into the footage. A duelist who doubles kills the sandbox soldier outright, which is
        -- why one round only ever shows the attack body.
        if i > 1 then
            -- The battle proc is still tearing down when the last frame is shot, and an EXP
            -- bar or a level-up can follow it, so the map is a `transition` rather than idle.
            -- Ending the phase from there times out on player_map_idle -- which is what the
            -- first version of this loop did. Wait the combat OUT (tapping A to clear a
            -- level-up) before touching the menu.
            waitFor(function()
                return not procActive(SYM.gProc_ekrBattle) and faction() == 0
                    and not menuOpen() and not procActive(SYM.ProcScr_StdEventEngine)
            end, 1800, true)
            if not endTurn() then
                log(string.format("  round %d: could not end the phase -- stopping", i))
                controllerFault = faultBefore; break
            end
            if not waitFor(function() return faction() == 0 and not menuOpen()
                    and not procActive(SYM.ProcScr_StdEventEngine) end, 5400, true) then
                log(string.format("  round %d: player phase never came back -- stopping", i))
                controllerFault = faultBefore; break
            end
        end
        if not positionForShot(pid) then
            if i == 1 then shot(name .. "-noshot")
                return result("FAIL", name .. " never reached firing position") end
            log(string.format("  round %d: nothing left in reach -- stopping", i))
            controllerFault = faultBefore; break
        end
        if i == 1 then shot(name .. "-deploy") end
        local fired = captureAttack(u.addr, name)
        if not fired then
            if i == 1 then
                return result("FAIL", "captureAttack never reached combat for " .. name) end
            log(string.format("  round %d: never reached combat -- stopping", i))
            controllerFault = faultBefore; break
        end
        done = i
        u = blue(pid) or u          -- re-read: the unit moved to its firing tile
        wait(30)
    end
    shot(name .. "-after")
    return result("PASS", string.format("%s anim captured (class 0x%X, %d/%d round(s))",
        name, cls, done, rounds))
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

-- RECORDCAST (#25): the OTHER two thirds of a unit's art, on the same TESTCH sandbox
-- `recordanim` uses. `recordanim` proves the battle animation; this proves the PORTRAIT and the
-- MAP SPRITE, which have no other in-engine capture -- the unit list shows the map sprite at
-- 16px among twelve others and never shows the bust at all, so "the art is wired" was until now
-- something you could only argue from injected tables.
--
-- It cursors onto the unit (framing its map sprite under the hand) and opens the status screen,
-- where FE8 draws the 96x80 bust next to the name/class/stat block -- i.e. the portrait, the
-- name, the class and the stat line in ONE frame, which is exactly what a look-test needs to
-- approve or reject. Pick with PT_CHAR=<id>, same CAST table as recordanim.
scenarios.recordcast = function()
    if not bootToMap() then return result("FAIL", "never reached the map") end
    local name = (PLAYTEST_CHAR and PLAYTEST_CHAR ~= "") and PLAYTEST_CHAR or "prof-rbg"
    local pid = CAST[name]
    if not pid then return result("FAIL", "unknown PT_CHAR " .. tostring(name)) end
    local u = blue(pid)
    if not u then
        return result("FAIL", string.format(
            "%s (pid 0x%02X) is not deployed -- recordcast needs a `make TESTCH=1` ROM", name, pid))
    end
    wait(60)
    if not cursorTo(u.x, u.y) then
        return result("FAIL", string.format("cursor never reached %s at (%d,%d)", name, u.x, u.y))
    end
    wait(30)
    shot(name .. "-mapsprite")            -- the map sprite, cursor-framed on its own tile
    -- R is FE8's status-screen shortcut from the map cursor. Guarded on the PROC rather than a
    -- frame count: a blind press that lands on nothing would still shoot, and would hand back a
    -- picture of the map captioned "portrait" -- the exact class of green-but-wrong this bench
    -- exists to stop.
    press(K.R); wait(20)
    if not waitFor(function() return procActive(SYM.gProcScr_StatScreen) end, 240) then
        return result("FAIL", "the status screen never opened for " .. name)
    end
    wait(45)                               -- let the bust finish drawing before the first frame
    shot(name .. "-portrait")
    for page = 2, 3 do                     -- the stat screen's other two pages
        press(K.RIGHT); wait(45)
        shot(string.format("%s-portrait-p%d", name, page))
    end
    return result("PASS", string.format(
        "%s: map sprite + status screen captured (pid 0x%02X at (%d,%d))", name, pid, u.x, u.y))
end

-- RECORDRAVISIN (#19): the named ch05 boss is a raw CharacterData pid (0xB8), so she cannot
-- ride recordcast's blue CAST sandbox. Capture her on the real CH05BOOT map instead: the red
-- unit's live FE8 status screen proves the raw pid -> portraitId binding as well as the dressed
-- Riev graphics. A source-sheet preview cannot prove either half of that connection.
scenarios.recordravisin = function()
    local pid, name = 0xB8, "ravisin"
    -- FAST BEFORE the boot, not after: ch05's opening now plays 48 A-presses of dialogue
    -- BEFORE the map, and bootToMap drives all of it. Poking the config afterwards leaves that
    -- whole cutscene running at readable typewriter speed -- ~10000 frames, over half this
    -- scenario's 300s budget spent on a scene it does not film.
    pokeFastConfig()
    if not bootToMap() then return result("FAIL", "never reached the ch05 map") end
    if not waitFor(function()
        return faction() == 0 and not menuOpen()
            and not procActive(SYM.ProcScr_StdEventEngine)
            and controllerState() == "player_map_idle"
    end, 6000, true) then
        return result("FAIL", "ch05 never returned player control")
    end
    local u = red(pid)
    if not u then return result("FAIL", "Ravisin (pid 0xB8) is not in the red array") end
    if not cursorTo(u.x, u.y) then
        return result("FAIL", string.format("cursor never reached Ravisin at (%d,%d)", u.x, u.y))
    end
    wait(30)
    shot(name .. "-mapsprite")
    press(K.R); wait(20)
    if not waitFor(function() return procActive(SYM.gProcScr_StatScreen) end, 240) then
        return result("FAIL", "Ravisin's status screen never opened")
    end
    wait(45)
    shot(name .. "-portrait")
    return result("PASS", string.format(
        "Ravisin: real ch05 status screen captured (raw pid 0x%02X at (%d,%d))", pid, u.x, u.y))
end

-- Back-compat alias: recordrbgtest == recordanim for RBG.
scenarios.recordrbgtest = function()
    if not bootToMap() then return result("FAIL", "never reached the map") end
    return captureCharAnim("rbg")
end

-- RECORDENEMY (#90): capture a reskinned ENEMY class's battle anim on the SAME TESTCH sandbox
-- the PC cast is captured on (`recordanim`) -- one bench for every battle animation, no
-- chapter-specific boot. inject_test_chapter deploys one hostile of each enemy_class_reskins
-- slot as a foe; the money shot is the ATTACK swing, which a defender never plays, so a HARMLESS
-- (pow 0) player attacks the chosen foe at melee -> it survives and COUNTER-attacks, and
-- captureAttack shoots the whole battle. Needs `make TESTCH=1`. Pick the foe with PT_CHAR
-- (default kobold-grunt); the map keys the campaign.yaml enemy_class_reskins slot class ids.
local RESKIN_ENEMY_CLASS = {
    ["kobold-grunt"]   = 0x82,   -- CLASS_BRG_LIZARD_WILDLING
    ["kobold-blade"]   = 0x80,   -- CLASS_MNC_LIZARDZERKER
    ["kobold-brute"]   = 0x81,   -- CLASS_MNC_LIZARDZERKER_BRUTE
    ["goblin-soldier"] = 0x6A,   -- CLASS_BLST_REGULAR_EMPTY (fire imp, lance)
    ["goblin-fighter"] = 0x6B,   -- CLASS_BLST_LONG_EMPTY (fire imp, axe)
    -- ch05's risen tomb-guard (#25). These are the ids campaign.yaml's `slot_id` claims, and
    -- the bench grew a second ROW to seat them -- see SANDBOX_FOE_POSITIONS.
    ["risen-spear"]    = 0x84,   -- CLASS_SOL_SKELEBERDIER (skeleton lance)
    ["tomb-reaver"]    = 0x85,   -- CLASS_FGT_SKELEBERDIER (skeleton axe)
    ["crypt-blade"]    = 0x86,   -- CLASS_MNC_BONEWALKER (one-armed skeleton sword)
    ["bone-archer"]    = 0x87,   -- CLASS_ARC_WIGHT_SNIPER (skeleton bow)
}
-- Named RAW-PID creatures are picked by CHARACTER, not by class (the table lives inside the
-- scenario: this chunk is at the 200-local ceiling). Their anim binds through CharacterData
-- `_u25`, so the class alone does not identify them: on the sandbox the white moose is the
-- only CLASS_GWYLLGI, but the class is what a plain Gwyllgi would ALSO match, and matching it
-- would silently bench the stock hound. Match the pid the sandbox deploys.
scenarios.recordenemy = function()
    if not bootToMap() then return result("FAIL", "never reached the sandbox map") end
    wait(60); pokeAnimsOn()
    local sel = (PLAYTEST_CHAR and PLAYTEST_CHAR ~= "") and PLAYTEST_CHAR or "kobold-grunt"
    -- Raw-pid creatures the sandbox deploys under their OWN pid (RAW_PID_BATTLE_ANIMS).
    local wantPid = ({ ["white-moose"] = 0xb9,   -- ch05's cornered miniboss (#25)
                       ["ravisin"]     = 0xb8 }) -- ch05's frost-druid boss (#25)
                    [sel]
    local want = (not wantPid) and (RESKIN_ENEMY_CLASS[sel] or tonumber(sel)) or nil
    if not want and not wantPid then
        return result("FAIL", "unknown enemy '" .. sel .. "' -- one of: "
            .. "kobold-grunt kobold-blade kobold-brute white-moose ravisin, or a raw class id "
            .. "(e.g. 0x82)") end
    local function classOf(u) return ru8(ru32(u.addr + 0x04) + 0x04) end
    -- the chosen foe: by CHARACTER for a raw-pid creature, by CLASS for a class-level reskin
    local foe
    for i = 0, 23 do
        local r = unitAt(SYM.gUnitArrayRed, i)
        if r and not isDead(r) then
            if (wantPid and r.charId == wantPid) or (want and classOf(r) == want) then
                foe = r; break
            end
        end
    end
    if not foe then
        return result("FAIL", string.format(
            "no live foe %s in the sandbox (build with `make TESTCH=1`)",
            wantPid and string.format("with pid 0x%X", wantPid)
                    or string.format("of class 0x%X", want))) end
    -- A bait whose reach OVERLAPS THE FOE'S, which is not always a melee one. A bow cannot
    -- counter at range 1, so an adjacent bait films nothing: the archer simply takes the hit
    -- and the run reports no anim. Approach it with a bow or a tome instead and it answers at
    -- range 2 (Nicolas, 2026-08-20 -- RBG is our archer and this is how he fights). That is
    -- also why CLASS_ARCHER was missing from the bench's weapon table; the gap was this
    -- picker, not the class.
    local fmin, fmax = unitAttackRange(foe)
    if not fmin then
        return result("FAIL", "the chosen foe carries no weapon, so it can never counter")
    end
    local pl, plmn, plmx, dist
    for i = 0, 15 do
        local u = unitAt(SYM.gUnitArrayBlue, i)
        if u and not isDead(u) then
            local mn, mx = unitAttackRange(u)
            if mn then
                for d = fmin, fmax do          -- a distance BOTH can strike at
                    if d >= mn and d <= mx then pl, plmn, plmx, dist = u, mn, mx, d; break end
                end
            end
        end
        if pl then break end
    end
    if not pl then
        return result("FAIL", string.format(
            "no player unit whose reach overlaps the foe's %d-%d -- the bait has to be able to "
            .. "hit it at a distance it can answer at", fmin, fmax))
    end
    -- All live foe tiles: the sandbox packs several reskins in a row, so we must place the
    -- player on a tile orthogonally adjacent to ONLY the target -- otherwise captureAttack's
    -- cursor can land on a neighbouring foe (e.g. the sword Lizardzerker next to the axe grunt)
    -- and we'd capture the WRONG class's anim.
    local foeTiles = {}
    for i = 0, 23 do
        local r = unitAt(SYM.gUnitArrayRed, i)
        if r and not isDead(r) then foeTiles[r.x .. "," .. r.y] = true end
    end
    local grid = mapUnitAt(pl.x, pl.y)
    local placed = false
    -- Every tile at Manhattan `dist` from the foe, vertical offsets first: the bench is laid
    -- out in ROWS, so a tile above or below the target has fewer foe neighbours than one
    -- beside it. At dist 1 this is exactly the old {0,-1},{0,1},{1,0},{-1,0}.
    -- ORDER IS EXPLICIT, not sorted. A comparator on |dx| leaves {0,-1} and {0,+1} tied, and
    -- table.sort is not stable, so "up first" was luck -- and it stopped being lucky: the
    -- rewrite put DOWN first, which on the bench's y=9 row is straight off the map.
    -- UP before DOWN before sideways, nearest column outward, so a row of foes still gets the
    -- tile with the fewest neighbours and the bottom row still gets a tile that EXISTS.
    local ring = {}
    for adx = 0, dist do
        for _, dx in ipairs(adx == 0 and { 0 } or { -adx, adx }) do
            local dy = dist - math.abs(dx)
            if dy ~= 0 then table.insert(ring, { dx, -dy }) end   -- up
            table.insert(ring, { dx, dy })                        -- down (dy==0 -> sideways)
        end
    end
    -- BOUNDS FROM THE MAP. The guard was `tx <= 24 and ty <= 15`, a literal from a bigger
    -- chapter, and the sandbox is 15x10: y=10 is off the map but `mapUnitAt` reads gBmMapUnit's
    -- zero-filled border row and answers "empty", so the tile is accepted and `cursorTo` can
    -- then never reach it. Same class of bug as mapfull's hardcoded grid, one file over.
    local mw, mh = mapSize()
    for _, d in ipairs(ring) do
        local tx, ty = foe.x + d[1], foe.y + d[2]
        if tx >= 0 and tx < mw and ty >= 0 and ty < mh and mapUnitAt(tx, ty) == 0 then
            -- No OTHER foe inside the BAIT'S OWN reach -- which is what makes the attack menu
            -- ambiguous and lets captureAttack film the wrong creature. At melee this is the
            -- old "nothing else orthogonally adjacent"; at range it correctly widens.
            local clean = true
            for key in pairs(foeTiles) do
                local nx, ny = key:match("^(-?%d+),(-?%d+)$")
                nx, ny = tonumber(nx), tonumber(ny)
                if not (nx == foe.x and ny == foe.y) then
                    local md = math.abs(nx - tx) + math.abs(ny - ty)
                    if md >= plmn and md <= plmx then clean = false; break end
                end
            end
            if clean then
                setMapUnit(pl.x, pl.y, 0)
                emu:write8(pl.addr + 0x10, tx); emu:write8(pl.addr + 0x11, ty)
                setMapUnit(tx, ty, grid)
                pl.x, pl.y = tx, ty
                placed = true; break
            end
        end
    end
    if not placed then
        return result("FAIL", string.format(
            "no tile at range %d from ONLY the target foe (bait reach %d-%d)", dist, plmn, plmx))
    end
    pokeHarmless(pl)                       -- pow 0: the player's hit can't kill -> the foe counters
    -- ONE description of what we baited, used by both the log and the verdict: a raw-pid
    -- creature has no `want` class and a reskin has no `wantPid`, so formatting either
    -- unconditionally throws (it did, on this scenario's first moose run).
    local what = wantPid and string.format("pid 0x%X", wantPid)
                          or string.format("class 0x%X", want)
    log(string.format("baiting %s (%s) at (%d,%d) with player at (%d,%d)",
        sel, what, foe.x, foe.y, pl.x, pl.y))
    if not moveUnit(pl.x, pl.y, pl.x, pl.y) then
        return result("FAIL", "action menu never opened on the firing tile") end
    shot(sel .. "-deploy")
    local fired = captureAttack(pl.addr, sel); shot(sel .. "-after")
    if not fired then return result("FAIL", "captureAttack never reached combat") end
    return result("PASS", string.format("%s anim captured (baited %s counter)", sel, what))
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
-- the decomp + the ch02 build (CH02_CHWINGA / CH02_ITEM_IDS in tools/build_campaign.py).
local CH02_CHWINGA_PIDS = { 0xCA, 0xC9, 0xC8 }   -- DARA/KLIMT/MANSEL = Mote/Rime/Glimmer (green)
local CH02_CHARMS = { 0x28, 0x6D, 0x6E }         -- Hand Axe / Elixir / Pure Water (Mote's Red Gem moved to ch03's chest, #23)
local CLASS_ARCHER = 0x19                          -- the fliers-vs-bows debut enemy (CH02_CLASS_IDS)
local CH02_CHAPTER = 3                             -- ch02 hosts on chapter slot 3 (ch01 -> MNC2(0x3))
local CH03_CHAPTER = 4                             -- ch03 hosts on chapter slot 4 (ch02 ending -> MNC2(0x4))
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
        if not waitFor(function() return faction() == 0 and not menuOpen() end, 6000, true) then
            traceFailure("ch01_seize", "player phase returns before the next move",
                "fail:player-phase-timeout", nil, "ch01-seize-phase-timeout")
            return "controller"
        end
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
                if not moveUnit(lord.x, lord.y, lord.x, lord.y) then return "controller" end
                if not chooseAttack(lord.addr) then return "controller" end
            else
                if not marchToward(lord, goal.x, goal.y + 1, 24, 15) then return "controller" end
            end
        else
            if moveUnit(lord.x, lord.y, goal.x, goal.y) then
                local actions = Controller.legalActions(observeController())
                if not Controller.findAction(actions, "seize") then
                    traceFailure("seize", "live unit menu exposes semantic Seize",
                        "fail:seize-not-legal", nil, "ch01-seize-missing")
                    return "controller"
                end
                if not selectSemantic("seize", "Seize starts the ch01 win event", function()
                    return procActive(SYM.ProcScr_StdEventEngine) or chapter() ~= 2
                end, 900) then return "controller" end
            else
                return "controller"
            end
            if waitFor(function() return chapter() ~= 2 end, 9000, true) then return "won" end
            traceFailure("seize", "ch01 advances after the Seize event",
                "fail:chapter-advance-timeout", nil, "ch01-seize-timeout")
            return "controller"
        end
        local phase = runEnemyPhase(CH01_PARK)
        if phase == "gameover" then return "gameover" end
        if phase ~= "player" then return "controller" end
    end
    return "timeout"
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
        for j = 0, 7 do local u = unitAt(SYM.gUnitArrayBlue, j)
            if u and (u.state & 0x9) == 0 and u.x ~= 0xFF then return true end end
        return false
    end
    for _ = 1, 16000 do
        if chapter() == CH02_CHAPTER and faction() == 0 and turn() >= 1
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
    for _, pid in ipairs(CH02_CHWINGA_PIDS) do
        local g = findUnit(SYM.gUnitArrayGreen, 20, pid)
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
-- 0xaa generics + the 0xb7 grell) so its flagged death keys the trigger to it alone. Same
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
        local bgrid = mapUnitAt(b.x, b.y)
        local parked = false
        for _, d in ipairs({ { 1, 0 }, { -1, 0 }, { 0, 1 }, { 0, -1 } }) do
            local tx, ty = leader.x + d[1], leader.y + d[2]
            if tx >= 0 and tx <= 24 and ty >= 0 and ty <= 15 and mapUnitAt(tx, ty) == 0 then
                setMapUnit(b.x, b.y, 0)
                emu:write8(b.addr + 0x10, tx); emu:write8(b.addr + 0x11, ty)
                setMapUnit(tx, ty, bgrid)
                log(string.format("turn %d: Brute parked at (%d,%d) next to braulo (%d,%d)",
                    turn, tx, ty, leader.x, leader.y))
                parked = true
                break
            end
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
    local function blueTrex() return findUnit(SYM.gUnitArrayBlue, 20, CHAR_TREX) end
    local trex = findUnit(SYM.gUnitArrayGreen, 12, CHAR_TREX)
    if not trex then return result("FAIL", "green Trex (0x1C) not found in the green array") end
    if blueTrex() then return result("FAIL", "Trex is already blue before any talk") end
    local rec = blue(0x01) -- the leader is always deployed and is a recruit candidate
    if not rec then return result("FAIL", "leader (0x01) not deployed") end
    log(string.format("green Trex at (%d,%d); recruiter at (%d,%d)", trex.x, trex.y, rec.x, rec.y))
    shot("ch03talk-green")
    -- Park the recruiter on a free tile orthogonally adjacent to Trex.
    local rgrid = mapUnitAt(rec.x, rec.y)
    local parked = false
    for _, d in ipairs({ { 1, 0 }, { -1, 0 }, { 0, 1 }, { 0, -1 } }) do
        local tx, ty = trex.x + d[1], trex.y + d[2]
        if tx >= 0 and tx <= 24 and ty >= 0 and ty <= 15 and mapUnitAt(tx, ty) == 0 then
            setMapUnit(rec.x, rec.y, 0)
            emu:write8(rec.addr + 0x10, tx); emu:write8(rec.addr + 0x11, ty)
            setMapUnit(tx, ty, rgrid)
            log(string.format("recruiter parked at (%d,%d), adjacent to Trex (%d,%d)", tx, ty, trex.x, trex.y))
            parked = true
            break
        end
    end
    if not parked then return result("FAIL", "no free tile adjacent to Trex to park the recruiter") end
    -- Select the recruiter (no move) -> command menu. Parked next to ISOLATED green Trex in the
    -- galleries (no enemy in weapon range), Talk is the first command row -- no Attack precedes it.
    rec = blue(0x01)
    waitFor(function() return faction() == 0 and not menuOpen() end, 300, true)
    if not moveUnit(rec.x, rec.y, rec.x, rec.y) then
        shot("ch03talk-no-menu")
        return result("FAIL", "could not open the recruiter's command menu")
    end
    wait(30); shot("ch03talk-menu")
    if not chooseTalk() then return result("FAIL", "live command menu did not expose a working Talk") end
    shot("ch03talk-dialogue-1") -- Trex's migrated talk lines rendering in-engine
    local pages = 1
    for _ = 1, 3600 do      -- advance only when FE8 exposes TalkWaitForInput
        if blueTrex() then break end
        if controllerState() == "dialogue_wait" then
            pages = pages + 1
            if pages <= 5 then shot(string.format("ch03talk-dialogue-p%d", pages)) end
            if not guardedInput("advance_dialogue", "A", "dialogue input wait clears", function(after)
                return controllerState(after) ~= "dialogue_wait"
            end, 120) then return result("FAIL", "Talk dialogue input did not advance") end
        else
            yield()
        end
    end
    wait(30); shot("ch03talk-after")
    for i = 0, 19 do -- dump the full blue roster so the flip is unambiguous
        local u = unitAt(SYM.gUnitArrayBlue, i)
        if u then log(string.format("  blue[%02d] char=0x%02X pos=(%d,%d)", i, u.charId, u.x, u.y)) end
    end
    local nowBlue = blueTrex() ~= nil
    local stillGreen = findUnit(SYM.gUnitArrayGreen, 12, CHAR_TREX) ~= nil
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
    for i = 0, 23 do
        local u = unitAt(SYM.gUnitArrayBlue, i)
        if u then
            party = party + 1
            -- on the field = not US_HIDDEN (1<<0) and not US_NOT_DEPLOYED (1<<3), real tile
            if (u.state & 0x9) == 0 and u.x ~= 0xFF then deployed = deployed + 1 end
            log(string.format("  blue[%02d] char=0x%02X pos=(%d,%d) state=0x%08X",
                i, u.charId, u.x, u.y, u.state))
        end
    end
    local CHAR_TREX = 0x1C
    if findUnit(SYM.gUnitArrayBlue, 20, CHAR_TREX) then
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

-- CH03DOOR (#23 chests/doors): prove the door tile-change wiring end-to-end in-engine. Boot to the
-- ch03 map, hand a deployed unit a Door Key (and strip its weapon so the command menu is [Door,
-- Item, Wait] -- Door at row 0, deterministic), park it beside the (2,3) door, drive Door, and
-- assert gBmMapBaseTiles[3][2] flips from the closed door (812<<2) to the floor tile below it
-- (492<<2, per Nicolas's "the tile directly below"). Run: PT_HOST_CHAPTER=4 run.sh ch03door
-- (needs a CH03BOOT=1 ROM). The chest path shares this MapChange array -- verifying the door proves
-- both mechanisms (GetMapChangeIdAt -> CallTileChangeEvent -> ApplyMapChangesById).
scenarios.ch03door = function()
    if not bootToMap() then return result("FAIL", "never reached the ch03 map") end
    local DX, DY = 2, 3
    local CLOSED, OPEN_T = 812 * 4, 492 * 4   -- gBmMapBaseTiles holds metatile<<2
    local pre = baseTile(DX, DY)
    log(string.format("door (%d,%d) tile before = %d (want closed %d)", DX, DY, pre, CLOSED))
    if pre ~= CLOSED then
        return result("FAIL", string.format(
            "door (%d,%d) reads %d, not the closed-door tile %d -- placement or gBmMapBaseTiles addr wrong",
            DX, DY, pre, CLOSED))
    end
    -- Grab the first deployed blue unit (on the field: not US_HIDDEN|US_NOT_DEPLOYED, real tile).
    local u
    for i = 0, 23 do
        local c = unitAt(SYM.gUnitArrayBlue, i)
        if c and (c.state & 0x9) == 0 and c.x ~= 0xFF then u = c break end
    end
    if not u then return result("FAIL", "no deployed blue unit to open the door") end
    -- Door Key in slot 0 (0x6A, 1 use), zero the rest -> no weapon -> no Attack row.
    emu:write16(u.addr + 0x1E, 0x6A | (0x01 << 8))
    for s = 1, 4 do emu:write16(u.addr + 0x1E + s * 2, 0) end
    -- Park orthogonally adjacent to the door on a known-passable floor cell ((2,2) floor / (2,4) road;
    -- the door's left/right are wall frame). Vacate the old tile, occupy the new -- cursor-select
    -- reads gBmMapUnit, not xPos (cf. the ch03talk park trick).
    local grid = mapUnitAt(u.x, u.y)
    local parked
    for _, t in ipairs({ { DX, DY - 1 }, { DX, DY + 1 } }) do
        if mapUnitAt(t[1], t[2]) == 0 then
            setMapUnit(u.x, u.y, 0)
            emu:write8(u.addr + 0x10, t[1]); emu:write8(u.addr + 0x11, t[2])
            setMapUnit(t[1], t[2], grid)
            parked = t
            break
        end
    end
    if not parked then return result("FAIL", "no free tile adjacent to the (2,3) door to park a unit") end
    log(string.format("parked opener at (%d,%d), adjacent to the door", parked[1], parked[2]))
    shot("ch03door-before")
    -- Select (no move) -> command menu, then resolve the live Door command (#238). This used
    -- to press A on "Door (row 0)" and then a SECOND A to "confirm the door target" -- but
    -- DoorCommandEffect (bmmenu.c) returns MENU_ACT_END: it sets gActionData and the menu is
    -- gone, there is no target step. So the first press depended on Door happening to be the
    -- top row, and the second went into whatever the map put up next.
    waitFor(function() return faction() == 0 and not menuOpen() end, 300, true)
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
    for i = 0, 23 do
        local c = unitAt(SYM.gUnitArrayBlue, i)
        if c and (c.state & 0x9) == 0 and c.x ~= 0xFF then u = c break end
    end
    if not u then return result("FAIL", "no deployed blue unit to open the chest") end
    -- Chest Key in slot 0 (0x69, 1 use), zero the rest -> no weapon (no Attack) + free slots for the loot.
    emu:write16(u.addr + 0x1E, 0x69 | (0x01 << 8))
    for s = 1, 4 do emu:write16(u.addr + 0x1E + s * 2, 0) end
    -- Chests open from ON the tile: teleport the opener onto (6,3) (vacate old tile, occupy the chest).
    if mapUnitAt(CX, CY) ~= 0 then return result("FAIL", "the (6,3) chest tile is already occupied") end
    setMapUnit(u.x, u.y, 0)
    local grid = 1  -- blue army slot-1 grid marker isn't needed; any non-zero registers occupancy
    emu:write8(u.addr + 0x10, CX); emu:write8(u.addr + 0x11, CY)
    setMapUnit(CX, CY, grid)
    shot("ch03chest-before")
    waitFor(function() return faction() == 0 and not menuOpen() end, 300, true)
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
    for i = 0, 23 do
        local c = unitAt(SYM.gUnitArrayBlue, i)
        if c and (c.state & 0x9) == 0 and c.x ~= 0xFF then u = c break end
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
    local grid = mapUnitAt(u.x, u.y)
    local moved = false
    for y = 1, 14 do
        for x = 1, 15 do
            if FLOOR[terr(x, y)] and mapUnitAt(x, y) == 0
                and mapUnitAt(x - 1, y) == 0 and mapUnitAt(x + 1, y) == 0
                and mapUnitAt(x, y - 1) == 0 and mapUnitAt(x, y + 1) == 0 then
                setMapUnit(u.x, u.y, 0)
                emu:write8(u.addr + 0x10, x); emu:write8(u.addr + 0x11, y)
                setMapUnit(x, y, grid)
                log(string.format("relocated the holder to the isolated tile (%d,%d)", x, y))
                moved = true
                break
            end
        end
        if moved then break end
    end
    if not moved then return result("FAIL", "no isolated floor tile found to open a clean Item menu") end
    u = unitAt(SYM.gUnitArrayBlue, 0) and u   -- addr stable
    waitFor(function() return faction() == 0 and not menuOpen() end, 300, true)
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
    -- The engine only spawns a unit's STANDING map sprite during a sprite refresh
    -- (RefreshUnitSprites, fired on phase transitions / menu exits, bmio.c) -- a memory-poked
    -- deploy sets his position but never creates the sprite object. So make every enemy
    -- frail+harmless (a safe enemy phase) and cycle ONE enemy phase back to player: that refresh
    -- draws Baxby's real, injected map sprite (the same one ch03 renders) so the still shows him.
    pokeFastConfig()   -- map-anim + fast so the refresh phase is quick
    for i = 0, 23 do
        local r = unitAt(SYM.gUnitArrayRed, i)
        if r and not isDead(r) then pokeFrail(r); pokeHarmless(r) end
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
    -- charm-gifts (CHECK_ALIVE -> GIVEITEMTO) are captured before the MNC2(0x4) chain reloads into
    -- ch03 (slot 4) and PREP re-picks the convoy/inventory. (Coarse polling skipped the charm window.)
    -- The ch02->ch03 chain (#23) replaced the old dev-placeholder->title landing: the ending now
    -- MNC2s straight into ch03, so we A-mash through it until chapter() == 4 (ch03), not the title.
    if routed and not advanced() then endTurn() end
    local reachedCh03 = false
    local watchEnding = INSPECT.watch("clear_ch02_ending")
    for _ = 1, TUNE.bootSteps do
        snapCharms()
        if chapter() == CH03_CHAPTER then reachedCh03 = true; snapCharms(); break end
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
    log(string.format("charms delivered: %d/3; reached ch03=%s (chapter=%d)",
        #best, tostring(reachedCh03), chapter()))
    if #best < 3 then
        return result("FAIL", string.format(
            "ch02 charm-gift broken: only %d/3 chwinga charms reached the leader/convoy", #best)) end
    if not reachedCh03 then
        return result("FAIL", "ch02->ch03 chain broken: ending did not MNC2 into ch03 (slot 4)") end
    result("PASS", "ch02 routed + chained into ch03; all 3 chwinga charms delivered (CHECK_ALIVE -> GIVEITEMTO)")
end

-- recordchain: a REVIEW GIF of the ch02 -> ch03 chain in motion (#23 chaining pass). Loads the
-- ch02start checkpoint, routs the raiders at top speed (same deterministic rout as clear_ch02),
-- fires the DefeatAll win, then records the ch02 ending -> MNC2(0x4) -> ch03 opening -> Preparations
-- as normal-speed motion frames (recordCutscene from the current position, no reload). Turn the
-- frames into a GIF with: tools/playtest/make_gif.py recordchain chain --name ch02-ch03-chain
scenarios.recordchain = function()
    wait(30)
    if not loadState("ch02start") then return result("FAIL", "no ch02start checkpoint (run.sh builds it)") end
    wait(90)
    pokeFastConfig()
    local start = chapter()
    local function advanced() return chapter() ~= start or procActive(SYM.gProcScr_TitleScreen) end
    local routed = false
    for t = 1, 12 do
        if advanced() then break end
        waitFor(function() return faction() == 0 and not menuOpen() end, 6000, true)
        wait(60)
        protectChwinga()   -- keep the chwinga alive so all 3 charm-gifts play in the ending
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
                    u = blue(u.charId)
                    if u and moveUnit(u.x, u.y, u.x, u.y) then
                        chooseAttack(u.addr)
                        waitFor(function() return faction() == 0 and not menuOpen()
                            and not procActive(SYM.gProc_ekrBattle) end, 600)
                    end
                end
            end
        end
        log(string.format("recordchain rout turn %d: liveEnemies=%d chapter=%d", t, #liveEnemies(), chapter()))
        if #liveEnemies() == 0 then routed = true; break end
        if advanced() then break end
        if runEnemyPhase(CH02_PARK) == "gameover" then
            return result("FAIL", string.format("game over on turn %d -- party lost before the chain", t)) end
    end
    if not (routed or advanced()) then return result("FAIL", "could not rout ch02 -- no chain to record") end
    if routed and not advanced() then endTurn() end   -- fire the DefeatAll win -> the ending auto-plays
    -- Record the ending -> MNC2(0x4) -> ch03 opening -> PREP from HERE (no state reload). Normal speed
    -- so the text/fades animate for the GIF; A-mash to advance beats; stop when ch03 Preparations opens.
    return recordCutscene{ tag = "chain", until_ = "prep", speed = "normal",
                           pressEvery = 24, shotEvery = 3, maxFrames = 9000 }
end

-- ---- ch02 demo GIFs (#22 review): showcase the chapter on a phone via committed GIFs.
-- make_gif.py turns the tagged frames into a GIF under docs/demo/; commit it on the feature branch
-- for GitHub review (and prune it before merge unless a live doc links it). Workflow:
--   tools/playtest/run.sh recordch02intro && tools/playtest/make_gif.py recordch02intro intro --name ch02-opening
--   tools/playtest/run.sh recordch02map   && tools/playtest/make_gif.py recordch02map   map   --name ch02-map

-- ckpt_ch02intro: stop at the very start of ch02 (slot 3), BEFORE the opening cutscene plays,
-- so recordch02intro can replay the title card + Vellynne/chwinga beats at viewable speed.
scenarios.ckpt_ch02intro = function()
    if not reachCh01Map() then return end
    local status = seizeCh01ToCh02()
    if status ~= "won" then return result("FAIL", "ch01 seize failed (" .. status .. ")") end
    if not waitFor(function() return chapter() == CH02_CHAPTER end, 600) then
        return result("FAIL", "ch02 never began") end
    -- Advance past the title-card transition into the first STABLE opening dialogue beat before
    -- saving -- a state grabbed mid-transition crashes on resume (mGBA exited early). Wait for the
    -- map event engine to be running, then let the scene settle on a dialogue box.
    waitFor(function() return procActive(SYM.ProcScr_StdEventEngine) end, 600)
    wait(180)
    saveState("ch02intro")
    result("PASS", "ch02intro checkpoint saved (ch02 opening, first beat)")
end

-- (recordCutscene is defined up in the helpers section, before its first caller
--  recordending -- a local function is only visible lexically AFTER its definition.)

-- recordscene: record ANY dialogue cutscene without writing new Lua -- point it at a
-- pre-built save-state + a terminal condition via env vars. run.sh builds the checkpoint
-- named by PT_STATE (builder ckpt_<PT_STATE>) if it's missing/stale. Examples:
--   PT_STATE=ch02intro PT_TAG=intro PT_UNTIL=prep                   tools/playtest/run.sh recordscene
--   PT_STATE=seize     PT_TAG=end   PT_UNTIL=title PT_PRESSEVERY=72 tools/playtest/run.sh recordscene
scenarios.recordscene = function()
    -- Config arrives as PLAYTEST_* wrapper globals (run.sh maps PT_* -> PLAYTEST_*); mGBA's
    -- sandboxed lua has no os.getenv, so the whole harness uses injected globals, not the env.
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

-- recordch02intro: the ch02 opening in motion -- title card "Ch.2: Cold Welcome" + the Vellynne
-- and chwinga-adoption beats (custom busts + Mote/Rime/Glimmer names). Frames tagged "intro".
-- Thin wrapper over recordCutscene (dogfoods the generic recorder).
scenarios.recordch02intro = function()
    return recordCutscene({ state = "ch02intro", tag = "intro", until_ = "prep" })
end

-- recordch03open: the ch03 OPENING in motion (#23 Cutscenes) -- the Termalaine street over the
-- reused Targos-winter BG: the boy crier + RBG's bounty, Wolfram's ore + the KOBOLDS ONLY sign
-- (#58 narration box), Pinky's flyover recon revealing the grell. Records from the fresh CH03BOOT
-- New Game (no checkpoint) up to the Preparations screen. Frames tagged "ch03open" -> make_gif.
scenarios.recordch03open = function()
    return recordCutscene({ tag = "ch03open", until_ = "prep", pressEvery = 90 })
end

-- marchPartyToward: walk the party at (cx, cy) over up to `turns` player phases, stopping the
-- moment `stop()` goes true. Shared by ch04moose (the GATE: does the AREA fire) and
-- recordch04moose (the FILM: what the beat looks like), so the two can never disagree about how
-- the clearing is reached. The move is a REAL move (marchToward drives the game's own movement
-- map and finishes on Wait): an AREA is checked when an action ENDS, so a position poke would
-- never trigger it. Returns true if `stop()` fired, false if the turn budget ran out.
local function marchPartyToward(cx, cy, turns, stop, maxx, maxy)
    for _ = 1, turns do
        waitFor(function() return faction() == 0 and not menuOpen() end, 900, true)
        for i = 0, 7 do
            if stop() then return true end
            local u = unitAt(SYM.gUnitArrayBlue, i)
            if u and not isDead(u) and (u.state & 0x2) == 0 then
                marchToward(u, cx, cy, maxx or 14, maxy or 14)
                waitFor(function() return faction() == 0 and not menuOpen() end, 300, true)
            end
        end
        if stop() then return true end
        if runEnemyPhase() ~= "player" then return false end
    end
    return stop()
end

-- recordch04moose: the white-moose sighting in motion (#24) -- the party steps into the clearing,
-- the moose loads, RBG calls it, and it bolts SOUTHEAST (away from the party, Nicolas's call) and
-- is DISA'd. The march is the grind, so it runs in `pre` (unfilmed) and the recorder picks up the
-- instant the moose exists; the terminal is the moose GONE, plus a tail so the flee isn't cut off.
-- Run: PT_HOST_CHAPTER=5 tools/playtest/run.sh recordch04moose (needs a CH04BOOT=1 ROM).
scenarios.recordch04moose = function()
    local MOOSE_PID = 0xce
    local function moose() return findUnit(SYM.gUnitArrayGreen, 12, MOOSE_PID) end
    local reachedIt, goneFor = false, 0
    return recordCutscene({
        tag = "ch04moose", maxFrames = 5400, pressEvery = 90,
        pre = function()
            pokeFastConfig()
            if not bootToMap() then return false, "never reached the ch04 map" end
            if not waitFor(function()
                return faction() == 0 and not menuOpen()
                    and not procActive(SYM.ProcScr_StdEventEngine)
            end, 900, true) then
                return false, "ch04 map never became idle"
            end
            reachedIt = marchPartyToward(11, 4, 6, function() return moose() ~= nil end)
            if not reachedIt then return false, "party never triggered the moose sighting" end
            return true
        end,
        afterPre = pokeNormalConfig,
        until_ = function()
            if not reachedIt then return false end     -- never triggered: fail loudly, don't stop early
            if moose() ~= nil then return false end
            goneFor = goneFor + 1                      -- let the flee play out past the DISA
            return goneFor > 60
        end,
    })
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
    local MOOSE_PID = 0xce
    local X1, Y1, X2, Y2 = 8, 2, 14, 7   -- CH04_MOOSE_AREA
    local function moose() return findUnit(SYM.gUnitArrayGreen, 12, MOOSE_PID) end
    if not bootToMap() then return result("FAIL", "never reached the ch04 map") end
    pokeFastConfig()
    if moose() then return result("FAIL", "the moose is on the map at chapter start") end
    waitFor(function()
        return faction() == 0 and not menuOpen() and not procActive(SYM.ProcScr_StdEventEngine)
    end, 900, true)

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
        for i = 0, 7 do
            local u = unitAt(SYM.gUnitArrayBlue, i)
            if u and not isDead(u) and u.x >= X1 and u.x <= X2 and u.y >= Y1 and u.y <= Y2 then
                return true
            end
        end
        return false
    end
    -- The march itself is marchPartyToward (shared with recordch04moose, so the gate and the
    -- film reach the clearing the same way). The check this scenario adds on top is the one
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

-- ch04sprites: WHO is actually standing in the turn-2 pack, read from the unit arrays rather
-- than judged off a 240x160 frame (a custom map sprite under a faction palette is exactly the
-- thing that gets misread from pixels). Logs every red unit's charId + tile after the reveal
-- wave lands, so "Lupin is not wearing his Lycanroc" can be separated from "Lupin is not on
-- the map at all". Run: PT_HOST_CHAPTER=5 tools/playtest/run.sh ch04sprites (CH04BOOT=1 ROM).
scenarios.ch04sprites = function()
    local LUPIN = 0x1D                  -- CHARACTER_DUESSEL (Lupin's identity slot)
    if not bootToMap() then return result("FAIL", "never reached the ch04 map") end
    waitFor(function()
        return faction() == 0 and not menuOpen() and not procActive(SYM.ProcScr_StdEventEngine)
    end, 900, true)
    if not endTurn() then return result("FAIL", "could not end turn 1") end
    if not waitFor(function() return turn() >= 2 end, 5400) then
        return result("FAIL", "turn 2 never began")
    end
    waitFor(function()
        return faction() == 0 and not menuOpen() and not procActive(SYM.ProcScr_StdEventEngine)
    end, 3600, true)
    -- Camera + a known blue unit calibrate tile -> screen, so the crop of Lupin's tile is
    -- computed rather than eyeballed.
    log(string.format("  camera px (%d,%d)", ru16(SYM.gBmSt + 0x0C), ru16(SYM.gBmSt + 0x0E)))
    local found = false
    for i = 0, 23 do
        local u = unitAt(SYM.gUnitArrayRed, i)
        if u and not isDead(u) then
            log(string.format("  red[%02d] char=0x%02X at (%d,%d)%s",
                i, u.charId, u.x, u.y, u.charId == LUPIN and "   <- LUPIN" or ""))
            if u.charId == LUPIN then found = true end
        end
    end
    for i = 0, 7 do
        local u = unitAt(SYM.gUnitArrayBlue, i)
        if u and not isDead(u) then
            log(string.format("  blue[%02d] char=0x%02X at (%d,%d)", i, u.charId, u.x, u.y))
        end
    end
    -- The map-sprite VRAM cache. gUnitSpriteSlots[id] == 0xFF means that sprite was never
    -- allocated on this map; a real slot means it was, and any invisibility is downstream.
    -- 32x32 sprites cost 4 slots each out of a 0x40 space shared with the 16x16 sprites
    -- growing down from the other end, so a monster-heavy map can simply run out.
    log(string.format("  sms cursors: 32x=%d  16x=%d",
        ru8(SYM.gSMS32xGfxIndexCounter), ru8(SYM.gSMS16xGfxIndexCounter)))
    -- Fog: a unit the player cannot SEE is not drawn, which is indistinguishable from a
    -- broken map sprite. Print the fog state of every pack tile.
    local fogRow = function(y) return ru32(ru32(SYM.gBmMapFog) + y * 4) end
    local lup = findUnit(SYM.gUnitArrayRed, 24, LUPIN)
    for _, t in ipairs({ {0,0}, {1,0}, {2,0}, {0,1}, {2,1}, {0,2} }) do
        log(string.format("  fog(%d,%d) = %d%s", t[1], t[2], ru8(fogRow(t[2]) + t[1]),
            (lup and lup.x == t[1] and lup.y == t[2]) and "   <- Lupin's tile" or ""))
    end
    for _, id in ipairs({ 107, 109, 110, 115, 117, 119, 124 }) do
        local slot = ru8(SYM.gUnitSpriteSlots + id)
        log(string.format("  gUnitSpriteSlots[%d] = %s", id,
            slot == 0xFF and "0xFF (NEVER ALLOCATED)" or tostring(slot)))
    end
    shot("ch04sprites-pack")
    if not found then
        return result("FAIL", "no unit with Lupin's charId (0x1D) in the red array on turn 2")
    end
    return result("PASS", "Lupin is on the map as a red unit -- see the log for the roster")
end

-- ch04Parley(opts) -- drive Marty's Talk on the wolf pack: the chapter's mercy/recruit hook and
-- the switch that picks which ENDING plays. Shared by recordch04parley (which films it) and
-- clear_ch04_parley (which needs the flag set before routing), so semantic Talk selection, re-parking,
-- and the outcome check exist once (#204). Assumes the map is already booted and turn 1 is live.
--   opts.shots  -- frame-tag to screenshot into while the exchange plays; nil films nothing
-- Returns false plus a reason string, or true plus (nil, pack) once Lupin is blue -- where
-- `pack` is { before, after }: the wolves' tiles going into the Talk and coming out of it.
local CH04_LUPIN_PID, CH04_MARTY_PID = 0x1D, 0x02   -- CHARACTER_DUESSEL / CHARACTER_SETH
-- The five generic wolves, one pid each (build_campaign.CH04_PACK_PIDS -- #203). They used to
-- share 0xb3, which is exactly why the parley could not convert them one at a time.
local CH04_PACK_PIDS = { [0xb0] = true, [0xb1] = true, [0xb2] = true, [0xb4] = true, [0xb5] = true }

-- Where the pack is standing, keyed by pid: { [pid] = {x, y} } over one faction array. One pid
-- per wolf is what makes this readable at all, and it is how the parley's two claims are checked
-- from DATA -- how many came over (count) and that each converted where it stood (tiles).
local function ch04PackTiles(array, slots)
    local at = {}
    for i = 0, slots - 1 do
        local u = unitAt(array, i)
        if u and not isDead(u) and CH04_PACK_PIDS[u.charId] then at[u.charId] = { u.x, u.y } end
    end
    return at
end
local function ch04Parley(opts)
    opts = opts or {}
    local LUPIN, MARTY = CH04_LUPIN_PID, CH04_MARTY_PID
    local function redLupin() return findUnit(SYM.gUnitArrayRed, 24, LUPIN) end
    local function blueLupin() return findUnit(SYM.gUnitArrayBlue, 20, LUPIN) end
    local function snap() if opts.shots then shot(opts.shots) end end
    waitFor(function()
        return faction() == 0 and not menuOpen() and not procActive(SYM.ProcScr_StdEventEngine)
    end, 900, true)
    -- The pack (and Lupin) only exist from turn 2.
    if turn() < 2 then
        if not endTurn() then return false, "could not end turn 1" end
    end
    if not waitFor(function() return turn() >= 2 and redLupin() ~= nil end, 5400) then
        snap()
        return false, "the wolf pack never arrived on turn 2"
    end
    waitFor(function()
        return faction() == 0 and not menuOpen() and not procActive(SYM.ProcScr_StdEventEngine)
    end, 3600, true)
    local marty = blue(MARTY)
    if not marty then return false, "Marty (0x02) is not deployed -- he owns the Talk" end
    -- Park Marty orthogonally adjacent to Lupin. setMapUnit keeps the engine's tile->unit grid
    -- in sync, so Talk-adjacency reads immediately with no phase cycle (the ch03talk trick) --
    -- the point here is filming the SCENE, not pathing a cavalier across a fog map.
    local lup = redLupin()
    local grid, parked = mapUnitAt(marty.x, marty.y), false
    for _, d in ipairs({ { 1, 0 }, { -1, 0 }, { 0, 1 }, { 0, -1 } }) do
        local tx, ty = lup.x + d[1], lup.y + d[2]
        if tx >= 0 and ty >= 0 and mapUnitAt(tx, ty) == 0 then
            setMapUnit(marty.x, marty.y, 0)
            emu:write8(marty.addr + 0x10, tx); emu:write8(marty.addr + 0x11, ty)
            setMapUnit(tx, ty, grid)
            parked = true
            break
        end
    end
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
    for i = 1, 3600 do
        if i % 3 == 0 then snap() end
        if blueLupin() then break end
        if controllerState() == "dialogue_wait" then
            if not guardedInput("advance_dialogue", "A", "dialogue input wait clears", function(after)
                return controllerState(after) ~= "dialogue_wait"
            end, 120) then return false, "parley dialogue input did not advance" end
        else
            yield()
        end
    end
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
    waitFor(function() return faction() == 0 and not menuOpen()
        and not procActive(SYM.ProcScr_StdEventEngine) end, 6000, true)
    if liftFogOntoTheGrid() == 0 then
        return result("FAIL", "fog lifted but no enemy reached gBmMapUnit")
    end
    -- The pack only exists from turn 2. Wait for LUPIN, not merely for the turn counter: it ticks
    -- the moment the player phase ends, well before the reveal event LOAD1s the wave (waiting on
    -- the counter alone found an empty field).
    if not endTurn() then return result("FAIL", "could not end turn 1") end
    if not waitFor(function()
        return turn() >= 2 and findUnit(SYM.gUnitArrayRed, 24, CH04_LUPIN_PID) ~= nil
    end, 5400) then
        return result("FAIL", "the wolf pack never arrived on turn 2")
    end
    waitFor(function() return faction() == 0 and not menuOpen()
        and not procActive(SYM.ProcScr_StdEventEngine) end, 3600, true)
    for i = 0, 23 do
        local r = unitAt(SYM.gUnitArrayRed, i)
        if r and not isDead(r) then
            log(string.format("  red[%02d] char=0x%02X at (%d,%d)%s", i, r.charId, r.x, r.y,
                r.charId == CH04_LUPIN_PID and "   <- LUPIN" or ""))
        end
    end
    local function packAlive()
        local n = 0
        for i = 0, 23 do
            local r = unitAt(SYM.gUnitArrayRed, i)
            if r and not isDead(r) and CH04_PACK_PIDS[r.charId] then n = n + 1 end
        end
        return n
    end
    local function firstWolf()
        for i = 0, 23 do
            local r = unitAt(SYM.gUnitArrayRed, i)
            if r and not isDead(r) and CH04_PACK_PIDS[r.charId] then return r end
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
        for i = 0, 23 do
            local r = unitAt(SYM.gUnitArrayRed, i)
            if r and not isDead(r) then pokeFrail(r); pokeHarmless(r) end
        end
        wolf = firstWolf()
        for i = 0, 19 do
            local u = unitAt(SYM.gUnitArrayBlue, i)
            if u and not isDead(u) and (u.state & 0x2) == 0 and u.charId ~= CH04_MARTY_PID then
                local mn, mx = unitAttackRange(u)
                if mn and mn <= 1 and teleportAdjacentTo(u, { wolf }) then
                    u = unitAt(SYM.gUnitArrayBlue, i)
                    if u and canAttackFromHere(u, mn, mx) and moveUnit(u.x, u.y, u.x, u.y) then
                        local was = packAlive()
                        chooseAttack(u.addr)
                        waitFor(function() return faction() == 0 and not menuOpen()
                            and not procActive(SYM.gProc_ekrBattle) end, 600)
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
    local BASIL, SAHNAR = 0x13, 0x16        -- CHARACTER_ARTUR / CHARACTER_MARISA
    local LUPIN = 0x1D                      -- CHARACTER_DUESSEL, the slot ch05 gives the wolf
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
    local ARM = opts.arm or 0x9D1
    local RECRUIT_BOXES = (ARM == 0x9E8) and 16 or 17
    local function blueBasil() return findUnit(SYM.gUnitArrayBlue, 20, BASIL) end
    local function redSahnar() return findUnit(SYM.gUnitArrayRed, 24, SAHNAR) end
    local function blueSahnar() return findUnit(SYM.gUnitArrayBlue, 20, SAHNAR) end
    if not bootToMap() then return result("FAIL", "never reached the ch05 map") end
    pokeFastConfig()
    waitFor(function()
        return faction() == 0 and not menuOpen() and not procActive(SYM.ProcScr_StdEventEngine)
    end, 6000, true)

    -- 0. The wolf, in whatever roster state this run is about. CHECK_ALIVE reads the ROSTER and
    --    not the field (eventscr.c:3212 -- missing OR US_DEAD gives slot C = 0, while
    --    US_NOT_DEPLOYED is CHECK_DEPLOYED's business alone), so these two pokes are the whole
    --    experiment: a benched Lupin must still take the wolf's arm, a dead one must not.
    if opts.lupin then
        local wolf = findUnit(SYM.gUnitArrayBlue, 62, LUPIN)
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
            emu:write32(wolf.addr + 0x0C, wolf.state | US_DEAD | 1)  -- ... | US_HIDDEN
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
        local green = findUnit(SYM.gUnitArrayGreen, 20, BASIL)
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
    for _ = 1, 7200 do
        if turn() >= 2 and eruptionBoxes >= 4 then break end
        if controllerState() == "dialogue_wait" then
            eruptionBoxes = eruptionBoxes + 1
            if not guardedInput("advance_dialogue", "A", "eruption dialogue wait clears",
                function(after) return controllerState(after) ~= "dialogue_wait" end, 120) then
                return result("FAIL", "eruption dialogue input did not advance")
            end
        else
            yield()
        end
    end
    if eruptionBoxes ~= 4 then
        shot("ch05recruit")
        return result("FAIL", string.format(
            "eruption warning showed %d boxes, expected the four locked Ravisin boxes",
            eruptionBoxes))
    end
    waitFor(function()
        return faction() == 0 and not menuOpen() and not procActive(SYM.ProcScr_StdEventEngine)
    end, 3600, true)

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
    local grid, parked = mapUnitAt(basil.x, basil.y), false
    for _, d in ipairs({ { 1, 0 }, { -1, 0 }, { 0, 1 }, { 0, -1 } }) do
        local tx, ty = sah.x + d[1], sah.y + d[2]
        if tx >= 0 and ty >= 0 and mapUnitAt(tx, ty) == 0 then
            setMapUnit(basil.x, basil.y, 0)
            emu:write8(basil.addr + 0x10, tx); emu:write8(basil.addr + 0x11, ty)
            setMapUnit(tx, ty, grid)
            parked = true
            break
        end
    end
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
    for _ = 1, BUDGET do
        if blueSahnar() then break end
        if controllerState() == "dialogue_wait" then
            boxes = boxes + 1
            -- WHICH message is on screen, sampled while the FIRST box of the scene is up.
            -- After the scene ends every menu and unit name decodes through the same buffer
            -- and overwrites it, so this cannot be read from the verdict at the bottom.
            playedMsg = playedMsg or INSPECT.activeMsg()
            if not guardedInput("advance_dialogue", "A", "dialogue input wait clears", function(after)
                return controllerState(after) ~= "dialogue_wait"
            end, 120) then return result("FAIL", "recruit dialogue input did not advance") end
        else
            yield()
        end
    end
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

-- recordch05eruption: the smallest visual proof for #260. Boot the real ch05 map, idle turn 1,
-- then record only Ravisin's four-box turn-2 warning through Sahnar's rise and the return of
-- player control. The recorder advances dialogue while filming; the terminal requires that a
-- real dialogue wait was observed, so reaching turn 2 without the warning cannot pass.
-- Run: PT_HOST_CHAPTER=6 tools/playtest/run.sh recordch05eruption (needs a CH05BOOT=1 ROM).
scenarios.recordch05eruption = function()
    -- FAST BEFORE the boot: ch05's opening is 48 A-presses of dialogue ahead of the map, and
    -- bootToMap drives all of it unfilmed. At readable speed that alone is ~10000 frames.
    pokeFastConfig()
    if not bootToMap() then return result("FAIL", "never reached the ch05 map") end
    waitFor(function()
        return faction() == 0 and not menuOpen() and not procActive(SYM.ProcScr_StdEventEngine)
    end, 6000, true)
    if not endTurn() then return result("FAIL", "could not end turn 1") end
    local sawWarning = false
    return recordCutscene({
        tag = "ch05eruption", maxFrames = 5400, pressEvery = 90,
        until_ = function()
            if turn() >= 2 and controllerState() == "dialogue_wait" then sawWarning = true end
            return sawWarning and turn() >= 2 and faction() == 0 and not menuOpen()
                and not procActive(SYM.ProcScr_StdEventEngine)
        end,
    })
end

-- Park an unexhausted blue unit on a village door and take the Visit command, stopping the
-- moment the location event starts. Split from the dialogue-advancing half so the RECORDER can
-- own the filmed part: `openVillageVisit` is the unfilmed walk-in (a `pre`), the line itself is
-- what the camera wants. Returns ok, reason.
local function openVillageVisit(x, y)
    local u
    for i = 0, 19 do
        local c = unitAt(SYM.gUnitArrayBlue, i)
        if c and not isDead(c) and (c.state & 0x2) == 0 then u = c break end
    end
    if not u then return false, "no unexhausted blue unit to visit with" end
    -- setMapUnit keeps the engine's tile->unit grid in sync, so the Visit check reads the new
    -- position immediately (the ch03talk/parley trick).
    local grid = mapUnitAt(u.x, u.y)
    setMapUnit(u.x, u.y, 0)
    emu:write8(u.addr + 0x10, x); emu:write8(u.addr + 0x11, y)
    setMapUnit(x, y, grid)
    if not cursorTo(x, y) then return false, "cursor could not reach the village" end
    if not moveUnit(x, y, x, y) then
        return false, "could not select the unit standing on the village"
    end
    if not selectSemantic("visit", "Visit starts the live location event", function(after)
        return after.menu == nil
    end, 600) then return false, "live command menu did not expose Visit" end
    return true
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
local function visitVillage(x, y, done, onBox)
    local ok, why = openVillageVisit(x, y)
    if not ok then return false, why end
    local spoke = false
    for _ = 1, 3600 do
        if done() then break end
        if controllerState() == "dialogue_wait" then
            spoke = true
            if onBox then onBox() end
            if not guardedInput("advance_dialogue", "A", "dialogue input wait clears", function(after)
                return controllerState(after) ~= "dialogue_wait"
            end, 120) then return false, "village dialogue input did not advance" end
        else
            yield()
        end
    end
    return true, nil, spoke
end

-- ch04village (#205): does the Lonelywood village actually hand over its Iron Axe?
-- It did not, for the whole slice, and NOTHING looked wrong: the map drew a cottage, the chapter
-- compiled and played. FE8 gates the Visit menu item on the TERRAIN under the unit (bmmenu.c:735)
-- before it ever consults the location event, and the snowy reskin had mapped vanilla's village
-- metatile onto ruins. So this checks the two halves that must BOTH hold -- a visitable tile and a
-- wired Village() entry -- by the only evidence that settles it: the axe is in the party's hands
-- afterwards and was not before.
-- Run: PT_HOST_CHAPTER=5 tools/playtest/run.sh ch04village (needs a CH04BOOT=1 ROM).
scenarios.ch04village = function()
    local VILLAGE_X, VILLAGE_Y, IRON_AXE = 8, 2, 0x1F
    if not bootToMap() then return result("FAIL", "never reached the ch04 map") end
    pokeFastConfig()
    waitFor(function() return faction() == 0 and not menuOpen()
        and not procActive(SYM.ProcScr_StdEventEngine) end, 6000, true)
    local function axes()
        local n = 0
        for _, id in ipairs(collectedItems()) do if id == IRON_AXE then n = n + 1 end end
        return n
    end
    local before = axes()
    log(string.format("ch04village: %d Iron Axe(s) in the party before visiting", before))
    local ok, why = visitVillage(VILLAGE_X, VILLAGE_Y, function() return axes() > before end)
    if not ok then return result("FAIL", why) end
    shot("ch04village")
    local after = axes()
    if after <= before then
        return result("FAIL", string.format(
            "visited (%d,%d) but the party still holds %d Iron Axe(s) -- the village handed over "
            .. "nothing (check the tile's terrain AND the Village() entry)",
            VILLAGE_X, VILLAGE_Y, after))
    end
    return result("PASS", string.format(
        "the Lonelywood village handed over its Iron Axe: %d -> %d in the party", before, after))
end

-- ch05reliquaries (#25): all FOUR reliquary doors -- each one speaks, and each hands over ITS
-- OWN gift. ch05village covers the south door alone, and a scenario's verdict only covers what
-- it actually reads: three doors, three faces and three of the four authored lines had no
-- witness at all, which is the same blind spot that let ch05village pass for months while
-- proving nothing about the recruit. The gifts are per-tile on purpose (vanilla's placement,
-- richest where the eruption races), so "some item arrived" is not the assertion -- the RIGHT
-- item is. `spoke` is checked too: a wired-but-empty message would hand the gift over in
-- silence and every item check would still pass.
-- Run: PT_HOST_CHAPTER=6 tools/playtest/run.sh ch05reliquaries (needs a CH05BOOT=1 ROM).
scenarios.ch05reliquaries = function()
    local SITES = {
        {name = "north  Torch",       x = 5,  y = 1,  item = 0x70},
        {name = "west   Secret Book", x = 5,  y = 6,  item = 0x5D},
        {name = "east   Armorslayer", x = 12, y = 10, item = 0x0E},
        {name = "south  Dracoshield", x = 12, y = 19, item = 0x60},
    }
    if not bootToMap() then return result("FAIL", "never reached the ch05 map") end
    pokeFastConfig()
    waitFor(function() return faction() == 0 and not menuOpen()
        and not procActive(SYM.ProcScr_StdEventEngine) end, 6000, true)
    local function held(id)
        local n = 0
        for _, got in ipairs(collectedItems()) do if got == id then n = n + 1 end end
        return n
    end
    -- The visit's `done` fires the moment the ITEM lands, but the location event is still
    -- running behind it (give-item tail, the door's MapChange, EVBIT_T, ENDA). Walking to the
    -- next door while std_event holds the controller is an illegal input, and the run dies on
    -- "cursor could not reach" -- which reads like a map problem and is really an impatience
    -- problem. Settle back to player-idle between doors.
    local function settle()
        return waitFor(function()
            return faction() == 0 and not menuOpen()
                and not procActive(SYM.ProcScr_StdEventEngine)
                and controllerState() == "player_map_idle"
        end, 3000, true)
    end
    local silent = {}
    for _, site in ipairs(SITES) do
        if not settle() then
            return result("FAIL", string.format(
                "the map never returned to player control before %s (%d,%d)",
                site.name, site.x, site.y))
        end
        local before = held(site.item)
        -- One shot per door by default (enough to prove the face and the first line). Set
        -- PT_RECORD_BOXES=1 for a full review capture: every box of every door, which is what
        -- you want when the question is "read the whole scene", not "did it fire".
        local shown = false
        local ok, why, spoke = visitVillage(site.x, site.y, function()
            return held(site.item) > before
        end, function()
            if os.getenv("PT_RECORD_BOXES") then
                shot("box")
            elseif not shown then
                shot("reliquary"); shown = true
            end
        end)
        if not ok then
            return result("FAIL", string.format("%s (%d,%d): %s", site.name, site.x, site.y, why))
        end
        if held(site.item) <= before then
            return result("FAIL", string.format(
                "%s (%d,%d) was visited but its gift never arrived -- the door ran, the "
                .. "give-item tail did not", site.name, site.x, site.y))
        end
        if not spoke then silent[#silent + 1] = site.name end
        log(string.format("ch05reliquaries: %s handed over its gift", site.name))
    end
    if #silent > 0 then
        return result("FAIL", "these doors paid out in SILENCE (no text box): "
            .. table.concat(silent, ", "))
    end
    return result("PASS", "all four reliquaries spoke and handed over their own gift")
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
    if not waitFor(function()
        return faction() == 0 and not menuOpen() and not procActive(SYM.ProcScr_StdEventEngine)
            and controllerState() == "player_map_idle"
    end, 6000, true) then
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
    local grid = mapUnitAt(hero.x, hero.y)
    setMapUnit(hero.x, hero.y, 0)
    emu:write8(hero.addr + 0x10, ARENA_X); emu:write8(hero.addr + 0x11, ARENA_Y)
    setMapUnit(ARENA_X, ARENA_Y, grid)
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
    setMapUnit(ARENA_X, ARENA_Y, 0)
    emu:write8(hero.addr + 0x10, fromX); emu:write8(hero.addr + 0x11, fromY)
    setMapUnit(fromX, fromY, grid)
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
            if not guardedInput("advance_dialogue", "A", "arena tutorial page advances",
                function(after) return controllerState(after) ~= "dialogue_wait" end, 120) then
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
    if not guardedInput("advance_dialogue", "A", "welcome advances to the live wager choice",
        function(after) return controllerState(after) == "yes_no_choice" end, 300) then
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
            if not guardedInput("advance_dialogue", "A", string.format(
                "Arena dialogue page %d advances toward combat", arenaPages),
                function(after) return controllerState(after) ~= "dialogue_wait" end, 300) then
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

-- ch05village (#25): does the SOUTH reliquary at (12,19) actually hand over its Dracoshield?
-- Two things this pins, both of which shipped wrong once. First the same failure ch04village
-- exists for: ch05's Location list was EMPTY, so four villages plus an armory and a vendor sat on
-- intact tiles that nothing pointed at -- a finished-looking map with unreachable rewards.
-- Second, WHICH gift: (12,19) is the south-east site and the turn-2 eruption pair spawns beside
-- it, so vanilla puts its richest gift here and its cheapest at (5,1); ours had them swapped,
-- which no other gate can see (same item set, same total, parity still reads PARITY). Checking
-- the Dracoshield specifically -- not "some item" -- is what makes that visible here too.
-- Run: PT_HOST_CHAPTER=6 tools/playtest/run.sh ch05village (needs a CH05BOOT=1 ROM).
scenarios.ch05village = function()
    local VILLAGE_X, VILLAGE_Y, DRACOSHIELD = 12, 19, 0x60
    if not bootToMap() then return result("FAIL", "never reached the ch05 map") end
    pokeFastConfig()
    waitFor(function() return faction() == 0 and not menuOpen()
        and not procActive(SYM.ProcScr_StdEventEngine) end, 6000, true)
    local function shields()
        local n = 0
        for _, id in ipairs(collectedItems()) do if id == DRACOSHIELD then n = n + 1 end end
        return n
    end
    local before = shields()
    log(string.format("ch05village: %d Dracoshield(s) in the party before visiting", before))
    local ok, why = visitVillage(VILLAGE_X, VILLAGE_Y, function() return shields() > before end)
    if not ok then return result("FAIL", why) end
    shot("ch05village")
    local after = shields()
    if after <= before then
        return result("FAIL", string.format(
            "visited (%d,%d) but the party still holds %d Dracoshield(s) -- the reliquary handed "
            .. "over nothing (check the tile's terrain AND the Village() entry)",
            VILLAGE_X, VILLAGE_Y, after))
    end
    return result("PASS", string.format(
        "the south reliquary handed over its Dracoshield: %d -> %d in the party", before, after))
end

-- ch05raid (#25): can the party LOSE a reliquary? The chapter has declared a village-raid race
-- since #196 -- "the eruption's dead race the party for the spread reward-sites" -- and for that
-- whole time nothing on the map could reach one: every wave was `aggressive`, no site carried an
-- event id, and ch05 registered no MapChange at all, so all four were safe for the whole chapter
-- and ch05village/ch05reliquaries passed anyway. They only ever walk a unit to a door.
--
-- The verdict here is the TERRAIN, because terrain is what FE8 itself reads: CanUnitVisit
-- (bmmenu.c) and gTerrainList_LootableVillages (cp_utility.c) both decide from it, so a site that
-- has become RUINS_REGULAR is one the player cannot enter and a second raider will not revisit.
-- Its event id staying UNSET is the other half -- TILE_COMMAND_20 changes the tile and sets
-- nothing (eventinfo.c), which is exactly why a sacked site cannot count toward the save-all.
-- Run: PT_HOST_CHAPTER=6 tools/playtest/run.sh ch05raid (needs a CH05BOOT=1 ROM).
scenarios.ch05raid = function()
    local SITE_X, SITE_Y = 12, 19          -- reliquary-south: vanilla's turn-2 pair spawns beside it
    local VILLAGE_REGULAR, RUINS, DRACOSHIELD = 0x03, 0x25, 0x60
    local SITE_FLAG = 10                   -- CH05_VILLAGE_FLAGS['reliquary-south']
    if not bootToMap() then return result("FAIL", "never reached the ch05 map") end
    pokeFastConfig()
    waitFor(function() return faction() == 0 and not menuOpen()
        and not procActive(SYM.ProcScr_StdEventEngine) end, 6000, true)
    if terrainAt(SITE_X, SITE_Y) ~= VILLAGE_REGULAR then
        return result("FAIL", string.format(
            "reliquary-south (%d,%d) is terrain 0x%02X at turn 1, not a village -- nothing can "
            .. "raid it and nothing can visit it", SITE_X, SITE_Y, terrainAt(SITE_X, SITE_Y)))
    end
    -- Count the gift BEFORE, like ch04village/ch05village do. An absolute "the party holds no
    -- Dracoshield" would fail the moment the chapter ships one anywhere else on the map.
    local function shields()
        local n = 0
        for _, got in ipairs(collectedItems()) do if got == DRACOSHIELD then n = n + 1 end end
        return n
    end
    local before = shields()
    -- Hand the site to the raiders: never visit it, just give the turns back. The party sits at
    -- the WEST spawn and the site is south-EAST, so idling does not contest the race.
    for t = 1, 8 do
        local phase = runEnemyPhase()
        if phase == nil then
            return result("FAIL", string.format("the enemy phase never returned on turn %d", t))
        end
        if phase == "gameover" then
            shot("ch05raid-gameover")
            return result("FAIL", string.format(
                "the party died on turn %d before any raider reached a reliquary", t))
        end
        if terrainAt(SITE_X, SITE_Y) == RUINS then
            -- Put the CAMERA on the site before the shot. The verdict below is a terrain byte,
            -- and a terrain byte has been right while the tiles it names drew wrong; the frame
            -- is the only thing that shows the ruin actually replaced the building.
            cursorTo(SITE_X, SITE_Y)
            wait(90)                -- the map scrolls to the cursor; capturing before it
                                    -- arrives photographs wherever the fight happened to be
            shot("ch05raid")
            log(string.format("ch05raid: reliquary-south fell on turn %d", turn()))
            if shields() > before then
                return result("FAIL", string.format(
                    "the site was sacked but its Dracoshield reached the party anyway "
                    .. "(%d -> %d) -- a lost site must cost the player its gift",
                    before, shields()))
            end
            if eventFlag(SITE_FLAG) then
                return result("FAIL", string.format(
                    "reliquary-south was RAIDED but its event id %d is set -- a sacked site "
                    .. "would count toward the save-all payout", SITE_FLAG))
            end
            return result("PASS", string.format(
                "reliquary-south was desecrated on turn %d: terrain 0x%02X -> 0x%02X, no gift, "
                .. "flag %d unset", turn(), VILLAGE_REGULAR, RUINS, SITE_FLAG))
        end
    end
    shot("ch05raid-unraided")
    return result("FAIL", string.format(
        "eight turns and reliquary-south still stands (terrain 0x%02X) -- no raider reached it, "
        .. "so the race the chapter declares does not exist", terrainAt(SITE_X, SITE_Y)))
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
    local SITES = {
        { name = "north", x = 5,  y = 1,  item = 0x70, flag = 12 },
        { name = "west",  x = 5,  y = 6,  item = 0x5D, flag = 11 },
        { name = "east",  x = 12, y = 10, item = 0x0E, flag = 9  },
        { name = "south", x = 12, y = 19, item = 0x60, flag = 10 },
    }
    local RAVISIN, GUIDING_RING = 0xb8, 0x68
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
        return waitFor(function()
            return faction() == 0 and not menuOpen()
                and not procActive(SYM.ProcScr_StdEventEngine)
                and controllerState() == "player_map_idle"
        end, 3000, true)
    end
    waitFor(function() return faction() == 0 and not menuOpen()
        and not procActive(SYM.ProcScr_StdEventEngine) end, 6000, true)
    -- Save all four. Raiders are on the board now, so this is a race the scenario has to WIN;
    -- if a site falls first its flag never sets and the payout is correctly withheld, which
    -- would read here as a failure to visit rather than as a payout bug.
    for _, site in ipairs(SITES) do
        if not settle() then
            return result("FAIL", "the map never returned to player control before " .. site.name)
        end
        disarmTheTomb()
        local ok, why = visitVillage(site.x, site.y, function()
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
        -- ...and they need a MELEE WEAPON in slot 0, or parking the boss next to them proves
        -- nothing: unitAttackRange returns nil for a staff, and ch05 deploys two healers.
        local hero, hmin, hmax = nil, nil, nil
        for i = 0, 23 do
            local u = unitAt(SYM.gUnitArrayBlue, i)
            if u and not isDead(u) and (u.state & 0x3) == 0 and mapUnitAt(u.x, u.y) ~= 0 then
                local mn, mx = unitAttackRange(u)
                if mn and mn <= 1 and mx >= 1 then hero, hmin, hmax = u, mn, mx; break end
            end
        end
        if hero == nil then
            return result("FAIL", "no selectable blue unit with a melee weapon left to strike the boss")
        end
        pokeFrail(boss)
        boss = red(RAVISIN)
        local bossGrid = mapUnitAt(boss.x, boss.y)
        local parked = false
        for _, d in ipairs({ { 1, 0 }, { -1, 0 }, { 0, 1 }, { 0, -1 } }) do
            local tx, ty = hero.x + d[1], hero.y + d[2]
            if tx >= 0 and ty >= 0 and mapUnitAt(tx, ty) == 0 then
                setMapUnit(boss.x, boss.y, 0)
                emu:write8(boss.addr + 0x10, tx); emu:write8(boss.addr + 0x11, ty)
                setMapUnit(tx, ty, bossGrid)
                parked = true
                break
            end
        end
        if not parked then return result("FAIL", "no free tile beside a blue unit to park Ravisin") end
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

-- recordch05ravisindeath (#262): the smallest real-map proof for Ravisin's locked death quote.
-- Setup is unfilmed: boot ch05, park a one-hit Ravisin beside one live melee attacker, and drive
-- the game's own Attack path. chooseAttack hands control back at the FIRST dialogue wait after
-- Ravisin is dead, so the recorder starts on her death box; the expected unwired-ending placeholder
-- may follow after EVFLAG_DEFEAT_BOSS is set.
-- Run: PT_HOST_CHAPTER=6 tools/playtest/run.sh recordch05ravisindeath (CH05BOOT=1 ROM).
scenarios.recordch05ravisindeath = function()
    local RAVISIN, boxes = 0xb8, 0
    return recordCutscene({
        tag = "ch05ravisindeath", speed = "normal", maxFrames = 1800, shotEvery = 1,
        pressEvery = 90,
        pre = function()
            pokeFastConfig()
            if not bootToMap() then return false, "never reached the ch05 map" end
            if not waitFor(function()
                return faction() == 0 and not menuOpen()
                    and not procActive(SYM.ProcScr_StdEventEngine)
            end, 6000, true) then
                return false, "ch05 map never became idle"
            end
            local boss = red(RAVISIN)
            if not boss then return false, "Ravisin (pid 0xb8) is not in the red array" end
            local hero, hmin, hmax
            for i = 0, 23 do
                local u = unitAt(SYM.gUnitArrayBlue, i)
                if u and not isDead(u) and (u.state & 0x3) == 0
                    and mapUnitAt(u.x, u.y) ~= 0 then
                    local mn, mx = unitAttackRange(u)
                    if mn and mn <= 1 and mx >= 1 then
                        hero, hmin, hmax = u, mn, mx
                        break
                    end
                end
            end
            if not hero then return false, "no selectable blue melee attacker" end

            pokeFrail(boss)
            pokeHarmless(boss)
            emu:write8(hero.addr + 0x14, 30) -- deterministic might for the proof strike
            emu:write8(hero.addr + 0x15, 30) -- deterministic hit for the proof strike
            boss = red(RAVISIN)
            local bossGrid = mapUnitAt(boss.x, boss.y)
            local mapw, maph = mapSize()
            local parked = false
            for _, d in ipairs({ { 1, 0 }, { -1, 0 }, { 0, 1 }, { 0, -1 } }) do
                local tx, ty = hero.x + d[1], hero.y + d[2]
                if tx >= 0 and tx < mapw and ty >= 0 and ty < maph
                    and mapUnitAt(tx, ty) == 0 then
                    setMapUnit(boss.x, boss.y, 0)
                    emu:write8(boss.addr + 0x10, tx); emu:write8(boss.addr + 0x11, ty)
                    setMapUnit(tx, ty, bossGrid)
                    parked = true
                    break
                end
            end
            if not parked then return false, "no free tile beside the melee attacker" end
            hero = blue(hero.charId) or hero
            if not canAttackFromHere(hero, hmin, hmax) then
                return false, "parked Ravisin is not in the attacker's live range"
            end
            if not moveUnit(hero.x, hero.y, hero.x, hero.y) then
                return false, "could not open the attacker's command menu"
            end
            if not chooseAttack(hero.addr, function()
                return isDead(red(RAVISIN)) and controllerState() == "dialogue_wait"
            end) then
                return false, "the proof strike did not resolve"
            end
            if not (isDead(red(RAVISIN)) and controllerState() == "dialogue_wait") then
                return false, "Ravisin died without opening her death quote"
            end
            return true
        end,
        afterPre = pokeNormalConfig,
        until_ = function()
            if controllerState() == "dialogue_wait" then boxes = boxes + 1 end
            return boxes == 1 and eventFlag(2) and controllerState() ~= "dialogue_wait"
        end,
    })
end

-- recordch05platform (#65 / #25): what the fighters are STANDING ON in ch05.
-- ch05 hosts on slot 6, and slot 6 ships vanilla Ch6's `battleTileSet = 6`, whose table sends
-- TERRAIN_ROAD to `michi1` and TERRAIN_PLAINS to `heichi1`. ch05's map is 53% road, so every
-- fight in a snowbound elven tomb was staged on a dirt track and a green verge -- reported by
-- eye, because nothing in the build, the tests or any scenario looks at the ground.
-- So this films it, and films it ON ROAD specifically: both combatants are parked on
-- TERRAIN_ROAD and the scenario FAILS if they are not, because road is the tile class that was
-- wrong and a fight staged on a fence would prove nothing about it.
-- AND IT READS THE PLATFORM, not just the tile. The first cut asserted terrain, filmed, and
-- PASSED while the fighters stood on the wrong ground -- the terrain was right and the lookup
-- off it was not (a raw table index where the engine wants index+1, so every snow chapter drew
-- the row below the one it named). gBanimFloorfx is the engine's own answer to "which platform",
-- so the terminal below demands it be one of OUR rows and names which.
-- Battle animations are forced ON (the whole subject is the animation's backdrop) -- note
-- pokeNormalConfig only clears gameSpeed and would leave a prior pokeFastConfig's map combat
-- in place, which draws no platform at all.
-- Run: PT_HOST_CHAPTER=6 tools/playtest/run.sh recordch05platform (needs a CH05BOOT=1 ROM).
scenarios.recordch05platform = function()
    -- battle_terrain_table indices our vendored grounds occupy (PLATFORM_BASE_INDEX..+3:
    -- ms_snowdrift / ms_snowrough / ms_snowice / ms_snowpath). TERRAIN_ROAD has its own slot in
    -- the engine's 66-entry array -- it is where vanilla's slot-6 table puts `michi1`, the dirt
    -- road ch05 was inheriting -- so road must resolve to ms_snowpath. Anything else (vanilla
    -- ground, or one of ours a row off) is the failure this scenario exists to name.
    local TERRAIN_ROAD = 0x02
    local PLAT_DRIFT, PLAT_ROUGH, PLAT_ICE, PLAT_PATH = 115, 116, 117, 118
    local PLAT_NAME = { [PLAT_DRIFT] = "ms_snowdrift", [PLAT_ROUGH] = "ms_snowrough",
                        [PLAT_ICE] = "ms_snowice", [PLAT_PATH] = "ms_snowpath" }
    local ground, groundSeen = nil, false
    local function setUp()
            pokeFastConfig()
            if not bootToMap() then return false, "never reached the ch05 map" end
            if not waitFor(function()
                return faction() == 0 and not menuOpen()
                    and not procActive(SYM.ProcScr_StdEventEngine)
            end, 6000, true) then
                return false, "ch05 map never became idle"
            end
            local a = SYM.gPlaySt + 0x40
            local c = ru32(a)
            c = c & ~(3 << 17)                    -- animationType = ON (full battle anims)
            c = c & ~(1 << 7)                     -- gameSpeed = normal
            emu:write32(a, c)
            local hero, hmin, hmax
            for i = 0, 61 do
                local u = unitAt(SYM.gUnitArrayBlue, i)
                if u and not isDead(u) and (u.state & 0x3) == 0 and mapUnitAt(u.x, u.y) ~= 0 then
                    local mn, mx = unitAttackRange(u)
                    if mn and mn <= 1 and mx >= 1 then hero, hmin, hmax = u, mn, mx break end
                end
            end
            if not hero then return false, "no selectable blue melee attacker" end
            local foe
            for i = 0, 49 do
                local r = unitAt(SYM.gUnitArrayRed, i)
                if r and not isDead(r) and mapUnitAt(r.x, r.y) ~= 0 then foe = r break end
            end
            if not foe then return false, "no live red unit to stage the fight against" end
            pokeHarmless(foe)                     -- the fight must finish, not end the film early
            -- A PAIR of orthogonally adjacent free ROAD tiles, found on the engine's own terrain
            -- map rather than assumed from the layout.
            local mapw, maph = mapSize()
            local ax, ay, bx, by
            for y = 0, maph - 1 do
                for x = 0, mapw - 1 do
                    if terrainAt(x, y) == TERRAIN_ROAD then
                        for _, d in ipairs({ { 1, 0 }, { 0, 1 } }) do
                            local nx, ny = x + d[1], y + d[2]
                            if nx < mapw and ny < maph and terrainAt(nx, ny) == TERRAIN_ROAD
                                and (mapUnitAt(x, y) == 0 or (x == hero.x and y == hero.y))
                                and (mapUnitAt(nx, ny) == 0 or (nx == foe.x and ny == foe.y)) then
                                ax, ay, bx, by = x, y, nx, ny
                                break
                            end
                        end
                    end
                    if ax then break end
                end
                if ax then break end
            end
            if not ax then return false, "no adjacent pair of free ROAD tiles on the ch05 map" end
            local hgrid, fgrid = mapUnitAt(hero.x, hero.y), mapUnitAt(foe.x, foe.y)
            setMapUnit(hero.x, hero.y, 0); setMapUnit(foe.x, foe.y, 0)
            emu:write8(hero.addr + 0x10, ax); emu:write8(hero.addr + 0x11, ay)
            emu:write8(foe.addr + 0x10, bx); emu:write8(foe.addr + 0x11, by)
            setMapUnit(ax, ay, hgrid); setMapUnit(bx, by, fgrid)
            log(string.format("ch05platform: %d,%d vs %d,%d -- terrain 0x%02X / 0x%02X (ROAD)",
                ax, ay, bx, by, terrainAt(ax, ay), terrainAt(bx, by)))
            hero = blue(hero.charId) or hero
            if not canAttackFromHere(hero, hmin, hmax) then
                return false, "the parked foe is not in the attacker's live range"
            end
            if not moveUnit(hero.x, hero.y, hero.x, hero.y) then
                return false, "could not open the attacker's command menu"
            end
            -- chooseAttack's three input steps WITHOUT its combat wait: the wait is what the
            -- camera is here for, and calling it would resolve the fight before filming starts.
            if not selectSemantic("attack", "Attack opens the live weapon menu", function(after)
                return controllerState(after) == "weapon_menu"
            end, 300) then return false, "no Attack on the command menu" end
            if not selectSemantic("select_weapon", "weapon opens the attack target selector",
                function(after)
                    return controllerState(after) == "target_selection"
                        and after.target and after.target.kind == "attack"
                end, 300) then return false, "no live weapon to attack with" end
            if not guardedInput("confirm_target", "A", "target selection commits the attack",
                function(after)
                    return after.procs.battle ~= nil or controllerState(after) ~= "target_selection"
                end, 300) then return false, "the attack never committed" end
            return true
    end

    wait(30)
    local ok, why = setUp()
    if not ok then return result("FAIL", "ch05platform setup failed: " .. tostring(why)) end
    -- The loop is the scenario's own, NOT recordCutscene's, and that is the finding this
    -- scenario is named for rather than a style choice: recordCutscene calls `o.post(reached)`
    -- and DISCARDS the return, then returns its own "cutscene recorded" PASS. The first cut put
    -- the platform assertion in `post`, so the verdict was decided by whether a film was made
    -- and the assertion was dead code -- the same "a verdict only covers what it READS" defect,
    -- one level up. A scenario with something to assert owns its loop and calls result() once.
    for f = 1, 1500 do
        if f % 2 == 0 then shot("ch05platform") end
        -- gBanimFloorfx is s16[2] (POS_L/POS_R) and is -1 until the anim resolves it.
        local l = rs16(SYM.gBanimFloorfx)
        if not groundSeen and l >= 0 then
            ground, groundSeen = l, true
            log(string.format("ch05platform: standing on battle_terrain_table[%d] (%s)",
                l, PLAT_NAME[l] or "NOT one of ours -- vanilla ground"))
        end
        if controllerState() == "dialogue_wait" then
            if not guardedInput("advance_dialogue", "A", "dialogue input wait clears",
                function(after) return controllerState(after) ~= "dialogue_wait" end, 120) then
                return result("FAIL", "ch05platform dialogue postcondition failed")
            end
        end
        if groundSeen and faction() == 0 and not menuOpen()
            and not procActive(SYM.ProcScr_BattleEventEngine)
            and controllerState() == "player_map_idle" then
            break
        end
        yield()
    end
    if not groundSeen then
        return result("FAIL", "the battle animation never resolved a ground index")
    end
    if ground ~= PLAT_PATH then
        return result("FAIL", string.format(
            "road resolved to battle_terrain_table[%d] (%s), not ms_snowpath[%d] -- ch05 is "
            .. "standing on the wrong platform", ground,
            PLAT_NAME[ground] or "a vanilla ground", PLAT_PATH))
    end
    return result("PASS", "ch05's roads fight on ms_snowpath, the snowed-over track")
end

-- recordch05combatquotes (#25): scenes 12 and 13, filmed in ONE combat.
-- The two beats are separate mechanisms -- Ravisin's taunt is a gBattleTalkList pair that fires at
-- battle START, Basil's death box is a gDefeatTalkList row that fires when she falls -- but ONE
-- fight produces both, in that order, so it is one run and not two.
-- What only a run can answer: whether each box renders with the right FACE. Both draw over the
-- combat overlay rather than the map, and three data checks passing while three faces rendered
-- corrupted is a thing this chapter has already done. Basil's is her ONE death quote (#6,
-- chapter=0xFF) -- ch05 briefly gave her a second, chapter-keyed box and it was cut -- so what
-- this film shows is her universal line playing where the tomb is the chapter that killed her.
-- MAP COMBAT, normal speed, on recordfix's finding: an in-battle quote is buried and aliased under
-- full battle anims and reads as a lingering overlay in map combat.
-- Determinism instead of AI faith: every OTHER red is made harmless AND Basil is given the defence
-- to shrug a harmless weapon off, so no wandering enemy can take the kill this film exists to
-- attribute to Ravisin, who is given the power to land it through that same defence.
-- Run: PT_HOST_CHAPTER=6 tools/playtest/run.sh recordch05combatquotes (CH05BOOT=1 ROM).
scenarios.recordch05combatquotes = function()
    local BASIL, RAVISIN = 0x13, 0xb8            -- CHARACTER_ARTUR / Ravisin's raw pid
    wait(30)
    pokeFastConfig()
    if not bootToMap() then return result("FAIL", "never reached the ch05 map") end
    if not waitFor(function()
        return faction() == 0 and not menuOpen()
            and not procActive(SYM.ProcScr_StdEventEngine)
    end, 6000, true) then
        return result("FAIL", "ch05 map never became idle")
    end
    local boss = red(RAVISIN)
    if not boss then return result("FAIL", "Ravisin (pid 0xb8) is not in the red array") end
    local basil = blue(BASIL)
    if not basil then
        return result("FAIL", "Basil is not BLUE at turn 1 -- the opening join CUSA never fired")
    end
    -- Only Ravisin may land a killing blow. pow=0 alone does NOT protect a 1-HP unit (weapon
    -- might still gets through), so Basil keeps her HP and takes the DEFENCE that zeroes a
    -- harmless attacker's damage; Ravisin is given power enough to cut straight through it.
    for i = 0, 49 do
        local r = unitAt(SYM.gUnitArrayRed, i)
        if r and not isDead(r) and r.charId ~= RAVISIN then pokeHarmless(r) end
    end
    emu:write8(basil.addr + 0x17, 40)     -- def: nothing harmless can scratch her
    emu:write8(basil.addr + 0x18, 40)     -- res: Ravisin's Flux is magic, so cover both
    emu:write8(boss.addr + 0x14, 60)      -- pow: her hit goes through that, once
    emu:write8(boss.addr + 0x15, 60)      -- hit: and it does not miss
    -- Park Basil orthogonally adjacent to Ravisin's guard tile, keeping the tile->unit grid in
    -- sync (recordch05recruit's idiom) so adjacency reads with no phase cycle.
    local grid, parked = mapUnitAt(basil.x, basil.y), false
    for _, d in ipairs({ { 1, 0 }, { -1, 0 }, { 0, 1 }, { 0, -1 } }) do
        local tx, ty = boss.x + d[1], boss.y + d[2]
        if tx >= 0 and ty >= 0 and mapUnitAt(tx, ty) == 0 then
            setMapUnit(basil.x, basil.y, 0)
            emu:write8(basil.addr + 0x10, tx); emu:write8(basil.addr + 0x11, ty)
            setMapUnit(tx, ty, grid)
            parked = true
            break
        end
    end
    if not parked then return result("FAIL", "no free tile beside Ravisin to park Basil") end
    basil = blue(BASIL)
    log(string.format("ch05combatquotes: Basil (%d,%d) HP %d parked beside Ravisin (%d,%d)",
        basil.x, basil.y, ru8(basil.addr + 0x13), boss.x, boss.y))
    if not endTurn() then return result("FAIL", "could not end the player turn") end
    -- The capture loop is HAND-ROLLED, and recordCutscene is the wrong tool here for a measured
    -- reason: it films at a fixed cadence, and the first cut of this scenario shot every frame
    -- of a SIXTEEN-enemy phase, spent the whole wall clock on screenshots of units walking, and
    -- timed out having captured 1173 frames and not one dialogue box. Shoot the phase sparsely
    -- and the QUOTE densely -- recordfix's cadence, for recordfix's reason.
    local quotes, wasUp, deathFrame = 0, false, nil
    for f = 1, 12000 do
        local up = procActive(SYM.ProcScr_BattleEventEngine)
        if up then
            if not wasUp then
                quotes = quotes + 1
                log(string.format("ch05combatquotes: quote box %d up at f%d (Basil HP %d)",
                    quotes, f, blue(BASIL) and ru8(blue(BASIL).addr + 0x13) or -1))
            end
            shot("ch05combatquotes")                       -- every frame while a box is up
            if f % 36 == 0 then press(K.A, 3) end          -- page it slowly enough to read
        else
            if f % 6 == 0 then shot("ch05combatquotes") end
            if controllerState() == "dialogue_wait" and f % 45 == 0 then press(K.A, 3) end
        end
        wasUp = up
        local b = blue(BASIL)
        if isDead(b) and not deathFrame then deathFrame = f end
        -- Instrumented, so a second failure names its own cause instead of buying a third run.
        if f % 600 == 0 then
            local r = red(RAVISIN)
            log(string.format("ch05combatquotes: f%d faction=%d turn=%d quotes=%d "
                .. "basilHP=%d ravisin=(%d,%d)", f, faction(), turn(), quotes,
                b and ru8(b.addr + 0x13) or -1, r and r.x or -1, r and r.y or -1))
        end
        if gameOverActive() then break end
        if quotes >= 2 and deathFrame and not up and f > deathFrame + 120 then break end
        if faction() == 0 and turn() >= 2 and f > 600 then break end   -- the phase ran out
        yield()
    end
    if quotes < 1 then
        return result("FAIL", "the enemy phase never opened an in-battle quote box -- Ravisin "
            .. "did not engage the Basil parked beside her")
    end
    if not deathFrame then
        return result("FAIL", string.format(
            "%d quote box(es) played but Basil survived, so her chapter death box never ran",
            quotes))
    end
    if quotes < 2 then
        return result("FAIL", "Basil fell after only one quote box -- the taunt and her death "
            .. "box did not both play")
    end
    return result("PASS", "Ravisin's taunt opened the fight and Basil's death box closed it")
end

-- recordch05opening (#25): the MOTION proof for ch05's three BACKDROP scenes -- Basil and Sahnar
-- through the stone, Sephek's orders, Ravisin's appraisal -- which the chapter played SILENTLY
-- until now (CH05_BEGINNING_SCRIPT was ours already and simply had no TEXTSHOW in it).
-- What only a run can answer, and reasoning cannot: whether BG_MS_ELVEN_TOMB actually comes up
-- behind the text, and whether the FADI/FADU pair BETWEEN scenes returns to the tomb rather than
-- to black or to the host slot's map -- the BACG is never re-issued across the three, on the
-- grounds that it is still in VRAM (EventShowTextBgDirect only decompresses while activeTextType
-- is REMOVEPORTRAITS, and each Text() leaves it at TEXTSTART). That is a decomp READING, so it
-- gets filmed rather than asserted.
-- Setup is the BOOT ONLY, unfilmed, and stops the instant the chapter's event engine goes live so
-- no box is eaten before the camera rolls. The terminal is the PREP screen, which is what the
-- opening runs into (CALL EventScr_08591FD8), so the film covers the whole backdrop half and
-- stops before the map.
-- Run: PT_HOST_CHAPTER=6 tools/playtest/run.sh recordch05opening (needs a CH05BOOT=1 ROM).
scenarios.recordch05opening = function()
    return recordCutscene({
        -- shotEvery 4 and pressEvery 90 are recordch05recruit's, for the same reason: this is a
        -- 42-box run of scenes, and filming every frame makes a GIF minutes long.
        tag = "ch05opening", speed = "normal", maxFrames = 14000, shotEvery = 4,
        pressEvery = 90,
        pre = function()
            pokeFastConfig()                   -- boot fast; the scenes themselves play normal
            for _ = 1, TUNE.bootSteps do
                -- NOT inChapter(): that stays FALSE for the whole BeginningScene (the chapter
                -- is not "in" until the map is up), so waiting on it hands the opening to
                -- advanceBootState, which mashes A through all 42 boxes before the camera ever
                -- rolls -- a run that films nothing and reports a timeout. Stop on the EVENT
                -- ENGINE instead, which goes live the moment the opening script starts, and on
                -- a dialogue wait as the backstop in case the engine proc is missed between
                -- observations.
                if procActive(SYM.ProcScr_StdEventEngine) then return true end
                local observation = observeController()
                local state = controllerState(observation)
                if state == "dialogue_wait" then return true end
                -- Branch on the return, as the other five call sites do: a hard boot failure
                -- otherwise spins the whole cap and reports the generic "never reached", which
                -- names nothing (TUNE.bootSteps' own comment, #232).
                if advanceBootState(observation, state) == false then
                    return false, "boot stalled before ch05's opening: " .. tostring(state)
                end
                yield()
            end
            return false, "never reached ch05's opening event"
        end,
        afterPre = pokeNormalConfig,
        until_ = "prep",
    })
end

-- recordch05openinglupin (#25): the SAME film against the ch05lupinboot ROM, which carries a
-- live Lupin, so scene 4's CHECK_ALIVE takes its ALIVE arm and box 1 is Lupin's "The trail
-- leads here" instead of Pinky's "The tracks stop here". One routine, two ROMs: the scenario
-- drives identical input either way and the ROM decides which arm plays, which is the point.
-- Measured 2026-08-14, the two films agree through scenes 1-3 (bar 2-4 frame emulator timing
-- jitter around fades) and diverge from scene 4's FIRST BOX to the end. The tail divergence is
-- not four scenes of difference: the two arms' box 1 are different lengths, so everything after
-- is time-shifted and no frame lines up again. Compare them by eye, not by frame equality.
-- Delegates rather than aliases: matrix.py attributes harness SOURCE per function for the
-- verdict cache, and a bare `= scenarios.x` assignment is a name it cannot attribute a body
-- to. The cache stays correct either way -- matrix.reaches() closes over every NAME a body
-- mentions, so recordch05opening is inside this one's closure (verified: 55 names) and an
-- edit to it does move this scenario's key.
scenarios.recordch05openinglupin = function()
    return scenarios.recordch05opening()
end

-- recordch05join (#25): the MOTION proof for scene 5 -- Basil trundles up, cracks the tourist
-- joke, and JOINS. It is a SEPARATE film from recordch05opening rather than an extension of it,
-- because the two sit on opposite sides of Preparations: the opening's terminal IS the prep
-- screen, and this beat plays after it (decisions.md -> "Inheriting a channel is not inheriting
-- a POSITION"). Re-filming four proven backdrop scenes to reach a fourth-quarter beat would also
-- spend the whole record budget on footage #279 already shipped.
-- What only a run can answer: whether the map is actually UP behind the bubble. The beat's FADU
-- is ours -- the shared prep prologue fades to black and leaves it there -- and PutTalkBubble
-- anchors to a unit, so a missing fade or a camera still parked on the deploy pocket both render
-- as "the text played and looked wrong", which no memory assertion sees.
-- The terminal is BASIL TURNING BLUE **on the expected number of boxes**, not "dialogue happened".
-- Both are load-bearing. The CUSA is the join, so a film that ends on it has proved the beat
-- reached its own point; and the box COUNT is the only thing that says WHICH ARM ran -- Lupin's is
-- 3, the no-Lupin arm is 4, because Nicolas's authored break splits the substitute turn (#25).
-- Both arms run fine, which is the whole hazard: a scenario that checked only "a scene played"
-- would pass on either, and so would one that merely LOGGED the count. `expect` is therefore part
-- of the terminal -- on the wrong arm it is never satisfied and recordCutscene fails the run.
-- It cannot be a second `result()` call instead: `result` only LOGS, and run.sh breaks on the
-- first RESULT line it polls, so a FAIL logged after recordCutscene's PASS may never be read.
-- Run: PT_HOST_CHAPTER=6 tools/playtest/run.sh recordch05join (needs a CH05BOOT=1 ROM).
scenarios.recordch05join = function(expect)
    local BASIL, SAHNAR = 0x13, 0x16         -- CHARACTER_ARTUR / CHARACTER_MARISA
    expect = expect or 4                     -- ch05boot has no Lupin: the 4-box arm
    -- Scene 6's own A-presses, which this film now runs on to (#25). It is the NEXT thing in the
    -- same event list -- the CUSA is not the end of the after-prep block any more -- and reaching
    -- it costs nothing here, where the 49-box opening and prep are already paid for. A separate
    -- film would pay that boot again to capture seven boxes.
    local SCENE6_BOXES = 7
    -- ...and SCENE 7 after it, the last beat before turn 1 (#25). Two boxes with the moose's
    -- charge between them, which is the ONLY reason this film runs on again: the charge is
    -- NET-ZERO by construction (it breaks out of the pen and a negative-speed MOVE snaps it
    -- back off camera) and "it ended where it started" is indistinguishable from "it never
    -- moved" unless something watches the middle. So this samples the moose's tile every frame
    -- and latches BOTH halves -- it left the pen, and it is back on it when the map goes live.
    -- Its pen is parity-locked (threat 14.1, cornered on the map's top edge); a charge that
    -- quietly relocated it would hand the player a monster four tiles closer for free, and
    -- nothing static would ever see it.
    -- RUN_X/RUN_Y is the route's LAST leg, and the latch has to be that rather than "moved at
    -- all": since 2026-08-15 the moose is placed in the top-right corner before the beat, so it
    -- is already off its pen for the whole film and "not on (10,0)" proves nothing.
    local SCENE7_BOXES, MOOSE, PEN_X, PEN_Y, RUN_X, RUN_Y = 2, 0xb9, 10, 0, 10, 4
    local boxes, waiting, warned = 0, false, false
    local joined, scene6, charged, nocharge = false, false, false, false
    return recordCutscene({
        tag = "ch05join", speed = "normal", maxFrames = 15000, shotEvery = 4, pressEvery = 90,
        pre = function()
            -- Fast config BEFORE the boot, never after: this ROM is 49 boxes of opening ahead of
            -- Preparations, and a scenario that pokes it afterwards burns most of its budget on a
            -- scene it does not film (the standing ch05boot trap).
            pokeFastConfig()
            -- `bootToMap(true)` stops AT prep instead of driving through it, which is exactly the
            -- seam this film starts on. Then exit via Fight! unfilmed, so frame 1 is our FADU.
            -- The controllerState guard is ch03prep's, and it is not belt-and-braces: bootToMap
            -- ALSO returns true from its player_map_idle branch, so a missed prep classification
            -- would hand the opening to advanceBootState, which mashes A through prep AND through
            -- scene 5 -- and the film would then start after the beat it exists to record, with
            -- Basil already blue, and PASS having captured nothing.
            if not bootToMap(true) or controllerState() ~= "prep_main" then
                return false, "never reached ch05's Preparations"
            end
            if not driveThroughPrep() then return false, "Preparations never exited via Fight!" end
            return true
        end,
        afterPre = pokeNormalConfig,
        until_ = function()
            -- Count the RISING EDGE of each dialogue wait. recordCutscene advances the boxes
            -- itself, and this terminal is evaluated before it does, so every box is seen once.
            local now = controllerState() == "dialogue_wait"
            if now and not waiting then boxes = boxes + 1 end
            waiting = now
            -- Overshoot is decidable the moment it happens, so say so while the log still has
            -- the context; the generic "never reached its end" arrives much later.
            -- The ARM check still fires exactly at the CUSA, which is the only moment the count
            -- identifies which branch ran (Lupin 3, no-Lupin 4). Latched, because the film runs
            -- on past it now and `boxes` keeps climbing through scene 6.
            if not joined and findUnit(SYM.gUnitArrayBlue, 20, BASIL) and boxes == expect then
                joined = true
                log(string.format("ch05join: Basil is BLUE after %d boxes -- the %s arm; "
                    .. "the join CUSA landed", boxes,
                    expect == 3 and "Lupin (3-box)" or "no-Lupin (4-box)"))
            end
            if not joined and boxes > expect and not warned then
                warned = true
                log(string.format("ch05join: box %d is past the expected %d with Basil still "
                    .. "green -- the WRONG CHECK_ALIVE arm is playing on this ROM",
                    boxes, expect))
            end
            -- Then SCENE 6, the reason this film runs past the join (#25): Sahnar alone on the
            -- arena, vanilla's 0x9C3 as a plain on-map bubble. The terminal is her seven boxes
            -- AND the unit being there -- the bubble anchors to a unit, so a scene that played
            -- with a missing LOAD1 or a camera parked elsewhere renders as "the text happened
            -- and looked wrong", which no memory assertion sees. That is the whole reason this
            -- is a film and not a check.
            -- Latched: this used to BE the terminal, and a terminal only fires once. Now that
            -- the film runs on into scene 7 it is a waypoint, and an unlatched waypoint logs
            -- the same line on every frame until the next box lands.
            if not scene6 and joined and boxes == expect + SCENE6_BOXES
                and findUnit(SYM.gUnitArrayRed, 24, SAHNAR)
                and controllerState() ~= "dialogue_wait" then
                scene6 = true
                log(string.format("ch05join: scene 6 played its %d boxes with Sahnar RED on the "
                    .. "arena -- the summon put her there and the bubble had her to anchor to",
                    SCENE6_BOXES))
            end
            -- Scene 7. Sample the moose EVERY frame, not at the terminal: the charge is the
            -- middle of a message and it is undone before the scene ends, so the terminal alone
            -- cannot tell a lunge that ran from one that never fired.
            local moose = findUnit(SYM.gUnitArrayRed, 24, MOOSE)
            if moose and not charged and moose.x == RUN_X and moose.y == RUN_Y then
                charged = true
                log(string.format("ch05join: the moose RAN the route -- corner, left along the "
                    .. "rim, then down to (%d,%d)", RUN_X, RUN_Y))
            end
            -- The terminal is the moose STANDING ON ITS PEN after the scene's last box, and it
            -- is deliberately not "the last box landed". The snap back is three commands later
            -- (REMA, camera, STAL(30)), so there is a legitimate ~43-frame window -- measured on
            -- the 2026-08-14 run -- in which the moose is still on its charge tile with the
            -- boxes all spent. A terminal that read that window would call the reset a defect
            -- while it was on its way. Waiting for the pen instead makes a charge that never
            -- came BACK time the film out, which is the failure we actually want to see.
            if joined and charged and boxes == expect + SCENE6_BOXES + SCENE7_BOXES
                and moose and moose.x == PEN_X and moose.y == PEN_Y
                and controllerState() ~= "dialogue_wait" then
                log(string.format("ch05join: scene 7 played its %d boxes; the moose charged and "
                    .. "is back on (%d,%d) -- net-zero, so the fight starts where parity says",
                    SCENE7_BOXES, PEN_X, PEN_Y))
                return true
            end
            -- Both halves diagnosed WHERE THEY HAPPEN, latched, so the log carries the reason
            -- rather than leaving the generic "never reached its end" to be read backwards.
            if not nocharge and not charged
                and boxes == expect + SCENE6_BOXES + SCENE7_BOXES
                and controllerState() ~= "dialogue_wait" then
                nocharge = true
                log("ch05join: scene 7's boxes are spent and the moose never reached the end of "
                    .. "its route -- the charge is missing, and the beat is two lines and a pause")
            end
            return false
        end,
    })
end

-- recordch05moose (#25): scene 7 ALONE -- Pinky asks, the moose breaks, Meesmickle answers.
-- Runs on `ch05mooseboot`, whose beginning scene IS this beat: no backdrops, no PREP, no join,
-- no Sahnar monologue. `recordch05join` can reach scene 7 too and pays ~52 A-presses of approved
-- footage to do it, which is four and a half minutes of watching to review ten seconds; Nicolas
-- stopped a run over exactly that (2026-08-15). Iteration on a late beat is a BUILD, not a
-- playthrough -- so this films from the first frame of the thing under review.
-- What only a run can answer, and all three are things a still would hide:
--   * the bubble is DOWN while the moose runs ([CloseSpeechSlow]; it used to charge underneath
--     Pinky's box and was covered),
--   * the route TURNS on screen -- top-right corner, left along the rim, then down at them,
--   * and the moose is back on its parity-locked pen when the map goes live.
-- Run: PT_HOST_CHAPTER=6 tools/playtest/run.sh recordch05moose (needs a CH05MOOSE=1 ROM).
scenarios.recordch05moose = function()
    local MOOSE, PEN_X, PEN_Y, RUN_X, RUN_Y = 0xb9, 10, 0, 10, 4
    local BOXES = 2
    local boxes, waiting, charged = 0, false, false
    return recordCutscene({
        tag = "ch05moose", speed = "normal", maxFrames = 3000, shotEvery = 3, pressEvery = 90,
        pre = function()
            -- Fast config BEFORE the boot, as every ch05boot scenario must -- though on THIS
            -- ROM the boot is a title screen and a chapter intro, not an opening.
            pokeFastConfig()
            -- NOT bootToMap(): it drives to `player_map_idle`, and on this ROM the beginning
            -- scene IS the beat, so it would mash A through both boxes and hand the film an
            -- idle map. (Measured: 3000 frames of nothing, 2026-08-15.) Stop at the CHAPTER
            -- INTRO, spend its one press here, and let the film open on the FADU -- so the
            -- camera move and the hold on the moose are in shot, not just the dialogue.
            for _ = 1, TUNE.bootSteps do
                local obs = observeController()
                local st = controllerState(obs)
                if st == "dialogue_wait" then return true end      -- already at box 1
                if st == "chapter_intro_input" then
                    advanceBootState(obs, st)                      -- the last press before it
                    return true
                end
                if advanceBootState(obs, st) ~= true then
                    return false, "boot stalled at " .. tostring(st) .. " before scene 7"
                end
                yield()
            end
            return false, "boot cap expired before scene 7"
        end,
        afterPre = pokeNormalConfig,
        until_ = function()
            local now = controllerState() == "dialogue_wait"
            if now and not waiting then boxes = boxes + 1 end
            waiting = now
            local moose = findUnit(SYM.gUnitArrayRed, 24, MOOSE)
            if moose and not charged and moose.x == RUN_X and moose.y == RUN_Y then
                charged = true
                log(string.format("ch05moose: it RAN the route -- corner, left along the rim, "
                    .. "then down to (%d,%d)", RUN_X, RUN_Y))
            end
            -- Terminal is the moose STANDING ON ITS PEN after the last box, not the last box:
            -- the snap back is three commands later, so there is a legitimate window in which
            -- it is still on its charge tile with the boxes spent.
            if charged and boxes == BOXES and moose
                and moose.x == PEN_X and moose.y == PEN_Y
                and controllerState() ~= "dialogue_wait" then
                log(string.format("ch05moose: %d boxes; back on (%d,%d) -- net-zero, so the "
                    .. "fight starts where parity says", BOXES, PEN_X, PEN_Y))
                return true
            end
            return false
        end,
    })
end

-- recordch05joinlupin (#25): the same film against ch05lupinboot, whose live Lupin sends scene 5's
-- CHECK_ALIVE down its ALIVE arm -- so box 2 is Basil reading the wolf ("...Wolf. You're hers.")
-- rather than reading the party ("...You're none of hers."). One routine, two ROMs, and the 3 it
-- passes is the ASSERTION that the ROM picked the arm it was built to pick: if the CH05LUPIN
-- injection or the CHECK_ALIVE ever regresses, this ROM plays the 4-box arm and the terminal is
-- never met. Delegates rather than aliases, for the verdict-cache attribution reason recorded on
-- recordch05openinglupin.
scenarios.recordch05joinlupin = function()
    return scenarios.recordch05join(3)
end

-- recordch05ending (#25): the MOTION proof for ch05's ENDING -- scene 16, all three beats, over
-- BG_MS_ELVEN_TOMB. Films on the ch05endingboot DEBUG ROM (CH05ENDING=full), whose beginning
-- script LOMAs, loads Basil and Sahnar blue, arms the four reliquary flags and CALLs the ending
-- straight off New Game. Reaching it honestly is the whole opening, Preparations and a boss
-- kill, and there are three roster arms to look at.
-- What only a run can answer: whether the backdrop actually comes up behind the text, whether
-- the podium manager really does hold Basil for all nineteen boxes, and where the Guiding
-- Ring's popup lands relative to the closing
-- fade -- the give opens a BLOCKING convoy menu on a full pack, which is why it sits before the
-- FADI and why that placement is filmed rather than asserted.
-- THE MESSAGE ID IS THE ARM ASSERTION -- not the box count, which is a floor. All three arms
-- play fine and that is the hazard (decisions.md -> the ch05 endings); they are only three
-- boxes apart, so a length can say "at least this long" and never "this scene". The count
-- still guards LENGTH: 19 boxes is scene 16 with the berry beat IN (7 + 6 + 6), so a Sahnar
-- gate that regressed to always-skip drops to 13 and fails here rather than looking like a
-- shorter film. Every arm then adds the dev placeholder's own FOUR boxes.
-- Run: PT_HOST_CHAPTER=6 tools/playtest/run.sh recordch05ending (needs CH05BOOT=1 CH05ENDING=full).
scenarios.recordch05ending = function(opts)
    -- `opts.boxes` is the arm's own length and `opts.arm` the message that must produce it.
    -- Each arm is a WHOLE message rather than a spliced beat, so its A-press count is its
    -- authored box count plus the RBG-campfire placeholder that follows every one of them:
    --   full        0x9C9  19 + 4 = 23
    --   berry cut   0x9CA  13 + 4 = 17   (Sahnar was never recruited)
    --   Basil died  0x9F3  10 + 4 = 14
    -- The placeholder is FOUR boxes. This said "+1" and priced `full` at 20 -- wrong, and it
    -- never showed, because the count is a FLOOR (a short arm withholds the terminal rather
    -- than failing) so 23 >= 20 passed for months. Measured 2026-08-21 while filming the other
    -- two arms; the ARM is what actually gates now, and the floor only guards length.
    opts = opts or {}
    local BOXES = opts.boxes or 23
    local ARM = opts.arm or 0x9C9        -- which ENDING message this ROM must actually play
    local boxes, waiting, blamed, playedMsg = 0, false, false, nil
    return recordCutscene({
        -- recordch05opening's cadence: a 20-box run of scenes, and filming every frame makes a
        -- GIF minutes long.
        tag = "ch05ending", speed = "normal", maxFrames = 14000, shotEvery = 4, pressEvery = 90,
        pre = function()
            -- Fast through the boot, normal for the scenes -- and stop at the CHAPTER INTRO
            -- rather than driving to the map, because on THIS ROM the beginning script IS the
            -- ending: bootToMap() would mash A through the whole thing and film an empty map
            -- (the same trap recordch05moose documents).
            pokeFastConfig()
            for _ = 1, TUNE.bootSteps do
                local obs = observeController()
                local st = controllerState(obs)
                if st == "dialogue_wait" then return true end
                if st == "chapter_intro_input" then
                    advanceBootState(obs, st)
                    return true
                end
                if advanceBootState(obs, st) ~= true then
                    return false, "boot stalled at " .. tostring(st) .. " before the ending"
                end
                yield()
            end
            return false, "boot cap expired before ch05's ending"
        end,
        afterPre = pokeNormalConfig,
        -- Terminal is the TITLE screen, because the ending lands on the dev placeholder and
        -- that ends on MNTS -- ch06 is not hosted yet, and that is by design.
        until_ = function()
            local now = controllerState() == "dialogue_wait"
            if now and not waiting then
                boxes = boxes + 1
                -- WHICH ending is on screen, latched on its first box. The box count below is
                -- a FLOOR (a short arm withholds the terminal), so it can say "at least this
                -- long" and never "this arm" -- and these three arms are only 3 boxes apart.
                -- `sActiveMsg` names the message outright (decisions.md -> "Two arms of one
                -- branch can be the same LENGTH").
                playedMsg = playedMsg or INSPECT.activeMsg()
            end
            waiting = now
            if procActive(SYM.gProcScr_TitleScreen) then
                if playedMsg ~= ARM then
                    if not blamed then
                        blamed = true
                        log(string.format("ch05ending: the scene that played was message 0x%X, "
                            .. "not the 0x%X this ROM's arm asks for -- filming the wrong arm "
                            .. "under the right name is the one failure a floor cannot catch",
                            playedMsg or 0, ARM))
                    end
                    return false
                end
                if boxes < BOXES then
                    -- Refuse the terminal rather than passing a short film, which is
                    -- recordch05moose's shape: doneFn is read for truthiness alone, so an
                    -- assertion that fails has to WITHHOLD the end and let the cap expire.
                    -- The log is what names it -- the verdict line only says "never reached".
                    if not blamed then
                        blamed = true
                        log(string.format("ch05ending: the title arrived after %d boxes, not "
                            .. "the %d this arm (message 0x%X) runs to -- the scene was SHORTER "
                            .. "than it should be. Arm lengths, placeholder included: 23 full, "
                            .. "17 berry-beat cut, 14 Basil's death variant.",
                            boxes, BOXES, ARM))
                    end
                    return false
                end
                log(string.format("ch05ending: %d boxes of message 0x%X -- the arm this ROM "
                    .. "was built for", boxes, playedMsg))
                return true
            end
            return false
        end,
    })
end

-- recordch05endingnosahnar (#25): the SAME ending with the berry exchange cut, which is what a
-- player who never turned Sahnar sees. Six boxes shorter, and the cut is generated from the one
-- locked script by `variant_beat` -- so what this films is whether the drop reads as a scene or
-- as a hole where a scene was.
-- Run: PT_HOST_CHAPTER=6 tools/playtest/run.sh recordch05endingnosahnar (CH05ENDING=no-sahnar).
scenarios.recordch05endingnosahnar = function()
    return scenarios.recordch05ending({ boxes = 17, arm = 0x9CA })
end

-- recordch05endingbasildied (#25): scene 17, the ending played over Basil's body. ONE arm and no
-- Sahnar axis -- she is deliberately silent over her even when recruited (the YAML's "NOT NESTED"
-- note) -- so this is the whole variant in ten boxes. The last of ch05's unfilmed scenes.
-- Run: PT_HOST_CHAPTER=6 tools/playtest/run.sh recordch05endingbasildied (CH05ENDING=basil-died).
scenarios.recordch05endingbasildied = function()
    return scenarios.recordch05ending({ boxes = 14, arm = 0x9F3 })
end

-- recordch05recruit (#25): the MOTION proof for the locked Basil->Sahnar Talk at 0x9E8 -- the
-- chapter's payoff scene, and the review artifact for it. Stills mislead on dialogue (they catch
-- the typewriter mid-stroke), so what gets reviewed is the film.
-- Setup is unfilmed and is ch05recruit's own chain with the assertions stripped: boot ch05, idle
-- turn 1, end it, let the eruption speak until Sahnar rises RED, then park Basil orthogonally
-- adjacent and take Talk. The camera starts on Sahnar's "Far enough. The tomb is--" and runs to
-- the CUSA, so the film covers the recognition, both proofs, the turn, and Basil's unanswered
-- berry question. The chain is repeated rather than shared because harness.lua has two top-level
-- local slots left under Lua's 200-local ceiling (tools/check.py measures it) and a shared driver
-- would need one; ch05recruit remains the ASSERTING gate, this one only has to film.
-- Run: PT_HOST_CHAPTER=6 tools/playtest/run.sh recordch05recruit (needs a CH05BOOT=1 ROM).
scenarios.recordch05recruit = function()
    local BASIL, SAHNAR, boxes = 0x13, 0x16, 0   -- CHARACTER_ARTUR / CHARACTER_MARISA
    return recordCutscene({
        -- shotEvery 4, not the 1 a one-box quote can afford: this is a 21-A-press scene, and at
        -- every frame it captures ~2900 shots that make a four-minute GIF of a one-minute scene.
        tag = "ch05recruit", speed = "normal", maxFrames = 9000, shotEvery = 4,
        pressEvery = 90,
        pre = function()
            pokeFastConfig()
            if not bootToMap() then return false, "never reached the ch05 map" end
            if not waitFor(function()
                return faction() == 0 and not menuOpen()
                    and not procActive(SYM.ProcScr_StdEventEngine)
            end, 6000, true) then
                return false, "ch05 map never became idle"
            end
            if not findUnit(SYM.gUnitArrayBlue, 20, BASIL) then
                return false, "Basil is not BLUE at turn 1 -- the opening join CUSA never fired"
            end
            -- NO turn-end, and no eruption to sit through. Sahnar is on the arena at TURN 1
            -- since #25 (Ravisin raises her in scene 3), so the Talk is reachable immediately
            -- and this film spends none of its budget on Ravisin's warning -- which was never
            -- its subject. The old chain ended turn 1 and waited on `turn() >= 2 and redSahnar()`;
            -- with her red from the start that breaks the moment the counter ticks, mid-eruption,
            -- and the Talk would have been driven while the warning was still on screen.
            local sah = findUnit(SYM.gUnitArrayRed, 24, SAHNAR)
            if not sah then
                return false, "Sahnar is not RED on the arena at turn 1 -- scene 6's LOAD1 "
                    .. "never fired, so there is nobody to Talk"
            end
            -- setMapUnit keeps the tile->unit grid in sync, so adjacency reads with no phase
            -- cycle: the point of this film is the scene, not a 5-MOV healer's walk.
            local basil = findUnit(SYM.gUnitArrayBlue, 20, BASIL)
            if not basil then return false, "Basil left the blue array before the Talk" end
            local grid, parked = mapUnitAt(basil.x, basil.y), false
            for _, d in ipairs({ { 1, 0 }, { -1, 0 }, { 0, 1 }, { 0, -1 } }) do
                local tx, ty = sah.x + d[1], sah.y + d[2]
                if tx >= 0 and ty >= 0 and mapUnitAt(tx, ty) == 0 then
                    setMapUnit(basil.x, basil.y, 0)
                    emu:write8(basil.addr + 0x10, tx); emu:write8(basil.addr + 0x11, ty)
                    setMapUnit(tx, ty, grid)
                    parked = true
                    break
                end
            end
            if not parked then return false, "no free tile adjacent to Sahnar to park Basil" end
            basil = findUnit(SYM.gUnitArrayBlue, 20, BASIL)
            if not basil or not moveUnit(basil.x, basil.y, basil.x, basil.y) then
                return false, "no live command menu for Basil"
            end
            if not chooseTalk() then
                return false, "Basil's command menu did not expose Talk"
            end
            return true
        end,
        afterPre = pokeNormalConfig,
        -- Stop on the CUSA, not on a box count: the flip is what ENDS the scene, and a count
        -- here would make the camera the thing that decides when the payoff is over.
        until_ = function()
            if controllerState() == "dialogue_wait" then boxes = boxes + 1 end
            return findUnit(SYM.gUnitArrayBlue, 20, SAHNAR) ~= nil
        end,
    })
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
    waitFor(function() return faction() == 0 and not menuOpen()
        and not procActive(SYM.ProcScr_StdEventEngine) end, 6000, true)
    local before = terrainAt(DOOR_X, DOOR_Y)
    log(string.format("ch04cottage: door (%d,%d) terrain=0x%02X before visiting",
        DOOR_X, DOOR_Y, before))
    if before ~= VILLAGE_REGULAR then
        return result("FAIL", string.format(
            "(%d,%d) is terrain 0x%02X, not a visitable village (0x%02X) -- FE8 gates the Visit "
            .. "menu item on the TERRAIN before it ever consults the location event (bmmenu.c)",
            DOOR_X, DOOR_Y, before, VILLAGE_REGULAR))
    end
    local ok, why, spoke = visitVillage(DOOR_X, DOOR_Y, function()
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

-- recordch04cottage (#24): the cottage's five boxes in MOTION, for review with Nicolas -- stills
-- catch the typewriter mid-stroke, so a scene is reviewed as a GIF (decided 2026-06-10).
-- The walk-in runs UNFILMED in `pre`, at FAST speed, handing back to normal before the event
-- starts: recordCutscene sets speed BEFORE pre runs, so an unfilmed grind at real speed eats the
-- frame budget before the beat begins (the recordch04moose lesson). The camera picks up at the
-- first text box and stops when the door shuts.
-- Run: PT_HOST_CHAPTER=5 tools/playtest/run.sh recordch04cottage (needs a CH04BOOT=1 ROM), then
--   tools/playtest/make_gif.py recordch04cottage cottage --name ch04-forest-cottage --fps 14
scenarios.recordch04cottage = function()
    local DOOR_X, DOOR_Y, VILLAGE_CLOSED = 1, 11, 0x04
    return recordCutscene({
        tag = "cottage", speed = "normal", maxFrames = 3000,
        pre = function()
            pokeFastConfig()
            if not bootToMap() then return false, "never reached the ch04 map" end
            waitFor(function() return faction() == 0 and not menuOpen()
                and not procActive(SYM.ProcScr_StdEventEngine) end, 6000, true)
            local ok, why = openVillageVisit(DOOR_X, DOOR_Y)
            if not ok then return false, why end
            pokeNormalConfig()   -- film the line at real speed
        end,
        until_ = function() return terrainAt(DOOR_X, DOOR_Y) == VILLAGE_CLOSED end,
    })
end

-- ch04snag (#214): the Iron Axe's whole purpose. Vanilla Ch4's village hands you the axe to chop
-- a snag into a bridge, and the retile kept the snag at (4,8) with the river at (4,9). Snags are
-- natively attackable -- bmtrick.c auto-adds a 20 HP TRAP_OBSTACLE on every TERRAIN_SNAG tile --
-- but the BRIDGE half is a MapChange the chapter has to register, and hosted chapters get their
-- changeLayerId zeroed. So this asserts the payoff by TERRAIN, which is what actually decides
-- whether a unit can cross: (4,9) is impassable river before, and a crossing after.
-- Run: PT_HOST_CHAPTER=5 tools/playtest/run.sh ch04snag (needs a CH04BOOT=1 ROM).
scenarios.ch04snag = function()
    local SNAG_X, SNAG_Y = 4, 8
    local CROSS_X, CROSS_Y = 4, 9        -- the river row the trunk falls across
    -- TERRAIN_BRIDGE_SNAG (constants/terrains.h). snowy-bern now paints this native terrain with
    -- the winterized center of vanilla's downed-log composition, replacing the old generic-bridge
    -- workaround (#24).
    local T_CROSSING = 0x34
    if not bootToMap() then return result("FAIL", "never reached the ch04 map") end
    pokeFastConfig()
    waitFor(function() return faction() == 0 and not menuOpen()
        and not procActive(SYM.ProcScr_StdEventEngine) end, 6000, true)
    log(string.format("ch04snag: before -- snag(%d,%d) terrain=0x%02X  crossing(%d,%d) terrain=0x%02X",
        SNAG_X, SNAG_Y, terrainAt(SNAG_X, SNAG_Y), CROSS_X, CROSS_Y, terrainAt(CROSS_X, CROSS_Y)))
    if terrainAt(CROSS_X, CROSS_Y) == T_CROSSING then
        return result("FAIL", "the crossing is already a bridge before the snag was touched")
    end
    -- Any armed unit will do; the axe is the fiction, not a requirement (a snag is an obstacle
    -- and takes damage from anything that can reach it).
    local u
    for i = 0, 19 do
        local c = unitAt(SYM.gUnitArrayBlue, i)
        if c and not isDead(c) and (c.state & 0x2) == 0 and unitAttackRange(c) then u = c break end
    end
    if not u then return result("FAIL", "no armed blue unit to swing at the snag") end
    -- Park adjacent to the snag and hit it until the obstacle dies. Its HP is the trap's `extra`,
    -- so the only signal that matters is the TERRAIN flipping underneath.
    for swing = 1, 12 do
        if terrainAt(CROSS_X, CROSS_Y) == T_CROSSING then break end
        local m = findUnit(SYM.gUnitArrayBlue, 20, u.charId)
        if not m then break end
        if (m.state & 0x2) ~= 0 then
            runEnemyPhase()
            waitFor(function() return faction() == 0 and not menuOpen() end, 900, true)
            m = findUnit(SYM.gUnitArrayBlue, 20, u.charId)
            if not m then break end
        end
        local grid = mapUnitAt(m.x, m.y)
        setMapUnit(m.x, m.y, 0)
        emu:write8(m.addr + 0x10, SNAG_X); emu:write8(m.addr + 0x11, SNAG_Y - 1)
        setMapUnit(SNAG_X, SNAG_Y - 1, grid)
        m = findUnit(SYM.gUnitArrayBlue, 20, u.charId)
        if not cursorTo(m.x, m.y) then break end
        if moveUnit(m.x, m.y, m.x, m.y) then
            chooseAttack(m.addr)
            waitFor(function() return faction() == 0 and not menuOpen()
                and not procActive(SYM.gProc_ekrBattle) end, 900)
        end
        log(string.format("  swing %d: crossing terrain=0x%02X", swing, terrainAt(CROSS_X, CROSS_Y)))
    end
    shot("ch04snag")
    local after = terrainAt(CROSS_X, CROSS_Y)
    log(string.format("ch04snag: after -- snag(%d,%d) terrain=0x%02X  crossing(%d,%d) terrain=0x%02X",
        SNAG_X, SNAG_Y, terrainAt(SNAG_X, SNAG_Y), CROSS_X, CROSS_Y, after))
    if after ~= T_CROSSING then
        return result("FAIL", string.format(
            "the snag broke but (%d,%d) is terrain 0x%02X, not a crossing (0x%02X) -- the "
            .. "MapChange did not apply", CROSS_X, CROSS_Y, after, T_CROSSING))
    end
    return result("PASS", string.format(
        "the snag fell: (%d,%d) is now a bridge -- the river is crossable", CROSS_X, CROSS_Y))
end

-- attackprobe (#204): regression diagnostic for the retired blind-Attack failure. When the engine
-- saw no target, row 0 was Item and the old bot used a vulnerary at full HP forever. This stages ONE
-- unit's attack on the CURRENT host chapter and dumps the DATA that decides that row -- the live
-- vision range, every red with the grid id and fog byte under it, and the 5x5 gBmMapUnit window
-- around the firing tile -- then photographs the open menu, which says outright whether an
-- Attack row exists. Chapter-agnostic: it reads whatever map bootToMap lands on.
-- Run: PT_HOST_CHAPTER=5 tools/playtest/run.sh attackprobe
scenarios.attackprobe = function()
    if not bootToMap() then return result("FAIL", "never reached the map") end
    pokeFastConfig()
    emu:write8(SYM.gPlaySt + 0x0D, 0)   -- lift fog, exactly as the clear-bot does
    waitFor(function() return faction() == 0 and not menuOpen()
        and not procActive(SYM.ProcScr_StdEventEngine) end, 900, true)
    local w, h = mapSize()
    local fogAt = function(x, y) return ru8(ru32(ru32(SYM.gBmMapFog) + y * 4) + x) end
    log(string.format("map=%dx%d turn=%d visionRange=%d (0 = fog off)",
        w, h, turn(), ru8(SYM.gPlaySt + 0x0D)))
    for i = 0, 23 do
        local r = unitAt(SYM.gUnitArrayRed, i)
        if r and not isDead(r) then
            pokeFrail(r); pokeHarmless(r)
            log(string.format("  red[%02d] char=0x%02X at (%d,%d) hp=%d grid=0x%02X fog=%d",
                i, r.charId, r.x, r.y, r.hp, mapUnitAt(r.x, r.y), fogAt(r.x, r.y)))
        end
    end
    -- The lift the clear-bot actually uses. It reports how many reds reached the grid, which is
    -- the whole diagnosis: 0 means the engine cannot see a single enemy, whatever the unit array
    -- says, and no tile on this map will offer an Attack row.
    if liftFogOntoTheGrid() == 0 then
        return result("FAIL", "fog lifted but NO red reached gBmMapUnit -- nothing is attackable")
    end
    -- blue[0] may have spent its action triggering the refresh; take the first unit that still
    -- has one AND carries a weapon.
    local u, mn, mx
    for i = 0, 19 do
        local c = unitAt(SYM.gUnitArrayBlue, i)
        if c and not isDead(c) and (c.state & 0x2) == 0 then
            local a, b = unitAttackRange(c)
            if a then u, mn, mx = c, a, b break end
        end
    end
    if not u then return result("FAIL", "no armed, unexhausted blue unit left to probe with") end
    log(string.format("probing with char=0x%02X at (%d,%d) reach=[%d,%d] grid=0x%02X",
        u.charId, u.x, u.y, mn, mx, mapUnitAt(u.x, u.y)))
    if not teleportToFiringTile(u, mn, mx) then
        return result("FAIL", "no firing tile within reach of any live enemy")
    end
    u = findUnit(SYM.gUnitArrayBlue, 20, u.charId)   -- refresh: the teleport relocated it
    if not u then return result("FAIL", "the probed unit vanished from the blue array") end
    log(string.format("engine offers an Attack row from (%d,%d): %s", u.x, u.y,
        tostring(canAttackFromHere(u, mn, mx))))
    for dy = -2, 2 do
        local row = {}
        for dx = -2, 2 do
            local x, y = u.x + dx, u.y + dy
            row[#row + 1] = (x >= 0 and x < w and y >= 0 and y < h)
                and string.format("%02X", mapUnitAt(x, y)) or "--"
        end
        log(string.format("  grid y=%2d (x=%d..%d): %s", u.y + dy, u.x - 2, u.x + 2,
            table.concat(row, " ")))
    end
    if not moveUnit(u.x, u.y, u.x, u.y) then
        shot("attackprobe-nomenu")
        return result("FAIL", string.format(
            "command menu never opened on firing tile (%d,%d)", u.x, u.y))
    end
    wait(30)
    shot("attackprobe-menu")
    return result("PASS", string.format(
        "command menu open on (%d,%d) -- read attackprobe-menu for the Attack row", u.x, u.y))
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
    waitFor(function() return faction() == 0 and not menuOpen()
        and not procActive(SYM.ProcScr_StdEventEngine) end, 6000, true)
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
        waitFor(function() return faction() == 0 and not menuOpen()
            and not procActive(SYM.ProcScr_StdEventEngine) end, 6000, true)
        for i = 0, 23 do
            local r = unitAt(SYM.gUnitArrayRed, i)
            if r and not isDead(r) then pokeFrail(r); pokeHarmless(r) end
        end
        -- Stage-by-stage logging (#204): a clear-bot that stalls must say WHICH stage failed --
        -- no weapon / no firing tile / no command menu / no kill. The first run of this scenario
        -- reported only "liveEnemies=10" for 16 turns, which named none of them.
        local mw, mh = mapSize()
        log(string.format("%s iter %d: gameTurn=%d map=%dx%d liveEnemies=%d",
            tag, t, turn(), mw, mh, #liveEnemies()))
        for i = 0, 19 do
            if won() or #liveEnemies() == 0 then break end
            local u = unitAt(SYM.gUnitArrayBlue, i)
            if u and not isDead(u) and (u.state & 0x2) == 0 then
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
                        local before = #liveEnemies()
                        chooseAttack(u.addr, function() return #liveEnemies() == 0 end)
                        -- Break the settle the moment the kill empties the map: DefeatAll fires
                        -- on that death and the ending starts playing at once, so a blind
                        -- 600-frame wait here spends the victory fanfare and half the treeline
                        -- scene before the capture loop below gets its first frame (#204).
                        waitFor(function() return #liveEnemies() == 0
                            or (faction() == 0 and not menuOpen()
                                and not procActive(SYM.gProc_ekrBattle)) end, 600)
                        log(string.format("  blue[%d] pid=0x%02X attacked from (%d,%d): liveEnemies %d -> %d",
                            i, u.charId, u.x, u.y, before, #liveEnemies()))
                    end
                end
            end
        end
        log(string.format("%s turn %d: liveEnemies=%d chapter=%d", tag, t, #liveEnemies(), chapter()))
        if won() then break end
        if gameOverActive() then shot(tag .. "-gameover")
            return result("FAIL", string.format("game over on turn %d -- party lost", t)) end
        if #liveEnemies() == 0 then break end
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
    local ended = false
    for f = 1, 5400 do
        if f % 4 == 0 then shot(tag) end
        if won() then ended = true break end
        -- Advance the ending only where FE8 is CLASSIFIED as waiting for it (#238). The
        -- every-90-frames A this replaces was the "stray press on Press START" hazard the
        -- comment above worries about, made structural: a cadence cannot see what is on
        -- screen, so the guard against it was a frame count chosen to be slow enough. A
        -- guarded input on dialogue_wait cannot fire on the title at all.
        if controllerState() == "dialogue_wait" then
            if not guardedInput("advance_dialogue", "A", "the ending's dialogue wait clears",
                function(after) return controllerState(after) ~= "dialogue_wait" end, 120) then
                break
            end
        else
            yield()
        end
    end
    log(string.format("%s: liveEnemies=%d chapter=%d (host=%d)",
        tag, #liveEnemies(), chapter(), HOST_CHAPTER))
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

-- recordch04open: the ch04 OPENING in motion (#24 Stage 4) -- the two-BG Lonelywood scene:
-- beat A in Speaker Nimsy Huddle's cottage over the vanilla House1 hearth, then the CUT to the
-- fogged forest edge for Pinky's fog-of-war heads-up. The second BACG rides a REMOVEPORTRAITS
-- re-arm, and the podium anchors are what keep Nimsy from fading herself out mid-scene -- both
-- are things only MOTION shows. Fresh CH04BOOT New Game (no checkpoint), up to Preparations.
-- Run: PT_HOST_CHAPTER=5 tools/playtest/run.sh recordch04open (needs a CH04BOOT=1 ROM).
scenarios.recordch04open = function()
    return recordCutscene({ tag = "ch04open", until_ = "prep", pressEvery = 90 })
end

-- recordch04reveal: the turn-2 wolf-pack REVEAL cutscene in motion (#24 Stage 2c/4) -- the
-- camera pans to the NW fog, the pack bursts in on LOAD1, CUMO focuses Lupin commanding it,
-- and the two beats plant the parley. Unlike the opening this one fires MID-CHAPTER, so the
-- lead-up is driven (boot -> prep -> idle turn 1) and the recorder picks up at the turn-2
-- player phase. Terminal = the event engine has let go and control is back.
-- Run: PT_HOST_CHAPTER=5 tools/playtest/run.sh recordch04reveal (needs a CH04BOOT=1 ROM).
scenarios.recordch04reveal = function()
    if not bootToMap() then return result("FAIL", "never reached the ch04 map") end
    waitFor(function()
        return faction() == 0 and not menuOpen() and not procActive(SYM.ProcScr_StdEventEngine)
    end, 900, true)
    if not endTurn() then return result("FAIL", "could not end turn 1") end
    -- Ride turn 1's enemy phase out inside the RECORDER so the reveal itself is captured. Both
    -- paths now advance only an observed dialogue-input wait; the recorder additionally takes
    -- dense frames until turn 2's event engine lets go at EVBIT_T.
    local sawTurn2 = false
    return recordCutscene({
        tag = "ch04reveal", maxFrames = 5400, pressEvery = 90,
        until_ = function()
            if turn() >= 2 then sawTurn2 = true end
            return sawTurn2 and faction() == 0 and not menuOpen()
                and not procActive(SYM.ProcScr_StdEventEngine)
        end,
    })
end

-- recordch03talk: the Trex TALK-RECRUIT in motion (#23 Cutscenes) -- green Trex standing on the
-- ch03 map, a party member Talks to him, the migrated bounty dialogue plays, and the CUSA flips
-- him GREEN -> BLUE (cast OBJ palette). Same park-adjacent dance as the ch03talk PASS/FAIL test,
-- but films densely (every 3 frames) through the beat for a GIF. Fresh CH03BOOT New Game.
scenarios.recordch03talk = function()
    if not bootToMap() then return result("FAIL", "never reached the ch03 map") end
    local CHAR_TREX = 0x1C -- CHARACTER_RENNAC (Trex rides the Rennac slot)
    local function blueTrex() return findUnit(SYM.gUnitArrayBlue, 20, CHAR_TREX) end
    local trex = findUnit(SYM.gUnitArrayGreen, 12, CHAR_TREX)
    if not trex then return result("FAIL", "green Trex (0x1C) not found in the green array") end
    local rec = blue(0x01)
    if not rec then return result("FAIL", "leader (0x01) not deployed") end
    -- Park the recruiter on a free tile orthogonally adjacent to green Trex (setMapUnit keeps the
    -- occupancy grid in sync so Talk-adjacency reads with no phase cycle -- the ch03talk trick).
    local rgrid = mapUnitAt(rec.x, rec.y)
    local parked = false
    for _, d in ipairs({ { 1, 0 }, { -1, 0 }, { 0, 1 }, { 0, -1 } }) do
        local tx, ty = trex.x + d[1], trex.y + d[2]
        if tx >= 0 and tx <= 24 and ty >= 0 and ty <= 15 and mapUnitAt(tx, ty) == 0 then
            setMapUnit(rec.x, rec.y, 0)
            emu:write8(rec.addr + 0x10, tx); emu:write8(rec.addr + 0x11, ty)
            setMapUnit(tx, ty, rgrid)
            parked = true
            break
        end
    end
    if not parked then return result("FAIL", "no free tile adjacent to Trex to park the recruiter") end
    pokeNormalConfig(); pokeAnimsOn()
    -- Clear the turn-1 entrance cutscene so we have real control (cf. recordch03win).
    waitFor(function()
        return faction() == 0 and not menuOpen()
           and not procActive(SYM.ProcScr_StdEventEngine)
           and not procActive(SYM.ProcScr_BattleEventEngine)
    end, 900, true)
    -- 1. Frame GREEN Trex on his ledge before the talk.
    cursorTo(trex.x, trex.y)
    for f = 1, 60 do if f % 3 == 0 then shot("ch03talk") end yield() end
    -- 2. Talk through the live semantic command and target selector, then film through CUSA.
    rec = blue(0x01)
    waitFor(function() return faction() == 0 and not menuOpen() end, 300, true)
    if not moveUnit(rec.x, rec.y, rec.x, rec.y) then
        return result("FAIL", "no command menu for the recruiter")
    end
    if not chooseTalk() then return result("FAIL", "semantic Talk did not reach dialogue input") end
    -- The migrated recruit dialogue is several pages; advance only at TalkWaitForInput.
    for i = 1, 3600 do
        if i % 3 == 0 then shot("ch03talk") end
        if blueTrex() then break end
        if controllerState() == "dialogue_wait" then
            if not guardedInput("advance_dialogue", "A", "dialogue input wait clears", function(after)
                return controllerState(after) ~= "dialogue_wait"
            end, 120) then return result("FAIL", "Talk dialogue input did not advance") end
        else yield() end
    end
    if not blueTrex() then return result("FAIL", "Trex never flipped blue (CUSA did not fire)") end
    for f = 1, 40 do if f % 3 == 0 then shot("ch03talk") end yield() end -- linger on the flip
    -- 3. The CUSA changes Trex's FACTION, but his standing MAP SPRITE only redraws to the blue
    --    party palette on a RefreshUnitSprites (phase transition) -- so cycle one phase, then frame
    --    him again to SHOW the green->blue party-palette sprite (the sprite we painted).
    cursorTo(trex.x, trex.y)
    for f = 1, 24 do if f % 3 == 0 then shot("ch03talk") end yield() end
    runEnemyPhase() -- end turn -> enemy phase -> back to player: triggers the sprite refresh
    local bt = blueTrex()
    local framed
    if bt then framed = cursorTo(bt.x, bt.y) else framed = cursorTo(trex.x, trex.y) end
    if not framed then return result("FAIL", "could not frame Trex after the phase refresh") end
    for f = 1, 90 do if f % 3 == 0 then shot("ch03talk") end yield() end -- Trex now blue on the map
    return result("PASS", "ch03 talk-recruit recorded (green -> blue, sprite refreshed)")
end

-- recordch03win: the grell/mogall's DEATH + the ending cutscene in motion (#23 Cutscenes). Same
-- park-the-grell-adjacent + scripted-kill dance as the ch03win PASS/FAIL test, but films densely:
-- the leader's battle animation, the grell's death, its flagged defeat quote (EVFLAG_DEFEAT_BOSS),
-- then the DefeatBoss ending cutscene (RBG's bounty over the Termalaine square BG -> title). A
-- bounded A-cadence advances the ending text beats but stops the instant the title proc appears
-- (mashing at "Press START" would boot a spurious New Game). Fresh CH03BOOT New Game.
scenarios.recordch03win = function()
    if not bootToMap() then return result("FAIL", "never reached the ch03 map") end
    if not red(0xb7) then return result("FAIL", "grell (pid 0xb7) not found in the red array") end
    local leader = blue(0x01)
    if not leader then return result("FAIL", "leader (0x01) not deployed") end
    emu:write16(leader.addr + 0x1E, 0x2D1F) -- Iron Axe in items[0]: guaranteed in-range kill weapon
    pokeAnimsOn()
    -- The longer opening + the turn-1 Trex ENTRANCE cutscene (TURN(1) event) hold control past
    -- bootToMap; until it clears, moveUnit can't open a command menu (the driver-pacing regression
    -- the handoff flags). Advance (tapping A) until genuine player control returns.
    waitFor(function()
        return faction() == 0 and not menuOpen()
           and not procActive(SYM.ProcScr_StdEventEngine)
           and not procActive(SYM.ProcScr_BattleEventEngine)
    end, 900, true)
    for f = 1, 20 do if f % 3 == 0 then shot("ch03win") end yield() end -- settle on the map
    -- Park the frail'd grell on a free tile adjacent to the leader (no other foe near the left
    -- entrance) so the attack target is unambiguously the grell. Re-park each attempt in case a
    -- whiff or the grell's AI move disturbs it (mirrors the ch03win PASS/FAIL retry).
    local function parkGrell()
        local g = red(0xb7)
        if not g or isDead(g) then return false end
        pokeFrail(g); g = red(0xb7)
        local ggrid = mapUnitAt(g.x, g.y)
        for _, d in ipairs({ { 1, 0 }, { -1, 0 }, { 0, 1 }, { 0, -1 } }) do
            local tx, ty = leader.x + d[1], leader.y + d[2]
            if tx >= 0 and tx <= 24 and ty >= 0 and ty <= 15 and mapUnitAt(tx, ty) == 0 then
                setMapUnit(g.x, g.y, 0)
                emu:write8(g.addr + 0x10, tx); emu:write8(g.addr + 0x11, ty)
                setMapUnit(tx, ty, ggrid)
                return true
            end
        end
        return false
    end
    -- Attack + FILM the battle anim. moveUnit lands on the command menu; then A(Attack) ->
    -- A(weapon) -> A(target) starts combat. CRUCIAL: pressing A DURING an FE8 battle anim SKIPS
    -- it, so we must NOT press once combat starts -- just screenshot every frame while it plays.
    -- The hit lands late in the anim (grell -> dead); we film the death collapse, THEN tap A to
    -- clear the EXP/result screen (chooseAttack's greyed+tapA terminator both skips the anim AND
    -- fires before it renders, which is why the first cut missed the whole kill).
    local function filmedAttack()
        leader = blue(0x01)
        if not cursorTo(leader.x, leader.y) then return end
        press(K.A); wait(15)         -- select the leader; the move-range display animates in
        -- Confirm on the leader's own tile (no move) to open the command menu. A SINGLE confirm-A
        -- gets eaten while the range display is still settling (the ch03win regression: enemy
        -- poked, actor at rest, cursor already there so no travel delay) -- so retry A until the
        -- menu actually opens, checking BEFORE each extra press so we never over-advance into it.
        local opened = false
        for _ = 1, 10 do
            if menuOpen() then opened = true break end
            press(K.A); if waitFor(menuOpen, 14) then opened = true break end
        end
        if not opened then press(K.B); press(K.B); return end
        press(K.A); wait(8); press(K.A); wait(8); press(K.A) -- Attack -> weapon -> target -> combat
        local deadAt = nil
        for i = 1, 900 do
            if i % 2 == 0 then shot("ch03win") end
            if not deadAt and (isDead(red(0xb7)) or eventFlag(2)) then deadAt = i end
            if deadAt then
                if i > deadAt + 200 then break end                 -- ~200f tail: death + defeat quote
                if i > deadAt + 70 and i % 10 == 0 then press(K.A, 2) end -- clear EXP AFTER the death anim
            end
            yield()
        end
    end
    for turn = 1, 3 do
        if isDead(red(0xb7)) or eventFlag(2) then break end
        if not parkGrell() then return result("FAIL", "no free tile adjacent to the leader for the grell") end
        cursorTo(leader.x, leader.y)
        for f = 1, 30 do if f % 3 == 0 then shot("ch03win") end yield() end -- frame the standoff
        filmedAttack()
        if isDead(red(0xb7)) or eventFlag(2) then break end
        -- a whiff: run the enemy phase (filming) and retry next player turn
        for f = 1, 40 do if f % 4 == 0 then shot("ch03win") end yield() end
        if runEnemyPhase() == "gameover" then return result("FAIL", "unexpected game over") end
    end
    if not (isDead(red(0xb7)) or eventFlag(2)) then
        return result("FAIL", "could not kill the grell in 3 turns")
    end
    -- Film the defeat quote + the DefeatBoss ending cutscene. Advance text with a bounded
    -- A-cadence, breaking the instant the title proc appears (mashing there boots a New Game).
    local presses = 0
    for i = 1, 2600 do
        if i % 3 == 0 then shot("ch03win") end
        if procActive(SYM.gProcScr_TitleScreen) then break end
        if i % 24 == 0 and presses < 14 then press(K.A, 3); presses = presses + 1 end
        yield()
    end
    result("PASS", "ch03 grell death + ending recorded")
end

-- recordch03midmap: the Icewind Brute's DEATH + the on-map RBG-execution cutscene in motion (#23
-- item 1). Same park-adjacent + filmed-kill dance as recordch03win, but targets the Brute (0xb6)
-- and films the three EXECUTION beats (Marty's mercy / RBG's "Say cheese" shot / Wolfram's ore gag)
-- that the mid-map AFEV fires on its death -- a bounded A-cadence advances the beats and stops the
-- instant the guard flag EVFLAG_TMP(11) is set (the chapter keeps going, so there's no title to hit).
-- Fresh CH03BOOT New Game. Run: PT_HOST_CHAPTER=4 tools/playtest/run.sh recordch03midmap.
scenarios.recordch03midmap = function()
    if not bootToMap() then return result("FAIL", "never reached the ch03 map") end
    if not red(0xb6) then return result("FAIL", "Icewind Brute (pid 0xb6) not found in the red array") end
    local leader = blue(0x01)
    if not leader then return result("FAIL", "leader (0x01) not deployed") end
    emu:write16(leader.addr + 0x1E, 0x2D1F) -- Iron Axe in items[0]: guaranteed in-range kill weapon
    pokeAnimsOn()
    waitFor(function()
        return faction() == 0 and not menuOpen()
           and not procActive(SYM.ProcScr_StdEventEngine)
           and not procActive(SYM.ProcScr_BattleEventEngine)
    end, 900, true)
    for f = 1, 20 do if f % 3 == 0 then shot("ch03midmap") end yield() end -- settle on the map
    -- Bring the LEADER to the Brute (at its real central tile ~14,6) rather than dragging the Brute
    -- to the left-entrance spawn: the execution beats fire ON the kill tile, so killing centrally
    -- keeps the camera central and the on-map talk bubble on-screen (a left-edge kill anchors the
    -- bubble off the tilemap). Frail the Brute so the range-1 strike kills before it counters.
    local function parkBrute()
        local b = red(0xb6)
        if not b or isDead(b) then return false end
        pokeFrail(b); b = red(0xb6)
        local lgrid = mapUnitAt(leader.x, leader.y)
        -- Prefer a PASSABLE (walkable) adjacent tile so the leader stands on real mine FLOOR (the
        -- stone battle platform), exactly like actual play -- an impassable wall/pillar tile is a
        -- rough terrain and would film the leader on the rock platform instead (Nicolas 2026-07-11).
        for _, passableOnly in ipairs({ true, false }) do
            for _, d in ipairs({ { 1, 0 }, { -1, 0 }, { 0, 1 }, { 0, -1 } }) do
                local tx, ty = b.x + d[1], b.y + d[2]
                if tx >= 0 and tx <= 24 and ty >= 0 and ty <= 15 and mapUnitAt(tx, ty) == 0
                   and (not passableOnly or not IMPASSABLE_TERRAIN[terrainAt(tx, ty)]) then
                    setMapUnit(leader.x, leader.y, 0)
                    emu:write8(leader.addr + 0x10, tx); emu:write8(leader.addr + 0x11, ty)
                    setMapUnit(tx, ty, lgrid)
                    leader = blue(0x01)
                    log(string.format("leader parked at (%d,%d) terrain=%d (brute@%d,%d terrain=%d)",
                        tx, ty, terrainAt(tx, ty), b.x, b.y, terrainAt(b.x, b.y)))
                    return true
                end
            end
        end
        return false
    end
    -- Attack + film the battle anim (do NOT press once combat starts -- A skips an FE8 anim). The
    -- hit kills the frail'd Brute; film the death, then a LIGHT A-cadence clears the EXP screen
    -- without mashing into the execution beats that fire right after (EVFLAG_TMP(10) -> the AFEV).
    local function filmedAttack()
        leader = blue(0x01)
        if not cursorTo(leader.x, leader.y) then return end
        press(K.A); wait(15)
        local opened = false
        for _ = 1, 10 do
            if menuOpen() then opened = true break end
            press(K.A); if waitFor(menuOpen, 14) then opened = true break end
        end
        if not opened then press(K.B); press(K.B); return end
        press(K.A); wait(8); press(K.A); wait(8); press(K.A) -- Attack -> weapon -> target -> combat
        -- Film the anim to the death, then STOP -- do NOT clear the EXP screen here. The execution
        -- beats fire right after the death, so any EXP-mash would blow through them; the slow cadence
        -- below advances the EXP screen AND the beats one screen at a time.
        local deadAt = nil
        for i = 1, 900 do
            if i % 2 == 0 then shot("ch03midmap") end
            if not deadAt and (isDead(red(0xb6)) or eventFlag(10)) then deadAt = i end
            if deadAt and i > deadAt + 120 then break end          -- tail: the death collapse
            yield()
        end
    end
    for turn = 1, 3 do
        if isDead(red(0xb6)) or eventFlag(10) then break end
        if not parkBrute() then return result("FAIL", "no free tile adjacent to the leader for the Brute") end
        cursorTo(leader.x, leader.y)
        for f = 1, 30 do if f % 3 == 0 then shot("ch03midmap") end yield() end -- frame the standoff
        filmedAttack()
        if isDead(red(0xb6)) or eventFlag(10) then break end
        for f = 1, 40 do if f % 4 == 0 then shot("ch03midmap") end yield() end
        if runEnemyPhase() == "gameover" then return result("FAIL", "unexpected game over") end
    end
    if not (isDead(red(0xb6)) or eventFlag(10)) then
        return result("FAIL", "could not kill the Brute in 3 turns")
    end
    -- Film the EXP screen + the execution beats ONE PAGE AT A TIME: a hold long enough for the page
    -- to draw + linger, THEN one A. Enough steps to reach Wolfram's last line (EXP + Marty + Brute +
    -- RBG x3 + Wolfram x2 ~= 8 pages; extra steps film the map resuming, proof the chapter continues).
    -- Film the whole scene (EXP + 7 beats / 2 action boxes ~= 13 pages) ONE PAGE AT A TIME: a fixed
    -- 70-frame hold (each page draws + lingers, readable) then a ROBUST A (8-frame press -- a short
    -- press(A,3) under-registers at 240fps, so 13 pages fell short). Generous step count (22 > 13
    -- pages) covers a stray missed press + films the map resuming after the guard flag sets.
    press(K.A, 8); wait(40)                                     -- dismiss the EXP/level screen
    for _ = 1, 22 do
        for f = 1, 70 do if f % 3 == 0 then shot("ch03midmap") end yield() end  -- page draws + holds
        press(K.A, 8)                                                          -- advance one page (robust)
    end
    result("PASS", "ch03 Brute death + RBG-execution midmap recorded")
end

-- recordch02map: pan the cursor across the ch02 map (NW deploy + the 3 green chwinga -> the
-- chardalyn raiders E/SE), so the GIF shows the snowy layout + the green chwinga map sprites in
-- their idle bob. Frames tagged "map". Loads the ch02start checkpoint (turn 1, all units placed).
scenarios.recordch02map = function()
    wait(30)
    if not loadState("ch02start") then return result("FAIL", "no ch02start checkpoint (run.sh builds it)") end
    wait(60); pokeAnimsOn()
    -- a slow sweep across the 15x15 map; the map-sprite idle animation plays while we pan.
    local path = { { 2, 4 }, { 4, 4 }, { 6, 5 }, { 8, 6 }, { 10, 7 }, { 12, 7 }, { 13, 6 }, { 11, 8 }, { 8, 8 }, { 4, 5 }, { 3, 4 } }
    for _, p in ipairs(path) do
        cursorTo(p[1], p[2])
        for f = 1, 18 do if f % 3 == 0 then shot("map") end yield() end
    end
    result("PASS", "ch02 map pan recorded")
end

-- recordch02combat: a deployed cast member attacks a chardalyn raider on the ch02 map -- a battle
-- animation in motion for the demo reel. Frames tagged "combat". Loads the stable ch02start state.
scenarios.recordch02combat = function()
    wait(30)
    if not loadState("ch02start") then return result("FAIL", "no ch02start checkpoint (run.sh builds it)") end
    wait(60); pokeAnimsOn()
    local pid
    for _, p in ipairs({ 0x01, 0x02, 0x03, 0x04, 0x05, 0x06, 0x07, 0x08 }) do
        local u = blue(p)
        if u and not isDead(u) and unitAttackRange(u) then pid = p break end
    end
    if not pid then return result("FAIL", "no deployed attacker") end
    if not positionForShot(pid) then return result("FAIL", "couldn't reach a firing tile") end
    local u = blue(pid)
    if not captureAttack(u.addr, "combat") then return result("FAIL", "combat never animated") end
    result("PASS", "ch02 combat recorded")
end

-- recordch02ending: the closing cutscene -- rout the band (deterministic frail+teleport, as in
-- clear_ch02), then capture the Targos ending beats (fisher / Rootis / #58 narration box / RBG)
-- at viewable speed. Frames tagged "ending". One run off ch02start (no fragile mid-scene state).
scenarios.recordch02ending = function()
    wait(30)
    if not loadState("ch02start") then return result("FAIL", "no ch02start checkpoint (run.sh builds it)") end
    wait(60)
    pokeFastConfig()
    local start = chapter()
    for t = 1, 12 do
        if chapter() ~= start or procActive(SYM.gProcScr_TitleScreen) then break end
        waitFor(function() return faction() == 0 and not menuOpen() end, 6000, true)
        wait(60)
        for i = 0, 23 do
            local r = unitAt(SYM.gUnitArrayRed, i)
            if r and not isDead(r) then pokeFrail(r); pokeHarmless(r) end
        end
        for i = 0, 7 do
            if #liveEnemies() == 0 then break end
            local u = unitAt(SYM.gUnitArrayBlue, i)
            if u and not isDead(u) and (u.state & 0x2) == 0 then
                local mn, mx = unitAttackRange(u)
                if mn and teleportToFiringTile(u, mn, mx) then
                    u = blue(u.charId)
                    if u and moveUnit(u.x, u.y, u.x, u.y) then
                        chooseAttack(u.addr)
                        waitFor(function() return faction() == 0 and not menuOpen()
                            and not procActive(SYM.gProc_ekrBattle) end, 600)
                    end
                end
            end
        end
        if #liveEnemies() == 0 then break end
        if runEnemyPhase(CH02_PARK) == "gameover" then return result("FAIL", "party lost") end
    end
    if #liveEnemies() ~= 0 then return result("FAIL", "rout incomplete -- no ending to record") end
    endTurn()   -- fire the DefeatAll win -> the ending scene
    pokeNormalConfig()   -- readable text speed for the capture
    local fr, atTitle = 0, false
    while fr < 6000 do
        fr = fr + 1
        if fr % 4 == 0 then shot("ending") end
        if fr % 60 == 0 then press(K.A, 4) end
        if procActive(SYM.gProcScr_TitleScreen) then atTitle = true break end
        yield()
    end
    shot("ending")
    result("PASS", atTitle and "ch02 ending recorded (reached title)" or "ch02 ending recorded")
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
