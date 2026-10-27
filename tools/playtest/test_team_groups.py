"""team_groups.py: every class a player unit can hold has a group (#510 step 9 PR E)."""
import os
import re
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.dirname(HERE))

import team_groups as tg  # noqa: E402
import difficulty  # noqa: E402
import inject.cast  # noqa: E402
import inject.decomp  # noqa: E402
import inject.paths  # noqa: E402
from inject.sms import promotion_branches  # noqa: E402
from inject.class_ids import DEFAULT_CAMPAIGN  # noqa: E402


def with_promotions(classes):
    """The classes plus everything FE8's branching promotion table reaches from them."""
    branches, out, todo = promotion_branches(), set(), list(classes)
    while todo:
        c = todo.pop()
        if c not in out:
            out.add(c)
            todo.extend(branches.get(c, ()))
    return out


def vanilla_player_classes():
    """Each story unit's default class, Eirika (0x01) to Tana (0x22): the enum's playable run."""
    chars = inject.decomp.enum_values(
        inject.decomp.vanilla_decomp_text('include/constants/characters.h'), 'CHARACTER_')
    text = inject.decomp.vanilla_decomp_text('src/data_characters.c')
    out = set()
    for name, v in chars.items():
        if chars['CHARACTER_EIRIKA'] <= v <= chars['CHARACTER_TANA']:
            s, e = inject.decomp._find_brace_block(text, '[%s - 1]' % name,
                                                   inject.paths.CHARACTERS_C)
            out.add(re.search(r'\.defaultClass\s*=\s*(CLASS_\w+)', text[s:e]).group(1))
    return out


def our_player_classes():
    return {inject.cast.class_enum_for(inject.cast.load_unit(DEFAULT_CAMPAIGN, uid))
            for uid in difficulty.ROSTER}


class EveryPlayerClassHasAGroup(unittest.TestCase):
    def check(self, classes):
        missing = sorted(with_promotions(classes) - set(tg.class_group()))
        self.assertEqual(missing, [], 'player classes with no team group')

    def test_vanilla(self):
        self.check(vanilla_player_classes())

    def test_ours(self):
        self.check(our_player_classes())


class Table(unittest.TestCase):
    def test_every_capped_group_exists(self):
        self.assertLessEqual(set(tg.MAXIMA), set(tg.GROUPS))

    def test_env_carries_decomp_ids(self):
        env = tg.env()
        self.assertEqual(env['groups'][str(0x05)], 'mounted')       # CLASS_CAVALIER
        self.assertEqual(env['groups'][str(0x02)], 'lord')          # CLASS_EIRIKA_LORD
        self.assertEqual(env['maxima']['armour'], 1)

    def test_a_class_in_two_groups_raises(self):
        saved = tg.GROUPS
        try:
            tg.GROUPS = dict(saved, extra=('CLASS_CAVALIER',))
            with self.assertRaises(ValueError):
                tg.class_group()
        finally:
            tg.GROUPS = saved


if __name__ == '__main__':
    unittest.main()
