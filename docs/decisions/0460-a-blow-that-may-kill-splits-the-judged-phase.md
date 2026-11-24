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

**Wear.** Both side records share the marginal strike's wear ledger (`after[r] = after[t]`): the
ledger holds weapon uses, not HP, and the uses spent are the exchange's expected ones, not each
side's. Per-side uses would need each leaf's wear carried through the exchange's joint, which
keeps none (`M.exchangeOf` sums it over every way). The counter-kill split already shared one
ledger across its two ways (both took `done`'s last strike's), so expected-value wear stays the
stand-in, as ADR 0423's note has it.

**Not changed.** A berserk strike on a red keeps its mean and `M.berserkKills` (the two never
both remove a target: no split is made for a berserk strike). The phase after next stays a read
of our guessed turn (ADR 0389), the larger part of its misses (#743).

**Cost, accepted (Nicolas, 2026-11-23).** The split plays more ways in every judged phase: +5.0%
CPU on an identical Ch15 game (below). Nicolas accepted it as #671's exception (the bot plays well
first; the cost is fixed there, not here): #671 comment 7118862017.

**Proof (ADR 0430).** Unit tests that fail without the change (`test_sight.lua`: the death's
ways, each with its own record and chance, the floor's three cases, the alive way's counter
split; `M.deathSplit`'s conditioned records, with and without a joint, and a death of float
dust; `test_bot.lua`: the planner's plan-wide kill ways, which now read `Sight.jointAt`, as
before).

One replay: vanilla Ch19 `b640e-cs-s4007` attempt 1, `PT_FORECAST` on. Enemy attacks on a unit
at 0 HP: 9 on main (run `fc743d19`), 0 on the branch (run `fx743n19`). Ways per next phase: 2.5
mean on main, 4.6 on the branch. Both games were lost (main: turn 6, 11 deaths; branch: turn 13,
14 deaths): a different game, so no verdict.

Timing: vanilla Ch15 `b640e-cs-s4002` attempt 1, the identical game on both (acts `1d960643`, 26
plans), base and branch back to back, load average 4-5. CPU 356.6 s -> 374.3 s (+5.0%); emulation
`run_s` 229.2 s -> 244.1 s (+6.5%).
