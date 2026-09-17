---
id: 237
title: "A wash-out is a CHROMA failure, and our checks all measured luminance"
date: "2026-08-12"
section: "Operational Gotchas (durable)"
issues: [265]
---

# A wash-out is a CHROMA failure, and our checks all measured luminance

Two Arena palettes were authored, shipped past every automated check, and were rejected on
sight — the combat coliseum and then the welcome exterior. Both preserved luminance faithfully
(the exterior's range even *widened*, 159 → 175) and both crushed saturation: the masonry went
from 0.29–0.74 down to 0.10–0.20 and stopped reading as stone. Nothing we assert on catches
that, because a palette test naturally reaches for "is it the right brightness."

Two durable rules came out of it:

- **Recolour work is expressed as a DELTA over vanilla, never as a replacement palette.** Name
  only the words that change; the build composes them over the base ROM's own bytes. A delta
  cannot wash out what it does not mention, and it preserves animated entries for free (the
  Arena backdrop cycles 3 of its 64 words — a hand-authored phase set has to reproduce that
  by hand and silently flattens it if it doesn't).
- **Assert what stayed VANILLA, not only what changed.** A proof that only checks the new
  colours arrived would have passed the rejected palettes too. `ch05arena` now anchors three
  untouched vanilla words per view alongside the ones it expects to move.

Artistically the same lesson: cooling *everything* reads as fog, not winter. Warm stone under
a cold sky is colder than cold stone under a cold sky, because the contrast is what carries it.
_Decided: 2026-08-12 (Nicolas + Claude, #265)._
