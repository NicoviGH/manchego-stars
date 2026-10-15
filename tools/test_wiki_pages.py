#!/usr/bin/env python3
"""Our chapter pages are laid out as the Fire Emblem Wiki lays out its own (#493).

`wiki.pages.chapter` writes wikitext that calls the wiki's templates. This holds its skeleton --
the section headings and the page-level templates, in order -- to the wiki's own chapter source:
every chapter page we generate must be an in-order subsequence of the exemplars' skeleton (a
section we have no data for is left out, never moved or invented).
"""
import os
import re
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import gen_wiki                                           # noqa: E402
from wiki import mw                                       # noqa: E402

PAGES = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'wiki', 'vendor', 'pages')
INLINE = {'h', 'hl', 'FE8', 'Item', 'DEFAULTSORT'}       # inline templates, not layout


def skeleton(text):
    seq = []
    for node in mw.parse(text):
        if isinstance(node, mw.Tpl):
            name = ''.join(x for x in node.parts[0] if isinstance(x, str)).strip()
            name = name.split(':', 1)[0]
            if name not in INLINE:
                seq.append(name[:1].upper() + name[1:])
        else:
            seq += [h.strip() for h in re.findall(r'^(={2,4}[^=\n]+={2,4})\s*$', node, re.M)]
    # A table's row count is data, not layout: consecutive repeats (one cell per unit) are one.
    return [x for i, x in enumerate(seq) if i == 0 or x != seq[i - 1]]


def merged(*seqs):
    """One order that contains each exemplar's skeleton in order (their union)."""
    out = []
    for seq in seqs:
        pos = 0
        for item in seq:
            if item in out[pos:]:
                pos = out.index(item, pos) + 1
            else:
                out.insert(pos, item)
                pos += 1
    return out


def is_subsequence(seq, of):
    it = iter(of)
    return all(item in it for item in seq)


class ChapterLayout(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        exemplars = []
        for stem in ('The_Bandits_of_Borgo', 'The_Protected', 'Escape!'):
            with open(os.path.join(PAGES, stem + '.wiki'), encoding='utf-8') as f:
                exemplars.append(skeleton(f.read()))
        cls.order = merged(*exemplars)
        chs = gen_wiki.chapters()
        units = gen_wiki.units_index()
        first = next(c for c in chs if not c.get('is_prologue'))
        first['_founding'] = sorted(k for k, u in units.items() if u['_kind'] == 'pcs')
        cls.pages = {}
        for i, c in enumerate(chs):
            if c.get('status') == 'planned':
                continue
            cls.pages[c['_slug']] = gen_wiki.chapter_wikitext(
                c, chs[i - 1] if i else None, chs[i + 1] if i + 1 < len(chs) else None,
                units, chs, gen_wiki.WikiFiles())

    def test_every_hosted_chapter_follows_the_wikis_section_order(self):
        for slug, text in sorted(self.pages.items()):
            with self.subTest(slug):
                ours = skeleton(text)
                self.assertTrue(is_subsequence(ours, self.order),
                                '%s: %s\nis not in the wiki\'s order %s' % (slug, ours, self.order))

    def test_ch02_carries_vanilla_ch2s_shop_and_its_green_allies(self):
        ours = skeleton(self.pages['ch02'])
        self.assertIn('===Shop data===', ours)
        self.assertIn('===NPC data===', ours)

    def test_ch03_lists_trex_as_an_npc_until_recruited(self):
        text = self.pages['ch03']
        npc = text[text.index('===NPC data==='):]
        self.assertIn('|name=Trex', npc)
        self.assertIn('{{h|+1|Upon Trex being recruited}}', text)

    def test_a_recruit_joins_the_way_the_build_wires_it(self):
        # Read from what the build wires, never `recruit.via` (Trex says `story`, and the wiki
        # printed "Automatically" for a unit you have to talk to).
        self.assertIn('|recruitment method=NPC, talk to with any party member',
                      self.pages['ch03'])
        self.assertIn('|recruitment method=Enemy, talk to with [[Basil]]', self.pages['ch05'])


class ScriptLayout(unittest.TestCase):
    """Script subpages are laid out as `The Bandits of Borgo/Script` and `Ancient Horrors/Script`
    are: their ==sections== and page templates, in order. A subheading is the scene's own, and a
    {{Quote}} is a line, so neither is layout."""

    @classmethod
    def setUpClass(cls):
        exemplars = []
        for stem in ('The_Bandits_of_Borgo__Script', 'Ancient_Horrors__Script'):
            with open(os.path.join(PAGES, stem + '.wiki'), encoding='utf-8') as f:
                exemplars.append(cls.sections(f.read()))
        cls.order = merged(*exemplars)
        chs = gen_wiki.chapters()
        units = gen_wiki.units_index()
        cls.pages = {c['_slug']: gen_wiki.script_wikitext(
            c, chs[i - 1] if i else None, chs[i + 1] if i + 1 < len(chs) else None, units)
            for i, c in enumerate(chs)}

    @staticmethod
    def sections(text):
        return [x for x in skeleton(text) if x in ('ChapterNav', 'NavScriptFE8')
                or (x.startswith('==') and not x.startswith('==='))]

    def test_every_script_follows_the_wikis_section_order(self):
        for slug, text in sorted(self.pages.items()):
            if not text:
                continue
            with self.subTest(slug):
                ours = self.sections(text)
                self.assertTrue(is_subsequence(ours, self.order),
                                '%s: %s\nis not in the wiki\'s order %s' % (slug, ours, self.order))

    def test_battle_quotes_and_talks_are_headed_as_the_wiki_heads_them(self):
        text = self.pages['ch06']
        for heading in ('===Fighting Nerra===', '===Defeating Nerra===', '===Anyone and Grynsk==='):
            self.assertIn(heading, text)
        self.assertIn("'''Nerra:''' Ngh... Not today.", text)
        self.assertIn('===Anyone and Trex===', self.pages['ch03'])

    def test_a_talk_recruit_ends_on_the_recruit(self):
        # From the wiring (`talk_joins`): Basil joins ch05 too, but in its opening, not this talk.
        talk = self.pages['ch05'].split('==Talk conversations==')[1].split('==Battle quotes==')[0]
        self.assertIn('===Basil and Sahnar===', talk)
        self.assertIn('(Sahnar is recruited)', talk)
        self.assertNotIn('(Basil is recruited)', talk)

    def test_a_scene_with_a_missing_unit_is_a_variant_not_a_second_scene(self):
        text = self.pages['ch05']
        self.assertIn('====With Lupin====', text)
        self.assertIn('====Without Lupin====', text)
        self.assertNotIn('(no Lupin)', text)

    def test_a_stage_direction_is_a_real_exit_not_podium_juggling(self):
        for slug, text in self.pages.items():
            lines = text.splitlines()
            for i, line in enumerate(lines):
                m = re.match(r'\((.+) leaves\)', line)
                if not m:
                    continue
                scene = '\n'.join(lines[i + 1:]).split('\n\n')[0]
                self.assertNotIn("'''%s:'''" % m.group(1), scene, '%s: %s' % (slug, line))

    def test_script_nav_points_at_the_neighbouring_scripts(self):
        self.assertIn('|prechapter=The Elven Tomb/Script{{!}}The Elven Tomb', self.pages['ch06'])


if __name__ == '__main__':
    unittest.main()
