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
        import difficulty
        self.assertIsNone(difficulty.item_weapon(water[0].item))


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


class Vehicles(unittest.TestCase):
    """A gift's vehicle is how it is DELIVERED, on both sides: a visit (village, house, boat
    talk) is `village`; anything a scene hands out (a clear bonus, an ally's parting gift, the
    Prologue's Rapier) is `scene`."""

    def test_a_flavored_reward_resolves_through_its_fe_base(self):
        chap = {'villages': [{'visit_reward': [{'id': 'frost-brand', 'fe_base': 'steel-sword'}]}]}
        self.assertEqual([kits.Pickup('ITEM_SWORD_STEEL', 'village', 4)],
                         kits.chapter_pickups(chap, 4))

    def test_a_save_all_bonus_is_a_scene_gift_on_both_sides(self):
        self.assertIn(kits.Pickup('ITEM_GUIDINGRING', 'scene', 5), kits.our_pickups(CAMPAIGN))
        self.assertIn(kits.Pickup('ITEM_GUIDINGRING', 'scene', 5), kits.twin_pickups())

    def test_the_twin_splits_by_script_not_by_item(self):
        # A scene and a village both give an Iron Sword; the scene's goes to Eirika by name.
        info = 'Village(EVFLAG_TMP(9), EventScr_V, 1, 1)\n'
        script = ('CONST_DATA EventListScr EventScr_S[] = {\n'
                  '    SVAL(EVT_SLOT_3, ITEM_SWORD_IRON)\n    GIVEITEMTO(CHARACTER_EIRIKA)\n'
                  '    ENDA\n};\n'
                  'CONST_DATA EventListScr EventScr_V[] = {\n'
                  '    SVAL(EVT_SLOT_3, ITEM_SWORD_IRON)\n    GIVEITEMTO(CHAR_EVT_ACTIVE_UNIT)\n'
                  '    ENDA\n};\n')
        import difficulty
        real = difficulty.inject.decomp.vanilla_decomp_text

        def text(rel):
            if rel.endswith('zz-eventinfo.h'):
                return info
            if rel.endswith('zz-eventscript.h'):
                return script
            return real(rel)
        with mock.patch.object(difficulty.inject.decomp, 'vanilla_decomp_text', text):
            t = difficulty.twin_event_payload('zz')
        self.assertEqual([('ITEM_SWORD_IRON', ('CHARACTER_EIRIKA',))],
                         list(zip(t['scene_gifts'], t['scene_gift_to'])))
        self.assertEqual(['ITEM_SWORD_IRON'], t['village_gifts'])


class OurPickupsAreCached(unittest.TestCase):
    def test_a_second_read_does_not_walk_the_chapters_again(self):
        import difficulty
        kits.our_pickups(CAMPAIGN)
        with mock.patch.object(difficulty, 'chapter_economy',
                               side_effect=AssertionError('walked again')):
            kits.our_pickups(CAMPAIGN)


class TwinReadsOnlyWhatItReaches(unittest.TestCase):
    def test_through_stops_the_chain(self):
        self.assertFalse([p for p in kits.twin_pickups(7) if p.chapter > 7])
        self.assertIn(kits.Pickup('ITEM_SWORD_STEEL', 'worldmap_shop', 5), kits.twin_pickups(7))


class OurWorldMap(unittest.TestCase):
    def test_projected_until_stocked(self):
        ours = [p for p in kits.our_pickups(CAMPAIGN) if p.vehicle == 'worldmap_shop']
        twin = [p for p in kits.twin_pickups() if p.vehicle == 'worldmap_shop']
        self.assertEqual({(p.item, p.chapter) for p in twin}, {(p.item, p.chapter) for p in ours})
        self.assertTrue(all(p.projected for p in ours))

    def test_a_stock_list_replaces_the_projection(self):
        nodes = [{'id': 'targos', 'unlocks_after': 'ch01', 'stock': ['iron-sword']}]
        kits._our_pickups.cache_clear()
        self.addCleanup(kits._our_pickups.cache_clear)
        with mock.patch.object(kits, '_our_world_map', return_value=nodes):
            ours = [p for p in kits.our_pickups(CAMPAIGN) if p.vehicle == 'worldmap_shop']
        self.assertEqual([kits.Pickup('ITEM_SWORD_IRON', 'worldmap_shop', 1)], ours)


def member(name, kinds, items=(), char=None):
    """A party member who can wield every weapon of `kinds`."""
    import difficulty

    def can_use(item):
        w = difficulty.item_weapon(item)
        return w is not None and w.kind in kinds
    return kits.Member(name, can_use, tuple(items), char)


