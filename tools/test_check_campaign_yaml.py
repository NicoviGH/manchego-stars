#!/usr/bin/env python3
"""Tests for the campaign.yaml declaration guards in tools/check.py (#30).

The thing being pinned: a chapter's number and name live in its own
`chapters/ch*.yaml`, `tools/campaign_chapters.py` is the one reader, and
`docs/CHAPTERS.md` is generated from that. `campaign.yaml` used to carry a second,
hand-kept copy -- and because nothing read it, nothing could notice it going wrong.
It did, in all three ways at once: the prologue was missing, `count: 7` described a
nine-chapter campaign, and from ch04 on every entry named a chapter one number too
low (the Elven Tomb filed as ch04 when it is ch05, and so on down to the Eastway
Ambush at ch07 when it is ch08).

A restatement nothing reads cannot break a build. It misleads the next reader
instead, which is the failure this guard exists to prevent.

Run: python3 tools/test_check_campaign_yaml.py
"""
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import check


class NoChapterListInCampaignYaml(unittest.TestCase):

    def _run_on(self, body):
        tmp = tempfile.NamedTemporaryFile('w', suffix='.yaml', delete=False)
        tmp.write(body)
        tmp.close()
        original = check._campaign_yamls
        try:
            check._campaign_yamls = lambda: [tmp.name]
            fail = []
            check.check_campaign_declares_no_chapter_list(fail)
            return fail
        finally:
            check._campaign_yamls = original
            os.unlink(tmp.name)

    def test_a_restated_chapter_list_is_rejected(self):
        fail = self._run_on('title: "X"\n'
                            'chapters:\n'
                            '  count: 7\n'
                            '  list:\n'
                            '    - ch01-the-iron-trail\n')
        self.assertEqual(1, len(fail), fail)
        self.assertIn('chapters', fail[0])

    def test_it_names_the_reader_that_owns_the_fact(self):
        """A guard that only says no leaves the next person guessing where to look."""
        fail = self._run_on('chapters:\n  count: 7\n')
        self.assertIn('campaign_chapters', fail[0])

    def test_a_campaign_yaml_without_one_passes(self):
        self.assertEqual([], self._run_on('title: "X"\nstarting_gold: 500\n'))

    def test_the_live_campaign_yaml_passes(self):
        fail = []
        check.check_campaign_declares_no_chapter_list(fail)
        self.assertEqual([], fail)

    def test_the_glob_actually_finds_the_live_file(self):
        """The guard passing because it scanned NOTHING is the failure mode to rule out."""
        found = [os.path.relpath(p, check.REPO) for p in check._campaign_yamls()]
        self.assertIn('campaigns/rime-of-the-frostmaiden/campaign.yaml', found)


if __name__ == '__main__':
    unittest.main(verbosity=2)
