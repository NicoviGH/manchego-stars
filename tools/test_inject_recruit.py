#!/usr/bin/env python3
"""Tests for tools/inject/recruit.py.

Run:  python3 tools/test_inject_recruit.py
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import inject.recruit


class SharedTalkRecruitWiring(unittest.TestCase):
    """The faction-parameterized on-map talk-recruit assembly reused by ch03 (green Trex),
    ch04 (red Lupin), and ch05 (green Basil + red Sahnar). ONE flow: a CHAR-per-recruiter
    list -> a shared talk script whose CUSA flips the target BLUE. A group parley splices a
    `pre_script` (its conversion sweep) in BEFORE the CUSA, so it rides the same recruit path."""

    def test_talk_script_splices_pre_script_before_cusa(self):
        s = inject.recruit.talk_recruit_script(0x9BA, 'CHARACTER_DUESSEL', pre_script='    DISA(0xb3)\n')
        self.assertGreater(s.index('DISA(0xb3)'), s.index('TEXTSHOW(0x9BA)'))  # after the talk line
        self.assertLess(s.index('DISA(0xb3)'), s.index('CUSA(CHARACTER_DUESSEL)'))  # before the join

    def test_talk_script_without_pre_script_is_backward_compatible(self):
        # ch03's green recruit passes no pre_script -- the script stays exactly as before.
        s = inject.recruit.talk_recruit_script(0x9A5, 'CHARACTER_RENNAC')
        self.assertNotIn('DISA', s)
        self.assertIn('CUSA(CHARACTER_RENNAC)', s)

    def test_wiring_bundles_the_char_list_and_the_talk_script(self):
        char_events, script = inject.recruit.talk_recruit_wiring(
            ['CHARACTER_SETH'], 'CHARACTER_DUESSEL', 'EVFLAG_TMP(9)',
            'EventScr_089F2340', 0x9BA, pre_script='    DISA(0xb3)\n')
        self.assertEqual(char_events.count('CHAR('), 1)
        self.assertIn('CHAR(EVFLAG_TMP(9), EventScr_089F2340, CHARACTER_SETH, '
                      'CHARACTER_DUESSEL)', char_events)
        self.assertTrue(char_events.rstrip().endswith('END_MAIN\n}'))
        self.assertIn('CUSA(CHARACTER_DUESSEL)', script)
        self.assertIn('DISA(0xb3)', script)


if __name__ == '__main__':
    unittest.main()
