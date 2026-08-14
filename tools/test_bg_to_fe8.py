#!/usr/bin/env python3
"""Tests for the event-BG vendoring tool (tools/bg_to_fe8.py).

The one this file exists for: **the FE9-10 CG rips ship letterboxed.** Their picture is
240 wide inside a 256-wide canvas, with the remaining 16 columns a flat black bar. The
tool's `--fit crop` centre-crops, so it took columns 8..247 -- keeping HALF the bar on the
right while throwing away 8 columns of real picture on the left. Both ch05 backdrops
shipped that way and the bar is visible in-engine (Nicolas, 2026-08-14).

What made it slip through is worth keeping in view: the vendoring check was "0 of 38400
pixels differ from the 5-bit source crop", which proves the CONVERSION is faithful and says
nothing about whether the crop was the right crop.
"""
import os
import sys
import unittest

import numpy as np
from PIL import Image

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bg_to_fe8 as bg


def _art(w, h, seed=0):
    """A patch of non-uniform 'picture': every column carries several colours."""
    rng = np.random.RandomState(seed)
    return rng.randint(40, 240, size=(h, w, 3)).astype('uint8')


class LetterboxBarsAreTrimmedBeforeFitting(unittest.TestCase):
    """A border column of ONE colour carries no picture. Real art columns hold many."""

    def test_a_right_hand_bar_is_removed(self):
        a = np.concatenate([_art(240, 160), np.zeros((160, 16, 3), 'uint8')], axis=1)
        out = bg.trim_uniform_border(Image.fromarray(a))
        self.assertEqual((240, 160), out.size)

    def test_bars_on_every_side_are_removed(self):
        a = np.zeros((200, 280, 3), 'uint8')
        a[20:180, 20:260] = _art(240, 160)
        out = bg.trim_uniform_border(Image.fromarray(a))
        self.assertEqual((240, 160), out.size)

    def test_a_non_black_bar_counts_too(self):
        """The rule is UNIFORM, not black -- a white or magenta mat is the same artifact."""
        bar = np.full((160, 16, 3), 255, 'uint8')
        out = bg.trim_uniform_border(Image.fromarray(
            np.concatenate([_art(240, 160), bar], axis=1)))
        self.assertEqual((240, 160), out.size)

    def test_real_art_is_never_trimmed(self):
        im = Image.fromarray(_art(256, 160))
        self.assertEqual((256, 160), bg.trim_uniform_border(im).size)

    def test_a_flat_edge_inside_a_picture_is_not_eaten_past_the_cap(self):
        """Safety rail: a picture that is mostly one flat colour (a night sky, a fade to
        black) must not be trimmed away to nothing. Never give back less than half."""
        a = np.zeros((160, 256, 3), 'uint8')
        a[:, 250:] = _art(6, 160)          # only a sliver is non-uniform
        out = bg.trim_uniform_border(Image.fromarray(a))
        self.assertGreaterEqual(out.size[0], 128)

    def test_a_trim_that_would_force_an_upscale_is_refused(self):
        """Found in review. A source ALREADY at 240x160 with one flat edge row -- a deliberate
        letterbox line, which real art has -- came out 240x159, and fit_240x160 then NEAREST-
        upscaled it back, changing 28640 of 38400 pixels where the old code returned the image
        untouched. Trimming must never force an upscale to pay for stripping a mat."""
        a = _art(240, 160)
        a[0, :] = 17
        im = Image.fromarray(a)
        self.assertEqual((240, 160), bg.trim_uniform_border(im).size)
        out = np.asarray(bg.fit_240x160(bg.trim_uniform_border(im), 'crop'), dtype=int)
        self.assertEqual(0, int((out != np.asarray(im, dtype=int)).any(axis=2).sum()))

    def test_an_oversized_source_still_trims_down_to_the_target(self):
        """The rail is 'never below the target', not 'never trim' -- the real rips are 256 wide
        and must still lose their 16 columns."""
        a = np.concatenate([_art(240, 160), np.zeros((160, 16, 3), 'uint8')], axis=1)
        self.assertEqual((240, 160), bg.trim_uniform_border(Image.fromarray(a)).size)

    def test_the_mode_survives_the_trim(self):
        a = np.concatenate([_art(240, 160), np.zeros((160, 16, 3), 'uint8')], axis=1)
        out = bg.trim_uniform_border(Image.fromarray(a).convert('P'))
        self.assertEqual((240, 160), out.size)


class TheRealRipsLandOnTheirOwnPicture(unittest.TestCase):
    """End-to-end on the two ch05 backdrops, if their sources are present.

    Skipped rather than vendored: the sources live in the FE-Repo, not this tree.
    """
    CAMPAIGN = 'rime-of-the-frostmaiden'

    def _shipped(self, stem):
        p = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'campaigns',
                         self.CAMPAIGN, 'backgrounds', stem + '.png')
        if not os.path.isfile(p):
            self.skipTest('%s not vendored' % stem)
        return np.asarray(Image.open(p).convert('RGB'), dtype=int)

    def _assert_no_bar(self, stem):
        a = self._shipped(stem)
        self.assertEqual((160, 240, 3), a.shape)
        # Columns AND rows: checking only columns would ship a surviving top/bottom mat with
        # a green suite (review, 2026-08-14).
        for edge, cols in (('left', range(0, 4)), ('right', range(236, 240))):
            for c in cols:
                self.assertGreater(
                    len(set(map(tuple, a[:, c, :]))), 1,
                    '%s: %s column %d is a single flat colour -- a letterbox bar survived '
                    'the vendoring (see trim_uniform_border)' % (stem, edge, c))
        for edge, rows in (('top', range(0, 4)), ('bottom', range(156, 160))):
            for r in rows:
                self.assertGreater(
                    len(set(map(tuple, a[r, :, :]))), 1,
                    '%s: %s row %d is a single flat colour -- a letterbox bar survived '
                    'the vendoring (see trim_uniform_border)' % (stem, edge, r))

    def test_the_elven_tomb_shows_no_letterbox(self):
        self._assert_no_bar('bg_ElvenTomb')

    def test_the_ridge_shows_no_letterbox(self):
        self._assert_no_bar('bg_ForestOutskirtsWinter')


if __name__ == '__main__':
    unittest.main()
