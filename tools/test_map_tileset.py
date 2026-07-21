#!/usr/bin/env python3
"""Tests for the FEBuilder/FE-Repo tileset import (#40, map_tileset_tool.py).

The converter is thin because the formats align (mapchip_config == the decomp tile
config byte-for-byte; object PNG == 4-bit local indices + a banked 256-color
palette), so the tests pin exactly those assumptions: packing order, palette
quantization, the bank guard -- and the end-to-end oracle: the vendored
cave-interior tileset assembling Cynon's own test map must reproduce the
committed review render (docs/demo/ch03-mineshaft-tileset-demo.png) pixel-exact.
"""
import hashlib
import json
import os
import struct
import sys
import tempfile
import unittest

import yaml

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import map_tileset_tool as mt  # noqa: E402

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CAVE = os.path.join(REPO, 'campaigns/rime-of-the-frostmaiden/maps/tilesets/cave-interior')
SNOWY_FIELDS = os.path.join(
    REPO, 'campaigns/rime-of-the-frostmaiden/maps/tilesets/snowy-fields')
SNOWY_BERN = os.path.join(
    REPO, 'campaigns/rime-of-the-frostmaiden/maps/tilesets/snowy-bern')
DEMO = os.path.join(REPO, 'docs/demo/ch03-mineshaft-tileset-demo.png')
DECOMP = os.path.join(REPO, 'fireemblem8u')


def _object_png(path, px=None, palette=None):
    """A synthetic 256x256 mode-P object sheet."""
    from PIL import Image
    img = Image.new('P', (256, 256), 0)
    for (x, y), v in (px or {}).items():
        img.putpixel((x, y), v)
    pal = palette or []
    pal = pal + [0] * (768 - len(pal))
    img.putpalette(pal)
    img.save(path)
    return path


class TestConvertObjectPng(unittest.TestCase):
    def test_4bpp_packing_low_nibble_is_left_pixel(self):
        with tempfile.TemporaryDirectory() as d:
            p = _object_png(os.path.join(d, 'o.png'), px={(0, 0): 3, (1, 0): 5})
            gfx, _ = mt.convert_object_png(p)
        self.assertEqual(len(gfx), 32768)          # 1024 tiles x 32 B
        self.assertEqual(gfx[0], 3 | (5 << 4))     # tile 0 row 0: left=3, right=5

    def test_tile_order_is_row_major_across_the_sheet(self):
        with tempfile.TemporaryDirectory() as d:
            # (8,0) = tile 1's top-left; (0,8) = tile 32's top-left.
            p = _object_png(os.path.join(d, 'o.png'), px={(8, 0): 7, (0, 8): 9})
            gfx, _ = mt.convert_object_png(p)
        self.assertEqual(gfx[32] & 0xF, 7)          # tile 1, byte 0, low nibble
        self.assertEqual(gfx[32 * 32] & 0xF, 9)     # tile 32, byte 0, low nibble

    def test_palette_quantizes_rgb888_to_bgr555(self):
        with tempfile.TemporaryDirectory() as d:
            p = _object_png(os.path.join(d, 'o.png'),
                            palette=[255, 128, 8])   # color 0: R=255 G=128 B=8
            _, pal = mt.convert_object_png(p)
        self.assertEqual(len(pal), 320)              # 10 banks x 16 x 2 B
        v = struct.unpack_from('<H', pal, 0)[0]
        self.assertEqual(v & 31, 31)                 # R 255 -> 31
        self.assertEqual((v >> 5) & 31, 16)          # G 128 -> 16
        self.assertEqual((v >> 10) & 31, 1)          # B 8 -> 1

    def test_rejects_pixels_beyond_4bit(self):
        with tempfile.TemporaryDirectory() as d:
            p = _object_png(os.path.join(d, 'o.png'), px={(0, 0): 16})
            with self.assertRaises(SystemExit):
                mt.convert_object_png(p)


