---
id: 236
title: "Reading a VANILLA tileset's art: the committed object sheet is an INVERTED grayscale PNG"
date: "2026-08-10"
section: "Operational Gotchas (durable)"
issues: [24]
---

# Reading a VANILLA tileset's art: the committed object sheet is an INVERTED grayscale PNG

`map_tileset_tool.Tileset` wants `.4bpp` + `.gbapal` + `.bin`. For our vendored tilesets those
three files are the committed source. For a *vanilla* tileset they are build artifacts and are
not in the decomp's HEAD — what is committed is `graphics/map/ObjectTypeN.png`,
`graphics/map/MapPaletteN.pal` and `graphics/map/TileConfigurationN.bin`. Rebuild the other two:

- `ObjectTypeN.png` is 256x256 **mode-L**, and its gray levels are the 4-bit index **inverted** —
  white is index 0, black is index 15, so `index = 15 - (gray // 17)`. Pack it straight and you
  get a picture that looks plausible (coherent shapes, wrong hues) rather than obvious garbage,
  which is exactly how it survives a glance. Rebuild the mode-P form and hand it to
  `convert_object_png`; do not write a second packer.
- `MapPaletteN.pal` is JASC-PAL, 160 colours = the 10 banks x 16 the `.gbapal` holds.
- The chapter's three asset names come from `vanilla_layout_tileset_assets(dec, layout)` — asset
  table proximity is NOT authoritative (that docstring says why). Vanilla Ch4 is
  `ObjectType1 / MapPalette1 / TileConfiguration1`.

**Verify by byte-compare, not by eye**: pack the sheet and assert it equals the decomp's own
built `ObjectTypeN.4bpp`. That check is what caught the inversion; the render alone did not.
An instance of "verify via data, not pixels" pointed the other way — here the DATA is ground
truth for a question that *looks* like an art question.
_Decided: 2026-08-10 (Claude, while surveying the snag family for #24)._
