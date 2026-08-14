#!/usr/bin/env python3
"""Convert an arbitrary image into an FE8 event-background (`BACG`) source PNG.

FE8 event BGs are 240x160, 4bpp, with up to 8 sixteen-colour sub-palettes (one
per 8x8 tile) -> 128 colours max. The decomp's `tsa_generator.py` (FETSATOOL,
`feimg2`) reads each tile's palette bank from its first pixel (`tile[0] // 16`)
and assumes every pixel in that tile lies in one 16-aligned bank, so the PNG it
ingests must already be **banked**: mode-P, palette laid out as N*16 entries,
every 8x8 tile drawing from exactly one bank.

This produces that PNG. Pipeline: fit to 240x160 -> round to GBA 5-bit depth ->
quantise -> greedily pack each tile's colours into <=8 banks of <=16. A clean
low-colour source (e.g. the Zeldacrafter snow-town, 15 colours) lands in a single
bank untouched; a busier CG spreads across banks. A dithered or photo-derived CG
cannot pack that way at all, so it is instead refit: eight 15-colour palettes are
fitted to the picture and each tile assigned the one that reproduces it best.

Usage: tools/bg_to_fe8.py <src-image> <out.png> [--colors N] [--fit crop|pad]
"""
import argparse
import sys
import numpy as np
from PIL import Image

W, H = 240, 160


def trim_uniform_border(im, min_keep=0.5):
    """Strip a letterbox MAT: edge rows/columns that are a single flat colour.

    The FE9-10 CG rips ship this way -- a 240-wide picture inside a 256-wide canvas, the
    spare 16 columns filled flat black. Centre-cropping such a source to 240 keeps HALF the
    bar and discards an equal strip of real picture on the opposite side, which is exactly
    what shipped on both ch05 backdrops before this existed (visible in-engine, 2026-08-14).

    The test is UNIFORMITY, not darkness: a border column of one colour carries no picture,
    whatever that colour is (black here, but a white or magenta mat is the same artifact).
    Measured on the two real rips, a bar column holds exactly 1 distinct colour while the
    art beside it holds 8-12, so the two are not near each other and no tolerance is needed.

    `min_keep` is a safety rail for pictures that are largely flat by design -- a night sky,
    a fade to black. Trimming stops rather than give back less than this fraction of either
    dimension; a legitimately flat-edged image is left for a human to crop.
    """
    a = np.asarray(im.convert('RGB'))
    h, w = a.shape[:2]
    flat_row = [len(np.unique(a[y].reshape(-1, 3), axis=0)) == 1 for y in range(h)]
    flat_col = [len(np.unique(a[:, x].reshape(-1, 3), axis=0)) == 1 for x in range(w)]

    def span(flat, size):
        lo, hi = 0, size
        while lo < hi and flat[lo]:
            lo += 1
        while hi > lo and flat[hi - 1]:
            hi -= 1
        return (0, size) if (hi - lo) < max(1, int(size * min_keep)) else (lo, hi)

    top, bottom = span(flat_row, h)
    left, right = span(flat_col, w)
    if (left, top, right, bottom) == (0, 0, w, h):
        return im
    return im.crop((left, top, right, bottom))


