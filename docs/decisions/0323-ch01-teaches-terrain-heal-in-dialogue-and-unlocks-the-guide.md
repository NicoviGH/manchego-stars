---
id: 323
title: "ch01 teaches terrain healing in dialogue, and unlocks the Guide on every difficulty"
date: "2026-10-02"
section: "Story & Dialogue"
issues: [21, 135]
---

# ch01 teaches terrain healing in dialogue, and unlocks the Guide on every difficulty

The v0.1.0 playtester read ch01's healing forts and gate as a glitch (#135 finding 8). Vanilla
teaches the same thing in its Ch1 (`EventScr_Ch1Tut_GuideTerrainHeal`: a tutorial box naming
Breguet on his gate, then `ENUT(0xCE)`), but only in tutorial mode, and ADR 0104 keeps tutorial
mode off Normal. A faithful copy would have hidden the fix from the player who reported it.

**So the lesson is party dialogue, per ADR 0156's C-hybrid, and it plays in every mode.** On
turn 1, right after Izobai's taunt, Wolfram smells woodsmoke: the goblins have fires in the
mounds and behind the gate, and anyone resting there thaws out and heals. The cold of Icewind
Dale is the in-world reason the tiles heal. Then vanilla's tail runs unchanged: the cursor
flashes on her gate and the two camp-front forts, and `ENUT(0xCE)` unlocks the Guide's
"Fortresses & Castle Gates" entry.

That flag also makes the Guide command appear at all. `IsGuideLocked()` hides it until some
Guide flag is set, and until this change none was set before ch05's arena (flag 234), so ch01
to ch04 had no Guide. The `ch01guide` verdict scenario asserts both the flag and the menu entry.

The speaker talks whether or not he is deployed, as RBG's ch02 flier warning does.

_Decided: 2026-10-02 (Nicolas) — dialogue over a tutorial box, Wolfram's line picked from
drafts; the in-world reason was his question ("why would a gate and mound heal them?")._
