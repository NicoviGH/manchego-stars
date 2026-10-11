---
id: 341
title: "ch07 rides snowy-bern; the castle it lacks is ported in from snowy-fields"
date: "2026-10-11"
section: "Art & Audio"
issues: [27]
---

# ch07 rides snowy-bern; the castle it lacks is ported in from snowy-fields

Nicolas, 2026-10-11, after comparing three renders of vanilla `Ch7Map`. **The pick was the hybrid:**
snowy-bern as the base, so Bremen stays in the same family as the other snowy-bern towns, plus the two
things snowy-bern lacks.

- **The keep.** Snowy-bern has no castle. snowy-fields (N426's snow Fields) has one at vanilla's own
  metatile ids, and it is ported into snowy-bern's empty slots 69/83/94/95/96/97/101/115/120. It is
  recoloured into lit bank 4, and its ground is redrawn from snowy-bern's snow (metatile 99), so it
  stands on the map's own snow. The terrain is vanilla's: `TILE_2C`, with the gate (slot 115) as
  `GATE_CASTLE`.
- **Lake water.** Snowy-bern has no `LAKE` (0x16) metatile, and Ch7's moat is lake. Slot 121 is
  metatile 276's art (the water ch06's lake uses) stamped `LAKE`, per ADR 0013.

Both are mapped in `reskin-learned.json`, so any later Fields-based retile inherits them.

**There was room only after deduplication.** The map tile sheet is a hardware ceiling. obj1 and obj2
both decompress into BG VRAM 0x8000-0xFFFF (`bmmap.c` UnpackChapterMapGraphics), which holds exactly
the 1024 ids a TSA entry can name. Snowy-bern had 13 free tiles and the castle needs 36.
`map_tileset_tool.dedupe_tiles` merged 35 exact or mirrored duplicates. Every metatile, and every
shipped map on snowy-bern and snowy-bern-ice, renders pixel-identically after it. The work is done
by `dedupe_tiles` and `port_structure`, and both write a base and its variants together, so
snowy-bern-ice stays a compatible variant.

**Rejected:**
- snowy-fields for the whole map: zero terrain diffs, but a different look from the snowy-bern
  chapters.
- port-or-town-winter: it has no mountain, peak or river art, and Ch7 has 107 such cells of 440.
  It suits a town-street map, not this layout.
