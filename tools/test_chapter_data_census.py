#!/usr/bin/env python3
"""Tests for tools/inject/chapter_data.py -- the ROMChapterData census (#396).

The failure class this exists for has landed FIVE times: a hosted chapter squats a vanilla
slot, and every `chapter_settings.json` field it does not write it keeps, tuned for a
different chapter. Goal text ids (#207), battle grounds (#289), the difficulty triple (#303),
`.traps` (#306) and `initialFogLevel` (#365) were each found one at a time, by something else
going wrong. The census answers "is there a sixth" once.

Two halves, like tools/test_event_group_census.py: pure tests over synthetic censuses, which
run anywhere, and live-tree tests that need an INJECTED decomp and skip when there is not one
-- on a clean tree every field reads INHERITED, which is true and useless.

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
    def test_an_undeclared_inherited_field_fails_the_build(self):
        with self.assertRaises(SystemExit) as e:
            cd.assert_census_declared(censuses={'ch05': {'initialWeather': cd.INHERITED}},
                                      declared={})
        self.assertIn('initialWeather', str(e.exception))

    def test_a_declared_inherited_field_passes(self):
        self.assertTrue(cd.assert_census_declared(
            censuses={'ch05': {'initialWeather': cd.INHERITED}},
            declared={'initialWeather': 'vanilla ships WEATHER_FINE on every slot we host'}))

    def test_a_declaration_for_a_field_we_actually_WRITE_is_stale_and_fails(self):
        with self.assertRaises(SystemExit) as e:
            cd.assert_census_declared(
                censuses={'ch05': {'battleTileSet': cd.WRITTEN}},
                declared={'battleTileSet': 'a reason nobody needs'})
        self.assertIn('stale', str(e.exception))

    def test_a_field_upstream_ADDS_tomorrow_fails_until_somebody_rules(self):
        with self.assertRaises(SystemExit) as e:
            cd.assert_census_declared(
                censuses={'ch05': {'someFieldUpstreamAdded': cd.INHERITED}}, declared={})
        self.assertIn('someFieldUpstreamAdded', str(e.exception))


class IntroCamera(unittest.TestCase):
    """`initialPosX/Y` is the chapter-intro camera centre (`chapterintrofx.c:864`), and it is
    the one inherited field whose safety is a property of OUR map rather than of vanilla's
    value. A hosted chapter's map is its DONOR's geometry, which is a different chapter from
    its host SLOT -- ch06 hosts on slot 7 and paints FE8 Ch13's map -- so the slot's camera
    tile lands on a map it was never measured against. The declaration says "in bounds", and
    this is what makes that a measurement instead of a hope."""

    def test_every_hosted_chapters_inherited_camera_tile_is_inside_its_map(self):
        self.assertEqual([], cd.intro_camera_out_of_bounds())

    def test_a_camera_tile_past_the_map_edge_is_reported(self):
        self.assertEqual(
            [('chNN', (30, 2), (15, 15))],
            cd.intro_camera_out_of_bounds(cameras={'chNN': (30, 2)},
                                          sizes={'chNN': (15, 15)}))


class PassOwnership(unittest.TestCase):
    """`OWNED_BY_PASS` is a claim about `build_campaign`'s code, so it is checked against that
    code. A claim nobody rechecks is how a field keeps a justification after the pass that
    justified it was renamed or stopped writing it -- the failure mode the whole census is
    about, one level up."""

    @staticmethod
    def _source_of(func_name):
        """The pass's own source, plus every ALL_CAPS module constant it names -- because a
        total pass writes its fields through a table (`DIFFICULTY_FIELDS`) rather than by
        spelling each one inside its body."""
        import ast
        path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'build_campaign.py')
        with open(path, encoding='utf-8') as fh:
            src = fh.read()
        tree = ast.parse(src)
        func = next((n for n in tree.body
                     if isinstance(n, ast.FunctionDef) and n.name == func_name), None)
        if func is None:
            return None
        chunks = [ast.get_source_segment(src, func) or '']
        wanted = {n.id for n in ast.walk(func)
                  if isinstance(n, ast.Name) and n.id.isupper()}
        for node in tree.body:
            if isinstance(node, ast.Assign) and any(
                    isinstance(t, ast.Name) and t.id in wanted for t in node.targets):
                chunks.append(ast.get_source_segment(src, node) or '')
        return '\n'.join(chunks)

    def test_every_owning_pass_exists_and_names_the_field_it_owns(self):
        for field, pass_name in sorted(cd.OWNED_BY_PASS.items()):
            src = self._source_of(pass_name)
            self.assertIsNotNone(src, '%s: no top-level `%s` in build_campaign.py'
                                      % (field, pass_name))
            leaf = field.split('.')[-1]
            self.assertIn(leaf, src,
                          '%s claims `%s` writes it, and that pass never names %r'
                          % (field, pass_name, leaf))

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
    INJECTED, 'the decomp is not injected: on a clean tree every field reads INHERITED, '
              'which is true and useless -- run a build first')
class LiveTree(unittest.TestCase):
    def test_every_hosted_chapter_gets_a_verdict_for_every_field(self):
        for h in hosts.hosted_chapters():
            self.assertEqual(set(cd.fields()), set(cd.census(h.name)))

    def test_the_live_tree_passes_because_every_inherited_field_is_declared(self):
        self.assertTrue(cd.assert_census_declared())

    def test_the_fields_the_incidents_were_about_are_WRITTEN_where_they_were_fixed(self):
        # #207 goal text ids, #289 battle grounds, #365 fog. Each was a real shipped bug;
        # the census is what keeps the fix visible rather than remembered.
        self.assertEqual(cd.WRITTEN, cd.census('ch05')['goal.statusObjectiveTextId'])
        self.assertEqual(cd.WRITTEN, cd.census('ch05')['battleTileSet'])
        self.assertEqual(cd.WRITTEN, cd.census('ch06')['initialFogLevel'])


if __name__ == '__main__':
    unittest.main(verbosity=2)
