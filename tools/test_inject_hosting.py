#!/usr/bin/env python3
"""Tests for tools/inject/hosting.py.

Run:  python3 tools/test_inject_hosting.py
"""
import json
import os
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from inject.namespace import stubbed
import inject.asset_table
import inject.decomp
import inject.hosting
import inject.hosts
import inject.paths
from inject import source as injector  # the injector's source, every file of it (#389)


class HostChapterEventGroup(unittest.TestCase):
    """A hosted chapter must RUN the ChapterEventGroup its injector fills.

    Vanilla's slot index tracks the chapter number only up to 4: FE8 inserts chapter 5X
    at slot 5, so slot 5's mapEventDataId resolves to Ch5XEvents while inject_ch04 writes
    every event into Ch5EventData. Retargeting a host slot rewrites the MAP ids, and the
    map ids alone are enough to make the chapter look right -- so the failure is silent
    and total: the slot presents OUR 15x15 map while running 5X's roster and scripts
    (24 foreign reds off the footprint, the party never deployed, the cursor initialised
    onto an off-map sentinel). Naming the event group is therefore mandatory, not optional.
    """

    TABLE = 'gChapterDataAssetTable'

    def _vanilla_index(self, symbol):
        """`symbol`'s index in the COMMITTED asset table (our injectors only append, so
        vanilla indices are stable -- but read HEAD anyway, never the built tree)."""
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, 'asset_table.s')
            with open(path, 'w', encoding='utf-8') as f:
                f.write(inject.decomp.vanilla_decomp_text('data/data_8B363C.s'))
            return inject.asset_table._asm_table_word_index(path, self.TABLE, symbol)

    def _retarget(self, host_index, event_group):
        """Run _retarget_host_chapter against a throwaway copy of vanilla's settings."""
        vanilla = json.loads(inject.decomp.vanilla_decomp_text('src/data/chapter_settings.json'))
        donor = 3
        goal_type = vanilla['chapters'][donor]['goal']['windowDataType']
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, 'chapter_settings.json')
            with open(path, 'w', encoding='utf-8') as f:
                json.dump(vanilla, f)
            with stubbed('CHAPTER_SETTINGS_JSON', path):
                return inject.hosting._retarget_host_chapter(
                    host_index, donor, goal_type, 'unreachable in this test',
                    (0, 0, 0, 0), 4, event_group=event_group,
                    goal_text_ids=(0x9C4, 0x9C5))

    def test_slot_five_is_chapter_5x_not_chapter_5(self):
        # The trap itself, pinned against vanilla so a decomp bump can't quietly move it.
        vanilla = json.loads(inject.decomp.vanilla_decomp_text('src/data/chapter_settings.json'))
        self.assertEqual(vanilla['chapters'][inject.hosts.CH04_HOST_INDEX]['mapEventDataId'],
                         self._vanilla_index('Ch5XEvents'))
        self.assertNotEqual(self._vanilla_index('Ch5XEvents'),
                            self._vanilla_index(inject.hosts.CH04_EVENT_GROUP))

    def test_ch04_host_slot_is_repointed_off_ch5x_onto_its_own_event_group(self):
        host = self._retarget(inject.hosts.CH04_HOST_INDEX, inject.hosts.CH04_EVENT_GROUP)
        self.assertEqual(host['mapEventDataId'],
                         self._vanilla_index(inject.hosts.CH04_EVENT_GROUP))

    def test_every_hosted_chapter_names_the_event_group_it_fills(self):
        # The earlier slots were correct only because slot index == chapter number there;
        # they are now explicit, so the next hosted chapter cannot inherit the coincidence.
        # Enumerated, NOT listed: a hand-written tuple would leave the next chapter
        # uncovered by the guard written for exactly its failure (#138).
        # The prologue is the one chapter that does not retarget: it frames its own slot and
        # keeps that slot's prep number, which the frame refuses to let a retarget overwrite.
        chapters = [c for c in inject.hosts.hosted_chapters() if c.name != 'prologue']
        self.assertTrue(chapters, 'no hosted chapters discovered')
        for chapter in chapters:
            host = self._retarget(chapter.host_index, chapter.event_group)
            self.assertEqual(host['mapEventDataId'], self._vanilla_index(chapter.event_group),
                             '%s: host slot %d must run %s'
                             % (chapter.name, chapter.host_index, chapter.event_group))

    def test_making_it_explicit_moves_ch04_alone(self):
        """ch01-ch03 must be byte-identical after the repoint -- they were already right,
        so naming the group is a no-op there and the ONLY behaviour change is slot 5."""
        vanilla = json.loads(inject.decomp.vanilla_decomp_text('src/data/chapter_settings.json'))
        for host_index, group in ((inject.hosts.CH01_HOST_INDEX, inject.hosts.CH01_EVENT_GROUP),
                                  (inject.hosts.CH02_HOST_INDEX, inject.hosts.CH02_EVENT_GROUP),
                                  (inject.hosts.CH03_HOST_INDEX, inject.hosts.CH03_EVENT_GROUP)):
            self.assertEqual(vanilla['chapters'][host_index]['mapEventDataId'],
                             self._vanilla_index(group),
                             'slot %d already ran %s -- the repoint must not move it'
                             % (host_index, group))
        self.assertNotEqual(vanilla['chapters'][inject.hosts.CH04_HOST_INDEX]['mapEventDataId'],
                            self._vanilla_index(inject.hosts.CH04_EVENT_GROUP),
                            'ch04 is the one slot the repoint actually changes')


class ChainStep(unittest.TestCase):
    """`chain(src, dst)` is the one chain step (#479): it keeps the step name the ordering
    facts address, and rewrites exactly one dev landing in src's script."""

    def test_the_step_is_named_for_its_seam(self):
        self.assertEqual('chain_ch05_to_ch06', inject.hosting.chain('ch05', 'ch06').__name__)

    def test_it_swaps_the_landing_for_the_mnc2(self):
        hosts = {h.name: h for h in inject.hosts.hosted_chapters()}
        landing = inject.hosting.dev_placeholder_scene()
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, 'script.h')
            with open(path, 'w', encoding='utf-8') as f:
                f.write('{\n' + landing + '    ENDA\n}')
            with mock.patch.object(inject.hosting, 'event_script_path', lambda _i: path):
                inject.hosting.chain('ch05', 'ch06')('rime-of-the-frostmaiden')
            with open(path, encoding='utf-8') as f:
                out = f.read()
            self.assertNotIn(landing, out)
            self.assertIn('MNC2(0x%X) /* -> ch06 "The Maer Monster"' % hosts['ch06'].host_index,
                          out)
            # a second run finds no landing: the chain refuses rather than guessing
            with mock.patch.object(inject.hosting, 'event_script_path', lambda _i: path):
                with self.assertRaises(SystemExit):
                    inject.hosting.chain('ch05', 'ch06')('rime-of-the-frostmaiden')


if __name__ == '__main__':
    unittest.main()
