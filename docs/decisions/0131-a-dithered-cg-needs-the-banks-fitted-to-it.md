---
id: 131
title: "A dithered CG needs the banks FITTED to it, not tiles that already agree (`bg_to_fe8.py`)"
date: "2026-08-09"
section: "Art & Audio"
issues: []
---

# A dithered CG needs the banks FITTED to it, not tiles that already agree (`bg_to_fe8.py`)

The original converter only ever *packed*: it quantised globally, then put two tiles in one bank when
one tile's colour SET nested inside the other's. That reproduces a clean low-colour source **exactly**
(the Zeldacrafter Targos snow-town: 15 colours, 1 bank), and it cannot convert a photo-derived CG at
all. A dithered source checkerboards two shades pixel-by-pixel, so a single 8×8 tile of dusk sky holds
16–18 colours that no other tile matches: the Fenriel winter CGs needed 265–377 banks, and squeezing
`--colors` down until they packed left **15 colours in 1 bank — 7 of FE8's 8 thrown away**.
- So `bank_cluster` fits 8 palettes of 15 to the picture: seed by tile mean colour (farthest-point,
  deterministic), then alternate *requantise each bank from its assigned tiles' pixels* / *reassign each
  tile to the bank that reproduces it with least error*. Both steps only lower error, so it converges.
- **8 is the engine's budget for a plain `BACG`, and only that:** `eventscr.c` loads one with
  `ApplyPalettes(pal, 8, 8)` + a `0x8000` TSA base, i.e. banks 0–7 → hardware palettes 8–15.
  **The FADE/TRANSITION path applies only 6** — `sub_800EC50` / `sub_800ED50`
  (`ConvoBackgroundFadeProc`) call `ApplyPalettes(pal, 0, 6)` / `(pal, 8, 6)`. An 8-bank BG shown
  through those loses banks 6–7 and renders garbage in whatever they cover, and nothing in the
  build catches it. So a BG destined for a transition/fade-in subcode is converted
  **`--banks 6`**; `--banks` is validated 1..8 for that reason (`bg_to_fe8.py` refuses more, since
  no path can load them). Ch01's ending is a plain `BACG` + `FADU`, hence 8. **Bremen is banked at
  8: ch07 must either show it with a plain `BACG` or reconvert it at 6.**
- **The packing path is kept and tried first**, so every already-shipped BG still converts
  byte-identically (asserted on `bg_TargosWinter.png`); clustering is lossy and only the fallback.
- **A bank no tile chose is compacted away**, so the reported bank count is the count actually
  used — an emptied bank is re-seeded from the whole image and rarely wins a tile back, which
  would otherwise reproduce the wasted-budget failure the function exists to fix while printing 8.
- **Bank palettes are snapped back to the 5-bit grid.** MEDIANCUT returns cluster AVERAGES, which
  land off-grid even when every input pixel was on it; gbagfx then truncates the low 3 bits, so an
  unrounded palette ships colours the tool never chose its indices for.
- Squared distances are computed in **int32**. In int16 a channel delta squares to 65025, wraps
  negative, and `argmin` then picks the **worst** bank — which renders as bright blotches in dark
  regions. Caught by looking at the output, exactly as the index-0 gotcha above was.
First use: Bryn Shander's ch01 ending + Bremen's reserved ch07 slot, both 8 banks / 120 colours,
verified in-engine on the `recordending` cutscene.
_Decided: 2026-08-09_
