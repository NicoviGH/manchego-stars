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
import re
import shutil
import sys
import tempfile
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


class StaleResults(unittest.TestCase):
    """Regression: a run takes minutes and results.json is what everything downstream
    polls for, so last run's copy must not survive into this one."""

    def test_clearing_removes_a_previous_runs_verdicts(self):
        import tempfile
        d = tempfile.mkdtemp()
        with open(mx.results_path(d), 'w') as fh:
            fh.write('{"ok": true}')
        mx.clear_results(d)
        self.assertFalse(os.path.exists(mx.results_path(d)))

    def test_clearing_an_empty_directory_is_not_an_error(self):
        import tempfile
        mx.clear_results(tempfile.mkdtemp())      # must not raise


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

    def test_the_talk_recruits_other_arm_is_actually_gated(self):
        """`ch05recruit` runs on a ROM with no wolf, so it only ever walks the no-Lupin arm --
        an inverted BEQ or a swapped pair of message ids passes it. A scenario in no suite runs
        in no gate, which is how a branch ends up with one tested arm and one hoped-for one."""
        for scenario in ('ch05lupinbenched', 'ch05lupinkilled'):
            self.assertIn(scenario, self.m.scenarios)
            member_of = [s for s, members in self.m.suites.items() if scenario in members]
            self.assertTrue(member_of, '%s is in no suite, so nothing runs it' % scenario)
        self.assertIn('ch05lupinbenched', self.m.suites['gate'],
                      'the gate must walk the arm ch05recruit cannot reach')

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

    def test_the_ravisin_capture_uses_the_real_ch05_map(self):
        s = self.m.resolve('recordravisin')
        self.assertEqual(s.rom, 'ch05boot')
        self.assertEqual(s.host_chapter, 6)
        self.assertEqual(s.kind, 'record')

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


class ParallelScenarios(unittest.TestCase):
    """Scenarios inside one ROM config run concurrently; builds never do."""

    def _report(self, m, names, jobs, record):
        def build(rom, flags):
            record.append(('build', rom))
            return True

        def run_scenario(scn):
            record.append(('run', scn.name))
            return mx.Outcome(scn.name, scn.rom, 'PASS', 1.0, '', '')

        return mx.execute(m.plan(names), build=build, run_scenario=run_scenario, jobs=jobs)

    def test_checkpointless_scenarios_are_parallel_safe(self):
        m = manifest(scenarios={'a': {}, 'b': {}})
        par, ser = mx.scenario_lanes([m.resolve('a'), m.resolve('b')])
        self.assertEqual([s.name for s in par], ['a', 'b'])
        self.assertEqual(ser, [])

    def test_a_checkpoint_scenario_is_forced_serial(self):
        """states/<name>.ss is a SHARED file a scenario will mint if it is stale, so two
        scenarios wanting one checkpoint would race to write it."""
        m = manifest(scenarios={'a': {}, 'b': {'checkpoint': 'prep'}})
        par, ser = mx.scenario_lanes([m.resolve('a'), m.resolve('b')])
        self.assertEqual([s.name for s in par], ['a'])
        self.assertEqual([s.name for s in ser], ['b'])

    def test_every_scenario_still_runs_exactly_once_in_parallel(self):
        m = manifest(scenarios={'a': {}, 'b': {}, 'c': {'rom': 'ch04boot'}})
        rec = []
        report = self._report(m, ['a', 'b', 'c'], jobs=4, record=rec)
        self.assertEqual(sorted(o.scenario for o in report.outcomes), ['a', 'b', 'c'])
        self.assertEqual(sorted(n for k, n in rec if k == 'run'), ['a', 'b', 'c'])

    def test_a_build_never_overlaps_its_own_group_s_runs(self):
        """The tree holds ONE fireemblem8.gba -- a build during a live run would swap the
        ROM out from under the emulator."""
        m = manifest(scenarios={'a': {}, 'b': {}, 'c': {'rom': 'ch04boot'}})
        rec = []
        self._report(m, ['a', 'b', 'c'], jobs=4, record=rec)
        kinds = [k for k, _ in rec]
        self.assertEqual(kinds.count('build'), 2)
        # the second build must come after every run of the first group
        second = [i for i, (k, _) in enumerate(rec) if k == 'build'][1]
        first_group = {n for k, n in rec[:second] if k == 'run'}
        self.assertEqual(first_group, {'a', 'b'})


