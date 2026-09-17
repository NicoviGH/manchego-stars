---
id: 130
title: "Event backgrounds (`BACG`): vendored winter CGs, injected as NEW `gConvoBackgroundData` slots"
date: "2026-06-25"
section: "Art & Audio"
issues: []
---

# Event backgrounds (`BACG`): vendored winter CGs, injected as NEW `gConvoBackgroundData` slots

Cutscene backdrops are `gConvoBackgroundData[]` (eventscr2.c) `{tiles, map, palette}` triples, 240×160,
4bpp with up to **8 sixteen-colour sub-palettes** (one per 8×8 tile = 128 colours). We vendor winter
backdrops from the FE-Repo (the Icewind Dale set is rich)
and add each as an **additive new slot** past `BG_BLANK` (0x35) — never reskin a vanilla entry.
- **Pipeline:** `tools/bg_to_fe8.py` (any image → 240×160, GBA-5bit, tile-banked mode-P PNG; greedy
  ≤8-bank pack, falling back to an 8-bank refit for dithered CGs — see the entry below) → `inject_backgrounds` copies it to `graphics/bg/`, appends the enum id (backgrounds.h),
  extern decls (bg.h), table row (eventscr2.c) and incbin symbols (data_bg.s); make's generic
  gbagfx/FETSATOOL rules build the bins. The 4 patched files are in `PATCHED_DECOMP_FILES`.
- **Gotcha — index 0 is transparent.** GBA BG colour index 0 shows the backdrop (FE8 sets it black),
  so a converter that uses local index 0 for a real colour renders **black holes** wherever that colour
  appears (caught in-engine on the ch02 Targos BG: the bright sky/snow speckled black). `bg_to_fe8.py`
  reserves index 0 (colours start at local 1; ≤15 usable per bank). A flat-quant *preview* won't show
  this — only the real GBA render does, so **verify event BGs in-engine**, not by reconstructing the PNG.
- **Slots: appended PAST the sentinel, so there is no ceiling.** Campaign BGs start at **0x38**, after
  vanilla's last enum `BG_RANDOM` (0x37) — relocating BG_RANDOM to free 0x36 would have capped us at one
  extra BG. The two pre-0x38 indices get placeholder table rows so the table stays index==enum contiguous
  (`eventscr.c` short-circuits on `bgIndex == BG_RANDOM` before any lookup, so it never reads its row).
  First use: ch02 Targos ending (Zeldacrafter snow-town).
_Decided: 2026-06-25_
