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

    RAW_BOSSES = {'0xb7': 12, '0xb6': 3, '0xb8': 7, '0xb9': 6}

    def test_every_raw_pid_boss_is_registered(self):
        missing = inject.raw_pids.unregistered_raw_pid_bosses('rime-of-the-frostmaiden')
        self.assertEqual(missing, [],
                         'raw-pid boss(es) with no RAW_PID_LEVEL_SOURCES row: %s' % missing)

    def test_the_registry_READER_sees_every_roster_key_too(self):
        # otherwise the guard has no reachable green state: a raw-pid boss under
        # `reinforcements:` is flagged as unregistered, and adding the row that silences it
        # makes the reader sys.exit("does not exist") and kills the build.
        chap = {'reinforcements': [{'id': 'stowaway', 'is_boss': True, 'level': 9}]}
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
    `map_placement_preview.enemy_bodies` must now share (#367): both readers ask "is this
    body on the opening board", and both got it wrong by testing `arrives_turn` alone --
    which is absent, and therefore falsy, on a `reinforcements:`/`enemy_reinforcements:`
    entry that carries `trigger_turn` instead. The KEY is what makes an entry a
    reinforcement; `arrives_turn` only refines `enemy_units` itself (ch06's Difficult-only
    wave stays inside `enemy_units` for exactly this reason)."""

    def test_an_enemy_units_entry_with_no_arrives_turn_is_turn1(self):
        self.assertTrue(inject.raw_pids.entry_is_turn1('enemy_units', {'id': 'a'}))

    def test_an_enemy_units_entry_with_arrives_turn_1_is_turn1(self):
        self.assertTrue(inject.raw_pids.entry_is_turn1('enemy_units', {'id': 'a', 'arrives_turn': 1}))

    def test_an_enemy_units_entry_with_arrives_turn_above_1_is_not(self):
        self.assertFalse(inject.raw_pids.entry_is_turn1('enemy_units', {'id': 'a', 'arrives_turn': 4}))

    def test_a_reinforcements_key_entry_is_never_turn1_even_with_no_arrives_turn(self):
        # The exact shape of the bug: ch02's `rear-raiders` carries `trigger_turn`, not
        # `arrives_turn`, so `entry.get('arrives_turn')` alone reads it as turn-1.
        self.assertFalse(inject.raw_pids.entry_is_turn1('reinforcements',
                                           {'id': 'rear-raiders', 'trigger_turn': 3}))

    def test_an_enemy_reinforcements_key_entry_is_never_turn1_either(self):
        self.assertFalse(inject.raw_pids.entry_is_turn1('enemy_reinforcements', {'id': 'w'}))


if __name__ == '__main__':
    unittest.main()