class RomCache(unittest.TestCase):
    """A harness-only change must not pay for four rebuilds."""

    def test_the_digest_ignores_files_that_cannot_change_the_rom(self):
        """harness.lua/matrix.py/matrix.yaml drive the EMULATOR. If they were inputs the
        cache would miss on exactly the edits it exists to make free."""
        for rel in ('tools/playtest/harness.lua', 'tools/playtest/matrix.py',
                    'tools/playtest/matrix.yaml'):
            self.assertNotIn(rel, mx.ROM_INPUT_PATHS)

    def test_the_digest_covers_what_the_rom_is_built_from(self):
        for rel in ('campaigns', 'engine', 'tools/inject', 'tools/build_campaign.py'):
            self.assertIn(rel, mx.ROM_INPUT_PATHS)

    def test_make_flags_and_campaign_are_part_of_the_key(self):
        """Otherwise a CH04BOOT ROM would be served to a CH05BOOT scenario."""
        a = mx.rom_input_hash(['CH04BOOT=1'])
        b = mx.rom_input_hash(['CH05BOOT=1'])
        self.assertTrue(a and b)
        self.assertNotEqual(a, b)

    def test_a_touched_input_changes_the_digest(self):
        target = os.path.join(mx.REPO, 'tools', 'build_campaign.py')
        before = mx.rom_input_hash([])
        st = os.stat(target)
        try:
            os.utime(target, ns=(st.st_atime_ns, st.st_mtime_ns + 10 ** 9))
            self.assertNotEqual(before, mx.rom_input_hash([]))
        finally:
            os.utime(target, ns=(st.st_atime_ns, st.st_mtime_ns))
        self.assertEqual(before, mx.rom_input_hash([]))

    def test_a_miss_reports_nothing_to_restore(self):
        self.assertFalse(mx.restore_cached_rom('canonical', 'deadbeef' * 4))
        self.assertFalse(mx.restore_cached_rom('canonical', None))

    def test_the_ELF_travels_with_the_rom(self):
        """gen_symbols.py reads fireemblem8.elf, and the boot flags MOVE symbols: a
        ch05boot ELF and a canonical ELF disagree on 58 of the names the harness reads
        (gUnitLookup, gItemData, Menu_OnIdle...). Restoring a cached .gba while the tree
        keeps the previous config's .elf makes every scenario read the wrong addresses --
        and a gate spanning four configs restores three of them that way on every warm
        run. Cache the pair or cache neither."""
        self.assertEqual({ext for ext, _ in mx.ROM_CACHE_ARTIFACTS},
                         {'.gba', '.elf', '.json', '.scopes.json'})

    def test_the_scope_manifest_travels_with_the_rom_too(self):
        """Same lesson as the ELF: a restored ROM must bring the manifest of what the
        build that produced it wrote, or the verdict key reads whatever built last."""
        self.assertIn(mx.SCOPES_PATH, [dest for _, dest in mx.ROM_CACHE_ARTIFACTS])

    def test_a_partial_slot_is_not_restored(self):
        """Half a slot is worse than none: a .gba without its .elf is exactly the
        wrong-symbols failure this cache must not create."""
        import tempfile as _t
        d = _t.mkdtemp()
        self.addCleanup(shutil.rmtree, d, True)
        with open(os.path.join(d, 'canonical-abc.gba'), 'w') as fh:
            fh.write('x')
        self.assertFalse(mx.restore_cached_rom('canonical', 'abc', cache_dir=d))


# A miniature harness.lua with the same SHAPE as the real one: a preamble holding
# tuning, top-level helpers, a mid-file top-level table sitting between two helpers,
# and two scenarios that reach different helpers.
HARNESS_FIXTURE = '''\
local TUNE = { inputAttempts = 3 }

local function yield() coroutine.yield() end

local function shared(n)
    return yield(n)
end

local NAMES = { [1] = "alpha" }

local function onlyForA(n)
    return shared(n) + NAMES[1]
end

local function onlyForB(n)
    return shared(n) - 1
end

scenarios.alpha = function()
    return onlyForA(1)   -- a comment
end

scenarios.beta = function()
    return onlyForB(2)
end
'''


class HarnessSourceAnalysis(unittest.TestCase):
    """The call-graph machinery that scopes both the #238 press gate and the verdict
    cache. It lives here, with the rest of the code that reads harness.lua."""

    def funcs(self):
        return mx.harness_functions(HARNESS_FIXTURE)

    def test_every_top_level_function_is_found_with_its_kind(self):
        funcs = self.funcs()
        self.assertEqual(funcs['alpha'][1], 'scenario')
        self.assertEqual(funcs['shared'][1], 'helper')
        self.assertIn('onlyForB', funcs)

    def test_a_closure_is_transitive_and_includes_itself(self):
        self.assertEqual(mx.reaches('alpha', self.funcs()),
                         {'alpha', 'onlyForA', 'shared', 'yield'})

    def test_a_closure_excludes_helpers_it_never_mentions(self):
        self.assertNotIn('onlyForB', mx.reaches('alpha', self.funcs()))

    def test_a_helper_passed_as_a_VALUE_is_still_reached(self):
        """`waitFor(shared)` and `{ fn = onlyForB }` hand a helper over without calling
        it at the reference site. Following call syntax alone lets it escape the closure,
        and an edit to it would then leave the verdict key still."""
        source = HARNESS_FIXTURE.replace('    return onlyForA(1)   -- a comment',
                                         '    return yield(onlyForB)')
        self.assertIn('onlyForB', mx.reaches('alpha', mx.harness_functions(source)))

    def test_a_body_carries_no_comments(self):
        """A comment cannot change a verdict, so it must not change a fingerprint."""
        self.assertNotIn('a comment', self.funcs()['alpha'][0])

    def test_shared_text_carries_top_level_data_no_function_owns(self):
        """`NAMES` sits between two helpers. It feeds observation, so an edit to it
        must invalidate EVERY scenario -- including ones whose closure misses the
        helper it happens to be glommed onto."""
        shared = mx.harness_shared(HARNESS_FIXTURE)
        self.assertIn('alpha', shared)          # the NAMES table's contents
        self.assertIn('inputAttempts', shared)  # the preamble

    def test_shared_text_leaves_out_the_bodies_functions_do_own(self):
        shared = mx.harness_shared(HARNESS_FIXTURE)
        self.assertNotIn('onlyForA(1)', shared, 'a scenario body is not shared text')
        self.assertNotIn('shared(n) - 1', shared, 'a multi-line helper body is not shared text')

    def test_a_one_line_function_falls_back_to_being_shared(self):
        """`local function yield() ... end` has no column-0 terminator to split on.
        Unattributable means SHARED, never dropped -- the conservative direction."""
        self.assertIn('coroutine.yield', mx.harness_shared(HARNESS_FIXTURE))

    def test_the_real_harness_partitions_without_losing_a_scenario(self):
        with open(mx.HARNESS) as fh:
            source = fh.read()
        funcs = mx.harness_functions(source)
        for name in mx.harness_scenarios():
            self.assertIn(name, funcs, '%s is defined but not attributable' % name)


