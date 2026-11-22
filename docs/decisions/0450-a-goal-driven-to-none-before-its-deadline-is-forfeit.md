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

**What changed.** `Goals.forfeited` also counts a DATED goal (`g.closes` set: a looter or a
scripted removal ends it) the plan leaves out of reach by its deadline: its reach chance was at
least `closes.gone` before the plan (the planner's `M.GONE`, 0.5) and is none after it
(`closes.reach[id] = { before, after }`). The planner builds `reach` per plan (`reached`) with the
one chance reader, `Goals.chance` (through `chanceOf`), on the board the plan leaves with every
unit alive, no win and no opener's chance: reaching the goal alone, not the goalTerm's `after`,
which is weighted by survival, the win and a recruit's death. Those weights are the cap's and the
win's own counts, and ADR 0384 forbids counting a unit's death again as a forfeit. An undated goal
is never counted this way (the issue's "before its deadline"). `reach` and `gone` come together
(`forfeited` asserts it). No new weight. `Goals.chance` reads 0 for a goal whose closing phase is
before the phase its taker arrives on, so "no unit can arrive in time" is the 0. A taken goal is
not read.

**The risk, and what limits it.** A false 0 from the chance model, on either side. The floor
(`before >= GONE`) only guards the BEFORE side: a goal that was never likelier than not is no loss.
It does not guard an `after` 0 that is false (Rennac's 0 before #710 was an `after`-side 0: the
model read a lock on his tile as no way there). What still can give one: `sight.turnsTo` reading no
way, or too long a way, to a goal from the tile a plan leaves a unit on, or a `closes` that is
earlier than the game's real one. What limits it now: the read is the game's movement and the
looter's own closing phase, with no weight of ours; the rule needs a likelier-than-not chance to
start from; and the same read already decides the goal's chance in every plan's goal term, so a
wrong 0 here is a wrong 0 there. A false 0 would mark down a plan that moves a unit away from a
goal the read wrongly cuts off, and the plans that keep the goal in reach rank above it; it cannot
reject a plan or end a game, since forfeits order plans and the cap admits them.

**The Seize.** `best.forfeited` is written into the plan's ledger as closed, and botrun's
`unjustified_seize_skip` reads that ledger: a Seize skip is justified only while a row is feasible.
A goal the plan puts out of reach by its deadline is closed in that ledger, so it no longer justifies
holding the Seize. That is right: a goal lost by its deadline is lost, and the Seize costs it
nothing. The closure path is the one `g.closes <= 1` already takes. It cannot flag a skip the rank
chose, because forfeits rank first: a plan that forfeits every remaining goal ties the Seize on
forfeits (the win closes all) and loses to it on `complete`.

**Proof (ADR 0430).** `test_goals.lua`: a dated goal driven from 0.6 to 0 is counted; 0.3 to 0, 0.9 to 0.2
and an undated goal at 0.6 to 0 are not; `reach` without `gone` raises. `test_bot.lua`, on a village
a looter takes after phase 3: a unit waiting where its reach chance falls from 0.75 to 0 has it in
`plan.forfeited`, and the tile that keeps it (0.75 to 0.72) is the one played; a unit whose only
village is in reach but whose own death chance is 1 (the goal term's `after` reads 0.00) forfeits
nothing. Each fails against main; the death case and the undated and `gone` checks also fail
against the first version of this PR, which counted the goal term's `after`.
Replay (`resume --game vanilla --tag fix714f2 --campaigns b640e-cs-s4005 --chapter 10 --last 10
--attempts 1 --scout --route 1 --seal-at 10`; `fix714f` was already taken by an earlier #714 run):
won on turn 14, 0 deaths, the village (11,15) razed in enemy phase 3 (the Fighter). Same result as
`fix714e` (#722's code): on turn 2 Tana waits at (14,4), the village chance 0.81 to 0.72 as in
`fix714e`; main (`fix714m`) played 0.81 to 0.00 there. So #722's candidate already kept the chance
on turn 2; this rule changes no decision on this game. On turn 3 the village is already closed in
the ledger and every plan forfeits it. The rule is proven by the two tests, not by this replay.
