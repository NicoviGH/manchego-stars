#!/usr/bin/env python3
"""Workflow coverage for #193's protected vanilla forest retiles."""
import importlib
import json
import os
import re
import struct
import subprocess
import sys
import unittest
import uuid


REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DECOMP = os.path.join(REPO, 'fireemblem8u')
MAPS = os.path.join(REPO, 'campaigns/rime-of-the-frostmaiden/maps')
TOOLS = os.path.join(REPO, 'tools')
if TOOLS not in sys.path:
    sys.path.insert(0, TOOLS)

try:
    importer = importlib.import_module('import_map_layout')
except SystemExit:
    importer = None


def _compiled_grid(stem):
    with open(os.path.join(MAPS, stem + '.json'), encoding='utf-8') as source:
        layout = json.load(source)
    with open(os.path.join(MAPS, stem + '.mar'), 'rb') as source:
        raw = source.read()
    grid = [struct.unpack_from('<H', raw, cell * 2)[0] >> 5
            for cell in range(layout['width'] * layout['height'])]
    return layout['width'], layout['height'], grid


class TestVanillaRetileImport(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from map_tileset_tool import (_tileset_from_dir,
                                      preserved_terrain_targets,
                                      vanilla_layout_data)

        width, _, source_cells, source_terrain = vanilla_layout_data(
            DECOMP, 'PrologueMap')
        with open(os.path.join(MAPS, 'reskin-learned.json'), encoding='utf-8') as source:
            rules = json.load(source)
        snowy = _tileset_from_dir(os.path.join(MAPS, 'tilesets/snowy-bern'))
        targets = preserved_terrain_targets(
            source_cells, source_terrain, snowy, rules, width)
        cls.first_forest_cell = min(targets)
        cls.generic_snow_tile = 6

    def prologue_export(self):
        width, height, grid = _compiled_grid('ch00-prologue')
        return {
            'tileset': 'snowy-bern',
            'retile_mode': 'vanilla',
            'vanilla_layout': 'PrologueMap',
            'width': width,
            'height': height,
            'grid': grid,
        }

    def require_importer(self):
        if importer is None:
            self.fail('import_map_layout must be import-safe')
        self.assertTrue(hasattr(importer, 'validate_vanilla_retile'))

    def test_valid_vanilla_retile_passes(self):
        self.require_importer()
        data = self.prologue_export()
        importer.validate_vanilla_retile(data, DECOMP, MAPS)

    def test_changed_forest_cell_is_rejected_before_compile(self):
        self.require_importer()
        data = self.prologue_export()
        data['grid'][self.first_forest_cell] = self.generic_snow_tile
        with self.assertRaisesRegex(ValueError, r'forest sequence.*expected'):
            importer.validate_vanilla_retile(data, DECOMP, MAPS)

    def test_custom_canvas_without_vanilla_layout_is_exempt(self):
        self.require_importer()
        importer.validate_vanilla_retile(
            {'tileset': 'snowy-bern', 'retile_mode': 'custom',
             'width': 1, 'height': 1, 'grid': [6]},
            DECOMP, MAPS)

    def test_snowy_payload_without_source_metadata_requires_regeneration(self):
        self.require_importer()
        data = self.prologue_export()
        del data['retile_mode']
        del data['vanilla_layout']
        with self.assertRaisesRegex(ValueError, r'regenerate'):
            importer.validate_vanilla_retile(data, DECOMP, MAPS)


class TestMapEditorRetileMetadata(unittest.TestCase):
    def test_prologue_generation_stamps_start_and_browser_exports(self):
        token = 'task-2-' + uuid.uuid4().hex
        html_name = token + '.html'
        json_name = token + '.json'
        paths = [
            os.path.join(REPO, 'review', html_name),
            os.path.join(REPO, 'review', json_name),
            os.path.join(REPO, 'review', token + '-start.png'),
        ]
        try:
            subprocess.run(
                [sys.executable, '-B', os.path.join(TOOLS, 'gen_map_editor.py'),
                 'PrologueMap', html_name, json_name],
                cwd=REPO, check=True, capture_output=True, text=True)

            with open(paths[1], encoding='utf-8') as source:
                start = json.load(source)
            self.assertEqual(start['retile_mode'], 'vanilla')
            self.assertEqual(start['vanilla_layout'], 'PrologueMap')

            with open(paths[0], encoding='utf-8') as source:
                html = source.read()
            match = re.search(r'const EXPORT_META=(\{.*?\});', html)
            self.assertIsNotNone(match, 'browser export metadata was not embedded')
            browser_export = json.loads(match.group(1))
            self.assertEqual(browser_export['retile_mode'], 'vanilla')
            self.assertEqual(browser_export['vanilla_layout'], 'PrologueMap')
        finally:
            for path in paths:
                if os.path.exists(path):
                    os.remove(path)


if __name__ == '__main__':
    unittest.main()
