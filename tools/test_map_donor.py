"""`map_donor` derives a chapter's retile donor -- and says when it CANNOT.

The ADR these pin: docs/decisions.md -> "A base-map LABEL is prose -- the donor is DERIVED".
Each test is one of the three ways the naive version of this lies.
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import map_donor                                                # noqa: E402


class OurOwnLayoutsAreNotCandidates(unittest.TestCase):
    """The build copies our maps INTO the decomp's layout dir, so an unfiltered scan
    reports ch01's own artifact as ch01's donor."""

    def test_labels_come_from_build_campaign_not_a_prefix(self):
        labels = map_donor.our_layout_labels()
        self.assertIn('Ch01IronTrailMap', labels)
        self.assertIn('Ch00PrologueMap', labels)
        self.assertNotIn('Ch13EirikaMap', labels)   # vanilla must survive the filter

    def test_no_layout_of_ours_is_offered_as_a_donor(self):
        ours = map_donor.our_layout_labels()
        offered = set(map_donor.vanilla_layouts())
        self.assertEqual(ours & offered, set())


class TheDonorIsRecovered(unittest.TestCase):
    def test_ch01_is_hamill_canyon_not_fluorspars_oath(self):
        """The correction this tool exists for. Ch13EphraimMap is 22x22 and cannot even
        be a candidate for a 25x16 map."""
        width, height, scored = map_donor.candidates('ch01-the-iron-trail')
        self.assertEqual((width, height), (25, 16))
        self.assertEqual(scored[0][1], 'Ch13EirikaMap')
        self.assertNotIn('Ch13EphraimMap', [name for _, name in scored])

    def test_a_low_score_still_identifies_when_it_is_the_only_candidate(self):
        """ch03 edited the geometry, so it agrees with Borgo only ~85%. That is a fact
        about our repaint: at 17x16 there is exactly one vanilla layout to be."""
        _, _, scored = map_donor.candidates('ch03-the-termalaine-mine')
        self.assertEqual(len(scored), 1)
        self.assertEqual(scored[0][1], 'Ch3Map')
        self.assertLess(scored[0][0], 0.9)


class AnUnbreakableTieIsReported(unittest.TestCase):
    def test_ch05_ties_because_the_two_donors_are_byte_identical(self):
        _, _, scored = map_donor.candidates('ch05-the-elven-tomb')
        top = [name for score, name in scored if score == scored[0][0]]
        self.assertEqual(sorted(top), ['Ch5Map', 'Ch5TownMapPast'])
        self.assertIn('Ch5TownMapPast', map_donor.identical_to('Ch5Map', top))


class TheBlockedSetIsDeclared(unittest.TestCase):
    def test_water_is_not_impassable_because_a_retile_repaints_it(self):
        """ch06 turns sea into walkable ice. Counting water as a wall would score a coast
        map against its own future."""
        for water in (0x15, 0x36, 0x3c, 0x10):
            self.assertNotIn(water, map_donor.IMPASSABLE)
        self.assertIn(0x12, map_donor.IMPASSABLE)   # peak


if __name__ == '__main__':
    unittest.main()
