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
        # SHAPES, derived from the whole AI vector, not the approach byte alone. `striker` is
        # the one the old two-label vocabulary could not say: holds ground, but steps out
        # within its own move range to strike. It is most of this roster, and reading those
        # units as `never-move` is what let ch06's clock be designed around a line that in
        # fact walks to the boats (decisions.md -> "AI_B is the APPROACH and AI_A is the
        # ACTION"). The boss is `statue` because his VECTOR says so -- GuardTileAI, inherited
        # from Novala -- rather than because an `is_boss` flag patched the label.
        behaviours = {b for _, _, b, _, _ in units}
        self.assertIn('striker', behaviours)
        self.assertIn('pursuer', behaviours)
        self.assertIn('statue', behaviours)
        self.assertNotIn('hold-position', behaviours)

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


class ContestedReach(unittest.TestCase):
    """`reached_on:` is the number ch06's whole clock rests on, and until now nothing read it.

    It was also measured on an EMPTY MAP: `foot_reach` was a Dijkstra over terrain that did not
    know units exist. In FE a unit cannot move through an enemy body, so a line standing across
    a channel is a wall -- and ch06's east boat sits behind exactly such a line. An uncontested
    number flatters our map more than it flatters vanilla's, whose rescue route peels away from
    the fight entirely (decisions.md -> "Vanilla Ch6's urgency is TRAVEL TIME").
    """

    def _grid(self):
        # 5x1 corridor of plain, cost 1 per step.
        plain = [t for t, c in pp.FOOT_COST.items() if c == 1][0]
        return [[plain] * 5]

    def test_an_open_corridor_costs_one_point_per_step(self):
        dist = pp.foot_reach(self._grid(), [(0, 0)])
        self.assertEqual(4, dist[(4, 0)])

    def test_a_body_in_the_corridor_makes_the_far_side_UNREACHABLE(self):
        """The whole point: FE has no phasing through an enemy."""
        dist = pp.foot_reach(self._grid(), [(0, 0)], blocked={(2, 0)})
        self.assertNotIn((4, 0), dist)
        self.assertEqual(1, dist[(1, 0)])

    def test_a_body_ON_the_source_does_not_break_the_walk(self):
        dist = pp.foot_reach(self._grid(), [(0, 0)], blocked={(0, 0)})
        self.assertEqual(4, dist[(4, 0)])

    def test_blocked_defaults_to_empty_so_the_old_reading_is_still_available(self):
        self.assertEqual(pp.foot_reach(self._grid(), [(0, 0)]),
                         pp.foot_reach(self._grid(), [(0, 0)], blocked=set()))

    def test_turns_is_ceiling_of_points_over_move(self):
        """A unit spends up to `mov` points a turn, so 6 points at mov 5 is two turns."""
        self.assertEqual(1, pp.arrival_turn(5, 5))
        self.assertEqual(2, pp.arrival_turn(6, 5))
        self.assertEqual(2, pp.arrival_turn(10, 5))
        self.assertIsNone(pp.arrival_turn(None, 5))


class FiringCellsLivesHereNotInRescueForecast(unittest.TestCase):
    """`firing_cells` (every foot-standable cell within weapon range of a target) is a
    terrain/range primitive, the same family as `foot_reach`/`mov_cost_row` -- it belongs on
    this module's desk, not `rescue_forecast`'s, which had grown its own copy of the exact
    Manhattan-range check `units_reaching` already does inline. `rescue_forecast.firing_cells`
    is now an alias, so a fix to the rule (the range bound, the passability gate) cannot land
    in one consumer and not the other."""

    def test_firing_cells_lives_on_map_placement_preview(self):
        terrain = [[pp.TERRAIN['TERRAIN_PLAINS']] * 5] * 5
        self.assertEqual(pp.firing_cells(terrain, (2, 2), 1),
                         [(1, 2), (2, 1), (2, 3), (3, 2)])

    def test_rescue_forecast_is_an_alias_not_a_second_copy(self):
        import rescue_forecast as rf
        self.assertIs(rf.firing_cells, pp.firing_cells)

    def test_units_reaching_shares_the_same_range_rule_firing_cells_uses(self):
        """A STATUE (budget 0 -- cannot move, even to attack) is a threat only from the tile
        it already stands on, which isolates the pure RANGE check from any movement search:
        a body on one of `firing_cells`'s own cells is found; the same tile one step outside
        the range bound is not -- both directions, so a swap to a shared implementation
        can't silently widen or narrow who counts as a threat."""
        plain = [t for t, c in pp.FOOT_COST.items() if c == 1][0]
        terrain = [[plain] * 6]
        statue = {'ai': '{0x3, 0x3, 0x0, 0x0}', 'why': 't'}   # ActionStanding + NeverMove
        chap = {'enemy_units': [
            {'id': 'in-range', 'class': 'soldier', 'level': 1,
             'inventory': [{'id': 'iron-lance'}], 'positions': [[1, 0]],
             'ai_override': statue},
            {'id': 'out-of-range', 'class': 'soldier', 'level': 1,
             'inventory': [{'id': 'iron-lance'}], 'positions': [[5, 0]],
             'ai_override': statue},
        ]}
        found = {eid for eid, _ai in pp.units_reaching(chap, terrain, [(2, 0)])}
        self.assertIn('in-range', found)          # iron-lance range 2: |1-2| = 1
        self.assertNotIn('out-of-range', found)   # |5-2| = 3, past range


