#!/usr/bin/env python3
"""Render a vanilla FE8 compressed BG asset (image + TSA + palette) straight out of
`baserom.gba` to a PNG, without building or booting anything.

Why this exists: palette work on a vanilla backdrop used to cost a full ROM build plus an
mGBA playtest run per colour guess -- the single most expensive loop in this repo
(`docs/decisions.md` -> "Playtest runs are the most expensive thing in this repo"). Every
asset we recolour is a plain `.incbin` from the base ROM at a fixed offset, so the exact
pixels the GBA would draw can be reproduced offline in milliseconds. Iterate here; spend the
one in-engine run on confirming the answer, not finding it.

It also answers the question a palette edit always has to answer first: *which palette
index owns this thing, and does anything else share it?* `--index-map` and `--isolate`
report that from the real TSA rather than from guesswork.

    # what vanilla's arena coliseum actually looks like, phase A
    python3 tools/rom_bg_preview.py arena_battle --out /tmp/vanilla.png

    # which bank/index pairs cover the bottom strip (the fighting floor)?
    python3 tools/rom_bg_preview.py arena_battle --index-map --region 0,17,46,20

    # paint every pixel using bank 8 index 5 magenta, leave the rest alone
    python3 tools/rom_bg_preview.py arena_battle --isolate 8:5 --out /tmp/iso.png
"""

import argparse
import collections
import os
import sys

from PIL import Image

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BASEROM = os.path.join(REPO, 'fireemblem8u', 'baserom.gba')

# Vanilla assets we know how to draw. Offsets/lengths are the `.incbin` arguments in the
# decomp's own data files -- the authoritative source, not measured or guessed.
#   img/tsa: (rom_offset, byte_length), LZ77-compressed
#   pals:    {name: rom_offset}, raw BGR555, 0x80 bytes = four 16-colour banks
#   base_bank: the hardware palette bank the asset's FIRST bank lands in. The TSA's palette
#              nibble is RELATIVE (0..3 here) -- the engine chooses where the four banks are
#              copied -- so this is what a live-palette-RAM address is counted from, not what
#              the TSA stores. Getting this backwards indexes off the end of the palette.
ASSETS = {
    # data/banim-efxlvupfx.s -- the Arena coliseum drawn behind an arena fight. Owns the
    # visible floor as well as the stands; Arena mode skips the normal terrain platform
    # (EfxClearScreenFx clears BG2 when GetBattleAnimArenaFlag()), so nothing else paints here.
    # src/banim-ekrarena.c copies the live phase to gPaletteBuffer + 0x60 -> banks 6..9.
    'arena_battle': {
        'img': (0x5BC188, 0x266C),
        'tsa': (0x5BE7F4, 0x7A0),
        'pals': {'A': 0x5BEF94, 'B': 0x5BF014, 'C': 0x5BF094},
        'base_bank': 6,
    },
    # data/data_9A31F8.s -- the coliseum EXTERIOR behind the Arena welcome/wager UI.
    # src/uiarena.c: Decompress(gGfx_ArenaBuildingFront, ...) + ApplyPalettes(..., 0xC, 4),
    # so its four banks land at hardware BG banks 12..15. Single palette, no cycle.
    # Its TSA is NOT compressed: CallARM_FillTileRect takes a raw blob whose first two bytes
    # are (width - 1, height - 1) -- 0x1D, 0x13 here, i.e. exactly one 30x20 screen.
    'arena_front': {
        'img': (0x9A8F94, 0x2BDC),
        'tsa': (0x9ABB70, 0x4B4),
        'tsa_format': 'filltilerect',
        'pals': {'A': 0x9AC024},
        'base_bank': 12,
    },
}


