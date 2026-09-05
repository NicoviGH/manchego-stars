#!/usr/bin/env python3
"""`make chapter chNN` -- declared-vs-built status, derived and never hand-kept (#312).

49% of ch05's commits touched only `docs/` or `HANDOFF.md`: a human writing down state the
repo already knows. Every number this reports has exactly one source, and these tests pin
which source, because a status report that drifts is worse than no status report.

Run: python3 tools/test_chapter_status.py
"""
import os
import sys
import re
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import chapter_status as cs


class FindingAChapter(unittest.TestCase):
    def test_a_short_id_resolves_to_the_chapter_yaml(self):
        """`make chapter CH=ch06` names a chapter the way every other tool here does."""
        self.assertEqual('ch06-the-maer-monster', cs.load('ch06')['id'])

    def test_an_unknown_chapter_says_which_ones_exist(self):
        with self.assertRaises(KeyError) as caught:
            cs.load('ch99')
        self.assertIn('ch05', str(caught.exception))


class Scenes(unittest.TestCase):
    """Declared vs built, per scene. The distinction #312 exists to make."""

    def test_a_declared_scene_reports_its_authored_box_count(self):
        row = next(r for r in cs.scenes('ch05') if r.slot == 'vanilla 0x9BB')
        self.assertTrue(row.declared)
        self.assertEqual(19, row.boxes)

    def test_a_planned_chapter_declares_events_with_no_script_yet(self):
        """ch06's four events are seeds -- named beats with nothing written. That IS the
        status, and reporting it is the point: 'declared but unbuilt' is the row a human
        used to keep in HANDOFF by hand."""
        rows = cs.scenes('ch06')
        self.assertTrue(rows)
        self.assertFalse(any(r.declared for r in rows))
        self.assertTrue(all(r.boxes == 0 for r in rows))

    def test_a_previewable_scene_carries_its_real_A_press_count(self):
        """Presses come off the rendered body (#311), not off the authored box count -- so
        this row is the one place the two numbers can be compared at a glance."""
        row = next(r for r in cs.scenes('ch05') if r.slot == 'vanilla 0x9BB')
        self.assertEqual('ch05/1', row.preview)
        self.assertEqual(23, row.presses)
        self.assertNotEqual(row.boxes, row.presses)


class MessageIds(unittest.TestCase):
    """How much room a chapter has left, which is the number that decides whether the next
    scene costs an id or a redesign."""

    def test_ch05_claims_the_ids_the_ownership_registry_says_it_does(self):
        import build_campaign as bc
        room = cs.message_ids('ch05')
        self.assertEqual(set(bc.HOSTED_CHAPTER_MESSAGE_IDS['ch05']), set(room.claimed))

    def test_headroom_counts_only_ids_inside_the_chapter_s_own_host_block(self):
        """ch05 hosts on slot 6, so it owns vanilla Ch6's dead block -- NOT vanilla Ch5's,
        even though it is Ch5's 1:1 twin. It also WRITES ids outside that block (the four
        reliquary lines, the moose's appended name), and those are claims but not headroom:
        counting them as block usage would report the block as overfull."""
        room = cs.message_ids('ch05')
        inside = lambda m: any(lo <= m <= hi for lo, hi in room.block)
        self.assertTrue(all(inside(m) for m in room.used_in_block))
        self.assertTrue(any(not inside(m) for m in room.claimed))
        capacity = sum(hi - lo + 1 for lo, hi in room.block)
        self.assertEqual(capacity - len(room.used_in_block), room.free)

    def test_headroom_sums_across_every_declared_range(self):
        """ch05 spends its slot-6 block down to zero and draws the rest from the pool, so a
        reader that looked at only the first range would still call it FULL."""
        room = cs.message_ids('ch05')
        self.assertGreater(len(room.block), 1)
        self.assertGreater(room.free, 0)

    def test_two_chapters_may_not_declare_overlapping_blocks(self):
        """`assert_message_ids_unique` catches two chapters writing the same id. This catches
        the setup that makes that inevitable, before either has spent anything."""
        import build_campaign as bc
        self.assertTrue(bc.assert_message_blocks_disjoint())
        with self.assertRaises(SystemExit):
            bc.assert_message_blocks_disjoint({'a': ((0x100, 0x110),),
                                               'b': ((0x105, 0x120),)})

    def test_a_chapter_with_no_declared_block_says_so_rather_than_guessing(self):
        """ch01 predates the per-chapter block registry. Reporting 0 free would read as
        'full' when the truth is 'nobody wrote it down'."""
        self.assertIsNone(cs.message_ids('ch01').block)


