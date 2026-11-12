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
and so are `over_cap`, `reinforcement` and `fog`: unknown is never zero. Until PR-C gives each
style its cap, `cap` and `over_cap` are null on every death: null says the over-cap check has not
run, where false would say it ran and passed. (PR-C, ADR 0384: every planned style now has its cap,
so they are filled; greedy, which plays no plan, keeps them null.)

**The flags and the cause** (FR-004, FR-005). The flags are independent facts. `reinforcement`:
the killer was not on the board the plan was made on (`plan.snapshot`). `fog`: it was on that
board but not among the plan's enemies. `boss`: the game's boss bit on the killer. The cause
follows the spec's precedence, `M.CAUSES` in `botrun.lua`, the one list `montecarlo.py` reads:
over_cap, reinforcement, fog, rng_tail (a positive prediction), other. A zero prediction is never
a tail. A death with no fighter (an event's `SET_HP`, a poison tick) is `other/noncombat` ahead of
`rng_tail` and of `missing_prediction`: the plan's combat odds were never about it, so it is
neither the roll the plan lost nor a read that failed. The details of `other` (`M.DETAILS`):
- sandbox faults: `missing_prediction`; `forecast_desync`, a death from a strike the plan played
  itself and saw no death in (the lone judged striker, or a counter it expected at zero);
- blindspots: `zero_multi_attacker` (several judged strikers, zero together),
  `unrevealed_killer` (a seen enemy the judged phase never sent at the unit),
  `player_phase_counter` (a counter the forecast said would not come), `noncombat` (no fighter).

The killer is matched by unit index and charId together: `Board.killer` now returns the killer's
index as well, and the death watch records it as `killerId`. Generic enemies share a charId (122
vanilla unit defs are `CHARACTER_MONSTER_BA`), so the charId alone could name the wrong one; and
FE8 reloads a freed slot, so the index alone could match an arrival to the unit the snapshot saw
die there. A snapshot unit that fell at or after the plan was made (botrun's `diedAt`, set in the
order the game killed them) is no killer either: a generic arrival of the same charId can take
its slot.

**Why the counter chance is zero under the planner.** `Bot.candidates` refuses (a known break of
ADR 0396), for every style but greedy, an attack whose counter alone can kill the attacker. Every attack the planner is
offered therefore has `die` 0, and a player-phase death after one is `other/forecast_desync`. That
is the honest reading: the forecast said the counter could not kill.

**Reasons for missed goals** (FR-006). A missed recruit was `died_after_joining` (it fell on our
side), `killed_before_talk` (the game killed it on another side), `left_map` (it left the field and
the game did not kill it: a script unloaded it or it escaped), `talk_skipped` (a plan's
candidates offered the Talk: the plan record's `talks`) or `not_reached`. `died_after_joining` is
not in the spec's list. The live proof needed it: vanilla Ch5 attempt 1's Joshua was talked over
and fell on turn 9, so ADR 0376 counts him missing (not in the party at the end), and without it
the record called him `talk_skipped`.

A missed reward's reason is the explore log's status, renamed by one table (`M.REWARD_REASONS`):
`skipped` (offered to a unit and never taken), `never_offered` (no plan was offered it; whether a
unit could have reached it is not known), and two the spec
does not list, `closed` (another side closed it first: a pillage or a thief, offered before or
not) and `failed` (tried, and the harness could not drive it: the run crashed there). A reward
offered and then pillaged is `closed`, as its status says. `unknown` is the last reason. Only the planner records what it was offered (its plans' `explore` and
`talks`), so a run without it (the greedy style) cannot tell skipped from never offered, or a
skipped Talk from one never reached, and says `unknown` rather than guess.

**Stalls and anomalies** (FR-007). The old count of repeated boards is renamed `board_repeats`
(`stalls` is in `DEAD_CONCEPTS`). A stall is a `stall_events` entry: `unjustified_seize_skip`, or
`idle_3`, three player phases in a row with no lord move, kill, Visit, Talk or Chest, recorded
again at every third phase of a longer stretch. Only a player-phase kill is progress: an enemy
that dies on a counter in its own phase is not the bot moving the chapter on. A seize skip
is recorded once a turn, when a plan's candidates offered the Seize and the plan did not take it
(the plan record's `seizable` and `seizes`).
Until PR-D builds `Goals.ledger`, its ledger is the open goals of the plan's `goalWorth` other
than the objective. A skip with one is justified and is not a stall. The anomalies:
- `stall_abort`: the run ended `stuck`;
- `seize_delay`: a win after an unjustified seize skip, with the delay from the first one;
- `bait_loop`: an enemy that stood on two tiles in turn for four phase starts;
- `same_turn_green`: a green lost on the turn it was first seen at a phase start, so the planner
  had one player phase to save it;
- `unseen_green`: a green lost before any player phase saw it.

`narrate` is `montecarlo.py story <trace> --turn N`, which tells that turn and the one before.
`montecarlo.keep_trace` sets it, the one place that knows where the trace is kept; botrun records
only the turn.

**Measured** (T027, 2026-11-01). The planner changes are record-only: `montecarlo.py suite
--baseline --jobs 8` played all 52 runs with the same outcome, turns, deaths and frame count as
PR-A's baseline (ADR 0387), at 1,883.6 CPU s (SC-003's stand-in until ADR 0384's 2026-11-03
amendment re-based it on PR-D's `AiDecideMain` calls). Three runs on this branch, as the
review's fixes landed: 1,877.0, 1,920.4 and 1,964.4 CPU s (5 min 31 s to 5 min 47 s wall).
Play is frame-for-frame the same and the record adds only per-death and per-phase bookkeeping, so the spread reads as
machine load; it rose each run, so all three are given. The graded records (the last two runs
agree on every count):
- 20 blue or green deaths: 17 `rng_tail` (no cap yet, so every positive prediction is a tail;
  PR-C's caps make the high ones `over_cap`), 2 `other/unrevealed_killer` (vanilla Ch5 seed
  1001, scout Ch13 seed 2001) and 1 `other/forecast_desync` (ours ch03 seed 1001, turn 11).
- 5 `stall_abort` (vanilla Ch1 seed 1001; scout Ch14, all four seeds), 32 `idle_3` stalls, no
  seize skip in any run. Every anomaly carries its story command.
- Missed recruits: 7 `not_reached`, 5 `killed_before_talk`. Missed rewards: 27 `unreachable`, 12
  `closed`, 9 `skipped`.
- Ours ch02, all four seeds: allied greens 0xC9 and 0xCA fall on turns 2 and 3 to 0x48 (boss
  flag), predicted at 47.4% and 49.6%. The plan sees each as a coin flip.
- Vanilla Ch5, attempts 1-3 (seed 1): attempt 1 loses 0x04 on turn 2 to 0x80 at 78.6%, 0x0A on
  turn 3 to Joshua (0x20, still red) at 19.0%, and Joshua himself on turn 9 after joining
  (`died_after_joining`); attempt 2 loses nobody and skips the village at 5,6; attempt 3 loses
  0x04 on turn 2 at 29.4%. In the suite's four Ch5 seeds Joshua kills a unit of ours in every
  one, and seed 1001 misses him as `killed_before_talk`.

## Amended 2026-11-11 (#510, run `fwd1`): four records said something that did not happen

Run `fwd1` (findings: #510 comment 6810177817; plan item A: comment 6810567866) read four
records that named the wrong thing. None changes how the bot plays.

- **A lord felled by our own act is `lost`, why "game over in the player phase".** The game
  runs its game-over event only after the death quote and the act, so `api.lost()` (the screen)
  was still false when the act returned; the bot ended its phase into the title screen and the
  record said `crashed`, "the enemy phase never returned control" (campaign `fwd1-cs-s4002`,
  chapter index 9, attempt 10: charId 15 fell on its own attack on turn 15). The run now ends
  on the kill itself: `api.killed()` named a unit of `Bot.gameOver`'s set.
- **A red unit is killed only when the game says so.** A red one gone from the field with no
  `api.killed()` entry was counted as felled; it is now read as a blue or green one always was
  (unloaded by a script, or escaped). A recruit that left that way is missed as `left_map`, not
  `killed_before_talk`.
- **`unreachable` is now `never_offered`.** The record only ever knew that no plan was offered
  the tile.
- **A razed village names its raider.** The enemy-act watch named the row above the village
  (where `AiPillageAction` runs the event), a tile the explore log does not hold, so
  `closed_by` stayed empty. It names the village's tile now.

Two things are added to an attempt's record:

- `team`: the prep screen's pick (`cap`, `demands`, and per roster unit `charId`, `group`,
  `forced`, `carried`, `answers`, `why` with `benched` for a unit left out, `covers`). Until
  now only the worker's log held it.
- `player_phases` and `acts_hash`: the player phases played (the game's turn counter stops at
  999) and a hash of the player acts in order. Equal hashes on two attempts of one start mean
  one game was played twice.
