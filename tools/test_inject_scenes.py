#!/usr/bin/env python3
"""Tests for tools/inject/scenes.py.

Run:  python3 tools/test_inject_scenes.py
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import build_campaign as bc
import inject.scenes


class BattleQuotePair(unittest.TestCase):
    """gBattleTalkList entries come in TWOS, and one of the two is easy to forget.

    `CallBattleQuoteEventsIfAny` (eventinfo.c) is handed (attacker, defender) and tries
    (A,B), (A,0), (0,B) in that order, so a boss line that should play "whoever swung
    first" needs BOTH a row keyed on the boss as defender and a row keyed on the boss as
    attacker. Vanilla ships exactly that pair for every boss it gives a taunt (O'Neill,
    Breguet, Saar...), and a single row plays on one side of the engagement only.
    """

    def test_the_pair_covers_both_sides_of_the_engagement(self):
        self.assertTrue(hasattr(inject.scenes, 'battle_quote_pair'),
                        'the two-row boss-taunt idiom needs one owner, not a copy per chapter')
        rows = inject.scenes.battle_quote_pair('0xb8', 'CHAPTER_L_6', 0x9F2, 'a boss taunt')
        self.assertEqual(2, rows.count('.pidA'))
        # The player-engages row names the boss as pidB behind the leader sentinel; the
        # boss-engages row names it as pidA and leaves pidB out entirely (a zero pidB is
        # what makes the lookup match on pidA alone).
        player_row, boss_row = rows.split('    },')[:2]
        self.assertIn('.pidA     = CHAR_EVT_PLAYER_LEADER,', player_row)
        self.assertIn('.pidB     = 0xb8,', player_row)
        self.assertIn('.pidA     = 0xb8,', boss_row)
        self.assertNotIn('.pidB', boss_row)
        self.assertEqual(2, rows.count('.chapter = CHAPTER_L_6,'))
        self.assertEqual(2, rows.count('.flag    = EVFLAG_BATTLE_QUOTES,'))
        self.assertEqual(2, rows.count('.msg     = 0x9F2,'))

    def test_the_shared_flag_is_what_makes_it_play_once(self):
        """Both rows carry the SAME flag on purpose: GetBattleQuoteEntry skips any entry
        whose flag is already set, so the row that did not fire is retired by the row that
        did. Two different flags would let the taunt play twice, once per side."""
        rows = inject.scenes.battle_quote_pair('0xb8', 'CHAPTER_L_6', 0x9F2, 'a boss taunt')
        flags = {line.strip() for line in rows.split('\n') if '.flag' in line}
        self.assertEqual(1, len(flags))


class SharedEventShapes(unittest.TestCase):
    """The event-script shapes every chapter calls instead of copying (#479, ADR 0340)."""

    def test_a_second_backdrop_rearms_the_load_mode_and_plays_its_cue_before_the_fade(self):
        first = inject.scenes.backdrop('BG_A', 'the town', card=(0x9A0, 'Bremen'))
        self.assertEqual(first, '    REMOVEPORTRAITS\n    BACG(BG_A) /* the town */\n'
                                '    FADU(16)\n'
                                '    BROWNBOXTEXT(0x9A0, 8, 8) /* "Bremen" location card */\n')
        second = inject.scenes.backdrop('BG_B', 'the hall', rearm=True, cue='    MUSC(X)\n')
        self.assertTrue(second.startswith('    REMOVEPORTRAITS /* re-arm BACG BG-load mode'))
        self.assertLess(second.index('BACG(BG_B)'), second.index('MUSC(X)'))
        self.assertLess(second.index('MUSC(X)'), second.index('FADU(16)'))

    def test_the_exists_branch_asks_the_army_not_the_field(self):
        out = inject.scenes.branch_on_check_exists('CHARACTER_X', '    A\n', '    B\n', 4)
        self.assertTrue(out.startswith('    CHECK_EXISTS(CHARACTER_X)\n    BEQ(0x4,'))
        self.assertIn('LABEL(0x5)', out)

    def test_alive_flags_branch_past_their_own_enut(self):
        out = inject.scenes.record_alive_flags(
            [('a', '0x1', '0xFC', '0x3'), ('b', '0x2', '0xFD', '0x4')], 'lived')
        for pid, flag, label in (('0x1', '0xFC', '0x3'), ('0x2', '0xFD', '0x4')):
            self.assertLess(out.index('CHECK_ALIVE(%s)' % pid), out.index('ENUT(%s)' % flag))
            self.assertLess(out.index('BEQ(%s,' % label), out.index('ENUT(%s)' % flag))
            self.assertLess(out.index('ENUT(%s)' % flag), out.index('LABEL(%s)' % label))

    def test_a_debug_boot_without_the_chapter_seed_is_refused(self):
        with self.assertRaises(SystemExit):
            inject.scenes.debug_boot_script('--chNN-ending', 7, '', 'map', 'body\n')
        out = inject.scenes.debug_boot_script(
            '--chNN-ending', 7, '    SEED\n', 'the map', '    BODY\n',
            music='    MUSC(M)\n', before_seed='    BEFORE\n')
        order = [out.index(x) for x in ('MUSC(M)', 'LOMA(0x7) /* the map */', 'BEFORE', 'SEED',
                                        'BODY', 'ENDA')]
        self.assertEqual(order, sorted(order))

    def test_the_party_frame_defaults_to_the_lord_and_refuses_an_empty_tile(self):
        chap = {'deployment': {'deploy_slots': [[3, 4], [5, 6]]}}
        self.assertEqual((3, 4), inject.scenes.party_camera_tile(chap))
        self.assertEqual((5, 6), inject.scenes.party_camera_tile(chap, (5, 6)))
        with self.assertRaises(SystemExit):
            inject.scenes.party_camera_tile(chap, (9, 9))

    def test_the_gather_refuses_two_on_a_tile_and_a_spare_too_close(self):
        loads = lambda n: 'MS_T%02d' % n  # noqa: E731
        members = {'marty': (1, 1), 'pinky': (2, 1)}
        with self.assertRaises(SystemExit):
            inject.scenes.gather_cast({'marty': (1, 1), 'pinky': (1, 1)}, [(1, 1)], (20, 20),
                                      loads, 0x40, 6, 'test')
        with self.assertRaises(SystemExit):
            inject.scenes.gather_cast(members, [(1, 1), (2, 1)], (3, 1), loads, 0x40, 6, 'test')
        out = inject.scenes.gather_cast(members, [(1, 1), (2, 1)], (20, 20), loads, 0x40, 6,
                                        'test', scatter='    CLEE\n')
        self.assertTrue(out.startswith('    FADI(16)'))
        self.assertLess(out.index('CLEE'), out.index('MOVE_CLOSEST'))
        # every member is LOADed only if the army has them, never conjured
        self.assertEqual(2, out.count('CHECK_EXISTS('))
        self.assertLess(out.rindex('MOVE_CLOSEST'), out.index('LOAD1(0x1, MS_T00)'))
        self.assertTrue(out.endswith('    FADU(16)\n'))


if __name__ == '__main__':
    unittest.main()
