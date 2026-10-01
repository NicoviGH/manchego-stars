#!/usr/bin/env python3
"""Tests for tools/inject/item_icons.py.

Run:  python3 tools/test_inject_item_icons.py
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import inject.arena
import inject.item_icons
from inject.engine_patches import patched_text


class ItemIconPal2(unittest.TestCase):
    """Custom-coloured icons append a third source palette and draw from reserved BG bank 15.

    The two vanilla banks are shared UI state and must never be repainted; text can use bank 5.
    """
    CAMPAIGN = 'rime-of-the-frostmaiden'

    def test_bgr555_packs_5bit_channels(self):
        self.assertEqual(inject.arena._bgr555('#000000'), 0)
        self.assertEqual(inject.arena._bgr555('#ffffff'), 0x7FFF)          # 31|31<<5|31<<10
        self.assertEqual(inject.arena._bgr555('#ff0000'), 0x001F)          # red in low 5 bits
        self.assertEqual(inject.arena._bgr555('#0000ff'), 0x7C00)          # blue in high 5 bits

    def test_pal2_palette_is_16_bgr555_entries(self):
        colors = ['#000000'] * 16
        b = inject.item_icons._item_icon_pal2_bytes(colors)
        self.assertEqual(len(b), 32)                             # 16 colors x 2 bytes
        self.assertEqual(b, b'\x00' * 32)

    def test_pal2_palette_rejects_wrong_length(self):
        with self.assertRaises(SystemExit):
            inject.item_icons._item_icon_pal2_bytes(['#000000'] * 15)

    def test_pal2_appends_third_bank_without_repainting_vanilla_banks(self):
        vanilla = bytearray(range(64))
        out = inject.item_icons._append_item_icon_pal2(vanilla, ['#000000'] * 16)
        self.assertEqual(out[:64], vanilla)
        self.assertEqual(out[64:], b'\x00' * 32)

    def test_redgem_resolves_to_pal2_icon_id_136(self):
        # ITEM_REDGEM (the Tourmaline) is the campaign's one custom-palette icon; its iconId is 136.
        self.assertEqual(inject.item_icons._pal2_icon_ids(self.CAMPAIGN), [136])

    def test_iconids_asm_lists_ids_then_terminator(self):
        asm = inject.item_icons._ms_pal2_iconids_asm([136, 5])
        self.assertIn('.global gMSPal2IconIds', asm)
        self.assertIn('.hword 136', asm)
        self.assertIn('.hword 5', asm)
        self.assertIn('.hword 0xFFFF', asm)                     # terminator (no valid iconId is 0xFFFF)

    def test_patch_loads_custom_bank_fifteen_without_changing_vanilla_load(self):
        out = patched_text('src/icon.c')
        self.assertIn('ApplyPalettes(item_icon_palette[0], Dest, 2);', out)
        self.assertNotIn('ApplyPalette(item_icon_palette[2], 15);\n}', out)
        self.assertIn('gMSPal2IconIds', out)
        self.assertIn('(OamPalBase & 0xF000) == 0x4000', out)
        self.assertIn('ApplyPalette(item_icon_palette[2], 15);', out)
        self.assertIn('OamPalBase = (OamPalBase & 0x0FFF) | 0xF000;', out)


if __name__ == '__main__':
    unittest.main()
