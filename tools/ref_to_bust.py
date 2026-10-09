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
      --matte rrggbb  paint the keyed background this colour (the outline's) before
                      the downscale, so a light background cannot halo the edge.
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


# Cel mode: the ink lines of a clean cel-shaded ref, as a fraction of each target pixel's area,
# above which that pixel is drawn as ink. Low enough that a source line thinner than one target
# pixel still lands as a continuous 1px line instead of breaking into dots.
CEL_INK_COVERAGE = 0.22
CEL_INK_LUMA = 200          # summed RGB below which a source pixel is ink
CEL_FG_COVERAGE = 0.45      # fraction of a target pixel that must be subject to keep it


def _cel_downscale(hires, fgh):
    """96x80 indexed bust for a flat cel-shaded ref, as cleanly as the downscale allows.

    The default path resamples twice with Lanczos and lets pngquant dither: right for painted
    refs, wrong for flat ones, where Lanczos rings at every hard edge and the dither scatters
    speckle across flat colour. Here instead: ONE area-average to target (no ringing); a palette
    chosen at 4x target, where the art's flat colours outnumber the anti-aliased edge blends
    that would otherwise spend palette slots; every pixel snapped to it with no dither; and the
    ink lines rebuilt from the source's own dark pixels by area coverage, so a thin line stays
    one continuous pixel wide (Nicolas, 2026-10-09: "make the descale as clean as possible").
    """
    a = np.asarray(hires.convert('RGB')).astype(int)
    ink = (a.sum(2) < CEL_INK_LUMA) & fgh

    def cover(mask, size):
        return np.asarray(Image.fromarray((mask * 255).astype('uint8')).resize(size, Image.BOX)) / 255.0

    ink_cover = cover(ink, (BUST_W, BUST_H))
    # A pixel the outline crosses is subject even where the line is thinner than half a pixel:
    # keyed on fg coverage alone, the outer outline vanished wherever it was thinnest (Messie's
    # nose, 2026-10-09).
    m = (cover(fgh, (BUST_W, BUST_H)) >= CEL_FG_COVERAGE) | (ink_cover >= CEL_INK_COVERAGE)
    small = np.asarray(hires.resize((BUST_W, BUST_H), Image.BOX).convert('RGB')).astype(int)
    mid = hires.resize((BUST_W * 4, BUST_H * 4), Image.BOX)
    m4 = cover(fgh, mid.size) >= 0.99
    rgba = np.dstack([np.asarray(mid.convert('RGB')), np.where(m4, 255, 0).astype('uint8')])
    with tempfile.NamedTemporaryFile(suffix='.png') as fi, \
         tempfile.NamedTemporaryFile(suffix='.png') as fo:
        Image.fromarray(rgba).save(fi.name)
        subprocess.run(['pngquant', '16', '--nofs', '--force', '--output', fo.name, fi.name],
                       check=True)
        q = np.asarray(Image.open(fo.name).convert('RGBA'))
    cols = q[..., :3][q[..., 3] >= 128]
    uniq, counts = np.unique(cols, axis=0, return_counts=True)
    pal = uniq[np.argsort(counts)[::-1][:15]].astype(int)
    out = np.zeros((BUST_H, BUST_W), int)
    d = ((small[m][:, None, :] - pal[None]) ** 2).sum(2)
    out[m] = d.argmin(1) + 1
    inked = (ink_cover >= CEL_INK_COVERAGE) & m
    # The silhouette is always inked, FE-portrait style: a ref may rim-light an edge instead of
    # outlining it (Messie's snout), and a pale rim reads as no edge at 96x80. Off-frame counts
    # as subject, so a neck cut by the frame gets no line across the cut.
    pad = np.pad(m, 1, constant_values=True)
    edge = m & ~(pad[:-2, 1:-1] & pad[2:, 1:-1] & pad[1:-1, :-2] & pad[1:-1, 2:])
    inked |= edge
    out[inked] = int(pal.sum(1).argmin()) + 1
    res = Image.new('P', (BUST_W, BUST_H))
    flat = pal.reshape(-1).tolist()
    res.putpalette([0, 255, 0] + flat + [0] * (768 - 3 - len(flat)))
    res.putdata(out.flatten().tolist())
    return res


def sample_pixel_grid(img, cell, origin=0):
    """A pixel-art ref saved large (and often as a JPEG) -> its NATIVE grid, one sample per
    cell centre. Every later step then sees the artist's flat colours, never compression
    noise; scale back up with NEAREST before convert(). `origin` is the grid's offset in the
    ref (a cell boundary at x = origin + k*cell). Messie's ref is 41px cells at -1 (#26)."""
    img = img.convert('RGB')
    nw, nh = (img.width - origin) // cell, (img.height - origin) // cell
    out = Image.new('RGB', (nw, nh), (255, 255, 255))
    for j in range(nh):
        for i in range(nw):
            x, y = origin + i * cell + cell // 2, origin + j * cell + cell // 2
            if 0 <= x < img.width and 0 <= y < img.height:
                out.putpixel((i, j), img.getpixel((x, y)))
    return out


def _lum(a):
    return 0.299 * a[..., 0] + 0.587 * a[..., 1] + 0.114 * a[..., 2]


def retint_ramp(img, dark, light, select, blend=None):
    """Repaint one colour family onto two target colours, keeping the art's own shading.

    `dark` and `light` are (source_rgb, target_rgb) anchors: a pixel as bright as an anchor's
    source lands exactly on its target, brighter or darker ones scale with it, and pixels
    inside `blend` (a (lo, hi) luminance window; default: the middle of the two anchors)
    blend. `select(rgb_float_array) -> bool mask` picks the family
    (e.g. "blue-ish"), so outline, metal and eyes outside it are untouched. Used to bring a ref
    onto the cast palette its map sprite already wears (Messie: blue -> slate, #26)."""
    a = np.asarray(img.convert('RGB')).astype(np.float32) / 255
    f = lambda c: np.array(c, np.float32) / 255
    L = _lum(a)
    l0, l1 = _lum(f(dark[0])), _lum(f(light[0]))
    lo, hi = blend or (l0 + (l1 - l0) * 0.35, l1 - (l1 - l0) * 0.2)
    w = np.clip((L - lo) / max(hi - lo, 1e-6), 0, 1)[..., None]
    new = np.clip(f(dark[1]) * (L / l0)[..., None] * (1 - w)
                  + f(light[1]) * (L / l1)[..., None] * w, 0, 1)
    m = select(a)
    a[m] = new[m]
    return Image.fromarray((a * 255).round().astype('uint8'))


def convert(ref_path, crop_box, bg_thresh=45.0, sharpen=0, zoom=1.0, matte=None, cel=False):
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
    if matte is not None:
        # Paint the keyed background with the subject's OUTLINE colour before the downscale.
        # Left as is, a light background averages into every edge pixel and quantizes into a
        # light halo outside the outline (Messie's white-backed pixel art, #26); matted, the
        # edge blends outline into outline and stays clean.
        bgm = Image.fromarray((conn * 255).astype('uint8')).resize(hires.size, Image.NEAREST)
        hires.paste(Image.new('RGB', hires.size, tuple(matte)), (0, 0), bgm)
    if cel:
        fgh = np.asarray(Image.fromarray((fg * 255).astype('uint8')).resize(hires.size, Image.NEAREST)) > 127
        return _cel_downscale(hires, fgh)
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
    ap.add_argument('--matte', help='hex colour (e.g. 000000) painted over the keyed background '
                    'before the downscale -- the subject\'s outline colour; kills a light halo. '
                    'Record as art.render.matte in YAML.')
    ap.add_argument('--preview', help='also write a 3x nearest-neighbour preview here')
    a = ap.parse_args()
    box = tuple(int(v) for v in a.crop.split(','))
    matte = tuple(int(a.matte[i:i + 2], 16) for i in (0, 2, 4)) if a.matte else None
    res = convert(a.ref, box, a.bg_thresh, a.sharpen, a.zoom, matte)
    if a.flip_h:
        res = res.transpose(Image.FLIP_LEFT_RIGHT)
    res.save(a.out)
    print('%s -> %s (96x80 indexed, %d colors)' % (a.ref, a.out, len(set(res.getdata()))))
    if a.preview:
        res.convert('RGB').resize((BUST_W * 3, BUST_H * 3), Image.NEAREST).save(a.preview)
        print('preview -> %s' % a.preview)


if __name__ == '__main__':
    main()
