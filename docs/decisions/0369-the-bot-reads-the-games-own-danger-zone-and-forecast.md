---
id: 369
title: "The bot reads the game's own danger zone and forecast, by running FE8's functions in a sandbox"
date: "2026-10-26"
section: "Combat System"
issues: [510]
---

# The bot reads the game's own danger zone and forecast, by running FE8's functions in a sandbox

#510 step 9 PR D. The bot's policy (ADR 0368) decides from a `sight` table. `tools/playtest/sight.lua`
builds that table from the running ROM, and **every game rule in it is FE8's own code, run as the game
runs it, never a copy** (Nicolas, 2026-10-26: "we want to use as much vanilla code as we can";
"we need not reinvent vanilla AI behavior, it's all there"). A divergence from vanilla is a gap to
close, not a ruling to record.

| sight | FE8 code it runs (decomp) | read from |
|---|---|---|
| `danger(x, y)` | `GenerateDangerZoneRange(FALSE)` (bmidoten.c, the player phase's danger zone) | `gBmMapRange`: 0 = no enemy reaches; otherwise COVERAGE, 1 per tile an enemy could strike from (`GenerateUnitCompleteAttackRange`), not an enemy count |
| `threat(enemy)` | `GenerateDangerZoneRange` itself, every OTHER enemy made invalid for the call (`pCharacterData` 0, so `UNIT_IS_VALID` fails) while still standing on `gBmMapUnit` and blocking as it does: fog, roofs and magic all the game's | `gBmMapRange` |
| `reach(unit)` | `GenerateUnitMovementMap` (either faction) | `gBmMapMovement` < 120, less occupied tiles (`gBmMapUnit`) |
| `range(unit)` | `GetUnitEquippedWeapon` (the first weapon `CanUnitUseWeapon` accepts, which `BU_ISLOT_AUTO` strikes with), then that item's range byte as `GetItemMinRange`/`GetItemMaxRange` read it (both inline: no symbol to call) | `gItemData` |
| `canSeize(unit)` | `CanUnitSeize` (bmdifficulty.c), the Seize command's own usability check; patch 0005 makes it the chosen lead in our build | its return |
| `attack(u, e, x, y)`: our attack and `e`'s counter | `BattleGenerateSimulation` + `InitBattleForecastBattleStats` (the forecast window's two calls) | `gBattleActor`/`gBattleTarget`, the forecast proc's hit counts; Monster Stone and broken weapons as bksel.c reads them |
| `strike(u, e, x, y)`: `e`'s own strike on its phase | the enemy phase's per-unit setup (cp_decide.c: `AiUpdateNoMoveFlag`, the combat weight table from `ai_config`, `AiInitDangerMap`, `AiClearDecision`), then `AiAttemptOffensiveAction(AiIsUnitEnemy)` itself, then the decision simulated (`BattleGenerateSimulation`, or `BattleGenerateBallistaSimulation` for slot 0xFF) | `gAiDecision`, then `gBattleActor` |
| `objective` | `GetROMChapterStruct` (goal window type +0x8C, its end turn +0x8D, whose last turn the goal window shows as End − 1, so turns left = End − turn); `GetAvailableTileEventCommand` per tile for the Seize tile (as bmcommanddbg.c finds it) | the chapter data |
| `field(goal)` | `GenerateExtendedMovementMap` from the goal, out to `MAP_MOVEMENT_EXTENDED`, with the movement costs (`GetUnitMovementCost`) of the first deployed unit that can Seize, else the first deployed: the map FE8's AI heads for a far target over (cp_0803E2F4.c) | `gBmMapMovement` |
| `nextTurnEvent(turn)` | `SearchAvailableEvent`/`SearchNextAvailableEvent` over `GetChapterEventDataPointer(ch)->turnBasedEvents` (the phase change's own turn-event check, eventinfo.c), the turn and phase set to each later turn | the first turn offering a script not already available now |
| `Sight.seed(s)` | `InitRN(s)` | `gRNSeeds` (file-static in rng.c; nm lists it) |

**How the game's code is run.** `Sight.machine` saves the emulator state and puts the CPU in System
mode, Thumb, IRQs masked, FIRST: `sp` and `lr` are banked, so they are read and written in the mode the
call runs in. It sets r0-r3 (and the stack for a fifth argument), points `lr` at a two-byte Thumb
`b .` written into scratch RAM above the call's stack, and jumps to the function. The harness then
yields frames until the CPU sits in that loop, the caller reads what it needs, and the state is loaded
back: RAM, registers and RNG exactly as they were. It never single-steps. `emu:step()` from inside
mGBA's frame callback deadlocks when a call crosses the end of a frame. ch01's danger zone does, and
the retail Prologue's happened not to, which is how a first single-stepping version passed on retail
and hung on ours. Every frame a call runs is counted (`TUNE.sandboxFrames`): the load rewinds the
frame counter, so log stamps, a run's `frames` and run.sh's frame budget and stall watch add it back,
and a heartbeat line every 600 of them keeps a long think visible.

**Why not drive the forecast window.** The window cannot answer the enemy phase. FE8 zeroes the
weapon of a target outside its weapon's range (`SetBattleUnitWeapon`, `BattleInitTargetCanCounter`),
so the window never shows what an enemy does to a tile it is not already beside, which is the whole
of the bot's worst case. Driving the window would also cost a select, move, menu and back-out per
question.

**The enemy's strike is its AI's own decision.** For one target the sandbox moves our unit onto
(x, y), in its struct and on `gBmMapUnit`, hides every other unit the AI could choose (`US_HIDDEN`:
`AiAttemptOffensiveAction` skips them as targets; they keep their `gBmMapUnit` entries and still
block), makes the enemy the active unit, runs the decide loop's per-unit setup and then the offensive
routine itself. Its STAY, ballista and thief branches all come with it: a no-move unit strikes only
from where it stands, a thief with room steals instead. The AI picks the weapon AND the tile together,
only from where it can move, and "no combat decision on our unit" means it cannot strike us there this
turn (`taken*` all 0). Proven on retail: asked how O'Neill, handed Iron, Steel, Silver and Hand Axes,
strikes Seth on (9,5), the AI throws the Hand Axe from (9,7), two tiles off, because its one free
adjacent tile is held by his own soldier and the rest are out of his movement.

**Our attack and the enemy's strike are two reads.** `attack` is our attack from (x, y) with the
enemy's `counter*` (the weapon it holds, as FE8's counters are, `SetBattleUnitWeapon(target,
BU_ISLOT_AUTO)`; `counters` false and 0 when it cannot answer). `strike` is always the enemy's own
strike on its phase, which the enemy-phase worst case reads. One field for both had charged the bot
the counter weapon, from where the enemy stands, for the next phase too. Whether an attack's counter
alone can kill is the bot's (`counterWorst` ≥ HP, nothing for a sure first-blow kill), so the rule
lives in one place.

