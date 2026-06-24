#!/usr/bin/env python3
"""Tests for the lane-ownership guard in tools/check.py (#55).

Pins the pure ownership logic: which lane owns a file, and which staged files violate the
seam from a given lane. The git plumbing (reading manchego.lane / staged files) is a thin
wrapper exercised by the pre-commit hook itself. Run: python3 tools/test_check_lanes.py
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import check


class FileLane(unittest.TestCase):
    def test_content_exclusive_files_and_dirs(self):
        self.assertEqual(check._file_lane('tools/build_campaign.py'), 'content')
        self.assertEqual(check._file_lane('campaigns/rime/chapters/ch02.yaml'), 'content')
        self.assertEqual(check._file_lane('tools/portrait_tool.py'), 'content')

    def test_pipeline_exclusive_files_and_dirs(self):
        self.assertEqual(check._file_lane('tools/difficulty.py'), 'pipeline')
        self.assertEqual(check._file_lane('tools/playtest/run.sh'), 'pipeline')
        self.assertEqual(check._file_lane('.github/workflows/checks.yml'), 'pipeline')

    def test_shared_files_are_unowned(self):
        for p in ('tools/inject/decomp.py', 'tools/inject/engine_hooks.py',
                  'docs/decisions.md', 'CLAUDE.md', 'Makefile', 'HANDOFF.md'):
            self.assertIsNone(check._file_lane(p), p)


class LaneViolations(unittest.TestCase):
    def test_pipeline_editing_content_file_is_the_violation(self):
        # The exact mistake this guard exists to stop: pipeline touching build_campaign.py.
        v = check._lane_violations('pipeline',
                                   ['tools/build_campaign.py', 'tools/difficulty.py'])
        self.assertEqual(v, [('tools/build_campaign.py', 'content')])

    def test_content_editing_pipeline_file_is_a_violation(self):
        v = check._lane_violations('content', ['tools/difficulty.py'])
        self.assertEqual(v, [('tools/difficulty.py', 'pipeline')])

    def test_shared_files_never_violate(self):
        self.assertEqual(check._lane_violations('pipeline',
                         ['tools/inject/decomp.py', 'docs/decisions.md']), [])

    def test_no_lane_is_the_unrestricted_integration_tree(self):
        # The primary checkout (no lane) is integration/solo work -- nothing is blocked there,
        # so a single window on `main` can edit any file. Enforcement lives in lane worktrees.
        self.assertEqual(check._lane_violations(None, ['tools/build_campaign.py',
                                                       'tools/difficulty.py', 'campaigns/x.yaml']),
                         [])


if __name__ == '__main__':
    unittest.main()
