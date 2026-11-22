---
id: 454
title: "An enemy-phase death is graded by the committed plan's weighted read"
date: "2026-11-22"
section: "Combat System"
issues: [717, 510]
---

# An enemy-phase death is graded by the committed plan's weighted read

**Decided (Nicolas, 2026-11-22, "Oh yeah I approve your recommendations"; #717's classing
comment).** Reverses ADR 0400 §1. It changes what the `over_cap`, `rng_tail` and blindspot
("other" at 0) counts mean; it changes no play.

**The error.** Three vanilla Ch15 deaths to Caellach (0x53) in tag `p709b` were graded 0
(blindspots) though every plan read them. `botrun.lua` `M.grade` read two things wrong:
- **The plan.** It graded by the plan that last moved the unit (ADR 0400 §1). In all three, that
  plan was an assault that protected its earlier attackers only through a later bait act; a
  replan dropped the bait and left the attacker stranded. The enemy phase was played against the
  replan, not the mover.
- **The number.** It read `predict[].die`, the likeliest way of the judged phase. For Cormag
  (0x0E) the mover plan read 0 there and 0.041 weighted over every way.

**The call.** An enemy-phase death is graded by the phase's last plan (botrun's `commit`, the plan
the enemy phase was played against), by `protected[].die`: the chance `Planner.admit` tests
against the cap, over every way of the judged phase plus the lookahead's second phase (and the
wear, where read). A unit the plan does not protect (an allied green) is read from its `predict`.
The mover plan's read is kept beside it (`mover_predicted`, `mover_ref`), never graded.
`M.deathRead` is the one reader of a plan's death chance for a unit. A player-phase death is
unchanged (its counter's `die`).

**Why not the mover (ADR 0400 §1's reason).** That ADR moved off the phase's last plan because a
unit moved under the cap and found over it by a replan read `over_cap`. That is what happened: the
plan played into the enemy phase accepted the risk. The cap's verdict belongs to the plan the
phase met; what the mover believed is the second field, for asking why the replan changed it.

**Proof.** `test_botrun.lua`: a death with `predict.die` 0 and `protected.die` 0.041 grades
0.041, a tail, over a 1% cap (fails on main: 0); the mover test now grades the replan's 90% and
keeps the mover's 30% beside it (fails on main). Re-graded from the kept `p709b` traces, the
three deaths read 0.744 (cap 0.01: over_cap, Saleh 0x17), 0.0455 (cap 0.05: rng_tail, Cormag) and
0.324 (cap 0.05: over_cap, Joshua 0x20), as #717 classed them by hand.

**Left open, #736.** The bait question: a plan that protects earlier attackers only through a
later bait act is priced as if the bait always runs.
