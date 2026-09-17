---
id: 117
title: "Battle-anim ground platforms: vendored snow/ice (FE-Repo, not stone)"
date: "2026-06-23"
section: "Art & Audio"
issues: []
---

# Battle-anim ground platforms: vendored snow/ice (FE-Repo, not stone)

FE8's battle "platform" (the ground combatants stand on) is terrain-driven (`gBanimFloorfx` →
`battle_terrain_table[]`); vanilla has **no snow platform** (the pale `siroyuka1` is a stone floor).
So we vendor from the FE-Repo `{Cynon} Battle Platforms` pack (F2E, **credit Cynon** in `CREDITS.md`),
256×32 = drop-in for the vanilla format. Per-chapter picks, book-grounded (twilight palettes for the
Everlasting Rime, never the bright "Light" daylight unless chosen):
- **Prologue (the Eastway caravan road, windswept tundra)** → `Snowdrift`, palette cooled ~20% for twilight.
- **Ch1 (the Iron Trail, rocky mountain pass)** → `Snow Uneven Ground` (**Light** — Nicolas's pick 2026-06-23; Night/Medium read too dark/blue).
- **Frozen-water beats** (Lac Dinneshere etc.) → back-pocket `Ice Flat` / `Ice FE6 Magically Frozen Lake`.
**Done (2026-06-23):** `inject_battle_platforms` vendors the three platforms into new
`battle_terrain_table` slots (115–117), remaps `BanimTerrainGroundDefault` to snow-OPEN
(plains→Snowdrift, rough→Uneven, water→Ice) for the prologue/sandbox (`battleTileSet 0`), and
adds a snow-ROUGH `BanimTerrainGround_Tileset15` (open ground→Uneven) that **Ch1 (idx 2)** is
pointed at via `chapter_settings.json`. Resolves per-tile, no force. Verified in-engine: RBG
fires in real Ch1 on the Uneven ground unforced. RBG's faked battle anim keeps its **current
scale** (the ~0.92× shrink was previewed and declined). Future snow chapters: set their
`battleTileSet` to 0 (open) or 0x15 (rough) per scenery.
_Decided: 2026-06-23_
