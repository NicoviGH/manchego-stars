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


class DisplayName(unittest.TestCase):
    def test_every_vanilla_class_reads_as_the_game_names_it(self):
        # The wiki and the class index print classes by this rule; the game's own nameTextId
        # is the reference (FE8 truncates "Pegasus Kn."/"Wyvern Kn."; the full names win).
        import re
        from inject.decomp import vanilla_decomp_text
        from inject.text import messages
        classes = vanilla_decomp_text('src/data_classes.c')
        msgs = messages(vanilla_decomp_text('texts/texts.txt'))
        for m in re.finditer(r'\[(CLASS_\w+) - 1\]\s*=\s*\{(.*?)\n\s*\},', classes, re.S):
            n = re.search(r'\.nameTextId\s*=\s*(0x[0-9a-fA-F]+|\d+)', m.group(2))
            if not n:
                continue
            game = msgs.get(int(n.group(1), 0), '')
            token = m.group(1)[len('CLASS_'):].lower().replace('_', '-')
            self.assertEqual(game.replace(' Kn.', ' Knight'), class_ids.class_display_name(token),
                             token)



class EnumValues(unittest.TestCase):
    """`inject.decomp.enum_values`, the one parser of a decomp header's `NAME = <int>`."""

    TEXT = ('enum {\n    CLASS_NONE = 0x00,\n    CLASS_EIRIKA_LORD = 2,\n'
            '    CHARACTER_WIGHT_CHUnk = 0x5D,\n    CLASS_OBSTACLE = CLASS_EIRIKA_LORD,\n};\n')

    def test_hex_and_decimal_and_mixed_case(self):
        from inject.decomp import enum_values
        self.assertEqual(enum_values(self.TEXT, 'CLASS_'), {'CLASS_NONE': 0, 'CLASS_EIRIKA_LORD': 2})
        self.assertEqual(enum_values(self.TEXT, 'CHARACTER_'), {'CHARACTER_WIGHT_CHUnk': 0x5D})

    def test_a_shift_enumerator_is_its_bit(self):
        # bmunit.h writes unit state bits as `US_UNDER_A_ROOF = (1 << 7),`.
        from inject.decomp import enum_values
        text = 'enum {\n    US_HIDDEN       = (1 << 0),\n    US_UNDER_A_ROOF = (1 << 7),\n};\n'
        self.assertEqual(enum_values(text, 'US_'), {'US_HIDDEN': 1, 'US_UNDER_A_ROOF': 0x80})


if __name__ == '__main__':
    unittest.main()
