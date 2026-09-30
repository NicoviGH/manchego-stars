#!/usr/bin/env python3
"""Tests for tools/inject/text.py.

Run:  python3 tools/test_inject_text.py
"""
import os
import re
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import inject.chapter_ids
import inject.chapters.ch05
import inject.hosting
import inject.text
import fe8_talk_font as font


class WrappingMeasuresPixelsNotCharacters(unittest.TestCase):
    """`_wrap_fe_lines` used to take a CHARACTER width. The engine has never counted characters:
    `GetStrTalkLen` (scene.c) sums `glyph->width` in pixels and `StartTalkExt` divides that into
    tiles. See `docs/decisions.md` -> "We wrapped on-map talk at 29 CHARACTERS".
    """

    def test_a_line_of_narrow_glyphs_is_allowed_to_be_LONGER(self):
        """The whole gain. Under a character rule these two wrap identically; under the real
        constraint the thin one earns more characters because it DRAWS narrower."""
        narrow = ' '.join(['illililli'] * 6)
        wide = ' '.join(['WWWWWWWWW'] * 6)
        self.assertGreater(len(inject.text._wrap_fe_lines(narrow)[0]),
                           len(inject.text._wrap_fe_lines(wide)[0]))

    def test_no_emitted_line_exceeds_the_budget_vanilla_proves_safe(self):
        text = ('The witch has lost her way. She is disturbing the dead, and I have counted '
                'every one of them since the stone closed over me.')
        for line in inject.text._wrap_fe_lines(text):
            self.assertLessEqual(font.text_px(line), font.TALK_BUDGET_PX, repr(line))

    def test_the_budget_sits_inside_the_band_vanilla_actually_ships(self):
        """Calibrated against the WHOLE corpus, not one message -- which is the mistake the old
        29-character rule made (it generalised MSG_910, a narrow message, into a ceiling).

        Measured over all 35,483 drawn lines in vanilla's `texts.txt`: the 99th percentile is
        197px, the 99.9th is 211px, and just 38 lines exceed 210px (all of them epilogue cards
        and system menus, which are not the talk window). A budget in the high 190s therefore
        emits everything vanilla emits in this channel without sitting on the extreme tail."""
        self.assertGreaterEqual(font.TALK_BUDGET_PX, 197)   # vanilla's 99th percentile
        self.assertLessEqual(font.TALK_BUDGET_PX, 211)      # its 99.9th

    def test_the_dash_glue_still_holds_and_still_fits(self):
        """The one pre-existing invariant this must not break: a bare `--` never opens a line,
        and the line it lands on still has to fit."""
        wrapped = inject.text._wrap_fe_lines('Struck off edges. There was fighting here -- long ago now')
        self.assertFalse(any(l.startswith('--') for l in wrapped))
        for line in wrapped:
            self.assertLessEqual(font.text_px(line), font.TALK_BUDGET_PX, repr(line))

    def test_ch05s_talk_recruit_gets_cheaper_without_losing_a_word(self):
        """The measurable payoff, asserted on real authored prose rather than a fixture."""
        chap = inject.hosting._load_chapter_yaml('rime-of-the-frostmaiden', inject.chapter_ids.CH05_CHAPTER_YAML)
        event = next(e for e in chap['events'] if e['trigger'] == 'sahnar_talk')
        box8 = next(iter(event['script'][7].values()))
        self.assertEqual(1, len(inject.text._wrap_fe_lines(box8)) // 2 + len(inject.text._wrap_fe_lines(box8)) % 2,
                         'the wolf proof used to page in two and now fits one box')