class Art(unittest.TestCase):
    def test_ch05_s_named_units_are_the_ones_with_an_identity(self):
        """Bosses, minibosses and recruits -- not the generic line classes, which wear a
        chapter reskin rather than art of their own."""
        named = {r.unit for r in cs.art('ch05')}
        self.assertLessEqual({'ravisin', 'white-moose', 'sahnar', 'basil'}, named)
        self.assertNotIn('tomb-reaver', named)

    def test_a_finished_unit_reports_all_three_pieces(self):
        row = next(r for r in cs.art('ch05') if r.unit == 'ravisin')
        self.assertEqual((True, True, True), (row.portrait, row.map_sprite, row.battle_anim))
        self.assertEqual([], row.missing)

    def test_a_unit_with_no_art_at_all_lists_what_is_missing(self):
        """ch06's monster is named and unbuilt, which is the row that tells you what the next
        chapter still owes."""
        rows = cs.art('ch06')
        self.assertTrue(rows)
        self.assertTrue(any(r.missing for r in rows))


class Scenarios(unittest.TestCase):
    def test_a_chapter_lists_the_scenarios_that_cover_it(self):
        """`matrix.yaml` says which host chapter each scenario boots, so 'what proves ch05'
        is a lookup rather than something a human remembers."""
        names = {r.scenario for r in cs.scenarios('ch05')}
        self.assertIn('ch05recruit', names)
        self.assertNotIn('ch01', names)

    def test_a_scenario_with_no_cached_verdict_reports_unknown_not_a_failure(self):
        """An unrun scenario is not a failing one, and a report that blurs the two would
        push someone into a playtest run to find out -- the exact cost this is here to save."""
        rows = cs.scenarios('ch05', cache_dir=os.path.join(os.sep, 'nonexistent-cache'))
        self.assertTrue(rows)
        self.assertTrue(all(r.verdict is None for r in rows))


class LooseEnds(unittest.TestCase):
    def test_ch05_is_no_longer_out_of_message_ids(self):
        """It WAS full -- 0x9E4-0x9F5, all eighteen spent -- because the first allocation
        rule capped every chapter at whatever its host slot happened to spend. A second
        range from the never-shipped pool is what unblocks its next scene."""
        self.assertGreater(cs.message_ids('ch05').free, 0)
        self.assertFalse(any('block is full' in e for e in cs.loose_ends('ch05')))

    def test_a_planned_chapter_reports_its_unwritten_scenes_and_missing_art(self):
        ends = cs.loose_ends('ch06')
        self.assertTrue(any('no script yet' in e for e in ends))
        self.assertTrue(any('art' in e for e in ends))

    def test_a_finished_chapter_has_fewer_loose_ends_than_a_planned_one(self):
        self.assertLess(len(cs.loose_ends('ch05')), len(cs.loose_ends('ch06')))


class TheReport(unittest.TestCase):
    def test_a_record_scenario_is_not_reported_as_never_run(self):
        """The verdict cache only ever stores a PASS, and only for `kind: verdict`. A
        `record` scenario's output IS the picture, so it has no verdict to store -- printing
        'never run' beside twelve of them reads as a chapter in trouble when nothing is
        wrong."""
        text = cs.report('ch05')
        record = [r for r in cs.scenarios('ch05') if r.kind == 'record']
        self.assertTrue(record)
        for row in record:
            line = next(ln for ln in text.split('\n') if row.scenario in ln)
            self.assertNotIn('never run', line)

    def test_the_report_names_every_section(self):
        text = cs.report('ch05')
        for heading in ('chapter', 'scenes', 'message ids', 'art', 'scenarios'):
            self.assertIn(heading, text.lower(), heading)

    def test_the_report_renders_for_every_chapter_including_unbuilt_ones(self):
        """A status command that only works on finished chapters is useless for the one
        question it exists to answer: what does the NEXT chapter still owe."""
        for chapter in cs.load_all():
            short = chapter['id'].split('-')[0]
            self.assertIn(short, cs.report(short), short)

    @unittest.skipUnless(cs.event_group_census('ch05') is not None,
                         'the decomp is not injected -- the census reads what a build wrote')
    def test_the_census_row_reports_the_SAME_data_the_build_guard_rules_on(self):
        """#312 left this row pending #313. Now that the census exists, `make chapter` reports
        it and the build refuses it off ONE census -- two would be two answers."""
        from inject import event_group
        text = cs.report('ch05')
        self.assertIn('WRITTEN', text)
        self.assertEqual(event_group.census('ch05'), cs.event_group_census('ch05'))

    @unittest.skipUnless(cs.event_group_census('ch05') is not None,
                         'the decomp is not injected -- the census reads what a build wrote')
    def test_every_inherited_field_shown_carries_its_declared_reason(self):
        """An inherited field with no reason beside it is the silence this replaces."""
        for field, why in cs.inherited_reasons('ch05').items():
            self.assertNotEqual('UNRULED', why, field)


