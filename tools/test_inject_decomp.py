#!/usr/bin/env python3
"""Tests for tools/inject/decomp.py.

Run:  python3 tools/test_inject_decomp.py
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import inject.decomp
from inject import source as injector  # the injector's source, every file of it (#389)


class FeItemEnum(unittest.TestCase):
    """Resolve a YAML inventory entry to its vanilla ITEM_ enum -- via fe_base (a flavor
    name over a vanilla weapon) else the id itself (a plain vanilla weapon). Lets the
    prologue injector drive the boss weapon from the ch00 YAML, not a hardcode (#52)."""

    def test_resolves_flavor_weapon_via_fe_base(self):
        # Sephek's "ice-longsword" is flavor; fe_base steel-sword supplies the real item.
        self.assertEqual(inject.decomp.fe_item_enum({'id': 'ice-longsword', 'fe_base': 'steel-sword'}),
                         'ITEM_SWORD_STEEL')

    def test_resolves_plain_weapon_via_id(self):
        self.assertEqual(inject.decomp.fe_item_enum({'id': 'iron-axe'}), 'ITEM_AXE_IRON')


class ChapterEnum(unittest.TestCase):
    """`chapter_enum` / `chapter_titles`: the one reader of include/constants/chapters.h."""

    def test_a_route_chapter_resolves_by_its_constant(self):
        enum = inject.decomp.chapter_enum()
        self.assertEqual(0x0A, enum['CHAPTER_E_9'])
        self.assertEqual(0x0D, enum['CHAPTER_E_13'])      # Hamill Canyon; chapter_settings calls it E12
        self.assertEqual(0x3D, enum['CHAPTER_E_11'])      # Ch11 sits out of line
        self.assertEqual(0x3E, enum['CHAPTER_I_11'])
        self.assertEqual(0x16, enum['CHAPTER_E_21X'])

    def test_a_title_is_the_enumerators_comment(self):
        titles = inject.decomp.chapter_titles()
        self.assertEqual('Ch13: Hamill Canyon', titles['CHAPTER_E_13'])
        self.assertEqual('Ch11: Phantom Ship', titles['CHAPTER_I_11'])


if __name__ == '__main__':
    unittest.main()