class VerdictFingerprint(unittest.TestCase):
    """A verdict is a pure function of four inputs; the fingerprint must move when
    any of them does, and hold still when nothing else does."""

    def setUp(self):
        self.m = manifest(scenarios={'alpha': {}, 'beta': {'rom': 'ch04boot'}})
        self.alpha = self.m.resolve('alpha')

    def fingerprint(self, rom='romdigest', harness=HARNESS_FIXTURE, driver='D',
                    scenario=None, env=None):
        return mx.scenario_fingerprint(scenario or self.alpha, rom,
                                       harness_source=harness, driver=driver,
                                       env=env if env is not None else {})

    def test_the_same_four_inputs_give_the_same_key(self):
        self.assertEqual(self.fingerprint(), self.fingerprint())

    def test_a_different_rom_digest_is_a_different_key(self):
        self.assertNotEqual(self.fingerprint(), self.fingerprint(rom='other'))

    def test_an_unbuildable_rom_digest_refuses_to_cache(self):
        """rom_input_hash returns None when it cannot pin the decomp. No key, no cache."""
        self.assertIsNone(self.fingerprint(rom=None))

    def test_editing_the_scenarios_own_body_is_a_different_key(self):
        edited = HARNESS_FIXTURE.replace('return onlyForA(1)', 'return onlyForA(9)')
        self.assertNotEqual(self.fingerprint(), self.fingerprint(harness=edited))

    def test_editing_a_helper_it_reaches_is_a_different_key(self):
        edited = HARNESS_FIXTURE.replace('return shared(n) + NAMES[1]', 'return 0')
        self.assertNotEqual(self.fingerprint(), self.fingerprint(harness=edited))

    def test_editing_top_level_data_no_function_owns_is_a_different_key(self):
        edited = HARNESS_FIXTURE.replace('inputAttempts = 3', 'inputAttempts = 5')
        self.assertNotEqual(self.fingerprint(), self.fingerprint(harness=edited))
        edited = HARNESS_FIXTURE.replace('"alpha"', '"omega"')
        self.assertNotEqual(self.fingerprint(), self.fingerprint(harness=edited))

    def test_editing_ANOTHER_scenario_is_the_SAME_key(self):
        """The whole point. harness.lua is one chunk and nearly every task edits it;
        hashing it whole would invalidate all 17 scenarios on every commit."""
        edited = HARNESS_FIXTURE.replace('return onlyForB(2)', 'return onlyForB(3)')
        self.assertEqual(self.fingerprint(), self.fingerprint(harness=edited))

    def test_editing_a_helper_it_never_reaches_is_the_SAME_key(self):
        edited = HARNESS_FIXTURE.replace('return shared(n) - 1', 'return 42')
        self.assertEqual(self.fingerprint(), self.fingerprint(harness=edited))

    def test_rewording_a_comment_is_the_SAME_key(self):
        """Comments are stripped, so prose cannot move a verdict key. (Adding or
        removing a LINE still does -- conservative, and the safe direction.)"""
        edited = HARNESS_FIXTURE.replace('-- a comment', '-- a different comment')
        self.assertEqual(self.fingerprint(), self.fingerprint(harness=edited))

    def test_editing_the_driver_is_a_different_key(self):
        """controller.lua decides every classification the scenario guards on, and
        run.sh decides the emulator it guards them in."""
        self.assertNotEqual(self.fingerprint(), self.fingerprint(driver='D2'))


    def test_a_changed_manifest_entry_is_a_different_key(self):
        """Same Lua, same ROM -- but a different host chapter or deadline is a
        different run."""
        other = manifest(scenarios={'alpha': {'host_chapter': 6}}).resolve('alpha')
        self.assertNotEqual(self.fingerprint(), self.fingerprint(scenario=other))

    def test_a_scenario_the_harness_does_not_define_refuses_to_cache(self):
        gone = manifest(scenarios={'ghost': {}}).resolve('ghost')
        self.assertIsNone(self.fingerprint(scenario=gone))

    def test_a_PT_env_var_the_run_reads_is_part_of_the_key(self):
        """run.sh passes PT_SEED/PT_CHAR/PT_ROUNDS... straight into the wrapper, so two
        runs of the same scenario at different seeds are different runs. Without this,
        `PT_SEED=7 matrix.py run --scenarios fuzz_ch01` collides with the seed-1 key and
        is served a cached PASS it never earned."""
        base = self.fingerprint(env={})
        self.assertEqual(base, self.fingerprint(env={'PT_UNRELATED': 'x'}))
        self.assertNotEqual(base, self.fingerprint(env={'PT_SEED': '7'}))
        self.assertNotEqual(self.fingerprint(env={'PT_SEED': '7'}),
                            self.fingerprint(env={'PT_SEED': '8'}))

    def test_a_checkpoint_backed_scenario_keys_on_its_BUILDER_too(self):
        """ckpt_X is invoked by run.sh, not called from Lua, so it lands in neither the
        closure nor the shared residue -- editing the builder would leave the key still."""
        harness = HARNESS_FIXTURE + '''
scenarios.ckpt_thing = function()
    return onlyForB(7)
end
'''
        backed = manifest(scenarios={'alpha': {'checkpoint': 'thing'}}).resolve('alpha')
        before = self.fingerprint(harness=harness, scenario=backed)
        after = self.fingerprint(harness=harness.replace('onlyForB(7)', 'onlyForB(8)'),
                                 scenario=backed)
        self.assertNotEqual(before, after)

    def test_a_checkpointless_scenario_ignores_the_builders(self):
        harness = HARNESS_FIXTURE + '''
scenarios.ckpt_thing = function()
    return onlyForB(7)
end
'''
        self.assertEqual(self.fingerprint(harness=harness),
                         self.fingerprint(harness=harness.replace('onlyForB(7)', 'onlyForB(8)')))


