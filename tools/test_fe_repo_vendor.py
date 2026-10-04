#!/usr/bin/env python3
"""fe_repo_vendor's offline rules: which files an anim folder contributes, how a community
sheet is re-encoded, and what counts as the same picture. `verify` itself needs the network."""
import unittest

from PIL import Image

import fe_repo_vendor as v

KEY = (0x80, 0xa0, 0x80)


def indexed(pal, data, size):
    im = Image.new('P', size)
    im.putpalette([c for rgb in pal for c in rgb] + [0, 0, 0] * (16 - len(pal)))
    im.putdata(data)
    return im


class AnimFiles(unittest.TestCase):
    FOLDER = ['Axe Frame Data.dmp', 'Axe Sheet 1.png', 'Axe.bin', 'Axe.gif', 'Axe.txt',
              'Axe_000.png', 'Axe_001.png', 'Axe_without_comment.txt', 'README.md']

    def test_the_script_and_numbered_frames_and_nothing_else(self):
        self.assertEqual([('Axe.txt', 'Axe.txt'), ('Axe_000.png', 'Axe_000.png'),
                          ('Axe_001.png', 'Axe_001.png')], v.anim_files(self.FOLDER))

    def test_a_commented_script_is_taken_under_the_name_feditor_reads(self):
        names = ['Sword with comments.txt', 'Sword no comments.txt', 'Sword_000.png']
        self.assertEqual(('Sword with comments.txt', 'Sword.txt'),
                         v.anim_files(names, 'Sword with comments.txt')[0])

    def test_a_folder_without_its_script_names_what_it_has(self):
        with self.assertRaises(ValueError) as cm:
            v.anim_files(['Sword with comments.txt', 'Sword_000.png'])
        self.assertIn('Sword with comments.txt', str(cm.exception))


class Normalise(unittest.TestCase):
    def test_the_key_lands_on_index_0_and_duplicate_indices_collapse(self):
        # Index 0 an ordinary colour, the key spent on TWO indices (2 and 3).
        src = indexed([(0xf8, 0xf8, 0xd0), (0x40, 0x38, 0x38), KEY, KEY],
                      [2, 3, 0, 1], (2, 2))
        out = v.normalise_sheet(src)
        self.assertEqual(KEY, tuple(out.getpalette()[0:3]))
        self.assertEqual([0, 0, 1, 2], list(out.getdata()))
        self.assertEqual(v.picture(src), v.picture(out))

    def test_rgba_alpha_becomes_the_key(self):
        src = Image.new('RGBA', (2, 1))
        src.putdata([(0, 0, 0, 0), (10, 20, 30, 255)])
        out = v.normalise_sheet(src)
        self.assertEqual([0, 1], list(out.getdata()))
        self.assertEqual(v.picture(src), v.picture(out))

    def test_a_keyless_rgba_sheet_keeps_a_colour_that_matches_its_corner(self):
        # Transparent background stored as BLACK, and a pure-black outline: alpha says which
        # is which. Guessing the key from the corner pixel would erase the outline.
        src = Image.new('RGBA', (3, 1))
        src.putdata([(0, 0, 0, 0), (0, 0, 0, 255), (200, 10, 10, 255)])
        self.assertEqual([None, (0, 0, 0), (200, 10, 10)], v.picture(src)[1])
        out = v.normalise_sheet(src)
        self.assertEqual(v.picture(src), v.picture(out))
        self.assertEqual([0, 1, 2], list(out.getdata()))

    def test_a_sheet_with_no_transparency_marker_is_refused(self):
        src = Image.new('RGB', (2, 1))
        src.putdata([(1, 1, 1), (2, 2, 2)])
        with self.assertRaises(ValueError):
            v.normalise_sheet(src)

    def test_more_colours_than_a_map_sprite_holds_is_refused(self):
        src = Image.new('RGB', (17, 1))
        src.putdata([KEY] + [(i, i, i) for i in range(16)])
        with self.assertRaises(ValueError):
            v.normalise_sheet(src)


class Picture(unittest.TestCase):
    def test_a_different_pixel_is_a_different_picture(self):
        a = indexed([KEY, (1, 2, 3)], [0, 1], (2, 1))
        b = indexed([KEY, (1, 2, 4)], [0, 1], (2, 1))
        self.assertNotEqual(v.picture(a), v.picture(b))


if __name__ == '__main__':
    unittest.main()
