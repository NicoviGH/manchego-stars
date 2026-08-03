#!/usr/bin/env python3
"""Regression coverage for state-driven playtest scenario wiring."""
import os
import unittest


REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HARNESS = os.path.join(REPO, 'tools/playtest/harness.lua')


class TestPlaytestHarness(unittest.TestCase):
    def test_moose_recorder_wires_fast_setup_to_guaranteed_cleanup(self):
        with open(HARNESS, encoding='utf-8') as source:
            harness = source.read()

        start = harness.index('scenarios.recordch04moose = function()')
        end = harness.index('\n-- ch04moose:', start)
        recorder = harness[start:end]

        fast = recorder.index('pokeFastConfig()')
        boot = recorder.index('bootToMap()')
        march = recorder.index('marchPartyToward(')
        self.assertLess(fast, boot)
        self.assertLess(boot, march)
        self.assertIn('return false, "never reached the ch04 map"', recorder)
        self.assertIn('return false, "party never triggered the moose sighting"', recorder)
        self.assertIn('afterPre = pokeNormalConfig', recorder)


if __name__ == '__main__':
    unittest.main()
