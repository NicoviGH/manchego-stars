---
id: 363
title: "A chapter not written yet is its vanilla twin, for the difficulty math"
date: "2026-10-22"
section: "Combat System"
issues: [510]
---

# A chapter not written yet is its vanilla twin, for the difficulty math

Nicolas, 2026-10-22: a `status: planned` chapter does not exist yet. Period. Until it is
written, its difficulty is its vanilla twin's, and its draft YAML is never read as a force.

The curve already did this (ADR 0087): a planned row prints its twin's numbers as the
target. The per-chapter report (`make difficulty CH=chNN`) did not. It read the draft's
roster and levels and printed them under a "seed, not authoritative" banner. That read broke
once the board and the combat read shared one force walk (#525). ch08's draft has an unarmed
entry with no position and no donor, and the walk asked it for AI.

**Now** `difficulty.unwritten_projection` is the one answer for an unwritten chapter. On
`VANILLA_CHAIN` it is the twin's force against the twin's arriving party (`planned_target`).
Off the chain it is the fixed yardstick (`vanilla_projection`). The curve's planned rows and
the per-chapter report both print it, and the report reads nothing else from the draft.

**A written chapter places every body it fields.** `danger_map.bodies` raises on a body with
no position, rather than leaving it off the map while the parity read still fights it. The
board and the force then could not stay the same list, and step 7's engagements index one
into the other.
