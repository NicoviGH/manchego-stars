---
id: 317
title: "The timeline reads when each force reaches the deploy front"
date: "2026-10-02"
section: "Combat System"
issues: [430]
---

# The timeline reads when each force reaches the deploy front

#430 step 2b, layer 2. Layer 1 (ADR 0316) scores each force as if every enemy attacked on
turn 1. `tools/timeline.py` reads when they arrive, ours and the twin's, phase by phase. It
appears in `make difficulty CH=chNN` under TIMELINE.

**Both sides are read on `danger_map.Board`.** Ours comes from the chapter YAML. The twin's
comes from the decomp: its layout (`mainLayerId` into `gChapterDataAssetTable`), its red
UnitDefinitions at their REDA end tiles with their AI bytes, and the turn its eventscript
loads each wave. `Board` now takes a ready body list (`fielded=`) for a board that is not one
of our chapters.

**The front is where the party deploys.** For us that is `deployment.deploy_slots`, or the
`player_units` tiles in a fixed-roster chapter. For the twin it is the table its
`ChapterEventGroup` names as `playerUnitsInNormal`. Scanning the eventscript for blue units
instead picks up cutscene arrays and, in vanilla Ch5, Ch4's table. The decomp's table
reproduces ch04's and ch05's `deploy_slots` exactly.

**Per body**, first contact is the first phase it can stand in weapon range of a front tile.
**Per phase**, peak threat is the expected damage on the most exposed front tile, against the
field's least durable member. The party holds the front and never advances, so a chapter the
party has to cross (ch03: neither side ever makes contact) reads as quiet on both sides. The
comparison holds because both sides are read the same way. Hard-only waves count on both
sides, as `difficulty` already counts them.

**`danger_map` learned two things it needed for every chapter, not just ch06.** A
`composition` bag's body moves as its own member. A campaign reskin slot (ch03's
brigand-brute) moves as the `class:` it clones.

**First reading**, for step 3. ch04 and ch06 track their twins closely. ch05's waves land on
turns 3 and 5, where vanilla's land on 6 and 8. ch01 puts three bodies on the front on phase 1
where vanilla puts none, and it has no counterpart to vanilla's turn-2 wave. ch02's front heats
up a phase earlier than vanilla's (31 against 7 on phase 3).
