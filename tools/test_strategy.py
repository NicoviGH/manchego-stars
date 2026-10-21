#!/usr/bin/env python3
"""Tests for tools/strategy.py -- the Strategy sections as claims (#510 step 6).

    python3 tools/test_strategy.py
"""
import os
import sys
import unittest

import yaml

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import difficulty as dif
import strategy

CAMPAIGN = 'rime-of-the-frostmaiden'
HOSTED = ['ch00', 'ch01', 'ch02', 'ch03', 'ch04', 'ch05', 'ch06', 'ch07']


def chapter(ch):
    with open(dif.chapter_path(CAMPAIGN, ch), encoding='utf-8') as f:
        return yaml.safe_load(f)


class EveryClaimCitesItsSection(unittest.TestCase):
    def test_every_twin_claim_resolves(self):
        for ref in strategy._twin_file():
            with self.subTest(ref=ref):
                self.assertTrue(strategy.twin_claims(ref))

    def test_every_chapter_claim_resolves(self):
        for ch in HOSTED:
            with self.subTest(ch=ch):
                self.assertTrue(strategy.our_claims(chapter(ch)))

    def test_every_hosted_twin_is_curated(self):
        for ch in HOSTED:
            with self.subTest(ch=ch):
                self.assertIn(chapter(ch)['parity_reference'], strategy._twin_file())

    def test_a_terrain_claim_names_a_tile_its_map_has(self):
        for ch in HOSTED:
            chap = chapter(ch)
            for key, claims, tiles in (
                    ('ours', strategy.our_claims(chap), strategy.chapter_tiles(chap)),
                    ('twin', strategy.twin_claims(chap['parity_reference']),
                     strategy.twin_tiles(chap['parity_reference']))):
                for c in claims:
                    if c['kind'] == 'terrain':
                        with self.subTest(ch=ch, side=key, tile=c['tile']):
                            self.assertTrue(strategy._terrain_line(c, tiles).startswith('note'))


class Validate(unittest.TestCase):
    SECTION = "Use [[Eirika]]'s [[Rapier|rapier]] on the {{title|boss}}."

    def claim(self, **kw):
        return dict({'kind': 'carry', 'unit': 'eirika', 'vs': 'boss',
                     'cite': "Use Eirika's rapier on the boss."}, **kw)

    def test_plain_strips_wiki_markup(self):
        self.assertEqual(strategy.plain(self.SECTION), "Use Eirika's rapier on the boss.")

    def test_a_matching_citation_passes(self):
        strategy.validate([self.claim()], self.SECTION, 'x')

    def test_a_citation_not_in_the_section_raises(self):
        with self.assertRaisesRegex(ValueError, 'does not have'):
            strategy.validate([self.claim(cite='Use Seth.')], self.SECTION, 'x')

    def test_an_unknown_kind_raises(self):
        with self.assertRaisesRegex(ValueError, 'unknown claim kind'):
            strategy.validate([self.claim(kind='vibe')], self.SECTION, 'x')

    def test_a_missing_field_raises(self):
        c = self.claim()
        del c['vs']
        with self.assertRaisesRegex(ValueError, 'lacks vs'):
            strategy.validate([c], self.SECTION, 'x')

    def test_an_unmodelled_claim_names_a_later_step(self):
        c = {'kind': 'unmodelled', 'topic': 'shop', 'step': 6,
             'cite': "Use Eirika's rapier on the boss."}
        with self.assertRaisesRegex(ValueError, 'step 6'):
            strategy.validate([c], self.SECTION, 'x')


class Matching(unittest.TestCase):
    LABELS = frozenset({'goblin-chief', 'armor-knight', 'boss'})

    def test_by_class_id_or_boss(self):
        for vs in ('armor-knight', 'armor_knight', 'goblin-chief', 'boss', 'all'):
            self.assertTrue(strategy.matches(self.LABELS, vs), vs)
        self.assertFalse(strategy.matches(self.LABELS, 'fighter'))

    def test_a_list_means_any(self):
        self.assertTrue(strategy.matches(self.LABELS, ['fighter', 'armor-knight']))
        self.assertFalse(strategy.matches(self.LABELS, ['fighter', 'soldier']))

    def test_twin_labels_name_class_character_and_boss(self):
        labels = strategy.twin_labels('FE8 Ch1')
        self.assertEqual(len(labels), len(dif.vanilla_enemy_bodies('FE8 Ch1')))
        self.assertIn(('breguet', frozenset({'armor-knight', 'breguet', 'boss'})), labels)


class Terrain(unittest.TestCase):
    def test_cover_reads_the_decomp_tables(self):
        self.assertEqual(dif.terrain_cover('forest'), (20, 1, 0))
        self.assertEqual(dif.terrain_cover('fort'), (20, 2, 0))

    def test_a_flier_gets_nothing_from_a_forest(self):
        self.assertEqual(dif.terrain_cover('forest', flier=True), (0, 0, 0))

    def test_on_terrain_folds_terrain_res(self):
        import fe_combat as fc
        u = fc.Combatant('u', 20, 5, 5, 5, 3, 1, 0, 10, fc.W['iron-axe'])
        on, avo = dif.on_terrain(u, 'TERRAIN_FLOOR_MAGIC')
        self.assertEqual(on.res - u.res, dif.terrain_cover('TERRAIN_FLOOR_MAGIC')[2])
        self.assertEqual(avo, dif.terrain_cover('TERRAIN_FLOOR_MAGIC')[0])


class Findings(unittest.TestCase):
    def test_ch04_reads_the_mogalls_as_its_threat(self):
        chap = chapter('ch04')
        out = strategy.findings(chap, dif.chapter_matchup(chap, CAMPAIGN, 'normal'), 'normal')
        self.assertTrue(any(l.startswith('OK   threat mogall') for l in out['ours']), out)

    def test_an_answer_claim_leaves_the_boss_out(self):
        chap = chapter('ch01')
        out = strategy.findings(chap, dif.chapter_matchup(chap, CAMPAIGN, 'normal'), 'normal')
        self.assertTrue(any(l.startswith('OK   answer eirika vs fighter') for l in out['twin']),
                        out)


if __name__ == '__main__':
    unittest.main()
