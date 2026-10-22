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
        # No reskin dresses ch01's armor-knight, so naming the vanilla class is right here. Another
        # chapter's Knight reskin (ch06's IronShell) must not reach him: the key is (chapter,
        # token), never `base` (#347).
        self.assertEqual('CLASS_ARMOR_KNIGHT', inject.chapters.ch01.CH01_CLASS_IDS['armor-knight'])
        dressed = [r['id'] for r in inject.reskins.enemy_class_reskins(self.CAMPAIGN)
                   if 'armor-knight' in (r.get('dresses') or {}).get('ch01', [])]
        self.assertEqual([], dressed)

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


class AppendedSlotIds(unittest.TestCase):
    """An appended class id is DECLARED (a save stores class ids, so one may never move), and
    the build refuses ids that collide, overlap vanilla, or leave a gap."""
    VANILLA = {'CLASS_SOLDIER': 0x0F, 'CLASS_PUPIL_T1': 0x7F}

    def rk(self, rid, slot_id=None, slot=None):
        out = {'id': rid, 'base': 'CLASS_SOLDIER', 'slot': slot or 'CLASS_' + rid.upper()}
        if slot_id is not None:
            out['slot_id'] = slot_id
        return out

    def test_the_live_campaign_is_clean(self):
        self.assertEqual([], inject.reskins.slot_id_violations(
            inject.reskins.enemy_class_reskins('rime-of-the-frostmaiden'),
            inject.reskins.vanilla_class_values()))

    def test_a_new_slot_without_an_id_is_told_the_next_free_one(self):
        got = inject.reskins.slot_id_violations(
            [self.rk('a', 0x80), self.rk('b', 0x81), self.rk('new')], self.VANILLA)
        self.assertEqual(1, len(got))
        self.assertIn('next free id is 0x82', got[0])

    def test_a_vanilla_slot_needs_no_id(self):
        self.assertEqual([], inject.reskins.slot_id_violations(
            [self.rk('goblin', slot='CLASS_SOLDIER')], self.VANILLA))

    def test_collision_overlap_and_gap_are_each_refused(self):
        dup = inject.reskins.slot_id_violations([self.rk('a', 0x80), self.rk('b', 0x80)],
                                                self.VANILLA)
        self.assertTrue(any("'a' and 'b'" in m for m in dup), dup)
        self.assertTrue(inject.reskins.slot_id_violations([self.rk('a', 0x7F)], self.VANILLA))
        gap = inject.reskins.slot_id_violations([self.rk('a', 0x80), self.rk('b', 0x82)],
                                                self.VANILLA)
        self.assertTrue(any('without a gap' in m for m in gap), gap)



class ClonesPlayAsTheirBase(unittest.TestCase):
    """A reskin is its base class to the rules (ADR 0362): on its effectiveness lists, and
    never a clone of a class the engine tests by id."""

    ITEMUSE = ('CONST_DATA u8 ItemEffectiveness_Horse[] = {\n'
               '    CLASS_TROUBADOUR,\n'
               '    CLASS_CAVALIER,\n'
               '    CLASS_NONE,\n'
               '};\n'
               '\n'
               'CONST_DATA u8 ItemEffectiveness_Armor[] = {\n'
               '    CLASS_ARMOR_KNIGHT,\n'
               '    CLASS_NONE,\n'
               '};\n')

    def test_a_clone_joins_every_list_its_base_is_on(self):
        out = inject.reskins.add_clones_to_effectiveness(
            self.ITEMUSE, [('CLASS_CAVALIER', 'CLASS_CAV_SHARK_RIDER'),
                           ('CLASS_SOLDIER', 'CLASS_SOL_MERFOLK')])
        self.assertIn('    CLASS_CAVALIER,\n    CLASS_CAV_SHARK_RIDER,\n    CLASS_NONE,', out)
        self.assertNotIn('CLASS_SOL_MERFOLK', out)
        self.assertEqual(out.count('CLASS_CAV_SHARK_RIDER'), 1)

    def test_a_name_that_only_starts_like_the_base_is_not_matched(self):
        out = inject.reskins.add_clones_to_effectiveness(
            self.ITEMUSE, [('CLASS_ARMOR', 'CLASS_X')])
        self.assertNotIn('CLASS_X', out)

    def test_a_trailing_comment_or_blank_line_keeps_the_layout(self):
        text = ('CONST_DATA u8 ItemEffectiveness_Horse[] = {\n'
                '\n'
                '    CLASS_CAVALIER, /* mounted */\n'
                '    CLASS_NONE,\n'
                '};\n')
        out = inject.reskins.add_clones_to_effectiveness(
            text, [('CLASS_CAVALIER', 'CLASS_CAV_SHARK_RIDER')])
        self.assertIn('{\n\n    CLASS_CAVALIER, /* mounted */\n    CLASS_CAV_SHARK_RIDER,\n'
                      '    CLASS_NONE,', out)

    def test_the_step_writes_from_vanilla_so_a_rebuild_adds_nothing(self):
        # data_itemuse.c is restored every build AND the step reads HEAD, not the tree.
        import inject.warm
        self.assertIn('src/data_itemuse.c', inject.warm.PATCHED_DECOMP_FILES)
        import inspect
        self.assertIn("vanilla_decomp_text('src/data_itemuse.c')",
                      inspect.getsource(inject.reskins.inject_reskin_effectiveness))

    def test_every_source_that_tests_a_class_id_is_classified(self):
        import subprocess
        decomp = os.path.join(inject.reskins.REPO, 'fireemblem8u')
        listed = subprocess.check_output(
            ['git', '-C', decomp, 'grep', '-l', '-E',
             r'(==|!=) *CLASS_[A-Z]|case CLASS_[A-Z]|CLASS_[A-Z0-9_]+ *(==|!=)',
             'HEAD', '--', 'src/*.c'], encoding='utf-8')
        found = {line.split(':', 1)[1] for line in listed.split()}
        patches = os.path.join(inject.reskins.REPO, 'engine', 'patches')
        for root, _, names in os.walk(patches):
            for name in sorted(n for n in names if n.endswith('.patch')):
                path = os.path.join(root, name)
                with open(path, encoding='utf-8') as f:
                    added = ''.join(l[1:] for l in f
                                    if l.startswith('+') and not l.startswith('+++'))
                if inject.reskins.class_id_tests(added):
                    found.add(os.path.relpath(path, inject.reskins.REPO))
        gameplay = set(inject.reskins.GAMEPLAY_ID_SOURCES)
        presentation = set(inject.reskins.PRESENTATION_ID_SOURCES)
        self.assertEqual(gameplay & presentation, set())
        self.assertEqual(found - {'src/bmitem.c'} - gameplay - presentation, set(),
                         'classify these in inject.reskins')

    def test_id_switched_classes_include_the_combat_skills(self):
        ids = inject.reskins.id_switched_classes()
        for c in ('CLASS_SNIPER', 'CLASS_WYVERN_KNIGHT', 'CLASS_GENERAL', 'CLASS_BISHOP',
                  'CLASS_ENTOUMBED', 'CLASS_MOGALL', 'CLASS_ROGUE'):
            self.assertIn(c, ids)
        self.assertNotIn('CLASS_CAVALIER', ids)

    def test_no_declared_reskin_clones_an_id_switched_class(self):
        ids = inject.reskins.id_switched_classes()
        for rk in inject.reskins.enemy_class_reskins('rime-of-the-frostmaiden'):
            self.assertNotIn(rk['base'], ids, rk['id'])


if __name__ == '__main__':
    unittest.main()
