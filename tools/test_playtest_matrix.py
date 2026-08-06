#!/usr/bin/env python3
"""Tests for tools/playtest/matrix.py -- the #231 playtest matrix runner.

Two layers:

  * the PURE layer (resolution, selection, grouping, ordering, aggregation) is
    tested against synthetic manifests with hand-written oracles, so a test never
    builds a ROM or launches mGBA;
  * the REAL-DATA layer asserts the shipped `matrix.yaml` still describes
    `harness.lua` -- that is the drift guard `check.py` also runs.

Run:

    python3 tools/test_playtest_matrix.py
"""
import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, 'playtest'))
import matrix as mx


def manifest(**over):
    """A small hand-written manifest; each test overrides just what it exercises."""
    data = {
        'defaults': {'rom': 'canonical', 'host_chapter': 1, 'fps': 240,
                     'vsync': 0, 'deadline': 420, 'kind': 'verdict'},
        'checkpoint_deadline': 900,
        'rom_configs': {
            'canonical': {},
            'testch': {'TESTCH': 1},
            'ch04boot': {'CH04BOOT': 1},
        },
        'classes': [],
        'scenarios': {'win': {}},
        'suites': {},
    }
    data.update(over)
    return mx.Manifest(data)


class Resolution(unittest.TestCase):
    def test_bare_scenario_takes_every_default(self):
        s = manifest().resolve('win')
        self.assertEqual((s.rom, s.host_chapter, s.fps, s.vsync, s.deadline),
                         ('canonical', 1, 240, 0, 420))
        self.assertIsNone(s.checkpoint)

    def test_scenario_entry_overrides_the_defaults(self):
        m = manifest(scenarios={'ch04moose': {'rom': 'ch04boot', 'host_chapter': 5}})
        s = m.resolve('ch04moose')
        self.assertEqual(s.rom, 'ch04boot')
        self.assertEqual(s.host_chapter, 5)

    def test_class_rule_applies_by_glob(self):
        # ports run.sh's `case "$SCENARIO" in record*) FPS=60; VSYNC=1; DEADLINE_S=300`
        m = manifest(classes=[{'match': 'record*', 'fps': 60, 'vsync': 1, 'deadline': 300}],
                     scenarios={'recordending': {}, 'win': {}})
        self.assertEqual(m.resolve('recordending').fps, 60)
        self.assertEqual(m.resolve('recordending').vsync, 1)
        self.assertEqual(m.resolve('recordending').deadline, 300)
        self.assertEqual(m.resolve('win').fps, 240)

    def test_a_later_class_rule_wins_like_a_second_bash_case(self):
        # run.sh sets record*=300s, then a SECOND case bumps recordch02ending to 600s.
        m = manifest(classes=[{'match': 'record*', 'fps': 60, 'deadline': 300},
                              {'match': 'recordch02ending', 'deadline': 600}],
                     scenarios={'recordch02ending': {}})
        s = m.resolve('recordch02ending')
        self.assertEqual(s.deadline, 600)
        self.assertEqual(s.fps, 60, 'the earlier rule still supplies what the later one omits')

    def test_scenario_entry_beats_a_class_rule(self):
        m = manifest(classes=[{'match': 'record*', 'deadline': 300}],
                     scenarios={'recordslow': {'deadline': 999}})
        self.assertEqual(m.resolve('recordslow').deadline, 999)

    def test_unknown_scenario_is_an_error(self):
        with self.assertRaises(mx.ManifestError):
            manifest().resolve('nosuchscenario')

    def test_unknown_rom_config_is_an_error(self):
        m = manifest(scenarios={'win': {'rom': 'nosuchrom'}})
        with self.assertRaises(mx.ManifestError):
            m.resolve('win')

    def test_checkpoint_implies_its_ckpt_builder_by_convention(self):
        m = manifest(scenarios={'recordending': {'checkpoint': 'seize'}})
        s = m.resolve('recordending')
        self.assertEqual(s.checkpoint, 'seize')
        self.assertEqual(s.checkpoint_builder, 'ckpt_seize')

    def test_make_flags_render_from_the_rom_config(self):
        m = manifest(scenarios={'ch04moose': {'rom': 'ch04boot'}})
        self.assertEqual(m.resolve('ch04moose').make_flags, ['CH04BOOT=1'])
        self.assertEqual(m.resolve_rom('canonical'), [])


