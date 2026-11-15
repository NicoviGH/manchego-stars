"""The harness's seal and booster ids (INSPECT.BAG.USE, harness.lua) are the game's own: the
id lists CanUnitUseItem's switch (bmitemuse.c) routes to CanUnitUsePromotionItem and to
CanUnitUseStatGainItem. Bot.supply's rule A gives the convoy every seal and booster a unit
cannot use (ADR 0416), so an id missing here would stay in a bag for good."""
import os
import re
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from inject.decomp import vanilla_decomp_text  # noqa: E402

HARNESS = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'playtest', 'harness.lua')
ROUTES = {'CanUnitUsePromotionItem': 'seal', 'CanUnitUseStatGainItem': 'booster'}


def game_use_ids():
    """{item id: 'seal' | 'booster'} from CanUnitUseItem's switch."""
    ids = {m.group(1): int(m.group(2), 0) for m in re.finditer(
        r'^\s*(ITEM_\w+)\s*=\s*(0x[0-9A-Fa-f]+|\d+)', vanilla_decomp_text('include/constants/items.h'),
        re.M)}
    src = vanilla_decomp_text('src/bmitemuse.c')
    start = re.search(r'^s8 CanUnitUseItem\(', src, re.M).start()
    body = src[start:src.index('\n}\n', start)]
    out = {}
    # each run of case labels and the call its return makes
    for m in re.finditer(r'((?:\s*case ITEM_\w+:)+)\s*return (\w+)\(', body):
        kind = ROUTES.get(m.group(2))
        if kind:
            for name in re.findall(r'case (ITEM_\w+):', m.group(1)):
                out[ids[name]] = kind
    return out


def harness_use_ids():
    with open(HARNESS) as fh:
        text = fh.read()
    table = re.search(r'USE = \{(.*?)\},\n', text, re.S).group(1)
    return {int(i, 16): k for i, k in re.findall(r'\[0x([0-9A-Fa-f]+)\] = "(\w+)"', table)}


class HarnessItemUse(unittest.TestCase):
    def test_the_harness_lists_the_switchs_seals_and_boosters(self):
        game = game_use_ids()
        self.assertEqual(sorted(set(game.values())), ['booster', 'seal'])
        self.assertEqual(harness_use_ids(), game)


if __name__ == '__main__':
    unittest.main()
