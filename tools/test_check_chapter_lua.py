#!/usr/bin/env python3
"""Tests for check.py's chapter-Lua-chunk coordinate guard (#26).

A chapter chunk (`tools/playtest/chNN.lua`) restates coordinates the chapter YAML already
declares -- ch06.lua carries both hulls' pocket cells and both pocket DOORS, and ch06clock's
whole verdict is that a melee attacker stands on one of those doors. A stale door there does
not crash: it produces a scenario that runs, reads the wrong cell, and FAILs blaming the
engine. That is the same failure `check_declared_cases` exists to stop for `visit` steps.

The pure half is tested against synthetic inputs, both directions -- clean input produces
nothing, drifted input produces the finding -- because a guard that cannot fail is not one.

Run: python3 tools/test_check_chapter_lua.py
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import check                                            # noqa: E402

DOC = {
    'rescue_boats': [{'id': 'boat-east', 'tile': [17, 12], 'door': [17, 13]}],
    'enemy_units': [{'id': 'ice-crab', 'positions': [[7, 20]]}],
}
CLEAN = '''return {
    BOATS = {
        { id = "boat-east", pid = 0xbb, x = 17, y = 12, doorX = 17, doorY = 13, sinks_on = 7 },
    },
    PURSUERS = {
        { id = "ice-crab", boat = "boat-west", x = 7, y = 20, range = 1 },
    },
}
'''


def run(text=CLEAN, doc=None):
    return check._chapter_lua_fact_violations('tools/playtest/ch06.lua', text,
                                              'ch06.yaml', doc if doc is not None else DOC)


class TestChapterLuaFacts(unittest.TestCase):
    def test_matching_coordinates_are_clean(self):
        self.assertEqual(run(), [])

    def test_a_drifted_tile_is_reported(self):
        found = run(CLEAN.replace('x = 17, y = 12', 'x = 17, y = 11'))
        self.assertEqual(len(found), 1, found)
        self.assertIn('boat-east', found[0])
        self.assertIn('(17,11)', found[0])

    def test_a_drifted_door_is_reported(self):
        # The one that matters most: ch06clock's verdict is a door cell, so a stale door
        # reads as a broken pocket rather than as a stale constant.
        found = run(CLEAN.replace('doorX = 17, doorY = 13', 'doorX = 16, doorY = 13'))
        self.assertEqual(len(found), 1, found)
        self.assertIn('door', found[0])

    def test_a_drifted_enemy_start_tile_is_reported(self):
        # A pursuer is FOUND by its start tile (every ch06 enemy shares one generic pid), so
        # this coordinate is not decoration -- a stale one finds no unit and fails at boot.
        found = run(CLEAN.replace('x = 7, y = 20', 'x = 7, y = 19'))
        self.assertEqual(len(found), 1, found)
        self.assertIn('ice-crab', found[0])

    def test_an_id_the_chapter_does_not_declare_is_reported(self):
        found = run(CLEAN.replace('"ice-crab"', '"ice-krab"'))
        self.assertEqual(len(found), 1, found)
        self.assertIn('ice-krab', found[0])

    def test_every_drifted_row_is_reported_not_just_the_first(self):
        bad = CLEAN.replace('x = 17, y = 12', 'x = 0, y = 0').replace('x = 7, y = 20',
                                                                     'x = 1, y = 1')
        self.assertEqual(len(run(bad)), 2, run(bad))

    def test_a_row_without_an_id_is_out_of_scope_rather_than_a_crash(self):
        # ch05.lua's reliquaries are keyed by `name`, not `id`, and its chapter YAML calls
        # them `reliquary-north`. Matching those would mean renaming a shipped chapter's
        # constants, so they are deliberately not in scope -- and must not raise here.
        self.assertEqual(run('return { X = { { name = "north", x = 5, y = 1 } } }'), [])

    def test_a_chunk_with_no_coordinate_rows_is_clean(self):
        self.assertEqual(run('return { MSG = { OPENING = 0x9F6 } }'), [])

    def test_a_missing_chapter_doc_is_reported_rather_than_passing_vacuously(self):
        found = run(doc=None if False else {})
        self.assertTrue(found)
        self.assertIn('boat-east', found[0])


if __name__ == '__main__':
    unittest.main()
