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
        scenes = dict(vanilla_scene.scene_text_ids(CH5))
        self.opening = scenes['EventScr_Ch5_BeginningScene']

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

    def test_on_map_messages_report_the_map_channel(self):
        """The channel is load-bearing: on-map bubbles wrap at 29 chars, Text_BG ~42."""
        chan = dict(self.opening)
        for mid in (0x9BB, 0x9BE, 0x9C2, 0x9C3, 0x9C4):
            self.assertEqual(chan[mid], 'map', 'MSG_%X should be on-map' % mid)

    def test_source_order_is_preserved_across_channels(self):
        """Text_BG and TEXTSHOW interleave; neither may be grouped ahead of the other."""
        chans = [chan for _mid, chan in self.opening]
        self.assertEqual(chans[1], 'map')                  # 0x9BB
        self.assertEqual(chans[2], 'BG_SERAFEW_VILLAGE')   # 0x9BC
        self.assertEqual(chans[4], 'map')                  # 0x9BE

    def test_the_mid_battle_and_talk_scenes_stay_separate(self):
        """The escalation and the Talk-recruit are their own event lists, not the opening.

        ch05 leans on this: 0x9BA-0x9C4 is ONE pre-map list (so nothing in it can
        interleave), while 0x9C5 and 0x9CC carry real triggers.
        """
        scenes = dict(self.vs.scene_text_ids(CH5))
        self.assertEqual([m for m, _c in scenes['EventScr_089F22A4']], [0x9C5])
        self.assertEqual([m for m, _c in scenes['EventScr_089F2270']], [0x9CC])


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
