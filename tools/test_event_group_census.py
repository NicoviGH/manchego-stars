#!/usr/bin/env python3
"""Every ChapterEventGroup field is WRITTEN or DECLARED-INHERITED, and nothing else (#313).

A hosted chapter adopts a vanilla host slot, and every field we do not declare silently keeps
the donor's value. That has bitten five times -- goal text ids (#207), battle grounds (#289),
difficulty numbers (#303), `.traps` (#306), and the encounter rosters, still live -- and every
one was found by something else going wrong.

The answer is not a better runbook: it is to enumerate the full attribute set and require every
attribute to be accounted for. Same shape as `terraform import`.

Run: python3 tools/test_event_group_census.py
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from inject import event_group


class TheFieldSet(unittest.TestCase):
    def test_fields_are_read_from_the_decomp_struct(self):
        """From the source, not from recollection: a field added to the struct upstream has to
        show up here on its own, or the census silently stops covering it."""
        fields = event_group.fields()
        self.assertEqual(20, len(fields))
        self.assertEqual('turnBasedEvents', fields[0])
        self.assertEqual('endingSceneEvents', fields[-1])
        self.assertIn('traps', fields)
        self.assertIn('enemyUnitsChoice3InEncounter', fields)

    def test_the_field_order_is_the_struct_order(self):
        """Pinned so the parse cannot silently start following something other than the
        struct. Identity comes from the field NAME (the group ships as designated
        initializers), so order is a sanity check here rather than the thing being relied on."""
        fields = event_group.fields()
        self.assertEqual(fields.index('traps') + 1, fields.index('extraTrapsInHard'))
        self.assertLess(fields.index('playerUnitsInNormal'),
                        fields.index('playerUnitsChoice1InEncounter'))


VANILLA = """
CONST_DATA struct ChapterEventGroup Ch6Events = {
    .turnBasedEvents      = EventListScr_Ch6_Turn,
    .characterBasedEvents = EventListScr_Ch6_Character,
    .traps                = TrapData_Event_Ch6,
    .playerUnitsInNormal  = UnitDef_088B6540,
};
"""

OURS = """
CONST_DATA struct ChapterEventGroup Ch6Events = {
    .turnBasedEvents      = MS_Ch05Turn,
    .characterBasedEvents = EventListScr_Ch6_Character,
    .traps                = MS_Ch05Traps,
    .playerUnitsInNormal  = UnitDef_088B6540,
};
"""


class ReadingAGroup(unittest.TestCase):
    def test_the_group_is_read_by_FIELD_NAME(self):
        """The group ships as designated initializers, so a field is named where it is set --
        it cannot be misread by position the way the compiled `.word` list can."""
        got = event_group.initializer('Ch6Events', VANILLA)
        self.assertEqual('EventListScr_Ch6_Turn', got['turnBasedEvents'])
        self.assertEqual('TrapData_Event_Ch6', got['traps'])

    def test_a_missing_group_is_an_error_not_an_empty_read(self):
        """An empty read would classify every field as inherited and pass the census in
        silence -- the exact outcome this guard exists to make impossible."""
        with self.assertRaises(KeyError):
            event_group.initializer('Ch9Events', VANILLA)


class Classifying(unittest.TestCase):
    def setUp(self):
        self.ours = event_group.initializer('Ch6Events', OURS)
        self.vanilla = event_group.initializer('Ch6Events', VANILLA)

    def test_a_field_we_changed_is_WRITTEN_and_one_we_did_not_is_INHERITED(self):
        got = event_group.classify(
            ['turnBasedEvents', 'characterBasedEvents', 'traps', 'playerUnitsInNormal'],
            self.ours, self.vanilla)
        self.assertEqual('WRITTEN', got['turnBasedEvents'])
        self.assertEqual('INHERITED', got['characterBasedEvents'])
        self.assertEqual('WRITTEN', got['traps'])
        self.assertEqual('INHERITED', got['playerUnitsInNormal'])

    def test_every_struct_field_gets_a_verdict_even_if_nobody_sets_it(self):
        """A field the census does not rule on is the silent inheritance this exists to
        prevent, so an uninitialised one is ABSENT rather than missing from the result."""
        got = event_group.classify(event_group.fields(), self.ours, self.vanilla)
        self.assertEqual(set(event_group.fields()), set(got))
        self.assertEqual('ABSENT', got['endingSceneEvents'])


class WhatInheritedActuallyMeans(unittest.TestCase):
    """The subtlety this guard turns on, and the one that makes a pointer comparison useless.

    Our injectors mostly keep the donor's SYMBOL and rewrite what it points AT --
    `EventListScr_Ch6_Turn` is still called that and contains none of vanilla's events. A
    census that compares the initializer token calls all of those INHERITED, which is both
    wrong and unusable: it would demand a declared reason for twenty fields per chapter,
    almost all of them false. What leaks the donor's DATA is a field whose target is still
    vanilla's, so that is what has to be compared.
    """

    def test_a_field_whose_TARGET_was_rewritten_is_written_even_if_the_pointer_is_not(self):
        got = event_group.census('ch05')
        # #306 declared ch05's traps empty by rewriting TrapData_Event_Ch6 to TRAP_NONE,
        # leaving `.traps = TrapData_Event_Ch6` untouched. A pointer census calls this
        # INHERITED, which is exactly backwards.
        self.assertEqual('WRITTEN', got['traps'])

    def test_the_event_lists_are_ours_although_they_keep_vanillas_names(self):
        got = event_group.census('ch05')
        for field in ('turnBasedEvents', 'characterBasedEvents', 'locationBasedEvents',
                      'miscBasedEvents'):
            self.assertEqual('WRITTEN', got[field], field)


class TheLiveCensus(unittest.TestCase):
    """Against the real decomp, which is the only place the finding can come from."""

    def test_every_hosted_chapter_s_group_can_be_located_and_read(self):
        from inject import hosts
        for hosted in hosts.hosted_chapters():
            path = event_group.header_for(hosted.event_group)
            self.assertTrue(path.endswith('.h'), hosted.event_group)

    def test_ch05_still_inherits_the_six_encounter_rosters(self):
        """The finding #313 was opened to surface, asserted so it cannot quietly change
        without somebody ruling on it. ch05 hosts on slot 6, so these are vanilla Ch6's
        SKIRMISH rosters -- dormant only while no world map is exposed."""
        got = event_group.census('ch05')
        for field in event_group.fields():
            if 'InEncounter' in field:
                self.assertEqual('INHERITED', got[field], field)


class UnclassifiedIsABuildFailure(unittest.TestCase):
    """The deliverable: the field-inheritance failure class stops being discoverable only by
    shipping a bug. Five instances found it the hard way -- goal text ids, battle grounds,
    difficulty numbers, `.traps`, and the encounter rosters."""

    def test_the_live_tree_passes_because_every_inherited_field_is_declared(self):
        event_group.assert_census_declared()

    def test_an_undeclared_inherited_field_fails_the_build(self):
        with self.assertRaises(SystemExit) as caught:
            event_group.assert_census_declared(
                censuses={'ch05': {'tutorialEvents': event_group.INHERITED}},
                declared={})
        self.assertIn('tutorialEvents', str(caught.exception))

    def test_a_declaration_for_a_field_we_actually_WRITE_is_stale_and_fails(self):
        """A reason nobody needs is a reason nobody rechecks. Left standing, it is how a
        field that used to be inherited keeps a stale justification after it stops being."""
        with self.assertRaises(SystemExit) as caught:
            event_group.assert_census_declared(
                censuses={'ch05': {'traps': event_group.WRITTEN}},
                declared={'traps': 'we do not inherit this'})
        self.assertIn('traps', str(caught.exception))

    def test_a_NEW_struct_field_nobody_has_ruled_on_fails(self):
        """Scope item three: a field appearing in the struct fails the build until somebody
        rules on it. That is the whole point -- the guard has to notice what we did not."""
        with self.assertRaises(SystemExit):
            event_group.assert_census_declared(
                censuses={'ch05': {'someNewFieldUpstreamAdded': event_group.INHERITED}},
                declared={})

    def test_the_six_encounter_rosters_are_declared_KEPT_for_the_world_map(self):
        """Nicolas, 2026-08-23: vanilla has optional skirmishes, so we do too -- the rosters
        get authored with the world map (#29). They are DECLARED-INHERITED for that reason,
        not nulled: nulling would have foreclosed the feature, and `GetChapterSkirmishLeaderClasses`
        dereferences all three enemy rosters unconditionally anyway."""
        for field, reason in event_group.DECLARED_INHERITED.items():
            if 'InEncounter' in field:
                self.assertIn('#29', reason, field)


if __name__ == '__main__':
    unittest.main()