class ScenarioScopes(unittest.TestCase):
    """Which build scopes a scenario's verdict can possibly depend on (#255 phase 2).

    A scenario's chapter dependency is a RANGE, not a point: it boots somewhere and plays
    FORWARD, and a checkpoint-backed scenario replays that whole chain (ckpt_ch02start
    replays ch00 -> ch01 -> ch02). Scoping one to its host chapter alone would be exactly
    the hand-declared impact map #255 exists to avoid.
    """

    def _scenario(self, **over):
        data = dict(rom='canonical', host_chapter=2)
        data.update(over)
        rom = data.pop('rom')
        m = manifest(rom_configs={'canonical': {}, 'testch': {'TESTCH': 1},
                                  'ch03boot': {'CH03BOOT': 1}, 'ch05boot': {'CH05BOOT': 1}},
                     scenarios={'s': dict(data, rom=rom)})
        return m.resolve('s')

    def scopes(self, observed=None, **over):
        return mx.scenario_scopes(self._scenario(**over), observed=observed)

    def test_global_is_always_in_scope(self):
        self.assertIn('global', self.scopes())

    def test_a_canonical_scenario_traverses_from_the_prologue(self):
        """It boots at New Game, so everything between the prologue and its own chapter is
        content it actually plays through."""
        self.assertEqual(self.scopes(rom='canonical', host_chapter=4, observed=[1, 2, 3, 4]),
                         {'global', 'chapter:prologue', 'chapter:ch01', 'chapter:ch02',
                          'chapter:ch03'})

    def test_a_boot_rom_scenario_starts_at_its_own_chapter(self):
        """The whole point: a CH05BOOT scenario never reaches the prologue, so a prologue
        edit cannot change its verdict."""
        self.assertEqual(self.scopes(rom='ch05boot', host_chapter=6, observed=[0, 6]),
                         {'global', 'chapter:ch05'})

    def test_a_boot_rom_scenario_does_not_depend_on_earlier_chapters(self):
        for earlier in ('chapter:prologue', 'chapter:ch01', 'chapter:ch04'):
            self.assertNotIn(earlier, self.scopes(rom='ch05boot', host_chapter=6,
                                                  observed=[0, 6]))

    def test_a_boot_rom_scenario_still_covers_a_range_it_plays_forward_into(self):
        self.assertEqual(self.scopes(rom='ch03boot', host_chapter=5, observed=[4, 5]),
                         {'global', 'chapter:ch03', 'chapter:ch04'})

    def test_the_testch_sandbox_depends_on_global_only(self):
        """The sandbox replaces the prologue on slot 1 and is written by a step whose name
        names no chapter, so its content is already inside `global`."""
        self.assertEqual(self.scopes(rom='testch', host_chapter=1), {'global'})

    def test_without_an_observation_the_range_runs_to_the_END(self):
        """matrix.yaml's `host_chapter` is the harness's PT_HOST_CHAPTER hint (default 1),
        NOT the last chapter a scenario plays -- `ch01win` boots at the prologue and plays
        into ch01 while declaring host_chapter 1. Treating it as an upper bound left ch01's
        map able to change without re-running the scenario that plays it. With nothing
        observed, the honest answer is everything from the boot point forward."""
        got = self.scopes(rom='canonical', host_chapter=1)
        for scope in ('chapter:prologue', 'chapter:ch01', 'chapter:ch05'):
            self.assertIn(scope, got)

    def test_an_OBSERVED_traversal_narrows_it_to_what_the_run_actually_visited(self):
        """Derived from what the scenario DID, the same way the build manifest is derived
        from what the builder did."""
        got = mx.scenario_scopes(self._scenario(rom='canonical', host_chapter=1),
                                 observed=[0, 1, 2])
        self.assertEqual(got, {'global', 'chapter:prologue', 'chapter:ch01'})

    def test_an_observed_traversal_always_keeps_the_boot_chapter(self):
        got = mx.scenario_scopes(self._scenario(rom='ch05boot', host_chapter=6), observed=[0])
        self.assertIn('chapter:ch05', got)

    def test_host_chapter_no_longer_bounds_anything(self):
        """It is the harness's PT_HOST_CHAPTER hint, not a statement about how far a
        scenario plays, and reading it as one was a stale-PASS bug (#272 review)."""
        self.assertEqual(self.scopes(rom='canonical', host_chapter=1),
                         self.scopes(rom='canonical', host_chapter=6))


class ObservedChapters(unittest.TestCase):
    """Which chapters a scenario ACTUALLY visited, read out of its own run log."""

    def test_it_reads_the_slots_the_run_reported(self):
        log = '[f000001] {"world":{"chapter":0}}\n[f000900] {"world":{"chapter":6}}\n'
        self.assertEqual(mx.observed_chapters(log), [0, 6])

    def test_a_log_with_no_chapter_records_observes_nothing(self):
        self.assertIsNone(mx.observed_chapters('RESULT: PASS -- nothing to see'))


