---
id: 415
title: "One split floor bounds the whole judged plan: its uncertain kills and its enemy phases"
date: "2026-11-15"
section: "Combat System"
issues: [510]
---
# One split floor bounds the whole judged plan: its uncertain kills and its enemy phases

ADR 0411 bounded the enemy phase's counter-kill split by `Sight.SPLIT_FLOOR` (1/64) and left
the next bound, the same floor over the whole judged plan, as a recommendation for Nicolas.
Nicolas left the overnight run of 2026-11-15 to Claude's own calls, so it was taken then on
the evidence below. It is his to reverse.

**The cost, measured** (tag `ch15diag2`, the decision cap lifted on a throwaway branch,
party1c's Ch14 start played into vanilla Ch15, Eirika's route). Ch15's turn-2 decision ran
6,027,632 frames, over the 4,000,000 cap. It judged 33 plans and 5,041 enemy phases. Over
the attempt's 23 judged decisions, the mend's plans took 52% of the phases (10,546 of
20,427) and the beam's took 44%. A beam plan averaged 98 phases and a mend plan 57: each
plan is played once per way its uncertain kills can go (`Planner.BRANCH` of them, up to 256
ways), and each way is an enemy phase of 30 to 46 enemies.

| Hypothesis | Test that would refute it | Result |
|---|---|---|
| The mend is the cost, so a screen over its tries is the bound | the beam's plans are a small share | **refuted**: the beam's are 44%, and a mend-only screen leaves them |
| The cost is the product of the plan's ways and the phase's splits | the floored plans cost about as much | **confirmed**: the floor cuts the slowest decision 36-fold (below) |
| The floor changes what the bot decides | its play diverges early from the unfloored run | **refuted** on this evidence: Ch14's 27 turns are act for act the same, and Ch15's first 49 acts |

**Decision: a way of the plan's uncertain kills splits on the next kill only while the chance
off that kill's likeliest side is at least `Sight.SPLIT_FLOOR` of the whole plan, and each
enemy phase is told its way's share of the plan (`mass`), so its own counter splits are
bounded by the same floor of the plan, not of the phase.** Below the floor, the way keeps the
average, as a kill past `BRANCH` does, and a kill every way left unsplit counts as averaged,
not branched. The bound is on the chance off the likeliest side: a counter's dim of three or
more ways may still leave one of its ways rarer than the floor, and `BRANCH` bounds the
ways. The lookahead's phase is the plan's average way, the whole plan, so its share is 1.
Each way left unsplit is counted (the planner's
`cost.floored`, the record's `plans.floored`), apart from `averaged` and `unsplit`. The
planner reads the floor from the sight (`sight.splitFloor`), so `Sight.SPLIT_FLOOR` stays
its one owner.

Against ADR 0396's tests: the quantity is the chance of a way of the plan, which the judge
already sums; it bounds what is played, it bans no act; it holds for every objective and
style; nothing else bounded the product of the two splits; it names no unit or chapter.

**What it proved** (the same start, one attempt each, campaign 4006):

| Run | Ch14 | Ch15 slowest decision | Ch15 |
|---|---|---|---|
| main, cap lifted (`waitfix2`) | won, 27 turns, 468,778 frames, acts hash 189d8d55 | 3,557,992 frames (turn 2) | lost on turn 23, Ephraim falls (77% predicted, over the cap: a sacrifice) |
| the floor (`floor1`) | won, 27 turns, 203,315 frames, acts hash 189d8d55 | 98,542 frames (turn 2) | lost on turn 11, Ephraim falls (6.5% predicted: the dice) |

The whole floored run took 5.5 minutes against `waitfix2`'s 55. Unit tests, each failing
without the change: `test_bot.lua` (an even kill splits the plan into two phases, each told its
share; a 1% miss stays one phase and is counted) and `test_sight.lua` (a 10% counter kill
splits a phase that is the whole plan and not one that is a tenth of it).

**Untested.** The evidence that the floor keeps the bot's choices is one start and one seed.
Whether the floor moves any frozen-suite game: the suite is not run for a PR
and runs before the bot's reading is next relied on. What Ch15 needs beyond the cost: all three
Ch15 games tonight fell back to a sacrifice plan on most turns, and the two losses are
Ephraim's death, the floored one at 6.5%. That is one game each, a lead and not a cause.