class EnemyBodiesAndUnitsReachingReadEveryRosterKey(unittest.TestCase):
    """`enemy_bodies` and `units_reaching` both docstring-claimed to cover reinforcements and
    both did not: `enemy_bodies` never looked past `enemy_units:`, and a naive fix that just
    widened the loop without the KEY test would have flipped the bug rather than fixed it,
    since a `reinforcements:`/`enemy_reinforcements:` entry carries `trigger_turn`, not
    `arrives_turn` -- ch02's real `rear-raiders` wave (#367).
    """

    def test_a_reinforcements_key_entry_is_not_a_turn1_blocking_body(self):
        chap = {'reinforcements': [{'id': 'w', 'trigger_turn': 3, 'positions': [[2, 0]]}]}
        self.assertEqual(pp.enemy_bodies(chap), set())

    def test_an_enemy_reinforcements_key_entry_is_not_a_turn1_body_either(self):
        chap = {'enemy_reinforcements': [{'id': 'w', 'trigger_turn': 3,
                                          'positions': [[2, 0]]}]}
        self.assertEqual(pp.enemy_bodies(chap), set())

    def test_an_enemy_units_entry_is_still_a_turn1_blocking_body(self):
        chap = {'enemy_units': [{'id': 'a', 'positions': [[1, 0]]}]}
        self.assertEqual(pp.enemy_bodies(chap), {(1, 0)})

    def test_an_enemy_units_wave_past_turn_1_is_still_excluded(self):
        chap = {'enemy_units': [{'id': 'a', 'arrives_turn': 4, 'positions': [[1, 0]]}]}
        self.assertEqual(pp.enemy_bodies(chap), set())

    def test_units_reaching_finds_a_unit_declared_under_reinforcements(self):
        """The docstring has always claimed this ("REINFORCEMENTS ARE INCLUDED"); it was
        only ever true of ch06 because ch06 happens to keep its wave inside `enemy_units`."""
        plain = [t for t, c in pp.FOOT_COST.items() if c == 1][0]
        terrain = [[plain] * 5]
        chap = {'reinforcements': [{
            'id': 'w', 'class': 'soldier', 'level': 1, 'trigger_turn': 3,
            'inventory': [{'id': 'iron-lance'}], 'positions': [[0, 0]],
            'ai_override': {'ai': '{0x0, 0x0, 0x0, 0x0}', 'why': 'test pursuer'},
        }]}
        found = pp.units_reaching(chap, terrain, [(4, 0)])
        self.assertEqual([f[0] for f in found], ['w'])

    def _reinforcement_entry(self, eid='w'):
        return {'id': eid, 'class': 'soldier', 'level': 1, 'trigger_turn': 3,
                'inventory': [{'id': 'iron-lance'}], 'positions': [[0, 0]],
                'ai_override': {'ai': '{0x0, 0x0, 0x0, 0x0}', 'why': 'test pursuer'}}

    def test_placed_units_draws_a_reinforcements_key_wave_too(self):
        """`placed_units` -- the tool's own PNG render, not a value any gate consumes --
        was the THIRD copy of this exact bug: it still read `chapter.get('enemy_units')`
        alone, so a `reinforcements:`/`enemy_reinforcements:` wave was simply absent from
        the picture, even after `enemy_bodies` and `units_reaching` were fixed to see it."""
        chap = {'reinforcements': [self._reinforcement_entry()]}
        units = pp.placed_units(chap)
        self.assertEqual([eid for _tile, _code, _beh, eid, _late in units], ['w'])

    def test_placed_units_marks_a_reinforcements_key_wave_as_LATE(self):
        """The render draws a late body as a hollow ring -- 'not here at turn 1'. A
        reinforcement-key entry is never turn-1 regardless of its own fields, per
        `build_campaign.entry_is_turn1`."""
        chap = {'reinforcements': [self._reinforcement_entry()]}
        _tile, _code, _beh, _eid, late = pp.placed_units(chap)[0]
        self.assertTrue(late)

    def test_placed_units_still_marks_a_hard_mode_only_enemy_units_entry_as_LATE(self):
        """`hard_mode_only` is a MODE gate, not a turn-arrival one -- `entry_is_turn1` does
        not know about it, so the two conditions have to stay OR'd, not replaced."""
        chap = {'enemy_units': [{'id': 'h', 'class': 'soldier', 'level': 1,
                                 'hard_mode_only': True,
                                 'inventory': [{'id': 'iron-lance'}], 'positions': [[0, 0]],
                                 'ai_override': {'ai': '{0x0, 0x0, 0x0, 0x0}', 'why': 't'}}]}
        _tile, _code, _beh, _eid, late = pp.placed_units(chap)[0]
        self.assertTrue(late)

    def test_placed_units_still_marks_a_plain_enemy_units_body_as_not_late(self):
        chap = {'enemy_units': [{'id': 'a', 'class': 'soldier', 'level': 1,
                                 'inventory': [{'id': 'iron-lance'}], 'positions': [[0, 0]],
                                 'ai_override': {'ai': '{0x0, 0x0, 0x0, 0x0}', 'why': 't'}}]}
        _tile, _code, _beh, _eid, late = pp.placed_units(chap)[0]
        self.assertFalse(late)


