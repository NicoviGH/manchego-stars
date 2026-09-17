---
id: 55
title: "Ch3 chests + doors ride ONE per-chapter MapChange array; a door opens to the tile below it."
date: "2026-07-11"
section: "Combat System"
issues: [23]
---

# Ch3 chests + doors ride ONE per-chapter MapChange array; a door opens to the tile below it.

FE8 flips a tile on loot/open via a per-chapter `struct MapChange` array (`gChapterDataAssetTable[map.changeLayerId]`):
opening a chest runs `CallChestOpeningEvent(GetMapChangeIdAt(x,y), item)` and opening a door runs
`CallTileChangeEvent(GetMapChangeIdAt(x,y))` — **both look up the change by POSITION** (`GetMapChangeIdAt`
auto-finds the 1×1 region covering the tile), so chests and doors coexist in one array (`MS_Ch03MapChanges`);
ids only need to stay unique. `ApplyMapChangesById` writes `gBmMapBaseTiles[y][x] = tile` for each non-zero
`metatile<<2` word. **The chests** all open to the shared FF5-navy open tile (17→29). **The doors** each open to
the metatile **directly below the door cell** (Nicolas 2026-07-11 — "use the tile directly adjacent and below
it"), read off the painted `.mar` at build time (`_read_map_metatile`) so it tracks any re-retile — no hand-copied
tile numbers. On the committed map that's road/stairs (572/626/492, all passable): vanilla Ch3's `Door_(6,10)`
opens the lower gallery, `Door_(10,5)` the stairs down, `Door_(2,3)` the upper room. Authored as `chests:`/`doors:`
position lists in the ch03 YAML → `Chest()`/`Door_()` in `EventListScr_Ch4_Location[]` + the paired MapChange.
Verified in-engine (`PT_HOST_CHAPTER=4 run.sh ch03door`): hand a unit a Door Key, drive Door, and
`gBmMapBaseTiles[3][2]` flips 3248→1968 (812→492<<2). The chest path shares this array + code path, so the
door proof covers both. `gBmMapBaseTiles` is a ROM-`.data` pointer (objdump `g O ROM` @ 0x085AF5DC) → the
EWRAM `sBmBaseTilesPool` row array, never reassigned — read the pointer from ROM, then index the rows.
_Decided: 2026-07-11 (Nicolas — open-door tile rule; CLAUDE — shared-array wiring, #23 chests/doors)._
