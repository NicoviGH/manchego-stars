#!/usr/bin/env python3
"""Tests for the iconic-matchup injection (#8).

One campaign flavor decision -- fire bites Icewind's ice-creatures -- expressed as
vanilla FE8 class-keyed effectiveness (x3, decisions.md §Combat "Iconic matchups").
campaign.yaml `iconic_matchups:` is the source of truth; these tests pin (a) the
generated C list shape, (b) the x3 math in the difficulty model, and (c) that the
YAML and the model can't silently drift apart.
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import build_campaign as bc  # noqa: E402
import difficulty as df      # noqa: E402
import fe_combat as fc       # noqa: E402

import yaml  # noqa: E402

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CAMPAIGN_YAML = os.path.join(REPO, 'campaigns/rime-of-the-frostmaiden/campaign.yaml')

CLASSES_H = 'enum { CLASS_CYCLOPS = 0x5A, CLASS_DRUID = 0x2F, };'


class TestMatchupClassList(unittest.TestCase):
    def test_snippet_shape(self):
        ident, snippet = bc._matchup_class_list(
            {'id': 'fire-vs-ice', 'effective_vs': ['cyclops', 'druid']}, CLASSES_H)
        self.assertEqual(ident, 'ItemEffectiveness_Iconic_fire_vs_ice')
        self.assertIn('CONST_DATA u8 ItemEffectiveness_Iconic_fire_vs_ice[]', snippet)
        self.assertIn('    CLASS_CYCLOPS,\n', snippet)
        self.assertIn('    CLASS_DRUID,\n', snippet)
        self.assertTrue(snippet.rstrip().endswith('0,\n};'))   # 0-terminated list

    def test_unknown_class_rejected(self):
        with self.assertRaises(SystemExit):
            bc._matchup_class_list(
                {'id': 'x', 'effective_vs': ['ice-weasel']}, CLASSES_H)


class TestEffectiveMath(unittest.TestCase):
    def _target(self, tags):
        return fc.Combatant('t', hp=30, pow=0, skl=0, spd=0, df=0, res=5, lck=0,
                            con=10, weapon=None, tags=frozenset(tags))

    def _mage(self, weapon):
        return fc.Combatant('m', hp=20, pow=6, skl=8, spd=8, df=2, res=6, lck=4,
                            con=6, weapon=fc.W[weapon])

    def test_fire_triples_vs_cyclops_tag(self):
        # (Pow 6 + Fire Mt 5) x3 - Res 5 = 28, vs 6 plain
        self.assertEqual(fc.damage(self._mage('fire'), self._target({'cyclops'})), 28)
        self.assertEqual(fc.damage(self._mage('fire'), self._target(set())), 6)

    def test_elfire_triples_vs_druid_tag(self):
        self.assertEqual(fc.damage(self._mage('elfire'), self._target({'druid'})),
                         (6 + 10) * 3 - 5)

    def test_flux_is_not_effective(self):
        self.assertEqual(fc.damage(self._mage('flux'), self._target({'cyclops'})),
                         6 + 7 - 5)


class TestYamlModelConsistency(unittest.TestCase):
    """campaign.yaml drives the ROM; fe_combat/difficulty drive the balance math.
    If one gains a matchup the other doesn't know, parity reads go silently wrong."""

    def setUp(self):
        with open(CAMPAIGN_YAML, encoding='utf-8') as f:
            self.matchups = (yaml.safe_load(f) or {}).get('iconic_matchups') or []

    def test_campaign_declares_the_matchup(self):
        self.assertTrue(self.matchups, 'campaign.yaml lost its iconic_matchups block')

    def test_model_mirrors_every_yaml_matchup(self):
        for m in self.matchups:
            target_tags = set()
            for tok in m['effective_vs']:
                enum = 'CLASS_' + str(tok).upper().replace('-', '_')
                tags = df.CLASS_TAGS.get(enum)
                self.assertTrue(tags, '%s: CLASS_TAGS has no tags for %s -- the '
                                'difficulty model would miss this matchup' % (m['id'], enum))
                target_tags |= set(tags)
            for wkey in m['weapons']:
                w = fc.W.get(wkey)
                self.assertIsNotNone(w, '%s: fe_combat.W has no %r' % (m['id'], wkey))
                self.assertTrue(set(w.effective) & target_tags,
                                '%s: fe_combat.W[%r].effective misses the matchup '
                                'tags %s' % (m['id'], wkey, sorted(target_tags)))

    def test_yaml_weapons_resolve_to_items(self):
        from inject.decomp import WEAPON_ITEM_ENUM
        for m in self.matchups:
            for wkey in m['weapons']:
                self.assertIn(wkey, WEAPON_ITEM_ENUM)


if __name__ == '__main__':
    unittest.main()
