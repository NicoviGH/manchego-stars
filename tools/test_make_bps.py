#!/usr/bin/env python3
"""Tests for the pure-Python BPS patch encoder (tools/make_bps.py, #37/#59).

BPS is the standard ROM-hack delta format: it lets us publish a small public patch
(no copyrighted ROM bytes) that testers apply to their own legal FE8 ROM. We emit only
SourceRead + TargetRead actions, which is valid BPS and near-optimal for our case (an
in-place-edited ROM the same size as vanilla). The applier here doubles as the build's
self-verify (round-trip + CRC32 footer) so a bad patch never ships.
"""
import os
import random
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import make_bps  # noqa: E402


class TestVarint(unittest.TestCase):
    def test_roundtrip(self):
        for n in (0, 1, 2, 127, 128, 129, 16383, 16384, 1 << 20, 16777216):
            buf = make_bps.encode_varint(n)
            val, pos = make_bps.decode_varint(buf, 0)
            self.assertEqual(val, n, 'varint roundtrip failed for %d' % n)
            self.assertEqual(pos, len(buf))


class TestPatchRoundTrip(unittest.TestCase):
    def setUp(self):
        random.seed(1234)
        self.source = bytes(random.getrandbits(8) for _ in range(4096))

    def test_apply_reconstructs_target_small_diff(self):
        target = bytearray(self.source)
        for i in (10, 500, 501, 502, 4000):  # a few in-place edits
            target[i] ^= 0xFF
        target = bytes(target)
        patch = make_bps.create_patch(self.source, target)
        self.assertEqual(make_bps.apply_patch(patch, self.source), target)

    def test_small_diff_yields_small_patch(self):
        target = bytearray(self.source)
        target[100] ^= 0xFF
        patch = make_bps.create_patch(self.source, bytes(target))
        # A one-byte change must not produce a patch the size of the whole ROM.
        self.assertLess(len(patch), len(self.source) // 4)

    def test_identical_source_target(self):
        patch = make_bps.create_patch(self.source, self.source)
        self.assertEqual(make_bps.apply_patch(patch, self.source), self.source)

    def test_header_is_bps1(self):
        patch = make_bps.create_patch(self.source, self.source)
        self.assertEqual(patch[:4], b'BPS1')

    def test_wrong_source_fails_checksum(self):
        target = bytes(bytearray(self.source[:1]) + self.source[1:])
        patch = make_bps.create_patch(self.source, target)
        wrong = bytearray(self.source)
        wrong[0] ^= 0xFF
        with self.assertRaises(ValueError):
            make_bps.apply_patch(patch, bytes(wrong))

    def test_differing_sizes(self):
        target = self.source + b'\x00\x01\x02\x03'  # grew
        patch = make_bps.create_patch(self.source, target)
        self.assertEqual(make_bps.apply_patch(patch, self.source), target)


if __name__ == '__main__':
    unittest.main()
