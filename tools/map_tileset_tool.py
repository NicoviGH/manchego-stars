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


def compile_layout(grid, out_bin, map_id, tileset='snowy-bern'):
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
        json.dump({'id': map_id, 'width': w, 'height': h, 'tileset': tileset}, f)
    return out_bin


def _tileset_from_dir(d):
    name = os.path.basename(d.rstrip('/'))
    return Tileset(os.path.join(d, name + '.4bpp'),
                   os.path.join(d, name + '.gbapal'),
                   os.path.join(d, name + '.bin'))


# ── FEBuilder/FE-Repo tileset import (#40) ────────────────────────────────────────

CONFIG_SIZE = 9216          # 8192 B TSA + 1024 B terrain -- byte-identical to ours
OBJECT_SHEET_PX = 256       # object PNG: 256x256 mode-P, 4-bit local pixel indices
PALETTE_BANKS = 10          # FE8 map BG palette: 10 banks x 16 (the .gbapal 320 B)


def convert_object_png(png_path):
    """FE-Repo object PNG -> (raw 4bpp tile sheet bytes, .gbapal bytes).

    The PNG is 256x256 mode-P: pixel values are the 4-bit within-bank color index
    (0-15); the BANK for each on-screen use comes from the TSA entry's bits 12-15,
    and the PNG's 256-color palette is those banks stacked 16-at-a-time. So the
    sheet packs straight to 4bpp (low nibble = left pixel, GBA order) and the
    palette's first 10 banks (160 colors) quantize RGB888 -> BGR555."""
    from PIL import Image
    img = Image.open(png_path)
    if img.mode != 'P' or img.size != (OBJECT_SHEET_PX, OBJECT_SHEET_PX):
        sys.exit('ERROR: %s must be a %dx%d indexed (mode-P) PNG, got %s %s'
                 % (png_path, OBJECT_SHEET_PX, OBJECT_SHEET_PX, img.mode, img.size))
    px = list(img.getdata())
    if max(px) > 15:
        sys.exit('ERROR: %s has pixel indices > 15 -- not 4-bit local indices '
                 '(re-export from FEBuilder/usenti in the banked mode-P form)'
                 % png_path)
    gfx = bytearray()
    tiles_per_row = OBJECT_SHEET_PX // 8
    for t in range(tiles_per_row * tiles_per_row):
        tx, ty = (t % tiles_per_row) * 8, (t // tiles_per_row) * 8
        for row in range(8):
            base = (ty + row) * OBJECT_SHEET_PX + tx
            for b in range(4):
                left, right = px[base + b * 2], px[base + b * 2 + 1]
                gfx.append(left | (right << 4))
    rgb = img.getpalette()
    rgb = rgb + [0] * (PALETTE_BANKS * 16 * 3 - len(rgb))   # PIL trims short palettes
    pal = bytearray()
    for c in range(PALETTE_BANKS * 16):
        r, g, b = rgb[c * 3], rgb[c * 3 + 1], rgb[c * 3 + 2]
        pal += struct.pack('<H', (r >> 3) | ((g >> 3) << 5) | ((b >> 3) << 10))
    return bytes(gfx), bytes(pal)


def import_febuilder_tileset(config_path, object_png, out_dir):
    """Vendor a community tileset (FEBuilder/FE-Repo format) as decomp-format
    pieces under maps/tilesets/<name>/ (the shape _tileset_from_dir and
    build_campaign's tileset injection consume).

    The .mapchip_config is byte-identical to the decomp tile config (verified on
    Snowy Bern #41 and Cynon's Mineshaft #40) -- copied through. The object PNG
    converts via convert_object_png. Rejects a config whose TSA references a
    palette bank the 10-bank .gbapal can't carry."""
    cfg = open(config_path, 'rb').read()
    if len(cfg) != CONFIG_SIZE:
        sys.exit('ERROR: %s is %d B; a mapchip_config is exactly %d (8192 TSA + '
                 '1024 terrain)' % (config_path, len(cfg), CONFIG_SIZE))
    banks = {struct.unpack_from('<H', cfg, i * 2)[0] >> 12 for i in range(4096)}
    if max(banks) >= PALETTE_BANKS:
        sys.exit('ERROR: %s TSA uses palette bank(s) %s; the FE8 map BG palette '
                 'carries only banks 0-%d' % (config_path,
                                              sorted(b for b in banks
                                                     if b >= PALETTE_BANKS),
                                              PALETTE_BANKS - 1))
    gfx, pal = convert_object_png(object_png)
    name = os.path.basename(out_dir.rstrip('/'))
    os.makedirs(out_dir, exist_ok=True)
    for ext, data in (('bin', cfg), ('4bpp', gfx), ('gbapal', pal)):
        with open(os.path.join(out_dir, '%s.%s' % (name, ext)), 'wb') as f:
            f.write(data)
    return out_dir


def tmx_grid(tmx_path):
    """Metatile grid of a Tiled .tmx (the FE-Repo test-map format: 16px tiles,
    one layer, <tile gid=N/> entries, firstgid=1 -> metatile = gid - 1)."""
    import xml.etree.ElementTree as ET
    root = ET.parse(tmx_path).getroot()
    layer = root.find('layer')
    w, h = int(layer.get('width')), int(layer.get('height'))
    first = int(root.find('tileset').get('firstgid'))
    gids = [int(t.get('gid', first)) for t in layer.find('data').iter('tile')]
    if len(gids) != w * h:
        sys.exit('ERROR: %s layer holds %d tiles; expected %dx%d'
                 % (tmx_path, len(gids), w, h))
    empty = gids.count(0)
    if empty:
        # Tiled writes gid="0" for an EMPTY cell (its map-change layers are full of
        # them); an FE map layer has no empty -- passing it through would index
        # metatile -1 (renders garbage, crashes compile_layout).
        sys.exit('ERROR: %s main layer has %d empty cells (gid 0) -- fill the '
                 'layer before importing' % (tmx_path, empty))
    return [[gids[y * w + x] - first for x in range(w)] for y in range(h)]


def render_grid(ts, grid, out_png, zoom=2):
    """Assemble a metatile grid on tileset `ts` into a PNG (the in-engine look,
    sans sprites) -- the load-test-on-paper for a vendored tileset."""
    from PIL import Image
    cell = 16 * zoom
    h, w = len(grid), len(grid[0])
    img = Image.new('RGB', (w * cell, h * cell))
    for y, row in enumerate(grid):
        for x, m in enumerate(row):
            img.paste(ts.metatile_image(m).resize((cell, cell), Image.NEAREST),
                      (x * cell, y * cell))
    img.save(out_png)
    return out_png


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
    i = sub.add_parser('import', help='vendor an FEBuilder/FE-Repo tileset '
                       '(mapchip_config + object PNG -> decomp pieces)')
    i.add_argument('config', help='the .mapchip_config (9216 B)')
    i.add_argument('object_png', help='the 256x256 mode-P object-palette PNG')
    i.add_argument('out_dir', help='maps/tilesets/<name>/ (dir name = piece stem)')
    r = sub.add_parser('render-tmx', help='assemble a Tiled .tmx on a vendored '
                       'tileset -> PNG (verifies the import end-to-end)')
    r.add_argument('tileset_dir')
    r.add_argument('tmx')
    r.add_argument('out')
    r.add_argument('--zoom', type=int, default=2)
    args = ap.parse_args()
    if args.cmd == 'import':
        print(import_febuilder_tileset(args.config, args.object_png, args.out_dir))
    elif args.cmd == 'render-tmx':
        ts = _tileset_from_dir(args.tileset_dir)
        print(render_grid(ts, tmx_grid(args.tmx), args.out, zoom=args.zoom))
    else:
        ts = _tileset_from_dir(args.tileset_dir)
        if args.cmd == 'atlas':
            print(ts.atlas(args.out, zoom=args.zoom, label=args.label))
        elif args.cmd == 'candidates':
            for var, bright, m in ts.uniform_candidates():
                print('idx %4d (r%d,c%d) var=%-8s bright=%-6s terrain=0x%02x'
                      % (m, m // 32, m % 32, var, bright, ts.terrain(m)))
