#!/usr/bin/env python3
"""Tests for tools/verdict_diff.py -- the per-PR parity verdict diff (#510 step 0).

The live read is ~50s and needs a base worktree, so these pin the pure half: what counts as
moved, and what the markdown says about it.

Run: python3 tools/test_verdict_diff.py
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import verdict_diff as vd


def row(verdict='OK', tr=1.0, lr=1.0, **kw):
    r = {'verdict': verdict, 'threat_ratio': tr, 'load_ratio': lr, 'accepted_adr': None,
         'boss_drop': False, 'role': [], 'ai': [], 'locked': False}
    r.update(kw)
    return r


def snap(**rows_by_mode):
    return {m: dict(rows_by_mode.get(m, {})) for m in vd.MODES}


class Moved(unittest.TestCase):
    def test_a_ratio_below_print_precision_does_not_move(self):
        self.assertEqual(vd._moved(row(tr=1.061), row(tr=1.064)), [])

    def test_a_small_move_across_a_rounding_boundary_moves(self):
        self.assertEqual(vd._moved(row(tr=1.064), row(tr=1.066)), ['threat_ratio'])

    def test_a_ratio_the_curve_would_print_differently_moves(self):
        self.assertEqual(vd._moved(row(lr=1.36), row(lr=1.30)), ['load_ratio'])

    def test_a_finding_moves_without_the_verdict(self):
        self.assertEqual(vd._moved(row(), row(role=['boss folds'])), ['role'])

    def test_a_row_that_appears_moves(self):
        self.assertEqual(vd._moved(None, row()), ['row'])

    def test_lock_is_not_a_verdict(self):
        # #510 unlocks every chapter: that must not read as every row moving.
        self.assertEqual(vd._moved(row(locked=True), row(locked=False)), [])


class Render(unittest.TestCase):
    def test_nothing_moved_still_prints_the_grid(self):
        s = snap(table={'CH1 ch01': row()})
        md = vd.render(s, s)
        self.assertIn('**0 verdict(s) changed**, 0 row(s) moved', md)
        self.assertIn('| CH1 ch01 | OK |', md)
        self.assertIn('No verdict, ratio or finding moved.', md)

    def test_a_flip_is_bold_and_counted(self):
        before = snap(normal={'CH4 ch04': row(lr=1.20)})
        after = snap(normal={'CH4 ch04': row('OFF', lr=1.30)})
        md = vd.render(before, after)
        self.assertIn('**1 verdict(s) changed**', md)
        self.assertIn('**OK → OFF**', md)
        self.assertIn('| CH4 ch04 | normal | OK → OFF | x1.00 → x1.00 | x1.20 → x1.30 |  |',
                      md)

    def test_chapters_sort_by_number_not_text(self):
        s = snap(table={'CH10 ch10': row(), 'CH2 ch02': row()})
        md = vd.render(s, s)
        self.assertLess(md.index('CH2 ch02'), md.index('CH10 ch10'))


class OldTreeText(unittest.TestCase):
    LINE = ('  CH1 ch01-the-iron-trai FE8 Ch1       17.7 (x1.06)      3.0 (x1.36)       30%'
            '     OK  [locked]  [accepted ADR 0042]')

    def test_numbers_read_off_a_printed_row(self):
        self.assertEqual(vd._numbers_from_text(self.LINE, 'CH1 ch01-the-iron-trai'),
                         (1.06, 1.36, 42))


if __name__ == '__main__':
    unittest.main()
