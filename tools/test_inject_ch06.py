#!/usr/bin/env python3
"""Tests for tools/inject/chapters/ch06.py.

Run:  python3 tools/test_inject_ch06.py
"""
import os
import re
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import inject.chapters.ch06
import inject.hosting
import inject.units
from inject import source as injector  # the injector's source, every file of it (#389)


class ItemDropIsCarriedOnce(unittest.TestCase):
    """FE8 drops the LAST item, and a chapter YAML may name the drop in `inventory:` too.

    ch06 is the first chapter whose data spells it both ways; appending unconditionally emitted a
    second copy on three units while `make difficulty` still read PARITY, because the parity model
    prices the YAML rather than the rows the injector emits.
    """

    CAMPAIGN = 'rime-of-the-frostmaiden'

    def test_a_drop_already_in_inventory_is_not_duplicated(self):
        self.assertEqual(inject.units._items_with_drop_last(['A', 'B'], 'B'), ['A', 'B'])

    def test_a_drop_absent_from_inventory_is_appended(self):
        self.assertEqual(inject.units._items_with_drop_last(['A'], 'B'), ['A', 'B'])

    def test_a_drop_listed_first_is_moved_LAST(self):
        # De-duplicating alone would leave the engine dropping the wrong item.
        self.assertEqual(inject.units._items_with_drop_last(['B', 'A'], 'B'), ['A', 'B'])

    def test_no_ch06_enemy_carries_a_duplicate(self):
        chap = inject.hosting._load_chapter_yaml(self.CAMPAIGN, inject.chapters.ch06.CH06_CHAPTER_YAML)
        rows = inject.chapters.ch06.ch06_enemy_rows(chap) + inject.chapters.ch06.ch06_enemy_rows(
            chap, arrives_turn=inject.chapters.ch06.CH06_HARD_WAVE_TURN)
        for row in rows:
            items = re.search(r'\.items = \{ (.*?) \}', row).group(1).split(', ')
            items = [i for i in items if i != '0']
            self.assertEqual(len(items), len(set(items)), row)

    def test_every_dropper_matches_its_vanilla_donors_item_count(self):
        """The check that would have caught it: our row against the donor unit it is derived
        from. Vanilla's three ch06 droppers carry 2 / 1 / 2 items; ADR 0329's re-classed
        Mercenary carries one more, the Steel Lance it now fights with, ahead of the drop."""
        chap = inject.hosting._load_chapter_yaml(self.CAMPAIGN, inject.chapters.ch06.CH06_CHAPTER_YAML)
        expected = {'shark-rider-halberd': 2, 'merfolk-trident-drop': 2, 'lamia-mender': 2}
        rows = inject.chapters.ch06.ch06_enemy_rows(chap)
        for enemy_id, count in expected.items():
            row = next(r for r in rows if '/* %s --' % enemy_id in r)
            items = re.search(r'\.items = \{ (.*?) \}', row).group(1).split(', ')
            self.assertEqual(len(items), count, '%s: %s' % (enemy_id, row))
            self.assertIn('.itemDrop = 1', row, enemy_id)


if __name__ == '__main__':
    unittest.main()
