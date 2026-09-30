#!/usr/bin/env python3
"""Tests for tools/inject/villages.py.

Run:  python3 tools/test_inject_villages.py
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import inject.chapter_ids
import inject.hosting
import inject.villages


class VillageBoxSpeakers(unittest.TestCase):
    """`visit_text` may name a speaker per box, the same `- who: "line"` form the chapter
    scene scripts already use. ch02's south hut needs it: the resident carries vanilla's
    alarm and Glimmerfrost hands over the token, and she cannot be given the resident's
    face -- chwinga have their own bust and never speak."""

    def test_a_plain_string_belongs_to_the_default_speaker(self):
        # ch04/ch05 author flat strings and must keep working untouched.
        self.assertEqual([('resident', 'Line one.'), ('resident', 'Line two.')],
                         inject.villages.village_boxes({'id': 'v', 'visit_text': ['Line one.',
                                                                     'Line two.']}))

    def test_a_mapping_names_its_speaker(self):
        boxes = inject.villages.village_boxes({'id': 'v', 'visit_text': [
            {'resident': 'What? B-bandits?!'},
            {'chwinga-glimmer': '(It presses meltwater on you.)'}]})
        self.assertEqual([('resident', 'What? B-bandits?!'),
                          ('chwinga-glimmer', '(It presses meltwater on you.)')], boxes)

    def test_a_box_naming_two_speakers_is_refused(self):
        # One box is one A-press by one person; two keys would silently drop a line.
        with self.assertRaises(SystemExit):
            inject.villages.village_boxes({'id': 'v', 'visit_text': [{'a': 'x', 'b': 'y'}]})

    def test_a_flowed_scalar_is_still_refused(self):
        with self.assertRaises(SystemExit):
            inject.villages.village_boxes({'id': 'v', 'visit_text': 'one long flowed line'})


class VillageGiftsInheritVanilla(unittest.TestCase):
    """On a retile, WHICH gift sits on WHICH tile is vanilla's decision.

    Worth a gate because the failure is invisible to every other one: swap two gifts and the
    item set, the economy total and the parity verdict are all unchanged, while the chapter's
    risk/reward inverts. ch05 shipped with booster-def and torch swapped -- the richest gift
    ended up on the safest site, and the cheapest on the one the turn-2 raiders reach first."""

    INFO = ('CONST_DATA EventListScr EventListScr_Ch5_Location[] = {\n'
            '    Armory(ShopList_Event_Ch5Armory, 2, 1)\n'
            '    Village(EVFLAG_TMP(8),  EventScr_A, 12, 10)\n'
            '    Village(EVFLAG_TMP(9),  EventScr_B, 12, 19)\n'
            '    END_MAIN\n};\n')
    SCRIPT = ('CONST_DATA EventListScr EventScr_A[] = {\n'
              '    SVAL(EVT_SLOT_3, 0xe)\n    GIVEITEMTO(CHAR_EVT_ACTIVE_UNIT)\n};\n'
              'CONST_DATA EventListScr EventScr_B[] = {\n'
              '    SVAL(EVT_SLOT_3, 0x60)\n    GIVEITEMTO(CHAR_EVT_ACTIVE_UNIT)\n};\n')
    ITEMS = {'armorslayer': 'ITEM_SWORD_ARMORSLAYER', 'booster-def': 'ITEM_BOOSTER_DEF',
             'torch': 'ITEM_TORCH'}

    def _gifts(self):
        return inject.villages.vanilla_village_gifts('Ch5Map', self.INFO, self.SCRIPT)

    def _chap(self, tile, gift):
        return {'map': {'vanilla_layout': 'Ch5Map'},
                'villages': [{'id': 'v', 'tile': list(tile),
                              'visit_reward': [{'id': gift, 'amount': 1}]}]}

    def test_it_reads_the_gift_out_of_the_village_script(self):
        # the tile is in the Location list, the ITEM is a raw id inside the script it names --
        # which is why it is easy to have the data and never actually look at it
        self.assertEqual(self._gifts(),
                         {(12, 10): 'ITEM_SWORD_ARMORSLAYER', (12, 19): 'ITEM_BOOSTER_DEF'})

    def test_a_matching_gift_passes(self):
        inject.villages.assert_village_gifts_match_vanilla(
            self._chap((12, 19), 'booster-def'), self.ITEMS, self._gifts())

    def test_a_swapped_gift_is_refused(self):
        with self.assertRaises(SystemExit) as caught:
            inject.villages.assert_village_gifts_match_vanilla(
                self._chap((12, 19), 'torch'), self.ITEMS, self._gifts())
        self.assertIn('vanilla_gift_divergence', str(caught.exception),
                      'the error must name the escape hatch')

    def test_a_declared_divergence_is_allowed(self):
        chap = self._chap((12, 19), 'torch')
        chap['villages'][0]['vanilla_gift_divergence'] = 'the tomb has no armoury tier yet'
        inject.villages.assert_village_gifts_match_vanilla(chap, self.ITEMS, self._gifts())

    def test_a_site_vanilla_does_not_have_is_left_alone(self):
        # a village we ADDED, not moved -- nothing to inherit
        inject.villages.assert_village_gifts_match_vanilla(
            self._chap((3, 3), 'torch'), self.ITEMS, self._gifts())

    def test_a_from_scratch_canvas_is_skipped(self):
        chap = self._chap((12, 19), 'torch')
        chap['map'] = {}                      # no vanilla_layout -> no vanilla to inherit
        inject.villages.assert_village_gifts_match_vanilla(chap, self.ITEMS, self._gifts())

    def test_an_unmapped_reward_id_is_refused(self):
        with self.assertRaises(SystemExit):
            inject.villages.assert_village_gifts_match_vanilla(
                self._chap((12, 19), 'nonesuch'), self.ITEMS, self._gifts())

    def test_the_live_ch05_villages_inherit_vanilla(self):
        chap = inject.hosting._load_chapter_yaml('rime-of-the-frostmaiden', inject.chapter_ids.CH05_CHAPTER_YAML)
        inject.villages.assert_village_gifts_match_vanilla(chap, inject.chapter_ids.CH05_ITEM_IDS)


class LocationEventsAreBuiltFromTheYaml(unittest.TestCase):
    """An empty Location list makes every reward on the map unobtainable while the map still
    draws it -- ch04's unreachable Iron Axe, and ch05's four villages plus an armory and vendor."""

    VILLAGES = [{'id': 'a', 'tile': [12, 19], 'visit_reward': [{'id': 'booster-def'}]},
                {'id': 'b', 'tile': [5, 1]}]
    SLOTS = {'a': 'MS_Ch05VisitSouth', 'b': 'MS_Ch05VisitNorth'}

    def test_each_village_rides_its_own_script_at_its_own_tile(self):
        body = inject.villages.location_events(self.VILLAGES, self.SLOTS)
        self.assertIn('Village(0, MS_Ch05VisitSouth, 12, 19)', body)
        self.assertIn('Village(0, MS_Ch05VisitNorth, 5, 1)', body)
        self.assertTrue(body.rstrip().endswith('END_MAIN\n}'))

    def test_a_village_with_no_reward_says_so_rather_than_naming_an_item(self):
        body = inject.villages.location_events(self.VILLAGES, self.SLOTS)
        self.assertIn('the line is the reward', body)

    def test_a_village_given_an_event_id_carries_it_into_the_macro(self):
        """The event id is the whole village-raid race (#25). `Village(eid, ..)` expands to the
        VILL *and* a LOCA on the tile above -- the destruction hook AiPillageAction fires -- and
        SearchAvailableEvent skips an entry whose flag is SET. So the flag is what records a
        visit, what disarms the raider, and what the save-all payout later reads with
        CHECK_EVENTID. Flag 0 is EVFLAG_ALWAYS_FALSE: CheckChapterFlag(0) returns 0 forever, so
        a 0 village is never visited, never safe, and can never be counted."""
        body = inject.villages.location_events(self.VILLAGES, self.SLOTS,
                                  flags={'a': 'EVFLAG_TMP(9)', 'b': 'EVFLAG_TMP(10)'})
        self.assertIn('Village(EVFLAG_TMP(9), MS_Ch05VisitSouth, 12, 19)', body)
        self.assertIn('Village(EVFLAG_TMP(10), MS_Ch05VisitNorth, 5, 1)', body)

    def test_shops_need_no_script_and_no_text(self):
        body = inject.villages.location_events([], {}, (('Armory', 'ShopList_Event_Ch5Armory', 2, 1),
                                          ('Vendor', 'ShopList_Event_Ch5Vendor', 6, 10)))
        self.assertIn('Armory(ShopList_Event_Ch5Armory, 2, 1)', body)
        self.assertIn('Vendor(ShopList_Event_Ch5Vendor, 6, 10)', body)

    def test_village_reward_item_uses_the_chapters_own_map(self):
        """It used to close over CH04_ITEM_IDS, which made a shared helper silently ch04-only:
        ch05's stat boosters are not in that dict, so the first reuser would die on a KeyError."""
        village = {'id': 'a', 'visit_reward': [{'id': 'booster-def'}]}
        self.assertEqual(inject.villages.village_reward_item(village, {'booster-def': 'ITEM_BOOSTER_DEF'}),
                         'ITEM_BOOSTER_DEF')
        self.assertIsNone(inject.villages.village_reward_item({'id': 'b'}, {}))


if __name__ == '__main__':
    unittest.main()
