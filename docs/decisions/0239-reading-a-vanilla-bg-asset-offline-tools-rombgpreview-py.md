---
id: 239
title: "Reading a vanilla BG asset offline: `tools/rom_bg_preview.py`, and TSA is not always LZ77"
date: "2026-08-12"
section: "Operational Gotchas (durable)"
issues: [265]
---

# Reading a vanilla BG asset offline: `tools/rom_bg_preview.py`, and TSA is not always LZ77

Every backdrop we recolour is a plain `.incbin` from `baserom.gba` at a fixed offset, so the
exact pixels the GBA would draw can be reproduced in milliseconds with no build and no emulator.
`rom_bg_preview.py` does that, and its `--index-map` / `--isolate` answer the question a palette
edit must answer first: *which index owns this thing, and does anything else share it?* Use it
before touching a palette; spend the one in-engine run confirming the answer, not finding it.

Two traps it encodes, both settled from the decomp rather than by guessing:

- **The TSA palette nibble is RELATIVE** (0..3), not the hardware bank. The engine chooses where
  the four banks land — `gPaletteBuffer + 0x60` → banks 6..9 for the combat backdrop,
  `ApplyPalettes(..., 0xC, 4)` → banks 12..15 for the exterior. Index with the relative value,
  report with the hardware one.
- **Not every TSA is compressed.** `CallARM_FillTileRect` takes a raw blob, and `TmApplyTsa`
  (`asm/arm.s`) settles its shape: the loops are INCLUSIVE (the stored bytes are width-1 and
  height-1) and it fills BOTTOM-TO-TOP, so the TSA's first row is the screen's last. Getting
  that wrong renders a sheared picture that looks like a decode bug in the image data.
_Decided: 2026-08-12 (Claude, #265)._