class Selection(unittest.TestCase):
    def test_suite_expands_to_its_members(self):
        m = manifest(scenarios={'a': {}, 'b': {}, 'c': {}},
                     suites={'gate': ['a', 'c']})
        self.assertEqual(m.select(suite='gate'), ['a', 'c'])

    def test_explicit_scenarios_pass_through_in_order(self):
        m = manifest(scenarios={'a': {}, 'b': {}})
        self.assertEqual(m.select(scenarios=['b', 'a']), ['b', 'a'])

    def test_all_selects_every_verdict_scenario_only(self):
        m = manifest(scenarios={'a': {}, 'recordx': {'kind': 'record'},
                                'ckpt_y': {'kind': 'checkpoint'},
                                'probe': {'kind': 'diagnostic'}, 'b': {}})
        self.assertEqual(m.select(all_verdicts=True), ['a', 'b'])

    def test_unknown_suite_is_an_error(self):
        with self.assertRaises(mx.ManifestError):
            manifest().select(suite='nope')

    def test_selecting_nothing_is_an_error(self):
        with self.assertRaises(mx.ManifestError):
            manifest().select()


class Grouping(unittest.TestCase):
    def test_each_rom_configuration_is_built_at_most_once(self):
        m = manifest(scenarios={'a': {'rom': 'ch04boot'}, 'b': {}, 'c': {'rom': 'ch04boot'}})
        groups = m.plan(['a', 'b', 'c'])
        self.assertEqual([g.rom for g in groups], ['canonical', 'ch04boot'])
        self.assertEqual(len(groups), 2, 'interleaved roms must still collapse to one build each')
        self.assertEqual([s.name for s in groups[1].scenarios], ['a', 'c'])

    def test_group_order_follows_the_rom_configs_declaration_order(self):
        m = manifest(scenarios={'a': {'rom': 'ch04boot'}, 'b': {'rom': 'testch'}, 'c': {}})
        self.assertEqual([g.rom for g in m.plan(['a', 'b', 'c'])],
                         ['canonical', 'testch', 'ch04boot'])

    def test_checkpointless_scenarios_run_before_checkpoint_backed_ones(self):
        # a cheap failure must surface before a 15-minute ckpt_ch02start replay
        m = manifest(scenarios={'heavy': {'checkpoint': 'ch02start'}, 'cheap': {}})
        self.assertEqual([s.name for s in m.plan(['heavy', 'cheap'])[0].scenarios],
                         ['cheap', 'heavy'])

    def test_scenarios_sharing_a_checkpoint_are_contiguous(self):
        m = manifest(scenarios={'p': {'checkpoint': 'prep'}, 's': {'checkpoint': 'seize'},
                                'p2': {'checkpoint': 'prep'}})
        order = [s.name for s in m.plan(['p', 's', 'p2'])[0].scenarios]
        self.assertEqual(order, ['p', 'p2', 's'],
                         'switching checkpoints back and forth re-earns nothing but costs a load')

    def test_a_generic_scenario_needs_an_explicit_rom(self):
        m = manifest(scenarios={'attackprobe': {'rom': 'any'}})
        with self.assertRaises(mx.ManifestError):
            m.plan(['attackprobe'])
        groups = m.plan(['attackprobe'], rom='ch04boot')
        self.assertEqual(groups[0].rom, 'ch04boot')

    def test_an_explicit_rom_override_regroups_everything(self):
        m = manifest(scenarios={'a': {'rom': 'canonical'}, 'b': {'rom': 'ch04boot'}})
        groups = m.plan(['a', 'b'], rom='testch')
        self.assertEqual(len(groups), 1)
        self.assertEqual(groups[0].rom, 'testch')


