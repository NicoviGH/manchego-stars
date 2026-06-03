# Portraits

Authored FE8 talking-portrait busts, one `<unit>.png` per cast/recruit.

- **Format:** 96×80 indexed PNG, ≤16 colors, palette index 0 = transparent.
- **`<unit>_preview.png`:** 3× nearest-neighbour preview (human-viewable; derived, not used by the build).
- **Source art:** flat cel-shaded Gemini/Nano-Banana references in the project References folder
  (see [[feedback_nicolas_not_an_artist]] and [[feedback_custom_art_lever]] in memory).
- **Reproducible:** each bust byte-regenerates from its unit YAML `art.render:` block (ref/crop/zoom).

## Pipeline

1. `tools/ref_to_bust.py <ref.png> <unit>.png --crop x0,y0,x1,y1 [--zoom z] [--preview <unit>_preview.png]`
   — crop/zoom a clean reference to a head-and-shoulders bust, segment the flat background,
   area-average downscale to 96×80, then quantize to ≤16 colors with **pngquant** (index 0
   transparent). pngquant holds saturated accents (a blue eye, a cyan star) that PIL's
   median-cut folds into grey, so clean flat refs survive the ~20× reduction natively — no
   per-accent rescue pass needed. Feed it **flatter + bolder + fewer colors**, not "more
   detail" (detail below 96×80 just averages to mush).
2. `tools/portrait_tool.py encode <unit>.png <sheet>.png`
   — pack the bust into the decomp's 256×32 tile sheet (the `gSprite_Face96x96` OAM layout);
   `decode` reverses it. Verified byte-identical round-trip on vanilla portraits.
3. The sheet + palette + mouth/chibi go into `fireemblem8u/graphics/portrait/`, then `gbagfx` → ROM
   (wiring a portrait onto a unit is the build-campaign pipeline, issues #13–15).

## FE8 dead-zone constraint

FE8's talking-portrait OAM never draws the top-left & top-right 16×48 corners (~20% of the
frame). Check any bust and reframe until those corners are clear:

```
tools/portrait_tool.py preview <unit>.png <out>.png   # [authored | what-FE8-draws | clip overlay] + clip count
```

The lever is `--zoom z<1`: it shrinks the subject and adds top headroom (shoulders pinned to
the bottom), pulling tall/wide features (caps, ears, fuses, barrels) down out of the dead
corners. **Descale, never crop a must-keep feature.** Every shipped bust here is at or near
0 px clipped.

## Hand passes

pngquant renders nearly everything natively, so there is exactly one surviving companion
script (run after `ref_to_bust.py`):

- `marty_eye_fixup.py` — Marty's face is only ~17px tall, below what any downscale resolves,
  so this redraws his eyes (round black + white catchlight) and smile crisp. It auto-locates
  the face from the rendered FACE-grey blob and picks palette slots by colour (no hardcoded
  coordinates or palette indices), with eye/mouth positions measured from the ref's own
  downscale. Reproduce command in the docstring.

(The earlier rootis/pinky/pepperjack/brie cleanup passes were palette-budget rescues for the
old PIL quantizer; pngquant keeps those accents natively, so they were removed.)
