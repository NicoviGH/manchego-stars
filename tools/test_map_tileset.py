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
import re
import struct
import sys
import tempfile
import unittest

import yaml

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import map_tileset_tool as mt  # noqa: E402
import build_campaign as bc  # noqa: E402

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


class TestEditorUsesTheResolver(unittest.TestCase):
    """gen_map_editor must RESOLVE the reference pane's tileset, never scan for it.

    The resolver and the test above both existed while gen_map_editor kept its own
    backward scan over gChapterDataAssetTable, so Ch5Map's reference pane rendered
    through Ch5x's castle interior -- correct geometry, wrong art, which reads as a
    corrupt map. Painting a retile against that reference is painting against a lie.
    """

    SOURCE = os.path.join(REPO, 'tools', 'gen_map_editor.py')

    def test_calls_vanilla_layout_tileset_assets(self):
        with open(self.SOURCE, encoding='utf-8') as f:
            source = f.read()
        self.assertIn('vanilla_layout_tileset_assets(dec, layout)', source)

    def test_no_backward_scan_for_tileset_assets(self):
        with open(self.SOURCE, encoding='utf-8') as f:
            source = f.read()
        for probe in ("startswith('TileConfiguration')",
                      "startswith('MapPalette')",
                      "startswith('ObjectType')"):
            self.assertNotIn(probe, source,
                             'asset-table proximity is not authoritative -- '
                             'resolve through chapter_settings.json instead')

    def test_no_hardcoded_tileset_1_in_the_reference_pane(self):
        """The reskin-mode reference pane hardcoded tileset 1 for every layout.

        A separate instance of the same defect from the backward scan, and the one
        that actually reached the screen: Ch5Map rides tileset 2, so the pane a
        retile is painted against rendered through the wrong art entirely.
        """
        with open(self.SOURCE, encoding='utf-8') as f:
            source = f.read()
        for probe in ('ObjectType1', 'MapPalette1', 'TileConfiguration1'):
            self.assertNotIn(
                "graphics/map/%s" % probe, source,
                'the reference pane must resolve the layout OWN tileset, '
                'not assume tileset 1')

    def test_ch5map_resolves_to_tileset_2_not_ch5x_castle(self):
        if not os.path.isdir(DECOMP):
            self.skipTest('decomp submodule not checked out')
        self.assertEqual(
            ('ObjectType2', 'MapPalette2', 'TileConfiguration2'),
            mt.vanilla_layout_tileset_assets(DECOMP, 'Ch5Map'))


class TestPaletteHidesUnusedSlots(unittest.TestCase):
    """TERRAIN_NONE is the tileset's own 'this slot is unused' flag.

    The palette used to filter on a solid-ORANGE colour probe, which is tileset-specific:
    Port-or-Town marks its 144 unused slots solid TEAL, so every one of them showed up as a
    paintable brush. Terrain 0x00 generalises and is authoritative.
    """

    def test_terrain_none_slots_are_excluded(self):
        with open(os.path.join(REPO, 'tools', 'gen_map_editor.py'), encoding='utf-8') as f:
            source = f.read()
        self.assertIn("win.terrain(m) != 0x00", source)

    def test_no_committed_map_paints_a_terrain_none_tile(self):
        maps = os.path.join(REPO, 'campaigns/rime-of-the-frostmaiden/maps')
        for stem, tileset in (('ch00-prologue', 'snowy-bern'),
                              ('ch01-the-iron-trail', 'snowy-bern'),
                              ('ch02-cold-welcome', 'snowy-bern'),
                              ('ch04-lonelywood-forest', 'snowy-bern'),
                              ('ch03-the-termalaine-mine', 'cave-interior')):
            ts = mt._tileset_from_dir(os.path.join(maps, 'tilesets', tileset))
            with open(os.path.join(maps, stem + '.json'), encoding='utf-8') as f:
                info = json.load(f)
            with open(os.path.join(maps, stem + '.mar'), 'rb') as f:
                raw = f.read()
            for cell in range(info['width'] * info['height']):
                metatile = struct.unpack_from('<H', raw, cell * 2)[0] >> 5
                self.assertNotEqual(
                    0x00, ts.terrain(metatile),
                    '%s cell %d paints metatile %d, which the tileset marks unused'
                    % (stem, cell, metatile))


