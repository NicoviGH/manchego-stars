#!/usr/bin/env python3
"""Tests for tools/playtest/make_gif.py pure helpers (frame collection + the
ffmpeg MP4 invocation). Run:  python3 tools/playtest/test_make_gif.py
"""
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import make_gif as mg


class CollectFrames(unittest.TestCase):
    """Frames are `NN-<tag>.png`; NN is a zero-padded global counter so lexical
    sort == capture order. collect_frames filters to the tag and keeps that order."""

    def _touch(self, d, *names):
        for n in names:
            open(os.path.join(d, n), 'w').close()

    def test_filters_to_tag_in_capture_order(self):
        with tempfile.TemporaryDirectory() as d:
            self._touch(d, '00-intro.png', '01-rbg.png', '02-rbg.png', '03-end.png')
            got = [os.path.basename(f) for f in mg.collect_frames(d, 'rbg')]
            self.assertEqual(got, ['01-rbg.png', '02-rbg.png'])

    def test_empty_tag_takes_every_frame(self):
        with tempfile.TemporaryDirectory() as d:
            self._touch(d, '00-a.png', '01-b.png')
            self.assertEqual(len(mg.collect_frames(d, '')), 2)


class Mp4Cmd(unittest.TestCase):
    """The ffmpeg arg list for encoding a zero-padded frame sequence to H.264."""

    def test_builds_a_libx264_yuv420p_invocation(self):
        cmd = mg.mp4_cmd('/tmp/seq/%04d.png', 'out.mp4', fps=15, scale=2)
        self.assertEqual(cmd[0], 'ffmpeg')
        self.assertIn('-framerate', cmd)
        self.assertEqual(cmd[cmd.index('-framerate') + 1], '15')
        self.assertEqual(cmd[cmd.index('-i') + 1], '/tmp/seq/%04d.png')
        self.assertIn('libx264', cmd)
        self.assertIn('yuv420p', cmd)
        self.assertEqual(cmd[-1], 'out.mp4')

    def test_2x_scale_uses_nearest_neighbor_filter(self):
        cmd = mg.mp4_cmd('/tmp/seq/%04d.png', 'out.mp4', fps=12, scale=2)
        self.assertIn('-vf', cmd)
        self.assertEqual(cmd[cmd.index('-vf') + 1], 'scale=iw*2:ih*2:flags=neighbor')

    def test_1x_scale_omits_the_filter(self):
        cmd = mg.mp4_cmd('/tmp/seq/%04d.png', 'out.mp4', fps=12, scale=1)
        self.assertNotIn('-vf', cmd)

    def test_fps_renders_without_trailing_zero(self):
        cmd = mg.mp4_cmd('/tmp/seq/%04d.png', 'out.mp4', fps=12.0, scale=2)
        self.assertEqual(cmd[cmd.index('-framerate') + 1], '12')


if __name__ == '__main__':
    unittest.main()