class ArrivalTurnToIsSharedByBothDirections(unittest.TestCase):
    """`reached_on` (MANY deploy cells -> ONE target) and `rescue_forecast.arrival_to_cells`
    (ONE enemy -> MANY candidate firing cells) were mirror-image compositions of the exact
    same two primitives, `foot_reach` then `arrival_turn`, glued together twice. One
    function that takes both ends as lists covers either direction; `reached_on` and
    `arrival_to_cells` are both thin callers of it now."""

    def test_many_sources_to_one_target_matches_reached_on(self):
        plain = [t for t, c in pp.FOOT_COST.items() if c == 1][0]
        terrain = [[plain] * 6]
        got = pp.arrival_turn_to(terrain, [(0, 0), (5, 0)], 'TerrainTable_MovCost_CommonT1Normal',
                                 mov=3, targets=[(2, 0)])
        self.assertEqual(got, 1)          # (0,0) is 2 points away, one turn at mov 3

    def test_one_source_to_many_targets_matches_arrival_to_cells(self):
        plain = [t for t, c in pp.FOOT_COST.items() if c == 1][0]
        terrain = [[plain] * 6]
        got = pp.arrival_turn_to(terrain, [(0, 0)], 'TerrainTable_MovCost_CommonT1Normal',
                                 mov=3, targets=[(5, 0), (2, 0)])
        self.assertEqual(got, 1)          # the NEARER target wins, whichever list position

    def test_no_reachable_target_is_none_not_an_error(self):
        plain = [t for t, c in pp.FOOT_COST.items() if c == 1][0]
        terrain = [[plain] * 6]
        got = pp.arrival_turn_to(terrain, [(0, 0)], 'TerrainTable_MovCost_CommonT1Normal',
                                 mov=3, targets=[])
        self.assertIsNone(got)

    def test_rescue_forecasts_arrival_to_cells_delegates_to_the_shared_primitive(self):
        import rescue_forecast as rf
        plain = [t for t, c in pp.FOOT_COST.items() if c == 1][0]
        terrain = [[plain] * 6]
        via_wrapper = rf.arrival_to_cells(terrain, (0, 0),
                                          'TerrainTable_MovCost_CommonT1Normal', 3, [(2, 0)])
        via_shared = pp.arrival_turn_to(terrain, [(0, 0)],
                                        'TerrainTable_MovCost_CommonT1Normal', 3, [(2, 0)])
        self.assertEqual(via_wrapper, via_shared)


