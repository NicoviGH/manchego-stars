#!/usr/bin/env python3
"""Tests that a scene LOADs every PLAYER CHARACTER it stages (#337).

`docs/decisions.md` → *"Permadeath is a combat rule, not a narrative one"* puts all eight PCs
in every cutscene whether or not they are alive. That policy rests on one invariant nothing
enforced:

    A cutscene LOADs its actors; it never assumes they are standing on the map.

`LoadUnit` performs no death check, so loading a dead character is fine. `GetUnitFromCharId`
returns NULL for an ABSENT one, and `CUMO_CHAR` / `MOVE` / `MOVE_DEFINED` resolve through it --
so a beat naming a PC the scene never loaded is the same never-returns soft-lock
`assert_scripted_move_reachable` was written for, and it fires only once a player has actually
lost that character before that beat.

WHY ONLY THE PCs, measured rather than assumed. Applying "every staged character must be
LOADed" to the emitted scripts flags 73 sites in UNTOUCHED VANILLA, which obviously works:
vanilla can stage Eirika without loading her because Eirika is always there. We have no such
character -- the player picks their own lord and any PC can be dead or simply not picked at
PREP -- so the guarantee vanilla relies on is exactly the one that does not transfer.

Everything else a scene stages is guaranteed by construction: ch05's `CUMO_CHAR(0xb8)` is
Ravisin, the boss, on the map from the chapter's own table since turn 1. Flagging her would be
the gate crying wolf on the first chapter it looked at.

The PC set is `PORTRAIT_MAP`: a PC rides its portrait slot, so its on-map pid is
`CHARACTER_<slot>` -- braulo is `CHARACTER_EIRIKA`, pinky is `CHARACTER_NEIMI`.

Run: python3 tools/test_scene_actors.py
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import build_campaign as bc


class TheStagedPidIsFoundWhereTheMacroPUTSIt(unittest.TestCase):
    """`MOVE(speed, pid, x, y)` -- the pid is the SECOND argument (EAstdlib.h:117).

    Reading it as the first flags 378 sites campaign-wide, because vanilla's speeds are
    `0x10`/`0x0` and every one of them parses as a character id.
    """

    def test_MOVE_reads_its_pid_from_the_second_argument(self):
        staged = bc.scene_staged_pids('    MOVE(0x10, CHARACTER_EIRIKA, 3, 4)\n')
        self.assertEqual({bc.character_pid('CHARACTER_EIRIKA')}, staged)

    def test_a_MOVE_speed_is_not_mistaken_for_a_character(self):
        self.assertNotIn(0x10, bc.scene_staged_pids('    MOVE(0x10, 0xce, 3, 4)\n'))

    def test_CUMO_CHAR_and_MOVE_DEFINED_read_their_first(self):
        self.assertEqual({0xce}, bc.scene_staged_pids('    CUMO_CHAR(0xce)\n'))
        self.assertEqual({0xce}, bc.scene_staged_pids('    MOVE_DEFINED(0xce)\n'))


class ASceneMustLoadThePCsItStages(unittest.TestCase):

    BRAULO = 'CHARACTER_EIRIKA'          # braulo rides the Eirika slot (PORTRAIT_MAP)

    def test_a_staged_PC_with_no_LOAD_is_refused(self):
        with self.assertRaises(SystemExit) as caught:
            bc.assert_scene_loads_its_actors(
                '{\n    CUMO_CHAR(%s)\n    ENUN\n}' % self.BRAULO, 'EventScr_Test')
        self.assertIn('braulo', str(caught.exception))

    def test_the_error_names_the_scene_and_what_to_do(self):
        with self.assertRaises(SystemExit) as caught:
            bc.assert_scene_loads_its_actors(
                '{\n    MOVE(0x10, %s, 3, 4)\n}' % self.BRAULO, 'EventScr_Messie')
        message = str(caught.exception)
        self.assertIn('EventScr_Messie', message)
        self.assertIn('LOAD', message)

    def test_a_staged_PC_the_scene_LOADS_is_fine(self):
        bc.assert_scene_loads_its_actors(
            '{\n    LOAD1(0x1, UnitDef_TestParty)\n    ENUN\n    CUMO_CHAR(%s)\n}' % self.BRAULO,
            'EventScr_Test', loaded_pids={bc.character_pid(self.BRAULO)})

    def test_a_boss_the_chapter_owns_is_NOT_flagged(self):
        """ch05's Ravisin (0xb8) is on the map from turn 1 by the chapter's own table.

        She is the reason this guard is scoped to the PCs: she is staged without a LOAD in
        her own scene, she is not a soft-lock, and flagging her would be the gate crying wolf
        on the first real chapter it read."""
        bc.assert_scene_loads_its_actors('{\n    CUMO_CHAR(0xb8)\n}', 'EventScr_089F2B74')

    def test_a_generic_pid_is_not_flagged(self):
        bc.assert_scene_loads_its_actors('{\n    CUMO_CHAR(0xce)\n}', 'EventScr_Moose')


class TheGuardRidesTheWriteItself(unittest.TestCase):
    """Wired at the choke point, so a future scene cannot be written without it."""

    def test_writing_a_scene_that_stages_an_unloaded_PC_fails_the_build(self):
        from inject import decomp
        text = 'CONST_DATA EventListScr EventScr_New[] = {\n    ENDA\n};\n'
        with self.assertRaises(SystemExit):
            decomp._replace_brace_block(
                text, 'EventScr_New[] =',
                '{\n    CUMO_CHAR(CHARACTER_EIRIKA)\n    ENDA\n}', 'test.h')

    def test_a_non_scene_block_is_not_inspected(self):
        """UnitDefs and tables go through the same writer and are not scenes."""
        from inject import decomp
        text = 'CONST_DATA struct UnitDefinition UnitDef_X[] = {\n 0 \n};\n'
        out = decomp._replace_brace_block(text, 'UnitDef_X[] =',
                                          '{\n    CUMO_CHAR(CHARACTER_EIRIKA)\n}', 'test.h')
        self.assertIn('CUMO_CHAR', out)

    def test_the_live_build_passes_its_own_guard(self):
        """Every scene the injectors write today, checked as they are written."""
        self.assertTrue(callable(bc.assert_scene_loads_its_actors))


if __name__ == '__main__':
    unittest.main(verbosity=2)
