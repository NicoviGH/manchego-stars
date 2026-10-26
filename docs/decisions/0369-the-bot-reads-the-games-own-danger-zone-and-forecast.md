---
id: 369
title: "The bot reads the game's own danger zone and forecast, by running FE8's functions in a sandbox"
date: "2026-10-26"
section: "Combat System"
issues: [510]
---

# The bot reads the game's own danger zone and forecast, by running FE8's functions in a sandbox

#510 step 9 PR D. The bot's policy (ADR 0368) decides from a `sight` table. `tools/playtest/sight.lua`
builds that table from the running ROM, and every answer in it is computed by FE8's own code:

| sight | FE8 code it runs (decomp) | read from |
|---|---|---|
| `danger(x, y)` | `GenerateDangerZoneRange(FALSE)` (bmidoten.c, the player phase's danger zone) | `gBmMapRange`: 0 = no enemy reaches; otherwise COVERAGE, 1 per tile an enemy could strike from (`GenerateUnitCompleteAttackRange`), not an enemy count |
| `threat(enemy)` | `GenerateDangerZoneRange`'s body for ONE unit: `GenerateUnitMovementMap`, its tile lifted off `gBmMapUnit`, `GenerateMagicSealMap` for a magic user, `GenerateUnitCompleteAttackRange` (every weapon it can use) | `gBmMapRange` |
| `reach(unit)` | `GenerateUnitMovementMap` (either faction) | `gBmMapMovement` < 120, less occupied tiles (`gBmMapUnit`) |
| `forecast(u, e, x, y)`: our attack and `e`'s counter | `BattleGenerateSimulation` + `InitBattleForecastBattleStats` (the forecast window's two calls) | `gBattleActor`/`gBattleTarget`, the forecast proc's hit counts |
| `forecast(u, e, x, y)`: `e`'s strike on its phase | `AiAttemptOffensiveAction`'s per-target routine (cp_battle.c), then the same two calls | the AI's chosen slot and tile, then `gBattleActor` |
| `objective` | `GetROMChapterStruct` (goal window type +0x8C, its turn +0x8D); `GetAvailableTileEventCommand` per tile for the Seize tile (as bmcommanddbg.c finds it) | the chapter data |
| `field(goal)` | `GenerateExtendedMovementMap` from the goal, out to `MAP_MOVEMENT_EXTENDED`, with the movement costs (`GetUnitMovementCost`) of the first deployed unit that can Seize, else the first deployed: the map FE8's AI heads for a far target over (cp_0803E2F4.c) | `gBmMapMovement` |
| `canSeize(unit)` | `CanUnitSeize` (bmdifficulty.c), the Seize command's own usability check; patch 0005 makes it the chosen lead in our build | its return |
| `range(unit)` | `GetUnitEquippedWeapon` (the first weapon `CanUnitUseWeapon` accepts, which `BU_ISLOT_AUTO` strikes with), then that item's range byte as `GetItemMinRange`/`GetItemMaxRange` read it (both inline: no symbol to call) | `gItemData` |
| `Sight.seed(s)` | `InitRN(s)` | `gRNSeeds` (file-static in rng.c; nm lists it) |

**How the game's code is run.** `Sight.machine` saves the emulator state, sets r0-r3 (and the stack
for a fifth argument), masks IRQs, points `lr` at a two-byte Thumb `b .` written into scratch RAM
above the call's stack, and jumps to the function. The harness then yields frames until the CPU sits
in that loop, the caller reads what it needs, and the state is loaded back: RAM, registers and RNG are
exactly as they were. It never single-steps. `emu:step()` from inside mGBA's frame callback
deadlocks when a call crosses the end of a frame. ch01's danger zone does, and the retail Prologue's
happened not to, which is how a first single-stepping version passed on retail and hung on ours.

**Why not drive the forecast window.** The window cannot answer the enemy phase. FE8 zeroes the
weapon of a target outside its weapon's range (`SetBattleUnitWeapon`, `BattleInitTargetCanCounter`),
so the window never shows what an enemy does to a tile it is not already beside, which is the whole
of the bot's worst case. Driving the window would also cost a select, move, menu and back-out per
question.

**The enemy's strike is the enemy AI's own decision, run as the game runs it** (Nicolas,
2026-10-26: "we want to use as much vanilla code as we can"). For one target, FE8's
`AiAttemptOffensiveAction` (cp_battle.c) is followed call for call in the sandbox:
- our unit is moved onto (x, y), in its struct AND on `gBmMapUnit`, so movement and blocking see it there;
- the enemy becomes `gActiveUnit`, with its movement map, magic seal map and working map set up as the AI sets them;
- each item slot in order: stop at an empty slot, skip Nightmare (compared as the whole item word,
  uses included, as the game does), skip what `CanUnitUseWeapon` or `AiReachesByBirdsEyeDistance`
  rules out, then `AiFillReversedAttackRangeMap` + `AiSimulateBestBattleAgainstTarget`, which picks
  the TILE (`AiGetCombatPositionScore`) and scores the fight (`AiComputeCombatScore`);
- the best score wins, a tie to the later slot (`>=`), and the strike is simulated with that slot
  from that tile.