class Aggregation(unittest.TestCase):
    def run_plan(self, m, names, verdicts, build_fails=()):
        """Drive execute() with fakes: no make, no mGBA."""
        self.built = []

        def build(rom, flags):
            self.built.append(rom)
            return rom not in build_fails

        def run_scenario(scn):
            v = verdicts[scn.name]
            return mx.Outcome(scenario=scn.name, rom=scn.rom, verdict=v, seconds=1.0,
                              artifacts='/tmp/playtest-' + scn.name,
                              log_tail='' if v == 'PASS' else 'boom')

        return mx.execute(m.plan(names), build=build, run_scenario=run_scenario)

    def test_all_pass_reports_ok_and_exit_zero(self):
        m = manifest(scenarios={'a': {}, 'b': {}})
        report = self.run_plan(m, ['a', 'b'], {'a': 'PASS', 'b': 'PASS'})
        self.assertEqual(report.exit_code, 0)
        self.assertTrue(report.ok)
        self.assertEqual([o.verdict for o in report.outcomes], ['PASS', 'PASS'])

    def test_one_failure_fails_the_whole_run(self):
        m = manifest(scenarios={'a': {}, 'b': {}})
        report = self.run_plan(m, ['a', 'b'], {'a': 'PASS', 'b': 'FAIL'})
        self.assertEqual(report.exit_code, 1)
        self.assertFalse(report.ok)
        self.assertEqual([o.scenario for o in report.failures], ['b'])

    def test_a_failing_scenario_does_not_stop_the_rest_of_the_matrix(self):
        m = manifest(scenarios={'a': {}, 'b': {}, 'c': {}})
        report = self.run_plan(m, ['a', 'b', 'c'], {'a': 'FAIL', 'b': 'PASS', 'c': 'PASS'})
        self.assertEqual(len(report.outcomes), 3, 'the matrix reports every scenario, not the first')

    def test_a_failed_build_blocks_only_its_own_group(self):
        m = manifest(scenarios={'a': {}, 'b': {'rom': 'ch04boot'}})
        report = self.run_plan(m, ['a', 'b'], {'a': 'PASS'}, build_fails={'ch04boot'})
        self.assertEqual(report.exit_code, 1)
        by_name = {o.scenario: o.verdict for o in report.outcomes}
        self.assertEqual(by_name['a'], 'PASS')
        self.assertEqual(by_name['b'], 'BLOCKED')

    def test_each_rom_is_built_exactly_once_during_execution(self):
        m = manifest(scenarios={'a': {'rom': 'ch04boot'}, 'b': {}, 'c': {'rom': 'ch04boot'}})
        self.run_plan(m, ['a', 'b', 'c'], {'a': 'PASS', 'b': 'PASS', 'c': 'PASS'})
        self.assertEqual(self.built, ['canonical', 'ch04boot'])
        self.assertEqual(len(self.built), len(set(self.built)))

    def test_duplicate_build_count_is_reported_for_the_222_metric(self):
        m = manifest(scenarios={'a': {'rom': 'ch04boot'}, 'b': {}, 'c': {'rom': 'ch04boot'}})
        report = self.run_plan(m, ['a', 'b', 'c'], {'a': 'PASS', 'b': 'PASS', 'c': 'PASS'})
        self.assertEqual(report.duplicate_builds, 0)
        self.assertEqual(report.builds, 2)


class TableRendering(unittest.TestCase):
    def outcome(self, name, verdict, seconds=61.0, rom='canonical'):
        return mx.Outcome(scenario=name, rom=rom, verdict=verdict, seconds=seconds,
                          artifacts='/tmp/playtest-' + name, log_tail='tail here')

    def test_success_table_is_one_line_per_scenario(self):
        report = mx.Report([self.outcome('a', 'PASS'), self.outcome('b', 'PASS')],
                           builds=1, duplicate_builds=0, seconds=122.0)
        body = mx.render_table(report)
        self.assertEqual(len([l for l in body.splitlines() if 'PASS' in l]), 2)
        self.assertIn('1m01s', body, 'durations read as human time, not raw seconds')

    def test_failure_output_names_the_artifact_and_the_tail(self):
        report = mx.Report([self.outcome('a', 'PASS'), self.outcome('b', 'FAIL')],
                           builds=1, duplicate_builds=0, seconds=10.0)
        body = mx.render_failures(report)
        self.assertIn('/tmp/playtest-b', body)
        self.assertIn('tail here', body)
        self.assertNotIn('/tmp/playtest-a', body, 'passing scenarios stay quiet')

    def test_duration_formatting(self):
        self.assertEqual(mx.human_duration(9), '9s')
        self.assertEqual(mx.human_duration(61), '1m01s')
        self.assertEqual(mx.human_duration(3725), '1h02m05s')


