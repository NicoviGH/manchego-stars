#!/usr/bin/env python3
"""Map tileset helpers (#40 task 2): render a GBAFE tileset's metatiles so maps can
be authored by metatile index, and compile a hand-authored layout grid -> the decomp
layout .bin (and matching .json).

A GBAFE tileset is 3 raw pieces (the decomp/FEBuilder format, see maps/README.md):
  <name>.4bpp    1024 8x8 tiles, 4bpp (32768 B)
  <name>.gbapal  160 colors, BGR555 (320 B) = 10 banks x 16
  <name>.bin     tile config: 8192 B TSA (1024 metatiles x 4 tiles x 2 B) + 1024 B terrain

A metatile is 2x2 tiles (16x16 px). A TSA entry is a standard GBA BG map entry:
bits 0-9 tile index, bit 10 hflip, bit 11 vflip, bits 12-15 palette bank.

The layout .bin is: byte width, byte height, then width*height little-endian u16,
each = metatile_index * 4 (verified across vanilla Prologue/Ch1/Ch5X maps).
"""

import json
import os
import struct
import sys

NUM_METATILES = 1024


class Tileset:
    def __init__(self, gfx_path, pal_path, cfg_path):
        self.gfx = open(gfx_path, 'rb').read()
        pal = open(pal_path, 'rb').read()
        self.cfg = open(cfg_path, 'rb').read()
        self.palettes = [[self._color(pal, bank * 16 + c) for c in range(16)]
                         for bank in range(10)]

    @staticmethod
    def _color(pal, i):
        v = pal[i * 2] | (pal[i * 2 + 1] << 8)
        return ((v & 31) << 3, ((v >> 5) & 31) << 3, ((v >> 10) & 31) << 3)

    def _tile_px(self, tidx, bank):
        """64 RGB pixels (row-major) of one 8x8 4bpp tile under palette `bank`."""
        base = tidx * 32
        pal = self.palettes[bank if bank < 10 else 0]
        px = []
        for row in range(8):
            for b in range(4):
                byte = self.gfx[base + row * 4 + b]
                px.append(pal[byte & 0xF])
                px.append(pal[byte >> 4])
        return px

    def metatile_image(self, m):
        """16x16 RGB image of metatile `m` (2x2 tiles, order TL,TR,BL,BR)."""
        from PIL import Image
        img = Image.new('RGB', (16, 16))
        for sub in range(4):
            entry = struct.unpack_from('<H', self.cfg, m * 8 + sub * 2)[0]
            tidx = entry & 0x3FF
            hflip = (entry >> 10) & 1
            vflip = (entry >> 11) & 1
            bank = (entry >> 12) & 0xF
            px = self._tile_px(tidx, bank)
            ox, oy = (sub % 2) * 8, (sub // 2) * 8
            for yy in range(8):
                for xx in range(8):
                    sx = 7 - xx if hflip else xx
                    sy = 7 - yy if vflip else yy
                    img.putpixel((ox + xx, oy + yy), px[sy * 8 + sx])
        return img

    def terrain(self, m):
        """The metatile's terrain-type byte (TSA is 8192 B, terrain follows)."""
        return self.cfg[8192 + m]

    def atlas(self, out_path, zoom=2, label=False):
        """Render all 1024 metatiles to a 32x32 grid PNG. label=True overlays the
        metatile index every 4th cell (legible authoring reference)."""
        from PIL import Image, ImageDraw
        cell = 16 * zoom
        img = Image.new('RGB', (32 * cell, 32 * cell), (255, 0, 255))
        for m in range(NUM_METATILES):
            mt = self.metatile_image(m).resize((cell, cell), Image.NEAREST)
            img.paste(mt, ((m % 32) * cell, (m // 32) * cell))
        if label:
            d = ImageDraw.Draw(img)
            for m in range(0, NUM_METATILES, 4):
                d.text(((m % 32) * cell + 1, (m // 32) * cell + 1), str(m),
                       fill=(255, 255, 0))
        img.save(out_path)
        return out_path

    def uniform_candidates(self, min_bright=170, top=20):
        """Most-uniform bright metatiles (low color variance) -> plain ground tiles."""
        import statistics
        out = []
        for m in range(NUM_METATILES):
            px = []
            for sub in range(4):
                e = struct.unpack_from('<H', self.cfg, m * 8 + sub * 2)[0]
                px += self._tile_px(e & 0x3FF, (e >> 12) & 0xF)
            r = [p[0] for p in px]
            g = [p[1] for p in px]
            b = [p[2] for p in px]
            bright = (sum(r) + sum(g) + sum(b)) / (len(px) * 3)
            if bright < min_bright:
                continue
            var = statistics.pvariance(r) + statistics.pvariance(g) + statistics.pvariance(b)
            out.append((round(var, 1), round(bright, 1), m))
        out.sort()
        return out[:top]


def compile_layout(grid, out_bin, map_id):
    """grid = list of rows of metatile indices -> decomp FEBuilder .mar + .json.

    The build runs this .mar through scripts/mar_to_map.py (Makefile %.bin: %.mar),
    which prepends width/height from the .json and emits each tile value >> 3. FE8
    then reads a .bin tile as metatile = value >> 2 (bmmap.c GetTrueTerrainAt). So the
    .mar must carry NO header (mar_to_map adds it) and store each tile as
    metatile_index << 5, so >>3 yields the engine's index<<2. (Writing index*4 + a
    header here scrambles the map: mar_to_map eats the header as a tile and halves the
    magnitudes.)"""
    h = len(grid)
    w = len(grid[0])
    if any(len(row) != w for row in grid):
        sys.exit('ERROR: ragged grid (rows differ in width)')
    if w > 255 or h > 255:
        sys.exit('ERROR: map %dx%d exceeds 255' % (w, h))
    data = bytearray()
    for row in grid:
        for m in row:
            data += struct.pack('<H', m << 5)
    with open(out_bin, 'wb') as f:
        f.write(data)
    with open(os.path.splitext(out_bin)[0] + '.json', 'w') as f:
        json.dump({'id': map_id, 'width': w, 'height': h}, f)
    return out_bin


def _tileset_from_dir(d):
    name = os.path.basename(d.rstrip('/'))
    return Tileset(os.path.join(d, name + '.4bpp'),
                   os.path.join(d, name + '.gbapal'),
                   os.path.join(d, name + '.bin'))


if __name__ == '__main__':
    import argparse
    ap = argparse.ArgumentParser(description=__doc__)
    sub = ap.add_subparsers(dest='cmd', required=True)
    a = sub.add_parser('atlas', help='render the metatile atlas')
    a.add_argument('tileset_dir')
    a.add_argument('out')
    a.add_argument('--label', action='store_true')
    a.add_argument('--zoom', type=int, default=2)
    c = sub.add_parser('candidates', help='list uniform ground-tile candidates')
    c.add_argument('tileset_dir')
    args = ap.parse_args()
    ts = _tileset_from_dir(args.tileset_dir)
    if args.cmd == 'atlas':
        print(ts.atlas(args.out, zoom=args.zoom, label=args.label))
    elif args.cmd == 'candidates':
        for var, bright, m in ts.uniform_candidates():
            print('idx %4d (r%d,c%d) var=%-8s bright=%-6s terrain=0x%02x'
                  % (m, m // 32, m % 32, var, bright, ts.terrain(m)))
