import unittest

from PIL import Image

import descale_battleframe as db


class LockedLayoutDescaleTest(unittest.TestCase):
    def test_applies_one_source_space_transform_to_every_pose(self):
        """The artist's offsets survive: no individual crop or feet reanchoring."""
        ready = Image.new('RGBA', (80, 80))
        windup = Image.new('RGBA', (80, 80))
        peak = Image.new('RGBA', (80, 80))
        ready.paste((200, 0, 0, 255), (20, 40, 40, 72))
        windup.paste((200, 0, 0, 255), (10, 16, 60, 72))
        peak.paste((200, 0, 0, 255), (0, 32, 80, 72))

        out = db.descale_locked_layout(
            {'ready': ready, 'windup': windup, 'peak': peak},
            body_h=16, flip=False, outline=False,
        )

        self.assertEqual({image.size for image in out.values()}, {(40, 32)})
        self.assertEqual(out['ready'].getchannel('A').getbbox(), (10, 12, 20, 28))
        self.assertEqual(out['windup'].getchannel('A').getbbox(), (5, 0, 30, 28))
        self.assertEqual(out['peak'].getchannel('A').getbbox(), (0, 8, 40, 28))

    def test_palette_keeps_a_reserved_small_accent_colour(self):
        frame = Image.new('RGBA', (20, 20), (130, 25, 25, 255))
        frame.paste((180, 180, 195, 255), (0, 0, 2, 2))

        pal, _ = db._shared_palette([frame], reserved=((180, 180, 195),))

        self.assertIn((180, 180, 195),
                      [tuple(pal.getpalette()[i:i + 3]) for i in range(0, 48, 3)])


class AdaptiveReserveTest(unittest.TestCase):
    def test_descale_threads_reserved_accent_into_adaptive_palette(self):
        """A tiny accent (Rootis's orange nose) survives the near-monochrome frame only
        because the adaptive path now forwards --reserve to _shared_palette. Without the
        thread it loses the frequency contest against the blue/white body and quantizes out."""
        nose = (240, 110, 55)
        body = Image.new('RGBA', (40, 40), (0, 0, 0, 0))
        body.paste((205, 210, 225, 255), (8, 4, 32, 36))     # big pale-blue snowman body
        body.paste(nose, (18, 18, 22, 21))                   # a handful of carrot pixels

        out = db.descale(
            {'ready': body, 'windup': body, 'peak': body},
            body_h=32, flip=False, outline=False, reserved=(nose,),
        )

        colours = {px for px in out['ready'].convert('RGBA').getdata() if px[3] != 0}
        self.assertIn(nose + (255,), colours)


if __name__ == '__main__':
    unittest.main()
