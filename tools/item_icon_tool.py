#!/usr/bin/env python3
"""Item-icon helpers for Manchego Stars.

FE8 item icons are 16x16 4bpp tiles concatenated in graphics/item_icon/, indexed by
gItemData[].iconId, all sharing one 16-colour palette (item_icon_palette.agbpal,
bank 0 = indices 0-15). We don't hand-draw: this tool authors an icon as a 16x16
palette-index grid and packs it into FE8's 4bpp tile layout, and renders any .4bpp
back to a PNG (scaled) for offline review. Build wiring injects the result over the
target icon's .4bpp (campaign content, restored from git each build).

Layout: a 16x16 icon = 4 8x8 tiles in order TL, TR, BL, BR; within a tile, 8 rows of
8 px, each byte = two pixels (low nibble = left). cf. data/data_item_icon.s.
"""
import os
import struct
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PAL = os.path.join(REPO, 'fireemblem8u', 'graphics', 'item_icon',
                   'item_icon_palette.agbpal')


def load_palette(path=PAL):
    """First 16 BGR555 entries (bank 0) -> list of (r,g,b)."""
    raw = open(path, 'rb').read()
    cols = []
    for i in range(0, 32, 2):
        v = struct.unpack('<H', raw[i:i + 2])[0]
        cols.append(((v & 31) * 255 // 31,
                     ((v >> 5) & 31) * 255 // 31,
                     ((v >> 10) & 31) * 255 // 31))
    return cols


def pack_4bpp(grid):
    """16x16 list-of-rows of palette indices (0-15) -> 128-byte FE8 4bpp blob."""
    assert len(grid) == 16 and all(len(r) == 16 for r in grid), 'grid must be 16x16'
    out = bytearray()
    for ty in (0, 1):
        for tx in (0, 1):
            for y in range(8):
                row = grid[ty * 8 + y]
                for x in range(0, 8, 2):
                    lo = row[tx * 8 + x] & 0xF
                    hi = row[tx * 8 + x + 1] & 0xF
                    out.append(lo | (hi << 4))
    return bytes(out)


def unpack_4bpp(blob):
    """128-byte FE8 4bpp blob -> 16x16 grid of palette indices."""
    grid = [[0] * 16 for _ in range(16)]
    p = 0
    for ty in (0, 1):
        for tx in (0, 1):
            for y in range(8):
                for x in range(0, 8, 2):
                    b = blob[p]; p += 1
                    grid[ty * 8 + y][tx * 8 + x] = b & 0xF
                    grid[ty * 8 + y][tx * 8 + x + 1] = (b >> 4) & 0xF
    return grid


def write_indexed_png(grid, out_png):
    """Write a 16x16 mode-P PNG with FE8's shared 16-colour item palette (index 0 =
    background, as gbagfx expects). This is the build-source form: the decomp's
    `%.4bpp: %.png` rule (gbagfx) converts it to 4bpp at compile time."""
    from PIL import Image
    pal = load_palette()
    flat = []
    for c in pal:
        flat += list(c)
    flat += [0, 0, 0] * (256 - len(pal))
    img = Image.new('P', (16, 16))
    img.putpalette(flat)
    for y in range(16):
        for x in range(16):
            img.putpixel((x, y), grid[y][x])
    img.save(out_png)
    return out_png


def render(blob, out_png, scale=16):
    """Decode a .4bpp icon to a scaled PNG (index 0 = transparent)."""
    from PIL import Image
    pal = load_palette()
    grid = unpack_4bpp(blob)
    img = Image.new('RGBA', (16, 16))
    for y in range(16):
        for x in range(16):
            idx = grid[y][x]
            img.putpixel((x, y), (0, 0, 0, 0) if idx == 0 else pal[idx] + (255,))
    img.resize((16 * scale, 16 * scale), Image.NEAREST).save(out_png)
    return out_png


# Palette-index legend (bank 0): 0 transparent, 1 white, 7 vivid blue, 8 grey-blue
# (shadow), 9 light lavender-blue (sheen), 10 teal-green (leaf/stem), 4 dark green
# (leaf edge), 14 very-dark (rim + calyx button).
def blueberry_grid():
    """The shipped Goodberry: a blue berry with a dark five-point calyx button, a green
    branch rooted in the button's centre, and a single rounded leaf to the left
    (design "L2", chosen 2026-06-16; iterated with Nicolas)."""
    B, RIM = 7, 14            # body, dark rim
    SHADOW, SHEEN = 8, 9      # lower-right shadow band, low-left sheen
    STEM, LEAF, LEAFDK = 10, 10, 4   # green stem + leaf, dark-green leaf edge
    BUTTON = 14               # calyx star (same dark as the rim)
    g = [[0] * 16 for _ in range(16)]
    cx, cy, r = 7.5, 9.0, 6.2
    for y in range(16):
        for x in range(16):
            d = ((x - cx) ** 2 + (y - cy) ** 2) ** 0.5
            if d <= r - 1.4:
                g[y][x] = B
            elif d <= r:
                g[y][x] = RIM
    for y in range(16):
        for x in range(16):
            if g[y][x] != B:
                continue
            d = ((x - cx) ** 2 + (y - cy) ** 2) ** 0.5
            if (x - cx) + (y - cy) > 4.6 and d > r - 2.4:
                g[y][x] = SHADOW
    for (x, y) in [(4, 10), (5, 11), (4, 11)]:
        if g[y][x] == B:
            g[y][x] = SHEEN
    # calyx: dark five-point star on the upper-front face
    for (x, y) in [(7, 4), (7, 5), (6, 5), (8, 5), (5, 6), (6, 6), (7, 6),
                   (8, 6), (9, 6), (6, 7), (8, 7), (7, 7)]:
        g[y][x] = BUTTON
    # green branch rooted in the button's centre, running up
    for (x, y) in [(7, 6), (7, 5), (7, 4), (7, 3), (7, 2)]:
        g[y][x] = STEM
    # single rounded leaf to the left
    for (x, y, c) in [(6, 2, LEAF), (5, 2, LEAF), (6, 1, LEAF), (5, 1, LEAFDK)]:
        g[y][x] = c
    return g


def main():
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument('cmd', choices=['render', 'gen-blueberry'])
    ap.add_argument('--in', dest='inp')
    ap.add_argument('--out', required=True)
    ap.add_argument('--png')
    a = ap.parse_args()
    if a.cmd == 'render':
        render(open(a.inp, 'rb').read(), a.out)
    elif a.cmd == 'gen-blueberry':
        grid = blueberry_grid()
        if a.out.endswith('.png'):
            write_indexed_png(grid, a.out)        # build-source indexed PNG
        else:
            with open(a.out, 'wb') as f:
                f.write(pack_4bpp(grid))          # raw 4bpp (review/debug)
        if a.png:
            render(pack_4bpp(grid), a.png)        # scaled RGBA preview
    print('wrote', a.out)


if __name__ == '__main__':
    main()
