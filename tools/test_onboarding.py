#!/usr/bin/env python3
"""Tests for tools/gen_onboarding_index.py -- the FE8 tutorial-parity guardrail.

The catalog (campaigns/.../onboarding-catalog.yaml) is the stable record of what
vanilla FE8 teaches and through which channel; each chapter YAML's `introduces:`
field is the living ledger of which concept first appears in OUR chapter order and
how we cover it. These tests pin the integrity invariants (no orphan/double-debut
concepts) and the generated-doc freshness, so a drift can't land silently.
Run:  python3 tools/test_onboarding.py
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import gen_onboarding_index as onb


class CatalogIntegrity(unittest.TestCase):
    def test_catalog_concepts_have_required_fields(self):
        for c in onb.load_catalog():
            for k in ('id', 'concept', 'vanilla_channel', 'vanilla_text'):
                self.assertIn(k, c, '%s missing %r' % (c.get('id', '?'), k))

    def test_every_introduced_concept_is_in_the_catalog(self):
        ids = {c['id'] for c in onb.load_catalog()}
        for cid, chapters in onb.load_chapter_introductions().items():
            self.assertIn(cid, ids,
                          'chapter(s) %s introduce unknown concept %r (not in catalog)'
                          % (chapters, cid))

    def test_no_concept_debuts_in_two_chapters(self):
        dupes = {cid: chs for cid, chs in onb.load_chapter_introductions().items()
                 if len(chs) > 1}
        self.assertEqual(dupes, {}, 'each concept debuts once; double-introduced: %s' % dupes)

    def test_integrity_errors_is_empty(self):
        self.assertEqual(onb.integrity_errors(), [])

    def test_orphan_concept_is_flagged(self):
        errs = onb.integrity_errors(catalog=[{'id': 'a'}], intros={'b': ['Ch 1']})
        self.assertTrue(any('not in the catalog' in e for e in errs), errs)

    def test_double_debut_is_flagged(self):
        errs = onb.integrity_errors(catalog=[{'id': 'a'}], intros={'a': ['Ch 1', 'Ch 2']})
        self.assertTrue(any('multiple chapters' in e for e in errs), errs)


class GeneratedDoc(unittest.TestCase):
    def test_doc_is_fresh(self):
        want = onb.generate()[0]
        have = None
        if os.path.isfile(onb.OUT):
            with open(onb.OUT, encoding='utf-8') as f:
                have = f.read()
        self.assertEqual(have, want,
                         'docs/ONBOARDING.md is stale -- regenerate: '
                         'python3 tools/gen_onboarding_index.py')

    def test_uncovered_concepts_are_surfaced_as_pending(self):
        covered = set(onb.load_chapter_introductions())
        uncovered = [c['id'] for c in onb.load_catalog() if c['id'] not in covered]
        md = onb.generate()[0]
        if uncovered:
            self.assertIn('Pending', md,
                          'concepts with no chapter coverage must show in a Pending section')


if __name__ == '__main__':
    unittest.main()
