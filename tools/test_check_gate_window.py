#!/usr/bin/env python3
"""Tests for the gate's chapter window (check.py, #302).

The merge gate is the spine plus the two most recently hosted chapters. Left alone it
accumulates: ch02 and ch03 aged out of it by hand, ch04 did not when ch05 landed, and at
eighteen chapters an accumulating gate is ~130 scenarios and ~18 builds -- a gate nobody
runs, which protects nothing. The window is derived from the host registry, so hosting
ch06 is what moves it.

Run: python3 tools/test_check_gate_window.py
"""
import collections
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import check  # noqa: E402

Hosted = collections.namedtuple('Hosted', 'name number host_index event_group')

HOSTED = [Hosted('prologue', 0, 1, 'Ch1Events'),
          Hosted('ch01', 1, 2, 'Ch2Events'),
          Hosted('ch02', 2, 3, 'Ch3Events'),
          Hosted('ch03', 3, 4, 'Ch4Events'),
          Hosted('ch04', 4, 5, 'Ch5EventData'),
          Hosted('ch05', 5, 6, 'Ch6Events')]


class GateWindow(unittest.TestCase):

    def test_the_spine_and_the_last_two_chapters_pass(self):
        boots = {'win': 1, 'ch01win': 1, 'recordunitlist': None,
                 'ch04moose': 5, 'ch05arena': 6}
        self.assertEqual(check._gate_window_violations(boots, HOSTED), [])

    def test_a_chapter_that_has_fallen_out_of_the_window_is_reported(self):
        boots = {'win': 1, 'ch03talk': 4, 'ch04moose': 5, 'ch05arena': 6}
        msgs = check._gate_window_violations(boots, HOSTED)
        self.assertEqual(len(msgs), 1, msgs)
        self.assertIn('ch03talk', msgs[0])
        self.assertIn('ch03', msgs[0])

    def test_the_message_says_where_the_scenario_should_go(self):
        """A guard that only says no costs the reader a lookup: the depth is not deleted,
        it moves to that chapter's own suite."""
        msgs = check._gate_window_violations({'ch03talk': 4}, HOSTED)
        self.assertIn('SUITE=ch03', msgs[0])

    def test_hosting_a_new_chapter_is_what_moves_the_window(self):
        """The window is derived, so ch06 landing is what ages ch04 out -- nobody edits a
        list of allowed chapters."""
        boots = {'ch04moose': 5, 'ch05arena': 6}
        self.assertEqual(check._gate_window_violations(boots, HOSTED), [])

        after = HOSTED + [Hosted('ch06', 6, 7, 'Ch7EventData')]
        msgs = check._gate_window_violations(dict(boots, ch06smoke=7), after)

        self.assertEqual(len(msgs), 1, msgs)
        self.assertIn('ch04moose', msgs[0])

    def test_a_scenario_with_no_boot_chapter_is_always_allowed(self):
        """The sandbox and the controller contract belong to no chapter and never age."""
        self.assertEqual(check._gate_window_violations({'recordunitlist': None}, HOSTED), [])

    def test_the_real_gate_is_inside_its_window(self):
        fail = []
        check.check_gate_chapter_window(fail)
        self.assertEqual(fail, [])


if __name__ == '__main__':
    unittest.main()
