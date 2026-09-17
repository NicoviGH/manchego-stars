#!/usr/bin/env python3
"""Tests for check_decision_records_wellformed + the decisions index (#384).

`docs/decisions/` is the source of truth now, so a malformed ADR is a decision that quietly
stops being indexed -- the same class of failure as a check that is defined but never
registered. These pin that the guard goes RED on each way that happens, because a gate only
ever run against a passing tree has never demonstrated it can fail.

The real corpus is the passing oracle; every failing case is a synthetic directory.

Run: python3 tools/test_check_decision_records.py
"""
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import check                                                          # noqa: E402
import gen_decisions_index as gen                                     # noqa: E402

GOOD = ('---\n'
        'id: %d\n'
        'title: "A decision"\n'
        'date: "2026-09-17"\n'
        'section: "Operational Gotchas (durable)"\n'
        'issues: [1]\n'
        '---\n\n# A decision\n\nBody.\n')


class TheRealCorpusIsClean(unittest.TestCase):

    def test_guard_passes_on_the_tree(self):
        fail = []
        check.check_decision_records_wellformed(fail)
        self.assertEqual([], fail)

    def test_index_is_fresh(self):
        want = gen.generate()[0]
        with open(os.path.join(gen.REPO, 'docs/decisions.md'), encoding='utf-8') as fh:
            have = fh.read()
        self.assertEqual(want, have,
                         'docs/decisions.md is stale -- python3 tools/gen_decisions_index.py')

    def test_every_decision_has_a_known_section(self):
        for rec in gen.adrs():
            self.assertIn(rec['section'], gen.SECTION_ORDER, rec['path'])

    def test_ids_are_dense_and_unique(self):
        ids = sorted(r['id'] for r in gen.adrs())
        self.assertEqual(len(ids), len(set(ids)), 'duplicate decision ids')
        self.assertEqual(ids, list(range(1, len(ids) + 1)),
                         'decision ids should run 1..N with no gaps')


class ItCatchesWhatItIsFor(unittest.TestCase):

    def _run(self, files):
        with tempfile.TemporaryDirectory() as tmp:
            d = os.path.join(tmp, 'docs', 'decisions')
            os.makedirs(d)
            for name, body in files.items():
                with open(os.path.join(d, name), 'w', encoding='utf-8') as fh:
                    fh.write(body)
            real_repo, real_dir = check.REPO, gen.ADR_DIR
            check.REPO, gen.ADR_DIR = tmp, d
            try:
                fail = []
                check.check_decision_records_wellformed(fail)
                return fail
            finally:
                check.REPO, gen.ADR_DIR = real_repo, real_dir

    def test_duplicate_ids_fail(self):
        fail = self._run({'0001-a.md': GOOD % 1, '0001-b.md': GOOD % 1})
        self.assertTrue(any('is used by both' in f for f in fail), fail)

    def test_id_not_matching_filename_fails(self):
        fail = self._run({'0007-a.md': GOOD % 3})
        self.assertTrue(any('filename does not match' in f for f in fail), fail)

    def test_missing_front_matter_fails(self):
        fail = self._run({'0001-a.md': '# no front matter\n\nbody\n'})
        self.assertTrue(any('could not be parsed' in f for f in fail), fail)

    def test_missing_title_fails(self):
        body = ('---\nid: 1\nsection: "Operational Gotchas (durable)"\n---\n\nBody.\n')
        fail = self._run({'0001-a.md': body})
        self.assertTrue(any('no title' in f for f in fail), fail)

    def test_missing_section_fails(self):
        body = '---\nid: 1\ntitle: "T"\n---\n\nBody.\n'
        fail = self._run({'0001-a.md': body})
        self.assertTrue(any('no section' in f for f in fail), fail)

    def test_a_padded_id_is_rejected_because_yaml_mangles_it(self):
        """0009 parses as the string "0009"; 0001 parses as octal 1. Both are traps, so
        ids are written unpadded and the filename carries the padding."""
        body = GOOD.replace('id: %d', 'id: 0009')
        fail = self._run({'0009-a.md': body})
        self.assertTrue(any('non-integer id' in f for f in fail), fail)


class CitationsResolve(unittest.TestCase):
    """A `decisions.md -> "Title"` pointer must name something real (#386).

    This gate exists because a review caught a pointer to "Always use the decomp" -- a title
    that has never existed in this repo -- and because two more pointers had gone stale across
    the #384 split with nothing to notice. Before #384 there was no way to validate one: the
    target was a sentence inside a 728 KB file.
    """

    def test_the_tree_has_no_broken_citations(self):
        fail = []
        check.check_decision_citations_resolve(fail)
        self.assertEqual([], fail)

    def test_the_corpus_covers_body_text_and_section_names(self):
        """9 of the repo's 29 pointers name body text rather than a title -- "Playtest runs
        are the most expensive thing in this repo" is prose inside 0232. A validator that
        knew only titles would call all of them broken, which is worse than no validator."""
        corpus = gen.citation_corpus()
        for phrase in ('playtest runs are the most expensive thing in this repo',
                       'what terrain cannot do is stop a ranged weapon',
                       'working conventions'):          # a SECTION, which lives in no record
            self.assertIn(phrase, corpus)

    def test_it_goes_red_on_a_pointer_that_names_nothing(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            doc = os.path.join(tmp, 'FAKE.md')
            with open(doc, 'w', encoding='utf-8') as fh:
                fh.write('see `decisions.md` -> "A decision that was never written down"\n')
            real_docs = check._docs
            real_src = check._handwritten_sources
            check._docs = lambda: [doc]
            check._handwritten_sources = lambda: []
            try:
                fail = []
                check.check_decision_citations_resolve(fail)
            finally:
                check._docs, check._handwritten_sources = real_docs, real_src
        self.assertEqual(1, len(fail), fail)
        self.assertIn('names no title, heading or phrase', fail[0])


if __name__ == '__main__':
    unittest.main()
