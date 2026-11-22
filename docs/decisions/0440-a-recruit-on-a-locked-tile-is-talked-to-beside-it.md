---
id: 440
title: "A recruit on a locked tile is talked to beside it"
date: "2026-11-22"
section: "Combat System"
issues: [710, 699, 510]
---

# A recruit on a locked tile is talked to beside it

**Decided (#710), #510 step 9.** Extends ADR 0381 (a talk recruit is a march goal).

**The bug.** In vanilla Ch14 Rennac's AI path runs over two unopened chests. `meet` priced the
walk to each path tile with `turnsTo`, and a chest tile is a locked tile: the price went through
`keyWay` and the convoy-key way. That way was taken only when `from == u` (#705), and the
planner's positions are never `u`, so after any plan that moved a talker the way was skipped and
his chance read exactly 0 (0.74 before the plan). The memo key read `from`'s coordinates, so the
same arguments read 3.2 or nil depending on call order.

**Decided.**
1. A Talk is made from a tile beside the recruit, never on his tile, so a recruit goal's
   `turnsTo` is asked with `beside`: the lock on his own tile is left out (`turnsFor`'s `keyed`
   read). A chest goal keeps its lock.
2. The convoy-key way is taken when `from` is at `u`'s coordinates, not when it is the table
   `u`. The take is this turn's act, so a unit that moved on has none, and the test now agrees
   with the memo key.

**Measure.** The effect is one replay of the game that showed the problem (ADR 0430).
