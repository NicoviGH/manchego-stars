---
id: 14
title: "A vanilla layout's tileset is resolved, never inferred from asset-table position (#25)."
date: "2026-08-07"
section: "Engine & Tech Stack"
issues: [25]
---

# A vanilla layout's tileset is resolved, never inferred from asset-table position (#25).

`gChapterDataAssetTable` groups a tileset's `ObjectType`/`MapPalette`/`TileConfiguration` before
the layouts that ride it -- but only usually. FE8 inserts Ch5x at slot 5, so `Ch5Map` sits after
tileset 3's group while riding tileset 2. A backward scan mis-resolves **54 of the vanilla
layouts** (`Ch4Map` and `Ch5Map` among them) and renders correct geometry through the wrong art:
authoritative-looking, and worse than no reference when a retile is being painted against it.
Resolve through `chapter_settings.json` via `map_tileset_tool.vanilla_layout_tileset_assets`.
Why this surfaced only at ch05: every earlier reskin (Prologue/Ch1/Ch2/Ch4) rides tileset 1, and
ch03's `Ch3Map` sits immediately after tileset 2's group, so the scan happened to be right.
_Decided: 2026-08-07 (CLAUDE; found painting ch05, fixed with 4 guard tests)_
