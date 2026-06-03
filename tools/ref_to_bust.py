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


def _zoom_out(src, crop_box, zoom):
    """Expand crop_box so the current subject occupies `zoom` of the frame.

    The extra width is split evenly (horizontal centering); the extra height is
    added entirely at the TOP (the shoulders stay pinned to the bottom edge, as in
    vanilla FE8 busts -- headroom appears above the head, where FE8's dead corners
    sit). Where the larger box runs off the ref, pad the ref with its border-median
    color so the new margin reads as flat background and gets keyed transparent.
    Returns (possibly padded) src and the new crop_box. No-op at zoom == 1.0.
    """
    if zoom >= 1.0:
        return src, crop_box
    x0, y0, x1, y1 = crop_box
    w, h = x1 - x0, y1 - y0
    dx = (w / zoom - w) / 2.0
    dy = (h / zoom - h)                       # all headroom on top; bottom fixed
    nx0, ny0, nx1, ny1 = x0 - dx, y0 - dy, x1 + dx, y1
    pl = max(0, int(np.ceil(-nx0)))
    pt = max(0, int(np.ceil(-ny0)))
    pr = max(0, int(np.ceil(nx1 - src.width)))
    pb = max(0, int(np.ceil(ny1 - src.height)))
    if pl or pt or pr or pb:
        a = np.asarray(src)
        edge = np.concatenate([a[0:8].reshape(-1, 3), a[:, 0:8].reshape(-1, 3),
                               a[:, -8:].reshape(-1, 3)])
        fill = tuple(int(v) for v in np.median(edge, axis=0))
        padded = Image.new('RGB', (src.width + pl + pr, src.height + pt + pb), fill)
        padded.paste(src, (pl, pt))
        src = padded
        nx0, ny0, nx1, ny1 = nx0 + pl, ny0 + pt, nx1 + pl, ny1 + pt
    return src, (int(round(nx0)), int(round(ny0)), int(round(nx1)), int(round(ny1)))


def _pad_to_box(src, box):
    """Pad src with its border-median color so an out-of-bounds crop box (e.g. a
    crop shifted past the ref edge to reposition the subject) reads as flat
    background. No-op when the box is fully inside the ref (byte-identical)."""
    x0, y0, x1, y1 = box
    pl, pt = max(0, -x0), max(0, -y0)
    pr, pb = max(0, x1 - src.width), max(0, y1 - src.height)
    if not (pl or pt or pr or pb):
        return src, box
    a = np.asarray(src)
    edge = np.concatenate([a[0:8].reshape(-1, 3), a[:, 0:8].reshape(-1, 3),
                           a[:, -8:].reshape(-1, 3)])
    fill = tuple(int(v) for v in np.median(edge, axis=0))
    padded = Image.new('RGB', (src.width + pl + pr, src.height + pt + pb), fill)
    padded.paste(src, (pl, pt))
    return padded, (x0 + pl, y0 + pt, x1 + pl, y1 + pt)


