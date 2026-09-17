---
id: 270
title: "A rescue clock is a HIT RATE, so a scenario MEASURES it and never asserts it"
date: "2026-09-04"
section: "Operational Gotchas (durable)"
issues: [26]
---

# A rescue clock is a HIT RATE, so a scenario MEASURES it and never asserts it

ch06's chapter YAML declares its two hulls sinking on **turn 7 and turn 8**, and `ch06clock` was
about to assert exactly that. It does not, and the reason generalises past this chapter.

The west fuse is one Level 1 Bael swinging a venin claw at a 19 HP, 5 Def hull sitting in FOREST.
Read off the decomp's own tables: 6 damage a connection, four connections to sink it, and a **47
displayed hit** into the hull's +1 Def / +20 avoid cover — 45% true on 2RN. Seven phases of that
sink the hull about **38%** of the time. "Turn 8" is not a turn number; it is the middle of a
distribution, and one playtest is one sample of it. A scenario that asserted the declared turn
would be a coin-flip verdict: green or red on the same unchanged ROM, which is worse than no
coverage because it teaches the next session to re-run until it passes.

So the case splits what it does by what is actually deterministic:

- **Asserted** — the pathing. Neither pursuer stalls short of its hull; the range-1 attacker, once
  in range, is standing on the pocket's single door cell and nowhere else; nothing reaches a hull
  on enemy phase 1. Those are properties of the map and the AI, and they are the same every run.
- **Measured and logged** — the sink turn, printed against the declared one. A run that disagrees
  is a finding about the chapter's balance, not a broken scenario.

The corollary for the instrument: **the first run of `ch06clock` watched two units and could not
name a third.** An 11-damage hit landed on the east hull during enemy phase 1 while the only mover
near it was three tiles out and nothing in the emitted `MS_Ch06Line` was in weapon range at all.
That gap is not a bad guess, it is a scenario too narrow to distinguish "the AI did something
surprising" from "what LOADED is not the table we emitted" — so it now dumps the whole red roster
at turn 1 and every red within three tiles of a hull the moment the hull loses HP. A run costs the
same either way; the reading is what varies (see *"Playtest runs are the most expensive thing in
this repo"*).

What that first run actually returned is on **#26**, and the response — retune the placement, or
restate the budget the chapter claims — is not settled here.
