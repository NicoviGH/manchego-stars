-- sight.lua -- what the bot SEES, read from the game itself (#510 step 9, PR D).
--
-- bot.lua decides from a `sight` table and re-creates nothing; this file builds that table
-- from the running ROM. Every answer is computed by FE8's own code, run as the game runs it --
-- never a rule written here (Nicolas, 2026-10-26: "we need not reinvent vanilla AI behavior,
-- it's all there"; ADR 0369).
--
-- HOW THE GAME'S CODE IS RUN. Sight.machine(cpu) is a sandbox: it saves the emulator's state,
-- points the CPU at a game function (args in r0-r3 and on the stack, IRQs masked, lr at a
-- return loop it writes into scratch RAM, which halts in the BIOS: ADR 0380), lets the emulator
-- run frames until the call is back in that loop, reads what the caller asks for, and loads the
-- state back -- registers, RAM and RNG exactly as they were. It never single-steps: a call
-- long enough to cross the end of a frame (ch01's danger zone) deadlocks mGBA's emu:step()
-- inside its frame callback, so the call runs as ordinary emulation, between frames. The
-- forecast WINDOW cannot answer the enemy phase: FE8 zeroes the weapon of a target outside its
-- range (SetBattleUnitWeapon, BattleInitTargetCanCounter), so it never shows an enemy's strike
-- on a tile it is not beside.
--
-- WHEN A JUDGED PHASE DISAGREES WITH THE BOARD ONE ACT LATER, SUSPECT THIS FILE BEFORE THE
-- PLANNER. Nested sandboxes undo only api.write*; a game call that writes a unit struct (an
-- equip reorders the bag) needs api.keep16 first, or one judged plan leaks into the next (#554:
-- found in one instrumented run that logged every enemy decision and the target's bag). The
-- AI's own decision is one: it advances the unit's scripts (M.keepAi, #510). The map refresh
-- is another: it rewrites each red's fog bits, and the unit, hidden and fog maps, for where
-- our units stand (M.refresh, M.keepMaps, #510, #681).
-- And a ballista's rider that decides to strike with its own weapon steps off it (M.keepRide).
-- PT_LEAKGUARD=1 (run.sh) logs every word of a unit struct a nested sandbox leaves changed,
-- puts it back and plays on; the run fails at its end, listing them all (M.leaks; botrun's
-- `leaks`): run one after changing what a sandbox calls.
-- A game-backed read gets its unit test (test_sight.lua) through a pure helper beside it:
-- M.loots, M.opensChests, M.closingsKey, M.sackedTerrain, M.waveCloses, M.keepAi, M.refresh,
-- M.keepMaps, M.keepRide, M.aiPhaseStart, M.phaseStarted, M.phaseKey, M.decisionCalls,
-- M.battleWord, M.phaseWays, M.watched.
--
-- ── Sight.new(api) -> sight (bot.lua's contract) ────────────────────────────────────────────
-- api: { mem = { u8, s8, u16, s16, u32 }, write8, write16, write32, SYM, cpu (Sight.machine's),
--        Board (board.lua's bound reader, Board.bind: itemRange(item), staffRange(item),
--        distance(ax, ay, bx, by)),
--        map = function() -> w, h, chapter = function() -> index,
--        turn = function() -> n, board = Board.read }
-- ONE sight per run. Its answers about the board are kept until refresh(), which the caller
-- calls whenever the board may have changed (after every action, at every phase); the chapter's
-- goal and Seize tile are read once.
--   refresh()                drop every board answer; recount the objective's turns left.
--   watch(fn | nil)          fn() is asked before every game call from now on, and what it
--                            raises ends the read (M.watched; botrun's decision budget).
--   newPhase()               refresh(), and a fresh `cache` for the phase: an AI a turn event
--                            rewrote between phases is in no cache key.
--   remember(enemies)        a retry's memory (ADR 0399): enemies = { { id, charId, classId, arrival } }, every
--                            red unit earlier attempts at this start showed on screen (nil or
--                            {} on attempt 1). From then on a remembered unit counts as seen
--                            wherever the fog alone would hide it: danger, threat, keySources,
--                            closings' looters and both judged phases (M.playsAsSeen).
--   knows(u)                 whether red unit `u` is one remember() named (Board.memoryKey: a unit
--                            on the field at the start by its slot, character and class; an
--                            arrival by its character, class and arrival turn, ADR 0449, for
--                            it can take a slot another unit died out of).
--   arrived(list)            botrun's stamps: { { id, charId, classId, turn } }, the turn each
--                            red unit arrived on (0: there at the start), what knows() reads
--   sighted(units)           botrun's every board: the red units it shows out of the fog, each
--                            one's tile kept as where this attempt last saw it (#713, ADR 0455)
--   ghostOf(u) -> {x, y}|nil a ghost (M.ghostOf): red unit `u` in fog now, seen earlier this
--                            attempt and not remembered by a retry, played from its last-seen
--                            tile in the danger maps and both judged phases -- what a player
--                            knows of it. nil when another unit holds that tile.
--   plays(u)                 whether a fogged red plays as seen: knows(u), or a ghost placed
--                            in the sandbox open now (placeGhosts)
--   danger(x, y)             gBmMapRange after GenerateDangerZoneRange(FALSE), fog and roofs as
--                            the game shows them, a remembered unit's tile lifted out of the
--                            fog for the call: 0 when no enemy reaches (x, y), else its
--                            COVERAGE -- GenerateUnitCompleteAttackRange adds 1 for every tile
--                            an enemy could strike it from, so it is not an enemy count.
--   threat(e) -> function(x, y) -> coverage: GenerateDangerZoneRange itself, every other enemy
--                            marked US_UNDER_A_ROOF for the call -- the one state its loop skips
--                            a unit for and nothing else reads -- so it walks `e` alone while
--                            the others stay valid units: they block it on gBmMapUnit and a
--                            Magic Seal still seals (GenerateMagicSealMap). Fog: the game's,
--                            a remembered unit's tile lifted as danger's.
--   reach(unit, friends)     tiles with gBmMapMovement < 120 after GenerateUnitMovementMap,
--                            less those another unit stands on (gBmMapUnit). Either faction.
--   cantoTiles(unit, act)    where a Canto unit may move on to after `act` (TryMakeCantoUnit,
--                            GenerateUnitMovementMapExt from the act's tile); empty for any
--                            other. See s.cantoTiles.
--   weapons(unit)            the weapons the Attack command's Weapon Select lists, in item
--                            order: per item CanUnitUseWeaponNow allows (AttackCommandUsability's
--                            loop), { slot, min, max } with GetItemMinRange/GetItemMaxRange's
--                            reach. Board.weaponFor says which of them strikes a tile.
--   canSeize(unit)           the game's CanUnitSeize (bmdifficulty.c), the Seize command's check.
--   attack(u, e, x, y, slot) our unit from (x, y) on enemy `e` where it stands, with the weapon in
--                            item `slot` (nil = the first of weapons(u) that reaches), as the forecast
--                            window shows it (BattleGenerateSimulation +
--                            InitBattleForecastBattleStats): hit, dmg, crit, hits; `e`'s
--                            counter* (counterHit, counterDmg, counterCrit, counterHits) and
--                            `counters` (false, counter* 0, when it cannot answer) -- all for
--                            the logs. What it does is played (ADR 0377): the simulation run
--                            once per way its rolls can go, each BattleRoll1RN/2RN caught and
--                            forced (cpu.breakpoint): dealt / counterDist = { [HP lost] = p }
--                            for `e` / our unit, kill / die = the chance it kills `e` / our unit,
--                            killsTarget = the plain simulation (every hit lands, nothing
--                            procs) leaves `e` at 0. nil when (x, y) is out of our range.
--   strike(u, e, x, y, slot, from)  `e`'s own strike on `u` standing on (x, y), on its phase: the
--                            enemy phase's per-unit step (cp_decide.c CpDecide_Main: the maps
--                            rebuilt, AiUpdateNoMoveFlag, the combat weight table,
--                            AiInitDangerMap, AiClearDecision), then AiDecideMain itself -- the
--                            unit's own AI scripts, STAY, ballista and thief branches included
--                            -- with every other target hidden for the decision, so it can only
--                            choose `u`. Its decision is simulated and
--                            played as attack()'s: takenHit, takenDmg, takenCrit, takenHits
--                            (the window's), takenSlot, takenTile, takenDist (what it takes off
--                            `u`), counterDist (what `u`'s counter takes off `e`). All 0 (slot/
--                            tile nil, takenDist nothing) when the AI does not strike `u` there.
--                            `from` ({ x, y }, optional): `e` is first stood there, in the
--                            sandbox only -- the strike an enemy seen before would make from
--                            the fog's edge (Bot.fogRead, #510 PR A).
--   batch(fn)                fn's reads in one save/load: one decision's worth of questions
--                            cost one state round trip, not one each.
--   fullInfo(fn)             batch(), the fog off (M.fullInfo): fn(board), the board read with
--                            no unit fogged. A diagnostic's (FR-019), in place of batch, never
--                            inside a sandbox; nothing it reads outlives the call.
--   changed(change, fn)      fn() on the board a plan leaves: each door opened and wall broken
--                            in change.opened ({ ["x,y"] = true }) and each enemy killed in
--                            change.gone ({ [id] = true }) applied as enemyPhase applies them
--                            (M.openMap, M.takeOff), in one sandbox; the board's answers read
--                            inside are dropped after it (M.changed). The planner's re-listing
--                            (#661, #670).
--   enemyPhase(plan)        the enemy phase the AI would play against a planned board, in
--                            one batch. plan = { blues = { { unit, x, y, hp } }, waits = { { unit, x, y, order } }, gone =
--                            { [enemy id] = true } }: our units stand where the plan leaves
--                            them with its HP (plan.waits, optional: the units the plan acts, each at
--                            its end tile in act order `order`, a unit its counter killed
--                            among them; the AI changes the Misc events make at those waits are
--                            played first, M.areaWake; the result's .areaPositional and
--                            .areaTruncated count what its scripts left unread), the gone are off the map, plan.opened =
--                            { ["x,y"] = true } the doors it opens and walls it breaks, each
--                            map change applied (M.openMap), the game builds its
--                            own turn order (BuildAiUnitList, SortAiUnitList), and each enemy
--                            in it the player can see or plays() makes its own decision (the setup
--                            strike() uses, every target open). A strike moves the enemy to
--                            its tile and takes its expected damage off the target before the
--                            next decides. plan.reds = { [enemy id] = hp } (optional): the HP
--                            the plan leaves an enemy. Where the target's counter may kill
--                            the striker (its played chance, `felled`), the rest of the phase
--                            is played both ways, the striker's tile freed in the second
--                            (ch02: a Brigand Marty killed let the next one in), while the
--                            rarer way is at least M.SPLIT_FLOOR of the phase (M.phaseWays).
--                            -> { { enemy, target, taken* as strike(), counterDist, felled,
--                            strikerHp, targetHp } }: the likeliest
--                            outcome's strikes, with .outcomes = { { p, strikes } } (p sums
--                            to 1) for every way the phase went, and .unsplit = the
--                            uncertain counter kills below the floor, played one way.
--   nextPhase(plan, reply)   the enemy phase AFTER the next (the planner's lookahead, FR-017),
--                            our units holding between, or with `reply` playing armyReply's
--                            turn: plan as enemyPhase's; the next phase
--                            played along its expected way, every enemy moving, then the turn
--                            advanced, the fog refreshed and the second played as enemyPhase
--                            plays one. -> as enemyPhase, plus .hp (each blue and green unit's
--                            HP when it begins, 0 if dead) and .moved. See s.nextPhase.
--   objective                { kind, tile, turnsLeft, boss, gameOver } -- see objective();
--                            boss = where a boss's death ends the chapter (a Defeat Boss goal, or
--                            a Misc DefeatBoss event beside another goal), the charId whose death
--                            quote raises EVFLAG_DEFEAT_BOSS (GetDefeatTalkEntry), read at the start;
--                            gameOver = the charIds, on any side, whose death sets
--                            EVFLAG_GAMEOVER (SetPidDefeatedFlag: a lord's), read at the start.
--   field(goal)              dist[y][x] = the movement cost from `goal` to (x, y), FE8's
--                            GenerateExtendedMovementMap with fieldUnit()'s costs; nil =
--                            unreached.
--   fieldUnit()              the first deployed unit that can Seize, else the first deployed.
--   terrain(x, y)            gBmMapTerrain[y][x].
--   redCount()               CountRedUnits: every red not dead (a Rout's count).
--   unseen()                 every tile the fog hides now: gBmMapFog 0 there, which
--                            RefreshEntityBmMaps never leaves without fog (bmmap.c). An enemy
--                            in fog is the game's US_BIT9 (board.lua), no target.
--   staves(u)                the staves `u` can heal with, { slot (0-based), amount, exp,
--                            range (its reach: Board.staffRange, Physic's Mag/2) }:
--                            one of M.HEAL_STAVES that CanUnitUseStaff allows.
--   canTalk(u, t)            the Talk command's own pair check, CheckForCharacterEvents (what
--                            MakeTalkTargetList adds a neighbour by).
--   offers(u, tiles, act, target)  of `tiles`, those where `u` standing there gets the unit
--                            menu's own command for `act` (MENU_CHECK: TalkCommandUsability,
--                            DoorCommandUsability, ...) enabled, its target list holding
--                            `target` (a unit for Talk, a door's tile for Door), in one sandbox.
--   opens(u, terrain)        `u` holds what opens that terrain (TERRAIN_DOOR, TERRAIN_CHEST_FULL):
--                            GetUnitKeyItemSlotForTerrain, a key or a thief's lockpick.
--   convoyKey(u, terrain)    the convoy's first item that opens `terrain` (a door's by default) for
--                            `u`, { id, uses }; nil with a full bag or none (what Supply's Take
--                            hands).
--   opensChest(u)            opens() for a chest (#699: a chest key is the convoy's to give).
--   isChestLock(terrain)     whether a locked() terrain is a chest's (a door's is the other).
--   opensDoor(u), holdsKey(u)  opens() for a door; for a door or a chest (what a keys claim
--                            hunts: an enemy carrying a key, or a thief's lockpick).
--   locked(u, x, y)          the terrain at (x, y) when it is a door or a full chest `u` holds
--                            nothing to open (opens()), else nil.
--   keySources(u, terrain)   the enemies whose fall gives `u` what opens `terrain`: red (a
--                            green ally is never struck, ADR 0384), on the field, seen (no US_BIT9) or knows(), marked US_DROP_ITEM -- the game gives
--                            a downed unit's last item to the blue unit that downs it
--                            (bmmind.c, GetUnitLastItem) -- and `u` holding that item passes
--                            GetUnitKeyItemSlotForTerrain (a lockpick only for a thief).
--   explorable()             the villages and chests still open now: { x, y, kind =
--                            "visit"|"chest", house (a Visit whose entry has flag 0) } per tile whose Visit or Chest command (read with
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
--                            BattleGenerateSimulation): { dealt, wear, wearSlot, wearAt }
--                            (M.strikeWallIn). A wall is always hit and never crit
--                            (ComputeBattleObstacleStats).
--   doors()                  the door tiles still closed: a tile whose command is Door
--                            (read with the Seize tile) and whose terrain is still a door.
--   mapChange(x, y)          the tiles opening the door or breaking the wall at (x, y) opens:
--                            its map change's drawn tiles fieldUnit() can walk, { x, y, tile,
--                            terrain, cost } (M.mapChangeTiles); nil when no change covers it.
--                            Kept for the run.
--   heals(u, x, y, hurt)     what `u` could heal standing on (x, y): per staff in staves(u)
--                            that CanUnitUseItem allows there -- which builds vanilla's own heal
--                            target list -- { slot, amount = GetUnitItemHealAmount, targets =
--                            { unit index bytes } }. `hurt` (optional, units): allies read as
--                            one HP short, for a heal the planner means to follow a blow.
--   maxHps(units)            sets each unit's `maxhp` to GetUnitMaxHp (maxHP + the equipped
--                            weapon's HP bonus), the cap AddUnitHp holds a heal to.
--   terrainHeal(u)           the HP the tile `u` stands on heals it at the start of its own
--                            faction's phase, as MakeTerrainHealTargetList reads it
--                            (bmtarget.c): GetTerrainHealAmount(terrain) * GetUnitMaxHp(u) / 100,
--                            truncated toward zero as C does (a fort 20%, a gate or throne 10%);
--                            0 off a heal tile, and for a unit the game skips
--                            (Board.terrainHealSkips). The raw amount: AddUnitHp's clamp to max
--                            HP (Board.addHp) is the caller's. The phases enemyPhase and
--                            nextPhase play heal every red this way as each begins (healFaction).
--   mend(u)                  an item that heals `u` itself (a Vulnerary): not a staff (IA_STAFF),
--                            GetUnitItemHealAmount > 0, CanUnitUseItem (its HP is short) --
--                            { slot, amount }, the first in the inventory; nil.
--   salve(u)                 whether `u` holds such an item at all, whatever its HP (the
--                            planner's wear, ADR 0421): mend() offers none at full HP.
--   obstacles()              every obstacle the Attack command can strike, as
--                            TryAddTrapsToTargetList (bmtarget.c) lists them from the trap pool:
--                            a TRAP_OBSTACLE's damaged wall at its tile, or the tile below where
--                            two are stacked (InitMapObstacles traps the top one only), or its
--                            snag. { x, y, hp, trap } -- hp = the trap's `extra`, trap = its
--                            tile ("x,y"): a two-tile wall's tiles share it, and its HP.
--   nextTurnEvent(turn)      the first later turn at which a turn event the game would fire is
--                            not already firing now (SearchAvailableEvent over the chapter's
--                            turnBasedEvents, the turn and phase set to each), or nil.
--   scriptedUnits()          the units the chapter's turn events load and remove, read once off
--                            their script bytes (#724): { arrivals = { { charId, x, y, turn,
--                            boardTurn } }, removals = { [charId] = boardTurn } }.
--   cache                    {} for ONE player phase (bot.lua keeps attacks and strikes there).
--   demands()                what the map asks of a team (M.demandsOf), at the prep screen:
--                            the board's red units and the chapter's tile commands (read once,
--                            with the Seize tile), fog from gPlaySt.chapterVisionRange, and a
--                            `talk` demand per recruit a unit brings over for free (M.freeTalks).
--   answer(u, d) -> answered, strength: how `u` answers demand `d`, by the game's own checks.
--                            enemy: attack() on d.rep from r.max away (N, E, S, W, the first on
--                            the map), answered when it kills in one round and outlives the
--                            counter (M.answerOf); strength = its expected damage that round.
--                            chests/doors: GetUnitKeyItemSlotForTerrain finds a key or lockpick
--                            (ChestCommandUsability, DoorCommandUsability). fog: GetUnitFogViewRange
--                            sees past the chapter's range (a thief, a torch). sustain: a
--                            staff it heals with (staves()). village: it reaches the tile, from
--                            fieldUnit()'s tile, in no more turns than the fastest red unit
--                            from its own (GenerateExtendedMovementMap on each one's costs,
--                            turns = cost / UNIT_MOV rounded up).
-- Sight.seed(api, s)         InitRN(s): the game's own seeding, written into gRNSeeds.
-- Sight.dice(api)            the three u16 words at gRNSeeds, as { s0, s1, s2 } (the one reader).
-- Sight.advance(api, n)      n draws of the game's own NextRN taken from gRNSeeds and written
--                            back (no new seed: the stream moves along, never restarts).

local M = {}

M.calls = {}                 -- game calls made, by function address (the run's cost record)
M.FRAME_BUDGET = 600         -- frames one call may run; a full map's danger zone takes a few
M.MOVE_LIMIT = 120           -- include/bmmap.h: a movement-map cost at or above it is unreachable
M.UNREACHED = 0xFF           -- GenerateMovementMap fills its map with -1 before it floods
M.ISLOT_AUTO = -1            -- include/bmbattle.h BU_ISLOT_AUTO
M.TILE_COMMAND_SEIZE = 0x11  -- include/eventinfo.h
M.TILE_COMMAND_VISIT, M.TILE_COMMAND_DOOR, M.TILE_COMMAND_CHEST = 0x10, 0x12, 0x14
M.TERRAIN_DOOR, M.TERRAIN_CHEST_FULL = 0x1E, 0x21   -- include/constants/terrains.h
M.TERRAIN_VILLAGE_CLOSED, M.TERRAIN_CHEST_EMPTY = 0x04, 0x20
-- The terrain a demand kind (api.needs' `doors`, `chests`) opens: the one owner of kind -> lock.
M.LOCK_TERRAIN = { doors = M.TERRAIN_DOOR, chests = M.TERRAIN_CHEST_FULL }
-- the tile command that offers each lock demand kind: with LOCK_TERRAIN, the one owner of
-- command -> kind -> terrain (demandsOf, lockNeeded, isChestLock, locked)
M.LOCK_KIND = { [M.TILE_COMMAND_CHEST] = "chests", [M.TILE_COMMAND_DOOR] = "doors" }
M.ITEM_BOOSTER_SKL = 0x5D    -- include/constants/items.h: ADR 0379's line, the first booster
M.MENU_ENABLED = 1           -- include/uimenu.h
M.MENU_NOTSHOWN = 3
M.FACTION_MASK = 0xC0        -- include/bmunit.h: a unit index's faction bits (blue 0x00)
M.EVFLAG_WIN = 3             -- the same; the completion flag of a win event
M.EVFLAG_DEFEAT_BOSS = 2     -- include/constants/event-flags.h; DefeatTalkEnt +04 flag
M.EVFLAG_GAMEOVER = 101      -- the same; RunWaitEvents ends the game when it is set
M.DEFEAT_TALK_FLAG = 0x04
M.TERRAIN_WALL_DAMAGED, M.TERRAIN_SNAG = 0x1B, 0x33
-- bmtrick.h: struct Trap { u8 xPos, yPos, type, extra; s8 data[4] } in sTrapPool, ended by
-- TRAP_NONE; TRAP_OBSTACLE = walls and snags. A ballista's uses are its data[2]
-- (TRAP_EXTDATA_BLST_ITEMUSES), at +06.
M.TRAP_SIZE, M.TRAP_MAX, M.TRAP_OBSTACLE, M.TRAP_BLST_USES = 8, 64, 2, 6
-- bmunit.h: US_IN_BALLISTA, and ballistaIndex at 0x1C (its trap's index in sTrapPool; the
-- halfword's other byte is movBonus) and pMapSpriteHandle at 0x3C, what M.keepRide keeps
M.US_IN_BALLISTA, M.UNIT_BALLISTA, M.UNIT_SPRITE = 1 << 11, 0x1C, 0x3C
-- whether a unit state word (+0C) is a ballista's rider's
function M.riding(state) return ((state or 0) & M.US_IN_BALLISTA) ~= 0 end
-- include/cp_script.h: struct AiScr is 0x10 bytes, `cmd` at +00; AI_CMD_PILLAGE runs
-- AiScriptCmd_10_DoLooting, and a script loops back with AI_CMD_GOTO.
M.AI_SCR_SIZE, M.AI_CMD_PILLAGE, M.AI_CMD_GOTO, M.AI_SCR_MAX = 0x10, 0x10, 0x03, 32
-- include/constants/items.h; include/bmunit.h CA_STEAL, CA_BALLISTAE
M.ITEM_CHESTKEY, M.ITEM_LOCKPICK, M.CA_STEAL, M.CA_BALLISTAE = 0x69, 0x6B, 0x04, 1 << 7
-- The staves the game heals one ally with: bmitemuse.c DoItemUse sends Heal, Mend and Recover
-- (0x4B-0x4D) and Physic (0x4E) to DoUseHealStaff, gSelectInfo_Heal's target selection, the one
-- the harness plays. GetUnitItemHealAmount (bmitem.c) is no test of it: it adds its holder's
-- power for ANY staff (IA_STAFF), so a Barrier read as a heal and its use opened
-- gSelectInfo_Barrier (vanilla E_16, campaign 4006, turn 5: a crash). Fortify heals in
-- an area with no target selection (SetStaffUseAction): not one of them.
M.HEAL_STAVES = { [0x4B] = true, [0x4C] = true, [0x4D] = true, [0x4E] = true }
-- include/bmunit.h CA_CANTO: a second move after an act (playerphase.c TryMakeCantoUnit),
-- read off the character's and the class's attributes ORed (UNIT_CATTRIBUTES)
M.CA_CANTO = 1 << 1
-- The acts that hand a Canto unit its second move: any but Wait, Combat or Staff
-- (TryMakeCantoUnit's switch) of those the bot plays and drives one through (harness
-- awaitActed's `canto`).
M.CANTO_ACTS = { rescue = true, drop = true, visit = true, chest = true, talk = true }

-- What act `a` of unit `uid` leaves carried, in stageCarry's shape (the planner's st.carry):
-- a Rescue's target carried by `uid`, a Drop's set on its tile; nil for any other act.
function M.carryOf(a, uid)
    if a.act == "rescue" then return { [a.targetId] = { by = uid } } end
    if a.act == "drop" then return { [a.targetId] = { x = a.dropAt.x, y = a.dropAt.y } } end
    return nil
end
M.CLOSE_HORIZON = 8   -- enemy phases closings() plays forward
-- turns s.scriptedUnits() reads the turn events of: a turn an event can name runs to
-- M.LAST_EVENT_TURN (a byte); the scan stops at 30: the latest start turn any vanilla turn event names is
-- 19 (grep of src/events/*eventinfo.h TurnEvent*, 255 = open-ended end excluded), and each turn
-- costs three game calls. A turn event starting later than the horizon is not read
M.SCRIPT_HORIZON = 30
-- include/types.h goal window types, chapter data +0x8C (goalWindowDataType); +0x8D is
-- goalWindowEndTurnNumber, whose LAST turn the game's own goal window shows as End - 1
-- (player_interface.c), so the turns left on turn T are End - T.
M.GOALS = { [0] = "seize", [1] = "rout", [2] = "survive", [3] = "boss", [4] = "special" }
M.CHAPTER_GOAL, M.CHAPTER_GOAL_TURN = 0x8C, 0x8D
M.LAST_EVENT_TURN = 0xFF     -- eventinfo.c EvCheck02_TURN: turns are a byte (0xFF = open-ended)
M.PHASES = { 0x00, 0x40, 0x80 }   -- gPlaySt.faction: blue, green, red

-- struct BattleUnit (include/bmbattle.h) and BattleForecastProc (include/bksel.h) offsets.
local BU = { weapon = 0x48, weaponBefore = 0x4A, weaponAttributes = 0x4C, weaponSlotIndex = 0x51,
             canCounter = 0x52, attack = 0x5A, defense = 0x5C, hit = 0x64, crit = 0x6A,
             statusOut = 0x6F, hpInitial = 0x72, nonZeroDamage = 0x7C, weaponBroke = 0x7D }
-- include/bmunit.h UNIT_STATUS_PETRIFY and UNIT_STATUS_13: the two statuses a blow sets that
-- end the battle like a death (BattleGenerateHit)
local STATUS_PETRIFY, STATUS_13 = 11, 13
-- struct BattleUnit is 0x80 bytes; its word at +0x10 holds xPos, yPos (the low half), maxHP
-- and curHP. struct BattleStats: +00 config and +02 range share its first word.
local BU_SIZE, BU_POSITION, POSITION_BITS = 0x80, 0x10, 0xFFFF
-- The AI's two bytes on a unit the enemy phase's start rewrites (M.battleWord): +0A aiFlags,
-- the third byte of the word at +08 (level, exp, aiFlags, index), and +46 ai_counter, the
-- third of the word at +44 (ai2, ai_b_pc, ai_counter).
local BU_AI_FLAGS, BU_AI_COUNTER, AI_BYTE_BITS = 0x08, 0x44, 0x00FF0000
local PROC_HITS_A, PROC_HITS_B = 0x50, 0x51
M.SCRATCH_SIZE = 0x54        -- the forecast proc; EventInfo (0x1C) reuses the same bytes
-- struct Unit (include/bmunit.h): +00 pCharacterData, +0C state, +10/+11 xPos/yPos,
-- +40 u16 ai_config. Its state bits are board.lua's (Board.US_*).
local UNIT_STATE, UNIT_X, UNIT_Y, UNIT_HP, UNIT_AI_CONFIG = 0x0C, 0x10, 0x11, 0x13, 0x40
M.UNIT_STATE, M.UNIT_X, M.UNIT_Y = UNIT_STATE, UNIT_X, UNIT_Y   -- the harness's probes'
-- struct AiState (include/cp_common.h): +79 decideState, +7A dangerMapFilled, +7C unk7C (the
-- staff AI's HP threshold), +7D combatWeightTableId; the weight table comes from ai_config
-- bits 3..7 (AI_UNIT_CONFIG_COMBATWEIGHT_*). cp_decide.c's per-unit loop writes these as field
-- assignments, which are copied here as they stand.
local AI_DECIDE_STATE, AI_DANGER_FILLED, AI_STAFF_HP, AI_WEIGHT_TABLE = 0x79, 0x7A, 0x7C, 0x7D
local AI_WEIGHT_SHIFT, AI_WEIGHT_MASK = 3, 0x1F << 3
-- What cp_phase.c AiPhaseInit writes at an enemy phase's start (M.aiPhaseStart): +78 orderState,
-- +7B flags (AI_FLAG_0 = 1), +7E unk7E, +80 u32 specialItemFlags, +84 unk84, +85 bestBlueMov
-- (SetupUnitInventoryAIFlags's), +86 cmd_result[8].
local AI_ORDER_STATE, AI_FLAGS, AI_UNK7E, AI_ITEM_FLAGS, AI_UNK84, AI_BEST_MOV, AI_CMD_RESULT =
    0x78, 0x7B, 0x7E, 0x80, 0x84, 0x85, 0x86
local AI_FLAG_0, AI_CMD_RESULTS = 1, 8
-- cp_phase.c AiPhaseBerserkInit's gAiState.flags (AI_FLAG_BERSERKED)
local AI_FLAG_BERSERKED = 4
-- gAiDecision's itemSlot for the ballista (AiAttemptBallistaCombat's -1); its layout is
-- board.lua's (Board.AI_DEC).
local BALLISTA_SLOT = 0xFF
-- struct ActionData (include/bmmind.h): +13 xOther, +14 yOther, +15 trapType (a wall's HP when
-- the Attack menu forecasts a strike on it).
local ACTION_X_OTHER, ACTION_Y_OTHER, ACTION_TRAP_TYPE = 0x13, 0x14, 0x15
-- struct EventInfo (include/eventinfo.h): +00 listScript, +04 script, +1A pidA, +1B pidB;
-- 0x1C bytes. A talk entry (EvtListTalk, struct EvCheck03/04) holds script +04, pidA +08,
-- pidB +09.
local EVENT_INFO_SIZE, EVENT_SCRIPT, EVENT_PID_A, EVENT_PID_B = 0x1C, 0x04, 0x1A, 0x1B
-- struct EventInfo +08 flag, +18/+19 xPos/yPos; struct ChapterEventGroup +08 locationBasedEvents
local EVENT_FLAG, EVENT_X, EVENT_Y = 0x08, 0x18, 0x19
local CHAPTER_TURNS, CHAPTER_LOCATIONS, CHAPTER_MISC = 0x00, 0x08, 0x0C
local TALK_SCRIPT, TALK_PID_A, TALK_PID_B, NO_PID = 0x04, 0x08, 0x09, 0xFF
-- struct ChapterEventGroup (include/chapterdata.h): +04 characterBasedEvents, the talks.
local CHAPTER_TALKS = 0x04
-- struct PlaySt: +0D chapterVisionRange (0 = no fog), +0F faction, +10 u16 chapterTurnNumber.
local PLAY_VISION, PLAY_FACTION, PLAY_TURN = 0x0D, 0x0F, 0x10
M.PLAY_VISION = PLAY_VISION
-- UNIT_MOV (bmunit.h): struct Unit +04 pClassData, +1D s8 movBonus; struct ClassData +12 baseMov.
local UNIT_CLASS, UNIT_MOV_BONUS, CLASS_MOV = 0x04, 0x1D, 0x12
-- UNIT_MOV of the unit struct at `addr`: the class's MOV plus the unit's bonus. Pure over mem.
function M.movOf(mem, addr)
    return mem.s8(addr + UNIT_MOV_BONUS) + mem.s8(mem.u32(addr + UNIT_CLASS) + CLASS_MOV)
end
-- struct ClassData +28 attributes (CA_*), as CharacterData's; struct Unit +42 ai1, +44 ai2 (the
-- AI script indices)
local CLASS_ATTRIBUTES, UNIT_AI1, UNIT_AI2 = 0x28, 0x42, 0x44
-- bmunit.h, what M.keepAi keeps: aiFlags is the byte at 0x0A (0x0B, the other byte of its
-- halfword, is the unit's index, written only when the unit is made); the AI block is the
-- UNIT_AI_WORDS halfwords from ai_config, 0x40 to 0x47: ai_config, ai1 and ai_a_pc, ai2 and
-- ai_b_pc, ai_counter and a padding byte
M.UNIT_AI_FLAGS, M.UNIT_AI_CONFIG, M.UNIT_AI_WORDS = 0x0A, UNIT_AI_CONFIG, 4

-- Sight.machine(cpu) -> sandbox(fn): cpu = { read(reg), write(reg, v), read32(addr),
-- write16(addr, v), write32(addr, v), save() -> state, load(state), frames(done, max) -> bool
-- (run emulated frames until done() or `max` have passed) }. sandbox(fn) runs fn(call, scratch)
-- between a save and a load and returns what fn returns; call(addr, args) runs one game function
-- and returns its r0. `scratch` is SCRATCH_SIZE free bytes for the caller. The CPU is put in
-- System mode FIRST: sp and lr are banked, so they are read and written in the mode the call runs
-- in -- a frame that ends inside an IRQ or SWI would otherwise hand out that mode's registers.
-- Above the call's stack sit `scratch` and the return loop; the load puts back whatever was there.
--
-- Sight.machine(cpu, true) is the same call KEPT (#510 step 9 PR E): what the game function
-- wrote stays -- a shop proc it started runs on the next frame -- and only the registers are put
-- back, so the game resumes where the frame left it: at its rest between frames, which a kept
-- call first runs real frames to reach (M.REST_PC, below). They are read and written in the mode the
-- frame ended in, System's sp and lr too (the call's own mode). pc is put back through a
-- measured write: mGBA's pc write refills the pipeline, so it reads one instruction past what
-- was written (measured 2026-10-27 at a frame boundary, the BIOS halt loop, ARM: +4).
local THUMB_B_SELF = 0xE7FE
-- The return loop of a call that is loaded back HALTS rather than spins: a CPU spinning in
-- `b .` is emulated instruction by instruction to the frame's end (measured, Manchego Stars
-- ch01: 0.47 ms a sandbox frame against ~0.13 for a live one, which sits in the BIOS's
-- VBlankIntrWait; 1.05 ms with breakpoints held), and mGBA skips a halted CPU from event to
-- event. A RAM write to HALTCNT is ignored outside the BIOS (mGBA io.c, as on hardware), so
-- the loop calls the BIOS's Halt (swi 2), REG_IE cleared first so nothing wakes it. The halted
-- CPU's pc sits in the BIOS, outside the loop, so the loop first marks a word that the call
-- has returned. Each call writes the game's IE back before it starts: the frame ends with the
-- CPU halted (the game's VBlankIntrWait, or this loop), and only an enabled, pending interrupt
-- (VBlank's IF, never acknowledged: IRQs stay masked) wakes it. The load puts IE back.
--   +00 ldr r1, [pc, #12]   (the marker's address, the word at +10)
--   +02 str r1, [r1, #0]    (marker = its own address)
--   +04 ldr r1, [pc, #12]   (REG_IE, the word at +14)
--   +06 movs r2, #0
--   +08 strh r2, [r1, #0]   (IE = 0)
--   +0A swi 2
--   +0C b +0A
-- The next call leaves the BIOS's SWI frame unreturned, so each call also puts the SVC
-- stack pointer back where the sandbox found it (without, ~46 calls crept the SVC stack into
-- the game's IRQ area and a call never returned). A KEPT call keeps `b .`: its SWI would
-- overwrite the game's own SVC lr and spsr, which a frame ending inside VBlankIntrWait still
-- needs, and no load puts them back.
M.HALT_LOOP = { 0x4903, 0x6009, 0x4903, 0x2200, 0x800A, 0xDF02, 0xE7FD, 0x46C0 }
local HALT_LOOP = M.HALT_LOOP
M.HALT_MARKER, M.HALT_IE = 0x10, 0x14         -- the loop's two literal words: the marker's
local HALT_MARKER, HALT_IE = M.HALT_MARKER, M.HALT_IE   -- address, then REG_IE
M.MARKER_AT = 0x7C                            -- the marker word, at top + 7C (under the loop)
local MARKER_AT = M.MARKER_AT
M.REG_IE = 0x04000200
local REG_IE = M.REG_IE
local SVC_NOIRQ = 0x13 | 0x80                 -- CPSR mode Supervisor, I
-- A call LIST runs every call of it in one stretch of emulation: each call takes a whole frame
-- however little of it the function uses (the rest spins in the loop), and one enemy's
-- decision was five calls of its own (#510 step 9: ~8,000 of ch02's 9,748 calls an attempt). The stub,
-- Thumb, ARMv4T (no blx): r4 walks a list of { addr|1, r0, r1, r2, r3, [sp] } words ended by
-- addr 0; it calls each through a `bx r5` veneer and branches to the return loop at the end.
-- r4-r6 are callee-saved (AAPCS), so every called function keeps them.
-- Calls in one list. The list sits at loop + LIST_AT = top + 0xC0 and the caller's stack starts
-- at top + 0x180 or above, so 0xC0 bytes hold up to seven entries and the end word; the
-- longest list is six, a decision inside its phase (aiDecide).
M.LIST_MAX = 6
M.LIST_STUB = {
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
    0xE7E1,           -- +1A b loop             (loop = stub - 0x20)
    0x4728,           -- +1C bx r5
}
local LIST_STUB = M.LIST_STUB
M.LIST_STUB_AT = 0x20                                  -- past the halt loop's 0x18 bytes
local LIST_STUB_AT, LIST_AT, LIST_ENTRY = M.LIST_STUB_AT, 0x40, 24
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
-- An enemy phase's outcomes, { { p, strikes } } (p sums to 1), and how many uncertain counter
-- kills and status staves it left unsplit. strikeAt(k, done) plays the k-th enemy of `n` after
-- `done`'s strikes: nil when it neither strikes nor casts a status staff; for a strike, `t`
-- (t.felled: the played chance the target's counter kills it), `done` with t added, and free(),
-- which takes the striker off its tile. A status staff (#674) is no strike: `t` = { lands = its
-- hit's chance }, `done` as it was, and free() its hit. Either splits the phase alike, and one
-- left unsplit takes its likelier side (a hit at even odds or better lands).
-- A striker the counter may kill splits the phase: the enemies after it decide once with it
-- standing and once with its tile free (each in a nested `sandbox`, so neither sees the
-- other's board), the second as likely as the counter kills it (ch02: a Brigand Marty killed
-- let the next one in). A split is played only while its rarer side is at least `floor`
-- (M.SPLIT_FLOOR) of the whole phase: below it the phase goes on the likelier way alone
-- (the striker gone at even odds or better, as nextPhase's expected way has it) and the kill
-- is counted, never silent. Every split played both ways doubled the phase with each such
-- striker, a certain kill included: vanilla Ch15 (Eirika)'s first decision ran 8.4 million
-- frames in one such phase without an answer (ADR 0411). The floor bounds the outcomes at
-- 1 / floor, since each split leaves both sides at least that likely. The value is a tuning
-- one (the ADR has what 1/64 and 1/256 cost and played).
-- `mass0` (optional, default 1): the phase's own chance within the plan the planner judges (one
-- way of the plan's uncertain kills, ADR 0415), so one floor bounds the whole judged plan. The
-- lookahead's phase (nextPhase) is the plan's average way, the whole plan: its default 1 is right.
-- `tail(done, mass)` (optional): what follows the list on each way, played at its end on that
-- way's board -> its own outcomes, as phaseWays' (our berserk phase's ways each end in the enemy
-- phase that board starts, #660). `done0` (optional): the strikes before the list.
M.SPLIT_FLOOR = 1 / 64
function M.phaseWays(n, strikeAt, sandbox, floor, mass0, tail, done0)
    floor = floor or M.SPLIT_FLOOR
    local unsplit = 0
    local function play(i, done, mass)
        for k = i, n do
            local t, now, free = strikeAt(k, done)
            if t then
                done = now
                local q = t.lands or t.felled
                if q > 0 and q < 1 and mass * math.min(q, 1 - q) >= floor then
                    local out = {}
                    local stood = sandbox(function() return play(k + 1, done, mass * (1 - q)) end)
                    local fell = sandbox(function()
                        free()
                        return play(k + 1, done, mass * q)
                    end)
                    for _, o in ipairs(stood) do
                        out[#out + 1] = { p = o.p * (1 - q), strikes = o.strikes }
                    end
                    for _, o in ipairs(fell) do
                        out[#out + 1] = { p = o.p * q, strikes = o.strikes }
                    end
                    return out
                elseif q > 0 then
                    if q < 1 then unsplit = unsplit + 1 end
                    if q >= 0.5 then free() end
                end
            end
        end
        if tail then return tail(done, mass) end
        return { { p = 1, strikes = done } }
    end
    return play(1, done0 or {}, mass0 or 1), unsplit
end

-- Where a sandbox's frame starts below the game's sp (the call's stack top), and where its return
-- loop sits above that.
function M.top(sp) return (sp - 0x180) & ~7 end
M.SCRATCH_AT, M.LOOP_AT = 0x10, 0x80   -- below SCRATCH_AT: a fifth argument, at the stack top
-- A kept call runs only while the game rests between frames, its CPU halted in the BIOS's
-- VBlankIntrWait: pc reads M.REST_PC there (measured 2026-11-15, vanilla Ch15's prep, every
-- resting boundary 0x1F8 with cpsr 0x2000001F). A frame can also end inside the game's own
-- VBlank work (the same run: pc 0x2E8, a BIOS routine called from OnVBlank's Proc_Run, the
-- terrain window drawing). The registers put back resume that work where it stood, with the
-- pointers it held: StartShopScreen kept there ended the terrain window, the shop took its
-- freed slot (the free list hands back the last slot freed), and the resumed draw wrote its
-- text over the shop's stock (#620: the list shrank under the hand and the purchase failed).
-- So a kept call first runs frames until the CPU rests, and fails loudly if it never does.
-- The halt is reached only from the end of a main loop (bm.c's, the two battle loops', the link
-- error screen's: every VBlankIntrWait in src/ follows its loop's Proc_Run), so a CPU resting
-- there holds no proc walk. 0x1F8 is the halt of the BIOS the emulator runs: mGBA's built-in
-- one (no gba.bios is configured); another BIOS rests elsewhere and fails the wait loudly.
-- A kept call's frames, the wait and the call's own, are real frames (cpu.live): no load
-- rewinds them, so they are not counted as the sight's (cpu.frames).
M.REST_PC, M.REST_FRAMES = 0x1F8, 600
function M.machine(cpu, keep)
    return function(fn)
        local frames = keep and assert(cpu.live, "sight: a kept call needs cpu.live") or cpu.frames
        if keep and cpu.read("pc") ~= M.REST_PC
                and not frames(function() return cpu.read("pc") == M.REST_PC end, M.REST_FRAMES) then
            error(string.format("sight: the CPU never rested between frames in %d frames (pc 0x%08X, "
                .. "rest 0x%X, mGBA's built-in BIOS): a kept call would resume the game mid-frame",
                M.REST_FRAMES, cpu.read("pc"), M.REST_PC))
        end
        -- The load puts every register back; only cpsr is kept here. A kept call loads
        -- nothing, so it reads every register first.
        local state = keep and readRegisters(cpu) or cpu.save()
        local cpsr, top, scratch, loop, marker, ie, svcSp
        local function returned()
            if marker then return cpu.read32(marker) == marker end
            local pc = cpu.read("pc")
            return pc >= loop and pc <= loop + 8
        end
        -- the CPU sent to `pc` (lr = the loop, unless the stub sets its own) with the return
        -- loop armed, run until it is back in it -> r0. sp and lr are banked: written after the
        -- switch.
        local function run(pc, what, lr)
            if keep then
                cpu.write16(loop, THUMB_B_SELF)
            else
                for i, h in ipairs(HALT_LOOP) do cpu.write16(loop + (i - 1) * 2, h) end
                cpu.write32(loop + HALT_MARKER, marker)
                cpu.write32(loop + HALT_IE, REG_IE)
                cpu.write32(marker, 0)
                cpu.write16(REG_IE, ie)
                cpu.write("cpsr", (cpsr & ~0xFF) | SVC_NOIRQ)
                cpu.write("sp", svcSp)
            end
            cpu.write("cpsr", (cpsr & ~0xFF) | SYSTEM_THUMB_NOIRQ)
            cpu.write("sp", top)
            if lr then cpu.write("lr", lr) end
            cpu.write("pc", pc)
            if not frames(returned, M.FRAME_BUDGET) then
                error(string.format("sight: %s did not return in %d frames (pc 0x%08X)",
                    what, M.FRAME_BUDGET, cpu.read("pc")))
            end
            return cpu.read("r0")
        end
        local function call(addr, args)
            if type(addr) == "table" then
                -- a list: { { addr, args }... }, each args at most five -> the last call's r0
                local list = addr
                assert(#list >= 1 and #list <= M.LIST_MAX,
                    "sight: a call list holds 1-" .. M.LIST_MAX .. " calls")
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
                cpu.write("r4", at)
                return run(stub, string.format("a call list (0x%08X first)", list[1][1]))
            end
            M.calls[addr] = (M.calls[addr] or 0) + 1
            for i, a in ipairs(args) do
                if i <= 4 then cpu.write("r" .. (i - 1), a & 0xFFFFFFFF)
                else cpu.write32(top + (i - 5) * 4, a & 0xFFFFFFFF) end
            end
            return run(addr & ~1, string.format("call 0x%08X", addr), loop | 1)
        end
        -- Everything after the save is inside the pcall, the mode switch included: whatever
        -- raises, the state is loaded back.
        local ok, a, b = pcall(function()
            cpsr = cpu.read("cpsr")
            cpu.write("cpsr", (cpsr & ~0xFF) | SYSTEM_THUMB_NOIRQ)
            top = M.top(cpu.read("sp"))
            -- SCRATCH_SIZE fits between scratch and the loop; a call list's stub and list
            -- sit above the loop (LIST_STUB_AT, LIST_AT: LIST_MAX entries and the end)
            scratch, loop = top + M.SCRATCH_AT, top + M.LOOP_AT
            if not keep then
                marker, ie = top + MARKER_AT, cpu.read32(REG_IE) & 0xFFFF
                cpu.write("cpsr", (cpsr & ~0xFF) | SVC_NOIRQ)
                svcSp = cpu.read("sp")
                cpu.write("cpsr", (cpsr & ~0xFF) | SYSTEM_THUMB_NOIRQ)
            end
            return fn(call, scratch)
        end)
        if keep then writeRegisters(cpu, state) else cpu.load(state) end
        if not ok then error(a, 0) end
        return a, b
    end
end

-- `cache[key]`, else read(), kept there only when no sandbox is `open()`: a read made inside one
-- may see its writes (journaled, or a game call's own), so it is returned and dropped.
function M.keptRead(cache, key, read, open)
    if cache[key] ~= nil then return cache[key] end
    local now = read()
    if not open() then cache[key] = now end
    return now
end

-- `body()` run with a breakpoint on each of `holds` ({ { addr, fn }... }: fn runs each time the
-- CPU reaches addr), every one cleared after it returns or raises: mGBA steps the CPU one
-- instruction at a time while any is set, so they are held only for the calls that need them.
-- -> what body returns. (INSPECT.breakWhile is the live game's: held frame by frame.)
function M.withBreaks(cpu, holds, body)
    local ids = {}
    local out = table.pack(pcall(function()
        for _, h in ipairs(holds) do ids[#ids + 1] = cpu.breakpoint(h[1], h[2]) end
        return body()
    end))
    for _, id in ipairs(ids) do cpu.unbreak(id) end
    if not out[1] then error(out[2], 0) end
    return table.unpack(out, 2, out.n)
end

-- An inventory entry as the unit struct holds it: the item id, its uses in the high byte.
local function itemOf(it) return it.id | (it.uses << 8) end

-- The staves in `u`'s inventory it heals one ally with (M.HEAL_STAVES) and CanUnitUseStaff
-- allows, in order: { slot, amount (GetUnitItemHealAmount), exp (M.staffExp), range (its reach,
-- Board.staffRange; 0 is Physic's Mag/2: GetUnitItemUseReachBits, bmitem.c, and
-- GetUnitMagBy2Range, bmunit.c) }. `call` is a sandbox's, `Board` the bound reader; s.staves'
-- one owner, and through it the `sustain` demand's.
function M.healStaves(Board, call, S, u)
    local out = {}
    for i, it in ipairs(u.items) do
        local item = itemOf(it)
        if M.HEAL_STAVES[item & 0xFF] and call(S.CanUnitUseStaff, { u.addr, item }) ~= 0 then
            local range = Board.staffRange(item) or 1
            if range == 0 then range = call(S.GetUnitMagBy2Range, { u.addr }) end
            out[#out + 1] = { slot = i - 1, amount = call(S.GetUnitItemHealAmount, { u.addr, item }),
                              exp = M.staffExp(call, S, u.addr, i - 1), range = range }
        end
    end
    return out
end

-- The items in `u`'s inventory that heal their holder (a Vulnerary, an Elixir), in order:
-- { slot, item, amount }. A heal that is no staff (Board.staffRange, IA_STAFF): asking
-- CanUnitUseStaff instead would let through a staff its holder cannot use (no rank, asleep,
-- silenced: bmitem.c CanUnitUseStaff), which heals others, never its holder. `call` is a
-- sandbox's, `Board` the bound reader; s.mend and s.salve's one owner.
function M.selfHeals(Board, call, S, u)
    local out = {}
    for i, it in ipairs(u.items) do
        local amount = call(S.GetUnitItemHealAmount, { u.addr, itemOf(it) })
        if amount > 0 and Board.staffRange(itemOf(it)) == nil then
            out[#out + 1] = { slot = i - 1, item = itemOf(it), amount = amount }
        end
    end
    return out
end

local function s16(v) return v >= 0x8000 and v - 0x10000 or v end
local function s32(v) return v >= 0x80000000 and v - 0x100000000 or v end

-- What one use of an item costs, from its price `cost` at its full `uses` (GetItemCost on
-- GetItemMaxUses, bmitem.c), in gold (#642): 0 for an unbreakable item, which never wears out
-- (IA_UNBREAKABLE: GetItemAfterUse takes no use, and GetItemMaxUses reads 0xFF for it, a count
-- no breakable item has in data_items.c; GetItemCost then gives costPerUse alone, which would
-- read as a 255th of its price); its price over its uses (ItemData costPerUse) otherwise; nil
-- when the game gives it no price (costPerUse 0: a Sacred Twin, Excalibur).
M.UNBREAKABLE_USES = 0xFF
function M.usePriceOf(cost, uses)
    if uses == M.UNBREAKABLE_USES then return 0 end
    if not cost or cost <= 0 or not uses or uses <= 0 then return nil end
    return cost / uses
end

-- One side of a simulated exchange, as the forecast window shows it (bksel.c): hit, crit,
-- damage (the window's own sum: battleAttack less the other side's battleDefense, bksel.c
-- :233), how many blows (the proc's hit count for that side), and whether it is armed (a
-- weapon, or one that broke). Display only, for the logs: what an exchange DOES is `played`.
-- spendsMiss: the weapon spends a use on a miss too (bmbattle.c BattleGenerateHitEffects: a
-- use goes on a hit, or on every blow of an IA_MAGIC or IA_UNCOUNTERABLE weapon; #642).
-- unbreakable: the weapon never loses a use (IA_UNBREAKABLE, GetItemAfterUse). wearSlot: the
-- bag slot its uses come off (M.wearSlotOf).
M.SPENDS_MISS = 0x82   -- IA_MAGIC (1 << 1) | IA_UNCOUNTERABLE (1 << 7), include/bmitem.h
M.IA_UNBREAKABLE = 1 << 3
-- How a battle unit's weapon spends its uses (its weaponAttributes): spendsMiss, unbreakable,
-- and uses, the uses it had as the battle took it up (weaponBefore): no more can be spent.
function M.spendRule(mem, bu)
    local attributes = mem.u32(bu + BU.weaponAttributes)
    return { spendsMiss = (attributes & M.SPENDS_MISS) ~= 0,
             unbreakable = (attributes & M.IA_UNBREAKABLE) ~= 0,
             uses = mem.u16(bu + BU.weaponBefore) >> 8 }
end
function M.side(mem, me, other, proc, hitsAt)
    local dmg = s16(mem.u16(me + BU.attack)) - s16(mem.u16(other + BU.defense))
    local rule = M.spendRule(mem, me)
    return { hit = s16(mem.u16(me + BU.hit)), crit = s16(mem.u16(me + BU.crit)),
             spendsMiss = rule.spendsMiss, unbreakable = rule.unbreakable, uses = rule.uses,
             dmg = dmg > 0 and dmg or 0, hits = mem.s8(proc + hitsAt),
             armed = mem.u16(me + BU.weapon) ~= 0 or mem.s8(me + BU.weaponBroke) ~= 0,
             wearSlot = M.wearSlotOf(mem, me) }
end

-- The HP a battle unit lost in the simulation just run. A blow that petrifies ends the battle
-- as a death does (BattleGenerateHit), and a petrified unit is out of the fight, so the bot
-- counts it as every HP lost: our pricing, not the game's.
function M.lost(mem, bu)
    local initial = mem.s8(bu + BU.hpInitial)
    local status = mem.s8(bu + BU.statusOut)
    if status == STATUS_PETRIFY or status == STATUS_13 then return initial end
    return initial - mem.u8(bu + UNIT_HP)
end

-- The bag slot (0-based) whose item a battle unit's spent uses come off, or nil when they come
-- off none of its items (#644 review): BattleApplyUnitUpdates writes the battle's weapon back to
-- unit.items[weaponSlotIndex] only when canCounter. A ballista's strike
-- (SetBattleUnitWeaponBallista) sets canCounter FALSE and leaves weaponSlotIndex as the last
-- battle left it, so its slot names whatever item that battle used. A borrowed item's slot is
-- 0xFF (SetBattleUnitWeapon), past the bag: M.wear takes nothing there.
function M.wearSlotOf(mem, bu)
    if mem.s8(bu + BU.canCounter) == 0 then return nil end
    return mem.u8(bu + BU.weaponSlotIndex)
end

-- The uses the battle just run took off one battle unit's weapon (#644): BattleGenerateHitEffects
-- (bmbattle.c) spends them with GetItemAfterUse, from weaponBefore, the weapon as the battle took
-- it up (SetBattleUnitWeapon). A weapon that broke (weaponBroke) spent all it had; one the
-- battle set to 0 without breaking was never swung (out of range: SetBattleUnitWeapon) and
-- spent none. An unbreakable one keeps its uses, so it reads 0.
function M.worn(mem, bu)
    local before = mem.u16(bu + BU.weaponBefore) >> 8
    if mem.s8(bu + BU.weaponBroke) ~= 0 then return before end
    local after = mem.u16(bu + BU.weapon)
    if after == 0 then return 0 end
    return before - (after >> 8)
end

-- The uses each side's weapon spent in one played way, by the HP the target had lost when each
-- blow came (#644 review): { actor = { [lost] = uses }, target = { [lost] = uses } }. The way
-- was played at the target's own HP; an earlier blow of a plan can leave it on less, and there
-- its death comes sooner and the blows after it are never thrown (Planner.wearAt reads it so).
-- `hits` = the way's blows in order (Board.hits); `sides` = { actor, target }, each M.side's
-- (spendsMiss, unbreakable, uses; uses nil = no cap, as a wall's unbreakable side). As BattleGenerateHitEffects spends them: a use on a hit, or on any
-- blow of a weapon that spends on a miss, none of an IA_UNBREAKABLE one (GetItemAfterUse). The
-- target loses HP to the actor's hits, and to its own Devil Axe's (a devil blow strikes its own
-- wielder). A weapon spends no more than the uses it had (side.uses, M.spendRule): a Brave
-- weapon on its last use breaks on the round's first blow and still throws the second
-- (BattleGenerateRoundHits tests the weapon once per round; GetItemAfterUse of the broken 0 is
-- 0), which lands and costs nothing (vanilla Ch19, campaign 4006, #684). `worn` = { actor,
-- target }: the uses the game took (M.worn). This reading of the hit array must count the
-- same, else it is wrong and fails loudly. Pure.
function M.wornBy(hits, sides, worn)
    local out, spent, lost = { actor = {}, target = {} }, { actor = 0, target = 0 }, 0
    for _, h in ipairs(hits) do
        local side = sides[h.by]
        if not side.unbreakable and (not h.miss or side.spendsMiss)
                and (side.uses == nil or spent[h.by] < side.uses) then
            out[h.by][lost] = (out[h.by][lost] or 0) + 1
            spent[h.by] = spent[h.by] + 1
        end
        if not h.miss and (h.by == "actor") ~= (h.devil == true) then lost = lost + h.dmg end
    end
    for _, by in ipairs({ "actor", "target" }) do
        if spent[by] ~= worn[by] then
            error(string.format("sight: the hit array reads %d uses spent by the %s, the game "
                .. "took %d (weaponBefore less weapon)", spent[by], by, worn[by]))
        end
    end
    return out
end

-- The chance one of the game's rolls passes (rng.c): Roll1RN draws one NextRN_100, Roll2RN
-- the floor of two draws' mean, and passes below the threshold; NextRN_100 is NextRN() * 100
-- / 0x10000. The game has no function for a roll's odds (ADR 0377, reason 1): this counts
-- them over every 16-bit NextRN, each taken as equally likely. `threshold` is the u16 the
-- BattleRoll functions take.
-- ODDS[n][t]: a roll of `n` draws passing at threshold t (0..100), built once: draw[k] counts
-- the NextRN values whose NextRN_100 is k, and Roll2RN's floor((a + b) / 2) < t is a + b < 2t,
-- so its odds are a prefix sum over the pair sums' counts.
local ODDS
local function buildOdds()
    local draw, pairs2 = {}, {}
    for k = 0, 99 do draw[k] = 0 end
    for v = 0, 0xFFFF do
        local k = v * 100 // 0x10000
        draw[k] = draw[k] + 1
    end
    for sum = 0, 199 do pairs2[sum] = 0 end
    for a = 0, 99 do
        for b = 0, 99 do pairs2[a + b] = pairs2[a + b] + draw[a] * draw[b] end
    end
    local one, two = { [0] = 0 }, { [0] = 0 }
    local n1, n2 = 0, 0
    for t = 1, 100 do
        n1 = n1 + draw[t - 1]
        n2 = n2 + pairs2[2 * t - 2] + pairs2[2 * t - 1]
        one[t], two[t] = n1 / 0x10000, n2 / 0x100000000
    end
    return { one, two }
end
function M.rollChance(numbers, threshold)
    if threshold >= 100 then return 1 end
    if threshold <= 0 then return 0 end
    ODDS = ODDS or buildOdds()
    return ODDS[numbers][threshold]
end

-- An exchange's played outcomes (`leaves`: { p, dealt, back }, each the HP one side lost) as
-- two distributions { [hp lost] = probability }: the target's (dealt) and the actor's (back),
-- and the two together (joint: { { p, dealt, back } }, one per pair that can happen, in
-- dealt-then-back order): whether a counter lands depends on whether our blow killed first,
-- and the planner plays the enemy phase on each pair (T100b). wear = { actor, target,
-- actorAt, targetAt }: the weapon uses each side is expected to spend, over the same ways (a
-- leaf's `wear` and `counterWear`, M.worn's; a leaf without them spent none), and the same by
-- the HP the target had lost when each blow came (a leaf's `wornAt`, M.wornBy's), #644.
function M.exchangeOf(leaves)
    local dealt, back, pair = {}, {}, {}
    local wear = { actor = 0, target = 0, actorAt = {}, targetAt = {} }
    for _, l in ipairs(leaves) do
        dealt[l.dealt] = (dealt[l.dealt] or 0) + l.p
        back[l.back] = (back[l.back] or 0) + l.p
        wear.actor = wear.actor + l.p * (l.wear or 0)
        wear.target = wear.target + l.p * (l.counterWear or 0)
        for by, at in pairs({ actor = wear.actorAt, target = wear.targetAt }) do
            for lost, n in pairs(l.wornAt and l.wornAt[by] or {}) do
                at[lost] = (at[lost] or 0) + l.p * n
            end
        end
        local k = l.dealt .. ":" .. l.back
        pair[k] = pair[k] or { p = 0, dealt = l.dealt, back = l.back }
        pair[k].p = pair[k].p + l.p
    end
    local joint = {}
    for _, x in pairs(pair) do joint[#joint + 1] = x end
    table.sort(joint, function(a, b)
        if a.dealt ~= b.dealt then return a.dealt < b.dealt end
        return a.back < b.back
    end)
    return dealt, back, joint, wear
end

-- What the exchange just simulated teaches one side of it, by the game's own count
-- (GetBattleUnitExpGain, bmbattle.c: BattleApplyExpGains awards it to both sides after a real
-- battle; a simulation never calls it): `side` "actor" (our attack) or "target" (our unit an
-- enemy strikes, its counter's), its experience when its blows deal nothing, when they deal
-- damage, and when they kill. The count tells the three apart by two fields only, the side's
-- nonZeroDamage and the other's HP (the Unit sits at +00 of a battle unit, so its curHP is
-- UNIT_HP there too), so each read sets those two on the simulation's battle units, the side
-- alive: a dead one gains nothing, which the planner reads off the exchange's ways. Which of
-- the three a plan gets is the planner's, at the HPs the plan leaves. Inside a sandbox, on the
-- plain simulation (ADR 0414).
function M.expOf(api, call, S, side)
    local me, them = S.gBattleActor, S.gBattleTarget
    if side == "target" then me, them = them, me end
    api.write8(me + UNIT_HP, 1)
    local function count(damaged, hp)
        api.write8(me + BU.nonZeroDamage, damaged)
        api.write8(them + UNIT_HP, hp)
        return call(S.GetBattleUnitExpGain, { me, them })
    end
    return { none = count(0, 1), hit = count(1, 1), kill = count(1, 0) }
end

-- The experience a heal with the staff in item `slot` teaches the unit at `addr`, by the game's
-- own count (GetBattleUnitStaffExp, bmbattle.c: 10 + the staff's cost per use / 20, halved once
-- promoted, 0 for a unit that cannot gain levels), on the battle unit the Staff command sets up
-- (BattleInitItemEffect). The count's 1 for a miss never applies to a heal: the setup clears
-- the blows (ClearBattleHits) and a heal rolls none. Inside a sandbox (ADR 0414).
function M.staffExp(call, S, addr, slot)
    call(S.BattleInitItemEffect, { addr, slot })
    return call(S.GetBattleUnitStaffExp, { S.gBattleActor })
end

-- An exchange's played results, kept by its battle key (`memo`: key -> { dealt, back, joint,
-- exp }): `play()` makes the first three on a miss, and `count()` (M.expOf) the fourth for a
-- `teaches` read whenever the entry lacks it, so an entry a non-teaching read (an enemy's
-- strike) made first is filled in, and none is ever cleared. The count runs first: both are
-- called on the plain simulation the key was read from, and the played ways leave the last
-- way's battle units behind. The count leaves the battle units written (its cases' fields);
-- the sandbox puts them back, and no caller reads them after an exchange. Pure.
function M.known(memo, key, teaches, count, play)
    local known = memo[key]
    -- the count is one side's: a key read for the other side is a broken assumption (the key's
    -- actor decides the side), never a count to hand back
    assert(not (teaches and known and known.side and known.side ~= teaches),
           "sight: one battle key read for both sides' experience")
    local exp = known and known[4]
    if teaches and not exp then exp = count() end
    if not known then
        known = play()
        memo[key] = known
    end
    if exp then known[4], known.side = exp, known.side or teaches end
    return known
end

-- Every way one exchange can go, as the game plays it (ADR 0377): `sim` ({ addr, args }:
-- BattleGenerateSimulation or its ballista twin) is run again and again, each roll it makes caught
-- at S.BattleRoll1RN/S.BattleRoll2RN's entry (M.withBreaks) and its simResult (r1, which a
-- simulation returns in place of rolling) forced, depth first: pass where it can, then fail. A roll
-- that cannot go the other way (threshold 0, or 100 and up) is not split. `lost()` -> the HP the
-- target and the actor lost in the run just made, then the weapon uses the actor and the target
-- spent in it (M.worn) and the same by the target's HP lost (M.wornBy); all optional.
-- -> { { p, dealt, back, wear, counterWear, wornAt } }. Inside a sandbox; the breakpoints are
-- set only for these calls (mGBA steps while one is set).
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
    local leaves = {}
    M.withBreaks(cpu, { { S.BattleRoll1RN, catch(1) }, { S.BattleRoll2RN, catch(2) } }, function()
        local split
        repeat
            at = 0
            call(sim[1], sim[2])
            local p = 1
            for i = 1, at do p = p * (path[i] and odds[i] or 1 - odds[i]) end
            local dealt, back, wear, counterWear, wornAt = lost()
            leaves[#leaves + 1] = { p = p, dealt = dealt, back = back, wear = wear,
                                    counterWear = counterWear, wornAt = wornAt }
            -- the next outcome: the deepest roll forced to pass that can also fail
            split = at
            while split > 0 and not (path[split] and odds[split] < 1) do split = split - 1 end
            for i = split + 1, #path do path[i], odds[i] = nil, nil end
            if split > 0 then path[split] = false end
        until split == 0
    end)
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
-- damage it is expected to deal; counterWorst: the most the counter can take off our unit
-- (nothing when `e` cannot answer, or dies before it can). Pure, so test_sight.lua builds
-- every case.
function M.attackOf(ours, eHp, uHp)
    local c = ours.counter
    local counters = c.armed and c.hits > 0
    local kill, expected = M.odds({ ours.dealt }, eHp)
    -- wear: the weapon uses the attack is expected to spend, as the game's played ways spent
    -- them (M.worn, exchangeOf; #644), at the target's own HP; wearAt the same by the HP the
    -- target had lost when each blow came (M.wornBy), wearSlot the bag slot they come off
    -- (M.wearSlotOf). #642's price and #644's phase both read it (ADR 0423's 2026-11-18 note).
    -- counterWear / counterWearAt / counterSlot: the same for the target's counter.
    return { hit = ours.hit, dmg = ours.dmg, crit = ours.crit, hits = ours.hits,
             spendsMiss = ours.spendsMiss, wear = ours.wear or 0, wearAt = ours.wearAt,
             wearSlot = ours.wearSlot, counterWear = c.wear or 0, counterWearAt = c.wearAt,
             counterSlot = c.wearSlot, counters = counters,
             counterHit = counters and c.hit or 0, counterDmg = counters and c.dmg or 0,
             counterCrit = counters and c.crit or 0, counterHits = counters and c.hits or 0,
             killsTarget = ours.killsTarget, dealt = ours.dealt, counterDist = ours.back,
             joint = ours.joint, exp = ours.exp,
             kill = kill, die = (M.odds({ ours.back }, uHp)), sure = M.least(ours.dealt) >= eHp,
             expected = expected, counterWorst = M.worst(ours.back) }
end

-- The army's reply's kills (sight.nextPhase with `reply`; #510 comment 6906859807): options =
-- { { unit, enemy, tile, p } }, every kill one of our units can make from a free tile it
-- reaches, p its chance. A kill at even odds or better is made, as the lookahead's own line
-- has a striker our counter kills at even odds gone: the likeliest first, one act a unit, one
-- death an enemy, one unit a tile. -> the kills made, in that order. Pure.
function M.replyKills(options)
    local sure = {}
    for _, o in ipairs(options) do
        if o.p >= 0.5 then sure[#sure + 1] = o end
    end
    table.sort(sure, function(a, b)
        if a.p ~= b.p then return a.p > b.p end
        if a.unit ~= b.unit then return a.unit < b.unit end
        if a.enemy ~= b.enemy then return a.enemy < b.enemy end
        if a.tile.y ~= b.tile.y then return a.tile.y < b.tile.y end
        return a.tile.x < b.tile.x
    end)
    local acted, dead, taken, out = {}, {}, {}, {}
    for _, o in ipairs(sure) do
        local at = o.tile.x .. "," .. o.tile.y
        if not acted[o.unit] and not dead[o.enemy] and not taken[at] then
            acted[o.unit], dead[o.enemy], taken[at] = true, true, true
            out[#out + 1] = o
        end
    end
    return out
end

-- The army's reply's step for a unit that kills nothing: the tile of `tiles` the fewest
-- enemies reach (`danger(x, y)`), its own tile `at` on a tie, then the nearest, then the first
-- in `tiles`. nil when `tiles` is empty. Pure.
function M.safest(tiles, danger, at)
    local best, bestDanger, bestDist
    for _, t in ipairs(tiles) do
        local d = danger(t.x, t.y)
        local dist = math.abs(t.x - at.x) + math.abs(t.y - at.y)
        if not best or d < bestDanger or (d == bestDanger and dist < bestDist) then
            best, bestDanger, bestDist = t, d, dist
        end
    end
    return best
end

-- A judged phase's strike by enemy `id` on unit `target` (strikeOf's, `side` its simulation),
-- played at the HPs the phase had left when it came: strikerHp / targetHp, which its exchange's
-- ways were simulated at, felled the chance our counter kills the striker, and targetLevel the
-- target's level (the board's), the one its count (`taught`) was read at: a level-up since
-- changes the count. Pure.
function M.strikeAt(side, id, target, strikerHp, targetHp, level)
    local t = M.strikeOf(side)
    t.enemy, t.target = id, target
    t.strikerHp, t.targetHp, t.targetLevel = strikerHp, targetHp, level
    t.felled = (M.odds({ t.counterDist }, t.strikerHp))
    return t
end

-- The enemy's strike read off its simulation, or none (nil) when its AI does not strike:
-- taken* as the window shows it, takenDist what it takes off our unit (takenWorst: the most),
-- counterDist what our counter takes off it; joint the two together (exchangeOf's, dealt =
-- what it takes off our unit, back = what our counter takes off it); taught our unit's count
-- (expOf's, its side "target"), nil when the target is no player unit.
function M.strikeOf(t)
    local dealt = t and t.dealt or { [0] = 1 }
    return { takenHit = t and t.armed and t.hit or 0, takenDmg = t and t.dmg or 0,
             takenCrit = t and t.crit or 0, takenHits = t and t.hits or 0,
             takenSlot = t and t.slot or nil, takenTile = t and t.tile or nil,
             takenDist = dealt, takenWorst = M.worst(dealt),
             counterDist = t and t.back or { [0] = 1 },
             joint = t and t.joint or nil, taught = t and t.exp or nil,
             wear = t and t.wear or 0, wearSlot = t and t.wearSlot or nil,
             counterWear = t and t.counter and t.counter.wear or 0,
             counterSlot = t and t.counter and t.counter.wearSlot or nil }
end

-- Whether our attack ANSWERS its target, and how hard: the game's own simulation kills it
-- and no way the exchange can go kills our unit; strength = the damage it is expected to deal
-- (capped at the target's HP).
-- Pure.
function M.answerOf(a, hp)
    return a.killsTarget and a.counterWorst < hp, a.expected
end

-- Whether a lock tile (command `c`, the terrain `terrain` on it now) is one a key may still be
-- needed for: still shut (a full chest, a closed door), and some fielded unit in `blues` has a
-- march path to it (`turnsTo` is not nil: sight's, the game's costs; the cost itself, so how many
-- turns, is not read). With no unit on the map nothing is known to be out of reach, so every shut
-- lock counts. A lock behind another lock has no path and is not counted: its key is the
-- mid-map fetch's (bot.lua supplyKey).
function M.lockNeeded(c, terrain, blues, turnsTo)
    if terrain ~= M.LOCK_TERRAIN[M.LOCK_KIND[c.cmd]] then return false end
    if #blues == 0 then return true end
    for _, u in ipairs(blues) do
        if turnsTo(u, { x = c.x, y = c.y }) then return true end
    end
    return false
end

-- What the map asks of a team, for Bot.team (#510 plan comment, "Party selection"). Pure, so
-- test_sight.lua builds every case. units = Board.read's; commands = {{ x, y, cmd }...} the
-- chapter's tile commands; fog = gPlaySt.chapterVisionRange. One demand per red class on the
-- field (need = how many stand there, rep = the first), one per village tile, one for chests
-- and one for doors when there are any, fog when the chapter has it, and sustain always. A lock
-- demand's `need` is the openers the team seats; its `locks` the tiles a key may still be needed
-- for (#711), those `needed(command)` accepts (default: all), so a door nobody can reach does
-- not pull a spare key into a bag.
-- `freeTalks` (M.freeTalks) adds one `talk` demand per recruit a unit may bring over for free:
-- answered only by those talkers, so Bot.team seats one of them (#699).
function M.demandsOf(units, commands, fog, freeTalks, needed)
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
    local kinds = M.LOCK_KIND
    for _, c in ipairs(commands) do
        if c.cmd == M.TILE_COMMAND_VISIT then
            out[#out + 1] = { id = string.format("village:%d,%d", c.x, c.y), kind = "village",
                              need = 1, tile = { x = c.x, y = c.y } }
        elseif kinds[c.cmd] then
            -- `need` is the openers the team seats (one opener opens every lock); `locks` is the
            -- tiles to open, one key each (Bot.supply's takeKeys, #711)
            if not once[c.cmd] then
                once[c.cmd] = { id = kinds[c.cmd], kind = kinds[c.cmd], need = 1, locks = 0 }
                out[#out + 1] = once[c.cmd]
            end
            if not needed or needed(c) then once[c.cmd].locks = once[c.cmd].locks + 1 end
        end
    end
    if fog > 0 then out[#out + 1] = { id = "fog", kind = "fog", need = 1 } end
    local recruits = {}
    for recruit in pairs(freeTalks or {}) do recruits[#recruits + 1] = recruit end
    table.sort(recruits)
    for _, recruit in ipairs(recruits) do
        -- a list: the demand goes into the run's record, whose objects take string keys only
        local talkers = {}
        for talker in pairs(freeTalks[recruit]) do talkers[#talkers + 1] = talker end
        table.sort(talkers)
        out[#out + 1] = { id = string.format("talk:%d", recruit), kind = "talk", need = 1,
                          talkers = talkers }
    end
    out[#out + 1] = { id = "sustain", kind = "sustain", need = 1 }
    return out
end

-- The walk of an event script's bytes (callsScript, scriptEffects): `visit(at, cmd, sub)` is
-- called for each command, in order, and the walk stops early when it returns true (walkScript
-- then returns true). A CALL or ENQUEUE_CALL (the script pointer at +4 either way) is visited
-- and then walked into, so a called script's commands come in place and a visitor's own state
-- (the slot 2 SVAL set before a CALL) holds through it: Eirika's E_14 talk reaches the paid-recruit
-- script through a second CALL. A command's length is its first halfword's second nibble, in
-- halfwords (event.c), its label the halfword after it (EvtLabel, EvtGoto, EvtBEQ...).
-- The bytecode is linear and a GOTO or branch can jump over an END to a CALL behind a later
-- LABEL, so an END stops the walk only when every label a GOTO/branch named is already behind it.
-- Bounded: EV_SCRIPT_LIMIT commands a script, and a pointer is followed only inside the ROM
-- (a script in RAM, or garbage, is not read). `opts`: { memo = true } walks each script once
-- (a visitor with no state between CALLs, callsScript: a diamond of CALLs is then linear, not
-- exponential), { budget = n } stops the walk after n commands in all (a visitor with state, as
-- scriptEffects' slot 2, walks a script CALLed twice twice, so its total is bounded instead).
-- walkScript returns (stopped, truncated): `truncated` is true when the budget ended a walk.
-- Without memo the scripts being walked are a stack that guards a loop. Branches are not
-- evaluated: every command the bytes reach linearly is visited. Pure over mem.
-- Every ENQUEUE_CALL is followed, whatever its subcommand: an enqueued paid script reads as paid,
-- which only withholds a free-talker demand, never adds a wrong one.
local EV_CMD_LABEL, EV_CMD_GOTO, EV_CMD_CALL, EV_CMD_ENQUEUE_CALL, EV_CMD_BRANCH, EV_CMD_END =
    0x08, 0x09, 0x0A, 0x0B, 0x0C, 0x01
M.EV_SCRIPT_LIMIT = 512
M.EV_WALK_BUDGET = 8 * M.EV_SCRIPT_LIMIT
-- the cartridge ROM is the 32MB the GBA maps at 0x08 and 0x09 (top byte), so `ptr >> 25 == 4`
local ROM_REGION, ROM_SHIFT = 4, 25
function M.walkScript(mem, script, visit, opts)
    opts = opts or {}
    local stack, left, truncated = {}, opts.budget or math.huge, false
    local done = opts.memo and {} or nil
    local function walk(from)
        if from >> ROM_SHIFT ~= ROM_REGION or stack[from] or (done and done[from]) then return false end
        stack[from] = true
        if done then done[from] = true end
        local at, reached, wanted, stopped = from, {}, {}, false
        for _ = 1, M.EV_SCRIPT_LIMIT do
            local head = mem.u16(at)
            local cmd, len = head >> 8, (head >> 4) & 0xF
            if len == 0 then break end
            if left <= 0 then truncated = true; break end
            left = left - 1
            if visit(at, cmd, head & 0xF) then stopped = true; break end
            if cmd == EV_CMD_LABEL then
                reached[mem.u16(at + 2)] = true
            elseif cmd == EV_CMD_GOTO or cmd == EV_CMD_BRANCH then
                wanted[mem.u16(at + 2)] = true
            elseif cmd == EV_CMD_CALL or cmd == EV_CMD_ENQUEUE_CALL then
                if walk(mem.u32(at + 4)) then stopped = true; break end
            elseif cmd == EV_CMD_END then
                local ahead = false
                for label in pairs(wanted) do
                    if not reached[label] then ahead = true end
                end
                if not ahead then break end
            end
            at = at + len * 2
        end
        stack[from] = nil
        return stopped
    end
    local stopped = walk(script)
    return stopped, truncated
end

-- Whether the event script at `script` CALLs `target` (EV_CMD_CALL or EV_CMD_ENQUEUE_CALL),
-- through the CALLs of its own (M.walkScript's walk, each script once).
function M.callsScript(mem, script, target)
    if script == target then return true end
    return M.walkScript(mem, script, function(at, cmd)
        return (cmd == EV_CMD_CALL or cmd == EV_CMD_ENQUEUE_CALL) and mem.u32(at + 4) == target
    end, { memo = true })
end

-- What an event script does to the field's units, read from its bytes (#724): the units it loads
-- and the ones it removes. -> { loads = { { charId, x, y } }, removals = { charId }, truncated }.
-- Encodings (include/eventscript.h, src/eventscr.c): a command's head halfword is cmd << 8 | len
-- << 4 | sub (_EvtCmd, eventscript.h:570); SVAL (EvtSetSlot, :591) is slot at +2 and a u32 at +4;
-- LOAD1-3 (EvtLoadUnit1.., :687, sub 0-2) is a UnitDefinition array at +4, and a pointer < 0
-- means slot 2 (Event2C_LoadUnits, eventscr.c:2797); LOADSINGLEUNIT (:722, Event32_SpawnSingleUnit,
-- eventscr.c:3128) is the allegiance in sub, the char at +2 (-3: slot 2), x and y bytes at +4, +5;
-- CHANGESTATE (EvtKillUnit/EvtRemoveUnit, :720-723, Event34_MessWithUnitState) sub 0xD KILL or
-- 0xF DISA is the char at +2. DISA_IF (0xE, EvtWaitUnitDeathFade) is not counted: it waits for a
-- death fade a script began, not a removal of its own. A UnitDefinition (bmunit.h:195) is 0x14
-- bytes, an array ends at charIndex 0 (GetLoadUnitsAmount), x is the 6 bits and y the next 6 of
-- the halfword at +4. A LOAD1-3 load also carries its definition (`def`, its address) and
-- whether it loads an enemy (`red`: allegiance 2, the bits 1-2 of +3), for s.arrivalUnits.
-- Slot 2 is tracked by the walk through its CALLs (SVAL slot 2 then CALL(EventScr_LoadReinforce),
-- LOAD1(1, -1)). A unit the script loads AND removes (a cutscene cast) is no removal of the
-- field's: the removal is dropped. An ESTIMATE: the script's guards (CHECK_ALIVE,
-- CHECK_ALLEGIANCE, a flag) are not evaluated, so a removal that only holds for a unit in some
-- state reads as always; a REDA walks a loaded unit off the tile read; LOAD_PRECONF's
-- SETCOUNT and SETCHANCE (eventscript.h:451-453) are not read, so an array is loaded whole. The
-- walk is bounded to M.EV_WALK_BUDGET commands in all: a read the budget cut short has
-- `truncated = true` and is an estimate of less than the script does. Pure over mem.
local EV_CMD_SVAL, EV_CMD_LOADUNIT, EV_CMD_LOADSINGLEUNIT, EV_CMD_CHANGESTATE =
    0x05, 0x2C, 0x32, 0x34
local EVSUB_KILL, EVSUB_DISA, EVENT_SLOT_2 = 0xD, 0xF, 2
local UDEF_SIZE, UDEF_LIMIT = 0x14, 64
local MAP_COORD_LIMIT = 64   -- x and y are 6-bit fields in a UnitDefinition; a byte's 7th bit is a sign
-- A UnitDefinition's allegiance (bmunit.h:202: the 2 bits above autolevel in +3): 0 blue, 1
-- green, 2 red (LoadUnit's switch, bmunit.c:586)
local UDEF_RED = 2
function M.udefAllegiance(byte3) return (byte3 >> 1) & 3 end
function M.scriptEffects(mem, script)
    local loads, removed, slot2 = {}, {}, 0
    local _, truncated = M.walkScript(mem, script, function(at, cmd, sub)
        if cmd == EV_CMD_SVAL then
            if mem.u16(at + 2) == EVENT_SLOT_2 then slot2 = mem.u32(at + 4) end
        elseif cmd == EV_CMD_LOADUNIT and sub <= 2 then
            local ud = mem.u32(at + 4)
            if ud >= 0x80000000 then ud = slot2 end
            if ud >> ROM_SHIFT == ROM_REGION then
                for i = 0, UDEF_LIMIT - 1 do
                    local d = ud + i * UDEF_SIZE
                    if mem.u8(d) == 0 then break end
                    local xy = mem.u16(d + 4)
                    loads[#loads + 1] = { charId = mem.u8(d), x = xy & 0x3F, y = (xy >> 6) & 0x3F,
                                          def = d, red = M.udefAllegiance(mem.u8(d + 3)) == UDEF_RED }
                end
            end
        elseif cmd == EV_CMD_LOADSINGLEUNIT then
            local pid = mem.u16(at + 2)
            if pid == 0xFFFD then pid = slot2 end
            local x, y = mem.u8(at + 4), mem.u8(at + 5)
            if pid > 0 and pid < 0x100 and x < MAP_COORD_LIMIT and y < MAP_COORD_LIMIT then
                loads[#loads + 1] = { charId = pid, x = x, y = y }
            end
        elseif cmd == EV_CMD_CHANGESTATE and (sub == EVSUB_KILL or sub == EVSUB_DISA) then
            local pid = mem.u16(at + 2)
            if pid > 0 and pid < 0x100 then removed[#removed + 1] = pid end
        end
        return false
    end, { budget = M.EV_WALK_BUDGET })
    local cast = {}
    for _, l in ipairs(loads) do cast[l.charId] = true end
    local removals = {}
    for _, c in ipairs(removed) do
        if not cast[c] then removals[#removals + 1] = c end
    end
    return { loads = loads, removals = removals, truncated = truncated }
end

-- The AI changes an event script makes, read from its bytes (#712): the units it switches to
-- another AI. -> { changes = { { charId, ai1, ai2 } }, positional, truncated }, in script order.
-- Encodings: CHAI (EvtChangeAI, include/eventscript.h:729, EV_CMD_CHANGEAI 0x39) is the char at +2
-- (a negative one: slot 2) and the AI in slot 1, ai1 its low byte and ai2 the next
-- (Event39_ChangeAiScript, eventscr.c:3604-3623 -> ChangeAiForCharacter, eventscr3.c:61: every
-- unit of that character in the green and red factions). SVAL (slot at +2, a u32 at +4) is tracked
-- through the walk's CALLs as scriptEffects tracks slot 2. CHAI_AT (sub 1, EvtChangeAIat :730)
-- takes its units from a queue and a position slot the script fills (vanilla E_10's and E_14's
-- AREA scripts, through EventScr_ChangeAIinQueue, events_script_utils.c:523): `positional` counts
-- them, none is read. An ESTIMATE as scriptEffects is: guards are not evaluated (the
-- UnTriggerIfNotFaction call at the head of an AREA script ends it for a unit not of the
-- faction it names, and the player's units are the ones asked). Pure over mem.
local EV_CMD_CHANGEAI, EVSUB_CHAI_AT, EVENT_SLOT_1 = 0x39, 1, 1
function M.scriptAiChanges(mem, script)
    local changes, positional, slot1, slot2 = {}, 0, 0, 0
    local _, truncated = M.walkScript(mem, script, function(at, cmd, sub)
        if cmd == EV_CMD_SVAL then
            local slot = mem.u16(at + 2)
            if slot == EVENT_SLOT_1 then slot1 = mem.u32(at + 4)
            elseif slot == EVENT_SLOT_2 then slot2 = mem.u32(at + 4) end
        elseif cmd == EV_CMD_CHANGEAI then
            if sub == EVSUB_CHAI_AT then
                positional = positional + 1
            else
                local pid = mem.u16(at + 2)
                if pid >= 0x8000 then pid = slot2 end
                changes[#changes + 1] = { charId = pid & 0xFF, ai1 = slot1 & 0xFF,
                                          ai2 = (slot1 >> 8) & 0xFF }
            end
        end
        return false
    end, { budget = M.EV_WALK_BUDGET })
    return { changes = changes, positional = positional, truncated = truncated }
end

-- The turn events' effects (M.scriptEffects of each, in the order the game offers them: `events`
-- = { { turn, boardTurn, eventTurn, loads, removals, truncated } }) as s.scriptedUnits' answer:
-- { arrivals = { { charId, x, y, turn, boardTurn, eventTurn, def, red } }, removals = { [charId] =
-- boardTurn }, truncated }. `eventTurn` is the turn the event itself runs on (its phase may be
-- the enemy's, so the unit acts on that turn; nil in `events`: the boardTurn); `def` and `red`
-- are the load's own (M.scriptEffects). A unit's earliest removal is
-- kept, and a removal at or before the unit's earliest arrival is dropped: a cast loaded in one
-- event and removed in an earlier or the same one was never a unit of the field. Pure.
function M.foldScripted(events)
    local out, first = { arrivals = {}, removals = {} }, {}
    for _, e in ipairs(events) do
        out.truncated = out.truncated or e.truncated
        for _, l in ipairs(e.loads) do
            out.arrivals[#out.arrivals + 1] = { charId = l.charId, x = l.x, y = l.y, turn = e.turn,
                                                boardTurn = e.boardTurn,
                                                eventTurn = e.eventTurn or e.boardTurn,
                                                def = l.def, red = l.red }
            first[l.charId] = math.min(first[l.charId] or e.boardTurn, e.boardTurn)
        end
    end
    for _, e in ipairs(events) do
        for _, c in ipairs(e.removals) do
            if e.boardTurn > (first[c] or 0) then
                out.removals[c] = math.min(out.removals[c] or e.boardTurn, e.boardTurn)
            end
        end
    end
    return out
end

-- The recruits a unit brings over for FREE: of `talks` (M.recruitTalks), the talks to a unit not
-- yet in the party (`joined`, a set of charIds) whose script never reaches the paid-recruit
-- script `paid` (common-events.h EventScr_9EEB00: it asks the price; E_14's Eirika and Rennac).
-- The game marks no talk free or paid, so the script is read. a = 0 is anyone: no demand.
-- -> { [recruit] = { [talker] = true } }
function M.freeTalks(mem, talks, paid, joined)
    local out = {}
    for _, t in ipairs(talks) do
        if t.a ~= 0 and not (joined or {})[t.b] and not M.callsScript(mem, t.script, paid) then
            out[t.b] = out[t.b] or {}
            out[t.b][t.a] = true
        end
    end
    return out
end

-- Turns left on a Defense map on turn `turn`: End - turn. FE8 has no function for it: the goal
-- window does the same sum inline, drawing "turn / goalWindowEndTurnNumber - 1" and "Last Turn"
-- from End - 1 on (player_interface.c). Pure.
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
-- Whether AI script `index` loots (AiScriptCmd_10_DoLooting): table[0][index] holds
-- AI_CMD_PILLAGE before the GOTO that loops it. `scripts` = gpAi1Table's or gpAi2Table's
-- address (cp_data.c: vanilla's looters are AI2 0x04 and 0x05, PillageThen*).
function M.loots(mem, scripts, index)
    local at = mem.u32(mem.u32(scripts) + index * 4)
    for i = 0, M.AI_SCR_MAX - 1 do
        local cmd = mem.u8(at + i * M.AI_SCR_SIZE)
        if cmd == M.AI_CMD_PILLAGE then return true end
        if cmd == M.AI_CMD_GOTO then return false end
    end
    return false
end

-- Whether an enemy's AI script (gpAi1Table's or gpAi2Table's address `scripts`, index `index`)
-- can decide on anything outside its own reach, for the bot's strike memo (bot.lua strikeKey,
-- ADR 0431): the strike is the unit's whole decision, so a step that runs before the combat
-- step can pre-empt it, and the memo keys the reds such a step reads.
-- Read off cp_script.c's commands, each classed by what it reads of a red (an ally):
--   * neutral: conditional (its left side is a counter or a result of a function call, and
--     any call is `unsafe`), goto, label, nop, the staff actions (a unit with a staff is whole-
--     board anyway, bot.lua), the no-ops;
--   * an action (05, 07): AiAttemptOffensiveAction reads only the units it may attack and, for a
--     thief, the tiles beside them, all within the unit's movement and weapon range;
--   * a move (0C, 0D, 0F, 10, 11, 12, 13, 16-1A): tile occupancy anywhere on the map (a looter
--     walks 0x7c, a march picks the free tile nearest its goal). It pre-empts a strike only when
--     it runs before the action: after one that always runs (chance 99+: NextRN_N(100) <= it)
--     it is reached only when the action found nothing, so the strike is nil either way;
--   * unsafe: a function call (01: a leader's script, a summon, a unit looked up by id), a
--     script change (02), an action on a character or a class (04, 08), a command the game does
--     not know. Any of them reachable = true.
-- A script with no action step cannot produce a strike at all. The walk follows every branch
-- (a conditional's label and its fall-through), and an unreadable one (a label that is not
-- there, a script past M.AI_SCR_LIMIT commands) counts as reading.
M.AI_SCR_LIMIT = 64
local SCRIPT_CMD = { neutral = {}, action = { [0x05] = true, [0x07] = true }, move = {} }
for _, c in ipairs({ 0x00, 0x03, 0x06, 0x09, 0x0A, 0x0B, 0x0E, 0x14, 0x15, 0x1B, 0x1C }) do
    SCRIPT_CMD.neutral[c] = true
end
for _, c in ipairs({ 0x0C, 0x0D, 0x0F, 0x10, 0x11, 0x12, 0x13, 0x16, 0x17, 0x18, 0x19, 0x1A }) do
    SCRIPT_CMD.move[c] = true
end
function M.scriptReadsReds(mem, scripts, index)
    local base = mem.u32(mem.u32(scripts) + index * 4)
    local function field(i, off) return mem.u8(base + i * M.AI_SCR_SIZE + off) end
    -- the commands that can run after command `i`; nil when a label is not there
    local function after(i)
        local cmd, target = field(i, 0), field(i, 3)
        if cmd ~= 0x03 and cmd ~= 0x00 then return { i + 1 } end
        local jump = 0   -- a label id of 0 starts the script over (AiScriptCmd_03_Goto)
        if target ~= 0 then
            jump = nil
            for j = 0, M.AI_SCR_LIMIT - 1 do
                if field(j, 0) == 0x1C and field(j, 3) == target then jump = j + 1; break end
            end
        end
        if jump == nil then return nil end
        if cmd == 0x03 then return { jump } end
        return { i + 1, jump }
    end
    -- every command the script can reach, and whether one of them is an action
    local reach, queue, hasAction = {}, { 0 }, false
    while #queue > 0 do
        local i = table.remove(queue)
        if not reach[i] then
            if i >= M.AI_SCR_LIMIT then return true end
            reach[i] = true
            local cmd = field(i, 0)
            if SCRIPT_CMD.action[cmd] then hasAction = true
            elseif not SCRIPT_CMD.neutral[cmd] and not SCRIPT_CMD.move[cmd] then return true end
            local nexts = after(i)
            if not nexts then return true end
            for _, n in ipairs(nexts) do queue[#queue + 1] = n end
        end
    end
    if not hasAction then return false end
    -- a move is harmless once an action that always runs has found nothing
    local seen, stack = {}, { { 0, false } }
    while #stack > 0 do
        local top = table.remove(stack)
        local i, acted = top[1], top[2]
        local k = i * 2 + (acted and 1 or 0)
        if not seen[k] then
            seen[k] = true
            local cmd = field(i, 0)
            if SCRIPT_CMD.move[cmd] and not acted then return true end
            if SCRIPT_CMD.action[cmd] and field(i, 1) >= 99 then acted = true end
            for _, n in ipairs(after(i)) do stack[#stack + 1] = { n, acted } end
        end
    end
    return false
end

-- Whether a looter with `items` (ids) and class `attributes` takes chests as well as villages:
-- AiGetChestUnlockItemSlot (cp_utility.c) -- a Chest Key, or a Lockpick on a CA_STEAL class;
-- a full bag (`capacity` items: Board.ITEM_COUNT) takes nothing (it flags the unit to escape
-- instead).
function M.opensChests(items, attributes, capacity)
    if #items >= capacity then return false end
    for _, it in ipairs(items) do
        if it.id == M.ITEM_CHESTKEY then return true end
        if it.id == M.ITEM_LOCKPICK and (attributes & M.CA_STEAL) ~= 0 then return true end
    end
    return false
end

-- closings()' cache key: what its read depends on -- the turn, the horizon, each looter as it
-- stands (id, tile, HP), each of our units (its tile; with a watched unit also id, HP and who it
-- carries: the second look reads them as the AI's targets, and a carrier's stats halve), the open tiles, each
-- wave's units and the map. A looter killed or moved, a player unit moved or hurt, a tile taken, a
-- door opened is a new key.
function M.closingsKey(turn, k, waves, looters, open, blockers, map, watch)
    -- the map (sight.mapKey): a looter walks through a door the planner's re-listing opened
    -- (sight.changed, #661), and that read must not answer for the shut map
    local parts = { "m" .. tostring(map or "-") }
    for _, o in ipairs(looters) do parts[#parts + 1] = o.id .. "@" .. o.x .. "," .. o.y .. "/" .. o.hp end
    -- the units watched (their paths are in the answer): a watched looter reads as an unwatched one
    for id in pairs(watch or {}) do parts[#parts + 1] = "v" .. id end
    -- our units: the AI's first look hides them (they still block its walk), its second look
    -- (M.secondLook) reads them as targets, so who stands where and how hurt is in the key
    -- (HP and what a unit carries only when a unit is watched: with none, no second look runs
    -- and the tiles are all the first look reads of them)
    local looked = next(watch or {}) ~= nil
    for _, o in ipairs(blockers or {}) do
        parts[#parts + 1] = "b" .. (looked and (o.id or "") or "") .. "@" .. o.x .. "," .. o.y
            .. (looked and ("/" .. (o.hp or 0) .. "c" .. (o.carrying or 0)) or "")
    end
    for key in pairs(open) do parts[#parts + 1] = key end
    for _, w in ipairs(waves or {}) do
        for _, u in ipairs(w.units) do
            parts[#parts + 1] = "w" .. w.turn .. ":" .. u.class .. "@" .. u.x .. "," .. u.y
        end
    end
    table.sort(parts)
    return turn .. "|" .. k .. "|" .. table.concat(parts, ";")
end

-- A watched unit's path (closings' second answer): paths[id][phase] = the tile it stands on after
-- enemy phase `phase`. `at` = { [id] = tile } holds each unit's latest tile; a unit that decided
-- nothing this phase (not played as seen, or no move) keeps the tile it had, so no phase is a
-- hole; one in `gone` (it escaped) is not written: the phase it leaves on has no tile.
function M.carryPaths(paths, at, phase, gone)
    for id, tile in pairs(at) do
        if not gone[id] then
            paths[id] = paths[id] or {}
            paths[id][phase] = tile
        end
    end
end

-- A watched unit that stood on its start tile in every phase of closings()' replay with our units
-- hidden (#724: Ch13's Cormag, a wyvern in the peaks, has no target then and never leaves them).
-- The replay is asked again for these with our units as they stand, because the game's own AI
-- moves a unit toward the units it can see. `starts` = { [id] = tile }, `gone` = the ids that
-- escaped. -> { [id] = true }. Pure.
function M.stayedPut(paths, starts, gone)
    local out = {}
    for id, start in pairs(starts) do
        local path = paths[id]
        if path and next(path) and not gone[id] then
            local still = true
            for _, t in pairs(path) do
                if t.x ~= start.x or t.y ~= start.y then still = false end
            end
            if still then out[id] = true end
        end
    end
    return out
end

-- The second look's paths, `seen` = { [id] = path }, taken where a unit left its start tile or
-- escaped (`escaped` = { [id] = true }: the path is then the phases before it, as closes' deadline
-- less one, empty when it went in the first); one that stayed put again keeps the first (the same
-- stationary path, so a unit the game's AI does not move reads as it did). `paths` is edited. Pure.
function M.takeSecondLook(paths, seen, starts, escaped)
    for id, path in pairs(seen) do
        for _, t in pairs(path) do
            if t.x ~= starts[id].x or t.y ~= starts[id].y then paths[id] = path; break end
        end
    end
    for id in pairs(escaped or {}) do paths[id] = seen[id] or {} end
end

-- The second look of closings() (#724), the one place its steps are wired: the watched units that
-- stayed put in the first (M.stayedPut) are `replayAgain`ed -- a function of the set, run on the
-- board as it stood, which answers (their second paths, the ids that escaped) -- and their answer
-- taken (M.takeSecondLook). Asked of nothing when no unit stayed put. `paths` is edited.
function M.secondLook(paths, starts, gone, replayAgain)
    local again = M.stayedPut(paths, starts, gone)
    if next(again) == nil then return end
    local second, escaped = replayAgain(again)
    M.takeSecondLook(paths, second, starts, escaped)
end

-- The terrain closings() leaves on a tile a looter took, `t` its explorable() entry: an emptied
-- chest, else a closed village -- off the AI's loot lists (cp_utility.c
-- gTerrainList_LootableVillages(AndChests)), so the looter goes on to its next target.
function M.sackedTerrain(t)
    return t and t.kind == "chest" and M.TERRAIN_CHEST_EMPTY or M.TERRAIN_VILLAGE_CLOSED
end

-- The enemy phase, numbered from turn `now`'s as 1, at which a wave loaded on turn `turn`
-- reaches a tile `turns` of its moves away: it first moves on its own turn's phase.
function M.waveCloses(turn, now, turns)
    if not turns then return nil end
    return (turn - now) + turns
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
-- gBmMapUnit's (x, y): set to unit `id` (0 = no unit) by putOn; liftOff clears it only when
-- `id` is the one there (a sandbox may have stood another unit on it), true when it did.
function M.putOn(api, x, y, id) api.write8(cell(api.mem, api.SYM.gBmMapUnit, x, y), id) end
function M.liftOff(api, x, y, id)
    if grid(api.mem, api.SYM.gBmMapUnit, x, y) ~= id then return false end
    M.putOn(api, x, y, 0)
    return true
end
-- Moves `u` onto (x, y): its struct and gBmMapUnit, so movement and blocking see it there.
-- Its id off the struct (+0B, as Board.unitAt reads it): harness.lua hands canAttack a lean unit
-- (Board.leanAt), which has none. A staged plan moves a unit onto a tile whose ally it moves
-- off later (stagePhase, the plan's own order), so by default the new unit takes the cell and
-- the ally's later liftOff then finds it is not the ally's. `keepOccupant` (asActive) leaves a
-- cell another unit holds as it is: the actor is only a struct there, off the map.
local UNIT_INDEX = 0x0B
-- gUnitArrayRed's 50 slots by unit id (bmunit.h:376; Board.FACTIONS' red)
local RED_FIRST, RED_LAST = 0x81, 0xB2
function M.standOn(api, u, x, y, keepOccupant)
    -- where it stands now, not u.x/u.y: a sandbox may have moved it already
    local cx, cy = api.mem.u8(u.addr + UNIT_X), api.mem.u8(u.addr + UNIT_Y)
    local id = api.mem.u8(u.addr + UNIT_INDEX)
    M.liftOff(api, cx, cy, id)
    local held = grid(api.mem, api.SYM.gBmMapUnit, x, y)
    if not (keepOccupant and held ~= 0 and held ~= id) then M.putOn(api, x, y, id) end
    api.write8(u.addr + UNIT_X, x)
    api.write8(u.addr + UNIT_Y, y)
end
-- The red unit in slot `id` as an arrival's stand-in (#713 fix 3, ADR 0456): the board's own
-- read of it (Board.unitAt: classId, level, items { id, uses }), with `mov` (M.movOf), `reach`
-- (the longest maxRange of its weapons, Board.itemRange; 0 with none) and `words` (the
-- struct's halfwords, for M.standIn). `Board` is the bound reader (api.Board). Pure over mem.
function M.arrivalOf(mem, S, Board, id)
    local u = Board.unitAt(S.gUnitArrayRed, id - RED_FIRST)
    u.mov, u.reach, u.words = M.movOf(mem, u.addr), 0, {}
    for _, it in ipairs(u.items or {}) do
        local _, max = Board.itemRange(it.id)
        if max and max > u.reach then u.reach = max end
    end
    for k = 0, Board.UNIT_SIZE // 2 - 1 do u.words[k + 1] = mem.u16(u.addr + k * 2) end
    return u
end

-- Inside a sandbox: the stand-in `e` ({ id, addr, words }, s.strike's) loaded into its free red
-- slot as M.arrivalOf read it, its index the slot's (ClearUnit keeps a slot's index,
-- bmunit.c:229). api writes only: the journal empties the slot again when the sandbox returns,
-- and the words any game call wrote there since with it.
function M.standIn(api, e)
    for k, v in ipairs(e.words) do api.write16(e.addr + (k - 1) * 2, v) end
    api.write8(e.addr + UNIT_INDEX, e.id)
end

-- Inside a sandbox: `u` on (x, y) as the active unit, not yet acted, as the unit menu finds
-- it after a move: its struct there and gActiveUnit it, and OFF the unit map, the part of
-- UnitBeginAction (bmunit.c) a menu read sees. Its tile stays clear until
-- PlayerPhase_FinishAction (playerphase.c) puts it back after the act, so no list the menu
-- makes holds the unit itself. Left out: US_HIDDEN and gActiveUnitMoveOrigin, which no menu or
-- target code reads; a RefreshEntityBmMaps after this would put the unit back (bmmap.c skips
-- only hidden units), so no read here calls one.
-- Physic's list (ForEachUnitInRange, bmtarget.c) listed a wounded healer stood on its tile and
-- the game refused the target (vanilla E_20, campaign 4006, turn 24: Saleh, charId 0x17, a crash).
-- `asIs`: the unit's state left as it stands (canAttack asks from where a unit is, which may
-- be after its Canto move: AttackCommandUsability hides Attack from a US_HAS_MOVED unit).
function M.asActive(api, u, x, y, asIs)
    local S = api.SYM
    local id = api.mem.u8(u.addr + UNIT_INDEX)
    -- A wait tile may be an ally's (the plan may vacate it): the actor's struct stands there but
    -- the ally keeps its cell, so no read may ask the map who stands on the actor's tile. Zeroing
    -- it erased the ally for every later read in the sandbox, and the Drop list offered its tile
    -- (vanilla Ch2 seed 4005, turn 5, #654).
    M.standOn(api, u, x, y, true)
    M.liftOff(api, x, y, id)
    if not asIs then
        api.write32(u.addr + UNIT_STATE, api.mem.u32(u.addr + UNIT_STATE) & ~api.Board.US_HAS_MOVED)
    end
    api.write32(S.gActiveUnit, u.addr)
    api.write8(S.gActiveUnitId, id)
end
local function readGrid(mem, base, w, h)
    local g = {}
    for y = 0, h - 1 do
        g[y] = {}
        for x = 0, w - 1 do g[y][x] = grid(mem, base, x, y) end
    end
    return g
end

-- Inside a sandbox: `info` (scratch) made a fresh struct EventInfo over the chapter's event
-- list at `offset` in its ChapterEventGroup (GetChapterEventDataPointer), ready for the game's
-- SearchAvailableEvent -- the turn events (+00), the talks (+04), the location events (+08).
local function eventSearch(api, call, info, offset)
    local events = call(api.SYM.GetChapterEventDataPointer, { api.chapter() })
    for o = 0, EVENT_INFO_SIZE - 4, 4 do api.write32(info + o, 0) end
    api.write32(info, api.mem.u32(events + offset))
end

-- Inside a sandbox: the scripts the chapter's event list at `offset` offers now, in the game's
-- order, { { script, flag (EventInfo +08) } } (availableList), or { [script] = flag }
-- (availableScripts): the game's SearchAvailableEvent walk.
local function availableList(api, call, info, offset)
    eventSearch(api, call, info, offset)
    local out = {}
    local found = call(api.SYM.SearchAvailableEvent, { info })
    while found ~= 0 do
        out[#out + 1] = { script = api.mem.u32(info + EVENT_SCRIPT),
                          flag = api.mem.u32(info + EVENT_FLAG) }
        found = call(api.SYM.SearchNextAvailableEvent, { info })
    end
    return out
end
local function availableScripts(api, call, info, offset)
    local out = {}
    for _, e in ipairs(availableList(api, call, info, offset)) do out[e.script] = e.flag end
    return out
end

-- Inside a sandbox: the turn-event scripts the game offers at `turn` and `phase` (gPlaySt's
-- turn and faction set, then availableScripts over the chapter's turn events): { [script] = flag }.
-- The one reading of the game's per-phase turn-event check (eventinfo.c), s.nextTurnEvent's and
-- s.scriptedUnits'.
function M.turnScripts(api, call, info, turn, phase)
    api.write16(api.SYM.gPlaySt + PLAY_TURN, turn)
    api.write8(api.SYM.gPlaySt + PLAY_FACTION, phase)
    return availableScripts(api, call, info, CHAPTER_TURNS)
end

-- ChangeUnitAi (eventscr3.c:33-58), inside a sandbox: `e`'s AI scripts switched, as an event's
-- CHAI does. A hidden or dead unit is left; an ai1 of AI_A_INVALID (0x15, the enumerator after
-- AI_A_14, cp_common.h:110) or an ai2 of AI_B_INVALID (0x13, after AI_B_12, :135) leaves that
-- script alone; each script's counter restarts at 0 and an ai2 of AI_B_0C flags the unit
-- AI_UNIT_FLAG_3 (cp_common.h:58). These are api writes, so the journal puts the board's words
-- back when the sandbox returns, and the decisions' own keep (M.keepAi: it holds the value it
-- finds first, here the woken one) unwinds before them, to the board's: no keep16 is
-- needed (it is for a game call's writes, which no journal sees).
local AI_A_INVALID, AI_B_INVALID, AI_B_0C, AI_UNIT_FLAG_3 = 0x15, 0x13, 0x0C, 0x08
local UNIT_AI_A_PC, UNIT_AI_B_PC = 0x43, 0x45
function M.changeUnitAi(api, e, ai1, ai2)
    if api.mem.u32(e.addr + UNIT_STATE) & (api.Board.US_HIDDEN | api.Board.US_DEAD) ~= 0 then
        return false
    end
    if ai1 ~= AI_A_INVALID then
        api.write8(e.addr + UNIT_AI1, ai1)
        api.write8(e.addr + UNIT_AI_A_PC, 0)
    end
    if ai2 ~= AI_B_INVALID then
        api.write8(e.addr + UNIT_AI2, ai2)
        api.write8(e.addr + UNIT_AI_B_PC, 0)
        if ai2 == AI_B_0C then
            api.write8(e.addr + M.UNIT_AI_FLAGS, api.mem.u8(e.addr + M.UNIT_AI_FLAGS) | AI_UNIT_FLAG_3)
        end
    end
    return true
end

-- The AI changes the plan's own waits cause, played inside a sandbox before the enemy phase
-- (#712). The game runs the chapter's Misc events after every unit's wait (RunWaitEvents,
-- eventinfo.c:1628-1659: SearchAvailableEvent over miscBasedEvents with gActiveUnit the unit that
-- waited, each script started after SetFlag(flag), StartEventFromInfo, eventinfo.c:71-77), and an
-- AREA entry (EvCheck0B_AREA, eventinfo.c:1020) offers its script when gActiveUnit stands in its
-- rectangle and its flag is clear. `waits` = the plan's waits, { { unit, x, y, order } }: for each,
-- in the order the plan acts them (`order`, the act's index; the game runs the events at each wait
-- in turn, so two entries sharing a flag fire for the first unit to wait), the unit is stood on
-- its end tile for the ask (its x and y bytes, journaled and put back: a unit the counter killed is in no board list, and
-- the game keeps a dead unit's tile, UnitKill, bmunit.c:958, and runs the wait events after the
-- action whether or not it died, playerphase.c:98-99, cp_perform.c:85-86) and the game is asked
-- what it offers there; a flag an earlier wait took is not offered again (the game's SetFlag before
-- the script), and each script's CHAI changes (M.scriptAiChanges) are written into the units of that
-- character in `byId` (ChangeAiForCharacter: every non-blue unit; M.changeUnitAi).
-- -> woken { { id, ai1, ai2 } }, and stats { positional, truncated }: the scripts that ran
-- whose CHAI_AT the walk did not read (#727) and whose walk the budget cut short, for the
-- planner's cost line (a plan's silent estimate is never silent).
-- `memo` = { tiles = {}, scripts = {} }, the board's: what the game offers on a tile (the Misc
-- kinds in vanilla -- AREA, the Defeat flags, AFEV, CauseGameOverIfLordDies -- ask the unit's
-- tile and the flags, never who it is) and what each script changes (ROM bytes). An ESTIMATE as
-- M.scriptAiChanges is: not modelled are RunWaitEvents' other work (it sets or clears
-- EVFLAG_DEFEAT_ALL, and runs nothing when flag 0x65 is set or no blue unit is left) and a
-- lookahead reply turn (armyReply: its units end elsewhere and wake nothing). `info` is a sandbox's
-- scratch.
function M.areaWake(api, call, info, byId, waits, memo)
    local S, mem = api.SYM, api.mem
    local fired, woken, stats = {}, {}, { positional = 0, truncated = 0 }
    local order = {}
    for i, w in ipairs(waits) do order[i] = w end
    local rank = {}
    for i, w in ipairs(waits) do rank[w] = i end
    table.sort(order, function(x, y)
        local ox, oy = x.order or math.huge, y.order or math.huge
        if ox ~= oy then return ox < oy end
        return rank[x] < rank[y]
    end)
    for _, b in ipairs(order) do
        local key = b.x * 64 + b.y
        local entries = memo.tiles[key]
        if not entries then
            -- stood on its end tile for the ask alone, then back: a dead actor is in no list of
            -- the phase, and a map refresh would put its struct on the tile it died on
            local ax, ay = mem.u8(b.unit.addr + UNIT_X), mem.u8(b.unit.addr + UNIT_Y)
            api.write8(b.unit.addr + UNIT_X, b.x)
            api.write8(b.unit.addr + UNIT_Y, b.y)
            api.write32(S.gActiveUnit, b.unit.addr)
            entries = availableList(api, call, info, CHAPTER_MISC)
            memo.tiles[key] = entries
            api.write8(b.unit.addr + UNIT_X, ax)
            api.write8(b.unit.addr + UNIT_Y, ay)
        end
        for _, entry in ipairs(entries) do
            if entry.flag == 0 or not fired[entry.flag] then
                fired[entry.flag] = true
                local fx = memo.scripts[entry.script]
                if not fx then
                    fx = M.scriptAiChanges(mem, entry.script)
                    memo.scripts[entry.script] = fx
                end
                stats.positional = stats.positional + fx.positional
                stats.truncated = stats.truncated + (fx.truncated and 1 or 0)
                for _, c in ipairs(fx.changes) do
                    for id, e in pairs(byId) do
                        if e.faction ~= "blue" and e.charId == c.charId
                                and M.changeUnitAi(api, e, c.ai1, c.ai2) then
                            woken[#woken + 1] = { id = id, ai1 = c.ai1, ai2 = c.ai2 }
                        end
                    end
                end
            end
        end
    end
    return woken, stats
end

-- Whether a Misc list's scripts `after` a death flag was set hold one `before` did not that
-- completes EVFLAG_WIN: the chapter's win event (an unconditional entry is in both; a TMP or
-- DefeatAll flag's is no DefeatBoss win). Scripts are keyed by address, so two entries sharing
-- one merge; every such pair in vanilla's Misc lists is AREA entries of one TMP flag (checked by
-- grepping each *-eventinfo.h Misc list for a repeated script), so none hides a WIN. Pure.
function M.winEvent(before, after)
    for script, flag in pairs(after) do
        if not before[script] and flag == M.EVFLAG_WIN then return true end
    end
    return false
end

-- Sight.batching(outer, guarded, log) -> sandbox, api: Sight.machine made re-entrant (the
-- planner's cost, #510 step 9) over `outer` (Sight.new's api), and an api whose writes it
-- journals. guarded = nil, or a function -> the spans of memory ({ { addr, bytes, name } }:
-- the unit structs, the trap pool) a nested sandbox must hand back as it found them, and
-- log = the list each word one did not hand back is added to (M.leaks), once a word, the
-- word then put back so the run plays on as if kept (PT_LEAKGUARD=1, a diagnostic: it reads
-- every span twice a sandbox).
function M.batching(outer, guarded, log)
    -- The outermost sandbox() saves the state and loads it back at the end, as Sight.machine
    -- always did; a call made inside it (s.batch, or one read calling another) runs within
    -- that save, and every byte it wrote through `api` is put back when it returns, so one
    -- read cannot leak into the next. A game function's own writes are not journaled. The
    -- ones a read can make fresh (a movement map, the battle structs, gAiDecision) it makes
    -- fresh first. The ones on a unit struct nothing makes fresh, so they are kept before the
    -- call (keep16: M.equip's bag, M.keepAi's AI bytes, M.keepMaps's state word, M.keepRide's
    -- ballista) and the journal puts them back.
    local mem0 = outer.mem
    -- kept[depth] = the addresses keep16 holds for the sandbox open at that depth
    local journal, kept
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
        -- keep16(addr, n): the n halfwords from addr are put back when the sandbox returns,
        -- for a game call about to write them itself (M.equip, M.keepAi), with no write made
        -- now. A halfword is kept once a sandbox: its first value there is the one put back,
        -- so a second keep (every enemy decision asks, M.keepAi) reads and journals nothing.
        keep16 = function(addr, n)
            if not journal then return end
            local held = kept[#kept]
            -- a span asked for again in this sandbox (every decision keeps the map pools) is
            -- already held whole: skip its walk. The memo lives in `held`, so it resets with it.
            local spans = held.spans
            if not spans then spans = {}; held.spans = spans end
            if (spans[addr] or 0) >= n then return end
            spans[addr] = n
            for k = 0, n - 1 do
                local at = addr + k * 2
                if not held[at] then
                    held[at] = true
                    journal[#journal + 1] = { at, mem0.u16(at), outer.write16 }
                end
            end
        end,
    }, { __index = outer })
    local machine = M.machine(api.cpu)
    local depth, outerCall, outerScratch = 0, nil, nil
    local function sandbox(fn)
        if depth == 0 then
            depth, journal, kept = 1, {}, { {} }
            local ok, a, b = pcall(machine, function(call, scratch)
                outerCall, outerScratch = call, scratch
                return fn(call, scratch)
            end)
            depth, journal, kept, outerCall, outerScratch = 0, nil, nil, nil, nil
            if not ok then error(a, 0) end
            return a, b
        end
        local mark = #journal
        local was = guarded and M.spanWords(mem0, guarded())
        depth = depth + 1
        kept[depth] = {}
        local ok, a, b = pcall(fn, outerCall, outerScratch)
        kept[depth] = nil
        depth = depth - 1
        for k = #journal, mark + 1, -1 do
            local e = journal[k]
            e[3](e[1], e[2])
            journal[k] = nil
        end
        if not ok then error(a, 0) end
        if was then
            for _, l in ipairs(M.leaks(mem0, was)) do
                M.logLeak(log, l)
                outer.write32(l.addr + l.off, l.was)
            end
        end
        return a, b
    end
    -- whether a sandbox is open: memory may then hold its writes, journaled or the game's own
    -- (a call's EquipUnitItemSlot reorders a bag; only M.equip keeps it, so call that)
    local function open() return depth > 0 end
    -- how many sandboxes are open (0 outside one): a ghostly() scope's own depth (#713)
    local function level() return depth end
    return sandbox, api, open, level
end

-- Whether the unit at `unitAddr` opens `terrain` as its bag stands: the game's own check, a key
-- slot of 0 or more (GetUnitKeyItemSlotForTerrain returns -1 for none). The one owner of that
-- read: s.opens, keyItemOpens and a theft's before-and-after (M.pilfer).
function M.opensAt(call, S, unitAddr, terrain)
    return s32(call(S.GetUnitKeyItemSlotForTerrain, { unitAddr, terrain })) >= 0
end

-- Inside a sandbox: `u` holds the weapon in item `slot` as it does after striking with it
-- (WeaponSelectMenu_Selected: EquipUnitItemSlot), the one it counters with next phase.
-- EquipUnitItemSlot reorders the bag in place, a game write no journal sees, so the bag is
-- journaled first and a nested sandbox puts it back: otherwise one judged plan's equip leaks
-- into the next one's, whose slot then names another item (vanilla Ch5: Seth's Iron Sword
-- left in front, his counter judged unable to kill Joshua, who then died to it).
-- It moves items 0..slot only (bmitem.c), so those are kept. api = M.batching's (its
-- Board bound: api.Board), call = the sandbox's. Every equip goes through here.
-- Whether the game takes `value` (id | uses << 8) for a key of the unit at `unitAddr` to
-- `terrain`: the item put alone in its bag, GetUnitKeyItemSlotForTerrain (bmunit.c) asked, the
-- bag put back. A Lockpick is a key only to a thief. io = { read16, write16 }, `call` the
-- sandbox's, B = board.lua's Board. The one owner: sight.keySources and harness's
-- INSPECT.isKey (Bot.fullBag). Not s.holding, which adds items after the unit's own for a
-- read of the unit as it fights: the game's key check finds the first key in the bag, so this
-- one needs the item alone, the others cleared (and, being a plain function over `io`, it is
-- called with no Sight object, from the harness).
function M.keyItemOpens(io, call, S, B, unitAddr, value, terrain)
    local bag = {}
    for k = 0, B.ITEM_COUNT - 1 do
        local at = unitAddr + B.UNIT_ITEMS + k * 2
        bag[k] = io.read16(at)
        io.write16(at, k == 0 and value or 0)
    end
    -- the item alone in slot 0: the slot the game's check finds, so >= 0 is its yes
    local key = M.opensAt(call, S, unitAddr, terrain)
    for k = 0, B.ITEM_COUNT - 1 do io.write16(unitAddr + B.UNIT_ITEMS + k * 2, bag[k]) end
    return key
end

-- What the game says `value` (id | uses << 8) opens for the unit, by demand kind
-- (M.LOCK_TERRAIN): { doors, chests }, each a keyItemOpens read.
function M.keyOpens(io, call, S, B, unitAddr, value)
    local out = {}
    for kind, terrain in pairs(M.LOCK_TERRAIN) do
        out[kind] = M.keyItemOpens(io, call, S, B, unitAddr, value, terrain)
    end
    return out
end

-- Whether a keyOpens read opens any lock: what makes an item a "key" in a bag.
function M.opensAnyLock(opens)
    for kind in pairs(M.LOCK_TERRAIN) do
        if opens[kind] then return true end
    end
    return false
end

-- A keyOpens read kept per unit and item id: the game's key check reads the id, never the uses
-- (the one value `uses` is taken from, the first copy seen), so one read serves every copy.
function M.keyReader(io, call, S, B)
    local memo = {}
    return function(unitAddr, item)
        local k = unitAddr .. ":" .. item.id
        if memo[k] == nil then
            memo[k] = M.keyOpens(io, call, S, B, unitAddr, item.id | (item.uses << 8))
        end
        return memo[k]
    end
end

-- fn(copy) with each of `values` (id | uses << 8, in order) in the first empty slots of `u`'s
-- bag, inside a sandbox: what the game would say of the unit holding those items (what the
-- prep shop would sell it), asked of the game itself and put back on return, fn's error
-- included. `copy` is the board unit with the items listed, so s.answer and s.weapons read it
-- as held. The bag must be packed: the board read (Board.items) and the roster stop at the
-- first empty slot, so an item past a gap is one `u.items` does not list, and a value written
-- after #u.items would land on it. api = M.batching's, sandbox its sandbox.
function M.holding(api, sandbox, u, values, fn)
    local Board = api.Board
    local slot = #u.items
    if slot + #values > Board.ITEM_COUNT then error("sight.lua: holding: the bag is full", 2) end
    for k = slot, Board.ITEM_COUNT - 1 do
        if api.mem.u16(u.addr + Board.UNIT_ITEMS + k * 2) ~= 0 then
            error("sight.lua: holding: the bag is not packed (an item past slot " .. slot .. ")", 2)
        end
    end
    return sandbox(function()
        local items = table.move(u.items, 1, slot, 1, {})
        for k, value in ipairs(values) do
            api.write16(u.addr + Board.UNIT_ITEMS + (slot + k - 1) * 2, value)
            items[slot + k] = { id = value & 0xFF, uses = value >> 8 }
        end
        return fn(setmetatable({ items = items }, { __index = u }))
    end)
end

-- Inside a sandbox: the map change at (x, y) applied as the game applies it, every write
-- journaled through `api` so the next judged plan finds the map as it was. A door's event
-- (EvtListDOOR: script 1, the map change alone) and a broken wall (UpdateObstacleFromBattle)
-- both run ApplyMapChangesById then RefreshTerrainBmMap: each non-zero tile of the change's
-- rectangle (struct MapChange: +01 x, +02 y, +03 w, +04 h, +08 data) into gBmMapBaseTiles, and
-- its terrain gTilesetTerrainLookup[tile >> 2] into gBmMapTerrain. Done by hand, not by
-- TriggerMapChanges, whose own writes no journal sees: one plan's open door leaked into every
-- later plan's board (PR #596 review). What it leaves out: the change's enabled bit and a
-- wall's trap (read by no enemy's move), and a roof the change removes (UpdateRoofedUnits;
-- a door or wall is no roof). No change at the tile: nothing.
function M.openMap(api, call, S, x, y)
    local mem = api.mem
    for _, t in ipairs(M.mapChangeTiles(mem, call, S, x, y) or {}) do
        -- a u16 grid: `cell`'s row, two bytes a tile
        api.write16(cell(mem, S.gBmMapBaseTiles, 0, t.y) + t.x * 2, t.tile)
        api.write8(cell(mem, S.gBmMapTerrain, t.x, t.y), t.terrain)
    end
end

-- The tiles the map change at (x, y) writes, { x, y, tile, terrain } row by row: each non-zero
-- tile of its rectangle, as ApplyMapChangesById writes them, and the terrain
-- RefreshTerrainBmMap reads for it (gTilesetTerrainLookup[tile >> 2]); nil when no change
-- covers the tile. The one walk of a change's rectangle: openMap applies it, sight.mapChange
-- says what a door or wall opens (a gate two tiles deep, a roofed room, opens whole with its
-- first tile). `costs` (optional): a movement cost table (GetUnitMovementCost's s8 per terrain,
-- -1 = no way); only the tiles it walks are kept, each with its `cost` -- a change also draws
-- the walls round what it opens, and they are no ground.
function M.mapChangeTiles(mem, call, S, x, y, costs)
    local id = call(S.GetMapChangeIdAt, { x, y })
    if id >= 0x80000000 then return nil end
    local mc = call(S.GetMapChange, { id })
    if mc == 0 then return nil end
    local x0, y0, w, h = mem.u8(mc + 1), mem.u8(mc + 2), mem.u8(mc + 3), mem.u8(mc + 4)
    local data, lookup = mem.u32(mc + 8), mem.u32(S.gTilesetTerrainLookup)
    local out, k = {}, 0
    for iy = 0, h - 1 do
        for ix = 0, w - 1 do
            local tile = mem.u16(data + 2 * k)
            k = k + 1
            if tile ~= 0 then
                local terrain = mem.u8(lookup + (tile >> 2))
                local cost = costs and mem.s8(costs + terrain)
                if not costs or cost > 0 then
                    out[#out + 1] = { x = x0 + ix, y = y0 + iy, tile = tile, terrain = terrain,
                                      cost = cost or nil }
                end
            end
        end
    end
    return out
end

-- M.spanWords(mem, spans) -> { { addr, words, n, name } }: each span ({ addr, bytes, name }: a
-- unit struct, the trap pool) as it reads now, in its n words.
-- M.leaks(mem, was) -> { { name, addr, off, was, now } }: every word of one that no longer
-- reads as `was` has it. M.batching's guard (PT_LEAKGUARD=1) asks after a nested sandbox put
-- its journal back: a difference is a game call's write that nothing kept, the kind that made
-- one judged plan leak into the next (the bag, #554; the AI bytes, the fog bits and a rider's
-- ballista, #510).
-- M.logLeak(log, leak): `leak` added to the list `log` (log.seen indexes it by word), or the
-- one already there counted again, with any new value it leaked to: one game call leaks the
-- same word every plan it judges, and a second call may leak it to another value.
-- M.leakLine(leak) -> what a run's end says of it.
function M.spanWords(mem, spans)
    local out = {}
    for x, span in ipairs(spans) do
        local words, n = {}, span[2] // 4
        for k = 0, n - 1 do words[k] = mem.u32(span[1] + k * 4) end
        out[x] = { span[1], words, n, span[3] }
    end
    return out
end
function M.leaks(mem, was)
    local out = {}
    for _, u in ipairs(was) do
        for k = 0, u[3] - 1 do
            local now = mem.u32(u[1] + k * 4)
            if now ~= u[2][k] then
                out[#out + 1] = { name = u[4], addr = u[1], off = k * 4, was = u[2][k], now = now }
            end
        end
    end
    return out
end
function M.logLeak(log, l)
    log.seen = log.seen or {}
    local key = l.addr + l.off
    local got = log.seen[key]
    if not got then
        -- nows lists each value it leaked to, in order; nowSeen is the set (a value of 1 kept
        -- in the list itself would overwrite its first entry)
        got = { name = l.name, addr = l.addr, off = l.off, was = l.was, nows = {}, nowSeen = {},
                n = 0 }
        log.seen[key] = got
        log[#log + 1] = got
    end
    got.n = got.n + 1
    if not got.nowSeen[l.now] then
        got.nowSeen[l.now] = true
        got.nows[#got.nows + 1] = l.now
    end
end
function M.leakLine(l)
    local nows = {}
    for k, v in ipairs(l.nows) do nows[k] = ("0x%08X"):format(v) end
    return ("sandbox leak: the %s at 0x%08X, word +0x%02X, was 0x%08X and is %s after its "
        .. "sandbox returned (%d times): a game call wrote it and no keep16 held it "
        .. "(sight.lua's header)"):format(l.name, l.addr, l.off, l.was,
                                          table.concat(nows, " or "), l.n)
end

-- Inside a sandbox, before an enemy decides (aiDecide) or its phase starts (M.aiPhaseStart,
-- whose two game calls write aiFlags and ai_counter): the AI bytes of `units` (every unit on
-- the board, a list or a table by id) are put back when the sandbox returns, the ones the game's
-- AI writes on unit structs as it decides. On the deciding unit (gActiveUnit): ai1, ai2 and both
-- script counters (cp_script.c: AiScriptCmd_02_ChangeAi, and each command's (*pc)++ on ai_a_pc
-- or ai_b_pc), ai_counter (AiScriptCmd_10_DoLooting; cp_battle.c
-- AiAttemptStealActionWithinMovement; cp_0803E2F4.c AiTryMoveToSpecificPosition) and aiFlags
-- (the escape flag: cp_utility.c AiGetChestUnlockItemSlot, which AiFindPillageLocation calls,
-- and cp_script.c AiScriptCmd_17_DoEscape; cpextra_80407F0.c AiSpecialItemLockpick). On
-- ANOTHER unit: aiFlags alone (cp_0803E2F4.c AiTryGetNearestHealPoint flags the unit standing
-- on the heal tile). Every unit's whole AI block is kept all the same, not the decider's
-- alone: a keep is free after the first one in a sandbox (keep16), and that no decision
-- writes another unit's block is a reading of the decomp, not a measurement.
-- Without it a looter the closings replay had played past its last village read as no looter
-- (PillageThenPursue sets AI2 to 0) for the rest of the decision's batch: vanilla Ch9's village
-- read "closes in 3 phases" once and "never closes" every time after, each turn (#510).
function M.keepAi(api, units)
    for _, o in pairs(units) do
        api.keep16(o.addr + M.UNIT_AI_FLAGS, 1)
        api.keep16(o.addr + M.UNIT_AI_CONFIG, M.UNIT_AI_WORDS)
    end
end

-- Inside a sandbox, before the game refreshes its maps: every unit's state word is put back
-- when the sandbox returns. RefreshEntityBmMaps (bmmap.c RefreshUnitsOnBmMap) rewrites a red
-- unit's fog bits for the board it is called on: US_BIT9 set on one standing in fog, and
-- cleared for US_BIT8 on one our units now see. A judged plan stands our units elsewhere, so
-- the refresh inside it marks as seen an enemy only that plan would reveal; the journal puts
-- our units back and, without this, left the enemy seen for every plan judged after it in
-- the batch, where it then decided and struck (s.decides reads the bit before any refresh).
-- Found by PT_LEAKGUARD on vanilla Ch6, turn 2 (#510). `units` as M.keepAi's.
-- M.refresh is that keep and the call; aiDecide, whose refresh rides in its one call list,
-- keeps and lists it itself. Every refresh inside a sandbox is one of the two.
-- The map pools are kept the same way (M.keepMapPools): the refresh clears gBmMapUnit,
-- gBmMapHidden and gBmMapFog and refills them from the structs as the sandbox stands them, a
-- unit it hides left out, and the journal puts only the structs back. The AI's own decision
-- hides our units (closings, onlyTarget), so the refresh in it wiped every blue unit off the
-- unit map for the plans read after it in the batch: Drop's list offered the tile of an ally
-- standing there and the game refused it (vanilla Ch19, campaign 4002 attempt 2 turn 12,
-- #681). The hidden and fog maps are the same refresh's, kept on the same list.
function M.keepMaps(api, units)
    for _, o in pairs(units) do api.keep16(o.addr + UNIT_STATE, 2) end
    M.keepMapPools(api)
end
-- The map pools a refresh rebuilds (bmmap.c RefreshEntityBmMaps: BmMapFill on each).
M.REFRESHED_MAPS = { "gBmMapUnit", "gBmMapHidden", "gBmMapFog" }
-- Each pool's cells, put back when the sandbox returns. BmMapInit lays a map out as h + 4 row
-- pointers then (w + 2)-wide rows, the handle on the third pointer; BmMapFill clears
-- (h + 4) * (w + 2) bytes from the first pointer, an odd count less its last byte (size - 1),
-- and so does this: halfwords, floor. A missing symbol or a map not built yet is a programming
-- error (a refresh only runs on a loaded chapter's map; gen_symbols.py must list the pool), so
-- it raises, naming it, instead of keeping nothing.
function M.keepMapPools(api)
    local mem, S = api.mem, api.SYM
    if not S.gBmMapSize then error("keepMapPools: SYM.gBmMapSize is missing", 0) end
    local w, h = api.Board.mapSize()   -- the bound reader (Board.bind)
    local words = ((w + 2) * (h + 4)) // 2
    for _, name in ipairs(M.REFRESHED_MAPS) do
        if not S[name] then error("keepMapPools: SYM." .. name .. " is missing (gen_symbols.py)", 0) end
        local rows = mem.u32(S[name])
        if rows == 0 then error("keepMapPools: " .. name .. " is not built (no map loaded)", 0) end
        api.keep16(mem.u32(rows - 8), words)
    end
end
function M.refresh(api, call, S, units)
    M.keepMaps(api, units)
    call(S.RefreshEntityBmMaps, {})
end

-- Inside a sandbox, before enemy `e` decides (aiDecide): a ballista's rider is put back on
-- it when the sandbox returns. The AI's attack decision steps the deciding unit off a ballista
-- that is spent, or when it picks its own weapon over it (cp_battle.c
-- AiAttemptOffensiveAction and AiAttemptCombatWithinMovement: bmarch.c
-- TryRemoveUnitFromBallista), which clears US_IN_BALLISTA (the state word: M.keepMaps keeps
-- it), the unit's ballistaIndex, and on the ballista's trap its ridden flag and its tile, set
-- to the unit's. Without it the rider read as on foot, and the ballista as free and standing
-- where a judged plan had stood the rider, for every plan judged after. Found by PT_LEAKGUARD
-- on vanilla Ch13, turn 11 (#510). The step off also redraws (RefreshUnitSprites), which
-- writes every unit's pMapSpriteHandle anew, null on one the plan hid: only drawing reads it,
-- and `units` (as M.keepAi's) have it kept all the same, so the guard stays exact.
function M.keepRide(api, S, e, units)
    if not M.riding(api.mem.u32(e.addr + UNIT_STATE)) then return end
    for _, o in pairs(units) do api.keep16(o.addr + M.UNIT_SPRITE, 2) end
    api.keep16(e.addr + M.UNIT_BALLISTA, 1)
    api.keep16(S.sTrapPool + api.mem.u8(e.addr + M.UNIT_BALLISTA) * M.TRAP_SIZE,
               M.TRAP_SIZE // 2)
end

-- One word of a battle unit, at offset `at`, as the played exchanges are kept by it (the
-- sight's battleKey): less where the unit stands, and less its aiFlags and ai_counter. The
-- enemy phase's start rewrites both on a unit (M.aiPhaseStart: the heal flag from its HP, a
-- player unit's flags from its bag, its ai_counter a count of the units around it), and no
-- battle code reads either: aiFlags is read in cp_*.c, cpextra_80407F0.c, eventscr3.c and
-- bmsave.c alone, ai_counter by the AI on the unit deciding and by bmsave.c. Kept in the key,
-- ai_counter made one exchange a new one wherever the unit stood: vanilla Ch6 seed 1001
-- played 1,949 simulations for the 1,496 it needs, the same decisions.
function M.battleWord(at, word)
    if at == BU_POSITION then return word & ~POSITION_BITS end
    if at == BU_AI_FLAGS or at == BU_AI_COUNTER then return word & ~AI_BYTE_BITS end
    return word
end

-- Inside a sandbox, where a simulated enemy phase begins: the game's own phase start
-- (cp_phase.c AiPhaseInit), which no player-phase read had run. Its field assignments are
-- written here as they stand and its two calls made, the faction red first:
-- UpdateAllPhaseHealingAIStatus sets the heal flag (aiFlags bit 0) of each unit of
-- gPlaySt.faction from its HP, which the turn order (cp_order.c) and the staff AI read on
-- units other than the decider, and SetupUnitInventoryAIFlags reads the player's units for
-- gAiState.bestBlueMov and their aiFlags and ai_counter. AiPhaseInit itself is not called: it
-- starts gProcScr_CpOrder, which would play the phase on the sandbox's next frame.
-- Without it a judged phase read the player phase's leftovers: the flags and cmd_result of
-- the last real enemy phase (the save's on turn 1, specialItemFlags and bestBlueMov too), and
-- the heal flag of an enemy the plan had just wounded as it stood before the wound. Once
-- every player unit had acted the flags read AI_FLAG_BERSERKED (4, cp_phase.c
-- AiPhaseBerserkInit's value), and every enemy then decided as a berserked unit, no script
-- run: vanilla Ch9's looters attacked their own side in each such read, 104 decisions of 320
-- in one attempt, and took no village (#510, ADR 0407).
-- What the sandbox hands back: every write made here (journaled), gAiState.bestBlueMov
-- (journaled with unk84's halfword before the game writes it) and the units' aiFlags and
-- ai_counter (M.keepAi; `units` as its: Board.read's every occupied slot). NOT handed back:
-- the scratch maps SaveNumberOfAlliedUnitsIn0To8Range fills for each player unit
-- (gBmMapMovement zeroed, and its 8-tile range added into whichever map gWorkingBmMap names
-- then, cp_utility.c), as no game call's map writes are; what follows a phase start is an
-- enemy's decision, which makes its maps anew. ai_counter is therefore a count of the units
-- around a player unit only when the working map is the movement map; nothing reads it there.
-- `after` = the caller's next calls, run in the same list (a list is one emulated run, a call
-- of its own a frame more on every phase and strike) -> the last one's r0.
-- `known` = what the two calls wrote on this very board (M.phaseStarted, read after an
-- earlier start), written back in their place: a strike stands one unit elsewhere and
-- changes its equipped weapon, and neither call reads where a unit stands or which weapon
-- is first (the heal flag is from HP, bestBlueMov and a player unit's flags from who is on
-- the map, its Mov and what its bag holds), bar ai_counter and the scratch maps: no decision
-- read off them was seen to change (ADR 0407: the same acts on four runs with the calls on
-- every strike and with them once a board). Called for every strike they cost vanilla Ch14
-- seed 1001 47.8 CPU s against main's 46.2.
-- What both phase starts (AiPhaseInit, AiPhaseBerserkInit) write alike, after keeping the units'
-- AI bytes for the sandbox to hand back: the phase's faction and AI flags, unk7E, cmd_result and
-- the chapter's specialItemFlags. -> their two calls, then `after`'s, as one list.
local function phaseFields(api, S, units, faction, flags, after)
    local mem, A = api.mem, S.gAiState
    M.keepAi(api, units)
    api.write8(S.gPlaySt + PLAY_FACTION, faction)
    api.write8(A + AI_FLAGS, flags)
    api.write8(A + AI_UNK7E, 0xFF)
    for k = 0, AI_CMD_RESULTS - 1 do api.write8(A + AI_CMD_RESULT + k, 0) end
    api.write32(A + AI_ITEM_FLAGS, mem.u32(S.gAiItemConfigTable + api.chapter() * 4))
    local list = { { S.UpdateAllPhaseHealingAIStatus, {} }, { S.SetupUnitInventoryAIFlags, {} } }
    for _, c in ipairs(after or {}) do list[#list + 1] = c end
    return list
end

function M.aiPhaseStart(api, call, S, units, after, known)
    local A = S.gAiState
    local list = phaseFields(api, S, units, M.PHASES[3], AI_FLAG_0, after)
    api.write8(A + AI_ORDER_STATE, 0)
    api.write16(A + AI_UNK84, 0)
    if known then
        api.write8(A + AI_BEST_MOV, known.mov)
        for _, o in pairs(units) do api.write8(o.addr + M.UNIT_AI_FLAGS, known.flags[o.addr]) end
        return call(after)
    end
    return call(list)
end

-- Our units the game's berserk phase moves after our player phase (#660): bm.c runs
-- gProcScr_BerserkCpPhase right after each phase, before the next faction's, and
-- cp_order.c CpOrderBerserkInit lists the phase faction's units whose status is BERSERK and
-- whose state is none of US_HIDDEN, US_UNSELECTABLE, US_DEAD, US_RESCUED, US_HAS_MOVED_AI, in
-- unit-index order (no sort). `units` = Board.read's, `after` = the player phases that start
-- before the one this phase follows (0: this turn's; 1: the lookahead's second phase): each
-- start ticks the status down once and clears it at 0 (bmunit.c TickActiveFactionTurn), so a
-- unit berserks then only while its duration is above `after`. `Board` = api.Board (its
-- status and state bits). -> the ids, in the game's order
function M.berserkers(mem, Board, units, after)
    local skips = Board.US_HIDDEN | Board.US_UNSELECTABLE | Board.US_DEAD | Board.US_RESCUED
        | Board.US_HAS_MOVED_AI
    local out = {}
    for _, o in pairs(units) do
        if o.faction == "blue"
                and Board.statusAfter(mem.u8(o.addr + Board.UNIT_STATUS), after)
                    == Board.STATUS_BERSERK
                and (mem.u32(o.addr + UNIT_STATE) & skips) == 0 then
            out[#out + 1] = o.id
        end
    end
    table.sort(out)
    return out
end

-- Inside a sandbox, the berserk phase's start for the player's side (cp_phase.c
-- AiPhaseBerserkInit): the fields both starts write (phaseFields), the faction the player's (the
-- phase runs inside the player phase) and AI_FLAG_BERSERKED, then its two calls. Unlike
-- AiPhaseInit it leaves orderState and unk84 alone. What follows is the berserked units'
-- decisions; the enemy phase after starts anew (aiOrder).
function M.berserkPhaseStart(api, call, S, units)
    call(phaseFields(api, S, units, M.PHASES[1], AI_FLAG_BERSERKED))
end

-- The red units' fog bits (US_BIT9, and US_BIT8 the refresh clears) as they stand, which the
-- berserk phase's refreshes under the player's faction rewrite (bmmap.c RefreshUnitsOnBmMap):
-- `units` as M.berserkers', `Board` its too (Board.FOG_BITS) -> { [addr] = bits }, for M.putFog
function M.keptFog(mem, Board, units)
    local out = {}
    for _, o in pairs(units) do
        if o.faction == "red" then out[o.addr] = mem.u32(o.addr + UNIT_STATE) & Board.FOG_BITS end
    end
    return out
end
-- ... put back on each unit's state word, its other bits as they are now (`kept` may be nil)
function M.putFog(api, Board, kept)
    for addr, bits in pairs(kept or {}) do
        api.write32(addr + UNIT_STATE, (api.mem.u32(addr + UNIT_STATE) & ~Board.FOG_BITS) | bits)
    end
end

-- Whether a berserk strike (t.berserk) kills its target on the phase's expected way: its HP
-- `left` after the strike's expected damage. Such a target is taken off the map for the units
-- after it, as nextPhase takes one; an enemy's own strike keeps its target (the judged phase
-- reads it on the target's whole odds).
function M.berserkKills(t, left) return t.berserk == true and left <= 0 end

-- An enemy's status staff (#674) as its decision names it: AI_ACTION_STAFF (cp_staff.c
-- AiStaffSleepBerserk, AiStaffSilence: AiSetDecision's target and item slot) with a staff whose
-- hit sets a status (Board.STATUS_STAVES) in the decided slot of the unit at `actor`. `D` =
-- gAiDecision. -> { target = its id, status, tile = { x, y } }, or nil for any other act (a
-- heal staff's included: it sets no status, and the judged phase does not play it)
function M.staffAct(mem, Board, D, actor)
    local DEC = Board.AI_DEC
    if mem.u8(D + DEC.ACTION) ~= Board.AI_ACTION_STAFF then return nil end
    local item = mem.u16(actor + Board.UNIT_ITEMS + mem.u8(D + DEC.SLOT) * 2) & 0xFF
    local status = Board.STATUS_STAVES[item]
    if not status then return nil end
    return { target = mem.u8(D + DEC.TARGET), status = status,
             tile = { x = mem.u8(D + DEC.X), y = mem.u8(D + DEC.Y) } }
end
-- An enemy thief's steal as its decision names it: AI_ACTION_STEAL (cp_battle.c
-- AiAttemptStealActionWithinMovement: AiSetDecision's tile, target and the item's slot in the
-- target's bag, taken from the highest-ranked item among every unit the thief can stand beside,
-- the game's own choice, ADR 0379). `D` = gAiDecision. -> { steal = true, target = the id, slot,
-- tile = { x, y } the thief stands on }, or nil for any other act
function M.stealAct(mem, Board, D)
    local DEC = Board.AI_DEC
    if mem.u8(D + DEC.ACTION) ~= Board.AI_ACTION_STEAL then return nil end
    return { steal = true, target = mem.u8(D + DEC.TARGET), slot = mem.u8(D + DEC.SLOT),
             tile = { x = mem.u8(D + DEC.X), y = mem.u8(D + DEC.Y) } }
end
-- ActionSteal's bag change (bmmind.c:365), inside a sandbox: both bags are kept first (api.keep16),
-- since the game's own UnitRemoveItem and UnitAddItem write a unit struct that a nested sandbox
-- does not undo, and one plan's theft would leak into the next plan's board. The target's drop
-- flag goes when the slot is its last item (an api write, journaled), the item leaves its bag
-- (UnitRemoveItem packs it) and UnitAddItem puts it in the thief's first free slot (the AI steals
-- only with one, cp_battle.c:46). A gold item (which ActionSteal pays into the party's gold
-- instead) is never on the AI's steal list, so it is not handled. -> the item's id
function M.moveItem(api, call, S, Board, from, slot, to)
    local mem = api.mem
    local raw = mem.u16(from + Board.UNIT_ITEMS + slot * 2)
    local count = 0
    for i = 0, Board.ITEM_COUNT - 1 do
        if mem.u16(from + Board.UNIT_ITEMS + i * 2) ~= 0 then count = count + 1 end
    end
    local state = mem.u32(from + UNIT_STATE)
    if state & Board.US_DROP_ITEM ~= 0 and slot == count - 1 then
        api.write32(from + UNIT_STATE, state & ~Board.US_DROP_ITEM)
    end
    api.keep16(from + Board.UNIT_ITEMS, Board.ITEM_COUNT)
    api.keep16(to + Board.UNIT_ITEMS, Board.ITEM_COUNT)
    call(S.UnitRemoveItem, { from, slot })
    call(S.UnitAddItem, { to, raw })
    return raw & 0xFF
end
-- A theft played on the board, inside an open sandbox: the thief `e` stood on the act's tile
-- (`standOn`), the item moved from the target's bag to its own (a theft never misses), so a later
-- enemy decides on the board it leaves and a second thief finds the item gone. -> { thief,
-- target, item, lock = true when the target opened a chest before and no longer does }
function M.pilfer(api, call, S, Board, standOn, e, act)
    local addr = api.mem.u32(S.gUnitLookup + act.target * 4)
    local chests = M.LOCK_TERRAIN.chests
    local was = M.opensAt(call, S, addr, chests)
    standOn(e, act.tile.x, act.tile.y)
    local item = M.moveItem(api, call, S, Board, addr, act.slot, e.addr)
    return { thief = e.id, target = act.target, item = item,
             lock = was and not M.opensAt(call, S, addr, chests) }
end
-- What an enemy's decision is, and which handler plays it: a steal (M.stealAct) before a staff
-- (M.staffAct), each an act of its own; else a strike when the AI named a target; else none. The
-- one dispatch of enemyPhase's ways and nextPhase's first phase, so a new act is added once.
-- `on` = { steal, staff, strike, none } functions; -> what the chosen one returns.
function M.stepOf(act, target, on)
    if act and act.steal then return on.steal(act) end
    if act then return on.staff(act) end
    if target then return on.strike(target) end
    return on.none()
end
-- The strikes of a phase's way after one more act: `done`'s, then the strike `t` (nil for a
-- theft), and the thefts so far, then `theft` (a list read by the planner as `.thefts`; the
-- copy is new, so a way never changes the list another way holds). The one owner of how a
-- way's list carries them: a thief that steals after another enemy struck keeps its record.
function M.chain(done, t, theft)
    local now = {}
    for x = 1, #done do now[x] = done[x] end
    if t then now[#now + 1] = t end
    now.thefts = done.thefts
    if theft then
        now.thefts = {}
        for x, th in ipairs(done.thefts or {}) do now.thefts[x] = th end
        now.thefts[#now.thefts + 1] = theft
    end
    return now
end
-- The phase's result list: the likeliest outcome `top`'s strikes and thefts, every outcome and
-- the unsplit count riding on it (what enemyPhase returns).
function M.phaseList(top, outcomes, unsplit)
    local out = {}
    for x, t in ipairs(top.strikes) do out[x] = t end
    out.thefts = top.strikes.thefts
    out.outcomes, out.unsplit = outcomes, unsplit
    return out
end
-- Whether the player's unit `o` (Board.read's) is asleep or berserked once the next player
-- phase's start ticks it (Board.statusAfter, one start): the army's reply between the
-- lookahead's phases leaves it where it stands, as the planner's own `held` (Board.statusHeld)
-- leaves it on the player's turn. A berserked one moves in the berserk phase instead.
function M.heldAtReply(mem, Board, o)
    return Board.statusHeld(Board.statusAfter(mem.u8(o.addr + Board.UNIT_STATUS), 1))
end
-- A status staff's hit on the unit at `addr`: the status for SetUnitStatus's turns (bmbattle.c
-- BattleApplyUnitUpdates writes statusOut through it). The AI casts only on a living unit with no
-- status (AiStaffSleepBerserk), so a unit an earlier strike of the way killed, or that has a
-- status already, takes none.
function M.setStatus(api, Board, addr, status)
    local mem = api.mem
    if mem.u8(addr + UNIT_HP) == 0 or Board.statusOf(mem.u8(addr + Board.UNIT_STATUS)) ~= 0 then
        return
    end
    api.write8(addr + Board.UNIT_STATUS, status | (Board.STATUS_TURNS << 4))
end

-- What a phase start's two calls left on the board, for M.aiPhaseStart's `known`:
-- gAiState.bestBlueMov and every unit's aiFlags. Read inside the sandbox that started the
-- phase, before any decision (a decision writes its own unit's flags).
function M.phaseStarted(mem, S, units)
    local known = { mov = mem.u8(S.gAiState + AI_BEST_MOV), flags = {} }
    for _, o in pairs(units) do known.flags[o.addr] = mem.u8(o.addr + M.UNIT_AI_FLAGS) end
    return known
end

-- What a kept phase start (M.phaseStarted) is kept by: each unit's HP, state word and AI scripts
-- (ai1, ai2: a plan's wait that wakes an enemy, M.areaWake, writes them, and ChangeUnitAi flags
-- an ai2 of AI_B_0C, which the start's kept aiFlags would write over) as they read now, by
-- its address. They are what the two calls read that a sandbox can have staged
-- (a plan's HP, a unit hidden, carried or off the map), so a strike asked inside a staged
-- board finds no start kept for it and makes its own; a unit's Mov and bag change only with
-- the board (`seen`).
function M.phaseKey(mem, units)
    local parts = {}
    for _, o in pairs(units) do
        parts[#parts + 1] = ("%x:%d:%x:%d:%d"):format(o.addr, mem.u8(o.addr + UNIT_HP),
                                                      mem.u32(o.addr + UNIT_STATE),
                                                      mem.u8(o.addr + UNIT_AI1),
                                                      mem.u8(o.addr + UNIT_AI2))
    end
    table.sort(parts)
    return table.concat(parts, ",")
end

-- One enemy decision's calls after its field writes (cp_decide.c CpDecide_Main's loop body):
-- the per-unit setup, then the decision. `stale` = an enemy's HP was written since the heal
-- flags were last read: UpdateAllPhaseHealingAIStatus leads, as the game runs it after every
-- act (cp_perform.c CpPerform_Cleanup). Run before every decision it changed nothing where no
-- HP had (the flag is HP against two thresholds, the exit one never under the enter one,
-- cp_data.c gAI3HealingThresholdTable, and only that function writes it) and was 36,166 calls
-- in a vanilla Ch5 attempt. `split` = the caller acts between the two (a phase start leads
-- the setup, or the targets are narrowed after it): -> setup, decide; else one list, nil.
function M.decisionCalls(S, unit, stale, split)
    local setup = { { S.RefreshEntityBmMaps, {} }, { S.AiUpdateNoMoveFlag, { unit } },
                    { S.AiInitDangerMap, {} } }
    if stale then table.insert(setup, 1, { S.UpdateAllPhaseHealingAIStatus, {} }) end
    local decide = { { S.AiClearDecision, {} }, { S.AiDecideMain, {} } }
    if split then return setup, decide end
    setup[#setup + 1], setup[#setup + 2] = decide[1], decide[2]
    return setup, nil
end

function M.equip(api, call, S, u, slot)
    if not slot or slot <= 0 then return end
    api.keep16(u.addr + api.Board.UNIT_ITEMS, slot + 1)
    call(S.EquipUnitItemSlot, { u.addr, slot })
end

-- Inside a sandbox: `u`'s strike from (x, y) on the wall `o` ({ x, y, hp }), as the Attack
-- menu forecasts it (AttackMapSelect_SwitchIn: the wall's place and HP in gActionData, then
-- InitObstacleBattleUnit and BattleGenerateSimulation with no target unit) -> { dealt = the HP
-- it takes off the wall, wear = the uses it spends (M.worn), wearSlot (M.wearSlotOf), wearAt =
-- the same uses by the HP the wall had lost before each blow (M.wornBy) }. A wall never
-- counters and every blow on it lands (ComputeBattleObstacleStats: hit 100, crit 0), so the
-- forecast's one way is the strike's only one; a planner reads its wear at the HP an earlier
-- blow of its plan leaves the wall (Planner.wearAt), as for a unit.
function M.strikeWallIn(api, call, S, u, o, x, y, slot)
    local mem = api.mem
    api.write8(S.gActionData + ACTION_X_OTHER, o.x)
    api.write8(S.gActionData + ACTION_Y_OTHER, o.y)
    api.write8(S.gActionData + ACTION_TRAP_TYPE, o.hp)
    call(S.InitObstacleBattleUnit, {})
    call(S.BattleGenerateSimulation, { u.addr, 0, x, y, slot or M.ISLOT_AUTO })
    local worn = M.worn(mem, S.gBattleActor)
    local at = M.wornBy(api.Board.hits(), { actor = M.spendRule(mem, S.gBattleActor),
                                            target = { unbreakable = true } },
                        { actor = worn, target = 0 })
    return { dealt = M.lost(mem, S.gBattleTarget), wear = worn,
             wearSlot = M.wearSlotOf(mem, S.gBattleActor), wearAt = at.actor }
end

-- The phase's wear ledger (#644 review): per unit (its struct's address) and bag slot, the
-- uses the phase is expected to have taken off that item so far (`total`) and the whole uses
-- already written off it (`taken`). Each strike adds its expected wear to the total, and the
-- item has lost the rounded total: three strikes at 0.45 on a 1-use stone spend it (1.35, and
-- the stone is gone 83% of the time), where rounding each strike alone never would. A ledger is
-- never changed in place: the phase splits into ways (M.phaseWays) and each way keeps the
-- ledger its own strikes left. -> the ledger with `expected` more on (addr, slot), and the
-- uses to take off the item now. Pure.
function M.tally(ledger, addr, slot, expected)
    local rows = {}
    for k, row in pairs(ledger[addr] or {}) do rows[k] = row end
    local row = rows[slot] or { total = 0, taken = 0 }
    local total = row.total + expected
    local n = math.floor(total + 0.5) - row.taken
    rows[slot] = { total = total, taken = row.taken + n }
    local out = {}
    for k, v in pairs(ledger) do out[k] = v end
    out[addr] = rows
    return out, n
end

-- The ledger after the item in `slot` of the unit at `addr` is gone and its bag packed
-- (UnitRemoveInvalidItems): the item's row dropped, the rows of the slots after it one slot
-- down, as their items are. Pure.
function M.packed(ledger, addr, slot)
    local rows = {}
    for k, row in pairs(ledger[addr] or {}) do
        if k < slot then rows[k] = row elseif k > slot then rows[k - 1] = row end
    end
    local out = {}
    for k, v in pairs(ledger) do out[k] = v end
    out[addr] = rows
    return out
end

-- Where the item of bag slot `k` is after EquipUnitItemSlot(`slot`) (bmitem.c: the item of
-- `slot` to the front, the ones before it each one slot back). Pure.
function M.afterEquip(slot, k)
    if not k or not slot or slot <= 0 then return k end
    if k == slot then return 0 end
    if k < slot then return k + 1 end
    return k
end

-- Inside a sandbox: the unit at `addr` after a battle that is expected to take `expected` uses
-- off the item in its bag slot `slot` (0-based), as the game leaves it (#644): the uses the
-- ledger's rounded total now takes (M.tally), one GetItemAfterUse each (Board.itemAfterUse: an
-- IA_UNBREAKABLE item keeps its uses, the last use leaves 0), the item written back to its slot
-- (BattleApplyUnitUpdates) and the bag packed (UpdateUnitFromBattle's UnitRemoveInvalidItems),
-- so a weapon spent to 0 is gone and the unit fights the rest of the phase unarmed (vanilla
-- Ch19: Myrrh, charId 0x1E, read at 0% death with the Divinestone she had spent). The phase is
-- played along its expected way, as a strike takes its expected damage rounded. No slot (a
-- ballista's strike, or a counter that wrote nothing back: M.wearSlotOf) or one past the bag (a
-- borrowed item's 0xFF) is no item of the unit's. The packing is a game write no journal sees,
-- so the bag is kept first (M.equip's reason). -> the ledger after it.
function M.wear(api, call, S, ledger, addr, slot, expected)
    local Board = api.Board
    if not expected or expected <= 0 or not slot or slot < 0 or slot >= Board.ITEM_COUNT then
        return ledger
    end
    local n
    ledger, n = M.tally(ledger, addr, slot, expected)
    if n <= 0 then return ledger end
    local at = addr + Board.UNIT_ITEMS + slot * 2
    local item = api.mem.u16(at)
    for _ = 1, n do
        if item == 0 then break end
        item = Board.itemAfterUse(item)
    end
    api.write16(at, item)
    if item == 0 then
        api.keep16(addr + Board.UNIT_ITEMS, Board.ITEM_COUNT)
        call(S.UnitRemoveInvalidItems, { addr })
        ledger = M.packed(ledger, addr, slot)
    end
    return ledger
end

-- Inside a sandbox: a ballista's strike spends the ballista's own uses, which live on its trap
-- (BattleApplyBallistaUpdates writes the battle weapon's uses to TRAP_EXTDATA_BLST_ITEMUSES),
-- never its rider's bag (M.wearSlotOf). At 0 GetBallistaItemAt gives no weapon, so a phase
-- after (the lookahead's second) finds it spent. `trap` = its sTrapPool entry, its own row in
-- the ledger (M.tally). -> the ledger after it.
function M.wearBallista(api, ledger, trap, expected)
    if not expected or expected <= 0 then return ledger end
    local n
    ledger, n = M.tally(ledger, trap, 0, expected)
    if n > 0 then
        local at = trap + M.TRAP_BLST_USES
        api.write8(at, math.max(0, api.mem.u8(at) - n))
    end
    return ledger
end

-- Inside a sandbox: a phase strike `t` (M.strikeOf's) leaves both weapons at the uses it is
-- expected to spend: the striker's at `strikerAddr`, the target's counter's at `targetAddr`.
-- -> the ledger after it (M.wear).
function M.strikeWear(api, call, S, ledger, t, strikerAddr, targetAddr)
    ledger = M.wear(api, call, S, ledger, strikerAddr, t.wearSlot, t.wear)
    return M.wear(api, call, S, ledger, targetAddr, t.counterSlot, t.counterWear)
end

-- Inside a sandbox: our unit `u` holding what the plan leaves it to fight the enemy phase with:
-- the weapon of its act's `slot` equipped (M.equip puts it in slot 0), less the uses that act
-- is expected to spend (`wear`) off the item the battle used (`wearSlot`, the bag slot before
-- the equip: an attack the game armed itself, slot nil, used its first usable weapon, which
-- need not be slot 0), #644. -> the ledger after it (M.wear).
-- The ledger's rows of the unit at `addr` after EquipUnitItemSlot(`slot`) moved its bag
-- (M.afterEquip): each row follows its item, so a use the phase already counted on the sword
-- stays on the sword when a javelin is brought to the front (PR #645 re-review). Pure.
function M.equipRows(ledger, addr, slot)
    if not slot or slot <= 0 or not ledger[addr] then return ledger end
    local rows = {}
    for k, row in pairs(ledger[addr]) do rows[M.afterEquip(slot, k)] = row end
    local out = {}
    for k, v in pairs(ledger) do out[k] = v end
    out[addr] = rows
    return out
end

function M.armAsPlanned(api, call, S, ledger, u, slot, wearSlot, wear)
    M.equip(api, call, S, u, slot)
    ledger = M.equipRows(ledger, u.addr, slot)
    return M.wear(api, call, S, ledger, u.addr, M.afterEquip(slot, wearSlot), wear)
end

-- Inside a sandbox: the wear a staged plan starts its phase with (stagePhase), -> the ledger
-- (M.tally). Our units armed as the plan leaves them (M.armAsPlanned: `blues`' slot, wearSlot,
-- wear), and each enemy's weapon worn by its counters to the plan's attacks (#644 review: one
-- whose counter spent its last javelin struck with it in the phase): `redWear` = { [id] =
-- { [slot] = uses } }, each slot as the board's bag has it, so the highest slot first (a
-- packed bag moves only the slots after the one emptied). `byId` = the board's units by id.
function M.stageWear(api, call, S, plan, byId)
    local ledger = {}
    for _, b in ipairs(plan.blues) do
        ledger = M.armAsPlanned(api, call, S, ledger, b.unit, b.slot, b.wearSlot, b.wear)
    end
    for id, slots in pairs(plan.redWear or {}) do
        local e = byId[id]
        local order = {}
        for slot in pairs(slots) do order[#order + 1] = slot end
        table.sort(order, function(a, b) return a > b end)
        for _, slot in ipairs(order) do
            if e then ledger = M.wear(api, call, S, ledger, e.addr, slot, slots[slot]) end
        end
    end
    return ledger
end

-- The ledger the strikes `done` of a phase's way leave: the last one's (`after`, keyed by the
-- strike), or the phase's `base` when none struck. Pure.
function M.ledgerAfter(after, base, done)
    local last = done[#done]
    return last and after[last] or base
end

-- Inside a sandbox: phase strike `t` (M.strikeAt's, of `side`, the enemy at `strikerAddr` on the
-- unit at `targetAddr`) wears its weapons on the ledger the way's earlier strikes `done` left
-- (M.ledgerAfter), and the ledger it leaves is kept as after[t] for the strikes after it in its
-- way (M.phaseWays splits a phase; each way carries its own). A ballista's strike (its slot
-- BALLISTA_SLOT) wears the trap its rider sits on (sTrapPool[ballistaIndex], M.wearBallista).
function M.strikeLedger(api, call, S, after, base, done, t, side, strikerAddr, targetAddr)
    local ledger = M.ledgerAfter(after, base, done)
    if side.slot == BALLISTA_SLOT then
        ledger = M.wearBallista(api, ledger,
            S.sTrapPool + api.mem.u8(strikerAddr + M.UNIT_BALLISTA) * M.TRAP_SIZE, t.wear)
    end
    after[t] = M.strikeWear(api, call, S, ledger, t, strikerAddr, targetAddr)
    return after[t]
end

-- Inside a sandbox: the army reply's killer `u` armed as its kill `k` (M.replyKills', its weapon
-- `k.slot`) leaves it: that weapon equipped, less the uses the kill's exchange (`kill`, its
-- side as `exchange` reads it: wear, wearSlot) is expected to spend, on `ledger`. -> the ledger.
function M.replyArm(api, call, S, ledger, u, k, kill)
    return M.armAsPlanned(api, call, S, ledger, u, k.slot, kill.wearSlot, kill.wear)
end

-- Sight.fullInfo(sandbox, open, api, S, isolate, fn): FR-019's full-information diagnostic
-- (R-7), never production. fn(board) runs in one outermost sandbox with the fog off -- the
-- vision range (gPlaySt +0D) written 0 through the journaled api, then the game's own
-- RefreshEntityBmMaps, whose RefreshUnitsOnBmMap clears US_BIT9 on every red it now sees
-- (bmmap.c) -- and is handed the board read there, no unit `fogged`. That one write is all it
-- changes: an arrival is a unit no event has loaded yet, and no RNG is drawn, so neither is
-- revealed. The game's writes (unit states, the fog and unit maps) are not journaled, so only
-- the outermost load undoes them: inside an open sandbox it refuses. isolate() swaps the
-- caller's caches for fresh ones and returns their restore, run however fn ends: an answer
-- read with the fog off must not be kept for the fogged board.
function M.fullInfo(sandbox, open, api, S, isolate, fn)
    if open() then
        error("sight.lua: fullInfo inside an open sandbox would leak its game writes", 0)
    end
    return M.isolated(sandbox, isolate, function(call)
        api.write8(S.gPlaySt + PLAY_VISION, 0)
        call(S.RefreshEntityBmMaps, {})
        return fn(api.board())
    end)
end

-- Sight.isolated(sandbox, isolate, fn): fn(call) in a sandbox, the caller's board answers
-- swapped for fresh ones for it: isolate() swaps them and returns their restore, run however
-- fn ends. A read on a board the sandbox changed (fullInfo's fog off, changed's board) must not be
-- kept for the board as it is. fullInfo's and Sight.changed's one shape.
function M.isolated(sandbox, isolate, fn)
    local restore = isolate()
    local ok, a, b = pcall(sandbox, fn)
    restore()
    if not ok then error(a, 0) end
    return a, b
end

-- Inside a sandbox: every map change in `set` ({ ["x,y"] = true }: the doors a plan opens and
-- the walls it breaks) applied, M.openMap's. The judged phase's (enemyPhase) and changed's.
function M.openAll(api, call, S, set)
    for at in pairs(set or {}) do
        local x, y = at:match("^(%d+),(%d+)$")
        M.openMap(api, call, S, tonumber(x), tonumber(y))
    end
end

-- Inside a sandbox: unit `e` hidden from the AI (US_HIDDEN: its target loops skip it; it keeps its
-- gBmMapUnit entry, so it still blocks), the write journaled. The one owner of the hide: takeOff,
-- onlyTarget. -> a function that writes the state word back as it was.
function M.hideUnit(api, e)
    local was = api.mem.u32(e.addr + UNIT_STATE)
    api.write32(e.addr + UNIT_STATE, was | api.Board.US_HIDDEN)
    return function() api.write32(e.addr + UNIT_STATE, was) end
end

-- Inside a sandbox: unit `e`, standing on (x, y), off the map as a death takes it -- off
-- gBmMapUnit, and US_HIDDEN, which RefreshUnitsOnBmMap skips (bmmap.c) -- every write
-- journaled. The judged phase's (a kill, a counter's) and Sight.changed's.
function M.takeOff(api, e, x, y)
    M.liftOff(api, x, y, e.id)
    M.hideUnit(api, e)
end

-- The answers a changed board starts from (s.changed): none of `kept`'s, but the march cost
-- grids when `keepGrids` (terrain's alone: no unit blocks them) and the danger and threat grids
-- when `keepDanger` (no door opened and nothing remembered died). A kill changes neither
-- grid: GenerateDangerZoneRange counts a hidden unit (bmidoten.c skips only the roofed and the
-- fogged), and a red's movement is blocked by no red, so the dead enemy's reach stays. The
-- threat table is shared, not copied, so a grid read on that board stays for the next.
function M.freshSeen(kept, keepGrids, keepDanger)
    return { threats = keepDanger and kept.threats or {},
             danger = keepDanger and kept.danger or nil,
             grids = keepGrids and kept.grids or {} }
end

-- Sight.changed(sandbox, api, S, isolate, change, byId, fn, prime): fn() run on the board a plan's
-- changes leave, in one sandbox whose journal undoes them when it returns: change.opened
-- ({ ["x,y"] = true }, the doors it opens and walls it breaks, M.openAll) and change.gone
-- ({ [id] = true }, the enemies it kills, M.takeOff; byId: the units by id, where each stands).
-- The planner's re-listing (#661, #670) asks there which tiles the units still to act now
-- reach, and their acts from those. Every write is journaled, so unlike fullInfo it may run
-- inside a batch. isolate() as M.isolated's: a read on the changed board must not be kept for
-- the board as it is; prime(units), when given, is handed the units read once there.
function M.changed(sandbox, api, S, isolate, change, byId, fn, prime)
    return M.isolated(sandbox, isolate, function(call)
        M.openAll(api, call, S, change.opened)
        for id in pairs(change.gone or {}) do
            local e = byId[id]
            if e then M.takeOff(api, e, e.x, e.y) end
        end
        -- prime(units): the board's units read once, on the board the changes leave, for every
        -- read fn makes (a sandbox open keeps no read of its own: keptRead)
        if prime then prime(api.board().units) end
        return fn()
    end)
end

-- Whether red unit `u` is one a retry remembers: `keys` = { [Board.memoryKey] = true } (s.knows).
-- `arrival`: the turn `u` arrived on (nil or 0 for one on the field at the start). A unit that
-- arrived is asked by its class and turn alone, never by the slot it landed in; one on the field
-- at the start by its slot (Board.memoryKey, ADR 0449). So a memory of the start's unit in a slot
-- does not name an arrival that took the slot later, nor the reverse.
function M.knows(Board, keys, u, arrival)
    return keys ~= nil and u ~= nil
        and keys[Board.memoryKey(u.id, u.charId, u.classId, arrival)] == true
end

-- Whether an enemy with unit state `state` counts as seen (Board.playsAsSeen, the game's US_BIT9
-- its fog): what both judged phases' decides, closings' looters and keySources ask.
function M.playsAsSeen(Board, state, knows)
    return Board.playsAsSeen((state & Board.US_BIT9) ~= 0, knows)
end

-- #713 fix 1 (ADR 0455): red unit `u`'s ghost, the record `seen[u.id]` of where this attempt
-- last saw it ({ charId, classId, arrival, x, y }, s.sighted), when `u` is in fog now and is
-- the same unit: its character, class and arrival turn (`arrival`, s.arrivalOf: a slot an
-- arrival refilled is another unit). `known`: a retry remembers it (ADR 0399), which plays it
-- where it stands, so it has no ghost. A player knows where he last saw an enemy, not where it
-- went in the fog: the bot plays it from there, never from its true tile.
function M.ghostOf(seen, u, known, arrival)
    local g = seen and seen[u.id]
    if g and u.faction == "red" and u.onField and not u.dead and u.fogged and not known
        and g.charId == u.charId and g.classId == u.classId and g.arrival == arrival then
        return g
    end
    return nil
end

-- Every unit of `list` that has a ghost record (M.ghostOf), whether or not its tile is free:
-- -> { { unit, g } }. M.ghostsOn's candidates, and s.changed's tiles a kill may free.
function M.ghostCandidates(list, seen, known, arrivalOf)
    local out = {}
    for _, o in ipairs(list) do
        local g = M.ghostOf(seen, o, known(o), arrivalOf(o))
        if g then out[#out + 1] = { unit = o, g = g } end
    end
    return out
end

-- Whether placeGhosts may place now: `state` = the scope's ghosts (nil outside a ghostly()
-- scope, false before placing, a table after), `scopeLevel` its sandbox depth, `level` the
-- depth now. -> "place", "placed" (done for this scope), or raises: outside a scope, or in a
-- sandbox nested in it (its journal would move the ghosts back while the scope still names them).
function M.ghostPlacing(state, scopeLevel, level)
    assert(state ~= nil, "placeGhosts outside a ghostly sandbox")
    assert(level == scopeLevel, "placeGhosts in a sandbox nested in its ghostly scope")
    return state and "placed" or "place"
end

-- The ghosts that play among `list` (#713, ADR 0455): -> { [id] = { x, y } }, each unit's
-- M.ghostOf tile, when no unit the player can see stands there -- a unit of another faction,
-- a red in sight, or a fogged one a retry remembers (known(o)) -- and no ghost seen there more
-- recently (`seq`, s.sighted's order) claims it. A hidden red there blocks nothing: the player
-- cannot know it is there. at(o) -> x, y where o stands now, or nil for a unit that holds no
-- tile there. The board's `at` is its read tile: a unit off the field or dead is skipped by
-- the onField and dead tests here. A sandbox's is its struct's, where a staged plan has stood
-- the player's units, and nil for one the sandbox took off (US_HIDDEN: a judged kill).
-- The one owner of the rule, for s.ghostOf (the board's) and placeGhosts (a sandbox's).
function M.ghostsOn(list, seen, known, arrivalOf, at)
    local cand = M.ghostCandidates(list, seen, known, arrivalOf)
    local out = {}
    for _, c in ipairs(cand) do
        local g, held = c.g, false
        for _, b in ipairs(list) do
            if b.id ~= c.unit.id and b.onField and not b.dead
                and (b.faction ~= "red" or not b.fogged or known(b)) then
                local bx, by = at(b)
                held = held or (bx == g.x and by == g.y)
            end
        end
        for _, d in ipairs(cand) do
            held = held or (d ~= c and d.g.x == g.x and d.g.y == g.y and d.g.seq > g.seq)
        end
        if not held then out[c.unit.id] = { x = g.x, y = g.y } end
    end
    return out
end

-- canExplore's memo key: the act, the tile and the tile's terrain (an opened chest's changes)
function M.exploreKey(kind, x, y, terrain) return kind .. "@" .. x .. "," .. y .. "#" .. terrain end

-- M.watched(cpu) -> a cpu that asks `watch()` before it runs a game call's frames, and
-- set(watch | nil), which names it. The one place every simulation passes through however
-- deep its sandboxes nest, so a caller can end a read that runs away: what watch raises
-- unwinds through each sandbox, which puts its writes back on the way (s.watch; botrun's
-- decision budget, ADR 0411).
function M.watched(cpu)
    local watch
    return setmetatable({ frames = function(done, max)
        if watch then watch() end
        return cpu.frames(done, max)
    end }, { __index = cpu }), function(fn) watch = fn end
end

-- The HP a heal tile gives: `pct` (TerrainTable_HealAmount's s8, read as a register: 0x80 and
-- up is negative) of `maxHp`, truncated toward zero as C's `/ 100` does (Lua's `//` floors).
function M.terrainHealPoints(pct, maxHp)
    if pct >= 0x80 then pct = pct - 0x100 end
    local n = pct * maxHp
    return n >= 0 and n // 100 or -((-n) // 100)
end

function M.new(outer)
    local watchedCpu, setWatch = M.watched(outer.cpu)
    outer = setmetatable({ cpu = watchedCpu }, { __index = outer })
    -- outer.leakGuard (PT_LEAKGUARD=1): the run's leak log. Every nested sandbox hands the
    -- unit structs and the trap pool back as it found them, or what it did not is logged
    -- there and put back (M.leaks). The units are the board's, read each time.
    local sandbox, api, open, level
    sandbox, api, open, level = M.batching(outer, outer.leakGuard and function()
        local spans = { { outer.SYM.sTrapPool, M.TRAP_MAX * M.TRAP_SIZE, "trap pool" } }
        for _, o in ipairs(api.board().units) do
            spans[#spans + 1] = { o.addr, outer.Board.UNIT_SIZE, "unit struct" }
        end
        return spans
    end, outer.leakGuard)
    local mem, S, Board = api.mem, api.SYM, api.Board
    local US_HIDDEN, US_UNDER_A_ROOF = Board.US_HIDDEN, Board.US_UNDER_A_ROOF
    local w, h = api.map()
    -- outer.strikeCheck (PT_STRIKECHECK=1): the run's log for the bot's strike-memo guard
    -- (bot.lua strike), which reads it as s.strikeCheck
    local s = { cache = {}, odds = M.odds, splitFloor = M.SPLIT_FLOOR, strikeCheck = outer.strikeCheck }
    -- Every read `fn` makes, in ONE save and load (see sandbox above).
    function s.batch(fn) return sandbox(function() return fn() end) end
    -- watch() is asked before every game call from now on (nil: no longer): M.watched.
    s.watch = setWatch
    local seen   -- this board's answers, dropped by refresh()
    local remembered   -- remember()'s keys: { [Board.memoryKey] = true }, nil on attempt 1
    -- #713 (ADR 0455): where this attempt last saw each red unit, by slot (s.sighted, M.ghostOf),
    -- and the ghosts placed in the sandbox open now: nil outside a ghostly() one, false in one
    -- before placeGhosts ran, { [id] = true } after (the ghosts standing on their tile)
    -- `ghostLevel`: the sandbox depth the open ghostly() scope runs at; `sightings` orders
    -- the records (M.ghostsOn's `seq`)
    local lastSeen, ghosts, ghostLevel, sightings = {}, nil, nil, 0

    -- The board's units, read once per board like every other answer: kept only from a read
    -- made with no sandbox open, the live board (refresh() takes it, so a decision's batch finds
    -- it there), or from s.changed's prime (one read on the changed board). One read inside a
    -- sandbox may see its writes -- a unit stood elsewhere, its HP set, a bag a game call
    -- reordered -- so it is read fresh and dropped.
    local function units()
        return M.keptRead(seen, "units", function() return api.board().units end, open)
    end

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
    -- Inside a sandbox: the flag unit `charId`'s death sets, its GetDefeatTalkEntry row's (quote
    -- text or none); nil when it has no row. Read at the start: the rows are the chapter's.
    local function defeatFlag(call, charId)
        local ent = call(S.GetDefeatTalkEntry, { charId })
        return ent ~= 0 and mem.u16(ent + M.DEFEAT_TALK_FLAG) or nil
    end
    -- The units whose death ends the game, on any side (an escort's too): the game's own death
    -- step, run in one sandbox. SetPidDefeatedFlag sets the unit's flag -- but never
    -- EVFLAG_GAMEOVER for the chapter's protected unit on a non-story map -- and that flag is
    -- what RunWaitEvents ends the game on. Each unit's flag is cleared after (ClearFlag) before
    -- the next is read: GetDefeatTalkEntry skips a row whose flag is set.
    -- The same pass finds the boss: the red unit whose death raises EVFLAG_DEFEAT_BOSS (its
    -- row's flag) -- how the game itself ends the chapter, not CA_BOSS, which a boss on a cloned
    -- generic row (Manchego Stars ch03's grell) does not carry. On a Defeat Boss goal that flag
    -- is the win. On any other goal it is the win only when the flag makes the Misc list offer a
    -- new WIN event (M.winEvent: vanilla Ch13's `DefeatBoss(scr)` = AFEV(EVFLAG_WIN, scr,
    -- EVFLAG_DEFEAT_BOSS), Main_Code_Helpers.h): a Seize map's boss has the same row (Ch3's
    -- Bazba) and ends nothing, and Ch1's Misc list offers a TMP flag's event, not a WIN (#721).
    local read = sandbox(function(call, info)
        local out, boss = {}, nil
        local before   -- the Misc list's scripts with no death flag set, read at the first candidate
        for _, u in ipairs(api.board().units) do
            local flag = u.onField and defeatFlag(call, u.charId)
            if flag then
                local candidate = not boss and u.faction == "red" and flag == M.EVFLAG_DEFEAT_BOSS
                if candidate and goal.kind ~= "boss" then
                    before = before or availableScripts(api, call, info, CHAPTER_MISC)
                end
                call(S.SetPidDefeatedFlag, { u.charId, flag })
                if call(S.CheckFlag, { M.EVFLAG_GAMEOVER }) & 0xFF ~= 0 then
                    out[#out + 1] = u.charId
                end
                if candidate then
                    if goal.kind == "boss"
                            or M.winEvent(before, availableScripts(api, call, info, CHAPTER_MISC)) then
                        boss = u.charId
                    end
                end
                call(S.ClearFlag, { flag })
            end
        end
        return { gameOver = out, boss = boss }
    end)
    s.objective.gameOver, s.objective.boss = read.gameOver, read.boss

    -- The chapter's recruit talks, searched once per Sight (the search runs the game's event
    -- walk): this Sight is made for one prep screen, as `commands` above is read once.
    local talks
    function s.demands()
        -- the party is every blue slot, benched units too (Board.read), so a recruit already
        -- in it is joined whether or not it is deployed
        local us, joined = units(), {}
        for _, u in ipairs(us) do
            if u.faction == "blue" then joined[u.charId] = true end
        end
        talks = talks or M.recruitTalks(M.talks(api, sandbox))
        local free = M.freeTalks(mem, talks, S.EventScr_9EEB00, joined)
        -- a lock a key may still be needed for: still shut, and some fielded unit's march reaches
        -- it (s.turnsTo: the game's costs, a closed door's own tile the field's start). `blues`
        -- are the units on the field at the prep screen (the game's default deployment), not
        -- Bot.team's pick: the team is chosen from these demands, so its deployment is not known
        -- yet, and a benched unit has no tile to march from. A lock only a benched flier would
        -- reach is not counted; its key then comes mid-map (supplyKey), a miss that costs a
        -- walk, where an over-count costs a bag slot for good. With no unit on the map yet
        -- nothing is known to be out of reach, so every shut lock counts.
        local blues = {}
        for _, u in ipairs(us) do
            if u.faction == "blue" and u.onField then blues[#blues + 1] = u end
        end
        local function needed(c)
            return M.lockNeeded(c, s.terrain(c.x, c.y), blues, s.turnsTo)
        end
        return M.demandsOf(us, commands, mem.u8(S.gPlaySt + PLAY_VISION), free, needed)
    end

    -- FE8's own march distance to `tile`: GenerateExtendedMovementMap from it, out to
    -- MAP_MOVEMENT_EXTENDED -- the map its AI heads for a far target over (cp_0803E2F4.c) --
    -- on `unit`'s movement costs (GetUnitMovementCost: its class's table for the weather).
    -- dist[y][x], nil = unreached. Units do not block it, as they do not block the AI's. One
    -- per class and tile for the board (a broken wall or an opened door changes the map).
    -- `classData` (optional) puts that class's costs on `unit` first, for a unit not loaded yet.
    local function costGrid(unit, tile, classData)
        local costGrids = seen.grids
        local cls = classData or mem.u32(unit.addr + UNIT_CLASS)
        local k = cls .. "@" .. tile.x .. "," .. tile.y
        if costGrids[k] == nil then
            costGrids[k] = sandbox(function(call)
                if classData then api.write32(unit.addr + UNIT_CLASS, classData) end
                local costs = call(S.GetUnitMovementCost, { unit.addr })
                call(S.GenerateExtendedMovementMap, { tile.x, tile.y, costs })
                local dist = {}
                for y = 0, h - 1 do
                    dist[y] = {}
                    for x = 0, w - 1 do
                        local v = grid(mem, S.gBmMapMovement, x, y)
                        if v ~= M.UNREACHED then dist[y][x] = v end
                    end
                end
                return dist
            end)
        end
        return costGrids[k]
    end
    local function movOf(unit) return M.movOf(mem, unit.addr) end
    -- Turns `unit` needs from `at` to `tile` on its own movement costs, nil = never.
    local function turnsTo(unit, tile, at)
        local cost = costGrid(unit, tile)[at.y][at.x]
        if not cost then return nil end
        return math.ceil(cost / movOf(unit))
    end
    function s.mov(u) return movOf(u) end
    -- the api's, for the goals: cost / UNIT_MOV NOT rounded (every step toward a goal counts;
    -- goals.lua rounds up where the real arrival matters), from `from` (default: where u stands)
    function s.turnsTo(u, tile, from)
        from = from or u
        local cost = costGrid(u, tile)[from.y][from.x]
        if not cost then return nil end
        return cost / movOf(u)
    end

    -- The march field from `tile` on `u`'s costs (costGrid, memoised per class and tile): from
    -- where a unit stands, the cost to every tile it could march to; dist[y][x], nil = never.
    function s.march(u, tile) return costGrid(u, tile) end

    -- What an item is worth: FE8's own GetItemCost (price per use x uses, bmitem.c) on the
    -- item at its full uses (GetItemMaxUses), the number the game sums for the party's worth.
    -- Its full uses are memoised beside it (`maxUses`): usePrice reads them on every strike
    -- the bot weighs, and a game call each time cost #642's price a quarter of its CPU.
    local prices, maxUses = {}, {}
    function s.itemCost(id)
        if prices[id] == nil then
            prices[id], maxUses[id] = sandbox(function(call)
                local uses = call(S.GetItemMaxUses, { id })
                return call(S.GetItemCost, { id | (uses << 8) }), uses
            end)
        end
        return prices[id]
    end
    -- What one use of an item costs (M.usePriceOf on the game's own two numbers). #642's
    -- weapon-use price.
    function s.usePrice(id)
        local cost = s.itemCost(id)
        return M.usePriceOf(cost, maxUses[id])
    end

    local raced = {}   -- village id -> the fastest red unit's turns (false: none reaches)
    local SIDES = { { 0, -1 }, { 1, 0 }, { 0, 1 }, { -1, 0 } }

    function s.answer(u, d)
        if d.kind == "enemy" then
            -- per weapon, its strike from the first side tile at its longest reach; the best
            -- (an answer first, then the strength)
            local e, best, strength = d.rep, nil, 0
            for _, wp in ipairs(s.weapons(u)) do
                for _, o in ipairs(SIDES) do
                    local x, y = e.x + o[1] * wp.max, e.y + o[2] * wp.max
                    local a = x >= 0 and y >= 0 and x < w and y < h
                        and s.attack(u, e, x, y, wp.slot)
                    if a then
                        local ok, str = M.answerOf(a, u.hp)
                        if best == nil or (ok and not best) or (ok == best and str > strength) then
                            best, strength = ok, str
                        end
                        break
                    end
                end
            end
            return best or false, strength
        elseif d.kind == "chests" or d.kind == "doors" then
            return s.opens(u, M.LOCK_TERRAIN[d.kind]), 0
        elseif d.kind == "fog" then
            return sandbox(function(call)
                return call(S.GetUnitFogViewRange, { u.addr })
            end) > mem.u8(S.gPlaySt + PLAY_VISION), 0
        elseif d.kind == "talk" then
            for _, talker in ipairs(d.talkers) do
                if talker == u.charId then return true, 0 end
            end
            return false, 0
        elseif d.kind == "sustain" then
            return #s.staves(u) > 0, 0
        elseif d.kind == "village" then
            if raced[d.id] == nil then
                local best = false
                for _, e in ipairs(units()) do
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
    -- unit alone -- class, level, HP, status, items, whether it rides a ballista (a rider has
    -- no weapon of its own: M.weapons) -- never on where anyone stands, so they outlive
    -- refresh(): keyed by those facts, a changed unit is simply a new key.
    local own = {}
    -- `hp` is "-" for an answer HP never moves (max HP)
    local function ownKey(kind, u, hp)
        local parts = { kind, u.id, u.classId or "-", u.level or "-", hp, u.status or "-",
                        M.riding(u.state) and "r" or "-" }
        for _, it in ipairs(u.items or {}) do parts[#parts + 1] = it.id .. "x" .. it.uses end
        return table.concat(parts, ":")
    end
    -- `hp` (optional): "-" for a read its HP does not change (s.salve); default u.hp
    local function mine(kind, u, ask, hp)
        local k = ownKey(kind, u, hp or u.hp)
        local v = own[k]
        if v == nil then
            v = ask()
            if v == nil then v = false end
            own[k] = v
        end
        return v or nil
    end

    function s.refresh()
        seen = M.freshSeen({}, false, false)
        units()
        s.objective.turnsLeft = goal.kind == "survive" and M.turnsLeft(goal.endTurn, api.turn())
            or nil
    end
    s.refresh()

    function s.newPhase()
        s.refresh()
        s.cache = {}
    end

    -- fn(board) with the fog off (M.fullInfo): the board's answers and the phase's cache are
    -- fresh for the call and the fogged ones come back after it
    -- the board's answers fresh for a changed board's read, and the phase's cache too unless
    -- `keepCache` (its memos key on the map, ctx.mapKey); the march cost grids too unless
    -- `keepGrids` (they are the terrain's alone: no unit blocks them, costGrid), the danger and
    -- threat grids too when `keepDanger` (M.freshSeen); -> their restore (M.isolated)
    local function fresh(keepCache, keepGrids, keepDanger)
        local keptSeen, keptCache = seen, s.cache
        seen = M.freshSeen(keptSeen, keepGrids, keepDanger)
        if not keepCache then s.cache = {} end
        return function() seen, s.cache = keptSeen, keptCache end
    end
    function s.fullInfo(fn)
        return M.fullInfo(sandbox, open, api, S, fresh, fn)
    end
    -- fn() on the board `change` leaves (M.changed). The phase's cache is kept: its memos
    -- (bot.lua's attacks and strikes) key on mapKey, which reads the opened map, and on every
    -- unit standing (a kill's board is another key). The cost grids are kept when no map
    -- changes: a kill moves no terrain. The units are read once on the changed board (prime):
    -- every nested sandbox in it already finds the board's read cached, as on the live board
    function s.changed(change, fn)
        local byId = {}
        for _, o in ipairs(units()) do byId[o.id] = o end
        local keepGrids = next(change.opened or {}) == nil
        -- a kill-only change keeps the danger and threat grids too (M.freshSeen), unless a
        -- killed enemy is one the retry remembers: liftRemembered lifts only a unit not hidden
        local keepDanger = keepGrids
        -- nor when one stood on the last-seen tile of a fogged unit (M.ghostOf): its death
        -- frees the tile for that ghost to play from (M.ghostsOn, #713)
        local ghostAt = {}
        for _, c in ipairs(M.ghostCandidates(units(), lastSeen, s.knows, s.arrivalOf)) do
            ghostAt[c.g.x .. "," .. c.g.y] = true
        end
        for id in pairs(change.gone or {}) do
            local k = byId[id]
            if k and (s.knows(k) or ghostAt[k.x .. "," .. k.y]) then keepDanger = false end
        end
        return M.changed(sandbox, api, S, function() return fresh(true, keepGrids, keepDanger) end,
                         change, byId, fn, function(list) seen.units = list end)
    end

    function s.remember(enemies)
        remembered = nil
        for _, e in ipairs(enemies or {}) do
            remembered = remembered or {}
            remembered[Board.memoryKey(e.id, e.charId, e.classId, e.arrival)] = true
        end
        -- every answer read before is without the memory; attempt 1 (none) keeps them
        if remembered then s.refresh() end
    end
    -- The turn each slot's present unit arrived on (botrun's stamp, ADR 0449): slot -> { charId,
    -- classId, turn }; `list` = { { id, charId, classId, turn } }. A slot another unit holds now
    -- has no arrival under this unit's name. The answers read before are without a changed
    -- arrival, so they are dropped (once per list), but only when one changes: the start's units
    -- (turn 0) are keyed by slot and change nothing.
    local arrivals = {}
    function s.arrived(list)
        local changed = false
        for _, e in ipairs(list) do
            local was = arrivals[e.id]
            local before = was and was.charId == e.charId and was.classId == e.classId
                and was.turn > 0 and was.turn or nil
            if (e.turn > 0 and e.turn or nil) ~= before then changed = true end
            arrivals[e.id] = { charId = e.charId, classId = e.classId, turn = e.turn }
        end
        -- a ghost is matched by its arrival too (M.ghostOf)
        if changed and (remembered or next(lastSeen)) then s.refresh() end
    end
    function s.arrivalOf(u)
        local a = arrivals[u.id]
        return a and a.charId == u.charId and a.classId == u.classId and a.turn or nil
    end
    function s.knows(u) return M.knows(Board, remembered, u, s.arrivalOf(u)) end
    function s.sighted(list)
        for _, u in ipairs(list) do
            sightings = sightings + 1
            lastSeen[u.id] = { charId = u.charId, classId = u.classId, arrival = s.arrivalOf(u),
                               x = u.x, y = u.y, seq = sightings }
        end
        if seen then seen.ghosts = nil end   -- boardGhosts' answer is read from these
    end
    -- the board's ghosts as read (units(), M.ghostsOn), kept with its other answers
    local function boardGhosts()
        return M.keptRead(seen, "ghosts", function()
            return M.ghostsOn(units(), lastSeen, s.knows, s.arrivalOf,
                              function(o) return o.x, o.y end)
        end, open)
    end
    -- u's ghost tile on the board as read, nil when it has none or its tile is taken
    function s.ghostOf(u) return boardGhosts()[u.id] end
    function s.plays(u) return s.knows(u) or (ghosts and ghosts[u.id]) == true end
    -- fn(call, proc) as a sandbox's body that may place the ghosts (placeGhosts): they stand on
    -- their tile until that sandbox returns, when M.batching's journal writes their structs and
    -- cells back. A sandbox opened inside one that placed them reads them where that one's play
    -- left them, and places none of its own.
    local function ghostly(fn)
        return function(call, proc)
            if ghosts ~= nil then return fn(call, proc) end
            ghosts, ghostLevel = false, level()
            local ok, a, b = pcall(fn, call, proc)
            ghosts, ghostLevel = nil, nil
            if not ok then error(a, 0) end
            return a, b
        end
    end
    -- In a ghostly() sandbox's own body (not a sandbox nested in it, whose journal would put the
    -- ghosts back while `ghosts` still named them), once: every ghost among `list` that plays
    -- there (M.ghostsOn, each unit where its struct stands: a staged plan's units are already on
    -- their tiles) stood on its last-seen tile (M.standOn: its struct and gBmMapUnit, journaled).
    local function placeGhosts(list)
        if M.ghostPlacing(ghosts, ghostLevel, level()) == "placed" then return end
        ghosts = {}
        local tiles = M.ghostsOn(list, lastSeen, s.knows, s.arrivalOf, function(o)
            if (mem.u32(o.addr + UNIT_STATE) & US_HIDDEN) ~= 0 then return nil end
            return mem.u8(o.addr + UNIT_X), mem.u8(o.addr + UNIT_Y)
        end)
        for _, o in ipairs(list) do
            local g = tiles[o.id]
            if g then
                if mem.u8(o.addr + UNIT_X) ~= g.x or mem.u8(o.addr + UNIT_Y) ~= g.y then
                    M.standOn(api, o, g.x, g.y)
                end
                ghosts[o.id] = true
            end
        end
    end
    -- Inside a sandbox: every remembered red's tile out of the fog (gBmMapFog 1), the one test
    -- GenerateDangerZoneRange skips a fogged unit by (bmidoten.c), so its reach counts as if seen.
    -- Where each stands and its fog bit are read off its unit struct, not the board's snapshot:
    -- inside nextPhase the first phase has moved them (armyReply's danger read)
    local function liftRemembered()
        if not remembered and not ghosts then return end
        for _, o in ipairs(units()) do
            local st = mem.u32(o.addr + UNIT_STATE)
            -- counts as seen (M.playsAsSeen): in sight, its tile is already out of the fog
            -- (inside nextPhase once M.refresh has run, as armyReply runs it first); in fog,
            -- remembered or a ghost on its last-seen tile (s.plays)
            if o.faction == "red" and o.onField and (st & US_HIDDEN) == 0
                and M.playsAsSeen(Board, st, s.plays(o)) then
                api.write8(cell(mem, S.gBmMapFog, mem.u8(o.addr + UNIT_X),
                                mem.u8(o.addr + UNIT_Y)), 1)
            end
        end
    end

    -- Inside a sandbox: the danger map (gBmMapRange, how many enemies reach each tile) on the
    -- board as it stands, every remembered red lifted out of the fog. GenerateDangerZoneRange
    -- counts every unit with a character, a hidden one too, and leaves out only one under a roof
    -- or in fog: a red `roofed(o, state)` names is put under a roof for the read, then taken out.
    -- s.danger's, s.threat's and armyReply's one reader.
    local function dangerGrid(call, roofed)
        local roof = {}
        for _, o in ipairs(units()) do
            local st = mem.u32(o.addr + UNIT_STATE)
            if o.faction == "red" and roofed and (st & US_UNDER_A_ROOF) == 0 and roofed(o, st) then
                api.write32(o.addr + UNIT_STATE, st | US_UNDER_A_ROOF)
                roof[#roof + 1] = o
            end
        end
        placeGhosts(units())
        liftRemembered()
        call(S.GenerateDangerZoneRange, { 0 })
        local g = readGrid(mem, S.gBmMapRange, w, h)
        for _, o in ipairs(roof) do
            api.write32(o.addr + UNIT_STATE, mem.u32(o.addr + UNIT_STATE) & ~US_UNDER_A_ROOF)
        end
        return g
    end

    function s.danger(x, y)
        if not seen.danger then
            seen.danger = sandbox(ghostly(function(call) return dangerGrid(call) end))
        end
        return seen.danger[y] and seen.danger[y][x] or 0
    end

    function s.threat(e)
        if not seen.threats[e.id] then
            seen.threats[e.id] = sandbox(ghostly(function(call)
                return dangerGrid(call, function(o) return o.id ~= e.id end)
            end))
        end
        local g = seen.threats[e.id]
        return function(x, y) return g[y] and g[y][x] or 0 end
    end

    -- Inside a sandbox, after a movement map for `u` standing on (ux, uy): the tiles it
    -- reaches (gBmMapMovement < MOVE_LIMIT), less those another unit stands on (gBmMapUnit),
    -- its own left in; with `friends`, an ally's tile too, marked `by`. reach's and
    -- cantoTiles' one reader.
    local function movementTiles(u, ux, uy, friends)
        local out = {}
        for y = 0, h - 1 do
            for x = 0, w - 1 do
                local by = grid(mem, S.gBmMapUnit, x, y)
                local own = x == ux and y == uy
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
    end

    -- Inside a sandbox: the tiles `u` reaches standing on (x, y) (its struct's own tile: the
    -- movement map reads where it stands), less a rider's forbidden ones. s.reach's,
    -- armyReply's and cantoTiles' readers.
    -- tilesIn: after a movement map is made (reachIn's, or cantoTiles' own Ext one), the tiles
    -- of it `u` may end on from (x, y). reachIn: the map from where it stands, then those.
    local function tilesIn(call, u, x, y, friends)
        return M.riderTiles(api, call, u, movementTiles(u, x, y, friends), { x = x, y = y })
    end
    local function reachIn(call, u, x, y, friends)
        call(S.GenerateUnitMovementMap, { u.addr })
        return tilesIn(call, u, x, y, friends)
    end

    function s.reach(u, friends)
        return sandbox(function(call) return reachIn(call, u, u.x, u.y, friends) end)
    end

    function s.weapons(u)
        return mine("weapons", u, function() return M.weapons(api, u, sandbox) end)
    end

    -- The widest max range of any weapon item in `u`'s bag (0: none): a superset of what the game
    -- counts (AiAttemptOffensiveAction's CanUnitUseWeapon, less ITEM_NIGHTMARE; `weapons` also
    -- drops a magic seal), for the bot's strike memo key (bot.lua strikeScope, strikeKey).
    function s.itemReach(u)
        local far = 0
        for _, it in ipairs(u.items or {}) do
            local _, mx = api.Board.itemRange(itemOf(it))
            if mx and mx > far then far = mx end
        end
        return far
    end

    -- Whether `e`'s decision can read reds that are not near it or its target, which the bot's
    -- strike memo keys whole-board: a ballista class or rider (AiAttemptBallistaCombat takes a
    -- ballista tile anywhere in its movement, cp_battle.c), a staff in its bag (AiTryDoStaff: a
    -- heal reaches an ally anywhere in its movement; Fortify counts every red with a flag,
    -- sub_803C364), or an AI script that can decide on one (M.scriptReadsReds).
    function s.readsReds(e)
        if M.riding(e.state) then return true end
        local chptr, clptr = mem.u32(e.addr), mem.u32(e.addr + UNIT_CLASS)
        local attrs = chptr ~= 0 and clptr ~= 0
            and (mem.u32(chptr + CLASS_ATTRIBUTES) | mem.u32(clptr + CLASS_ATTRIBUTES)) or 0
        if (attrs & M.CA_BALLISTAE) ~= 0 then return true end
        for _, it in ipairs(e.items or {}) do
            if api.Board.staffRange(itemOf(it)) then return true end
        end
        return M.scriptReadsReds(mem, S.gpAi1Table, mem.u8(e.addr + UNIT_AI1))
            or M.scriptReadsReds(mem, S.gpAi2Table, mem.u8(e.addr + UNIT_AI2))
    end

    -- fn(copy) with each of `values` (id | uses << 8) in the first empty slots of `u`'s bag: M.holding.
    function s.holding(u, values, fn) return M.holding(api, sandbox, u, values, fn) end

    function s.canSeize(u)
        return mine("seize", u, function() return M.canSeize(api, u, sandbox) end) or false
    end

    local function lost(bu) return M.lost(mem, bu) end

    -- One exchange as the forecast window reads it (`sim`, then InitBattleForecastBattleStats)
    -- and as it plays: the actor's side (M.side) with .counter the target's, .killsTarget the
    -- game's own simulation (every hit lands, nothing procs), and .dealt / .back its played
    -- distributions (M.exchangeOf). Inside a sandbox.
    -- The played outcomes, kept by what the game played them from (ADR 0377, reason 2: a
    -- MEASURED cost -- the Manchego Stars ch01 bot run took 7,266 simulations and 17.4 CPU s
    -- without it, 2,116 and 12.0 with it, against 827 and 10.5 before any were played): both
    -- battle units as the simulation set them up, every byte but where they
    -- stand and their ai_counter (M.battleWord), and gBattleStats' config and range. The
    -- chapter (BattleCheckSilencer reads it) is this sight's own.
    local playedBy = {}
    -- whether a strike on a player unit reads its counter's count: only the judged phase
    -- (s.enemyPhase) scores it; the lookahead's phases and a single strike's forecast do not
    local learning = false
    -- fn() with `learning` set to `v`, put back as it was after. No pcall: an error keeps its
    -- traceback, and leaves the flag at `v` only until the next entry sets its own, which
    -- costs reads at most (an unscored count), never a wrong score.
    local function learningAs(v, fn)
        local was = learning
        learning = v
        local out = fn()
        learning = was
        return out
    end
    local function battleKey()
        local parts = { mem.u32(S.gBattleStats) }
        for _, bu in ipairs({ S.gBattleActor, S.gBattleTarget }) do
            for at = 0, BU_SIZE - 4, 4 do
                parts[#parts + 1] = M.battleWord(at, mem.u32(bu + at))
            end
        end
        return table.concat(parts, ":")
    end

    -- `teaches`: the side ("actor" or "target") that is our unit, whose experience the exchange
    -- also reads (expOf). A key's actor is in it, so a key is always read for the same side.
    local function exchange(call, proc, sim, teaches)
        call({ sim, { S.InitBattleForecastBattleStats, { proc } } })
        local side = M.side(mem, S.gBattleActor, S.gBattleTarget, proc, PROC_HITS_A)
        side.counter = M.side(mem, S.gBattleTarget, S.gBattleActor, proc, PROC_HITS_B)
        side.killsTarget = mem.u8(S.gBattleTarget + UNIT_HP) == 0
        local known = M.known(playedBy, battleKey(), teaches,
            function() return M.expOf(api, call, S, teaches) end,
            function()
                local sides = { actor = side, target = side.counter }
                local dealt, back, joint, wear = M.exchangeOf(M.played(api.cpu, call, sim, S,
                    function()
                        local worn = { actor = M.worn(mem, S.gBattleActor),
                                       target = M.worn(mem, S.gBattleTarget) }
                        return lost(S.gBattleTarget), lost(S.gBattleActor), worn.actor,
                               worn.target, M.wornBy(Board.hits(), sides, worn)
                    end))
                return { dealt, back, joint, wear = wear }
            end)
        side.dealt, side.back, side.joint, side.exp = known[1], known[2], known[3], known[4]
        side.wear, side.wearAt = known.wear.actor, known.wear.actorAt
        side.counter.wear, side.counter.wearAt = known.wear.target, known.wear.targetAt
        return side
    end

    function s.attack(u, e, x, y, slot)
        local w = Board.weaponFor(s.weapons(u), x, y, e.x, e.y, slot)
        if not w then return nil end
        local ours = sandbox(function(call, proc)
            return exchange(call, proc,
                { S.BattleGenerateSimulation, { u.addr, e.addr, x, y, w.slot } }, "actor")
        end)
        return M.attackOf(ours, e.hp, u.hp)
    end

    -- `u`'s strike from (x, y) on the wall `o` ({ x, y, hp }), as the Attack menu forecasts
    -- it (AttackMapSelect_SwitchIn: the wall's place and HP in gActionData, then
    -- InitObstacleBattleUnit and BattleGenerateSimulation with no target unit) -> what the
    -- strike takes off the wall in the game's own simulation. Kept by the unit's facts and the
    -- wall, its HP too: the blow reads the attacker's might against the wall's class.
    function s.strikeWall(u, o, x, y, slot)
        -- the wall's HP is in the key: the read is HP lost, which the wall's HP caps
        return mine("wall@" .. o.x .. "," .. o.y .. "/" .. tostring(slot) .. "#" .. o.hp, u,
                    function() return sandbox(function(call)
            return M.strikeWallIn(api, call, S, u, o, x, y, slot)
        end) end)
    end

    local function standOn(u, x, y) M.standOn(api, u, x, y) end

    -- The red slots no unit is loaded in (pCharacterData 0), by id, as memory stands.
    local function freeRed()
        local out = {}
        for id = RED_FIRST, RED_LAST do
            local addr = mem.u32(S.gUnitLookup + id * 4)
            if addr ~= 0 and mem.u32(addr) == 0 then out[#out + 1] = { id = id, addr = addr } end
        end
        return out
    end

    -- Hides every other unit the AI could choose, so its own routine can only pick `u`. Hidden
    -- units keep their gBmMapUnit entries: they still block as they do.
    -- `all` is units(), read before the sandbox stood `u` elsewhere.
    local function onlyTarget(u, all)
        for _, o in ipairs(all) do
            if o.faction ~= "red" and o.id ~= u.id and o.onField then M.hideUnit(api, o) end
        end
    end

    -- Enemy `e`'s own decision on the board as it stands, inside a sandbox: cp_decide.c
    -- CpDecide_Main's per-unit step, in its order, with every player unit still visible: the
    -- AI's danger map (AiFillDangerMap) is their threat, and its tile choice reads it. The step
    -- is CpDecide_Main's loop body, not a function: CpDecide_Main itself would start
    -- gProcScr_CpPerform, which plays the act on the sandbox's next frame. So its field
    -- assignments are written here and its calls made. Left out: RenderBmMap and
    -- RefreshUnitSprites (they draw) and the US_HAS_MOVED_AI it sets after (read only by
    -- cp_order.c's list building, done before any decision). `all` = the board's units (M.keepAi keeps
    -- their AI bytes; the caller holds them, so no decision reads the board for it). `before`
    -- runs just ahead of the decision (strike() narrows the targets there). `starts` = the
    -- decision is its phase's first act and nothing ordered it (strike()): the phase start
    -- (M.aiPhaseStart) leads its calls. Any other decision is inside a phase aiOrder started,
    -- the faction red (asserted: decided on the player's, it would read the player phase's
    -- gAiState again). Its calls are M.decisionCalls's, the heal flags read again first when
    -- a staged phase wrote an enemy's HP since (`healStale`: wound() sets it).
    -- -> the struck unit's id and the strike as
    -- the forecast reads it (M.side, with slot and tile), or nil when the AI does not attack;
    -- then, when it casts a status staff (M.staffAct) or steals (M.stealAct) instead, the act as a
    -- third value.
    local healStale = false
    -- A simulated phase's own HP write, on the unit at `addr`: `decides` = it is of the side
    -- deciding, whose heal flags the next decision must read again.
    local function wound(addr, hp, decides)
        api.write8(addr + UNIT_HP, hp)
        if decides then healStale = true end
    end
    local function aiDecide(call, proc, e, all, before, starts, tileOnly)
        M.keepAi(api, all)
        M.keepMaps(api, all)   -- `setup` refreshes the maps
        M.keepRide(api, S, e, all)
        api.write32(S.gActiveUnit, e.addr)
        api.write8(S.gActiveUnitId, e.id)
        -- written before AiUpdateNoMoveFlag, which touches only gAiState.flags, so the calls
        -- run as one list (cp_decide.c's order kept)
        api.write8(S.gAiState + AI_DECIDE_STATE, 0)
        api.write8(S.gAiState + AI_STAFF_HP, 0)
        api.write8(S.gAiState + AI_WEIGHT_TABLE,
            (mem.u16(e.addr + UNIT_AI_CONFIG) & AI_WEIGHT_MASK) >> AI_WEIGHT_SHIFT)
        api.write8(S.gAiState + AI_DANGER_FILLED, 0)
        local setup, decide
        if starts then
            -- the phase start as the two calls leave it on these HPs and states, read once
            -- for them (M.phaseKey) on a board (`seen`, dropped by refresh()): the setup's
            -- three calls write no aiFlags and no bestBlueMov
            setup, decide = M.decisionCalls(S, e.addr, false, true)
            seen.phaseStart = seen.phaseStart or {}
            local key = M.phaseKey(mem, all)
            local known = seen.phaseStart[key]
            M.aiPhaseStart(api, call, S, all, setup, known)
            seen.phaseStart[key] = known or M.phaseStarted(mem, S, all)
        else
            -- the player's berserked unit decides in the berserk phase (M.berserkPhaseStart's,
            -- the player's faction)
            local phase = e.faction == "blue" and M.PHASES[1] or M.PHASES[3]
            assert(mem.u8(S.gPlaySt + PLAY_FACTION) == phase,
                   "sight: a unit decides inside a phase aiOrder or berserkPhaseStart started, "
                   .. "or starts its own")
            setup, decide = M.decisionCalls(S, e.addr, healStale, before ~= nil)
            call(setup)
        end
        healStale = false   -- a phase start reads them too
        if before then before() end
        if decide then call(decide) end
        if tileOnly then return nil, nil end   -- the caller reads the tile (gAiDecision), not the blow
        local D = S.gAiDecision
        local DEC = Board.AI_DEC
        if mem.u8(D + DEC.ACTION) ~= Board.AI_ACTION_COMBAT then
            return nil, nil, M.staffAct(mem, Board, D, e.addr) or M.stealAct(mem, Board, D)
        end
        local target = mem.u8(D + DEC.TARGET)
        local addr = mem.u32(S.gUnitLookup + target * 4)
        local sx, sy, slot = mem.u8(D + DEC.X), mem.u8(D + DEC.Y), mem.u8(D + DEC.SLOT)
        local sim = slot == BALLISTA_SLOT
            and { S.BattleGenerateBallistaSimulation, { e.addr, addr, sx, sy } }
            or { S.BattleGenerateSimulation, { e.addr, addr, sx, sy, slot } }
        -- a player unit struck (a blue index) learns from its counter: its side is read too.
        -- Not by our own berserked unit: a battle between two player units awards none
        -- (BattleApplyExpGains, M.taughtMiss)
        local teaches = learning and target < 0x40 and e.faction ~= "blue" and "target" or nil
        local side = exchange(call, proc, sim, teaches)
        side.slot, side.tile = slot, { x = sx, y = sy }
        return target, side
    end

    -- `e` may be a stand-in (#713 fix 3, ADR 0456): an arrival of s.arrivalUnits, whose `words`
    -- are loaded into a free red slot for the strike (M.standIn), `from` its tile. With no free
    -- slot it makes no strike.
    function s.strike(u, e, x, y, slot, from)
        local all = units()
        if e.words then
            local free = freeRed()
            if #free == 0 then return M.strikeOf(nil) end
            local f = free[#free]
            e = { id = f.id, addr = f.addr, words = e.words, faction = "red" }
        end
        local t = learningAs(false, function() return sandbox(function(call, proc)
            if e.words then M.standIn(api, e) end
            standOn(u, x, y)
            if from then standOn(e, from.x, from.y) end
            M.equip(api, call, S, u, slot)
            -- the strike is the enemy's phase too, started on the board as stood (`starts`).
            -- `u` is made the one target only after the danger map: the AI's target loops
            -- skips hidden units.
            local target, side = aiDecide(call, proc, e, all,
                                          function() onlyTarget(u, all) end, true)
            if target ~= u.id then return nil end
            return side
        end) end)
        return M.strikeOf(t)
    end

    -- the enemy's turn order, built as on its phase (cp_order.c) after the phase's own start
    -- (M.aiPhaseStart: the faction red, the heal flags the order reads), inside an open
    -- sandbox. `all` = the board's units, as aiDecide's.
    local function aiOrder(call, all)
        local n = M.aiPhaseStart(api, call, S, all, { { S.BuildAiUnitList, {} } })
        healStale = false
        if n > 0 then call(S.SortAiUnitList, { n }) end
        local out = {}
        for i = 0, n - 1 do out[#out + 1] = mem.u8(S.gAiState + i) end
        return out
    end
    -- after aiDecide(e): e stood where the decision moves it -> that tile, or nil when it
    -- performs nothing
    local function followMove(e)
        local D, DEC = S.gAiDecision, Board.AI_DEC
        if mem.u8(D + DEC.PERFORMED) == 0 then return nil end
        local x, y = mem.u8(D + DEC.X), mem.u8(D + DEC.Y)
        standOn(e, x, y)
        return x, y
    end

    -- The plan's Rescues and Drops, as the game writes them (bmunit.c UnitRescue,
    -- UnitDrop), inside an open sandbox: a carried unit off gBmMapUnit and hidden, so the AI
    -- never targets it (cp_battle.c skips US_RESCUED); its carrier US_RESCUING, so
    -- GetUnitSkill and GetUnitSpeed halve its stats in every forecast; a dropped one on its
    -- tile. `carry` is the planner's: [id] = { by = carrier } or { x, y } once dropped.
    -- `byId` is units() by id.
    local function stageCarry(byId, carry)
        local CARRY = Board.US_RESCUED | US_HIDDEN
        for id, c in pairs(carry or {}) do
            local t = byId[id]
            local r = t and byId[c.by or mem.u8(t.addr + Board.UNIT_RESCUE)]
            if t and c.by and r then
                local tx, ty = mem.u8(t.addr + UNIT_X), mem.u8(t.addr + UNIT_Y)
                M.liftOff(api, tx, ty, t.id)
                api.write32(t.addr + UNIT_STATE, mem.u32(t.addr + UNIT_STATE) | CARRY)
                api.write32(r.addr + UNIT_STATE, mem.u32(r.addr + UNIT_STATE) | Board.US_RESCUING)
                api.write8(t.addr + Board.UNIT_RESCUE, r.id)
                api.write8(r.addr + Board.UNIT_RESCUE, t.id)
                api.write8(t.addr + UNIT_X, mem.u8(r.addr + UNIT_X))
                api.write8(t.addr + UNIT_Y, mem.u8(r.addr + UNIT_Y))
            elseif t and c.x then
                api.write32(t.addr + UNIT_STATE, mem.u32(t.addr + UNIT_STATE) & ~CARRY)
                api.write8(t.addr + Board.UNIT_RESCUE, 0)
                if r then
                    api.write32(r.addr + UNIT_STATE,
                                mem.u32(r.addr + UNIT_STATE) & ~Board.US_RESCUING)
                    api.write8(r.addr + Board.UNIT_RESCUE, 0)
                end
                standOn(t, c.x, c.y)
            end
        end
    end

    -- The HP the tile `terrain` heals the unit at `addr`, the game's own: its table's percent of
    -- GetUnitMaxHp. One owner for the board's read (s.terrainHeal) and the sandbox's (healFaction).
    local healPct = {}
    local function healAmount(call, terrain, addr)
        assert(S.GetTerrainHealAmount, "sight.terrainHeal: symbols.lua lacks GetTerrainHealAmount (run gen_symbols.py)")
        local pct = healPct[terrain]
        if pct == nil then
            pct = call(S.GetTerrainHealAmount, { terrain })   -- a ROM table: read once a terrain
            healPct[terrain] = pct
        end
        if pct == 0 then return 0 end
        return M.terrainHealPoints(pct, call(S.GetUnitMaxHp, { addr }))
    end

    -- The start of `faction`'s phase inside a sandbox: each of its units the game would heal (not
    -- Board.terrainHealSkips) gains its tile's heal, held to its max HP (Board.addHp), where it
    -- stands NOW (the second phase's units have moved). The game does this at the start of each
    -- faction's own phase (MakeTerrainHealTargetList(gPlaySt.faction)) before anyone acts, and our
    -- plan's HP on the reds (plan.reds) is the unhealed one, so every phase the planner judges
    -- starts from the same HP the game's own would (#709). Each unit's own writes are independent,
    -- so the order of `byId` does not matter.
    local function healFaction(call, byId, faction)
        for _, o in pairs(byId) do
            if o.faction == faction and not Board.terrainHealSkips({ state = mem.u32(o.addr + UNIT_STATE) }) then
                local hp = mem.u8(o.addr + UNIT_HP)
                if hp > 0 then
                    local terrain = grid(mem, S.gBmMapTerrain, mem.u8(o.addr + UNIT_X), mem.u8(o.addr + UNIT_Y))
                    local heal = healAmount(call, terrain, o.addr)
                    if heal > 0 then
                        -- `decides`: only the reds, whose phase it is, read the heal flags again; a blue's or
                        -- green's heal changes no red's decision
                        wound(o.addr, Board.addHp(hp, heal, call(S.GetUnitMaxHp, { o.addr })),
                              faction == "red")
                    end
                end
            end
        end
    end

    -- the enemy phase against a staged plan, inside an open sandbox (enemyPhase, nextPhase):
    -- our units stood and their HP set, armed as the plan leaves them, the reds' HP and the
    -- uses their counters to our planned attacks spent, the gone off the map. `wearing.base` is
    -- the wear ledger (M.tally) the phase starts from: the plan's own wear on it.
    local function stagePhase(call, scratch, plan)
        local byId = {}
        for _, o in ipairs(units()) do byId[o.id] = o end
        for _, b in ipairs(plan.blues) do
            standOn(b.unit, b.x, b.y)
            api.write8(b.unit.addr + UNIT_HP, b.hp)
        end
        -- the ghosts (#713) after our units: a cell the plan stands a player unit on holds none
        placeGhosts(units())
        -- the waits the plan makes run the chapter's Misc events before the enemy phase: an AREA
        -- event that wakes an enemy (vanilla Ch16's Sage, #712) has done so by then
        seen.area = seen.area or { tiles = {}, scripts = {} }
        local _, area = M.areaWake(api, call, scratch, byId, plan.waits or {}, seen.area)
        for id, hp in pairs(plan.reds or {}) do
            if byId[id] then api.write8(byId[id].addr + UNIT_HP, hp) end
        end
        healFaction(call, byId, "red")   -- the reds' phase begins: a heal tile heals before any acts
        local wearing = { base = M.stageWear(api, call, S, plan, byId) }
        stageCarry(byId, plan.carry)
        local function remove(e, x, y) M.takeOff(api, e, x, y) end
        local gone = {}
        for id in pairs(plan.gone or {}) do
            gone[id] = true
            if byId[id] then remove(byId[id], byId[id].x, byId[id].y) end
        end
        -- the doors the plan opens and the walls it breaks (M.openMap): the enemies behind
        -- them reach through (vanilla Ch3: Colm opened (6,9) and the Brigand behind it killed
        -- him at 0%)
        M.openAll(api, call, S, plan.opened)
        -- The berserk phase (#660): the player's berserked units (M.berserkers, `after` as its)
        -- on a phase start of their own (M.berserkPhaseStart) -> their ids, in the game's order.
        -- Its decisions refresh the maps under the player's faction, which rewrites a red unit's
        -- fog bits (bmmap.c RefreshUnitsOnBmMap) to what the plan's units see; the enemy order
        -- after reads them as the phase found them (`fogWas`, put back by order()), so `decides`
        -- sees what it sees with no berserked unit (sight's keepMaps: the seen read is before any
        -- refresh). The bits are kept per phase, every way of it alike.
        local fogWas
        local function berserkFirst(after)
            local ids = M.berserkers(mem, Board, byId, after)
            fogWas = nil
            if #ids == 0 then return ids end
            fogWas = M.keptFog(mem, Board, byId)
            M.berserkPhaseStart(api, call, S, byId)
            healStale = false   -- the start's own heal statuses read every HP
            return ids
        end
        local function order()
            M.putFog(api, Board, fogWas)
            return aiOrder(call, byId)
        end
        -- an enemy in the order that decides: not gone; seen (US_BIT9: hidden by fog), or
        -- remembered (knows(): an earlier attempt at this start showed it, ADR 0399), or a
        -- ghost on its last-seen tile (plays(), #713, ADR 0455); or our berserked unit
        -- (M.berserkers, never fogged); and alive: a berserk strike's expected damage can
        -- leave its target at 0 HP on the map
        local function decides(id)
            local e = byId[id]
            if not e or gone[id] or mem.u8(e.addr + UNIT_HP) == 0 then return false end
            return M.playsAsSeen(Board, mem.u32(e.addr + UNIT_STATE), s.plays(e)) and e
        end
        -- e strikes as it decided: stood on its tile, its expected damage off the target, and
        -- the uses the exchange is expected to spend off both weapons (M.wear): a counter that
        -- spends the target's last use leaves it unarmed for the next enemy (#644). The ledger
        -- it adds to is the one the way's last strike (`done`'s) left, or the phase's base; the
        -- strike's own is kept beside it (`after`, weak: never on the strike, which is logged)
        local after = setmetatable({}, { __mode = "k" })
        local function strike(e, id, target, side, done)
            local addr = mem.u32(S.gUnitLookup + target * 4)
            local t = M.strikeAt(side, id, target, mem.u8(e.addr + UNIT_HP), mem.u8(addr + UNIT_HP),
                                 byId[target] and byId[target].level)
            local now = M.chain(done, t)
            standOn(e, side.tile.x, side.tile.y)
            local _, mean = M.odds({ t.takenDist }, t.targetHp)
            -- the target's heal flag is stale when it is of the deciding side (the faction whose
            -- heal statuses the phase reads): a red struck by the player's berserked unit is not
            local left = t.targetHp - math.floor(mean + 0.5)
            wound(addr, left, byId[target] ~= nil and byId[target].faction == e.faction)
            -- a strike by the player's berserked unit (#660), marked for the planner: its
            -- striker is one of the player's, whose death to the counter is a loss
            t.berserk = e.faction == "blue" or nil
            if M.berserkKills(t, left) and byId[target] then
                local o = byId[target]
                remove(o, mem.u8(o.addr + UNIT_X), mem.u8(o.addr + UNIT_Y))
            end
            M.strikeLedger(api, call, S, after, wearing.base, done, t, side, e.addr, addr)
            return t, now, addr
        end
        -- the ledger the strikes `done` leave (the base when none)
        function wearing.after(done) return M.ledgerAfter(after, wearing.base, done) end
        -- e casts the status staff it decided (#674, M.staffAct): stood on its tile, the hit's
        -- chance read there (GetOffensiveStaffAccuracy reads the distance; bmusemind.c
        -- ExecStatusStaff rolls it once) -> the chance, and land(), which sets the status. The
        -- statuses a hit sets act through the game's own reads: a sleeping unit gives no counter
        -- (the simulation), and a berserked one moves in the berserk phase (M.berserkers)
        local function cast(e, act)
            standOn(e, act.tile.x, act.tile.y)
            local addr = mem.u32(S.gUnitLookup + act.target * 4)
            local q = call(S.GetOffensiveStaffAccuracy, { e.addr, addr }) / 100
            return q, function() M.setStatus(api, Board, addr, act.status) end
        end
        -- e steals as it decided (#711, M.stealAct, M.pilfer)
        local function pilfer(call, e, act)
            return M.pilfer(api, call, S, Board, standOn, e, act)
        end
        return byId, order, decides, strike, remove, gone, wearing, berserkFirst, cast, pilfer, area
    end

    -- The phase over `list`, each enemy deciding in turn (M.phaseWays splits it where a counter
    -- may kill the striker) -> the likeliest outcome's strikes, with .outcomes and .unsplit.
    -- The berserk phase first (#660): `berserkFirst(after)` (stagePhase's) starts it and names
    -- the units it moves; each of its ways ends in the enemy phase `order()` lists on that way's
    -- board. `order` = stagePhase's, and `cast` (a status staff's, #674).
    local function playPhase(call, proc, byId, berserkFirst, after, order, decides, strike, remove,
                             mass0, cast, pilfer)
        local function ways(list, mass, tail, done0)
            return M.phaseWays(#list, function(k, done)
                local id = list[k]
                local e = decides(id)
                if not e then return nil end
                local target, side, act = aiDecide(call, proc, e, byId)
                return M.stepOf(act, target, {
                    -- a theft (#711): no strike and no chance, the board changes as it did; the
                    -- way's strikes list carries it (.thefts) for the planner's price
                    steal = function()
                        return { lands = 0 }, M.chain(done, nil, pilfer(call, e, act))
                    end,
                    -- a status staff (#674): no strike, its hit a way of its own
                    staff = function()
                        local q, land = cast(e, act)
                        return { lands = q }, done, land
                    end,
                    strike = function()
                        local t, now = strike(e, id, target, side, done)
                        return t, now, function() remove(e, side.tile.x, side.tile.y) end
                    end,
                    none = function() return nil end,
                })
            end, sandbox, nil, mass, tail, done0)
        end
        local outcomes, unsplit
        local berserk = berserkFirst(after)
        if #berserk > 0 then
            local enemy = 0
            outcomes, unsplit = ways(berserk, mass0, function(done, mass)
                local o, u = ways(order(), mass, nil, done)
                enemy = enemy + u
                return o
            end)
            unsplit = unsplit + enemy
        else
            outcomes, unsplit = ways(order(), mass0)
        end
        -- the list is the likeliest outcome's strikes; every outcome rides on it
        local top = outcomes[1]
        for _, o in ipairs(outcomes) do
            if o.p > top.p then top = o end
        end
        return M.phaseList(top, outcomes, unsplit)
    end

    function s.enemyPhase(plan)
        return learningAs(true, function() return sandbox(ghostly(function(call, proc)
            local byId, order, decides, strike, remove, _, _, berserkFirst, cast, pilfer, area =
                stagePhase(call, proc, plan)
            local out = playPhase(call, proc, byId, berserkFirst, 0, order, decides, strike, remove,
                                  plan.mass, cast, pilfer)
            -- what the plan's waits' events left unread (M.areaWake's stats), for the cost line
            out.areaPositional, out.areaTruncated = area.positional, area.truncated
            return out
        end)) end)
    end

    -- The army's reply between the lookahead's two enemy phases (#510 comment 6906859807): the
    -- turn our units would play there, read cheaply, in place of the hold. The hold read 71.5%
    -- death where 3.0% died: the army kills and blocks between the phases. First every kill
    -- our units can make at even odds or better (M.replyKills), taken as made, as nextPhase
    -- takes a striker our counter kills at even odds: its miss is not read (#510 PR 637 review:
    -- whether a kill the reply made left a death unread is checked on the runs, not assumed).
    -- The kill's chance is read once a weapon distance (the target's tile sets the blow), and
    -- every free tile at that distance offers it; the counter the killer takes is read again on
    -- the tile it is given, its weapon equipped as the attack would, and its expected damage
    -- stays on it (at 1 HP or more, as nextPhase keeps a striker's) and is reported as `lost`.
    -- Then each unit that killed nothing steps to the free tile in its reach that the fewest
    -- enemies left reach (M.safest), the most threatened first. Greens are the AI's and hold.
    -- Inside nextPhase's sandbox, after its first phase; `remove` is stagePhase's. The faction
    -- written for the danger read is put back, so the turn after reads the phase as the hold's.
    -- A killer's weapon loses the uses its kill is expected to spend (#644 review), on
    -- `wearing.base`, stagePhase's ledger, which the second phase then starts from.
    -- -> { kills = { { unit, enemy, x, y, p, lost } }, steps = { { unit, x, y } } }
    local function armyReply(call, proc, byId, remove, wearing)
        local ours, reds = {}, {}
        for _, o in pairs(byId) do
            local st = mem.u32(o.addr + UNIT_STATE)
            if (st & US_HIDDEN) == 0 and mem.u8(o.addr + UNIT_HP) > 0 then
                if o.faction == "blue" then
                    -- one asleep or berserked once the player phase's start ticks it (#674: the
                    -- enemy's staff) is the player's to move no more: it stands (bot.lua's
                    -- `held`, Board.statusHeld)
                    if not M.heldAtReply(mem, Board, o) then ours[#ours + 1] = o end
                elseif o.faction == "red" and M.playsAsSeen(Board, st, s.plays(o)) then
                    reds[#reds + 1] = o
                end
            end
        end
        local function byUnit(a, b) return a.id < b.id end
        table.sort(ours, byUnit)
        table.sort(reds, byUnit)
        local function at(o) return mem.u8(o.addr + UNIT_X), mem.u8(o.addr + UNIT_Y) end
        local function reach(u)
            local ux, uy = at(u)
            return reachIn(call, u, ux, uy)
        end
        local function strike(u, e, t, slot)
            return exchange(call, proc, { S.BattleGenerateSimulation,
                { u.addr, e.addr, t.x, t.y, slot } }, "actor")
        end
        local options = {}
        for _, u in ipairs(ours) do
            local weapons, tiles, uhp = s.weapons(u) or {}, reach(u), mem.u8(u.addr + UNIT_HP)
            for _, e in ipairs(reds) do
                local ex, ey = at(e)
                local ehp, read = mem.u8(e.addr + UNIT_HP), {}
                for _, t in ipairs(tiles) do
                    local d = math.abs(t.x - ex) + math.abs(t.y - ey)
                    if read[d] == nil then
                        local wp = Board.weaponFor(weapons, t.x, t.y, ex, ey)
                        read[d] = wp and { slot = wp.slot,
                                           p = M.attackOf(strike(u, e, t, wp.slot), ehp, uhp).kill }
                                  or false
                    end
                    if read[d] then
                        options[#options + 1] = { unit = u.id, enemy = e.id, tile = t,
                                                  p = read[d].p, slot = read[d].slot }
                    end
                end
            end
        end
        local out, acted = { kills = {}, steps = {} }, {}
        for _, k in ipairs(M.replyKills(options)) do
            local u, e = byId[k.unit], byId[k.enemy]
            local hp = mem.u8(u.addr + UNIT_HP)
            local kill = strike(u, e, k.tile, k.slot)
            local _, back = M.odds({ kill.back }, hp)
            remove(e, at(e))
            standOn(u, k.tile.x, k.tile.y)
            wearing.base = M.replyArm(api, call, S, wearing.base, u, k, kill)
            local left = math.max(1, hp - math.floor(back + 0.5))
            wound(u.addr, left, false)
            acted[u.id] = true
            out.kills[#out.kills + 1] = { unit = k.unit, enemy = k.enemy, x = k.tile.x,
                                          y = k.tile.y, p = k.p, lost = hp - left }
        end
        -- the threat left, read on our phase (GenerateDangerZoneRange reads the non-active
        -- side's) with the fog as the first phase left it; the gone stand under a roof for it
        M.refresh(api, call, S, byId)
        local faction = mem.u8(S.gPlaySt + PLAY_FACTION)
        api.write8(S.gPlaySt + PLAY_FACTION, M.PHASES[1])
        local danger = dangerGrid(call, function(_, st) return (st & US_HIDDEN) ~= 0 end)
        api.write8(S.gPlaySt + PLAY_FACTION, faction)
        local function threat(x, y) return danger[y] and danger[y][x] or 0 end
        local rest, onTile = {}, {}
        for _, u in ipairs(ours) do
            if not acted[u.id] then
                rest[#rest + 1] = u
                onTile[u.id] = threat(at(u))
            end
        end
        table.sort(rest, function(a, b)
            if onTile[a.id] ~= onTile[b.id] then return onTile[a.id] > onTile[b.id] end
            return a.id < b.id
        end)
        for _, u in ipairs(rest) do
            local ux, uy = at(u)
            local t = M.safest(reach(u), threat, { x = ux, y = uy })
            if t and (t.x ~= ux or t.y ~= uy) then
                standOn(u, t.x, t.y)
                out.steps[#out.steps + 1] = { unit = u.id, x = t.x, y = t.y }
            end
        end
        return out
    end

    -- The enemy phase AFTER the next one (#510 step 9's lookahead, FR-017), our units holding
    -- between (the R-8 spike's intervening player turn) unless `reply` asks armyReply's turn
    -- there (below). plan as enemyPhase's. The
    -- next phase is played along its expected way, unbranched: each enemy goes where its own
    -- decision takes it (a strike's tile, or the move it decides without striking), a strike
    -- takes its expected damage, a player unit left at 0 HP is off the map, and a striker our
    -- counter kills at even odds or better is gone. The turn then advances and the second phase
    -- is played as enemyPhase plays one, every way a counter may kill. Only what the player
    -- sees decides, in both: an enemy hidden by fog does not act unless a retry remembers it
    -- (knows(), ADR 0399) or this attempt saw it (a ghost, played from its last-seen tile:
    -- plays(), ADR 0455), and no arrival is placed (one not yet loaded is no unit to play).
    -- -> as enemyPhase, plus .hp = { [blue or green unit id] = its HP when the second phase
    -- begins, 0 when the first left it dead }
    -- and .moved = the units the first phase moved (enemies, and the player's berserked units,
    -- #660), { { id, x, y } }, .fell = the ids of the
    -- strikers our counters removed in it (a Rout's count, Planner.secondRead).
    -- `reply` (#510 comment 6906859807, ADR 0389's amendment of 2026-11-17): our units play
    -- armyReply's turn between the two phases in place of the hold; .reply = what they played.
    -- The planner asks it on every second phase but PT_REPLY=hold's.
    function s.nextPhase(plan, reply)
        return learningAs(false, function() return sandbox(ghostly(function(call, proc)
            local byId, order, decides, strike, remove, _, wearing, berserkFirst, cast, pilfer, area =
                stagePhase(call, proc, plan)
            local moved, fell = {}, {}
            -- the first phase's strikes in order, our berserked units' first (playPhase): each
            -- wears on what the last left (M.tally)
            local first = {}
            local function decideAll(ids)
                for _, id in ipairs(ids) do
                    local e = decides(id)
                    if e then
                        local target, side, act = aiDecide(call, proc, e, byId)
                        M.stepOf(act, target, {
                            -- a theft (#711): the board changes as it did (the first phase's
                            -- thefts are priced in enemyPhase; the lookahead reads its board)
                            steal = function()
                                pilfer(call, e, act)
                                moved[#moved + 1] = { id = id, x = act.tile.x, y = act.tile.y }
                            end,
                            -- a status staff (#674): it lands on the expected way when its hit
                            -- is even odds or better, as a counter kill is taken
                            staff = function()
                                local q, land = cast(e, act)
                                if q >= 0.5 then land() end
                                moved[#moved + 1] = { id = id, x = act.tile.x, y = act.tile.y }
                            end,
                            strike = function()
                                local t, now, addr = strike(e, id, target, side, first)
                                first = now
                                moved[#moved + 1] = { id = id, x = side.tile.x, y = side.tile.y }
                                -- (a berserk strike's kill: strike() took it off already)
                                if mem.u8(addr + UNIT_HP) == 0 and not t.berserk then
                                    local u = byId[target]
                                    if u then
                                        remove(u, mem.u8(u.addr + UNIT_X), mem.u8(u.addr + UNIT_Y))
                                    end
                                end
                                if t.felled >= 0.5 then
                                    remove(e, side.tile.x, side.tile.y)
                                    -- a Rout's count: the player's berserked unit is none of it
                                    if not t.berserk then fell[#fell + 1] = id end
                                else
                                    -- it lives: our counter's expected damage stays on it, as a
                                    -- strike's stays on its target
                                    local _, back = M.odds({ t.counterDist }, t.strikerHp)
                                    wound(e.addr, math.max(1, t.strikerHp - math.floor(back + 0.5)),
                                          true)
                                end
                            end,
                            none = function()
                                local x, y = followMove(e)
                                if x then moved[#moved + 1] = { id = id, x = x, y = y } end
                            end,
                        })
                    end
                end
            end
            decideAll(berserkFirst(0))
            decideAll(order())
            -- the second phase wears on what the first and the reply left
            wearing.base = wearing.after(first)
            -- the greens' phase and then the player's begin between the two reds' phases: a heal
            -- tile heals each of those units as it does the reds, before the army's reply moves
            -- (and `hp` below)
            healFaction(call, byId, "green")
            healFaction(call, byId, "blue")
            local played = reply and armyReply(call, proc, byId, remove, wearing) or nil
            -- player units and the greens: a green whose death ends the game is protected too
            local hp = {}
            for id, o in pairs(byId) do
                if o.faction ~= "red" then
                    local hidden = (mem.u32(o.addr + UNIT_STATE) & US_HIDDEN) ~= 0
                    hp[id] = hidden and 0 or mem.u8(o.addr + UNIT_HP)
                end
            end
            api.write16(S.gPlaySt + PLAY_TURN, mem.u16(S.gPlaySt + PLAY_TURN) + 1)
            -- the fog as the first phase leaves it (RefreshUnitsOnBmMap sets US_BIT9 there): an
            -- enemy that walked out of it is seen, one that walked into it is not
            M.refresh(api, call, S, byId)
            -- the second reds' phase begins (after the army's reply, as the game's)
            healFaction(call, byId, "red")
            -- our berserked units again, those the next player phase's start leaves berserked
            local out = playPhase(call, proc, byId, berserkFirst, 1, order, decides, strike,
                                  remove, nil, cast, pilfer)
            out.hp, out.moved, out.reply, out.fell = hp, moved, played, fell
            out.areaPositional, out.areaTruncated = area.positional, area.truncated
            return out
        end)) end)
    end

    -- When each village or chest still open (explorable()) closes: the first enemy phase,
    -- numbered from this turn's as 1, after which an enemy has looted it, nil = not within `k`
    -- (default M.CLOSE_HORIZON).
    -- The field's looters (a red unit whose own AI scripts loot, M.loots on its ai1 and ai2) and
    -- the units the caller watches (below) play k enemy phases forward with the game's own AI
    -- (aiDecide, as enemyPhase plays one), in the game's turn order, every other unit held where
    -- it stands and the player's hidden from the AI (the question is when a tile falls
    -- undefended): a looter's decision is AI_ACTION_PILLAGE on the tile, and it is stood where
    -- it decided to go. Only those decide: replaying every enemy for 8 phases on every decision
    -- tripled a Ch5 attempt's AI calls (3,787 -> 11,086). Read again only when a looter, a watched
    -- unit, a player unit or an open tile changed. A wave not
    -- loaded yet (waves = { { turn, units = { { class, x, y, ai1, ai2, items = {ids} } } } },
    -- the guide's reinforcements resolved) loots when an AI script of its does (M.loots), chests too
    -- when it can open one (M.opensChests): from its spawn tile, on its class's costs, as soon
    -- as its moves reach the tile (M.waveCloses). Read once per board.
    -- A unit the caller watches (`watch` = { [unit id] = true }: Goals.closings names the field's
    -- recruits) is played the same way, and when the game's AI decides to escape with it
    -- (AI_ACTION_ESCAPE: AiTryMoveTowardsEscape, set only when the escape point is within its
    -- move, and AiEscapeAction then clears the unit) the answer holds "unit:<id>" -> that enemy
    -- phase: the phase the game removes it, so a Talk to it after that is no Talk (#699). The
    -- second answer is { [unit id] = { [enemy phase] = {x, y} } }, where each watched unit stands
    -- after each phase before it is gone (M.carryPaths: the escape phase is left out, so a path
    -- is as long as its deadline less one). A watched unit that never left its tile with our
    -- units hidden is played again with them visible (M.secondLook, #724): the game's AI then
    -- moves it toward the units it can see. Our units are taken to stand still for all k
    -- phases, and only a unit that stayed put is read again. A scripted removal (a turn event's
    -- DISA or KILL) is not played here: s.scriptedUnits reads it off the script's bytes and
    -- Goals.closings folds it in (#724). All are estimates, as the chest closings are: a
    -- recruit's moves and its escape phase are the ones he makes with our units hidden (or, for
    -- the second look, where they stand now); the planner uses them as the deadline it is.
    -- closings() by what it reads: the turn, k, the waves, each looter or watched unit, and
    -- each player unit, as they stand (one an act kills, moves or hurts is a new read). newPhase()
    -- runs before every decision.
    local closingsAt = {}
    function s.closings(k, waves, watch)
        k = k or M.CLOSE_HORIZON
        local turn0 = mem.u16(S.gPlaySt + PLAY_TURN)
        local open, all = {}, units()
        for _, t in ipairs(s.explorable()) do open[t.x .. "," .. t.y] = t end
        local looter, looters, blockers = {}, {}, {}
        for _, o in ipairs(all) do
            if o.faction == "red" and o.onField and ((watch or {})[o.id]
                    or M.loots(mem, S.gpAi1Table, mem.u8(o.addr + UNIT_AI1))
                    or M.loots(mem, S.gpAi2Table, mem.u8(o.addr + UNIT_AI2))) then
                looter[o.id] = true
                looters[#looters + 1] = o
            elseif o.faction ~= "red" and o.onField then
                blockers[#blockers + 1] = o
            end
        end
        local ck = M.closingsKey(turn0, k, waves, looters, open, blockers, s.mapKey(), watch)
        if closingsAt[ck] then return closingsAt[ck].out, closingsAt[ck].paths end
        local out, paths = {}, {}
        local function close(x, y, phase)
            local key = x .. "," .. y
            if open[key] and (not out[key] or phase < out[key]) then out[key] = phase end
        end
        sandbox(function(call, proc)
            local byId = {}
            for _, o in ipairs(all) do byId[o.id] = o end
            local D, DEC = S.gAiDecision, Board.AI_DEC
            -- The enemy phases played, from the board as the sandbox it runs in found it: the units
            -- of `who` decide in the game's own order, `at` = each watched one's latest tile (a
            -- path of it is written to `into`), an escape is gone (`gone`, and out["unit:<id>"]),
            -- `onPillage(x, y, phase)` is asked of a looter's pillage, and `tileOnly` skips the
            -- battle simulation a decision to attack would run (only the tile it moves to is read).
            local function replay(who, at, into, gone, onPillage, tileOnly)
                for phase = 1, next(who) and k or 0 do
                    api.write16(S.gPlaySt + PLAY_TURN, turn0 + phase - 1)
                    for _, id in ipairs(aiOrder(call, all)) do
                        local e = who[id] and byId[id]
                        if e and M.playsAsSeen(Board, mem.u32(e.addr + UNIT_STATE), s.knows(e)) then
                            aiDecide(call, proc, e, all, nil, nil, tileOnly)
                            local x, y = followMove(e)
                            if x then
                                if at[id] then at[id] = { x = x, y = y } end
                                if mem.u8(D + DEC.ACTION) == Board.AI_ACTION_ESCAPE then
                                    -- gone this phase: it plays no more and holds no tile
                                    out["unit:" .. id] = out["unit:" .. id] or phase
                                    who[id], gone[id] = nil, true
                                elseif mem.u8(D + DEC.ACTION) == Board.AI_ACTION_PILLAGE and onPillage then
                                    onPillage(x, y, phase)
                                end
                            end
                        end
                    end
                    M.carryPaths(into, at, phase, gone)
                end
            end
            -- each watched unit's tile now (path[0] is the goal's own), and those that escaped
            local at, gone = {}, {}
            for id in pairs(watch or {}) do
                local e = looter[id] and byId[id]
                if e then at[id] = { x = e.x, y = e.y } end
            end
            -- The first look, in a sandbox of its own (rolled back when it returns: the second
            -- look starts from the board as it stood, its AI words, tiles, terrain and fog bits).
            -- The question is when a tile falls if no player unit defends it: our units are
            -- hidden from the AI (they still block, as onlyTarget leaves them), or a looter
            -- beside one attacks it every phase of the replay and never loots (vanilla Ch2:
            -- (1,12) read "closes on turn 5" until our units came near, then nothing, and fell).
            -- The phase start skips a hidden unit too (SetupUnitInventoryAIFlags), so the
            -- replay's gAiState.bestBlueMov is 0: no tile is kept from a looter for a faster
            -- player unit (cp_utility.c AiTryMoveTowards), the same question asked. Read off
            -- the decomp; its effect on a closing turn is not measured. A wave's reach follows
            -- in it: its class's costs, on a stand-in unit struct (any on the board).
            sandbox(function()
                for _, o in ipairs(all) do
                    if o.faction ~= "red" and o.onField then M.hideUnit(api, o) end
                end
                replay(looter, at, paths, gone, function(x, y, phase)
                    close(x, y, phase)
                    -- the tile is taken: AiPillageAction opens a chest (it empties) or runs the
                    -- village's tile change, which the replay does not play; a terrain off the AI's
                    -- loot lists (cp_utility.c gTerrainList_Lootable*) keeps it from being chosen
                    -- again, so the looter goes on to its next target
                    api.write8(cell(mem, S.gBmMapTerrain, x, y), M.sackedTerrain(open[x .. "," .. y]))
                end)
                local stand = all[1]
                for _, wv in ipairs(waves or {}) do
                    if wv.turn > turn0 and stand then
                        for _, wu in ipairs(wv.units) do
                            local cls = call(S.GetClassData, { wu.class })
                            local items = {}
                            for _, id in ipairs(wu.items or {}) do items[#items + 1] = { id = id } end
                            local villages = M.loots(mem, S.gpAi1Table, wu.ai1)
                                or M.loots(mem, S.gpAi2Table, wu.ai2)
                            local chests = villages
                                and M.opensChests(items, mem.u32(cls + CLASS_ATTRIBUTES), Board.ITEM_COUNT)
                            for _, t in pairs(open) do
                                -- a House is never looted (AiLocationIsPillageTarget: no House)
                                if (t.kind == "visit" and villages and not t.house)
                                        or (t.kind == "chest" and chests) then
                                    local cost = costGrid(stand, t, cls)[wu.y][wu.x]
                                    local turns = cost and math.ceil(cost / mem.s8(cls + CLASS_MOV))
                                    local at = M.waveCloses(wv.turn, turn0, turns)
                                    if at then close(t.x, t.y, at) end
                                end
                            end
                        end
                    end
                end
            end)
            -- The second look (#724): a watched unit that never left its tile with our units
            -- hidden is played again, in a sandbox of its own from the board as it stood, our
            -- units visible and standing where they do for all k phases (an estimate: they will
            -- move), so the game's AI decides where it goes, toward the units it can see. Only a
            -- unit that stayed put is read again: every other path is as it was.
            local starts = {}
            for id in pairs(watch or {}) do
                local e = byId[id]
                if e and at[id] then starts[id] = { x = e.x, y = e.y } end
            end
            M.secondLook(paths, starts, gone, function(again)
                return sandbox(function()
                    local there, second, escaped = {}, {}, {}
                    for id in pairs(again) do there[id] = { x = starts[id].x, y = starts[id].y } end
                    local goneAgain = {}
                    replay(again, there, second, goneAgain, nil, true)
                    for id in pairs(goneAgain) do escaped[id] = true end
                    return second, escaped
                end)
            end)
        end)
        closingsAt[ck] = { out = out, paths = paths }
        return out, paths
    end

    function s.terrain(x, y) return grid(mem, S.gBmMapTerrain, x, y) end
    -- The red units the game counts for a Rout (CountRedUnits, bmunit.c): every valid red not
    -- dead -- carried, hidden and fogged ones too. Read once per board.
    function s.redCount()
        if seen.redCount == nil then
            seen.redCount = sandbox(function(call) return call(S.CountRedUnits, {}) end)
        end
        return seen.redCount
    end
    function s.unseen()
        local out = {}
        for y = 0, h - 1 do
            for x = 0, w - 1 do
                if grid(mem, S.gBmMapFog, x, y) == 0 then out[#out + 1] = { x = x, y = y } end
            end
        end
        return out
    end

    function s.opens(u, terrain)
        return mine("opens" .. terrain, u, function() return sandbox(function(call)
            return M.opensAt(call, S, u.addr, terrain)
        end) end) or false
    end

    -- Whether `u` holding `item` would open `terrain` (M.keyItemOpens): the game's check reads
    -- UNIT_CATTRIBUTES, the character's and the class's (a thief's lockpick), and the item, so
    -- it is kept by all three.
    local wouldOpen = {}
    local function opensWith(u, item, terrain)
        local k = u.charId .. ":" .. u.classId .. ":" .. item .. ":" .. terrain
        if wouldOpen[k] == nil then
            wouldOpen[k] = sandbox(function(call)
                return M.keyItemOpens({ read16 = mem.u16, write16 = api.write16 }, call, S,
                                      Board, u.addr, item | (1 << 8), terrain)
            end)
        end
        return wouldOpen[k]
    end
    function s.keySources(u, terrain)
        local out = {}
        for _, e in ipairs(units()) do
            local last = e.items and e.items[#e.items]
            local st = e.state or 0
            if e.faction == "red" and e.onField and not e.dead and last
                and st & Board.US_DROP_ITEM ~= 0 and M.playsAsSeen(Board, st, s.knows(e))
                and opensWith(u, last.id, terrain) then
                out[#out + 1] = e
            end
        end
        return out
    end

    -- the convoy's key for `terrain` (a door's by default; a chest's for the chest goals, #699)
    function s.convoyKey(u, terrain)
        terrain = terrain or M.TERRAIN_DOOR
        return M.convoyKey(Board, mem, S, u, function(id) return opensWith(u, id, terrain) end)
    end

    -- (like opensDoor: the bot asks the one lock, not the terrain)
    function s.opensChest(u) return s.opens(u, M.LOCK_TERRAIN.chests) end
    function s.isChestLock(terrain) return terrain == M.LOCK_TERRAIN.chests end

    function s.locked(u, x, y)
        local t = s.terrain(x, y)
        if (t == M.LOCK_TERRAIN.doors or t == M.LOCK_TERRAIN.chests) and not s.opens(u, t) then
            return t
        end
        return nil
    end

    function s.opensDoor(u) return s.opens(u, M.LOCK_TERRAIN.doors) end
    function s.holdsKey(u) return s.opensDoor(u) or s.opensChest(u) end

    function s.canTalk(u, t)
        return sandbox(function(call)
            return call(S.CheckForCharacterEvents, { u.charId, t.charId }) & 0xFF ~= 0
        end)
    end

    local function asActive(u, x, y) M.asActive(api, u, x, y) end

    -- A razed village keeps its Visit command (GetAvailableTileEventCommand), but the Visit
    -- menu is shown to no one there (VisitCommandUsability reads the tile): ch02's (12,3) on
    -- turn 8. Silence greys it out and leaves it shown, so it stays open.
    local function visitShown(x, y)
        for _, u in ipairs(units()) do
            if u.faction == "blue" and u.onField and sandbox(function(call)
                asActive(u, x, y)
                return call(S.VisitCommandUsability, { 0, 0 }) ~= M.MENU_NOTSHOWN
            end) then return true end
        end
        return false
    end

    -- Whether the Visit at (x, y) is a House: its location entry (SearchAvailableEvent over the
    -- chapter's locationBasedEvents, as GetAvailableTileEventCommand finds it) has flag 0, so
    -- its Visit never closes and it marks nothing taken (eventinfo House(0, ...)); a village's
    -- entry sets a flag. `info` is a sandbox's scratch.
    local function isHouse(call, info, x, y)
        eventSearch(api, call, info, CHAPTER_LOCATIONS)
        api.write8(info + EVENT_X, x)
        api.write8(info + EVENT_Y, y)
        return call(S.SearchAvailableEvent, { info }) ~= 0 and mem.u32(info + EVENT_FLAG) == 0
    end

    function s.explorable()
        if not seen.explorable then
            seen.explorable = sandbox(function(call, info)
                local out = {}
                for _, c in ipairs(commands) do
                    local kind = (c.cmd == M.TILE_COMMAND_VISIT and "visit")
                        or (c.cmd == M.TILE_COMMAND_CHEST and "chest")
                    -- a chest another side has emptied keeps its tile command (a green unit
                    -- opened ours-ch03's (6,3)): only a full chest's terrain is one to open
                    if kind and call(S.GetAvailableTileEventCommand, { c.x, c.y }) == c.cmd
                        and (kind ~= "visit" or visitShown(c.x, c.y))
                        and (kind ~= "chest" or s.terrain(c.x, c.y) == M.TERRAIN_CHEST_FULL) then
                        out[#out + 1] = { x = c.x, y = c.y, kind = kind,
                                          house = kind == "visit" and isHouse(call, info, c.x, c.y)
                                              or nil }
                    end
                end
                return out
            end)
        end
        return seen.explorable
    end

    -- Usability reads the unit and the tile it stands on, never where anyone else is, and is
    -- only asked of a tile explorable() still offers: kept by the unit's facts, the tile and its
    -- terrain. The terrain is in the key because Usability reads it (ChestCommandUsability: a
    -- full chest), and another side may change it: a green unit opened ours-ch03's (6,3) and
    -- the kept yes sent unit 3 to an empty chest (held-out seed 2001, 2026-11-10).
    function s.canExplore(u, x, y, kind)
        return mine(M.exploreKey(kind, x, y, s.terrain(x, y)), u, function() return sandbox(function(call)
            asActive(u, x, y)
            local check = kind == "visit" and S.VisitCommandUsability or S.ChestCommandUsability
            return call(check, { 0, 0 }) == M.MENU_ENABLED
        end) end) or false
    end

    -- the unit menu's own check for each act it has one for (bmmenu.c)
    local MENU_CHECK = { talk = "TalkCommandUsability", door = "DoorCommandUsability",
                         visit = "VisitCommandUsability", chest = "ChestCommandUsability",
                         seize = "UnitActionMenu_CanSeize", rescue = "RescueUsability",
                         drop = "DropUsability", supply = "SupplyUsability" }

    -- whether the last target list built holds unit `id`, or the tile `at` with uid `uid` (a
    -- wall's is 0, a door's TERRAIN_DOOR: TryAddClosedDoorToTargetList)
    local function listed(call, id, at, uid)
        for k = 0, call(S.GetSelectTargetCount, {}) - 1 do
            local t = call(S.GetTarget, { k })
            if at then
                if mem.u8(t + 2) == (uid or 0) and mem.u8(t) == at.x and mem.u8(t + 1) == at.y then
                    return true
                end
            elseif mem.u8(t + 2) == id then
                return true
            end
        end
        return false
    end

    -- Inside a sandbox with the unit active: the unit menu's own check for `act` is enabled
    -- and, given a target, the list it built holds it (a unit by its id, a door by its tile).
    local function menuOffers(call, act, target)
        if call(S[MENU_CHECK[act]], { 0, 0 }) ~= M.MENU_ENABLED then return false end
        if not target then return true end
        if act == "door" then return listed(call, nil, target, M.TERRAIN_DOOR) end
        return listed(call, target.id)
    end

    function s.offers(u, tiles, act, target)
        return sandbox(function(call)
            local out = {}
            for _, t in ipairs(tiles) do
                asActive(u, t.x, t.y)
                if menuOffers(call, act, target) then out[#out + 1] = t end
            end
            return out
        end)
    end

    -- Where `u` may move on to after its act `a` on a.move (Canto, playerphase.c
    -- TryMakeCantoUnit): nothing for an act not in M.CANTO_ACTS, nor unless its character or class carries CA_CANTO, it has not
    -- already had its second move (US_HAS_MOVED) and the move to the act's tile left it Mov
    -- (moveCount, the movement map's cost of that tile). Then the game's own map from the
    -- act's tile with what is left (GenerateUnitMovementMapExt(unit, MOV - moveCount)), on the
    -- board as the act leaves it and as the game refreshes it before the second move
    -- (PlayerPhase_FinishAction: RefreshEntityBmMaps, so a Rescue's target is off the map and a
    -- Drop's on its tile), less every tile another unit stands on -> { {x, y} }, the act's tile
    -- among them. Kept for the board, per unit, tile and carry.
    function s.cantoTiles(u, a)
        if not M.CANTO_ACTS[a.act] then return {} end
        local x, y = a.move.x, a.move.y
        local carry = M.carryOf(a, u.id)
        local k = u.id .. "@" .. x .. "," .. y .. "/" .. (a.act == "rescue" and ("r" .. a.targetId)
            or a.act == "drop" and ("d" .. a.dropAt.x .. "," .. a.dropAt.y) or "-")
        seen.canto = seen.canto or {}
        if seen.canto[k] then return seen.canto[k] end
        local out = {}
        -- a unit with no character or class is no unit to move (and movOf reads the class)
        local chptr, clptr = mem.u32(u.addr), mem.u32(u.addr + UNIT_CLASS)
        local attrs = chptr ~= 0 and clptr ~= 0
            and (mem.u32(chptr + CLASS_ATTRIBUTES) | mem.u32(clptr + CLASS_ATTRIBUTES)) or 0
        if (attrs & M.CA_CANTO) ~= 0
                and (mem.u32(u.addr + UNIT_STATE) & Board.US_HAS_MOVED) == 0 then
            local mov = movOf(u)
            out = sandbox(function(call)
                call(S.GenerateUnitMovementMap, { u.addr })
                local spent = grid(mem, S.gBmMapMovement, x, y)
                if spent >= mov then return {} end
                local byId = {}
                for _, o in ipairs(units()) do byId[o.id] = o end
                standOn(u, x, y)
                stageCarry(byId, carry)
                M.refresh(api, call, S, byId)
                call(S.GenerateUnitMovementMapExt, { u.addr, mov - spent })
                return tilesIn(call, u, x, y)
            end)
        end
        seen.canto[k] = out
        return out
    end

    -- Each tile of `tiles` from which `u`, carrying a unit, may Drop it, and where: the game's
    -- own list (DropUsability builds it, bmtarget.c MakeDropTargetList: an empty adjacent tile
    -- the carried unit can stand on) -> { { x, y, drops = { {x, y} } } }
    function s.drops(u, tiles)
        return sandbox(function(call)
            local out = {}
            for _, t in ipairs(tiles) do
                asActive(u, t.x, t.y)
                if call(S[MENU_CHECK.drop], { 0, 0 }) == M.MENU_ENABLED then
                    local at = {}
                    for k = 0, call(S.GetSelectTargetCount, {}) - 1 do
                        local p = call(S.GetTarget, { k })
                        at[#at + 1] = { x = mem.u8(p), y = mem.u8(p + 1) }
                    end
                    if #at > 0 then out[#out + 1] = { x = t.x, y = t.y, drops = at } end
                end
            end
            return out
        end)
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
        local weapons = a.act == "attack" and s.weapons(u)
        local ok = sandbox(function(call)
            asActive(u, x, y)
            if a.act == "attack" then
                for _, w in ipairs(weapons) do
                    if a.slot == nil or a.slot == w.slot then
                        call(S.MakeTargetListForWeapon, { u.addr, itemOf(u.items[w.slot + 1]) })
                        if listed(call, a.targetId, a.obstacle) then return true end
                    end
                end
                return false
            elseif a.act == "item" then
                local it = u.items[a.slot + 1]
                return it ~= nil and call(S.CanUnitUseItem, { u.addr, itemOf(it) }) ~= 0
            elseif a.act == "supply" then
                -- the key the act names is still the convoy's for this unit
                local key = s.convoyKey(u, a.terrain)
                return menuOffers(call, "supply") and key ~= nil and key.id == a.item
                    and key.uses == a.uses
            elseif a.act == "drop" then
                return call(S[MENU_CHECK.drop], { 0, 0 }) == M.MENU_ENABLED
                    and listed(call, nil, a.dropAt)   -- a drop tile's uid is 0 (TryAddToDropTargetList)
            elseif MENU_CHECK[a.act] then
                local target = (a.act == "talk" or a.act == "rescue") and { id = a.targetId } or nil
                return menuOffers(call, a.act, target)
            end
            return true
        end)
        if ok and a.canto then
            for _, t in ipairs(s.cantoTiles(u, a)) do
                if t.x == a.canto.x and t.y == a.canto.y then return nil end
            end
            return "the game offers no Canto move to that tile"
        end
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
            return sandbox(function(call) return M.healStaves(api.Board, call, S, u) end)
        end)
    end

    function s.heals(u, x, y, hurt)
        local staves = s.staves(u)
        if #staves == 0 then return {} end
        if hurt then s.maxHps(hurt) end
        return sandbox(function(call)
            -- as the menu finds the healer: off the unit map, so it never lists itself
            asActive(u, x, y)
            -- a planned heal: these allies read as wounded, so the game's list offers them
            for _, o in ipairs(hurt or {}) do
                if mem.u8(o.addr + UNIT_HP) >= o.maxhp then api.write8(o.addr + UNIT_HP, o.maxhp - 1) end
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
                    out[#out + 1] = { slot = slot, targets = targets, exp = st.exp,
                                      amount = call(S.GetUnitItemHealAmount, { u.addr, item }) }
                end
            end
            return out
        end)
    end

    -- Each unit's max HP as the game reads it, GetUnitMaxHp: maxHP plus the equipped weapon's
    -- HP bonus, the cap AddUnitHp holds every heal to (bmunit.c). Set on each unit as `maxhp`,
    -- the misses asked in one sandbox.
    function s.maxHps(units)
        local miss = {}
        for _, u in ipairs(units) do
            if own[ownKey("maxhp", u, "-")] == nil then miss[#miss + 1] = u end
        end
        if #miss > 0 then
            sandbox(function(call)
                for _, u in ipairs(miss) do own[ownKey("maxhp", u, "-")] = call(S.GetUnitMaxHp, { u.addr }) end
            end)
        end
        for _, u in ipairs(units) do u.maxhp = own[ownKey("maxhp", u, "-")] end
    end

    -- healFaction on its own, the units as { faction, addr } by id (the phase's `byId`)
    function s.healFaction(byId, faction) sandbox(function(call) healFaction(call, byId, faction) end) end

    function s.terrainHeal(u)
        if Board.terrainHealSkips(u) then return 0 end
        local terrain = s.terrain(u.x, u.y)
        local k = ownKey("terrainheal", u, "-") .. ":" .. terrain
        if own[k] == nil then
            own[k] = sandbox(function(call) return healAmount(call, terrain, u.addr) end)
        end
        return own[k]
    end

    function s.mend(u)
        return mine("mend", u, function() return sandbox(function(call)
            for _, h in ipairs(M.selfHeals(api.Board, call, S, u)) do
                if call(S.CanUnitUseItem, { u.addr, h.item }) ~= 0 then
                    return { slot = h.slot, amount = h.amount }
                end
            end
            return nil
        end) end)
    end

    -- Whether `u` holds a heal for itself at all, whatever its HP now: the item s.mend offers
    -- once it is hurt (CanUnitUseItem refuses one at full HP). One read for every HP.
    function s.salve(u)
        return mine("salve", u, function() return sandbox(function(call)
            return #M.selfHeals(api.Board, call, S, u) > 0
        end) end, "-")
    end

    -- The map as a phase can change it: the terrain of every tile with a command (a door
    -- opened, a chest emptied, a village razed) and every wall's HP. Read once per board. A
    -- read kept across a board (bot.lua's phase memos of attacks and strikes) keys on it: an
    -- enemy's path runs through what the plan opened.
    function s.mapKey()
        if not seen.mapKey then
            local parts = {}
            for _, c in ipairs(commands) do parts[#parts + 1] = s.terrain(c.x, c.y) end
            for _, o in ipairs(s.obstacles()) do
                parts[#parts + 1] = o.x .. "," .. o.y .. "=" .. o.hp .. "/" .. s.terrain(o.x, o.y)
            end
            seen.mapKey = table.concat(parts, ";")
        end
        return seen.mapKey
    end

    -- What opening the door or breaking the wall at (x, y) opens: the tiles of its map change
    -- the march walks, on fieldUnit()'s costs as field() reads (M.mapChangeTiles), each with
    -- its cost; nil when it has no change. A change is the chapter's data, so the read is kept
    -- for the run, per class.
    local changes = {}
    function s.mapChange(x, y)
        local unit = s.fieldUnit()
        if not unit then return nil end
        local k = mem.u32(unit.addr + UNIT_CLASS) .. "@" .. x .. "," .. y
        if changes[k] == nil then
            changes[k] = sandbox(function(call)
                local costs = call(S.GetUnitMovementCost, { unit.addr })
                return M.mapChangeTiles(mem, call, S, x, y, costs)
            end) or false
        end
        return changes[k] or nil
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
                    -- `trap`: the one trap both tiles of a two-tile wall share, and so one HP
                    -- (a strike on either takes it off both: bot.lua's wallKey)
                    local trap = x .. "," .. y
                    if here == M.TERRAIN_WALL_DAMAGED or here == M.TERRAIN_SNAG then
                        out[#out + 1] = { x = x, y = y, hp = hp, trap = trap }
                    end
                    if y + 1 < h and s.terrain(x, y + 1) == M.TERRAIN_WALL_DAMAGED then
                        out[#out + 1] = { x = x, y = y + 1, hp = hp, trap = trap }
                    end
                end
            end
            seen.obstacles = out
        end
        return seen.obstacles
    end

    function s.fieldUnit()
        local first
        for _, u in ipairs(units()) do
            if u.faction == "blue" and u.onField then
                if s.canSeize(u) then return u end
                first = first or u
            end
        end
        return first
    end

    -- The march heading to a goal: costGrid on fieldUnit()'s costs. Each unit's real reach is
    -- reach()'s.
    function s.field(goalTile)
        local unit = s.fieldUnit()
        return unit and costGrid(unit, goalTile) or nil
    end

    -- The game's turn-event check (eventinfo.c: the phase-change hook searches turnBasedEvents
    -- with SearchAvailableEvent), asked at each later turn and phase (M.eventOrder). A script
    -- already available now (a repeating event) is no change; the first turn offering a new one
    -- is. Cost: a frame or more per call, ~765 for a full scan to turn 255 -- paid only when a
    -- board repeats, against a chapter's tens of thousands.
    function s.nextTurnEvent(turn)
        return sandbox(function(call, info)
            local function scriptsAt(t, phase) return M.turnScripts(api, call, info, t, phase) end
            local now = scriptsAt(turn, M.PHASES[1])
            for _, at in ipairs(M.eventOrder(turn)) do
                local found = M.firstNewEvent(now, { { turn = at.turn,
                                                       scripts = scriptsAt(at.turn, at.phase) } })
                if found then return found end
            end
            return nil
        end)
    end

    -- What the chapter's turn events do to the recruits, read once from the built ROM's scripts
    -- (#724): { arrivals = { { charId, x, y, turn, boardTurn } }, removals = { [charId] =
    -- boardTurn } }. Each turn event the game offers on turns 1..M.SCRIPT_HORIZON (turnScripts,
    -- the game's own turn/phase/flag check, each script at the first phase it is offered) has its
    -- bytes walked (M.scriptEffects: no event is run, nothing is written but the sandbox's turn
    -- and phase, which it puts back). `boardTurn` is the first player turn its effect is on the
    -- board: the turn itself for a blue-phase event, the next for a green or red one; `turn` is
    -- the same, as botrun's arrivals_seen reads an arrival no enemy was seen acting on (the
    -- board of the next player phase). `truncated` is set when a script's walk hit the budget. A
    -- unit's earliest arrival and earliest removal are kept, and a removal at or before the
    -- unit's earliest arrival is dropped (a cast loaded in one event and removed in a later one
    -- is no removal of a unit that was on the field). About 3 x the horizon game calls once a
    -- chapter (cached), none a turn.
    -- An estimate where scriptEffects' is: guards are not evaluated, a load tile is not where a
    -- REDA leaves the unit. The flags the scan reads are those of its first call (the chapter's
    -- first plan), so an event a later flag opens is not in it. A read made inside a sandbox (a
    -- decision's batch) may see flags that sandbox set, so it is returned but not kept.
    local scripted
    function s.scriptedUnits()
        if scripted then return scripted end
        local read = sandbox(function(call, info)
            local events, done = {}, {}
            for t = 1, M.SCRIPT_HORIZON do
                for _, phase in ipairs(M.PHASES) do
                    local fresh = {}
                    for script in pairs(M.turnScripts(api, call, info, t, phase)) do
                        if not done[script] then fresh[#fresh + 1] = script end
                    end
                    table.sort(fresh)   -- pairs() order is no order: a run must replay
                    for _, script in ipairs(fresh) do
                        done[script] = true
                        local fx = M.scriptEffects(mem, script)
                        local boardTurn = phase == M.PHASES[1] and t or t + 1
                        events[#events + 1] = { turn = boardTurn, boardTurn = boardTurn, eventTurn = t,
                                                loads = fx.loads, removals = fx.removals, truncated = fx.truncated }
                    end
                end
            end
            return M.foldScripted(events)
        end)
        if not open() then scripted = read end
        return read
    end

    -- The enemies the chapter's turn events bring on (#713 fix 3, ADR 0456), each as the game
    -- itself loads it: of s.scriptedUnits' arrivals, every red LOAD1-3 load, through the game's
    -- own event loader on its quiet path (eventscr.c LoadUnit_800F704(def, 1, TRUE, 0), as
    -- EventScr's quiet load calls it, :2264: LoadUnit, the difficulty's bonus levels, the last
    -- REDA tile at once by MoveUnitExt). One arrival at a time on the board as it stands: each
    -- is read (M.arrivalOf) and its slot emptied before the next. All in ONE sandbox at the top
    -- level, which loads the whole state back after (RAM, RNG, the sprites it refreshed).
    -- -> { { charId, x, y, eventTurn, boardTurn, classId, level, items, mov, reach, words } },
    -- x and y where the loader leaves it. An ESTIMATE: its stats are one draw of the game's
    -- RNG (GetAutoleveledStatIncrease, bmbattle.c:1241), not the draw it will make; a single
    -- spawn (LOADSINGLEUNIT) has no definition and is not built, nor a load that finds no free
    -- red slot (the loader would read a NULL unit). Read once a sight, never inside a sandbox
    -- (asserted: a nested one does not undo the loader's writes): botrun reads it at each
    -- fog chapter's player phase, with no plan's sandbox open.
    local arrivalUnits
    function s.arrivalUnits()
        if arrivalUnits then return arrivalUnits end
        assert(not open(), "sight.arrivalUnits inside a sandbox: botrun reads it at the phase start")
        assert(S.LoadUnit_800F704, "sight.arrivalUnits: symbols.lua lacks LoadUnit_800F704 (run gen_symbols.py)")
        local wanted = {}
        for _, a in ipairs(s.scriptedUnits().arrivals) do
            if a.def and a.red then wanted[#wanted + 1] = a end
        end
        arrivalUnits = sandbox(function(call)
            local out = {}
            for _, a in ipairs(wanted) do
                local free = freeRed()
                if #free > 0 then
                    call(S.LoadUnit_800F704, { a.def, 1, 1, 0 })
                    for _, f in ipairs(free) do
                        if mem.u32(f.addr) ~= 0 then
                            local o = M.arrivalOf(mem, S, Board, f.id)
                            o.eventTurn, o.boardTurn = a.eventTurn, a.boardTurn
                            out[#out + 1] = o
                            api.write32(f.addr, 0)   -- the slot free again for the next
                            call(S.RefreshEntityBmMaps, {})
                            break
                        end
                    end
                end
            end
            return out
        end)
        return arrivalUnits
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

-- Inside a sandbox (or Sight.machine's), after `u`'s movement map from `from` (default its own
-- tile; a Canto move's, the act's): `tiles` less those a ballista's rider may not end on. A
-- rider moves with its ballista, and the game's own check (CanMoveActiveUnitTo, playerphase.c)
-- lets it end on no tile a ballista stands on but the one it set out from; the ridden one's
-- trap keeps the tile it was boarded on until the rider exits (TryRemoveUnitFromBallista).
-- An ally's tile (`by`, reach's `friends`) is asked with the ally lifted off gBmMapUnit, as it
-- will be once it has moved. A unit on foot keeps them all. The callers: s.reach,
-- s.cantoTiles, and harness.lua's marchToward.
function M.riderTiles(api, call, u, tiles, from)
    if not M.riding(u.state) then return tiles end
    local S = api.SYM
    local ox, oy = from and from.x or u.x, from and from.y or u.y
    api.write32(S.gActiveUnit, u.addr)
    api.write16(S.gActiveUnitMoveOrigin, ox)
    api.write16(S.gActiveUnitMoveOrigin + 2, oy)
    local out = {}
    for _, t in ipairs(tiles) do
        local lifted = t.by and M.liftOff(api, t.x, t.y, t.by)
        if (t.x == ox and t.y == oy) or call(S.CanMoveActiveUnitTo, { t.x, t.y }) ~= 0 then
            out[#out + 1] = t
        end
        if lifted then M.putOn(api, t.x, t.y, t.by) end
    end
    return out
end

-- The convoy's first item that would let `u` open a door or chest (`opens(id)`: sight's
-- opensWith, the game's own key check), { id, uses }; nil when its bag has no room for it or
-- the convoy holds none, or when the convoy is not the game's (Board.convoyFault). What the
-- Supply command's Take would hand it (prep_itemsupply.c: Take refuses a full bag).
-- sight.convoyKey.
function M.convoyKey(Board, mem, S, u, opens)
    if #(u.items or {}) >= Board.ITEM_COUNT or Board.convoyFault(mem, S) then return nil end
    for _, c in ipairs(Board.convoyItems(mem, S)) do
        if opens(c.id) then return { id = c.id, uses = c.uses } end
    end
    return nil
end

-- `u`'s weapons as Weapon Select lists them (sight.weapons), without a whole sight.
function M.weapons(api, u, sandbox)
    local S = api.SYM
    -- A ballista's rider is shown no Attack (AttackCommandUsability's US_IN_BALLISTA gate):
    -- only Attack w/Ballista, which the bot never plays. Vanilla Ch10 (Eirika's route): Innes
    -- (charId 11) joined riding an emptied ballista and the bot planned his bow (#510).
    if M.riding(u.state) then return {} end
    return (sandbox or M.machine(api.cpu))(function(call)
        local out = {}
        for i, it in ipairs(u.items) do
            local item = itemOf(it)
            if call(S.CanUnitUseWeaponNow, { u.addr, item }) ~= 0 then
                local mn, mx = api.Board.itemRange(item)
                out[#out + 1] = { slot = i - 1, min = mn, max = mx }
            end
        end
        return out
    end)
end

-- Whether the game shows `u` the Attack command where it stands (AttackCommandUsability, `u`
-- the active unit), without a whole sight (harness.lua's clear loop).
function M.canAttack(api, u, sandbox)
    local S = api.SYM
    return (sandbox or M.machine(api.cpu))(function(call)
        M.asActive(api, u, api.mem.u8(u.addr + UNIT_X), api.mem.u8(u.addr + UNIT_Y), true)
        return call(S.AttackCommandUsability, { 0, 0 }) == M.MENU_ENABLED
    end)
end

-- The game's CanUnitSeize for `u` without a whole sight (harness.lua's clear loop).
function M.canSeize(api, u, sandbox)
    return (sandbox or M.machine(api.cpu))(function(call)
        return call(api.SYM.CanUnitSeize, { u.addr }) ~= 0
    end)
end

-- The chapter's talk events the game would run now, without a whole sight (the run's owed
-- recruits): SearchAvailableEvent walks the chapter's characterBasedEvents asking for a pair no
-- entry names, a breakpoint on each talk check (EvCheck03_CHAR, EvCheck04_CHARASM) reads the
-- entry it is handed, and CheckForCharacterEvents(a, b) keeps the ones available (flag unset,
-- condition met). -> { { a = pidA, b = pidB, script } }, a = 0 being anyone.
function M.talks(api, sandbox)
    local mem, S = api.mem, api.SYM
    return (sandbox or M.machine(api.cpu))(function(call, info)
        eventSearch(api, call, info, CHAPTER_TALKS)
        api.write8(info + EVENT_PID_A, NO_PID)
        api.write8(info + EVENT_PID_B, NO_PID)
        local seen = {}
        local function entry()
            local at = mem.u32(info)
            seen[#seen + 1] = { a = mem.u8(at + TALK_PID_A), b = mem.u8(at + TALK_PID_B),
                                script = mem.u32(at + TALK_SCRIPT) }
        end
        M.withBreaks(api.cpu, { { S.EvCheck03_CHAR, entry }, { S.EvCheck04_CHARASM, entry } },
            function() call(S.SearchAvailableEvent, { info }) end)
        local out = {}
        for _, t in ipairs(seen) do
            if call(S.CheckForCharacterEvents, { t.a, t.b }) ~= 0 then out[#out + 1] = t end
        end
        return out
    end)
end

-- The talks of `talks` (M.talks) that would bring a unit over: a pair the table also holds the
-- other way round with the same script is the game's CharacterEventBothWays (two entries, one
-- script), a conversation between two of our units (E_15's Duessel and Cormag,
-- ch15a-eventinfo.h), never a recruit (#699). Two one-way talks with their own scripts both
-- stay. -> the recruit talks.
function M.recruitTalks(talks)
    local pair = {}
    for _, t in ipairs(talks) do pair[t.a .. ">" .. t.b .. ">" .. tostring(t.script)] = true end
    local out = {}
    for _, t in ipairs(talks) do
        if not pair[t.b .. ">" .. t.a .. ">" .. tostring(t.script)] then out[#out + 1] = t end
    end
    return out
end

-- What each stolen item costs a clean clear (ADR 0379): its AiGetItemStealRank, and whether
-- that ranks it above ITEM_BOOSTER_SKL in the game's own list. -> { [item] = { rank, spoils } }
function M.stealRanks(api, items)
    local S = api.SYM
    return M.machine(api.cpu)(function(call)
        local line = call(S.AiGetItemStealRank, { M.ITEM_BOOSTER_SKL })
        local out = {}
        for _, item in ipairs(items) do
            local rank = call(S.AiGetItemStealRank, { item })
            out[item] = { rank = rank, spoils = rank < line }
        end
        return out
    end)
end

-- InitRN(seed) run in the sandbox, its three seeds then written into the live game: the run's
-- whole RNG stream is the game's own function of `seed`.
function M.seed(api, seed)
    local S = api.SYM
    local words = M.machine(api.cpu)(function(call)
        call(S.InitRN, { seed })
        return M.dice(api)
    end)
    M.setDice(api, words)
    return words
end

-- The game's RNG state: the three u16 words at gRNSeeds. A record that keeps them shows whether
-- two attempts rolled the same dice.
function M.dice(api)
    local S = api.SYM
    return { api.mem.u16(S.gRNSeeds), api.mem.u16(S.gRNSeeds + 2), api.mem.u16(S.gRNSeeds + 4) }
end

-- The three words written into the live gRNSeeds (the one writer: seed and advance use it).
function M.setDice(api, words)
    for i, v in ipairs(words) do api.write16(api.SYM.gRNSeeds + (i - 1) * 2, v) end
end

-- One NextRN (rng.c) on the three u16 words `w` = { s0, s1, s2 }, in place; returns the draw.
-- Pure, so a test checks it against rng.c's arithmetic with no emulator.
function M.nextRN(w)
    local s0, s1, s2 = w[1], w[2], w[3]
    local rn = ((s1 << 11) + (s0 >> 5)) & 0xFFFF
    s2 = (s2 * 2) & 0xFFFF
    if s1 & 0x8000 ~= 0 then s2 = (s2 + 1) & 0xFFFF end
    rn = rn ~ s2
    w[3], w[2], w[1] = s1, s0, rn
    return rn
end

-- `n` NextRN draws thrown away from the live gRNSeeds: the same effect as the game rolling `n`
-- more times. It does not re-seed (InitRN would restart the stream at one of seven starts); it
-- moves the run along the stream it is on. 0 draws touch nothing (not even a write).
function M.advance(api, n)
    if n <= 0 then return end
    local w = M.dice(api)
    for _ = 1, n do M.nextRN(w) end
    M.setDice(api, w)
end

return M
