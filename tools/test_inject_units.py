#!/usr/bin/env python3
"""Tests for tools/inject/units.py.

Run:  python3 tools/test_inject_units.py
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import inject.chapters.ch05
import inject.decomp
import inject.hosts
import inject.paths
import inject.units

# Read the COMMITTED decomp, not the working tree -- the build overwrites donor portrait
# slots (Gilliam/Neimi/Moulder/Vanessa), so a working-tree read would be non-hermetic.
VANILLA = inject.decomp.vanilla_decomp_text('src/data_characters.c')


class CampaignOwnedUnitTables(unittest.TestCase):
    """Campaign rosters live in symbols NAMED for our chapter, not in whichever vanilla
    table the host slot's stripped cutscenes happened to leave unreferenced.

    Squatting cost us twice: the symbol name lied (ch04's moose rides a table our own
    source calls "dead Ch5 unit table"), and it rationed each chapter to the tables its
    host slot freed -- slot 5 freed seven, slot 6 frees three, and ch05 needs seven."""

    HEADER = ('extern CONST_DATA struct UnitDefinition UnitDef_Event_PrologueAlly[];\n'
              'extern CONST_DATA struct UnitDefinition UnitDef_088B61A8[];\n')
    ROWS = ['    {\n        .charIndex = 0xaa,\n    },']

    def test_definition_appends_a_terminated_table_under_our_prefix(self):
        out = inject.units.unit_table_definition('/* udefs */\n', 'MS_Ch05Line', self.ROWS, 'ch05 line')
        self.assertIn('CONST_DATA struct UnitDefinition MS_Ch05Line[] = {', out)
        self.assertIn('.charIndex = 0xaa,', out)
        self.assertIn('{ 0 },', out, 'the table must carry its terminator')
        self.assertTrue(out.startswith('/* udefs */\n'), 'existing content is preserved')

    def test_definition_leaves_the_vanilla_table_it_replaces_untouched(self):
        udefs = ('CONST_DATA struct UnitDefinition UnitDef_088B61A8[] = {\n'
                 '    { .charIndex = 0x80, },\n};\n')
        out = inject.units.unit_table_definition(udefs, 'MS_Ch05Line', self.ROWS, 'ch05 line')
        self.assertIn(udefs, out, 'appending must not disturb the vanilla roster')

    def test_extern_is_added_once_and_is_idempotent(self):
        once = inject.units.unit_table_extern(self.HEADER, 'MS_Ch05Line', 'ch05 line')
        twice = inject.units.unit_table_extern(once, 'MS_Ch05Line', 'ch05 line')
        self.assertEqual(once, twice)
        self.assertEqual(twice.count('MS_Ch05Line[];'), 1)

    def test_extern_declares_before_the_scripts_that_name_it(self):
        out = inject.units.unit_table_extern(self.HEADER, 'MS_Ch05Line', 'ch05 line')
        self.assertIn('extern CONST_DATA struct UnitDefinition MS_Ch05Line[];', out)
        # agbcc needs the decl in the extern block, not appended past the file's tail
        self.assertLess(out.index('MS_Ch05Line'), out.index('UnitDef_088B61A8'))

    def test_a_symbol_without_the_prefix_is_refused(self):
        # The prefix is the whole guarantee: an un-prefixed name is indistinguishable from
        # the vanilla tables, which is the confusion this retires.
        for bad in ('UnitDef_088B61A8', 'Ch05Line'):
            with self.assertRaises(SystemExit):
                inject.units.unit_table_definition('', bad, self.ROWS, 'ch05 line')
            with self.assertRaises(SystemExit):
                inject.units.unit_table_extern(self.HEADER, bad, 'ch05 line')


class ChapterLabelConstants(unittest.TestCase):
    """CHAPTER_L_* names and their VALUES diverge from slot 5 on, because FE8 inserted
    Ch5x at slot 5. Guessing the name from the slot number is right by accident for slots
    1-4 and wrong from 6 -- and wrong FAILS SILENTLY: a gDefeatTalkList entry keyed to the
    wrong .chapter never matches, so the boss dies, no flag is set, DefeatBoss never fires,
    and the chapter simply cannot be won."""

    HEADER = ('enum {\n'
              '    CHAPTER_L_PROLOGUE = 0x00,\n'
              '    CHAPTER_L_4 = 0x04, // Ch4: Ancient Horrors\n'
              '    CHAPTER_L_5X = 0x05, // Ch5x: Unbroken Heart\n'
              '    CHAPTER_L_5 = 0x06, // Ch5: The Empire\'s Reach\n'
              '    CHAPTER_L_6 = 0x07, // Ch6: Victims of War\n'
              '};\n')

    def test_slot_six_is_chapter_l_5_not_chapter_l_6(self):
        # ch05 hosts on slot 6. This single assertion is the whole point of the helper.
        self.assertEqual(inject.units.chapter_label_constant(6, self.HEADER), 'CHAPTER_L_5')

    def test_the_name_matches_the_number_only_below_the_ch5x_insert(self):
        self.assertEqual(inject.units.chapter_label_constant(4, self.HEADER), 'CHAPTER_L_4')
        self.assertEqual(inject.units.chapter_label_constant(5, self.HEADER), 'CHAPTER_L_5X')
        self.assertEqual(inject.units.chapter_label_constant(7, self.HEADER), 'CHAPTER_L_6')

    def test_an_unnamed_slot_is_refused_rather_than_guessed(self):
        with self.assertRaises(SystemExit):
            inject.units.chapter_label_constant(0x40, self.HEADER)

    def test_it_reads_the_real_decomp_header(self):
        # Guards the parse against a chapters.h reformat, and pins the live ch05 answer.
        self.assertEqual(inject.units.chapter_label_constant(inject.hosts.CH05_HOST_INDEX), 'CHAPTER_L_5')
        self.assertEqual(inject.units.chapter_label_constant(inject.hosts.CH03_HOST_INDEX), 'CHAPTER_L_4')


class EventGroupRosterPointer(unittest.TestCase):
    """Declaring our own roster table is half the job -- the ENGINE reads the roster through
    the ChapterEventGroup. A table nobody points at is inert, and the slot silently keeps
    deploying the vanilla one: ch05 shipped one build that put the party on vanilla Ch6's
    start tiles, four of them inside walls, while PREP ran and the load-test PASSed."""

    INFO = ('CONST_DATA EventListScr EventListScr_Ch6_Turn[] = {\n    END_MAIN\n};\n\n'
            'CONST_DATA struct ChapterEventGroup Ch6Events = {\n'
            '    .turnBasedEvents = EventListScr_Ch6_Turn,\n'
            '    .playerUnitsInNormal = UnitDef_Event_Ch6Ally,\n'
            '    .playerUnitsInHard   = UnitDef_Event_Ch6Ally,\n'
            '};\n')

    def test_it_repoints_the_named_field(self):
        out = inject.units.point_event_group_at(self.INFO, 'Ch6Events', 'playerUnitsInNormal',
                                      'MS_Ch05DeployCap')
        self.assertIn('.playerUnitsInNormal = MS_Ch05DeployCap,', out)
        # the OTHER difficulty is a separate decision and must not move on its own
        self.assertIn('.playerUnitsInHard   = UnitDef_Event_Ch6Ally,', out)

    def test_it_does_not_touch_fields_outside_the_group(self):
        out = inject.units.point_event_group_at(self.INFO, 'Ch6Events', 'playerUnitsInNormal',
                                      'MS_Ch05DeployCap')
        self.assertIn('EventListScr EventListScr_Ch6_Turn[] = {', out)
        self.assertIn('.turnBasedEvents = EventListScr_Ch6_Turn,', out)

    def test_a_missing_field_is_refused(self):
        with self.assertRaises(SystemExit):
            inject.units.point_event_group_at(self.INFO, 'Ch6Events', 'nosuchField', 'MS_Ch05DeployCap')

    def test_the_live_ch05_group_deploys_our_table(self):
        """The regression itself. Runs against the INJECTED tree, so it only means anything
        after a build -- skipped on a clean checkout rather than failing or passing vacuously.

        The skip has to key on a symbol only WE write. It used to look for
        `struct ChapterEventGroup Ch6Events`, which is VANILLA's own and is present in a
        pristine checkout -- so the guard never fired, and on CI (which runs `make test` before
        any injection) the assertion ran against vanilla data and reported our roster pointer
        missing. Nobody found out, because this class sat below `unittest.main()` and had never
        run. `MS_Ch05DeployCap` is ours: absent pristine, present once injected.
        """
        if not os.path.exists(inject.paths.CH05_EVENTINFO_H):
            self.skipTest('decomp not present')
        with open(inject.paths.CH05_EVENTINFO_H, encoding='utf-8') as f:
            if inject.chapters.ch05.CH05_ALLY_TABLE not in f.read():
                self.skipTest('tree not injected (no %s) -- run a build first'
                              % inject.chapters.ch05.CH05_ALLY_TABLE)
        inject.units.assert_event_group_roster(inject.paths.CH05_EVENTINFO_H, inject.hosts.CH05_EVENT_GROUP,
                                     inject.chapters.ch05.CH05_ALLY_TABLE)


if __name__ == '__main__':
    unittest.main()
