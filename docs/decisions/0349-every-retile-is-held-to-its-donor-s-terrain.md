---
id: 349
title: "Every retile is held to its donor's terrain on every run, flips included"
date: "2026-10-15"
section: "Engine & Tech Stack"
issues: [495]
---

# Every retile is held to its donor's terrain on every run, flips included

Nicolas, 2026-10-15: a retile "should function identically to its donor map. We just reskinned
it." ADR 0013 said so, but its check ran only when a map was imported. Measured against the
donors, three committed maps had drifted: ch03 on 167 cells, ch02 on 2, ch01 on 13.

**The guard.** `test_map_tileset.EveryRetilePlaysLikeItsDonor` compares every hosted chapter's
compiled map with its donor, cell by cell, allowing only the cells its YAML lists under
`terrain_divergence`. The donor is derived from geometry (`map_donor`). `map.vanilla_layout` is
not required, because declaring it also turns on the donor's shops and gift placement; where a
chapter does declare it, it must name the derived layout. ch01 declares its 13 cells: vanilla
Ch1's seize gate (ADR 0078) and its two hint Houses, which Ch13EirikaMap has no place for.

**The fix is a tool.** `map_tileset_tool restore-terrain <stem> <donor>` re-tags a metatile
that only ever sits on one donor terrain. A metatile painted across several roles keeps the
majority role, and each other role gets a clone: the same four quarters composed into a free
slot with that terrain byte. The art stays pixel-identical; ch03's render differs from before
only at its three cracked walls. ch03's 32 water cells play as WALL again (fliers crossed them
as SEA), and its boss stands on THRONE, not MOUNTAIN.

**Flips play like the donor's too.** Borgo's three cracked walls are WALL_DAMAGED again, drawn
with the tileset's own cracked art. Each breaks into ROAD through a 1x1 MapChange
(`inject.terrain.cracked_wall_changes`). Its HP is the twin's: `apply_chapter_wall_hp` writes each
hosted chapter's twin `mapCrackedWallHeath` into its host slot, so ch03's walls take vanilla
Ch3's 25, not slot 4's 50. A ch03 door opens onto the terrain vanilla's opened door has
(`vanilla_map_change_terrain`), drawn like the tile below it, or the tile above when the cell
below plays differently; (10,5) sits over the stairs, and vanilla opens it onto FLOOR.
`Ch03FlipsPlayLikeVanillaCh3` holds every flip to vanilla Ch3's array.

**ch02's northern huts are villages again.** Pillage AI targets VILLAGE_REGULAR
(`AiLocationIsPillageTarget`), and our ruins were RUINS_REGULAR, so the raid had two fewer
targets than vanilla's. Raiders loot a village through its `Village()` tile event, so both
huts are fully wired: Location entries, flags 11 and 12, and sacked/visited changes. While they
were ruins their gifts had been parked on the field chwinga as survival charms (ADR 0051). They
are back on vanilla's tiles: (4,2) gives the Hand Axe that stands in for the Red Gem (ADR 0052),
and (7,2) the Elixir. The two field chwinga each give a Vulnerary instead (Nicolas, 2026-10-15),
so the gift set stays vanilla's.
