#!/usr/bin/env python3
"""The wiki is generated from the chapter YAML and the decomp; these pin that it builds from
the real repo, gives every chapter a page, and that its open-decisions list is exactly the
chapters' `open_questions` (the list a reader settles from)."""
import os
import re
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import gen_wiki                                        # noqa: E402


class TestGenWiki(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        out, cls.n, cls.k = gen_wiki.build()
        with open(out, encoding='utf-8') as f:
            cls.page = f.read()
        cls.chapters = gen_wiki.chapters()

    def test_every_chapter_has_a_page(self):
        for c in self.chapters:
            self.assertIn('<section class="page" id="%s"' % c['_slug'], self.page)
        self.assertEqual(self.n, len(self.chapters))

    def test_open_decisions_are_the_yaml_questions(self):
        want = sum(len(c.get('open_questions') or []) for c in self.chapters)
        self.assertEqual(self.k, want)
        block = re.search(r'<section class="page" id="decisions".*?</section>', self.page, re.S)
        self.assertEqual(block.group(0).count('<tr>') - 1, want)

    def test_twin_payload_is_read_from_the_decomp(self):
        # vanilla Ch5's five village/clear gifts all reach ch05 (ADR 0049's 1:1 economy)
        ch05 = re.search(r'<section class="page" id="ch05".*?</section>', self.page, re.S).group(0)
        self.assertIn('ITEM_GUIDINGRING', ch05)
        self.assertNotIn('not found in ours</span>', ch05)

    def test_item_names_are_the_games_own(self):
        self.assertEqual(gen_wiki.item_name('ITEM_BOOSTER_POW'), 'Energy Ring')
        self.assertEqual(gen_wiki.our_item('iron-blade')[1], 'ITEM_BLADE_IRON')


if __name__ == '__main__':
    unittest.main()
