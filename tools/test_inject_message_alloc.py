#!/usr/bin/env python3
"""Tests for tools/inject/message_alloc.py (#411).

Run:  python3 tools/test_inject_message_alloc.py
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import inject.chapter_ids
import inject.message_alloc as alloc
import inject.messages
import inject.text


class AllocationIsDerivedFromTheLedger(unittest.TestCase):
    """A chapter names the messages it needs; the build numbers them."""

    def test_ids_start_past_vanilla_and_are_dense(self):
        ids = alloc.allocated_message_ids({'ch05': ('a',), 'ch06': ('b', 'c')})
        self.assertEqual(sorted(ids.values()),
                         list(range(alloc.VANILLA_MESSAGE_COUNT,
                                    alloc.VANILLA_MESSAGE_COUNT + 3)))

    def test_chapters_take_contiguous_runs_in_campaign_order(self):
        # Declared out of order on purpose: the dict's order is not the allocation's.
        ids = alloc.allocated_message_ids({'ch06': ('b', 'c'), 'ch05': ('a',)})
        base = alloc.VANILLA_MESSAGE_COUNT
        self.assertEqual(ids, {('ch05', 'a'): base, ('ch06', 'b'): base + 1,
                               ('ch06', 'c'): base + 2})

    def test_a_new_need_in_an_earlier_chapter_costs_no_redesign(self):
        # The point of #411: ch05 needing one more message is a line in the ledger, and the
        # chapters after it renumber themselves -- nothing outside the build names these ids.
        before = alloc.allocated_message_ids({'ch05': ('a',), 'ch06': ('b',)})
        after = alloc.allocated_message_ids({'ch05': ('a', 'new'), 'ch06': ('b',)})
        self.assertEqual(after[('ch06', 'b')], before[('ch06', 'b')] + 1)

    def test_a_key_that_would_not_sort_in_campaign_order_is_refused(self):
        with self.assertRaises(SystemExit) as caught:
            alloc.allocated_message_ids({'prologue': ('a',)})
        self.assertIn('ch00', str(caught.exception))

    def test_a_duplicate_key_is_refused(self):
        with self.assertRaises(SystemExit) as caught:
            alloc.allocated_message_ids({'ch05': ('a', 'a')})
        self.assertIn("'a'", str(caught.exception))

    def test_an_unknown_key_is_refused_by_name(self):
        with self.assertRaises(SystemExit) as caught:
            alloc.appended_message_id('ch05', 'no-such-message')
        self.assertIn('APPENDED_MESSAGES', str(caught.exception))

    def test_shipped_allocation_is_unchanged(self):
        # The ROM-identical half of the done-when, pinned: these three name plates shipped at
        # these ids before allocation existed.
        self.assertEqual(inject.chapter_ids.CH05_MOOSE_NAME_MSG, 0xD4C)
        self.assertEqual(inject.chapter_ids.CH06_BOAT_NAME_MSGS,
                         {'boat-east': 0xD4D, 'boat-west': 0xD4E})


class AllocatedIdsAreClaimed(unittest.TestCase):
    def test_every_allocated_id_is_claimed_by_its_chapter(self):
        claims = inject.messages.HOSTED_CHAPTER_MESSAGE_IDS
        for (chapter, key), mid in alloc.allocated_message_ids().items():
            self.assertIn(mid, claims.get(chapter, ()), '%s %s' % (chapter, key))


class ReservingHeaders(unittest.TestCase):
    """Every allocated id gets its header up front, so no pass depends on another's appends."""

    def _vanilla(self):
        return ['## MSG_D4A', 'x[X]', '', '## MSG_D4B', 'y[X]', '']

    def test_reserve_appends_every_allocated_header_in_order(self):
        lines = self._vanilla()
        inject.text.reserve_message_headers(lines, [0xD4C, 0xD4D])
        self.assertEqual(lines, self._vanilla() + ['## MSG_D4C', '[X]', '',
                                                   '## MSG_D4D', '[X]', ''])

    def test_reserve_is_idempotent(self):
        lines = self._vanilla()
        inject.text.reserve_message_headers(lines, [0xD4C])
        once = list(lines)
        inject.text.reserve_message_headers(lines, [0xD4C])
        self.assertEqual(lines, once)

    def test_a_reserved_header_takes_a_body_like_any_other(self):
        lines = self._vanilla()
        inject.text.reserve_message_headers(lines, [0xD4C, 0xD4D])
        inject.text.set_message_body(lines, 0xD4C, 'Moose[X]')
        self.assertEqual(lines[6:], ['## MSG_D4C', 'Moose[X]', '', '## MSG_D4D', '[X]', ''])

    def test_a_hole_is_refused(self):
        lines = self._vanilla()
        with self.assertRaises(SystemExit):
            inject.text.reserve_message_headers(lines, [0xD4D])

    def test_an_unreserved_id_past_vanilla_still_fails_loudly(self):
        with self.assertRaises(SystemExit):
            inject.text.set_message_body(self._vanilla(), 0xD4C, 'Moose[X]')


if __name__ == '__main__':
    unittest.main()
