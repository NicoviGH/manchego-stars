#!/usr/bin/env python3
"""Tests for tools/inject/chapters/ch06.py.

Run:  python3 tools/test_inject_ch06.py
"""
import os
import re
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import inject.cast
import inject.chapter_ids
import inject.chapters.ch06
import inject.map_sprites
import inject.recruit
import inject.decomp
import inject.hosting
import inject.units
from inject import source as injector  # the injector's source, every file of it (#389)


class ItemDropIsCarriedOnce(unittest.TestCase):
    """FE8 drops the LAST item, and a chapter YAML may name the drop in `inventory:` too.

    ch06 is the first chapter whose data spells it both ways; appending unconditionally emitted a
    second copy on three units while `make difficulty` still read PARITY, because the parity model
    prices the YAML rather than the rows the injector emits.
    """

    CAMPAIGN = 'rime-of-the-frostmaiden'

    def test_a_drop_already_in_inventory_is_not_duplicated(self):
        self.assertEqual(inject.units._items_with_drop_last(['A', 'B'], 'B'), ['A', 'B'])

    def test_a_drop_absent_from_inventory_is_appended(self):
        self.assertEqual(inject.units._items_with_drop_last(['A'], 'B'), ['A', 'B'])

    def test_a_drop_listed_first_is_moved_LAST(self):
        # De-duplicating alone would leave the engine dropping the wrong item.
        self.assertEqual(inject.units._items_with_drop_last(['B', 'A'], 'B'), ['A', 'B'])

    def test_no_ch06_enemy_carries_a_duplicate(self):
        chap = inject.hosting._load_chapter_yaml(self.CAMPAIGN, inject.chapters.ch06.CH06_CHAPTER_YAML)
        rows = inject.chapters.ch06.ch06_enemy_rows(chap) + inject.chapters.ch06.ch06_enemy_rows(
            chap, arrives_turn=inject.chapters.ch06.CH06_HARD_WAVE_TURN)
        for row in rows:
            items = re.search(r'\.items = \{ (.*?) \}', row).group(1).split(', ')
            items = [i for i in items if i != '0']
            self.assertEqual(len(items), len(set(items)), row)

    def test_every_dropper_matches_its_vanilla_donors_item_count(self):
        """The check that would have caught it: our row against the donor unit it is derived
        from. Vanilla's three ch06 droppers carry 2 / 1 / 2 items; ADR 0329's re-classed
        Mercenary carries one more, the Steel Lance it now fights with, ahead of the drop."""
        chap = inject.hosting._load_chapter_yaml(self.CAMPAIGN, inject.chapters.ch06.CH06_CHAPTER_YAML)
        expected = {'shark-rider-halberd': 2, 'merfolk-trident-drop': 2, 'lamia-mender': 2}
        rows = inject.chapters.ch06.ch06_enemy_rows(chap)
        for enemy_id, count in expected.items():
            row = next(r for r in rows if '/* %s --' % enemy_id in r)
            items = re.search(r'\.items = \{ (.*?) \}', row).group(1).split(', ')
            self.assertEqual(len(items), count, '%s: %s' % (enemy_id, row))
            self.assertIn('.itemDrop = 1', row, enemy_id)


class MessieWearsHisOwnArt(unittest.TestCase):
    """Messie is a cutscene actor, not cast, so `classed_cast` never sees him. He rides the
    scripted-neutral path the white moose does: a raw pid of his own, wearing his own sheet."""

    CAMPAIGN = 'rime-of-the-frostmaiden'

    def test_his_pid_wears_his_map_sprite(self):
        inject.recruit.assert_custom_art_pid_wired(inject.chapter_ids.CH06_MESSIE_PID, 'messie', 'test')

    def test_his_pid_is_named_messie_and_wears_the_syrene_bust(self):
        """Read Syrene's portraitId out of the decomp, never a literal: the bust the build
        dresses is Syrene's slot, so his on-map unit must point at that same face."""
        unit_id, slot, portrait_id, name = inject.cast.RAW_PID_PORTRAITS[
            inject.chapter_ids.CH06_MESSIE_PID]
        self.assertEqual(('messie', 'Messie'), (unit_id, name))
        self.assertEqual(inject.cast.GUEST_PORTRAIT_MAP['messie'], slot)
        src = open(os.path.join(inject.decomp.REPO, 'fireemblem8u', 'src', 'data_characters.c'),
                   encoding='utf-8').read()
        row = src[src.index('[CHARACTER_SYRENE - 1]'):]
        row = row[:row.index('},')]
        self.assertEqual(int(re.search(r'\.portraitId = (0x[0-9a-fA-F]+)', row).group(1), 16),
                         portrait_id)

    def test_the_build_guard_sees_his_declared_art(self):
        """A cutscene actor's `art.map_sprite` block is in scope of the "declared art must be
        wired" guard, or his sheet could fall out of the tables and nothing would say so."""
        declared = inject.map_sprites.declared_map_sprite_units(self.CAMPAIGN)
        self.assertIn('messie', declared)

    def test_a_neutral_with_no_committed_walk_gets_the_glide(self):
        """Messie hauls himself onto the ice, so he moves; a neutral with no hand-drawn walk
        sheet glides on its idle the way the cast do, instead of failing the build."""
        body = injector.def_source('_inject_scripted_neutral_sprites')
        self.assertIn('synth_mu_sheet', body)


if __name__ == '__main__':
    unittest.main()
