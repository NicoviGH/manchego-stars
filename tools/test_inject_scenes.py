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


if __name__ == '__main__':
    unittest.main()
