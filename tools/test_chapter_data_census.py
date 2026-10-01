#!/usr/bin/env python3
"""Tests for tools/inject/chapter_data.py -- the ROMChapterData census (#396).

The failure class this exists for has landed FIVE times: a hosted chapter squats a vanilla
slot, and every `chapter_settings.json` field it does not write it keeps, tuned for a
different chapter. Goal text ids (#207), battle grounds (#289), the difficulty triple (#303),
`.traps` (#306) and `initialFogLevel` (#365) were each found one at a time, by something else
going wrong. The census answers "is there a sixth" once.

The row is now framed from blank (#412, `inject/chapter_frame.py`), so the census is the
frame's ruling, listed, and runs anywhere. The live-tree half needs an INJECTED decomp: it
checks the bytes of every field the frame left inherited.

Run:  python3 tools/test_chapter_data_census.py
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from inject import chapter_data as cd
from inject import event_group, hosts


class Fields(unittest.TestCase):
    """The field list is the decomp's own, read at HEAD -- never a copy kept here."""

    def test_a_nested_group_contributes_its_LEAVES(self):
        f = cd.fields()
        self.assertIn('map.obj1Id', f)
        self.assertIn('goal.destPosX', f)
        self.assertIn('rank.tactics.A.EliwoodStory.Normal', f)

    def test_a_group_itself_is_not_a_field(self):
        # `map` is not a thing a pass can write or inherit; its eight leaves are.
        self.assertNotIn('map', cd.fields())
        self.assertNotIn('rank', cd.fields())

    def test_the_scalars_next_to_the_fog_field_are_in_the_census(self):
        # #396 names these two as the obvious next candidates after #365's fog.
        for f in ('initialWeather', 'initialPosX', 'initialPosY'):
            self.assertIn(f, cd.fields())


class Classify(unittest.TestCase):
    def test_a_changed_leaf_is_WRITTEN_and_an_unchanged_one_is_INHERITED(self):
        verdicts = cd.classify(['a', 'b'], {'a': 1, 'b': 2}, {'a': 1, 'b': 9})
        self.assertEqual(cd.INHERITED, verdicts['a'])
        self.assertEqual(cd.WRITTEN, verdicts['b'])

    def test_a_leaf_our_entry_does_not_carry_is_ABSENT(self):
        verdicts = cd.classify(['a', 'b'], {'a': 1}, {'a': 1, 'b': 9})
        self.assertEqual(cd.ABSENT, verdicts['b'])


class Ruling(unittest.TestCase):
    """The row is framed from blank (#412): the census lists the frame's ruling, and the build
    checks the bytes only for what the frame left INHERITED."""

    def test_every_hosted_chapter_has_every_field_ruled(self):
        for h in hosts.hosted_chapters():
            census = cd.census(h.name)
            self.assertEqual(set(cd.fields()), set(census))
            self.assertNotIn(cd.UNRULED, census.values(), h.name)

    def test_the_goal_template_is_written_not_inherited(self):
        # Copied from a vanilla slot of the declared objective TYPE: a write the frame makes.
        for f in ('goal.windowDataType', 'goal.destPosX', 'goal.windowEndTurnNumber'):
            self.assertEqual(cd.WRITTEN, cd.census('ch05')[f], f)
            self.assertEqual(cd.WRITTEN, cd.census('prologue')[f], f)

    def test_a_write_behind_the_frame_is_caught(self):
        self.assertIn('initialWeather', ' '.join(cd.behind_the_frame(
            'ch05', ['initialWeather'], {'initialWeather': 3}, {'initialWeather': 0})))
        self.assertEqual([], cd.behind_the_frame(
            'ch05', ['initialWeather'], {'initialWeather': 0}, {'initialWeather': 0}))


