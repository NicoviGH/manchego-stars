#!/usr/bin/env python3
"""Every bust marks palette index 0 transparent.

FE8 draws a bust's palette index 0 as transparent, so the game never shows that colour, and
our busts carry whatever key their source used: pure green, magenta, sage. Only four of them
said so in the file, so any reader that is not the game (the wiki, an image viewer) showed a
green box behind most faces and not others (#486). The colours stay as they are -- they are
palette bytes in the ROM -- and the file now says index 0 is transparent, which every reader
honours. Read with the standard library, so it runs wherever the tests do.
"""
import glob
import os
import struct
import unittest

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BUSTS = os.path.join(REPO, 'campaigns', '*', 'portraits', '*.png')


def png_chunks(path):
    """{chunk type: first chunk's data} for one PNG."""
    with open(path, 'rb') as f:
        data = f.read()
    assert data[:8] == b'\x89PNG\r\n\x1a\n', path
    out, at = {}, 8
    while at < len(data):
        length, kind = struct.unpack('>I4s', data[at:at + 8])
        out.setdefault(kind.decode('latin-1'), data[at + 8:at + 8 + length])
        at += 12 + length
    return out


class TestBustKey(unittest.TestCase):
    def test_every_bust_is_indexed_with_index_0_transparent(self):
        busts = [p for p in glob.glob(BUSTS) if not p.endswith('_preview.png')]
        self.assertTrue(busts)
        for path in busts:
            chunks = png_chunks(path)
            colour_type = chunks['IHDR'][9]
            rel = os.path.relpath(path, REPO)
            self.assertEqual(colour_type, 3, '%s is not indexed' % rel)
            self.assertIn('tRNS', chunks, '%s does not mark index 0 transparent' % rel)
            self.assertEqual(chunks['tRNS'][0], 0, '%s: index 0 is not transparent' % rel)


if __name__ == '__main__':
    unittest.main()