class ScopedFingerprint(unittest.TestCase):
    MANIFEST = {
        'global': {'paths': ['a'], 'digest': 'G1'},
        'chapter:prologue': {'paths': ['b'], 'digest': 'P1'},
        'chapter:ch05': {'paths': ['c'], 'digest': 'C51'},
    }

    def setUp(self):
        self.m = manifest(rom_configs={'canonical': {}, 'ch05boot': {'CH05BOOT': 1}},
                          scenarios={'alpha': {'rom': 'ch05boot', 'host_chapter': 6}})

    def fingerprint(self, scenario_manifest, rom='romdigest'):
        return mx.scenario_fingerprint(self.m.resolve('alpha'), rom,
                                       harness_source=HARNESS_FIXTURE, driver='D', env={},
                                       scopes=scenario_manifest)

    def test_a_scope_it_does_not_depend_on_cannot_move_its_key(self):
        """The headline: a prologue edit must stop re-running ch05's scenarios."""
        moved = dict(self.MANIFEST, **{'chapter:prologue': {'paths': ['b'], 'digest': 'P2'}})
        self.assertEqual(self.fingerprint(self.MANIFEST), self.fingerprint(moved))

    def test_its_own_chapter_moving_moves_the_key(self):
        moved = dict(self.MANIFEST, **{'chapter:ch05': {'paths': ['c'], 'digest': 'C52'}})
        self.assertNotEqual(self.fingerprint(self.MANIFEST), self.fingerprint(moved))

    def test_global_moving_moves_the_key(self):
        moved = dict(self.MANIFEST, **{'global': {'paths': ['a'], 'digest': 'G2'}})
        self.assertNotEqual(self.fingerprint(self.MANIFEST), self.fingerprint(moved))

    def test_no_manifest_falls_back_to_the_whole_rom_key(self):
        """None means "we do not know what that build wrote". The phase 1 key is the
        conservative answer, and it must still respond to the ROM digest."""
        self.assertNotEqual(self.fingerprint(None, rom='r1'), self.fingerprint(None, rom='r2'))

    def test_a_scoped_key_ignores_the_monolithic_rom_digest(self):
        """Once the build has told us what it wrote, rom_input_hash is the coarse proxy we
        are replacing -- keeping it in the key would leave every task invalidating
        everything, which is the whole ceiling phase 2 lifts."""
        self.assertEqual(self.fingerprint(self.MANIFEST, rom='r1'),
                         self.fingerprint(self.MANIFEST, rom='r2'))

    def test_the_scoped_key_still_pins_the_decomp_and_engine_sources(self):
        """No scope can see them: we COMPILE the decomp's own sources and only patch a few,
        so a submodule bump touching an engine file no injector writes rebuilds the ROM and
        moves not one scope digest. Dropping rom_input_hash must not drop that pin."""
        a = mx.scenario_fingerprint(self.m.resolve('alpha'), 'r', harness_source=HARNESS_FIXTURE,
                                    driver='D', env={}, scopes=self.MANIFEST, engine='E1')
        b = mx.scenario_fingerprint(self.m.resolve('alpha'), 'r', harness_source=HARNESS_FIXTURE,
                                    driver='D', env={}, scopes=self.MANIFEST, engine='E2')
        self.assertNotEqual(a, b)

    def test_a_scope_missing_from_the_manifest_is_not_silently_ignored(self):
        """A chapter the scenario depends on that the build never wrote must still be
        recorded as absent, or "the step vanished" and "the step is unchanged" are the
        same key."""
        without = {k: v for k, v in self.MANIFEST.items() if k != 'chapter:ch05'}
        self.assertNotEqual(self.fingerprint(self.MANIFEST), self.fingerprint(without))


class DriverModuleReach(unittest.TestCase):
    """A dofile'd module is reached by the scenarios that USE it, not by all of them.

    Lumping every driver file into one digest meant an edit to `clearbot.lua` -- which only
    the clear* scenarios touch -- re-ran ch05arena. Same trap #255 warns about for
    harness.lua, one file over.
    """

    def test_the_bindings_are_read_out_of_harness_lua(self):
        """Derived from the dofile lines, not a hand-kept table."""
        mods = mx.driver_modules()
        self.assertEqual(mods.get('clearbot.lua'), 'CLEARBOT')
        self.assertEqual(mods.get('controller.lua'), 'Controller')
        self.assertEqual(mods.get('pathing.lua'), 'PATHING')

    def test_a_generated_table_has_no_binding_and_is_not_a_module(self):
        self.assertNotIn('symbols.lua', mx.driver_modules())

    def test_the_binding_LINE_itself_does_not_count_as_a_use(self):
        """`local CLEARBOT = dofile(...)` is top-level, so it lands in the shared harness
        text. Counting it would make every module reachable by everyone and the split would
        do nothing at all."""
        reached = mx.scenario_driver_modules('ch05arena')
        self.assertNotIn('clearbot.lua', reached)

    def test_a_scenario_reaches_the_modules_it_actually_uses(self):
        self.assertIn('clearbot.lua', mx.scenario_driver_modules('clear_ch01'))

    def test_every_verdict_scenario_reaches_the_classifier(self):
        """controller.lua really is consulted by every guarded input -- that part of the
        old lumping was right."""
        for name in ('ch05arena', 'clear_ch01', 'ch01win'):
            self.assertIn('controller.lua', mx.scenario_driver_modules(name))

    def test_editing_an_unreached_module_does_not_move_the_key(self):
        m = manifest(scenarios={'ch05arena': {}})
        s = m.resolve('ch05arena')
        base = mx.scenario_fingerprint(s, 'r', env={})
        moved = mx.scenario_fingerprint(s, 'r', env={},
                                        driver_files={'clearbot.lua': 'CHANGED'})
        self.assertEqual(base, moved)

    def test_editing_a_reached_module_moves_the_key(self):
        m = manifest(scenarios={'ch05arena': {}})
        s = m.resolve('ch05arena')
        base = mx.scenario_fingerprint(s, 'r', env={})
        moved = mx.scenario_fingerprint(s, 'r', env={},
                                        driver_files={'controller.lua': 'CHANGED'})
        self.assertNotEqual(base, moved)

    def test_run_sh_stays_global(self):
        """It is the launcher: it decides fps, deadline and the wrapper for every run."""
        m = manifest(scenarios={'ch05arena': {}})
        s = m.resolve('ch05arena')
        self.assertNotEqual(mx.scenario_fingerprint(s, 'r', env={}),
                            mx.scenario_fingerprint(s, 'r', env={},
                                                    driver_files={'run.sh': 'CHANGED'}))


