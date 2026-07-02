#!/usr/bin/env python3
"""Tests for the nat-20 crit flourish pipeline (#11).

The ROM side is a campaign-agnostic engine hook (engine_hooks.
_inject_crit_d20_flourish, guarded by check_engine_guards_present); these tests
pin the ASSET pipeline: the stored-form GBA LZ77 container, the 4bpp/palette/TSA
conversion, and a full decode-back roundtrip proving the injected bytes redraw
the source art pixel-exactly.
"""
import os
import struct
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import build_campaign as bc  # noqa: E402

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
D20 = os.path.join(REPO, 'campaigns/rime-of-the-frostmaiden/battle_anims/d20-crit.png')


def unlz(d):
    """Reference GBA LZ77 decoder (mirrors LZ77UnCompWram)."""
    size = struct.unpack('<I', d[:4])[0] >> 8
    out = bytearray()
    i = 4
    while len(out) < size:
        flags = d[i]
        i += 1
        for bit in range(8):
            if len(out) >= size:
                break
            if flags & (0x80 >> bit):
                b1, b2 = d[i], d[i + 1]
                i += 2
                cnt, off = (b1 >> 4) + 3, ((b1 & 0xF) << 8 | b2) + 1
                for _ in range(cnt):
                    out.append(out[-off])
            else:
                out.append(d[i])
                i += 1
    return bytes(out)


class TestStoredLz(unittest.TestCase):
    def test_roundtrip(self):
        for payload in (b'', b'x', bytes(range(256)) * 9):
            self.assertEqual(unlz(bc._gba_lz77_stored(payload)), payload)


class TestFlourishBins(unittest.TestCase):
    def setUp(self):
        self.img_lz, self.pal, self.tsa_lz = bc._crit_flourish_bins(D20)
        self.img = unlz(self.img_lz)
        self.tsa = unlz(self.tsa_lz)

    def test_shapes(self):
        self.assertEqual(len(self.pal), 32)              # 16 BGR555 colors
        self.assertEqual(len(self.tsa), 30 * 20 * 2)     # full BG1 map
        self.assertEqual(len(self.img) % 32, 0)          # whole 4bpp tiles
        self.assertEqual(self.img[:32], bytes(32))       # tile 0 = blank screen

    def test_tsa_references_only_real_tiles(self):
        ntiles = len(self.img) // 32
        entries = struct.unpack('<%dH' % (30 * 20), self.tsa)
        self.assertTrue(all(e < ntiles for e in entries))
        self.assertTrue(any(e for e in entries))         # the die is actually placed

    def test_decode_roundtrip_matches_source_art(self):
        # Redraw the 240x160 overlay from the injected bytes and compare the die
        # region against the source PNG (transparent -> index 0 either way).
        from PIL import Image
        src = Image.open(D20).convert('RGBA')
        pal = [((v & 31) << 3, ((v >> 5) & 31) << 3, ((v >> 10) & 31) << 3)
               for v in struct.unpack('<16H', self.pal)]
        entries = struct.unpack('<%dH' % (30 * 20), self.tsa)
        tw = src.width // 8
        ox, oy = (30 - tw) // 2, 3
        for y in range(src.height):
            for x in range(src.width):
                e = entries[(oy + y // 8) * 30 + (ox + x // 8)]
                byte = self.img[e * 32 + (y % 8) * 4 + (x % 8) // 2]
                idx = (byte >> 4) if x % 2 else (byte & 0xF)
                sp = src.getpixel((x, y))
                if sp[3] < 128:
                    self.assertEqual(idx, 0, 'transparent pixel (%d,%d)' % (x, y))
                else:
                    # BGR555 quantization: each channel snaps to a multiple of 8
                    want = (sp[0] & ~7, sp[1] & ~7, sp[2] & ~7)
                    self.assertEqual(pal[idx], want, 'pixel (%d,%d)' % (x, y))

    def test_too_many_colors_rejected(self):
        from PIL import Image
        with tempfile.TemporaryDirectory() as d:
            im = Image.new('RGBA', (16, 16))
            im.putdata([(x * 8, y * 8, 128, 255) for y in range(16) for x in range(16)])
            p = os.path.join(d, 'x.png')
            im.save(p)
            with self.assertRaises(SystemExit):
                bc._crit_flourish_bins(p)


if __name__ == '__main__':
    unittest.main()
