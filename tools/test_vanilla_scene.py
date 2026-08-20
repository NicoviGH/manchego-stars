"""Regression tests for tools/vanilla_scene.py -- the vanilla dialogue miner.

Guards the bug that made this tool actively misleading (found 2026-07-29): it
matched TEXTSHOW only, so every Text_BG scene was silently dropped. FE8 Ch5 puts
its two Grado command scenes on a backdrop, so the miner reported that chapter's
opening as 8 messages when it is 11 -- omitting exactly the two scenes ch05's
0x9BC and 0x9BD are modelled on. A miner that under-reports is worse than one that
errors: it reads as evidence that vanilla lacks a beat.
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CH5 = os.path.join(REPO, 'fireemblem8u', 'src', 'events', 'ch5-eventscript.h')


@unittest.skipUnless(os.path.isfile(CH5), 'fireemblem8u submodule not checked out')
class VanillaSceneChannels(unittest.TestCase):
    """Both text channels are mined, in source order, with the channel reported."""

    def setUp(self):
        import vanilla_scene
        self.vs = vanilla_scene
        # Mine HEAD, exactly as main() does -- NOT the on-disk file. ch5-eventscript.h is
        # where inject_ch04 hosts our Ch4, so after any `make CH04BOOT=1` the working-tree
        # copy has no Ch5 scenes at all and this suite errors on a missing scene name. That
        # is the same trap the tool itself was fixed for (46f8b12): a test that reads the
        # built tree is measuring our injection, not vanilla.
        self.scenes = dict(vanilla_scene.scene_text_ids(
            CH5, src=vanilla_scene._decomp_text('src/events/ch5-eventscript.h')))
        self.opening = self.scenes['EventScr_Ch5_BeginningScene']

    def test_beginning_scene_has_all_eleven_messages(self):
        """0x9BA-0x9C4 inclusive. A TEXTSHOW-only scan finds 8 of these."""
        self.assertEqual([mid for mid, _chan in self.opening],
                         [0x9BA, 0x9BB, 0x9BC, 0x9BD, 0x9BE,
                          0x9BF, 0x9C0, 0x9C1, 0x9C2, 0x9C3, 0x9C4])

    def test_the_two_backdrop_scenes_are_not_dropped(self):
        """0x9BC (Glen briefs Saar) and 0x9BD (Glen and Cormag) are Text_BG.

        These are the scenes the bug hid, and the ones our 0x9BC/0x9BD copy.
        """
        chan = dict(self.opening)
        self.assertEqual(chan[0x9BC], 'BG_SERAFEW_VILLAGE')
        self.assertEqual(chan[0x9BD], 'BG_SERAFEW_VILLAGE')

    def test_a_bare_textshow_under_a_backdrop_is_not_on_map(self):
        """`SetBackground` + bare `TEXTSHOW` is a BACKDROP scene, not a bubble.

        The second half of the same bug, and the one that outlived the first fix: the
        miner classified by the TEXT CALL alone, so every scene vanilla plays as
        `SetBackground(BG_X)` followed by a plain `TEXTSHOW` came back as "map". Both of
        ch5's are (0x9BB the meet-cute, 0x9BE/0x9BF the arrival), and `decisions.md` ->
        "A cutscene's CHANNEL is inherited from the twin" already names 0x9BB as a
        reporting artifact -- it just could not fix it from inside the tool.

        `EventScr_SetBackground` (events_script_utils.c:224) is FADI + REMOVEPORTRAITS +
        BACG + FADU: the backdrop is UP from that point, and it stays up across `REMA`,
        which is why 0x9BF is still BG_TOWN with no second SetBackground of its own.
        """
        chan = dict(self.opening)
        self.assertEqual(chan[0x9BB], 'BG_SERAFEW_VILLAGE')
        self.assertEqual(chan[0x9BE], 'BG_TOWN')
        self.assertEqual(chan[0x9BF], 'BG_TOWN')

    def test_on_map_messages_report_the_map_channel(self):
        """The channel is load-bearing: on-map bubbles wrap at 29 chars, Text_BG ~42.

        These five are the real bubbles: `CALL(EventScr_TextShowWithFadeIn)` (FADI +
        TEXTSTART + CLEAN + FADU) took BG_TOWN back down at 0x9BF's end, and every one
        of them opens on its own `TEXTSTART` with no backdrop in front of it.
        """
        chan = dict(self.opening)
        for mid in (0x9C0, 0x9C1, 0x9C2, 0x9C3, 0x9C4):
            self.assertEqual(chan[mid], 'map', 'MSG_%X should be on-map' % mid)

    def test_the_ending_scene_is_a_backdrop_scene(self):
        """`EventScr_Ch5_EndingScene` plays over BG_SERAFEW_VILLAGE, all three messages.

        This is the reading ch05's scenes 16/17 inherit their channel from, and the one
        the old miner got wrong: it reported all three as "map", and that artifact was
        copied into the ch05 YAML's mined note ("ON-MAP so bubbles wrap at 29"), into
        issue #25 and into HANDOFF. The script is FADI(16) -- the map goes DOWN -- then
        SetBackground, then bare TEXTSHOWs; there is no TEXTSTART anywhere in it.
        """
        ending = dict(self.scenes['EventScr_Ch5_EndingScene'])
        self.assertEqual([mid for mid, _c in self.scenes['EventScr_Ch5_EndingScene']],
                         [0x9C9, 0x9CA, 0x9CB])
        for mid in (0x9C9, 0x9CA, 0x9CB):
            self.assertEqual(ending[mid], 'BG_SERAFEW_VILLAGE',
                             'MSG_%X is a backdrop scene' % mid)

    def test_the_talk_recruit_really_is_on_map(self):
        """0x9CC opens on `TEXTSTART` with no backdrop -- our scene 14's 29 is correct.

        Asserted beside the ending so the pair reads as the contrast it is: the two
        scenes sit forty lines apart in one file and take DIFFERENT channels.
        """
        talk = dict(self.scenes['EventScr_089F2270'])
        self.assertEqual(talk[0x9CC], 'map')

    def test_source_order_is_preserved_across_channels(self):
        """The two call FORMS interleave; neither may be grouped ahead of the other.

        `Text_BG(BG, id)` and bare `TEXTSHOW(id)` alternate through this opening, and a
        scan that collected one form and then the other would still report all eleven
        ids -- just in the wrong order, which is worse than missing them. Asserted on the
        CHANNEL sequence rather than the call form, because the channel is now state: the
        opening walks BG_SERAFEW_VILLAGE -> BG_TOWN -> map, in that order and once each.
        """
        chans = [chan for _mid, chan in self.opening]
        self.assertEqual(chans, ['BG_SERAFEW_VILLAGE'] * 4 + ['BG_TOWN'] * 2 + ['map'] * 5)

    def test_the_mid_battle_and_talk_scenes_stay_separate(self):
        """The escalation and the Talk-recruit are their own event lists, not the opening.

        ch05 leans on this: 0x9BA-0x9C4 is ONE pre-map list (so nothing in it can
        interleave), while 0x9C5 and 0x9CC carry real triggers.
        """
        # setUp's HEAD-mined scenes, not the working tree: EventScr_089F22A4 is the very
        # slot inject_ch04 repurposes for its turn-2 reveal cutscene, so on a built tree
        # this would assert against OUR script and report vanilla's 0x9C5 as ch04's stubs.
        self.assertEqual([m for m, _c in self.scenes['EventScr_089F22A4']], [0x9C5])
        self.assertEqual([m for m, _c in self.scenes['EventScr_089F2270']], [0x9CC])


@unittest.skipUnless(os.path.isfile(CH5), 'fireemblem8u submodule not checked out')
class MessageBodiesComeFromHead(unittest.TestCase):
    """The bodies are read at HEAD, never from the working tree.

    `texts/texts.txt` is the FIRST entry in `build_campaign.PATCHED_DECOMP_FILES` -- the build
    rewrites it in place with OUR campaign text under vanilla's own MSG ids. A miner that
    opened it directly would hand our own lines back as the vanilla pacing benchmark, which is
    worse than under-reporting because it reads as independent evidence. Found reviewing
    PR #196, where the tool shipped reading the working tree; these two tests are the guard.
    """

    def test_bodies_do_not_come_from_the_working_tree(self):
        """Deterministic: make any working-tree read of texts.txt fail, and still succeed."""
        import builtins
        import vanilla_scene
        real_open = builtins.open

        def guarded(path, *a, **kw):
            if 'texts.txt' in str(path):
                raise AssertionError('load_messages() read the working tree, not HEAD')
            return real_open(path, *a, **kw)

        builtins.open = guarded
        try:
            msgs = vanilla_scene.load_messages()
        finally:
            builtins.open = real_open
        self.assertGreater(len(msgs), 3000)

    def test_the_body_it_returns_is_vanillas(self):
        """MSG_9BB is vanilla's Joshua/Natasha meet-cute -- the slot ch05's 0x9BB replaces.

        If this ever returns OUR text, the miner is reading a built tree.
        """
        import vanilla_scene
        body = vanilla_scene.load_messages()[0x9BB]
        self.assertIn('FID_Natasha', body)
        self.assertNotIn('Sahnar', body)


if __name__ == '__main__':
    unittest.main()
