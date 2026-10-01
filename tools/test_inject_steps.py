#!/usr/bin/env python3
"""Tests for tools/inject/steps.py -- the injection steps and their declarations (#409).

Run:  python3 tools/test_inject_steps.py
"""
import argparse
import os
import shutil
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import build_scopes  # noqa: E402
from inject import steps  # noqa: E402
from inject.steps import FlagView, Step  # noqa: E402


def _names(registry):
    return [step.name for step in registry]


def _moved(registry, name, before):
    """`registry` with the first step called `name` moved to just before step `before`."""
    out = list(registry)
    step = out.pop(_names(out).index(name))
    out.insert(_names(out).index(before), step)
    return out


def _args(**flags):
    base = dict(campaign='c', montage=False, test_chapter=False, lord_boot=False,
                ch01_boot=False, ch03_boot=False, ch04_boot=False, ch05_boot=False,
                ch05_lupin=False, ch05_moose=False, ch05_ending=None, ch06_boot=False)
    base.update(flags)
    return argparse.Namespace(**base)


def a(): pass        # noqa: E704  -- tiny named steps for the synthetic registries
def b(): pass        # noqa: E704
def c(): pass        # noqa: E704


class TheRegistry(unittest.TestCase):
    def test_it_agrees_with_its_own_declarations(self):
        self.assertEqual(steps.validate(steps.STEPS), [])

    def test_every_retired_injection_order_pair_still_fails_when_reversed(self):
        # What check.py's hand-pinned INJECTION_ORDER held (audit 2.6, #110), now carried by
        # the declarations: moving the later step ahead of the earlier one must be refused.
        for first, then in (
                ('_inject_lord_select_engine', '_inject_lord_floor_engine'),
                ('inject_map_sprites', 'inject_enemy_class_reskins'),
                ('inject_enemy_class_reskins', 'inject_enemy_class_battle_anims'),
                ('inject_enemy_class_reskins', 'inject_ch01'),
                ('inject_winter_tileset', 'inject_ch01'),
                ('inject_winter_tileset', 'inject_prologue'),
                ('inject_ch01', 'inject_prologue'),
                ('inject_ch02', 'inject_ch04'),
                ('inject_ch03', 'inject_ch04'),
                ('inject_ch04', 'inject_ch05'),
                ('inject_ch03', 'chain_ch03_to_ch04'),
                ('inject_ch04', 'chain_ch04_to_ch05'),
                ('inject_ch05', 'inject_ch06'),
                ('inject_ch05', 'chain_ch05_to_ch06')):
            problems = steps.validate(_moved(steps.STEPS, then, first))
            self.assertTrue(any('%s must run before %s' % (first, then) in p for p in problems),
                            '%s ahead of %s was not refused: %s' % (then, first, problems))

    def test_the_cached_steps_run_before_every_flag_reader(self):
        cached = [i for i, step in enumerate(steps.STEPS) if step.cached]
        self.assertEqual(len(cached), 2)
        reordered = _moved(steps.STEPS, 'inject_battle_anims', 'chain_ch03_to_ch04')
        self.assertTrue(any('injection cache: inject_battle_anims' in p
                            for p in steps.validate(reordered)))

    def test_every_scope_is_global_or_one_chapter(self):
        for step in steps.STEPS:
            self.assertRegex(step.scope, r'^(global|chapter:(prologue|ch\d\d))$', step.name)
            # A step writing for both sides of a seam is global: guessing one side would
            # leave the other's scenarios reading a digest that never moved (#255).
            if step.name.startswith('chain_'):
                self.assertEqual(step.scope, 'global', step.name)

    def test_exactly_one_new_game_target_per_configuration(self):
        boots = [s for s in steps.STEPS if s.name == '_configure_boot']
        for flags in ({}, {'montage': True}, {'test_chapter': True},
                      {'test_chapter': True, 'lord_boot': True}, {'ch01_boot': True},
                      {'ch03_boot': True}, {'ch04_boot': True}, {'ch05_boot': True},
                      {'ch06_boot': True}, {'ch05_boot': True, 'test_chapter': True}):
            args = _args(**flags)
            hits = [s.title or s.name for s in boots if s.when(FlagView(args, s))]
            self.assertEqual(len(hits), 1, '%s -> %s' % (flags, hits))

    def test_the_prologue_runs_only_on_the_canonical_path(self):
        prologue = [s for s in steps.STEPS if s.name == 'inject_prologue'][0]
        self.assertTrue(prologue.when(FlagView(_args(montage=True), prologue)))
        for flags in ({'test_chapter': True}, {'ch05_boot': True}):
            self.assertFalse(prologue.when(FlagView(_args(**flags), prologue)), flags)