class OnlyTheChaptersThisBuildInjected(unittest.TestCase):
    """A boot build never runs inject_prologue, so slot 1 holds bytes no injector wrote.

    Censusing it there demanded rulings on the two goal ids the prologue writes, and every
    boot and test-chapter build died at this guard -- the whole playtest matrix but one ROM.
    With that fixed, ch01/ch03 boots died one guard later, on #398's reachable scenes.
    """

    def test_a_build_that_skips_the_prologue_does_not_census_it(self):
        names = [h.name for h in hosts.injected_chapters(prologue_injected=False)]
        self.assertNotIn('prologue', names)
        self.assertEqual([h.name for h in hosts.hosted_chapters()][1:], names)

    def test_the_canonical_build_censuses_every_hosted_chapter(self):
        self.assertEqual(hosts.hosted_chapters(),
                         hosts.injected_chapters(prologue_injected=True))

    def test_every_guard_that_reads_a_hosted_slot_gets_the_chapters_it_injected(self):
        # The two censuses and #398's reachable-scene guard all read what sits in each
        # hosted slot; the last one failed ch01/ch03 boots on vanilla Ch1's tutorial scenes.
        import re
        from inject.source import def_source
        main = def_source('main')
        self.assertTrue(re.search(r'\bhosted = injected_chapters\(prologue_injected\)', main))
        for guard in ('chapter_frame.assert_framed(',
                      'event_group.assert_census_declared(',
                      'chapter_data.assert_census_declared(',
                      'assert_reachable_scenes_load_their_actors('):
            call = main[main.index(guard) + len(guard):]
            self.assertTrue(re.match(r'\s*(hosted=)?(injected_chapters\(|hosted\b)', call),
                            '%s is not scoped to the chapters this build injected' % guard)


class IntroCamera(unittest.TestCase):
    """`initialPosX/Y` is the chapter-intro camera centre (`chapterintrofx.c:864`), and it is
    the one inherited field whose safety is a property of OUR map rather than of vanilla's
    value. A hosted chapter's map is its DONOR's geometry, which is a different chapter from
    its host SLOT -- ch06 hosts on slot 7 and paints FE8 Ch13's map -- so the slot's camera
    tile lands on a map it was never measured against. The declaration says "in bounds", and
    this is what makes that a measurement instead of a hope."""

    def test_every_hosted_chapters_inherited_camera_tile_is_inside_its_map(self):
        self.assertEqual([], cd.intro_camera_out_of_bounds())

    def test_the_map_size_is_actually_READ(self):
        """The check is only a measurement if it finds the map. Reading a key the layout
        JSONs do not carry returns None for every chapter, `out_of_bounds` returns [] for all
        of them, and the test above passes while measuring nothing -- which is what it did."""
        self.assertEqual((22, 22), cd._map_size('ch06'))
        self.assertEqual((15, 10), cd._map_size('prologue'))

    def test_a_camera_tile_past_the_map_edge_is_reported(self):
        self.assertEqual(
            [('chNN', (30, 2), (15, 15))],
            cd.intro_camera_out_of_bounds(cameras={'chNN': (30, 2)},
                                          sizes={'chNN': (15, 15)}))


