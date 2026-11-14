---
id: 411
title: "A judged enemy phase splits on a counter kill only above a floor, and a decision that runs away ends its attempt `timeout`"
date: "2026-11-14"
section: "Combat System"
issues: [510]
---

# A judged enemy phase splits on a counter kill only above a floor, and a decision that runs away ends its attempt `timeout`

On the scout lap (ADR 0409), Eirika's route reached vanilla Ch15. The first decision of turn 1
ran over an hour, 8.4 million frames of game code inside the planner's simulations, made no
plan, and was stopped by hand (#510 comment 6881113521).

**The cause, from one instrumented run** (a stack sample every 600 sandbox frames and the game
calls counted, killed at 400,000 frames). 602 of 667 samples stood in `sight.lua`'s enemy
phase, in the recursion that plays the phase both ways after a striker the target's counter
may kill, with 34 to 44 Lua levels hidden under it in the deepest (about three a split, so a
dozen or more splits open at once: inferred from the depth, not counted). 116,128 enemy
decisions had been made by then and the phase was not done; the 200 phases staged before it
had cost almost nothing. The split was unbounded: every striker with any chance of dying to
the counter doubled the rest of the phase, one whose death was certain included (its
"stands" way was played at chance 0).

| Hypothesis | Test that would refute it | Result |
|---|---|---|
| The new door read (ADR 0410) is costly on this map | it is a small share of the samples | **refuted**: in none of the 667 |
| The desert makes the reach and field reads slow | they are a small share | **refuted**: 1 sample in a reach, field or turns read |
| Candidates explode (army, enemies, items) | the plan count is ordinary | **refuted** for this hang: 19 samples in the candidates' exposure reads, and once it decides, 117 acts offered and 10 plans judged. What the plans cost on this map is the next wall, below |
| A sandbox that never ends | frames grow with no new phase | **confirmed** in effect: one phase, doubling per striker |

**Decision 1: a split is played only while its rarer way is at least `Sight.SPLIT_FLOOR`
(1/64) of the whole phase.** `Sight.phaseWays` owns the split (pure, so `test_sight.lua`
holds it). Below the floor the phase goes on the likelier way alone: the striker stays on a
rare kill and leaves its tile at even odds or better, as `nextPhase`'s expected way already
has it. Each kill left unsplit is counted (`unsplit`: the phase's, the planner's cost, the
record's `plans.unsplit`), apart from `averaged`, which keeps its meaning. Every split leaves
both ways at least the floor likely, so a phase has at most 64 ways. A certain kill is no
longer split at all, which changes nothing it reads.

Against ADR 0396's tests: the quantity is the chance of a way of the phase, which the judge
already sums; it is a bound on what is played, not a ban on any act; it holds for every
objective and style; `Planner.BRANCH` bounds the plan's own uncertain kills and nothing
bounded this split; the sentence names no unit or chapter.

**The floor is a tuning value and Nicolas's to confirm.** What the instrumented runs say of
it, on Ch15's first decision: at 1/64 it costs 276,386 frames (421 judged phases, at most 25
ways a phase); at 1/256, 402,251 frames (at most 50 ways) and the same plan played (Seth's
Visit at (17,6), judged 199). Of the counter kills left unsplit at 1/64 in that run's first
1.5 million frames, 18,002 were certain kills (no information lost), 8,089 were under 5% and
the other 2,826 lay between.

**Decision 2: a decision may run `Botrun.DECISION_FRAMES` (1,500,000) frames of game code;
past that the attempt ends `timeout`.** `Sight.watched` asks a watch before every game call,
however deep the sandboxes nest; botrun's watch raises once the decision is over its budget,
each sandbox puts its writes back on the way out, and the record is emitted with outcome
`timeout` and `timeout = { turn, frames, limit, stage, plans_judged, phases }` (the last three
are the planner's `opts.at`: where it was). The environment is not clean (`fault: timeout`),
`montecarlo.py` counts it with the runs that have no game result, and a campaign stops there
under its own name, never retried: the next attempt would meet the same board and spend the
same budget.

**Why 1,500,000, and that it is Nicolas's to confirm.** The kept records hold no decision's
own frames (5,936 records read; from now on `plans.slowest` keeps the slowest decision's frames
and turn). What they do hold is each attempt's frames and plans made: the most any attempt
averaged per plan is 152,790 frames (vanilla Ch4, campaign 4003: 3,055,800 frames over 20
plans), the median 2,259. The limit is about ten times that slowest average, some ten minutes
of one worker, and under a fifth of what the hang had run when it was stopped. It is not
proven that no kept attempt held one decision above it: the largest whole attempt is
3,545,061 frames, so a limit of 4,000,000 is the one no kept record could have met.

**What it proved** (the lap's saved Ch15 start, one attempt each, campaign 4006).

| Run | Ch15's first decision | The attempt |
|---|---|---|
| main (the lap, stopped by hand) | over 8,400,000 frames, more than an hour, no plan | none |
| this change, `PT_LEAKGUARD=1` (`ch15b`) | 276,386 frames, about two minutes: Seth's Visit at (17,6) | `timeout` on turn 5 after 2,041 s: that turn's decision met the limit in the mend, 24 plans and 2,888 phases judged. One death before it (Ewan, turn 2). No leak raised over 4,131 judged phases |

Unit tests, each failing without its part of the change (run once against it): the split
rule put back to "every counter kill" plays 1,048,576 ways for 20 strikers
(`test_sight.lua`, 8 failures); the watch's limit switched off leaves the over-budget
decision to play on (`test_botrun.lua`, 7); the campaign's stop removed retries a timeout
(`test_campaign.lua`, 6). `test_bot.lua` holds the planner's `unsplit` count and `opts.at`.

**What it does not fix: Ch15's decisions are slow, and the next bound is a tuning call.**
With the split bounded, every turn's first decision on Ch15 still costs about a million
frames (turn 3: 975,518; turn 4: 1,220,020; turn 5: over the limit), seven to ten minutes
each. The cost is the judge's own product: 15 to 36 plans a decision (10 to 31 of them the
mend's), each played over its uncertain kills' ways (`Planner.BRANCH`, up to 256), each way an
enemy phase of 32 to 46 enemies deciding (500 to 1,000 frames). ADR 0384 measured `BRANCH = 8`
as never binding on the suite; on this map it binds.

One experiment, not shipped (a probe, tag `ch15x`): the same floor applied to the whole
judged plan -- a way of the plan's uncertain kills is split only while the chance off its
likeliest side is at least 1/64 of the plan, and each enemy phase starts from its way's share
-- plays the whole attempt in 216 s (500,209 frames, 1,428 phases, the slowest decision
99,102 frames). That attempt is lost on turn 6 (Ephraim falls in the enemy phase; Ewan on
turn 2 and Knoll on turn 6 before him), with no plan under the cap on turns 2, 3, 5 and 6.
It changes what `BRANCH` bounds and may move suite games, so it is recommended, not decided:
Nicolas's call.

**Untested.** Whether the floor at 1/64 moves any suite game (the frozen suite is not run for
a PR); whether any kept attempt held a decision over 1,500,000 frames; what Ch15 needs beyond
the cost (the experiment's loss and its four over-cap turns are one game: a lead).
