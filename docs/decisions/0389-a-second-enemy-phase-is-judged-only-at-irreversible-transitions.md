---
id: 389
title: "A second enemy phase is judged only at irreversible transitions, under a fixed budget"
date: "2026-11-03"
section: "Combat System"
issues: [510]
---

# A second enemy phase is judged only at irreversible transitions, under a fixed budget

**Decided (spec FR-017, FR-018, #510 comment 6563384018); built as the R-8 spike (Nicolas,
2026-11-03: hold first), #510 step 9 PR-E** (the plan's T057-T069, #510 comment 6563384310).

**The rule.** The planner judges each plan against one enemy phase. Some risks show only a phase
later: a door or wall opened onto a room, a unit stepping into a boss's reach, a reinforcement wave
due. At those moments, and only then, the finalists meet a second enemy phase:

- **Triggers** (`planner.lua` `M.triggers`): a door opened or a wall struck (`breach`); a unit ending
  in a seen boss's reach (`sight.threat`) from a tile outside it (`boss`). A boss the fog hides
  triggers nothing.
- **No arrival trigger (Nicolas, 2026-11-03: "drop it").** FR-017 also named the turn on or before
  a known arrival. But `nextPhase` cannot place units, so that second phase played without the wave
  and learned nothing about it. In the measures below it took 24 of 101 triggered decisions on the
  tuning seeds. Known arrivals still make the march hold the turn before (`Bot.nextArrival`).
  Placing a claim's wave, and with it the trigger, is #569.
