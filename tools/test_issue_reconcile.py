#!/usr/bin/env python3
"""Tests for the pure cores of tools/issue_reconcile.py (no gh/git needed)."""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import issue_reconcile as ir  # noqa: E402


class ClosingRefs(unittest.TestCase):
    def test_recognizes_github_closing_keywords(self):
        log = ('feat: do a thing\n\nCloses #20\n'
               '---\nfix(x): patch\n\nFixes #7, resolved #9\n'
               '---\nchore\n\nRefs #99\n')  # Refs is NOT a closing keyword
        self.assertEqual(ir.closing_ref_numbers(log), {20, 7, 9})

    def test_empty_log_has_no_refs(self):
        self.assertEqual(ir.closing_ref_numbers(''), set())


class ChapterStem(unittest.TestCase):
    def test_prologue_maps_to_ch00(self):
        self.assertEqual(
            ir.chapter_stem_for_title('Prologue — map + events (A Dagger of Ice)'),
            'ch00')

    def test_chapter_numbers_zero_padded(self):
        self.assertEqual(ir.chapter_stem_for_title('Ch1 — The Iron Trail'), 'ch01')
        self.assertEqual(ir.chapter_stem_for_title('Chapter 8 — finale'), 'ch08')

    def test_non_chapter_titles_are_none(self):
        self.assertIsNone(ir.chapter_stem_for_title('Lord-select UX: show summary'))
        self.assertIsNone(ir.chapter_stem_for_title('Battle animations — 10 cast'))


class ShippedStems(unittest.TestCase):
    def test_requires_both_locked_dialogue_and_host_fn(self):
        chapters = {
            'ch00': 'script:  # LOCKED 2026-06-10\n',   # locked + hosted below
            'ch02': 'script:  # LOCKED 2026-06-20\n',   # locked but NOT hosted
            'ch03': 'objective: seize\n',               # neither
        }
        build = 'def inject_prologue(c):\n    pass\ndef inject_ch01(c):\n    pass\n'
        # ch00 -> inject_prologue present; ch02 -> inject_ch02 absent.
        self.assertEqual(ir.shipped_stems(chapters, build), {'ch00'})


class LikelyCloseable(unittest.TestCase):
    def setUp(self):
        self.issues = [
            {'number': 20, 'title': 'Prologue — map + events'},
            {'number': 21, 'title': 'Ch1 — The Iron Trail'},
            {'number': 22, 'title': 'Ch2 — Cold Welcome'},
            {'number': 46, 'title': 'Lord-select UX'},
        ]

    def test_flags_shipped_unclosed_chapter_issue(self):
        out = ir.likely_closeable(self.issues, shipped={'ch00'}, closing_refs=set())
        self.assertEqual([n for n, _, _ in out], [20])

    def test_does_not_flag_when_already_closed_by_commit(self):
        out = ir.likely_closeable(self.issues, shipped={'ch00'}, closing_refs={20})
        self.assertEqual(out, [])

    def test_does_not_flag_locked_but_unhosted_chapter(self):
        # ch02 (#22) has locked dialogue but no host -> not in `shipped` -> skip.
        out = ir.likely_closeable(self.issues, shipped={'ch00', 'ch01'},
                                  closing_refs=set())
        self.assertEqual(sorted(n for n, _, _ in out), [20, 21])

    def test_ignores_non_chapter_issues(self):
        out = ir.likely_closeable(self.issues, shipped={'ch00'}, closing_refs=set())
        self.assertNotIn(46, [n for n, _, _ in out])


if __name__ == '__main__':
    unittest.main()
