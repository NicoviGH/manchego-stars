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
bank untouched; a busier CG spreads across banks. >8 banks is a hard error (the
source is too colour-dense per region for FE8's BG format -- reduce it first).

Usage: tools/bg_to_fe8.py <src-image> <out.png> [--colors N] [--fit crop|pad]
"""
import argparse
import sys
import numpy as np
from PIL import Image

W, H = 240, 160


def fit_240x160(im, mode):
    """Center the source in a 240x160 frame: 'crop' fills (cover), 'pad' letterboxes."""
    im = im.convert('RGB')
    sw, sh = im.size
    if (sw, sh) == (W, H):
        return im
    scale = max(W / sw, H / sh) if mode == 'crop' else min(W / sw, H / sh)
    nw, nh = max(1, round(sw * scale)), max(1, round(sh * scale))
    im = im.resize((nw, nh), Image.LANCZOS)
    canvas = Image.new('RGB', (W, H), (0, 0, 0))
    canvas.paste(im, ((W - nw) // 2, (H - nh) // 2))
    return canvas


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
        sys.exit('ERROR: %d banks needed (>8). Source too colour-dense per 8x8 '
                 'region for an FE8 BG; pre-reduce it.' % len(banks))
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
    args = ap.parse_args(argv)

    rgb = fit_240x160(Image.open(args.src), args.fit)
    a = (np.array(rgb) >> 3) << 3                       # GBA 5-bit depth
    q = Image.fromarray(a.astype('uint8')).quantize(
        colors=min(args.colors, 128), method=Image.MEDIANCUT, dither=Image.NONE)
    gpal = q.getpalette()[:min(args.colors, 128) * 3]
    idx = np.array(q)

    tile_bank, banks = bank_pack(idx)

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

    out = Image.new('P', (W, H))
    out.putdata(out_idx.flatten().tolist())
    out.putpalette(pal + [0, 0, 0] * (256 - len(pal) // 3))
    out.save(args.out)
    print('%s -> %s : %d bank(s), %d colours, 240x160'
          % (args.src, args.out, len(banks), sum(len(b) for b in banks)))
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