class ShellEnvExport(unittest.TestCase):
    """`run.sh` consumes matrix.py resolve -- so the export must be eval-safe."""

    def test_export_emits_assignments_run_sh_can_eval(self):
        m = manifest(scenarios={'ch04moose': {'rom': 'ch04boot', 'host_chapter': 5}})
        env = dict(line.split('=', 1) for line in
                   mx.export_env(m.resolve('ch04moose')).splitlines())
        self.assertEqual(env['MX_HOST_CHAPTER'], "'5'")
        self.assertEqual(env['MX_FPS'], "'240'")
        self.assertEqual(env['MX_ROM'], "'ch04boot'")
        self.assertEqual(env['MX_MAKE_FLAGS'], "'CH04BOOT=1'")

    def test_absent_checkpoint_exports_empty_not_the_word_none(self):
        env = dict(line.split('=', 1) for line in
                   mx.export_env(manifest().resolve('win')).splitlines())
        self.assertEqual(env['MX_CHECKPOINT'], "''")
        self.assertEqual(env['MX_CHECKPOINT_BUILDER'], "''")

    def test_every_exported_value_is_single_quoted(self):
        for line in mx.export_env(manifest().resolve('win')).splitlines():
            _, value = line.split('=', 1)
            self.assertTrue(value.startswith("'") and value.endswith("'"), line)


class VerdictParsing(unittest.TestCase):
    """Regression: the first live matrix run reported every scenario FAIL because the
    parser looked for a line STARTING with RESULT:. The harness stamps a frame counter
    on every line, so it never does."""

    REAL_PASS = ("wrote tools/playtest/symbols.lua (77 symbols)\n"
                 "running 'controller_turn' (pid 34280, 240fps)\n"
                 "----------------------------------------\n"
                 "[f000092] scenario: controller_turn\n"
                 "[f007234] RESULT: PASS -- no-prep boot -> move -> semantic Wait\n"
                 "artifacts: /tmp/playtest-controller_turn")
    REAL_FAIL = ("[f000092] scenario: ch04snag\n"
                 "[f004660] RESULT: FAIL -- the snag broke but (4,9) is terrain 0x10\n"
                 "artifacts: /tmp/playtest-ch04snag")

    def test_frame_stamped_pass_is_read_as_pass(self):
        self.assertEqual(mx.parse_verdict(self.REAL_PASS, 0), 'PASS')

    def test_frame_stamped_fail_is_read_as_fail(self):
        self.assertEqual(mx.parse_verdict(self.REAL_FAIL, 1), 'FAIL')

    def test_the_word_pass_elsewhere_in_the_line_does_not_count(self):
        text = '[f001] RESULT: FAIL -- the PASS condition never held\n'
        self.assertEqual(mx.parse_verdict(text, 1), 'FAIL')

    def test_the_last_result_line_wins(self):
        # run.sh cats the log and then echoes the verdict again
        text = '[f001] RESULT: FAIL -- first try\n[f002] RESULT: PASS -- retried\n'
        self.assertEqual(mx.parse_verdict(text, 0), 'PASS')

    def test_no_verdict_at_all_is_an_error_not_a_failure(self):
        self.assertEqual(mx.parse_verdict('mGBA exited early\n', 1), 'ERROR')

    def test_a_pass_line_with_a_nonzero_exit_is_not_trusted(self):
        self.assertEqual(mx.parse_verdict(self.REAL_PASS, 1), 'FAIL')


