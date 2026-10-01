#!/usr/bin/env python3
"""Tests that the fingerprint gate is aimed at the configurations a change can reach (#424).

Fingerprinting every ROM configuration costs ~2.5 min each, and most of them build the same
tree as the default but for one boot step. So `fingerprint_reach` answers which ones a change
can move, from the step declarations: a configuration is worth fingerprinting only where a
step that runs under it reads a flag it sets (or runs under it alone), and the change lands in
that step's code. These pin both directions -- a ch05 edit must reach every ch05 arm, and an
edit no flag-reading step imports must reach the default alone.

Run: python3 tools/test_fingerprint_reach.py
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import fingerprint_reach as fr                                        # noqa: E402

CH05_ARMS = {'ch05boot', 'ch05lupinboot', 'ch05mooseboot', 'ch05endingboot',
             'ch05endingnosahnar', 'ch05endingbasildied'}


class TheConfigurations(unittest.TestCase):

    def test_they_are_the_matrix_rom_configs_with_canonical_first(self):
        configs = fr.configurations()
        self.assertEqual('canonical', next(iter(configs)))
        self.assertEqual([], configs['canonical'])
        self.assertEqual(['--ch05-boot', '--ch05-ending=no-sahnar'],
                         sorted(configs['ch05endingnosahnar']))


class TheReach(unittest.TestCase):

    def reached(self, *paths):
        return set(fr.reach(list(paths)))

    def test_a_chapter_module_reaches_its_own_boots_and_the_default(self):
        self.assertEqual({'canonical'} | CH05_ARMS,
                         self.reached('tools/inject/chapters/ch05.py'))

    def test_a_module_only_the_montage_path_imports_reaches_the_montage(self):
        """The prologue runs in the default build too, but with --montage off: the montage's
        own code is exercised by `montage` alone, and the default would never see it break."""
        self.assertEqual({'canonical', 'montage'}, self.reached('tools/inject/montage.py'))

    def test_the_test_chapter_reaches_the_sandbox_and_its_lord_boot(self):
        """It never runs under a chapter boot, so a ch05 boot cannot see it change."""
        self.assertEqual({'canonical', 'testch', 'lordboot'},
                         self.reached('tools/inject/test_chapter.py'))

    def test_a_module_no_flag_reader_imports_reaches_the_default_alone(self):
        self.assertEqual({'canonical'}, self.reached('tools/inject/crit_flourish.py'))

    def test_the_boot_configurator_reaches_everything(self):
        self.assertEqual(set(fr.configurations()), self.reached('tools/inject/boot.py'))

    def test_the_step_list_and_the_cli_reach_everything(self):
        """They hold every step's `when` and `call`, which is where a flag is read."""
        every = set(fr.configurations())
        self.assertEqual(every, self.reached('tools/inject/steps.py'))
        self.assertEqual(every, self.reached('tools/build_campaign.py'))

    def test_campaign_data_reaches_everything(self):
        """No step declares what it READS, so data cannot be attributed to one."""
        self.assertEqual(set(fr.configurations()),
                         self.reached('campaigns/rime-of-the-frostmaiden/chapters/'
                                      'ch04-the-white-moose.yaml'))

    def test_what_the_build_never_reads_reaches_nothing(self):
        self.assertEqual(set(), self.reached('docs/decisions.md', 'tools/test_check_canaries.py',
                                             'tools/playtest/matrix.yaml'))

    def test_a_tools_module_the_injector_imports_is_reached_through_its_importers(self):
        """`yaml_loader` is not under tools/inject, but every chapter reads YAML through it."""
        self.assertTrue(CH05_ARMS <= self.reached('tools/yaml_loader.py'))

    def test_a_relative_import_is_followed(self):
        """`chapter_frame` imports `event_group` as `from . import ...`, and ch05 frames its
        event group through it (#428 review)."""
        self.assertTrue(CH05_ARMS <= self.reached('tools/inject/event_group.py'))

    def test_a_package_init_runs_for_every_module_under_it(self):
        self.assertTrue(CH05_ARMS <= self.reached('tools/inject/chapters/__init__.py'))

    def test_no_injector_file_reaches_nothing(self):
        """Every file under tools/inject/ is a ROM input, so the default build at least."""
        import glob
        for path in glob.glob(os.path.join(fr.REPO, 'tools', 'inject', '**', '*.py'),
                              recursive=True):
            rel = os.path.relpath(path, fr.REPO)
            self.assertIn('canonical', self.reached(rel), rel)

    def test_every_reached_configuration_says_why(self):
        for config, reasons in fr.reach(['tools/inject/chapters/ch05.py']).items():
            self.assertTrue(reasons, config)
        self.assertIn('inject_ch05', ' '.join(fr.reach(['tools/inject/chapters/ch05.py'])
                                              ['ch05mooseboot']))


if __name__ == '__main__':
    unittest.main()
