---
id: 268
title: "ch06's boats sit in POCKETS, because a village is a body you cannot walk into and a door you visit it from"
date: "2026-09-03"
section: "Operational Gotchas (durable)"
issues: [26]
---

# ch06's boats sit in POCKETS, because a village is a body you cannot walk into and a door you visit it from

The donor puts two **villages** where our two marooned boats sit. ch06's first pass repainted all
eighteen footprint cells walkable FOREST, so each hull was open on four sides, and declared the
sixteen extra cells as terrain divergences. That was backwards. A village in FE8 *is* a pocket: an
impassable body (`TILE_2E`) plus one door you interact with it from. Honouring the donor gives us
the shape for free — and, measured against the real Ch6, it is the shape the chapter needs.

**It cost no repainting.** A metatile carries its art (the TSA entries) and its meaning (the
terrain byte) independently, and the twelve metatiles involved are used *nowhere else*: all twelve
are `TERRAIN_NONE` in snowy-bern, i.e. our own slots in the range the ice tileset was built to
occupy. ch04, the only other map on snowy-bern, uses none of them; ch03 uses four of the indices
but on `cave-interior`, where the index means a different metatile. So the change is twelve bytes
in `snowy-bern-ice.bin` — `.4bpp` and `.gbapal` byte-identical, `.mar` untouched, the painted
ice-outcrop art pixel-for-pixel the same. `map_tileset_tool.py set-terrain` does it and prints the
blast radius first, because a terrain byte is SHARED and the map you had in mind is not the only
one riding the tileset.

`terrain_divergence` fell from **21 declared cells to 7** — the map moved closer to its donor by
doing less to it, which is the direction that block should always travel.

**The flier keeps her privilege, and that is vanilla's rule, not ours.** `TILE_2E` costs 1 to
`FlyNormal` and is impassable to every ground class. So Pinky can work a hull from four cells
where everyone else has one. Sealing her out would have needed `SNAG`/`WALL`/`VALLEY` — and would
have been *stricter than FE8*, in the one chapter whose whole lesson is "send a flier".

**What terrain cannot do is stop a ranged weapon.** FE8 has no line of sight: a javelin, bow or
tome reaches any tile in range through any wall. A pocket therefore shapes *melee* only, and
keeping range-2 units off a hull is a placement decision, permanently. This is why ch06's two
pursuers are deliberately different problems — the range-1 ice-crab is answered by standing in the
door, the range-1-2 javelin thrower has to be killed.
