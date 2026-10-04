#!/usr/bin/env python3
"""The chapter class resolver (inject.class_ids): a token deploys as its vanilla class unless a
reskin `dresses` it for THAT chapter."""
import os
import shutil
import tempfile
import unittest
from unittest import mock

import inject.class_ids as class_ids
from inject.class_ids import ChapterClassIds, reskin_claims


class ChapterScope(unittest.TestCase):
    def test_one_base_dresses_two_chapters_differently(self):
        # #347: goblin-soldier and risen-spear both clone CLASS_SOLDIER. Keyed on base, the
        # later claim won and ch01's goblins shipped as ch05's skeletons.
        self.assertEqual('CLASS_BLST_REGULAR_EMPTY', ChapterClassIds('ch01')['soldier'])
        self.assertEqual('CLASS_SOL_SKELEBERDIER', ChapterClassIds('ch05')['soldier'])

    def test_an_undressed_token_is_its_vanilla_class(self):
        self.assertEqual('CLASS_ARMOR_KNIGHT', ChapterClassIds('ch01')['armor-knight'])
        self.assertEqual('CLASS_SOLDIER', ChapterClassIds('ch02')['soldier'])
        self.assertEqual('CLASS_PEGASUS_KNIGHT', ChapterClassIds('ch02')['pegasus_knight'])

    def test_deploy_class_wins_over_class(self):
        ids = ChapterClassIds('ch03')
        self.assertEqual('CLASS_MNC_LIZARDZERKER_BRUTE',
                         ids.for_entry({'class': 'brigand', 'deploy_class': 'brigand-brute'}))
        self.assertEqual('CLASS_BRG_LIZARD_WILDLING', ids.for_entry({'class': 'brigand'}))

    def test_a_token_that_is_neither_raises(self):
        # 'brigand-brute' outside ch03 would derive CLASS_BRIGAND_BRUTE, which is not vanilla.
        # An appended reskin slot must never pass for a vanilla class either.
        with self.assertRaises(KeyError):
            ChapterClassIds('ch01')['brigand-brute']
        with self.assertRaises(KeyError):
            ChapterClassIds('ch01')['sol-skeleberdier']


class DuplicateClaim(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix='class_ids_')
        os.makedirs(os.path.join(self.tmp, 'campaigns', 'dup'))
        with open(os.path.join(self.tmp, 'campaigns', 'dup', 'campaign.yaml'), 'w') as f:
            f.write('enemy_class_reskins:\n'
                    '  - {id: a, base: CLASS_SOLDIER, slot: CLASS_A, dresses: {ch09: [soldier]}}\n'
                    '  - {id: b, base: CLASS_SOLDIER, slot: CLASS_B, dresses: {ch09: [soldier]}}\n')
        reskin_claims.cache_clear()

    def tearDown(self):
        reskin_claims.cache_clear()
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_two_reskins_dressing_one_chapter_token_is_an_error(self):
        with mock.patch.object(class_ids, 'REPO', self.tmp):
            with self.assertRaises(SystemExit) as cm:
                reskin_claims('dup')
        self.assertIn("'a' and 'b'", str(cm.exception))


if __name__ == '__main__':
    unittest.main()
