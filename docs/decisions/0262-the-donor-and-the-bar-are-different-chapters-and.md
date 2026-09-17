---
id: 262
title: "The DONOR and the BAR are different chapters, and ch06 makes that explicit"
date: "2026-08-28"
section: "Operational Gotchas (durable)"
issues: [26]
---

# The DONOR and the BAR are different chapters, and ch06 makes that explicit

ch06 paints **Ch13EphraimMap** and measures against **FE8 Ch6**. Approved by Nicolas.

- **Why that layout.** Three candidates sit inside the learned-reskin family (all `TileConfiguration1`,
  so all inherit the 50 hand-taught winter mappings). `Ch6Map` 29x20 has **zero** water. `MelkaenCoastMap`
  20x30 has 128 `TERRAIN_SEA` along two edges -- a coastline. `Ch13EphraimMap` 22x22 has **137
  `TERRAIN_RIVER` in concentric channels**: the only one whose water is a *route* rather than a border,
  which is the whole chapter (navigating ice floes inward to the monster).
- **Why the roster does not come with it.** Ch13Eph fields 58 enemies at avg L11.5 (20 Cavaliers,
  10 Pegasus Knights); Ch6 fields 24 at avg L6.2. Levels live in the roster we author, not in the tiles.
  ch01 already ships this split -- Hamill Canyon geometry, `parity_reference: "FE8 Ch1"`.
- ⚠️ **The seed had it wrong twice over**: it claimed `FE8 Ch5` for BOTH fields, which is ch05's own bar.
- **Movement is what makes the maze real** (`src/data_terrains.s`): `TERRAIN_RIVER` is impassable to foot,
  armour AND horse; cost 2 to Pirate, 1 to flier. So on our roster the maze elevates **Braulo** (Pirate)
  and **Pinky** (Pegasus) -- not the cavalry Ch13Eph was authored around. Copying its class bones would
  import a solution to *Ephraim's* roster problem.
- **`TERRAIN_GLACIER` shapes nothing** -- cost 1 for every class including armour. Permanent ridges are
  `TERRAIN_PEAK`; the destructible floes are `TERRAIN_SNAG` (impassable to all, fliers included). The seed
  said glacier; corrected in the same commit.
- **Tileset is `snowy-fields`** -- vendored, previously used by nothing, and its 48 RIVER metatiles are
  drawn as cracked ice channels (plus LAKE 18 / SEA 26 / SNAG 2). The seed named `water-boats`, which was
  never vendored at all.
- **Mode is a level shift, not a different force.** `chapter_settings` carries `easyMalus 4 / normalMalus 2
  / difficultBonus 3` for both chapters, and `difficulty.vanilla_chapter_shifts` reads it. Vanilla Ch6's
  own hard-mode delta is **+3 Cavaliers on turn 4** and nothing else -- a model worth copying for ch06's
  `difficulty:` block.

_Board: `https://claude.ai/code/artifact/6952f53d-0fde-4a0f-b07c-b8fc846d6f10`. Checklist: issue #26._