class DegradedModesMustSayCannotTell(unittest.TestCase):
    """Every optional import here has a fallback, and a fallback that reports a WRONG number
    is worse than one that reports none: the whole promise of this command is that its rows
    are true. Each of these silently lied."""

    def setUp(self):
        self._preview, self._bc = cs._preview_module, cs._build_campaign
        self.addCleanup(setattr, cs, '_preview_module', self._preview)
        self.addCleanup(setattr, cs, '_build_campaign', self._bc)
        cs._scenes_cache.clear()

    def tearDown(self):
        cs._scenes_cache.clear()

    def test_without_the_preview_module_scenes_are_unknown_not_unpreviewable(self):
        cs._preview_module = lambda: None
        self.assertFalse(any('cannot be previewed' in e for e in cs.loose_ends('ch05')))

    def test_without_build_campaign_a_full_block_is_not_reported_as_undeclared(self):
        """ch05's block is FULL. Rendering that as 'no host block declared' makes it
        indistinguishable from ch01, whose block genuinely was never written down."""
        cs._build_campaign = lambda: None
        text = cs.report('ch05')
        self.assertNotIn('no host block declared', text)
        self.assertIn('cannot tell', text)

    def test_without_build_campaign_box_counts_are_blank_rather_than_wrong(self):
        """Counting every script entry gives 20 where the truth is 19: stage directions are
        not boxes. A wrong number in the same column with no marker is the worst option."""
        cs._build_campaign = lambda: None
        row = next(r for r in cs.scenes('ch05') if r.slot == 'vanilla 0x9BB')
        self.assertIsNone(row.boxes)


class VerdictsThatCanOnlyEverBePasses(unittest.TestCase):
    def test_a_failed_scenario_is_not_reported_as_never_run(self):
        """`store_cached_verdict` writes a slot ONLY on PASS and clears the scenario's slots
        on a FAIL, so the cache can never say FAIL. Calling an empty slot 'never run' is
        exactly the unrun-vs-failing blur this is supposed to refuse -- the honest reading of
        an absent slot is 'no stored PASS'."""
        rows = cs.scenarios('ch05', cache_dir=os.path.join(os.sep, 'nonexistent-cache'))
        text = cs.report('ch05', cache_dir=os.path.join(os.sep, 'nonexistent-cache'))
        self.assertTrue(rows)
        self.assertNotIn('never run', text)
        self.assertIn('no stored PASS', text)


class CoverageComesFromTheMatrix(unittest.TestCase):
    def test_a_chapter_suite_names_the_scenarios_that_cover_its_chapter(self):
        """`host_chapter` is a BOOT HINT defaulting to 1, not an upper bound, so on a cold
        cache it misses every scenario that boots earlier and plays forward. ch02 has nine
        declared scenarios and reported none."""
        rows = cs.scenarios('ch02', cache_dir=os.path.join(os.sep, 'nonexistent-cache'))
        self.assertTrue(rows)
        self.assertNotIn('no playtest scenario covers this chapter',
                         cs.loose_ends('ch02'))

    def test_the_prologue_is_hosted_even_though_it_is_called_ch00(self):
        """The host registry calls it `prologue`; the YAML calls it ch00. Matching on the
        short id alone reported the prologue as unhosted, with two false loose ends."""
        self.assertIsNotNone(cs.host_slot('ch00'))
        self.assertEqual('Ch1Events', cs.event_group('ch00'))



