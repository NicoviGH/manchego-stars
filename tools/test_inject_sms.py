#!/usr/bin/env python3
"""Tests for tools/inject/sms.py.

Run:  python3 tools/test_inject_sms.py
"""
import os
import re
import shutil
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from inject.namespace import stubbed
import inject.decomp
import inject.paths
import inject.sms
from inject import source as injector  # the injector's source, every file of it (#389)

# Read the COMMITTED decomp, not the working tree -- the build overwrites donor portrait
# slots (Gilliam/Neimi/Moulder/Vanessa), so a working-tree read would be non-hermetic.
VANILLA = inject.decomp.vanilla_decomp_text('src/data_characters.c')


class SmsFreeListReclaimsDeadVanillaRows(unittest.TestCase):
    """We assign map sprites per CHARACTER where vanilla assigns them per CLASS, so every
    custom cast member needs its own wait row. That is the design. What was NOT the design
    is that CUSTOM_SMS_BASE only ever appended, leaving ~71 vanilla rows -- classes this
    campaign can never field, even after promotions -- sitting unused below it while we ran
    into the engine's 127 ceiling (#227, follow-up to #225).

    The dangerous part of reclaiming is that "unused" is not the same as "unreferenced":
    src/bmudisp.c renders ballista/trap sprites by LITERAL id, with no class involved.
    """
    CAMPAIGN = 'rime-of-the-frostmaiden'

    def test_the_trap_rendered_rows_are_reserved(self):
        """RenderUnitSprites passes 0x5B/0x5C/0x5D (ballista traps, by trap->extra) and
        0x66 (trap type 0xD) as literal SMS ids. No class points at them, so a class-only
        reachability scan calls them free -- and reusing one renders a PC on any map with
        a ballista. This is the #218 failure shape, so it is pinned here."""
        for literal in (0x5B, 0x5C, 0x5D, 0x66):
            self.assertIn(literal, inject.sms.SMS_RESERVED_IDS,
                          'SMS id 0x%02X is rendered by literal id in bmudisp.c' % literal)
        self.assertEqual(inject.sms.SMS_RESERVED_IDS & inject.sms.sms_free_rows(self.CAMPAIGN), set(),
                         'a reserved trap row was handed out as free')

    def test_the_reserved_literals_still_exist_in_the_decomp(self):
        """If a decomp bump changes which ids bmudisp renders by literal, the reservation
        list is stale and silently wrong -- so it is checked against HEAD, not trusted."""
        text = inject.decomp.vanilla_decomp_text('src/bmudisp.c')
        found = {int(m, 16) for m in
                 re.findall(r'(?:UseUnitSprite|GetInfo)\(0x([0-9A-Fa-f]+)\)', text)}
        self.assertEqual(found, inject.sms.SMS_RESERVED_IDS,
                         'bmudisp.c literal SMS ids changed: %s vs reserved %s'
                         % (sorted(found), sorted(inject.sms.SMS_RESERVED_IDS)))

    def test_a_class_we_field_is_never_free(self):
        """The whole safety property: no row reachable by a class this campaign can field
        may be reused."""
        free = inject.sms.sms_free_rows(self.CAMPAIGN)
        reachable = inject.sms.sms_reachable_rows(self.CAMPAIGN)
        self.assertEqual(free & reachable, set(),
                         'these rows are both free and reachable: %s'
                         % sorted(free & reachable))

    def test_both_promotion_branches_are_followed(self):
        """FE8 lets the player pick EITHER branch (gPromoJidLut[][2]). ClassData.promotion
        names only one, and following it alone missed Bishop, Ranger, Rogue, Summoner and
        Wyvern Knight (F) -- rows a PC can promote into (Nicolas, 2026-08-05)."""
        reachable = inject.sms.sms_reachable_rows(self.CAMPAIGN)
        for second_branch in ('CLASS_SWORDMASTER', 'CLASS_BISHOP', 'CLASS_RANGER',
                              'CLASS_ROGUE', 'CLASS_SUMMONER'):
            self.assertTrue(inject.sms.sms_rows_for_classes([second_branch]) <= reachable,
                            '%s is a reachable promotion branch; its row must not be free'
                            % second_branch)

    def test_the_whole_player_class_tree_is_reserved_not_just_todays_roster(self):
        """The roster is NOT final -- there are characters we have not written yet, so a
        row that looks dead today can belong to a future recruit's class. Reserve every
        class a player unit could ever hold or become, not merely the ones in YAML now."""
        reachable = inject.sms.sms_reachable_rows(self.CAMPAIGN)
        # Classes no current PC holds, from branches of the tree we do not field.
        for unfielded in ('CLASS_WYVERN_RIDER', 'CLASS_TROUBADOUR', 'CLASS_MONK',
                          'CLASS_JOURNEYMAN', 'CLASS_PUPIL'):
            self.assertTrue(inject.sms.sms_rows_for_classes([unfielded]) <= reachable,
                            '%s is player-holdable; reserve it against a future recruit'
                            % unfielded)

    def test_hand_reserved_classes_are_never_free(self):
        """Things no computation can infer: a bard/dancer recruit we have not written, and
        Frostmaiden's white dragon."""
        free = inject.sms.sms_free_rows(self.CAMPAIGN)
        self.assertEqual(inject.sms.sms_rows_for_classes(inject.sms.SMS_RESERVED_CLASSES) & free, set())

    def test_a_declared_art_donor_is_never_free(self):
        """Donors are named by SHEET (art.map_sprite.base: 'Cyclops'), so the CLASS_ token
        scan misses them -- and naming a vanilla class as a donor is a fair signal we might
        field it too."""
        donors = inject.sms._declared_donor_bases(self.CAMPAIGN)
        self.assertIn('Cyclops', donors, 'fixture check: a donor base is declared')
        free = inject.sms.sms_free_rows(self.CAMPAIGN)
        self.assertEqual(inject.sms.sms_rows_for_classes(
            {'CLASS_' + d.upper() for d in donors}) & free, set())

    def test_reclaiming_actually_buys_us_room(self):
        """The point of the exercise. Before #227 we had 2 ids of headroom, and the
        conservative policy still has to beat that by an order of magnitude."""
        self.assertGreater(len(inject.sms.sms_free_rows(self.CAMPAIGN)), 12,
                           'conservative reclaim should still free well over a dozen rows')

    def test_the_free_list_is_computed_not_hardcoded(self):
        body = injector.def_source('sms_free_rows')
        self.assertIn('sms_reachable_rows(', body,
                      'derive the free list from live reachability every build')
        self.assertNotRegex(body, r'\[\s*\d+\s*,\s*\d+\s*,\s*\d+',
                            'no hardcoded row list -- recompute it')

    def test_allocation_prefers_free_rows_then_appends(self):
        """Free rows first (they are the point), append as the fallback, and #225's
        ceiling guard still owns the append path."""
        free = sorted(inject.sms.sms_free_rows(self.CAMPAIGN))
        got = inject.sms.allocate_sms_ids(self.CAMPAIGN, len(free) + 3)
        self.assertEqual(got[:len(free)], free, 'free rows must be spent first, in order')
        for extra in got[len(free):]:
            self.assertGreaterEqual(extra, inject.sms.CUSTOM_SMS_BASE,
                                    'overflow past the free list must append, not wrap')
        self.assertEqual(len(set(got)), len(got), 'allocation handed out a duplicate id')

    def test_allocation_never_exceeds_the_engine_ceiling(self):
        with self.assertRaises(SystemExit):
            inject.sms.allocate_sms_ids(self.CAMPAIGN, 400)