class TestImportGuards(unittest.TestCase):
    def test_rejects_wrong_config_size(self):
        with tempfile.TemporaryDirectory() as d:
            cfg = os.path.join(d, 'c.mapchip_config')
            open(cfg, 'wb').write(b'\0' * 100)
            with self.assertRaises(SystemExit):
                mt.import_febuilder_tileset(cfg, 'unused.png',
                                            os.path.join(d, 'out'))

    def test_rejects_tsa_banks_the_gbapal_cannot_carry(self):
        with tempfile.TemporaryDirectory() as d:
            cfg = os.path.join(d, 'c.mapchip_config')
            data = bytearray(mt.CONFIG_SIZE)
            struct.pack_into('<H', data, 0, 12 << 12)   # TSA entry on bank 12
            open(cfg, 'wb').write(bytes(data))
            with self.assertRaises(SystemExit):
                mt.import_febuilder_tileset(cfg, 'unused.png',
                                            os.path.join(d, 'out'))


class TestTmxGrid(unittest.TestCase):
    TMX = ('<?xml version="1.0"?><map><tileset firstgid="1" name="t">'
           '<image source="t.png"/></tileset>'
           '<layer name="L" width="2" height="2"><data>'
           '<tile gid="28"/><tile gid="1"/><tile gid="4"/><tile gid="673"/>'
           '</data></layer></map>')

    def test_grid_shape_and_gid_offset(self):
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, 't.tmx')
            open(p, 'w').write(self.TMX)
            self.assertEqual(mt.tmx_grid(p), [[27, 0], [3, 672]])


class TestPreservedTerrainVariants(unittest.TestCase):
    class TargetTerrain:
        def __init__(self, terrain_by_metatile):
            self.terrain_by_metatile = terrain_by_metatile

        def terrain(self, metatile):
            return self.terrain_by_metatile[metatile]

    def test_requires_every_protected_source_metatile(self):
        with self.assertRaisesRegex(ValueError, r'metatile 11.*\(1, 0\)'):
            mt.preserved_terrain_targets(
                [10, 11], bytes([0] * 10 + [0x0c, 0x0c]),
                self.TargetTerrain({100: 0x0c}),
                {'map': {'10': 100}, 'preserve_terrain_variants': [0x0c]}, 2)

    def test_rejects_a_mapped_target_with_wrong_terrain(self):
        with self.assertRaisesRegex(ValueError, r'target metatile 100.*terrain 0x01'):
            mt.preserved_terrain_targets(
                [10], bytes([0] * 10 + [0x0c]),
                self.TargetTerrain({100: 0x01}),
                {'map': {'10': 100}, 'preserve_terrain_variants': [0x0c]}, 1)

    def test_returns_exact_per_cell_targets(self):
        self.assertEqual(
            mt.preserved_terrain_targets(
                [10, 10, 11], bytes([0] * 10 + [0x0c, 0x0c]),
                self.TargetTerrain({100: 0x0c, 101: 0x0c}),
                {'map': {'10': 100, '11': 101},
                 'preserve_terrain_variants': [0x0c]}, 3),
            {0: 100, 1: 100, 2: 101})

    def test_reads_vanilla_layout_and_its_terrain(self):
        width, height, cells, terrain = mt.vanilla_layout_data(DECOMP, 'PrologueMap')
        self.assertEqual((width, height), (15, 10))
        self.assertEqual(len(cells), width * height)
        self.assertIn(0x0c, terrain)
