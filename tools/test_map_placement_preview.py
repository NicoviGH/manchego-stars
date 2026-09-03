#!/usr/bin/env python3
"""map_placement_preview -- the picture a placement decision gets made on (#26).

What is worth testing here is not the pixels: it is that every number the picture asserts
is DERIVED from the engine and the chapter, never from a constant somebody typed. A
placement render that quietly disagrees with the build is worse than no render.
"""
import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import campaign_chapters as cc                                       # noqa: E402
import map_placement_preview as pp                                   # noqa: E402


def ch06():
    return [c for c in cc.load_all() if str(c['id']).startswith('ch06')][0]


class MoveCostRow(unittest.TestCase):
    """Costs come from data_terrains.c at HEAD, because the build patches the worktree."""

    def test_foot_row_matches_the_engine(self):
        row = pp.mov_cost_row()
        self.assertEqual(row[pp.TERRAIN['TERRAIN_PLAINS']], 1)
        self.assertEqual(row[pp.TERRAIN['TERRAIN_FOREST']], 2)
        # Impassable is ABSENT, not zero -- callers test membership.
        self.assertNotIn(pp.TERRAIN['TERRAIN_RIVER'], row)
        self.assertNotIn(pp.TERRAIN['TERRAIN_PEAK'], row)

    def test_a_flier_crosses_what_a_ground_class_cannot(self):
        fly = pp.mov_cost_row('TerrainTable_MovCost_FlyNormal')
        for terrain in ('TERRAIN_RIVER', 'TERRAIN_PEAK', 'TERRAIN_TILE_2E'):
            self.assertEqual(fly[pp.TERRAIN[terrain]], 1, terrain)

    def test_tile_2e_is_the_pocket_wall_it_is_claimed_to_be(self):
        """ch06's boat pockets rest entirely on this: TILE_2E stops every ground class and
        stops no flier. If the engine ever disagreed, the chapter's geometry would be a
        fiction (decisions.md -> 'ch06's boats sit in POCKETS')."""
        wall = pp.TERRAIN['TERRAIN_TILE_2E']
        for table in ('CommonT1Normal', 'HorseT1Normal', 'ArmorNormal',
                      'PirateNormal', 'ThiefNormal', 'BrigandNormal', 'AnimalT1Normal'):
            self.assertNotIn(wall, pp.mov_cost_row('TerrainTable_MovCost_' + table), table)
        self.assertIn(wall, pp.mov_cost_row('TerrainTable_MovCost_FlyNormal'))

    def test_an_unknown_table_is_refused_not_guessed(self):
        with self.assertRaises(SystemExit):
            pp.mov_cost_row('TerrainTable_MovCost_NoSuchClass')


class Board(unittest.TestCase):
    def setUp(self):
        self.chap = ch06()
        self.grid, self.terrain, self.ts = pp.load_map('ch06-maer-monster')

    def test_deploy_block_is_parsed_from_the_chapter_not_hardcoded(self):
        cells = pp.deploy_cells(self.chap, self.terrain)
        self.assertTrue(cells)
        for x, y in cells:
            self.assertTrue(4 <= x <= 10 and 0 <= y <= 2, (x, y))

    def test_every_boat_has_exactly_one_ground_neighbour_its_door(self):
        """The pocket, asserted against the compiled map rather than the prose."""
        foot = pp.mov_cost_row()
        for boat in self.chap['rescue_boats']:
            bx, by = boat['tile']
            ground = [(bx + dx, by + dy) for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1))
                      if foot.get(self.terrain[by + dy][bx + dx])]
            self.assertEqual(ground, [tuple(boat['door'])], boat['id'])
            self.assertEqual(boat['attackable_sides'], 1, boat['id'])

    def test_placed_units_are_read_from_the_chapters_own_positions(self):
        units = pp.placed_units(self.chap)
        self.assertEqual(len(units), sum(int(e.get('count', 1))
                                         for e in self.chap['enemy_units']))
        behaviours = {b for _, _, b, _, _ in units}
        self.assertIn('never-move', behaviours)
        self.assertIn('pursue', behaviours)
        self.assertIn('hold-position', behaviours)          # the boss, flagged by is_boss

    def test_no_enemy_stands_where_its_class_cannot(self):
        """The failure this tool exists to make impossible: a coordinate that looks fine on
        a grid and is water, wall or pocket to the class standing on it."""
        import re
        import build_campaign as bc
        classes = bc.vanilla_decomp_text('src/data_classes.c')
        enums = {'soldier': 'CLASS_SOLDIER', 'fighter': 'CLASS_FIGHTER',
                 'cavalier': 'CLASS_CAVALIER', 'mercenary': 'CLASS_MERCENARY',
                 'armor-knight': 'CLASS_ARMOR_KNIGHT', 'shaman': 'CLASS_SHAMAN',
                 'mage': 'CLASS_MAGE', 'priest': 'CLASS_PRIEST',
                 'troubadour': 'CLASS_TROUBADOUR', 'archer': 'CLASS_ARCHER',
                 'bael': 'CLASS_BAEL'}
        for enemy in self.chap['enemy_units']:
            block = re.search(r'\[%s - 1\] = \{(.*?)\n    \},' % enums[enemy['class']],
                              classes, re.S).group(1)
            table = re.search(r'pMovCostTable = \{\s*(TerrainTable_MovCost_\w+)',
                              block).group(1)
            costs = pp.mov_cost_row(table)
            for x, y in enemy['positions']:
                self.assertIn(self.terrain[y][x], costs,
                              '%s (%s) cannot stand on (%d,%d)'
                              % (enemy['id'], enemy['class'], x, y))

    def test_no_two_units_share_a_tile(self):
        tiles = [t for t, _, _, _, _ in pp.placed_units(self.chap)]
        self.assertEqual(len(tiles), len(set(tiles)))

    def test_render_writes_a_png(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = os.path.join(tmp, 'board.png')
            pp.render(self.chap, 'ch06-maer-monster', out, zoom=1)
            self.assertTrue(os.path.getsize(out) > 0)

    def test_a_concept_file_overrides_the_yaml(self):
        with tempfile.TemporaryDirectory() as tmp:
            concept = os.path.join(tmp, 'c.json')
            with open(concept, 'w') as fh:
                json.dump({'name': 'probe', 'premise': 'x',
                           'units': {'nerra': [[9, 12]]}}, fh)
            placed = dict((eid, tile) for tile, _, _, eid, _
                          in pp.placed_units(self.chap, concept))
            self.assertEqual(placed['nerra'], (9, 12))


if __name__ == '__main__':
    unittest.main()
