#!/usr/bin/env python3
"""Tests for the comment-drift guards in tools/check.py (2026-07-02 ADR "Comments
are testimony, code is evidence").

The incident being pinned: a stale build_campaign.py header ("zeroed personal
growths ... pure class rate") outlived the donor-parity code that replaced it and
got copied into an ADR as fact. Two gaps let it survive: check_no_dead_concepts
scanned docs only (never code comments), and the registered growth patterns were
too narrow to match the comment's actual phrasing. These tests hold both fixes.

Run: python3 tools/test_check_comment_drift.py
"""
import os
import re
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import check


DEAD_PAT = re.compile('|'.join(check.DEAD_CONCEPTS), re.I)

# The exact stale comment text from the incident (build_campaign.py pre-fix).
INCIDENT_LINE = ('# and zeroed personal growths (so the unit grows at its pure '
                 'class rate). When')


class DeadConceptPatterns(unittest.TestCase):
    def test_the_incident_comment_is_now_caught(self):
        # both retired phrasings in the one line; either alone must fire
        self.assertIsNotNone(DEAD_PAT.search(INCIDENT_LINE))
        self.assertIsNotNone(DEAD_PAT.search('zeroed personal growths'))
        self.assertIsNotNone(DEAD_PAT.search('grows at its pure class rate'))

    def test_the_original_narrow_phrasings_still_fire(self):
        self.assertIsNotNone(DEAD_PAT.search('zeroed growths'))
        self.assertIsNotNone(DEAD_PAT.search('pure-class growth'))

    def test_live_donor_vocabulary_is_not_flagged(self):
        for ok in ('growths copied verbatim from the growth donor',
                   'the donor personal bases',
                   'class growths from data_classes.c',):
            self.assertIsNone(DEAD_PAT.search(ok), ok)


class HandwrittenSourceScan(unittest.TestCase):
    """check_no_dead_concepts must scan code comments, not just docs."""

    def _with_planted_file(self, contents, suffix='.py'):
        tmp = tempfile.NamedTemporaryFile('w', suffix=suffix, delete=False,
                                          dir=os.path.dirname(os.path.abspath(__file__)))
        tmp.write(contents)
        tmp.close()
        return tmp.name

    def test_dead_concept_in_a_code_comment_is_flagged(self):
        path = self._with_planted_file('# legacy: zeroed personal growths here\n')
        try:
            orig_docs, orig_src = check._docs, check._handwritten_sources
            check._docs = lambda: []
            check._handwritten_sources = lambda: [path]
            fail = []
            check.check_no_dead_concepts(fail)
            self.assertEqual(len(fail), 1)
            self.assertIn('zeroed personal growths', fail[0])
        finally:
            check._docs, check._handwritten_sources = orig_docs, orig_src
            os.unlink(path)

    def test_the_repo_scan_globs_cover_the_incident_file(self):
        sources = [os.path.relpath(p, check.REPO) for p in check._handwritten_sources()]
        self.assertIn('tools/build_campaign.py', sources)
        self.assertIn('tools/playtest/harness.lua', sources)
        self.assertNotIn('tools/check.py', sources)   # hosts the registry; exempt

    def test_the_live_repo_is_clean(self):
        fail = []
        check.check_no_dead_concepts(fail)
        self.assertEqual(fail, [])


class DanglingRefs(unittest.TestCase):
    def _run_on(self, contents):
        tmp = tempfile.NamedTemporaryFile('w', suffix='.py', delete=False,
                                          dir=os.path.dirname(os.path.abspath(__file__)))
        tmp.write(contents)
        tmp.close()
        try:
            orig_docs, orig_src = check._docs, check._handwritten_sources
            check._docs = lambda: []
            check._handwritten_sources = lambda: [tmp.name]
            fail = []
            check.check_tool_refs_exist(fail)
            return fail
        finally:
            check._docs, check._handwritten_sources = orig_docs, orig_src
            os.unlink(tmp.name)

    def test_a_dangling_tool_ref_in_a_comment_is_flagged(self):
        fail = self._run_on('# see tools/zzz-does-not-exist.py for the old flow\n')
        self.assertEqual(len(fail), 1)
        self.assertIn('tools/zzz-does-not-exist.py', fail[0])

    def test_a_dangling_doc_ref_is_flagged(self):
        fail = self._run_on('# rationale: docs/zzz-retired-plan.md\n')
        self.assertEqual(len(fail), 1)
        self.assertIn('docs/zzz-retired-plan.md', fail[0])

    def test_a_real_tool_and_doc_pass(self):
        self.assertEqual(self._run_on(
            '# see tools/build_campaign.py + docs/decisions.md\n'), [])

    def test_decomp_internal_paths_do_not_false_positive(self):
        # "texttools/textdecoder.py" must not read as tools/textdecoder.py
        # (the FP that surfaced the moment the scan was extended to code)
        self.assertEqual(self._run_on(
            '# decodes via scripts/texttools/textdecoder.py in the decomp\n'), [])

    def test_gitignored_generated_targets_are_declared_artifacts(self):
        # symbols.lua is generated by gen_symbols.py and gitignored -- a reference
        # to it is a build-artifact pointer, not rot
        self.assertEqual(self._run_on('# emits tools/playtest/symbols.lua\n'), [])

    def test_the_live_repo_is_clean(self):
        fail = []
        check.check_tool_refs_exist(fail)
        self.assertEqual(fail, [])


if __name__ == '__main__':
    unittest.main()