class Arsenals(unittest.TestCase):
    P = kits.Pickup

    def names(self, ars, who):
        return [w.name for w in ars[who]]

    def test_join_kit_first(self):
        ars = kits.arsenals([], 1, [member('a', {'axe'}, ['ITEM_AXE_IRON', 'ITEM_AXE_HANDAXE'])],
                            'happy')
        self.assertEqual(['iron-axe', 'hand-axe'], self.names(ars, 'a'))

    def test_guaranteed_drops_village(self):
        picks = [self.P('ITEM_AXE_HANDAXE', 'village', 2)]
        party = [member('a', {'axe'}, ['ITEM_AXE_IRON'])]
        self.assertEqual(['iron-axe'], self.names(kits.arsenals(picks, 3, party, 'guaranteed'), 'a'))
        self.assertEqual(['iron-axe', 'hand-axe'],
                         self.names(kits.arsenals(picks, 3, party, 'happy'), 'a'))

    def test_item_waits_a_chapter(self):
        picks = [self.P('ITEM_AXE_HANDAXE', 'village', 2)]
        party = [member('a', {'axe'}, ['ITEM_AXE_IRON'])]
        self.assertEqual(['iron-axe'], self.names(kits.arsenals(picks, 2, party, 'happy'), 'a'))

    def test_a_scene_gift_is_in_hand_in_its_own_chapter(self):
        """The Prologue's opening scene hands Eirika the Rapier; she fights the Prologue with it."""
        picks = [self.P('ITEM_SWORD_RAPIER', 'scene', 0, ('CHARACTER_EIRIKA',))]
        party = [member('eirika', {'sword'}, ['ITEM_VULNERARY'], 'CHARACTER_EIRIKA')]
        self.assertEqual(['rapier'], self.names(kits.arsenals(picks, 0, party, 'guaranteed'),
                                                'eirika'))

    def test_unwieldable_goes_nowhere(self):
        picks = [self.P('ITEM_LANCE_JAVELIN', 'chest', 1)]
        ars = kits.arsenals(picks, 2, [member('a', {'axe'}, ['ITEM_AXE_IRON'])], 'happy')
        self.assertEqual(['iron-axe'], self.names(ars, 'a'))

    def test_named_recipient_only(self):
        picks = [self.P('ITEM_SWORD_RAPIER', 'scene', 0, ('CHARACTER_EIRIKA',))]
        party = [member('seth', {'sword'}, ['ITEM_SWORD_SILVER'], 'CHARACTER_SETH'),
                 member('eirika', {'sword'}, ['ITEM_SWORD_RAPIER'], 'CHARACTER_EIRIKA')]
        ars = kits.arsenals(picks, 1, party, 'guaranteed')
        self.assertEqual(['sword-silver'], self.names(ars, 'seth'))
        absent = kits.arsenals(picks, 1, party[:1], 'guaranteed')
        self.assertEqual(['sword-silver'], self.names(absent, 'seth'))

    def test_a_gift_for_either_of_two_goes_to_the_first_named(self):
        # Ch14's Audhulma: Joshua if he lives, else Eirika -- whatever the join order.
        picks = [self.P('ITEM_SWORD_RAPIER', 'scene', 1, ('CHARACTER_JOSHUA', 'CHARACTER_EIRIKA'))]
        party = [member('eirika', {'sword'}, [], 'CHARACTER_EIRIKA'),
                 member('joshua', {'sword'}, [], 'CHARACTER_JOSHUA')]
        ars = kits.arsenals(picks, 1, party, 'guaranteed')
        self.assertEqual(['rapier'], self.names(ars, 'joshua'))
        self.assertEqual([], self.names(ars, 'eirika'))

    def test_gift_goes_to_first_who_lacks_it(self):
        picks = [self.P('ITEM_AXE_HANDAXE', 'village', 1)]
        party = [member('a', {'axe'}, ['ITEM_AXE_HANDAXE']), member('b', {'axe'}, ['ITEM_AXE_IRON'])]
        ars = kits.arsenals(picks, 2, party, 'happy')
        self.assertEqual(['hand-axe'], self.names(ars, 'a'))
        self.assertEqual(['iron-axe', 'hand-axe'], self.names(ars, 'b'))

    def test_shop_steel_to_every_sword_user(self):
        picks = [self.P('ITEM_SWORD_STEEL', 'shop', 1)]
        party = [member('a', {'sword'}, ['ITEM_SWORD_IRON']), member('b', {'sword'}, ['ITEM_SWORD_IRON']),
                 member('c', {'axe'}, ['ITEM_AXE_IRON'])]
        ars = kits.arsenals(picks, 2, party, 'happy')
        self.assertIn('steel-sword', self.names(ars, 'a'))
        self.assertIn('steel-sword', self.names(ars, 'b'))
        self.assertNotIn('steel-sword', self.names(ars, 'c'))
        self.assertEqual(['iron-sword'], self.names(kits.arsenals(picks, 2, party, 'guaranteed'), 'a'))

    def test_past_five_slots_an_effective_weapon_is_kept(self):
        # Mt alone would cut the Armorslayer for a Steel Sword the Silver Sword beats outright.
        picks = [self.P(i, 'shop', 1) for i in ('ITEM_SWORD_STEEL', 'ITEM_SWORD_KILLER',
                                                 'ITEM_SWORD_SILVER', 'ITEM_SWORD_BRAVE',
                                                 'ITEM_SWORD_ARMORSLAYER', 'ITEM_SWORD_SLIM')]
        ars = kits.arsenals(picks, 2, [member('a', {'sword'}, ['ITEM_SWORD_IRON'])], 'happy')
        self.assertEqual(5, len(ars['a']))
        self.assertEqual('iron-sword', ars['a'][0].name)
        self.assertIn('armorslayer', self.names(ars, 'a'))
        self.assertNotIn('steel-sword', self.names(ars, 'a'))

    def test_non_weapon_join_items_are_not_weapons(self):
        ars = kits.arsenals([], 1, [member('a', {'axe'}, ['ITEM_AXE_IRON', 'ITEM_VULNERARY'])],
                            'happy')
        self.assertEqual(['iron-axe'], self.names(ars, 'a'))


if __name__ == '__main__':
    unittest.main()
