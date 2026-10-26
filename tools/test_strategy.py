#!/usr/bin/env python3
"""Tests for tools/strategy.py -- the Strategy sections as claims (#510 step 6).

    python3 tools/test_strategy.py
"""
import os
import sys
import unittest

import yaml

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import campaign_chapters
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

    def test_every_hosted_chapter_is_curated(self):
        for ch in HOSTED:
            with self.subTest(ch=ch):
                self.assertTrue(strategy.our_claims(chapter(ch)))

    def test_every_chapter_with_claims_resolves(self):
        """Planned chapters included: a claim is checked where it is written, not when the
        chapter is next read."""
        for chap in campaign_chapters.load_all(CAMPAIGN):
            if chap.get('strategy_claims'):
                with self.subTest(ch=chap.get('id')):
                    strategy.our_claims(chap)

    def test_every_story_chapter_has_claims(self):
        """Every vendored twin page with a Strategy section is curated (#510 step 9, C4): the
        vanilla baseline's bot reads them. Lagdou Ruins and Tower of Valni have no section,
        and Village of Silence's is empty, so none of them can be."""
        curated = {e['page'] for e in strategy._twin_file().values()}
        for name in sorted(os.listdir(strategy.TWIN_PAGES)):
            page = name[:-len('.wiki')]
            try:
                body = strategy.plain(strategy.twin_section(page))
            except ValueError:
                continue                            # no ==Strategy== section
            if body:
                with self.subTest(page=page):
                    self.assertIn(page, curated)

    def test_every_twin_claim_names_a_real_character_class_or_terrain(self):
        """The bot's runner resolves `unit`/`vs`/`tile` to the game's ids; a name the decomp does not
        have would raise there, hours into a run. Catch it here."""
        import inject.decomp as decomp
        names = {'all', 'boss'}
        for header, prefix in (('characters.h', 'CHARACTER_'), ('classes.h', 'CLASS_')):
            text = decomp.vanilla_decomp_text('include/constants/' + header)
            names |= {strategy._norm(n) for n in decomp.enum_values(text, prefix)}
        terrains = set(decomp.enum_values(
            decomp.vanilla_decomp_text('include/constants/terrains.h'), 'TERRAIN_'))
        for ref in strategy._twin_file():
            for c in strategy.twin_claims(ref):
                for field in ('unit', 'vs'):
                    vals = c.get(field)
                    for v in (vals if isinstance(vals, list) else [vals] if vals else []):
                        with self.subTest(ref=ref, field=field, name=v):
                            self.assertIn(strategy._norm(v), names)
                if 'tile' in c:
                    with self.subTest(ref=ref, field='tile', name=c['tile']):
                        self.assertIn(dif._terrain_key(c['tile']), terrains)

    def test_late_claims_not_read_by_parity(self):
        """ADR 0363: a planned chapter gets no strategy reading, so the claims curated past Ch7
        (bot data for the vanilla baseline) never reach our parity model."""
        planned = [c for c in campaign_chapters.load_all(CAMPAIGN) if c.get('status') == 'planned']
        self.assertTrue(planned)
        with self.assertRaisesRegex(ValueError, 'ADR 0363'):
            strategy.findings(planned[0], None)

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

    def test_plain_drops_a_comment_left_open(self):
        self.assertEqual('Use the forts.', strategy.plain('Use the forts. <!-- trailing'))

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

    def test_an_unmodelled_topic_must_be_in_the_taxonomy(self):
        c = {'kind': 'unmodelled', 'topic': 'village race',
             'cite': "Use Eirika's rapier on the boss."}
        with self.assertRaisesRegex(ValueError, 'not in the taxonomy'):
            strategy.validate([c], self.SECTION, 'x')

    def test_a_kits_topic_must_be_in_the_taxonomy(self):
        c = {'kind': 'kits', 'topic': 'loot', 'cite': "Use Eirika's rapier on the boss."}
        with self.assertRaisesRegex(ValueError, 'kits topic'):
            strategy.validate([c], self.SECTION, 'x')

    def test_a_claim_carries_no_step(self):
        """The topic fixes the step; a second copy in the claim could disagree with it."""
        c = {'kind': 'unmodelled', 'topic': 'recruit', 'step': 7,
             'cite': "Use Eirika's rapier on the boss."}
        with self.assertRaisesRegex(ValueError, 'carries no step'):
            strategy.validate([c], self.SECTION, 'x')

    def test_every_topic_has_a_step_and_a_meaning(self):
        for topic, (step, meaning) in strategy.TOPICS.items():
            with self.subTest(topic=topic):
                self.assertIn(step, (7, 'out'))
                self.assertTrue(meaning)

    def test_a_kits_claim_needs_a_topic(self):
        c = {'kind': 'kits', 'cite': "Use Eirika's rapier on the boss."}
        with self.assertRaisesRegex(ValueError, 'lacks topic'):
            strategy.validate([c], self.SECTION, 'x')


class KitsAndOut(unittest.TestCase):
    def test_a_kits_claim_reports_it_is_modelled(self):
        line = strategy._check({'kind': 'kits', 'topic': 'villages'}, [], [], [], {}, {})
        self.assertIn('kits villages', line)
        self.assertIn('happy path', line)

    def test_out_topics_print_as_not_modelled_by_decision(self):
        claims = [{'kind': 'unmodelled', 'topic': 'healing'},
                  {'kind': 'unmodelled', 'topic': 'recruit'}]
        self.assertEqual(['    unmodelled, step 7: recruit',
                          '    not modelled (ADR 0365): healing'],
                         strategy.unmodelled_lines(claims))


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
        self.assertIn(('breguet', frozenset({'armor-knight', 'breguet', 'boss'})),
                      [(t, lab) for _n, t, lab in labels])


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
        _claims, lines = strategy.findings(
            chap, dif.chapter_matchup(chap, CAMPAIGN, 'normal'), 'normal')['ours']
        self.assertTrue(any(l.startswith('OK   threat mogall') for l in lines), lines)

    def test_an_answer_claim_leaves_the_boss_out(self):
        chap = chapter('ch01')
        _claims, lines = strategy.findings(
            chap, dif.chapter_matchup(chap, CAMPAIGN, 'normal'), 'normal')['twin']
        self.assertTrue(any(l.startswith('OK   answer eirika vs fighter') for l in lines), lines)


if __name__ == '__main__':
    unittest.main()
