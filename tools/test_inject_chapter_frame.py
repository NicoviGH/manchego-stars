#!/usr/bin/env python3
"""Tests for tools/inject/chapter_frame.py: a hosted chapter's frame is written from blank (#412).

Run:  python3 tools/test_inject_chapter_frame.py
"""
import copy
import json
import os
import sys
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import inject.chapters.ch05
import inject.decomp
import inject.hosts
import inject.paths
from inject import chapter_data, chapter_frame, event_group

CH7_INFO = 'src/events/ch7-eventinfo.h'


def vanilla_info():
    return event_group.vanilla_header(CH7_INFO)


def vanilla_row(index=7):
    return json.loads(inject.decomp.vanilla_decomp_text(
        'src/data/chapter_settings.json'))['chapters'][index]


def list_body(info, symbol):
    start = info.index(symbol + '[] =')
    return info[info.index('{', start):info.index('};', start) + 1]


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
        out = chapter_frame.point_event_group_at(self.INFO, 'Ch6Events', 'playerUnitsInNormal',
                                                 'MS_Ch05DeployCap')
        self.assertIn('.playerUnitsInNormal = MS_Ch05DeployCap,', out)
        # the OTHER difficulty is a separate decision and must not move on its own
        self.assertIn('.playerUnitsInHard   = UnitDef_Event_Ch6Ally,', out)

    def test_it_does_not_touch_fields_outside_the_group(self):
        out = chapter_frame.point_event_group_at(self.INFO, 'Ch6Events', 'playerUnitsInNormal',
                                                 'MS_Ch05DeployCap')
        self.assertIn('EventListScr EventListScr_Ch6_Turn[] = {', out)
        self.assertIn('.turnBasedEvents = EventListScr_Ch6_Turn,', out)

    def test_a_missing_field_is_refused(self):
        with self.assertRaises(SystemExit):
            chapter_frame.point_event_group_at(self.INFO, 'Ch6Events', 'nosuchField',
                                               'MS_Ch05DeployCap')

    def test_the_live_ch05_group_deploys_our_table(self):
        """The regression itself, against the INJECTED tree. The skip keys on a symbol only
        WE write: vanilla's own group is present in a pristine checkout, and keying on it once
        made this test assert against vanilla data on CI."""
        if not os.path.exists(inject.paths.CH05_EVENTINFO_H):
            self.skipTest('decomp not present')
        with open(inject.paths.CH05_EVENTINFO_H, encoding='utf-8') as f:
            info = f.read()
        if inject.chapters.ch05.CH05_ALLY_TABLE not in info:
            self.skipTest('tree not injected (no %s) -- run a build first'
                          % inject.chapters.ch05.CH05_ALLY_TABLE)
        for field in event_group.ROSTERS:
            self.assertEqual(inject.chapters.ch05.CH05_ALLY_TABLE,
                             chapter_frame.group_symbol(info, inject.hosts.CH05_EVENT_GROUP,
                                                        field))


