#!/usr/bin/env python3
"""Rootis bust touch-up (faithful to "Rootis Bust 1", pixel-by-pixel like Marty).
The smooth downscale gives clean whites + coal squares, but three things need a hand
pass to match the ref: (1) the silhouette OUTLINE reads weak/muddy where the ref has a
strong continuous dark line; (2) the carrot NOSE renders as one flat red blob where the
ref is a faceted geometric pyramid (bright highlight ridge, darker right facet, dark
maroon edge/tip); (3) a few stray specks remain around the mouth. This deterministic
pass fixes exactly those and nothing else. Palette slots found by colour.

Reproduce:
  ref_to_bust.py "Rootis Bust 1.png" rootis.png --crop 126,100,1614,1340   (smooth, default)
  python3 rootis_cleanup.py rootis.png
"""
import sys
import numpy as np
from PIL import Image

p = sys.argv[1] if len(sys.argv) > 1 else "rootis.png"
im = Image.open(p)
idx = np.asarray(im).copy()
pal = np.array(im.getpalette()).reshape(-1, 3).astype(int)
H, W = idx.shape
BG = 0


def slot(rgb):
    return int(np.sqrt(((pal[:16] - np.array(rgb)) ** 2).sum(1)).argmin())


COAL = slot((20, 17, 24))
RED = slot((186, 55, 57))

# carrot facet palette (sampled from the ref's faceted pyramid) into free slots
HI, DARK, MAROON = 4, 5, 6
pal[HI] = (236, 152, 150)      # bright pink highlight ridge
pal[DARK] = (138, 34, 42)      # shadowed right facet
pal[MAROON] = (92, 22, 30)     # dark edge + recessed tip


def nb4(src, y, x):
    return [(y + dy, x + dx) for dy, dx in ((-1, 0), (1, 0), (0, -1), (0, 1))
            if 0 <= y + dy < H and 0 <= x + dx < W]


def despeckle():
    """A lone pixel matching none of its 4 neighbours, whose neighbours agree (>=3)
    AND is a strong colour outlier (>70), is noise -> snap to that majority."""
    src = idx.copy()
    for y in range(H):
        for x in range(W):
            nb = [src[a, b] for a, b in nb4(src, y, x)]
            if len(nb) < 3 or src[y, x] in nb:
                continue
            top = max(set(nb), key=nb.count)
            if nb.count(top) >= 3 and np.sqrt(((pal[src[y, x]] - pal[top]) ** 2).sum()) > 70:
                idx[y, x] = top


# (1) despeckle the raw render (carrot speck, stray edge pixels).
despeckle()

# (2) carrot facets. Detect the red mask (filling any enclosed light specks so they
#     join the nose), then paint: outer edge + bottom tip = maroon, a highlight ridge
#     ~40% in from the left, right of the ridge = dark facet.
mask = (idx == RED)
for _ in range(3):                          # absorb light pixels trapped inside the nose
    grow = np.zeros_like(mask)
    for y in range(H):
        for x in range(W):
            if mask[y, x] or idx[y, x] in (BG, COAL):
                continue
            if sum(mask[a, b] for a, b in nb4(idx, y, x)) >= 3:
                grow[y, x] = True
    if not grow.any():
        break
    mask |= grow
ys, xs = np.where(mask)
if len(xs):
    y0, y1 = ys.min(), ys.max()
    rows = {}
    for y in range(y0, y1 + 1):
        rxs = np.where(mask[y])[0]
        if len(rxs):
            rows[y] = (rxs.min(), rxs.max())
    new = {}
    for y, x in zip(ys.tolist(), xs.tolist()):
        lo, hi = rows[y]
        on_edge = any(not (0 <= a < H and 0 <= b < W and mask[a, b]) for a, b in nb4(idx, y, x))
        ridge = lo + int(round(0.40 * (hi - lo)))
        if y >= y1 - 1 or on_edge:          # recessed tip + geometric dark edge
            new[(y, x)] = MAROON
        elif x == ridge and y <= y1 - 3:     # bright lit ridge (fades before the tip)
            new[(y, x)] = HI
        elif x > ridge:                      # shadowed right facet
            new[(y, x)] = DARK
        else:                                # lit left facet keeps the main red
            new[(y, x)] = RED
    for (y, x), v in new.items():
        idx[y, x] = v

# (3) clean continuous dark outline: every body pixel touching the transparent bg snaps
#     to coal, giving the strong unbroken silhouette line the ref has (head + body).
src = idx.copy()
edge = [(y, x) for y in range(H) for x in range(W)
        if src[y, x] != BG and any(src[a, b] == BG for a, b in nb4(src, y, x))]
for y, x in edge:
    idx[y, x] = COAL

# (4) clean the purple anti-alias halo ringing the coal mouth dots (reads as specks).
#     Scoped to the mouth band only (leaves the eye/shadow purple alone). Each purple
#     pixel snaps to its dominant non-purple neighbour; ties break toward the lighter
#     face colour so the dots keep crisp edges instead of blobbing together.
PUR = slot((72, 55, 90))


def lum(i):
    return int(pal[i].sum())


src = idx.copy()
for y in range(49, min(67, H)):
    for x in range(W):
        if src[y, x] != PUR:
            continue
        nb = [src[a, b] for a, b in nb4(src, y, x) if src[a, b] not in (PUR, BG)]
        if nb:
            idx[y, x] = max(set(nb), key=lambda c: (nb.count(c), lum(c)))

# (5) final despeckle on the settled geometry -> clears any last isolated flecks.
despeckle()

out = Image.new('P', im.size)
out.putpalette(pal.flatten().tolist())
out.putdata(idx.flatten().tolist())
out.save(p)
out.convert('RGB').resize((W * 3, H * 3), Image.NEAREST).save(p.replace('.png', '_preview.png'))
print("applied Rootis touch-up (outline + faceted carrot + despeckle) to", p)