class TestAiFidelity(unittest.TestCase):
    """#335 scope item 3: a chapter's AI fidelity is visible in `make chapter CH=chNN`,
    beside scenes and art, so nobody has to remember to look for it."""

    def test_every_enemy_reports_the_donor_it_borrows_its_ai_from(self):
        rows = cs.ai('ch02')
        self.assertTrue(rows, 'ch02 fields enemies, so it has AI to report')
        for row in rows:
            self.assertTrue(row.unit, 'every row names its unit')
            # The donor IS the answer to "where did this AI come from". A row without one
            # would be an authored pattern, which is what #335 removed.
            self.assertTrue(row.donor or row.override,
                            '%s reports neither a donor nor an override' % row.unit)

    def test_an_override_is_reported_with_its_reason(self):
        # ch00's O'Neill overrides his donor's DoNothing, because vanilla event-scripts his
        # attack and we run no such script. An override without its `why` is a silenced guard.
        rows = [r for r in cs.ai('ch00') if r.override]
        self.assertTrue(rows, 'ch00 has an ai_override')
        for row in rows:
            self.assertTrue(row.why, '%s overrides its donor without a stated reason' % row.unit)

    def test_a_chapter_with_no_curated_twin_reports_nothing_rather_than_guessing(self):
        # Silence is the honest answer where there is no twin to borrow from -- that is a
        # parity_reference gap, not an AI one (difficulty.ai_donor_findings' own rule).
        self.assertEqual(cs.ai('ch99-not-a-chapter', missing_ok=True), [])

    def test_the_report_shows_the_ai_section(self):
        text = cs.report('ch02')
        self.assertIn('  ai ', text, 'the section is rendered')
        self.assertIn('donor', text)


class AiBehaviourTable(unittest.TestCase):
    """#344: the map named 8 of the decomp's 19 AI2 scripts, so eleven indices reported as
    bare numbers -- one of which (0x0A) vanilla's own Prologue fields. Thirteen are named now;
    the six the decomp itself only gives an ADDRESS stay unnamed.

    Every name here is pinned, including 0x01/0x02/0x07 -- the #359 review caught those three
    unpinned, which meant a decomp rename could mis-bucket units past a green suite."""

    SYMBOLS = {                      # index -> the decomp symbol whose name states behaviour
        0x00: 'AiScr_AiB_MoveToEnemy',
        0x01: 'AiScr_AiB_MoveToEnemy_IgnoreChar_Unused1',
        0x02: 'AiScr_AiB_MoveToEnemy_IgnoreChar_Unused2',
        0x03: 'AiScr_AiB_NeverMove',
        0x04: 'AiScr_AiB_PillageThenPursue',
        0x05: 'AiScr_AiB_PillageThenEscape',
        0x06: 'AiScr_AiB_MoveTwiceToEnemy',
        0x07: 'AiScr_AiB_MoveTwiceToEnemy_IgnoreChar_Unused1',
        0x0C: 'gAiScript_Escape',
        0x0E: 'gAiScript_AttackWallsSnags',
        0x10: 'AiScr_AiB_GuardSpecificLocation',
        0x11: 'AiScr_AiB_PillageThenPursueAfterOneTurn',
        0x12: 'AiScr_AiB_MoveToEnemyAfterOneTurn',
    }

    def _table(self):
        """{AI2 index: decomp symbol} from gAi2ScriptTable, read at HEAD.

        cp_data.C, not cp_data.s: the .s is a BUILD ARTIFACT and is not tracked at HEAD, so
        reading it would both fail here and make the answer depend on build state -- the exact
        trap decisions.md names about reading the built decomp tree. The table is written with
        DESIGNATED initialisers (`[AI_B_0A] = ...`), so the index is read from the designator
        rather than from position -- a table with a hole would otherwise silently shift.
        """
        import build_campaign as bc, re
        text = bc.vanilla_decomp_text('src/cp_data.c')
        body = text.split('gAi2ScriptTable[] = {', 1)[1].split('};', 1)[0]
        return {int(i, 16): sym
                for i, sym in re.findall(r'\[AI_B_([0-9A-Fa-f]{2})\]\s*=\s*(\w+)', body)}

    def test_the_decomp_table_is_the_length_the_map_assumes(self):
        table = self._table()
        self.assertEqual(19, len(table))
        self.assertEqual(set(range(19)), set(table), 'the table is dense 0x00..0x12')

    def test_every_named_index_matches_its_decomp_symbol(self):
        """A name here is a claim about vanilla, so it is checked against vanilla."""
        import chapter_status as cs
        table = self._table()
        for index, symbol in self.SYMBOLS.items():
            self.assertEqual(symbol, table[index],
                             'index 0x%02X is %s in the decomp' % (index, table[index]))
            self.assertIn(index, cs.AI_BEHAVIOUR)

    def test_indices_the_decomp_does_not_NAME_are_left_unnamed(self):
        """The six bare-address entries stay out of the map. Inventing a name for one would
        make a guess indistinguishable from a fact at the call site."""
        import chapter_status as cs
        table = self._table()
        for index, symbol in sorted(table.items()):
            if re.match(r'^gAiScript_[0-9A-Fa-f]{6,}$', symbol):
                self.assertNotIn(index, cs.AI_BEHAVIOUR,
                                 'index 0x%02X is only an address (%s)' % (index, symbol))

    def test_no_mapped_index_falls_outside_the_table(self):
        import chapter_status as cs
        table = self._table()
        self.assertEqual([], [i for i in cs.AI_BEHAVIOUR if i not in table])


