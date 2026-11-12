---
id: 403
title: "A wait that gains nothing ends: a stalled goal does not hold the win, and sixteen quiet player phases end the attempt"
date: "2026-11-12"
section: "Combat System"
issues: [510]
---

# A wait that gains nothing ends: a stalled goal does not hold the win, and sixteen quiet player phases end the attempt

**Item C of the fwd1 build plan (#510 comment 6810567866).** Rule 1 is call 3 of that comment,
approved by Nicolas on 2026-11-11 ("I approve all calls"); it amends FR-015 (a win put off is
justified while a ledger goal is still to get). Rule 2 is call 2, whose number Nicolas left to
Fable on 2026-11-12.

**The error.** A resumed vanilla Ch8 run (24 attempts, 2 campaigns) gave 13 wins, 1 loss and 10
`stuck`. Seven of the `stuck` attempts were offered the Seize hundreds of times and skipped it,
because a ledger goal (a chest nobody got nearer to) stayed `feasible`, so the win forfeited it
and every plan with the Seize ranked below a wait.

**One definition of progress.** A player phase made progress when it made an event (a kill made
in the player phase, a Visit, a Talk, a Chest, a door opened, a wall broken, the Seize) or a
new low in turns-to-goal: the objective's nearest unit, or a ledger goal's best taker, strictly
nearer than at any earlier reading of that id. The planner reads the turns (`plan.nearest`);
botrun counts the phases (`rec.progress`, the `progress` trace lines).

**Rule 1: a ledger goal nobody has neared for three player phases stops holding the win.** Per
goal id, botrun counts the readings in a row without a new low of its own
(`M.GOAL_QUIET` = 3, FR-007's number). At three, the goal's ledger row is `stalled` (a reward
needing it too; an `unknown` row stays `unknown`). `Goals.forfeited` counts `feasible` rows
only, so the win no longer forfeits it and the Seize is not outranked on forfeits. The goal is
unchanged for the units: they may still walk to it, and one new low makes its row `feasible`
again. A stalled ROW is not a stalled board (`opts.stalled`, a repeated board). A won run whose
missing reward's row was stalled in the last plan reports it as `stalled` in `missed_rewards`.

**Rule 2: sixteen player phases in a row with no progress end the attempt `stuck`**
(`M.QUIET_BOUND` = 16). Every kept vanilla win outside the old Ch8 waits has at most 15 such
phases (#510 comment 6828202335). The 13 wins of the resumed Ch8 run have at most 2 under the
full definition; its `stuck` attempts ran 8, 20, 30, 83, 389, 414, 436, 523, 611 and 1,206.
Sixteen spares every kept win and ends a wait within one more phase. It fires at the top of a
player phase, under the board-repeat rule's guard (a turn event still to fire may change the
board) and not while a Survive objective counts turns down, whose wait is the play. The count
lags one phase (a phase closes at the next phase's first plan), and the bound never resets it:
the record stays the plain count.

**Not changed.** `idle_3` and FR-007's stall still count the lord's moves; they are not this
signal, and changing what a stall event means is a separate call. There is no rule for a boss
nobody can kill under the cap: the bound ends that attempt.

**Known limit.** A phase's near half is read at the next phase's first plan, so it also holds
what the enemy phase did. On a Rout chapter the objective is the nearest enemy, and an enemy
walking in is a new low for `objective`; the trace's `near` names the id.

**ADR 0396's tests.**
1. Quantities: the game's turns to a tile (`sight.turnsTo`), its events, its turn events and
   Survive counter. Met.
2. Rule 1 is an ordering input (a row's status feeds the forfeit count the rank already reads),
   and forbids no act. Rule 2 is a bound on an attempt, not a move filter: it ends the run and
   forbids nothing the game allows. Only partly an "ordering"; it is a measurement's stop.
3. Every objective: Seize and Defeat Boss read the objective's nearest unit; Survive is
   excluded by name of its quantity (turns left). On Rout the near half can be satisfied by an
   enemy walking in, which delays the bound (above). Partly met.
4. No second owner: the rank's forfeit count stays the one place that holds a win back, and
   rule 1 only changes what it counts. The board-repeat rule is the other `stuck` rule, over a
   different quantity (a repeated board). Met.
5. The sentences name no unit, chapter or turn; the Ch8 numbers are the evidence above. Met.

**Amends** ADR 0388 (the record's `progress` and the `stalled` missed-reward reason), FR-015
(a stalled row is not an open goal for the seize-skip record).
