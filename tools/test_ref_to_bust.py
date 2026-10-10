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


class Accents(unittest.TestCase):
    """A colour too small to win one of the 15 slots on count (Messie's eye under the hat, #471)."""

    YELLOW = (240, 200, 40)

    def setUp(self):
        # 20 bands of distinct flat colour, more than the palette holds, and one small yellow dot.
        im = Image.new('RGB', (1000, 833), (55, 95, 87))
        d = ImageDraw.Draw(im)
        for i in range(20):
            d.rectangle((100 + i * 40, 100, 139 + i * 40, 760),
                        fill=(30 + i * 10, 60 + (i * 37) % 150, 200 - i * 8))
        d.rectangle((480, 400, 520, 440), fill=self.YELLOW)
        self.tmp = tempfile.NamedTemporaryFile(suffix='.png', delete=False)
        im.save(self.tmp.name)

    def tearDown(self):
        os.unlink(self.tmp.name)

    def _has_yellow(self, bust):
        pal = bust.getpalette()
        return any(abs(pal[i * 3] - 240) < 20 and abs(pal[i * 3 + 1] - 200) < 20
                   and pal[i * 3 + 2] < 90 for v in set(bust.getdata()) if v for i in [v])

    def test_without_it_the_dot_loses_its_slot(self):
        self.assertFalse(self._has_yellow(rb.convert(self.tmp.name, (0, 0, 1000, 833), cel=True)))

    def test_with_it_the_dot_keeps_its_colour(self):
        bust = rb.convert(self.tmp.name, (0, 0, 1000, 833), cel=True, accents=[self.YELLOW])
        self.assertTrue(self._has_yellow(bust))


class Flatten(unittest.TestCase):
    """A painted ref's texture comes out as flat tones, not speckle (Wolfram, Braulo, #471)."""

    def setUp(self):
        # A disc of brushwork: a fine random texture over one base colour.
        import random
        rnd = random.Random(471)
        im = Image.new('RGB', (1000, 833), (55, 95, 87))
        d = ImageDraw.Draw(im)
        d.ellipse((150, 100, 850, 800), fill=(120, 90, 60))
        px = im.load()
        for _ in range(60000):
            x, y = rnd.randrange(250, 750), rnd.randrange(200, 700)
            v = rnd.choice((-40, 40))
            r, g, b = px[x, y]
            for dx in range(3):
                px[x + dx, y] = (r + v, g + v, b + v)
        self.tmp = tempfile.NamedTemporaryFile(suffix='.png', delete=False)
        im.save(self.tmp.name)

    def tearDown(self):
        os.unlink(self.tmp.name)

    def _speckle(self, bust):
        """Interior pixels unlike all four neighbours -- the single-pixel noise a dither leaves."""
        px = bust.load()
        return sum(1 for x in range(36, 60) for y in range(28, 52)
                   if all(px[x, y] != px[x + dx, y + dy]
                          for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1))))

    def test_flattened_the_interior_is_flat(self):
        self.assertLessEqual(self._speckle(rb.convert(self.tmp.name, (0, 0, 1000, 833),
                                                      flatten=9)), 5)

    def test_unflattened_the_dither_speckles_it(self):
        self.assertGreater(self._speckle(rb.convert(self.tmp.name, (0, 0, 1000, 833))), 100)


class Retint(unittest.TestCase):
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
