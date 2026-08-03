#!/usr/bin/env python3
"""Regression coverage for state-driven playtest scenario wiring."""
import os
import unittest


REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HARNESS = os.path.join(REPO, 'tools/playtest/harness.lua')


class TestPlaytestHarness(unittest.TestCase):
    def test_moose_recorder_fast_forwards_only_the_unfilmed_march(self):
        with open(HARNESS, encoding='utf-8') as source:
            harness = source.read()

        start = harness.index('scenarios.recordch04moose = function()')
        end = harness.index('\n-- ch04moose:', start)
        recorder = harness[start:end]

        fast = recorder.index('pokeFastConfig()')
        boot = recorder.index('bootToMap()')
        march = recorder.index('marchPartyToward(')
        normal = recorder.index('pokeNormalConfig()')

        self.assertLess(fast, boot)
        self.assertLess(boot, march)
        self.assertLess(march, normal)


if __name__ == '__main__':
    unittest.main()