def lz77_decompress(data, offset=0):
    """Decode a GBA BIOS LZ77 (type 0x10) stream. Header: 0x10, then a 24-bit LE size."""
    if data[offset] != 0x10:
        sys.exit('ERROR: not an LZ77 stream at 0x%X (first byte 0x%02X)'
                 % (offset, data[offset]))
    size = data[offset + 1] | (data[offset + 2] << 8) | (data[offset + 3] << 16)
    src = offset + 4
    out = bytearray()
    while len(out) < size:
        flags = data[src]
        src += 1
        for bit in range(8):
            if len(out) >= size:
                break
            if flags & (0x80 >> bit):
                # Back-reference: 4-bit length-3, 12-bit displacement-1.
                b0, b1 = data[src], data[src + 1]
                src += 2
                length = (b0 >> 4) + 3
                disp = (((b0 & 0xF) << 8) | b1) + 1
                start = len(out) - disp
                if start < 0:
                    sys.exit('ERROR: LZ77 back-reference before start of output')
                for i in range(length):
                    out.append(out[start + i])          # may overlap; byte-at-a-time is correct
            else:
                out.append(data[src])
                src += 1
    return bytes(out[:size])


def bgr555_to_rgb(word):
    r, g, b = word & 0x1F, (word >> 5) & 0x1F, (word >> 10) & 0x1F
    return (r << 3) | (r >> 2), (g << 3) | (g >> 2), (b << 3) | (b >> 2)


def read_palette(rom, offset, count=64):
    return [rom[offset + i * 2] | (rom[offset + i * 2 + 1] << 8) for i in range(count)]


def tile_pixels(tiles, index):
    """The 8x8 4bpp tile at `index` as 64 palette indices, row-major."""
    base = index * 32
    px = []
    for byte in tiles[base:base + 32]:
        px.append(byte & 0xF)                            # low nibble is the LEFT pixel
        px.append(byte >> 4)
    return px


def tsa_entries(tsa):
    return [tsa[i] | (tsa[i + 1] << 8) for i in range(0, len(tsa), 2)]


def infer_dimensions(count, width=None):
    """A TSA is a flat u16 run; the decomp does not carry its shape. Prefer an explicit
    --width; otherwise pick the factorisation closest to a GBA screen's 30x20."""
    if width:
        if count % width:
            sys.exit('ERROR: %d TSA entries do not divide by width %d' % (count, width))
        return width, count // width
    # A GBA screen is 20 tiles tall and these backdrops fill it, so height is the reliable
    # signal; width varies because the engine pans across a wider image than it shows.
    best = None
    for w in range(8, 65):
        if count % w:
            continue
        h = count // w
        if h < 4 or h > 64:
            continue
        score = abs(h - 20) * 4 + abs(w - 30)
        if best is None or score < best[0]:
            best = (score, w, h)
    if best is None:
        sys.exit('ERROR: cannot infer a plausible shape for %d TSA entries; pass --width'
                 % count)
    return best[1], best[2]


def decode(asset, phase='A'):
    """-> (entries, cols, rows, tiles, palette_words, base_bank) for one asset+phase."""
    spec = ASSETS[asset]
    with open(BASEROM, 'rb') as f:
        rom = f.read()
    img_off, _ = spec['img']
    tsa_off, tsa_len = spec['tsa']
    tiles = lz77_decompress(rom, img_off)
    if spec.get('tsa_format') == 'filltilerect':
        # Raw, uncompressed, and read by TmApplyTsa (asm/arm.s) -- whose C reference settles
        # two things a guess gets wrong. Its loops are INCLUSIVE (`for h = height; h >= 0`),
        # so the stored bytes are width-1 and height-1; and it starts at
        # TILEMAP_LOCATED(tilemap, height, 0) and walks UP a row at a time
        # (`dst - width - 1 - 0x20`), so the TSA's FIRST row is the screen's BOTTOM row.
        cols = rom[tsa_off] + 1
        rows = rom[tsa_off + 1] + 1
        flat = tsa_entries(rom[tsa_off + 2:tsa_off + 2 + cols * rows * 2])
        entries = [entry for r in reversed(range(rows))
                   for entry in flat[r * cols:(r + 1) * cols]]
        if phase not in spec['pals']:
            sys.exit('ERROR: %s has no palette phase %r (have %s)'
                     % (asset, phase, ', '.join(sorted(spec['pals']))))
        return entries, tiles, read_palette(rom, spec['pals'][phase]), spec['base_bank'], \
            (cols, rows)
    tsa = lz77_decompress(rom, tsa_off)
    shape = None
    if phase not in spec['pals']:
        sys.exit('ERROR: %s has no palette phase %r (have %s)'
                 % (asset, phase, ', '.join(sorted(spec['pals']))))
    palette = read_palette(rom, spec['pals'][phase])
    return tsa_entries(tsa), tiles, palette, spec['base_bank'], shape