class TestVanillaLayoutTilesetResolution(unittest.TestCase):
    def test_chapter_settings_override_nearest_preceding_tileset(self):
        resolver = getattr(mt, 'vanilla_layout_tileset_assets', None)
        self.assertIsNotNone(resolver)
        if resolver is None:
            return
        with tempfile.TemporaryDirectory() as d:
            os.makedirs(os.path.join(d, 'data'))
            os.makedirs(os.path.join(d, 'src/data'))
            table = ('\t.word ObjectType1\n'
                     '\t.word MapPalette1\n'
                     '\t.word TileConfiguration1\n'
                     '\t.word Ch1Map\n'
                     '\t.word ObjectType2\n'
                     '\t.word MapPalette2\n'
                     '\t.word TileConfiguration2\n'
                     '\t.word Ch3Map\n'
                     '\t.word Ch4Map\n')
            with open(os.path.join(d, 'data/data_8B363C.s'), 'w') as f:
                f.write(table)
            settings = {
                'chapters': [{
                    'map': {
                        'mainLayerId': 8,
                        'obj1Id': 0,
                        'paletteId': 1,
                        'tileConfigId': 2,
                    },
                }],
            }
            with open(os.path.join(d, 'src/data/chapter_settings.json'), 'w') as f:
                json.dump(settings, f)

            self.assertEqual(
                ('ObjectType1', 'MapPalette1', 'TileConfiguration1'),
                resolver(d, 'Ch4Map'),
            )

    def test_uses_vanilla_head_when_build_injection_dirties_worktree(self):
        import subprocess

        with tempfile.TemporaryDirectory() as d:
            os.makedirs(os.path.join(d, 'data'))
            os.makedirs(os.path.join(d, 'src/data'))
            table = ('\t.word ObjectType1\n'
                     '\t.word MapPalette1\n'
                     '\t.word TileConfiguration1\n'
                     '\t.word Ch4Map\n')
            settings = {
                'chapters': [{
                    'map': {
                        'mainLayerId': 3,
                        'obj1Id': 0,
                        'paletteId': 1,
                        'tileConfigId': 2,
                    },
                }],
            }
            with open(os.path.join(d, 'data/data_8B363C.s'), 'w') as f:
                f.write(table)
            settings_path = os.path.join(d, 'src/data/chapter_settings.json')
            with open(settings_path, 'w') as f:
                json.dump(settings, f)
            # Sanitize the git environment: when this test runs *inside* the pre-commit
            # hook, git has exported GIT_DIR/GIT_INDEX_FILE (and core.hooksPath), so an
            # un-scoped fixture `git` would operate on the outer repo and re-fire its hook.
            # Strip GIT_* and disable hooks so the fixture repo is fully self-contained.
            env = {k: v for k, v in os.environ.items() if not k.startswith('GIT_')}
            git = ['git', '-c', 'core.hooksPath=/dev/null']
            subprocess.run(git + ['init', '-q'], cwd=d, env=env, check=True)
            subprocess.run(git + ['add', '.'], cwd=d, env=env, check=True)
            subprocess.run(
                git + ['-c', 'user.name=Test', '-c', 'user.email=test@example.com',
                       'commit', '-qm', 'fixture'],
                cwd=d,
                env=env,
                check=True,
            )

            with open(settings_path, 'w') as f:
                json.dump({'chapters': []}, f)

            self.assertEqual(
                ('ObjectType1', 'MapPalette1', 'TileConfiguration1'),
                mt.vanilla_layout_tileset_assets(d, 'Ch4Map'),
            )


class TestLearnedWinterReskin(unittest.TestCase):
    def test_ch4_preserves_vanilla_forest_sequence_roles(self):
        expected = {
            720: 128,
            782: 192,
            783: 193,
            784: 194,
            785: 195,
            815: 225,
        }
        learned_path = os.path.join(
            REPO, 'campaigns/rime-of-the-frostmaiden/maps/reskin-learned.json')
        with open(learned_path) as f:
            learned = json.load(f)['map']
        actual = {source: learned[str(source)] for source in expected}

        self.assertEqual(expected, actual)

        vanilla_config = os.path.join(
            REPO, 'fireemblem8u/graphics/map/TileConfiguration1.bin')
        snow_config = os.path.join(
            REPO,
            'campaigns/rime-of-the-frostmaiden/maps/tilesets/snowy-bern/snowy-bern.bin')
        with open(vanilla_config, 'rb') as f:
            vanilla_terrain = f.read()[8192:]
        with open(snow_config, 'rb') as f:
            snow_terrain = f.read()[8192:]
        for source, target in expected.items():
            self.assertEqual(0x0C, vanilla_terrain[source])
            self.assertEqual(0x0C, snow_terrain[target])

        layout_dir = os.path.join(REPO, 'fireemblem8u/graphics/map/layout')
        with open(os.path.join(layout_dir, 'Ch4Map.json')) as f:
            dimensions = json.load(f)
        with open(os.path.join(layout_dir, 'Ch4Map.mar'), 'rb') as f:
            raw_layout = f.read()
        cells = [struct.unpack_from('<H', raw_layout, offset)[0] >> 5
                 for offset in range(0, len(raw_layout), 2)]
        self.assertEqual(dimensions['width'] * dimensions['height'], len(cells))
        forest_cells = [m for m in cells if vanilla_terrain[m] == 0x0C]
        self.assertEqual(44, len(forest_cells))
        self.assertEqual(set(expected), set(forest_cells))

        changed = [i for i, m in enumerate(cells)
                   if m in expected and expected[m] != m]
        self.assertTrue(changed)
        self.assertTrue(all(vanilla_terrain[cells[i]] == 0x0C for i in changed))