class TheEventGroupStartsBlank(unittest.TestCase):
    """Framing vanilla Ch7's group the way ch06 does: what the chapter names, it gets; every
    other list is EMPTY, never the donor's."""

    def frame(self, lists=None, chapter='ch06'):
        return chapter_frame.frame_event_group(
            chapter, vanilla_info(), 'Ch7EventData',
            lists if lists is not None else
            {'miscBasedEvents': '{\n    CauseGameOverIfLordDies\n    END_MAIN\n}'},
            'MS_Ch06DeployCap', ('EventScr_Ch7_BeginningScene', 'EventScr_Ch7_EndingScene'))

    def test_a_list_the_chapter_fills_holds_its_body(self):
        out = self.frame()
        self.assertEqual('{\n    CauseGameOverIfLordDies\n    END_MAIN\n}',
                         list_body(out, 'EventListScr_Ch7_Misc'))

    def test_a_list_the_chapter_does_not_name_is_written_EMPTY(self):
        """Vanilla Ch7's Location list is a Seize plus two Houses. Left to the donor, ch06 would
        offer a Seize on a map with no throne and two visits on painted-over doors."""
        self.assertIn('Seize', list_body(vanilla_info(), 'EventListScr_Ch7_Location'))
        self.assertEqual('{\n    END_MAIN\n}',
                         list_body(self.frame(), 'EventListScr_Ch7_Location'))

    def test_both_difficulties_deploy_the_chapters_roster(self):
        out = self.frame()
        for field in event_group.ROSTERS:
            self.assertEqual('MS_Ch06DeployCap',
                             chapter_frame.group_symbol(out, 'Ch7EventData', field))

    def test_a_pointer_array_list_blanks_to_NULL_not_END_MAIN(self):
        """A tutorial list is an `EventListScr *[]` on some slots: END_MAIN there is an
        int-from-pointer compile error, so the blank follows the declared type."""
        info = 'CONST_DATA EventListScr * EventListScr_Ch3_Tutorials[] = {\n    NULL\n};\n'
        self.assertEqual('{\n    NULL\n}',
                         chapter_frame.blank_list(info, 'EventListScr_Ch3_Tutorials'))
        info = 'CONST_DATA EventListScr EventListScr_Ch4_Tutorial[] = {\n    END_MAIN\n};\n'
        self.assertEqual('{\n    END_MAIN\n}',
                         chapter_frame.blank_list(info, 'EventListScr_Ch4_Tutorial'))

    def test_a_list_that_is_not_an_event_list_is_refused(self):
        with self.assertRaises(SystemExit) as caught:
            self.frame({'traps': '{}'})
        self.assertIn('traps', str(caught.exception))


class NothingIsInheritedByDefault(unittest.TestCase):
    """The rulings are DATA the frame reads, so a field nobody rules on fails the build before
    anything is written -- including a field the decomp's struct gains upstream tomorrow."""

    def frame(self, chapter='ch06', lists=None):
        return chapter_frame.frame_event_group(
            chapter, vanilla_info(), 'Ch7EventData', lists or {}, 'MS_Ch06DeployCap',
            ('EventScr_Ch7_BeginningScene', 'EventScr_Ch7_EndingScene'))

    def test_a_field_nobody_rules_on_stops_the_frame(self):
        with mock.patch.dict(event_group.DECLARED_INHERITED, clear=True):
            with self.assertRaises(SystemExit) as caught:
                self.frame()
        self.assertIn('extraTrapsInHard', str(caught.exception))

    def test_a_chapter_may_keep_its_donors_list_by_declaring_why(self):
        reason = {'chNN': {'locationBasedEvents': 'the donor Seize is ours on purpose'}}
        with mock.patch.dict(event_group.DECLARED_INHERITED_BY_CHAPTER, reason):
            out = self.frame(chapter='chNN')
        self.assertEqual(list_body(vanilla_info(), 'EventListScr_Ch7_Location'),
                         list_body(out, 'EventListScr_Ch7_Location'))

    def test_a_reason_for_a_list_the_chapter_FILLS_is_stale(self):
        reason = {'chNN': {'turnBasedEvents': 'no longer true'}}
        with mock.patch.dict(event_group.DECLARED_INHERITED_BY_CHAPTER, reason):
            with self.assertRaises(SystemExit) as caught:
                self.frame(chapter='chNN', lists={'turnBasedEvents': '{\n    END_MAIN\n}'})
        self.assertIn('stale', str(caught.exception))

    def test_every_hosted_chapter_has_every_group_field_ruled(self):
        for hosted in inject.hosts.hosted_chapters():
            census = event_group.census(hosted.name)
            self.assertEqual(set(event_group.fields()), set(census))
            self.assertNotIn(event_group.UNRULED, census.values(), hosted.name)