- **All or none (FR-018).** The finalists are the best `M.FINAL` plans judged, by rank. If any
  triggers, each one gets one call to `sight.nextPhase`, or none does. The budget is
  `M.LOOK_DECISION` = 8 calls a decision and `M.LOOK_ATTEMPT` = 128 an attempt (botrun passes
  what is left as `opts.budget.attempt`). Too little left keeps the one-phase horizon, tagged
  `skipped`, and the attempt's first such decision is a `lookahead_budget` anomaly counting
  every one skipped (#570).
- **What the second phase reads.** Every unit the first phase may strike (ours and the allied
  greens) is asked again at the HP the first phase left it. Each protected unit's death chance
  becomes the chance it dies in either phase, `1 - (1 - first) * (1 - second)`; its first-phase
  branches are kept. The game-over chance composes the same way. A green that is neither protected
  nor a recruit adds its extra death to `green_die`. The judged score (`value`) pays each unit's
  extra death at its price and our units' HP lost, and `hp_left` loses it too. Both phases share
  one routine (`struckIn`). The finalists are then ranked again among themselves, with every
  plan's `behind` measured from the one best progress. A plan outside them lost to each one on the
  first phase and was never asked the second. In `considered`, the finalists come first.
- **The intervening player turn is a hold (the R-8 spike).** `sight.nextPhase` plays the next phase
  along its expected way, unbranched. Every enemy goes where its own decision takes it: a strike's
  tile, or the move it makes without striking (`enemyPhase` stands only strikers). Strikes take
  their expected damage. A unit of ours left at 0 HP is off the map. A striker our counter kills at
  even odds or better is gone; otherwise the counter's expected damage stays on it. Our units then
  hold, the turn advances, the fog is refreshed for where everyone now stands
  (`RefreshEntityBmMaps`), and the second phase is played as `enemyPhase` plays one, every way a
  counter may kill. Only what the player sees decides: an enemy hidden by fog does not act, and no
  arrival is placed on the map.
- **Recorded.** The plan's `lookahead` = `{ trigger, extended, skipped, calls }`, in the trace too;
  `considered[].extended`; and `protected[].second`. botrun sums `rec.lookahead` = `{ decisions,
  triggered, extended, skipped_budget, calls, cpu_s }`. `montecarlo.py suite` prints it per start
  and for the whole suite.

**Decided not to build (Nicolas, 2026-11-04).** The "first crossing" of a breach (FR-017's second
half of the first trigger): a door or wall struck triggers, stepping through it later does not.
Opening it is the move that cannot be taken back, and it already triggers; the step through is an
ordinary move the one-phase judgment covers. Reopen only on a death a replay (PR-F) ties to one.

Both measures below were taken WITH the arrival trigger, before it was dropped; the build without
it was not re-measured.

**Measured (2026-11-03, one 8-core Mac, load average about 2.5), before the review's fixes**
(see "After the review" below for the re-measure). `suite --baseline`, 52 runs:
- **SC-003:** 557,932 `AiDecideMain` calls against the budget of 678,787, 1.4% under PR-D's
  565,656. The lookahead's own cost was 616 calls to `nextPhase` and 16.0 CPU s, of 2,310.1 CPU s
  for the whole suite.
- **Triggered:** 234 of 768 planned decisions (30.5%); 154 extended, 80 skipped for budget.
  ours-ch03 alone has 62 of the skips.
- **Trigger kinds,** from the traces of the tuning seeds (26 runs, 101 triggered decisions):
  boss 54, arrival 24, breach 15, boss + breach 4, arrival + boss 4. Every skip was boss (24) or
  arrival (2). ours-ch03, a Defeat Boss map, triggered 36 times (boss 26, breach 8, both 2):
  every unit must step into the boss's reach to win, and each step is a first entry.
- **Play, tuning seeds, against PR-D's (`df18d70b20fa`):**
  - 19 of 26 runs are unchanged in outcome, turns, deaths and labelled fallbacks.
  - Wins stay at 23, deaths at 14, deaths over the cap at 0.
  - Clean clears fall from 14 to 13. Vanilla Ch5 seed 1002 lost Joshua before the Talk
    (`killed_before_talk`, the open item from 2026-10-30).
  - Turns to win moved both ways: vanilla Ch2 8 → 6, Ch3 13 → 11, Ch1 5 → 6, Ch5 9 → 10.
  - `fallback_sacrifice` anomalies rose from 2 to 8 across those runs, with no death behind them.
    The hold makes a unit that stays in reach take the second phase, so more finalists are over
    the cap.

**After the review (re-measured 2026-11-03, `suite --baseline`, 52 runs).** The `/code-review 568
medium` fixes change play: the second phase now counts every green and moves `green_die`, `hp_left`
and `value`, a surviving striker keeps our counter's damage, and the fog is refreshed before the
second phase.
- **SC-003:** 559,289 `AiDecideMain` calls against the budget of 678,787, 1.1% under PR-D's 565,656.
  The lookahead made 620 `nextPhase` calls. The machine's load average reached 45 during this run
  (2,791.5 CPU s for the suite, 19.8 s for the lookahead), so its CPU is not comparable with the
  first measure; the calls are the measure (ADR 0384).
- **Triggered:** 235 of 770 decisions (30.5%); 155 extended, 80 skipped for budget.
- **Play, tuning seeds, against PR-D's (`df18d70b20fa`):**
  - 20 of 26 runs are unchanged in outcome, turns, deaths and labelled fallbacks.
  - Wins stay at 23, deaths at 14, deaths over the cap at 0.
  - Clean clears fall from 14 to 13 (vanilla Ch5 seed 1002, Joshua killed before the Talk).
  - `fallback_sacrifice` labels across all 26 runs rise from 17 to 22, none with a death behind it.

**Decided (Nicolas, 2026-11-04, on Claude's recommendation).**
- **The hold stays.** The hold overstates risk: a real player would retreat or heal between the
  phases. Against PR-D it cost no win and no death, and no death came without a labelled
  fallback (but see ours-ch03 seed 1002 under "After #570", a case for PR-F). The
  re-proposal (R-8's first proposal) needs `sight` to stage a hypothetical board for every read
  `Bot.candidates` makes, at a cost never measured. Reopen only on a failure PR-F's replays tie to
  the hold.
- **The budget, not the boss trigger (#570).** On ours-ch03 the 32-call attempt budget was spent on
  the breaches (turns 5-7) and the approach (turns 3, 10-12), so every decision of the boss
  assault was skipped (turns 13-16 on tuning seed 1001, 15-23 on 1002); two vanilla tuning games
  hit it too. Narrowing the boss trigger to a unit's first entry was proposed first and rejected:
  the budget is gone before most units reach the boss. `M.LOOK_ATTEMPT` is 128 (the most any
  tuning game wanted was 19 triggered decisions, 76 calls); FR-018's "32 per attempt" is amended to
  match, and `matrix.yaml`'s suite manifest records 128 (test_montecarlo holds it to
  planner.lua). Raising the cap moves the limit rather than reserving any of it for late turns:
  a longer Defeat Boss map could spend it again, so a run that does now says so in its record
  (`lookahead_budget`). Measured in "After #570" below.

**After #570 (measured 2026-11-04, `suite --baseline`, 52 runs, `M.LOOK_ATTEMPT` = 128).** PR-E's
final measure, the comparison below, was taken with the arrival trigger; this build has neither
it nor the 32-call cap, so every change below is the two together.
- **SC-003:** 566,389 `AiDecideMain` calls against the budget of 678,787 (+1.3% on PR-E's 559,289,
  +0.1% on the 565,656 baseline). The lookahead made 608 `nextPhase` calls (10.2 CPU s).
- **No decision skipped for budget** (80 before): 152 of 701 decisions triggered, all extended.
  ours-ch03 extended 62 of 62.
- **Play, tuning seeds, against PR-E's final measure:**
  - 19 of 26 runs are unchanged in outcome, turns, deaths and labelled fallbacks.
  - Wins stay at 23. Clean clears rise from 13 to 14 (vanilla Ch5 seed 1002, a turn faster).
  - Deaths rise from 14 to 15: ours-ch03 seed 1002 loses unit 3 to the boss on turn 21 (predicted
    0.90, a labelled fallback). By turn 20 no plan judged was under the cap, even on one phase; the
    run had parted from PR-E's earlier, and PR-E's had a safe hold there. Whether the hold (which
    makes standing by the boss read as a second-phase death) caused it is not witnessed: it is a
    live-proof case for PR-F's replays (#570).
  - Deaths over the cap (a death's `over_cap`) rise from 8 to 9, every one on a turn with a
    labelled fallback. The unlabelled ones, which the earlier measures' "over the cap at 0"
    counted, stay at 0.
  - `fallback_sacrifice` labels rise from 22 to 29.