class ASpeakerWhoLeavesMidSceneFadesOut(unittest.TestCase):
    """`exits:` is the script directive for a speaker who WALKS OFF while the scene runs on.

    Found by Nicolas watching ch05's opening (2026-08-14): Sahnar goes, and then Basil delivers
    three boxes about her absence — *"...And there she stays."* — with Sahnar still standing at
    her podium the whole time. The stage direction was in the YAML as a comment ("She goes. A few
    steps on root-feet.") and nothing rendered it.

    `_script_to_message`'s podium manager infers a face LOAD from who speaks next, but it cannot
    infer a face EXIT: nobody speaks from that podium again, so it has no reason to touch it. Its
    own docstring names this as the one control it does not infer. `[OpenX][ClearFace]` is FE8's
    own answer — scene.c fades that podium's face over ~16 frames and frees its gFaces slot.
    """
    def _msg(self, script, staging=None):
        return inject.text._script_to_message(script, staging or {
            'basil':  ('[OpenMidLeft]', '[FID_Artur]'),
            'sahnar': ('[OpenMidRight]', '[FID_Marisa]')})

    def test_the_leaving_speakers_podium_is_cleared_where_she_goes(self):
        out = self._msg([{'sahnar': 'Go on, now.'},
                         {'exits': 'sahnar'},
                         {'basil': '...And there she stays.'}])
        self.assertIn('[OpenMidRight][ClearFace]', out)
        # Locate the line by its FIRST WORDS rather than the whole sentence: where the wrap
        # puts its [LF] is not what this test is about, and asserting on the unbroken string
        # made a wrap change look like a staging bug.
        self.assertLess(out.index('[OpenMidRight][ClearFace]'), out.index('...And there she'),
                        'she has to be gone BEFORE the line about her being gone')

    def test_the_remaining_speaker_is_untouched(self):
        out = self._msg([{'basil': 'one'}, {'sahnar': 'two'},
                         {'exits': 'sahnar'}, {'basil': 'three'}])
        self.assertEqual(1, out.count('[FID_Artur]'), 'Basil must not be reloaded or cleared')
        self.assertNotIn('[OpenMidLeft][ClearFace]', out)

    def test_an_exit_breaks_the_same_speaker_coalescing(self):
        """Basil's boxes either side of the exit must NOT merge into one block, or the
        [ClearFace] would land after both and the fade would play too late."""
        out = self._msg([{'sahnar': 'Go on, now.'}, {'basil': 'before'},
                         {'exits': 'sahnar'}, {'basil': 'after'}])
        self.assertLess(out.index('before'), out.index('[OpenMidRight][ClearFace]'))
        self.assertLess(out.index('[OpenMidRight][ClearFace]'), out.index('after'))

    def test_a_speaker_who_returns_gets_a_fresh_face(self):
        out = self._msg([{'sahnar': 'one'}, {'exits': 'sahnar'},
                         {'basil': 'two'}, {'sahnar': 'three'}])
        self.assertEqual(2, out.count('[LoadFace][FID_Marisa]'))

    def test_exiting_someone_who_is_not_on_screen_fails_loudly(self):
        """A drifted directive is a silent no-op otherwise, which is how the bug it fixes
        got shipped in the first place."""
        with self.assertRaises(SystemExit):
            self._msg([{'basil': 'one'}, {'exits': 'sahnar'}])

    def test_the_directive_is_not_counted_as_a_box(self):
        """Box counts are locked per scene. A stage direction is not an A-press."""
        script = [{'basil': 'one'}, {'exits': 'sahnar'}, {'basil': 'two'}]
        self.assertEqual(2, inject.text._script_box_count(script))

    def test_ch05_scene_1_actually_carries_it(self):
        chap = inject.hosting._load_chapter_yaml('rime-of-the-frostmaiden', inject.chapter_ids.CH05_CHAPTER_YAML)
        script = inject.chapters.ch05._chapter_event_by_slot(chap, 'chapter_start', 'vanilla 0x9BB', 'test')['script']
        exits = [i for i, e in enumerate(script) if 'exits' in e]
        self.assertEqual(1, len(exits), 'Sahnar leaves exactly once')
        self.assertEqual('sahnar', script[exits[0]]['exits'])
        self.assertEqual('...And there she stays.',
                         inject.text._fe_dialogue_text(next(iter(script[exits[0] + 1].values()))),
                         'the exit sits immediately before the line about her absence')
        body = dict(inject.chapters.ch05.ch05_opening_messages(chap))[0x9E9]
        self.assertLess(body.index('[OpenMidRight][ClearFace]'), body.index('And there she stays'))


