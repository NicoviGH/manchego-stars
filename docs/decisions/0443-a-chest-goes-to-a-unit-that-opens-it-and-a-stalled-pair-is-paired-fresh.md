---
id: 443
title: "A chest goes to a unit that opens it itself, and a stalled sent pair is paired fresh"
date: "2026-11-21"
section: "Combat System"
issues: [719, 510]
---

# A chest goes to a unit that opens it itself, and a stalled sent pair is paired fresh

**Decided (#719), #510 step 9.** Extends the exploring pass's sticky keep (`exploring`, `bot.lua`). No new number, and no plan is
scored differently: only `ctx.exploreGoal` changes.

**The bug.** Vanilla Ch16 (`b640e-cs-s4009`, attempt 1): a keyless unit may be sent to a chest
through the Chest Key an enemy Druid drops (`sight.keySources`), so that every chest has a taker
from turn 1. Colm (a Lockpick and a Chest Key) was walled in until a thief opened his chest on
turn 10. From turn 11 the sticky `sent` pass kept Eirika and Seth on the two chests Colm opens
himself: it asked only "tile open, reached, worth more than nothing", never whether a free unit
holds an opener. Colm waited at (14,4) to turn 33 and the run stalled on turn 34. The ledger had
marked both chests `stalled` from turn 20, but nothing in `exploring` read it.

**Part 1: openers first.** A unit that uses the tile on its own (`sight.canExplore`, the game's
menu check, asked only of a unit that can act) is paired before a unit that reaches a chest only
through an enemy's key. Fresh pairing is two passes (openers, then the keyless take what is left);
the sticky pass is two sweeps (openers' sent pairs first) and drops a keyless sent pair while a
free opener stands to take that tile. Turn-1 parallelism stays: the keyless unit still takes any
chest no free opener is paired to (ch23's win `is639-t639-cs-s4004` took its chests that way), so
the rejected alternative, "a key-drop pair only when no fielded unit opens the chest", which
serialises chests behind one opener, is not what this does. An acted unit keeps its tile as
before. A village is a tile every unit opens, so its pairing is unchanged.

**Part 2: a stalled pair is dropped.** A `sent` pair whose goal id is in `ctx.quietGoals` (the
ledger's `stalled`: no unit neared it over `GOAL_QUIET` waiting player phases) is not kept; the
goal is paired fresh, by the same rule as any other. This reuses the ledger's own mark.

**Proof (ADR 0430).** Unit tests that fail on main: the sticky case (a freed opener beside a
chest a keyless pair holds through a drop gets it), a stalled pair re-paired (two tests), and the
control, two chests with one opener and one keyless unit, taken in parallel (passes on main and
on the branch, as a control should). One replay, `fix719` (`resume --game vanilla --campaigns
b640e-cs-s4009 --chapter 16 --last 16 --attempts 1 --scout --route 1 --seal-at 10`): won on turn
19 with 1 death (Dozla, turn 5, as in `fix711c`), where `fix711c` stalled on turn 34. Chests:
(20,5) opened by Marisa on turn 13, (20,3) by Colm on turn 14, (3,12) opened by the thief
(enemy) on turn 10; (20,1) was not opened. The same thief stole Colm's Lockpick (turn 13) and
Chest Key (turn 14), so the last chest lost its opener to a theft, not to the pairing; that is
read from the trace's thief lines and the result line, and no run was made to test it.
