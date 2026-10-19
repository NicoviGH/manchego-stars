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
        s = snap(normal={'CH1 ch01': row()})
        md = vd.render(s, s)
        self.assertIn('**0 verdict(s) changed**, 0 row(s) moved', md)
        self.assertIn('| CH1 ch01 |  | OK |  |', md)
        self.assertIn('No verdict, ratio or finding moved.', md)

    def test_a_flip_is_bold_and_counted(self):
        before = snap(normal={'CH4 ch04': row(lr=1.20)})
        after = snap(normal={'CH4 ch04': row('OFF', lr=1.30)})
        md = vd.render(before, after)
        self.assertIn('**1 verdict(s) changed**', md)
        self.assertIn('**OK → OFF**', md)
        self.assertIn('| CH4 ch04 | normal | OK → OFF | x1.00 → x1.00 | x1.20 → x1.30 |  |',
                      md)

    def test_a_changed_finding_is_spelled_out_once_across_modes(self):
        before = snap(normal={'CH3 ch03': row()}, tutorial={'CH3 ch03': row()})
        after = snap(normal={'CH3 ch03': row(role=['boss folds'])},
                     tutorial={'CH3 ch03': row(role=['boss folds'])})
        md = vd.render(before, after)
        self.assertIn('- CH3 ch03, new (tutorial, normal): boss folds', md)
        self.assertEqual(md.count('boss folds'), 1)

    def test_chapters_sort_by_number_not_text(self):
        s = snap(normal={'CH10 ch10': row(), 'CH2 ch02': row()})
        md = vd.render(s, s)
        self.assertLess(md.index('CH2 ch02'), md.index('CH10 ch10'))


class OldTreeText(unittest.TestCase):
    LINE = ('  CH1 ch01-the-iron-trai FE8 Ch1       17.7 (x1.06)      3.0 (x1.36)       30%'
            '     OK  [locked]  [accepted ADR 0042]')

    def test_numbers_read_off_a_printed_row(self):
        self.assertEqual(vd._numbers_from_text(self.LINE, 'CH1 ch01-the-iron-trai'),
                         (1.06, 1.36, 42))


class ParityInputs(unittest.TestCase):
    """`needed` skips the diff when no parity input changed, so a file the read depends on
    and the list misses would let a PR move a verdict unseen. Trace a real read instead of
    trusting the list: every module it loads and every file it opens must be covered."""

    @classmethod
    def setUpClass(cls):
        import contextlib
        import io
        root = vd.REPO
        cls.opened = set()

        def hook(event, args):
            if event == 'open' and isinstance(args[0], str):
                p = os.path.abspath(args[0])
                if p.startswith(root + os.sep) and '__pycache__' not in p:
                    cls.opened.add(os.path.relpath(p, root))
        sys.addaudithook(hook)
        with contextlib.redirect_stdout(io.StringIO()):
            import difficulty
            difficulty.curve_report(vd.CAMPAIGN, mode='normal')
        cls.modules = {os.path.relpath(m.__file__, root) for m in list(sys.modules.values())
                       if getattr(m, '__file__', None)
                       and os.path.abspath(m.__file__).startswith(root + os.sep)}
        cls.inputs = vd.parity_inputs()

    def test_every_module_the_read_loads_is_an_input(self):
        missed = sorted(m for m in self.modules
                        if not vd.touches_parity([m], self.inputs)
                        and not m.startswith('tools/test_'))
        self.assertEqual(missed, [])

    def test_every_file_the_read_opens_is_an_input(self):
        missed = sorted(p for p in self.opened - self.modules
                        if not p.endswith('.py') and not vd.touches_parity([p], self.inputs))
        self.assertEqual(missed, [])

    def test_a_sprite_or_a_probe_is_not_an_input(self):
        self.assertEqual(vd.touches_parity(
            ['campaigns/rime-of-the-frostmaiden/portraits/x.png', 'tools/playtest/matrix.py',
             'docs/roadmap.md'], self.inputs), [])


if __name__ == '__main__':
    unittest.main()