class TestRetileInheritsVanillaTerrain(unittest.TestCase):
    """A retile changes art, never terrain -- on ANY tileset.

    The old guard only ran for snowy-bern, so ch05's port-or-town retile drifted eleven
    cells FENCE -> WALL unchecked. Those differ in exactly one table
    (TerrainTable_MovCost_Fly*), so the map looked right while silently walling out the
    campaign's only Pegasus Knight.
    """

    def _importer(self):
        import importlib
        return importlib.import_module('import_map_layout')

    def test_ch05_map_carries_vanilla_ch5_terrain(self):
        if not os.path.isdir(DECOMP):
            self.skipTest('decomp submodule not checked out')
        maps = os.path.join(REPO, 'campaigns/rime-of-the-frostmaiden/maps')
        with open(os.path.join(maps, 'ch05-the-elven-tomb.json'), encoding='utf-8') as f:
            info = json.load(f)
        with open(os.path.join(maps, 'ch05-the-elven-tomb.mar'), 'rb') as f:
            raw = f.read()
        grid = [struct.unpack_from('<H', raw, i * 2)[0] >> 5
                for i in range(info['width'] * info['height'])]
        export = dict(info, grid=grid, vanilla_layout='Ch5Map')
        self._importer().validate_terrain_matches_vanilla(export, DECOMP, maps)

    def test_guard_rejects_a_terrain_change(self):
        if not os.path.isdir(DECOMP):
            self.skipTest('decomp submodule not checked out')
        maps = os.path.join(REPO, 'campaigns/rime-of-the-frostmaiden/maps')
        _, _, cells, _ = mt.vanilla_layout_data(DECOMP, 'Ch5Map')
        ts = mt._tileset_from_dir(os.path.join(maps, 'tilesets', 'snowy-bern'))
        # paint every cell with one tile; it cannot carry all of vanilla Ch5's ten roles
        export = {'tileset': 'snowy-bern', 'width': 15, 'height': 21,
                  'grid': [66] * len(cells), 'vanilla_layout': 'Ch5Map'}
        with self.assertRaises(ValueError) as caught:
            self._importer().validate_terrain_matches_vanilla(export, DECOMP, maps)
        self.assertIn('re-author the metatile terrain byte', str(caught.exception))

    def test_editor_stamps_the_layout_for_a_blank_canvas_retile(self):
        with open(os.path.join(REPO, 'tools', 'gen_map_editor.py'), encoding='utf-8') as f:
            source = f.read()
        self.assertIn("EXPORT_META['vanilla_layout']=VANILLA_REF", source)


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


