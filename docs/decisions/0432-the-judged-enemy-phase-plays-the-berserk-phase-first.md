---
id: 432
title: "The judged enemy phase plays the berserk phase first"
date: "2026-11-19"
section: "Combat System"
issues: [660, 510]
---
# The judged enemy phase plays the berserk phase first

**Decided 2026-11-19 (#660).** It follows ADR 0396: the game's own phase, played as the game
plays it. No new rule or weight.

**The problem.** An enemy Bishop's Berserk staff berserks a player unit. The game then moves that
unit itself, in a berserk phase that runs right after the player phase, and it attacks the
nearest unit of either side. The bot did not model that phase. Its judged enemy phase played
enemies only, so a plan that left Eirika next to a berserked ally read her at 0% death. In vanilla
Ch14 (`scout-ch14/1001`, the #655 branch's run), Colm (charId 9) killed Moulder (charId 5) and
Garcia (charId 0x0A) killed Eirika, both berserked. The record graded both deaths
`reinforcement`, because the grader only looked for a red killer.

**What the game does (decomp).**
- `bm.c`: every phase is followed by `gProcScr_BerserkCpPhase`, in the same faction's phase.
- `cp_phase.c` `AiPhaseBerserkInit`: `gAiState.flags = AI_FLAG_BERSERKED`, `unk7E`, `cmd_result`
  and `specialItemFlags` set, then `UpdateAllPhaseHealingAIStatus` and
  `SetupUnitInventoryAIFlags`. Unlike `AiPhaseInit` it leaves `orderState` and `unk84` alone.
- `cp_order.c` `CpOrderBerserkInit`: the phase faction's units with status BERSERK and none of
  `US_HIDDEN`, `US_UNSELECTABLE`, `US_DEAD`, `US_RESCUED`, `US_HAS_MOVED_AI`, in unit-index
  order, with no sort. Each decides with the normal `AiDecideMain`; `AI_FLAG_BERSERKED` sends it
  down `AiDoBerserkAction` / `AiDoBerserkMove` (`cp_decide.c`).
- `bmunit.c` `TickActiveFactionTurn`: each phase start ticks the status down once and clears it
  at 0.

**The rule (`tools/playtest/sight.lua`, `planner.lua`, `botrun.lua`).**
1. **Who berserks.** `Sight.berserkers` lists the player's units the game's order would list.
   For the lookahead's second phase, only those whose status outlives one more player-phase tick.
2. **The phase start.** `Sight.berserkPhaseStart` writes `AiPhaseBerserkInit`'s fields, sets the
   faction to the player's and makes its two calls. The fields both phase starts write live in
   one helper (`phaseFields`). One owner (`berserkFirst`, `stagePhase`'s) starts the berserk
   phase for both judged phases. `aiDecide` accepts a decision in the player's
   faction for a player unit. A strike by a player unit teaches nothing, as the game awards none
   between two player units.
3. **Then the enemy phase.** `playPhase` plays the berserkers first with `phaseWays`. Each of their
   ways ends in the enemy phase, whose order (`aiOrder`) is built on that way's board, as the game
   builds it after the berserk phase (`phaseWays`' new `tail`).
   - A berserk strike that leaves its target at 0 HP on its expected way takes the target off
     the map, as `nextPhase` takes one. The enemies' own strikes keep their reading.
   - The berserk decisions refresh the maps under the player's faction, which rewrites the red
     units' fog bits. The enemy order reads them as the phase found them (`order()` puts them
     back), so who decides is what it is with no berserked unit.
   - The lookahead's first phase (`nextPhase`) does the same along its one expected way.
   - With no berserked unit the phase plays as before. The one other change is that `decides`
     refuses a unit at 0 HP. Only a berserk strike leaves a red there, since the plan's own reds
     are floored at 1 HP.
   - The counter kills each way's enemy phase leaves unsplit are counted per way, as `phaseWays`
     counts them per branch.
4. **What the planner reads.** A berserk strike is marked (`t.berserk`). It hits its target as
   any strike does. The striker also takes its target's counter as a blow (`blowsOn`), so its
   own death is read, and its target is named its striker. A player unit is never the boss or a
   Rout's last enemy (`endsIn`), and never counted in `nextPhase`'s `fell`.
5. **The grade.** `Botrun.grade` accepts a killer of any side. A player-unit killer sets
   `flags.berserk` and clears `player_phase` (it is not a counter to our act). The prediction is
   the plan's `predict`, which now judges the berserk phase. The cause stays the plan's reading:
   over the cap, a lost roll, or unseen. The issue had asked for a cause named `berserk`; a flag
   keeps the cause saying whether the plan read the death. Reports show the flag
   (`montecarlo.py` `death`), and `calibration` counts an unread one as `under: berserk`.

**Not covered.** An enemy berserked by the player's staff moves in a berserk phase after the
enemy phase. The bot casts heal staves only (`Sight.healStaves`, `M.HEAL_STAVES`: the one owner
of its Staff acts), so no enemy is ever berserked and the judged phase does not play it.
Nor does the judged phase play an enemy's status staff (`aiDecide` keeps combat only). A unit
the Bishop would berserk in the first phase is not berserked in the lookahead's second: #674.

**Proof (2026-11-19).**
- Unit tests, each failing on main's code: `test_sight.lua` (`berserkers`, `berserkPhaseStart`,
  `phaseWays`' tail, the source checks on the faction guard and the start's callers),
  `test_bot.lua` `test_planner_reads_the_berserk_phase` and `endsIn`'s boss case,
  `test_botrun.lua` `test_grade_a_berserk_phase_death` and
  `test_a_berserk_phase_death_through_the_record`, `test_montecarlo.py`'s flag and
  `under: berserk`.
- **No replay of the losing game.** Its record is of the #655 branch's instrument, and `replay`
  refuses a run of other code. On this code `suite --only scout-ch14/1001` plays another route.
  The Bishop's staff on Colm (charId 9, turn 8) does not berserk him (he acts on turn 9), and
  the game is won on turn 21 with no death (trace `14-s1001-a1-3a70a04e`). It shows no
  regression but never exercises the berserk phase.
- **The probe in the emulator instead (`PT_VANILLA=1 tools/playtest/run.sh berserkprobe`).** On
  the retail Prologue, Seth (charId 2) is given status 0x54 and Eirika (charId 1) is stood
  beside him on 5 HP. `sight.enemyPhase`: Seth strikes Eirika (her 5 HP at worst), then two
  enemies strike Seth. `sight.nextPhase`: Seth moves first, Eirika starts the second phase on
  2 HP (his expected blow), and no player unit is in `fell`. Control, Seth's status cleared: no
  strike of his, an enemy moves first, and Eirika keeps her 5 HP. On main's `sight.lua`:
  `FAIL -- berserked=0 control=0 lookahead first=false/false hp=5/5`.
