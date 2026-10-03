#!/usr/bin/env python3
"""Tests for tools/inject/chapters/ch01.py.

Run:  python3 tools/test_inject_ch01.py
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import inject.cast
import inject.chapters.ch01
import inject.message_alloc


class LordFloorRows(unittest.TestCase):
    """The per-lord survivability-floor table (#45 3b) the build emits as gLordFloorDeltas[]
    and the engine applies once at chapter start (#45 3c). One (hp, def, res) row per lord
    candidate, in the menu order the C table is indexed by. Oracle: difficulty --lord-floor."""

    CAMPAIGN = 'rime-of-the-frostmaiden'

    def test_ch1_deltas_match_the_floor_solver(self):
        # vs Ch1 enemies @target 3.5: the shamans are the glass picks (+7HP/+4Def); the armor
        # tanks (braulo/wolfram) already clear the floor, so they take nothing.
        rows = {uid: (hp, df, res) for uid, hp, df, res in inject.chapters.ch01.lord_floor_rows(
            self.CAMPAIGN, ['marty', 'meesmickle', 'pinky', 'braulo', 'wolfram'])}
        self.assertEqual(rows['marty'], (7, 4, 0))
        self.assertEqual(rows['meesmickle'], (7, 4, 0))
        self.assertEqual(rows['pinky'], (0, 4, 0))
        self.assertEqual(rows['braulo'], (0, 0, 0))
        self.assertEqual(rows['wolfram'], (0, 0, 0))

    def test_rows_preserve_candidate_order(self):
        # gLordFloorDeltas[] is indexed parallel to gLordSelectCandidates[], so the row order
        # MUST match the menu order it is handed -- a reorder would mis-assign every floor.
        order = ['wolfram', 'marty', 'pinky']
        self.assertEqual([uid for uid, *_ in inject.chapters.ch01.lord_floor_rows(self.CAMPAIGN, order)], order)


class FoundingExpTable(unittest.TestCase):
    """gFoundingExpGrants[] (#430 step 4): one { pid, exp } row per founding PC, the numbers
    exp_curve banks, 0-terminated for FoundingExp_ApplyOnce's loop."""
    CAMPAIGN = 'rime-of-the-frostmaiden'

    def test_every_founding_pc_gets_the_models_grant(self):
        import exp_curve
        grant = exp_curve.founding_grant(self.CAMPAIGN)
        cast = [(uid, 'SLOT%d' % i) for i, uid in enumerate(sorted(grant))] + [('baxby', 'X')]
        text = inject.chapters.ch01.founding_exp_table(self.CAMPAIGN, cast)
        for i, uid in enumerate(sorted(grant)):
            self.assertIn('CHARACTER_SLOT%d, %d, /* %s */' % (i, grant[uid], uid), text)
        self.assertNotIn('baxby', text)              # a recruit is not founding
        self.assertTrue(text.rstrip().endswith('0,\n};'))

    def test_the_lordfloor_scenario_expects_the_models_grant(self):
        import exp_curve, re
        lua = open(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                'playtest', 'harness.lua'), encoding='utf-8').read()
        self.assertEqual(int(re.search(r'local FOUNDING_EXP = (\d+)', lua).group(1)),
                         exp_curve.founding_grant(self.CAMPAIGN)['marty'])


class LordSelectPitches(unittest.TestCase):
    """The qualitative candidate blurbs (#46) the build emits as sLordSelectPitchMsg[],
    drawn by LordSelect_DrawCard as the cursor lands on each candidate. One (uid, pitch)
    per candidate, in the menu order the C table is indexed by -- PARALLEL to
    gLordSelectCandidates[]. The pitch is hand-authored YAML (lord_pitch:), never derived
    from stats; the build HARD-FAILS if any candidate lacks one (no silent gaps)."""

    CAMPAIGN = 'rime-of-the-frostmaiden'

    def test_returns_each_candidates_authored_pitch_in_order(self):
        rows = inject.chapters.ch01.lord_select_pitches(self.CAMPAIGN, ['braulo', 'pinky', 'wolfram'])
        self.assertEqual([uid for uid, _ in rows], ['braulo', 'pinky', 'wolfram'])
        self.assertEqual(rows[0][1],
                         inject.cast.load_unit(self.CAMPAIGN, 'braulo')['lord_pitch'])
        self.assertEqual(rows[1][1],
                         inject.cast.load_unit(self.CAMPAIGN, 'pinky')['lord_pitch'])

    def test_preserves_candidate_order(self):
        # sLordSelectPitchMsg[] is indexed parallel to gLordSelectCandidates[]: a reorder
        # would show the wrong blurb under every cursor position.
        order = ['wolfram', 'marty', 'pinky']
        self.assertEqual([uid for uid, _ in inject.chapters.ch01.lord_select_pitches(self.CAMPAIGN, order)],
                         order)

    def test_hard_fails_when_a_candidate_lacks_a_pitch(self):
        # Baxby (an NPC) carries no lord_pitch -> the build must refuse rather than ship a
        # blank card (the "no silent gaps" lock, Nicolas 2026-06-20).
        with self.assertRaises(SystemExit):
            inject.chapters.ch01.lord_select_pitches(self.CAMPAIGN, ['braulo', 'baxby'])


class TerrainHealBeat(unittest.TestCase):
    """#21 / #135 finding 8: the playtester read the forts' healing as a glitch. Turn 1 now
    explains it in dialogue on every difficulty, shows the tiles, and unlocks the Guide."""

    def setUp(self):
        from inject.hosting import _load_chapter_yaml
        chap = _load_chapter_yaml('rime-of-the-frostmaiden', inject.chapters.ch01.CH01_CHAPTER_YAML)
        self.beat = next(e for e in chap['events']
                         if e.get('trigger') == 'turn_start' and e.get('turn') == 1)
        self.chief = next(e for e in chap['enemy_units'] if e.get('id') == 'goblin-chief')
        self.script = inject.chapters.ch01.ch01_turn1_taunt_script(self.beat)

    def test_the_line_follows_the_taunt_and_the_guide_unlocks_last(self):
        s = self.script
        taunt = s.index('TEXTSHOW(0x%X)' % inject.chapters.ch01.CH01_TAUNT_MSG)
        line = s.index('TEXTSHOW(0x%X)' % inject.chapters.ch01.CH01_TERRAIN_HEAL_MSG)
        guide = s.index('ENUT(0xCE)')   # vanilla Ch1's flag for "Fortresses & Castle Gates"
        self.assertLess(taunt, line)
        self.assertLess(line, guide)

    def test_no_tutorial_mode_gate(self):
        # ADR 0104 keeps tutorial mode off Normal; a gate here would hide the fix from the
        # very player who reported it.
        self.assertNotIn('CHECK_TUTORIAL', self.script)
        self.assertNotIn('TUTORIALTEXTBOXSTART', self.script)

    def test_the_first_flash_is_izobais_gate_and_every_tile_flashes(self):
        tiles = self.beat['flash_tiles']
        self.assertEqual(list(tiles[0]), list(self.chief['position']))
        for x, y in tiles:
            self.assertIn('CURSOR_FLASHING(%d, %d)' % (x, y), self.script)

    def test_the_message_is_an_appended_id(self):
        self.assertGreaterEqual(inject.chapters.ch01.CH01_TERRAIN_HEAL_MSG,
                                inject.message_alloc.VANILLA_MESSAGE_COUNT)


class TerminatorParity(unittest.TestCase):
    """_term_pad guards FE8's Huffman terminator: the utf8 packer pairs printable bytes
    two-at-a-time, so a printable run with an ODD length swallows the byte after it. When
    that byte is [X] (0x00) the decoder runs into the next message. The parity that matters
    is the FINAL run (printables after the last control code), NOT the whole message
    (decisions.md, refined 2026-06-25 for the multi-line lord-select pitches, #46)."""

    def test_single_run_even_is_left_alone(self):
        self.assertEqual(inject.chapters.ch01._term_pad('Seth[X]'), 'Seth[X]')        # 4 even -> no pad

    def test_single_run_odd_is_padded(self):
        self.assertEqual(inject.chapters.ch01._term_pad('Franz[X]'), 'Franz[.][X]')   # 5 odd -> pad

    def test_multiline_even_total_but_odd_final_run_is_padded(self):
        # The bug class: earlier [LF] runs are odd, so the TOTAL is even (old code skipped
        # the pad) yet the FINAL run is odd and eats [X]. Mirrors Pinky's 16+19+13 pitch.
        self.assertEqual(inject.chapters.ch01._term_pad('a[LF]cde[X]'), 'a[LF]cde[.][X]')   # total 4 even, final 3 odd
        self.assertEqual(inject.chapters.ch01._term_pad('Flying[LF]over[LF]bows[X]'),       # 6+4+4=14 even, final 4 even
                         'Flying[LF]over[LF]bows[X]')                     # -> no pad (final even)

    def test_multiline_odd_total_but_even_final_run_is_not_padded(self):
        # The inverse: odd total would have tripped the old whole-message rule, but the
        # final run is even, so [X] is safe and no pad is wanted.
        self.assertEqual(inject.chapters.ch01._term_pad('abc[LF]de[X]'), 'abc[LF]de[X]')    # total 5 odd, final 2 even

    def test_control_codes_do_not_count_toward_the_final_run(self):
        # The final run is the printables after the LAST control tag; an [A]/[LF] resets it.
        self.assertEqual(inject.chapters.ch01._term_pad('hello[A][X]'), 'hello[A][X]')      # final run empty -> no pad

    def test_no_terminator_is_a_noop(self):
        self.assertEqual(inject.chapters.ch01._term_pad('odd'), 'odd')


if __name__ == '__main__':
    unittest.main()
