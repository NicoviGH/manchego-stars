-- sight.lua -- what the bot SEES, read from the game itself (#510 step 9, PR D).
--
-- bot.lua decides from a `sight` table and re-creates nothing; this file builds that table
-- from the running ROM. Every answer is computed by FE8's own code, run as the game runs it --
-- never a rule written here (Nicolas, 2026-10-26: "we need not reinvent vanilla AI behavior,
-- it's all there"; ADR 0369).
--
-- HOW THE GAME'S CODE IS RUN. Sight.machine(cpu) is a sandbox: it saves the emulator's state,
-- points the CPU at a game function (args in r0-r3 and on the stack, IRQs masked, lr at a
-- two-byte `b .` it writes into scratch RAM), lets the emulator run frames until the CPU sits
-- in that loop, reads what the caller asks for, and loads the state back -- registers, RAM and
-- RNG exactly as they were. It never single-steps: a call long enough to cross the end of a
-- frame (ch01's danger zone) deadlocks mGBA's emu:step() inside its frame callback, so the
-- call runs as ordinary emulation, between frames. The forecast WINDOW cannot answer the enemy
-- phase: FE8 zeroes the weapon of a target outside its range (SetBattleUnitWeapon,
-- BattleInitTargetCanCounter), so it never shows an enemy's strike on a tile it is not beside.
--
-- ── Sight.new(api) -> sight (bot.lua's contract) ────────────────────────────────────────────
-- api: { mem = { u8, s8, u16, s16, u32 }, write8, write16, write32, SYM, cpu (Sight.machine's),
--        Board (board.lua's bound reader, Board.bind: itemRange(item), distance(ax, ay, bx, by)),
--        map = function() -> w, h, chapter = function() -> index,
--        turn = function() -> n, board = Board.read }
-- ONE sight per run. Its answers about the board are kept until refresh(), which the caller
-- calls whenever the board may have changed (after every action, at every phase); the chapter's
-- goal and Seize tile are read once.
--   refresh()                drop every board answer; recount the objective's turns left.
--   newPhase()               refresh(), and a fresh `cache` for the phase: an AI a turn event
--                            rewrote between phases is in no cache key.
--   danger(x, y)             gBmMapRange after GenerateDangerZoneRange(FALSE), fog and roofs as
--                            the game shows them: 0 when no enemy reaches (x, y), else its
--                            COVERAGE -- GenerateUnitCompleteAttackRange adds 1 for every tile
--                            an enemy could strike it from, so it is not an enemy count.
--   threat(e) -> function(x, y) -> coverage: GenerateDangerZoneRange itself, every other enemy
--                            marked US_UNDER_A_ROOF for the call -- the one state its loop skips
--                            a unit for and nothing else reads -- so it walks `e` alone while
--                            the others stay valid units: they block it on gBmMapUnit and a
--                            Magic Seal still seals (GenerateMagicSealMap). Fog: the game's.
--   reach(unit, friends)     tiles with gBmMapMovement < 120 after GenerateUnitMovementMap,
--                            less those another unit stands on (gBmMapUnit). Either faction.
--   range(unit)              { min, max } of the weapon FE8 has equipped (GetUnitEquippedWeapon,
--                            the first CanUnitUseWeapon accepts, which BU_ISLOT_AUTO strikes
--                            with), read as GetItemMinRange/GetItemMaxRange read it; nil = none.
--   canSeize(unit)           the game's CanUnitSeize (bmdifficulty.c), the Seize command's check.
--   attack(u, e, x, y, slot) our unit from (x, y) on enemy `e` where it stands, as the forecast
--                            window shows it (BattleGenerateSimulation +
--                            InitBattleForecastBattleStats): hit, dmg, crit, hits; `e`'s
--                            counter* (counterHit, counterDmg, counterCrit, counterHits) and
--                            `counters` (false, counter* 0, when it cannot answer) -- all for
--                            the logs. What it does is played (ADR 0377): the simulation run
--                            once per way its rolls can go, each BattleRoll1RN/2RN caught and
--                            forced (cpu.breakpoint): dealt / counterDist = { [HP lost] = p }
--                            for `e` / our unit, kill / die = the chance it kills `e` / ours,
--                            killsTarget = the plain simulation (every hit lands, nothing
--                            procs) leaves `e` at 0. nil when (x, y) is out of our range.
--   strike(u, e, x, y)       `e`'s own strike on `u` standing on (x, y), on its phase: the
--                            enemy phase's per-unit setup (cp_decide.c: AiUpdateNoMoveFlag, the
--                            combat weight table, AiInitDangerMap, AiClearDecision), then
--                            AiAttemptOffensiveAction(AiIsUnitEnemy) itself -- STAY, ballista
--                            and thief branches included -- with every other target hidden for
--                            the call, so it can only choose `u`. Its decision is simulated and
--                            played as attack()'s: takenHit, takenDmg, takenCrit, takenHits
--                            (the window's), takenSlot, takenTile, takenDist (what it takes off
--                            `u`), counterDist (what `u`'s counter takes off `e`). All 0 (slot/
--                            tile nil, takenDist nothing) when the AI does not strike `u` there.
--   batch(fn)                fn's reads in one save/load: one decision's worth of questions
--                            cost one state round trip, not one each.
--   enemyPhase(plan)         the enemy phase the AI would play against a planned board, in
--                            one batch. plan = { blues = { { unit, x, y, hp } }, gone =
--                            { [enemy id] = true } }: our units stand where the plan leaves
--                            them with its HP, the gone are off the map, the game builds its
--                            own turn order (BuildAiUnitList, SortAiUnitList), and each enemy
--                            in it the player can see makes its own decision (the setup
--                            strike() uses, every target open). A strike moves the enemy to
--                            its tile and takes its expected damage off the target before the
--                            next decides. plan.reds = { [enemy id] = hp } (optional): the HP
--                            the plan leaves an enemy. Where the target's counter may kill
--                            the striker (its played chance, `felled`), the rest of the phase
--                            is played both ways, the striker's tile freed in the second
--                            (ch02: a Brigand Marty killed let the next one in).
--                            -> { { enemy, target, taken* as strike(), counterDist, felled,
--                            strikerHp, targetHp } }: the likeliest
--                            outcome's strikes, with .outcomes = { { p, strikes } } (p sums
--                            to 1) for every way the phase went.
--   objective                { kind, tile, turnsLeft, boss } -- see objective(); boss = on a
--                            Defeat Boss map, the charId whose death quote raises
--                            EVFLAG_DEFEAT_BOSS (GetDefeatTalkEntry), read at the start.
--   field(goal)              dist[y][x] = the movement cost from `goal` to (x, y), FE8's
--                            GenerateExtendedMovementMap with fieldUnit()'s costs; nil =
--                            unreached.
--   fieldUnit()              the first deployed unit that can Seize, else the first deployed.
--   terrain(x, y)            gBmMapTerrain[y][x].
--   visible(x, y)            the player sees (x, y): no fog (chapterVisionRange 0) or gBmMapFog
--                            set there -- bmtarget.c's own test; a red unit in fog is no target.
--   unseen()                 every tile the fog hides now ({} without fog).
--   staves(u)                the staves `u` can heal with, { slot (0-based), amount }:
--                            CanUnitUseStaff, and GetUnitItemHealAmount > 0.
--   canTalk(u, t)            the Talk command's own pair check, CheckForCharacterEvents (what
--                            MakeTalkTargetList adds a neighbour by).
--   opens(u, terrain)        `u` holds what opens that terrain (TERRAIN_DOOR, TERRAIN_CHEST_FULL):
--                            GetUnitKeyItemSlotForTerrain, a key or a thief's lockpick.
--   opensDoor(u), holdsKey(u)  opens() for a door; for a door or a chest (what a keys claim
--                            hunts: an enemy carrying a key, or a thief's lockpick).
--   explorable()             the villages and chests still open now: { x, y, kind =
--                            "visit"|"chest" } per tile whose Visit or Chest command (read with
--                            the Seize tile) GetAvailableTileEventCommand still returns -- a
--                            visited, pillaged or opened tile's flag drops it -- and, for a
--                            village, whose Visit VisitCommandUsability still shows one of our
--                            units standing there (a razed one keeps its command). Read once per
--                            board. A tile whose event only opens later in the chapter is not
--                            in the start list, so it is never offered.
--   canExplore(u, x, y, kind) the unit menu's own check with `u` standing on (x, y) as the
--                            active unit: VisitCommandUsability (not a Phantom, not Silenced)
--                            or ChestCommandUsability (a key or lockpick, CanUnitUseChestKeyItem)
--                            returns MENU_ENABLED.
--   legal(a, u) -> why|nil   whether the game still offers act `a` (the bot's act table) to
--                            `u`, the unit's live record, moving to a.move: its movement map
--                            reaches the tile (reach), and the unit menu's own check passes with
--                            it standing there as the active unit -- the Attack target list of
--                            a weapon CanUnitUseWeaponNow allows (MakeTargetListForWeapon: the
--                            unit or the wall still standing), heals() for a staff, CanUnitUseItem
--                            for an item, and Talk/Door/Visit/Chest/Seize's *Usability with
--                            Talk's target in its list. nil = legal, else why not. A kept plan
--                            plays its next act on this word, not its own (Planner.surprise).
--   strikeWall(u, o, x, y)   `u`'s strike from (x, y) on the wall o = { x, y, hp }, as the
--                            Attack menu forecasts it (InitObstacleBattleUnit, then
--                            BattleGenerateSimulation): { dmg, hits }. A wall is always hit
--                            and never crit (ComputeBattleObstacleStats).
--   doors()                  the door tiles still closed: a tile whose command is Door
--                            (read with the Seize tile) and whose terrain is still a door.
--   heals(u, x, y, hurt)     what `u` could heal standing on (x, y): per staff in staves(u)
--                            that CanUnitUseItem allows there -- which builds vanilla's own heal
--                            target list -- { slot, amount = GetUnitItemHealAmount, targets =
--                            { unit index bytes } }. `hurt` (optional, units): allies read as
--                            one HP short, for a heal the planner means to follow a blow.
--   mend(u)                  an item that heals `u` itself (a Vulnerary): not a staff,
--                            GetUnitItemHealAmount > 0, CanUnitUseItem (its HP is short) --
--                            { slot, amount }, the first in the inventory; nil.
--   obstacles()              every obstacle the Attack command can strike, as
--                            TryAddTrapsToTargetList (bmtarget.c) lists them from the trap pool:
--                            a TRAP_OBSTACLE's damaged wall at its tile, or the tile below where
--                            two are stacked (InitMapObstacles traps the top one only), or its
--                            snag. { x, y, hp } -- hp = the trap's `extra`.
--   nextTurnEvent(turn)      the first later turn at which a turn event the game would fire is
--                            not already firing now (SearchAvailableEvent over the chapter's
--                            turnBasedEvents, the turn and phase set to each), or nil.
--   cache                    {} for ONE player phase (bot.lua keeps attacks and strikes there).
--   demands()                what the map asks of a team (M.demandsOf), at the prep screen:
--                            the board's red units and the chapter's tile commands (read once,
--                            with the Seize tile), fog from gPlaySt.chapterVisionRange.
--   answer(u, d) -> answered, strength: how `u` answers demand `d`, by the game's own checks.
--                            enemy: attack() on d.rep from r.max away (N, E, S, W, the first on
--                            the map), answered when it kills in one round and outlives the
--                            counter (M.answerOf); strength = its expected damage that round.
--                            chests/doors: GetUnitKeyItemSlotForTerrain finds a key or lockpick
--                            (ChestCommandUsability, DoorCommandUsability). fog: GetUnitFogViewRange
--                            sees past the chapter's range (a thief, a torch). sustain: a held
--                            staff CanUnitUseStaff accepts. village: it reaches the tile, from
--                            fieldUnit()'s tile, in no more turns than the fastest red unit
--                            from its own (GenerateExtendedMovementMap on each one's costs,
--                            turns = cost / UNIT_MOV rounded up).
-- Sight.seed(api, s)         InitRN(s): the game's own seeding, written into gRNSeeds.

local M = {}

M.calls = {}                 -- game calls made, by function address (the run's cost record)
M.FRAME_BUDGET = 600         -- frames one call may run; a full map's danger zone takes a few
M.MOVE_LIMIT = 120           -- include/bmmap.h: a movement-map cost at or above it is unreachable
M.UNREACHED = 0xFF           -- GenerateMovementMap fills its map with -1 before it floods
M.ISLOT_AUTO = -1            -- include/bmbattle.h BU_ISLOT_AUTO
M.TILE_COMMAND_SEIZE = 0x11  -- include/eventinfo.h
M.TILE_COMMAND_VISIT, M.TILE_COMMAND_DOOR, M.TILE_COMMAND_CHEST = 0x10, 0x12, 0x14
M.TERRAIN_DOOR, M.TERRAIN_CHEST_FULL = 0x1E, 0x21   -- include/constants/terrains.h
M.MENU_ENABLED = 1           -- include/uimenu.h
M.MENU_NOTSHOWN = 3
M.FACTION_MASK = 0xC0        -- include/bmunit.h: a unit index's faction bits (blue 0x00)
M.EVFLAG_DEFEAT_BOSS = 2     -- include/constants/event-flags.h; DefeatTalkEnt +04 flag
M.DEFEAT_TALK_FLAG = 0x04
M.TERRAIN_WALL_DAMAGED, M.TERRAIN_SNAG = 0x1B, 0x33
-- bmtrick.h: struct Trap { u8 xPos, yPos, type, extra; s8 data[4] } in sTrapPool, ended by
-- TRAP_NONE; TRAP_OBSTACLE = walls and snags.
M.TRAP_SIZE, M.TRAP_MAX, M.TRAP_OBSTACLE = 8, 64, 2
-- include/types.h goal window types, chapter data +0x8C (goalWindowDataType); +0x8D is
-- goalWindowEndTurnNumber, whose LAST turn the game's own goal window shows as End - 1
-- (player_interface.c), so the turns left on turn T are End - T.
M.GOALS = { [0] = "seize", [1] = "rout", [2] = "survive", [3] = "boss", [4] = "special" }
M.CHAPTER_GOAL, M.CHAPTER_GOAL_TURN = 0x8C, 0x8D
M.LAST_EVENT_TURN = 0xFF     -- eventinfo.c EvCheck02_TURN: turns are a byte (0xFF = open-ended)
M.PHASES = { 0x00, 0x40, 0x80 }   -- gPlaySt.faction: blue, green, red

-- struct BattleUnit (include/bmbattle.h) and BattleForecastProc (include/bksel.h) offsets.
local BU = { weapon = 0x48, attack = 0x5A, defense = 0x5C, hit = 0x64, crit = 0x6A,
             statusOut = 0x6F, hpInitial = 0x72, weaponBroke = 0x7D }
-- include/bmunit.h UNIT_STATUS_PETRIFY and UNIT_STATUS_13: the two statuses a blow sets that
-- end the battle like a death (BattleGenerateHit)
local STATUS_PETRIFY, STATUS_13 = 11, 13
-- struct BattleUnit is 0x80 bytes; its word at +0x10 holds xPos, yPos (the low half), maxHP
-- and curHP. struct BattleStats: +00 config and +02 range share its first word.
local BU_SIZE, BU_POSITION, POSITION_BITS = 0x80, 0x10, 0xFFFF
local PROC_HITS_A, PROC_HITS_B = 0x50, 0x51
M.SCRATCH_SIZE = 0x54        -- the forecast proc; EventInfo (0x1C) reuses the same bytes
-- struct Unit (include/bmunit.h): +00 pCharacterData, +0C state, +10/+11 xPos/yPos,
-- +40 u16 ai_config. Its state bits are board.lua's (Board.US_*).
local UNIT_STATE, UNIT_X, UNIT_Y, UNIT_MAXHP, UNIT_HP, UNIT_AI_CONFIG =
    0x0C, 0x10, 0x11, 0x12, 0x13, 0x40
-- struct AiState (include/cp_common.h): +7A dangerMapFilled, +7D combatWeightTableId; the
-- weight table comes from ai_config bits 3..7 (AI_UNIT_CONFIG_COMBATWEIGHT_*), written by
-- cp_decide.c's per-unit loop as one field assignment, which is copied here as it stands.
local AI_DANGER_FILLED, AI_WEIGHT_TABLE = 0x7A, 0x7D
local AI_WEIGHT_SHIFT, AI_WEIGHT_MASK = 3, 0x1F << 3
-- struct AiDecision: +00 actionId, +02/+03 xMove/yMove, +06 targetId, +07 itemSlot (0xFF = the
-- ballista, AiAttemptBallistaCombat's -1). AI_ACTION_COMBAT = 1.
local DEC_ACTION, DEC_X, DEC_Y, DEC_TARGET, DEC_SLOT = 0x00, 0x02, 0x03, 0x06, 0x07
local AI_ACTION_COMBAT, BALLISTA_SLOT = 1, 0xFF
-- struct ActionData (include/bmmind.h): +13 xOther, +14 yOther, +15 trapType (a wall's HP when
-- the Attack menu forecasts a strike on it).
local ACTION_X_OTHER, ACTION_Y_OTHER, ACTION_TRAP_TYPE = 0x13, 0x14, 0x15
-- struct EventInfo (include/eventinfo.h): +00 listScript, +04 script; 0x1C bytes.
local EVENT_INFO_SIZE, EVENT_SCRIPT = 0x1C, 0x04
-- struct PlaySt: +0D chapterVisionRange (0 = no fog), +0F faction, +10 u16 chapterTurnNumber.
local PLAY_VISION, PLAY_FACTION, PLAY_TURN = 0x0D, 0x0F, 0x10
-- UNIT_MOV (bmunit.h): struct Unit +04 pClassData, +1D s8 movBonus; struct ClassData +12 baseMov.
local UNIT_CLASS, UNIT_MOV_BONUS, CLASS_MOV = 0x04, 0x1D, 0x12

-- Sight.machine(cpu) -> sandbox(fn): cpu = { read(reg), write(reg, v), write16(addr, v),
-- write32(addr, v), save() -> state, load(state), frames(done, max) -> bool (run emulated frames
-- until done() or `max` have passed) }. sandbox(fn) runs fn(call, scratch) between a save and a
-- load and returns what fn returns; call(addr, args) runs one game function and returns its r0.
-- `scratch` is SCRATCH_SIZE free bytes for the caller. The CPU is put in System mode FIRST:
-- sp and lr are banked, so they are read and written in the mode the call runs in -- a frame
-- that ends inside an IRQ or SWI would otherwise hand out that mode's registers. Above the
-- call's stack sit `scratch` and the return loop; the load puts back whatever was there.
--
-- Sight.machine(cpu, true) is the same call KEPT (#510 step 9 PR E): what the game function
-- wrote stays -- a shop proc it started runs on the next frame -- and only the registers are put
-- back, so the game resumes where the frame left it. They are read and written in the mode the
-- frame ended in, System's sp and lr too (the call's own mode). pc is put back through a
-- measured write: mGBA's pc write refills the pipeline, so it reads one instruction past what
-- was written (measured 2026-10-27 at a frame boundary, the BIOS halt loop, ARM: +4).
local THUMB_B_SELF = 0xE7FE
-- A call LIST runs every call of it in one stretch of emulation: each call takes a whole frame
-- however little of it the function uses (the rest spins in the loop), and one enemy's
-- decision is six calls (#510 step 9: ~8,000 of ch02's 9,748 calls an attempt). The stub,
-- Thumb, ARMv4T (no blx): r4 walks a list of { addr|1, r0, r1, r2, r3, [sp] } words ended by
-- addr 0; it calls each through a `bx r5` veneer and branches to the return loop at the end.
-- r4-r6 are callee-saved (AAPCS), so every called function keeps them.
M.LIST_MAX = 4                -- calls in one list (the room above the stub)
local LIST_STUB = {
    0x6825,           -- +00 ldr r5, [r4, #0]
    0x2D00,           -- +02 cmp r5, #0
    0xD009,           -- +04 beq +1A            (the end)
    0x6860,           -- +06 ldr r0, [r4, #4]
    0x68A1,           -- +08 ldr r1, [r4, #8]
    0x68E2,           -- +0A ldr r2, [r4, #12]
    0x6923,           -- +0C ldr r3, [r4, #16]
    0x6966,           -- +0E ldr r6, [r4, #20]
    0x9600,           -- +10 str r6, [sp, #0]   (a fifth argument, where call() puts it)
    0x3418,           -- +12 add r4, #24
    0xF000, 0xF802,   -- +14 bl +1C             (lr = +18)
    0xE7F2,           -- +18 b +00
    0xE7EB,           -- +1A b loop             (loop = stub - 0x0C)
    0x4728,           -- +1C bx r5
}
local LIST_STUB_AT, LIST_AT, LIST_ENTRY = 0x0C, 0x30, 24   -- past the loop's +8 window
local SYSTEM_THUMB_NOIRQ = 0x1F | 0x20 | 0x80   -- CPSR mode System, T, I
local GPRS = { "r0", "r1", "r2", "r3", "r4", "r5", "r6", "r7", "r8", "r9", "r10", "r11", "r12",
               "sp", "lr" }
local function readRegisters(cpu)
    local regs = { cpsr = cpu.read("cpsr"), pc = cpu.read("pc") }
    for _, r in ipairs(GPRS) do regs[r] = cpu.read(r) end
    cpu.write("cpsr", (regs.cpsr & ~0xFF) | SYSTEM_THUMB_NOIRQ)
    regs.systemSp, regs.systemLr = cpu.read("sp"), cpu.read("lr")
    cpu.write("cpsr", regs.cpsr)
    return regs
end
local function writeRegisters(cpu, regs)
    cpu.write("cpsr", (regs.cpsr & ~0xFF) | SYSTEM_THUMB_NOIRQ)
    cpu.write("sp", regs.systemSp)
    cpu.write("lr", regs.systemLr)
    cpu.write("cpsr", regs.cpsr)
    for _, r in ipairs(GPRS) do cpu.write(r, regs[r]) end
    cpu.write("pc", regs.pc)
    local ahead = cpu.read("pc") - regs.pc
    if ahead ~= 0 then cpu.write("pc", regs.pc - ahead) end
    if cpu.read("pc") ~= regs.pc then
        error(string.format("sight: pc reads 0x%08X after it was put back at 0x%08X",
            cpu.read("pc"), regs.pc))
    end
end
function M.machine(cpu, keep)
    return function(fn)
        -- The load puts every register back; only cpsr is kept here. A kept call loads
        -- nothing, so it reads every register first.
        local state = keep and readRegisters(cpu) or cpu.save()
        local cpsr, top, scratch, loop
        local function returned()
            local pc = cpu.read("pc")
            return pc >= loop and pc <= loop + 8
        end
        local function call(addr, args)
            if type(addr) == "table" then
                -- a list: { { addr, args }... }, each args at most five -> the last call's r0
                local list = addr
                assert(#list >= 1 and #list <= M.LIST_MAX, "sight: a call list holds 1-4 calls")
                local stub, at = loop + LIST_STUB_AT, loop + LIST_AT
                for i, h in ipairs(LIST_STUB) do cpu.write16(stub + (i - 1) * 2, h) end
                for k, c in ipairs(list) do
                    M.calls[c[1]] = (M.calls[c[1]] or 0) + 1
                    local e = at + (k - 1) * LIST_ENTRY
                    assert(#c[2] <= 5, "sight: a listed call takes at most five arguments")
                    cpu.write32(e, c[1] | 1)
                    for i = 1, 5 do cpu.write32(e + i * 4, (c[2][i] or 0) & 0xFFFFFFFF) end
                end
                cpu.write32(at + #list * LIST_ENTRY, 0)
                cpu.write16(loop, THUMB_B_SELF)
                cpu.write("cpsr", (cpsr & ~0xFF) | SYSTEM_THUMB_NOIRQ)
                cpu.write("sp", top)
                cpu.write("r4", at)
                cpu.write("pc", stub)
                if not cpu.frames(returned, M.FRAME_BUDGET) then
                    error(string.format("sight: a call list (0x%08X first) did not return in %d "
                        .. "frames (pc 0x%08X)", list[1][1], M.FRAME_BUDGET, cpu.read("pc")))
                end
                return cpu.read("r0")
            end
            M.calls[addr] = (M.calls[addr] or 0) + 1
            for i, a in ipairs(args) do
                if i <= 4 then cpu.write("r" .. (i - 1), a & 0xFFFFFFFF)
                else cpu.write32(top + (i - 5) * 4, a & 0xFFFFFFFF) end
            end
            cpu.write16(loop, THUMB_B_SELF)
            cpu.write("cpsr", (cpsr & ~0xFF) | SYSTEM_THUMB_NOIRQ)
            cpu.write("sp", top)
            cpu.write("lr", loop | 1)
            cpu.write("pc", addr & ~1)
            if not cpu.frames(returned, M.FRAME_BUDGET) then
                error(string.format("sight: call 0x%08X did not return in %d frames (pc 0x%08X)",
                    addr, M.FRAME_BUDGET, cpu.read("pc")))
            end
            return cpu.read("r0")
        end
        -- Everything after the save is inside the pcall, the mode switch included: whatever
        -- raises, the state is loaded back.
        local ok, a, b = pcall(function()
            cpsr = cpu.read("cpsr")
            cpu.write("cpsr", (cpsr & ~0xFF) | SYSTEM_THUMB_NOIRQ)
            top = (cpu.read("sp") - 0x180) & ~7
            -- SCRATCH_SIZE fits between scratch and the loop; a call list's stub and list
            -- sit above the loop (LIST_STUB_AT, LIST_AT: LIST_MAX entries and the end)
            scratch, loop = top + 0x10, top + 0x80
            return fn(call, scratch)
        end)
        if keep then writeRegisters(cpu, state) else cpu.load(state) end
        if not ok then error(a, 0) end
        return a, b
    end
end

local function s16(v) return v >= 0x8000 and v - 0x10000 or v end
local function s32(v) return v >= 0x80000000 and v - 0x100000000 or v end

-- One side of a simulated exchange, as the forecast window shows it (bksel.c): hit, crit,
-- damage (the window's own sum: battleAttack less the other side's battleDefense, bksel.c
-- :233), how many blows (the proc's hit count for that side), and whether it is armed (a
-- weapon, or one that broke). Display only, for the logs: what an exchange DOES is `played`.
function M.side(mem, me, other, proc, hitsAt)
    local dmg = s16(mem.u16(me + BU.attack)) - s16(mem.u16(other + BU.defense))
    return { hit = s16(mem.u16(me + BU.hit)), crit = s16(mem.u16(me + BU.crit)),
             dmg = dmg > 0 and dmg or 0, hits = mem.s8(proc + hitsAt),
             armed = mem.u16(me + BU.weapon) ~= 0 or mem.s8(me + BU.weaponBroke) ~= 0 }
end

-- The chance one of the game's rolls passes (rng.c): Roll1RN draws one NextRN_100, Roll2RN
-- the floor of two draws' mean, and passes below the threshold; NextRN_100 is NextRN() * 100
-- / 0x10000. The game has no function for a roll's odds (ADR 0377, reason 1): this counts
-- them over every 16-bit NextRN, each taken as equally likely. `threshold` is the u16 the
-- BattleRoll functions take.
local DRAW, ROLLS = nil, { {}, {} }
function M.rollChance(numbers, threshold)
    if threshold >= 100 then return 1 end
    if threshold <= 0 then return 0 end
    local known = ROLLS[numbers][threshold]
    if known then return known end
    if not DRAW then
        DRAW = {}
        for k = 0, 99 do DRAW[k] = 0 end
        for v = 0, 0xFFFF do
            local k = v * 100 // 0x10000
            DRAW[k] = DRAW[k] + 1
        end
    end
    local n = 0
    if numbers == 1 then
        for a = 0, threshold - 1 do n = n + DRAW[a] end
        known = n / 0x10000
    else
        for a = 0, 99 do
            for b = 0, 99 do
                if (a + b) // 2 < threshold then n = n + DRAW[a] * DRAW[b] end
            end
        end
        known = n / 0x100000000
    end
    ROLLS[numbers][threshold] = known
    return known
end

-- An exchange's played outcomes (`leaves`: { p, dealt, back }, each the HP one side lost) as
-- two distributions { [hp lost] = probability }: the target's (dealt) and the actor's (back).
function M.exchangeOf(leaves)
    local dealt, back = {}, {}
    for _, l in ipairs(leaves) do
        dealt[l.dealt] = (dealt[l.dealt] or 0) + l.p
        back[l.back] = (back[l.back] or 0) + l.p
    end
    return dealt, back
end

-- Every way one exchange can go, as the game plays it (ADR 0377): `sim` ({ addr, args }:
-- BattleGenerateSimulation or its ballista twin) is run again and again, each roll it makes
-- caught at S.BattleRoll1RN/S.BattleRoll2RN's entry and its simResult (r1, which a simulation
-- returns in place of rolling) forced, depth first: pass where it can, then fail. A roll that
-- cannot go the other way (threshold 0, or 100 and up) is not split. `lost()` -> the HP the
-- target and the actor lost in the run just made. -> { { p, dealt, back } }. Inside a
-- sandbox; the breakpoints are set only for these calls (mGBA steps while one is set).
function M.played(cpu, call, sim, S, lost)
    local path, odds, at = {}, {}, 0
    local function catch(numbers)
        return function()
            at = at + 1
            if path[at] == nil then
                odds[at] = M.rollChance(numbers, cpu.read("r0") & 0xFFFF)
                path[at] = odds[at] > 0
            end
            cpu.write("r1", path[at] and 1 or 0)
        end
    end
    local holds = { cpu.breakpoint(S.BattleRoll1RN, catch(1)),
                    cpu.breakpoint(S.BattleRoll2RN, catch(2)) }
    local leaves = {}
    local ok, err = pcall(function()
        local split
        repeat
            at = 0
            call(sim[1], sim[2])
            local p = 1
            for i = 1, at do p = p * (path[i] and odds[i] or 1 - odds[i]) end
            local dealt, back = lost()
            leaves[#leaves + 1] = { p = p, dealt = dealt, back = back }
            -- the next outcome: the deepest roll forced to pass that can also fail
            split = at
            while split > 0 and not (path[split] and odds[split] < 1) do split = split - 1 end
            for i = split + 1, #path do path[i], odds[i] = nil, nil end
            if split > 0 then path[split] = false end
        until split == 0
    end)
    for _, hold in ipairs(holds) do cpu.unbreak(hold) end
    if not ok then error(err, 0) end
    return leaves
end

-- The HP several independent exchanges take off one unit, as a distribution { [damage] =
-- probability }, capped at `cap` (the unit's HP: past it, it is dead and the rest does not
-- matter). Each of `dists` is one exchange's { [damage] = probability }.
function M.damage(dists, cap)
    local dist = { [0] = 1 }
    for _, one in ipairs(dists) do
        local nxt = {}
        for d, p in pairs(dist) do
            for x, q in pairs(one) do
                local to = math.min(d + x, cap)
                if p * q > 0 then nxt[to] = (nxt[to] or 0) + p * q end
            end
        end
        dist = nxt
    end
    return dist
end

-- P(`dists` together take at least `hp`), and the expected damage (capped at `hp`).
function M.odds(dists, hp)
    local dead, mean = 0, 0
    for d, p in pairs(M.damage(dists, hp)) do
        if d >= hp then dead = dead + p end
        mean = mean + d * p
    end
    return dead, mean
end

-- The most and the least a distribution can take: its largest and smallest damage with any
-- chance.
function M.worst(dist)
    local w = 0
    for d, p in pairs(dist) do
        if p > 0 and d > w then w = d end
    end
    return w
end
function M.least(dist)
    local l = math.huge
    for d, p in pairs(dist) do
        if p > 0 and d < l then l = d end
    end
    return l
end

-- Our attack read off its simulation: `ours` is our side, with `ours.counter` the enemy's,
-- `ours.killsTarget` the game's own simulation (every hit lands, nothing procs) and
-- `ours.dealt`/`ours.back` its played distributions. kill / die: the chance the exchange
-- kills `e` (at eHp) / our unit (at uHp); sure: every way it goes kills `e`; expected: the
-- damage it is expected to deal; counterWorst: the most the counter can take off ours
-- (nothing when `e` cannot answer, or dies before it can). Pure, so test_sight.lua builds
-- every case.
function M.attackOf(ours, eHp, uHp)
    local c = ours.counter
    local counters = c.armed and c.hits > 0
    local kill, expected = M.odds({ ours.dealt }, eHp)
    return { hit = ours.hit, dmg = ours.dmg, crit = ours.crit, hits = ours.hits,
             counters = counters,
             counterHit = counters and c.hit or 0, counterDmg = counters and c.dmg or 0,
             counterCrit = counters and c.crit or 0, counterHits = counters and c.hits or 0,
             killsTarget = ours.killsTarget, dealt = ours.dealt, counterDist = ours.back,
             kill = kill, die = (M.odds({ ours.back }, uHp)), sure = M.least(ours.dealt) >= eHp,
             expected = expected, counterWorst = M.worst(ours.back) }
end

-- The enemy's strike read off its simulation, or none (nil) when its AI does not strike:
-- taken* as the window shows it, takenDist what it takes off our unit (takenWorst: the most),
-- counterDist what our counter takes off it.
function M.strikeOf(t)
    local dealt = t and t.dealt or { [0] = 1 }
    return { takenHit = t and t.armed and t.hit or 0, takenDmg = t and t.dmg or 0,
             takenCrit = t and t.crit or 0, takenHits = t and t.hits or 0,
             takenSlot = t and t.slot or nil, takenTile = t and t.tile or nil,
             takenDist = dealt, takenWorst = M.worst(dealt),
             counterDist = t and t.back or { [0] = 1 } }
end

-- Whether our attack ANSWERS its target, and how hard: the game's own simulation kills it
-- and no way the exchange can go kills our unit; strength = the damage it is expected to deal
-- (capped at the target's HP).
-- Pure.
function M.answerOf(a, hp)
    return a.killsTarget and a.counterWorst < hp, a.expected
end

-- What the map asks of a team, for Bot.team (#510 plan comment, "Party selection"). Pure, so
-- test_sight.lua builds every case. units = Board.read's; commands = {{ x, y, cmd }...} the
-- chapter's tile commands; fog = gPlaySt.chapterVisionRange. One demand per red class on the
-- field (need = how many stand there, rep = the first), one per village tile, one for chests
-- and one for doors when there are any, fog when the chapter has it, and sustain always.
function M.demandsOf(units, commands, fog)
    local out, byClass, once = {}, {}, {}
    for _, u in ipairs(units) do
        if u.faction == "red" and u.onField and u.classId then
            local d = byClass[u.classId]
            if not d then
                d = { id = "enemy:" .. u.classId, kind = "enemy", need = 0, rep = u }
                byClass[u.classId] = d
                out[#out + 1] = d
            end
            d.need = d.need + 1
        end
    end
    local kinds = { [M.TILE_COMMAND_CHEST] = "chests", [M.TILE_COMMAND_DOOR] = "doors" }
    for _, c in ipairs(commands) do
        if c.cmd == M.TILE_COMMAND_VISIT then
            out[#out + 1] = { id = string.format("village:%d,%d", c.x, c.y), kind = "village",
                              need = 1, tile = { x = c.x, y = c.y } }
        elseif kinds[c.cmd] and not once[c.cmd] then
            once[c.cmd] = true
            out[#out + 1] = { id = kinds[c.cmd], kind = kinds[c.cmd], need = 1 }
        end
    end
    if fog > 0 then out[#out + 1] = { id = "fog", kind = "fog", need = 1 } end
    out[#out + 1] = { id = "sustain", kind = "sustain", need = 1 }
    return out
end

-- Turns left on a Defense map on turn `turn`: End - turn (the goal window's last turn is
-- End - 1). Pure.
function M.turnsLeft(endTurn, turn) return endTurn - turn end

-- Of a turn-event scan, the first later turn whose available scripts include one not available
-- now. `now` is a set of scripts; `later` a list of {turn, scripts}. Pure.
--
-- What "later" is: the check runs at the START of a player phase, when only (turn, blue) has
-- fired. So `now` is (turn, blue) alone, and the scan goes (turn, green), (turn, red), then every
-- phase of each later turn -- M.eventOrder. An event due in this turn's enemy phase is ahead.
function M.eventOrder(turn)
    local out = {}
    for _, phase in ipairs(M.PHASES) do
        if phase ~= M.PHASES[1] then out[#out + 1] = { turn = turn, phase = phase } end
    end
    for t = turn + 1, M.LAST_EVENT_TURN do
        for _, phase in ipairs(M.PHASES) do out[#out + 1] = { turn = t, phase = phase } end
    end
    return out
end
function M.firstNewEvent(now, later)
    for _, at in ipairs(later) do
        for script in pairs(at.scripts) do
            if not now[script] then return at.turn end
        end
    end
    return nil
end

local function cell(mem, base, x, y) return mem.u32(mem.u32(base) + y * 4) + x end
local function grid(mem, base, x, y) return mem.u8(cell(mem, base, x, y)) end
local function readGrid(mem, base, w, h)
    local g = {}
    for y = 0, h - 1 do
        g[y] = {}
        for x = 0, w - 1 do g[y][x] = grid(mem, base, x, y) end
    end
    return g
end

-- Sight.batching(outer) -> sandbox, api: Sight.machine made re-entrant (the planner's cost,
-- #510 step 9) over `outer` (Sight.new's api), and an api whose writes it journals.
function M.batching(outer)
    -- The outermost sandbox() saves the state and loads it back at the end, as Sight.machine
    -- always did; a call made inside it (s.batch, or one read calling another) runs within
    -- that save, and every byte it wrote through `api` is put back when it returns, so one
    -- read cannot leak into the next. A game function's own writes (a movement map, the
    -- battle structs, the AI's decision) are not journaled: each read that depends on one
    -- makes it fresh first.
    local mem0 = outer.mem
    local journal
    local function journaled(read, write)
        return function(addr, v)
            if journal then journal[#journal + 1] = { addr, read(addr), write } end
            write(addr, v)
        end
    end
    local api = setmetatable({
        write8 = journaled(mem0.u8, outer.write8),
        write16 = journaled(mem0.u16, outer.write16),
        write32 = journaled(mem0.u32, outer.write32),
    }, { __index = outer })
    local machine = M.machine(api.cpu)
    local depth, outerCall, outerScratch = 0, nil, nil
    local function sandbox(fn)
        if depth == 0 then
            depth, journal = 1, {}
            local ok, a, b = pcall(machine, function(call, scratch)
                outerCall, outerScratch = call, scratch
                return fn(call, scratch)
            end)
            depth, journal, outerCall, outerScratch = 0, nil, nil, nil
            if not ok then error(a, 0) end
            return a, b
        end
        local mark = #journal
        depth = depth + 1
        local ok, a, b = pcall(fn, outerCall, outerScratch)
        depth = depth - 1
        for k = #journal, mark + 1, -1 do
            local e = journal[k]
            e[3](e[1], e[2])
            journal[k] = nil
        end
        if not ok then error(a, 0) end
        return a, b
    end
    return sandbox, api
end

function M.new(outer)
    local sandbox, api = M.batching(outer)
    local mem, S, Board = api.mem, api.SYM, api.Board
    local US_HIDDEN, US_UNDER_A_ROOF = Board.US_HIDDEN, Board.US_UNDER_A_ROOF
    local w, h = api.map()
    local s = { cache = {}, odds = M.odds }
    -- Every read `fn` makes, in ONE save and load (see sandbox above).
    function s.batch(fn) return sandbox(function() return fn() end) end
    local seen   -- this board's answers, dropped by refresh()

    -- The chapter's goal and tile commands, read once: its kind, the Defense map's end turn,
    -- every tile's location event, and the Seize tile (the one whose command is Seize, as
    -- bmcommanddbg.c finds it).
    local commands = {}
    local goal = sandbox(function(call)
        local data = call(S.GetROMChapterStruct, { api.chapter() })
        local g = { kind = M.GOALS[mem.u8(data + M.CHAPTER_GOAL)] or "special",
                    endTurn = mem.u8(data + M.CHAPTER_GOAL_TURN) }
        for y = 0, h - 1 do
            for x = 0, w - 1 do
                local cmd = call(S.GetAvailableTileEventCommand, { x, y })
                if cmd ~= 0 then commands[#commands + 1] = { x = x, y = y, cmd = cmd } end
                if g.kind == "seize" and cmd == M.TILE_COMMAND_SEIZE then
                    g.tile = { x = x, y = y }
                end
            end
        end
        return g
    end)
    s.objective = { kind = goal.kind, tile = goal.tile }
    -- On a Defeat Boss map, the boss is the unit whose death quote raises the goal's flag --
    -- how the game itself ends the chapter (GetDefeatTalkEntry, EVFLAG_DEFEAT_BOSS), not
    -- CA_BOSS, which a boss on a cloned generic row (ours ch03's grell) does not carry.
    if goal.kind == "boss" then
        s.objective.boss = sandbox(function(call)
            for _, u in ipairs(api.board().units) do
                if u.faction == "red" and u.onField then
                    local ent = call(S.GetDefeatTalkEntry, { u.charId })
                    if ent ~= 0 and mem.u16(ent + M.DEFEAT_TALK_FLAG) == M.EVFLAG_DEFEAT_BOSS then
                        return u.charId
                    end
                end
            end
            return nil
        end)
    end

    function s.demands()
        return M.demandsOf(api.board().units, commands, mem.u8(S.gPlaySt + PLAY_VISION))
    end

    -- Turns `unit` needs from `at` to `tile` on its own movement costs, nil = never.
    local function turnsTo(unit, tile, at)
        local cost = sandbox(function(call)
            local costs = call(S.GetUnitMovementCost, { unit.addr })
            call(S.GenerateExtendedMovementMap, { tile.x, tile.y, costs })
            return grid(mem, S.gBmMapMovement, at.x, at.y)
        end)
        if cost == M.UNREACHED then return nil end
        local mov = mem.s8(unit.addr + UNIT_MOV_BONUS) + mem.s8(mem.u32(unit.addr + UNIT_CLASS) + CLASS_MOV)
        return math.ceil(cost / mov)
    end
    local raced = {}   -- village id -> the fastest red unit's turns (false: none reaches)
    local SIDES = { { 0, -1 }, { 1, 0 }, { 0, 1 }, { -1, 0 } }

    function s.answer(u, d)
        if d.kind == "enemy" then
            local e, r = d.rep, s.range(u)
            if not r then return false, 0 end
            for _, o in ipairs(SIDES) do
                local x, y = e.x + o[1] * r.max, e.y + o[2] * r.max
                if x >= 0 and y >= 0 and x < w and y < h then
                    local a = s.attack(u, e, x, y)
                    if a then return M.answerOf(a, u.hp) end
                end
            end
            return false, 0
        elseif d.kind == "chests" or d.kind == "doors" then
            return s.opens(u, d.kind == "chests" and M.TERRAIN_CHEST_FULL or M.TERRAIN_DOOR), 0
        elseif d.kind == "fog" then
            return sandbox(function(call)
                return call(S.GetUnitFogViewRange, { u.addr })
            end) > mem.u8(S.gPlaySt + PLAY_VISION), 0
        elseif d.kind == "sustain" then
            return sandbox(function(call)
                for _, it in ipairs(u.items) do
                    if call(S.CanUnitUseStaff, { u.addr, it.id }) ~= 0 then return true end
                end
                return false
            end), 0
        elseif d.kind == "village" then
            if raced[d.id] == nil then
                local best = false
                for _, e in ipairs(api.board().units) do
                    if e.faction == "red" and e.onField then
                        local n = turnsTo(e, d.tile, e)
                        if n and (not best or n < best) then best = n end
                    end
                end
                raced[d.id] = best
            end
            local from = s.fieldUnit()
            local n = from and turnsTo(u, d.tile, from)
            return n ~= nil and (raced[d.id] == false or n <= raced[d.id]), 0
        end
        error("sight.lua: unknown demand kind " .. tostring(d.kind), 2)
    end

    -- A unit's own answers (its weapon's reach, Seize, staves, Vulnerary, keys) depend on the
    -- unit alone -- class, level, HP, status, items -- never on where anyone stands, so they
    -- outlive refresh(): keyed by those facts, a changed unit is simply a new key.
    local own = {}
    local function mine(kind, u, ask)
        local parts = { kind, u.id, u.classId or "-", u.level or "-", u.hp, u.status or "-" }
        for _, it in ipairs(u.items or {}) do parts[#parts + 1] = it.id .. "x" .. it.uses end
        local k = table.concat(parts, ":")
        local v = own[k]
        if v == nil then
            v = ask()
            if v == nil then v = false end
            own[k] = v
        end
        return v or nil
    end

    function s.refresh()
        seen = { threats = {}, fields = {} }
        s.objective.turnsLeft = goal.kind == "survive" and M.turnsLeft(goal.endTurn, api.turn())
            or nil
    end
    s.refresh()

    function s.newPhase()
        s.refresh()
        s.cache = {}
    end

    function s.danger(x, y)
        if not seen.danger then
            seen.danger = sandbox(function(call)
                call(S.GenerateDangerZoneRange, { 0 })
                return readGrid(mem, S.gBmMapRange, w, h)
            end)
        end
        return seen.danger[y] and seen.danger[y][x] or 0
    end

    function s.threat(e)
        if not seen.threats[e.id] then
            seen.threats[e.id] = sandbox(function(call)
                for _, o in ipairs(api.board().units) do
                    if o.faction == "red" and o.id ~= e.id then
                        local st = mem.u32(o.addr + UNIT_STATE)
                        api.write32(o.addr + UNIT_STATE, st | US_UNDER_A_ROOF)
                    end
                end
                call(S.GenerateDangerZoneRange, { 0 })
                return readGrid(mem, S.gBmMapRange, w, h)
            end)
        end
        local g = seen.threats[e.id]
        return function(x, y) return g[y] and g[y][x] or 0 end
    end

    function s.reach(u, friends)
        return sandbox(function(call)
            call(S.GenerateUnitMovementMap, { u.addr })
            local out = {}
            for y = 0, h - 1 do
                for x = 0, w - 1 do
                    local by = grid(mem, S.gBmMapUnit, x, y)
                    local own = x == u.x and y == u.y
                    if grid(mem, S.gBmMapMovement, x, y) < M.MOVE_LIMIT then
                        if own or by == 0 then
                            out[#out + 1] = { x = x, y = y }
                        elseif friends and (by & M.FACTION_MASK) == (u.id & M.FACTION_MASK) then
                            out[#out + 1] = { x = x, y = y, by = by }
                        end
                    end
                end
            end
            return out
        end)
    end

    function s.range(u)
        return mine("range", u, function() return M.range(api, u, sandbox) end)
    end

    function s.canSeize(u)
        return mine("seize", u, function() return M.canSeize(api, u, sandbox) end) or false
    end

    -- The HP a battle unit lost in the simulation just run. A blow that petrifies ends the
    -- battle as a death does (BattleGenerateHit), and a petrified unit is out of the fight, so
    -- the bot counts it as every HP lost: our pricing, not the game's.
    local function lost(bu)
        local initial = mem.s8(bu + BU.hpInitial)
        local status = mem.s8(bu + BU.statusOut)
        if status == STATUS_PETRIFY or status == STATUS_13 then return initial end
        return initial - mem.u8(bu + UNIT_HP)
    end

    -- One exchange as the forecast window reads it (`sim`, then InitBattleForecastBattleStats)
    -- and as it plays: the actor's side (M.side) with .counter the target's, .killsTarget the
    -- game's own simulation (every hit lands, nothing procs), and .dealt / .back its played
    -- distributions (M.exchangeOf). Inside a sandbox.
    -- The played outcomes, kept by what the game played them from (ADR 0377, reason 2: a
    -- MEASURED cost -- the Manchego Stars ch01 bot run took 7,266 simulations and 17.4 CPU s
    -- without it, 2,116 and 12.0 with it, against 827 and 10.5 before any were played): both
    -- battle units as the simulation set them up, every byte but where they
    -- stand, and gBattleStats' config and range. The chapter (BattleCheckSilencer reads it) is
    -- this sight's own.
    local playedBy = {}
    local function battleKey()
        local parts = { mem.u32(S.gBattleStats) }
        for _, bu in ipairs({ S.gBattleActor, S.gBattleTarget }) do
            for at = 0, BU_SIZE - 4, 4 do
                local word = mem.u32(bu + at)
                if at == BU_POSITION then word = word & ~POSITION_BITS end
                parts[#parts + 1] = word
            end
        end
        return table.concat(parts, ":")
    end

    local function exchange(call, proc, sim)
        call({ sim, { S.InitBattleForecastBattleStats, { proc } } })
        local side = M.side(mem, S.gBattleActor, S.gBattleTarget, proc, PROC_HITS_A)
        side.counter = M.side(mem, S.gBattleTarget, S.gBattleActor, proc, PROC_HITS_B)
        side.killsTarget = mem.u8(S.gBattleTarget + UNIT_HP) == 0
        local key = battleKey()
        local known = playedBy[key]
        if not known then
            known = { M.exchangeOf(M.played(api.cpu, call, sim, S, function()
                return lost(S.gBattleTarget), lost(S.gBattleActor)
            end)) }
            playedBy[key] = known
        end
        side.dealt, side.back = known[1], known[2]
        return side
    end

    function s.attack(u, e, x, y, slot)
        local r = s.range(u)
        local d = Board.distance(x, y, e.x, e.y)
        if not (r and d >= r.min and d <= r.max) then return nil end
        local ours = sandbox(function(call, proc)
            return exchange(call, proc,
                { S.BattleGenerateSimulation, { u.addr, e.addr, x, y, slot or M.ISLOT_AUTO } })
        end)
        return M.attackOf(ours, e.hp, u.hp)
    end

    -- `u`'s strike from (x, y) on the wall `o` ({ x, y, hp }), as the Attack menu forecasts
    -- it (AttackMapSelect_SwitchIn: the wall's place and HP in gActionData, then
    -- InitObstacleBattleUnit and BattleGenerateSimulation with no target unit) -> what the
    -- strike takes off the wall in the game's own simulation. Kept by the unit's facts and the
    -- wall: the blow reads the attacker's might against the wall's class.
    function s.strikeWall(u, o, x, y)
        return mine("wall@" .. o.x .. "," .. o.y, u, function() return sandbox(function(call, proc)
            api.write8(S.gActionData + ACTION_X_OTHER, o.x)
            api.write8(S.gActionData + ACTION_Y_OTHER, o.y)
            api.write8(S.gActionData + ACTION_TRAP_TYPE, o.hp)
            call(S.InitObstacleBattleUnit, {})
            call(S.BattleGenerateSimulation, { u.addr, 0, x, y, M.ISLOT_AUTO })
            return { dealt = lost(S.gBattleTarget) }
        end) end)
    end

    -- Moves `u` onto (x, y): its struct and gBmMapUnit, so movement and blocking see it there.
    local function standOn(u, x, y)
        if mem.u8(cell(mem, S.gBmMapUnit, u.x, u.y)) == u.id then
            api.write8(cell(mem, S.gBmMapUnit, u.x, u.y), 0)
        end
        api.write8(cell(mem, S.gBmMapUnit, x, y), u.id)
        api.write8(u.addr + UNIT_X, x)
        api.write8(u.addr + UNIT_Y, y)
    end

    -- Hides every other unit the AI could choose, so its own routine can only pick `u`. Hidden
    -- units keep their gBmMapUnit entries: they still block as they do.
    local function onlyTarget(u)
        for _, o in ipairs(api.board().units) do
            if o.faction ~= "red" and o.id ~= u.id and o.onField then
                api.write32(o.addr + UNIT_STATE, mem.u32(o.addr + UNIT_STATE) | US_HIDDEN)
            end
        end
    end

    -- Enemy `e`'s own offensive decision on the board as it stands, inside a sandbox:
    -- cp_decide.c's per-unit setup, in its order, with every player unit still visible: the
    -- AI's danger map (AiFillDangerMap) is their threat, and its tile choice reads it. Left
    -- out: RefreshEntityBmMaps/RenderBmMap/RefreshUnitSprites (they would rebuild gBmMapUnit
    -- from the structs, which is already what it holds, and draw) and gAiState.unk7C = 0 (read
    -- only by cp_staff.c, the staff AI). `before` runs just ahead of the decision (strike()
    -- narrows the targets there). -> the struck unit's id and the strike as the forecast
    -- reads it (M.side, with slot and tile), or nil when the AI does not attack.
    local function aiDecide(call, proc, e, before)
        api.write32(S.gActiveUnit, e.addr)
        api.write8(S.gActiveUnitId, e.id)
        -- written before AiUpdateNoMoveFlag, which touches only gAiState.flags, so the calls
        -- run as one list (cp_decide.c's order kept)
        api.write8(S.gAiState + AI_WEIGHT_TABLE,
            (mem.u16(e.addr + UNIT_AI_CONFIG) & AI_WEIGHT_MASK) >> AI_WEIGHT_SHIFT)
        api.write8(S.gAiState + AI_DANGER_FILLED, 0)
        local decide = { { S.AiClearDecision, {} },
                         { S.AiAttemptOffensiveAction, { S.AiIsUnitEnemy | 1 } } }
        local setup = { { S.AiUpdateNoMoveFlag, { e.addr } }, { S.AiInitDangerMap, {} } }
        if before then
            call(setup)
            before()
            call(decide)
        else
            call({ setup[1], setup[2], decide[1], decide[2] })
        end
        local D = S.gAiDecision
        if mem.u8(D + DEC_ACTION) ~= AI_ACTION_COMBAT then return nil end
        local target = mem.u8(D + DEC_TARGET)
        local addr = mem.u32(S.gUnitLookup + target * 4)
        local sx, sy, slot = mem.u8(D + DEC_X), mem.u8(D + DEC_Y), mem.u8(D + DEC_SLOT)
        local sim = slot == BALLISTA_SLOT
            and { S.BattleGenerateBallistaSimulation, { e.addr, addr, sx, sy } }
            or { S.BattleGenerateSimulation, { e.addr, addr, sx, sy, slot } }
        local side = exchange(call, proc, sim)
        side.slot, side.tile = slot, { x = sx, y = sy }
        return target, side
    end

    function s.strike(u, e, x, y)
        local t = sandbox(function(call, proc)
            standOn(u, x, y)
            -- `u` is made the one target only after the danger map: AiAttemptOffensiveAction
            -- skips hidden units.
            local target, side = aiDecide(call, proc, e, function() onlyTarget(u) end)
            if target ~= u.id then return nil end
            return side
        end)
        return M.strikeOf(t)
    end

    function s.enemyPhase(plan)
        return sandbox(function(call, proc)
            local byId = {}
            for _, o in ipairs(api.board().units) do byId[o.id] = o end
            for _, b in ipairs(plan.blues) do
                standOn(b.unit, b.x, b.y)
                api.write8(b.unit.addr + UNIT_HP, b.hp)
            end
            for id, hp in pairs(plan.reds or {}) do
                if byId[id] then api.write8(byId[id].addr + UNIT_HP, hp) end
            end
            local function remove(e, x, y)
                if mem.u8(cell(mem, S.gBmMapUnit, x, y)) == e.id then
                    api.write8(cell(mem, S.gBmMapUnit, x, y), 0)
                end
                api.write32(e.addr + UNIT_STATE, mem.u32(e.addr + UNIT_STATE) | US_HIDDEN)
            end
            for id in pairs(plan.gone or {}) do
                if byId[id] then remove(byId[id], byId[id].x, byId[id].y) end
            end
            -- the game's own turn order, built as on its phase (cp_order.c)
            api.write8(S.gPlaySt + PLAY_FACTION, M.PHASES[3])
            local n = call(S.BuildAiUnitList, {})
            if n > 0 then call(S.SortAiUnitList, { n }) end
            local order = {}
            for i = 0, n - 1 do order[#order + 1] = mem.u8(S.gAiState + i) end
            -- the phase from order[i] on, after `done`'s strikes -> its outcomes. A striker
            -- the counter may kill splits it: the enemies after it decide once with it
            -- standing and once with its tile free (each in a nested sandbox, so neither
            -- sees the other's board), the second as likely as its played counter kills it.
            local function play(i, done)
                for k = i, #order do
                    local id = order[k]
                    local e = byId[id]
                    if e and not (plan.gone or {})[id] and s.visible(e.x, e.y) then
                        local target, side = aiDecide(call, proc, e)
                        if target then
                            local t = M.strikeOf(side)
                            t.enemy, t.target = id, target
                            local addr = mem.u32(S.gUnitLookup + target * 4)
                            t.strikerHp, t.targetHp = mem.u8(e.addr + UNIT_HP), mem.u8(addr + UNIT_HP)
                            t.felled = (M.odds({ t.counterDist }, t.strikerHp))
                            local now = {}
                            for x = 1, #done do now[x] = done[x] end
                            now[#now + 1] = t
                            done = now
                            standOn(e, side.tile.x, side.tile.y)
                            local _, mean = M.odds({ t.takenDist }, t.targetHp)
                            api.write8(addr + UNIT_HP, t.targetHp - math.floor(mean + 0.5))
                            local q = t.felled
                            if q > 0 then
                                local out = {}
                                local stood = sandbox(function() return play(k + 1, done) end)
                                local fell = sandbox(function()
                                    remove(e, side.tile.x, side.tile.y)
                                    return play(k + 1, done)
                                end)
                                for _, o in ipairs(stood) do
                                    out[#out + 1] = { p = o.p * (1 - q), strikes = o.strikes }
                                end
                                for _, o in ipairs(fell) do
                                    out[#out + 1] = { p = o.p * q, strikes = o.strikes }
                                end
                                return out
                            end
                        end
                    end
                end
                return { { p = 1, strikes = done } }
            end
            local outcomes = play(1, {})
            -- the list is the likeliest outcome's strikes; every outcome rides on it
            local top = outcomes[1]
            for _, o in ipairs(outcomes) do
                if o.p > top.p then top = o end
            end
            local out = {}
            for x, t in ipairs(top.strikes) do out[x] = t end
            out.outcomes = outcomes
            return out
        end)
    end

    function s.terrain(x, y) return grid(mem, S.gBmMapTerrain, x, y) end
    function s.visible(x, y)
        return mem.u8(S.gPlaySt + PLAY_VISION) == 0 or grid(mem, S.gBmMapFog, x, y) ~= 0
    end
    function s.unseen()
        local out = {}
        if mem.u8(S.gPlaySt + PLAY_VISION) == 0 then return out end
        for y = 0, h - 1 do
            for x = 0, w - 1 do
                if grid(mem, S.gBmMapFog, x, y) == 0 then out[#out + 1] = { x = x, y = y } end
            end
        end
        return out
    end

    local function itemOf(it) return it.id | (it.uses << 8) end

    function s.opens(u, terrain)
        return mine("opens" .. terrain, u, function() return sandbox(function(call)
            return s32(call(S.GetUnitKeyItemSlotForTerrain, { u.addr, terrain })) >= 0
        end) end) or false
    end

    function s.opensDoor(u) return s.opens(u, M.TERRAIN_DOOR) end
    function s.holdsKey(u)
        return s.opens(u, M.TERRAIN_DOOR) or s.opens(u, M.TERRAIN_CHEST_FULL)
    end

    function s.canTalk(u, t)
        return sandbox(function(call)
            return call(S.CheckForCharacterEvents, { u.charId, t.charId }) & 0xFF ~= 0
        end)
    end

    -- Inside a sandbox: `u` stands on (x, y) as the active unit, not yet acted, as the unit
    -- menu finds it after a move.
    local function asActive(u, x, y)
        standOn(u, x, y)
        api.write32(u.addr + UNIT_STATE, mem.u32(u.addr + UNIT_STATE) & ~Board.US_HAS_MOVED)
        api.write32(S.gActiveUnit, u.addr)
        api.write8(S.gActiveUnitId, u.id)
    end

    -- A razed village keeps its Visit command (GetAvailableTileEventCommand), but the Visit
    -- menu is shown to no one there (VisitCommandUsability reads the tile): ch02's (12,3) on
    -- turn 8. Silence greys it out and leaves it shown, so it stays open.
    local function visitShown(x, y)
        for _, u in ipairs(api.board().units) do
            if u.faction == "blue" and u.onField and sandbox(function(call)
                asActive(u, x, y)
                return call(S.VisitCommandUsability, { 0, 0 }) ~= M.MENU_NOTSHOWN
            end) then return true end
        end
        return false
    end

    function s.explorable()
        if not seen.explorable then
            seen.explorable = sandbox(function(call)
                local out = {}
                for _, c in ipairs(commands) do
                    local kind = (c.cmd == M.TILE_COMMAND_VISIT and "visit")
                        or (c.cmd == M.TILE_COMMAND_CHEST and "chest")
                    if kind and call(S.GetAvailableTileEventCommand, { c.x, c.y }) == c.cmd
                        and (kind ~= "visit" or visitShown(c.x, c.y)) then
                        out[#out + 1] = { x = c.x, y = c.y, kind = kind }
                    end
                end
                return out
            end)
        end
        return seen.explorable
    end

    -- Usability reads the unit and the tile it stands on, never where anyone else is, and is
    -- only asked of a tile explorable() still offers: kept by the unit's facts and the tile.
    function s.canExplore(u, x, y, kind)
        return mine(kind .. "@" .. x .. "," .. y, u, function() return sandbox(function(call)
            asActive(u, x, y)
            local check = kind == "visit" and S.VisitCommandUsability or S.ChestCommandUsability
            return call(check, { 0, 0 }) == M.MENU_ENABLED
        end) end) or false
    end

    -- the unit menu's own check for each act it has one for (bmmenu.c)
    local MENU_CHECK = { talk = "TalkCommandUsability", door = "DoorCommandUsability",
                         visit = "VisitCommandUsability", chest = "ChestCommandUsability",
                         seize = "UnitActionMenu_CanSeize" }

    -- whether the last target list built holds unit `id`, or the wall at `at` (uid 0)
    local function listed(call, id, at)
        for k = 0, call(S.GetSelectTargetCount, {}) - 1 do
            local t = call(S.GetTarget, { k })
            if at then
                if mem.u8(t + 2) == 0 and mem.u8(t) == at.x and mem.u8(t + 1) == at.y then return true end
            elseif mem.u8(t + 2) == id then
                return true
            end
        end
        return false
    end

    function s.legal(a, u)
        local x, y = a.move.x, a.move.y
        local reached = false
        for _, t in ipairs(s.reach(u)) do
            if t.x == x and t.y == y then reached = true end
        end
        if not reached then return "the next move is out of reach" end
        if a.act == "staff" then
            for _, st in ipairs(s.heals(u, x, y)) do
                if st.slot == a.slot then
                    for _, id in ipairs(st.targets) do
                        if id == a.targetId then return nil end
                    end
                end
            end
            return "the game offers no such heal"
        end
        local ok = sandbox(function(call)
            asActive(u, x, y)
            if a.act == "attack" then
                for _, it in ipairs(u.items) do
                    if call(S.CanUnitUseWeaponNow, { u.addr, itemOf(it) }) ~= 0 then
                        call(S.MakeTargetListForWeapon, { u.addr, itemOf(it) })
                        if listed(call, a.targetId, a.obstacle) then return true end
                    end
                end
                return false
            elseif a.act == "item" then
                local it = u.items[a.slot + 1]
                return it ~= nil and call(S.CanUnitUseItem, { u.addr, itemOf(it) }) ~= 0
            elseif MENU_CHECK[a.act] then
                if call(S[MENU_CHECK[a.act]], { 0, 0 }) ~= M.MENU_ENABLED then return false end
                return a.act ~= "talk" or listed(call, a.targetId)
            end
            return true
        end)
        if ok then return nil end
        return "the game offers no " .. (a.obstacle and "strike on that wall" or a.act)
    end

    function s.doors()
        local out = {}
        for _, c in ipairs(commands) do
            if c.cmd == M.TILE_COMMAND_DOOR and s.terrain(c.x, c.y) == M.TERRAIN_DOOR then
                out[#out + 1] = { x = c.x, y = c.y }
            end
        end
        return out
    end

    function s.staves(u)
        return mine("staves", u, function()
            return sandbox(function(call)
                local out = {}
                for i, it in ipairs(u.items) do
                    if call(S.CanUnitUseStaff, { u.addr, itemOf(it) }) ~= 0
                        and call(S.GetUnitItemHealAmount, { u.addr, itemOf(it) }) > 0 then
                        out[#out + 1] = { slot = i - 1,
                            amount = call(S.GetUnitItemHealAmount, { u.addr, itemOf(it) }) }
                    end
                end
                return out
            end)
        end)
    end

    function s.heals(u, x, y, hurt)
        local staves = s.staves(u)
        if #staves == 0 then return {} end
        return sandbox(function(call)
            standOn(u, x, y)
            -- a planned heal: these allies read as wounded, so the game's list offers them
            for _, o in ipairs(hurt or {}) do
                if mem.u8(o.addr + UNIT_HP) >= mem.u8(o.addr + UNIT_MAXHP) then
                    api.write8(o.addr + UNIT_HP, mem.u8(o.addr + UNIT_MAXHP) - 1)
                end
            end
            local out = {}
            for _, st in ipairs(staves) do
                local slot = st.slot
                local item = itemOf(u.items[slot + 1])
                if call(S.CanUnitUseItem, { u.addr, item }) ~= 0 then
                    local targets = {}
                    for k = 0, call(S.GetSelectTargetCount, {}) - 1 do
                        targets[#targets + 1] = mem.u8(call(S.GetTarget, { k }) + 2)
                    end
                    out[#out + 1] = { slot = slot, targets = targets,
                                      amount = call(S.GetUnitItemHealAmount, { u.addr, item }) }
                end
            end
            return out
        end)
    end

    function s.mend(u)
        return mine("mend", u, function() return sandbox(function(call)
            for i, it in ipairs(u.items) do
                local amount = call(S.GetUnitItemHealAmount, { u.addr, itemOf(it) })
                if amount > 0 and call(S.CanUnitUseStaff, { u.addr, itemOf(it) }) == 0
                    and call(S.CanUnitUseItem, { u.addr, itemOf(it) }) ~= 0 then
                    return { slot = i - 1, amount = amount }
                end
            end
            return nil
        end) end)
    end

    function s.obstacles()
        if not seen.obstacles then
            local out = {}
            for i = 0, M.TRAP_MAX - 1 do
                local t = S.sTrapPool + i * M.TRAP_SIZE
                local kind = mem.u8(t + 2)
                if kind == 0 then break end
                if kind == M.TRAP_OBSTACLE then
                    local x, y, hp = mem.u8(t), mem.u8(t + 1), mem.u8(t + 3)
                    local here = s.terrain(x, y)
                    if here == M.TERRAIN_WALL_DAMAGED or here == M.TERRAIN_SNAG then
                        out[#out + 1] = { x = x, y = y, hp = hp }
                    end
                    if y + 1 < h and s.terrain(x, y + 1) == M.TERRAIN_WALL_DAMAGED then
                        out[#out + 1] = { x = x, y = y + 1, hp = hp }
                    end
                end
            end
            seen.obstacles = out
        end
        return seen.obstacles
    end

    function s.fieldUnit()
        local first
        for _, u in ipairs(api.board().units) do
            if u.faction == "blue" and u.onField then
                if s.canSeize(u) then return u end
                first = first or u
            end
        end
        return first
    end

    -- FE8's own march distance: GenerateExtendedMovementMap from the goal, out to
    -- MAP_MOVEMENT_EXTENDED -- the map its AI heads for a far target over (cp_0803E2F4.c).
    -- Units do not block it, as they do not block the AI's. A field is a march heading; each
    -- unit's real reach is reach()'s.
    function s.field(goalTile)
        local k = goalTile.x .. "," .. goalTile.y
        if seen.fields[k] == nil then
            local unit = s.fieldUnit()
            seen.fields[k] = unit and sandbox(function(call)
                local costs = call(S.GetUnitMovementCost, { unit.addr })
                call(S.GenerateExtendedMovementMap, { goalTile.x, goalTile.y, costs })
                local dist = {}
                for y = 0, h - 1 do
                    dist[y] = {}
                    for x = 0, w - 1 do
                        local v = grid(mem, S.gBmMapMovement, x, y)
                        if v ~= M.UNREACHED then dist[y][x] = v end
                    end
                end
                return dist
            end) or false
        end
        return seen.fields[k] or nil
    end

    -- The game's turn-event check (eventinfo.c: the phase-change hook searches turnBasedEvents
    -- with SearchAvailableEvent), asked at each later turn and phase (M.eventOrder). A script
    -- already available now (a repeating event) is no change; the first turn offering a new one
    -- is. Cost: a frame or more per call, ~765 for a full scan to turn 255 -- paid only when a
    -- board repeats, against a chapter's tens of thousands.
    function s.nextTurnEvent(turn)
        return sandbox(function(call, info)
            local events = call(S.GetChapterEventDataPointer, { api.chapter() })
            local list = mem.u32(events)
            local function scriptsAt(t, phase)
                local out = {}
                api.write16(S.gPlaySt + PLAY_TURN, t)
                api.write8(S.gPlaySt + PLAY_FACTION, phase)
                for o = 0, EVENT_INFO_SIZE - 4, 4 do api.write32(info + o, 0) end
                api.write32(info, list)
                local found = call(S.SearchAvailableEvent, { info })
                while found ~= 0 do
                    out[mem.u32(info + EVENT_SCRIPT)] = true
                    found = call(S.SearchNextAvailableEvent, { info })
                end
                return out
            end
            local now = scriptsAt(turn, M.PHASES[1])
            for _, at in ipairs(M.eventOrder(turn)) do
                local found = M.firstNewEvent(now, { { turn = at.turn,
                                                       scripts = scriptsAt(at.turn, at.phase) } })
                if found then return found end
            end
            return nil
        end)
    end

    return s
end

-- A unit's attack reach without a whole sight (harness.lua's unitAttackRange): the weapon FE8
-- has equipped (GetUnitEquippedWeapon) and its range, { min, max } or nil. `sandbox` is
-- optional (a sight passes its own).
function M.range(api, u, sandbox)
    local S = api.SYM
    local item = (sandbox or M.machine(api.cpu))(function(call)
        return call(S.GetUnitEquippedWeapon, { u.addr })
    end)
    local mn, mx = api.Board.itemRange(item)
    return mn and { min = mn, max = mx } or nil
end

-- The game's CanUnitSeize for `u` without a whole sight (harness.lua's clear loop).
function M.canSeize(api, u, sandbox)
    return (sandbox or M.machine(api.cpu))(function(call)
        return call(api.SYM.CanUnitSeize, { u.addr }) ~= 0
    end)
end

-- InitRN(seed) run in the sandbox, its three seeds then written into the live game: the run's
-- whole RNG stream is the game's own function of `seed`.
function M.seed(api, seed)
    local S = api.SYM
    local words = M.machine(api.cpu)(function(call)
        call(S.InitRN, { seed })
        return { api.mem.u16(S.gRNSeeds), api.mem.u16(S.gRNSeeds + 2), api.mem.u16(S.gRNSeeds + 4) }
    end)
    for i, v in ipairs(words) do api.write16(S.gRNSeeds + (i - 1) * 2, v) end
    return words
end

return M
