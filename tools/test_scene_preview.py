#!/usr/bin/env python3
"""Reading a rendered message body back into the boxes a player will actually press through.

`_script_to_message` turns an authored `script:` into FE8 text codes. This reads that back --
the same body the ROM ships -- so a scene can be looked at without building one. The reader is
the only new logic in the preview: everything else reuses the chapter's own message builders,
so a preview cannot disagree with the build about what a scene says.

Run: python3 tools/test_scene_preview.py
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import build_campaign as bc
import scene_preview as sp


class ReadingABody(unittest.TestCase):
    def test_each_A_closes_one_box(self):
        """[A] is the A-press: one box per press, which is what a scene COSTS the player."""
        boxes = sp.read_boxes('[OpenMidLeft][LoadFace][FID_Artur]\n'
                              '[OpenMidLeft]Hello.[A][X]')
        self.assertEqual(1, len(boxes))

    def test_a_box_carries_the_face_speaking_and_the_podium_it_speaks_from(self):
        """Who is on screen, and where. `[LoadFace]` seats a face at the podium `[OpenX]` named."""
        box, = sp.read_boxes('[OpenMidLeft][LoadFace][FID_Artur]\n'
                             '[OpenMidLeft]Hello.[A][X]')
        self.assertEqual('OpenMidLeft', box.podium)
        self.assertEqual('Artur', box.face)

    def test_LF_puts_two_drawn_lines_in_one_box(self):
        """A page is two visible lines joined by [LF] -- one A-press shows both."""
        box, = sp.read_boxes('[OpenMidLeft][LoadFace][FID_Artur]\n'
                             '[OpenMidLeft]first line[LF]\nsecond line[A][X]')
        self.assertEqual(['first line', 'second line'], box.lines)

    def test_the_LF_that_follows_an_A_is_the_page_break_not_a_blank_line(self):
        """`_script_to_message` joins pages with `[A][LF]`. Read naively that trailing [LF]
        opens the next box with an empty first line, and every long turn in the campaign
        previews with a phantom blank -- which is exactly what the throwaway spike did."""
        first, second = sp.read_boxes('[OpenMidLeft][LoadFace][FID_Artur]\n'
                                      '[OpenMidLeft]page one[A][LF]\npage two[A][X]')
        self.assertEqual(['page one'], first.lines)
        self.assertEqual(['page two'], second.lines)


class StageBeatsThatCostNoPress(unittest.TestCase):
    """Things that happen BETWEEN boxes. They are why a scene reads the way it does on film,
    and a preview that drops them shows a face standing at its podium through lines it has
    already left (`exits:`, which is what ch05 scene 1's last three boxes are about)."""

    def test_a_face_leaving_is_a_step_but_not_a_box(self):
        steps = sp.read_scene('[OpenMidRight][LoadFace][FID_Marisa]\n'
                              '[OpenMidRight]Go on, now.[A]\n'
                              '[OpenMidRight][ClearFace]\n'
                              '[OpenMidLeft][LoadFace][FID_Artur]\n'
                              '[OpenMidLeft]...And there she stays.[A][X]')
        self.assertEqual(['box', 'exit', 'box'], [s.kind for s in steps])
        self.assertEqual('Marisa', steps[1].face)
        self.assertEqual(2, len(sp.read_boxes('[OpenMidRight][LoadFace][FID_Marisa]\n'
                                              '[OpenMidRight]Go on, now.[A]\n'
                                              '[OpenMidRight][ClearFace]\n'
                                              '[OpenMidLeft][LoadFace][FID_Artur]\n'
                                              '[OpenMidLeft]...And there she stays.[A][X]')))

    def test_the_talk_break_is_a_step_but_not_a_box(self):
        """`stage_break` hands the scene to the event script mid-message: the bubble closes,
        something wordless happens, TEXTCONT brings it back. No press."""
        steps = sp.read_scene('[OpenMidLeft][LoadFace][FID_Artur]\n'
                              '[OpenMidLeft]Look out![A][CloseSpeechSlow]\n[BreakTalk]\n'
                              '[OpenMidRight][LoadFace][FID_Marisa]\n'
                              '[OpenMidRight]...[A][X]')
        self.assertEqual(['box', 'pause', 'box'], [s.kind for s in steps])

    def test_faceless_narration_is_not_attributed_to_the_last_speaker(self):
        """A faceless speaker emits NO [OpenX] on purpose -- opening one anchors the window to
        an absent portrait's mouth and the box renders as a mis-placed sliver. So the podium
        the reader last saw is still the PREVIOUS speaker's, and carrying it forward would
        caption the campaign's narration with whoever happened to talk before it."""
        _spoken, narration = sp.read_boxes('[OpenMidLeft][LoadFace][FID_Artur]\n'
                                           '[OpenMidLeft]Hm.[A]\n'
                                           'The snow does not stop.[A][X]')
        self.assertIsNone(narration.face)
        self.assertIsNone(narration.podium)

    def test_narration_after_a_SILENT_face_is_not_attributed_to_it_either(self):
        """The same trap one move earlier. `present:`/`preload` seat silent listeners before
        the first bubble opens, so the last [OpenX] the reader saw is a face-management open
        and not a speaker's -- and a faceless beat after it inherits a listener who never
        said a word."""
        narration, = sp.read_boxes('[OpenFarLeft][LoadFace][FID_Artur]\n'
                                   'The snow does not stop.[A][X]')
        self.assertIsNone(narration.face)
        self.assertIsNone(narration.podium)

    def test_narration_after_a_face_LEAVES_is_not_seated_at_the_vacated_podium(self):
        """`exits:` emits [OpenX][ClearFace] -- also face management, also not a speaker."""
        _spoken, _exit, narration = sp.read_scene('[OpenMidRight][LoadFace][FID_Marisa]\n'
                                                  '[OpenMidRight]Go on, now.[A]\n'
                                                  '[OpenMidRight][ClearFace]\n'
                                                  'And there she stays.[A][X]')
        self.assertIsNone(narration.face)
        self.assertIsNone(narration.podium)


class TheRegistry(unittest.TestCase):
    """The preview reads the chapter's OWN message builders, so it cannot disagree with the
    build about what a scene says. These run against the real ch05 YAML."""

    def test_scene_1_reads_back_as_the_locked_basil_and_sahnar_scene(self):
        scene = sp.preview('ch05/1')
        self.assertEqual(0x9E9, scene.msg_id)
        self.assertEqual('basil', scene.boxes[0].speaker)
        self.assertEqual('Sahnar! Sahnar, the moose came back, the',
                         scene.boxes[0].lines[0])

    def test_the_press_count_is_read_off_the_BODY_not_the_authored_box_count(self):
        """#311 and `decisions.md` both said presses == authored boxes, "the wrapper never
        invents a page break". It does: a turn wrapping past two lines pages, and each page
        is its own press. Scene 1 is 19 authored boxes and costs the player 23. Reporting the
        authored count would have under-priced every scene with a long line in it."""
        _slot, _msg, authored, _what = bc.CH05_OPENING_SLOTS[0]
        self.assertEqual(19, authored)
        self.assertEqual(23, len(sp.preview('ch05/1').boxes))

    def test_a_builder_that_returns_one_bare_body_is_registered_like_any_other(self):
        """Most builders return [(msg_id, body)]; the one-box ones return the body itself.
        The registry names a message id either way, so the caller never has to know which."""
        scene = sp.preview('ch05/eruption')
        self.assertEqual(bc.CH05_ERUPTION_MSG, scene.msg_id)
        self.assertEqual('ravisin', scene.boxes[0].speaker)

    def test_a_battle_quote_is_previewed_against_the_BATTLE_bubble_budget(self):
        """`PutTalkBubble` HARD-FORCES 20 tiles for a quote shown during a battle animation and
        ignores the text width entirely -- 143px, not the talk bubble's 203. Previewing one at
        the wrong budget would clear a line the ROM wraps off the tilemap."""
        self.assertEqual(sp.BATTLE, sp.preview('ch05/ravisin-death').width)

    def test_every_registered_scene_renders(self):
        """A registry entry pointing at an id its builder no longer writes is the failure mode
        here, and it is silent until someone opens that scene."""
        for key in sp.registry():
            self.assertTrue(sp.preview(key).boxes, key)


class StaticChecksTheRomCannotCheaplyGive(unittest.TestCase):
    def test_no_two_scenes_claim_the_same_message_id(self):
        """A copy-pasted registry row pointing at a neighbour's id previews the WRONG scene
        under the right name, and goldens the wrong scene with it. The build's
        `assert_message_ids_unique` guards the injectors; this guards the registry."""
        seen = {}
        for key, (_title, msg_id, _builder, _width) in sp.registry().items():
            self.assertNotIn(msg_id, seen,
                             '%s and %s both claim MSG_%03X' % (seen.get(msg_id), key, msg_id))
            seen[msg_id] = key

    def test_claiming_a_key_twice_is_refused(self):
        """ch05/1..3 are generated from CH05_OPENING_SLOTS while ch05/4 onward are written by
        hand, so a FOURTH opening slot would generate a `ch05/4` the hand-written row then
        overwrites -- dropping that scene from --list, from `make scene` and from the golden
        book, with its message id reachable from no key at all. Silent, until someone goes
        looking for a scene that is simply not there."""
        reg = {}
        sp._claim(reg, 'ch05/4', 'first', 0x1, None, sp.TALK)
        with self.assertRaises(KeyError):
            sp._claim(reg, 'ch05/4', 'second', 0x2, None, sp.TALK)

    def test_every_branched_scene_registers_BOTH_arms(self):
        """An arm nobody can look at is an arm nobody proofreads -- and the no-Lupin arms are
        the ones that never play on the plain boot ROM, so film does not cover them either."""
        keys = set(sp.registry())
        branched = [k for k in keys if k + '-no-lupin' in keys]
        self.assertTrue(branched)
        for key in branched:
            self.assertNotEqual(sp.preview(key).boxes,
                                sp.preview(key + '-no-lupin').boxes, key)


class Formatting(unittest.TestCase):
    def test_a_line_over_the_channel_budget_is_called_out(self):
        """The whole point of previewing: an over-wide line runs off PutTalkBubble's unclamped
        right edge in-game (the ch03 crier bug). It has to be visible on the page, not found
        on film."""
        wide = 'W' * 40                       # 8px a glyph: 320px against the bubble's 203
        scene = sp.Scene('x', 'x', 0x1, sp.TALK,
                         [sp.Box('box', 'OpenMidLeft', 'Artur', [wide], 'basil')], None)
        self.assertIn('OVER', sp.format_scene(scene._replace(boxes=scene.steps)))

    def test_no_authored_ch05_scene_overflows_its_channel(self):
        """The inverse, and the one that matters: what ships is clean."""
        for key in sp.registry():
            self.assertNotIn('OVER', sp.format_scene(sp.preview(key)), key)


class TheGoldenMaster(unittest.TestCase):
    """Box rendering is deterministic, so a scene approved once stays verified for free
    (Feathers/Falco). The generated book IS the golden: `check_generated_indexes_fresh` already
    regenerates docs/CHAPTERS.md in memory and diffs it, so a scene book needs no new machinery."""

    def test_a_book_holds_that_chapter_s_scenes_in_registry_order(self):
        """Scoped to the chapter, because registering ch06 must not fail ch05's book -- and
        checked as an ORDERED list, because `assertIn` on a key passes trivially against its
        own `-no-lupin` twin."""
        book = sp.generate('ch05')
        want = [k for k in sp.registry() if k.split('/')[0] == 'ch05']
        found = [ln.split('  ')[0] for ln in book.split('\n') if ln.startswith('ch05/')]
        self.assertEqual(want, found)

    def test_the_book_is_deterministic(self):
        """It is diffed against a committed file, so anything unstable in it -- a dict order,
        a timestamp -- would fail the check on an unrelated commit and train everyone to
        regenerate without reading the diff."""
        self.assertEqual(sp.generate('ch05'), sp.generate('ch05'))

    def test_every_committed_book_matches_what_the_yaml_renders_today(self):
        """The regression gate: a wrap or staging change that moves a box fails HERE, with no
        ROM build and no playtest run.

        Every REGISTERED chapter, not a hardcoded ch05 -- `--write` writes a book per chapter,
        so naming one here would let a second chapter's book be generated and then never
        diffed, which is a golden that exists and guards nothing."""
        chapters = sorted({k.split('/')[0] for k in sp.registry()})
        self.assertTrue(chapters)
        for chapter in chapters:
            path = sp.book_path(chapter)
            self.assertTrue(os.path.isfile(path),
                            '%s has no committed book -- regenerate: '
                            'python3 tools/scene_preview.py --write' % chapter)
            with open(path, encoding='utf-8') as fh:
                self.assertEqual(fh.read(), sp.generate(chapter),
                                 'docs/scenes/%s.md is stale -- regenerate: '
                                 'python3 tools/scene_preview.py --write' % chapter)


if __name__ == '__main__':
    unittest.main()
