---
id: 338
title: "Our still busts draw their top corners (engine patch 0018)"
date: "2026-10-10"
section: "Art & Audio"
issues: [471]
---

# Our still busts draw their top corners (engine patch 0018)

Vanilla's 96x96 face layout (`gSprite_Face96x96`) leaves out the 16x48 strips at a bust's top
corners, so every custom bust had to keep its hat, ears or snout inside a 64 px channel above
row 48. Nicolas chose the engine patch on 2026-10-09 (#471; motivating case: Messie's mayor
bust, hat plus snout).

**How.**
- A face whose `FaceData.blinkKind` is `FACE_BLINK_STATIC` (new, 7) is a still. Every dressed
  slot gets it (`inject.portraits.patch_portrait_face_data`), because every dressed slot holds
  a `portrait_tool.generate(static_portrait=True)` bust.
- For those faces the talk-scene layout adds four pieces (a 16x32 and a 16x16 per corner)
  from sheet tiles 0x18-0x1B / 0x58-0x5B, which a vanilla face uses for its eye frames, and
  0x5C-0x5F, which nothing reads. `portrait_tool.CORNER_OBJECTS` packs them, and
  `test_engine_patches` pins the two tables together.
- The eye overlay paints nothing for a still face. Otherwise a blink or a close-eyes command
  would draw corner tiles over the eyes.
- The stat, support and world-map screens' 80x72 BG face fills its edge columns from the
  same tiles instead of blanking them.

**What it retires.** The dead-corner guards: `portrait_tool.what_ships` / `clipped_mask` /
`preview`, Messie's re-fit checks, and Sephek's corner-clear pass. Busts framed to dodge the
corners keep their framing until each one is reviewed for a larger scale.

**The rescale review (Nicolas, 2026-10-10).** With the corners drawn, each bust's framing was
measured against vanilla faces, whose tops reach the frame edge. The rule is the same for
every bust: grow it until its top reaches the edge, and stop before a shoulder is chopped
flat at the sides (a bottom-corner exit, as vanilla shoulders make, is fine).
- Rescaled: Baxby, Brie, Pepperjack (the top reaches the edge), Braulo and Wolfram (stopped by
  the shoulders; Wolfram's crop re-centred). The rest keep their framing by choice.
- `ref_to_bust` `zoom` above 1.0 tightens the crop, bottom still pinned.
- `flatten: N` (Braulo, Wolfram) is for a painted ref: an N px median on the source, one
  area-average and no dither. A vanilla face is flat clusters of a few tones per material,
  and the default path's dither turned brushwork into single-pixel speckle.
- Messie's mayor is the ch06 ref with the hat kept (zoom 0.81, the crown at the top edge).
  Two fixes made it: `accents` keeps a colour too small to win a palette slot (his eye,
  outbid by the hat's greys), and a tighter background key stops the flood eating the black
  hat where it meets the frame edge.