class Validation(unittest.TestCase):
    def setUp(self):
        self.facts = dict(steps.FACTS, x='why x')
        steps.FACTS, self._saved = self.facts, steps.FACTS
        self.addCleanup(setattr, steps, 'FACTS', self._saved)

    def test_a_need_listed_before_its_provider_names_both_and_why(self):
        problems = steps.validate([Step(b, needs=('x',)), Step(a, provides=('x',))])
        self.assertEqual(problems, ['a must run before b -- why x'])

    def test_a_need_nobody_provides_fails(self):
        self.assertEqual(steps.validate([Step(a, needs=('x',))]),
                         ["a needs 'x', which no step provides"])

    def test_an_undefined_fact_fails(self):
        self.assertIn("a names fact 'nope', which FACTS does not define",
                      steps.validate([Step(a, provides=('nope',))]))

    def test_a_cached_step_after_a_flag_reader_fails(self):
        problems = steps.validate([Step(a, flags=('ch05_boot',)), Step(b, cached=True)])
        self.assertEqual(len(problems), 1)
        self.assertIn('injection cache: b', problems[0])


class Flags(unittest.TestCase):
    def test_a_step_reads_campaign_and_its_declared_flags(self):
        view = FlagView(_args(ch05_boot=True), Step(a, flags=('ch05_boot',)))
        self.assertEqual((view.campaign, view.ch05_boot), ('c', True))

    def test_an_undeclared_flag_raises(self):
        view = FlagView(_args(), Step(a, flags=('ch05_boot',)))
        with self.assertRaisesRegex(AttributeError, 'a reads --ch06-boot but does not declare'):
            view.ch06_boot


class Running(unittest.TestCase):
    def setUp(self):
        self.tree = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tree, True)
        os.makedirs(os.path.join(self.tree, 'src'))
        self.scopes = build_scopes.BuildScopes(self.tree)

    def _writer(self, rel):
        def write(campaign):
            with open(os.path.join(self.tree, rel), 'w') as fh:
                fh.write(campaign)
        write.__name__ = 'write_' + rel.replace('/', '_').replace('.', '_')
        return write

    def test_strict_fails_an_undeclared_write_naming_step_and_path(self):
        step = Step(self._writer('src/a.c'), writes=('src/b.c',))
        with mock.patch.dict(os.environ, {'INJECT_STRICT': '1'}):
            with self.assertRaises(SystemExit) as cm:
                steps.run([step], _args(), self.scopes, anims=None)
        self.assertIn('write_src_a_c wrote src/a.c, which its `writes` do not declare',
                      str(cm.exception))

    def test_a_chapter_step_is_checked_even_outside_strict(self):
        step = Step(self._writer('src/a.c'), writes=('src/b.c',), scope='chapter:ch05')
        with mock.patch.dict(os.environ, {'INJECT_STRICT': ''}):
            with self.assertRaises(SystemExit):
                steps.run([step], _args(), self.scopes, anims=None)

    def test_the_footprint_check_catches_what_no_step_declares(self):
        ran = [Step(a, writes=('src/a.c',)), Step(b, writes=('texts/*',))]
        steps.check_footprint(ran, ['src/a.c', 'texts/texts.txt'])
        with self.assertRaisesRegex(SystemExit, r'wrote src/z\.c, which no step declares'):
            steps.check_footprint(ran, ['src/a.c', 'src/z.c'])

    def test_declared_writes_pass_and_land_in_the_steps_scope(self):
        step = Step(self._writer('src/a.c'), writes=('src/*.c',), scope='chapter:ch05')
        self.assertEqual(steps.run([step], _args(), self.scopes, anims=None), [step])
        self.assertEqual(self.scopes.finish()['chapter:ch05']['paths'], ['src/a.c'])

    def test_a_step_whose_when_is_false_does_not_run(self):
        step = Step(self._writer('src/a.c'), writes=('src/a.c',), flags=('ch05_boot',),
                    when=lambda args: args.ch05_boot)
        self.assertEqual(steps.run([step], _args(), self.scopes, anims=None), [])
        self.assertFalse(os.path.exists(os.path.join(self.tree, 'src', 'a.c')))

    def test_the_build_refuses_contradicted_declarations_before_writing(self):
        first = Step(self._writer('src/a.c'), writes=('src/a.c',), needs=('ch04-hosted',))
        with self.assertRaises(SystemExit):
            steps.run([first], _args(), self.scopes, anims=None)
        self.assertFalse(os.path.exists(os.path.join(self.tree, 'src', 'a.c')))


if __name__ == '__main__':
    unittest.main()