class TestFogHalfOfTheTilesetPalette(unittest.TestCase):
    """A tileset .gbapal is two sets of five banks: DisplayBmTile (bmmap.c) draws a visible
    tile from BG bank 6 and a fogged tile from bank 11, and UnpackChapterMapPalette loads the
    ten banks at BG 6..15. So banks 0-4 are lit and 5-9 are the fog copy -- and a vendored
    tileset that only recoloured the lit half puts the ORIGINAL season back on screen the
    moment fog turns on (ch04, #24)."""

    def _banks(self, pal):
        import struct
        return [[struct.unpack_from('<H', pal, b * 32 + i * 2)[0] for i in range(16)]
                for b in range(len(pal) // 32)]

    def _greenish(self, colour):
        r, g, b = colour & 31, (colour >> 5) & 31, (colour >> 10) & 31
        return g > r + 2 and g > b + 2

    def _snow_palette(self):
        path = os.path.join(REPO, 'campaigns/rime-of-the-frostmaiden/maps/tilesets/'
                                  'snowy-bern/snowy-bern.gbapal')
        with open(path, 'rb') as f:
            return f.read()

    def test_the_vendored_fog_half_is_still_green(self):
        """Pins the trap, not just the fix: the asset we vendor really does ship a summer fog
        half, so deriving it is necessary rather than defensive."""
        banks = self._banks(self._snow_palette())
        lit = sum(self._greenish(c) for b in banks[:5] for c in b)
        fog = sum(self._greenish(c) for b in banks[5:] for c in b)
        self.assertEqual(0, lit, 'the LIT half is winterized')
        self.assertGreater(fog, 0, 'the vendored FOG half is not')

    def test_derived_fog_half_carries_the_winter_lit_half(self):
        derived = bc.derive_fog_banks(self._snow_palette(),
                                      bc.TILESET_FOG_HAZE['snowy-bern'])
        banks = self._banks(derived)
        self.assertEqual(0, sum(self._greenish(c) for b in banks[5:] for c in b))
        # Fog is a HAZE, not a repaint: every fog colour is lighter than its lit twin, and
        # index 0 (the transparent/backdrop entry) is carried across untouched.
        for b in range(5):
            self.assertEqual(banks[b][0], banks[b + 5][0])
            for i in range(1, 16):
                lit, fog = banks[b][i], banks[b + 5][i]
                for shift in (0, 5, 10):
                    self.assertGreaterEqual((fog >> shift) & 31, (lit >> shift) & 31)

    def test_lit_half_is_untouched(self):
        pal = self._snow_palette()
        derived = bc.derive_fog_banks(pal, bc.TILESET_FOG_HAZE['snowy-bern'])
        self.assertEqual(pal[:5 * 32], derived[:5 * 32])


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

    def test_paint_metatile_allocates_private_tiles_and_preserves_terrain(self):
        from PIL import Image

        with tempfile.TemporaryDirectory() as d:
            stem = os.path.basename(d)
            gfx = bytearray(32768)
            cfg = bytearray(mt.CONFIG_SIZE)
            pal = bytearray(320)
            for color in range(16):
                struct.pack_into('<H', pal, (16 + color) * 2,
                                 color | (color << 5) | (color << 10))
            cfg[8192 + 36] = 0x34
            for entry in range(4096):
                struct.pack_into('<H', cfg, entry * 2, 0)
            for ext, data in (('4bpp', gfx), ('bin', cfg), ('gbapal', pal)):
                with open(os.path.join(d, stem + '.' + ext), 'wb') as output:
                    output.write(data)

            paint = Image.new('RGB', (16, 16))
            for y in range(16):
                for x in range(16):
                    value = 8 if (x + y) % 2 else 15
                    channel = value << 3
                    paint.putpixel((x, y), (channel, channel, channel))
            source = os.path.join(d, 'paint.png')
            paint.save(source)

            tile_ids = mt.paint_metatile(d, 36, source, bank=1)
            painted = mt._tileset_from_dir(d)

            self.assertEqual(0x34, painted.terrain(36))
            self.assertEqual({1}, {
                entry >> 12 for entry in struct.unpack_from('<4H', painted.cfg, 36 * 8)
            })
            self.assertTrue(all(tile_id != 0 for tile_id in tile_ids))
            self.assertEqual(list(paint.getdata()),
                             list(painted.metatile_image(36).getdata()))

    def test_paint_metatile_can_claim_an_unused_palette_bank(self):
        from PIL import Image

        with tempfile.TemporaryDirectory() as d:
            stem = os.path.basename(d)
            for ext, data in (('4bpp', bytes(32768)),
                              ('bin', bytes(mt.CONFIG_SIZE)),
                              ('gbapal', bytes(320))):
                with open(os.path.join(d, stem + '.' + ext), 'wb') as output:
                    output.write(data)
            paint = Image.new('P', (16, 16), 1)
            palette = [0] * 768
            palette[3:6] = [80, 120, 160]
            paint.putpalette(palette)
            source = os.path.join(d, 'indexed.png')
            paint.save(source)

            mt.paint_metatile(d, 36, source, bank=4, write_bank=True)
            painted = mt._tileset_from_dir(d)

            self.assertEqual((80, 120, 160), painted.palettes[4][1])
            self.assertEqual({4}, {
                entry >> 12 for entry in struct.unpack_from('<4H', painted.cfg, 36 * 8)
            })

    def test_paint_metatile_rejects_the_derived_fog_half(self):
        from PIL import Image

        with tempfile.TemporaryDirectory() as d:
            stem = os.path.basename(d)
            for ext, data in (('4bpp', bytes(32768)),
                              ('bin', bytes(mt.CONFIG_SIZE)),
                              ('gbapal', bytes(320))):
                with open(os.path.join(d, stem + '.' + ext), 'wb') as output:
                    output.write(data)
            source = os.path.join(d, 'indexed.png')
            Image.new('P', (16, 16), 1).save(source)

            with self.assertRaisesRegex(ValueError, 'lit palette bank'):
                mt.paint_metatile(d, 36, source, bank=5, write_bank=True)

    def test_reused_unreferenced_tile_is_not_overwritten_by_later_quadrants(self):
        from PIL import Image

        with tempfile.TemporaryDirectory() as d:
            stem = os.path.basename(d)
            gfx = bytearray(32768)
            gfx[32:64] = bytes([0x11] * 32)  # tile 1 already holds solid index 1
            cfg = bytearray(mt.CONFIG_SIZE)  # every metatile references tile 0
            pal = bytearray(320)
            for color in range(16):
                struct.pack_into('<H', pal, (16 + color) * 2,
                                 color | (color << 5) | (color << 10))
            for ext, data in (('4bpp', gfx), ('bin', cfg), ('gbapal', pal)):
                with open(os.path.join(d, stem + '.' + ext), 'wb') as output:
                    output.write(data)

            paint = Image.new('RGB', (16, 16))
            for quadrant, value in enumerate((1, 2, 3, 4)):
                channel = value << 3
                for y in range((quadrant // 2) * 8, (quadrant // 2 + 1) * 8):
                    for x in range((quadrant % 2) * 8, (quadrant % 2 + 1) * 8):
                        paint.putpixel((x, y), (channel, channel, channel))
            source = os.path.join(d, 'paint.png')
            paint.save(source)

            mt.paint_metatile(d, 36, source, bank=1)
            painted = mt._tileset_from_dir(d)
            self.assertEqual(list(paint.getdata()),
                             list(painted.metatile_image(36).getdata()))

    def test_down_log_strip_uses_the_vanilla_slots_and_native_snag_bank(self):
        bern = mt._tileset_from_dir(SNOWY_BERN)
        self.assertEqual([0x01, 0x34, 0x01],
                         [bern.terrain(m) for m in (7, 36, 11)])
        for metatile in (7, 36, 11):
            entries = struct.unpack_from('<4H', bern.cfg, metatile * 8)
            self.assertEqual({4}, {entry >> 12 for entry in entries})
            self.assertGreater(
                len(set(bern.metatile_image(metatile).convert('RGB').getdata())), 1,
                'snowy-bern metatile %d is still flat' % metatile,
            )

    def test_bank_fragments_use_tile_67s_pattern_in_the_native_snag_palette(self):
        bern = mt._tileset_from_dir(SNOWY_BERN)
        snow = list(bern.metatile_image(67).convert('RGB').getdata())
        wood = {bern.palettes[4][index] for index in (2, 11, 12, 13, 14)}
        native = bern.palettes[4][1:]

        def nearest(color):
            return min(native, key=lambda candidate: sum(
                (channel - other) ** 2 for channel, other in zip(color, candidate)))

        for metatile in (7, 11):
            pixels = list(bern.metatile_image(metatile).convert('RGB').getdata())
            self.assertEqual(80, sum(pixel in wood for pixel in pixels),
                             'metatile %d lost its vanilla wood silhouette' % metatile)
            mismatches = [position for position, (pixel, base) in
                          enumerate(zip(pixels, snow))
                          if pixel not in wood and pixel != nearest(base)]
            self.assertEqual([], mismatches,
                             'metatile %d does not preserve tile 67\'s snow pattern' % metatile)

    def test_down_log_does_not_replace_snowy_berns_shared_palette(self):
        with open(os.path.join(SNOWY_BERN, 'snowy-bern.gbapal'), 'rb') as source:
            self.assertEqual(
                '981988938f3617803c9f75ddb1391d731c551873bf2b96e06ea13a0bfeed4a63',
                hashlib.sha256(source.read()).hexdigest(),
            )


class TestVisitableTerrainSurvivesTheReskin(unittest.TestCase):
    """A retile may restyle a village; it may not stop it being a village.

    `bmmenu.c:735` shows Visit only when the unit stands on HOUSE / INN / RUINS_VILLAGE /
    VILLAGE_REGULAR terrain -- a `Village()` location event alone is not enough. So a reskin
    that maps a village metatile onto scenery silently deletes the reward, and nothing else
    in the pipeline notices: the map still compiles, renders and plays. That is exactly how
    ch04 lost both of vanilla Ch4's villages (#205).
    """

    VISITABLE = {'TERRAIN_HOUSE', 'TERRAIN_INN',
                 'TERRAIN_RUINS_VILLAGE', 'TERRAIN_VILLAGE_REGULAR'}

    def setUp(self):
        maps = os.path.join(REPO, 'campaigns/rime-of-the-frostmaiden/maps')
        with open(os.path.join(maps, 'reskin-learned.json')) as f:
            self.rules = json.load(f)
        # The snowy-bern retile family (Prologue/Ch1/Ch2/Ch4) all source TileConfiguration1,
        # so one source terrain table governs every entry in the learned map.
        with open(os.path.join(REPO, 'fireemblem8u/graphics/map/TileConfiguration1.bin'),
                  'rb') as f:
            self.vanilla_terrain = f.read()[8192:]
        with open(os.path.join(maps, 'tilesets/snowy-bern/snowy-bern.bin'), 'rb') as f:
            self.snow_terrain = f.read()[8192:]
        self.names = {int(value, 0): name for name, value in re.findall(
            r'(TERRAIN_[A-Z0-9_]+)\s*=\s*(0[xX][0-9A-Fa-f]+|\d+)',
            bc.vanilla_decomp_text('include/constants/terrains.h'))}

    def test_a_visitable_tile_stays_visitable_through_the_learned_map(self):
        broken = []
        for source, target in self.rules['map'].items():
            source_name = self.names.get(self.vanilla_terrain[int(source)])
            if source_name not in self.VISITABLE:
                continue
            target_name = self.names.get(self.snow_terrain[int(target)])
            if target_name != source_name:
                broken.append('%s (%s) -> %s (%s)'
                              % (source, source_name, target, target_name))
        self.assertEqual([], broken,
                         'the reskin turns a visitable tile into scenery: %s' % broken)

    def test_visitable_terrain_is_protected_from_a_future_retile(self):
        """The guard, not just the instance: `preserved_terrain_targets` rejects a mapping
        whose target terrain differs from the source's, but only for terrains listed here.
        Forest alone (#193) let ch04's villages through."""
        protected = {self.names.get(t) for t in self.rules['preserve_terrain_variants']}
        self.assertTrue(self.VISITABLE <= protected,
                        'unprotected visitable terrain: %s' % (self.VISITABLE - protected))


class TestCh04MapAndRosterPlacement(unittest.TestCase):
    def test_the_compiled_map_is_visitable_where_vanilla_put_its_villages(self):
        """The retile may restyle vanilla Ch4's two villages; it may not un-village them.
        Vanilla Ch4 wires `Village(0, ..., 1, 11)` and `Village(0, ..., 8, 2)`, and Visit is
        offered only on visitable terrain (bmmenu.c:735), so these two tiles decide whether
        ch04's Iron Axe exists at all (#205)."""
        maps = os.path.join(REPO, 'campaigns/rime-of-the-frostmaiden/maps')
        with open(os.path.join(maps, 'ch04-lonelywood-forest.json')) as f:
            width = json.load(f)['width']
        with open(os.path.join(maps, 'ch04-lonelywood-forest.mar'), 'rb') as f:
            mar = f.read()
        tileset = mt._tileset_from_dir(os.path.join(maps, 'tilesets/snowy-bern'))
        names = {int(value, 0): name for name, value in re.findall(
            r'(TERRAIN_[A-Z0-9_]+)\s*=\s*(0[xX][0-9A-Fa-f]+|\d+)',
            bc.vanilla_decomp_text('include/constants/terrains.h'))}
        for x, y in ((8, 2), (1, 11)):
            metatile = struct.unpack_from('<H', mar, (y * width + x) * 2)[0] >> 5
            self.assertEqual('TERRAIN_VILLAGE_REGULAR',
                             names.get(tileset.terrain(metatile)),
                             'ch04 (%d,%d) is metatile %d -- not a village tile'
                             % (x, y, metatile))

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
        # Realigned 2026-07-21 to the vanilla-Ch4 twin (see the ch04 ADR): the turn-1 line is
        # monsters-only (mogall + melee revenant + melee bonewalker + entombed); `mauthedoog` is now
        # the turn-2 NW-fog reveal pack, and the turn-3 reinforcements mirror the twin's two packs.
        expected = {
            'mogall': (
                'Mogall',
                [[11, 6], [13, 7], [12, 8], [13, 11]],
            ),
            'revenant': (
                'Revenant',
                [[9, 9], [10, 10]],
            ),
            'bonewalker': (
                'Bonewalker',
                [[1, 14], [5, 13], [8, 14]],
            ),
            'entoumbed': ('Entombed', [[13, 13]]),
            # The pack's FOOTPRINT is what mirrors vanilla Ch4; the ORDER is ours, because
            # positions[0] is the leader (Lupin) tile. He moved [0,0] -> [2,1]: at [0,0] he
            # sat outside the party's fog vision and was never drawn in his own reveal.
            # Compared as a set below, with the leader pinned separately.
            'mauthedoog': (
                'Mauthe Doog',
                [[2, 1], [2, 0], [0, 2], [0, 0], [1, 0], [0, 1]],
            ),
            'revenant-reinf': (
                'Revenant',
                [[13, 9], [14, 8], [10, 12], [11, 14]],
            ),
            'bonewalker-reinf': (
                'Bonewalker',
                [[14, 6], [13, 5], [14, 11]],
            ),
        }
        for unit_id, (name, positions) in expected.items():
            unit = enemies[unit_id]
            self.assertEqual(name, unit['name'])
            if unit_id == 'mauthedoog':
                # Footprint = vanilla's; order = ours (positions[0] is the leader's tile).
                self.assertCountEqual(positions, unit['positions'])
            else:
                self.assertEqual(positions, unit['positions'])
            self.assertEqual(unit['count'], len(unit['positions']))

        # The pack LEADER must stand where the party can actually see him when the reveal
        # fires -- an unseen unit is not drawn, so a leader outside fog vision makes his own
        # cutscene focus empty snow (verified in-engine by the `ch04sprites` scenario).
        self.assertEqual([2, 1], enemies['mauthedoog']['positions'][0])

        map_dir = os.path.join(
            REPO, 'campaigns/rime-of-the-frostmaiden/maps')
        with open(os.path.join(map_dir, 'ch04-lonelywood-forest.json')) as f:
            layout = json.load(f)
        with open(os.path.join(map_dir, 'ch04-lonelywood-forest.mar'), 'rb') as f:
            raw = f.read()
        cells = [struct.unpack_from('<H', raw, i)[0] >> 5
                 for i in range(0, len(raw), 2)]
        # Snapshot of the approved layout. Re-pinned 2026-08-01 (#205): the two village
        # doors at (8,2) and (1,11) were metatile 994 (RUINS_REGULAR) and are now 898
        # (VILLAGE_REGULAR) -- the reskin had mapped vanilla's village tile onto scenery,
        # which silently deleted both of vanilla Ch4's villages. Two cells changed, nothing
        # else; the per-tile assertion above is the one that states the intent.
        self.assertEqual(
            'c2c4ad7052242d2b731b7ad169fa8a29a0c680a0b48868134ff48dffb1d330b3',
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


class TestVariantCompatibility(unittest.TestCase):
    """A chapter-local tileset variant may ADD into unused slots -- never touch a live one.

    That is the rule protecting every map that already shipped on the base tileset: ch04
    rides snowy-bern, so a ch06 edit that reached a slot ch04 draws would silently
    restyle or re-terrain a finished chapter.
    """

    MAPS = os.path.join(REPO, 'campaigns/rime-of-the-frostmaiden/maps')

    def _variant(self, mutate):
        """Copy snowy-bern into a temp dir under a variant name, mutate it, and test."""
        base = os.path.join(self.MAPS, 'tilesets', 'snowy-bern')
        with tempfile.TemporaryDirectory() as tmp:
            tilesets = os.path.join(tmp, 'tilesets')
            os.makedirs(os.path.join(tilesets, 'snowy-bern'))
            os.makedirs(os.path.join(tilesets, 'variant'))
            for ext in ('4bpp', 'bin', 'gbapal'):
                blob = open(os.path.join(base, 'snowy-bern.%s' % ext), 'rb').read()
                open(os.path.join(tilesets, 'snowy-bern',
                                  'snowy-bern.%s' % ext), 'wb').write(blob)
                if ext == 'bin':
                    blob = mutate(bytearray(blob))
                open(os.path.join(tilesets, 'variant',
                                  'variant.%s' % ext), 'wb').write(bytes(blob))
            return mt.tilesets_are_compatible_variants(tmp, 'snowy-bern', 'variant')

    def _first_slot(self, terrain_is_zero):
        ts = mt._tileset_from_dir(os.path.join(self.MAPS, 'tilesets', 'snowy-bern'))
        for m in range(1, 1024):
            if (ts.terrain(m) == 0) == terrain_is_zero:
                return m
        self.fail('no such slot')

    def test_adding_into_an_unused_slot_is_compatible(self):
        free = self._first_slot(True)
        live = self._first_slot(False)

        def mutate(cfg):
            cfg[free * 8:free * 8 + 8] = cfg[live * 8:live * 8 + 8]
            cfg[8192 + free] = 0x0C
            return cfg

        self.assertTrue(self._variant(mutate))

    def test_reterraining_a_live_slot_is_rejected(self):
        live = self._first_slot(False)

        def mutate(cfg):
            cfg[8192 + live] = 0x0C
            return cfg

        self.assertFalse(self._variant(mutate))

    def test_repointing_a_live_slots_art_is_rejected(self):
        live = self._first_slot(False)

        def mutate(cfg):
            cfg[live * 8] ^= 0x01
            return cfg

        self.assertFalse(self._variant(mutate))

    def test_shipped_ice_variant_obeys_the_rule(self):
        self.assertTrue(mt.tilesets_are_compatible_variants(
            self.MAPS, 'snowy-bern', 'snowy-bern-ice'))

    def test_a_different_tileset_is_not_a_variant(self):
        self.assertFalse(mt.tilesets_are_compatible_variants(
            self.MAPS, 'snowy-bern', 'snowy-fields'))


class TestDeclaredDivergenceLookup(unittest.TestCase):
    """The escape hatch must actually find its chapter.

    It shipped dead: it compared the chapter `id` (ch06-the-maer-monster) against the map
    stem (ch06-maer-monster) and prefix-matched `map.file`, which is always
    'maps/<stem>.<ext>' and so never starts with the stem. Both tests failed for every
    chapter, so the guard silently saw "nothing declared" and rejected every deliberate
    cell. A green suite proved nothing because nothing exercised the lookup.
    """

    def setUp(self):
        sys.path.insert(0, os.path.join(REPO, 'tools'))
        import import_map_layout
        self.iml = import_map_layout

    def test_ch06_resolves_by_map_stem(self):
        rows = self.iml._declared_divergence('ch06-maer-monster')
        self.assertTrue(rows, 'ch06 declares divergences; the lookup returned none')
        self.assertIn((17, 13), rows)

    def test_unknown_stem_declares_nothing(self):
        self.assertEqual(self.iml._declared_divergence('ch99-nope'), {})

    def test_terrain_byte_accepts_every_spelling(self):
        forest = self.iml.TERRAIN_BY_NAME['TERRAIN_FOREST']
        for spelling in ('0x0C', '0x0c', 12, 'TERRAIN_FOREST'):
            self.assertEqual(self.iml._terrain_byte(spelling), forest)

    def test_every_declared_from_matches_vanilla(self):
        """A `from:` that lies makes the whole allowlist untrustworthy."""
        import yaml
        chapter = os.path.join(
            REPO, 'campaigns/rime-of-the-frostmaiden/chapters/ch06-the-maer-monster.yaml')
        with open(chapter, encoding='utf-8') as handle:
            data = yaml.safe_load(handle)
        _, _, cells, terrain = mt.vanilla_layout_data(
            os.path.join(REPO, 'fireemblem8u'), 'Ch13EphraimMap')
        width = data['map']['size'].split('\u00d7')[0]
        width = int(width) if width.isdigit() else 22
        names = {v: k for k, v in self.iml.TERRAIN_BY_NAME.items()}
        for row in data['terrain_divergence']:
            x, y = row['tile']
            got = names[terrain[cells[y * width + x]]]
            self.assertEqual(got, 'TERRAIN_' + row['from'],
                             'cell (%d, %d) declares from: %s but vanilla is %s'
                             % (x, y, row['from'], got))

class SetMetatileTerrain(unittest.TestCase):
    """Terrain is separate from art, and shared across every map on the tileset (#26).

    ch06's boat pockets are made by moving twelve terrain bytes and repainting nothing.
    The two things that must hold: the art really is untouched, and the blast radius is
    reported before it is taken -- a terrain byte belongs to the TILESET, so it changes the
    meaning of those metatiles for every map riding it, not just the one in mind.
    """

    def _tileset(self, tmp, terrain_bytes):
        d = os.path.join(tmp, 'probe')
        os.makedirs(d)
        with open(os.path.join(d, 'probe.bin'), 'wb') as fh:
            fh.write(bytes(8192) + bytes(terrain_bytes) + bytes(1024 - len(terrain_bytes)))
        with open(os.path.join(d, 'probe.4bpp'), 'wb') as fh:
            fh.write(bytes(32 * 1024))
        with open(os.path.join(d, 'probe.gbapal'), 'wb') as fh:
            fh.write(bytes(2 * 16 * 16))
        return d

    def test_it_moves_only_the_terrain_byte_and_leaves_the_art_alone(self):
        with tempfile.TemporaryDirectory() as tmp:
            d = self._tileset(tmp, [0x01, 0x0C, 0x0C, 0x10])
            before = open(os.path.join(d, 'probe.4bpp'), 'rb').read()
            changed = mt.set_metatile_terrain(d, [1, 2], 0x2E)
            self.assertEqual(changed, [(1, 0x0C, 0x2E), (2, 0x0C, 0x2E)])
            cfg = open(os.path.join(d, 'probe.bin'), 'rb').read()
            self.assertEqual(cfg[8192:8196], bytes([0x01, 0x2E, 0x2E, 0x10]))
            self.assertEqual(open(os.path.join(d, 'probe.4bpp'), 'rb').read(), before)

    def test_a_metatile_already_at_the_target_is_not_reported_as_changed(self):
        with tempfile.TemporaryDirectory() as tmp:
            d = self._tileset(tmp, [0x2E, 0x0C])
            self.assertEqual(mt.set_metatile_terrain(d, [0], 0x2E), [])

    def test_an_out_of_range_terrain_is_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            d = self._tileset(tmp, [0x01])
            with self.assertRaises(ValueError):
                mt.set_metatile_terrain(d, [0], 0x100)

    def test_terrain_impact_names_the_cells_that_change_meaning(self):
        """The audit that has to happen first. ch06 is the live case: twelve metatiles,
        fourteen cells, one map."""
        root = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                            'campaigns/rime-of-the-frostmaiden/maps')
        pocket = {10, 12, 17, 18, 30, 31, 40, 41, 48, 49, 50, 51}
        impact = mt.terrain_impact(root, 'snowy-bern-ice', pocket)
        self.assertEqual(list(impact), ['ch06-maer-monster'])
        self.assertEqual(sum(len(v) for v in impact['ch06-maer-monster'].values()), 14)

    def test_ch04s_tileset_is_untouched_by_ch06s_pocket_metatiles(self):
        """snowy-bern and snowy-bern-ice are separate .bin files, and ch04 rides the former.
        This is the claim the whole 'it costs no repainting' argument rests on."""
        root = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                            'campaigns/rime-of-the-frostmaiden/maps')
        pocket = {10, 12, 17, 18, 30, 31, 40, 41, 48, 49, 50, 51}
        self.assertEqual(mt.terrain_impact(root, 'snowy-bern', pocket), {})


if __name__ == '__main__':
    unittest.main()
