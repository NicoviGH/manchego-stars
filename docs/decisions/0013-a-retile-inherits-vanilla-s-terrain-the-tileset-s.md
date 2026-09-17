---
id: 13
title: "A retile inherits vanilla's terrain; the tileset's terrain table is ours to author (#25)."
date: "2026-08-07"
section: "Engine & Tech Stack"
issues: [25]
---

# A retile inherits vanilla's terrain; the tileset's terrain table is ours to author (#25).

A chapter that repaints a vanilla layout changes ART ONLY. Every cell keeps the terrain vanilla
gave it, because terrain is what the map MEANS: move cost, avoid, defence, and which menu the
engine offers. When a painted tile carries the wrong role, the fix is to author that metatile's
terrain byte in OUR vendored copy of the tileset -- never to swap the tile, which silently
overrides the map author's eye to chase a data problem. ch05 needed exactly three bytes
(`port-or-town-winter` metatiles 943/976/1010, `WALL` -> `FENCE`).
Enforced by `import_map_layout.validate_terrain_matches_vanilla`, which runs for EVERY tileset
and fails the import naming the cells. Its predecessor `validate_vanilla_retile` only ever ran
for `snowy-bern`, which is how ch05 drifted 11 cells `FENCE` -> `WALL` unnoticed: those two are
identical in every table except `TerrainTable_MovCost_Fly*` (a fence is flyable, a wall is not),
so the map would have quietly walled out Pinky, our only flier -- the ch04 unobtainable-village
failure class exactly. A blank canvas driven from `--vanilla` now stamps `vanilla_layout` so the
check has something to compare against.
_Decided: 2026-08-07 (Nicolas: "we're re-tiling so just copy vanilla's terrains")_
