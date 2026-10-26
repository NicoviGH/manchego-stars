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
| `reach(unit)` | `GenerateUnitMovementMap` (either faction) | `gBmMapMovement` < 120, less occupied tiles (`gBmMapUnit`) |
| `forecast(u, e, x, y)` | `BattleGenerateSimulation` + `InitBattleForecastBattleStats` (the forecast window's two calls) | `gBattleActor`/`gBattleTarget`, the forecast proc's hit counts |
| `objective` | `GetROMChapterStruct` (goal window type +0x8C, its turn +0x8D); `GetAvailableTileEventCommand` per tile for the Seize tile (as bmcommanddbg.c finds it) | the chapter data |
| `field(goal)` | `GetUnitMovementCost` of the lord (else the first deployed unit) | a BFS over the tiles it can enter (pathing.lua) |
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
of the bot's worst case. In the sandbox the enemy is the ACTOR. Our unit is placed on (x, y), and the
enemy strikes it from a tile at its own weapon's minimum range. That tile's terrain moves only the
enemy's avoid and defence, which no `taken*` field reads. Driving the window would also cost a
select, move, menu and back-out per question; a sandboxed call costs a frame or two.

**`taken*` means one thing.** It is what the enemy does to our unit on (x, y). When (x, y) is in our
weapon's range of it and it can answer, that is its counter in this exchange. Otherwise it is its own
strike on its phase. A new field, `counters`, says which: `counters == false` means our attack draws
no counter, and bot.lua's `counterWorst` takes nothing off for it. Without that, a bow striking a
sword-wielder at range 2 was charged the sword's strike twice.

**Rulings made here, each with its cost if wrong:**
- **The enemy strikes with the weapon its AI would choose against that unit** (Nicolas, 2026-10-26:
  the per-target pick is vanilla AI, so the sandbox runs it rather than assume the held weapon).
  FE8's own loop (cp_battle.c `AiAttemptOffensiveAction`) is followed slot by slot: stop at an empty
  slot, skip Nightmare (compared as the whole item word, uses included, as the game does), skip
  what `CanUnitUseWeapon` rejects, score each left with `AiSimulateBattleAgainstTargetAtPosition`
  (enemy as `gActiveUnit`, from a tile at that weapon's `GetItemMinRange`), keep the best, a tie to
  the later slot. The strike is then simulated with that slot. The AI also picks its TILE by
  `AiGetCombatPositionScore`; that is not followed, since the tile only moves the enemy's own avoid
  and defence. Cost if wrong: a score component that reads AI-phase state (`gAiState`, its danger
  map) could rank two weapons differently from the real enemy phase. A COUNTER stays the held
  weapon, because FE8's counters are (`SetBattleUnitWeapon(target, BU_ISLOT_AUTO)`).
- **`field(goal)` uses one unit's movement costs** (the lord's, else the first deployed unit's).
  A field only steers the march; each unit's real reach comes from `reach()`. A flier marching
  behind a foot unit's field takes a longer heading than it needs.
- **The goal window is the objective.** A `GOAL_TYPE_SPECIAL` chapter reads as `"special"`, and the
  bot marches on the nearest enemy there. A chapter whose real win condition differs from its goal
  window would be misread; none of ours or vanilla's is known to.
- **Retail's sightprobe reads the Prologue**, the first map New Game reaches. Retail Ch1 is only
  reached by playing the Prologue, which the `bot` scenario does: its Prologue record is emitted too.

**The drive loop** is `tools/playtest/botrun.lua`, its own chunk, talking to the harness only through
an `api` table (`test_botrun.lua` fakes it). It ends a run `won`, `lost`, `stuck` (a player phase
began on a board seen before: each on-field unit's id, tile and HP, plus the turns left on a Defense
map) or `crashed` (an action or enemy phase the harness could not drive, an action that left its
unit able to act, or Seize refused twice for one unit). There is no turn cap. It prints one line,
`BOTRUN <json>`, holding the run record (#510's plan, Task 7). Deaths in the enemy phase carry their
killer, read from `gBattleActor`/`gBattleTarget` the frame the unit falls. The attack driver
(`chooseAttack`) now steps the target selector to the enemy the bot chose (a new legal action,
`next_target`, RIGHT, uiselecttarget.c) instead of striking whichever the selector offers first.

`bot` and `sightprobe` are `manual: true` rows in matrix.yaml, headless, never in a suite.
