#!/usr/bin/env python3
"""Regression coverage for #193's vanilla Snowy Bern forest backfill."""
import hashlib
import json
import os
import struct
import unittest

import map_tileset_tool


REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DECOMP = os.path.join(REPO, 'fireemblem8u')
SNOW_CONFIG = os.path.join(
    REPO, 'campaigns/rime-of-the-frostmaiden/maps/tilesets/snowy-bern/snowy-bern.bin')
LEARNED = os.path.join(
    REPO, 'campaigns/rime-of-the-frostmaiden/maps/reskin-learned.json')

FOREST = 0x0C
FOREST_MAPPING = {
    720: 128, 782: 192, 783: 193, 784: 194, 785: 195,
    815: 225, 816: 226, 817: 227, 848: 258,
}
CASES = (
    ('PrologueMap', 'ch00-prologue', 5,
     '89c0e97a3e880fb3a9f3b8088bde158557a2c6e2f44840be6e488684895a89c1'),
    ('Ch13EirikaMap', 'ch01-the-iron-trail', 33,
     'dc078993983ed4247d05c26e94be228b2f2177cb2aead38b4285b95af7ce64af'),
    # Re-pinned by #495: (4,2) and (7,2) are villages again, not ruins.
    ('Ch2Map', 'ch02-cold-welcome', 27,
     '6085bdced182996a36fffd4f4ee951ad88b78623ab6121571b45e46232614b69'),
)


def _metatiles(path):
    with open(path, 'rb') as source:
        raw = source.read()
    values = struct.unpack('<%dH' % (len(raw) // 2), raw)
    indices = [value >> 5 for value in values]
    if list(values) != [index << 5 for index in indices]:
        raise AssertionError('%s is not metatile << 5 encoded' % path)
    return indices


def _vanilla_config(layout):
    """The tile config vanilla's chapter settings select for `layout`, read at HEAD."""
    names, map_data = map_tileset_tool._vanilla_layout_map(DECOMP, layout)
    return os.path.join(DECOMP, 'graphics/map', names[map_data['tileConfigId']] + '.bin')


class TestWinterForestBackfill(unittest.TestCase):
    def test_tracked_forest_cells_keep_the_vanilla_sequences(self):
        with open(LEARNED, encoding='utf-8') as source:
            learned = json.load(source)
        self.assertEqual(
            {source: learned['map'].get(str(source)) for source in FOREST_MAPPING},
            FOREST_MAPPING)

        with open(SNOW_CONFIG, 'rb') as source:
            snowy_config = source.read()
        for layout, winter_stem, count, nonforest_hash in CASES:
            vanilla = _metatiles(os.path.join(
                DECOMP, 'graphics/map/layout', layout + '.mar'))
            winter = _metatiles(os.path.join(
                REPO, 'campaigns/rime-of-the-frostmaiden/maps', winter_stem + '.mar'))
            with open(_vanilla_config(layout), 'rb') as source:
                vanilla_config = source.read()
            forest_cells = [
                cell for cell, metatile in enumerate(vanilla)
                if vanilla_config[8192 + metatile] == FOREST
            ]

            with self.subTest(layout=layout, invariant='forest count'):
                self.assertEqual(len(forest_cells), count)
            with self.subTest(layout=layout, invariant='aligned forest targets'):
                self.assertEqual(
                    [winter[cell] for cell in forest_cells],
                    [FOREST_MAPPING[vanilla[cell]] for cell in forest_cells])
            with self.subTest(layout=layout, invariant='winter forest terrain'):
                self.assertEqual(
                    [snowy_config[8192 + winter[cell]] for cell in forest_cells],
                    [FOREST] * count)
            with self.subTest(layout=layout, invariant='non-forest cells'):
                packed = b''.join(
                    struct.pack('<H', target)
                    for source, target in zip(vanilla, winter)
                    if vanilla_config[8192 + source] != FOREST)
                self.assertEqual(hashlib.sha256(packed).hexdigest(), nonforest_hash)


if __name__ == '__main__':
    unittest.main()