def render(entries, cols, rows, tiles, palette, base_bank, recolor=None):
    """Paint the TSA to an RGB image. `recolor` maps (bank, index) -> (r, g, b)."""
    im = Image.new('RGB', (cols * 8, rows * 8))
    px = im.load()
    for cell, entry in enumerate(entries[:cols * rows]):
        tile = entry & 0x3FF
        hflip, vflip = bool(entry & 0x400), bool(entry & 0x800)
        bank = (entry >> 12) & 0xF
        data = tile_pixels(tiles, tile)
        ox, oy = (cell % cols) * 8, (cell // cols) * 8
        for y in range(8):
            sy = 7 - y if vflip else y
            for x in range(8):
                sx = 7 - x if hflip else x
                idx = data[sy * 8 + sx]
                key = (base_bank + bank, idx)          # report in HARDWARE bank terms
                if recolor and key in recolor:
                    px[ox + x, oy + y] = recolor[key]
                else:
                    px[ox + x, oy + y] = bgr555_to_rgb(palette[bank * 16 + idx])
    return im


def index_map(entries, cols, rows, tiles, region=None):
    """Count pixels per (bank, index), optionally within a tile-space rectangle."""
    counts = collections.Counter()
    x0, y0, x1, y1 = region or (0, 0, cols, rows)
    for cell, entry in enumerate(entries[:cols * rows]):
        cx, cy = cell % cols, cell // cols
        if not (x0 <= cx < x1 and y0 <= cy < y1):
            continue
        bank = (entry >> 12) & 0xF
        for idx in tile_pixels(tiles, entry & 0x3FF):
            counts[(bank, idx)] += 1
    return counts


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('asset', choices=sorted(ASSETS))
    ap.add_argument('--phase', default='A', help='palette phase (default A)')
    ap.add_argument('--width', type=int, help='TSA width in tiles, if inference is wrong')
    ap.add_argument('--out', help='write a PNG here')
    ap.add_argument('--scale', type=int, default=1)
    ap.add_argument('--index-map', action='store_true',
                    help='report pixel counts per (bank, index)')
    ap.add_argument('--region', help='tile-space x0,y0,x1,y1 to restrict --index-map')
    ap.add_argument('--isolate', action='append', default=[],
                    help='BANK:INDEX to paint magenta, to see exactly what it owns')
    args = ap.parse_args(argv)

    entries, tiles, palette, base_bank, shape = decode(args.asset, args.phase)
    cols, rows = shape if shape and not args.width else infer_dimensions(len(entries), args.width)
    print('%s phase %s: %d tiles, %d TSA entries -> %dx%d tiles (%dx%d px)'
          % (args.asset, args.phase, len(tiles) // 32, len(entries), cols, rows,
             cols * 8, rows * 8))

    if args.index_map:
        region = tuple(int(v) for v in args.region.split(',')) if args.region else None
        counts = index_map(entries, cols, rows, tiles, region)
        total = sum(counts.values()) or 1
        print('  bank idx     pixels   share   colour')
        for (bank, idx), n in counts.most_common():
            word = palette[bank * 16 + idx]
            print('  %4d %3d %10d  %5.1f%%   #%02X%02X%02X'
                  % (base_bank + bank, idx, n, 100.0 * n / total,
                     *bgr555_to_rgb(word)))

    recolor = {}
    for spec in args.isolate:
        bank, idx = (int(v) for v in spec.split(':'))
        recolor[(bank, idx)] = (255, 0, 255)

    if args.out:
        im = render(entries, cols, rows, tiles, palette, base_bank, recolor or None)
        if args.scale > 1:
            im = im.resize((im.width * args.scale, im.height * args.scale),
                           Image.Resampling.NEAREST)
        im.save(args.out)
        print('  wrote %s' % args.out)
    return 0


if __name__ == '__main__':
    sys.exit(main())