class DriverSource(unittest.TestCase):
    """Everything OUTSIDE harness.lua that can change what a scenario does."""

    def setUp(self):
        self.files = mx.driver_source()
        self.text = '\n'.join('%s\n%s' % (k, v) for k, v in sorted(self.files.items()))

    def test_it_covers_the_classifier_every_guarded_input_consults(self):
        self.assertIn('function M.classify', self.text)

    def test_it_covers_run_sh(self):
        """run.sh decides fps, deadline, checkpoint handling and the wrapper the
        emulator actually loads."""
        self.assertIn('run_mgba', self.text)

    def test_it_leaves_out_the_GENERATED_symbol_tables(self):
        """symbols.lua/procscr.lua are rewritten by run.sh AFTER the fingerprint is taken,
        so hashing them makes every engine change cost TWO re-runs before the cache
        converges -- and alternating ROM configs may never converge at all. Their content
        is already implied: the ELF comes from rom_input_hash, the emitter is gen_symbols.py
        below, and both are in the key."""
        self.assertNotIn('gArenaState = 0x', self.text)   # a symbols.lua row
        self.assertNotIn('ProcScr_AsnycKeyStatus', self.text)   # a procscr.lua row

    def test_it_leaves_out_harness_itself(self):
        """harness.lua is keyed by CLOSURE, not whole-file -- including it here would
        undo the entire point of the closure."""
        self.assertNotIn('scenarios.ch05arena', self.text)

    def test_it_covers_the_symbol_GENERATOR_too(self):
        """symbols.lua/procscr.lua are regenerated by run.sh AFTER the fingerprint is
        taken, so hashing only the generated files would let an edit to what they contain
        slip past the key for one run."""
        self.assertIn('def parse_nm', self.text)

    def test_it_leaves_out_the_lua_test_modules(self):
        self.assertNotIn('test_controller', self.text)

    def test_every_PT_var_run_sh_reads_is_in_the_key(self):
        """A hand-kept list rots silently, and rotting HERE means a cached PASS served
        for a run the knob would have changed. PT_HOST_CHAPTER is the one exception:
        matrix.py sets it FROM the manifest entry, which export_env already covers."""
        with open(mx.RUN_SH) as fh:
            used = set(re.findall(r'PT_[A-Z_]+', fh.read())) - {'PT_HOST_CHAPTER'}
        self.assertTrue(used)
        self.assertEqual(used - set(mx.PLAYTEST_ENV_KEYS), set(),
                         'run.sh reads a PT_ knob the verdict key does not see')


