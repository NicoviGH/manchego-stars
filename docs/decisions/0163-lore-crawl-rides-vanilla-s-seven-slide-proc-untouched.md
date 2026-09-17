---
id: 163
title: "Lore crawl rides vanilla's seven-slide proc untouched; slides are re-rendered PNGs, gated by `MONTAGE=1`."
date: "2026-06-10"
section: "Story & Dialogue"
issues: []
---

# Lore crawl rides vanilla's seven-slide proc untouched; slides are re-rendered PNGs, gated by `MONTAGE=1`.

The "long ago…" monologue is seven prerendered 4bpp slides (`graphics/op_subtitle/`, `gOpSubtitleGfxLut`), not
message text — `opsubtitle.c` walks them with hardcoded transitions (plain fades 0-1, flare reveal on 2,
cross-blends 3-4, mural close 5-6; START skips). Our crawl was locked at 7 cards to reuse that machinery with zero
proc changes: `tools/gen_subtitle_cards.py` re-renders the slides from `events/opening-montage.yaml` (Georgia 13px
+1px tracking — side-by-side closest to vanilla's serif; quantized into the vanilla 16-color ramp so the warm AA
browns match; ≤220px lines, 24px pitch, block centered on (120,80); slide-display LUT retimed `120+8·words`,
clamped 240-360 frames). Index 0 is GBA-transparent → in-engine the cards read cream-on-black like vanilla, so the
slate PNG background is a converter placeholder only. **Build modes:** default `make` keeps the straight-to-map dev
boot; `MONTAGE=1 make` keeps `StartIntroMonologue` wired and re-renders the slides (distribution #37 must set it).
The controller covers the default straight-to-map build. A `MONTAGE=1` automation must add the subtitle proc's
explicit live skip-input state before pressing START; there is no cadence fallback. `record` captures the crawl
for GIF review. **Backdrop mural:** vanilla composites
the slides over `Img_CommGameBgScreen` (the brown rune wall)
— a SHARED asset (shops, chapter-intro fx, ending details, mural_background), so it is never overwritten; instead
opsubtitle.c is patched to montage-local `Img/Pal_MontageMural` symbols incbin'd in `data_opsubtitle.s`, fed by the
book's ch1 opener painting (aurora over a snow-buried township, `campaigns/.../events/opening-mural.png`; build
derives the 256×160 16-color mural: brightness 0.75, 15 colors + black at GBA-transparent index 0).
_Decided: 2026-06-10; crawl and aurora mural both GIF-reviewed and approved by Nicolas._
