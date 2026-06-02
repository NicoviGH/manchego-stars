#!/usr/bin/env python3
"""Marty bust = hybrid: the SMOOTH downscale renders the body (gills/cap/scarf/
tunic/staff) cleanly, but Marty's face is ~20px so the eyes/mouth blur. This
deterministic pass redraws the face to match the Marty 3 ref: clears the blurry
face band, then hand-draws two oval eyes (white catchlight spec INSIDE the black)
and a wide flattish smile. Palette slots are found by colour so it survives small
quantizer changes.

Reproduce:
  ref_to_bust.py "Marty 3.png" marty.png --crop 0,35,2222,1887   (smooth, default)
  python3 marty_eye_fixup.py marty.png
"""
import sys
import numpy as np
from PIL import Image

p = sys.argv[1] if len(sys.argv) > 1 else "marty.png"
im = Image.open(p)
idx = np.asarray(im).copy()
pal = np.array(im.getpalette()).reshape(-1, 3)


def nearest(rgb):
    return int(np.sqrt(((pal[:16].astype(int) - np.array(rgb)) ** 2).sum(1)).argmin())


LIGHT = nearest((190, 194, 189))   # flat face grey
WHITE = nearest((243, 252, 229))   # brightest -> catchlight
DARK = nearest((20, 17, 24))       # black -> eyes/mouth

# clear the blurry face band (forehead+eyes, then mouth) down to flat face grey
for y in range(34, 47):
    for x in range(37, 60):
        if idx[y, x] != LIGHT:
            idx[y, x] = LIGHT
for y in range(43, 51):
    for x in range(41, 56):
        if idx[y, x] != LIGHT:
            idx[y, x] = LIGHT


def _eye(x0):                      # 3x4 oval, white catchlight spec inside upper-centre
    idx[36, x0 + 1] = DARK
    idx[37, x0] = DARK; idx[37, x0 + 1] = WHITE; idx[37, x0 + 2] = DARK
    idx[38, x0] = DARK; idx[38, x0 + 1] = DARK;  idx[38, x0 + 2] = DARK
    idx[39, x0 + 1] = DARK


_eye(38)
_eye(56)

# wide curved U smile matching the ref: corners high (just under the eyes),
# arms curving down-in to a flat bottom at r47-48. Symmetric about face centre x48.
for (x, y) in [(43, 43), (53, 43), (43, 44), (53, 44), (44, 45), (52, 45),
               (45, 46), (51, 46),
               (46, 47), (47, 47), (48, 47), (49, 47), (50, 47),
               (47, 48), (48, 48), (49, 48)]:
    idx[y, x] = DARK

out = Image.new('P', im.size)
out.putpalette(pal.flatten().tolist())
out.putdata(idx.flatten().tolist())
out.save(p)
out.convert('RGB').resize((288, 240), Image.NEAREST).save(p.replace('.png', '_preview.png'))
print("applied Marty hybrid face redraw to", p)
