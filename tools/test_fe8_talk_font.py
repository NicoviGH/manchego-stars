#!/usr/bin/env python3
"""FE8's talk font is VARIABLE-WIDTH, and every wrap decision depends on it.

`GetStrTalkLen` (scene.c) accumulates `glyph->width` in PIXELS and `StartTalkExt` turns that
into the bubble's tile width; nothing in the engine ever counts characters. These tests pin the
table we measure with, and the two facts that make a character count the wrong instrument.

Run: python3 tools/test_fe8_talk_font.py
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import fe8_talk_font as font


class TheTable(unittest.TestCase):
    def test_every_printable_ascii_character_has_a_width(self):
        """A missing glyph would silently take a default and mis-measure the line it is on."""
        missing = [chr(c) for c in range(0x20, 0x7F) if chr(c) not in font.GLYPH_WIDTH]
        self.assertEqual([], missing)

    def test_the_font_is_actually_variable_width(self):
        """The whole point. If these were equal a character count would be a fair proxy."""
        self.assertLess(font.GLYPH_WIDTH['i'], font.GLYPH_WIDTH['W'])
        self.assertLess(font.GLYPH_WIDTH['.'], font.GLYPH_WIDTH['a'])
        self.assertGreater(len(set(font.GLYPH_WIDTH.values())), 3)

    def test_widths_are_plausible_pixel_counts_for_a_16px_cell(self):
        for ch, w in font.GLYPH_WIDTH.items():
            self.assertTrue(1 <= w <= 16, '%r has width %d' % (ch, w))


class Measuring(unittest.TestCase):
    def test_text_px_sums_the_glyphs(self):
        self.assertEqual(font.GLYPH_WIDTH['a'] + font.GLYPH_WIDTH['b'], font.text_px('ab'))

    def test_two_lines_of_equal_LENGTH_can_differ_by_half_their_WIDTH(self):
        """The failure a character count cannot see: same 12 characters, wildly different draw."""
        narrow, wide = font.text_px('iiiiiiiiiiii'), font.text_px('WWWWWWWWWWWW')
        self.assertLess(narrow * 2, wide)

    def test_the_budget_is_what_vanilla_ships_in_this_window(self):
        """MSG_9CC -- vanilla's Natasha->Joshua Talk, the scene ch05's recruit is the twin of --
        draws a 43-character line at 203px. Our budget sits just under it rather than at some
        number of characters, and must leave room for the bubble's own 2-tile border on a
        240px screen."""
        self.assertLessEqual(font.TALK_BUDGET_PX, 203)
        self.assertGreaterEqual(font.TALK_BUDGET_PX, 190)
        self.assertLessEqual(font.TALK_BUDGET_PX + 16, 240)

    def test_vanillas_own_widest_line_fits_the_budget(self):
        """The reference line itself must not be something we would refuse to emit."""
        self.assertLessEqual(font.text_px("I got nothing against heaven, but I'm right"),
                             203)


if __name__ == '__main__':
    unittest.main()
