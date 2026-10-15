#!/usr/bin/env python3
"""The wiki engine renders the Fire Emblem Wiki's own exemplar pages the way the wiki does (#493).

Every page we publish is wikitext calling the wiki's templates, so the templates are the layout,
and this is the proof the engine draws them faithfully: each vendored exemplar (one real FE8 page
per page type, `tools/wiki/vendor.py`) is expanded and rendered here and held against the wiki's
own render of the same page. A drop below a page's floor names the first differences.

The floors only rise. Where a page is short of 1.0 the comment says what the gap is, so a gap is
a known, named quirk rather than a number someone tuned until it passed.
"""
import gzip
import json
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from wiki import golden, mw, render                     # noqa: E402

VENDOR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'wiki', 'vendor')

# Exemplar -> the share of the wiki's page our render reproduces (golden.ratio), floored.
FLOORS = {
    'A_New_Journey': 1.0,
    'Availability_chart__The_Sacred_Stones': 1.0,
    'Bazba': 1.0,
    # Two empty <p class="mw-empty-elt"> MediaWiki leaves between the TCG card's icons.
    'Colm': 0.9998,
    'Dara': 1.0,
    'Escape!': 1.0,
    # The manual citations: MediaWiki opens a definition list at a mid-line `;` in "(PDF; pg.".
    'Fire_Emblem--_The_Sacred_Stones': 0.9992,
    'Imperial_Three': 1.0,
    'List_of_chapters_in_Fire_Emblem--_The_Sacred_Stones': 1.0,
    'List_of_characters_in_Fire_Emblem--_The_Sacred_Stones': 1.0,
    'Sacred_Stone_(object)': 1.0,
    'The_Bandits_of_Borgo': 1.0,
    'The_Bandits_of_Borgo__Script': 1.0,
    'The_Protected': 1.0,
}


def title_of(stem):
    return stem.replace('__', '/').replace('--', ':').replace('_', ' ')


def ours(stem):
    with open(os.path.join(VENDOR, 'pages', stem + '.wiki'), encoding='utf-8') as f:
        text = f.read()
    wiki = mw.Wiki(pagename=title_of(stem))
    return golden.tokens(render.render(wiki.expand_text(text)))


def theirs(stem):
    with gzip.open(os.path.join(VENDOR, 'golden', stem + '.json.gz'), 'rt',
                   encoding='utf-8') as f:
        return json.load(f)


class Exemplars(unittest.TestCase):
    def test_every_exemplar_has_a_floor(self):
        pages = sorted(f[:-5] for f in os.listdir(os.path.join(VENDOR, 'pages')))
        self.assertEqual(pages, sorted(FLOORS), 'vendor.py and FLOORS disagree on the exemplars')

    def test_each_exemplar_renders_like_the_wiki(self):
        for stem, floor in sorted(FLOORS.items()):
            with self.subTest(stem):
                a, b = ours(stem), theirs(stem)
                got = golden.ratio(a, b)
                self.assertGreaterEqual(got, floor, '%s: %.4f < %.4f\n%s' % (
                    stem, got, floor, '\n'.join(golden.diff(a, b, limit=8))))


class Engine(unittest.TestCase):
    """The MediaWiki rules the exemplars lean on, pinned one at a time."""

    def r(self, text):
        return render.render(mw.Wiki().expand_text(text))

    def test_a_switch_value_is_css_unescaped_in_a_style(self):
        self.assertIn('style="color: #a83028"',
                      self.r('{| style="color: {{#switch:x|x=\\#a83028}}"\n| a\n|}'))

    def test_a_cell_holding_only_a_hash_is_not_a_list(self):
        self.assertNotIn('<ol>', self.r('{|\n! #\n|}'))

    def test_a_link_trail_joins_the_link(self):
        self.assertIn('>chests</a>', self.r('[[chest]]s'))

    def test_an_invalid_title_stays_literal(self):
        self.assertIn('[[{{{x}}}]]', self.r('[[{{{x}}}]]'))

    def test_consecutive_indents_share_one_list(self):
        self.assertEqual(self.r(':a\n:b').count('<dl>'), 1)

    def test_a_named_ref_reuses_its_number_and_lists_each_use(self):
        out = self.r('a<ref name="x">src</ref> b<ref name="x" /> c<ref>two</ref>\n<references/>')
        self.assertEqual(out.count('>1<span class="cite-bracket">'), 2)
        self.assertIn('1.0</a>', out)
        self.assertIn('1.1</a>', out)
        self.assertIn('>2<span class="cite-bracket">', out)

    def test_a_second_references_prints_only_what_is_new(self):
        out = self.r('a<ref>one</ref>\n<references/>\n<references/>')
        self.assertEqual(out.count('mw-references-wrap'), 1)

    def test_a_stray_end_tag_is_dropped(self):
        self.assertNotIn('</span>', self.r('{|\n| x</span>\n|}'))

    def test_an_invoke_falls_back_to_the_callers_args(self):
        # Template:Lang passes nothing of its own: Module:Arguments reads the caller's.
        self.assertIn('lang="ga"', self.r('{{lang|ga|Mac Dara}}'))

    def test_an_unknown_template_raises_instead_of_rendering_wrong(self):
        with self.assertRaises(KeyError):
            self.r('{{No such template anywhere}}')


if __name__ == '__main__':
    unittest.main()