class WrongRomGuard(unittest.TestCase):
    """build_campaign stamps which flags built the ROM; a scenario bound to a different
    configuration must be refused in 0s rather than time out in mGBA."""

    def stamp(self, **flags):
        import json
        import tempfile
        path = os.path.join(tempfile.mkdtemp(), 'build-config.json')
        with open(path, 'w') as fh:
            json.dump({'campaign': 'x', 'flags': flags}, fh)
        return path

    def test_names_the_configuration_in_the_tree(self):
        m = manifest()
        path = self.stamp(TESTCH=False, CH04BOOT=True)
        self.assertEqual(mx.built_rom_config(m.rom_configs, path), 'ch04boot')

    def test_no_flags_set_is_the_canonical_build(self):
        m = manifest()
        path = self.stamp(TESTCH=False, CH04BOOT=False)
        self.assertEqual(mx.built_rom_config(m.rom_configs, path), 'canonical',
                         'canonical must not match every build just because it has no flags')

    def test_a_missing_stamp_is_unknown_not_canonical(self):
        self.assertIsNone(mx.built_rom_config(manifest().rom_configs, '/nonexistent/stamp'))

    def test_matching_rom_is_allowed(self):
        m = manifest(scenarios={'ch04moose': {'rom': 'ch04boot'}})
        path = self.stamp(CH04BOOT=True)
        self.assertIsNone(mx.check_rom(m, m.resolve('ch04moose'), path))

    def test_mismatched_rom_is_refused_and_says_how_to_fix_it(self):
        m = manifest(scenarios={'ch04moose': {'rom': 'ch04boot'}})
        problem = mx.check_rom(m, m.resolve('ch04moose'), self.stamp(TESTCH=True))
        self.assertIsNotNone(problem)
        self.assertIn('CH04BOOT=1', problem)
        self.assertIn('testch', problem)

    def test_an_unknown_stamp_does_not_block_the_run(self):
        m = manifest(scenarios={'ch04moose': {'rom': 'ch04boot'}})
        self.assertIsNone(mx.check_rom(m, m.resolve('ch04moose'), '/nonexistent/stamp'))

    def test_a_chapter_generic_scenario_is_never_refused(self):
        m = manifest(scenarios={'attackprobe': {'rom': 'any'}})
        self.assertIsNone(mx.check_rom(m, m.resolve('attackprobe'), self.stamp(TESTCH=True)))


