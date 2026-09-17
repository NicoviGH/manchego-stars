---
id: 274
title: "A reachability gate that skips reinforcements is grading the opening board, not the chapter"
date: "2026-09-04"
section: "Operational Gotchas (durable)"
issues: [26]
---

# A reachability gate that skips reinforcements is grading the opening board, not the chapter

`units_reaching` dropped every enemy with an `arrives_turn`, reasoning that it is "not on the
board when the clock starts". True, and irrelevant: a hull's fuse is costed against the units the
chapter **declares** as its clock, and an undeclared unit that reaches a hull on turn 5 sinks it
exactly as surely as one that reaches it on turn 1 — it just does it out of sight of a gate that
only ever looked at turn 1.

ch06's three Difficult-only turn-4 crab riders spawn on the WEST EDGE, a short ride from the west
hull's pocket, and their donor's pursuing approach walks them onto it. They were invisible, so
they carried no `ai_override` while their six turn-1 siblings all did — *"the hulls' clock is its
declared pursuers and nothing else"* had been applied to the opening board and nowhere else. They
now carry the same override, changing only the ACTION byte and leaving the donor's approach
(`0x0`, pursue) untouched.

The general form: **a guard scoped to turn 1 states a turn-1 fact, and difficulty is not a turn-1
property.** The three shipped difficulty modes are all shipped (*"Vanilla ships three difficulty
modes, so we ship three"*), so a hull that survives on Normal and sinks early on Difficult is a
defect the gate has to be able to see.

_Found by `/code-review` on #366 (2026-09-04)._