class TheDashGlueRespectsTheLineWidth(unittest.TestCase):
    """`_wrap_fe_lines` keeps a bare '--' off the start of a line by gluing it to the word
    before it -- but it did that without re-measuring, so a line that ended exactly at the
    budget came out over it. Found by ch05's scene 4, and it reaches every chapter: the glue
    is in the shared wrapper, not in any one scene.

    These now measure in PIXELS, because the wrapper does (`decisions.md` -> "We wrapped on-map
    talk at 29 CHARACTERS; the engine measures PIXELS"). The three invariants are unchanged in
    MEANING: the dash never opens a line, the line it lands on still fits, and the one case that
    genuinely cannot hold is stated rather than hidden.
    """
    BUDGETS = (120, 160, 190, 200, 210)

    def test_the_glued_dash_never_pushes_a_line_past_the_budget(self):
        line = 'Struck off edges. There was fighting here -- a great deal of it.'
        for budget in self.BUDGETS:
            for out in inject.text._wrap_fe_lines(line, budget):
                self.assertLessEqual(font.text_px(out), budget,
                                     '%r at %dpx' % (out, budget))

    def test_the_budget_holds_across_every_dash_position_in_a_line(self):
        """One sentence exercises one boundary. Walk the dash through every gap at a spread of
        budgets, so the fix is not merely right for the line that found the bug."""
        words = 'Struck off edges there was fighting here a great deal of it'.split()
        for i in range(1, len(words)):
            text = ' '.join(words[:i] + ['--'] + words[i:])
            for budget in range(100, 210, 7):
                for out in inject.text._wrap_fe_lines(text, budget):
                    if out.endswith(' --') and ' ' not in out[:-3]:
                        continue          # atomic word+dash: see the docstring's RESIDUAL
                    self.assertLessEqual(font.text_px(out), budget,
                                         '%r at %dpx (dash after %r)' % (out, budget, words[i - 1]))

    def test_an_unfittable_word_plus_dash_stays_atomic_rather_than_splitting(self):
        """The one case the budget CANNOT hold, stated so it is a known shape and not a
        surprise: the pair is indivisible, so it goes out over-budget and alone."""
        out = inject.text._wrap_fe_lines('I Auril-the-Frostmaiden-herself-and-then-some -- yes.', 120)
        self.assertIn('Auril-the-Frostmaiden-herself-and-then-some --', out)
        over = [l for l in out if font.text_px(l) > 120]
        self.assertEqual(['Auril-the-Frostmaiden-herself-and-then-some --'], over,
                         'only the atomic pair may exceed the budget')

    def test_the_dash_still_never_opens_a_line(self):
        """The reason the glue exists. When it cannot fit, the WORD moves down with it."""
        for budget in self.BUDGETS:
            for out in inject.text._wrap_fe_lines('There was fighting here -- a great deal of it.', budget):
                self.assertFalse(out.startswith('--'), '%r at %dpx' % (out, budget))

    def test_a_dash_that_fits_is_still_glued_where_it_was(self):
        wide = font.text_px('a b --')
        self.assertEqual(['a b --', 'c'], inject.text._wrap_fe_lines('a b -- c', wide))