def convert(ref_path, crop_box, bg_thresh=45.0, sharpen=0, reserve_extremes=True,
            ink_lum=150, ink_cov=4, downscale='smooth', zoom=1.0):
    src = Image.open(ref_path).convert('RGB')
    src, crop_box = _zoom_out(src, crop_box, zoom)
    src, crop_box = _pad_to_box(src, crop_box)
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

    # Downscale the FULL-RES crop to target. Two modes:
    #  - 'smooth' (default): area-average (BOX to 2x, then LANCZOS). Right for
    #    painterly/textured refs (the cats, Wolfram) where averaging keeps fur and
    #    skin gradients clean so eyes read; the ink overlay below re-crisps lines.
    #  - 'crisp': NEAREST point-sample. Right for refs that are ALREADY clean cel
    #    art (e.g. Marty): averaging a clean 23x-downscale edge invents grey halos
    #    around the eyes/mouth/outlines, so just sample the source pixels and skip
    #    the ink overlay entirely. Simpler, and matches the source's flat look.
    hires = src.crop(crop_box)
    if downscale == 'crisp':
        img = hires.resize((BUST_W, BUST_H), Image.NEAREST)
    else:
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
    if downscale == 'crisp':
        # Clean cel art: the point-sampled image already holds the source's real,
        # flat pixels -- so build the palette from its OWN dominant colors (true
        # hues), not MEDIANCUT centroids, which drift the hue (a terracotta scarf
        # quantizes to a rosy pink). Take the most frequent exact colors, force a
        # neutral-black slot for clean outlines/eyes, map every pixel to the
        # nearest, then despeckle the lone stray pixels point-sampling leaves.
        fcols = arr[m]
        uniq, cnt = np.unique(fcols, axis=0, return_counts=True)
        pal_arr = uniq[np.argsort(cnt)[::-1][:14]].astype(int)
        di = int(pal_arr.sum(1).argmin())
        if pal_arr[di].sum() > 140:                 # no genuine black present
            pal_arr = np.vstack([pal_arr, [20, 17, 24]])
        else:
            pal_arr[di] = (20, 17, 24)
        out = ((arr[:, :, None, :] - pal_arr[None, None, :, :]) ** 2).sum(3).argmin(2)
        # NOTE: no despeckle here. A despeckle pass can't tell a wanted bright
        # catchlight-in-dark-eye from an unwanted speck, and it filled in the eye
        # catchlights -> solid rectangular eyes. Tiny (~2px) features like Marty's
        # eyes are cleaned up with a deliberate per-portrait pixel touch-up instead.
        out = np.where(m, out + 1, 0)
        pal = pal_arr.reshape(-1).astype(int).tolist()
    elif reserve_extremes:
        fcols = arr[m]
        flum = fcols.sum(1)
        nb = max(1, int(len(flum) * 0.006))
        order = np.argsort(flum)
        bright = fcols[order[-nb:]].mean(0)
        dark = fcols[order[:nb]].mean(0)

        # Reserve slots for dominant SATURATED HUES too. reserve-extremes protects
        # only the luminance extremes (brightest highlight / blackest line); it does
        # nothing for saturated mid-tones, so a vivid minority color (a red tassel
        # stripe, a tan robe) on a cool-dominated portrait still gets folded into
        # grey by area-based MEDIANCUT -- which instead wastes slots splitting one
        # dark region into near-identical greys. Find the dominant saturated clusters
        # the area palette would drop and reserve a slot for each (max 2). Gated on
        # chroma + area, and skipped when the hue is already represented, so cool/
        # greyscale portraits with no dropped hue fire nothing -> identical palette.
        chroma = fcols.max(1) - fcols.min(1)
        sat = fcols[chroma >= 55]
        provisional = np.array(img.quantize(colors=13, method=Image.MEDIANCUT,
                                            dither=Image.NONE).getpalette()[:39]).reshape(-1, 3)
        anchors = np.vstack([provisional, bright, dark])
        chroma_cols = []

        def _unrepresented(col):
            ref_set = np.vstack([anchors] + chroma_cols) if chroma_cols else anchors
            return np.sqrt(((ref_set - col) ** 2).sum(1)).min() > 55

        if len(sat) >= 0.012 * len(fcols):
            # (a) distinct saturated RGB clusters, each at its own brightness. This
            #     catches a vivid shade even when it shares a hue with a duller
            #     dominant region (e.g. a dark sigil-cyan against the pale mask).
            bins = sat // 40
            keys, counts = np.unique(bins, axis=0, return_counts=True)
            for ki in np.argsort(counts)[::-1]:
                if counts[ki] < 0.012 * len(fcols):
                    break
                col = sat[(bins == keys[ki]).all(1)].mean(0)
                if _unrepresented(col):
                    chroma_cols.append(col)
                if len(chroma_cols) >= 2:
                    break
            # (b) warm/red rescue. Thin red/orange accents (a tassel stripe) span a
            #     wide brightness range, so they fragment across RGB bins and no
            #     single bin clears the area gate -- yet as a hue they are a clear
            #     minority color the cool palette would lose entirely. Reserve the
            #     mean of the genuinely red pixels (R well above both G and B, so
            #     tan/skin warm tones don't dilute it) if it isn't represented.
            red = sat[(sat[:, 0] > sat[:, 1] + 40) & (sat[:, 0] > sat[:, 2] + 40)]
            if len(red) >= 0.010 * len(fcols) and len(chroma_cols) < 3 and _unrepresented(red.mean(0)):
                chroma_cols.append(red.mean(0))

        nbase = 13 - len(chroma_cols)
        q = img.quantize(colors=nbase, method=Image.MEDIANCUT, dither=Image.NONE)
        base = np.array(q.getpalette()[:nbase * 3]).reshape(-1, 3)
        stack = [base] + ([np.array(chroma_cols)] if chroma_cols else []) + [bright[None], dark[None]]
        pal_arr = np.vstack(stack)
        # read the deepest dark as neutral black, so eyes/outlines land on black
        # rather than a muddy navy.
        pal_arr[int(pal_arr.sum(1).argmin())] = (20, 17, 24)

        # Smooth base + ink overlay. The plain area-average downscale keeps skin/
        # fur gradients clean (which is what lets eyes read against a textured
        # face), but blurs thin 1px features (eyes, mouth, outlines) into muddy
        # "mush". So use the smooth nearest-palette result as the base, and only
        # OVERRIDE it where a genuine near-black line runs: quantize a 3x crop and
        # if >=4/9 of a block is a near-black "ink" color, snap that pixel solid.
        # Thin dark features stay crisp 1px; everything else stays smooth (no
        # speckle in fur -- an earlier global crisp pass added that and cost the
        # cats/Wolfram their eye definition).
        lum = pal_arr.sum(1)
        out = ((arr[:, :, None, :] - pal_arr[None, None, :, :]) ** 2).sum(3).argmin(2)
        ink = set(np.where(lum < ink_lum)[0].tolist())
        # point-sampled ('crisp') base is already hard-edged; the ink overlay is a
        # fix for the smooth downscale's blur, so skip it entirely in crisp mode.
        big = np.asarray(hires.resize((BUST_W * 3, BUST_H * 3), Image.LANCZOS)).astype(int)
        bidx = ((big[:, :, None, :] - pal_arr[None, None, :, :]) ** 2).sum(3).argmin(2)
        for y in range(BUST_H if downscale != 'crisp' else 0):
            for x in range(BUST_W):
                blk = bidx[3 * y:3 * y + 3, 3 * x:3 * x + 3].ravel()
                ip = [v for v in np.unique(blk) if v in ink]
                if ip:
                    best = min(ip, key=lambda v: lum[v])
                    if (blk == best).sum() >= ink_cov:
                        out[y, x] = best
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
    ap.add_argument('--ink-lum', type=int, default=150,
                    help='luminance (R+G+B) below which a color counts as an "ink" line for the crisp-line '
                         'overlay (default 150). Raise to let darker-but-not-black lines snap crisp.')
    ap.add_argument('--ink-cov', type=int, default=4,
                    help='how many of a 3x3 block (max 9) must be ink for the pixel to snap to the line '
                         '(default 4). Lower = more aggressive line definition (thinner lines survive).')
    ap.add_argument('--downscale', choices=('smooth', 'crisp'), default='smooth',
                    help="'smooth' (default): area-average + ink overlay, for painterly/textured refs. "
                         "'crisp': NEAREST point-sample (no ink pass), for refs that are already clean cel "
                         'art -- avoids the grey halos area-averaging invents around clean eyes/mouths/edges.')
    ap.add_argument('--zoom', type=float, default=1.0,
                    help='shrink the subject to this fraction of the frame to add top headroom (default 1.0 '
                         '= unchanged). e.g. 0.85 pulls the silhouette inside FE8\'s clipped top corners; '
                         'shoulders stay pinned to the bottom edge.')
    a = ap.parse_args()
    box = tuple(int(v) for v in a.crop.split(','))
    res = convert(a.ref, box, a.bg_thresh, a.sharpen, a.reserve_extremes, a.ink_lum, a.ink_cov, a.downscale,
                  a.zoom)
    res.save(a.out)
    print('%s -> %s (96x80 indexed, %d colors)' % (a.ref, a.out, len(set(res.getdata()))))
    if a.preview:
        res.convert('RGB').resize((BUST_W * 3, BUST_H * 3), Image.NEAREST).save(a.preview)
        print('preview -> %s' % a.preview)


if __name__ == '__main__':
    main()
