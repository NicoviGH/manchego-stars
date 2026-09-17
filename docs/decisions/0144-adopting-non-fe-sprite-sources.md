---
id: 144
title: "Adopting non-FE sprite sources (Basil/Oddish)"
date: "2026-07-16"
section: "Art & Audio"
issues: []
---

# Adopting non-FE sprite sources (Basil/Oddish)

Basil's whole kit (portrait, SMS+MU map sprites, battle-anim frames) adopts **Oddish** sprite art
instead of generating or hand-drawing — Nicolas's call: prefer existing pixel art over generation
when a source fits. What the next adoption should know:
- **PMD SpriteCollab** (`github.com/PMDCollab/SpriteCollab`, `sprite/<dex>`) is the goldmine: official
  CHUNSOFT *Explorers of Sky* sheets with **8 directions × full action set** (Idle/Walk/Charge/Shoot/
  Attack/Hurt…). Mainline games only ever drew front/back — PMD is the only source of the **side-facing**
  poses FE8 battle anims need, and its **W row natively faces left** (FE8 player side; Marty faces left).
  Its `*-Shadow.png` sheets mark the ground: **align multi-sheet frames by shadow centroid**, not content
  bbox (poses lean; the ground line doesn't). Per-file `credits.txt` → `CREDITS.md`.
- **Pixel-art rescale without generation:** ffmpeg ships `hqx`/`xbr`/`super2xsai` filters (no new
  tooling). Integer hqx only — for 1.5x do `hqx=3` then an exact half downscale. Alpha survives via a
  **black matte for the colors + a separate hqx pass on the binary mask** (black fringe hides in the
  dark outline; magenta mattes leave a visible ring). After ANY resize, threshold alpha at 128 and
  **re-lock every pixel to the source's quantized palette** — LANCZOS + any-alpha indexing leaves ghost
  pixels that read as a halo/outline (caught by Nicolas on the first portrait pass).
- **Portrait dead zone:** the 96×80 bust's top 48 rows only draw x=16..80 (`gSprite_Face96x96` OAM
  layout), so wide-topped busts are capped by that 64px channel — descale/position to fit and prove it
  with `portrait_tool.py preview` (draw the red-hatch dead-zone overlay when showing candidates).
  `generate` also requires a **full 16-entry PNG palette** — Pillow writes truncated palettes; pad to 16.
- **Native-size adoption beats rescaling on map sprites:** PMD Oddish frames (14-20px) drop straight
  into the **16×32 tall SMS class** — but the wait-table donor must match the sheet's **frame count**:
  most 16×32 rows are 2-frame; the 3-frame 16×32 donors are the monster rows (we use **Cyclops**,
  the `donor_sms_geometry` docstring example). `map_sprite_swapper.py` grew `--idle-frame-h 32` for
  16×32 idle sheets (Trex's 16×16 default untouched).
- **Pending for the ch05 recruit wiring (#25):** Basil's `battle_anim:` block stays undeclared until
  `BANIM_DONORS` grows a **`priest` staff/heal donor** (he heals — shaman/dark is the wrong clone) —
  frames + recipe live in `battle_anims/basil/` + `npcs/basil.yaml` meanwhile.
_Decided: 2026-07-16_