class TestVendoredCaveInterior(unittest.TestCase):
    """The committed cave-interior pieces (#40; FE-Repo, Cynon, Gray palette)."""

    def test_piece_sizes(self):
        self.assertEqual(os.path.getsize(os.path.join(CAVE, 'cave-interior.bin')),
                         mt.CONFIG_SIZE)
        self.assertEqual(os.path.getsize(os.path.join(CAVE, 'cave-interior.4bpp')),
                         32768)
        self.assertEqual(os.path.getsize(os.path.join(CAVE, 'cave-interior.gbapal')),
                         320)

    def test_credits_shipped_with_the_asset(self):
        text = open(os.path.join(CAVE, 'CREDITS.txt'), encoding='utf-8').read()
        self.assertIn('Cynon', text)

    def test_test_map_render_matches_committed_review_image(self):
        # End-to-end oracle: converted pieces assembling Cynon's own Test Map
        # must reproduce the render Nicolas reviewed on #23 pixel-for-pixel.
        from PIL import Image
        ts = mt._tileset_from_dir(CAVE)
        grid = mt.tmx_grid(os.path.join(CAVE, 'test-map.tmx'))
        with tempfile.TemporaryDirectory() as d:
            out = mt.render_grid(ts, grid, os.path.join(d, 'r.png'), zoom=2)
            got = Image.open(out).convert('RGB')
            want = Image.open(DEMO).convert('RGB')
            self.assertEqual(got.size, want.size)
            self.assertEqual(list(got.getdata()), list(want.getdata()))


class TestVendoredSnowyFields(unittest.TestCase):
    """The intact N426 Snow / Fields + Customs alternate tileset."""

    def test_complete_alternate_ships_with_native_snag_family_and_credits(self):
        self.assertTrue(os.path.isdir(SNOWY_FIELDS))
        self.assertEqual(
            mt.CONFIG_SIZE,
            os.path.getsize(os.path.join(SNOWY_FIELDS, 'snowy-fields.bin')),
        )
        self.assertEqual(
            32768,
            os.path.getsize(os.path.join(SNOWY_FIELDS, 'snowy-fields.4bpp')),
        )
        self.assertEqual(
            320,
            os.path.getsize(os.path.join(SNOWY_FIELDS, 'snowy-fields.gbapal')),
        )

        with open(os.path.join(SNOWY_FIELDS, 'snowy-fields.bin'), 'rb') as f:
            terrain = f.read()[8192:]
        self.assertEqual([8, 35], [i for i, value in enumerate(terrain)
                                   if value == 0x33])
        self.assertEqual([4, 36, 37, 39], [i for i, value in enumerate(terrain)
                                          if value == 0x34])

        with open(os.path.join(SNOWY_FIELDS, 'CREDITS.txt'), encoding='utf-8') as f:
            credits = f.read()
        for artist in ('WAve', 'RandomWizard', 'Beast', 'N426'):
            self.assertIn(artist, credits)


class TestSnowyBernBorrowedSnags(unittest.TestCase):
    """The only cross-tileset exception: Super Fields' complete snag family."""

    def test_empty_matching_slots_hold_pixel_exact_snag_variants(self):
        bern = mt._tileset_from_dir(SNOWY_BERN)

        for metatile in (8, 35):
            self.assertEqual(0x33, bern.terrain(metatile))

        entries = []
        for metatile in (8, 35):
            entries.extend(struct.unpack_from(
                '<4H', bern.cfg, metatile * 8))
        self.assertEqual({4}, {entry >> 12 for entry in entries})
        self.assertEqual(
            {260, 261, 262, 263, 264, 265},
            {entry & 0x3FF for entry in entries},
        )

        approved = bern.metatile_image(35).convert('RGB')
        self.assertEqual(
            '104add1c96bddc9cfaaaab83f92c5bf65ce293a7dcf0bf4db913a610fbbc380d',
            hashlib.sha256(approved.tobytes()).hexdigest(),
        )