**Caches.** One sight per run; its board answers (danger, threats, ranges, Seize, fields) are dropped
by `refresh()`, which the drive loop calls after every action and at every phase, because one unit
moving can open or close another's path. bot.lua keeps attacks keyed on what the simulation reads
(the fighters, their tiles, the units within support range) and strikes keyed on the whole board,
since the AI's pick can change with any unit anywhere.

**The bot asks the game for every game rule; only the player's choices are its own.** A review of
bot.lua against that rule replaced each re-created rule with the game's answer:
- **Who may Seize** was `Board.canSeize` + the lead's pid + a memo of units the menu had refused:
  now `CanUnitSeize`, everywhere (the clear loop too). A refused Seize is a crash (the two disagree).
- **Promotion** checked `level >= 10` in the bot: the caller hands in `promotes` from the game's own
  promotion-item check, which covers class and level.
- **The shop** compared a stock item's rank with the unit's: the caller hands in `canUse`, the
  game's `CanUnitUseWeapon` for that unit over the stock.
- **Reach** read slot 0's range: now the game's equipped weapon (`range`), everywhere
  (harness.lua's `unitAttackRange`, the clear loop and greedy included).
- **Which enemies can strike a tile** walked the enemy's reach with its held weapon's range: now
  `threat(enemy)`.
- **The march** ran a BFS of ours over a cost table: now FE8's extended movement map.
- **Kept, cited:** a crit's x3 (`BattleGenerateHitAttributes`) in the worst case, and "a sure kill on
  the first blow draws no counter" (the attacker strikes first, `BattleUnwind`). No FE8 function
  returns either on its own; both are one line of the game's arithmetic, not a model of it. The
  combat weight table is cp_decide.c's one-field assignment from `ai_config`, copied as it stands
  (no function holds it).
- **The player's, not the game's:** the march goal, stepping off the throne, the cork push, the
  styles' gates and the claims are choices a player makes, so they stay the bot's.

**Rulings made here, each with its cost if wrong:**
- **One target at a time.** The AI chooses its target across all our units at once; the bot asks how
  each enemy would strike one unit on one tile, which is what a worst case sums. Cost if wrong: none
  for the worst case, but the bot cannot predict WHICH unit the AI goes for.
- **`field(goal)` uses one unit's movement costs** (the first deployed unit that can Seize, else the
  first deployed). A field only steers the march; each unit's real reach comes from `reach()`. A flier
  marching behind a foot unit's field takes a longer heading than it needs.
- **The goal window is the objective.** A `GOAL_TYPE_SPECIAL` chapter reads as `"special"`, and the bot
  marches on the nearest enemy there. A chapter whose real win condition differs from its goal window
  would be misread; none of ours or vanilla's is known to.
- **Retail's sightprobe reads the Prologue**, the first map New Game reaches. Retail Ch1 is only reached
  by playing the Prologue, which the `bot` scenario does: its Prologue record is emitted too.

**The drive loop** is `tools/playtest/botrun.lua`, its own chunk, talking to the harness only through
an `api` table (`test_botrun.lua` fakes it). It ends a run `won`, `lost`, `stuck` or `crashed`, with no
turn cap. `stuck`: a player phase began on a board already seen (each on-field unit's id, tile and HP,
the turns left on a Defense map, and the turns until the next arrival a reinforcements claim cites --
all Bot.decide reads), and `nextTurnEvent` finds no turn event still to fire; with one ahead, the run
waits for its turn. `crashed`: an action or enemy phase the harness could not drive, an action that
left its unit able to act, a Seize the menu refused though `CanUnitSeize` allowed it, or any Lua error
(the record is still emitted). It prints one line, `BOTRUN <json>`, holding the run record (#510's
plan, Task 7). Deaths in the enemy phase carry their killer, read from `gBattleActor`/`gBattleTarget`
the frame the unit falls, and a death the watcher missed is still recorded before a loss returns. The
attack driver (`chooseAttack`) steps the target selector to the enemy the bot chose (a new legal
action, `next_target`, RIGHT, uiselecttarget.c). `PT_STYLE`/`PT_CLAIMS` are JSON read from the
environment, never spliced into Lua source.

`bot` and `sightprobe` are `manual: true` rows in matrix.yaml, headless, never in a suite.
