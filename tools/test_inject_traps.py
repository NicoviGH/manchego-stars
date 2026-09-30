#!/usr/bin/env python3
"""Tests for tools/inject/traps.py.

Run:  python3 tools/test_inject_traps.py
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from inject.namespace import stubbed
import inject.hosting
import inject.traps
import inject.warm


class ChapterTraps(unittest.TestCase):
    """A hosted chapter DECLARES its traps; it never inherits the donor group's (#302/#303).

    The fourth instance of the same defect as the goal text ids (#207), the battle grounds
    and the difficulty numbers: `.traps` lives on the ChapterEventGroup, our injectors fill
    the group but never wrote that field, so a chapter kept whatever its donor carried.

    It was one chapter away from biting. ch05 fills `Ch6Events`, which is clean -- but the
    hosting pattern puts ch06 on slot 7 filling `Ch7Events`, and vanilla Ch7 (group `Ch7EventData`) carries
    TWO ballistae, at (17,8) and (2,10). ch06 would have shipped with enemy ballistae at another
    chapter's coordinates, in every mode, chosen by nobody.

    The build now WRITES the declaration every time, so inheritance is impossible by
    construction rather than by luck; a chapter that declares nothing gets TRAP_NONE.
    """

    def test_a_chapter_that_declares_nothing_renders_an_empty_table(self):
        self.assertEqual(inject.traps.trap_data_body([]), '    /* type */ TRAP_NONE')

    def test_a_declared_ballista_renders_vanillas_row_shape(self):
        body = inject.traps.trap_data_body(inject.traps.chapter_traps(
            {'traps': [{'type': 'ballista', 'x': 17, 'y': 8, 'item': 'ITEM_BALLISTA_REGULAR'}]}))
        self.assertIn('/* type */ TRAP_BALLISTA', body)
        self.assertIn('/* xPos */ 17', body)
        self.assertIn('/* yPos */ 8', body)
        self.assertIn('ITEM_BALLISTA_REGULAR', body)
        self.assertTrue(body.rstrip().endswith('TRAP_NONE'), 'table must be terminated')

    def test_an_unknown_trap_type_is_refused(self):
        with self.assertRaises(SystemExit):
            inject.traps.chapter_traps({'traps': [{'type': 'bear-trap', 'x': 1, 'y': 1}]})

    def test_only_types_the_engine_actually_places_are_offered(self):
        # `LoadTrapData` (bmtrap.c:245) has NO case for TRAP_OBSTACLE / TRAP_TORCHLIGHT /
        # TRAP_LIGHT_RUNE -- declaring one builds green and places nothing, the exact
        # silent runtime behaviour the whitelist exists to prevent. And TRAP_LIGHTARROW
        # falls THROUGH into AddGorgonEggTrap, because its `break` sits behind `#if BUGFIX`
        # and BUGFIX is defined nowhere in the submodule: a light arrow also hatches an
        # undeclared gorgon egg. None of the four are offerable.
        for token in ('obstacle', 'torchlight', 'light-rune', 'light-arrow'):
            self.assertNotIn(token, inject.traps.TRAP_TYPES, '%s is not placeable' % token)
        for token in ('ballista', 'firetile', 'gas', 'mine', 'gorgon-egg'):
            self.assertIn(token, inject.traps.TRAP_TYPES)

    def test_a_coordinate_outside_the_byte_range_is_refused(self):
        with self.assertRaises(SystemExit):
            inject.traps.chapter_traps({'traps': [{'type': 'gas', 'x': 999, 'y': 1}]})

    def test_a_ballista_without_ammunition_is_refused(self):
        # AddBallista (bmarch.c:89) takes `subtype` as the ITEM, and 0 means zero uses --
        # a ballista nothing can fire, with no build error.
        with self.assertRaises(SystemExit):
            inject.traps.chapter_traps({'traps': [{'type': 'ballista', 'x': 1, 'y': 1}]})

    def test_more_traps_than_the_engine_has_slots_is_refused(self):
        # AddTrap (bmtrick.c:113) scans sTrapPool for a free slot with NO bound.
        rows = [{'type': 'gas', 'x': 1, 'y': 1}] * (inject.traps.TRAP_MAX_COUNT + 1)
        with self.assertRaises(SystemExit):
            inject.traps.chapter_traps({'traps': rows})

    def test_a_non_integer_count_exits_cleanly(self):
        # Bare int() raised an uncaught ValueError traceback instead of a build error.
        with self.assertRaises(SystemExit):
            inject.traps.chapter_traps({'traps': [{'type': 'gas', 'x': 1, 'y': 1, 'count': 'two'}]})

    def test_a_count_that_truncates_in_a_u8_is_refused(self):
        with self.assertRaises(SystemExit):
            inject.traps.chapter_traps({'traps': [{'type': 'gas', 'x': 1, 'y': 1, 'count': 9999}]})

    def test_two_chapters_sharing_a_trap_symbol_is_refused(self):
        # chapter_trap_tables keys by SYMBOL, so a collision would silently drop one
        # chapter's declaration in a real build.
        with stubbed('_chapter_trap_symbol', lambda group: 'TrapData_Event_Ch1'):
            with self.assertRaises(SystemExit):
                inject.traps.chapter_trap_tables('rime-of-the-frostmaiden')

    def test_the_patched_file_is_restored_between_builds(self):
        # The pass rewrites events_trapdata.c every build. Without it in the restore list
        # the previous build's rows survive a rehost or a branch switch -- the same silent
        # inheritance this change removes, moved one level up.
        self.assertIn('src/events_trapdata.c', inject.warm.PATCHED_DECOMP_FILES)

    def test_every_hosted_chapter_declares_or_inherits_nothing(self):
        # Today all six donor tables are empty, so nothing is owed. The guard exists for
        # the first chapter whose donor is NOT -- ch06 on Ch7Events.
        self.assertEqual(inject.traps.inherited_traps_undeclared('rime-of-the-frostmaiden'), [])

    def test_the_guard_fires_when_a_donor_carries_traps_the_chapter_ignores(self):
        # Simulates ch06's situation: a chapter that declares NOTHING, filling a donor group
        # that carries ballistae. All six live chapters declare `traps: []`, so the silent
        # case has to be constructed -- which is the point of having declared them.
        real_load = inject.hosting._load_chapter_yaml

        def undeclared(campaign, filename):
            chap = dict(real_load(campaign, filename))
            chap.pop('traps', None)
            return chap

        with stubbed('_vanilla_trap_kinds',
                     lambda sym: ['TRAP_BALLISTA'] if sym.endswith('Ch6') else []), \
                stubbed('_load_chapter_yaml', undeclared):
            stranded = inject.traps.inherited_traps_undeclared('rime-of-the-frostmaiden')
        self.assertIn('ch05', stranded)

    def test_a_declared_empty_list_silences_the_guard(self):
        # `traps: []` is a DECISION, and must read as one -- not as "said nothing".
        with stubbed('_vanilla_trap_kinds', lambda sym: ['TRAP_BALLISTA']):
            self.assertEqual(inject.traps.inherited_traps_undeclared('rime-of-the-frostmaiden'), [])

    def test_the_write_pass_clears_every_hosted_chapters_table(self):
        written = inject.traps.chapter_trap_tables('rime-of-the-frostmaiden')
        from inject import hosts
        self.assertEqual(len(written), len(list(hosts.hosted_chapters())))
        for symbol, body in written.items():
            self.assertTrue(symbol.startswith('TrapData_Event_'), symbol)
            self.assertIn('TRAP_NONE', body)


if __name__ == '__main__':
    unittest.main()
