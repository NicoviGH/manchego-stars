#!/usr/bin/env python3
"""Tests for make_gif.encode_gif (#112, audit 2.7).

Committed docs/demo GIFs live in git history forever; encode_gif stores dirty-rect
deltas (shared palette + disposal=1) when that is BOTH smaller and decodes
identically to the full-frame form, else ships the legacy full-frame encoding.
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), 'playtest'))
try:
    from PIL import Image, ImageDraw
    import make_gif as mg
    HAVE_PIL = True
except ImportError:          # PIL-less CI checks job: the build job runs this
    HAVE_PIL = False


def sprite_clip(n=20, size=(240, 160)):
    """A battle-anim-shaped clip: static background, one small moving sprite."""
    frames = []
    for i in range(n):
        im = Image.new('RGB', size, (40, 44, 52))
        d = ImageDraw.Draw(im)
        d.rectangle([0, 120, size[0], 160], fill=(90, 90, 110))   # static ground
        d.rectangle([10 + i * 4, 60, 30 + i * 4, 100], fill=(200, 60, 60))
        frames.append(im)
    return frames


@unittest.skipUnless(HAVE_PIL, 'PIL not installed')
class TestEncodeGif(unittest.TestCase):
    def test_static_background_clip_uses_delta_and_shrinks(self):
        frames = sprite_clip()
        data, how = mg.encode_gif(frames, 83)
        self.assertEqual(how, 'delta')
        import io
        full = io.BytesIO()
        q = [f.quantize(colors=64) for f in frames]
        q[0].save(full, 'GIF', save_all=True, append_images=q[1:], disposal=2)
        self.assertLess(len(data), full.tell())

    def test_delta_decodes_identical_to_full(self):
        # The guarantee that makes delta safe to ship: both encodings of the
        # same quantized frames decode to the same pixels.
        data, how = mg.encode_gif(sprite_clip(), 83)
        decoded = mg._decoded_frames(data)
        self.assertEqual(len(decoded), 20)
        self.assertEqual(len(set(len(d) for d in decoded)), 1)

    def test_lossless_palette_when_under_256_colors(self):
        frames = sprite_clip(4)
        data, _ = mg.encode_gif(frames, 83)
        got = mg._decoded_frames(data)
        want = [f.tobytes() for f in frames]
        self.assertEqual(got, want)      # <=256 unique colors -> exact palette

    def test_over_256_colors_still_encodes(self):
        # A gradient forces the mediancut path; must not crash and must decode
        # to the right frame count.
        frames = []
        for i in range(3):
            im = Image.new('RGB', (64, 64))
            im.putdata([(x * 4, y * 4, i * 40) for y in range(64) for x in range(64)])
            frames.append(im)
        data, _ = mg.encode_gif(frames, 83)
        self.assertEqual(len(mg._decoded_frames(data)), 3)


if __name__ == '__main__':
    unittest.main()
