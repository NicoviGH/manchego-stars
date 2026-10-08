#!/usr/bin/env python3
"""Tests for tools/inject/chapters/ch05.py.

Run:  python3 tools/test_inject_ch05.py
"""
import os
import re
import shutil
import sys
import tempfile
import unittest
from unittest import mock

from PIL import Image

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from inject.namespace import stubbed
import build_campaign as bc
import inject.backgrounds
import inject.cast
import inject.chapter_ids
import inject.chapters.ch04
import inject.chapters.ch05
import inject.decomp
import inject.event_scripts
import inject.hosting
import inject.hosts
import inject.maps
import inject.messages
import inject.recruit
import inject.scenes
import inject.terrain
import inject.text
import inject.units
import inject.villages
import inject.warm
import yaml_loader
import fe8_talk_font as font
from inject import source as injector  # the injector's source, every file of it (#389)

# Read the COMMITTED decomp, not the working tree -- the build overwrites donor portrait
# slots (Gilliam/Neimi/Moulder/Vanessa), so a working-tree read would be non-hermetic.
VANILLA = inject.decomp.vanilla_decomp_text('src/data_characters.c')


def _ch05_ending(chap):
    """`ch05_ending_script` with the two cast slots the injector resolves at build time.

    Basil and Sahnar reach it as CHARACTER_ symbols (`char_symbol(...)` off the classed cast),
    not as raw pids -- the ending asks the ROSTER about both, and a raw pid would only ever
    match if the unit happened to still be wearing it.
    """
    return inject.chapters.ch05.ch05_ending_script(chap, 'CHARACTER_ARTUR', 'CHARACTER_MARISA')


class Ch05EruptionWarning(unittest.TestCase):
    """The turn-2 race warning belongs to ch05's HOST block, not its vanilla-Ch5 twin.

    The YAML label ``vanilla 0x9C5`` describes scene anatomy. Literal 0x9C5 is ch04's
    status-objective string, so using it here silently overwrites another chapter while
    every text decoder remains green. The warning also has to precede Sahnar's LOAD: the
    final locked box is Ravisin deciding to use the blade under the stone.
    """
    CAMPAIGN = 'rime-of-the-frostmaiden'

    def _chap(self):
        return inject.hosting._load_chapter_yaml(self.CAMPAIGN, inject.chapter_ids.CH05_CHAPTER_YAML)

    def test_warning_owns_a_named_id_from_ch05s_real_host_block(self):
        self.assertTrue(hasattr(inject.chapter_ids, 'CH05_ERUPTION_MSG'),
                        'ch05 needs a named host-block id for the eruption warning')
        self.assertEqual(0x9E4, inject.chapter_ids.CH05_ERUPTION_MSG)
        self.assertTrue(0x9E4 <= inject.chapter_ids.CH05_ERUPTION_MSG <= 0x9F3)
        self.assertNotEqual(inject.chapter_ids.CH04_GOAL_STATUS_MSG, inject.chapter_ids.CH05_ERUPTION_MSG)
        self.assertIn(inject.chapter_ids.CH05_ERUPTION_MSG, inject.messages.HOSTED_CHAPTER_MESSAGE_IDS['ch05'])
        self.assertEqual('ch05', inject.messages.assert_message_ids_unique()[inject.chapter_ids.CH05_ERUPTION_MSG])

    def test_locked_four_boxes_emit_one_faced_ravisin_message(self):
        self.assertTrue(hasattr(inject.chapters.ch05, 'ch05_eruption_message'),
                        'the locked YAML beat needs a message emitter')
        event = next(e for e in self._chap()['events'] if e['trigger'] == 'eruption_turn')
        self.assertEqual(4, len(event['script']))
        self.assertEqual({'ravisin'}, {next(iter(box)) for box in event['script']})
        for box in event['script']:
            self.assertLessEqual(len(inject.text._wrap_fe_lines(next(iter(box.values())))), 2)

        body = inject.chapters.ch05.ch05_eruption_message(self._chap())
        self.assertIn('[LoadFace][FID_Riev]', body)
        self.assertEqual(4, body.count('[A]'))
        for box in event['script']:
            for word in next(iter(box.values())).replace("'", '').split()[:3]:
                self.assertIn(word, body)

    def test_turn_two_stages_the_arriving_dead_before_the_warning(self):
        self.assertTrue(hasattr(inject.chapters.ch05, 'ch05_wave_script'),
                        'the wave script needs a testable owner for its ordering')
        script = inject.chapters.ch05.ch05_wave_script(2, 'MS_Ch05WaveT2')
        self.assertEqual(1, script.count('TEXTSHOW(0x%X)' % inject.chapter_ids.CH05_ERUPTION_MSG))
        self.assertIn('CUMO_CHAR(%s)' % inject.chapter_ids.CH05_BOSS_PID, script)
        self.assertLess(script.index('LOAD1(0x1, MS_Ch05WaveT2)'),
                        script.index('CUMO_CHAR(%s)' % inject.chapter_ids.CH05_BOSS_PID))
        self.assertLess(script.index('CUMO_CHAR(%s)' % inject.chapter_ids.CH05_BOSS_PID),
                        script.index('TEXTSHOW(0x%X)' % inject.chapter_ids.CH05_ERUPTION_MSG))

    def test_the_eruption_no_longer_raises_sahnar(self):
        """She is summoned ON SCREEN by Ravisin in scene 3 and stands on the arena from turn 1
        (#25, 2026-08-14) -- vanilla's own shape, where Joshua LOADs after the prep CALL. The
        eruption keeps its six reinforcements; a LOAD of her table here would put a second
        Sahnar on the board."""
        for turn in (2, 6, 8):
            script = inject.chapters.ch05.ch05_wave_script(turn, 'MS_Ch05WaveT%d' % turn)
            self.assertNotIn(inject.chapters.ch05.CH05_SAHNAR_TABLE, script)

    def test_later_waves_do_not_repeat_the_turn_two_warning(self):
        self.assertTrue(hasattr(inject.chapters.ch05, 'ch05_wave_script'),
                        'the wave script needs a testable owner for its ordering')
        for turn in (6, 8):
            script = inject.chapters.ch05.ch05_wave_script(turn, 'MS_Ch05WaveT%d' % turn)
            self.assertNotIn('TEXTSHOW(', script)
            self.assertNotIn('CUMO_CHAR(', script)


class Ch05RavisinDeathQuote(unittest.TestCase):
    """Ravisin's locked death box speaks without changing the DefeatBoss flag path."""
    CAMPAIGN = 'rime-of-the-frostmaiden'

    def _chap(self):
        return inject.hosting._load_chapter_yaml(self.CAMPAIGN, inject.chapter_ids.CH05_CHAPTER_YAML)

    def _event(self):
        return next(e for e in self._chap()['events'] if e['trigger'] == 'boss_death')

    def test_death_quote_owns_the_next_named_id_in_ch05s_real_host_block(self):
        self.assertTrue(hasattr(inject.chapter_ids, 'CH05_RAVISIN_DEATH_MSG'),
                        'Ravisin needs a named host-block id for her death quote')
        self.assertEqual(0x9E5, inject.chapter_ids.CH05_RAVISIN_DEATH_MSG)
        self.assertTrue(0x9E4 <= inject.chapter_ids.CH05_RAVISIN_DEATH_MSG <= 0x9F3)
        self.assertIn(inject.chapter_ids.CH05_RAVISIN_DEATH_MSG, inject.messages.HOSTED_CHAPTER_MESSAGE_IDS['ch05'])
        self.assertEqual('ch05', inject.messages.assert_message_ids_unique()[inject.chapter_ids.CH05_RAVISIN_DEATH_MSG])

    def test_locked_one_box_emits_ravisins_live_face_from_the_event_yaml(self):
        event = self._event()
        self.assertEqual('vanilla 0x9C8', event['slot'])
        self.assertEqual([{'ravisin': 'Frostmaiden... the winter is yours...'}], event['script'])
        self.assertTrue(hasattr(inject.chapters.ch05, 'ch05_ravisin_death_message'),
                        'the locked YAML beat needs a message emitter')

        body = inject.chapters.ch05.ch05_ravisin_death_message(self._chap())
        flowed = body.replace('[LF]\n', ' ')
        self.assertIn('[LoadFace][FID_Riev]', body)
        self.assertEqual(1, body.count('[A]'))
        self.assertIn('Frostmaiden', flowed)
        self.assertIn('the winter is yours', flowed)
        self.assertNotIn('I gave you everything', flowed)

    def test_flagged_defeat_entry_shows_the_quote_and_preserves_the_win_flag(self):
        self.assertTrue(hasattr(inject.chapters.ch05, 'ch05_ravisin_defeat_quote'),
                        'ch05 needs a testable owner for Ravisin defeat-talk wiring')
        quote = inject.chapters.ch05.ch05_ravisin_defeat_quote()
        self.assertIn('.pid     = %s' % inject.chapter_ids.CH05_BOSS_PID, quote)
        self.assertIn('.chapter = %s' % inject.units.chapter_label_constant(inject.hosts.CH05_HOST_INDEX), quote)
        self.assertIn('.flag    = EVFLAG_DEFEAT_BOSS', quote)
        self.assertIn('.msg     = 0x%X' % inject.chapter_ids.CH05_RAVISIN_DEATH_MSG, quote)
        self.assertNotIn('.msg     = 0,', quote)


class Ch05RavisinBattleTaunt(unittest.TestCase):
    """Scene 12: Ravisin's one box when a player unit engages her (#25).

    This is the twin of vanilla Saar's MSG_9C7 with one word swapped (empire ->
    Frostmaiden). It was wired NOWHERE for months -- gBattleTalkList carried the
    prologue's rows and nothing for her -- so the locked line existed in the YAML and
    could not play. The mechanism is FE8's own, not a turn event: the quote fires on
    first engagement, from either side, and retires itself.
    """
    CAMPAIGN = 'rime-of-the-frostmaiden'

    def _chap(self):
        return inject.hosting._load_chapter_yaml(self.CAMPAIGN, inject.chapter_ids.CH05_CHAPTER_YAML)

    def _event(self):
        return next(e for e in self._chap()['events'] if e['trigger'] == 'boss_battle')

    def test_taunt_owns_its_own_named_id_in_ch05s_host_block(self):
        self.assertTrue(hasattr(inject.chapter_ids, 'CH05_RAVISIN_TAUNT_MSG'),
                        'Ravisin needs a named host-block id for her battle taunt')
        self.assertEqual(0x9F2, inject.chapter_ids.CH05_RAVISIN_TAUNT_MSG)
        self.assertIn(inject.chapter_ids.CH05_RAVISIN_TAUNT_MSG, inject.messages.HOSTED_CHAPTER_MESSAGE_IDS['ch05'])
        self.assertEqual('ch05', inject.messages.assert_message_ids_unique()[inject.chapter_ids.CH05_RAVISIN_TAUNT_MSG])
        self.assertNotEqual(0x9C7, inject.chapter_ids.CH05_RAVISIN_TAUNT_MSG,
                            "the YAML's `vanilla 0x9C7` label cites the scene we mine, and "
                            'ch04 writes that literal id')

    def test_locked_one_box_emits_ravisins_live_face_from_the_event_yaml(self):
        event = self._event()
        self.assertEqual('vanilla 0x9C7', event['slot'])
        self.assertEqual(
            [{'ravisin': "Enemy of the Frostmaiden! Death's too good for you!"}],
            event['script'])
        self.assertTrue(hasattr(inject.chapters.ch05, 'ch05_ravisin_taunt_message'),
                        'the locked YAML beat needs a message emitter')

        body = inject.chapters.ch05.ch05_ravisin_taunt_message(self._chap())
        flowed = body.replace('[LF]\n', ' ')
        self.assertIn('[LoadFace][FID_Riev]', body)
        self.assertEqual(1, body.count('[A]'))
        self.assertIn('Enemy of the Frostmaiden', flowed)
        self.assertIn("Death's too good for you", flowed)
        # The whole point of the swap: her allegiance, never Grado's.
        self.assertNotIn('empire', flowed)

    def test_the_taunt_takes_vanillas_own_seat_for_this_slot(self):
        """Vanilla's MSG_9C7 and MSG_9C8 both put Saar on [OpenMidLeft], and ch05's
        eruption warning already seats Ravisin there. A battle quote draws over the
        combat screen with nobody opposite her, so the mined seat is the one to keep."""
        self.assertIn('[OpenMidLeft]', inject.chapters.ch05.ch05_ravisin_taunt_message(self._chap()))

    def test_engaging_ravisin_is_what_plays_it(self):
        self.assertTrue(hasattr(inject.chapters.ch05, 'ch05_ravisin_battle_quote'),
                        'ch05 needs a testable owner for Ravisin battle-talk wiring')
        rows = inject.chapters.ch05.ch05_ravisin_battle_quote()
        self.assertEqual(2, rows.count('.pidA'))
        self.assertIn('.pidB     = %s,' % inject.chapter_ids.CH05_BOSS_PID, rows)
        self.assertIn('.pidA     = %s,' % inject.chapter_ids.CH05_BOSS_PID, rows)
        self.assertEqual(2, rows.count('.chapter = %s,'
                                       % inject.units.chapter_label_constant(inject.hosts.CH05_HOST_INDEX)))
        self.assertEqual(2, rows.count('.msg     = 0x%X,' % inject.chapter_ids.CH05_RAVISIN_TAUNT_MSG))
        # EVFLAG_DEFEAT_BOSS is the WIN flag: setting it from a taunt would end the
        # chapter the moment somebody swung at her.
        self.assertNotIn('EVFLAG_DEFEAT_BOSS', rows)

    def test_the_taunt_does_not_ride_the_moose_or_a_turn_event(self):
        """The moose is a convertible miniboss on its own pid; the taunt is the BOSS's.
        And it is not a turn script -- the eruption warning is, and copying that shape
        would fire the taunt on a clock rather than on the fight."""
        rows = inject.chapters.ch05.ch05_ravisin_battle_quote()
        self.assertNotIn(inject.chapter_ids.CH05_MOOSE_PID, rows)
        for turn in (2, 6, 8):
            self.assertNotIn('TEXTSHOW(0x%X)' % inject.chapter_ids.CH05_RAVISIN_TAUNT_MSG,
                             inject.chapters.ch05.ch05_wave_script(turn, 'MS_Ch05WaveT%d' % turn))


class Ch05SahnarTalkRecruit(unittest.TestCase):
    """The chapter's payoff: Basil chaperoned across turns the risen Sahnar (#25).

    This scene shipped WIRED and UNWRITTEN for months, pointed at vanilla 0x9CC -- the
    Natasha->Joshua recruit ours is the twin of. On paper that is the legitimate placeholder
    pattern; on screen it was a bug, because our speakers wear the Artur and Marisa slots
    while 0x9CC loads Natasha's and Joshua's. What the player saw was Hlin Trollbane's bust
    (dressed onto the Natasha slot) talking to vanilla Joshua. So the face assertions below
    are the regression, not decoration: a decoder is green either way.
    """
    CAMPAIGN = 'rime-of-the-frostmaiden'

    def _chap(self):
        return inject.hosting._load_chapter_yaml(self.CAMPAIGN, inject.chapter_ids.CH05_CHAPTER_YAML)

    def _event(self):
        return next(e for e in self._chap()['events'] if e['trigger'] == 'sahnar_talk')

    def test_talk_moved_off_vanillas_id_into_ch05s_real_host_block(self):
        self.assertNotEqual(0x9CC, inject.chapter_ids.CH05_SAHNAR_TALK_MSG,
                            'the Talk still reads vanilla Ch5 prose in vanilla Ch5 faces')
        self.assertEqual(0x9E8, inject.chapter_ids.CH05_SAHNAR_TALK_MSG)
        self.assertTrue(0x9E4 <= inject.chapter_ids.CH05_SAHNAR_TALK_MSG <= 0x9F3)
        self.assertIn(inject.chapter_ids.CH05_SAHNAR_TALK_MSG, inject.messages.HOSTED_CHAPTER_MESSAGE_IDS['ch05'])
        self.assertEqual('ch05', inject.messages.assert_message_ids_unique()[inject.chapter_ids.CH05_SAHNAR_TALK_MSG])

    def test_the_yaml_slot_label_stays_an_anatomy_citation(self):
        """`vanilla 0x9CC` names the scene we MINE. It is not a destination -- and leaving the
        label alone while moving the id is the whole point of the two being different fields."""
        self.assertEqual('vanilla 0x9CC', self._event()['slot'])

    def test_locked_sixteen_boxes_emit_our_two_faces_and_never_vanillas(self):
        event = self._event()
        self.assertEqual(16, len(event['script']))
        self.assertEqual({'sahnar', 'basil'}, {next(iter(box)) for box in event['script']})

        body = dict(inject.chapters.ch05.ch05_sahnar_talk_messages(self._chap()))[inject.chapter_ids.CH05_SAHNAR_TALK_MSG]
        self.assertIn('[LoadFace][FID_Artur]', body)     # Basil
        self.assertIn('[LoadFace][FID_Marisa]', body)    # Sahnar
        self.assertNotIn('[FID_Natasha]', body)          # the bug: Hlin's dressed slot
        self.assertNotIn('[FID_Joshua]', body)           # the bug: vanilla's recruit
        # Prose flowed free of every text code: the authored sentences straddle both the
        # [LF] line break and the [A] page break, so asserting on either shape asserts on the
        # wrap rather than on the words.
        prose = ' '.join(re.sub(r'\[[^\]]*\]', ' ', body).split())
        self.assertIn('...Basil?', prose)                # the recognition IS the word
        self.assertIn('Only my true enemy has been revealed', prose)
        self.assertIn('Can I give you a berry now?', prose)    # last box, deliberately unanswered

    def test_the_two_shot_stages_recruiter_left_and_the_turned_unit_right(self):
        """ch04's parley idiom: the recruiter holds the party's side, the unit being turned
        holds the other, so neither podium swaps faces mid-scene."""
        body = dict(inject.chapters.ch05.ch05_sahnar_talk_messages(self._chap()))[inject.chapter_ids.CH05_SAHNAR_TALK_MSG]
        self.assertIn('[OpenMidLeft][LoadFace][FID_Artur]', body)
        self.assertIn('[OpenMidRight][LoadFace][FID_Marisa]', body)
        self.assertNotIn('[ClearFace]', body)

    def test_every_box_fits_the_map_talk_bubble(self):
        """The Talk rides TEXTSHOW -> PutTalkBubble, whose right-side branch computes
        x = 29 - width with no clamp: a line over 29 runs off the tilemap (the ch03 crier bug)."""
        body = dict(inject.chapters.ch05.ch05_sahnar_talk_messages(self._chap()))[inject.chapter_ids.CH05_SAHNAR_TALK_MSG]
        for line in body.split('\n'):
            printable = re.sub(r'\[[^\]]*\]', '', line)
            self.assertLessEqual(font.text_px(printable), font.TALK_BUDGET_PX,
                                     'bubble overflow: %r' % line)

    def test_talk_script_shows_the_moved_id_then_flips_sahnar_blue(self):
        _chars, script = inject.recruit.talk_recruit_wiring(
            ['CHARACTER_ARTUR'], 'CHARACTER_MARISA', inject.chapters.ch05.CH05_SAHNAR_TALK_FLAG,
            inject.chapters.ch05.CH05_SAHNAR_TALK_SCRIPT, inject.chapter_ids.CH05_SAHNAR_TALK_MSG)
        self.assertIn('TEXTSHOW(0x%X)' % inject.chapter_ids.CH05_SAHNAR_TALK_MSG, script)
        self.assertNotIn('TEXTSHOW(0x9CC)', script)
        self.assertLess(script.index('TEXTSHOW(0x%X)' % inject.chapter_ids.CH05_SAHNAR_TALK_MSG),
                        script.index('CUSA(CHARACTER_MARISA)'))


class EveryChannelIsMeasuredAgainstITSOwnWindow(unittest.TestCase):
    """A pixel budget is only valid for the renderer it was measured on, and three of this
    campaign's windows are NOT the talk bubble. Retiring the 29-character wrap gave all of them
    the bubble's 203px for a moment; these pin the three real numbers.

    Found in review of #298, which is worth recording: the change's own stated principle was
    "not every panel is the talk window", and it had been applied to two of the four.
    """
    CAMPAIGN = 'rime-of-the-frostmaiden'

    def test_battle_and_death_quotes_fit_the_FORCED_twenty_tile_bubble(self):
        """`IsBattleDeamonActive()` sends these through PutTalkBubble case 2/3 (scene.c:1769),
        which overwrites the measured width with a flat 20 tiles and starts text at tile 10.
        A line sized for the talk window draws off a 32-tile tilemap. Vanilla's own 123
        battle-quote messages all cap at 143px, which is that box less its borders."""
        chap = inject.hosting._load_chapter_yaml(self.CAMPAIGN, inject.chapter_ids.CH05_CHAPTER_YAML)
        for what, body in (('taunt', inject.chapters.ch05.ch05_ravisin_taunt_message(chap)),
                           ('death', inject.chapters.ch05.ch05_ravisin_death_message(chap))):
            for line in body.split('\n'):
                text = re.sub(r'\[[^\]]*\]', '', line)
                self.assertLessEqual(font.text_px(text), font.BATTLE_QUOTE_BUDGET_PX,
                                     '%s quote overruns the battle bubble: %r' % (what, text))

    def test_every_PCs_death_quote_fits_it_too(self):
        """These ride the same list and the same bubble, and there are eight of them."""
        for line in inject.text._wrap_fe_lines('A' * 3, font.BATTLE_QUOTE_BUDGET_PX):
            pass
        self.assertLess(font.BATTLE_QUOTE_BUDGET_PX, font.TALK_BUDGET_PX)

    def test_faceless_narration_fits_the_auto_centered_helpbox(self):
        """SOLOTEXTBOXSTART's box clamps at 0xC0 in helpbox.c while its text draws unclamped,
        so narration cannot take the bubble's budget."""
        self.assertEqual(0xC0, font.SOLO_BOX_BUDGET_PX)
        wrapped = inject.text._wrap_fe_lines(
            'The kobolds have left a sign here, and it is not a welcoming one at all.',
            font.SOLO_BOX_BUDGET_PX)
        for line in wrapped:
            self.assertLessEqual(font.text_px(line), font.SOLO_BOX_BUDGET_PX)