class TestCh04MapAndRosterPlacement(unittest.TestCase):
    def test_approved_layout_and_vanilla_named_roster_follow_ch4_path(self):
        chapter_path = os.path.join(
            REPO, 'campaigns/rime-of-the-frostmaiden/chapters',
            'ch04-the-white-moose.yaml')
        with open(chapter_path) as f:
            chapter = yaml.safe_load(f)

        self.assertEqual(9, chapter['deployment']['deploy_limit'])
        self.assertEqual(
            [[5, 2], [7, 3], [5, 1], [4, 0], [4, 2],
             [3, 3], [3, 1], [6, 1], [2, 2]],
            chapter['deployment']['deploy_slots'],
        )

        enemies = {unit['id']: unit for unit in chapter['enemy_units']}
        expected = {
            'mauthedoog': (
                'Mauthe Doog',
                [[1, 4], [2, 7], [3, 10], [5, 8], [7, 9], [11, 4]],
            ),
            'bonewalker': (
                'Bonewalker',
                [[1, 14], [5, 13], [8, 14], [10, 12], [11, 14]],
            ),
            'mogall': (
                'Mogall',
                [[11, 6], [13, 7], [12, 8], [13, 11]],
            ),
            'entoumbed': ('Entombed', [[13, 13]]),
            'mauthedoog-reinf': (
                'Mauthe Doog',
                [[0, 0], [2, 0], [0, 2], [2, 1]],
            ),
            'bonewalker-reinf': (
                'Bonewalker',
                [[13, 9], [14, 8], [14, 6]],
            ),
        }
        for unit_id, (name, positions) in expected.items():
            unit = enemies[unit_id]
            self.assertEqual(name, unit['name'])
            self.assertEqual(positions, unit['positions'])
            self.assertEqual(unit['count'], len(unit['positions']))

        map_dir = os.path.join(
            REPO, 'campaigns/rime-of-the-frostmaiden/maps')
        with open(os.path.join(map_dir, 'ch04-lonelywood-forest.json')) as f:
            layout = json.load(f)
        with open(os.path.join(map_dir, 'ch04-lonelywood-forest.mar'), 'rb') as f:
            raw = f.read()
        cells = [struct.unpack_from('<H', raw, i)[0] >> 5
                 for i in range(0, len(raw), 2)]
        self.assertEqual(
            'cb4551562830618fe089e2186a9b540cffdaa38b08b91618759893a6f8502d54',
            hashlib.sha256(struct.pack('<225H', *cells)).hexdigest(),
        )
        bern = mt._tileset_from_dir(SNOWY_BERN)
        all_positions = chapter['deployment']['deploy_slots'] + [
            pos for unit_id in expected
            for pos in enemies[unit_id]['positions']
        ]
        for x, y in all_positions:
            self.assertTrue(0 <= x < layout['width'])
            self.assertTrue(0 <= y < layout['height'])
            metatile = cells[y * layout['width'] + x]
            self.assertIn(bern.terrain(metatile), (0x01, 0x0C))


class TestMapEditorOutputs(unittest.TestCase):
    def test_absolute_editor_output_keeps_preview_beside_editor(self):
        import subprocess

        with tempfile.TemporaryDirectory() as d:
            editor = os.path.join(d, 'ch4-snowy-fields.html')
            layout = os.path.join(d, 'ch4-snowy-fields-layout.json')
            result = subprocess.run(
                [
                    sys.executable,
                    os.path.join(REPO, 'tools/gen_map_editor.py'),
                    '--tileset=snowy-fields',
                    'Ch4Map',
                    editor,
                    layout,
                ],
                cwd=REPO,
                capture_output=True,
                text=True,
            )
            self.assertEqual(0, result.returncode, result.stdout + result.stderr)
            self.assertTrue(os.path.isfile(os.path.join(
                d, 'ch4-snowy-fields-start.png')))


if __name__ == '__main__':
    unittest.main()
