#!/usr/bin/env python3
"""kits.py: what each side picks up, chapter by chapter, and what it carries (#510 step 8)."""
import os
import sys
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import kits  # noqa: E402

CAMPAIGN = 'rime-of-the-frostmaiden'


class OurPickups(unittest.TestCase):
    def setUp(self):
        self.ours = kits.our_pickups(CAMPAIGN)

    def test_ch02_village_hand_axe(self):
        self.assertIn(kits.Pickup('ITEM_AXE_HANDAXE', 'village', 2), self.ours)

    def test_planned_chapters_absent(self):
        import campaign_chapters
        planned = {int(c['chapter_number']) for c in campaign_chapters.load_all(CAMPAIGN)
                   if c.get('status') == 'planned'}
        self.assertTrue(planned)
        self.assertFalse([p for p in self.ours if p.chapter in planned])

    def test_pure_water_kept_but_not_weapon(self):
        water = [p for p in self.ours if p.item == 'ITEM_PUREWATER']
        self.assertTrue(water)
        self.assertFalse(kits.is_weapon(water[0]))
        self.assertTrue(kits.is_weapon(kits.Pickup('ITEM_AXE_HANDAXE', 'village', 2)))


class TwinPickups(unittest.TestCase):
    def setUp(self):
        self.twin = kits.twin_pickups()

    def test_prologue_rapier_named(self):
        self.assertIn(kits.Pickup('ITEM_SWORD_RAPIER', 'scene', 0, ('CHARACTER_EIRIKA',)),
                      self.twin)

    def test_ch2_village_gifts_are_village(self):
        self.assertIn(kits.Pickup('ITEM_ELIXIR', 'village', 2), self.twin)
        self.assertIn(kits.Pickup('ITEM_SWORD_SLIM', 'shop', 2), self.twin)
        # Ide is Ch2's node; its armory stocks a Slim Sword too.
        self.assertIn(kits.Pickup('ITEM_SWORD_SLIM', 'worldmap_shop', 2), self.twin)

    def test_ch3_chests(self):
        self.assertIn(kits.Pickup('ITEM_AXE_HANDAXE', 'chest', 3), self.twin)

    def test_serafew_armory(self):
        """Serafew is Ch5's node: its Steel Sword is world-map stock from Ch5 on."""
        self.assertIn(kits.Pickup('ITEM_SWORD_STEEL', 'worldmap_shop', 5), self.twin)
        self.assertNotIn(kits.Pickup('ITEM_SWORD_STEEL', 'worldmap_shop', 4), self.twin)


class OurWorldMap(unittest.TestCase):
    def test_projected_until_stocked(self):
        ours = [p for p in kits.our_pickups(CAMPAIGN) if p.vehicle == 'worldmap_shop']
        twin = [p for p in kits.twin_pickups() if p.vehicle == 'worldmap_shop']
        self.assertEqual({(p.item, p.chapter) for p in twin}, {(p.item, p.chapter) for p in ours})
        self.assertTrue(all(p.projected for p in ours))

    def test_a_stock_list_replaces_the_projection(self):
        nodes = [{'id': 'targos', 'unlocks_after': 'ch01', 'stock': ['iron-sword']}]
        with mock.patch.object(kits, '_our_world_map', return_value=nodes):
            ours = [p for p in kits.our_pickups(CAMPAIGN) if p.vehicle == 'worldmap_shop']
        self.assertEqual([kits.Pickup('ITEM_SWORD_IRON', 'worldmap_shop', 1)], ours)


if __name__ == '__main__':
    unittest.main()
