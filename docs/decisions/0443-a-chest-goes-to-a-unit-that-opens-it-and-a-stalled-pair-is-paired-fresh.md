---
id: 443
title: "A chest goes to a unit that opens it itself, and a stalled sent pair is paired fresh"
date: "2026-11-21"
section: "Combat System"
issues: [719, 510]
---

# A chest goes to a unit that opens it itself, and a stalled sent pair is paired fresh

**Decided (#719), #510 step 9.** Extends the exploring pass's sticky keep (`exploring`,
`bot.lua`). No new number. `ctx.exploreGoal` drives `goalFor` and candidate generation, so the set
of plans the planner sees changes; the scoring formula does not.

**The bug.** Vanilla Ch16 (`b640e-cs-s4009`, attempt 1): a keyless unit may be sent to a chest
through the Chest Key an enemy Druid drops (`sight.keySources`), so that every chest has a taker
from turn 1. Colm (a Lockpick and a Chest Key) was walled in until a thief opened his chest on
turn 10. From turn 11 the sticky `sent` pass kept Eirika and Seth on the two chests Colm opens
himself: it asked only "tile open, reached, worth more than nothing", never whether a free unit
holds an opener. Colm waited at (14,4) to turn 33 and the run stalled on turn 34. The ledger had
marked both chests `stalled` from turn 20, but nothing in `exploring` read it.

**Part 1: openers first.** A unit that uses the tile on its own (`ownOpener`: the game's menu
check, `sight.canExplore`, never asked of a unit that has acted) is paired before a unit that
reaches a chest only through an enemy's key. Fresh pairing is passes in that order (openers,
keyless, and last the unit a stalled pair dropped, Part 2). The sticky pass is two sweeps (openers'
sent pairs first) and drops a keyless sent pair while a free opener stands to take that tile. A
free opener has no goal, is not barred from the tile (the stuck record) and reaches it. The opener
found is spent: with two keyless sent pairs and one opener one pair is dropped, not both (both
dropped could swap chests and walk back, the handoff the sticky keep prevents). Turn-1 parallelism
stays: the keyless unit still takes any chest no free opener is paired to (ch23's win
`is639-t639-cs-s4004` took its chests that way), so the rejected alternative, "a key-drop pair only
when no fielded unit opens the chest", which serialises chests behind one opener, is not what this
does. A village is a tile every unit opens, so Part 1 leaves its pairing unchanged. An acted unit
keeps its tile as before.

**Part 2: a stalled pair is dropped.** A `sent` pair of a unit that can act, whose goal id is in
`ctx.quietGoals` (the ledger's `stalled`: no unit has neared it over `GOAL_QUIET` waiting player
phases), is not kept; the goal is paired fresh. It applies to a village as to a chest: nothing about
a village makes standing still fine, and the ledger marks both the same. An acted unit is the
exception: it is not in `ctx.actors`, so the fresh pass never re-pairs it, and dropping its pair
would lose its goal; it keeps the tile until it can act. Each unit is tried
once per quiet spell. `exploring` keeps `tried[goal id]` = the units a stalled goal was given to
(dropped from it, or paired to it), carried from plan to plan like `sent` (`plan.tried`, botrun's
`tried`, `opts.tried`; a re-plan within a phase gets the last plan's, as `sent` does, so a goal
cannot swap twice in a turn). A stalled pair is dropped only if its unit is not yet tried on that
goal; tried units are paired last for it, so a stalled goal is not handed back to a unit that
had it; if no other unit can take it, the tried unit keeps it. Without the record the goal
swapped A, C, A, C: `goalQuiet` counts the goal, not the pair, and its nearest reading is a min
over all takers, so the goal stayed quiet while units swapped (reproduced in review). An entry
lives only while its goal stays in `quietGoals`; once it leaves, the next stall starts fresh.
After every able unit has been tried the holder keeps the goal.

**Proof (ADR 0430).** Unit tests that fail on main: the sticky case (a freed opener beside a
chest a keyless pair holds through a drop gets it) and a stalled pair re-paired (an opener as the
sent unit, so only the quiet drop explains it). Each other rule has a test that fails when the rule
is mutated away: the fresh order (a far opener against a keyless unit beside the chest), a barred
opener, a spent opener, the acted exemption, the village, the tried record (no swap back, its fallback, its carrying, its
clearing) and botrun's pass-through of it. The control, two chests with one opener and one keyless unit taken in parallel, passes on
main and on the branch, as a control should. One replay, `fix719` (`resume --game vanilla
--campaigns b640e-cs-s4009 --chapter 16 --last 16 --attempts 1 --scout --route 1 --seal-at 10`),
before these review changes: won on turn 19 with 1 death (Dozla, turn 5, as in `fix711c`), where
`fix711c` stalled on turn 34. Chests: (20,5) opened by Marisa on turn 13, (20,3) by Colm on turn
14, (3,12) opened by the thief (enemy) on turn 10; (20,1) was not opened.

**Why (20,1) was missed (confirmed): a gap in ADR 0442, filed on #711.** On turn 13 the thief took
Colm's Lockpick (107), the fifth entry of the steal list. Colm kept his single-use Chest Key (105),
so ADR 0442's last-opener price read "still opens" and priced the theft at zero. He spent the key
on (20,3) on turn 14, leaving none for (20,1). The turn-14 theft was the chest's reward (101), not
his key. This PR does not touch that.