class ReachedOnIsDerived(unittest.TestCase):
    """ch06 declares `reached_on:` per class. It is now derived and compared, because a hand-kept
    number that nothing reads is how "foot reaches either door on turn 6" survived as the
    chapter's load-bearing claim without ever being true under fire."""

    def test_every_declared_class_is_one_the_deriver_knows(self):
        chap = pp.load_chapter('ch06')
        for boat in chap['rescue_boats']:
            for role in (boat.get('reached_on') or {}):
                self.assertIn(role, pp.REACH_ROLES,
                              '%r is declared but has no movement profile' % role)

    def test_the_contested_walk_reproduces_the_declared_numbers(self):
        """`reached_on_contested:` is the row that describes what a player actually walks, so
        it is derived and pinned. Nothing may hand-edit it away from the map."""
        chap = pp.load_chapter('ch06')
        terrain = pp.terrain_grid(chap)
        for boat in chap['rescue_boats']:
            got = pp.reached_on(chap, terrain, tuple(boat['door']), contested=True)
            for role, declared in (boat.get('reached_on_contested') or {}).items():
                self.assertEqual(declared, got[role],
                                 '%s %s: declared %s, derived %s'
                                 % (boat['id'], role, declared, got[role]))

    def test_a_contested_row_is_declared_for_every_boat(self):
        """The empty-map row alone is what let "foot reaches either door on turn 6" stand as
        the chapter's load-bearing claim while being false for every ground class."""
        for boat in pp.load_chapter('ch06')['rescue_boats']:
            self.assertIn('reached_on_contested', boat, boat['id'])

    def test_the_uncontested_walk_reproduces_the_declared_numbers(self):
        """The declared block was measured this way, so deriving it the same way must agree --
        that is what makes the CONTESTED number a finding rather than a tooling difference."""
        chap = pp.load_chapter('ch06')
        terrain = pp.terrain_grid(chap)
        for boat in chap['rescue_boats']:
            got = pp.reached_on(chap, terrain, tuple(boat['door']), contested=False)
            for role, declared in (boat.get('reached_on') or {}).items():
                self.assertEqual(declared, got[role],
                                 '%s %s: declared turn %s, derived %s'
                                 % (boat['id'], role, declared, got[role]))


class BehaviourColour(unittest.TestCase):
    """The legend must not promise a colour the render never draws.

    `ai_shape` replaced the approach-family vocabulary and `BEHAVIOUR_COLOUR` kept the old
    keys, so every one of ch06's 27 markers fell through to the default grey while the legend
    still advertised red/orange/yellow/purple. Nothing caught it because nothing tested the
    key set -- and a placement picture that mis-states behaviour is exactly the picture ch06's
    clock was designed against.
    """

    def test_every_shape_has_a_colour(self):
        import chapter_status as cs
        shapes = set()
        for action in cs.AI_ACTION:
            for approach in cs.AI_BEHAVIOUR:
                shape = cs.ai_shape((action, approach, 0, 0))
                if shape is not None:
                    shapes.add(shape)
        self.assertTrue(shapes, 'ai_shape named nothing -- the sweep is not reaching it')
        self.assertEqual(shapes - set(pp.BEHAVIOUR_COLOUR), set(),
                         'ai_shape returns a shape the render has no colour for')

    def test_no_colour_for_a_shape_that_does_not_exist(self):
        """The other direction: a stale key is a legend entry nothing can ever draw."""
        import chapter_status as cs
        shapes = {cs.ai_shape((a, b, 0, 0))
                  for a in cs.AI_ACTION for b in cs.AI_BEHAVIOUR}
        self.assertEqual(set(pp.BEHAVIOUR_COLOUR) - shapes, set(),
                         'BEHAVIOUR_COLOUR names a behaviour `ai_shape` never returns')

    def test_ch06_markers_all_resolve(self):
        """The regression itself: no ch06 unit renders as unclassified."""
        grey = sorted(u[3] for u in pp.placed_units(ch06())
                      if u[2] not in pp.BEHAVIOUR_COLOUR)
        self.assertEqual(grey, [], 'ch06 units with no derived shape: %r' % (grey,))


if __name__ == '__main__':
    unittest.main()
