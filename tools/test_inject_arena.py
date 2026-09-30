#!/usr/bin/env python3
"""Tests for tools/inject/arena.py.

Run:  python3 tools/test_inject_arena.py
"""
import hashlib
import os
import shutil
import sys
import tempfile
import textwrap
import unittest
from unittest import mock

from PIL import Image

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from inject.namespace import stubbed
import build_campaign as bc
import inject.arena
import inject.cast
import inject.chapter_ids
import inject.decomp
import inject.hosts
import inject.warm
from inject import engine_hooks as eh
from inject import source as injector  # the injector's source, every file of it (#389)


class ArenaPresentation(unittest.TestCase):
    """Arena presentation is campaign/chapter data over untouched vanilla mechanics (#265)."""
    CAMPAIGN = 'rime-of-the-frostmaiden'

    def test_the_welcome_screen_recolors_only_the_sky_and_the_awnings(self):
        delta = inject.arena.arena_presentation_config(self.CAMPAIGN)['welcome_delta']
        base = inject.arena.ARENA_FRONT_BASE_BANK
        sky = {(15 - base) * 16 + i for i in range(1, 9)} | {(12 - base) * 16 + 1}
        awnings = {(13 - base) * 16 + i for i in (1, 2, 3, 4, 10, 11, 15)}
        self.assertEqual(sky | awnings, set(delta),
                         'the coliseum EXTERIOR keeps its warm sandstone -- winter arrives '
                         'through the weather and the banners only (#265)')
        self.assertTrue(all(0 <= word <= 0x7FFF for word in delta.values()))

    def test_the_welcome_masonry_is_never_named_at_all(self):
        # The rejected first pass held luminance and crushed the stone's saturation from
        # 0.29-0.74 to 0.10-0.20, which is why it read as washed out while passing every
        # numeric check we had. The masonry bank is now simply unmentionable.
        delta = inject.arena.arena_presentation_config(self.CAMPAIGN)['welcome_delta']
        base = inject.arena.ARENA_FRONT_BASE_BANK
        for i in range(2, 16):
            self.assertNotIn((12 - base) * 16 + i, delta,
                             'masonry index %d must stay byte-identical to vanilla' % i)

    def test_the_welcome_delta_only_rewrites_the_words_it_names(self):
        synthetic = [0x0200 + i for i in range(64)]
        delta = inject.arena.arena_welcome_palette_delta(
            {'background': [{'bank': 13, 'index': 4, 'color': '#FFFFFF'}]}, 'fixture.yaml')
        words = inject.arena.arena_welcome_palette_words(delta, vanilla=synthetic)
        target = (13 - inject.arena.ARENA_FRONT_BASE_BANK) * 16 + 4
        self.assertEqual(0x7FFF, words[target])
        for i in range(64):
            if i != target:
                self.assertEqual(synthetic[i], words[i])

    # The combat backdrop is a DELTA over vanilla. These tests are written against a synthetic
    # vanilla palette wherever they can be, so they assert the composition rather than the
    # contents of a ROM that CI does not have (CI builds against 16MB of /dev/urandom).
    SYNTHETIC_VANILLA = {phase: [0x0100 + i for i in range(64)] for phase in 'ABC'}

    def test_live_campaign_recolors_the_floor_and_banners_and_nothing_else(self):
        delta = inject.arena.arena_presentation_config(self.CAMPAIGN)['combat_delta']
        base = inject.arena.ARENA_BATTLE_BG_BASE_BANK
        floor = {(9 - base) * 16 + i for i in (1, 2, 3, 4, 5, 6, 8, 9, 10)}
        banners = {(8 - base) * 16 + i for i in (4, 8)}
        self.assertEqual(floor | banners, set(delta),
                         'the coliseum may lose ONLY its sand floor and its red banners -- '
                         'every other word is vanilla stone, wood, gold or crowd (#265)')
        self.assertTrue(all(0 <= word <= 0x7FFF for word in delta.values()))

    def test_composition_preserves_a_words_per_phase_difference(self):
        # Vanilla animates three of its 64 words. A delta must leave any word it does not
        # name differing across A/B/C exactly as it did, or the ten-frame cycle flattens.
        animated = 40
        vanilla = {phase: [0x0100 + i for i in range(64)] for phase in 'ABC'}
        for offset, phase in enumerate('ABC'):
            vanilla[phase][animated] = 0x2000 + offset
        delta = inject.arena.arena_combat_palette_delta(
            {'background': [{'bank': 9, 'index': 3, 'color': '#FFFFFF'}]}, 'fixture.yaml')
        phases = inject.arena.arena_combat_palette_words(delta, vanilla=vanilla)['background']
        self.assertEqual([0x2000, 0x2001, 0x2002], [phase[animated] for phase in phases],
                         'an unnamed word must keep animating across the three phases')

    def test_the_delta_only_rewrites_the_words_it_names(self):
        delta = inject.arena.arena_combat_palette_delta(
            {'background': [{'bank': 9, 'index': 3, 'color': '#FFFFFF'}]}, 'fixture.yaml')
        out = inject.arena.arena_combat_palette_words(delta, vanilla=self.SYNTHETIC_VANILLA)
        target = (9 - inject.arena.ARENA_BATTLE_BG_BASE_BANK) * 16 + 3
        for phase, words in zip('ABC', out['background']):
            self.assertEqual(0x7FFF, words[target])
            for i in range(64):
                if i != target:
                    self.assertEqual(self.SYNTHETIC_VANILLA[phase][i], words[i])

    def test_the_delta_refuses_the_transparent_key(self):
        with self.assertRaises(SystemExit) as caught:
            inject.arena.arena_combat_palette_delta(
                {'background': [{'bank': 8, 'index': 0, 'color': '#FFFFFF'}]}, 'fixture.yaml')
        self.assertIn('transparent key', str(caught.exception))

    def test_malformed_combat_delta_names_the_config_path_and_field(self):
        with tempfile.TemporaryDirectory() as tmp:
            campaign = os.path.join(tmp, 'campaigns', 'fixture')
            os.makedirs(os.path.join(campaign, 'chapters'))
            config_path = os.path.join(campaign, 'campaign.yaml')
            with open(config_path, 'w') as f:
                f.write(textwrap.dedent('''
                    arena_presentation:
                      combat:
                        background: [["#000000"]]
                '''))
            with stubbed('REPO', tmp), \
                    stubbed('hosted_chapters', mock.Mock(return_value=[])):
                with self.assertRaises(SystemExit) as caught:
                    inject.arena.arena_presentation_config('fixture')
            self.assertIn(config_path, str(caught.exception))
            self.assertIn('arena_presentation.combat.background', str(caught.exception))

    def test_an_out_of_range_bank_names_the_four_banks_the_backdrop_owns(self):
        with self.assertRaises(SystemExit) as caught:
            inject.arena.arena_combat_palette_delta(
                {'background': [{'bank': 3, 'index': 5, 'color': '#FFFFFF'}]}, 'fixture.yaml')
        self.assertIn('[6, 7, 8, 9]', str(caught.exception))

    def test_ch05_declares_a_real_collision_free_attendant_portrait(self):
        cfg = inject.arena.arena_presentation_config(self.CAMPAIGN)
        override = cfg['chapters'][inject.hosts.CH05_HOST_INDEX]
        self.assertTrue(os.path.isfile(override['portrait_path']))
        self.assertEqual('Glen', override['face_slot'])
        self.assertEqual(0x4B, override['face_id'])
        taken = (set(inject.cast.PORTRAIT_MAP.values()) | set(inject.cast.GUEST_PORTRAIT_MAP.values())
                 | set(inject.chapter_ids.CH02_CHWINGA_PORTRAIT_SLOT.values())
                 | {slot for _mug, slot, _rc in inject.chapter_ids.CH05_VISIT_FACES.values()})
        self.assertNotIn(override['face_slot'], taken)

    def test_attendant_scales_the_fe_repo_chibi_to_fill_the_counter_envelope(self):
        override = inject.arena.arena_presentation_config(self.CAMPAIGN)['chapters'][inject.hosts.CH05_HOST_INDEX]
        bust = inject.arena._vendor_mug_to_arena_bust(override['portrait_path'])
        painted = Image.new('1', bust.size)
        painted.putdata([pixel != 0 for pixel in bust.getdata()])
        self.assertEqual((24, 0, 72, 48), painted.getbbox())
        sheet = Image.open(override['portrait_path']).convert('RGB')
        source = sheet.crop((96, 16, 128, 48)).resize(
            (48, 48), Image.Resampling.NEAREST)
        actual = bust.crop((24, 0, 72, 48)).convert('RGB')
        key = sheet.getpixel((0, 0))
        self.assertEqual(
            [inject.cast.PORTRAIT_TRANSPARENT_RGB if pixel == key else pixel
             for pixel in source.getdata()],
            list(actual.getdata()))

    def test_welcome_delta_validation_names_the_config_path_and_field(self):
        with self.assertRaises(SystemExit) as caught:
            inject.arena.arena_welcome_palette_delta({'background': []}, '/tmp/campaign.yaml')
        self.assertIn('/tmp/campaign.yaml', str(caught.exception))
        self.assertIn('arena_presentation.welcome.background', str(caught.exception))
        with self.assertRaises(SystemExit) as caught:
            inject.arena.arena_welcome_palette_delta(
                {'background': [{'bank': 13, 'index': 4, 'color': 'ice'}]},
                '/tmp/campaign.yaml')
        self.assertIn('arena_presentation.welcome.background[0]', str(caught.exception))
        self.assertIn('#RRGGBB', str(caught.exception))

    def _attendant_fixture(self, tmp, face_slot, portrait='ravisin.png'):
        campaign = os.path.join(tmp, 'campaigns', 'fixture')
        os.makedirs(os.path.join(campaign, 'chapters'), exist_ok=True)
        with open(os.path.join(campaign, 'campaign.yaml'), 'w') as f:
            f.write('{}\n')
        shutil.copy(os.path.join(inject.cast._bust_dir(self.CAMPAIGN), 'ravisin.png'),
                    os.path.join(campaign, portrait))
        chapter_path = os.path.join(campaign, 'chapters', 'ch05-fixture.yaml')
        with open(chapter_path, 'w') as f:
            f.write(textwrap.dedent('''
                chapter_number: 5
                arena_presentation:
                  attendant:
                    portrait: %s
                    face_slot: %s
            ''' % (portrait, face_slot)))
        return chapter_path

    def test_an_attendant_may_not_squat_on_a_slot_the_cast_already_owns(self):
        # inject_arena_attendant_portraits runs AFTER inject_portraits, so a collision would
        # overwrite a player character's face with a green build and no warning.
        with tempfile.TemporaryDirectory() as tmp:
            chapter_path = self._attendant_fixture(tmp, inject.cast.PORTRAIT_MAP['braulo'])
            with stubbed('REPO', tmp), \
                    stubbed('hosted_chapters', mock.Mock(return_value=[])):
                with self.assertRaises(SystemExit) as caught:
                    inject.arena.arena_presentation_config('fixture')
            self.assertIn(chapter_path, str(caught.exception))
            self.assertIn('already dressed by the campaign cast', str(caught.exception))

    def test_two_chapters_may_not_share_a_slot_with_different_attendants(self):
        overrides = {
            6: {'face_slot': 'Glen', 'portrait_path': '/a.png', 'face_id': 0x4B,
                'chapter_path': '/ch05.yaml'},
            7: {'face_slot': 'Glen', 'portrait_path': '/b.png', 'face_id': 0x4B,
                'chapter_path': '/ch06.yaml'},
        }
        with stubbed('arena_presentation_config', mock.Mock(return_value={'chapters': overrides})):
            with self.assertRaises(SystemExit) as caught:
                inject.arena.inject_arena_attendant_portraits('fixture', verbose=False)
        self.assertIn('/ch06.yaml', str(caught.exception))
        self.assertIn('already dressed with a different portrait', str(caught.exception))

    def test_missing_attendant_portrait_names_the_chapter_and_asset_path(self):
        with tempfile.TemporaryDirectory() as tmp:
            campaign = os.path.join(tmp, 'campaigns', 'fixture')
            chapters = os.path.join(campaign, 'chapters')
            os.makedirs(chapters)
            with open(os.path.join(campaign, 'campaign.yaml'), 'w') as f:
                f.write('{}\n')
            chapter_path = os.path.join(chapters, 'ch05-fixture.yaml')
            with open(chapter_path, 'w') as f:
                f.write(textwrap.dedent('''
                    chapter_number: 5
                    arena_presentation:
                      attendant:
                        portrait: portraits/vendor/missing.png
                        face_slot: Glen
                '''))
            with stubbed('REPO', tmp):
                with self.assertRaises(SystemExit) as caught:
                    inject.arena.arena_presentation_config('fixture')
            self.assertIn(chapter_path, str(caught.exception))
            self.assertIn('portraits/vendor/missing.png', str(caught.exception))

    def test_vendored_attendant_is_the_exact_pinned_fe_repo_file_and_is_credited(self):
        override = inject.arena.arena_presentation_config(self.CAMPAIGN)['chapters'][inject.hosts.CH05_HOST_INDEX]
        with open(override['portrait_path'], 'rb') as f:
            self.assertEqual(
                'b5a1bbfb2e2c20fc6c77c689936784166277c1652faf37c7f6c91935cea6583f',
                hashlib.sha256(f.read()).hexdigest())
        with open(os.path.join(inject.decomp.REPO, 'CREDITS.md'), encoding='utf-8') as f:
            credits = f.read()
        self.assertIn('Generic Pretsel', credits)
        self.assertIn('3abc62d4f0a12d300911b51788719f950c5f45b9', credits)

    def test_missing_configuration_generates_untouched_vanilla_fallbacks(self):
        source = inject.arena.arena_presentation_source(None, {})
        self.assertIn('return gPal_ArenaBuildingFront;', source)
        self.assertIn('return 0x67;', source)
        self.assertNotIn('gMSArenaBuildingFrontPalette[', source)

    def test_live_binding_selects_ch05_and_falls_back_for_other_chapters(self):
        cfg = inject.arena.arena_presentation_config(self.CAMPAIGN)
        words = inject.arena.arena_welcome_palette_words(cfg['welcome_delta'],
                                               vanilla=[0x0200 + i for i in range(64)])
        source = inject.arena.arena_presentation_source(words, cfg['chapters'])
        self.assertIn('gMSArenaBuildingFrontPalette[64]', source)
        self.assertIn('case %d:' % inject.hosts.CH05_HOST_INDEX, source)
        self.assertIn('return 0x4B;', source)
        self.assertIn('return 0x67;', source)

    def test_engine_hook_reaches_real_arena_ui_init_without_replacing_art_or_tsa(self):
        vanilla = inject.decomp.vanilla_decomp_text('src/uiarena.c')
        patched = eh._patch_arena_presentation_text(vanilla)
        init = patched[patched.index('void ArenaUi_Init'):patched.index('void sub_80B5970')]
        self.assertIn('StartTalkFace(GetArenaPresentationFace()', init)
        self.assertIn('ApplyPalettes(GetArenaPresentationPalette(), 0xC, 4);', init)
        self.assertIn('Decompress(gGfx_ArenaBuildingFront,', init)
        self.assertIn('CallARM_FillTileRect(gBG3TilemapBuffer, gTsa_ArenaBuildingFront,', init)
        self.assertNotIn('StartTalkFace(0x67,', init)
        self.assertNotIn('ApplyPalettes(gPal_ArenaBuildingFront,', init)

    def test_combat_backdrop_hook_uses_the_cycle_binding_from_frame_zero(self):
        vanilla = inject.decomp.vanilla_decomp_text('src/banim-ekrarena.c')
        transform = getattr(eh, '_patch_arena_battle_background_text', lambda text: text)
        patched = transform(vanilla)
        self.assertIn('extern u16 * CONST_DATA PalArray_ArenaBattleBg[];', patched)
        self.assertIn('CpuFastCopy(PalArray_ArenaBattleBg[0], gPaletteBuffer + 0x60, 0x80);',
                      patched)
        self.assertIn('LZ77UnCompVram(Img_ArenaBattleBg,', patched)
        self.assertIn('LZ77UnCompWram(Tsa_ArenaBattleBg,', patched)
        self.assertIn('0, 10,\n        1, 10,\n        2, 10,', patched)

    def test_combat_backdrop_source_repoints_all_three_phases_with_vanilla_fallback(self):
        cfg = inject.arena.arena_presentation_config(self.CAMPAIGN)
        vanilla = inject.decomp.vanilla_decomp_text('src/banim-ekrarena.c')
        generate = getattr(inject.arena, 'arena_battle_background_source',
                           lambda text, _phases: text)
        configured = generate(vanilla, inject.arena.arena_combat_palette_words(
            cfg['combat_delta'], vanilla=self.SYNTHETIC_VANILLA)['background'])
        for suffix in 'ABC':
            self.assertIn('gMSArenaBattleBgPalette%s[64]' % suffix, configured)
        cycle = configured[configured.index('u16 * CONST_DATA PalArray_ArenaBattleBg[] ='):]
        self.assertIn('gMSArenaBattleBgPaletteA,', cycle)
        self.assertIn('gMSArenaBattleBgPaletteB,', cycle)
        self.assertIn('gMSArenaBattleBgPaletteC,', cycle)

        fallback = generate(vanilla, None)
        self.assertNotIn('gMSArenaBattleBgPalette', fallback)
        fallback_cycle = fallback[fallback.index('u16 * CONST_DATA PalArray_ArenaBattleBg[] ='):]
        self.assertIn('Pal_ArenaBattleBg_A,', fallback_cycle)
        self.assertIn('Pal_ArenaBattleBg_B,', fallback_cycle)
        self.assertIn('Pal_ArenaBattleBg_C,', fallback_cycle)


    def test_vanilla_arena_path_bypasses_the_normal_terrain_platform(self):
        vanilla = inject.decomp.vanilla_decomp_text('src/banim-ekrdispup.c')
        setup = vanilla[vanilla.index('void EfxClearScreenFx(void)'):
                        vanilla.index('void sub_8051E00(void)')]
        self.assertIn('if (GetBattleAnimArenaFlag() == false)\n        sub_8051E00();', setup)
        self.assertIn('else\n        CpuFastFill16(0, gBG2TilemapBuffer, 0x800);', setup)

    def test_arena_source_is_restored_and_both_pipeline_steps_are_live(self):
        self.assertIn('src/uiarena.c', inject.warm.PATCHED_DECOMP_FILES)
        self.assertIn('src/banim-ekrarena.c', inject.warm.PATCHED_DECOMP_FILES)
        self.assertIn('src/banim_terrain_data.c', inject.warm.PATCHED_DECOMP_FILES)
        build = injector.injector_source()
        self.assertIn('engine_hooks._patch_arena_presentation()', build)
        self.assertIn('inject_arena_presentation(args.campaign)', build)


if __name__ == '__main__':
    unittest.main()
