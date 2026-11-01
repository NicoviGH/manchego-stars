---
id: 388
title: "An attempt record is graded and cause-attributed; a clean clear is derived and descriptive"
date: "2026-11-01"
section: "Combat System"
issues: [510]
---

# An attempt record is graded and cause-attributed; a clean clear is derived and descriptive

**Decided (Claude, 2026-11-01), #510 step 9 PR-B** (the plan's T012-T027, #510 comment
6563384310; spec FR-002 to FR-008, #510 comment 6563384018). It builds the attempt record of the
plan's data model. It builds on ADR 0376 (the four-part clean clear) and ADR 0379 (a theft
spoils it only above the stat boosters), and changes neither.

**The rule.** Each `BOTRUN` record grades what happened, beside `outcome` and `clean`:
- every blue or green death carries `predicted` (the committing plan's chance), `cap`,
  `over_cap`, `flags`, one `cause`, and for `other` a `detail` and its `family`, plus
  `plan_ref` (the plan's decision index) and, for a green, `escort`;
- the attempt carries `first_death_turn`, `greens` (escort and allied deaths), `missed_recruits`
  and `missed_rewards` (each with a reason), `seize_skips`, `stall_events`, `turns_to_win`,
  `anomalies` (each with its `story` command) and `board_repeats`.

`clean` keeps ADR 0376's derivation. It is descriptive only: no decision reads it (FR-008).

**The committing plan** (FR-003). For a player-phase death it is the plan that chose the act,
and `predicted` is that attack's counter chance (`die` on the act, `sight.odds` on its
`counterDist`). For an enemy-phase death it is the phase's last plan, and `predicted` is that
plan's `predict` for the unit. With no plan, or none that read the unit, `predicted` is null,
and so are `over_cap`, `reinforcement` and `fog`: unknown is never zero.

**The flags and the cause** (FR-004, FR-005). The flags are independent facts. `reinforcement`:
the killer was not on the board the plan was made on (`plan.snapshot`). `fog`: it was on that
board but not among the plan's enemies. `boss`: the game's boss bit on the killer. The cause
follows the spec's precedence, `M.CAUSES` in `botrun.lua`, the one list `montecarlo.py` reads:
over_cap, reinforcement, fog, rng_tail (a positive prediction), other. A zero prediction is never
a tail. The details of `other` (`M.DETAILS`):
- sandbox faults: `missing_prediction`; `forecast_desync`, a death from a strike the plan played
  itself and saw no death in (the lone judged striker, or a counter it expected at zero);
- blindspots: `zero_multi_attacker` (several judged strikers, zero together),
  `unrevealed_killer` (a seen enemy the judged phase never sent at the unit),
  `player_phase_counter` (a counter the forecast said would not come), `noncombat` (no fighter).

The killer is matched by unit index: `Board.killer` now returns the killer's index as well, and
the death watch records it as `killerId`. Generic enemies share a charId, so a match by charId
alone could name the wrong one.

**Why the counter chance is zero under the planner.** `Bot.candidates` refuses, for every style
but greedy, an attack whose counter alone can kill the attacker. Every attack the planner is
offered therefore has `die` 0, and a player-phase death after one is `other/forecast_desync`. That
is the honest reading: the forecast said the counter could not kill.

**Reasons for missed goals** (FR-006). A missed recruit was `died_after_joining` (it fell on our
side), `killed_before_talk` (its charId fell on another side), `talk_skipped` (a plan's
candidates offered the Talk: the plan record's `talks`) or `not_reached`. `died_after_joining` is
not in the spec's list. The live proof needed it: vanilla Ch5 attempt 1's Joshua was talked over
and fell on turn 9, so ADR 0376 counts him missing (not in the party at the end), and without it
the record called him `talk_skipped`. A missed reward was `skipped` (offered to a unit and never taken) or `unreachable`
(never offered). Its `status` keeps the explore log's word (closed, skipped, unreached).

**Stalls and anomalies** (FR-007). The old count of repeated boards is renamed `board_repeats`
(`stalls` is in `DEAD_CONCEPTS`). A stall is a `stall_events` entry: `unjustified_seize_skip`, or
`idle_3`, three player phases in a row with no lord move, kill, Visit, Talk or Chest. A seize skip
is recorded once a turn, when a plan's candidates offered the Seize and the plan did not take it.
Until PR-D builds `Goals.ledger`, its ledger is the open goals of the plan's `goalWorth` other
than the objective. A skip with one is justified and is not a stall. The anomalies:
- `stall_abort`: the run ended `stuck`;
- `seize_delay`: a win after a seize skip, with the delay in turns;
- `bait_loop`: an enemy that stood on two tiles in turn for four phase starts;
- `same_turn_green`: a green lost on the turn it was first seen at a phase start, so the planner
  had at most one player phase to save it.

`narrate` is `montecarlo.py story <trace> --turn N`, which tells that turn and the one before.
`keep_trace` points it at the kept trace.

**Measured** (T027, 2026-11-01). The planner changes are record-only: `montecarlo.py suite
--baseline --jobs 8` played all 52 runs with the same outcome, turns, deaths and frame count as
PR-A's baseline (ADR 0387), in 1,877.0 CPU s against 1,883.6 (5 min 31 s wall). What the graded
records say:
- 20 blue or green deaths: 17 `rng_tail` (no cap yet, so every positive prediction is a tail;
  PR-C's caps make the high ones `over_cap`), 2 `other/unrevealed_killer` (vanilla Ch5 seed
  1001, scout Ch13 seed 2001) and 1 `other/forecast_desync` (ours ch03 seed 1001, turn 11).
- 5 `stall_abort` (vanilla Ch1 seed 1001; scout Ch14, all four seeds), 11 `idle_3` stalls, no
  seize skip in any run.
- Ours ch02, all four seeds: allied greens 0xC9 and 0xCA fall on turns 2 and 3 to 0x48 (boss
  flag), predicted at 47.4% and 49.6%. The plan sees each as a coin flip.
- Vanilla Ch5, attempts 1-3 (seed 1): attempt 1 loses 0x04 on turn 2 to 0x80 at 78.6%, 0x0A on
  turn 3 to Joshua (0x20, still red) at 19.0%, and Joshua himself on turn 9 after joining
  (`died_after_joining`); attempt 2 loses nobody and skips the village at 5,6; attempt 3 loses
  0x04 on turn 2 at 29.4%. In the suite's four Ch5 seeds Joshua kills a unit of ours in every
  one, and seed 1001 misses him as `killed_before_talk`.
