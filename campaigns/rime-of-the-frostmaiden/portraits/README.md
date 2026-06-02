# Portraits

Authored FE8 talking-portrait busts, one `<unit>.png` per cast/recruit.

- **Format:** 96×80 indexed PNG, ≤16 colors, palette index 0 = transparent.
- **`<unit>_preview.png`:** 3× nearest-neighbour preview (human-viewable; derived, not used by the build).
- **Source art:** Nano Banana / Gemini references in the project References folder
  (see [[feedback_nicolas_not_an_artist]] in memory for the art workflow).

## Pipeline

1. `tools/ref_to_bust.py <ref.png> <unit>.png --crop x0,y0,x1,y1 --preview <unit>_preview.png`
   — translate a clean reference (flat background, head-and-shoulders) into the 96×80 indexed bust.
2. `tools/portrait_tool.py encode <unit>.png <sheet>.png`
   — pack the bust into the decomp's 256×32 tile sheet (the `gSprite_Face96x96` OAM layout);
   `decode` reverses it. Verified byte-identical round-trip on vanilla portraits.
3. The sheet + palette + mouth/chibi go into `fireemblem8u/graphics/portrait/`, then `gbagfx` → ROM
   (wiring a portrait onto a unit is the build-campaign pipeline, issues #13–15).

`braulo.png` is the first converted portrait (from `Broulo Face Clean.png`). Eyes/snarl
(berserker-fury per the unit's `art:` brief) can be refined with a manual pixel pass.

## Per-portrait hand passes

Small features blur below the bust's downscale, so some units get a deterministic
companion script (run after `ref_to_bust.py`, reproduce command in each docstring):

- `marty_eye_fixup.py` — hybrid: smooth body + hand-drawn 3×5 eyes and a flat smile
  (Marty's face is ~20px, below what any downscale renders cleanly).
- `rootis_cleanup.py` — faithful Bust 1 + pixel touch-ups: clean continuous coal
  silhouette outline, a faceted carrot nose (highlight ridge / dark facet / maroon
  tip), and removal of the purple anti-alias halo ringing the coal mouth dots.