class PassOwnership(unittest.TestCase):
    """`OWNED_BY_PASS` is a claim about the injector's code, so it is checked against that
    code. A claim nobody rechecks is how a field keeps a justification after the pass that
    justified it was renamed or stopped writing it -- the failure mode the whole census is
    about, one level up."""

    @staticmethod
    def _source_of(func_name):
        """The pass's own source, plus every ALL_CAPS module constant it names -- because a
        total pass writes its fields through a table (`DIFFICULTY_FIELDS`) rather than by
        spelling each one inside its body -- and every top-level helper it calls, because the
        two frame writers share one (`map_writes`)."""
        import ast
        from inject import source as injector
        defs = injector.top_level_definitions()
        hits = defs.get(func_name, [])
        funcs = [(path, n) for path, n in hits if isinstance(n, ast.FunctionDef)]
        if not funcs:
            return None
        path, func = funcs[-1]
        chunks = [injector.segment(path, func)]
        # The constants may live in any injector file once #389 moves them, so they are
        # looked up by name across all of them rather than beside the pass.
        wanted = {n.id for n in ast.walk(func)
                  if isinstance(n, ast.Name) and n.id.isupper()}
        for name in sorted(wanted):
            for where, node in defs.get(name, []):
                if isinstance(node, ast.Assign):
                    chunks.append(injector.segment(where, node))
        called = {n.func.id for n in ast.walk(func)
                  if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)}
        for name in sorted(called - {func_name}):
            for where, node in defs.get(name, []):
                if isinstance(node, ast.FunctionDef):
                    chunks.append(injector.segment(where, node))
        return '\n'.join(chunks)

    def test_every_owning_pass_exists_and_names_the_field_it_owns(self):
        for field, pass_name in sorted(cd.OWNED_BY_PASS.items()):
            src = self._source_of(pass_name)
            self.assertIsNotNone(src, '%s: no top-level `%s` in any injector file'
                                      % (field, pass_name))
            leaf = field.split('.')[-1]
            self.assertIn(leaf, src,
                          '%s claims `%s` writes it, and that pass never names %r'
                          % (field, pass_name, leaf))

    def test_the_prologue_is_not_credited_to_the_pass_it_never_calls(self):
        """`_retarget_host_chapter` is called by the six chapter injectors and NOT by
        `inject_prologue` -- the prologue runs on the slot it was given (inject/hosts.py) and
        frames that row itself. Crediting the retarget here would skip the ruling on the one
        field the prologue really does inherit: `prepScreenNumber`, vanilla's 2."""
        self.assertIsNone(cd.owner_for('prologue', 'prepScreenNumber'))
        self.assertEqual('_retarget_host_chapter',
                         cd.owner_for('ch03', 'prepScreenNumber'))

    def test_what_the_prologue_DOES_write_is_still_owned(self):
        self.assertEqual('inject_prologue', cd.owner_for('prologue', 'map.mainLayerId'))
        self.assertEqual('inject_prologue', cd.owner_for('prologue', 'fadeToBlack'))

    def test_a_total_pass_covers_the_prologue_too(self):
        for field in ('initialFogLevel', 'battleTileSet', 'normalModeLevelMalus'):
            self.assertIsNotNone(cd.owner_for('prologue', field), field)

    def test_no_field_is_both_owned_and_declared_inherited(self):
        both = sorted(set(cd.OWNED_BY_PASS) & set(cd.DECLARED_INHERITED))
        self.assertEqual([], both)

    def test_every_field_is_ruled_on_one_way_or_the_other(self):
        """The census's whole claim, stated once: nothing in the struct is unaccounted for."""
        unruled = [f for f in cd.fields()
                   if f not in cd.OWNED_BY_PASS and f not in cd.DECLARED_INHERITED]
        self.assertEqual([], unruled)


INJECTED = event_group.injected(paths=('src/data/chapter_settings.json',))


@unittest.skipUnless(
    INJECTED, 'the decomp is not injected -- run a build first')
class LiveTree(unittest.TestCase):
    def test_every_inherited_field_still_holds_its_donor_slots_value(self):
        self.assertTrue(cd.assert_census_declared())


class TheIncidentsStayFixed(unittest.TestCase):
    def test_the_fields_the_incidents_were_about_are_WRITTEN_where_they_were_fixed(self):
        # #207 goal text ids, #289 battle grounds, #365 fog. Each was a real shipped bug;
        # the census is what keeps the fix visible rather than remembered.
        self.assertEqual(cd.WRITTEN, cd.census('ch05')['goal.statusObjectiveTextId'])
        self.assertEqual(cd.WRITTEN, cd.census('ch05')['battleTileSet'])
        self.assertEqual(cd.WRITTEN, cd.census('ch06')['initialFogLevel'])


if __name__ == '__main__':
    unittest.main(verbosity=2)