class RealManifest(unittest.TestCase):
    """The drift guard: matrix.yaml must still describe harness.lua."""

    @classmethod
    def setUpClass(cls):
        cls.m = mx.Manifest.load()
        cls.harness = mx.harness_scenarios()

    def test_every_harness_scenario_has_a_manifest_row(self):
        missing = sorted(self.harness - set(self.m.scenarios))
        self.assertEqual(missing, [], 'new scenarios in harness.lua need a matrix.yaml row')

    def test_every_manifest_row_still_exists_in_harness(self):
        stale = sorted(set(self.m.scenarios) - self.harness)
        self.assertEqual(stale, [], 'matrix.yaml rows for scenarios harness.lua no longer defines')

    def test_every_scenario_resolves(self):
        for name in self.m.scenarios:
            self.m.resolve(name)

    def test_every_suite_member_exists_and_is_runnable(self):
        for suite, members in self.m.suites.items():
            self.assertTrue(members, 'suite %s is empty' % suite)
            for name in members:
                s = self.m.resolve(name)   # raises if unknown
                self.assertNotEqual(s.kind, 'checkpoint',
                                    '%s: %s is a checkpoint builder, not a scenario' % (suite, name))
                self.assertNotEqual(s.rom, 'any',
                                    '%s: %s is chapter-generic and needs an explicit rom' % (suite, name))

    def test_the_gate_suite_exists_and_spans_more_than_one_rom(self):
        gate = self.m.select(suite='gate')
        roms = {self.m.resolve(n).rom for n in gate}
        self.assertGreater(len(roms), 1, 'a single-ROM gate would not exercise the grouping')

    def test_the_gate_suite_plans_one_build_per_rom(self):
        groups = self.m.plan(self.m.select(suite='gate'))
        roms = [g.rom for g in groups]
        self.assertEqual(len(roms), len(set(roms)))

    def test_checkpoint_builders_are_all_marked_as_such(self):
        for name in self.m.scenarios:
            if name.startswith('ckpt_'):
                self.assertEqual(self.m.resolve(name).kind, 'checkpoint', name)

    def test_every_referenced_checkpoint_has_a_builder_scenario(self):
        for name in self.m.scenarios:
            s = self.m.resolve(name)
            if s.checkpoint and not s.dynamic_checkpoint:
                self.assertIn(s.checkpoint_builder, self.m.scenarios,
                              '%s wants checkpoint %s but ckpt_%s is not a scenario'
                              % (name, s.checkpoint, s.checkpoint))

    def test_a_checkpoint_and_its_builder_share_a_rom_configuration(self):
        # a builder run under a different flag would produce a state the consumer
        # then discards as ROM-hash-stale -- an invisible double cost
        for name in self.m.scenarios:
            s = self.m.resolve(name)
            if s.checkpoint and not s.dynamic_checkpoint:
                b = self.m.resolve(s.checkpoint_builder)
                self.assertEqual(b.rom, s.rom, '%s vs %s' % (name, s.checkpoint_builder))

    def test_the_ch04_scenarios_carry_the_flag_and_host_the_comments_document(self):
        for name in ('ch04moose', 'ch04packmath', 'ch04village', 'ch04cottage',
                     'ch04snag', 'clear_ch04', 'clear_ch04_parley', 'smoke_ch04'):
            s = self.m.resolve(name)
            self.assertEqual(s.rom, 'ch04boot', name)
            self.assertEqual(s.host_chapter, 5, name)

    def test_the_ch03_scenarios_carry_the_flag_and_host_the_comments_document(self):
        for name in ('ch03', 'ch03win', 'ch03talk', 'ch03door', 'ch03chest',
                     'ch03prep', 'ch03midmap', 'ch03tourmaline', 'smoke_ch03', 'clear_ch03'):
            s = self.m.resolve(name)
            self.assertEqual(s.rom, 'ch03boot', name)
            self.assertEqual(s.host_chapter, 4, name)

    def test_the_sandbox_scenarios_need_the_testch_rom(self):
        for name in ('recordanim', 'recordrbgtest', 'recordenemy', 'recordunitlist'):
            self.assertEqual(self.m.resolve(name).rom, 'testch', name)

    def test_run_sh_checkpoint_map_survived_the_port(self):
        # the exact table run.sh used to own, asserted row by row
        expected = {'recordending': 'seize', 'recordprep': 'prep', 'recordsupply': 'lordpinky',
                    'recordrescue': 'prep', 'recordtrade': 'prep', 'recordfix': 'prep',
                    'recordrbg': 'rbgch01', 'ch02': 'ch02start', 'smoke_ch02': 'ch02start',
                    'clear_ch02': 'ch02start', 'ch02baxby': 'ch02start',
                    'recordch02map': 'ch02start', 'recordch02combat': 'ch02start',
                    'recordch02ending': 'ch02start', 'recordchain': 'ch02start',
                    'recordch02intro': 'ch02intro'}
        for name, ckpt in expected.items():
            self.assertEqual(self.m.resolve(name).checkpoint, ckpt, name)

    def test_run_sh_timing_policy_survived_the_port(self):
        # record* -> 60fps/vsync/300s; smoke*|fuzz*|clear_ch02|clear_ch03|recordch02ending -> 600s
        self.assertEqual(self.m.resolve('recordending').fps, 60)
        self.assertEqual(self.m.resolve('recordending').vsync, 1)
        self.assertEqual(self.m.resolve('recordending').deadline, 300)
        self.assertEqual(self.m.resolve('win').fps, 240)
        self.assertEqual(self.m.resolve('win').deadline, 420)
        for name in ('smoke', 'smoke_ch02', 'fuzz', 'clear_ch02', 'clear_ch03'):
            self.assertEqual(self.m.resolve(name).deadline, 600, name)
        self.assertEqual(self.m.resolve('recordch02ending').deadline, 600)
        self.assertEqual(self.m.resolve('recordch02ending').fps, 60)
        self.assertEqual(self.m.resolve('llm').deadline, 2100)


if __name__ == '__main__':
    unittest.main()
