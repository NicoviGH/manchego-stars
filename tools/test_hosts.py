#!/usr/bin/env python3
"""Tests for the host-slot registry (inject/hosts.py, #241).

Two properties are load-bearing here, and both were review findings on #239:

  * The registry must import with NOTHING but the stdlib. `check.py` lints it in CI's
    lightweight `checks` job, which installs pyyaml and nothing else -- the first version
    imported build_campaign, which imports Pillow, so the job would have failed every push
    with "build_campaign does not import: No module named 'PIL'".
  * Enrolment must be a GATE, not a convention. Discovery from `CHNN_HOST_INDEX` only
    covers a chapter that spells its constants right; an injector with a typo'd or missing
    declaration is silently unhosted, which is the exact ch04 class of failure #138 set out
    to close.

Run: python3 tools/test_hosts.py
"""
import importlib
import importlib.abc
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from inject import hosts


class _BlockImports(importlib.abc.MetaPathFinder):
    """Simulates CI's `pip install pyyaml` environment."""

    def __init__(self, *names):
        self.blocked = set(names)

    def find_spec(self, name, path=None, target=None):
        if name.split('.')[0] in self.blocked:
            raise ImportError('No module named %r' % name.split('.')[0])


class DependencyFree(unittest.TestCase):
    def test_it_imports_without_pillow_or_yaml(self):
        """The CRITICAL finding: this is what CI actually runs the lint in."""
        blocker = _BlockImports('PIL', 'yaml', 'numpy')
        sys.meta_path.insert(0, blocker)
        try:
            for name in [m for m in sys.modules if m.startswith('inject.hosts')]:
                del sys.modules[name]
            module = importlib.import_module('inject.hosts')
            self.assertTrue(module.hosted_chapters())
        finally:
            sys.meta_path.remove(blocker)
            importlib.import_module('inject.hosts')


class Discovery(unittest.TestCase):
    def test_finds_every_currently_hosted_chapter(self):
        got = {c.name: c.host_index for c in hosts.hosted_chapters()}
        self.assertEqual(got, {'prologue': hosts.PROLOGUE_HOST_INDEX,
                               'ch01': hosts.CH01_HOST_INDEX,
                               'ch02': hosts.CH02_HOST_INDEX,
                               'ch03': hosts.CH03_HOST_INDEX,
                               'ch04': hosts.CH04_HOST_INDEX})

    def test_the_prologue_is_enrolled_like_any_other_chapter(self):
        """It was invisible to discovery because PROLOGUE_HOST_INDEX does not match
        CH(\\d+)_HOST_INDEX -- so slot 1 was unguarded and a later CH05_HOST_INDEX = 1
        would have collided with it in silence."""
        entry = {c.name: c for c in hosts.hosted_chapters()}['prologue']
        self.assertEqual(entry.host_index, 1)
        self.assertEqual(entry.event_group, 'Ch1Events')
        self.assertEqual(entry.number, 0)

    def test_a_chapter_claiming_the_prologue_slot_fails_loudly(self):
        scope = dict(vars(hosts), CH05_HOST_INDEX=hosts.PROLOGUE_HOST_INDEX,
                     CH05_EVENT_GROUP='Ch6Events')
        with self.assertRaises(ValueError) as caught:
            hosts.hosted_chapters(scope)
        self.assertIn('prologue', str(caught.exception))

    def test_it_is_ordered_by_chapter_NUMBER_not_name(self):
        """Ordering by name is tautological against a sorted() implementation, and wrong
        once the prologue joins: 'ch01' sorts before 'prologue'."""
        scope = dict(vars(hosts), CH10_HOST_INDEX=11, CH10_EVENT_GROUP='Ch11Events')
        names = [c.name for c in hosts.hosted_chapters(scope)]
        self.assertEqual(names, ['prologue', 'ch01', 'ch02', 'ch03', 'ch04', 'ch10'])

    def test_a_new_chapter_enrolls_itself(self):
        scope = dict(vars(hosts), CH05_HOST_INDEX=6, CH05_EVENT_GROUP='Ch6EventData')
        entry = {c.name: c for c in hosts.hosted_chapters(scope)}['ch05']
        self.assertEqual((entry.host_index, entry.event_group), (6, 'Ch6EventData'))

    def test_a_host_slot_without_an_event_group_fails_loudly(self):
        scope = dict(vars(hosts), CH05_HOST_INDEX=6)
        with self.assertRaises(ValueError) as caught:
            hosts.hosted_chapters(scope)
        self.assertIn('CH05_EVENT_GROUP', str(caught.exception))

    def test_two_chapters_may_not_share_a_host_slot(self):
        scope = dict(vars(hosts), CH05_HOST_INDEX=hosts.CH04_HOST_INDEX,
                     CH05_EVENT_GROUP='Ch6Events')
        with self.assertRaises(ValueError) as caught:
            hosts.hosted_chapters(scope)
        self.assertIn('CH04', str(caught.exception).upper())


class EnrolmentIsAGate(unittest.TestCase):
    """An injector that exists but declares nothing must be caught -- reading the SOURCE,
    so the lint never imports build_campaign (and its Pillow dependency)."""

    def test_it_finds_the_injectors_in_the_source(self):
        found = hosts.injector_chapters()
        self.assertEqual(found, ['prologue', 'ch01', 'ch02', 'ch03', 'ch04'])

    def test_it_reads_source_rather_than_importing(self):
        blocker = _BlockImports('PIL', 'yaml', 'numpy')
        sys.meta_path.insert(0, blocker)
        try:
            self.assertIn('ch04', hosts.injector_chapters())
        finally:
            sys.meta_path.remove(blocker)

    def test_an_injector_with_no_declaration_is_reported(self, ):
        src = 'def inject_ch05(campaign):\n    pass\n'
        self.assertEqual(hosts.undeclared_injectors(source=src), ['ch05'])

    def test_a_declared_injector_is_not_reported(self):
        src = 'def inject_ch05(campaign):\n    pass\n'
        scope = dict(vars(hosts), CH05_HOST_INDEX=6, CH05_EVENT_GROUP='Ch6Events')
        self.assertEqual(hosts.undeclared_injectors(source=src, scope=scope), [])

    def test_the_live_build_has_no_undeclared_injectors(self):
        self.assertEqual(hosts.undeclared_injectors(), [])


class TheLintRunsInTheCiEnvironment(unittest.TestCase):
    def test_check_hosted_chapters_declared_passes_without_pillow(self):
        """The regression this whole module exists for: `checks` runs `python3
        tools/check.py` with pyyaml and nothing else installed."""
        blocker = _BlockImports('PIL', 'numpy')
        sys.meta_path.insert(0, blocker)
        try:
            for name in [m for m in sys.modules if m == 'check']:
                del sys.modules[name]
            check = importlib.import_module('check')
            fail = []
            check.check_hosted_chapters_declared(fail)
            self.assertEqual(fail, [])
        finally:
            sys.meta_path.remove(blocker)


if __name__ == '__main__':
    unittest.main()
