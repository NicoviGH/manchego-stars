#!/usr/bin/env python3
"""Campaign sound effects (inject/sounds.py): appended, never a vanilla row edited.

Run: python3 tools/test_inject_sounds.py
"""
import aifc
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import inject.decomp
import inject.sounds as snd

CAMPAIGN = 'rime-of-the-frostmaiden'


class TheSongTable(unittest.TestCase):
    def test_vanilla_has_a_thousand_rows_so_the_first_campaign_id_is_0x3E8(self):
        """The index IS the song id. Counted off the vanilla table, not assumed."""
        table = inject.decomp.vanilla_decomp_text('sound/song_table.s')
        self.assertEqual(1000, snd.song_table_length(table))

    def test_a_campaign_song_rides_the_monster_cry_player(self):
        """Vanilla's monster cries sit on player 6; a cry on the BGM player would stop the music."""
        table = inject.decomp.vanilla_decomp_text('sound/song_table.s')
        self.assertIn('\tsong song814_mon_gar_critical1, 6, 6', table)
        self.assertEqual(6, snd.SFX_PLAYER)


class TheAppendedAssembly(unittest.TestCase):
    def test_the_song_plays_its_sample_at_the_recorded_rate(self):
        """Base key 60 and a Cn3 note: no transposition, so the cry sounds as recorded."""
        asm = snd.sound_asm('ms_x')
        self.assertIn('voice_directsound 60, 0, DirectSoundData_ms_x,', asm)
        self.assertIn('N96\t, Cn3, v127', asm)
        self.assertIn('.incbin "sound/direct_sound_samples/ms_x.bin"', asm)

    def test_the_macros_are_not_included_per_sound(self):
        """A second `.include "MPlayDef.s"` redefines every equate; the injector includes once."""
        self.assertNotIn('.include', snd.sound_asm('ms_x'))


class TheVendoredSamples(unittest.TestCase):
    def test_every_sample_is_mono_8_bit_aiff(self):
        """What aif2pcm accepts and the engine plays without conversion."""
        for _enum, stem, _credit in snd.CAMPAIGN_SOUNDS:
            path = os.path.join(inject.decomp.REPO, 'campaigns', CAMPAIGN, 'sounds', stem + '.aif')
            a = aifc.open(path, 'rb')
            try:
                self.assertEqual((1, 1), (a.getnchannels(), a.getsampwidth()), stem)
                self.assertGreater(a.getnframes(), 0, stem)
            finally:
                a.close()

    def test_enum_names_are_campaign_prefixed(self):
        for enum, _stem, _credit in snd.CAMPAIGN_SOUNDS:
            self.assertTrue(enum.startswith('SONG_MS_'), enum)


if __name__ == '__main__':
    unittest.main()