class TheSettingsRowStartsBlank(unittest.TestCase):
    """The same rule for the chapter_settings row, framed the way `_retarget_host_chapter` does."""

    def writes(self):
        row = vanilla_row()
        out = dict(('map.' + k, 0) for k in row['map'])
        out.update(('goal.' + k, v) for k, v in row['goal'].items())
        out.update({'mapEventDataId': 1, 'prepScreenNumber': 12, 'fadeToBlack': 1})
        return out

    def test_the_writes_land_and_the_key_order_survives(self):
        row = chapter_frame.frame_settings_row('ch06', vanilla_row(), self.writes())
        self.assertEqual(12, row['prepScreenNumber'])
        self.assertEqual(list(vanilla_row()), list(row))
        self.assertEqual(list(vanilla_row()['goal']), list(row['goal']))

    def test_a_field_the_frame_owns_cannot_be_left_out(self):
        writes = self.writes()
        del writes['fadeToBlack']
        with self.assertRaises(SystemExit) as caught:
            chapter_frame.frame_settings_row('ch06', vanilla_row(), writes)
        self.assertIn('fadeToBlack', str(caught.exception))

    def test_a_field_another_pass_owns_cannot_be_written_here(self):
        writes = dict(self.writes(), initialFogLevel=0)
        with self.assertRaises(SystemExit) as caught:
            chapter_frame.frame_settings_row('ch06', vanilla_row(), writes)
        self.assertIn('apply_chapter_fog', str(caught.exception))

    def test_writing_a_declared_inherited_field_is_a_stale_declaration(self):
        writes = dict(self.writes(), initialWeather=1)
        with self.assertRaises(SystemExit) as caught:
            chapter_frame.frame_settings_row('ch06', vanilla_row(), writes)
        self.assertIn('stale', str(caught.exception))

    def test_a_field_nobody_rules_on_stops_the_frame(self):
        with mock.patch.dict(chapter_data.DECLARED_INHERITED,
                             {'initialWeather': None}):
            with self.assertRaises(SystemExit) as caught:
                chapter_frame.frame_settings_row('ch06', vanilla_row(), self.writes())
        self.assertIn('initialWeather', str(caught.exception))

    def test_a_write_no_table_claims_is_refused(self):
        """The census lists ownership, so a write nobody claims would be listed UNRULED."""
        with mock.patch.dict(chapter_data.DECLARED_INHERITED, {'initialWeather': None}):
            with self.assertRaises(SystemExit) as caught:
                chapter_frame.frame_settings_row('ch06', vanilla_row(),
                                                 dict(self.writes(), initialWeather=1))
        self.assertIn('no frame claims', str(caught.exception))

    def test_a_field_that_is_not_in_the_struct_is_refused(self):
        writes = dict(self.writes(), noSuchField=1)
        with self.assertRaises(SystemExit):
            chapter_frame.frame_settings_row('ch06', vanilla_row(), writes)

    def test_nothing_but_the_writes_changes(self):
        before = vanilla_row()
        after = chapter_frame.frame_settings_row('ch06', copy.deepcopy(before), self.writes())
        changed = [f for f, v in chapter_data.leaves(after).items()
                   if chapter_data.leaves(before)[f] != v]
        self.assertTrue(set(changed) <= set(self.writes()), changed)


class EveryChapterIsFramed(unittest.TestCase):
    def test_a_hosted_chapter_that_skipped_the_frame_fails_the_build(self):
        rows = [inject.hosts.HostedChapter('chNN', 9, 9, 'ChNEvents')]
        with mock.patch.dict(chapter_frame.FRAMED,
                             {'settings': {'chNN'}, 'event_group': set()}):
            with self.assertRaises(SystemExit) as caught:
                chapter_frame.assert_framed(rows)
        self.assertIn('chNN (event_group)', str(caught.exception))

    def test_a_framed_chapter_passes(self):
        rows = [inject.hosts.HostedChapter('chNN', 9, 9, 'ChNEvents')]
        with mock.patch.dict(chapter_frame.FRAMED,
                             {'settings': {'chNN'}, 'event_group': {'chNN'}}):
            self.assertTrue(chapter_frame.assert_framed(rows))


if __name__ == '__main__':
    unittest.main()
