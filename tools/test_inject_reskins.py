#!/usr/bin/env python3
"""Tests for tools/inject/reskins.py.

Run:  python3 tools/test_inject_reskins.py
"""
import os
import re
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import inject.chapters.ch01
import inject.reskins


class AppendedClassSlot(unittest.TestCase):
    """Extend gClassData past the vanilla 0x7F tail so an enemy reskin can ride a NEW
    class slot (#23: the Lizardzerker) once the three ballista-empties are used up. Two
    pure text transforms: insert the enum constant + append a cloned gClassData entry."""

    HEADER = ('enum {\n'
              '    CLASS_MERCENARY           = 0x05,\n'
              '    CLASS_JOURNEYMAN_T1       = 0x7E,\n'
              '    CLASS_PUPIL_T1            = 0x7F,\n'
              '\n'
              '    // Hiding the game\'s misery\n'
              '    CLASS_OBSTACLE = CLASS_EPHRAIM_LORD,\n'
              '};\n')

    CDATA = ('CONST_DATA struct ClassData gClassData[] = {\n'
             '    [CLASS_MERCENARY - 1] = {\n'
             '        .SMSId = 0x10,\n'
             '        .number = CLASS_MERCENARY,\n'
             '        .pMapSpriteAnim = &gUnknown_08X,\n'
             '    },\n'
             '    [CLASS_PUPIL_T1 - 1] = {\n'
             '        .SMSId = 0x11,\n'
             '        .number = CLASS_PUPIL_T1,\n'
             '    },\n'
             '};\n')

    def test_enum_insert_places_the_new_constant_after_the_last_numeric_class(self):
        new = inject.reskins.class_enum_insert(self.HEADER, 'CLASS_MNC_LIZARDZERKER', 0x80)
        self.assertIn('CLASS_MNC_LIZARDZERKER = 0x80,', new)
        # after the vanilla 0x7F tail, before the CLASS_OBSTACLE alias block
        self.assertLess(new.index('CLASS_PUPIL_T1'), new.index('CLASS_MNC_LIZARDZERKER'))
        self.assertLess(new.index('CLASS_MNC_LIZARDZERKER'), new.index('CLASS_OBSTACLE'))
        # parseable by the existing enum reader -> 0x80
        self.assertEqual(dict(re.findall(r'(CLASS_MNC_LIZARDZERKER)\s*=\s*(0x[0-9A-Fa-f]+)',
                                         new)).get('CLASS_MNC_LIZARDZERKER'), '0x80')

    def test_enum_insert_is_idempotent(self):
        once = inject.reskins.class_enum_insert(self.HEADER, 'CLASS_MNC_LIZARDZERKER', 0x80)
        twice = inject.reskins.class_enum_insert(once, 'CLASS_MNC_LIZARDZERKER', 0x80)
        self.assertEqual(once, twice)
        self.assertEqual(twice.count('CLASS_MNC_LIZARDZERKER = 0x80,'), 1)

    def test_classdata_append_clones_the_base_body_under_the_new_designator(self):
        new = inject.reskins.classdata_append_clone(self.CDATA, 'CLASS_MERCENARY', 'CLASS_MNC_LIZARDZERKER')
        self.assertIn('[CLASS_MNC_LIZARDZERKER - 1] = {', new)
        # the clone carries the base body verbatim (SMSId/anim ride along; the reskin loop
        # repoints .number/.SMSId afterward via the existing _set_field path)
        clone = new[new.index('[CLASS_MNC_LIZARDZERKER - 1]'):]
        self.assertIn('.SMSId = 0x10,', clone)
        self.assertIn('.pMapSpriteAnim = &gUnknown_08X,', clone)

    def test_classdata_append_leaves_the_base_entry_byte_unchanged(self):
        new = inject.reskins.classdata_append_clone(self.CDATA, 'CLASS_MERCENARY', 'CLASS_MNC_LIZARDZERKER')
        base = self.CDATA[self.CDATA.index('[CLASS_MERCENARY - 1]'):self.CDATA.index('[CLASS_PUPIL_T1 - 1]')]
        self.assertIn(base, new)                       # donor block untouched
        self.assertLess(new.index('[CLASS_MNC_LIZARDZERKER - 1]'), new.rindex('};'))  # inside the array

    def test_classdata_append_is_idempotent(self):
        once = inject.reskins.classdata_append_clone(self.CDATA, 'CLASS_MERCENARY', 'CLASS_MNC_LIZARDZERKER')
        twice = inject.reskins.classdata_append_clone(once, 'CLASS_MERCENARY', 'CLASS_MNC_LIZARDZERKER')
        self.assertEqual(once, twice)
        self.assertEqual(twice.count('[CLASS_MNC_LIZARDZERKER - 1] = {'), 1)


