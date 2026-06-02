#!/usr/bin/env python3
"""Translate a (Nano Banana / Gemini) character reference into a game-ready
96x80 indexed FE8 portrait bust.

Pipeline: crop to a head-and-shoulders bust -> segment the flat background
(sample the border color, key pixels within an RGB distance of it, border-
connected flood seeded from top/left/right since the subject fills the bottom)
-> clean up specks/holes -> area-average downscale to 96x80 (no sharpening by
default, to match the flat hand-drawn look of vanilla FE8 portraits) -> quantize
to 15 colors (index 0 reserved transparent) -> erode the silhouette edge to
transparent for a clean cut.

The result drops straight into the insert pipeline:
    tools/portrait_tool.py encode <bust.png> <sheet.png>   ->  decomp -> gbagfx

Usage:
    ref_to_bust.py <ref.png> <out_bust.png> --crop x0,y0,x1,y1 [--preview big.png]

The --crop box is chosen per character (it is reference-specific framing); aim
for a ~96:80 (1.2) aspect: eyestalk/head tips near the top, shoulders at bottom.
"""

import argparse
import numpy as np
from PIL import Image, ImageFilter
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


def convert(ref_path, crop_box, bg_thresh=45.0, sharpen=0, reserve_extremes=True):
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
    if sharpen:
        img = img.filter(ImageFilter.UnsharpMask(radius=1, percent=sharpen, threshold=1))
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

    # MEDIANCUT picks palette colors by pixel *area*, so tiny high-contrast
    # details (a few near-white gem facets, a few pure-black eye/mouth pixels)
    # on a color-dominated portrait get starved and folded into the nearest big
    # grey region -> muddy, washed-out highlights and darks. Reserve two slots
    # for the foreground's brightest and darkest pixels so the extremes survive
    # (--reserve-extremes, on by default).
    arr = np.asarray(img).astype(int)
    if reserve_extremes:
        q = img.quantize(colors=13, method=Image.MEDIANCUT, dither=Image.NONE)
        base = np.array(q.getpalette()[:13 * 3]).reshape(-1, 3)
        fcols = arr[m]
        flum = fcols.sum(1)
        nb = max(1, int(len(flum) * 0.006))
        order = np.argsort(flum)
        bright = fcols[order[-nb:]].mean(0)
        dark = fcols[order[:nb]].mean(0)
        pal_arr = np.vstack([base, bright, dark])
        # read the deepest dark as neutral black, so eyes/outlines land on black
        # rather than a muddy navy.
        pal_arr[int(pal_arr.sum(1).argmin())] = (20, 17, 24)

        # Crisp, edge-preserving downscale. The plain area-average path (BOX->
        # LANCZOS) blends crisp reference pixels into intermediate "mush" colors
        # at every edge -- worst on thin 1px features (eyes, mouth) that smear to
        # grey. Instead: quantize a 3x-oversampled crop to the palette, then
        # collapse each 3x3 block to ONE index with an "ink" preference -- if a
        # near-black line passes through the block (>=3/9 subpixels) it wins, so
        # outlines and facial features stay solid 1px instead of blurring. Flat
        # regions fall through to the block's majority color (no invented blends).
        lum = pal_arr.sum(1)
        ink = set(np.where(lum < 170)[0].tolist())
        osf = 3
        big = np.asarray(hires.resize((BUST_W * osf, BUST_H * osf), Image.LANCZOS)).astype(int)
        bidx = ((big[:, :, None, :] - pal_arr[None, None, :, :]) ** 2).sum(3).argmin(2)
        out = np.zeros((BUST_H, BUST_W), int)
        for y in range(BUST_H):
            for x in range(BUST_W):
                blk = bidx[osf * y:osf * y + osf, osf * x:osf * x + osf].ravel()
                u, c = np.unique(blk, return_counts=True)
                ip = [v for v in u if v in ink]
                if ip:
                    best = min(ip, key=lambda v: lum[v])
                    out[y, x] = best if (blk == best).sum() >= 3 else u[c.argmax()]
                else:
                    dk = u[lum[u].argmin()]
                    out[y, x] = dk if (blk == dk).sum() >= (osf * osf) // 2 else u[c.argmax()]
        out = np.where(m, out + 1, 0)
        pal = pal_arr.reshape(-1).astype(int).tolist()
    else:
        q = img.quantize(colors=15, method=Image.MEDIANCUT, dither=Image.NONE)
        out = np.where(m, np.asarray(q).astype(int) + 1, 0)
        pal = q.getpalette()[:15 * 3]
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
    ap.add_argument('--sharpen', type=int, default=0,
                    help='UnsharpMask percent at target res (default 0 = off, matches the flat hand-drawn '
                         'look of vanilla FE8 portraits; higher adds crunch).')
    ap.add_argument('--no-reserve-extremes', dest='reserve_extremes', action='store_false',
                    help='disable reserving palette slots for the brightest/darkest pixels (default: reserve, '
                         'so small white highlights and black eyes/mouths survive quantization).')
    a = ap.parse_args()
    box = tuple(int(v) for v in a.crop.split(','))
    res = convert(a.ref, box, a.bg_thresh, a.sharpen, a.reserve_extremes)
    res.save(a.out)
    print('%s -> %s (96x80 indexed, %d colors)' % (a.ref, a.out, len(set(res.getdata()))))
    if a.preview:
        res.convert('RGB').resize((BUST_W * 3, BUST_H * 3), Image.NEAREST).save(a.preview)
        print('preview -> %s' % a.preview)


if __name__ == '__main__':
    main()
