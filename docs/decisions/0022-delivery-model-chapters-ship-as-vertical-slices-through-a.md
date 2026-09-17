---
id: 22
title: "Delivery model: chapters ship as vertical slices through a CD pipeline."
date: "2026-06-19"
section: "Working Conventions (Definition of Done)"
issues: []
---

# Delivery model: chapters ship as vertical slices through a CD pipeline.

The unit of delivery is a *playable* chapter slice (map + events + enemies + cast-at-parity + portraits +
draft dialogue), shipped to the friend group; polish (custom battle anims, final portraits, final
dialogue) is a later layer applied to an already-playable slice, so gameplay is testable before the art
exists. Every slice passes the same gates before friends see it: the drift guard (`check.py`), balance
parity (`make difficulty CH=chNN`), and stability (boots + completes crash-free). Two parallel tracks: the
**content track** (author each slice — sequential, needs Nicolas / voice bibles / DM notes, un-swarmable)
and the **pipeline track** (the CI gates + injection tooling — parallelizable, the part agents accelerate),
which meet at the gate. The same machine feeds the post-MVP back half (Ch9–21) as the DM notes land.
_Decided: 2026-06-19 (Nicolas)_
