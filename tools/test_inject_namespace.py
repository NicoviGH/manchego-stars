#!/usr/bin/env python3
"""Tests for tools/inject/namespace.py -- the injector's constants, across every module (#389).

Run:  python3 tools/test_inject_namespace.py
"""
import os
import sys
import types
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import inject.chapter_data  # noqa: E402
import inject.decomp  # noqa: E402
import inject.event_group  # noqa: E402
import inject.paths  # noqa: E402
import inject.scene_actors  # noqa: E402
from inject import namespace  # noqa: E402


class AStubReachesEveryReader(unittest.TestCase):
    """What `bc.NAME = value` did while the injector was one namespace."""

    def test_a_path_defined_in_several_modules_is_stubbed_in_all_of_them(self):
        # REPO is DEFINED (not imported) in paths, decomp, chapter_data and event_group: four
        # equal strings, four objects. Matching holders by identity stubbed one and left the
        # other three reading the real tree -- the stub that stubs nothing, again.
        readers = (inject.paths, inject.decomp, inject.chapter_data, inject.event_group)
        real = inject.paths.REPO
        with namespace.stubbed('REPO', '/stubbed'):
            self.assertEqual(['/stubbed'] * len(readers), [m.REPO for m in readers])
        self.assertEqual([real] * len(readers), [m.REPO for m in readers])

    def test_an_imported_function_is_stubbed_in_its_importers(self):
        with namespace.stubbed('vanilla_decomp_text', lambda rel: 'stub'):
            self.assertEqual('stub', inject.decomp.vanilla_decomp_text('x'))
            self.assertEqual('stub', inject.scene_actors.vanilla_decomp_text('x'))

    def test_a_name_no_module_binds_is_refused(self):
        with self.assertRaises(KeyError):
            with namespace.stubbed('NO_SUCH_INJECTOR_NAME', 1):
                pass


class TheRegistriesSeeEveryModule(unittest.TestCase):

    def test_a_constant_is_found_in_whichever_module_defines_it(self):
        found = namespace.injector_constants(r'^CH05_CHAPTER_YAML$')
        self.assertEqual(['CH05_CHAPTER_YAML'], list(found))

    def test_two_different_definitions_of_one_name_are_refused(self):
        a = types.ModuleType('inject.fake_a')
        b = types.ModuleType('inject.fake_b')
        a.CH99_X_MSG, b.CH99_X_MSG = 0x100, 0x200
        with mock.patch.object(namespace, 'injector_modules', return_value=[a, b]):
            with self.assertRaises(ValueError) as caught:
                namespace.injector_constants(r'_MSG$')
        self.assertIn('CH99_X_MSG', str(caught.exception))


if __name__ == '__main__':
    unittest.main()
