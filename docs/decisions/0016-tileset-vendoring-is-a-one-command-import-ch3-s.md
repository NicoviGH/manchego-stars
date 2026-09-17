---
id: 16
title: "Tileset vendoring is a one-command import; Ch3's cave tileset is `cave-interior` (#40)."
date: "2026-07-02"
section: "Engine & Tech Stack"
issues: [40]
---

# Tileset vendoring is a one-command import; Ch3's cave tileset is `cave-interior` (#40).

FEBuilder/FE-Repo tilesets need NO toolchain (no grit / Map Hacking Suite): the
`.mapchip_config` is byte-identical to the decomp tile config (verified twice: Snowy Bern #41,
Cynon's Mineshaft #40) and the 256x256 mode-P object-palette PNG is 4-bit local indices over a
banked 256-color palette, packing straight to `.4bpp` + `.gbapal` (first 10 banks). So
`map_tileset_tool.py import <config> <png> tilesets/<name>` is the whole pipeline, with a
TSA palette-bank guard (rejects banks >= 10 the FE8 map BG palette can't carry). Proof
standard for an import: assemble the asset's own Tiled test map (`render-tmx`) and pin it
against a reviewed render -- `cave-interior` (Cynon's Mineshaft, Gray; CC, cross-engine use
endorsed in its CREDITS) reproduces `docs/demo/ch03-mineshaft-tileset-demo.png` pixel-exact,
gated in `tools/test_map_tileset.py`. Engine seam: `_register_tileset(campaign, name, Stem,
comment)` registers any vendored tileset's asset-table entries (winter now rides it);
`_register_chapter_map(maps_dir, layout, comment)` points a chapter map at whichever registered
tileset the layout's own `.json` `tileset` stamp names (resolved via `TILESET_STEMS` -- no
per-call tileset argument).
Layout JSONs (editor export + compiled `<map>.json`) now stamp their `tileset`, so
`import_map_layout.py` compiles + previews on the right one. The map editor gained the
custom-canvas mode for non-reskin chapters: `gen_map_editor.py --tileset=cave-interior
--blank=WxH [--fill=N] [--ref=<image>]` (the `--ref` pane is for painting against the book's
Gem-Mine blockout, per the Ch3 layout pivot). `cave-interior` itself registers when the ch03
injector lands (#23) -- registering it with no consumer would be dead ROM bytes.
_Decided: 2026-07-02 (CLAUDE; #40 tasks 1-2 -- the "small converter, not a toolchain" call
from the 2026-06-29 session held)_

---
