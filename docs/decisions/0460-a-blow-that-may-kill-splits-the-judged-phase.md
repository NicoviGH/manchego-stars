---
id: 460
title: "A blow that may kill our unit splits the judged phase, and no unit stays on the map at 0 HP"
date: "2026-11-23"
section: "Combat System"
issues: [743, 510]
---

# A blow that may kill our unit splits the judged phase, and no unit stays on the map at 0 HP

**Decided (Nicolas, 2026-11-23: "yes build it", on #743 comment 7117572249's recommendation),
#510 step 9.** Amends ADR 0411 (the split and its floor), which split a phase only on our counter
killing the striker.

**The problem (measured, #743 comment 7117572249).** In the copy's enemy phase, an enemy's blow
left its target at the blow's mean damage. A likely death therefore stayed on the map, at 0 HP
when the mean reached the unit's HP, and the enemies after it struck the corpse. Seven
instrumented games (`fc743d*`, `PT_FORECAST=1`): 26 of 748 attack decisions in the next phase and
27 of 458 in the phase after next went to a unit at 0 HP. Where the copy first departed from the
game, a struck unit's HP was the cause in 10 of 21 phases (vanilla Ch19: enemies 137 and 139
struck green unit 68 at 0 HP, while in the game they killed our unit 2).

**1. The split (`sight.lua` `M.deathSplit`, `M.phaseWays`, the phase's `strike`).** An enemy's
blow that may kill its target splits the phase like a counter kill (ADR 0411): the enemies after
it decide once with the unit dead and off the map (`t.kill`: HP 0, `M.takeOff`), and once with it
alive. Each way's list carries that side's record of the blow (`t.deadT`, `t.aliveT`): its damage
and our counter as that side's joint outcomes took them (`t.joint`), so the planner's per-way
death read counts the death once, and a dead unit's counter fells no one. The alive way then
splits on our counter's kill at its own chance. The floor (`SPLIT_FLOOR`, of the whole judged
plan, ADR 0415) bounds both kinds alike.

**2. The board, split or not.** The unit is left at the HP it keeps given it lives (its expected
loss there, rounded, at least 1), never the mean. Below the floor the phase goes on the likelier
side: the unit is taken off at a death of 50% or better, as a counter kill takes the striker. The
blow keeps its whole record then, so its death chance is still read; the count goes to `unsplit`.
The lookahead's first phase, played along its expected way, takes the unit off on the same rule
(it took it off only at 0 HP).

**Not changed.** A berserk strike on a red keeps its mean and `M.berserkKills`. The phase after
next stays a read of our guessed turn (ADR 0389), the larger part of its misses (#743).

**Proof (ADR 0430).** Unit tests that fail without the change (`test_sight.lua`: the death's
ways, each with its own record and chance, the floor's three cases, the alive way's counter
split; `M.deathSplit`'s conditioned records). The replay and the timing are in PR's body.