class AReskinIsResolvedByItsOwnSlot(unittest.TestCase):
    """A reskin CLONES a vanilla class into its OWN class slot, so `base` is many-to-one.

    ch01 resolved its goblins through a dict keyed on the base class
    (`{rk['base']: rk['slot'] ...}`), and four bases are claimed twice -- goblin-soldier and
    ch05's risen-spear both clone CLASS_SOLDIER, goblin-fighter and tomb-reaver both clone
    CLASS_FIGHTER. Last-wins, so ch01's Fire Imps shipped as ch05's skeletons for twelve
    days (#347). Nothing failed: #48 measures stats, the playtest scenarios assert memory
    state, and neither reads which sprite a unit wears.

    Every other chapter names its slot outright (ch05: 'soldier' -> CLASS_SOL_SKELEBERDIER),
    which is correct by construction. ch01 now does the same.
    """

    CAMPAIGN = 'rime-of-the-frostmaiden'

    def _slot_of(self, reskin_id):
        rk = next(r for r in inject.reskins.enemy_class_reskins(self.CAMPAIGN)
                  if r['id'] == reskin_id)
        return rk['slot']

    def test_ch01_names_the_goblin_slots_not_the_vanilla_chassis(self):
        # Read the slot from campaign.yaml rather than repeating it here: the bug was the
        # code and the data disagreeing, so a test that hardcodes both cannot see it.
        self.assertEqual(self._slot_of('goblin-soldier'), inject.chapters.ch01.CH01_CLASS_IDS['soldier'])
        self.assertEqual(self._slot_of('goblin-fighter'), inject.chapters.ch01.CH01_CLASS_IDS['fighter'])

    def test_the_chief_has_no_reskin_and_stays_a_vanilla_knight(self):
        # armor-knight is claimed by no reskin, so naming the vanilla class is right here.
        self.assertEqual('CLASS_ARMOR_KNIGHT', inject.chapters.ch01.CH01_CLASS_IDS['armor-knight'])
        bases = {r['base'] for r in inject.reskins.enemy_class_reskins(self.CAMPAIGN)}
        self.assertNotIn('CLASS_ARMOR_KNIGHT', bases)

    def test_no_two_reskins_claim_the_same_slot(self):
        # THIS is the invariant, not "no two share a base" -- sharing a base is legitimate
        # and four pairs do it. A slot is the identity; two creatures in one slot is the
        # collision that would actually lose art.
        slots = [r['slot'] for r in inject.reskins.enemy_class_reskins(self.CAMPAIGN)]
        self.assertEqual(len(slots), len(set(slots)),
                         'a reskin slot is claimed twice: %s' % sorted(
                             s for s in slots if slots.count(s) > 1))

    def test_a_contested_base_is_still_allowed(self):
        # Guard the guard: several creatures rightly clone one chassis, and a check that
        # rejected duplicate bases would forbid ch05's skeletons and ch06's merfolk.
        bases = [r['base'] for r in inject.reskins.enemy_class_reskins(self.CAMPAIGN)]
        self.assertGreater(len(bases), len(set(bases)),
                           'bases are expected to be reused; if this ever stops being true '
                           'the many-to-one hazard is gone and this suite can relax')


if __name__ == '__main__':
    unittest.main()
