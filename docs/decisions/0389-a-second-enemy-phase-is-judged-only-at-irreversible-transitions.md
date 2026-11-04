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
  in a seen boss's reach (`sight.threat`) from a tile outside it (`boss`); the turn on, or the turn
  before, a known arrival (`arrival`: `style.arrivals`, a guide claim's or a retry's memory, ADR
  0386, through `Bot.nextArrival`). A boss the fog hides triggers nothing.
- **All or none (FR-018).** The finalists are the best `M.FINAL` plans judged, by rank. If any
  triggers, each one gets one call to `sight.nextPhase`, or none does. The budget is
  `M.LOOK_DECISION` = 8 calls a decision and `M.LOOK_ATTEMPT` = 32 an attempt (botrun passes what is
  left as `opts.budget.attempt`). Too little left keeps the one-phase horizon, tagged `skipped`.
- **What the second phase reads.** Each protected unit's death chance becomes the chance it dies in
  either phase, `1 - (1 - first) * (1 - second)`. Its first-phase branches are kept. The game-over
  chance composes the same way. The finalists are then ranked again among themselves. A plan
  outside them lost to each one on the first phase and was never asked the second.
- **The intervening player turn is a hold (the R-8 spike).** `sight.nextPhase` plays the next phase
  along its expected way, unbranched. Every enemy goes where its own decision takes it: a strike's
  tile, or the move it makes without striking (`enemyPhase` stands only strikers). Strikes take
  their expected damage. A unit of ours left at 0 HP is off the map, and a striker our counter kills
  at even odds or better is gone. Our units then hold, the turn advances, and the second phase is
  played as `enemyPhase` plays one, every way a counter may kill. Only what the player sees decides:
  an enemy hidden by fog does not act, and no arrival is placed on the map.
- **Recorded.** The plan's `lookahead` = `{ trigger, extended, skipped, calls }`, in the trace too;
  `considered[].extended`; and `protected[].second`. botrun sums `rec.lookahead` = `{ decisions,
  triggered, extended, skipped_budget, calls, cpu_s }`. `montecarlo.py suite` prints it per start
  and for the whole suite.

**Not built.** The "first crossing" of a breach (FR-017's second half of the first trigger) is
left out: a door or wall struck triggers, but stepping through it later does not.

**Measured (2026-11-03, one 8-core Mac, load average about 2.5).** `suite --baseline`, 52 runs:
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

**Open (for Nicolas).**
- **The hold or the re-proposal.** The hold overstates risk: a real player would retreat or heal
  between the phases. The re-proposal (R-8's first proposal) needs `sight` to stage a hypothetical
  board for every read `Bot.candidates` makes. Its cost is not measured.
- **The boss trigger on a Defeat Boss map.** It fires on most decisions there and spends the
  attempt's budget (ours-ch03). "First entry" may want to mean the first unit of the attempt, not
  each unit.
