---
id: 265
title: "A donor carries its AI, so there is nothing left to allowlist"
date: "2026-08-31"
section: "Operational Gotchas (durable)"
issues: [335]
---

# A donor carries its AI, so there is nothing left to allowlist

#335 proposed guarding AI drift the way `terrain_divergence` guards the map: bucket the twin's AI
by behaviour family, compare it against what our `ai_pattern` labels emit, and **fail unless the
difference is declared in an `ai_divergence:` block with a reason**. That block was never built,
and should not be.

The allowlist design assumed we AUTHOR the AI and reconcile the deltas afterwards. We no longer
author it. Every enemy now names a `donor:` -- the vanilla unit it is modelled on -- and the build
reads that unit's four `.ai` bytes straight out of `src/events_udefs.c`. There is no second
opinion for a chapter-level allowlist to referee. `ai_pattern` is gone from all six chapters
(63 entries), and `resolve_donor` raises when a donor cannot be resolved or when two candidates
disagree, so the parity gate already fails on exactly the condition the block was meant to catch.

Deliberate departures are still declared -- at the unit, which is where they actually happen.
`ai_override:` takes the bytes plus a **mandatory `why`**, and `ai_donor_findings` fails a build
that omits the reason ("an undeclared reason is a silenced guard, not a decision"). Three units use
it, each for a reason the donor cannot express: ch00's O'Neill, whose real AI is `DoNothing` and
only works because vanilla event-scripts his attack, would field a boss that never acts. That is
the divergence mechanism #335 wanted; it just belongs per-unit rather than per-chapter, because a
donor is chosen per-unit.

A donor is matched on where a vanilla unit **fights** -- the last point of its REDA path -- not
where it spawns. Matching on `xPosition`/`yPosition` looked right and silently mismatched ch05:
9 of 23 units resolved before the post was used as the key, 23 of 23 after.

The lesson generalises past AI: **when a fact can be DERIVED from the donor, deriving it removes
the need for a divergence block rather than requiring one.** A divergence allowlist is the right
shape only where we genuinely author something the twin also has an opinion about -- the map, where
our layout is ours and the comparison is advisory. Adding one here would have created a second
source for a fact the donor already owns, free to drift out of agreement with the ROM.

What #335 asked for that DOES survive: AI is visible in `make chapter CH=chNN` alongside scenes and
art, so a chapter's AI fidelity is legible without remembering to look.
