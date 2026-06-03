#!/usr/bin/env python3
"""Brie bust touch-up (faithful to "Pixel Brie.png", like Pinky/Rootis/Marty).

The smooth downscale frames the whole cannon-golem well (fuse, full barrel + bore, glam
eye, grin, treads), but Brie's two CYAN features can't survive the ~22x downscale + 16-
colour quantization: the hot-pink body floods the chroma-reservation slots, so both the
teal eyeshadow ringing her glam eye AND the cyan star decal quantize onto a muddy grey-
purple slot (idx6, ~138,122,147) and read grey, not cyan. CRUCIALLY that same grey slot
is ALSO the grey metal of her tank treads, so we cannot just re-saturate idx6 — that would
turn the treads teal (and snapping idx6 strays away would gut the treads). Instead we free
a NEW slot for teal and recolour only the eyeshadow/star pixels, leaving idx6 = tread grey.

This deterministic, colour-keyed pass restores them and nothing else:

  1. FREE A SLOT. idx2 and idx4 are near-identical cream anti-alias specks (<3 RGB apart,
     a handful of pixels each); merge idx4 into idx2 — invisible — to free one slot. With
     the one already-unused slot that gives two: one teal, one cyan.

  2. CYAN EYESHADOW. idx6 forms the eyeshadow arc wrapping the eye; inside a scoped eye box
     we repaint those idx6 pixels to a true teal in the freed slot. (Purple iris + white
     catchlight are separate slots; the treads, also idx6 but far below the box, stay grey.)

  3. CYAN STAR pops. The star is also idx6, spatially separate (upper body, right of the
     eye). Inside a scoped star box we repaint it to a BRIGHTER cyan, so it reads as a vivid
     accent — matching the ref.

16 colours preserved throughout (FE8 cap). Brie used 15; slot 3 was unused and slot 4 is
freed by the cream merge.

Reproduce:
  ref_to_bust.py "Pixel Brie.png" brie.png --crop 20,40,2150,1800   (smooth, default)
  python3 brie_cleanup.py brie.png
"""
import sys
import numpy as np
from PIL import Image

p = sys.argv[1] if len(sys.argv) > 1 else "brie.png"
im = Image.open(p)
idx = np.asarray(im).copy()
pal = np.array(im.getpalette()[:48]).reshape(-1, 3).astype(int)
H, W = idx.shape


def slot(rgb):
    return int(np.sqrt(((pal[:16] - np.array(rgb)) ** 2).sum(1)).argmin())


# Boxes located from the index map (row0,row1,col0,col1).
EYESHADOW = (9, 34, 13, 33)       # teal arc wrapping the glam eye
STAR = (5, 15, 39, 50)            # cyan star decal, right of the eye

GREY = slot((138, 122, 147))      # idx6: desaturated teal AND the tread metal grey

# ── 1. Free a slot by merging the near-identical cream specks ────────────────
CREAM = slot((234, 219, 186))     # idx2
DUP = slot((232, 218, 185))       # idx4 — within ~2 RGB of idx2, a couple of pixels
assert DUP != CREAM and np.sqrt(((pal[DUP] - pal[CREAM]) ** 2).sum()) < 9, "cream merge guard"
idx[idx == DUP] = CREAM           # invisible merge -> DUP slot is now free
used = set(idx.flatten().tolist())
free = [i for i in range(1, 16) if i not in used]
assert len(free) >= 2, f"need 2 free slots, found {free}"
TEAL, STAR_CYAN = free[:2]
pal[TEAL] = (66, 184, 196)        # ref eyeshadow teal ~58,182,196
pal[STAR_CYAN] = (96, 214, 230)   # brighter than the eyeshadow so the star reads as an accent

# ── 2. Cyan eyeshadow (scoped to the eye box; treads far below stay idx6 grey) ─
y0, y1, x0, x1 = EYESHADOW
box = idx[y0:y1, x0:x1]
box[box == GREY] = TEAL
idx[y0:y1, x0:x1] = box

# ── 3. Pop the star with a brighter cyan (scoped to the star box) ─────────────
y0, y1, x0, x1 = STAR
box = idx[y0:y1, x0:x1]
box[box == GREY] = STAR_CYAN
idx[y0:y1, x0:x1] = box

out = Image.fromarray(idx)
out.putpalette(pal.flatten().tolist())
out.save(p)
n_used = len(set(idx.flatten().tolist()))
print(f"{p}: cyan eyeshadow + star pop ({n_used} colours; "
      f"eyeshadow={TEAL} star={STAR_CYAN})")
