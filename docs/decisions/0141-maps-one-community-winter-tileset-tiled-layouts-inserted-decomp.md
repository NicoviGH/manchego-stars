---
id: 141
title: "Maps: one community winter tileset + Tiled layouts, inserted decomp-native"
date: "2026-06-07"
section: "Art & Audio"
issues: []
---

# Maps: one community winter tileset + Tiled layouts, inserted decomp-native

~8 of the 9 MVP maps are snow/ice, so we use **one shared winter tileset** — **Snowy Bern / Snowy Peaks** (FEU t/7204: snow ground, frozen buildings, walls, ice/water, forest, temple, mountains) — and author each chapter's layout in **Tiled**. Insertion is **decomp-native**: a GBAFE map is 4 pieces wired through `gChapterDataAssetTable` (`data/data_8B363C.s`) and incbinned in `data/const_data_chapter_maps.s` — tile graphics (`.4bpp.lz`), palette (`.gbapal`, raw), tile config/terrain (`.bin.lz` = 8192 B TSA + 1024 B terrain), layout (`graphics/map/layout/*.bin.lz`). A chapter's `src/data/chapter_settings.json` holds **u8 indices** into the asset table per piece (jsonproc regenerates `chapter_settings.h` each build). Layout `.bin` = `width, height` then `w·h` LE u16, each = **metatile_index × 4**; source path is `.mar`+`.json` → `scripts/mar_to_map.py` → `.bin` → Makefile `%.lz`.

**The tileset did NOT need grit / the Map Hacking Suite:** the community package ships pieces byte-identical to the decomp's (palette = `.gbapal`, mapchip_config = tile-config `.bin`, obj = GBA-LZ `.4bpp`), so it's a straight drop-in. `tools/build_campaign.py:inject_winter_tileset()` copies the pieces in, appends asset-table entries, and points a chapter at them — proven in-engine on the test chapter. **No raw-ROM hex / FEBuilder.** We did NOT palette-swap a temperate tileset and did NOT find ready-made snow town maps (community has tilesets, not finished maps). Tileset asset = #41 (done); pipeline = #40 (register/wire done; Tiled `.tmx`→`.bin` authoring is the open half); both feed per-chapter maps #20–#28. Workflow doc: `campaigns/.../maps/README.md`. Credit authors in `CREDITS.md`.
_Decided: 2026-06-07_