def fit_240x160(im, mode):
    """Center the source in a 240x160 frame: 'crop' fills (cover), 'pad' letterboxes."""
    im = im.convert('RGB')
    sw, sh = im.size
    if (sw, sh) == (W, H):
        return im
    scale = max(W / sw, H / sh) if mode == 'crop' else min(W / sw, H / sh)
    nw, nh = max(1, round(sw * scale)), max(1, round(sh * scale))
    # NEAREST, not LANCZOS: these sources are pixel art destined for a GBA 4bpp
    # re-quantise. Bilinear/Lanczos smoothing invents in-between colours that the
    # bank-packer then has to quantise back, producing blur + banding. Nearest
    # preserves the source pixels 1:1.
    im = im.resize((nw, nh), Image.NEAREST)
    canvas = Image.new('RGB', (W, H), (0, 0, 0))
    canvas.paste(im, ((W - nw) // 2, (H - nh) // 2))
    return canvas


def to_tiles(a):
    """(H,W,3) image -> (T,64,3) tiles in row-major tile order."""
    return (a.reshape(H // 8, 8, W // 8, 8, 3).transpose(0, 2, 1, 3, 4)
             .reshape(-1, 64, 3).astype(np.int32))   # int32: a squared channel delta (65025)
                                                    # overflows int16, and a wrapped-negative
                                                    # distance makes argmin pick the WORST bank


def _quantise_pixels(px, n):
    """MEDIANCUT palette of at most n colours for a pixel list (N,3) -> (m,3), m <= n.

    Snapped back onto the GBA 5-bit grid: MEDIANCUT returns cluster AVERAGES, which land
    off-grid even when every input pixel was on it, and gbagfx truncates the low 3 bits on
    its way into the .gbapal -- so an unrounded palette means the ROM shows colours the tool
    never chose its indices for. Rounding can also collide two entries; dedupe, since a
    duplicate would be a bank slot spent on a colour already available."""
    im = Image.fromarray(px.astype('uint8').reshape(-1, 1, 3)).quantize(
        colors=n, method=Image.MEDIANCUT, dither=Image.NONE)
    pal = np.array(im.getpalette()[:n * 3], dtype=np.int32).reshape(-1, 3)
    return np.unique((pal[np.unique(np.array(im))] >> 3) << 3, axis=0)


def _tile_err(tiles, pal):
    """Total squared error of each tile if drawn from `pal` -> (T,)."""
    return ((tiles[:, :, None, :] - pal[None, None, :, :]) ** 2).sum(3).min(2).sum(1)


def bank_cluster(tiles, nbanks=8, per_bank=15, rounds=6):
    """Fit `nbanks` palettes of `per_bank` colours to the tiles, and assign each tile one.

    The greedy `bank_pack` can only put two tiles in one bank when one tile's colour SET fits
    inside the other's, which a dithered source never satisfies: it checkerboards two shades
    pixel-by-pixel, so each 8x8 tile of sky holds 15-18 colours nobody else shares exactly.
    Such a source packs only when the global palette is squeezed to 15 colours -- one bank, and
    7 of FE8's 8 thrown away. So fit the banks to the picture instead of hunting for tiles that
    already agree: seed by tile mean colour, then alternate (a) requantise each bank from the
    pooled pixels of the tiles currently assigned to it, (b) reassign every tile to whichever
    bank reproduces it with least error. Both steps only lower total error, so it converges;
    `rounds` caps it. Lossy by construction -- for a clean low-colour source the caller keeps
    the exact `bank_pack` path instead. Returns (assign[T], banks[list of (m,3) arrays])."""
    means = tiles.mean(axis=1)
    # k-means++-style seeding by farthest-point: pick the tile mean furthest from the image
    # mean, then repeatedly the mean furthest from everything chosen. Deterministic (no RNG),
    # and it lands one seed in each colour region a CG actually has (sky, snow, lit windows).
    cent = [means[int(np.argmax(((means - means.mean(0)) ** 2).sum(1)))]]
    while len(cent) < nbanks:
        far = np.min([((means - c) ** 2).sum(1) for c in cent], axis=0)
        cent.append(means[int(np.argmax(far))])
    assign = np.argmin(np.stack([((means - c) ** 2).sum(1) for c in cent]), axis=0)
    banks = None
    for _ in range(rounds):
        banks = []
        for b in range(nbanks):
            px = tiles[assign == b].reshape(-1, 3)
            # An emptied bank keeps a palette (from the whole image) so it stays biddable in
            # the next reassignment rather than dropping out of the running for good.
            banks.append(_quantise_pixels(px if len(px) else tiles.reshape(-1, 3), per_bank))
        nxt = np.argmin(np.stack([_tile_err(tiles, p) for p in banks]), axis=0)
        if np.array_equal(nxt, assign):
            break
        assign = nxt
    # A bank no tile chose is a bank of the budget WASTED -- the exact failure this function
    # exists to fix -- so compact it away rather than reporting a count nothing uses. (It
    # happens: an emptied bank is re-seeded from the whole image and rarely wins a tile back.)
    used = sorted(set(assign.tolist()))
    remap = {b: i for i, b in enumerate(used)}
    return np.array([remap[b] for b in assign.tolist()]), [banks[b] for b in used]


def bank_pack(idx):
    """Greedily pack each 8x8 tile's colour set into banks of <=15 colours.
    GBA BG colour index 0 is TRANSPARENT (it shows the backdrop, which FE8 sets to
    black) -- so each 16-colour bank yields only 15 usable colours; index 0 is
    reserved. Returns (tile_bank[ty][tx], banks[list-of-color-index-lists]). <=8 or raises."""
    sets = {}
    for ty in range(H // 8):
        for tx in range(W // 8):
            sets[(ty, tx)] = frozenset(
                np.unique(idx[ty * 8:ty * 8 + 8, tx * 8:tx * 8 + 8]).tolist())
    # An FE8 BG tile maps to ONE 16-colour bank (index 0 reserved -> 15 usable), so a tile
    # needing >15 colours is unrepresentable -- fail clearly rather than later StopIteration.
    over = [k for k, s in sets.items() if len(s) > 15]
    if over:
        ty, tx = over[0]
        raise ValueError('tile (col %d, row %d) needs %d colours (>15)'
                         % (tx, ty, len(sets[(ty, tx)])))
    banks = []  # each a set of global colour indices
    # place the colour-richest tiles first so sparse tiles slot into existing banks
    for key in sorted(sets, key=lambda k: -len(sets[k])):
        s = sets[key]
        if not any(len(b | s) <= 15 for b in banks):
            banks.append(set())
        # first bank that still fits
        for b in banks:
            if len(b | s) <= 15:
                b |= s
                break
    if len(banks) > 8:
        raise ValueError('%d banks needed (>8)' % len(banks))
    banks = [sorted(b) for b in banks]
    tile_bank = {}
    for key, s in sets.items():
        tile_bank[key] = next(i for i, b in enumerate(banks) if s <= set(b))
    return tile_bank, banks


def main(argv):
    ap = argparse.ArgumentParser()
    ap.add_argument('src')
    ap.add_argument('out')
    ap.add_argument('--colors', type=int, default=128,
                    help='global colour budget before banking (<=128)')
    ap.add_argument('--fit', choices=('crop', 'pad'), default='crop')
    ap.add_argument('--banks', type=int, default=8,
                    help='bank budget when the source needs refitting (<=8)')
    ap.add_argument('--no-trim', action='store_true',
                    help='keep a uniform border instead of stripping it (see '
                         'trim_uniform_border); only for art whose flat mat is intentional')
    args = ap.parse_args(argv)
    # 8 is a hardware/engine ceiling, not a preference: eventscr.c gives a BACG background
    # palettes 8-15 (ApplyPalettes(pal, 8, 8)). A higher budget emits a BG the engine cannot
    # load; >20 dies inside PIL on a negative pad instead of saying so.
    if not 1 <= args.banks <= 8:
        sys.exit('ERROR: --banks must be 1..8 (FE8 gives a BACG background 8 palettes); got %d'
                 % args.banks)

    src = Image.open(args.src)
    if not args.no_trim:
        trimmed = trim_uniform_border(src)
        if trimmed.size != src.size:
            print('%s: trimmed a uniform border %s -> %s (letterbox mat)'
                  % (args.src, src.size, trimmed.size), file=sys.stderr)
        src = trimmed
    rgb = fit_240x160(src, args.fit)
    a = (np.array(rgb) >> 3) << 3                       # GBA 5-bit depth
    q = Image.fromarray(a.astype('uint8')).quantize(
        colors=min(args.colors, 128), method=Image.MEDIANCUT, dither=Image.NONE)
    gpal = q.getpalette()[:min(args.colors, 128) * 3]
    idx = np.array(q)

    # Lossless-if-possible: a clean low-colour source (the Zeldacrafter snow-town) has tiles
    # whose colour sets nest, so the greedy pack reproduces the quantised image EXACTLY. Only
    # when that is impossible do we refit the banks (lossy) -- which keeps every already-shipped
    # BG converting byte-identically.
    try:
        packed = bank_pack(idx)
    except ValueError as e:
        packed, why = None, str(e)

    # Only bank_pack's own "cannot be represented" ValueError may fall through to clustering: a
    # ValueError from the palette build below is a BUG, and swallowing it would silently ship the
    # lossy conversion in place of a good lossless one.
    if packed is not None:
        tile_bank, banks = packed
        how = 'packed'
        # Build the banked palette (N*16 entries) and remap every pixel to bank*16+local.
        # Local index 0 is the reserved transparent slot (kept black); real colours start at 1.
        pal = []
        for b in banks:
            pal += [0, 0, 0]                               # index 0: reserved/transparent
            for ci in b:
                pal += gpal[ci * 3:ci * 3 + 3]
            pal += [0, 0, 0] * (16 - 1 - len(b))           # pad each bank to 16
        out_idx = np.zeros((H, W), dtype=np.uint8)
        for (ty, tx), bank in tile_bank.items():
            local = {ci: j + 1 for j, ci in enumerate(banks[bank])}   # colours -> 1..15
            block = idx[ty * 8:ty * 8 + 8, tx * 8:tx * 8 + 8]
            out_idx[ty * 8:ty * 8 + 8, tx * 8:tx * 8 + 8] = \
                np.vectorize(lambda c: bank * 16 + local[c])(block)
    else:
        how = 'clustered (%s)' % why
        tiles = to_tiles(a)
        assign, banks = bank_cluster(tiles, nbanks=args.banks)
        pal, out_idx = [], np.zeros((H, W), dtype=np.uint8)
        for bp in banks:
            pal += [0, 0, 0]                               # index 0: reserved/transparent
            pal += [int(v) for v in bp.reshape(-1)]
            pal += [0, 0, 0] * (16 - 1 - len(bp))
        tw = W // 8
        for t, bank in enumerate(assign):
            ty, tx = divmod(t, tw)
            block = tiles[t]                               # (64,3)
            d = ((block[:, None, :] - banks[bank][None, :, :]) ** 2).sum(2)
            local = d.argmin(1) + 1                        # nearest bank colour, 1..15
            out_idx[ty * 8:ty * 8 + 8, tx * 8:tx * 8 + 8] = \
                (bank * 16 + local).reshape(8, 8).astype(np.uint8)

    out = Image.new('P', (W, H))
    out.putdata(out_idx.flatten().tolist())
    out.putpalette(pal + [0, 0, 0] * (256 - len(pal) // 3))
    out.save(args.out)
    print('%s -> %s : %d bank(s), %d colours, 240x160, %s'
          % (args.src, args.out, len(banks), sum(len(b) for b in banks), how))
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
