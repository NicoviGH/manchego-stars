#!/usr/bin/env python3
"""Pepperjack bust touch-up (faithful to "Pixel Pepperjack.png", like Pinky/Rootis/Marty).

The smooth downscale frames the whole cannon-golem well (fuse, full barrel + bore, grin,
treads). One small accent needs a hand pass:

  RED STAR pops. The star shares idx13 with the (correctly vivid) chili mustache, but it is
  small and sits on dark gunmetal, so it reads muddy. We give the star its own brighter red
  in a free slot, scoped to a star box, so it stands out without touching the chili.

(An earlier version also tried to re-orange the eye, but the box-scoped recolour caught
stray outline/shadow pixels near the eye and turned them into orange specks, so the eye is
left exactly as ref_to_bust.py renders it.)

16 colours preserved throughout (FE8 cap). Pepperjack used 13, leaving slots 3/4/6 free.

Reproduce:
  ref_to_bust.py "Pixel Pepperjack.png" pepperjack.png --crop 20,60,2130,1818   (smooth, default)
  python3 pepperjack_cleanup.py pepperjack.png
"""
import sys
import numpy as np
from PIL import Image

p = sys.argv[1] if len(sys.argv) > 1 else "pepperjack.png"
im = Image.open(p)
idx = np.asarray(im).copy()
pal = np.array(im.getpalette()[:48]).reshape(-1, 3).astype(int)
H, W = idx.shape


def slot(rgb):
    return int(np.sqrt(((pal[:16] - np.array(rgb)) ** 2).sum(1)).argmin())


# Box located from the index map (row0,row1,col0,col1).
STAR = (8, 16, 37, 51)        # red star decal on the upper body

# Free slot (Pepperjack used 13 colours; 3/4/6 are unused).
used = set(idx.flatten().tolist())
free = [i for i in range(1, 16) if i not in used]
assert free, f"need 1 free slot, found {free}"
STAR_RED = free[0]
pal[STAR_RED] = (216, 44, 38)     # brighter star red (chili keeps idx13)

# ── Pop the red star (scoped to the star box) ────────────────────────────────
RED = slot((175, 33, 29))         # the shared red the star quantized onto
y0, y1, x0, x1 = STAR
box = idx[y0:y1, x0:x1]
box[box == RED] = STAR_RED        # only the star's reds; the chili elsewhere stays idx13
idx[y0:y1, x0:x1] = box

out = Image.fromarray(idx)
out.putpalette(pal.flatten().tolist())
out.save(p)
n_used = len(set(idx.flatten().tolist()))
print(f"{p}: star pop ({n_used} colours; star={STAR_RED})")
