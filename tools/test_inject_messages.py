#!/usr/bin/env python3
"""Tests for tools/inject/messages.py.

Run:  python3 tools/test_inject_messages.py
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from inject.namespace import injector_constants
import build_campaign as bc
import inject.cast
import inject.chapter_ids
import inject.chapters.ch04
import inject.death_quotes
import inject.messages
from inject import source as injector  # the injector's source, every file of it (#389)


class MessageBlockGuardSeesEveryClaimedId(unittest.TestCase):
    """The deadness guard must not depend on a constant's NAME (review finding on #338).

    `injector_message_ids` finds ids by scanning globals whose name ends in `_MSG`/`_MSGS`,
    and its docstring promises "registering a new one is enough -- there is no second list to
    remember". That is false for an id held in a constant named anything else: ch02's two hut
    visits live in `CH02_VILLAGE_SLOTS`, so 0xAC0/0xAC1 were invisible to it. They are
    registered in HOSTED_CHAPTER_MESSAGE_IDS, which IS the authoritative list of what we
    spend -- so the guard should read that too, and stop depending on a naming convention
    nothing enforces.
    """

    def test_an_id_claimed_only_through_a_non_msg_constant_is_still_protected(self):
        # ch02's hut-visit ids come from CH02_VILLAGE_SLOTS, not a *_MSG constant.
        hut_ids = [slot[1] for slot in inject.chapter_ids.CH02_VILLAGE_SLOTS.values()]
        self.assertTrue(hut_ids)
        # A DIFFERENT chapter drawing a block over them must be refused.
        blocks = {'ch09': ((min(hut_ids), max(hut_ids)),)}
        bad = inject.messages.live_ids_in_declared_blocks(blocks=blocks)
        self.assertTrue(bad, 'a block over ch02\'s claimed hut ids must be refused, but the '
                             'guard only saw *_MSG constants')

    def test_a_chapter_may_still_declare_a_block_over_its_own_claims(self):
        # The whole point of a block is to hold the ids that chapter spends.
        self.assertEqual(inject.messages.live_ids_in_declared_blocks(
            blocks={'ch02': inject.messages.message_block_ranges('ch02')}), [])


class MessageBlockGuardHasNoBlindSpots(unittest.TestCase):
    """Code-review findings on #338: two more classes of id the guard could not see.

    Both are the SAME failure as the one 17c266a fixed -- a block drawn over them builds
    clean, ships, and replaces live text -- and both slipped through because the scan was
    shaped by how a constant is written rather than by what the build writes.
    """

    def _spent(self):
        return inject.messages.injector_message_ids()

    def test_ids_held_in_a_dict_are_seen(self):
        # PC_DEATH_QUOTE_MSGS is a DICT whose name does end in _MSGS, so its author followed
        # the convention exactly -- and the flattener wrapped it as `(the_dict,)`, dropping
        # all 13 ids. A block over them would have swapped a PC's death quote for other prose.
        ids = sorted(v for v in inject.death_quotes.PC_DEATH_QUOTE_MSGS.values() if isinstance(v, int))
        self.assertTrue(ids)
        spent = self._spent()
        missing = [hex(i) for i in ids if i not in spent]
        self.assertEqual([], missing, 'death-quote ids invisible to the guard')

    def test_a_block_over_the_death_quotes_is_refused(self):
        lo = min(v for v in inject.death_quotes.PC_DEATH_QUOTE_MSGS.values() if isinstance(v, int))
        self.assertTrue(inject.messages.live_ids_in_declared_blocks(blocks={'zz': ((lo, lo),)}))

    def test_goal_ids_below_the_old_floor_are_seen(self):
        # Every chapter's objective window/status string lives below 0x300, which an
        # undocumented lower bound silently excluded -- from the claims fold too, so
        # registering them did not help. A block there garbles the objective on every chapter.
        goals = [v for v in injector_constants('(GOAL_WINDOW_MSG|GOAL_STATUS_MSG)$').values()
                 if isinstance(v, int)]
        self.assertTrue(goals)
        spent = self._spent()
        self.assertEqual([], [hex(i) for i in goals if i not in spent])

    def test_a_block_over_the_goal_strings_is_refused(self):
        self.assertTrue(inject.messages.live_ids_in_declared_blocks(blocks={'zz': ((0x19D, 0x1A7),)}))

    def test_the_build_refuses_a_block_over_a_spent_id(self):
        # The guard's two siblings run in main() before any injector; this one ran only from
        # the tests, so a plain `make` with an edited block table still produced a ROM.
        main = injector.def_source('main')
        self.assertIn('live_ids_in_declared_blocks()', main,
                      'the deadness guard must run in the build, like its siblings')


class MessageBlockPool(unittest.TestCase):
    """A hosted chapter may declare MORE THAN ONE id range, and every range it declares must
    be genuinely dead.

    The original rule -- "take the dead block of the slot you displace" -- was safe without
    analysis, because blanking slot N's events kills slot N's text references. It also caps
    every chapter at whatever that one vanilla chapter happened to spend: ch05 hit 0 free at
    18 ids while 528 ids belonging to chapters we never ship sat unclaimed in runs up to 48.
    Widening is only safe if "this range is dead" is CHECKED, which is what these do.
    """

    def test_a_chapter_may_declare_several_ranges(self):
        ranges = inject.messages.message_block_ranges('ch05')
        self.assertGreater(len(ranges), 1)
        self.assertIn((0x9E4, 0x9F5), ranges)      # its original block, ids unmoved

    def test_capacity_sums_every_range(self):
        self.assertEqual(sum(hi - lo + 1 for lo, hi in inject.messages.message_block_ranges('ch05')),
                         inject.messages.message_block_capacity('ch05'))

    def test_overlap_is_refused_across_ranges_not_just_blocks(self):
        with self.assertRaises(SystemExit):
            inject.messages.assert_message_blocks_disjoint(
                {'a': ((0x100, 0x110), (0x300, 0x310)),
                 'b': ((0x200, 0x210), (0x305, 0x320))})

    def test_a_chapter_overlapping_ITSELF_is_refused(self):
        # Two ranges on one chapter double-count its own headroom, which reads as free space
        # that is not there.
        with self.assertRaises(SystemExit):
            inject.messages.assert_message_blocks_disjoint({'a': ((0x100, 0x110), (0x108, 0x120))})

    def test_no_declared_block_is_drawn_over_an_id_the_build_already_spends(self):
        """The guard that makes widening safe. Vanilla's references to a slot we host die
        when we blank that slot's events -- but ids we REPURPOSED are alive and no longer
        look like what they were."""
        self.assertEqual([], inject.messages.live_ids_in_declared_blocks())

    def test_the_guard_catches_a_range_drawn_over_a_repurposed_id(self):
        """0x969 was vanilla Ch2's first village text and is now a lord-select blurb. A
        block over it would build clean and garble a scene in play."""
        self.assertIn(0x969, inject.messages.injector_message_ids())
        offenders = inject.messages.live_ids_in_declared_blocks({'bogus': ((0x969, 0x96C),)})
        self.assertTrue(any('0x969' in o for o in offenders), offenders)

    def test_a_chapter_s_OWN_claims_inside_its_block_are_not_offenders(self):
        """Same range as the test above -- the only difference is that the chapter claims
        those ids, which is what a block is FOR. Without this carve-out every chapter would
        report its own scenes as collisions."""
        self.assertEqual([], inject.messages.live_ids_in_declared_blocks(
            {'bogus': ((0x969, 0x96C),)},
            claims={'bogus': (0x969, 0x96A, 0x96B, 0x96C)}))


class NamedRawPidsAreExclusive(unittest.TestCase):
    """A raw pid carrying a NAME PLATE may be claimed by one chapter only.

    `RAW_PID_PORTRAITS` writes nameTextId into gCharacterData[pid - 1], one row per pid with no
    chapter dimension -- unlike gDefeatTalkList, where ch03's grell and ch04's mogall share 0xb7
    legally because each entry is keyed by chapter too. ch06's boats took 0xb4/0xb5, already
    CH04_PACK_PIDS', and two of ch04's five Mauthe Doogs would have read "Fishing Boat".
    """

    def test_the_live_registry_is_clean(self):
        inject.messages.assert_named_raw_pids_are_exclusive()

    def test_a_generic_pid_may_still_be_shared(self):
        """ch05 and ch06 both spend 0x80 on autolevelled trash, and that is fine -- a generic pid
        is never named, so nothing global is written for it. The guard must not over-reach."""
        claims = inject.messages.raw_pid_claims()
        self.assertEqual(claims.get('0x80'), {'CH05', 'CH06'})
        self.assertNotIn('0x80', inject.cast.RAW_PID_PORTRAITS)

    def test_discovery_reads_strings_tuples_and_dicts(self):
        claims = inject.messages.raw_pid_claims()
        self.assertEqual(claims.get('0xb8'), {'CH05'})            # CH05_BOSS_PID, a bare string
        for pid in inject.chapters.ch04.CH04_PACK_PIDS:                             # a tuple
            self.assertIn('CH04', claims.get(pid, set()), pid)
        for pid in inject.chapter_ids.CH06_BOAT_PIDS.values():                    # a dict
            self.assertEqual(claims.get(pid), {'CH06'}, pid)

    def test_the_original_collision_is_caught(self):
        portraits = dict(inject.cast.RAW_PID_PORTRAITS)
        for pid in inject.chapter_ids.CH06_BOAT_PIDS.values():
            portraits.pop(pid, None)
        portraits['0xb4'] = ('boat-east', 0xD4D, None, 'Fishing Boat')
        scope = dict(injector_constants(inject.messages._RAW_PID_CONST_RE.pattern),
                     CH06_BOAT_PIDS={'boat-east': '0xb4', 'boat-west': '0xb5'})
        with self.assertRaises(SystemExit) as caught:
            inject.messages.assert_named_raw_pids_are_exclusive(portraits, scope)
        self.assertIn('0xb4', str(caught.exception))
        self.assertIn('CH04', str(caught.exception))


if __name__ == '__main__':
    unittest.main()