class SilentPresenceDirective(unittest.TestCase):
    """`present:` — a character is on screen for a scene and never speaks (#25).

    It exists because ch05's scene 3 has to SHOW Ravisin's raised Sahnar without spending a box
    on it. Nicolas, 2026-08-14: "you don't need to even add lines... just add sahnars portrait
    to the scene."

    It renders as a PRELOAD, and that is the engine's call rather than a design one:
    `TalkPrepNextChar` reopens the talk bubble whenever the active face differs from the
    speaking one, so a silent face loaded mid-message opens a bubble of its own and the scene
    plays with two stacked bubbles. Vanilla's silent loads are all preloads (MSG_0954, 095D,
    095E); it never loads a face mid-message without having it speak next.
    """
    STAGING = {'a': ('[OpenMidLeft]', '[FID_Artur]'),
               'b': ('[OpenMidRight]', '[FID_Riev]'),
               'c': ('[OpenFarRight]', '[FID_Marisa]')}

    def _msg(self, script, **kw):
        return inject.text._script_to_message(script, self.STAGING, **kw)

    def test_it_loads_the_face_without_opening_a_box(self):
        out = self._msg([{'present': 'c'}, {'a': 'one'}, {'a': 'two'}])
        self.assertIn('[OpenFarRight][LoadFace][FID_Marisa]', out)
        self.assertEqual(2, out.count('[A]'), 'a presence is staging, not an A-press')

    def test_it_is_not_a_box(self):
        self.assertIn('present', inject.text.SCRIPT_DIRECTIVES)
        self.assertEqual(2, inject.text._script_box_count(
            [{'present': 'c'}, {'a': 'one'}, {'a': 'two'}]))

    def test_the_face_is_PRELOADED_before_any_text(self):
        """The engine's rule, not ours. `TalkPrepNextChar` reopens the talk bubble whenever the
        active face differs from the speaking one, so a silent face loaded mid-message opens a
        bubble of its own and the scene plays with two stacked bubbles -- filmed 2026-08-14.
        Vanilla's silent loads are all preloads (MSG_0954, 095D, 095E); it never loads a face
        mid-message without having it speak next (MSG_904, 092C, 095A)."""
        out = self._msg([{'a': 'one'}, {'present': 'c'}, {'a': 'two'}])
        self.assertLess(out.index('[LoadFace][FID_Marisa]'), out.index('one'),
                        'a silent face must be up before the first bubble opens')

    def test_it_does_not_break_same_speaker_coalescing(self):
        """It is not a mid-scene event, so it must not split a speaker's consecutive turns into
        two blocks: their two pages stay inside ONE [OpenX] run, joined by [A][LF]. A re-opened
        podium between them would be a second bubble by another road."""
        out = self._msg([{'present': 'c'}, {'a': 'one'}, {'a': 'two'}])
        self.assertIn('one[A][LF]\ntwo[A]', out)
        # the only [OpenMidLeft]s are the load and the single block that follows it
        self.assertEqual(2, out.count('[OpenMidLeft]'))

    def test_a_presence_with_no_podium_is_refused(self):
        with self.assertRaises(SystemExit):
            self._msg([{'present': 'nobody'}, {'a': 'one'}])

    def test_staged_names_sees_silent_presences_and_departures(self):
        script = [{'a': 'one'}, {'present': 'c'}, {'exits': 'a'}]
        self.assertEqual({'a', 'c'}, inject.chapters.ch05._script_staged_names(script))

    def test_a_present_character_may_LATER_leave(self):
        """Staged silently, then walks off -- a legal scene, and the `exits:` guard used to
        hard-exit the build on it: the preload recorded the podium under an anonymous sentinel,
        so the leaver looked like an impostor holding somebody else's seat."""
        out = self._msg([{'present': 'c'}, {'a': 'one'}, {'exits': 'c'}, {'a': 'two'}])
        self.assertIn('[OpenFarRight][ClearFace]', out)
        self.assertLess(out.index('one'), out.index('[OpenFarRight][ClearFace]'))

    def test_an_anonymous_preload_still_cannot_be_exited(self):
        """The sentinel still does its job for callers passing `preload` directly: nobody
        holds those podiums by name, so `exits:` on one is still the error it always was."""
        with self.assertRaises(SystemExit):
            self._msg([{'a': 'one'}, {'exits': 'c'}],
                      preload=[('[OpenFarRight]', '[FID_Marisa]')])

    def test_sharing_a_podium_with_a_speaker_is_refused_too(self):
        """Distance 0, not just 1 -- and it is the WORSE case: the renderer clears the silent
        face outright the moment its podium-holder speaks, so it is destroyed before the first
        box rather than merely buried. The shared podium tables pair names onto tags, so this
        is the easy way to hit it."""
        script = [{'ravisin': 'one'}, {'present': 'sahnar'}]
        with self.assertRaises(SystemExit):
            inject.chapters.ch05.assert_silent_faces_have_elbow_room(
                script, {'ravisin': '[OpenMidRight]', 'sahnar': '[OpenMidRight]'}, 'test')


class SetMessageBodyReplacesTheWholeBody(unittest.TestCase):
    """A message body runs to the NEXT header, not to the first blank line.

    74 vanilla messages contain a mid-body blank line -- a scene with a [BreakTalk] between
    stanzas. Stopping at the first blank replaced only the opening stanza and left the rest
    of vanilla's scene sitting inside our message: ch02's Halvar bark took MSG_AC2 and kept
    Ephraim and Duessel discussing the Dark Stone underneath it. The ROM decoder stops at our
    [X] so verify_text saw nothing, which is exactly what makes it worth a test.
    """

    def _doc(self):
        return ['## MSG_001', 'first line', '', 'second stanza', 'third line', '',
                '## MSG_002', 'untouched', '']

    def test_a_body_with_a_blank_line_is_fully_replaced(self):
        lines = self._doc()
        inject.text.set_message_body(lines, 0x001, 'NEW[X]')
        self.assertEqual(['## MSG_001', 'NEW[X]', '', '## MSG_002', 'untouched', ''], lines)

    def test_the_next_message_is_untouched(self):
        lines = self._doc()
        inject.text.set_message_body(lines, 0x001, 'NEW[X]')
        self.assertEqual('untouched', lines[lines.index('## MSG_002') + 1])

    def test_a_simple_body_still_round_trips(self):
        lines = ['## MSG_001', 'old', '', '## MSG_002', 'keep', '']
        inject.text.set_message_body(lines, 0x001, 'new')
        self.assertEqual(['## MSG_001', 'new', '', '## MSG_002', 'keep', ''], lines)

    def test_replacing_the_last_message_does_not_run_off_the_end(self):
        lines = ['## MSG_001', 'old', '', 'more', '']
        inject.text.set_message_body(lines, 0x001, 'new')
        self.assertEqual(['## MSG_001', 'new', ''], lines)


if __name__ == '__main__':
    unittest.main()
