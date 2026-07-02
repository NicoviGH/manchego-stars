#!/usr/bin/env python3
"""Tests for the FEBuilder/FE-Repo tileset import (#40, map_tileset_tool.py).

The converter is thin because the formats align (mapchip_config == the decomp tile
config byte-for-byte; object PNG == 4-bit local indices + a banked 256-color
palette), so the tests pin exactly those assumptions: packing order, palette
quantization, the bank guard -- and the end-to-end oracle: the vendored
cave-interior tileset assembling Cynon's own test map must reproduce the
committed review render (docs/demo/ch03-mineshaft-tileset-demo.png) pixel-exact.
"""
import os
import struct
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import map_tileset_tool as mt  # noqa: E402

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CAVE = os.path.join(REPO, 'campaigns/rime-of-the-frostmaiden/maps/tilesets/cave-interior')
DEMO = os.path.join(REPO, 'docs/demo/ch03-mineshaft-tileset-demo.png')


def _object_png(path, px=None, palette=None):
    """A synthetic 256x256 mode-P object sheet."""
    from PIL import Image
    img = Image.new('P', (256, 256), 0)
    for (x, y), v in (px or {}).items():
        img.putpixel((x, y), v)
    pal = palette or []
    pal = pal + [0] * (768 - len(pal))
    img.putpalette(pal)
    img.save(path)
    return path


class TestConvertObjectPng(unittest.TestCase):
    def test_4bpp_packing_low_nibble_is_left_pixel(self):
        with tempfile.TemporaryDirectory() as d:
            p = _object_png(os.path.join(d, 'o.png'), px={(0, 0): 3, (1, 0): 5})
            gfx, _ = mt.convert_object_png(p)
        self.assertEqual(len(gfx), 32768)          # 1024 tiles x 32 B
        self.assertEqual(gfx[0], 3 | (5 << 4))     # tile 0 row 0: left=3, right=5

    def test_tile_order_is_row_major_across_the_sheet(self):
        with tempfile.TemporaryDirectory() as d:
            # (8,0) = tile 1's top-left; (0,8) = tile 32's top-left.
            p = _object_png(os.path.join(d, 'o.png'), px={(8, 0): 7, (0, 8): 9})
            gfx, _ = mt.convert_object_png(p)
        self.assertEqual(gfx[32] & 0xF, 7)          # tile 1, byte 0, low nibble
        self.assertEqual(gfx[32 * 32] & 0xF, 9)     # tile 32, byte 0, low nibble

    def test_palette_quantizes_rgb888_to_bgr555(self):
        with tempfile.TemporaryDirectory() as d:
            p = _object_png(os.path.join(d, 'o.png'),
                            palette=[255, 128, 8])   # color 0: R=255 G=128 B=8
            _, pal = mt.convert_object_png(p)
        self.assertEqual(len(pal), 320)              # 10 banks x 16 x 2 B
        v = struct.unpack_from('<H', pal, 0)[0]
        self.assertEqual(v & 31, 31)                 # R 255 -> 31
        self.assertEqual((v >> 5) & 31, 16)          # G 128 -> 16
        self.assertEqual((v >> 10) & 31, 1)          # B 8 -> 1

    def test_rejects_pixels_beyond_4bit(self):
        with tempfile.TemporaryDirectory() as d:
            p = _object_png(os.path.join(d, 'o.png'), px={(0, 0): 16})
            with self.assertRaises(SystemExit):
                mt.convert_object_png(p)


class TestImportGuards(unittest.TestCase):
    def test_rejects_wrong_config_size(self):
        with tempfile.TemporaryDirectory() as d:
            cfg = os.path.join(d, 'c.mapchip_config')
            open(cfg, 'wb').write(b'\0' * 100)
            with self.assertRaises(SystemExit):
                mt.import_febuilder_tileset(cfg, 'unused.png',
                                            os.path.join(d, 'out'))

    def test_rejects_tsa_banks_the_gbapal_cannot_carry(self):
        with tempfile.TemporaryDirectory() as d:
            cfg = os.path.join(d, 'c.mapchip_config')
            data = bytearray(mt.CONFIG_SIZE)
            struct.pack_into('<H', data, 0, 12 << 12)   # TSA entry on bank 12
            open(cfg, 'wb').write(bytes(data))
            with self.assertRaises(SystemExit):
                mt.import_febuilder_tileset(cfg, 'unused.png',
                                            os.path.join(d, 'out'))


class TestTmxGrid(unittest.TestCase):
    TMX = ('<?xml version="1.0"?><map><tileset firstgid="1" name="t">'
           '<image source="t.png"/></tileset>'
           '<layer name="L" width="2" height="2"><data>'
           '<tile gid="28"/><tile gid="1"/><tile gid="4"/><tile gid="673"/>'
           '</data></layer></map>')

    def test_grid_shape_and_gid_offset(self):
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, 't.tmx')
            open(p, 'w').write(self.TMX)
            self.assertEqual(mt.tmx_grid(p), [[27, 0], [3, 672]])


class TestVendoredCaveInterior(unittest.TestCase):
    """The committed cave-interior pieces (#40; FE-Repo, Cynon, Gray palette)."""

    def test_piece_sizes(self):
        self.assertEqual(os.path.getsize(os.path.join(CAVE, 'cave-interior.bin')),
                         mt.CONFIG_SIZE)
        self.assertEqual(os.path.getsize(os.path.join(CAVE, 'cave-interior.4bpp')),
                         32768)
        self.assertEqual(os.path.getsize(os.path.join(CAVE, 'cave-interior.gbapal')),
                         320)

    def test_credits_shipped_with_the_asset(self):
        text = open(os.path.join(CAVE, 'CREDITS.txt'), encoding='utf-8').read()
        self.assertIn('Cynon', text)

    def test_test_map_render_matches_committed_review_image(self):
        # End-to-end oracle: converted pieces assembling Cynon's own Test Map
        # must reproduce the render Nicolas reviewed on #23 pixel-for-pixel.
        from PIL import Image
        ts = mt._tileset_from_dir(CAVE)
        grid = mt.tmx_grid(os.path.join(CAVE, 'test-map.tmx'))
        with tempfile.TemporaryDirectory() as d:
            out = mt.render_grid(ts, grid, os.path.join(d, 'r.png'), zoom=2)
            got = Image.open(out).convert('RGB')
            want = Image.open(DEMO).convert('RGB')
            self.assertEqual(got.size, want.size)
            self.assertEqual(list(got.getdata()), list(want.getdata()))


if __name__ == '__main__':
    unittest.main()
