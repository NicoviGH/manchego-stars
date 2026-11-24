---
id: 463
title: "A struck unit keeps its likeliest HP in the copy's enemy phase, never the mean"
date: "2026-11-24"
section: "Combat System"
issues: [743, 510]
---

# A struck unit keeps its likeliest HP in the copy's enemy phase, never the mean

**Decided (Nicolas with Claude, 2026-11-24, #743 comment 7121316555), #510 step 9.** It follows
ADR 0460 (a blow that may kill splits the phase), ADR 0461 (an idle mover moves) and ADR 0462 (a
dying carrier sets down whom it carries): the copy's board between two enemies' decisions should
be one the game can produce.

**The problem (measured, #743 comment 7119556199).** The copy left a struck unit that lives at
its mean HP: its target's expected loss, rounded. The enemies after it score every candidate's
HP (cp_battle.c, the low-HP and kill components), and a candidate's HP differed from the game's
in 7 of the 8 departures traced. Witness: `fc743d21` (vanilla Ch21 `b640e-cs-s4009` attempt 1)
turn 13, Knoll at 19 in the copy, 29 in the game, and enemy 133 struck another unit.

**Why the likeliest result, not the mean, and not every outcome.** No player sees an average HP.
Before the dice, a player reads a blow by its likeliest case ("he probably gets hit, so he'll be
at 20"); the mean (23 after a 70% hit for 10 on 30 HP) is an HP the game cannot produce. A split
on every HP outcome was sized off for its cost (it multiplies the ways); the likeliest result
adds no way.

**The change (`sight.lua`).**
- One owner, `M.likeliestLeft(dists, hp)`: the HP a unit keeps at the likeliest outcome it lives
  through (M.damage's distribution of the exchanges together). Equal chances go to the larger
  loss. nil when no outcome leaves it alive.
- Its users, every place the judged phases left a living unit at a mean:
  - `M.deathSplit`'s `aliveHp`: the alive side's likeliest outcome.
  - The phase's `strike` (both judged phases, the lookahead's included): a blow that cannot
    kill leaves its target at the likeliest HP. A berserk strike, which is not split, kills at
    even odds or better (as the next phase's expected way takes a kill), else the same.
  - The next phase's striker our counter does not fell, and `armyReply`'s killer after the
    counter it takes: the likeliest HP, 1 when none.
- The death split itself (ADR 0460) is unchanged.

**Left out by scope.** The planner's own HP sums for its attacks on reds (`planner.lua`
`fx.hp`, `st.enemyHp`, the plan-wide kill ways' `left`) still read means: those are the plan's
own turn, not the copy's enemy phase. The weapon-use ledger (`M.wear`) still spends expected
uses.

**Proof.** `test_sight.lua`: `likeliestLeft` (the 70%-for-10 case, a likely miss, a likelier
death aside, a tie, two exchanges, no living outcome) and `deathSplit`'s `aliveHp` (5, the
likeliest, where the mean gave 6). Both fail on main's `sight.lua`. One replay: run `lh743a`
(vanilla Ch21 `b640e-cs-s4009` attempt 1, `PT_FORECAST` instrument applied uncommitted), against
`fc743d21` (main) and `fx743i` (after ADR 0461). Its game follows `fx743i`'s to turn 8, so the
witness turn 13 board was not reached: that case stays untested. One new miss, turn 1, is the
dice: enemy 137's blow on Eirika hits 55% of the time, so the copy left her at 23 where the game
rolled the miss (29), and enemy 138 chose another target. It shows the price of the rule: a blow
near even odds is read as its likelier side, where the mean hedged. Unmatched phases 2 of 36
(main 3 of 40, `fx743i` 2 of 32); deaths 1, read at 0.01 (main 3, `fx743i` 2). One game each: no
measure.
