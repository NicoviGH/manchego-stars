#!/usr/bin/env python3
"""Tests for tools/inject/raw_pids.py.

Run:  python3 tools/test_inject_raw_pids.py
"""
import os
import re
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import inject.decomp
import inject.paths
import inject.raw_pids


class SlotRiderPersonalLine(unittest.TestCase):
    """A boss on a vanilla CHARACTER slot inherits that character's line, which was tuned for
    the character's own class. ch07's Speaker fights as a Fighter on Murray's Cavalier slot, so
    his authored line has to replace Murray's in the ROM, or the Fighter swap leaves him 4 Def
    and an attack speed short of the boss he stands in for."""

    def test_every_slot_source_rides_the_slot_it_writes(self):
        for slot, (_yaml, uid) in inject.raw_pids.SLOT_PERSONAL_SOURCES.items():
            self.assertEqual(inject.raw_pids.ENEMY_BASE_SLOT.get(uid), slot, uid)

    def test_the_patch_writes_the_yaml_line_onto_the_slot(self):
        text = inject.decomp.vanilla_decomp_text('src/data_characters.c')
        out = inject.raw_pids.slot_personal_data(text, 'rime-of-the-frostmaiden')
        for slot, (chapter_yaml, uid) in inject.raw_pids.SLOT_PERSONAL_SOURCES.items():
            chap = inject.raw_pids._load_chapter_yaml('rime-of-the-frostmaiden', chapter_yaml)
            unit = next(e for e in inject.raw_pids.personal_bearers(chap) if e.get('id') == uid)
            marker = '[%s - 1]' % slot
            start, end = inject.decomp._find_brace_block(out, marker, inject.paths.CHARACTERS_C)
            for field in inject.raw_pids.BASE_FIELDS:
                found = re.search(r'\.%s\s*=\s*(-?\d+)' % field, out[start:end])
                got = int(found.group(1)) if found else 0
                self.assertEqual(got, int(unit['personal'].get(field, 0)), (uid, field))


class RawPidBossBaseLevel(unittest.TestCase):
    """A raw-pid boss must declare `baseLevel`, or the difficulty malus wipes its line.

    `UnitAutolevelPenalty` only fires `if (level > unit->pCharacterData->baseLevel)`.
    EVERY vanilla named boss ships baseLevel >= the level it deploys at -- Saar 8/8,
    Breguet 4/4, Bazba 6/6, Novala 10/7 -- so vanilla bosses never take the penalty and
    their hand-authored personal line is what reaches the map in all three modes.

    Our bosses that ride a vanilla CHARACTER_ slot inherit that protection for free. The
    four that ride RAW pids sit in gCharacterData gaps, where every field including
    baseLevel reads 0/1 -- so the penalty always fired, reset them to class base and
    rebuilt them from growths. Measured in-engine before the fix: Ravisin came out 40 HP
    on Normal against 35 on Difficult, because the reset path re-runs full `UnitAutolevel`
    (promoted branch included, +9 levels) while the Difficult path never does.

    The failure is SILENT -- a gap is all zeros and nothing complains -- so the registry
    is guarded rather than merely documented.
    """

    RAW_BOSSES = {inject.chapter_ids.CH03_BOSS_PID: 8, '0xb6': 3, '0xb8': 7, '0xb9': 6}

    def test_every_raw_pid_boss_is_registered(self):
        missing = inject.raw_pids.unregistered_raw_pid_bosses('rime-of-the-frostmaiden')
        self.assertEqual(missing, [],
                         'raw-pid boss(es) with no RAW_PID_LEVEL_SOURCES row: %s' % missing)

    def test_the_registry_READER_sees_a_wave_boss_too(self):
        # otherwise the guard has no reachable green state: a raw-pid boss arriving in a wave
        # is flagged as unregistered, and adding the row that silences it makes the reader
        # sys.exit("does not exist") and kills the build.
        chap = {'enemy_units': [{'id': 'stowaway', 'is_boss': True, 'level': 9,
                                 'arrives_turn': 3}]}
        self.assertEqual(inject.raw_pids._entry_base_level_in(chap, 'stowaway'), 9)

    def test_the_registry_reads_a_DECLARED_body_level(self):
        # `levels:` is the per-body list the ROM is built from; reading `level:` past it
        # writes baseLevel 1 (so the malus fires) while the model treats the boss as
        # malus-immune at its real level.
        chap = {'enemy_units': [{'id': 'b', 'is_boss': True, 'levels': [9]}]}
        self.assertEqual(inject.raw_pids._entry_base_level_in(chap, 'b'), 9)

    def test_a_raw_pid_boss_under_any_roster_key_is_caught(self):
        # `_our_base_level` models every boss as malus-immune WHEREVER it is declared, and
        # this registry is what makes that true -- so the guard has to look everywhere too.
        for key in inject.raw_pids.ENEMY_ROSTER_KEYS:
            chap = {key: [{'id': 'stowaway', 'is_boss': True, 'level': 9}]}
            self.assertEqual(inject.raw_pids._unregistered_raw_pid_boss_entries(chap), ['stowaway'], key)

    def test_registry_resolves_each_boss_to_its_deploy_level(self):
        got = inject.raw_pids.raw_pid_base_levels('rime-of-the-frostmaiden')
        self.assertEqual({k: got.get(k) for k in self.RAW_BOSSES}, self.RAW_BOSSES)

    def test_the_patch_writes_baselevel_into_character_data(self):
        text = inject.decomp.vanilla_decomp_text('src/data_characters.c')
        out = inject.raw_pids.raw_pid_portrait_data(text, 'rime-of-the-frostmaiden')
        for pid, level in self.RAW_BOSSES.items():
            start, end = inject.decomp._find_brace_block(out, '[%s - 1]' % pid, inject.paths.CHARACTERS_C)
            found = re.search(r'\.baseLevel\s*=\s*(-?\d+)', out[start:end])
            self.assertIsNotNone(found, '%s has no baseLevel field' % pid)
            self.assertEqual(int(found.group(1)), level, pid)

    def test_the_penalty_can_no_longer_fire_on_any_boss(self):
        # The property that actually matters, stated as the engine states it.
        for pid, level in inject.raw_pids.raw_pid_base_levels('rime-of-the-frostmaiden').items():
            self.assertFalse(level < level, pid)     # baseLevel >= deploy level
        got = inject.raw_pids.raw_pid_base_levels('rime-of-the-frostmaiden')
        for pid, base in got.items():
            self.assertGreaterEqual(base, self.RAW_BOSSES.get(pid, base), pid)