So the weapon and the tile are chosen together, only from tiles the enemy can really reach, and a
"no tile" answer means it cannot strike us there this turn (`taken*` all 0). Proven on retail: asked
how O'Neill, handed Iron, Steel, Silver and Hand Axes, strikes Seth on (9,5), the routine skips every
melee axe (its one free adjacent tile is held by his own soldier, the rest out of his movement) and
throws the Hand Axe from (9,7): `[0:skip 1:skip 2:skip 3:1040@(9,7)]`.

**The counter and the strike are two reads.** `counter*` is the enemy's answer to OUR attack (the
weapon it holds, as FE8's counters are, `SetBattleUnitWeapon(target, BU_ISLOT_AUTO)`; `counters`
false and 0 when it cannot answer), and `diesWorst` and the bot's `counterWorst` read it. `taken*`
is always its own strike on its phase, which the enemy-phase worst case reads. One field for both
had charged the bot the counter weapon, from where the enemy stands, for the next phase too.

**Which enemies reach a tile** is `threat(enemy)`, that enemy's own danger zone, every weapon it
carries. bot.lua's `reaches` reads it; it had walked the enemy's reach with the HELD weapon's range
only, missing a second weapon's.

**The bot asks the game for every game rule; only the player's choices are its own** (Nicolas,
2026-10-26: "we need not reinvent vanilla AI behavior, it's all there"). A review of bot.lua against
that rule replaced each re-created rule with the game's answer:
- **Who may Seize** was `Board.canSeize` + the lead's pid + a memo of units the menu had refused:
  now `CanUnitSeize`. botrun's memo is gone; a refused Seize is a crash (the two disagree).
- **Promotion** checked `level >= 10` in the bot: the caller now hands in `promotes` from the
  game's own promotion-item check, which covers class and level.
- **The shop** compared a stock item's rank with the unit's: the caller now hands in `canUse`,
  the game's `CanUnitUseWeapon` for that unit over the stock.
- **Our reach** read slot 0's range: now the game's equipped weapon (`range`).
- **Which enemies can strike a tile** walked the enemy's reach with its HELD weapon's range: now
  `threat(enemy)`, the game's danger zone for that one enemy, every weapon.
- **The march** ran a BFS of ours over a cost table: now FE8's own extended movement map.
- **The forecast cache** was keyed on the units within support range: the AI's strike can be changed
  by any unit on the board, so the key is the whole board.
- **Kept, cited:** a crit's x3 (`BattleGenerateHitAttributes`) in the worst case, and "a sure kill on
  the first blow draws no counter" (the attacker strikes first, `BattleUnwind`). No FE8 function
  returns either on its own; both are one line of the game's arithmetic, not a model of it.
- **The player's, not the game's:** the march goal, stepping off the throne, the cork push, the
  styles' gates and the claims are choices a player makes, so they stay the bot's.

**Rulings made here, each with its cost if wrong:**
- **One target at a time.** The AI chooses its TARGET across all our units at once; the bot asks
  how each enemy would strike one unit on one tile, which is what a worst case sums. Cost if wrong:
  none for the worst case, but the bot cannot predict WHICH unit the AI goes for.
- **AI state as it stands in our phase.** `AiComputeCombatScore` reads `gAiState` (its weight table)
  and AI maps the enemy phase refreshes. Cost if wrong: two weapons or tiles could rank differently
  than in the real enemy phase. Units whose AI script holds them still (`AI_FLAG_STAY`, ballistae,
  thieves) are read as ordinary attackers, as the game's own danger zone reads them.
- **`field(goal)` uses one unit's movement costs** (the first deployed unit that can Seize, else
  the first deployed). A field only steers the march; each unit's real reach comes from `reach()`.
  A flier marching behind a foot unit's field takes a longer heading than it needs.
- **The goal window is the objective.** A `GOAL_TYPE_SPECIAL` chapter reads as `"special"`, and the
  bot marches on the nearest enemy there. A chapter whose real win condition differs from its goal
  window would be misread; none of ours or vanilla's is known to.
- **Retail's sightprobe reads the Prologue**, the first map New Game reaches. Retail Ch1 is only
  reached by playing the Prologue, which the `bot` scenario does: its Prologue record is emitted too.

**The drive loop** is `tools/playtest/botrun.lua`, its own chunk, talking to the harness only through
an `api` table (`test_botrun.lua` fakes it). It ends a run `won`, `lost`, `stuck` (a player phase
began on a board seen before: each on-field unit's id, tile and HP, plus the turns left on a Defense
map) or `crashed` (an action or enemy phase the harness could not drive, an action that left its
unit able to act, or a Seize the menu refused although `CanUnitSeize` allowed it). There is no turn cap. It prints one line,
`BOTRUN <json>`, holding the run record (#510's plan, Task 7). Deaths in the enemy phase carry their
killer, read from `gBattleActor`/`gBattleTarget` the frame the unit falls. The attack driver
(`chooseAttack`) now steps the target selector to the enemy the bot chose (a new legal action,
`next_target`, RIGHT, uiselecttarget.c) instead of striking whichever the selector offers first.

`bot` and `sightprobe` are `manual: true` rows in matrix.yaml, headless, never in a suite.