class Ch05SahnarTalkNoLupinFallback(unittest.TestCase):
    """The Talk recruit's no-Lupin arm -- the LAST of ch05's five fallbacks (#25).

    Box 8 is PROOF #1, the evidence that turns Sahnar, and it is a wolf ch04's optional parley
    may never have handed the player. The substitute makes the proof BASIL instead: not
    "someone else already walked free" but "the two of us could".

    Shape is vanilla's, not ours. `ch14a-eventscript.h` branches on CHECK_ALIVE(CHARACTER_JOSHUA)
    -- Sahnar's own donor, and vanilla Ch5's optional Talk recruit -- and picks a WHOLE message
    per arm before converging on a shared LABEL (`TEXTSHOW(0xa93)` / `TEXTSHOW(0xa95)` ->
    `LABEL(0xb)`). Everything below asserts that shape rather than a second mechanism.
    """
    CAMPAIGN = 'rime-of-the-frostmaiden'

    def _chap(self):
        return inject.hosting._load_chapter_yaml(self.CAMPAIGN, inject.chapter_ids.CH05_CHAPTER_YAML)

    def _event(self):
        return next(e for e in self._chap()['events'] if e['trigger'] == 'sahnar_talk')

    def _fallback(self):
        event = self._event()
        return inject.scenes.variant_beat(event['script'], event['no_lupin_fallback'], 'test')

    def _wiring(self):
        _chars, script = inject.recruit.talk_recruit_wiring(
            ['CHARACTER_ARTUR'], 'CHARACTER_MARISA', inject.chapters.ch05.CH05_SAHNAR_TALK_FLAG,
            inject.chapters.ch05.CH05_SAHNAR_TALK_SCRIPT, inject.chapter_ids.CH05_SAHNAR_TALK_MSG,
            variant=(inject.chapters.ch05.CH05_LUPIN_CHARACTER, inject.chapter_ids.CH05_SAHNAR_TALK_NO_LUPIN_MSG))
        return script

    # -- the id ---------------------------------------------------------------
    def test_the_fallback_id_is_claimed_owned_and_outside_no_ones_reach(self):
        """0x9D1 is vanilla Ch5's TUTORIAL text (EventScr_089F231C), reachable only from
        EventListScr_Ch5_Tutorial -- which inject_ch04 zeroes. Same sweep that freed 0x9D2 for
        the moose quip, and the reliquary lines' 0x9CD..0x9D0 before it."""
        self.assertEqual(0x9D1, inject.chapter_ids.CH05_SAHNAR_TALK_NO_LUPIN_MSG)
        self.assertIn(inject.chapter_ids.CH05_SAHNAR_TALK_NO_LUPIN_MSG, inject.messages.HOSTED_CHAPTER_MESSAGE_IDS['ch05'])
        self.assertEqual('ch05',
                         inject.messages.assert_message_ids_unique()[inject.chapter_ids.CH05_SAHNAR_TALK_NO_LUPIN_MSG])

    def test_the_fallback_costs_one_extra_id_not_two(self):
        """`variant_beat` splices the substitute and the WHOLE scene goes to a second id --
        vanilla's own move. Splitting the scene around the differing box would cost two."""
        self.assertEqual({inject.chapter_ids.CH05_SAHNAR_TALK_MSG, inject.chapter_ids.CH05_SAHNAR_TALK_NO_LUPIN_MSG},
                         set(dict(inject.chapters.ch05.ch05_sahnar_talk_messages(self._chap()))))

    # -- the substitution -----------------------------------------------------
    def test_the_proof_moves_off_the_wolf_and_onto_basil_herself(self):
        event = self._event()
        self.assertEqual([8], event['no_lupin_fallback']['boxes'])
        self.assertIn('A wolf.', next(iter(event['script'][7].values())))
        for box in self._fallback():
            self.assertNotIn('wolf', next(iter(box.values())).lower())

    def test_every_box_but_the_proof_rides_through_unchanged(self):
        """Boxes 1-7 and 9-16 are shared, box 9's "we" included -- it already covers her."""
        locked, fallback = self._event()['script'], self._fallback()
        self.assertEqual(locked[:7], fallback[:7])
        self.assertEqual(locked[8:], fallback[9:])
        self.assertIn('That we have a choice', next(iter(fallback[9].values())))

    def test_the_substitute_is_hand_boxed_rather_than_left_to_the_wrapper(self):
        """VANILLA'S CONVENTION: every [LF] and every [A] in texts.txt is authored -- MSG_9CC,
        the scene we mine, places all 32 of its own page breaks. Flowed, our 61-character
        substitute pages itself at "We could go free as" / "well.", mid-clause. The break goes
        on the ellipsis, so the observation lands flat and the OFFER -- which is the whole
        proof -- takes its own press."""
        fallback = self._fallback()
        self.assertEqual(17, len(fallback), 'one replaced box, two of substitute')
        self.assertEqual('There is nothing holding us here...',
                         next(iter(fallback[7].values())))
        self.assertEqual('We could go free as well.', next(iter(fallback[8].values())))

    def test_neither_arm_lets_the_wrapper_page_the_substitute(self):
        bodies = dict(inject.chapters.ch05.ch05_sahnar_talk_messages(self._chap()))
        body = bodies[inject.chapter_ids.CH05_SAHNAR_TALK_NO_LUPIN_MSG]
        for authored in ('There is nothing holding us here...', 'We could go free as well.'):
            page = [p for p in body.split('[A]') if authored.split('.')[0][:20] in
                    re.sub(r'\[[^\]]*\]', '', p).replace('\n', '')]
            self.assertTrue(page, 'the substitute lost its authored box: %r' % authored)

    # -- the channel ----------------------------------------------------------
    def test_both_arms_fit_the_map_talk_bubble(self):
        for _msg, body in inject.chapters.ch05.ch05_sahnar_talk_messages(self._chap()):
            for line in body.split('\n'):
                printable = re.sub(r'\[[^\]]*\]', '', line)
                self.assertLessEqual(font.text_px(printable), font.TALK_BUDGET_PX,
                                     'bubble overflow: %r' % line)

    def test_both_arms_keep_the_two_shot_and_never_vanillas_faces(self):
        for _msg, body in inject.chapters.ch05.ch05_sahnar_talk_messages(self._chap()):
            self.assertIn('[OpenMidLeft][LoadFace][FID_Artur]', body)
            self.assertIn('[OpenMidRight][LoadFace][FID_Marisa]', body)
            self.assertNotIn('[FID_Natasha]', body)
            self.assertNotIn('[FID_Joshua]', body)

    # -- the branch, in vanilla's shape ---------------------------------------
    def test_the_branch_picks_a_WHOLE_message_per_arm_like_ch14as_ending(self):
        script = self._wiring()
        self.assertIn('CHECK_ALIVE(%s)' % inject.chapters.ch05.CH05_LUPIN_CHARACTER, script)
        alive = script.index('TEXTSHOW(0x%X)' % inject.chapter_ids.CH05_SAHNAR_TALK_MSG)
        absent = script.index('TEXTSHOW(0x%X)' % inject.chapter_ids.CH05_SAHNAR_TALK_NO_LUPIN_MSG)
        self.assertLess(script.index('CHECK_ALIVE'), alive)
        self.assertLess(alive, absent, 'the locked arm is the fall-through, as in ch14a')

    def test_the_arms_converge_before_the_single_CUSA_that_recruits_her(self):
        """One recruit, not one per arm. ch14a shares everything after LABEL(0xb) the same way,
        and a CUSA duplicated into both arms is how a branch grows a second bug per fix."""
        script = self._wiring()
        self.assertEqual(1, script.count('CUSA(CHARACTER_MARISA)'))
        self.assertEqual(1, script.count('TEXTSTART'), 'the window opens once, before the branch')
        self.assertEqual(1, script.count('REMA'))
        self.assertLess(script.index('TEXTSTART'), script.index('CHECK_ALIVE'))
        self.assertLess(script.index('TEXTSHOW(0x%X)' % inject.chapter_ids.CH05_SAHNAR_TALK_NO_LUPIN_MSG),
                        script.index('CUSA(CHARACTER_MARISA)'))

    def test_the_branchs_labels_can_be_moved_off_a_pre_scripts_own(self):
        """BEQ/GOTO scan the whole event list for a matching LABEL, so a branch left at 0 in a
        script whose `pre_script` also uses 0 jumps into the wrong arm. ch04's parley passes
        exactly such a sweep (one skip label per wolf), and it is only the distance between
        0x40 and 0 that keeps that safe today -- so the offset has to be reachable."""
        _chars, moved = inject.recruit.talk_recruit_wiring(
            ['CHARACTER_ARTUR'], 'CHARACTER_MARISA', inject.chapters.ch05.CH05_SAHNAR_TALK_FLAG, 'MS_Test',
            inject.chapter_ids.CH05_SAHNAR_TALK_MSG,
            variant=(inject.chapters.ch05.CH05_LUPIN_CHARACTER, inject.chapter_ids.CH05_SAHNAR_TALK_NO_LUPIN_MSG),
            label_base=0x50)
        self.assertIn('LABEL(0x50)', moved)
        self.assertIn('LABEL(0x51)', moved)
        self.assertNotIn('LABEL(0x0)', moved)

    def test_an_unbranched_talk_still_emits_no_branch_at_all(self):
        """ch03's Trex and ch04's Lupin pass no variant and must be byte-identical to before --
        the whole point of parameterising the ONE flow rather than forking it."""
        _chars, plain = inject.recruit.talk_recruit_wiring(
            ['CHARACTER_EIRIKA'], 'CHARACTER_MARISA', inject.chapters.ch05.CH05_SAHNAR_TALK_FLAG,
            'MS_Test', inject.chapter_ids.CH05_SAHNAR_TALK_MSG)
        self.assertNotIn('CHECK_ALIVE', plain)
        self.assertNotIn('BEQ', plain)
        self.assertNotIn('LABEL', plain)

    # -- the hazard this scene carries ----------------------------------------
    def test_every_A_press_is_one_the_AUTHOR_placed(self):
        """The property that REPLACED a trap, and the better of the two.

        While the wrapper measured CHARACTERS at 29, the locked box 8 (70 characters) paged
        itself in two, so this scene cost 21 presses for 16 authored boxes -- and both arms
        happened to land on 21, which made `ch05recruit`'s box count blind to which arm played.
        Measured in pixels at vanilla's own width nothing pages itself: presses == authored
        boxes, 16 against 17.

        So an A-press count is now a fact about the SCRIPT rather than about the wrap. That is
        worth asserting on its own. `sActiveMsg` stays the arm witness regardless -- identity is
        not length, and two arms of some future branch may be the same length again."""
        (_lm, locked), (_fm, fallback) = inject.chapters.ch05.ch05_sahnar_talk_messages(self._chap())
        self.assertEqual(len(self._event()['script']), locked.count('[A]'),
                         'the wrapper paged a box the author did not')
        self.assertEqual(len(self._fallback()), fallback.count('[A]'))
        self.assertNotEqual(locked.count('[A]'), fallback.count('[A]'))


