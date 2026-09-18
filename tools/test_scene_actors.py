#!/usr/bin/env python3
"""Tests that a scene LOADs every PLAYER CHARACTER it stages (#337).

`docs/decisions.md` → *"Permadeath is a combat rule, not a narrative one"* puts all eight PCs
in every cutscene whether or not they are alive. That policy rests on one invariant nothing
enforced:

    A cutscene LOADs its actors; it never assumes they are standing on the map.

`LoadUnit` performs no death check, so loading a dead character is fine. The unit lookup
returns NULL for an ABSENT one, and what happens next depends on the command -- the decomp is
explicit, and the two outcomes are not the same bug:

    CUMO_CHAR, and the TARGET of MOVEONTO/MOVE_NEXTTO, return EVC_ERROR. `EventEngine_Main`
    (event.c:106-112) breaks on EVC_ERROR WITHOUT advancing `pEventCurrent`, so the same
    command re-runs forever and the chapter HANGS.

    A move command's own MOVER returns EVC_ADVANCE_CONTINUE (eventscr.c:2960), so the script
    advances and the walk silently never happens -- the scene plays, wrong, around an actor
    who is not there.

Either way it fires only once a player has actually lost that character before that beat.

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
        self.assertEqual([bc.character_pid('CHARACTER_EIRIKA')], list(staged))

    def test_a_MOVE_speed_is_not_mistaken_for_a_character(self):
        self.assertNotIn(0x10, bc.scene_staged_pids('    MOVE(0x10, 0xce, 3, 4)\n'))

    def test_CUMO_CHAR_and_MOVE_DEFINED_read_their_first(self):
        self.assertIn(0xce, bc.scene_staged_pids('    CUMO_CHAR(0xce)\n'))
        self.assertIn(0xce, bc.scene_staged_pids('    MOVE_DEFINED(0xce)\n'))

    def test_MOVE_does_not_swallow_MOVE_DEFINED(self):
        """`MOVE` is a prefix of five other commands, each with a different pid position."""
        staged = bc.scene_staged_pids('    MOVE_DEFINED(CHARACTER_EIRIKA)\n')
        self.assertEqual([bc.character_pid('CHARACTER_EIRIKA')], list(staged))

    def test_MOVEONTO_stages_BOTH_its_mover_and_its_target(self):
        staged = bc.scene_staged_pids('    MOVEONTO(0x10, 0xce, CHARACTER_EIRIKA)\n')
        self.assertIn(0xce, staged)
        self.assertIn(bc.character_pid('CHARACTER_EIRIKA'), staged)

    def test_the_two_failure_modes_are_told_apart(self):
        """EVC_ERROR hangs the engine; EVC_ADVANCE_CONTINUE just skips the walk.

        `EventEngine_Main` (event.c:106-112) breaks on EVC_ERROR WITHOUT advancing
        `pEventCurrent`, so the command re-runs forever -- that is the hang. A move whose
        MOVER is NULL returns EVC_ADVANCE_CONTINUE (eventscr.c:2960) and the script carries
        on, so calling that a soft-lock would overstate it."""
        hangs = bc.scene_staged_pids('    CUMO_CHAR(0xce)\n')
        self.assertEqual('hangs', hangs[0xce])
        noop = bc.scene_staged_pids('    MOVE(0x10, 0xce, 1, 2)\n')
        self.assertNotEqual('hangs', noop[0xce])

    def test_a_pid_staged_twice_keeps_the_WORSE_outcome(self):
        both = bc.scene_staged_pids('    MOVE(0x10, 0xce, 1, 2)\n    CUMO_CHAR(0xce)\n')
        self.assertEqual('hangs', both[0xce])


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

    def test_a_campaign_owned_scene_is_checked_too(self):
        """`declare_event_script` APPENDS its scene; it never touches _replace_brace_block.

        That is the path ch05's talks, villages and arena take, and the one ch06's Messie
        scene will -- so hooking only the brace writer would have left the motivating case
        of this whole guard unchecked."""
        import inspect
        src = inspect.getsource(bc.declare_event_script)
        self.assertIn('SCENE_VALIDATORS', src)

    def test_an_MS_scene_name_is_not_filtered_out(self):
        """Campaign scenes are named MS_*, not EventScr_*, by `_assert_ms_symbol`."""
        with self.assertRaises(SystemExit):
            bc.assert_scene_loads_its_actors(
                '{\n    CUMO_CHAR(CHARACTER_EIRIKA)\n}', 'MS_Ch06Messie')


class TheLOADHalf(unittest.TestCase):
    """The half that decides whether an accusation is TRUE -- and had no coverage at all."""

    def test_LOAD3_counts_as_loading(self):
        """LOAD3 and LOAD4 exist (EAstdlib.h:112-113) and vanilla uses LOAD3 nine times.

        Matching only LOAD[12] fails the build on a scene that correctly loads its actor."""
        body = '{\n    LOAD3(0x1, %s)\n    CUMO_CHAR(CHARACTER_EIRIKA)\n}'
        sym = self._udef_carrying('CHARACTER_EIRIKA')
        bc.assert_scene_loads_its_actors(body % sym, 'EventScr_Test')

    def _udef_carrying(self, token):
        """A real UnitDefinition symbol that carries `token`, found in the live tree."""
        pid = bc.character_pid(token)
        import re as _re
        for text in bc._udef_sources():
            for m in _re.finditer(r'(UnitDef_\w+|MS_\w+)\[\]', text):
                if pid in bc._unit_def_pids(m.group(1)):
                    return m.group(1)
        self.skipTest('no UnitDefinition in this tree carries %s' % token)

    def test_a_campaign_owned_unit_table_resolves(self):
        """`_unit_def_pids` must search the per-chapter `ch*-eventudefs.h` headers too.

        Searching only `events_udefs.c` returns an EMPTY set for our own tables -- and an
        empty set reads as "this scene loaded nobody", turning a correct LOAD into a false
        accusation on exactly the scenes we write."""
        import re as _re
        ours = None
        for text in bc._udef_sources():
            for m in _re.finditer(r'\b(UnitDef_Event_\w+)\[\]', text):
                if bc._unit_def_pids(m.group(1)):
                    ours = m.group(1)
                    break
            if ours:
                break
        if ours is None:
            self.skipTest('no campaign-owned UnitDefinition in this tree')
        self.assertTrue(bc._unit_def_pids(ours),
                        '%s resolved to nobody, so a LOAD naming it reads as missing' % ours)


if __name__ == '__main__':
    unittest.main(verbosity=2)