class VerdictCacheStore(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp()
        self.artifacts = os.path.join(self.dir, 'playtest-alpha')
        os.makedirs(self.artifacts)
        with open(os.path.join(self.artifacts, 'playtest.log'), 'w') as fh:
            fh.write('[f000001] RESULT: PASS -- proved it\n')
        self.addCleanup(shutil.rmtree, self.dir, True)

    def outcome(self, verdict='PASS', name='alpha'):
        return mx.Outcome(scenario=name, rom='canonical', verdict=verdict, seconds=12.0,
                          artifacts=self.artifacts)

    def test_a_pass_round_trips(self):
        mx.store_cached_verdict('alpha', 'fp1', self.outcome(), cache_dir=self.dir)
        hit = mx.load_cached_verdict('alpha', 'fp1', cache_dir=self.dir)
        self.assertEqual(hit['verdict'], 'PASS')
        self.assertEqual(hit['seconds'], 12.0)

    def test_a_fail_is_NEVER_cached(self):
        """A flaky red must always re-run. Only green is skippable."""
        mx.store_cached_verdict('alpha', 'fp1', self.outcome('FAIL'), cache_dir=self.dir)
        self.assertIsNone(mx.load_cached_verdict('alpha', 'fp1', cache_dir=self.dir))

    def test_an_error_is_never_cached(self):
        mx.store_cached_verdict('alpha', 'fp1', self.outcome('ERROR'), cache_dir=self.dir)
        self.assertIsNone(mx.load_cached_verdict('alpha', 'fp1', cache_dir=self.dir))

    def test_a_different_fingerprint_is_a_miss(self):
        mx.store_cached_verdict('alpha', 'fp1', self.outcome(), cache_dir=self.dir)
        self.assertIsNone(mx.load_cached_verdict('alpha', 'fp2', cache_dir=self.dir))

    def test_no_fingerprint_is_a_miss_and_stores_nothing(self):
        mx.store_cached_verdict('alpha', None, self.outcome(), cache_dir=self.dir)
        self.assertIsNone(mx.load_cached_verdict('alpha', None, cache_dir=self.dir))

    def test_a_cached_pass_stays_INSPECTABLE(self):
        """A cached green that cannot be looked at is a green nobody can audit."""
        mx.store_cached_verdict('alpha', 'fp1', self.outcome(), cache_dir=self.dir)
        hit = mx.load_cached_verdict('alpha', 'fp1', cache_dir=self.dir)
        kept = os.path.join(hit['artifacts'], 'playtest.log')
        self.assertTrue(os.path.isfile(kept), 'the run log travels with the verdict')
        with open(kept) as fh:
            self.assertIn('RESULT: PASS', fh.read())

    def test_a_new_fingerprint_evicts_the_old_slot(self):
        """One slot per scenario: the cache tracks HEAD, not history."""
        mx.store_cached_verdict('alpha', 'fp1', self.outcome(), cache_dir=self.dir)
        mx.store_cached_verdict('alpha', 'fp2', self.outcome(), cache_dir=self.dir)
        self.assertIsNone(mx.load_cached_verdict('alpha', 'fp1', cache_dir=self.dir))
        self.assertIsNotNone(mx.load_cached_verdict('alpha', 'fp2', cache_dir=self.dir))

    def test_evicting_one_scenario_leaves_the_others_alone(self):
        mx.store_cached_verdict('beta', 'fp1', self.outcome(name='beta'), cache_dir=self.dir)
        mx.store_cached_verdict('alpha', 'fp2', self.outcome(), cache_dir=self.dir)
        self.assertIsNotNone(mx.load_cached_verdict('beta', 'fp1', cache_dir=self.dir))

    def test_a_corrupt_slot_is_a_miss_not_a_crash(self):
        os.makedirs(self.dir, exist_ok=True)
        with open(os.path.join(self.dir, 'alpha-fp1.json'), 'w') as fh:
            fh.write('{ not json')
        self.assertIsNone(mx.load_cached_verdict('alpha', 'fp1', cache_dir=self.dir))


class CacheScope(unittest.TestCase):
    """Which scenarios may be served from cache at all."""

    def test_only_verdict_scenarios_are_cached(self):
        """A `record` scenario exists to REFILL /tmp/playtest-<name> with motion frames,
        and make_gif.py reads that path by hand. Skipping the run leaves it stale, so the
        GIF is built from whatever ran last."""
        m = manifest(scenarios={'a': {}, 'recordx': {'kind': 'record'},
                                'probe': {'kind': 'diagnostic'}})
        cache = mx.VerdictCache([m.resolve(n) for n in ('a', 'recordx', 'probe')])
        self.assertEqual(set(cache.fingerprints), {'a'},
                         'only a verdict scenario is a candidate for being skipped')


class FailureInvalidates(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.dir, True)

    def outcome(self, verdict):
        return mx.Outcome('alpha', 'canonical', verdict, 1.0, '')

    def test_a_fresh_FAIL_evicts_the_stale_pass_for_the_same_key(self):
        """Same inputs, and it just failed. Leaving the PASS in place makes the next
        matrix run report green for a scenario that is red right now."""
        mx.store_cached_verdict('alpha', 'fp1', self.outcome('PASS'), cache_dir=self.dir)
        mx.store_cached_verdict('alpha', 'fp1', self.outcome('FAIL'), cache_dir=self.dir)
        self.assertIsNone(mx.load_cached_verdict('alpha', 'fp1', cache_dir=self.dir))

    def test_a_fresh_FAIL_evicts_an_older_key_too(self):
        mx.store_cached_verdict('alpha', 'fp1', self.outcome('PASS'), cache_dir=self.dir)
        mx.store_cached_verdict('alpha', 'fp2', self.outcome('FAIL'), cache_dir=self.dir)
        self.assertIsNone(mx.load_cached_verdict('alpha', 'fp1', cache_dir=self.dir))


class IncrementalExecution(unittest.TestCase):
    """`gate: 17/17 PASS -- 2 ran, 15 cached`. What must stop growing is the number
    of scenarios that EXECUTE per change, not the number that exist."""

    def run_plan(self, m, names, verdicts, cached=()):
        self.built, self.ran = [], []

        def build(rom, flags):
            self.built.append(rom)
            return True

        def run_scenario(scn):
            self.ran.append(scn.name)
            return mx.Outcome(scenario=scn.name, rom=scn.rom, verdict=verdicts[scn.name],
                              seconds=1.0, artifacts='/tmp/playtest-' + scn.name)

        def lookup_cached(scn):
            if scn.name not in cached:
                return None
            return mx.Outcome(scenario=scn.name, rom=scn.rom, verdict='PASS', seconds=9.0,
                              artifacts='/cache/' + scn.name, cached=True)

        return mx.execute(m.plan(names), build=build, run_scenario=run_scenario,
                          lookup_cached=lookup_cached)

    def test_a_cached_scenario_does_not_execute(self):
        m = manifest(scenarios={'a': {}, 'b': {}})
        self.run_plan(m, ['a', 'b'], {'b': 'PASS'}, cached=('a',))
        self.assertEqual(self.ran, ['b'])

    def test_a_cached_scenario_still_reports_its_verdict(self):
        m = manifest(scenarios={'a': {}, 'b': {}})
        report = self.run_plan(m, ['a', 'b'], {'b': 'PASS'}, cached=('a',))
        self.assertEqual([(o.scenario, o.verdict) for o in report.outcomes],
                         [('a', 'PASS'), ('b', 'PASS')])

    def test_the_manifest_order_survives_caching(self):
        m = manifest(scenarios={'a': {}, 'b': {}, 'c': {}})
        report = self.run_plan(m, ['a', 'b', 'c'], {'b': 'PASS'}, cached=('a', 'c'))
        self.assertEqual([o.scenario for o in report.outcomes], ['a', 'b', 'c'])

    def test_a_FULLY_cached_group_never_builds_its_rom(self):
        """The biggest win in the whole feature: a doc-only change costs no `make`
        and no emulator at all."""
        m = manifest(scenarios={'a': {}, 'b': {}})
        report = self.run_plan(m, ['a', 'b'], {}, cached=('a', 'b'))
        self.assertEqual(self.built, [])
        self.assertEqual(report.builds, 0)
        self.assertTrue(report.ok)

    def test_a_partly_cached_group_still_builds_once(self):
        m = manifest(scenarios={'a': {}, 'b': {}})
        self.run_plan(m, ['a', 'b'], {'b': 'PASS'}, cached=('a',))
        self.assertEqual(self.built, ['canonical'])

    def test_the_report_counts_ran_and_cached(self):
        m = manifest(scenarios={'a': {}, 'b': {}, 'c': {}})
        report = self.run_plan(m, ['a', 'b', 'c'], {'b': 'PASS'}, cached=('a', 'c'))
        self.assertEqual((report.ran, report.cached), (1, 2))

    def test_the_cache_is_consulted_AGAIN_after_a_build(self):
        """Phase 2: a scope manifest only exists once the build that produced it has run,
        so a configuration whose ROM inputs moved cannot be keyed on scopes until it is
        built. Building must therefore be able to REMOVE work, not just precede it -- a
        ch05 edit rebuilds the ROM and then re-runs only ch05's scenarios."""
        m = manifest(scenarios={'a': {}, 'b': {}})
        self.built, self.ran, self.refreshed = [], [], []
        cached = set()

        def build(rom, flags):
            self.built.append(rom)
            cached.add('a')          # the fresh manifest shows `a` untouched after all
            return True

        def run_scenario(scn):
            self.ran.append(scn.name)
            return mx.Outcome(scn.name, scn.rom, 'PASS', 1.0, '')

        def lookup_cached(scn):
            if scn.name not in cached:
                return None
            return mx.Outcome(scn.name, scn.rom, 'PASS', 9.0, '', cached=True)

        report = mx.execute(m.plan(['a', 'b']), build=build, run_scenario=run_scenario,
                            lookup_cached=lookup_cached,
                            after_build=lambda rom: self.refreshed.append(rom))
        self.assertEqual(self.refreshed, ['canonical'])
        self.assertEqual(self.ran, ['b'], 'the post-build re-check must drop `a`')
        self.assertEqual((report.ran, report.cached), (1, 1))

    def test_a_build_that_satisfies_EVERYTHING_runs_nothing(self):
        m = manifest(scenarios={'a': {}, 'b': {}})
        self.built, self.ran = [], []
        cached = set()

        def build(rom, flags):
            self.built.append(rom)
            cached.update({'a', 'b'})
            return True

        def run_scenario(scn):
            self.ran.append(scn.name)
            return mx.Outcome(scn.name, scn.rom, 'PASS', 1.0, '')

        def lookup_cached(scn):
            if scn.name not in cached:
                return None
            return mx.Outcome(scn.name, scn.rom, 'PASS', 9.0, '', cached=True)

        report = mx.execute(m.plan(['a', 'b']), build=build, run_scenario=run_scenario,
                            lookup_cached=lookup_cached)
        self.assertEqual(self.built, ['canonical'], 'it still had to build to find out')
        self.assertEqual(self.ran, [])
        self.assertEqual((report.ran, report.cached), (0, 2))

    def test_no_cache_lookup_at_all_runs_everything(self):
        m = manifest(scenarios={'a': {}, 'b': {}})
        self.run_plan(m, ['a', 'b'], {'a': 'PASS', 'b': 'PASS'})
        self.assertEqual(self.ran, ['a', 'b'])


class CachedRowsReadDistinctly(unittest.TestCase):
    """A cached green must never read as a fresh one."""

    def report(self):
        return mx.Report([mx.Outcome('a', 'canonical', 'PASS', 9.0, '/cache/a', cached=True),
                          mx.Outcome('b', 'canonical', 'PASS', 11.0, '/tmp/playtest-b')],
                         builds=1, duplicate_builds=0, seconds=20.0)

    def test_the_table_marks_which_rows_were_cached(self):
        body = mx.render_table(self.report())
        cached_row = [l for l in body.splitlines() if '/cache/a' in l][0]
        fresh_row = [l for l in body.splitlines() if '/tmp/playtest-b' in l][0]
        self.assertIn('cached', cached_row)
        self.assertNotIn('cached', fresh_row)

    def test_the_summary_reports_how_many_ran_and_how_many_were_cached(self):
        self.assertIn('1 ran, 1 cached', mx.render_table(self.report()))

    def test_results_json_records_the_cached_flag(self):
        self.assertEqual([o['cached'] for o in self.report().as_dict()['outcomes']],
                         [True, False])


if __name__ == '__main__':
    unittest.main()
