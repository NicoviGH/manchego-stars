"""ref_to_bust: the matte keeps a flat background from bleeding into an outlined subject's edge."""
import os
import sys
import tempfile
import unittest

from PIL import Image, ImageDraw

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ref_to_bust as rb  # noqa: E402


def _edge_colours(bust):
    """RGB of every subject pixel that touches the background (index 0)."""
    px, pal = bust.load(), bust.getpalette()
    out = set()
    for y in range(rb.BUST_H):
        for x in range(rb.BUST_W):
            if px[x, y] == 0:
                continue
            if any(0 <= x + dx < rb.BUST_W and 0 <= y + dy < rb.BUST_H and px[x + dx, y + dy] == 0
                   for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1))):
                i = px[x, y] * 3
                out.add(tuple(pal[i:i + 3]))
    return out


class Matte(unittest.TestCase):
    def setUp(self):
        # A black-outlined blue disc on white, drawn at a non-integer scale to the bust so the
        # downscale has to blend the outline with whatever sits outside it.
        im = Image.new('RGB', (1000, 833), 'white')
        ImageDraw.Draw(im).ellipse((200, 150, 800, 760), fill=(40, 140, 230), outline='black',
                                   width=30)
        self.tmp = tempfile.NamedTemporaryFile(suffix='.png', delete=False)
        im.save(self.tmp.name)

    def tearDown(self):
        os.unlink(self.tmp.name)

    def test_without_a_matte_the_white_background_halos_the_outline(self):
        light = [c for c in _edge_colours(rb.convert(self.tmp.name, (0, 0, 1000, 833)))
                 if sum(c) > 3 * 90]
        self.assertTrue(light)          # the defect the matte exists for (Messie, #26)

    def test_a_black_matte_leaves_only_dark_edge_pixels(self):
        bust = rb.convert(self.tmp.name, (0, 0, 1000, 833), matte=(0, 0, 0))
        self.assertEqual([c for c in _edge_colours(bust) if sum(c) > 3 * 90], [])


class Cel(unittest.TestCase):
    """The flat cel-art path (Messie, 2026-10-09: "make the descale as clean as possible")."""

    def setUp(self):
        # A disc whose RIGHT edge is rim-lit pale instead of outlined -- Messie's snout.
        im = Image.new('RGB', (1000, 833), (55, 95, 87))
        d = ImageDraw.Draw(im)
        d.ellipse((200, 150, 800, 760), fill=(40, 140, 230), outline=(20, 20, 40), width=12)
        d.rectangle((700, 300, 820, 600), fill=(55, 95, 87))
        d.ellipse((200, 150, 800, 760), fill=None, outline=(20, 20, 40), width=12)
        d.arc((200, 150, 800, 760), -60, 60, fill=(200, 230, 250), width=14)
        self.tmp = tempfile.NamedTemporaryFile(suffix='.png', delete=False)
        im.save(self.tmp.name)

    def tearDown(self):
        os.unlink(self.tmp.name)

    def test_every_silhouette_edge_is_inked_even_where_the_ref_rim_lights_it(self):
        bust = rb.convert(self.tmp.name, (0, 0, 1000, 833), matte=(20, 20, 40), cel=True)
        self.assertEqual([c for c in _edge_colours(bust) if sum(c) > 3 * 90], [])

    def test_the_flat_fill_is_one_colour_with_no_dither(self):
        """A flat field must come out as ONE palette index, not a speckle of near-neighbours."""
        bust = rb.convert(self.tmp.name, (0, 0, 1000, 833), matte=(20, 20, 40), cel=True)
        px = bust.load()
        inner = {px[x, y] for x in range(36, 52) for y in range(30, 50)}
        self.assertEqual(1, len(inner))


class PixelGridAndRetint(unittest.TestCase):
    def test_grid_sampling_recovers_the_native_art_through_jpeg_noise(self):
        import io
        art = Image.new('RGB', (4, 4), 'white')
        art.putpixel((1, 2), (40, 140, 230))
        big = art.resize((4 * 41, 4 * 41), Image.NEAREST)
        buf = io.BytesIO(); big.save(buf, 'JPEG', quality=80); buf.seek(0)
        got = rb.sample_pixel_grid(Image.open(buf), 41)
        self.assertEqual(got.size, (4, 4))
        self.assertTrue(all(abs(a - b) < 12 for a, b in zip(got.getpixel((1, 2)), (40, 140, 230))))
        self.assertTrue(min(got.getpixel((0, 0))) > 240)

    def test_grid_sampling_keeps_a_non_square_ref_s_shape(self):
        tall = Image.new('RGB', (2 * 41, 5 * 41), 'white')
        self.assertEqual(rb.sample_pixel_grid(tall, 41).size, (2, 5))

    def test_retint_lands_each_anchor_exactly_and_leaves_unselected_pixels(self):
        dark_src, light_src, gold = (51, 148, 234), (212, 236, 241), (208, 160, 40)
        img = Image.new('RGB', (3, 1))
        for i, c in enumerate((dark_src, light_src, gold)):
            img.putpixel((i, 0), c)
        blue = lambda a: a[..., 2] > a[..., 0] + 0.03
        out = rb.retint_ramp(img, (dark_src, (95, 111, 144)), (light_src, (180, 184, 190)), blue)
        near = lambda p, q: all(abs(x - y) <= 1 for x, y in zip(p, q))
        self.assertTrue(near(out.getpixel((0, 0)), (95, 111, 144)))
        self.assertTrue(near(out.getpixel((1, 0)), (180, 184, 190)))
        self.assertEqual(out.getpixel((2, 0)), gold)


if __name__ == '__main__':
    unittest.main()
