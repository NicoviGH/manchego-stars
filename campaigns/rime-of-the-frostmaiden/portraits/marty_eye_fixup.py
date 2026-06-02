#!/usr/bin/env python3
"""Marty's eyes (~2px) and mouth are below what the crisp downscale renders
consistently (eyes came out asymmetric, the mouth picked up cream specks). This
deterministic touch-up authors the face to match the Marty 3 ref: two matching
tall eyes (2-wide WHITE catchlight on top, dark body) and a wide shallow smile.
It also frees a clean-white palette slot by remapping a redundant face-grey.

Re-apply after re-rendering:
  ref_to_bust.py "Marty 3.png" marty.png --crop 0,35,2222,1887 --downscale crisp
  python3 marty_eye_fixup.py marty.png
"""
import sys
import numpy as np
from PIL import Image

p = sys.argv[1] if len(sys.argv) > 1 else "marty.png"
im = Image.open(p)
idx = np.asarray(im).copy()
pal = np.array(im.getpalette()).reshape(-1, 3)
FACE, DARK, CREAM = 1, 15, 13
GREYS = {4, 5, 6, 10}

# free a clean-WHITE slot: indices 1/3/7/11 are near-identical face greys, so
# remap 3 -> 1 (no visual change) and redefine 3 as white for the eye catchlights.
idx[idx == 3] = 1
WHITE = 3
pal[WHITE] = (236, 240, 243)

# clear the crisp render's messy eyes/mouth/specks in the face band
for y in range(42, 51):
    for x in range(40, 57):
        if idx[y, x] in ({DARK, CREAM} | GREYS):
            idx[y, x] = FACE


def _eye(x):                          # 2-wide white catchlight, dark body below
    idx[43, x] = WHITE; idx[43, x + 1] = WHITE
    idx[44, x] = DARK;  idx[44, x + 1] = DARK
    idx[45, x] = DARK;  idx[45, x + 1] = DARK
    idx[46, x] = DARK


_eye(43)
_eye(52)

for (x, y) in [(43, 47), (44, 48), (45, 48), (46, 49), (47, 49), (48, 49),
               (49, 49), (50, 49), (51, 48), (52, 48), (53, 47)]:   # wide shallow smile
    idx[y, x] = DARK

out = Image.new('P', im.size)
out.putpalette(pal.flatten().tolist())
out.putdata(idx.flatten().tolist())
out.save(p)
out.convert('RGB').resize((288, 240), Image.NEAREST).save(p.replace('.png', '_preview.png'))
print("applied Marty face touch-up to", p)