class Ch05OpeningBackdropScenes(unittest.TestCase):
    """ch05's opening plays three locked scenes at the tomb before the party arrives (#25).

    The chapter shipped with `CH05_BEGINNING_SCRIPT` running LOMA -> the line LOAD1s -> prep
    -> the join, SILENTLY: our own script, with no TEXTSHOW anywhere in it. These are the
    first three of the eleven scenes #25 still owed.

    CHANNEL is inherited rather than chosen. Vanilla Ch5's BeginningScene plays 0x9BA-0x9BE
    over a backdrop and only reaches TEXTSTART (on-map bubbles) once the party is physically
    on the street, so our twins are backdrop scenes too -- which is also the only thing that
    CAN work this early, PutTalkBubble having no staged unit to anchor to.
    """
    CAMPAIGN = 'rime-of-the-frostmaiden'

    def _chap(self):
        return inject.hosting._load_chapter_yaml(self.CAMPAIGN, inject.chapter_ids.CH05_CHAPTER_YAML)

    def test_the_three_ids_are_owned_unique_and_inside_ch05s_host_block(self):
        self.assertEqual([0x9E9, 0x9EA, 0x9EB],
                         [msg for _s, msg, _b, _w in inject.chapter_ids.CH05_OPENING_SLOTS])
        claimed = set(inject.messages.HOSTED_CHAPTER_MESSAGE_IDS['ch05'])
        owner = inject.messages.assert_message_ids_unique()
        for _slot, msg, _boxes, _what in inject.chapter_ids.CH05_OPENING_SLOTS:
            self.assertTrue(0x9E4 <= msg <= 0x9F3, 'outside ch05\'s Ch6 host block')
            self.assertIn(msg, claimed)
            self.assertEqual('ch05', owner[msg])

    def test_the_yaml_slot_labels_stay_anatomy_citations(self):
        """`vanilla 0x9BB` names the scene we MINE. ch04 hosts on slot 5 and WRITES that id --
        pointing a ch05 scene at it would play ch04's text in ch04's faces."""
        for slot, msg, _boxes, _what in inject.chapter_ids.CH05_OPENING_SLOTS:
            self.assertNotEqual(int(slot.split()[1], 16), msg)
            self.assertIn(int(slot.split()[1], 16),
                          inject.messages.HOSTED_CHAPTER_MESSAGE_IDS['ch04'])

    def test_each_scene_keeps_its_locked_box_count_and_speakers(self):
        chap = self._chap()
        expected = {'vanilla 0x9BB': (19, {'basil', 'sahnar'}),
                    'vanilla 0x9BC': (16, {'sephek', 'ravisin'}),
                    'vanilla 0x9BD': (7, {'ravisin', 'basil'})}
        for slot, _msg, boxes, _what in inject.chapter_ids.CH05_OPENING_SLOTS:
            script = inject.chapters.ch05._chapter_event_by_slot(chap, 'chapter_start', slot, 'test')['script']
            want_boxes, want_speakers = expected[slot]
            self.assertEqual(want_boxes, boxes, '%s: table box count' % slot)
            # Box count excludes stage directions (`exits:`): they cost no A-press.
            self.assertEqual(want_boxes, inject.text._script_box_count(script),
                             '%s: YAML box count' % slot)
            self.assertEqual(want_speakers,
                             {next(iter(b)) for b in script
                              if next(iter(b)) not in inject.text.SCRIPT_DIRECTIVES})

    def test_every_speaker_wears_our_face_and_never_the_donor_slots_own(self):
        """The #276 regression, one scene earlier: our cast wears vanilla slots, so a scene
        pointed at the wrong id plays the DONOR's face and words and every decoder stays green."""
        bodies = dict(inject.chapters.ch05.ch05_opening_messages(self._chap()))
        self.assertIn('[LoadFace][FID_Artur]', bodies[0x9E9])       # Basil
        self.assertIn('[LoadFace][FID_Marisa]', bodies[0x9E9])      # Sahnar
        self.assertIn('[LoadFace][FID_ONeill]', bodies[0x9EA])      # Sephek Kaltro
        self.assertIn('[LoadFace][FID_Riev]', bodies[0x9EA])        # Ravisin
        self.assertIn('[LoadFace][FID_Riev]', bodies[0x9EB])
        self.assertIn('[LoadFace][FID_Artur]', bodies[0x9EB])
        for body in bodies.values():
            self.assertNotIn('[FID_Natasha]', body)   # Hlin's dressed slot, not Basil's
            self.assertNotIn('[FID_Joshua]', body)

    def test_every_face_tag_the_opening_emits_is_defined_in_textdefs(self):
        """[FID_O_Neill] is not a tag -- textdefs.txt defines [FID_ONeill]. Sephek's portrait
        SLOT is spelled 'O_Neill' in GUEST_PORTRAIT_MAP and 'ONEILL' in PROLOGUE_SEPHEK_SLOT,
        and only the second is one _fid_tag can map, so the wrong source emits a tag the ROM
        has no face for. Caught here because nothing downstream complains: this is the same
        shape as #276, where every text decoder was green while the wrong face was on screen."""
        defined = set(re.findall(r'^\[(FID_\w+)\]',
                                 inject.decomp.vanilla_decomp_text('texts/textdefs.txt'), re.M))
        self.assertIn('FID_ONeill', defined)          # the fixture is real
        self.assertNotIn('FID_O_Neill', defined)      # and the near-miss is not
        for msg, body in inject.chapters.ch05.ch05_opening_messages(self._chap()):
            for tag in re.findall(r'\[(FID_\w+)\]', body):
                self.assertIn(tag, defined, '0x%X emits an undefined face tag' % msg)
        # BOTH spellings of every guest slot must resolve, not just the one this scene happens
        # to use -- otherwise the next scene to reach a guest through _cutscene_fid's
        # GUEST_PORTRAIT_MAP fallback re-opens the same silent hole.
        for unit, slot in inject.cast.GUEST_PORTRAIT_MAP.items():
            for spelling in (slot, slot.upper()):
                tag = inject.text._fid_tag(spelling).strip('[]')
                self.assertIn(tag, defined,
                              '%s (slot %r via %r) resolves to an undefined face tag %s'
                              % (unit, slot, spelling, tag))

    def test_a_speaker_holds_one_SIDE_across_the_whole_opening(self):
        """Ravisin speaks in scene 2 and again in scene 3, its immediate sequel. A per-scene
        default would seat her mid-LEFT in one and mid-right in the other, and a character who
        crosses the screen between adjacent scenes reads as a different person.

        Her exact rung is allowed to shift by one and does: scene 3 raises Sahnar beside her, and
        two faces need an empty rung between them, so Ravisin moves MidRight -> Right to open
        FarRight up (see `assert_silent_faces_have_elbow_room`). That costs nothing on screen --
        the two scenes are separate messages with a full fade through black between them, so
        there is no visible move. Vanilla makes the same shift WITHIN a message, and has to
        animate it (`[OpenMidRight][MoveRight]`, MSG_904)."""
        bodies = dict(inject.chapters.ch05.ch05_opening_messages(self._chap()))
        right = ('[OpenRight]', '[OpenMidRight]', '[OpenFarRight]')
        for msg in (0x9EA, 0x9EB):
            self.assertTrue(
                any('%s[LoadFace][FID_Riev]' % tag in bodies[msg] for tag in right),
                'Ravisin left the right-hand side in 0x%X' % msg)
        self.assertIn('[OpenMidLeft][LoadFace][FID_Artur]', bodies[0x9E9])
        self.assertIn('[OpenMidLeft][LoadFace][FID_Artur]', bodies[0x9EB])

    def test_the_locked_prose_survives_the_wrap(self):
        bodies = dict(inject.chapters.ch05.ch05_opening_messages(self._chap()))
        prose = {m: ' '.join(re.sub(r'\[[^\]]*\]', ' ', b).split()) for m, b in bodies.items()}
        self.assertIn('I wish I could share my berries with her', prose[0x9E9])
        self.assertIn('I know old things', prose[0x9E9])
        self.assertIn('I bring the Frostmaiden\'s will', prose[0x9EA])
        self.assertIn('She was a queen\'s blade once', prose[0x9EA])
        # The warning clause, pinned because it was WRONG once and the failure was invisible:
        # "warmer than they look" reads as a dismissal, since "warm" is the cult's own word for
        # the living-and-sick (ravisin.md), so the box undercut its own "Do not take them
        # lightly". Nothing downstream can tell a warning from an insult.
        self.assertIn('tougher than they look', prose[0x9EA])
        self.assertNotIn('warmer than they look', prose[0x9EA])
        self.assertIn('It never once occurred to me she might be of use', prose[0x9EB])

    def test_the_scenes_wrap_at_the_full_screen_42_not_the_bubble_29(self):
        """These play over a BACG, where the window is full-screen. The 29 exists for
        PutTalkBubble's unclamped right edge, and there is no bubble here."""
        bodies = dict(inject.chapters.ch05.ch05_opening_messages(self._chap()))
        widest = 0
        for body in bodies.values():
            for line in body.split('\n'):
                widest = max(widest, font.text_px(re.sub(r'\[[^\]]*\]', '', line)))
        self.assertLessEqual(widest, font.TALK_BUDGET_PX)
        self.assertGreater(widest, 140, 'these should use the full budget, not a narrow one')

    def test_the_block_raises_one_backdrop_plays_all_three_then_fades_out(self):
        """ONE tomb backdrop across the three tomb scenes, as vanilla spends
        BG_SERAFEW_VILLAGE on four consecutive ones. (Scene 4 then CUTS to the ridge -- a
        different place, so a second BACG; that seam is Ch05ArrivalSceneAndTheNoLupinBranch's.)"""
        block = inject.chapters.ch05.ch05_opening_backdrop_block()
        tomb = block[:block.index('BACG(%s)' % inject.chapters.ch05.CH05_ARRIVAL_BG)]
        self.assertEqual(1, tomb.count('BACG('), 'one backdrop, held across the three scenes')
        self.assertIn('BACG(%s)' % inject.chapters.ch05.CH05_OPENING_BG, block)
        self.assertLess(block.index('REMOVEPORTRAITS'), block.index('BACG('),
                        'BACG only decompresses while activeTextType is REMOVEPORTRAITS')
        self.assertLess(block.index('BACG('), block.index('FADU(16)'))
        for _slot, msg, _boxes, _what in inject.chapter_ids.CH05_OPENING_SLOTS:
            self.assertIn('Text(0x%X)' % msg, block)
        first, last = (block.index('Text(0x%X)' % inject.chapter_ids.CH05_OPENING_SLOTS[0][1]),
                       block.index('Text(0x%X)' % inject.chapter_ids.CH05_OPENING_SLOTS[-1][1]))
        self.assertLess(first, last, 'scenes must run in player order')
        self.assertTrue(block.rstrip().endswith('*/'))
        self.assertIn('FADI(16)', block.rstrip().split('\n')[-1])

    def test_separate_moments_fade_through_black_between_them(self):
        """Vanilla gives each of 0x9BC/0x9BD a full Text_BG fade cycle. Played as a hard cut,
        three different moments read as one continuous conversation."""
        block = inject.chapters.ch05.ch05_opening_backdrop_block()
        tomb = block[:block.index('BACG(%s)' % inject.chapters.ch05.CH05_ARRIVAL_BG)]
        self.assertEqual(len(inject.chapter_ids.CH05_OPENING_SLOTS), tomb.count('FADI(16)'),
                         'one fade between each pair of tomb scenes, plus the cut away')
        self.assertEqual(len(inject.chapter_ids.CH05_OPENING_SLOTS) + 1, block.count('FADI(16)'),
                         'and one more closing the ridge out into LOMA')

    def test_the_opening_never_reaches_for_Text_BG(self):
        """Text_BG ends in EventScr_TextShowWithFadeIn -- CLEAN then FADU back onto the MAP.
        Before LOMA that map is still the host slot's, so each scene would fade up on vanilla
        Ch6's terrain."""
        self.assertNotIn('Text_BG', inject.chapters.ch05.ch05_opening_backdrop_block())

    def test_the_backdrop_is_a_registered_campaign_bg_with_a_source_png(self):
        names = [enum for enum, _stem, _credit in inject.backgrounds.CAMPAIGN_BGS]
        self.assertIn(inject.chapters.ch05.CH05_OPENING_BG, names)
        stem = next(s for e, s, _c in inject.backgrounds.CAMPAIGN_BGS if e == inject.chapters.ch05.CH05_OPENING_BG)
        png = os.path.join(inject.decomp.REPO, 'campaigns', self.CAMPAIGN, 'backgrounds', stem + '.png')
        self.assertTrue(os.path.isfile(png), png)

    def test_the_vendored_backdrop_stays_inside_the_six_banks_the_fades_apply(self):
        """Bremen is banked at 8 and cannot be shown through a fade for exactly this reason
        (HANDOFF). A BG the opening fades in AND out of has to be under that ceiling."""
        from PIL import Image
        stem = next(s for e, s, _c in inject.backgrounds.CAMPAIGN_BGS if e == inject.chapters.ch05.CH05_OPENING_BG)
        im = Image.open(os.path.join(inject.decomp.REPO, 'campaigns', self.CAMPAIGN,
                                     'backgrounds', stem + '.png'))
        self.assertEqual('P', im.mode)
        self.assertEqual((240, 160), im.size)
        banks = max(int(i) // 16 for i in set(im.getdata())) + 1
        self.assertLessEqual(banks, 6, '%d banks -- the fade procs apply only six' % banks)


class Ch05ArrivalSceneAndTheNoLupinBranch(unittest.TestCase):
    """Scene 4 -- the party crests the ridge -- and the branch the whole chapter waits on (#25).

    It is the fourth backdrop scene and the FIRST with a `no_lupin_fallback`, so it is where the
    mechanism gets built. Four more scenes reuse it: Basil's join, Proof #1 in the Talk recruit,
    and both endings.

    The signal is `CHECK_ALIVE`, not a flag. `eventscr.c` returns 0 for a unit that is not found
    at all OR is `US_DEAD`, so never-recruited and recruited-then-killed collapse into the one
    arm we want; and because it reads the ROSTER rather than the field it also survives ch05's
    9-of-10 deploy, where a recruited Lupin can be sitting on the bench. Vanilla's own answer --
    ch14a branches its ending on CHECK_ALIVE(CHARACTER_JOSHUA), Joshua being vanilla Ch5's
    optional Talk recruit and Sahnar's donor.
    """
    CAMPAIGN = 'rime-of-the-frostmaiden'

    def _chap(self):
        return inject.hosting._load_chapter_yaml(self.CAMPAIGN, inject.chapter_ids.CH05_CHAPTER_YAML)

    def _scene(self):
        slot, _msg, _boxes, _what = inject.chapter_ids.CH05_ARRIVAL_SLOT
        return inject.chapters.ch05._chapter_event_by_slot(self._chap(), 'chapter_start', slot, 'test')

    # ── ids ────────────────────────────────────────────────────────────────────
    def test_both_ids_are_owned_unique_and_inside_ch05s_host_block(self):
        _slot, msg, _boxes, _what = inject.chapter_ids.CH05_ARRIVAL_SLOT
        claimed = set(inject.messages.HOSTED_CHAPTER_MESSAGE_IDS['ch05'])
        owner = inject.messages.assert_message_ids_unique()
        for mid in (msg, inject.chapter_ids.CH05_ARRIVAL_NO_LUPIN_MSG):
            self.assertTrue(0x9E4 <= mid <= 0x9F5, 'outside ch05\'s Ch6 host block')
            self.assertIn(mid, claimed)
            self.assertEqual('ch05', owner[mid])
        self.assertEqual((0x9EC, 0x9ED), (msg, inject.chapter_ids.CH05_ARRIVAL_NO_LUPIN_MSG),
                         "#25's allocation table")

    def test_the_fallback_costs_one_extra_id_not_four(self):
        """The wrong instinct is to split the scene around the differing box, which would spend
        four ids on a 7-box scene with one substitution. Duplicating text is free; ids are what
        is scarce, so the WHOLE variant scene goes to a second id and the branch picks."""
        self.assertEqual(1, len(self._scene()['no_lupin_fallback']['boxes']))
        written = dict(inject.chapters.ch05.ch05_opening_messages(self._chap()))
        arrival = [mid for mid in written
                   if mid in (inject.chapter_ids.CH05_ARRIVAL_SLOT[1], inject.chapter_ids.CH05_ARRIVAL_NO_LUPIN_MSG)]
        self.assertEqual(2, len(arrival), 'one scene, one variant, two ids')

    def test_the_yaml_slot_label_stays_an_anatomy_citation(self):
        slot, msg, _boxes, _what = inject.chapter_ids.CH05_ARRIVAL_SLOT
        self.assertNotEqual(int(slot.split()[1], 16), msg)
        self.assertIn(int(slot.split()[1], 16), inject.messages.HOSTED_CHAPTER_MESSAGE_IDS['ch04'])

    # ── the substitution ───────────────────────────────────────────────────────
    def test_the_chapters_first_line_has_a_speaker_on_both_paths(self):
        """Box 1 is the FIRST LINE OF THE CHAPTER and it is Lupin's, so a no-parley player
        would open ch05 on a speaker who is not there."""
        scene = self._scene()
        locked = scene['script']
        fallback = inject.scenes.variant_beat(locked, scene['no_lupin_fallback'], 'test')
        self.assertEqual('lupin', next(iter(locked[0])))
        self.assertEqual(len(locked), len(fallback))
        for i, box in enumerate(fallback, 1):
            (speaker, text), = box.items()
            self.assertTrue(speaker and text.strip(), 'box %d has no speaker/text' % i)
        self.assertNotIn('lupin', [next(iter(b)) for b in fallback],
                         'the no-parley path must never put Lupin on stage')
        self.assertEqual('pinky', next(iter(fallback[0])),
                         'box 1 goes to Pinky, continuing ch04\'s own no-Lupin tracker')

    def test_the_six_unchanged_boxes_ride_through_both_branches(self):
        scene = self._scene()
        fallback = inject.scenes.variant_beat(scene['script'], scene['no_lupin_fallback'], 'test')
        self.assertEqual(scene['script'][1:], fallback[1:])
        self.assertEqual('pinky', next(iter(fallback[-1])),
                         'Pinky keeps the closing spot on both paths')

    def test_a_drifted_anchor_fails_loudly_instead_of_mis_swapping(self):
        scene = self._scene()
        with self.assertRaises(SystemExit):
            inject.scenes.variant_beat(list(reversed(scene['script'])),
                            scene['no_lupin_fallback'], 'test')

    def test_one_box_may_be_replaced_by_SEVERAL(self):
        """A substitute chosen as prose can be too long for the channel it lands in -- ch05's
        on-map fallbacks are, at the bubble's 29. The author then has to place the extra
        A-press, so a `script:` entry may be a LIST of boxes standing in for the one named
        box. `boxes:`/`replaces:`/`script:` still agree one-for-one; only the substitute is
        plural, which is what keeps this the same mechanism rather than a second one."""
        beat = [{'a': 'one'}, {'b': 'two'}, {'c': 'three'}]
        out = inject.scenes.variant_beat(beat, {'boxes': [2], 'replaces': ['two'],
                                     'script': [[{'b': 'two-a'}, {'b': 'two-b'}]]}, 'test')
        self.assertEqual([{'a': 'one'}, {'b': 'two-a'}, {'b': 'two-b'}, {'c': 'three'}], out)

    def test_a_plural_substitute_does_not_shift_a_later_replacement(self):
        """The `boxes:` indices are read against the ORIGINAL beat. Splicing left to right
        without saying so would move every box after the first substitution, and the anchor
        assertion would then blame the locked script for moving."""
        beat = [{'a': 'one'}, {'b': 'two'}, {'c': 'three'}]
        out = inject.scenes.variant_beat(beat, {'boxes': [1, 3], 'replaces': ['one', 'three'],
                                     'script': [[{'a': 'x'}, {'a': 'y'}], {'c': 'z'}]}, 'test')
        self.assertEqual([{'a': 'x'}, {'a': 'y'}, {'b': 'two'}, {'c': 'z'}], out)

    def test_every_ch05_fallback_declares_one_schema_not_two(self):
        """ch05 authored its blocks with singular `box:`/`replaces:` while variant_beat --
        ch04's, already shipping -- reads LISTS. Normalising the YAML is what kept this at one
        mechanism; a reader that accepts both shapes is the second one.

        THREE, not the five #25 first listed: both ENDINGS were unbranched 2026-08-19 because
        "like she woke the wolves" does not name an optional recruit -- the party fights the
        pack whether or not Marty parleys it, so recruitment decides only whether Lupin JOINS.
        What is left is the arrival, the join and the Talk recruit, and all three address him
        as a UNIT rather than as a thing that happened.
        """
        chap = self._chap()
        blocks = [e['no_lupin_fallback'] for e in chap['events'] if 'no_lupin_fallback' in e]
        self.assertEqual(3, len(blocks), "#25's conditional scenes, minus the two endings")
        for fb in blocks:
            self.assertNotIn('box', fb, 'singular `box:` is the second schema')
            self.assertIsInstance(fb['boxes'], list)
            self.assertIsInstance(fb['replaces'], list)
            self.assertEqual(len(fb['boxes']), len(fb['replaces']))
            self.assertEqual(len(fb['boxes']), len(fb['script']))

    # ── the branch itself ──────────────────────────────────────────────────────
    def test_the_branch_asks_the_roster_and_never_a_flag(self):
        """A flag would have to survive a chapter boundary, and a FIELD test would send a player
        who recruited Lupin and benched him down the no-Lupin arm."""
        code = inject.scenes.branch_on_check_alive(inject.chapters.ch05.CH05_LUPIN_CHARACTER, '    HAVE\n', '    NONE\n')
        self.assertIn('CHECK_ALIVE(%s)' % inject.chapters.ch05.CH05_LUPIN_CHARACTER, code)
        self.assertNotIn('CHECK_EVENTID', code)
        self.assertNotIn('CHECK_DEPLOYED', code)
        self.assertEqual('CHARACTER_DUESSEL', inject.chapters.ch05.CH05_LUPIN_CHARACTER,
                         "Lupin's MAP identity is his portrait slot, not his STAT_DONOR")

    def test_the_two_arms_converge_on_one_label(self):
        code = inject.scenes.branch_on_check_alive('CHARACTER_X', '    HAVE\n', '    NONE\n')
        self.assertIn('BEQ(0x0, EVT_SLOT_C, EVT_SLOT_0)', code)
        self.assertLess(code.index('HAVE'), code.index('LABEL(0x0)'))
        self.assertLess(code.index('LABEL(0x0)'), code.index('NONE'))
        self.assertLess(code.index('NONE'), code.index('LABEL(0x1)'))
        self.assertIn('LABEL(0x4)', inject.scenes.branch_on_check_alive('C', '', '', label_base=4))

    def test_both_branch_primitives_are_one_skeleton_with_two_predicates(self):
        """branch_on_flag and branch_on_check_alive differ ONLY in their PREDICATE -- the line
        that loads slot C, and the comment naming what a jump means. Compared with those gone,
        the two must be the same code; if they ever diverge, one of them is a second mechanism."""
        strip = lambda c: [re.sub(r'/\*.*?\*/', '', l).rstrip() for l in c.split('\n')
                           if 'CHECK_ALIVE' not in l and 'CHECK_EVENTID' not in l]
        self.assertEqual(strip(inject.chapters.ch04.branch_on_flag('EVFLAG_TMP(9)', '    A\n', '    B\n')),
                         strip(inject.scenes.branch_on_check_alive('CHARACTER_X', '    A\n', '    B\n')))

    def test_the_beginning_script_picks_the_arm_around_the_arrival_text(self):
        block = inject.chapters.ch05.ch05_opening_backdrop_block()
        self.assertIn('CHECK_ALIVE(%s)' % inject.chapters.ch05.CH05_LUPIN_CHARACTER, block)
        self.assertIn('Text(0x%X)' % inject.chapter_ids.CH05_ARRIVAL_SLOT[1], block)
        self.assertIn('Text(0x%X)' % inject.chapter_ids.CH05_ARRIVAL_NO_LUPIN_MSG, block)
        # exactly one of the two plays: the alive arm GOTOs past the fallback
        self.assertLess(block.index('CHECK_ALIVE'),
                        block.index('Text(0x%X)' % inject.chapter_ids.CH05_ARRIVAL_SLOT[1]))
        self.assertLess(block.index('Text(0x%X)' % inject.chapter_ids.CH05_ARRIVAL_SLOT[1]),
                        block.index('Text(0x%X)' % inject.chapter_ids.CH05_ARRIVAL_NO_LUPIN_MSG))
        self.assertIn('GOTO(', block)

    def test_the_three_tomb_scenes_play_before_the_branch(self):
        """Player order: the tomb, then the ridge. The branch is the LAST thing before LOMA."""
        block = inject.chapters.ch05.ch05_opening_backdrop_block()
        for _slot, msg, _boxes, _what in inject.chapter_ids.CH05_OPENING_SLOTS:
            self.assertLess(block.index('Text(0x%X)' % msg), block.index('CHECK_ALIVE'))

    # ── the second backdrop ────────────────────────────────────────────────────
    def test_the_arrival_cuts_to_its_own_backdrop_and_re_arms_the_load_mode(self):
        """BACG only decompresses while activeTextType is REMOVEPORTRAITS/_1A22 (eventscr.c:1316);
        the Text() beats above left it at TEXTSTART, so a bare second BACG is a no-op and the tomb
        stays in VRAM. The ch03/ch04 stale-BG bug, one chapter later."""
        block = inject.chapters.ch05.ch05_opening_backdrop_block()
        self.assertEqual(2, block.count('BACG('), 'the tomb, then the ridge')
        self.assertIn('BACG(%s)' % inject.chapters.ch05.CH05_ARRIVAL_BG, block)
        second = block.index('BACG(%s)' % inject.chapters.ch05.CH05_ARRIVAL_BG)
        rearm = block.rindex('REMOVEPORTRAITS', 0, second)
        self.assertLess(block.index('Text(0x%X)' % inject.chapter_ids.CH05_OPENING_SLOTS[-1][1]), rearm,
                        're-arm has to come AFTER the tomb scenes that reset it')
        self.assertIn('FADI(16)', block[block.index(
            'Text(0x%X)' % inject.chapter_ids.CH05_OPENING_SLOTS[-1][1]):rearm],
            'fade the tomb out before cutting to the ridge')

    def test_the_arrival_backdrop_is_registered_with_a_source_png_inside_six_banks(self):
        from PIL import Image
        names = [enum for enum, _stem, _credit in inject.backgrounds.CAMPAIGN_BGS]
        self.assertIn(inject.chapters.ch05.CH05_ARRIVAL_BG, names)
        stem = next(s for e, s, _c in inject.backgrounds.CAMPAIGN_BGS if e == inject.chapters.ch05.CH05_ARRIVAL_BG)
        png = os.path.join(inject.decomp.REPO, 'campaigns', self.CAMPAIGN, 'backgrounds', stem + '.png')
        self.assertTrue(os.path.isfile(png), png)
        im = Image.open(png)
        self.assertEqual('P', im.mode)
        self.assertEqual((240, 160), im.size)
        banks = max(int(i) // 16 for i in set(im.getdata())) + 1
        self.assertLessEqual(banks, 6, '%d banks -- the fade procs apply only six' % banks)

    # ── the two bodies ─────────────────────────────────────────────────────────
    def test_both_bodies_wear_our_faces_and_wrap_at_the_scenic_42(self):
        bodies = dict(inject.chapters.ch05.ch05_opening_messages(self._chap()))
        locked, fallback = bodies[inject.chapter_ids.CH05_ARRIVAL_SLOT[1]], bodies[inject.chapter_ids.CH05_ARRIVAL_NO_LUPIN_MSG]
        # Face slots are PORTRAIT_MAP's, never STAT_DONOR's -- Wolfram's stats come from Gilliam
        # and his face from Franz, and a scene that reached for the donor would put a stranger on
        # screen with every text decoder still green (#276's shape).
        self.assertIn('[LoadFace][FID_Duessel]', locked)      # Lupin
        self.assertNotIn('[FID_Duessel]', fallback)
        for body in (locked, fallback):
            self.assertIn('[LoadFace][FID_Franz]', body)      # Wolfram
            self.assertIn('[LoadFace][FID_Seth]', body)       # Marty
            self.assertIn('[LoadFace][FID_Neimi]', body)      # Pinky
            self.assertNotIn('[FID_Gilliam]', body)
            self.assertNotIn('[FID_Knoll]', body)
            self.assertNotIn('[FID_Vanessa]', body)
            widest = max(font.text_px(re.sub(r'\[[^\]]*\]', '', line))
                         for line in body.split('\n'))
            self.assertLessEqual(widest, font.TALK_BUDGET_PX)

    def test_a_speaker_holds_one_podium_across_both_arms(self):
        bodies = dict(inject.chapters.ch05.ch05_opening_messages(self._chap()))
        for body in (bodies[inject.chapter_ids.CH05_ARRIVAL_SLOT[1]],
                     bodies[inject.chapter_ids.CH05_ARRIVAL_NO_LUPIN_MSG]):
            for spk, podium in inject.chapters.ch05.CH05_ARRIVAL_PODIUMS.items():
                tag = inject.text._fid_tag(inject.cast.PORTRAIT_MAP[spk])
                if tag in body:
                    self.assertIn('%s[LoadFace]%s' % (podium, tag), body,
                                  '%s must sit at %s in both arms' % (spk, podium))

    def test_the_four_speakers_fit_the_face_budget(self):
        """FACE_SLOT_COUNT is 4. A fifth podium evicts one mid-scene."""
        self.assertLessEqual(len(set(inject.chapters.ch05.CH05_ARRIVAL_PODIUMS.values())), 4)
        scene = self._scene()
        fallback = inject.scenes.variant_beat(scene['script'], scene['no_lupin_fallback'], 'test')
        for beat in (scene['script'], fallback):
            self.assertLessEqual(len({next(iter(b)) for b in beat}), 4)

    def test_the_locked_prose_survives_the_wrap(self):
        bodies = dict(inject.chapters.ch05.ch05_opening_messages(self._chap()))
        plain = {m: ' '.join(re.sub(r'\[[^\]]*\]', ' ', b).split()) for m, b in bodies.items()}
        locked = plain[inject.chapter_ids.CH05_ARRIVAL_SLOT[1]]
        fallback = plain[inject.chapter_ids.CH05_ARRIVAL_NO_LUPIN_MSG]
        self.assertIn('The trail leads here', locked)
        self.assertIn('The tracks stop here, Father', fallback)
        for body in (locked, fallback):
            self.assertIn('This was a training arena', body)   # Wolfram's Forge seed
            self.assertIn('This magic is familiar', body)      # Marty's hook
            self.assertIn('Father, I see it', body)            # Pinky's closer


class Ch05BasilJoinsAfterPrep(unittest.TestCase):
    """Scene 5 -- Basil trundles up, cracks the tourist joke, and JOINS (#25).

    The opening's FIRST on-map beat, and the first place the inherited channel had to be
    overruled. Vanilla plays its twin (0x9C2) BEFORE the prep CALL, because vanilla stages
    its speaking party with explicit LOAD1s; ours is placed BY prep, so before the CALL the
    field holds the risen line, Ravisin and a green shrub and nobody the shrub could be
    talking to. So the beat goes after `CALL(prep)` -- vanilla's own after-prep shape
    (`FADU(16)` -> `CUMO_*` -> `STAL` -> `CURE` -> `TEXTSTART`), which is exactly what its
    0x9C3/0x9C4 do -- and it lands adjacent to the CUSA that was already there, so the line
    that asks and the flip that answers are one beat instead of two across a screen.
    """
    CAMPAIGN = 'rime-of-the-frostmaiden'

    def _chap(self):
        return inject.hosting._load_chapter_yaml(self.CAMPAIGN, inject.chapter_ids.CH05_CHAPTER_YAML)

    def _scene(self):
        slot, _msg, _boxes, _what = inject.chapter_ids.CH05_BASIL_JOIN_SLOT
        return inject.chapters.ch05._chapter_event_by_slot(self._chap(), 'chapter_start', slot, 'test')

    def _script(self):
        return inject.chapters.ch05.ch05_beginning_script(self._chap(), 'CHARACTER_ARTUR',
                                        inject.chapters.ch05.CH05_SAHNAR_TABLE, 'CHARACTER_MARISA')

    # ── ids ────────────────────────────────────────────────────────────────────
    def test_both_ids_are_owned_unique_and_inside_ch05s_host_block(self):
        _slot, msg, _boxes, _what = inject.chapter_ids.CH05_BASIL_JOIN_SLOT
        claimed = set(inject.messages.HOSTED_CHAPTER_MESSAGE_IDS['ch05'])
        owner = inject.messages.assert_message_ids_unique()
        for mid in (msg, inject.chapter_ids.CH05_BASIL_JOIN_NO_LUPIN_MSG):
            self.assertTrue(0x9E4 <= mid <= 0x9F5, 'outside ch05\'s Ch6 host block')
            self.assertIn(mid, claimed)
            self.assertEqual('ch05', owner[mid])
        self.assertEqual((0x9EE, 0x9EF), (msg, inject.chapter_ids.CH05_BASIL_JOIN_NO_LUPIN_MSG),
                         "#25's allocation table")

    def test_the_yaml_slot_label_stays_an_anatomy_citation(self):
        """`vanilla 0x9C2` names the scene we MINE. It is also ch04's own no-parley ending,
        which is what the join beat once pointed at -- the collision guard's founding case."""
        slot, msg, _boxes, _what = inject.chapter_ids.CH05_BASIL_JOIN_SLOT
        self.assertNotEqual(int(slot.split()[1], 16), msg)
        self.assertIn(int(slot.split()[1], 16), inject.messages.HOSTED_CHAPTER_MESSAGE_IDS['ch04'])

    # ── the channel ────────────────────────────────────────────────────────────
    def test_both_bodies_wrap_at_the_bubble_29_not_the_scenic_42(self):
        """The first beat that rides TEXTSHOW -> PutTalkBubble, whose right-side branch
        computes x = 29 - width with no clamp: a line over 29 runs off the tilemap."""
        for _msg, body in inject.chapters.ch05.ch05_basil_join_messages(self._chap()):
            for line in body.split('\n'):
                printable = re.sub(r'\[[^\]]*\]', '', line)
                self.assertLessEqual(font.text_px(printable), font.TALK_BUDGET_PX,
                                     'bubble overflow: %r' % line)

    def test_basil_keeps_the_mid_left_she_holds_in_the_talk_recruit(self):
        for _msg, body in inject.chapters.ch05.ch05_basil_join_messages(self._chap()):
            self.assertIn('[OpenMidLeft][LoadFace][FID_Artur]', body)
            self.assertNotIn('[FID_Natasha]', body)     # her STAT_DONOR, never her face

    def test_the_scene_is_three_locked_basil_boxes(self):
        self.assertEqual(3, inject.chapter_ids.CH05_BASIL_JOIN_SLOT[2])
        self.assertEqual(['basil'] * 3, [next(iter(b)) for b in self._scene()['script']])

    # ── the substitution ───────────────────────────────────────────────────────
    def test_the_fallback_moves_basils_trigger_off_lupin_and_onto_the_party(self):
        """Box 2 is Basil reading the WOLF, and ch04's parley is optional. The variant makes
        the party itself the revelation: everyone she has met belonged to Ravisin."""
        scene = self._scene()
        fallback = inject.scenes.variant_beat(scene['script'], scene['no_lupin_fallback'], 'test')
        self.assertEqual([2], scene['no_lupin_fallback']['boxes'])
        self.assertIn('Wolf.', next(iter(scene['script'][1].values())))
        for box in fallback:
            self.assertNotIn('Wolf', next(iter(box.values())))
        self.assertEqual(scene['script'][0], fallback[0], 'the tourist joke is shared')
        self.assertEqual(scene['script'][-1], fallback[-1], 'the ask is shared')

    def test_the_no_lupin_arm_spends_a_fourth_a_press_on_an_AUTHORED_break(self):
        """Basil's substitute turn is 74 characters and this is a 29-wide bubble, so it cannot
        be one box. Left flowed, the wrapper chose the A-press and put it mid-clause; the YAML
        now authors two boxes instead. The break lands after the shock, not on the full stop --
        her run-on then arrives whole, which is the Ewan register her bible calls for.

        The arms are not required to be the same length. Only to each stand up."""
        scene = self._scene()
        fallback = inject.scenes.variant_beat(scene['script'], scene['no_lupin_fallback'], 'test')
        self.assertEqual(3, len(scene['script']))
        self.assertEqual(4, len(fallback))
        self.assertEqual("...You're none of hers.", next(iter(fallback[1].values())))
        self.assertTrue(next(iter(fallback[2].values())).startswith('Not one of you.'))
        # and no box of either arm splits under the wrap -- an [A] the AUTHOR did not place
        for _msg, body in inject.chapters.ch05.ch05_basil_join_messages(self._chap()):
            for page in body.split('[A]')[:-1]:
                self.assertLessEqual(len([l for l in page.split('[LF]') if l.strip()]), 2,
                                     'the wrapper paged this box, not the author: %r' % page)

    def test_the_fallback_costs_one_extra_id_not_three(self):
        written = dict(inject.chapters.ch05.ch05_basil_join_messages(self._chap()))
        self.assertEqual({inject.chapter_ids.CH05_BASIL_JOIN_SLOT[1], inject.chapter_ids.CH05_BASIL_JOIN_NO_LUPIN_MSG},
                         set(written), 'one scene, one variant, two ids')

    def test_the_locked_prose_survives_the_wrap(self):
        plain = {m: ' '.join(re.sub(r'\[[^\]]*\]', ' ', b).split())
                 for m, b in inject.chapters.ch05.ch05_basil_join_messages(self._chap())}
        locked = plain[inject.chapter_ids.CH05_BASIL_JOIN_SLOT[1]]
        fallback = plain[inject.chapter_ids.CH05_BASIL_JOIN_NO_LUPIN_MSG]
        self.assertIn('Oh! Tourists', locked)                 # the joke, both arms
        self.assertIn('Oh! Tourists', fallback)
        self.assertIn("You're hers", locked)
        self.assertIn('none of hers', fallback)
        for body in (locked, fallback):
            self.assertIn('Take me to her', body)             # the ask the CUSA answers

    # ── placement in the beginning script ──────────────────────────────────────
    def test_the_join_plays_AFTER_prep_because_the_party_is_PLACED_by_prep(self):
        """The one place scene 5 does not inherit its twin's channel. Vanilla LOAD1s its
        speaking party before the prep CALL; ours arrives through Pick Units, so a beat
        placed there would have Basil addressing an empty pocket."""
        script = self._script()
        prep = script.index('CALL(%s)' % inject.chapters.ch05.CH05_PREP_SCRIPT)
        text = script.index('TEXTSHOW(0x%X)' % inject.chapter_ids.CH05_BASIL_JOIN_SLOT[1])
        self.assertLess(prep, text)
        self.assertLess(text, script.index('CUSA('), 'she asks, then she flips')

    def test_the_beat_fades_up_and_finds_basil_before_it_speaks(self):
        """The shared prep prologue fades to black and leaves it there, so anything VISIBLE
        after the CALL brings its own FADU -- vanilla's 0x9C3 does exactly this. Then the
        bubble needs a unit: PutTalkBubble anchors to whoever the camera holds."""
        script = self._script()
        prep = script.index('CALL(%s)' % inject.chapters.ch05.CH05_PREP_SCRIPT)
        text = script.index('TEXTSHOW(0x%X)' % inject.chapter_ids.CH05_BASIL_JOIN_SLOT[1])
        tail = script[prep:text]
        self.assertIn('FADU(16)', tail)
        self.assertIn('CUMO_CHAR(CHARACTER_ARTUR)', tail)
        self.assertLess(tail.index('FADU(16)'), tail.index('CUMO_CHAR'))
        self.assertIn('CURE', tail)

    def test_the_second_branch_does_not_reuse_the_first_branchs_labels(self):
        """Two branches in ONE event list. `BEQ`/`GOTO` scan the list for a matching LABEL,
        so a second branch left at label_base 0 would jump into the arrival's arms."""
        script = self._script()
        self.assertEqual(2, script.count('CHECK_ALIVE(%s)' % inject.chapters.ch05.CH05_LUPIN_CHARACTER),
                         'the arrival and the join each ask the roster')
        for label in ('LABEL(0x0)', 'LABEL(0x1)', 'LABEL(0x2)', 'LABEL(0x3)'):
            self.assertEqual(1, script.count(label), '%s is not unique' % label)

    def test_exactly_one_arm_of_the_join_plays(self):
        script = self._script()
        locked = script.index('TEXTSHOW(0x%X)' % inject.chapter_ids.CH05_BASIL_JOIN_SLOT[1])
        fallback = script.index('TEXTSHOW(0x%X)' % inject.chapter_ids.CH05_BASIL_JOIN_NO_LUPIN_MSG)
        self.assertLess(script.index('CHECK_ALIVE', script.index('CALL(%s)'
                                     % inject.chapters.ch05.CH05_PREP_SCRIPT)), locked)
        self.assertLess(locked, fallback)
        self.assertIn('GOTO(0x3)', script)

    def test_the_backdrop_half_still_runs_before_LOMA_and_the_join_after(self):
        """Regression on the whole opening's order, which is what a reader loses first."""
        script = self._script()
        order = [script.index(needle) for needle in (
            'Text(0x%X)' % inject.chapter_ids.CH05_OPENING_SLOTS[0][1],       # scene 1, on the backdrop
            'Text(0x%X)' % inject.chapter_ids.CH05_ARRIVAL_SLOT[1],           # scene 4, on the ridge
            'LOMA(',
            'CALL(%s)' % inject.chapters.ch05.CH05_PREP_SCRIPT,
            'TEXTSHOW(0x%X)' % inject.chapter_ids.CH05_BASIL_JOIN_SLOT[1],    # scene 5, on the map
            'CUSA(',
            'TEXTSHOW(0x%X)' % inject.chapter_ids.CH05_SAHNAR_ALONE_SLOT[1])] # scene 6, on the map
        self.assertEqual(sorted(order), order)


class Ch05RavisinRaisesSahnarOnScreen(unittest.TestCase):
    """Scene 3 stages the summon with a PORTRAIT and no dialogue (#25, 2026-08-14).

    The design change that unblocked scene 6 — Sahnar stops being a turn-2 riser and goes on
    the map from turn 1, woken on screen by Ravisin — lands here, and it lands for free: the
    seven locked boxes are untouched and the scene gains an `enters:` directive instead of a
    line. Scene 3's power is that it is QUIET (the inverted-doubt beat, a friend being shut
    down), and a spoken resurrection would have buried it.
    """
    CAMPAIGN = 'rime-of-the-frostmaiden'

    def _chap(self):
        return inject.hosting._load_chapter_yaml(self.CAMPAIGN, inject.chapter_ids.CH05_CHAPTER_YAML)

    def _scene(self):
        return inject.chapters.ch05._chapter_event_by_slot(self._chap(), 'chapter_start', 'vanilla 0x9BD', 'test')

    def _body(self):
        return dict(inject.chapters.ch05.ch05_opening_messages(self._chap()))[0x9EB]

    def test_the_summon_costs_no_box_and_the_lock_is_intact(self):
        script = self._scene()['script']
        self.assertEqual(7, inject.text._script_box_count(script), 'still the seven locked boxes')
        self.assertEqual('sahnar', next(e['present'] for e in script if 'present' in e))
        self.assertNotIn('sahnar', {k for e in script for k in e if k != 'present'},
                         'she is raised, she does not speak -- her first words are scene 6')

    def test_she_is_on_screen_for_the_WHOLE_scene_and_the_contrast_is_the_summon(self):
        """She is staged first, not mid-scene -- the engine allows no other placement (see
        `SilentPresenceDirective`). The beat still reads, because it reads off the CONTRAST:
        absent through scene 2, standing at Ravisin's shoulder through all of scene 3. So
        "It never once occurred to me she might be of use" is an appraisal to her face, and
        "It's not your concern." is said over her."""
        script = self._scene()['script']
        keys = [next(iter(e)) for e in script]
        self.assertEqual(0, keys.index('present'), 'staged before the first box')
        body = self._body()
        plain = ' '.join(re.sub(r'\[[^\]]*\]', ' ', body).split())
        self.assertLess(plain.index("A queen's blade"), plain.index('might be of use'))
        self.assertLess(plain.index('might be of use'), plain.index("It's not your concern"))
        self.assertLess(body.index('[LoadFace][FID_Marisa]'), body.index("A queen's blade"))
        # and she is absent from scene 2, which is what makes her presence here legible at all
        self.assertNotIn('[FID_Marisa]', dict(inject.chapters.ch05.ch05_opening_messages(self._chap()))[0x9EA])

    def test_no_second_bubble__the_silent_face_is_up_before_the_first_box(self):
        """The defect Nicolas caught on film: two stacked speech bubbles, because the first cut
        loaded her mid-message and `TalkPrepNextChar` reopens the bubble whenever the active
        face differs from the speaking one. Preloading leaves the message in vanilla's own
        MSG_0954 shape -- every silent face up front, then text.

        NB an `[A]` followed by `[OpenX][LoadFace]` is NOT the bug and must not be asserted
        against: that is an ordinary speaker change (Basil's, three lines below), it ships in
        every scene we have, and the newly loaded face speaks immediately."""
        body = self._body()
        self.assertTrue(body.startswith('[OpenFarRight][LoadFace][FID_Marisa]\n'
                                        '[OpenRight][LoadFace][FID_Riev]'),
                        'both faces must be up before the first box: %r' % body[:120])
        # nobody is loaded again once the talking starts EXCEPT a speaker taking their own turn
        first_text = body.index("A queen's blade")
        for match in re.finditer(r'\[Open\w+\]\[LoadFace\](\[FID_\w+\])', body):
            if match.start() > first_text:
                self.assertEqual('[FID_Artur]', match.group(1),
                                 'only a speaker may load mid-message, and only to speak next')

    def test_the_raised_face_gets_a_whole_empty_rung_of_elbow_room(self):
        """The defect this scene taught, found by FILMING (2026-08-14). Podiums are a ladder and
        neighbouring rungs OVERLAP; FE8 draws the active speaker on top. For a scene of speakers
        that is harmless -- scene 4 seats four across adjacent rungs and each is drawn over the
        others when its turn comes. A face raised by `enters:` never takes a turn, so on a
        neighbouring rung it stays underneath for the whole scene: Sahnar's first pass put her on
        FarRight beside Ravisin on MidRight, and she played as a hood behind Ravisin's shoulder.

        Ravisin therefore moves to Right, leaving MidRight EMPTY between the two -- vanilla's own
        stable two-face right side (MSG_904, MSG_092C, MSG_0937, MSG_0954)."""
        self.assertEqual({'ravisin': '[OpenRight]', 'sahnar': '[OpenFarRight]'},
                         inject.chapters.ch05.CH05_OPENING_PODIUM_OVERRIDES['vanilla 0x9BD'])
        gap = (inject.chapters.ch05.PODIUM_ORDER.index('[OpenFarRight]') - inject.chapters.ch05.PODIUM_ORDER.index('[OpenRight]'))
        self.assertEqual(2, gap, 'a whole rung must sit empty between them')
        body = self._body()
        self.assertIn('[OpenFarRight][LoadFace][FID_Marisa]', body)
        self.assertIn('[OpenRight][LoadFace][FID_Riev]', body)
        self.assertEqual(1, body.count('[LoadFace][FID_Riev]'))
        self.assertNotIn('[OpenMidRight]', body, 'the rung between them stays empty')
        self.assertNotIn('[ClearFace]', body, 'nobody is evicted: three faces, four slots')

    def test_a_silent_face_next_door_to_a_speaker_is_refused(self):
        """The guard, on the exact shape that shipped wrong."""
        script = [{'ravisin': 'one'}, {'present': 'sahnar'}, {'ravisin': 'two'}]
        inject.chapters.ch05.assert_silent_faces_have_elbow_room(
            script, {'ravisin': '[OpenRight]', 'sahnar': '[OpenFarRight]'}, 'test')
        with self.assertRaises(SystemExit):
            inject.chapters.ch05.assert_silent_faces_have_elbow_room(
                script, {'ravisin': '[OpenMidRight]', 'sahnar': '[OpenFarRight]'}, 'test')

    def test_speakers_may_still_sit_on_adjacent_rungs(self):
        """Scene 4 does exactly this and is shipped and filmed. The rule is about SILENCE, not
        adjacency -- a guard that banned adjacency outright would have rejected it."""
        inject.chapters.ch05.assert_silent_faces_have_elbow_room(
            [{'a': 'x'}, {'b': 'y'}], {'a': '[OpenMidRight]', 'b': '[OpenFarRight]'}, 'test')
        self.assertEqual({'lupin': '[OpenFarLeft]', 'wolfram': '[OpenMidLeft]',
                          'marty': '[OpenMidRight]', 'pinky': '[OpenFarRight]'},
                         inject.chapters.ch05.CH05_ARRIVAL_PODIUMS)

    def test_the_face_arrives_before_basil_asks_after_her(self):
        body = self._body()
        self.assertLess(body.index('[LoadFace][FID_Marisa]'),
                        body.index('What will you do with her?'))
        self.assertLess(body.index('What will you do with her?'),
                        body.index("It's not your concern."))


class Ch05SahnarIsJoshuaAndBasilIsNatasha(unittest.TestCase):
    """Sahnar plays the way vanilla Joshua plays -- INCLUDING his refusal to hit the escort.

    `AI_A_07` is `gAiScript_ActionInRange_ExceptNatasha`. The refusal does not live in the
    `.ai` bytes: `AiScriptCmd_05_DoStandardAction` routes through
    `AiIsUnitEnemyAndNotInScrList`, which tests each candidate's `pCharacterData->number`
    against a list of character ids -- and vanilla's list holds `CHARACTER_NATASHA` literally.
    Copy the bytes alone and `0x7` degrades to plain `AI_A_00`, leaving a fragile Cleric a
    legal target for a Killing Edge. So the list is repointed at Basil.
    """
    CAMPAIGN = 'rime-of-the-frostmaiden'

    def _sahnar(self):
        chap = inject.hosting._load_chapter_yaml(self.CAMPAIGN, inject.chapter_ids.CH05_CHAPTER_YAML)
        return next(e for e in chap['enemy_units'] if e['id'] == 'sahnar')

    def _chap(self):
        return yaml_loader.yaml_load(open(os.path.join(
            inject.decomp.REPO, 'campaigns/rime-of-the-frostmaiden/chapters',
            inject.chapter_ids.CH05_CHAPTER_YAML), encoding='utf-8'))

    def test_she_carries_joshuas_exact_ai_bytes(self):
        # #335: borrowed from vanilla Joshua's own UnitDefinition, not authored.
        self.assertEqual('{0x7, 0x3, 0x9, 0x0}',
                         inject.units.enemy_ai_initialiser(self._chap(), self._sahnar()))

    def test_the_list_has_exactly_one_client_which_is_what_makes_it_safe(self):
        """`.ai = {0x7,` appears ONCE in all of FE8 -- `UnitDef_088B5914`, vanilla Ch5's
        Joshua. Read from decomp HEAD, never the built tree, which holds our injections."""
        udefs = inject.decomp.vanilla_decomp_text('src/events_udefs.c')
        self.assertEqual(1, udefs.count('.ai = {0x7,'))
        inject.chapters.ch05.assert_escort_safe_ai_has_one_client('{0x7, 0x3, 0x9, 0x0}')

    def test_a_second_client_in_ANY_chapter_is_refused(self):
        """The list is global, so the hazard is another chapter's unit reaching for `{0x7,`
        on its own account. Since #335 the sweep reads the AI every enemy actually EMITS
        rather than a table of labels -- which also catches a unit that inherits AI_A_07
        from its vanilla DONOR, a case the old table scan could not see at all."""
        planted = {'id': 'interloper', 'ai_override': {'ai': '{0x7, 0x3, 0x9, 0x0}',
                                                       'why': 'test'}}
        real = inject.chapters.ch05.escort_safe_ai_clients
        with stubbed('escort_safe_ai_clients', lambda: real() + ['ch04.interloper']):
            with self.assertRaises(SystemExit):
                inject.chapters.ch05.assert_escort_safe_ai_has_one_client('{0x7, 0x3, 0x9, 0x0}')
        self.assertIsNotNone(planted)

    def test_the_sweep_reads_every_chapter_and_finds_exactly_our_duelist(self):
        self.assertEqual(inject.chapters.ch05.escort_safe_ai_clients(), ['ch05.sahnar'])

    def test_the_repoint_swaps_natasha_for_our_escort_and_keeps_the_shape(self):
        """`AiIsInShortList` takes `const u16*` and stops on a zero entry, so the u8 array
        `{ id, 0, 0, 0 }` is the two-entry short list `{ id, TERMINATOR }`. Keep the shape."""
        vanilla = ('u8 CONST_DATA %s[] = { CHARACTER_NATASHA, 0, 0, 0 };'
                   % inject.chapters.ch05.ESCORT_SAFE_AI_LIST)
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, 'cp_data.c')
            with open(path, 'w', encoding='utf-8') as f:
                f.write('/* head */\n%s\n/* tail */\n' % vanilla)
            with stubbed('CP_DATA_C', path):
                inject.chapters.ch05.repoint_escort_safe_ai_list('CHARACTER_ARTUR', 'test escort')
                patched = open(path, encoding='utf-8').read()
                self.assertIn('u8 CONST_DATA %s[] = { CHARACTER_ARTUR, 0, 0, 0 };'
                              % inject.chapters.ch05.ESCORT_SAFE_AI_LIST, patched)
                self.assertNotIn('CHARACTER_NATASHA', patched)
                # NON-IDEMPOTENT ON PURPOSE: a second run has nothing to match, and a silent
                # pass would ship an unprotected escort. cp_data.c is in PATCHED_DECOMP_FILES
                # so it is restored from HEAD each build.
                with self.assertRaises(SystemExit):
                    inject.chapters.ch05.repoint_escort_safe_ai_list('CHARACTER_ARTUR', 'test escort')

    def test_cp_data_is_restored_from_HEAD_every_build(self):
        self.assertIn('src/cp_data.c', inject.warm.PATCHED_DECOMP_FILES)


class Ch05SahnarAloneOnTheArena(unittest.TestCase):
    """Scene 6 -- Sahnar alone at the sarcophagus, as a PLAIN ON-MAP BUBBLE (#25).

    This scene was the opening's problem child for exactly as long as Sahnar was a turn-2
    riser: with nothing of hers on the field, no talk bubble had a unit to anchor to, and the
    standing note priced it as needing a BACKDROP of its own -- the one place the twin was
    said to fail us. Nicolas's 2026-08-14 call moved her summon into scene 3, which puts her
    on the arena tile from turn 1 exactly as vanilla's `UnitDef_088B5914` puts Joshua there,
    and the exception evaporated. The beat is now vanilla's 0x9C3 down to the camera move, and
    all six locked boxes are untouched.
    """
    CAMPAIGN = 'rime-of-the-frostmaiden'

    def _chap(self):
        return inject.hosting._load_chapter_yaml(self.CAMPAIGN, inject.chapter_ids.CH05_CHAPTER_YAML)

    def _scene(self):
        slot, _msg, _boxes, _what = inject.chapter_ids.CH05_SAHNAR_ALONE_SLOT
        return inject.chapters.ch05._chapter_event_by_slot(self._chap(), 'chapter_start', slot, 'test')

    def _script(self):
        return inject.chapters.ch05.ch05_beginning_script(self._chap(), 'CHARACTER_ARTUR',
                                        inject.chapters.ch05.CH05_SAHNAR_TABLE, 'CHARACTER_MARISA')

    # ── the id ─────────────────────────────────────────────────────────────────
    def test_the_id_is_0x9F0_owned_unique_and_inside_ch05s_host_block(self):
        _slot, msg, _boxes, _what = inject.chapter_ids.CH05_SAHNAR_ALONE_SLOT
        self.assertEqual(0x9F0, msg, "#25's allocation table")
        self.assertTrue(0x9E4 <= msg <= 0x9F5, "outside ch05's Ch6 host block")
        self.assertIn(msg, set(inject.messages.HOSTED_CHAPTER_MESSAGE_IDS['ch05']))
        self.assertEqual('ch05', inject.messages.assert_message_ids_unique()[msg])

    def test_the_yaml_slot_label_stays_an_anatomy_citation(self):
        """`vanilla 0x9C3` names the scene we MINE -- Joshua's own solo beat on this tile."""
        slot, msg, _boxes, _what = inject.chapter_ids.CH05_SAHNAR_ALONE_SLOT
        self.assertNotEqual(int(slot.split()[1], 16), msg)

    def test_it_costs_ONE_id_because_she_never_mentions_the_wolf(self):
        self.assertNotIn('no_lupin_fallback', self._scene())
        self.assertEqual(1, len(inject.chapters.ch05.ch05_sahnar_alone_message(self._chap())))

    # ── the channel ────────────────────────────────────────────────────────────
    def test_the_body_wraps_at_the_bubble_29_not_the_scenic_42(self):
        """It rides TEXTSHOW -> PutTalkBubble, whose right-side branch computes x = 29 - width
        with no clamp: a line over 29 runs off the tilemap (the ch03 crier bug)."""
        for _msg, body in inject.chapters.ch05.ch05_sahnar_alone_message(self._chap()):
            for line in body.split('\n'):
                printable = re.sub(r'\[[^\]]*\]', '', line)
                self.assertLessEqual(font.text_px(printable), font.TALK_BUDGET_PX,
                                     'bubble overflow: %r' % line)

    def test_she_keeps_the_mid_right_she_holds_in_scene_1_and_the_talk(self):
        """A character who changes seats between her scenes reads as a different person --
        and mid-right is also the podium vanilla's own 0x9C3 gives Joshua on this tile."""
        self.assertEqual({'sahnar': '[OpenMidRight]'}, inject.chapters.ch05.CH05_SAHNAR_ALONE_PODIUMS)
        for _msg, body in inject.chapters.ch05.ch05_sahnar_alone_message(self._chap()):
            self.assertIn('[OpenMidRight][LoadFace][FID_Marisa]', body)
            self.assertNotIn('[FID_Joshua]', body)      # her STAT_DONOR, never her face

    def test_every_locked_word_survives_the_staging_change(self):
        """The scene moved from a 42-wide backdrop to a 29-wide bubble. What that is allowed
        to cost is an A-PRESS; what it is not allowed to cost is a word."""
        self.assertEqual(['sahnar'] * 7, [next(iter(b)) for b in self._scene()['script']])
        plain = ' '.join(re.sub(r'\[[^\]]*\]', ' ',
                                inject.chapters.ch05.ch05_sahnar_alone_message(self._chap())[0][1]).split())
        for locked in ('...Someone has come.',
                       'Four thousand years, and someone has finally come.',
                       '...I was given a purpose. To defend this tomb.',
                       'No one ever came. I stopped counting somewhere in the middle.',
                       '...Well. Something has come now.',
                       'I will defend this tomb. It is my purpose.'):
            self.assertIn(locked, plain, 'the 2026-07-29 lock lost a word')

    def test_the_one_box_that_cannot_fit_29_breaks_where_the_AUTHOR_put_it(self):
        """"No one ever came. I stopped counting somewhere in the middle." is 60 characters:
        three lines at the bubble's 29, and a box holds two. Left flowed, the wrapper picked
        the A-press and split it mid-clause ("...somewhere in the" / "middle."). The break is
        authored at the full stop, so the understatement gets its own press."""
        self.assertEqual(7, inject.chapter_ids.CH05_SAHNAR_ALONE_SLOT[2])
        boxes = [next(iter(b.values())) for b in self._scene()['script']]
        self.assertEqual('No one ever came.', boxes[3])
        self.assertEqual('I stopped counting somewhere in the middle.', boxes[4])
        body = inject.chapters.ch05.ch05_sahnar_alone_message(self._chap())[0][1]
        self.assertEqual(7, body.count('[A]'))
        # and NO box of the scene splits under the wrap -- an [A] the author did not place
        for page in body.split('[A]')[:-1]:
            self.assertLessEqual(len([l for l in page.split('[LF]') if l.strip()]), 2,
                                 'the wrapper paged this box, not the author: %r' % page)

    # ── placement in the beginning script ──────────────────────────────────────
    def test_the_camera_frames_the_arena_BEFORE_she_loads(self):
        """Vanilla's order, and it is the whole reveal: CUMO_AT the tile, hold, and only then
        LOAD1, so the player watches the duelist arrive instead of finding her there."""
        script = self._script()
        x, y = next(e for e in self._chap()['enemy_units']
                    if e['id'] == 'sahnar')['positions'][0]
        self.assertEqual((12, 6), (x, y), "vanilla Joshua's own tile, which is the arena")
        cumo = script.index('CUMO_AT(%d, %d)' % (x, y))
        load = script.index('LOAD1(0x1, %s)' % inject.chapters.ch05.CH05_SAHNAR_TABLE)
        text = script.index('TEXTSHOW(0x%X)' % inject.chapter_ids.CH05_SAHNAR_ALONE_SLOT[1])
        self.assertLess(cumo, load)
        self.assertLess(load, script.index('CUMO_CHAR(CHARACTER_MARISA)'))
        self.assertLess(script.index('CUMO_CHAR(CHARACTER_MARISA)'), text)

    def test_the_arena_framing_is_a_CAMERA_and_not_an_inherited_corner(self):
        """`CUMO_AT` draws a cursor and never scrolls (`EventDisplayCursor_Loop` ->
        `PutMapCursor`). This beat had no CAMERA at all and was framed by whatever `LOMA` left
        -- the map's north-west, which happens to hold the arena. It filmed correctly and was
        resting on an accident; anything that moved the reload origin would have played the
        scene off-screen with no error to read. Vanilla pairs the two here too."""
        script = self._script()
        x, y = inject.chapters.ch05.ch05_sahnar_station(self._chap())[0]
        self.assertIn('CAMERA(%d, %d)' % (x, y), script)
        self.assertLess(script.index('CAMERA(%d, %d)' % (x, y)),
                        script.index('CUMO_AT(%d, %d)' % (x, y)),
                        'the scroll comes before the pointer')

    def test_she_WALKS_OFF_the_arena_tile_or_the_chapter_loses_its_arena(self):
        """The regression this slice shipped and code review caught. (12,6) is
        TERRAIN_ARENA_REGULAR *and* the arena tutorial's own `AREA(..., 12, 6, 12, 6)` trigger,
        so a hostile parked there makes the arena unenterable for the entire chapter and
        silently kills the `arena-wager` debut (#264/#265). Vanilla walks Joshua off it the
        instant he lands (`MOVE(0x0, CHARACTER_JOSHUA, 9, 7)`); dropping that MOVE as
        'deliberate' is what broke it."""
        load, guard = inject.chapters.ch05.ch05_sahnar_station(self._chap())
        self.assertEqual((12, 6), load, "vanilla Joshua's LOAD tile, which is the arena")
        self.assertEqual((9, 7), guard, "vanilla Joshua's walk-off tile")
        self.assertNotEqual(load, guard, 'she may not end where she lands')
        script = self._script()
        self.assertIn('MOVE(0x0, CHARACTER_MARISA, 9, 7)', script)
        self.assertLess(script.index('LOAD1(0x1, %s)' % inject.chapters.ch05.CH05_SAHNAR_TABLE),
                        script.index('MOVE(0x0, CHARACTER_MARISA, 9, 7)'))
        self.assertLess(script.index('MOVE(0x0, CHARACTER_MARISA, 9, 7)'),
                        script.index('TEXTSHOW(0x%X)' % inject.chapter_ids.CH05_SAHNAR_ALONE_SLOT[1]),
                        'she is off the arena before she speaks')

    def test_a_missing_walk_off_is_refused_rather_than_shipped(self):
        chap = self._chap()
        sahnar = next(e for e in chap['enemy_units'] if e['id'] == 'sahnar')
        del sahnar['walks_to']
        with self.assertRaises(SystemExit):
            inject.chapters.ch05.ch05_sahnar_station(chap)

    def test_the_escort_is_measured_to_where_she_actually_STANDS(self):
        """Basil's walk is checked against Sahnar's fighting tile, not her load tile -- they
        are different tiles now, and the load tile is one she is never on when the Talk
        happens."""
        src = injector.injector_source()
        self.assertIn('must_reach=ch05_sahnar_station(chap)[1]', src)

    def test_she_loads_ONCE_and_after_prep_where_vanilla_loads_joshua(self):
        script = self._script()
        self.assertEqual(1, script.count('LOAD1(0x1, %s)' % inject.chapters.ch05.CH05_SAHNAR_TABLE))
        self.assertLess(script.index('CALL(%s)' % inject.chapters.ch05.CH05_PREP_SCRIPT),
                        script.index('LOAD1(0x1, %s)' % inject.chapters.ch05.CH05_SAHNAR_TABLE))

    def test_it_brings_no_second_fade_up_because_scene_5_already_did(self):
        """The prep prologue leaves the screen black and scene 5 pays the FADU for both. A
        second one here would flash the map back through black between two adjacent beats."""
        script = self._script()
        # Bounded at scene 7's first box: the bellow AFTER it brings a deliberate fade cycle
        # of its own (a full-screen CG over the map), which is not this scene's business.
        gap = script[script.index('TEXTSHOW(0x%X)' % inject.chapter_ids.CH05_BASIL_JOIN_SLOT[1]):
                     script.index('TEXTSHOW(0x%X)' % inject.chapter_ids.CH05_MOOSE_CHARGE_SLOT[1])]
        self.assertNotIn('FADU', gap)
        self.assertNotIn('FADI', gap)


class Ch05TheMooseCharges(unittest.TestCase):
    """Scene 7 -- the last beat before turn 1: Pinky asks, and the moose answers (#25).

    Two things are being protected here, and neither is the text.

    The first is the ID. The beat is a setup and a punchline across a WORDLESS action, which
    normally means two messages and two hosted ids -- and #25's allocation has exactly one
    spare left. `stage_cut:` renders vanilla's own `[BreakTalk]`, a pause the event script
    resumes with `TEXTCONT`, so the gap costs nothing.

    The second is the moose's POSITION. Its pen at (10,0) is parity-locked (threat 14.1,
    cornered against the map's top edge) and the charge is a cutscene lunge, not a placement:
    it runs out and is snapped back off camera before the fight starts. Nicolas asked for the
    charge to LAND on the start tile; row 0 is the map's top edge, so there is no tile behind
    it to come from, and forward-and-checked is the same net-zero the other way round.
    """
    CAMPAIGN = 'rime-of-the-frostmaiden'

    def _chap(self):
        return inject.hosting._load_chapter_yaml(self.CAMPAIGN, inject.chapter_ids.CH05_CHAPTER_YAML)

    def _scene(self):
        slot, _msg, _boxes, _what = inject.chapter_ids.CH05_MOOSE_CHARGE_SLOT
        return inject.chapters.ch05._chapter_event_by_slot(self._chap(), 'chapter_start', slot, 'test')

    def _body(self):
        return ''.join(b for _m, b in inject.chapters.ch05.ch05_moose_charge_message(self._chap()))

    def _script(self):
        return inject.chapters.ch05.ch05_beginning_script(self._chap(), 'CHARACTER_ARTUR',
                                        inject.chapters.ch05.CH05_SAHNAR_TABLE, 'CHARACTER_MARISA')

    # ── the id ─────────────────────────────────────────────────────────────────
    def test_the_id_is_0x9F1_owned_unique_and_inside_ch05s_host_block(self):
        _slot, msg, _boxes, _what = inject.chapter_ids.CH05_MOOSE_CHARGE_SLOT
        self.assertEqual(0x9F1, msg, "#25's allocation table")
        self.assertTrue(0x9E4 <= msg <= 0x9F5, "outside ch05's Ch6 host block")
        self.assertIn(msg, set(inject.messages.HOSTED_CHAPTER_MESSAGE_IDS['ch05']))
        self.assertEqual('ch05', inject.messages.assert_message_ids_unique()[msg])

    def test_the_yaml_slot_label_stays_an_anatomy_citation(self):
        """`vanilla 0x9C4` names the scene we MINE -- Natasha alone before the map. We take
        its POSITION and not its content, and we never write that id."""
        slot, msg, _boxes, _what = inject.chapter_ids.CH05_MOOSE_CHARGE_SLOT
        self.assertNotEqual(int(slot.split()[1], 16), msg)

    def test_the_wordless_beat_costs_no_second_id(self):
        """The whole reason `stage_cut:` exists. Two boxes with an engine action between
        them is ONE message with a `[BreakTalk]`, not two messages with two ids."""
        ids = [m for m, _b in inject.chapters.ch05.ch05_moose_charge_message(self._chap())]
        self.assertEqual([inject.chapter_ids.CH05_MOOSE_CHARGE_SLOT[1], inject.chapter_ids.CH05_MOOSE_QUIP_MSG], ids)
        for i in ids:
            self.assertIn(i, set(inject.messages.HOSTED_CHAPTER_MESSAGE_IDS['ch05']))
            self.assertEqual('ch05', inject.messages.assert_message_ids_unique()[i])

    def test_a_scene_that_loses_its_stage_cut_is_refused(self):
        """Without the pause the two boxes run together and the charge plays after both --
        the joke told backwards, and nothing else would notice."""
        chap = self._chap()
        slot = inject.chapter_ids.CH05_MOOSE_CHARGE_SLOT[0]
        event = inject.chapters.ch05._chapter_event_by_slot(chap, 'chapter_start', slot, 'test')
        event['script'] = [e for e in event['script'] if 'stage_cut' not in e]
        with self.assertRaises(SystemExit):
            inject.chapters.ch05.ch05_moose_charge_message(chap)

    def test_the_bellow_is_a_full_screen_CG_and_not_a_portrait(self):
        """Nicolas's art and Nicolas's idea (2026-08-15): the moose fills the screen between
        Pinky's question and the run. It is a BACG rather than a bust for the reason he raised
        himself -- a 96x80 portrait is drawn inside the talk window's envelope and those antlers
        do not fit it, while a BACG owns all 240x160 and has no envelope at all."""
        block = inject.chapters.ch05.ch05_moose_charge_block(inject.chapter_ids.CH05_MOOSE_PID,
                                           inject.chapters.ch05.ch05_moose_station(self._chap()),
                                           inject.chapters.ch05.ch05_party_camera_tile(self._chap()))
        self.assertIn('BACG(%s)' % inject.chapters.ch05.CH05_MOOSE_BELLOW_BG, block)
        self.assertIn((inject.chapters.ch05.CH05_MOOSE_BELLOW_BG, 'bg_WhiteMoose', '{Nicolas}'), inject.backgrounds.CAMPAIGN_BGS)
        # REMOVEPORTRAITS does double duty: it re-arms the BACG load mode (without it the BG
        # is a no-op -- the ch03/ch04 stale-BG bug) AND clears the faces, so the CG comes up
        # on a clean screen instead of behind Pinky's bust.
        self.assertLess(block.index('REMOVEPORTRAITS'), block.index('BACG('))
        # CLEAN is the restore, and it is the bit that was missing: without it the map comes
        # back wearing the CG's PALETTE (filmed 2026-08-15 -- a snowfield in moose-red).
        # `EventScr_RemoveBGIfNeeded` only does a conditional FADU and cannot do this job.
        # Vanilla's own order, from EventScr_TextShowWithFadeIn: FADI -> CLEAN -> FADU.
        bell = block[block.index('BACG('):]
        self.assertIn('CLEAN', bell)
        # order on the way out: fade the image down, CLEAN, fade the map up
        self.assertLess(bell.index('FADI'), bell.index('CLEAN'))
        self.assertLess(bell.index('CLEAN'), bell.rindex('FADU'))

    def test_the_bellow_SHAKES_and_that_is_our_first_authored_sound(self):
        """Nicolas asked for weight (2026-08-15). `EARTHQUAKE_START(0, 1)` gives both halves in
        one command: the shake, and `playse` firing vanilla's SONG_26A rumble -- the first sound
        effect this project has ever authored, everything else being vanilla's out of the box.

        WHAT it shakes is chosen by `activeTextType` rather than by us: `Event42_EarthQuake`
        maps 0/3/4 to a camera shake and 1 to a BG-position shake, and `REMOVEPORTRAITS` sets
        it to 1 -- so the judder lands on the BG layer, which at that moment IS the moose.
        Values 2 and 5 return EVC_ERROR, which does not advance the event and therefore hangs
        the chapter, so the ordering here is load-bearing rather than tidy."""
        block = inject.chapters.ch05.ch05_moose_charge_block(inject.chapter_ids.CH05_MOOSE_PID,
                                           inject.chapters.ch05.ch05_moose_station(self._chap()),
                                           inject.chapters.ch05.ch05_party_camera_tile(self._chap()))
        # The ANIMAL first, then the weight under it. Vanilla names almost none of its ~340
        # SFX, so the cry was found by asking what a CREATURE plays rather than by reading the
        # song table: `banim_code_sound_mauthedoog_roar` is 0x75, commented "low cry", and the
        # Mauthe Doog is CLASS_GWYLLGI -- the class the moose wears. Its own voice.
        self.assertIn('SOUN(%s)' % inject.chapters.ch05.CH05_MOOSE_BELLOW_SFX, block)
        # 0x32C = song812_mon_mdg_critical1, picked by ear off tools/sfx_preview.py. The id
        # space matters more than the value: `banim_code_sound_*` is NOT the song table, and
        # reading it as one auditioned an HP-bar tick as a monster roar.
        self.assertEqual('0x32C', inject.chapters.ch05.CH05_MOOSE_BELLOW_SFX)
        self.assertLess(block.index('SOUN('), block.index('EARTHQUAKE_START'))
        self.assertLess(block.index('BACG('), block.index('SOUN('), 'it roars once seen')
        # playse OFF: StartEventEarthQuake fires PlaySoundEffect(SONG_26A) the instant it
        # starts, on the same channel, so with it ON the rumble preempts the roar and the
        # animal is never heard. And END fades the SE channel, so it must not land mid-cry.
        self.assertIn('EARTHQUAKE_START(0, 0)', block, 'the 0 keeps the rumble off the roar')
        self.assertNotIn('EARTHQUAKE_START(0, 1)', block)
        self.assertIn('EARTHQUAKE_END', block, 'an unended quake shakes the whole chapter')
        q, e = block.index('EARTHQUAKE_START'), block.index('EARTHQUAKE_END')
        self.assertLess(block.index('REMOVEPORTRAITS'), q,
                        'activeTextType must be 1 (BG shake) before the quake, not 2/5 (HANG)')
        self.assertLess(block.index('BACG('), q, 'the image is up before it shakes')
        self.assertLess(q, e)
        self.assertLess(e, block.index('CLEAN'), 'it settles before the screen changes back')
        self.assertLess(block.index('STAL(90)'), e, 'the cry plays out BEFORE the SE fade')
        self.assertLess(block.index('SOUN('), block.index('EARTHQUAKE_START'))

    def test_the_music_DUCKS_and_comes_back(self):
        """The bug behind this test shipped in every film until Nicolas asked whether the music
        returns (2026-08-15): the bellow used `MUSCMID(SONG_SILENT)`, which is not a duck at
        all -- it fades the "silent song" IN and replaces the BGM for good. Nothing restored it,
        so the chapter ran from turn 1 in silence, and no assertion or playtest verdict looks at
        audio. Vanilla never ends a beginning scene on silence; ch05's own reliquary visits use
        the real pair, `MUSI` (EvtSetVolumeDown) and `MUNO` (EvtUnsetVolumeDown)."""
        script = self._script()
        beat = script[script.index('TEXTSHOW(0x%X)' % inject.chapter_ids.CH05_MOOSE_CHARGE_SLOT[1]):]
        self.assertIn('MUSI', beat, 'the music ducks under the cry')
        self.assertIn('MUNO', beat, 'a duck with no un-duck is silence for the rest of the map')
        self.assertLess(beat.index('MUSI'), beat.index('MUNO'))
        self.assertNotIn('SONG_SILENT', script,
                         'that is a replacement, not a duck, and it has no way back')

    def test_the_opening_never_ENDS_on_silence(self):
        """Whatever the opening does to the music, the map has to inherit something playing --
        the generalised form of the bug above, and cheap to keep true."""
        script = self._script()
        ducks = script.count('MUSI')
        self.assertEqual(ducks, script.count('MUNO'), 'every duck is paired')
        self.assertIn('MUSC(', script, 'something starts a song')

    def test_the_bellow_carries_no_text_but_DOES_cost_the_last_spare_id(self):
        """The image itself is wordless. What costs an id is that a scene change tears the talk
        down, so the punchline cannot resume the question's message and becomes its own --
        0x9D2, ch05's one spare. The block is now exactly spent; do not assume slack."""
        block = inject.chapters.ch05.ch05_moose_charge_block(inject.chapter_ids.CH05_MOOSE_PID,
                                           inject.chapters.ch05.ch05_moose_station(self._chap()),
                                           inject.chapters.ch05.ch05_party_camera_tile(self._chap()))
        bellow = block[block.index('REMOVEPORTRAITS'):block.index('MOVE_DEFINED')]
        for texty in ('Text_BG', 'TEXTSHOW', 'TEXTSTART'):
            self.assertNotIn(texty, bellow, 'the IMAGE itself carries no text')

    def test_the_bellow_lands_BETWEEN_the_question_and_the_run(self):
        """Nicolas's order, verbatim: "pinky's why isn't he running -> *moose bellows* ->
        *moose runs* -> meesmickle quip"."""
        block = inject.chapters.ch05.ch05_moose_charge_block(inject.chapter_ids.CH05_MOOSE_PID,
                                           inject.chapters.ch05.ch05_moose_station(self._chap()),
                                           inject.chapters.ch05.ch05_party_camera_tile(self._chap()))
        self.assertLess(block.index('TEXTSHOW('), block.index('BACG('), 'question, then bellow')
        self.assertLess(block.index('BACG('), block.index('MOVE_DEFINED'), 'bellow, then run')
        self.assertLess(block.index('MOVE_DEFINED'), block.index('TEXTSHOW(0x%X)' % inject.chapter_ids.CH05_MOOSE_QUIP_MSG), 'run, then quip')

    def test_the_CG_fits_the_SIX_banks_the_fade_procs_apply(self):
        """It fades in and out, and the fade/transition procs only apply six palettes -- the
        rule Bremen's unreferenced 8-bank CG exists to teach. Asserted on the committed asset."""
        png = os.path.join(inject.decomp.REPO, 'campaigns', self.CAMPAIGN, 'backgrounds',
                           'bg_WhiteMoose.png')
        im = Image.open(png)
        self.assertEqual((240, 160), im.size)
        self.assertEqual('P', im.mode)
        banks = {im.getpixel((x * 8, y * 8)) // 16
                 for x in range(240 // 8) for y in range(160 // 8)}
        self.assertLessEqual(max(banks) + 1, 6,
                             'a 7th/8th bank would not survive the fade')

    def test_the_talk_is_ENDED_before_the_screen_changes(self):
        """Nicolas, watching the first film (2026-08-15): "he runs under it and he's covered".
        `[BreakTalk]` only LOCKS the talk proc, so the last speaker's box hangs over the whole
        action. `[CloseSpeechSlow]` is `ClearTalkBubble()` and nothing else -- faces stay loaded
        and the talk state survives, so `TEXTCONT` brings the window back for Meesmickle."""
        # Superseded by the CUT: with a full-screen bellow between them the talk ENDS after
        # the question (REMA) rather than pausing, so the bubble comes down on its own and the
        # punchline is a fresh message. `[CloseSpeechSlow]` is kept for `stage_break` scenes.
        script = self._script()
        beat = script[script.index('TEXTSHOW(0x%X)' % inject.chapter_ids.CH05_MOOSE_CHARGE_SLOT[1]):]
        self.assertLess(beat.index('REMA'), beat.index('BACG('),
                        'the talk is down before the screen changes')
        self.assertNotIn('[BreakTalk]', self._body())

    def test_a_break_between_two_turns_by_ONE_speaker_is_refused(self):
        """The bubble reopens on `!TalkHasCorrectBubble()`, which compares the speaking face
        slot and width -- so a break with the same speaker on both sides resumes onto a bubble
        the engine still believes is correct and prints into a cleared window. It would look
        like the text simply vanished, which is not a thing to discover on film."""
        script = [{'pinky': 'One.'}, {'stage_cut': 'business'}, {'pinky': 'Two.'}]
        staging = {'pinky': ('[OpenMidLeft]', '[FID_Neimi]')}
        with self.assertRaises(SystemExit):
            inject.text._script_to_message(script, staging)
        with self.assertRaises(SystemExit):      # ...and a break with nothing after it
            inject.text._script_to_message([{'pinky': 'One.'}, {'stage_cut': 'business'}],
                                  staging)

    def test_a_stage_break_is_a_pause_and_not_a_box(self):
        """Scene box counts are locked and asserted against the YAML, so a directive that
        counted as an A-press would make every such assertion off by one."""
        self.assertIn('stage_cut', inject.text.SCRIPT_DIRECTIVES)
        self.assertEqual(2, inject.chapter_ids.CH05_MOOSE_CHARGE_SLOT[2])
        self.assertEqual(3, len(self._scene()['script']))    # two boxes and the direction
        self.assertEqual(2, inject.text._script_box_count(self._scene()['script']))
        self.assertEqual(2, self._body().count('[A]'))

    def test_the_stage_direction_lives_in_the_data_not_in_a_comment(self):
        """It is the middle beat of the scene, so it is authored where the other two are."""
        direction = next(e['stage_cut'] for e in self._scene()['script']
                         if 'stage_cut' in e)
        for locked in ('BELLOWS', 'comes', 'straight at them'):
            self.assertIn(locked, direction)

    # ── the channel ────────────────────────────────────────────────────────────
    def test_the_body_wraps_at_the_bubble_29_not_the_scenic_42(self):
        for line in self._body().split('\n'):
            printable = re.sub(r'\[[^\]]*\]', '', line)
            self.assertLessEqual(font.text_px(printable), font.TALK_BUDGET_PX,
                                     'bubble overflow: %r' % line)

    def test_both_locked_boxes_survive_word_for_word(self):
        self.assertEqual(['pinky', 'stage_cut', 'meesmickle'],
                         [next(iter(b)) for b in self._scene()['script']])
        plain = ' '.join(re.sub(r'\[[^\]]*\]', ' ', self._body()).split())
        for locked in ("...It's not running. Why isn't it running?!", 'You had to ask?'):
            self.assertIn(locked, plain, 'the 2026-07-29 lock lost a word')

    def test_pinky_keeps_the_far_right_he_holds_in_the_arrival(self):
        """He closes scene 4 on either arm and opens this one; a character who changes seats
        between his scenes reads as a different person each time. Meesmickle takes the widest
        two-shot the ladder offers against it, so setup and punchline come from opposite sides."""
        self.assertEqual(inject.chapters.ch05.CH05_ARRIVAL_PODIUMS['pinky'],
                         inject.chapters.ch05.CH05_MOOSE_CHARGE_PODIUMS['pinky'])
        seats = [inject.chapters.ch05.PODIUM_ORDER.index(p) for p in inject.chapters.ch05.CH05_MOOSE_CHARGE_PODIUMS.values()]
        self.assertGreater(abs(seats[0] - seats[1]), 1, 'neighbouring rungs overlap')
        self.assertIn('[OpenFarRight][LoadFace][FID_Neimi]', self._body())
        self.assertIn('[OpenMidLeft][LoadFace][FID_Gilliam]', self._body())

    # ── the charge ─────────────────────────────────────────────────────────────
    def test_the_charge_is_net_zero_so_the_fight_starts_where_parity_says(self):
        """It breaks out of the pen on screen and is put straight back. The pen is the tile
        the difficulty read is grounded on -- a charge that RELOCATED it would move a threat-14
        monster four tiles closer to the party for free."""
        pen, start, route = inject.chapters.ch05.ch05_moose_station(self._chap())
        self.assertEqual((10, 0), pen, "the parity-locked pen, vanilla's own rim tile")
        self.assertNotEqual(pen, route[-1], 'a charge that goes nowhere is not a charge')
        script = self._script()
        put = script.index('MOVE(0xffff, %s, %d, %d)' % (inject.chapter_ids.CH05_MOOSE_PID, *start))
        run = script.index('MOVE_DEFINED(%s)' % inject.chapter_ids.CH05_MOOSE_PID)
        back = script.index('MOVE(0xffff, %s, %d, %d)' % (inject.chapter_ids.CH05_MOOSE_PID, *pen))
        self.assertLess(put, run, 'it is placed before it runs')
        # ...and the placement happens where NOTHING CAN SEE IT. It used to sit inside the
        # beat with the screen already up, and Nicolas caught the teleport on film
        # (2026-08-15). An instant move is only invisible if nothing is looking.
        self.assertLess(put, script.index('CALL(%s)' % inject.chapters.ch05.CH05_PREP_SCRIPT),
                        'the corner placement is behind the opening fade, before prep')
        self.assertLess(run, script.index('TEXTSHOW(0x%X)' % inject.chapter_ids.CH05_MOOSE_QUIP_MSG), 'it charges BEFORE the punchline')
        self.assertLess(script.index('TEXTSHOW(0x%X)' % inject.chapter_ids.CH05_MOOSE_QUIP_MSG), back, 'and is snapped back after it')

    def test_the_run_is_an_authored_multi_leg_route_not_one_MOVE(self):
        """Lengthened 2026-08-15 (Nicolas): four tiles straight down was over before it read.
        The path is the beat now -- top-right corner, left along the rim, then down at the
        party -- so it is a REDA queue, which turns where the author says rather than wherever
        the pathfinder cuts the corner. Row 0's walkable stretch is only x=10..14, which is what
        makes the corner start legal at all."""
        pen, start, route = inject.chapters.ch05.ch05_moose_station(self._chap())
        self.assertEqual((14, 0), start, 'the top-right corner')
        self.assertEqual(((10, 0), (10, 4)), route, 'left along the rim, then down')
        self.assertGreater(len(route), 1, 'a single leg is the straight line this replaced')
        self.assertIn(pen, route, 'the run passes THROUGH the pen it is hauled back to')
        script = self._script()
        for x, y in route:                       # one REDA pair per waypoint
            self.assertIn('SVAL(EVT_SLOT_1, 0x%X)' % ((y << 6) | x), script)
        self.assertNotIn('MOVE(0x0, %s' % inject.chapter_ids.CH05_MOOSE_PID, script)

    def test_a_route_ending_on_the_pen_is_refused(self):
        """Then the snap-back is a no-op and the lunge is never undone on screen -- the run is
        meant to pass the pen and keep going at the party."""
        chap = self._chap()
        moose = next(e for e in chap['enemy_units'] if e['id'] == 'white-moose')
        moose['charge_route'] = [[10, 0]]
        with self.assertRaises(SystemExit):
            inject.chapters.ch05.ch05_moose_station(chap)

    def test_both_repositions_are_instant_and_unseen(self):
        """`Event2F_MoveUnit` short-circuits a negative speed to a bare `MoveUnit_` -- vanilla's
        own off-screen reposition (`ch14a` resets Carlyle with `MOVE(0xffff, ...)`). The first
        lands before the camera arrives, the second after it has cut south to the party, so
        neither is ever on screen."""
        script = self._script()
        pen, start, _route = inject.chapters.ch05.ch05_moose_station(self._chap())
        party = inject.chapters.ch05.ch05_party_camera_tile(self._chap())
        put = script.index('MOVE(0xffff, %s, %d, %d)' % (inject.chapter_ids.CH05_MOOSE_PID, *start))
        back = script.index('MOVE(0xffff, %s, %d, %d)' % (inject.chapter_ids.CH05_MOOSE_PID, *pen))
        self.assertLess(put, script.index('CAMERA(%d, %d)' % start),
                        'placed before the camera gets there')
        # The corner placement is out of the BEAT entirely -- the beat's only instant move is
        # the snap back at the end. That is what keeps it off screen.
        beat = inject.chapters.ch05.ch05_moose_charge_block(inject.chapter_ids.CH05_MOOSE_PID,
                                          inject.chapters.ch05.ch05_moose_station(self._chap()),
                                          inject.chapters.ch05.ch05_party_camera_tile(self._chap()))
        self.assertEqual(1, beat.count('MOVE(0xffff'), 'only the snap back lives in the beat')
        self.assertIn('MOVE(0xffff, %s, %d, %d)' % (inject.chapter_ids.CH05_MOOSE_PID, *pen), beat)
        self.assertLess(script.index('REMA', script.index('TEXTSHOW(0x%X)' % inject.chapter_ids.CH05_MOOSE_QUIP_MSG)), back,
                        'the bubble is down before the reset')
        self.assertLess(script.index('CAMERA(%d, %d)' % party), back,
                        'the camera is on the party before the reset')

    def test_an_unreachable_charge_tile_is_a_hang_and_is_gated(self):
        """MOVE + ENUN to a tile the unit cannot WALK to never returns -- ch04's own soft-lock,
        on this same animal. The flood fill runs at injection time."""
        src = injector.injector_source()
        self.assertIn("'the white moose (ch05 scene 7)'", src)
        maps_dir = os.path.join(inject.decomp.REPO, 'campaigns', self.CAMPAIGN, 'maps')
        _pen, start, route = inject.chapters.ch05.ch05_moose_station(self._chap())
        for leg in route:      # every leg, from where the run BEGINS -- not from the pen
            inject.terrain.assert_scripted_move_reachable(maps_dir, inject.chapters.ch05.CH05_LAYOUT[1], start, leg,
                                              inject.chapter_ids.CH04_MOOSE_MOV_TABLE, 'test')

    def test_a_missing_charge_tile_is_refused_rather_than_shipped(self):
        chap = self._chap()
        moose = next(e for e in chap['enemy_units'] if e['id'] == 'white-moose')
        del moose['charge_route']
        with self.assertRaises(SystemExit):
            inject.chapters.ch05.ch05_moose_station(chap)

    # ── the camera ─────────────────────────────────────────────────────────────
    def test_no_party_unit_is_named_for_the_camera(self):
        """ch05 deploys 9 of a 10-unit pool, so BOTH of this scene's speakers can be benched --
        and a benched unit is still in the array (US_NOT_DEPLOYED) at stale coordinates, so
        `CUMO_CHAR` would pan to nowhere rather than fail. The bubble does not need a unit:
        `StartTalkOpen` anchors it to the speaking FACE SLOT."""
        block = inject.chapters.ch05.ch05_moose_charge_block(inject.chapter_ids.CH05_MOOSE_PID,
                                           inject.chapters.ch05.ch05_moose_station(self._chap()),
                                           inject.chapters.ch05.ch05_party_camera_tile(self._chap()))
        self.assertNotIn('CUMO_CHAR', block)
        self.assertIn('CUMO_AT', block)

    def test_every_framing_is_a_CAMERA_and_not_a_bare_CUMO(self):
        """`EventDisplayCursor_Loop` calls `PutMapCursor` and nothing else -- a CUMO draws a
        cursor and never scrolls. The first cut of this wiring used CUMO alone for both
        framings; the run showed the map never cutting south, because what was moving the view
        was whatever `LOMA` left behind. Vanilla pairs the two ahead of its own 0x9C4."""
        block = inject.chapters.ch05.ch05_moose_charge_block(inject.chapter_ids.CH05_MOOSE_PID,
                                           inject.chapters.ch05.ch05_moose_station(self._chap()),
                                           inject.chapters.ch05.ch05_party_camera_tile(self._chap()))
        _pen, start, _route = inject.chapters.ch05.ch05_moose_station(self._chap())
        party = inject.chapters.ch05.ch05_party_camera_tile(self._chap())
        for tile in (start, party):
            self.assertIn('CAMERA(%d, %d)' % tile, block)
            self.assertLess(block.index('CAMERA(%d, %d)' % tile),
                            block.index('CUMO_AT(%d, %d)' % tile),
                            'the scroll comes before the pointer')
        self.assertEqual(block.count('CAMERA'), block.count('CUMO_AT'))

    def test_the_map_comes_up_on_the_PARTY_for_turn_1(self):
        """Vanilla's 0x9C4 ends framed on the deploy pocket and so does ours. It is also what
        hides the snap back: the moose's pen is off the bottom of that view."""
        block = inject.chapters.ch05.ch05_moose_charge_block(inject.chapter_ids.CH05_MOOSE_PID,
                                           inject.chapters.ch05.ch05_moose_station(self._chap()),
                                           inject.chapters.ch05.ch05_party_camera_tile(self._chap()))
        party = inject.chapters.ch05.ch05_party_camera_tile(self._chap())
        self.assertLess(block.index('REMA'), block.index('CAMERA(%d, %d)' % party),
                        'the bubble is down before the cut')

    def test_the_frame_holds_ONE_position_across_the_break(self):
        """`[BreakTalk]` only LOCKS the talk proc -- the bubble stays up and the faces stay
        loaded -- so a camera move inside the message would scroll the map out from under an
        open bubble. The frame goes where the LINE is about, and stays there until REMA."""
        block = inject.chapters.ch05.ch05_moose_charge_block(inject.chapter_ids.CH05_MOOSE_PID,
                                           inject.chapters.ch05.ch05_moose_station(self._chap()),
                                           inject.chapters.ch05.ch05_party_camera_tile(self._chap()))
        _pen, start, _route = inject.chapters.ch05.ch05_moose_station(self._chap())
        head = block[:block.index('REMA')]
        self.assertEqual(1, head.count('CUMO_AT'))
        self.assertIn('CUMO_AT(%d, %d)' % start, head)

    def test_the_party_framing_is_asserted_against_the_real_deploy_slots(self):
        """Vanilla's own `CAMERA(5, 18)` for this beat, and ours because the retile lifts Ch5's
        nine start tiles 1:1. A re-paint that moved the pocket would leave the last shot before
        turn 1 holding on an empty corner, silently."""
        chap = self._chap()
        self.assertEqual((5, 18), inject.chapters.ch05.ch05_party_camera_tile(chap))
        self.assertIn([5, 18], chap['deployment']['deploy_slots'])
        chap['deployment']['deploy_slots'] = [[0, 0]]
        with self.assertRaises(SystemExit):
            inject.chapters.ch05.ch05_party_camera_tile(chap)

    # ── placement in the beginning script ──────────────────────────────────────
    def test_the_debug_boot_lands_ON_the_beat_and_skips_the_approved_footage(self):
        """`--ch05-moose`. Scene 7 is the last beat of a ~52-A-press opening, so every film of
        it replayed four backdrop scenes, PREP, the join and Sahnar's monologue to reach ten
        seconds of moose -- Nicolas stopped a run over exactly that (2026-08-15). Iterating on a
        late beat has to cost a BUILD, not a playthrough."""
        seed = '    LOAD1(0x1, %s)\n    ENUN\n' % inject.chapters.ch05.CH05_BOOT_SEED_TABLE
        dbg = inject.chapters.ch05.ch05_beginning_script(self._chap(), 'CHARACTER_ARTUR', inject.chapters.ch05.CH05_SAHNAR_TABLE,
                                       'CHARACTER_MARISA', seed_load=seed, moose_only=True)
        self.assertIn('TEXTSHOW(0x%X)' % inject.chapter_ids.CH05_MOOSE_CHARGE_SLOT[1], dbg)
        self.assertIn('LOMA(0x%X)' % inject.hosts.CH05_HOST_INDEX, dbg)
        self.assertIn(inject.chapters.ch05.CH05_LINE_TABLE, dbg, 'the line is where the MOOSE comes from')
        self.assertIn(inject.chapters.ch05.CH05_BOOT_SEED_TABLE, dbg, 'and the seed is the party to cut back to')
        for skipped in (inject.chapters.ch05.CH05_OPENING_BG, inject.chapters.ch05.CH05_ARRIVAL_BG,
                        'CALL(%s)' % inject.chapters.ch05.CH05_PREP_SCRIPT,
                        'TEXTSHOW(0x%X)' % inject.chapter_ids.CH05_BASIL_JOIN_SLOT[1],
                        'TEXTSHOW(0x%X)' % inject.chapter_ids.CH05_SAHNAR_ALONE_SLOT[1]):
            self.assertNotIn(skipped, dbg, 'the debug boot replays nothing already approved')

    def test_the_debug_boot_refuses_to_exist_without_a_party(self):
        """It skips Preparations, so `--ch05-boot`'s seed is the only thing left that would put
        one on the map -- and the beat ends by cutting south to look at it."""
        with self.assertRaises(SystemExit):
            inject.chapters.ch05.ch05_beginning_script(self._chap(), 'CHARACTER_ARTUR', inject.chapters.ch05.CH05_SAHNAR_TABLE,
                                     'CHARACTER_MARISA', moose_only=True)

    def test_the_shipping_script_is_untouched_by_the_debug_flag(self):
        """A debug boot that changed the real opening would be worse than no debug boot."""
        real = self._script()
        for beat in (inject.chapter_ids.CH05_BASIL_JOIN_SLOT[1], inject.chapter_ids.CH05_SAHNAR_ALONE_SLOT[1],
                     inject.chapter_ids.CH05_MOOSE_CHARGE_SLOT[1]):
            self.assertIn('TEXTSHOW(0x%X)' % beat, real)
        self.assertIn('CALL(%s)' % inject.chapters.ch05.CH05_PREP_SCRIPT, real)

    def test_it_is_the_LAST_beat_before_the_map(self):
        script = self._script()
        self.assertLess(script.index('TEXTSHOW(0x%X)' % inject.chapter_ids.CH05_SAHNAR_ALONE_SLOT[1]),
                        script.index('TEXTSHOW(0x%X)' % inject.chapter_ids.CH05_MOOSE_CHARGE_SLOT[1]))
        self.assertLess(script.index('TEXTSHOW(0x%X)' % inject.chapter_ids.CH05_MOOSE_CHARGE_SLOT[1]),
                        script.index('ENUT(8)'))

    def test_it_plays_AFTER_prep_and_brings_no_fade_of_its_own(self):
        """Scene 5 already brought the screen up after the prep prologue's fade to black; 6
        and 7 ride it. A fade here would flash the map through black on the last beat."""
        script = self._script()
        self.assertLess(script.index('CALL(%s)' % inject.chapters.ch05.CH05_PREP_SCRIPT),
                        script.index('TEXTSHOW(0x%X)' % inject.chapter_ids.CH05_MOOSE_CHARGE_SLOT[1]))
        # It inherits scene 5's fade-up, so nothing between the join and its own first box
        # goes dark. What follows that box IS a fade cycle, and deliberately: the bellow is a
        # full-screen CG over the map, so it fades down to the image and back up to the map.
        gap = script[script.index('TEXTSHOW(0x%X)' % inject.chapter_ids.CH05_BASIL_JOIN_SLOT[1]):
                     script.index('TEXTSHOW(0x%X)' % inject.chapter_ids.CH05_MOOSE_CHARGE_SLOT[1])]
        self.assertNotIn('FADU', gap)
        self.assertNotIn('FADI', gap)
        bellow = script[script.index('TEXTSHOW(0x%X)' % inject.chapter_ids.CH05_MOOSE_CHARGE_SLOT[1]):
                        script.index('TEXTSHOW(0x%X)' % inject.chapter_ids.CH05_MOOSE_QUIP_MSG)]
        # SYMMETRIC, both ways, and that is not a preference: cutting in under a lit screen
        # read as a glitch on both edges (Nicolas, 2026-08-15 -- "jumpy/glitchy both in and
        # out of it"). This is vanilla's own backdrop shape, the one the ch05 opening uses
        # between its own scenes: map out, image in, hold, image out, map back.
        self.assertEqual(2, bellow.count('FADI(16)'), 'map out, then image out')
        self.assertEqual(2, bellow.count('FADU(16)'), 'image in, then map back')

    def test_the_moose_is_already_on_the_map_and_is_not_loaded_again(self):
        """It has stood in the turn-1 line since before prep -- this beat only has to look at
        it. A LOAD1 here would put a second moose on the rim."""
        script = self._script()
        self.assertNotIn('LOAD1(0x1, %s)' % inject.chapter_ids.CH05_MOOSE_PID, script)
        moose = next(e for e in self._chap()['enemy_units'] if e['id'] == 'white-moose')
        self.assertIsNone(moose.get('arrives_turn'), 'it rides the turn-1 line')

    def test_the_moose_still_does_not_speak(self):
        """Locked 2026-07-03 as a mute white ghost, and re-locked by this chapter. The charge
        is stage direction; nothing gives it a box."""
        self.assertNotIn('white-moose', [next(iter(b)) for b in self._scene()['script']])
        self.assertNotIn('moose:', str(self._scene()['script']))


class Ch05ArenaTutorial(unittest.TestCase):
    """The Elven Tomb inherits vanilla Ch5's arena lesson on a live tile trigger (#264).

    The YAML's ``vanilla 0x9D5 + 0x9D6`` label is anatomy, not permission to write into
    ch04's host block. The live tutorial therefore owns two ids from ch05's real Ch6 host
    block and reaches them through a one-shot event on the arena tile itself.
    """
    CAMPAIGN = 'rime-of-the-frostmaiden'

    def _chap(self):
        return inject.hosting._load_chapter_yaml(self.CAMPAIGN, inject.chapter_ids.CH05_CHAPTER_YAML)

    def _event(self):
        return next(e for e in self._chap()['events']
                    if e['trigger'] == 'arena_tile_visited')

    def test_the_two_messages_are_named_owned_and_inside_ch05s_host_block(self):
        self.assertEqual(0x9E6, inject.chapter_ids.CH05_ARENA_FOUND_MSG)
        self.assertEqual(0x9E7, inject.chapter_ids.CH05_ARENA_RULES_MSG)
        claimed = set(inject.messages.HOSTED_CHAPTER_MESSAGE_IDS['ch05'])
        for msg in (inject.chapter_ids.CH05_ARENA_FOUND_MSG, inject.chapter_ids.CH05_ARENA_RULES_MSG):
            self.assertTrue(0x9E4 <= msg <= 0x9F3)
            self.assertIn(msg, claimed)
            self.assertEqual('ch05', inject.messages.assert_message_ids_unique()[msg])

    def test_the_locked_six_boxes_keep_vanillas_one_plus_five_anatomy(self):
        event = self._event()
        self.assertEqual('vanilla 0x9D5 + 0x9D6', event['slot'])
        self.assertEqual(6, len(event['script']))
        self.assertEqual({'tutorial'}, {next(iter(box)) for box in event['script']})

        found, rules = inject.chapters.ch05.ch05_arena_messages(self._chap())
        self.assertEqual(1, found.count('[A]'))
        self.assertEqual(5, rules.count('[A]'))
        self.assertIn('[ToggleRed]arena', found)
        for phrase in ('one-on-one', 'twice', 'will not', 'press the B Button quickly'):
            self.assertIn(phrase, rules)

    def test_the_misc_list_fires_once_on_exactly_the_arena_tile(self):
        self.assertEqual('EVFLAG_TMP(13)', inject.chapters.ch05.CH05_ARENA_TUTORIAL_FLAG)
        location = inject.chapters.ch05.ch05_location_events(self._chap())
        misc = inject.chapters.ch05.ch05_misc_events()
        area = ('AREA(%s, %s, 12, 6, 12, 6)'
                % (inject.chapters.ch05.CH05_ARENA_TUTORIAL_FLAG, inject.chapters.ch05.CH05_ARENA_TRIGGER_SCRIPT))
        self.assertNotIn(area, location)
        self.assertEqual(1, misc.count(area))
        self.assertIn('DefeatBoss(%s)' % inject.chapters.ch05.CH05_ENDING_SCRIPT, misc)
        self.assertIn('CauseGameOverIfLordDies', misc)

    def test_the_trigger_is_player_only_and_calls_the_tutorial_in_every_mode(self):
        # The arena tutorial is the one place the player is told a loss is PERMANENT and
        # that B concedes, so it is not gated on tutorial mode the way vanilla's is (#303).
        # The faction gate stays -- an enemy on the tile must not fire it.
        trigger = inject.chapters.ch05.ch05_arena_trigger_script()
        self.assertIn('SVAL(EVT_SLOT_2, FACTION_ID_BLUE)', trigger)
        self.assertIn('CALL(EventScr_UnTriggerIfNotFaction)', trigger)
        self.assertLess(trigger.index('CALL(EventScr_UnTriggerIfNotFaction)'),
                        trigger.index('CALL(%s)' % inject.chapters.ch05.CH05_ARENA_TUTORIAL_SCRIPT))
        self.assertNotIn('CALL(EventScr_CallOnTutorialMode)', trigger)

        tutorial = inject.chapters.ch05.ch05_arena_tutorial_script()
        self.assertLess(tutorial.index('TEXTSHOW(0x%X)' % inject.chapter_ids.CH05_ARENA_FOUND_MSG),
                        tutorial.index('CAMERA(12, 6)'))
        self.assertIn('CURSOR_FLASHING(12, 6)', tutorial)
        self.assertLess(tutorial.index('CAMERA(12, 6)'),
                        tutorial.index('TEXTSHOW(0x%X)' % inject.chapter_ids.CH05_ARENA_RULES_MSG))
        self.assertIn('ENUT(234)', tutorial)


class PerPositionAiReachesTheEmittedRows(unittest.TestCase):
    """#335: an entry with one donor PER POSITION must emit those distinct AIs.

    This is a regression test for a real bug, caught by the output diff and not by any unit
    test: every injector called `enemy_ai_initialiser(chap, enemy)` without the position
    index, so all eight of ch05's tomb-reavers shipped their FIRST donor's AI. The YAML was
    right, the resolver was right, the tests were green, and the ROM got eight identical
    holders -- exactly the flattening the per-position donors exist to prevent."""

    def _chap(self, stem):
        import glob
        path = glob.glob(os.path.join(
            inject.decomp.REPO, 'campaigns/rime-of-the-frostmaiden/chapters', stem + '*.yaml'))[0]
        with open(path, encoding='utf-8') as source:
            return yaml_loader.yaml_load(source)

    def test_ch05_tomb_reavers_emit_three_distinct_behaviours(self):
        chap = self._chap('ch05')
        rows = '\n'.join(inject.chapters.ch05.ch05_enemy_rows(chap, exclude=('sahnar',)))
        reaver_ais = re.findall(r'tomb-reaver -- .*?\n(?:.*?\n)*?\s*\.ai = (\{[^}]*\})',
                                rows)
        self.assertEqual(8, len(reaver_ais), 'expected eight tomb-reavers')
        self.assertEqual({'{0x0, 0x3, 0x9, 0x0}', '{0x0, 0x0, 0x9, 0x0}',
                          '{0x0, 0x12, 0x9, 0x0}'}, set(reaver_ais))

    def test_ch01_spears_and_axes_each_ship_one_delayed_charger(self):
        chap = self._chap('ch01')
        spear = next(e for e in chap['enemy_units'] if e['id'] == 'goblin-spear')
        axe = next(e for e in chap['enemy_units'] if e['id'] == 'goblin-axe')
        import difficulty
        self.assertEqual(1, sum(1 for i in range(3)
                                if difficulty.enemy_ai_bytes(chap, spear, i)[1] == 0x12))
        self.assertEqual(1, sum(1 for i in range(3)
                                if difficulty.enemy_ai_bytes(chap, axe, i)[1] == 0x12))


class Ch05VillageRaidRace(unittest.TestCase):
    """ch05's declared structure: the eruption's dead race the party for the four reliquaries,
    and saving all four pays out (#25). Vanilla Ch5 is the reference for both halves -- it wires
    the same four tiles on EVFLAG_TMP(8..11), sends all six of its reinforcements in on AI_B_04
    (PillageThenPursue), and gates a Guiding Ring on four CHECK_EVENTIDs at the ending.

    None of it was wired here while the YAML claimed it was, so every test in this class pins a
    piece that shipped absent rather than wrong.
    """
    CAMPAIGN = 'rime-of-the-frostmaiden'

    def _chap(self):
        return inject.hosting._load_chapter_yaml(self.CAMPAIGN, inject.chapter_ids.CH05_CHAPTER_YAML)

    def test_each_reliquary_owns_an_event_id_ch05_does_not_already_spend(self):
        """We cannot copy vanilla's 8..11. ch05's opening ends on ENUT(8) -- which is
        EvtSetFlag, not un-trigger, and a vanilla prep idiom (ch12a/ch18a) -- and the Sahnar
        Talk holds 7. A site on either would start the chapter already visited: its VILL and its
        raider hook both disarmed, and the payout counting a door nobody opened."""
        flags = inject.chapters.ch05.CH05_VILLAGE_FLAGS
        self.assertEqual(set(flags), {v['id'] for v in self._chap()['villages']},
                         'every reliquary needs an id, and only the reliquaries')
        self.assertEqual(len(set(flags.values())), len(flags), 'two sites share one flag')
        self.assertNotIn('0', flags.values(), 'flag 0 is EVFLAG_ALWAYS_FALSE')
        for spent in (inject.chapters.ch05.CH05_SAHNAR_TALK_FLAG, 'EVFLAG_TMP(8)'):
            self.assertNotIn(spent, flags.values(),
                             '%s is already spent elsewhere in ch05' % spent)

    def test_the_location_list_arms_every_reliquary_with_its_flag(self):
        """Declaring the flags is not wiring them. The Location list is the only place the
        engine reads them, and it shipped `Village(0, ..)` for all four."""
        body = inject.chapters.ch05.ch05_location_events(self._chap())
        for vid, flag in inject.chapters.ch05.CH05_VILLAGE_FLAGS.items():
            self.assertIn('Village(%s, %s,' % (flag, inject.chapter_ids.CH05_VILLAGE_SLOTS[vid][0]), body)
        self.assertNotIn('Village(0,', body, 'an unflagged site cannot be raided or counted')
        self.assertIn('Armory(', body)        # the elven store rides the same list
        self.assertIn('Vendor(', body)

    def _changes(self):
        return inject.chapters.ch05.ch05_map_changes(self._chap(), self._maps_dir())

    def _maps_dir(self):
        return os.path.join(inject.decomp.REPO, 'campaigns', self.CAMPAIGN, 'maps')

    def _tileset(self):
        import map_tileset_tool as mt
        return mt._tileset_from_dir(os.path.join(self._maps_dir(), 'tilesets', inject.chapters.ch05.CH05_TILESET))

    def test_a_raided_site_is_ruined_across_vanillas_own_footprint(self):
        """AiPillageAction looks the change up at (x, y - 1) -- the tile ABOVE the door, where
        Village()'s destruction LOCA sits -- so a change on the door alone is never found and
        the site survives its own sacking. Vanilla answers with a 3x2 at (x-1, y-1), which
        covers the lookup tile AND the door, and we inherit its footprint with its geometry."""
        changes = self._changes()
        tileset, ruins = self._tileset(), inject.maps.terrain_ids()['TERRAIN_RUINS_REGULAR']
        for village in self._chap()['villages']:
            x, y = village['tile']
            block = [c for c in changes if (c[0], c[1]) == (x - 1, y - 1)]
            self.assertEqual(1, len(block), 'no ruin change for %r' % village['id'])
            _x, _y, w, h, tiles, _why = block[0]
            self.assertEqual((3, 2), (w, h))
            self.assertEqual(6, len(tiles))
            for m in tiles:
                self.assertEqual(ruins, tileset.terrain(m),
                                 'metatile %d is not ruins -- a "destroyed" site FE8 still '
                                 'reads as a village stays lootable and visitable' % m)
                self.assertFalse(inject.maps._is_blank_metatile(tileset, m),
                                 'ruin writes blank metatile %d' % m)

    def test_a_visited_site_shuts_its_door(self):
        changes = self._changes()
        for village in self._chap()['villages']:
            door = [c for c in changes if list(c[:4]) == village['tile'] + [1, 1]]
            self.assertEqual(1, len(door), 'no door change for %r' % village['id'])
            self.assertEqual(inject.maps.terrain_ids()['TERRAIN_VILLAGE_CLOSED'],
                             self._tileset().terrain(door[0][4][0]))

    def test_the_ruins_are_registered_before_the_doors(self):
        """Order is the whole correctness argument, and it is invisible in a screenshot.
        GetMapChangeIdAt keeps the LAST region covering a tile (bmtrick.c), and the 3x2 ruin
        overlaps its own door. Doors-first would make VISITING a site ruin the building."""
        changes = self._changes()
        doors = {tuple(v['tile']) for v in self._chap()['villages']}
        last_ruin = max(i for i, c in enumerate(changes) if (c[0], c[1]) not in doors)
        first_door = min(i for i, c in enumerate(changes) if (c[0], c[1]) in doors)
        self.assertLess(last_ruin, first_door,
                        'a door change ahead of a ruin change: visiting would ruin the site')

    def test_every_eruption_wave_races_the_sites(self):
        """Vanilla Ch5 sends ALL SIX of its reinforcements in on AI_B_04 -- three pairs, turns
        2/6/8, every one a pillager. Ours spawn on those same three tile-pairs, so 'we do what
        vanilla does' (Nicolas, 2026-08-09) means all three waves raid. Without a pillage AI on
        the board nothing on the map can reach a reliquary and the race is prose."""
        waves = [e for e in self._chap()['enemy_units'] if e.get('arrives_turn')
                 and e['id'] != 'sahnar']
        self.assertEqual(3, len(waves), 'ch05 has three eruption waves')
        chap = self._chap()
        for wave in waves:
            self.assertEqual('{0x0, 0x4, 0x9, 0x0}',
                             inject.units.enemy_ai_initialiser(chap, wave),
                             "%s does not race the reliquaries -- vanilla Ch5's own raider "
                             'AI, byte for byte (AI_B_04 = AiScr_AiB_PillageThenPursue), is '
                             'what its donor carries' % wave['id'])

    def test_a_raider_row_carries_the_pillage_ai_into_the_table(self):
        rows = '\n'.join(inject.chapters.ch05.ch05_enemy_rows(self._chap(), arrives_turn=2, exclude=('sahnar',)))
        self.assertIn('.ai = {0x0, 0x4, 0x9, 0x0},', rows)

    # -- the payout: vanilla's Guiding-Ring-on-all-four, which is why the flags exist ---------
    def test_the_bonus_is_withheld_unless_every_site_survived(self):
        """Vanilla's shape exactly: one CHECK_EVENTID per site, each branching PAST the gift the
        moment a flag is unset, so any single unset id skips the whole payout."""
        body = inject.villages.save_all_bonus_script({'a': 'EVFLAG_TMP(9)', 'b': 'EVFLAG_TMP(10)'},
                                        'ITEM_GUIDINGRING')
        self.assertEqual(2, body.count('CHECK_EVENTID('))
        self.assertIn('CHECK_EVENTID(EVFLAG_TMP(9))', body)
        self.assertIn('CHECK_EVENTID(EVFLAG_TMP(10))', body)
        self.assertEqual(2, body.count('BEQ('), 'every check needs its own skip branch')
        skip = re.search(r'BEQ\((0x[0-9A-F]+), EVT_SLOT_C, EVT_SLOT_0\)', body).group(1)
        self.assertIn('LABEL(%s)' % skip, body)
        self.assertLess(body.index('GIVEITEMTO'), body.index('LABEL(%s)' % skip),
                        'the gift must sit INSIDE the branch it is gated by')

    def test_the_bonus_goes_to_the_leader_not_the_last_unit_to_move(self):
        """CHAR_EVT_ACTIVE_UNIT is the village idiom -- the unit who walked in. There is no
        active unit at the ending, so the payout uses vanilla's CHAR_EVT_PLAYER_LEADER."""
        body = inject.villages.save_all_bonus_script({'a': 'EVFLAG_TMP(9)'}, 'ITEM_GUIDINGRING')
        self.assertIn('SVAL(EVT_SLOT_3, ITEM_GUIDINGRING)', body)
        self.assertIn('GIVEITEMTO(CHAR_EVT_PLAYER_LEADER)', body)

    def test_ch05_pays_out_a_vanilla_item_at_its_ending(self):
        """The bonus is vanilla Ch5's own Guiding Ring. It used to be a `crest-of-cold-iron`,
        an item that existed in no table and was handed over by nothing -- and the campaign
        renames items only for the Goodberry and Tourmaline (Nicolas, 2026-08-09)."""
        bonus = self._chap()['economy']['save_all_bonus']
        self.assertIn(bonus, inject.chapter_ids.CH05_ITEM_IDS, 'the save-all bonus must be a real FE item')
        self.assertEqual('ITEM_GUIDINGRING', inject.chapter_ids.CH05_ITEM_IDS[bonus])
        ending = _ch05_ending(self._chap())
        # Named flags, not a count: the ending also branches on the Sahnar RECRUIT flag now, and
        # a bare CHECK_EVENTID tally would pass with a village gate deleted and the recruit
        # gate counted in its place.
        for site in self._chap()['villages']:
            self.assertIn('CHECK_EVENTID(%s)' % inject.chapters.ch05.CH05_VILLAGE_FLAGS[site['id']], ending,
                          '%s does not gate the payout' % site['id'])
        self.assertIn('SVAL(EVT_SLOT_3, ITEM_GUIDINGRING)', ending)
        self.assertTrue(ending.rstrip().endswith('ENDA\n}'))

    def test_the_ring_is_handed_over_before_the_screen_goes_black(self):
        """Vanilla restores the screen (`EventScr_RemoveBGIfNeeded`) immediately ahead of its own
        GIVEITEMTO, and on a full pack the reason is not cosmetic: the give runs
        HandleNewItemGetFromDrop, which opens a BLOCKING convoy/discard menu. Behind a FADI the
        player is operating that menu blind."""
        ending = _ch05_ending(self._chap())
        head, _, tail = ending.partition('GIVEITEMTO')
        # The ending is a BACKDROP scene now, so the thing keeping the screen up is its own
        # BACG rather than a RemoveBGIfNeeded call -- but the requirement is the same one, and
        # it has to be asserted on the LAST fade before the give, not on the first FADI in the
        # script (which is the one that takes the battlefield down to raise the backdrop).
        self.assertIn('BACG(%s)' % inject.chapters.ch05.CH05_ENDING_BG, head, 'nothing is on screen at the give')
        self.assertNotIn('FADI(16)', head.split('BACG(%s)' % inject.chapters.ch05.CH05_ENDING_BG)[1],
                         'the backdrop is faded out again before the ring is handed over')
        self.assertIn('FADI(16)', tail, 'the fade into the landing must follow the give')

    def test_the_payout_gates_only_on_sites_the_location_list_armed(self):
        """The ending used to gate on the module dict while the Location list armed whatever the
        YAML declared. Drop a village and the ring becomes unobtainable, with a green build."""
        chap = self._chap()
        chap['villages'] = chap['villages'][:2]
        ending = _ch05_ending(chap)
        kept = {inject.chapters.ch05.CH05_VILLAGE_FLAGS[v['id']] for v in chap['villages']}
        gated = {f for f in inject.chapters.ch05.CH05_VILLAGE_FLAGS.values()
                 if 'CHECK_EVENTID(%s)' % f in ending}
        self.assertEqual(kept, gated,
                         'the payout must check exactly the sites that exist')

    def test_no_ch05_enemy_drops_anything(self):
        """Vanilla Ch5 has ZERO droppers -- Saar included. Ravisin used to carry a `drops:`
        block naming the crest, on a key the injector never reads, so it was decoration that
        read like wiring."""
        for enemy in self._chap()['enemy_units']:
            self.assertNotIn('drops', enemy, '%s carries a dead `drops:` key' % enemy['id'])
            self.assertNotIn('item_drop', enemy, '%s drops loot vanilla Ch5 never does'
                             % enemy['id'])


class CampaignOwnedEventScripts(unittest.TestCase):
    """The script twin of campaign-owned unit tables. A host slot frees only the scripts its
    stripped cutscenes stop referencing -- slot 6 leaves five, and ch05 needs three waves plus
    one per village. Naming our own removes the budget, and MS_Ch05VisitSouth says what it runs
    where EventScr_089F2AE4 says nothing."""

    HEADER = 'extern CONST_DATA EventListScr EventScr_9EEA58[];\n'

    def test_extern_is_added_once_and_is_idempotent(self):
        once = inject.event_scripts.event_script_extern(self.HEADER, 'MS_Ch05VisitSouth', 'south reliquary')
        twice = inject.event_scripts.event_script_extern(once, 'MS_Ch05VisitSouth', 'south reliquary')
        self.assertEqual(once, twice)
        self.assertEqual(twice.count('MS_Ch05VisitSouth[];'), 1)

    def test_an_unprefixed_symbol_is_refused(self):
        with self.assertRaises(SystemExit):
            inject.event_scripts.event_script_extern(self.HEADER, 'EventScr_089F2AE4', 'squatting')

    def test_a_declared_but_undefined_script_fails_the_build(self):
        """declare_event_script APPENDS, while the injector rewrites the same file wholesale from
        a copy read earlier -- so declaring before the bulk write silently discards every script.
        It happened, and the only symptom was a link error naming the reference, not the loss."""
        tmp = tempfile.mkdtemp()
        try:
            path = os.path.join(tmp, 'ch6-eventscript.h')
            with open(path, 'w') as f:
                f.write('CONST_DATA EventListScr MS_Ch05VisitNorth[] = {\n    ENDA\n};\n')
            inject.event_scripts.assert_event_scripts_defined(path, ['MS_Ch05VisitNorth'])   # present -> quiet
            with self.assertRaises(SystemExit) as caught:
                inject.event_scripts.assert_event_scripts_defined(
                    path, ['MS_Ch05VisitNorth', 'MS_Ch05VisitSouth'])
            self.assertIn('MS_Ch05VisitSouth', str(caught.exception))
            self.assertIn('AFTER', str(caught.exception), 'the error must name the ordering')
        finally:
            shutil.rmtree(tmp, ignore_errors=True)


class Ch05Endings(unittest.TestCase):
    """ch05's scenes 16 and 17 (#25) -- the two endings, and the three questions they ask.

    Wired as our other four endings are (FADI the map out, BACG, FADU, the beat calls, FADI into
    the landing), which is also what vanilla's own `EventScr_Ch5_EndingScene` does: it opens on
    FADI(16), raises BG_SERAFEW_VILLAGE and never issues a TEXTSTART. That last fact spent three
    weeks recorded backwards -- the ch05 YAML, issue #25 and HANDOFF all said "ON-MAP at 29",
    out of a `vanilla_scene.py` classifier that read a bare TEXTSHOW as on-map regardless of the
    backdrop in front of it (fixed, and pinned in test_vanilla_scene.py).
    """
    CAMPAIGN = 'rime-of-the-frostmaiden'

    def _chap(self):
        return inject.hosting._load_chapter_yaml(self.CAMPAIGN, inject.chapter_ids.CH05_CHAPTER_YAML)

    def _bodies(self):
        return dict(inject.chapters.ch05.ch05_ending_messages(self._chap()))

    def test_both_scenes_keep_their_locked_box_counts(self):
        """19 boxes in scene 16, 10 in scene 17. Locked 2026-07-30."""
        arms = inject.chapters.ch05._ch05_ending_variants(self._chap(), inject.chapters.ch05.CH05_ENDING_SLOT, 19, 'Basil alive')
        self.assertEqual(19, inject.text._script_box_count(arms[True]))
        lost = inject.chapters.ch05._ch05_ending_variants(self._chap(), inject.chapters.ch05.CH05_ENDING_LOST_SLOT, 10, 'Basil died')
        self.assertEqual(10, inject.text._script_box_count(lost[True]))

    def test_basil_never_leaves_the_screen(self):
        """THE reason scene 16 is one message per arm rather than three spliced beats.

        Split across three `Text()` calls it played correctly and looked wrong: each call is
        its own TEXTSTART..REMA, so the seams tore the faces down and Basil -- who speaks in
        all three -- faded out and reloaded into the seat she was already in, twice (Nicolas,
        watching the first film 2026-08-19). Held as one message the podium manager keeps her
        up from the first box to the last.

        Asserted on her podium's codes, which is where the defect actually lived: she may be
        loaded exactly once and never cleared, while mid-left cycles through everyone else.
        """
        for msg, body in self._bodies().items():
            right = body.count('[OpenMidRight][LoadFace]')
            self.assertLessEqual(right, 1,
                                 'MSG_%X reloads Basil mid-scene' % msg)
            self.assertNotIn('[OpenMidRight][ClearFace]', body,
                             'MSG_%X fades Basil out before the scene ends' % msg)
            self.assertGreater(body.count('[OpenMidLeft][LoadFace]'), 1,
                               'MSG_%X never rotates anyone through mid-left' % msg)

    def test_the_no_sahnar_arm_cuts_the_berry_exchange_rather_than_replacing_it(self):
        """A CUT, and the six boxes have to actually leave.

        The `replaces:` anchors cannot prove this on their own -- they assert where each named
        box sits, not that it went. A `no_sahnar_cut:` that grew a `script:` key would
        substitute instead of drop, pass every anchor, and ship a scene that mentions Sahnar to
        a player who never met her.
        """
        arms = inject.chapters.ch05._ch05_ending_variants(self._chap(), inject.chapters.ch05.CH05_ENDING_SLOT, 19, 'Basil alive')
        full, cut = arms[True], arms[False]
        self.assertEqual(13, inject.text._script_box_count(cut))
        self.assertNotIn('sahnar', {k for entry in cut for k in entry})
        self.assertIn('sahnar', {k for entry in full for k in entry})
        # ...and the seam it leaves has to be the one the YAML describes: the repotting runs
        # straight into Braulo's question.
        texts = [str(e) for e in cut]
        joined = ' | '.join(texts)
        self.assertIn('goodberry bush into your cause', joined)
        self.assertIn('What else did she do', joined)

    def test_the_sahnar_gate_asks_the_flag_as_well_as_the_roster(self):
        """CHECK_ALIVE ALONE IS WRONG HERE, and this is the test that says why.

        `GetUnitFromCharId` (bmunit.c) sweeps unit indices 1..0xFF -- every faction, not the
        player's roster -- so a Sahnar the player never turned is still FOUND, and still
        ALIVE, standing on the map as a red myrmidon when Ravisin dies. On CHECK_ALIVE alone
        the berry exchange plays with the party's own enemy thanking Basil by name.

        The recruit FLAG asks "was she turned"; CHECK_ALIVE then asks "is she still here", so
        a Sahnar recruited and later killed is silent too. Vanilla chains exactly this pair
        (ch19a's EventScr_089F8688: CHECK_EVENTID(7) into CHECK_ALIVE(CHARACTER_TANA)).

        Basil needs no flag on the other hand -- she is never hostile, joining by CUSA in
        scene 5 -- which is why her gate is a bare CHECK_ALIVE and hers is the only one.
        """
        ending = _ch05_ending(self._chap())
        full = 'Text(0x%X)' % inject.chapter_ids.CH05_ENDING_MSGS[True]
        guard = ending[:ending.index(full)]
        self.assertIn('CHECK_EVENTID(%s)' % inject.chapters.ch05.CH05_SAHNAR_TALK_FLAG, guard,
                      'the berry exchange is not gated on the RECRUIT flag')
        self.assertIn('CHECK_ALIVE(CHARACTER_MARISA)', guard,
                      'the berry exchange is not gated on Sahnar still being alive')
        # Both checks send the player to the SAME arm -- the cut scene, not two different ones.
        cut_label = 'BEQ(0x%X,' % inject.chapters.ch05.CH05_ENDING_SAHNAR_LABEL_BASE
        self.assertEqual(2, guard.count(cut_label))

    def test_every_arm_the_scene_branches_on_has_its_own_id(self):
        """Two for scene 16 (Sahnar recruited or not), one for 17, and each is a WHOLE scene.

        Whole copies rather than a prefix/arm/suffix split, which is what keeps Basil on
        screen. Nothing is hand-duplicated: the shorter one comes out of the one locked script
        through `variant_beat`.
        """
        self.assertEqual({True, False}, set(inject.chapter_ids.CH05_ENDING_MSGS))
        arms = inject.chapters.ch05._ch05_ending_variants(self._chap(), inject.chapters.ch05.CH05_ENDING_SLOT, 19, 'Basil alive')
        self.assertEqual(set(inject.chapter_ids.CH05_ENDING_MSGS), set(arms))
        lost = inject.chapters.ch05._ch05_ending_variants(self._chap(), inject.chapters.ch05.CH05_ENDING_LOST_SLOT, 10, 'Basil died')
        self.assertEqual({True}, set(lost))

    def test_neither_ending_branches_on_lupin(self):
        """UNBRANCHED 2026-08-19, and the premise was wrong rather than marginal.

        Both endings carried a `no_lupin_fallback` because Basil's "like she woke the wolves"
        was read as naming an optional recruit. It does not: recruitment decides whether Lupin
        JOINS, not whether the party ever met the pack, and ch04's turn-2 reveal puts the
        wolves in front of them on every path (Nicolas). The locked line is true in both
        worlds, so the branch could only ever have been wrong.

        Pinned two ways -- the YAML may not carry a block nothing reads, and the emitted script
        may not ask about him -- because a fallback restored by a merge would sit there looking
        live while `_ch05_ending_variants` quietly ignored it.
        """
        chap = self._chap()
        for slot in (inject.chapters.ch05.CH05_ENDING_SLOT, inject.chapters.ch05.CH05_ENDING_LOST_SLOT):
            event = inject.chapters.ch05._chapter_event_by_slot(chap, 'chapter_end', slot, 'ch05 ending')
            self.assertNotIn('no_lupin_fallback', event,
                             '%s carries a fallback nothing reads' % slot)
            joined = ' | '.join(str(e) for e in event['script'])
            self.assertNotIn('woke me', joined, '%s kept the retired substitute' % slot)
        ending = _ch05_ending(chap)
        self.assertNotIn(inject.chapters.ch05.CH05_LUPIN_CHARACTER, ending,
                         'the ending still asks the roster about Lupin')
        # The locked references SURVIVE -- unbranching keeps the line, it does not cut it.
        bodies = ' '.join(self._bodies().values())
        self.assertIn('she woke the wolves', bodies)
        self.assertIn('the moose, the wolf', bodies.lower())

    def test_the_endings_play_over_a_backdrop_and_never_open_a_bubble(self):
        """The channel, asserted on the script rather than on a comment.

        A BACG is up before any text call and no TEXTSTART is issued outside `Text()`'s own
        expansion -- which is what makes six speakers safe here. On-map a bubble anchors to a
        speaking UNIT (PutTalkBubble), and ch05 deploys 9 of a 10-unit pool, so Marty,
        Wolfram, Braulo and RBG can all be talking from a tile nobody is standing on.
        """
        ending = _ch05_ending(self._chap())
        first_text = ending.index('Text(0x')
        self.assertIn('BACG(%s)' % inject.chapters.ch05.CH05_ENDING_BG, ending[:first_text])
        self.assertNotIn('TEXTSTART', ending)
        self.assertNotIn('CUMO_CHAR', ending, 'a backdrop scene needs no camera on a speaker')

    def test_the_victory_sting_is_picked_per_arm(self):
        """Vanilla puts MUSC inside each side of its own CHECK_ALIVE and so do we.

        The one place ch05's ending departs from our other four, which have nothing to pick
        between: SONG_VICTORY when the escort lived, SONG_INTO_THE_SHADOW_OF_VICTORY when she
        did not, and neither before the branch where it would play over both.
        """
        ending = _ch05_ending(self._chap())
        basil = 'CHECK_ALIVE(CHARACTER_ARTUR)'
        self.assertIn(basil, ending)
        self.assertNotIn('MUSC(', ending[:ending.index(basil)],
                         'a sting before the branch plays the wrong one on the losing arm')
        self.assertIn('MUSC(SONG_VICTORY)', ending)
        self.assertIn('MUSC(SONG_INTO_THE_SHADOW_OF_VICTORY)', ending)

    def test_every_ending_id_is_claimed_and_unique(self):
        """Six ids, all in ch05's ledger and none written by another hosted chapter."""
        ids = (*inject.chapter_ids.CH05_ENDING_MSGS.values(), inject.chapter_ids.CH05_ENDING_LOST_MSG)
        self.assertEqual(len(ids), len(set(ids)), 'an ending id is used twice')
        for msg in ids:
            self.assertIn(msg, inject.messages.HOSTED_CHAPTER_MESSAGE_IDS['ch05'],
                          'MSG_%X is written but not claimed' % msg)
        for chapter, claimed in inject.messages.HOSTED_CHAPTER_MESSAGE_IDS.items():
            if chapter != 'ch05':
                self.assertEqual(set(), set(ids) & set(claimed),
                                 '%s already writes one of the ending ids' % chapter)

    def test_the_debug_boot_stages_each_arm_the_scene_branches_on(self):
        """`--ch05-ending=<arm>` puts the roster in the state its name claims.

        Asserted on what is LOADED, because that is the whole content of the boot: the ending
        reads the roster, so an arm that forgets to CUSA a unit blue films the wrong branch
        while looking like it worked.
        """
        chap = self._chap()
        seed = '    LOAD1(0x1, SEED)\n    ENUN\n'
        arms = {arm: inject.chapters.ch05.ch05_ending_debug_script(chap, seed, arm, 'CHARACTER_ARTUR',
                                                 inject.chapters.ch05.CH05_SAHNAR_TABLE, 'CHARACTER_MARISA')
                for arm in inject.chapter_ids.CH05_ENDING_ARMS}
        for arm, body in arms.items():
            self.assertIn('CALL(%s)' % inject.chapters.ch05.CH05_ENDING_SCRIPT, body, arm)
            self.assertIn(seed, body, '%s has no party, so the ring has no leader' % arm)
        self.assertIn('CUSA(CHARACTER_ARTUR)', arms['full'])
        self.assertIn('CUSA(CHARACTER_MARISA)', arms['full'])
        self.assertIn('ENUT(%s)' % inject.chapters.ch05.CH05_SAHNAR_TALK_FLAG, arms['full'],
                      'the berry beat reads the recruit FLAG, so the boot has to set it')
        self.assertIn('CUSA(CHARACTER_ARTUR)', arms['no-sahnar'])
        self.assertNotIn('CUSA(CHARACTER_MARISA)', arms['no-sahnar'])
        self.assertNotIn('ENUT(%s)' % inject.chapters.ch05.CH05_SAHNAR_TALK_FLAG, arms['no-sahnar'])
        self.assertNotIn('CUSA(CHARACTER_ARTUR)', arms['basil-died'])
        self.assertNotIn('CUSA(CHARACTER_MARISA)', arms['basil-died'])

    def test_the_debug_boot_always_arms_the_payout(self):
        """The give's placement relative to the closing fade is one of the things it films."""
        chap = self._chap()
        for arm in inject.chapter_ids.CH05_ENDING_ARMS:
            body = inject.chapters.ch05.ch05_ending_debug_script(chap, '    LOAD1(0x1, SEED)\n', arm,
                                               'CHARACTER_ARTUR', inject.chapters.ch05.CH05_SAHNAR_TABLE,
                                               'CHARACTER_MARISA')
            for site in chap['villages']:
                self.assertIn('ENUT(%s)' % inject.chapters.ch05.CH05_VILLAGE_FLAGS[site['id']], body,
                              '%s: %s is not armed' % (arm, site['id']))

    def test_the_debug_boot_refuses_to_build_without_a_party(self):
        """Without --ch05-boot there is no seed, and the ending gives its ring to the LEADER."""
        with self.assertRaises(SystemExit):
            inject.chapters.ch05.ch05_ending_debug_script(self._chap(), '', 'full', 'CHARACTER_ARTUR',
                                        inject.chapters.ch05.CH05_SAHNAR_TABLE, 'CHARACTER_MARISA')

    def test_every_ending_body_renders_at_the_backdrop_width(self):
        """Three bodies, every line inside 42, and every id emitted exactly once."""
        bodies = self._bodies()
        self.assertEqual(3, len(bodies))
        for msg, body in bodies.items():
            for line in body.replace('[LF]', '\n').split('\n'):
                text = re.sub(r'\[[^\]]*\]', '', line)
                self.assertLessEqual(font.text_px(text), font.TALK_BUDGET_PX,
                                     'MSG_%X overruns the full-screen window: %r' % (msg, text))


class ArenaTutorialPlaysInEveryMode(unittest.TestCase):
    """ch05's arena tutorial is SAFETY text, so it is not gated on tutorial mode (#303).

    `CHECK_TUTORIAL` is `!config.controller && !(chapterStateBits & PLAY_FLAG_HARD)`
    (eventscr.c:834) -- which is difficulty menu option 0 ONLY. Vanilla gates its arena
    tutorial that way, so on Normal and Difficult it simply never plays.

    We keep vanilla's ANATOMY but drop that one gate, because of what these two boxes
    actually say: a loss means the unit "will not be able to fight in any future battles",
    and B concedes for the fee. That is a permadeath warning and an escape hatch, not a
    flavour beat -- a Normal player who never sees it can lose a unit permanently to a
    mechanic nobody told them about. Nicolas, 2026-08-22: the arena tutorial and the crit
    warning ship on Normal, the rest of tutorial mode does not.

    Scope is exactly this one script: it is the ONLY `EventScr_CallOnTutorialMode` call in
    the build, so nothing else changes mode-gating with it. Every other teaching beat we
    ship (ch02's fliers-vs-bows warning) is plain dialogue and already played in all modes.
    """

    def test_the_arena_trigger_no_longer_calls_the_tutorial_mode_gate(self):
        self.assertNotIn('EventScr_CallOnTutorialMode', inject.chapters.ch05.ch05_arena_trigger_script())

    def test_the_trigger_keeps_its_player_only_faction_gate(self):
        # The OTHER gate must survive -- an enemy stepping on the tile must not fire it.
        script = inject.chapters.ch05.ch05_arena_trigger_script()
        self.assertIn('EventScr_UnTriggerIfNotFaction', script)
        self.assertIn('FACTION_ID_BLUE', script)

    def test_no_tutorial_mode_gate_remains_anywhere_in_the_build(self):
        # Guards the scope claim: if a future chapter adds one, this test says so rather
        # than letting mode-gated content appear again by inheritance.
        src = injector.injector_source()
        # The CALL SITE, not the word: the docstrings explain the gate we removed and why,
        # and banning the term would only push that explanation out of the code.
        self.assertEqual(src.count('CALL(EventScr_CallOnTutorialMode)'), 0)


if __name__ == '__main__':
    unittest.main()