class Ai1Table(unittest.TestCase):
    """`AI_ACTION` is a claim about `gAi1ScriptTable`, so it is checked against it.

    The AI_A half is the one that MOVES: `AI_A_00 ActionInRange` is `AI_ACTION(100)` and acting
    includes stepping within the unit's own range to reach a target, while `AI_B_03 NeverMove`
    is `AI_NOP_0E` and only suppresses crossing the map. Reading AI_B alone reported 48 of 51
    units as static when they step out (decisions.md -> "AI_B is the APPROACH and AI_A is the
    ACTION"), which is the same coverage gap #344 fixed one axis over."""

    SYMBOLS = {0x00: 'gAiScript_ActionInRange',
               0x01: 'gAiScript_ActionInRange_80Perc',
               0x02: 'gAiScript_ActionInRange_50Perc',
               0x03: 'gAiScript_ActionStanding',
               0x04: 'gAiScript_ActionStanding_80Perc',
               0x05: 'gAiScript_ActionStanding_50Perc',
               0x06: 'gAiScript_DoNothing',
               0x07: 'gAiScript_ActionInRange_ExceptNatasha',
               0x08: 'gAiScript_ActionInRange_ExceptCivilian'}

    def _table(self):
        import build_campaign as bc
        body = re.search(r'gAi1ScriptTable\[\] = \{(.*?)\n\};',
                         bc.vanilla_decomp_text('src/cp_data.c'), re.S).group(1)
        return {int(i, 16): sym
                for i, sym in re.findall(r'\[AI_A_([0-9A-Fa-f]{2})\]\s*=\s*(\w+)', body)}

    def test_the_decomp_table_is_the_length_the_map_assumes(self):
        table = self._table()
        self.assertEqual(21, len(table))
        self.assertEqual(set(range(21)), set(table), 'the table is dense 0x00..0x14')

    def test_every_named_index_matches_its_decomp_symbol(self):
        import chapter_status as cs
        table = self._table()
        for index, symbol in self.SYMBOLS.items():
            self.assertEqual(symbol, table[index],
                             'index 0x%02X is %s in the decomp' % (index, table[index]))
            self.assertIn(index, cs.AI_ACTION)

    def test_indices_the_decomp_does_not_NAME_are_left_unnamed(self):
        """Twelve bare-address entries (0x09..0x14) stay out, on the same rule AI_BEHAVIOUR
        follows: a guess must not be indistinguishable from a fact at the call site."""
        import chapter_status as cs
        for index, symbol in sorted(self._table().items()):
            if re.match(r'^gAiScript_[0-9A-Fa-f]{6,}$', symbol):
                self.assertNotIn(index, cs.AI_ACTION,
                                 'index 0x%02X is only an address (%s)' % (index, symbol))

    def test_no_mapped_index_falls_outside_the_table(self):
        import chapter_status as cs
        table = self._table()
        self.assertEqual([], [i for i in cs.AI_ACTION if i not in table])

    def test_every_named_action_is_classified_as_moving_or_holding(self):
        import chapter_status as cs
        for index, name in cs.AI_ACTION.items():
            self.assertTrue(name in cs.AI_ACTION_MOVES or name in cs.AI_ACTION_HOLDS,
                            '0x%02X (%s) is named but neither moves nor holds' % (index, name))


