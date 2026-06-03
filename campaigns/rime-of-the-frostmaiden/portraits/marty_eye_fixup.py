#!/usr/bin/env python3
"""Marty's face is only ~17px tall in the FE8 bust, so the ~20x downscale blurs
his eyes and smile to mush. This deterministic pass redraws them crisp, matching
the MartyFlat ref: two round black eyes with a white catchlight, and a wide gentle
smile. Everything is keyed off the rendered FACE blob (the smooth grey oval below
the gills), so it survives small reframes and re-quantizations -- no hardcoded
pixel coordinates, no hardcoded palette slots.

Reproduce:
  ref_to_bust.py "MartyFlat.png" marty.png --crop 0,35,2222,1887 --zoom 0.74
  python3 marty_eye_fixup.py marty.png
"""
import sys
import numpy as np
from PIL import Image
from collections import deque

p = sys.argv[1] if len(sys.argv) > 1 else "marty.png"
im = Image.open(p)
idx = np.asarray(im).copy()
pal = np.array(im.getpalette()).reshape(-1, 3)[:16].astype(int)


def nearest(rgb, skip0=True):
    d = ((pal - np.array(rgb)) ** 2).sum(1)
    if skip0:
        d[0] = 1 << 30                     # never pick index 0 (transparent)
    return int(d.argmin())


FACE = nearest((190, 194, 189))            # smooth face/gill grey
DARK = nearest((0, 0, 0))                  # darkest slot -> eyes/mouth ink
WHITE = nearest((255, 255, 255))           # brightest slot -> catchlight

# Locate the face: the largest connected blob of FACE-grey is the cheek oval.
m = (idx == FACE)
H, W = m.shape
lab = np.zeros((H, W), int)
n = best = bestn = 0
for sy in range(H):
    for sx in range(W):
        if m[sy, sx] and lab[sy, sx] == 0:
            n += 1
            dq = deque([(sy, sx)])
            lab[sy, sx] = n
            c = 0
            while dq:
                y, x = dq.popleft()
                c += 1
                for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                    ny, nx = y + dy, x + dx
                    if 0 <= ny < H and 0 <= nx < W and m[ny, nx] and lab[ny, nx] == 0:
                        lab[ny, nx] = n
                        dq.append((ny, nx))
            if c > bestn:
                bestn, best = c, n
ys, xs = np.where(lab == best)
cx = int(round(xs.mean()))
top, bot = ys.min(), ys.max()

# Erase the blurry interior: fill each row between its outermost face pixels back
# to flat FACE grey (closes the dark eye/mouth speckle; leaves the outline alone).
for y in range(top, bot + 1):
    rx = xs[ys == y]
    if len(rx):
        idx[y, rx.min():rx.max() + 1] = FACE


def eye(x0, y0):                           # 3x4 round eye, white catchlight up-left
    idx[y0, x0 + 1] = DARK
    idx[y0 + 1, x0] = DARK; idx[y0 + 1, x0 + 1] = WHITE; idx[y0 + 1, x0 + 2] = DARK
    idx[y0 + 2, x0] = DARK; idx[y0 + 2, x0 + 1] = DARK;  idx[y0 + 2, x0 + 2] = DARK
    idx[y0 + 3, x0 + 1] = DARK


# Eye centres sit ~6px either side of face centre (measured from the ref's own
# downscale: dark clusters at cx-6 and cx+6, ~12px apart) and high on the face.
eye(cx - 7, top + 3)                       # left eye  (3px wide, centre cx-6)
eye(cx + 5, top + 3)                       # right eye (centre cx+6)

# Wide gentle smile: small upturned corners, then a long flat bottom -- sitting
# high (rows top+9..top+11) so it reads close under the eyes, per the ref.
for (dx, dy) in [(-5, 9), (5, 9),                          # upturned corners
                 (-4, 10), (4, 10),
                 (-3, 11), (-2, 11), (-1, 11), (0, 11), (1, 11), (2, 11), (3, 11)]:  # flat
    idx[top + dy, cx + dx] = DARK

out = Image.new('P', im.size)
out.putpalette(pal.flatten().tolist() + [0] * (768 - 48))
out.putdata(idx.flatten().tolist())
out.save(p)
out.convert('RGB').resize((W * 3, H * 3), Image.NEAREST).save(p.replace('.png', '_preview.png'))
print("redrew Marty's face on", p)
