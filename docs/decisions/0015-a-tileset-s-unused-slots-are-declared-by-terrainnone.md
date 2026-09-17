---
id: 15
title: "A tileset's unused slots are declared by `TERRAIN_NONE`, not by a filler colour (#25)."
date: "2026-08-07"
section: "Engine & Tech Stack"
issues: [25]
---

# A tileset's unused slots are declared by `TERRAIN_NONE`, not by a filler colour (#25).

The editor palette filtered unpaintable slots by probing for solid ORANGE, which is one
tileset's convention: `port-or-town-winter` marks its 144 unused slots solid TEAL, so every one
appeared as a brush. Terrain `0x00` is the tileset's own declaration and generalises
(snowy-bern 96, snowy-fields 172, cave-interior 5). Verified no committed map paints one.
_Decided: 2026-08-07 (CLAUDE)_
