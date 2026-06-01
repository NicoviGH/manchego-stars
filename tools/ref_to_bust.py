#!/usr/bin/env python3
"""Translate a (Nano Banana / Gemini) character reference into a game-ready
96x80 indexed FE8 portrait bust.

Pipeline: crop to a head-and-shoulders bust -> segment the flat background
(sample the border color, key pixels within an RGB distance of it, border-
connected flood seeded from top/left/right since the subject fills the bottom)
-> clean up specks/holes -> sharpen + downscale to
96x80 -> quantize to 15 colors (index 0 reserved transparent) -> erode the
silhouette edge to transparent for a clean cut.

The result drops straight into the insert pipeline:
    tools/portrait_tool.py encode <bust.png> <sheet.png>   ->  decomp -> gbagfx

Usage:
    ref_to_bust.py <ref.png> <out_bust.png> --crop x0,y0,x1,y1 [--preview big.png]

The --crop box is chosen per character (it is reference-specific framing); aim
for a ~96:80 (1.2) aspect: eyestalk/head tips near the top, shoulders at bottom.
"""

import argparse
import numpy as np
from PIL import Image, ImageFilter, ImageEnhance
from collections import deque

BUST_W, BUST_H = 96, 80


def _label(mask):
    H, W = mask.shape
    lab = np.zeros((H, W), int)
    n = 0
    for sy in range(H):
        for sx in range(W):
            if mask[sy, sx] and lab[sy, sx] == 0:
                n += 1
                dq = deque([(sy, sx)])
                lab[sy, sx] = n
                while dq:
                    y, x = dq.popleft()
                    for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                        ny, nx = y + dy, x + dx
                        if 0 <= ny < H and 0 <= nx < W and mask[ny, nx] and lab[ny, nx] == 0:
                            lab[ny, nx] = n
                            dq.append((ny, nx))
    return lab, n


def convert(ref_path, crop_box, bg_thresh=45.0):
    src = Image.open(ref_path).convert('RGB')
    crop = src.crop(crop_box).resize((480, 400), Image.LANCZOS)
    rgb = np.asarray(crop).astype(np.float32)
    H, W = rgb.shape[:2]

    # Sample the flat background color from the top + left/right edges (the
    # subject fills the bottom-center), then key pixels within bg_thresh RGB
    # distance of it. Works for any flat backdrop (cream, grey, ...), not just
    # bright cream. The border-connected flood below keeps any same-colored
    # region enclosed by the subject as foreground.
    edge = np.concatenate([rgb[0:8].reshape(-1, 3),
                           rgb[:, 0:8].reshape(-1, 3),
                           rgb[:, -8:].reshape(-1, 3)])
    bg_color = np.median(edge, axis=0)
    bg = np.sqrt(((rgb - bg_color) ** 2).sum(2)) < bg_thresh

    # border-connected background flood, seeded from top + left + right only
    conn = np.zeros((H, W), bool)
    dq = deque()
    for x in range(W):
        if bg[0, x]:
            conn[0, x] = True
            dq.append((0, x))
    for y in range(H):
        for x in (0, W - 1):
            if bg[y, x]:
                conn[y, x] = True
                dq.append((y, x))
    while dq:
        y, x = dq.popleft()
        for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            ny, nx = y + dy, x + dx
            if 0 <= ny < H and 0 <= nx < W and bg[ny, nx] and not conn[ny, nx]:
                conn[ny, nx] = True
                dq.append((ny, nx))
    fg = ~conn

    # Downscale the FULL-RES crop with area-averaging (BOX to 2x target, then
    # LANCZOS to target), THEN sharpen at the target resolution. Sharpening
    # before the downscale (the old path) blurred small features like eyes into
    # muddy grey halos; area-averaging + a target-res unsharp keeps them crisp.
    hires = src.crop(crop_box)
    img = hires.resize((BUST_W * 2, BUST_H * 2), Image.BOX).resize((BUST_W, BUST_H), Image.LANCZOS)
    img = img.filter(ImageFilter.UnsharpMask(radius=1, percent=170, threshold=1))
    m = np.asarray(Image.fromarray((fg * 255).astype('uint8')).resize((BUST_W, BUST_H), Image.LANCZOS)) > 120

    lab, n = _label(m)
    for i in range(1, n + 1):
        if (lab == i).sum() < 20:
            m[lab == i] = False
    labh, nh = _label(~m)
    for i in range(1, nh + 1):
        comp = (labh == i)
        edge = comp[0].any() or comp[-1].any() or comp[:, 0].any() or comp[:, -1].any()
        if comp.sum() < 30 and not edge:
            m[comp] = True

    # Boost contrast slightly so distinct regions separate into distinct palette
    # entries (low-contrast areas like Marty's face otherwise smear across
    # near-identical greys -> looks blurry). No saturation boost: it tints
    # neutral features (eyes/face) purple/cyan.
    img = ImageEnhance.Contrast(img).enhance(1.15)
    # Quantize only the FOREGROUND: fill the background with the median fg colour
    # first so the flat bg doesn't consume a palette slot, and use MAXCOVERAGE
    # (MEDIANCUT wasted ~6 of the 15 slots on near-duplicate greys, the main
    # cause of the muddy/blurry look).
    arr = np.asarray(img).astype(np.uint8).copy()
    fgpx = arr[m]
    if len(fgpx):
        arr[~m] = np.median(fgpx, axis=0).astype(np.uint8)
    q = Image.fromarray(arr).quantize(colors=15, method=Image.MAXCOVERAGE, dither=Image.NONE)
    qi = np.asarray(q).astype(int)
    pal = q.getpalette()[:15 * 3]
    out = np.where(m, qi + 1, 0)
    # erode silhouette edge -> transparent for a clean cut
    eroded = out.copy()
    for y in range(BUST_H):
        for x in range(BUST_W):
            if m[y, x]:
                for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                    ny, nx = y + dy, x + dx
                    if not (0 <= ny < BUST_H and 0 <= nx < BUST_W) or not m[ny, nx]:
                        eroded[y, x] = 0
                        break

    res = Image.new('P', (BUST_W, BUST_H))
    res.putpalette([0, 255, 0] + pal + [0] * (768 - 3 - len(pal)))
    res.putdata(eroded.flatten().tolist())
    return res


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('ref')
    ap.add_argument('out')
    ap.add_argument('--crop', required=True, help='x0,y0,x1,y1 in ref pixels (~1.2 aspect)')
    ap.add_argument('--bg-thresh', type=float, default=45.0,
                    help='RGB distance from the sampled border color to treat as background (default 45)')
    ap.add_argument('--preview', help='also write a 3x nearest-neighbour preview here')
    a = ap.parse_args()
    box = tuple(int(v) for v in a.crop.split(','))
    res = convert(a.ref, box, a.bg_thresh)
    res.save(a.out)
    print('%s -> %s (96x80 indexed, %d colors)' % (a.ref, a.out, len(set(res.getdata()))))
    if a.preview:
        res.convert('RGB').resize((BUST_W * 3, BUST_H * 3), Image.NEAREST).save(a.preview)
        print('preview -> %s' % a.preview)


if __name__ == '__main__':
    main()
