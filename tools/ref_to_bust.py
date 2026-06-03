#!/usr/bin/env python3
"""Translate a character reference into a game-ready 96x80 indexed FE8 bust.

Pipeline (deliberately minimal -- the less we edit a clean ref, the better it
reads; over-processing a flat ref desaturates it):

  crop/zoom to a head-and-shoulders bust  ->  segment the flat background
  (border-median key + border-connected flood, since the subject fills the
  bottom)  ->  area-average downscale to 96x80  ->  quantize to <=16 colors with
  pngquant (index 0 reserved transparent).

pngquant is a far better low-colour quantizer than PIL's MEDIANCUT: it keeps
saturated accents (a blue eye, a cyan star, purple crystals) that median-cut
folds into grey. The clean cel-art refs we feed it (flat colour, hard outlines)
survive the downscale; ask the ref generator for "flat cel-shaded, bold black
outlines, ~16-colour palette, no gradients/fine texture" -- detail below 96x80
just averages into mush.

Usage:
    ref_to_bust.py <ref.png> <out_bust.png> --crop x0,y0,x1,y1 [options]
      --zoom z        shrink the subject to fraction z of the frame for top
                      headroom (clears FE8's dead top corners); default 1.0.
      --sharpen pct   optional UnsharpMask at target res (default 0 = off).
      --bg-thresh d   RGB distance from the border colour treated as background.
      --preview big   also write a 3x nearest-neighbour preview.

The --crop box is per-character framing; aim for ~96:80 (1.2) aspect.
"""

import argparse
import subprocess
import tempfile
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


def _pngquant_quantize(img, m, ncolors=16):
    """Quantize the 96x80 RGB `img` to <=16 colors with pngquant, keeping only the
    masked subject. Background (~m) becomes index 0 (transparent); the subject's
    colours land in indices 1.. . Returns (index_array, flat_palette_1..N).

    pngquant counts the transparent entry toward `ncolors`, so feeding it RGBA with
    a transparent background yields <=15 opaque colours + transparent = <=16 total,
    exactly FE8's ceiling with index 0 free.
    """
    rgb = np.asarray(img.convert('RGB'))
    rgba = np.dstack([rgb, np.where(m, 255, 0).astype('uint8')])
    with tempfile.NamedTemporaryFile(suffix='.png') as fi, \
         tempfile.NamedTemporaryFile(suffix='.png') as fo:
        Image.fromarray(rgba).save(fi.name)
        subprocess.run(['pngquant', str(ncolors), '--force', '--output', fo.name, fi.name],
                       check=True)
        q = np.asarray(Image.open(fo.name).convert('RGBA'))

    out = np.zeros(m.shape, int)
    opaque = (q[..., 3] >= 128) & m
    cols = q[..., :3][opaque]
    if len(cols) == 0:
        return out, [0, 0, 0]
    uniq, counts = np.unique(cols, axis=0, return_counts=True)
    keep = uniq[np.argsort(counts)[::-1][:15]].astype(int)         # <=15 opaque slots
    d = ((cols[:, None, :].astype(int) - keep[None]) ** 2).sum(2)
    out[opaque] = d.argmin(1) + 1
    return out, keep.reshape(-1).tolist()


def convert(ref_path, crop_box, bg_thresh=45.0, sharpen=0, zoom=1.0):
    src = Image.open(ref_path).convert('RGB')
    src, crop_box = _zoom_out(src, crop_box, zoom)
    src, crop_box = _pad_to_box(src, crop_box)
    crop = src.crop(crop_box).resize((480, 400), Image.LANCZOS)
    rgb = np.asarray(crop).astype(np.float32)
    H, W = rgb.shape[:2]

    # Segment the flat background: sample the border colour (the subject fills the
    # bottom-centre), key pixels within bg_thresh of it, then keep only the
    # border-connected region as background -- so any same-colour pocket enclosed
    # by the subject stays foreground.
    edge = np.concatenate([rgb[0:8].reshape(-1, 3),
                           rgb[:, 0:8].reshape(-1, 3),
                           rgb[:, -8:].reshape(-1, 3)])
    bg_color = np.median(edge, axis=0)
    bg = np.sqrt(((rgb - bg_color) ** 2).sum(2)) < bg_thresh

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

    # Area-average downscale to target (BOX to 2x then LANCZOS) -- keeps flat
    # colour zones and gradients clean at the ~20x reduction.
    hires = src.crop(crop_box)
    img = hires.resize((BUST_W * 2, BUST_H * 2), Image.BOX).resize((BUST_W, BUST_H), Image.LANCZOS)
    if sharpen:
        img = img.filter(ImageFilter.UnsharpMask(radius=1, percent=sharpen, threshold=1))
    m = np.asarray(Image.fromarray((fg * 255).astype('uint8')).resize((BUST_W, BUST_H), Image.LANCZOS)) > 120

    # Silhouette hygiene only (no colour editing): drop tiny stray fg blobs and
    # fill small interior holes in the mask.
    lab, n = _label(m)
    for i in range(1, n + 1):
        if (lab == i).sum() < 20:
            m[lab == i] = False
    labh, nh = _label(~m)
    for i in range(1, nh + 1):
        comp = (labh == i)
        touches_edge = comp[0].any() or comp[-1].any() or comp[:, 0].any() or comp[:, -1].any()
        if comp.sum() < 30 and not touches_edge:
            m[comp] = True

    out, pal = _pngquant_quantize(img, m)

    res = Image.new('P', (BUST_W, BUST_H))
    res.putpalette([0, 255, 0] + pal + [0] * (768 - 3 - len(pal)))
    res.putdata(out.flatten().tolist())
    return res


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('ref')
    ap.add_argument('out')
    ap.add_argument('--crop', required=True, help='x0,y0,x1,y1 in ref pixels (~1.2 aspect)')
    ap.add_argument('--zoom', type=float, default=1.0,
                    help='shrink the subject to this fraction of the frame for top headroom '
                         '(clears FE8 dead corners); default 1.0 = unchanged.')
    ap.add_argument('--sharpen', type=int, default=0,
                    help='UnsharpMask percent at target res (default 0 = off). A taste dial; '
                         'the clean-ref + pngquant path is already crisp.')
    ap.add_argument('--bg-thresh', type=float, default=45.0,
                    help='RGB distance from the sampled border colour to treat as background (default 45).')
    ap.add_argument('--flip-h', action='store_true',
                    help='mirror horizontally so the bust faces FE8-canonical screen-left '
                         '(use when the ref faces right); record as art.render.flip_h in YAML.')
    ap.add_argument('--preview', help='also write a 3x nearest-neighbour preview here')
    a = ap.parse_args()
    box = tuple(int(v) for v in a.crop.split(','))
    res = convert(a.ref, box, a.bg_thresh, a.sharpen, a.zoom)
    if a.flip_h:
        res = res.transpose(Image.FLIP_LEFT_RIGHT)
    res.save(a.out)
    print('%s -> %s (96x80 indexed, %d colors)' % (a.ref, a.out, len(set(res.getdata()))))
    if a.preview:
        res.convert('RGB').resize((BUST_W * 3, BUST_H * 3), Image.NEAREST).save(a.preview)
        print('preview -> %s' % a.preview)


if __name__ == '__main__':
    main()