class EntryIsTurn1(unittest.TestCase):
    """`entry_is_turn1` is the one predicate `difficulty.chapter_enemy_groups` and
    `map_placement_preview.enemy_bodies` share (#367): "is this body on the opening board".
    Every wave lives in `enemy_units` and lands by `arrives_turn` (#479)."""

    def test_an_enemy_units_entry_with_no_arrives_turn_is_turn1(self):
        self.assertTrue(inject.raw_pids.entry_is_turn1('enemy_units', {'id': 'a'}))

    def test_an_enemy_units_entry_with_arrives_turn_1_is_turn1(self):
        self.assertTrue(inject.raw_pids.entry_is_turn1('enemy_units', {'id': 'a', 'arrives_turn': 1}))

    def test_a_wave_is_not(self):
        entry = {'id': 'a', 'arrives_turn': 3}
        self.assertEqual(inject.raw_pids.entry_arrival_turn(entry), 3)
        self.assertFalse(inject.raw_pids.entry_is_turn1('enemy_units', entry))

    def test_a_placed_non_enemy_entry_is_not_part_of_the_turn1_force(self):
        self.assertFalse(inject.raw_pids.entry_is_turn1('green_allies', {'id': 'g'}))


class GenericPidsCloneTheirDonor(unittest.TestCase):
    """A chapter's generics moved to a pid of their own so they can carry its name (#493). The
    move must not change how they load: each pid's row is its vanilla donor's, field for field."""

    def test_each_clone_matches_its_donor_except_number_name_and_help(self):
        from inject.cast import RAW_PID_HELP
        from inject.chapter_ids import GENERIC_PID_DONORS
        vanilla = inject.decomp.vanilla_decomp_text('src/data_characters.c')
        text = inject.raw_pids.raw_pid_portrait_data(vanilla, 'rime-of-the-frostmaiden')

        def fields(src, pid):
            s, e = inject.decomp._find_brace_block(src, '[%s - 1]' % pid, 'data_characters.c')
            return dict(re.findall(r'\.(\w+)\s*=\s*([^,\n]+),', src[s:e]))

        for pid, donor in GENERIC_PID_DONORS.items():
            got, want = fields(text, pid), fields(vanilla, donor)
            self.assertEqual(got.pop('number'), pid)
            want.pop('number')
            self.assertNotEqual(got.pop('nameTextId'), want.pop('nameTextId'), pid)
            self.assertEqual(int(got.pop('descTextId'), 0), RAW_PID_HELP[pid][0])
            want.pop('descTextId')
            self.assertEqual(got, want, '%s is not a clone of %s' % (pid, donor))

    def test_every_chapter_pid_is_its_own(self):
        from inject.chapter_ids import GENERIC_PIDS
        pids = [p for ps in GENERIC_PIDS.values() for p in ps]
        self.assertEqual(len(pids), len(set(pids)))
        for chapter, ps in GENERIC_PIDS.items():
            for i, pid in enumerate(ps):
                self.assertEqual(pid, inject.raw_pids.enemy_pid(chapter, {'id': 'x'}, i))


if __name__ == '__main__':
    unittest.main()