class CustomSmsIdsStayUnderTheEngineMask(unittest.TestCase):
    """FE8 looks up a map sprite's geometry through a MASKED index:

        #define GetInfo(id) (unit_icon_wait_table[(id) & ((1<<7)-1)])

    so an SMS id >= 128 silently reads a VANILLA row -- id 128 draws Ephraim Lord's
    sheet at Ephraim Lord's size class. It does not crash and it does not warn: the
    unit just renders as somebody else. The mask is NOT the array bound either
    (gUnitSpriteSlots is u8[0xD0] and ids 128-207 are valid slot-cache indices), which
    is exactly why nothing else catches it (#225).

    Our custom ids start at CUSTOM_SMS_BASE = 107, so the budget is small and finite.
    """

    def test_the_limit_is_read_from_the_decomp_not_hardcoded(self):
        """Ground the ceiling in the engine that enforces it -- if a decomp bump widens
        or narrows the mask, the guard must follow it rather than assert a stale 127."""
        self.assertEqual(inject.sms._sms_id_mask_bits(), 7)
        self.assertEqual(inject.sms.sms_id_max(), 127)

    def test_the_mask_read_fails_loudly_if_the_define_moves(self):
        body = injector.def_source('_sms_id_mask_bits')
        self.assertIn('sys.exit', body)
        self.assertIn('vanilla_decomp_text', body,
                      'read the mask from HEAD -- the working tree is our own artifact')

    def test_every_wait_table_append_goes_through_the_guarded_helper(self):
        """A new sprite pass must not be able to append a row unguarded. The choke point
        is _append_wait_rows; nothing else may append to unit_icon_wait_table[]."""
        src = injector.injector_source()
        self.assertNotIn('_append_table_rows(UNIT_ICON_WAIT_C', src,
                         'wait rows are placed by _write_wait_row, never blind-appended')
        self.assertGreaterEqual(src.count('_write_wait_row('), 6,
                                'all five sprite passes + the definition')

    def _table(self, tmp, nrows):
        path = os.path.join(tmp, 'unit_icon_wait_data.c')
        rows = ''.join('\t{0, UNIT_ICON_SIZE_16x16, sheet_%d},\n' % i for i in range(nrows))
        with open(path, 'w', encoding='utf-8') as f:
            f.write('UnitIconWait unit_icon_wait_table[] = {\n%s};\n' % rows)
        return path

    def test_the_guard_rejects_a_row_past_the_mask(self):
        """The regression: overflowing must fail the BUILD, naming the id, rather than
        shipping a sprite that renders as a vanilla class."""
        tmp = tempfile.mkdtemp()
        try:
            path = self._table(tmp, 128)                     # ids 0..127: exactly full
            with stubbed('UNIT_ICON_WAIT_C', path):
                self.assertEqual(inject.sms._wait_table_len(), 128)
                with self.assertRaises(SystemExit) as cm:
                    inject.sms._write_wait_row(128, '\t{0, UNIT_ICON_SIZE_16x16, x}, // 128 basil')
            msg = str(cm.exception)
            self.assertIn('128', msg, 'name the overflowing id')
            self.assertIn('127', msg, 'state the ceiling')
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_the_guard_allows_the_last_usable_id(self):
        """127 is usable -- an off-by-one here would cost us a sprite we own."""
        tmp = tempfile.mkdtemp()
        try:
            with stubbed('UNIT_ICON_WAIT_C', self._table(tmp, 127)):
                inject.sms._write_wait_row(127, '\t{0, UNIT_ICON_SIZE_16x16, x}, // 127 sahnar')
                self.assertEqual(inject.sms._wait_table_len(), 128)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_a_row_that_would_land_off_its_own_id_is_rejected(self):
        """The id/row desync #227 closes: an appended row must land at exactly the index
        its id names, or every later unit renders its neighbour's sheet."""
        tmp = tempfile.mkdtemp()
        try:
            with stubbed('UNIT_ICON_WAIT_C', self._table(tmp, 50)):
                with self.assertRaises(SystemExit) as cm:
                    inject.sms._write_wait_row(60, '\t{0, UNIT_ICON_SIZE_16x16, x}, // 60 gap')
            self.assertIn('desync', str(cm.exception))
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_a_reclaimed_row_is_replaced_in_place_not_appended(self):
        """Reclaiming means overwriting the dead vanilla row, leaving the table length
        unchanged -- if it appended instead, the id would name the wrong index."""
        tmp = tempfile.mkdtemp()
        try:
            with stubbed('UNIT_ICON_WAIT_C', self._table(tmp, 107)) as path:
                inject.sms._write_wait_row(48, '\t{0, UNIT_ICON_SIZE_16x16, mine}, // 48 braulo')
                self.assertEqual(inject.sms._wait_table_len(), 107, 'table length must not grow')
                with open(inject.paths.UNIT_ICON_WAIT_C, encoding='utf-8') as f:
                    body = [ln for ln in f.read().splitlines() if ln.lstrip().startswith('{')]
                self.assertIn('braulo', body[48], 'row 48 must hold the new sprite')
                self.assertIn('sheet_47', body[47], 'its neighbours must be untouched')
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_the_remaining_headroom_is_reported_while_it_is_still_cheap_to_act_on(self):
        """Running low is worth knowing BEFORE the build that runs out, so the allocator
        reports what is left and says so loudly when it is nearly gone."""
        body = injector.def_source('sms_alloc_report')
        self.assertIn('SMS_ID_LOW_WATER', body)
        self.assertIn('print(', body, 'report the headroom, do not only enforce it')


if __name__ == '__main__':
    unittest.main()
