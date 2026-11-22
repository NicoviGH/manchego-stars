---
id: 450
title: "A goal driven to none before its deadline is forfeit"
date: "2026-11-22"
section: "Combat System"
issues: [714, 699, 510]
---

# A goal driven to none before its deadline is forfeit

**Decided (#714), #510 step 9. The scoring half of #714, Nicolas's call on 2026-11-22 ("Oh yeah I
approve your recommendations").** Amends ADR 0396's rank (`forfeits` first) and completes ADR 0444,
which left this half open. No new weight.

**The gap.** `Goals.forfeited` counted an open goal as lost only when a looter closes it within
one enemy phase (`g.closes <= 1`), the win ends the chapter, or a recruit dies. A plan that leaves
a village no unit can reach any more, with the looter still phases away, ranked the same as one
that keeps it. Vanilla Ch10 (`b640e-cs-s4005`): the Pirate razes the village (11,15) in enemy
phase 4; a turn-2 plan that left Tana too far to arrive in time forfeited nothing.

**What changed.** `Goals.forfeited` also counts a goal the plan drives from a chance of at least
`closes.gone` before it to none after it (`after <= Goals.DUST`), whatever the goal's deadline.
The planner passes the rows its own `goalTerm` already computes (`st.goalWorth`: each goal's
`before` and `after` chance) and `Planner.GONE` (0.5, the line the planner already calls
"gone"/"won"). `Goals.chance` reads 0 for a goal whose closing phase is before the phase its
taker arrives on, so "no unit can arrive in time" is the 0. A goal the plan takes reads 1, so a
taken goal is never counted. Rows that are not `feasible` (stalled, unknown) are still not
counted: `forfeited` only lists ledger rows.

**The risk, and what limits it.** A false 0 from the chance model (Rennac's 0 before #710) would
mark a plan down for a goal it never lost. The floor limits it: a goal that was never likelier
than not before the plan (`before < GONE`) is no loss. A goal that reads 0 only after a plan, from
a model that is right about the plan, is the loss itself.

**Proof (ADR 0430).** `test_goals.lua`: `Goals.forfeited` counts a goal driven from 0.6 to 0,
not one from 0.3 to 0, nor one left at 0.2 (the first fails on main). `test_bot.lua`: a unit
that must wait where the village's chance falls from 0.75 to 0 (deadline phase 3) has the village
in `plan.forfeited` (fails on main); where a tile keeps it in reach, that tile is the one played.
Replay (`resume --game vanilla --tag fix714f2 --campaigns b640e-cs-s4005 --chapter 10 --last 10
--attempts 1 --scout --route 1 --seal-at 10`; `fix714f` was already taken by an earlier #714 run):
won on turn 14, 0 deaths, the village (11,15) razed in enemy phase 3 (the Fighter). Same result as
`fix714e` (#722's code): on turn 2 Tana waits at (14,4), the village chance 0.81 to 0.72 as in
`fix714e`; main (`fix714m`) played 0.81 to 0.00 there. So #722's candidate already kept the chance
on turn 2; this rule changes no decision on this game. On turn 3 the village is already closed in
the ledger and every plan forfeits it. The rule is proven by the two tests, not by this replay.