class AiShape(unittest.TestCase):
    """The three-way shape a FULL vector describes. Two buckets could not express the case
    that actually shipped: a unit that holds its ground but steps out to strike."""

    def test_a_pursuer_crosses_the_map(self):
        import chapter_status as cs
        self.assertEqual('pursuer', cs.ai_shape((0x00, 0x00, 0, 0)))

    def test_engage_plus_never_move_is_a_STRIKER_not_a_statue(self):
        """The whole finding. ch06's merfolk are exactly this, and were read as statues."""
        import chapter_status as cs
        self.assertEqual('striker', cs.ai_shape((0x00, 0x03, 0, 0)))

    def test_hold_plus_never_move_is_a_statue(self):
        """vanilla Ch6's Novala -- GuardTileAI, the only non-ActionInRange unit in that force."""
        import chapter_status as cs
        self.assertEqual('statue', cs.ai_shape((0x03, 0x03, 0, 0)))

    def test_inert_plus_never_move_is_a_statue_too(self):
        """DoNothing -- vanilla Ch6's three green villagers."""
        import chapter_status as cs
        self.assertEqual('statue', cs.ai_shape((0x06, 0x03, 0, 0)))

    def test_an_own_errand_is_neither(self):
        import chapter_status as cs
        self.assertEqual('own-errand', cs.ai_shape((0x00, 0x05, 0, 0)))

    def test_an_unnamed_approach_is_unclassified(self):
        import chapter_status as cs
        self.assertIsNone(cs.ai_shape((0x00, 0x0A, 0, 0)))

    def test_an_unnamed_ACTION_is_unclassified_even_when_the_approach_is_named(self):
        """The half that decides movement is AI_A, so an unknown there is unknown overall --
        bucketing it by AI_B alone is the exact error this change exists to end."""
        import chapter_status as cs
        self.assertIsNone(cs.ai_shape((0x09, 0x03, 0, 0)))

    def test_a_bare_int_is_REFUSED_rather_than_misread(self):
        """A stale `ai_shape(ai[1])` call would classify a whole roster off half a vector and
        look perfectly correct. It raises instead."""
        import chapter_status as cs
        self.assertRaises(TypeError, cs.ai_shape, 0x03)


class BehaviourSplit(unittest.TestCase):
    """Reported, never folded into threat: since #335 derives AI from the donor, our shape IS
    the twin's, so a weighting would scale both sides and always say x1.00 (#344)."""

    def test_it_counts_each_shape(self):
        import chapter_status as cs
        got = cs.behaviour_split([(0x00, 0x00, 0, 0), (0x00, 0x12, 0, 0),
                                  (0x00, 0x03, 0, 0), (0x03, 0x10, 0, 0)])
        self.assertEqual(2, got['pursuer'])
        self.assertEqual(1, got['striker'])
        self.assertEqual(1, got['statue'])
        self.assertEqual(0, got['unclassified'])

    def test_a_known_but_non_player_behaviour_is_its_OWN_bucket(self):
        import chapter_status as cs
        got = cs.behaviour_split([(0x00, 0x05, 0, 0), (0x00, 0x0C, 0, 0), (0x00, 0x0E, 0, 0)])
        self.assertEqual(3, got['own_errand'])
        self.assertEqual(0, got['unclassified'])
        self.assertEqual(0, got['pursuer'])

    def test_every_named_pair_lands_in_exactly_one_bucket(self):
        """A NAMED family must never fall through to unclassified -- the rule #344's review
        found broken, now enforced across BOTH halves."""
        import chapter_status as cs
        for a in cs.AI_ACTION:
            for b in cs.AI_BEHAVIOUR:
                got = cs.behaviour_split([(a, b, 0, 0)])
                self.assertEqual(0, got['unclassified'],
                                 '(0x%02X, 0x%02X) is named on both halves but falls through'
                                 % (a, b))

    def test_an_unnamed_script_is_UNCLASSIFIED_not_bucketed(self):
        import chapter_status as cs
        got = cs.behaviour_split([(0x00, 0x0A, 0, 0)])
        self.assertEqual(1, got['unclassified'])
        self.assertEqual(0, got['statue'])

    def test_an_index_off_the_end_is_unclassified_too(self):
        import chapter_status as cs
        self.assertEqual(1, cs.behaviour_split([(0xFF, 0xFF, 0, 0)])['unclassified'])

    def test_the_buckets_account_for_every_unit(self):
        import chapter_status as cs
        vectors = [(0x00, 0x00, 0, 0), (0x00, 0x03, 0, 0), (0x03, 0x03, 0, 0),
                   (0x00, 0x0A, 0, 0), (0xFF, 0xFF, 0, 0), (0x00, 0x11, 0, 0),
                   (0x00, 0x05, 0, 0)]
        got = cs.behaviour_split(vectors)
        self.assertEqual(got['n'], got['pursuer'] + got['striker'] + got['statue']
                         + got['own_errand'] + got['unclassified'])


if __name__ == '__main__':
    unittest.main()
