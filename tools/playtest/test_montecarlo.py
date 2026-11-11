"""montecarlo.py: the bot's run pool (#510 step 9 PR F, Task 11), its paired verdict and the
cell driver (Task 12)."""
import contextlib
import io
import json
import multiprocessing
import os
import re
import shutil
import sys
import tempfile
import time
import unittest
from unittest import mock

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import matrix  # noqa: E402
import montecarlo as mc  # noqa: E402


def _append_many(path, who, n):
    # a record long enough that a torn write would show: 4 KB of payload
    for i in range(n):
        mc.append_record(path, {'who': who, 'i': i, 'pad': 'x' * 4096})


# A BOTRUN record as botrun.lua's finish() writes it today (v1), and as the #510 step 9 plan's
# data model extends it (v2): the extra fields are added beside v1's, so every reader of v1 must
# read a v2 line the same way. Each later PR that writes a v2 field reads it from V2.
V1 = {'game': 'vanilla', 'rom_hash': 'c25b145e3745', 'chapter': 3, 'mode': 'normal', 'seed': 1,
      'attempt': 1, 'style': {'aggression': 'careful'}, 'claims_played': [],
      'claims_unplayed': [], 'outcome': 'won', 'turns': 9, 'why': 'the chapter advanced',
      'frames': 28445, 'deaths': [{'charId': 0x42, 'faction': 'green', 'turn': 4,
                                   'killer': 0x81, 'phase': 'enemy'}],
      'kills': {'1': 3}, 'deployed': [1, 2], 'bot_faults': [], 'watch_faults': [],
      'thefts': [], 'plans': {'made': 40, 'kept': 31}, 'bag': [], 'stalls': 1,
      'explore': {}, 'recruits': {'owed': [0x30], 'joined': [0x30]},
      'clear': {'won': True, 'lost': [{'charId': 0x42, 'faction': 'green', 'turn': 4,
                                       'killer': 0x81}],
                'recruits_missing': [], 'rewards_missing': [], 'stolen': []},
      'clean': False, 'costs': {'cpu_s': 12.2, 'sandbox_calls': 900}}
_GRADED = [dict(V1['deaths'][0], predicted=0.02, cap=0.01, over_cap=True,
                flags={'reinforcement': False, 'fog': False, 'boss': True, 'player_phase': False},
                cause='over_cap', detail=None, plan_ref=17, escort=False)]
V2 = dict({k: v for k, v in V1.items() if k != 'stalls'}, board_repeats=1,
          instrument='0123456789ab+suite-1', env_status='clean', deaths=_GRADED,
          clear=dict(V1['clear'], lost=_GRADED),
          first_death_turn=4, greens={'escort_deaths': [], 'allied_deaths': [0x42]},
          missed_recruits=[], missed_rewards=[], seize_skips=[], stall_events=[],
          turns_to_win=9, anomalies=[],
          lookahead={'decisions': 40, 'triggered': 3, 'extended': 3, 'skipped_budget': 0,
                     'calls': 12, 'cpu_s': 0.8})


class Records(unittest.TestCase):
    def test_parse_botrun_line(self):
        text = '\n'.join([
            'engine noise',
            'BOTRUN {"attempt": 2, "outcome": "won", "clean": true}',
            '[f085128] BOTRUN {"attempt": 3, "outcome": "lost"}',
            'CAMPAIGN {"outcome": "played"}',
        ])
        got = mc.parse_lines(text, mc.BOTRUN)
        self.assertEqual([r['attempt'] for r in got], [2, 3])
        self.assertEqual(mc.parse_lines(text, mc.CAMPAIGN), [{'outcome': 'played'}])

    def test_a_v2_record_reads_as_its_v1(self):
        # the plan's contract: parsers ignore fields they do not know, so v1 records still parse;
        # a v2 line says what v1 says and more (T018: its graded causes)
        text = '\n'.join('[f9] BOTRUN ' + json.dumps(r) for r in (V1, V2))
        v1, v2 = mc.parse_lines(text, mc.BOTRUN)
        self.assertEqual((v1, v2), (V1, V2))
        self.assertIn(mc.spoiled(v1), mc.spoiled(v2))
        self.assertIn('lost 0x42 (green, turn 4, to 0x81)', mc.attempt_line(v1, set()))
        r1, r2 = mc.chapter_result([v1], 3), mc.chapter_result([v2], 3)
        self.assertEqual((r1['died'], r1['clean']), (r2['died'], r2['clean']))
        self.assertEqual(mc.first_clean([v1]), mc.first_clean([v2]))

    def test_a_graded_line_names_causes_reasons_and_anomalies(self):
        # T018: each death's cause, prediction and flags; each missed goal's reason; each
        # anomaly with its story command; stalls
        r = dict(V2, clean=False, missed_recruits=[{'charId': 0x30, 'reason': 'talk_skipped'}],
                 missed_rewards=[{'x': 3, 'y': 7, 'kind': 'visit', 'reason': 'skipped'}],
                 clear=dict(V2['clear'], recruits_missing=[0x30]),
                 stall_events=[{'turn': 6, 'kind': 'idle_3'}],
                 anomalies=[{'kind': 'seize_delay', 'turn': 5,
                             'narrate': mc.narrate('t.jsonl.gz', 5)}])
        line = mc.attempt_line(r, set())
        self.assertIn('lost 0x42 (green, turn 4, to 0x81) over_cap at 2.0%, boss', line)
        self.assertIn('missed 0x30 (talk_skipped)', line)
        self.assertIn('village 3,7 skipped', line)
        self.assertIn('[stalls: idle_3 turn 6]', line)
        self.assertIn('anomaly: seize_delay turn 5 -> python3 tools/playtest/montecarlo.py '
                      'story t.jsonl.gz --turn 5', line)
        other = dict(_GRADED[0], cause='other', detail='unrevealed_killer', predicted=0,
                     flags={})
        self.assertIn('other (blindspot: unrevealed_killer) at 0.0%', mc.death(other))
        lost = dict(V2, outcome='lost', deaths=[other])
        self.assertIn('deaths: lost 0x42', mc.attempt_line(lost, set()))
        crashed = mc.attempt_line(dict(lost, outcome='crashed', why='Lua error'), set())
        self.assertIn('(Lua error) (deaths: lost 0x42', crashed)   # labelled apart

    def test_a_cause_botrun_does_not_name_is_refused(self):
        # the names are botrun.lua's M.CAUSES and M.DETAILS, read from its text
        causes, details = mc.botrun_names()
        self.assertEqual(causes, ('over_cap', 'reinforcement', 'fog', 'rng_tail', 'other'))
        self.assertEqual(details['forecast_desync'], 'sandbox_fault')
        with self.assertRaises(ValueError):
            mc.death(dict(_GRADED[0], cause='bad_luck'))

    def test_append_is_one_line_per_run(self):
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, 'runs.jsonl')
            procs = [multiprocessing.Process(target=_append_many, args=(path, w, 100))
                     for w in ('a', 'b')]
            for p in procs:
                p.start()
            for p in procs:
                p.join()
            with open(path) as fh:
                lines = fh.read().splitlines()
            self.assertEqual(len(lines), 200)
            recs = [json.loads(line) for line in lines]   # every line parses whole
            for w in ('a', 'b'):
                self.assertEqual(sorted(r['i'] for r in recs if r['who'] == w), list(range(100)))


_RUN_ROOT = None


def setUpModule():
    # no test may prune or delete the real /tmp's run dirs
    global _RUN_ROOT
    _RUN_ROOT = mc.RUN_ROOT
    mc.RUN_ROOT = tempfile.mkdtemp()


def tearDownModule():
    shutil.rmtree(mc.RUN_ROOT, True)
    mc.RUN_ROOT = _RUN_ROOT


class RunDirs(unittest.TestCase):
    """#574: a passing run leaves no dir behind; a failing one's is kept, the newest N."""

    def tmp(self):
        d = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, d, True)
        return d

    def setUp(self):
        self.root, self.d = self.tmp(), self.tmp()
        self.out = os.path.join(self.d, 'runs.jsonl')

    def launch(self, line):
        """A fake run.sh: a tagged run dir with a ROM and a trace, and `line` (a format taking
        the task's seed) as its stdout."""
        def launch(task, tag, log_path):
            where = os.path.join(self.root, 'playtest-campaign@' + tag)
            os.makedirs(where)
            with open(os.path.join(where, 'fireemblem8.gba'), 'wb') as fh:
                fh.write(b'rom')
            with open(os.path.join(where, 'trace-1.jsonl'), 'w') as fh:
                fh.write('{"t": "start"}\n')
            return (line % task['seed'] if line else ''), where
        return launch

    def pool(self, outcome, n=1, keep=mc.KEEP_FAILED, extra=''):
        line = None if outcome is None else (
            'BOTRUN {"seed": %%d, "outcome": "%s", "trace": "trace-1.jsonl"%s}\n'
            % (outcome, extra))
        return list(mc.Pool(jobs=2, out=self.out, launch=self.launch(line),
                            run_root=self.root, keep_failed=keep).run(
            [{'seed': s} for s in range(1, n + 1)]))

    def test_a_passing_run_leaves_no_dir_and_keeps_its_trace(self):
        recs = self.pool('won', n=3)
        self.assertEqual(os.listdir(self.root), [])
        for r in recs:
            self.assertTrue(os.path.isfile(os.path.join(self.d, r['trace'])),
                            'the trace is filed before the dir goes')
            self.assertNotIn('run_dir', r, 'a record never names a dir that is gone')
        with open(self.out) as fh:
            self.assertEqual(len(fh.read().splitlines()), 3, 'records are kept on disk')

    def test_a_failing_run_keeps_its_dir_marked(self):
        recs = self.pool('crashed')
        self.assertTrue(os.path.isdir(recs[0]['run_dir']))
        self.assertTrue(os.path.isfile(os.path.join(recs[0]['run_dir'], mc.FAILED_MARK)))
        self.assertTrue(os.path.isfile(os.path.join(recs[0]['run_dir'], 'fireemblem8.gba')))

    def test_a_stall_or_a_fault_is_failing(self):
        for outcome, extra in (('stuck', ''), ('won', ', "env_status": {"fault": "watch"}')):
            recs = self.pool(outcome, extra=extra)
            self.assertTrue(os.path.isdir(recs[0]['run_dir']), outcome + extra)

    def test_a_campaign_passes_on_its_own_answer_and_fails_on_a_crash(self):
        for end, passed in (('played', True), ('done', True), ('bot_fault', True),
                            ('infeasible', True), ('crashed', False), ('no_style', False)):
            text = ('BOTRUN {"seed": 1, "chapter": 2, "outcome": "won"}\n'
                    'CAMPAIGN {"outcome": "%s"}\n' % end)
            self.assertEqual(mc.passing(mc.records_of({}, text, '/w', '/x.log')), passed, end)

    def test_only_the_newest_failing_dirs_are_kept(self):
        self.pool('crashed', n=5, keep=2)
        self.assertEqual(len(os.listdir(self.root)), 2)

    def test_a_worker_that_left_no_record_is_failing(self):
        recs = self.pool(None)
        self.assertTrue(os.path.isdir(recs[0]['run_dir']))

    def test_a_cleanup_error_never_costs_the_run(self):
        """A full disk while marking a failing run is said, and the Pool goes on."""
        where = self.launch(None)({'seed': 1}, 'z', '/x.log')[1]
        with mock.patch.object(mc, 'prune_runs', side_effect=OSError(28, 'No space left')), \
                contextlib.redirect_stderr(io.StringIO()) as err:
            mc.settle_run_dir(where, False, self.root)
        self.assertIn('No space left', err.getvalue())

    def make(self, name, age, failed=False, deep=False):
        where = os.path.join(self.root, name)
        os.makedirs(os.path.join(where, 'shots'))
        then = time.time() - age
        files = ['mgba-stdout.log'] + ([mc.FAILED_MARK] if failed else [])
        for f in files:
            open(os.path.join(where, f), 'w').close()
            os.utime(os.path.join(where, f), (then, then))
        if deep:   # a live run writing only into a subdir
            open(os.path.join(where, 'shots', '01.png'), 'w').close()
        os.utime(os.path.join(where, 'shots'), (then, then))
        os.utime(where, (then, then))
        return where

    def test_the_next_run_prunes_dead_and_surplus_dirs(self):
        dead = self.make('playtest-campaign@1-1-0', age=2 * mc.STALE_S)
        live = self.make('playtest-campaign@1-1-1', age=60)
        deep = self.make('playtest-campaign@1-1-2', age=2 * mc.STALE_S, deep=True)
        old = [self.make('playtest-campaign@2-1-%d' % i, age=3600 + i, failed=True)
               for i in range(4)]
        other = self.make('playtest-ch01', age=2 * mc.STALE_S)   # untagged: not the pool's
        self.pool('won', keep=2)
        left = set(os.path.join(self.root, n) for n in os.listdir(self.root))
        self.assertEqual(left, {live, deep, old[0], old[1], other})
        self.assertFalse(os.path.exists(dead))

    def test_two_pools_never_share_a_tag(self):
        """`cell` makes a Pool per look: a reused tag would overwrite a kept failing dir."""
        first = self.pool('crashed')[0]['run_dir']
        second = self.pool('crashed')[0]['run_dir']
        self.assertNotEqual(first, second)
        self.assertTrue(os.path.isdir(first) and os.path.isdir(second))

    def test_a_dir_outside_the_run_root_is_never_touched(self):
        where = os.path.join(self.tmp(), 'playtest-campaign@x')
        os.makedirs(where)
        mc.settle_run_dir(where, True, self.root)
        self.assertTrue(os.path.isdir(where))


class Workers(unittest.TestCase):
    def run_pool(self, launch, tasks, jobs=2):
        d = tempfile.mkdtemp()
        out = os.path.join(d, 'runs.jsonl')
        recs = list(mc.Pool(jobs=jobs, out=out, launch=launch).run(tasks))
        with open(out) as fh:
            kept = [json.loads(line) for line in fh]
        return recs, kept

    def test_each_record_carries_its_workers_wall_time_and_its_own_store(self):
        d = tempfile.mkdtemp()
        other = os.path.join(d, 'other.jsonl')

        def launch(task, tag, log_path):
            if task['seed'] == 2:
                raise RuntimeError('died')
            return 'BOTRUN {"seed": %d, "outcome": "won"}\n' % task['seed'], '/tmp/x'
        recs, kept = self.run_pool(launch, [{'seed': 1}, {'seed': 2, 'out': other}])
        self.assertTrue(all(isinstance(r['wall_s'], float) for r in recs))
        self.assertEqual([r['seed'] for r in kept], [1])
        with open(other) as fh:
            crashed = json.loads(fh.read())
        self.assertEqual(crashed['env_status'], {'fault': 'crash', 'outcome_dependent': True})

    def test_a_campaign_end_with_no_bot_record_says_its_environment_failed(self):
        # campaign.lua's own crashes (load, arrive, save, cap) end before the bot plays
        only = mc.records_of({}, 'CAMPAIGN {"outcome": "crashed", "why": "load: x"}', '/tmp/w',
                             '/nonexistent.log')
        self.assertEqual(only[0]['env_status'], mc.unread())
        both = mc.records_of({}, 'BOTRUN {"outcome": "won", "env_status": "clean"}\n'
                             'CAMPAIGN {"outcome": "played"}', '/tmp/w', '/nonexistent.log')
        self.assertEqual([r.get('env_status') for r in both], ['clean', None])

    def test_a_campaigns_own_answer_is_no_environment_fault(self):
        # campaign.lua ends no_style (fewer styles than the attempt asked) before any bot plays
        rec = mc.records_of({}, 'CAMPAIGN {"outcome": "no_style"}', '/tmp/w', '/x.log')[0]
        self.assertNotIn('env_status', rec)
        self.assertIsNone(mc.attempt_line(dict(rec, kind='campaign', task_attempt=3), set()))

    def test_crashed_worker_is_recorded(self):
        def launch(task, tag, log_path):
            if task['campaign']['attempt'] == 2:
                raise RuntimeError('mgba-headless exited early')
            k = task['campaign']['attempt']
            return 'BOTRUN {"attempt": %d, "outcome": "won", "clean": true}\n' % k, '/tmp/x'
        recs, kept = self.run_pool(launch, mc.attempt_tasks({'from': 4}, 3))
        self.assertEqual(len(kept), 3, 'every worker leaves one record')
        dead = [r for r in kept if r['outcome'] == 'crashed']
        self.assertEqual(len(dead), 1)
        self.assertEqual(dead[0]['attempt'], 2)
        self.assertIn('mgba-headless exited early', dead[0]['why'])
        self.assertTrue(dead[0]['log'].endswith('.log'), 'it names its log')

    def test_a_worker_with_no_record_is_crashed_and_its_run_dir_named(self):
        recs, kept = self.run_pool(lambda t, tag, lp: ('', '/tmp/playtest-campaign@' + tag),
                                   mc.attempt_tasks({'from': 4}, 1))
        self.assertEqual(kept[0]['outcome'], 'crashed')
        self.assertTrue(kept[0]['run_dir'].startswith('/tmp/playtest-campaign@'))

    def test_a_k_past_every_style_is_no_style(self):
        # campaign.lua's stop(): the campaign's last line, without a chapter
        text = ('CAMPAIGN {"chapter": 4, "attempts": 2}\n'
                'CAMPAIGN {"outcome": "no_style", "why": "chapter 4 has 2 styles, not 3"}\n')
        recs, kept = self.run_pool(lambda t, tag, lp: (text, '/tmp/x'),
                                   mc.attempt_tasks({'from': 4}, 1))
        self.assertEqual(kept[0]['outcome'], 'no_style')
        self.assertEqual(kept[0]['kind'], 'campaign')
        self.assertIn('2 styles', kept[0]['why'])

    def test_each_worker_gets_its_own_tag(self):
        tags = []

        def launch(task, tag, log_path):
            tags.append(tag)
            return '', '/tmp/x'
        self.run_pool(launch, mc.attempt_tasks({'from': 4}, 4), jobs=4)
        self.assertEqual(len(set(tags)), 4)
        for t in tags:
            self.assertRegex(t, r'^[A-Za-z0-9_-]+$', "run.sh's PT_RUN_TAG alphabet")


class Attempts(unittest.TestCase):
    def test_tasks_number_the_attempts_from_the_saved_start(self):
        tasks = mc.attempt_tasks({'id': 'c', 'from': 4, 'last': [4]}, 3, seed=5)
        self.assertEqual([t['campaign']['attempt'] for t in tasks], [1, 2, 3])
        self.assertEqual({t['campaign']['from'] for t in tasks}, {4})
        self.assertEqual({t['seed'] for t in tasks}, {5})

    def test_a_run_that_crashed_before_its_bot_reported_is_listed(self):
        said = set()
        ok = {'attempt': 1, 'outcome': 'won', 'turns': 8, 'frames': 30919, 'task_attempt': 1}
        self.assertIn('30919 frames', mc.attempt_line(ok, said))
        self.assertIsNone(mc.attempt_line({'kind': 'campaign', 'outcome': 'won',
                                           'task_attempt': 1}, said))
        self.assertIsNone(mc.attempt_line({'kind': 'campaign', 'outcome': 'crashed',
                                           'task_attempt': 1}, said), 'attempt 1 was listed')
        line = mc.attempt_line({'kind': 'campaign', 'outcome': 'crashed', 'task_attempt': 2,
                                'why': 'Lua error'}, said)
        self.assertEqual(line, 'attempt 2: crashed before the bot reported (Lua error)')

    def test_attempts_need_a_saved_start(self):
        with self.assertRaises(ValueError):
            mc.attempt_tasks({'id': 'c'}, 2)

    def test_first_clean_is_the_lowest_clean_attempt(self):
        recs = [{'attempt': 3, 'clean': True}, {'attempt': 1, 'clean': False},
                {'attempt': 2, 'clean': True}, {'attempt': None, 'outcome': 'crashed'}]
        self.assertEqual(mc.first_clean(recs), 2)
        self.assertIsNone(mc.first_clean([{'attempt': 1, 'clean': False}]))

    def test_first_clean_needs_all_four_parts(self):
        # a clear the run could not judge (no owed recruit list) is never a clean one
        self.assertIsNone(mc.first_clean([{'attempt': 1, 'outcome': 'won', 'clean': None}]))
        self.assertEqual(mc.first_clean([{'attempt': 1, 'outcome': 'won', 'clean': False},
                                         {'attempt': 2, 'outcome': 'won', 'clean': True}]), 2)

    def test_an_attempt_line_says_what_spoiled_it(self):
        r = {'attempt': 1, 'outcome': 'won', 'turns': 9, 'clean': False,
             'deaths': [{'charId': 0x42, 'faction': 'green', 'turn': 4, 'killer': 0x81}],
             'clear': {'won': True, 'lost': [{'charId': 0x42, 'faction': 'green', 'turn': 4,
                                              'killer': 0x81}],
                       'recruits_missing': [0x30],
                       'rewards_missing': [{'x': 3, 'y': 7, 'kind': 'visit', 'why': 'closed',
                                            'closed_by': 0x81}],
                       'stolen': [{'thief': 0x85, 'from': 0x01, 'item': 0x89, 'turn': 6}]}}
        line = mc.attempt_line(r, set())
        self.assertIn('0x85 stole item 0x89 from 0x01 (turn 6)', line)
        self.assertIn('lost 0x42 (green, turn 4, to 0x81)', line)
        self.assertIn('missed 0x30', line)
        self.assertIn('village 3,7 closed by 0x81', line)
        clean = mc.attempt_line({'attempt': 2, 'outcome': 'won', 'turns': 8, 'clean': True,
                                 'thefts': [{'thief': 0x8E, 'from': 0x05, 'item': 0x6A,
                                             'turn': 7, 'spoils': False}]}, set())
        self.assertIn('won clean', clean)
        self.assertIn('[noted: 0x8E stole item 0x6A from 0x05 (turn 7)]', clean)


class Verdict(unittest.TestCase):
    """The verdict (ADR 0385, #510 step 9 PR-H): any protected death on attempt 1, exact
    Clopper-Pearson bounds at alpha / (4 x 3 x N), the +-10-point margin, at every look."""

    N = 24   # ch00-ch07 in three modes, the frozen cell count ADR 0385's figures are for

    def test_clopper_pearson_matches_published_exact_values(self):
        # T088. Newcombe 1998a (Stat Med 17:857-872), Table I, method 5 (the exact
        # Clopper-Pearson interval), its four worked examples, each two-sided 95%: one-sided
        # bounds at 0.025 each
        for k, n, lo, hi in ((81, 263, 0.2527, 0.3676), (15, 148, 0.0578, 0.1617),
                             (0, 20, 0.0, 0.1684), (1, 29, 0.0009, 0.1776)):
            got = mc.clopper_pearson(k, n, 0.025)
            self.assertAlmostEqual(got[0], lo, places=4, msg=(k, n))
            self.assertAlmostEqual(got[1], hi, places=4, msg=(k, n))
        # k = 0 and k = n have a closed form: 1 - level^(1/n), and its mirror
        self.assertEqual(mc.clopper_pearson(0, 50, 0.01)[0], 0.0)
        self.assertAlmostEqual(mc.clopper_pearson(0, 50, 0.01)[1], 1 - 0.01 ** (1 / 50), places=9)
        self.assertEqual(mc.clopper_pearson(20, 20, 0.025), (1 - mc.clopper_pearson(0, 20, 0.025)[1], 1.0))
        with self.assertRaises(ValueError):
            mc.clopper_pearson(3, 2, 0.025)

    def test_each_bound_takes_its_share_of_the_familywise_alpha(self):
        # T089, FR-026: four bounds a look, three looks, N cells
        self.assertAlmostEqual(mc.bound_level(self.N), 0.05 / (4 * 3 * 24))
        self.assertAlmostEqual(mc.bound_level(1), 0.05 / 12)
        for bad in (0, -1, 2.0, True, None):
            with self.assertRaises(ValueError):
                mc.bound_level(bad)

    def test_paired_bounds_the_discordant_proportions_marginal_the_arms(self):
        # T089: a both-died b only-ours c only-twin d neither
        table = (30, 6, 2, 62)
        level = mc.bound_level(self.N)
        lb, ub = mc.clopper_pearson(6, 100, level)
        lc, uc = mc.clopper_pearson(2, 100, level)
        self.assertEqual(mc.confirmatory_interval(table, self.N, 'paired'), (lb - uc, ub - lc))
        l1, u1 = mc.clopper_pearson(36, 100, level)
        l2, u2 = mc.clopper_pearson(32, 100, level)
        self.assertEqual(mc.confirmatory_interval(table, self.N, 'marginal'), (l1 - u2, u1 - l2))
        p, m = (mc.confirmatory_interval(table, self.N, a) for a in ('paired', 'marginal'))
        self.assertLess(p[1] - p[0], m[1] - m[0], 'pairs that covary narrow the interval')
        with self.assertRaises(ValueError):
            mc.confirmatory_interval(table, self.N, 'mcnemar')

    def test_zero_discordance_needs_no_rule_of_its_own(self):
        # T090: the bounds handle 0 of n; ADR 0385's figures at N = 24
        v = mc.paired_verdict([(False, False)] * 50, self.N, 'paired')
        self.assertAlmostEqual(v['hi'], 0.159, places=3)
        self.assertEqual((v['look'], v['verdict'], v['settled']), (50, 'INCONCLUSIVE', False))
        self.assertIn('next look is at 100', v['reason'])
        v = mc.paired_verdict([(True, True), (False, False)] * 100, self.N, 'paired')
        self.assertAlmostEqual(v['hi'], 0.042, places=3)
        self.assertAlmostEqual(v['lo'], -0.042, places=3)
        self.assertEqual((v['look'], v['verdict'], v['settled']), (200, 'EQUIVALENT', True))

    def test_the_labels_are_checked_in_order_at_every_look(self):
        # T090, FR-028: equivalence first, then a side, then nothing
        self.assertEqual(mc.label(-0.05, 0.08), 'EQUIVALENT')
        self.assertEqual(mc.label(0.01, 0.09), 'EQUIVALENT', 'inside the margin wins over a side')
        self.assertEqual(mc.label(0.01, 0.30), 'HARDER')
        self.assertEqual(mc.label(-0.30, -0.01), 'EASIER')
        self.assertEqual(mc.label(-0.12, 0.12), 'INCONCLUSIVE')
        # a large gap is called at the first look: Manchego Stars loses someone on 30 of 50, the
        # twin never
        v = mc.paired_verdict([(True, False)] * 30 + [(False, False)] * 20, self.N, 'paired')
        self.assertEqual((v['look'], v['verdict'], v['settled']), (50, 'HARDER', True))
        self.assertAlmostEqual(v['diff'], 0.6)
        v = mc.paired_verdict([(False, True)] * 30 + [(False, False)] * 20, self.N, 'paired')
        self.assertEqual(v['verdict'], 'EASIER')
        # a small real gap never settles early, and the last look settles INCONCLUSIVE
        block = [(True, False)] * 6 + [(False, True)] * 3 + [(False, False)] * 41
        for n in (50, 100):
            self.assertFalse(mc.paired_verdict(block * (n // 50), self.N, 'paired')['settled'])
        v = mc.paired_verdict(block * 4, self.N, 'paired')
        self.assertEqual((v['verdict'], v['settled'], v['discordant']), ('INCONCLUSIVE', True, 36))

    def test_no_look_between_planned_ones(self):
        # 70 pairs: the last 20 are a wall of ours-only deaths, but the look is at 50, on the
        # first 50 alone, and those are even
        pairs = [(True, False), (False, True)] * 25 + [(True, False)] * 20
        v = mc.paired_verdict(pairs, self.N, 'paired')
        self.assertEqual((v['look'], v['diff']), (50, 0))
        self.assertFalse(v['settled'])
        self.assertIsNone(mc.paired_verdict(pairs[:49], self.N, 'paired')['look'])
        with self.assertRaises(ValueError):
            mc.paired_verdict(pairs, self.N, 'paired', look=70)

    def test_unresolved_attempts_stay_in_the_denominators_bounded_both_ways(self):
        # T091, FR-027: each unresolved pair is read as the worst case each way
        pairs = [(False, False)] * 196 + [(None, False), (False, None), (None, None),
                                          (True, None)]
        low, high = mc.bound_unresolved(pairs)
        self.assertEqual(low, mc.table_of([(False, False)] * 196 + [
            (False, False), (False, True), (False, True), (True, True)]))
        self.assertEqual(high, mc.table_of([(False, False)] * 196 + [
            (True, False), (False, False), (True, False), (True, False)]))
        self.assertEqual(sum(low), 200, 'nothing is dropped')
        v = mc.paired_verdict(pairs, self.N, 'paired')
        self.assertEqual(v['unresolved'], 4)
        self.assertEqual(v['lo'], mc.confirmatory_interval(low, self.N, 'paired')[0])
        self.assertEqual(v['hi'], mc.confirmatory_interval(high, self.N, 'paired')[1])

    def test_a_verdict_the_bounded_interval_does_not_support_is_withheld(self):
        # T091: 200 even pairs are EQUIVALENT; 20 of them unresolved widen it past the margin,
        # and an interval that then decides nothing is withheld, not inconclusive
        even = [(False, False)] * 200
        self.assertEqual(mc.paired_verdict(even, self.N, 'paired')['verdict'], 'EQUIVALENT')
        v = mc.paired_verdict([(None, None)] * 20 + even[20:], self.N, 'paired')
        self.assertEqual((v['verdict'], v['settled']), ('WITHHELD', True))
        self.assertIn('20 unresolved', v['reason'])
        # a gap clear even at the worst case is still called
        v = mc.paired_verdict([(True, False)] * 40 + [(None, None)] * 2 + [(False, False)] * 8,
                              self.N, 'paired')
        self.assertEqual(v['verdict'], 'HARDER')

    def test_the_pilot_reports_its_table_and_picks_its_analysis(self):
        # T093, FR-025: 5 both, 3 only Manchego Stars, 2 only the twin, 40 neither
        pairs = [(True, True)] * 5 + [(True, False)] * 3 + [(False, True)] * 2 + \
            [(False, False)] * 40 + [(None, True)]
        s = mc.pilot_summary(pairs, self.N, cpu_s=3600.0, reach={'ours': {'reached': 51}})
        self.assertEqual((s['table'], s['ours_only'], s['twin_only'], s['unresolved']),
                         ((5, 3, 2, 40), 3, 2, 1))
        self.assertAlmostEqual(s['diff'], 0.02)
        self.assertAlmostEqual(s['discordance'], 0.1)
        self.assertAlmostEqual(s['corr'], (5 * 40 - 6) / (8 * 42 * 7 * 43) ** 0.5)
        self.assertEqual(s['analysis'], 'paired', 'the arms covary positively')
        # ADR 0385's reference at 200 pairs and N = 24: 10% discordance reads +-11.7
        self.assertAlmostEqual(s['half_width'], 0.117, places=3)
        self.assertFalse(s['reachable'])
        self.assertEqual((s['cpu_s'], s['reach']), (3600.0, {'ours': {'reached': 51}}))
        self.assertNotIn('verdict', s, 'pilot pairs are never confirmatory')
        # 5% discordance reads +-8.8, inside the margin
        s = mc.pilot_summary([(True, False), (False, True)] + [(False, False)] * 38, self.N)
        self.assertAlmostEqual(s['half_width'], 0.088, places=3)
        self.assertTrue(s['reachable'])

    def test_arms_that_do_not_covary_are_analysed_marginally(self):
        # independent arms: covariance 0 (a d = b c), so marginal, its width at the pooled rate
        s = mc.pilot_summary([(True, True)] * 1 + [(True, False)] * 9 + [(False, True)] * 9 +
                             [(False, False)] * 81, self.N)
        self.assertEqual((s['cov'], s['analysis']), (0.0, 'marginal'))
        level = mc.bound_level(self.N)
        lo, hi = mc.clopper_pearson(20, 200, level)
        self.assertAlmostEqual(s['half_width'], hi - lo)
        with self.assertRaises(ValueError):
            mc.pilot_summary([(None, True)], self.N)


class Cell(unittest.TestCase):
    """run_cell and cell_pairs over a fake `play`: `fate(name, seed, chapter) -> records of
    that replicate` (a campaign cell's: BOTRUN records then its CAMPAIGN summary)."""

    N = 24

    def sides(self, store_dir=None):
        d = store_dir or tempfile.mkdtemp()
        out = {}
        for n, ch in (('ours', 4), ('vanilla', 3)):
            env = {'last': [ch], 'claims': {}, 'game': n}
            out[n] = mc.campaign_side(env, ch, 'normal', os.path.join(d, n + '.jsonl'),
                                      mc.cell_stamp(env, 'normal', 'bot1'), n == 'vanilla')
            out[n]['stamp'] = mc.cell_stamp(env, 'normal', 'bot1')
        return out

    def play(self, fate, log):
        def play(side, tasks):
            name = 'vanilla' if side['vanilla'] else 'ours'
            out = []
            for t in tasks:
                log.append((name, t['seed']))
                for r in fate(name, t['seed'], side['chapter']):
                    out.append(dict(r, seed=t['seed']))
            return out
        return play

    @staticmethod
    def died(yes, chapter, clean=None):
        # a played record as botrun.lua writes one: its environment held, its death graded
        deaths = [{'charId': 1, 'faction': 'blue', 'cause': 'rng_tail', 'turn': 3}] if yes else []
        return [{'chapter': chapter, 'attempt': 1, 'outcome': 'won', 'deaths': deaths,
                 'clean': (not yes) if clean is None else clean, 'env_status': 'clean'},
                {'kind': 'campaign', 'outcome': 'done'}]

    def test_kept_pairs_are_read_from_the_store_first(self):
        sides = self.sides()
        for s in range(1, 51):
            for r in self.died(False, 3):
                mc.append_record(sides['vanilla']['store'],
                                 dict(r, seed=s, **sides['vanilla']['stamp']))
        log = []
        v = mc.run_cell(sides, self.play(lambda n, s, ch: self.died(True, ch), log), self.N,
                        'paired')
        self.assertEqual((v['verdict'], v['look']), ('HARDER', 50))
        self.assertEqual(v['played'], {'ours': 50, 'vanilla': 0})
        self.assertNotIn('vanilla', {n for n, _ in log})

    def test_a_kept_run_of_another_env_is_played_again(self):
        sides = self.sides()
        env = {'last': [3], 'claims': {'3': ['x']}, 'game': 'vanilla'}
        other = mc.cell_stamp(env, 'normal', 'bot1')
        self.assertNotEqual(other, sides['vanilla']['stamp'], 'claims are in the stamp')
        for s in range(1, 51):
            for r in self.died(True, 3):
                mc.append_record(sides['vanilla']['store'], dict(r, seed=s, **other))
        v = mc.run_cell(sides, self.play(lambda n, s, ch: self.died(n == 'ours', ch), []),
                        self.N, 'paired')
        self.assertEqual(v['played']['vanilla'], 50)

    def test_a_cell_stops_at_the_first_look_that_decides(self):
        # no discordance: +-15.9 at 50 is too wide, +-8.3 at 100 is inside the margin
        v = mc.run_cell(self.sides(), self.play(lambda n, s, ch: self.died(False, ch), []),
                        self.N, 'paired')
        self.assertEqual((v['look'], v['verdict'], v['settled']), (100, 'EQUIVALENT', True))
        self.assertEqual(v['played'], {'ours': 100, 'vanilla': 100})
        # 10% discordance, evenly split, decides nothing anywhere and plays to the last look
        v = mc.run_cell(self.sides(), self.play(
            lambda n, s, ch: self.died((s % 20 == 0) if n == 'ours' else (s % 20 == 10), ch),
            []), self.N, 'paired')
        self.assertEqual((v['look'], v['verdict'], v['settled']), (200, 'INCONCLUSIVE', True))
        self.assertEqual(v['played'], {'ours': 200, 'vanilla': 200})

    def test_the_endpoint_is_any_death_in_attempt_one_and_clean_is_only_reported(self):
        # a won attempt with a death is a death; a lost attempt with none is not; a later
        # retry is not the first attempt
        recs = [{'chapter': 3, 'attempt': 1, 'outcome': 'won', 'clean': False,
                 'deaths': [{'charId': 2, 'faction': 'blue'}]},
                {'chapter': 3, 'attempt': 2, 'outcome': 'won', 'clean': True, 'deaths': []}]
        r = mc.chapter_result(recs, 3)
        self.assertEqual((r['status'], r['died'], r['clean']), ('played', True, False))
        r = mc.chapter_result([{'chapter': 3, 'attempt': 1, 'outcome': 'lost', 'deaths': []}], 3)
        self.assertEqual((r['died'], r['clean']), (False, False))
        # a green whose death does not end the game is not the endpoint; one that does is
        green = {'charId': 9, 'faction': 'green', 'escort': False}
        vip = dict(green, escort=True)
        for d, want in ((green, False), (vip, True)):
            r = mc.chapter_result([{'chapter': 3, 'attempt': 1, 'outcome': 'won',
                                    'deaths': [d]}], 3)
            self.assertEqual(r['died'], want, d)

    def test_a_crash_is_retried_once_on_its_own_seed_then_bounded(self):
        # T091: Manchego Stars seed 3 crashes twice; it stays in the pairs as unresolved
        def fate(n, s, ch):
            if (n, s) == ('ours', 3):
                return [{'chapter': ch, 'attempt': 1, 'outcome': 'crashed', 'run_dir': '/tmp/r3',
                         'why': 'Lua error: boom', 'log_tail': ['RESULT: FAIL']},
                        {'kind': 'campaign', 'outcome': 'crashed', 'why': 'chapter 4 attempt 1'}]
            return self.died(False, ch)
        log = []
        got = mc.cell_pairs(self.sides(), self.play(fate, log), list(range(1, 51)))
        self.assertEqual(log.count(('ours', 3)), 2, 'played, then retried once on its seed')
        self.assertNotIn(('ours', 51), log, 'and no seed stands in for it')
        self.assertEqual(len(got['pairs']), 50)
        self.assertEqual(got['pairs'][2], (None, False))
        p = got['problems']
        self.assertEqual([(x['side'], x['seed'], x['status']) for x in p],
                         [('ours', 3, 'unresolved')])
        self.assertEqual((p[0]['why'], p[0]['log_tail']), ('Lua error: boom', ['RESULT: FAIL']))
        self.assertFalse(got['withheld'])

    def test_a_retry_that_plays_is_the_first_attempt(self):
        tries = []

        def fate(n, s, ch):
            if (n, s) == ('ours', 3) and not tries:
                tries.append(1)
                return [{'chapter': ch, 'attempt': 1, 'outcome': 'crashed', 'why': 'x'},
                        {'kind': 'campaign', 'outcome': 'crashed'}]
            return self.died(n == 'ours', ch)
        got = mc.cell_pairs(self.sides(), self.play(fate, []), [3])
        self.assertEqual(got['pairs'], [(True, False)])
        self.assertEqual(got['problems'], [])

    def test_a_campaign_cell_compares_only_what_both_arms_reach(self):
        # T092, FR-024: vanilla seed 7 lost an earlier chapter; the pair is left out and counted
        def fate(n, s, ch):
            if (n, s) == ('vanilla', 7):
                return [{'chapter': 2, 'attempt': 1, 'outcome': 'lost'},
                        {'kind': 'campaign', 'outcome': 'bot_fault',
                         'why': 'chapter 2: no clean clear in 300 attempts'}]
            return self.died(False, ch)
        got = mc.cell_pairs(self.sides(), self.play(fate, []), list(range(1, 11)))
        self.assertEqual(len(got['pairs']), 9)
        self.assertEqual(got['paired'], [1, 2, 3, 4, 5, 6, 8, 9, 10], 'the seeds that made a pair')
        self.assertEqual(got['reach']['vanilla'], {'reached': 9, 'unreached': 1, 'unresolved': 0})
        self.assertEqual(got['reach']['ours'], {'reached': 10, 'unreached': 0, 'unresolved': 0})
        p = got['problems'][0]
        self.assertEqual((p['side'], p['seed'], p['status']), ('vanilla', 7, 'unreached'))
        self.assertIn('never played chapter 3', p['why'])
        self.assertIn('300 attempts', p['why'])
        self.assertFalse(got['withheld'])

    def test_unresolved_reachability_withholds_the_comparison(self):
        # T091: a campaign that crashed before the chapter, twice
        def fate(n, s, ch):
            if (n, s) == ('ours', 1):
                return [{'chapter': 2, 'attempt': 1, 'outcome': 'crashed', 'why': 'Lua error: x'},
                        {'kind': 'campaign', 'outcome': 'crashed', 'why': 'chapter 2 crashed'}]
            return self.died(False, ch)
        log = []
        v = mc.run_cell(self.sides(), self.play(fate, log), self.N, 'paired')
        self.assertEqual((v['verdict'], v['settled'], v['look']), ('WITHHELD', False, 50))
        self.assertIn('whether it reaches it is unknown', v['reason'])
        p = v['problems'][0]
        self.assertEqual(p['status'], 'reach_unresolved')
        self.assertIn('crashed (chapter 2, attempt 1): Lua error: x', p['why'])
        self.assertEqual(log.count(('ours', 1)), 2)

    def test_a_pinned_attempt_that_crashed_unwritten_is_unresolved_not_unreached(self):
        # review of #582: a chapter cell starts at the chapter, so a worker that died before
        # writing one is attempt 1 unresolved, bounded, never a withheld comparison
        crash = [{'outcome': 'crashed', 'attempt': 1, 'why': 'launch died'}]
        self.assertEqual(mc.chapter_result(crash, 3)['status'], 'reach_unresolved')
        r = mc.chapter_result(crash, 3, pinned=True)
        self.assertEqual((r['status'], r['tries']), ('unresolved', 1))
        self.assertTrue(mc.again(crash, 3, True), 'its retry is owed')
        self.assertFalse(mc.again(crash * 2, 3, True), 'and only one')
        sides = self.sides()
        for side in sides.values():
            side['pinned'] = True
        got = mc.cell_pairs(sides, self.play(
            lambda n, s, ch: crash if (n, s) == ('ours', 2) else self.died(False, ch)[:1], []),
            [1, 2, 3])
        self.assertFalse(got['withheld'])
        self.assertEqual(got['pairs'], [(False, False), (None, False), (False, False)])
        self.assertEqual(got['results'][2]['ours']['status'], 'unresolved')

    def test_a_retry_counts_only_the_plays_that_stopped_where_this_one_did(self):
        # review of #582: an earlier chapter's crash the campaign got past is not a retry
        recs = [{'chapter': 2, 'attempt': 1, 'outcome': 'crashed'},
                {'chapter': 2, 'attempt': 2, 'outcome': 'won'},
                {'chapter': 3, 'attempt': 1, 'outcome': 'crashed'},
                {'kind': 'campaign', 'outcome': 'crashed'}]
        r = mc.chapter_result(recs, 3)
        self.assertEqual((r['status'], r['tries']), ('unresolved', 1))
        self.assertTrue(mc.again(recs, 3))
        before = [{'chapter': 2, 'attempt': 1, 'outcome': 'crashed'},
                  {'kind': 'campaign', 'outcome': 'crashed'}]
        self.assertEqual(mc.chapter_result(before, 3)['tries'], 1)
        self.assertFalse(mc.again(before * 2, 3))

    def test_a_cell_needs_its_last_looks_seeds(self):
        with self.assertRaises(ValueError):
            mc.run_cell(self.sides(), self.play(lambda n, s, ch: [], []), self.N, 'paired',
                        seeds=range(1, 100))

    def test_campaign_tasks_keep_their_seed_from_new_game(self):
        stamp = mc.cell_stamp({'last': [7]}, 'difficult', 'b')
        tasks = mc.campaign_tasks({'last': [7]}, [5, 6], 'difficult', stamp, vanilla=True)
        self.assertEqual([t['seed'] for t in tasks], [5, 6])
        camp = tasks[0]['campaign']
        self.assertNotIn('from', camp)
        self.assertNotIn('attempt', camp)
        self.assertNotEqual(camp['id'], tasks[1]['campaign']['id'], 'each seed its own campaign')
        self.assertEqual((tasks[0]['mode'], tasks[0]['vanilla']), ('difficult', True))
        with self.assertRaises(ValueError):
            mc.campaign_tasks({'from': 4}, [1], 'normal', stamp)
        named = mc.campaign_tasks({'last': [7]}, [5], None, {'x': 1}, prefix='cs')
        self.assertEqual(named[0]['campaign']['id'], 'cs-s5')

    def test_a_tasks_stamp_reaches_every_record_crashed_too(self):
        d = tempfile.mkdtemp()
        out = os.path.join(d, 'runs.jsonl')

        def launch(task, tag, log_path):
            if task['seed'] == 2:
                raise RuntimeError('died')
            return 'BOTRUN {"seed": %d, "outcome": "won"}\n' % task['seed'], '/tmp/x'
        stamp = mc.cell_stamp({}, 'normal', 'b')
        list(mc.Pool(jobs=2, out=out, launch=launch).run(
            mc.campaign_tasks({}, [1, 2], 'normal', stamp)))
        kept = mc.kept_runs(out, stamp)
        self.assertEqual(sorted(kept), [1, 2])
        self.assertEqual(kept[2][0]['outcome'], 'crashed')
        self.assertIn('died', kept[2][0]['why'])

    def test_bot_hash_follows_the_lua(self):
        d = tempfile.mkdtemp()
        with open(os.path.join(d, 'bot.lua'), 'w') as fh:
            fh.write('return 1')
        h1 = mc.bot_hash(d)
        with open(os.path.join(d, 'bot.lua'), 'w') as fh:
            fh.write('return 2')
        self.assertNotEqual(h1, mc.bot_hash(d))

    def test_bot_hash_ignores_generated_tables_and_tests(self):
        # a ROM rebuild rewrites symbols.lua; a test edit runs no differently: neither may
        # throw away every kept run
        d = tempfile.mkdtemp()
        with open(os.path.join(d, 'bot.lua'), 'w') as fh:
            fh.write('return 1')
        h1 = mc.bot_hash(d)
        for name in ('symbols.lua', 'procscr.lua', 'test_bot.lua'):
            with open(os.path.join(d, name), 'w') as fh:
                fh.write('-- changed')
        self.assertEqual(h1, mc.bot_hash(d))
        with open(os.path.join(d, 'harness.lua'), 'w') as fh:
            fh.write('-- the bot api')
        self.assertNotEqual(h1, mc.bot_hash(d))

    def test_a_runs_trace_is_kept_gzipped_beside_the_runs(self):
        import gzip
        d = tempfile.mkdtemp()
        out = os.path.join(d, 'store', 'runs.jsonl')
        os.makedirs(os.path.dirname(out))
        rd = tempfile.mkdtemp()
        with open(os.path.join(rd, 'trace-ours-4-a1.jsonl'), 'w') as fh:
            fh.write('{"t": "start"}\n{"t": "end"}\n')

        def launch(task, tag, log_path):
            return ('BOTRUN {"seed": %d, "chapter": 4, "attempt": 1, "campaign": "c", '
                    '"trace": "trace-ours-4-a1.jsonl"}\n' % task['seed'], rd)
        recs = list(mc.Pool(jobs=1, out=out, launch=launch).run(
            mc.campaign_tasks({}, [3], 'normal', mc.cell_stamp({}, 'normal', 'b'))))
        rel = recs[0]['trace']
        self.assertTrue(rel.startswith('traces/c/4-s3-a1-'), rel)
        with gzip.open(os.path.join(d, 'store', rel), 'rt') as fh:
            self.assertEqual([json.loads(x)['t'] for x in fh], ['start', 'end'])

    def test_an_anomalys_story_command_names_the_kept_trace(self):
        d = tempfile.mkdtemp()
        rd = tempfile.mkdtemp()
        with open(os.path.join(rd, 'tr.jsonl'), 'w') as fh:
            fh.write('{"t": "start"}\n')
        rec = {'trace': 'tr.jsonl', 'run_dir': rd, 'chapter': 2, 'seed': 1, 'attempt': 1,
               'anomalies': [{'kind': 'stall_abort', 'turn': 7}]}
        out = os.path.join(d, 'runs.jsonl')
        mc.keep_trace(rec, out)
        self.assertEqual(rec['anomalies'][0]['narrate'],
                         mc.narrate(os.path.join(d, rec['trace']), 7))
        gone = {'trace': 'none.jsonl', 'run_dir': rd, 'anomalies': [{'kind': 'x', 'turn': 1}]}
        mc.keep_trace(gone, out)
        self.assertNotIn('narrate', gone['anomalies'][0])   # no kept trace, no command


# The frozen suite's manifest (#510 step 9 plan, T005; FR-021 and FR-025): a matrix.yaml
# `instrument:` section, defaults merged into each start as matrix.yaml's rows are.
SUITE = {
    'version': 1, 'held_out_frozen_at': None, 'route': 1,
    'emulator': {'binary': 'tools/emulator/mgba-headless', 'sha1': 'e' * 40},
    'seed_sets': {'confirmatory': [1, 200], 'pilot': [3001, 3050]}, 'cells': 24,
    'defaults': {'seeds': {'tuning': [1001, 1002], 'held_out': [2001, 2002]}, 'style': 'drawn',
                 'invariant': 'record', 'estimate_wall_s': 600,
                 'budgets': {'beam': 6, 'final': 4, 'branch': 8, 'lookahead_decision': 8,
                             'lookahead_attempt': 128}},
    'shops_from': ['references/sim/vanilla/h/states/c'],
    'starts': [
        {'start_id': 'vanilla-ch3', 'game': 'vanilla', 'chapter': 3, 'rom_hash': 'c25b145e3745',
         'state_path': 'references/sim/vanilla/c25b145e3745/states/c/3.ss', 'state_sha1': 'a' * 40,
         'provenance': {'campaign': 'c', 'seed': 1, 'source': '#510'}, 'label': 'fixture'},
        {'start_id': 'ours-ch02', 'game': 'ours', 'chapter': 3, 'rom_hash': 'fd3cb9d8dca6',
         'state_path': 'references/sim/ours/fd3cb9d8dca6/states/o/3.ss', 'state_sha1': 'b' * 40,
         'provenance': {'campaign': 'o', 'seed': None, 'source': '#510'}, 'label': 'fixture',
         'seeds': {'tuning': [1003, 1004]}}],
}


def frozen_fixture(tuning_calls, held_out_calls, tuning=None, losses=()):
    """A frozen baseline (suite-frozen.json's shape) with these calls a set."""
    return {'instrument': 'f+v1', 'calls': {'tuning': tuning_calls, 'held_out': held_out_calls},
            'tuning': tuning or {}, 'held_out_losses': list(losses)}


class Suite(unittest.TestCase):
    def load(self, inst):
        import yaml
        d = tempfile.mkdtemp()
        path = os.path.join(d, 'matrix.yaml')
        with open(path, 'w') as fh:
            yaml.safe_dump({'instrument': inst}, fh)
        return mc.load_suite(path)

    def suite(self):
        return json.loads(json.dumps(SUITE))   # a deep copy each test may change

    def refuses(self, inst, words):
        with self.assertRaises(matrix.ManifestError) as cm:
            self.load(inst)
        self.assertIn(words, str(cm.exception))

    def test_a_start_takes_the_defaults_it_does_not_name(self):
        got = self.load(self.suite())
        a, b = got['starts']
        self.assertEqual(a['seeds'], {'tuning': [1001, 1002], 'held_out': [2001, 2002]})
        # a table a start names merges key by key: its own tuning, the default held-out
        self.assertEqual(b['seeds'], {'tuning': [1003, 1004], 'held_out': [2001, 2002]})
        self.assertEqual((a['style'], a['budgets']['lookahead_attempt']), ('drawn', 128))
        self.assertEqual(got['version'], 1)

    def test_the_shipped_manifest_loads(self):
        got = mc.load_suite()
        # FR-021: vanilla 6, Manchego Stars 4, scout 4 (Ch6, the fog map, PR-G; Ch10, Ch13, Ch14)
        self.assertEqual(len(got['starts']), 14)
        self.assertEqual(sum(len(s['seeds']['tuning']) + len(s['seeds']['held_out'])
                             for s in got['starts']), 56)   # SC-001, amended by PR-G
        # T084: the failing decision snapshots, one per witnessed or unresolved T079 death
        self.assertEqual(sorted(sn['start_id'] for sn in got['snapshots']),
                         ['ours-ch02', 'ours-ch03', 'scout-ch6'])
        # the frozen baseline (ADR 0395) is this manifest's: every tuning run it keeps is one the
        # manifest plays, and every one the manifest plays is kept, so a start added or a seed
        # moved since the freeze is a refreeze, never a silent gap
        frozen = mc.load_frozen()
        self.assertIsNotNone(frozen, 'suite-frozen.json is committed')
        self.assertEqual(frozen['manifest_version'], got['version'])
        self.assertEqual(sorted(frozen['tuning']), sorted(
            '%s/%s' % (s['start_id'], seed) for s in got['starts'] for seed in s['seeds']['tuning']))
        self.assertEqual(len(frozen['held_out_losses']), len(set(frozen['held_out_losses'])))
        lo, hi = got['seed_sets']['confirmatory']
        self.assertLessEqual(mc.LOOKS[-1], hi - lo + 1, 'a cell plays seeds 1..LOOKS[-1]')
        # the budgets the manifest records are the ones the planner plays (PR #560: `branch`
        # stayed 2 when planner.lua's M.BRANCH moved; #571: `lookahead_attempt` stayed 32)
        src = open(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'planner.lua')).read()
        for key, const in (('beam', 'BEAM'), ('final', 'FINAL'), ('branch', 'BRANCH'),
                           ('lookahead_decision', 'LOOK_DECISION'),
                           ('lookahead_attempt', 'LOOK_ATTEMPT')):
            m = re.search(r'^M\.%s = (\d+)' % const, src, re.M)
            self.assertIsNotNone(m, 'planner.lua sets M.%s to a number' % const)
            for s in got['starts']:
                self.assertEqual(s['budgets'][key], int(m.group(1)),
                                 '%s: budgets.%s is M.%s' % (s['start_id'], key, const))

    def test_a_start_listed_twice_raises(self):
        inst = self.suite()
        inst['starts'].append(dict(inst['starts'][0]))
        self.refuses(inst, 'vanilla-ch3')
        inst = self.suite()
        inst['starts'].append(dict(inst['starts'][0], start_id='again'))
        self.refuses(inst, 'listed twice')

    def test_a_start_without_its_state_hash_raises(self):
        inst = self.suite()
        del inst['starts'][1]['state_sha1']
        self.refuses(inst, 'state_sha1')

    def test_a_seed_in_two_sets_raises(self):
        for where, seed in (('held_out', 1001), ('tuning', 3010), ('held_out', 150)):
            inst = self.suite()
            inst['starts'][1]['seeds'] = {'tuning': [1003, 1004], 'held_out': [2003, 2004]}
            inst['starts'][1]['seeds'][where][0] = seed
            self.refuses(inst, str(seed))

    def test_a_missing_budget_raises(self):
        inst = self.suite()
        del inst['defaults']['budgets']['lookahead_decision']
        self.refuses(inst, 'lookahead_decision')

    def test_suite_tasks_play_attempt_one_from_each_pinned_state(self):
        suite = self.load(self.suite())
        envs = {'vanilla': {'last': [99], 'claims': {}}, 'ours': {'last': [8], 'shops': {}}}
        tasks = mc.suite_tasks(suite, envs, 'i+v1', {'vanilla': '/v.jsonl', 'ours': '/o.jsonl'})
        self.assertEqual(len(tasks), 8)   # two starts x (two tuning + two held-out)
        t = tasks[0]
        self.assertEqual(t['campaign'], {'last': [3], 'claims': {}, 'id': 'c', 'from': 3,
                                         'attempt': 1})
        self.assertEqual((t['seed'], t['vanilla'], t['instrument'], t['out']),
                         (1001, True, 'i+v1', '/v.jsonl'))
        self.assertEqual(t['stamp'], {'task_attempt': 1,
                                      'suite': {'start_id': 'vanilla-ch3', 'set': 'tuning',
                                                'version': 1}})
        self.assertEqual([(x['seed'], x['stamp']['suite']['set']) for x in tasks[4:]],
                         [(1003, 'tuning'), (1004, 'tuning'), (2001, 'held_out'),
                          (2002, 'held_out')])
        self.assertFalse(tasks[4]['vanilla'])
        self.assertEqual(len(mc.suite_tasks(suite, envs, 'i', {}, sets=('tuning',))), 4)

    def test_chapter_tasks_give_each_replicate_its_own_seed_on_the_pinned_start(self):
        # T092, FR-024: one task a seed, both arms from their pinned starts, attempt 1 only
        suite = self.load(self.suite())
        envs = {'vanilla': {'last': [99], 'claims': {}}, 'ours': {'last': [8], 'shops': {}}}
        outs = {'vanilla': '/v.jsonl', 'ours': '/o.jsonl'}
        arms = [mc.chapter_tasks(suite, envs, 'i', outs, mc.start_of(suite, sid), 'pilot')
                for sid in ('ours-ch02', 'vanilla-ch3')]
        for tasks in arms:
            self.assertEqual([t['seed'] for t in tasks], list(range(3001, 3051)))
            self.assertEqual({t['stamp']['suite']['set'] for t in tasks}, {'pilot'})
        self.assertEqual(arms[0][0]['campaign'], {'last': [3], 'shops': {}, 'id': 'o', 'from': 3,
                                                  'attempt': 1})
        self.assertEqual((arms[1][0]['campaign']['from'], arms[1][0]['out']), (3, '/v.jsonl'))
        v3 = mc.start_of(suite, 'vanilla-ch3')
        some = mc.chapter_tasks(suite, envs, 'i', outs, v3, 'confirmatory', [7, 2])
        self.assertEqual([t['seed'] for t in some], [2, 7])
        for bad in (('pilot', [7]), ('tuning', [2001]), ('nope', None)):
            with self.assertRaises(ValueError):
                mc.chapter_tasks(suite, envs, 'i', outs, v3, *bad)

    def cell_start(self, campaign, chapter=3, game='vanilla', seed=4001):
        return {'start_id': '%s/%d' % (campaign, chapter), 'game': game, 'chapter': chapter,
                'rom_hash': 'h', 'state_path': 'x', 'state_sha1': 'y', 'estimate_wall_s': 600,
                'provenance': {'campaign': campaign, 'seed': seed}}

    def test_a_chapter_side_deals_each_seed_its_start_and_reads_only_those_runs(self):
        # T100e: seed s plays start (s - first) % K whichever seeds a look plays, and a kept
        # run counts only on the start its seed is dealt
        suite = self.load(self.suite())
        d = tempfile.mkdtemp()
        store = os.path.join(d, 'runs.jsonl')
        starts = [self.cell_start('cs-s4001'), self.cell_start('cs-s4002', seed=4002)]
        base = {'game': 'vanilla', 'rom_hash': 'h', 'instrument': 'i', 'chapter': 3,
                'attempt': 1, 'outcome': 'won'}
        for seed, inst, sid, kind, rom in ((3001, 'i', 'cs-s4001/3', 'pilot', 'h'),
                                           (3002, 'i', 'cs-s4002/3', 'pilot', 'h'),
                                           (3003, 'i', 'cs-s4002/3', 'pilot', 'h'),  # not its
                                           (3004, 'old', 'cs-s4002/3', 'pilot', 'h'),
                                           (3005, 'i', 'cs-s4001/3', 'tuning', 'h'),
                                           (3007, 'i', 'cs-s4001/3', 'pilot', 'other')):
            mc.append_record(store, dict(base, seed=seed, instrument=inst, rom_hash=rom,
                                         suite={'start_id': sid, 'set': kind, 'version': 1}))
        side = mc.chapter_side(suite, {'vanilla': {}, 'ours': {}}, 'i', starts, 'pilot',
                               store, 'h')
        self.assertEqual(sorted(side['kept']()), [3001, 3002])
        self.assertEqual((side['chapter'], side['vanilla'], side['starts']), (3, True, starts))
        got = side['tasks']([3009, 3002, 3001])
        self.assertEqual(sorted((t['seed'], t['stamp']['suite']['start_id'], t['campaign']['id'])
                                for t in got),
                         [(3001, 'cs-s4001/3', 'cs-s4001'), (3002, 'cs-s4002/3', 'cs-s4002'),
                          (3009, 'cs-s4001/3', 'cs-s4001')])
        one = mc.chapter_side(suite, {'vanilla': {}, 'ours': {}}, 'i', starts[:1], 'pilot',
                              store, 'h')
        self.assertEqual({t['campaign']['id'] for t in one['tasks']([3001, 3002])},
                         {'cs-s4001'}, 'one start takes every seed')

    def test_a_benched_arm_plays_and_keeps_under_its_own_instrument(self):
        # the benched-twin experiment: its runs are never read as the instrument's, nor its
        # instrument's as its own, and each of its tasks carries the bench to run.sh
        suite = self.load(self.suite())
        top = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, top)
        d = os.path.join(top, 'h')   # the store is named by its ROM hash
        os.makedirs(d)
        store = os.path.join(d, 'runs.jsonl')
        base = {'game': 'vanilla', 'rom_hash': 'h', 'chapter': 3, 'attempt': 1,
                'outcome': 'won', 'suite': {'start_id': 'cs-s4001/3', 'set': 'pilot',
                                            'version': 1}}
        mc.append_record(store, dict(base, seed=3001, instrument='i'))
        mc.append_record(store, dict(base, seed=3002, instrument='i+bench02'))
        simdirs = {'vanilla': d, 'ours': '/s/ours/h2'}
        starts = {'vanilla': [self.cell_start('cs-s4001')],
                  'ours': [self.cell_start('cs-s4001', 4, 'ours')]}
        sides = mc.chapter_sides(suite, simdirs, {'vanilla': {}, 'ours': {}}, 'i', starts,
                                 'pilot', {'vanilla': [0x02]})
        self.assertEqual(sorted(sides['vanilla']['kept']()), [3002])
        task = sides['vanilla']['tasks']([3009])[0]
        self.assertEqual((task['instrument'], task['bench']), ('i+bench02', [0x02]))
        self.assertNotIn('bench', sides['ours']['tasks']([3009])[0])
        self.assertEqual(sides['ours']['tasks']([3009])[0]['instrument'], 'i')
        self.assertEqual(sides['ours']['store'], '/s/ours/h2/runs.jsonl')
        plain = mc.chapter_side(suite, {'vanilla': {}, 'ours': {}}, 'i', starts['vanilla'],
                                'pilot', store, 'h')
        self.assertEqual(sorted(plain['kept']()), [3001])
        sides['ours']['reached'], sides['vanilla']['reached'] = (1, 3), (1, 1)
        self.assertEqual(mc.games_line(sides, [3001, 3002]),
                         'over 1 Manchego Stars games (1 of 3 pinned campaigns reached the '
                         'chapter) and '
                         '1 vanilla games (1 of 1 pinned campaigns reached the chapter)')

    def test_the_games_line_counts_only_the_starts_the_seeds_were_dealt(self):
        # review of #587: K starts asked, fewer dealt (more starts than seeds, or an early look)
        suite = self.load(self.suite())
        sides = {n: mc.chapter_side(suite, {'vanilla': {}, 'ours': {}}, 'i',
                                    [self.cell_start('cs-s%d' % s, game=n, seed=s)
                                     for s in range(4001, 4061)], 'pilot', '/r.jsonl', 'h')
                 for n in ('ours', 'vanilla')}
        for side in sides.values():
            side['reached'] = (60, 60)
        self.assertIn('over 50 Manchego Stars games', mc.games_line(sides, range(3001, 3051)))
        self.assertIn('and 2 vanilla games', mc.games_line(sides, [3001, 3002, 3061]))

    def pins(self, store, campaigns):
        os.makedirs(store, exist_ok=True)
        mc.write_pins(store, [{'campaign': 'cs-s%d' % seed, 'seed': seed, 'outcome': 'done',
                               'why': None, 'chapters': {str(c): 'sha%d' % c for c in chs}}
                              for seed, chs in campaigns])

    def test_cell_starts_are_the_first_k_pinned_campaigns_that_reached_the_chapter(self):
        suite = self.load(self.suite())
        top = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, top)
        store = os.path.join(top, 'h')
        self.pins(store, [(4003, [0, 1, 2, 3]), (4001, [0, 1, 2, 3]), (4002, [0, 1]),
                          (4004, [0, 1, 2, 3])])
        got = mc.cell_starts(suite, store, 'vanilla', 3, 2)
        self.assertEqual([st['start_id'] for st in got], ['cs-s4001/3', 'cs-s4003/3'])
        st = got[0]
        self.assertEqual((st['game'], st['chapter'], st['rom_hash'], st['state_sha1'],
                          st['provenance'], st['estimate_wall_s']),
                         ('vanilla', 3, 'h', 'sha3', {'campaign': 'cs-s4001', 'seed': 4001}, 600))
        # where the harness loads it from, so check_starts takes it as pinned
        self.assertEqual(os.path.abspath(os.path.join(mc.REPO, st['state_path'])),
                         os.path.abspath(os.path.join(store, 'states', 'cs-s4001', '3.ss')))
        self.assertEqual(len(mc.cell_starts(suite, store, 'vanilla', 1, 4)), 4)
        with self.assertRaises(ValueError) as cm:
            mc.cell_starts(suite, store, 'vanilla', 3, 4)
        self.assertIn('3 vanilla campaigns', str(cm.exception))
        self.assertIn('starts --game vanilla', str(cm.exception))
        self.assertEqual(mc.cell_pins(os.path.join(top, 'none')), [])

    def test_a_cell_runs_start_is_found_by_its_id_so_replay_can_play_it(self):
        # review of #587: a pilot's discordant pair names cs-s4001/3, and replay must find it
        suite = self.load(self.suite())
        top = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, top)
        simdirs = {'vanilla': os.path.join(top, 'v'), 'ours': os.path.join(top, 'o')}
        # both games name their starts campaigns cs-s<seed>, so one id is in both stores:
        # the record's game picks the store (re-review of #587)
        self.pins(simdirs['vanilla'], [(4001, [3, 4])])
        self.pins(simdirs['ours'], [(4001, [3, 4])])
        for game in ('ours', 'vanilla'):
            st = mc.start_by_id(suite, simdirs, 'cs-s4001/3', game)
            self.assertEqual((st['game'], st['chapter'], st['state_sha1']), (game, 3, 'sha3'))
            self.assertTrue(st['state_path'].endswith(
                os.path.join(os.path.basename(simdirs[game]), 'states', 'cs-s4001', '3.ss')))
        self.assertEqual(mc.start_by_id(suite, simdirs, 'vanilla-ch3', 'vanilla')['start_id'],
                         'vanilla-ch3')
        for bad in ('cs-s4001/5', 'cs-s4009/3', 'cs-s4001/x', 'nope'):
            with self.assertRaises(ValueError):
                mc.start_by_id(suite, simdirs, bad, 'vanilla')
        with mock.patch.object(mc, 'suite_setup', return_value=(suite, simdirs, dict)), \
                mock.patch.object(mc, 'check_starts', return_value=[]):
            one, _dirs, _envs = mc.pinned_setup(['cs-s4001/3'], 'vanilla')
        task = mc.start_task(one, {'vanilla': {'last': [9]}, 'ours': {}}, 'i', 'cs-s4001/3',
                             'pilot', 3007)
        self.assertEqual((task['seed'], task['campaign']['id'], task['campaign']['from']),
                         (3007, 'cs-s4001', 3))

    def test_cell_setup_refuses_what_cannot_be_played(self):
        suite = self.load(self.suite())
        top = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, top)
        simdirs = {'vanilla': os.path.join(top, 'v'), 'ours': os.path.join(top, 'o')}
        self.pins(simdirs['vanilla'], [(4001, [3])])
        self.pins(simdirs['ours'], [(4001, [4])])
        with mock.patch.object(mc, 'suite_setup', return_value=(suite, simdirs, dict)), \
                mock.patch.object(mc, 'check_starts', return_value=[]) as check:
            suite_, dirs, _envs, starts = mc.cell_setup(3, 1)
            self.assertEqual({a: [st['start_id'] for st in v] for a, v in starts.items()},
                             {'ours': ['cs-s4001/4'], 'vanilla': ['cs-s4001/3']})
            checked = check.call_args[0][0]
            self.assertEqual(([st['start_id'] for st in checked['starts']],
                              checked['snapshots']), (['cs-s4001/4', 'cs-s4001/3'], []))
            sides = mc.chapter_sides(suite_, dirs, {'vanilla': {}, 'ours': {}}, 'i', starts,
                                     'pilot')
            self.assertEqual((sides['ours']['reached'], sides['vanilla']['reached']),
                             ((1, 1), (1, 1)))
            self.assertIn('needs a start an arm', mc.cell_setup(3, 0))
            self.assertIn('not a written chapter', mc.cell_setup(99, 1))
            self.assertIn('1 %s campaigns' % 'ours', mc.cell_setup(3, 2))   # the game id
            check.return_value = ['cs-s4001/3: its state is gone']
            self.assertIn('its state is gone', mc.cell_setup(3, 1))

    def test_starts_plays_only_unpinned_seeds_and_pins_each_campaign_as_it_ends(self):
        suite = self.load(self.suite())
        suite['seed_sets']['starts'] = [4001, 4005]
        top = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, top)
        store = os.path.join(top, 'h')
        simdirs = {'vanilla': store, 'ours': os.path.join(top, 'o')}
        self.pins(store, [(4002, [0, 1])])
        # a killed earlier play of 4001 left a start this play never reaches
        os.makedirs(os.path.join(store, 'states', 'cs-s4001'))
        with open(os.path.join(store, 'states', 'cs-s4001', '7.ss'), 'wb') as fh:
            fh.write(b'stale')
        played = []

        class Fake:
            def run(self, tasks):
                for t in tasks:
                    played.append((t['seed'], t['campaign']['id'], t['campaign']['last'],
                                   t['campaign']['start_only'], t['vanilla']))
                    if t['seed'] == 4004:   # the harness failed: never pinned, played again
                        yield {'seed': 4004, 'outcome': 'crashed', 'why': 'no ROM'}
                        continue
                    d = os.path.join(store, 'states', t['campaign']['id'])
                    os.makedirs(d, exist_ok=True)
                    for c in (0, 1, 2):
                        with open(os.path.join(d, '%d.ss' % c), 'wb') as fh:
                            fh.write(b'%d' % c)
                    with open(os.path.join(d, '2.json'), 'w') as fh:
                        fh.write('{}')
                    yield {'seed': t['seed'], 'chapter': 2, 'outcome': 'lost'}   # an attempt
                    # the campaign's end: no chapter
                    yield {'kind': 'campaign', 'seed': t['seed'], 'outcome': 'infeasible',
                           'why': '300 attempts'}
                    # each worker's end is pinned before the next worker's runs are read
                    self_pins = {c['seed'] for c in mc.cell_pins(store)}
                    assert t['seed'] in self_pins, self_pins
        out = io.StringIO()
        with mock.patch.object(mc, 'suite_setup', return_value=(
                suite, simdirs, lambda: {'vanilla': {'last': [99]}, 'ours': {}})), \
                contextlib.redirect_stdout(out):
            self.assertEqual(mc.starts_main(mock.Mock(game='vanilla', count=3, jobs=2),
                                            Fake()), 0)
            self.assertEqual(mc.starts_main(mock.Mock(game='vanilla', count=4, jobs=2),
                                            Fake()), 1, 'a crash fails the command')
            self.assertEqual(mc.starts_main(mock.Mock(game='vanilla', count=4, jobs=2),
                                            Fake()), 1)
            self.assertEqual(mc.starts_main(mock.Mock(game='vanilla', count=6, jobs=2),
                                            Fake()), 1)
        last = max(p[1] for p in __import__('campaign_env').cell_chapters().values())
        self.assertEqual(played, [(4001, 'cs-s4001', [last], last, True),
                                  (4003, 'cs-s4003', [last], last, True),
                                  (4004, 'cs-s4004', [last], last, True),
                                  (4004, 'cs-s4004', [last], last, True)])
        pins = {c['seed']: c for c in mc.cell_pins(store)}
        self.assertEqual(sorted(pins), [4001, 4002, 4003], 'the crash is not pinned')
        self.assertIn('cs-s4004: crashed, not pinned (no ROM', out.getvalue())
        self.assertEqual(pins[4001]['outcome'], 'infeasible')
        self.assertEqual(pins[4001]['chapters'],
                         {str(c): mc.sha1_file(os.path.join(store, 'states', 'cs-s4001',
                                                            '%d.ss' % c)) for c in (0, 1, 2)})
        self.assertEqual(pins[4002]['chapters'], {'0': 'sha0', '1': 'sha1'}, 'kept as pinned')
        self.assertIn('refused: --count 6', out.getvalue())
        self.assertIn('ch01 (index 1): 3 of 3 pinned campaigns reached its start\n'
                      'ch02 (index 2): 2 of 3', out.getvalue())

    def test_resume_carries_a_campaign_on_under_a_new_id_from_its_saved_start(self):
        """`resume` (ADR 0399): a copy of the campaign's states under `<tag>-<campaign>`, so the
        pinned file is never re-saved; from its latest start unless told; its own seed; and a
        refusal before any copy for a rewritten pin, a missing start or a taken id."""
        top = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, top)
        store = os.path.join(top, 'h')
        for name, chs in (('cs-s4001', (6, 7)), ('full-s4008', (9,))):
            d = os.path.join(store, 'states', name)
            os.makedirs(d)
            for c in chs:
                with open(os.path.join(d, '%d.ss' % c), 'wb') as fh:
                    fh.write(b'%s-%d' % (name.encode(), c))
        mc.write_pins(store, [{'campaign': 'cs-s4001', 'seed': 4001, 'outcome': 'bot_fault',
                               'why': None, 'chapters': {
                                   str(c): mc.sha1_file(os.path.join(store, 'states', 'cs-s4001',
                                                                     '%d.ss' % c))
                                   for c in (6, 7)}}])
        pins = {c['campaign']: c for c in mc.cell_pins(store)}
        env = {'last': [22], 'route': 1}
        tasks = mc.resume_tasks(store, env, ['cs-s4001', 'full-s4008'], pins, 'mem1', vanilla=True)
        self.assertEqual([(t['campaign']['id'], t['campaign']['from'], t['seed'],
                           t['campaign']['last']) for t in tasks],
                         [('mem1-cs-s4001', 7, 4001, [22]), ('mem1-full-s4008', 9, 4008, [22])])
        self.assertNotIn('attempt', tasks[0]['campaign'], 'every attempt, in sequence')
        self.assertEqual(tasks[0]['stamp'], {'resumed_from': 'cs-s4001/7'})
        self.assertTrue(os.path.exists(os.path.join(store, 'states', 'mem1-cs-s4001', '7.ss')))
        one = mc.resume_tasks(store, env, ['cs-s4001'], pins, 'mem2', chapter=6, last=7)
        self.assertEqual((one[0]['campaign']['from'], one[0]['campaign']['last']), (6, [7]))
        self.assertNotIn('max_attempts', one[0]['campaign'], 'the retry cap, unless told')
        cut = mc.resume_tasks(store, env, ['cs-s4001'], pins, 'cut1', attempts=2)
        self.assertEqual(cut[0]['campaign']['max_attempts'], 2, '--attempts: a chapter stops there')
        with self.assertRaisesRegex(ValueError, 'already exists'):
            mc.resume_tasks(store, env, ['cs-s4001'], pins, 'mem1')
        with self.assertRaisesRegex(ValueError, 'no saved start at chapter index 3'):
            mc.resume_tasks(store, env, ['cs-s4001'], pins, 'mem3', chapter=3)
        with open(os.path.join(store, 'states', 'cs-s4001', '7.ss'), 'wb') as fh:
            fh.write(b're-saved')
        with self.assertRaisesRegex(ValueError, 'not the start cell-starts.json pins'):
            mc.resume_tasks(store, env, ['cs-s4001'], pins, 'mem4')
        self.assertFalse(os.path.exists(os.path.join(store, 'states', 'mem3-cs-s4001')),
                         'a refusal copies nothing')
        # a copy that fails part way removes every copy the call made (the tag stays free)
        real, calls = shutil.copytree, []

        def flaky(src, dst):
            calls.append(dst)
            if len(calls) == 2:
                os.makedirs(dst)
                raise OSError('disk full')
            return real(src, dst)
        with mock.patch.object(mc.shutil, 'copytree', flaky):
            with self.assertRaises(OSError):
                mc.resume_tasks(store, env, ['cs-s4001', 'full-s4008'], {}, 'mem5', vanilla=True)
        self.assertEqual([n for n in os.listdir(os.path.join(store, 'states')) if n.startswith('mem5')],
                         [], 'no copy is left behind')

    def test_pinned_setup_checks_only_the_named_starts_and_refuses_the_rest(self):
        suite = self.load(self.suite())
        suite['snapshots'] = [{'snapshot_id': 'x', 'start_id': 'vanilla-ch3'}]
        simdirs = {'vanilla': '/v', 'ours': '/o'}
        seen = []

        def check(one, dirs):
            seen.append(([s['start_id'] for s in one['starts']],
                         [s['snapshot_id'] for s in one['snapshots']]))
            return ['vanilla-ch3: its state is gone'] if len(seen) > 1 else []
        with mock.patch.object(mc, 'suite_setup', return_value=(suite, simdirs, dict)), \
                mock.patch.object(mc, 'check_starts', check):
            self.assertEqual(mc.pinned_setup(['vanilla-ch3'], 'vanilla')[0],
                             dict(suite, starts=[mc.start_of(suite, 'vanilla-ch3')]))
            self.assertIn('its state is gone', mc.pinned_setup(['vanilla-ch3'], 'vanilla'))
            self.assertIn('no start nope', mc.pinned_setup(['nope'], 'vanilla'))
        self.assertEqual(seen[0], (['vanilla-ch3'], []), 'it plays no snapshot, so checks none')

    def test_the_cell_count_is_checked_before_anything_plays(self):
        # review of #582: --cells 0 is refused, never read as "the manifest's"
        suite = {'cells': 24}
        self.assertEqual(mc.frozen_cells(mock.Mock(cells=None), suite), 24)
        self.assertEqual(mc.frozen_cells(mock.Mock(cells=8), suite), 8)
        for bad in (0, -1):
            with self.assertRaises(ValueError):
                mc.frozen_cells(mock.Mock(cells=bad), suite)

    def test_a_cell_takes_one_kind_of_flags(self):
        # review of #582: a mix of chapter and campaign flags is an error, never half-read
        for argv in (['cell', '--analysis', 'paired', '--chapter', '3', '--ours', 'o.json'],
                     ['cell', '--analysis', 'paired', '--chapter', '3', '--ours', 'o',
                      '--vanilla', 'v', '--ours-chapter', '4', '--vanilla-chapter', '3'],
                     ['cell', '--analysis', 'paired', '--ours', 'o', '--vanilla', 'v',
                      '--ours-chapter', '4']):
            with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
                mc.main(argv)

    def test_a_pilot_with_no_resolved_pair_refuses_and_says_why(self):
        # re-review of #582: every pair unresolved is a refusal with each run's words, not a
        # traceback after the runs
        suite = self.load(self.suite())
        side = {'kept': dict, 'tasks': lambda seeds: [], 'chapter': 3, 'pinned': True}
        problem = {'side': 'ours', 'seed': 3001, 'status': 'unresolved', 'why': 'Lua error: x'}
        out = io.StringIO()
        with mock.patch.object(mc, 'cell_setup', return_value=(
                suite, {'ours': '/o', 'vanilla': '/v'}, dict, {'ours': [], 'vanilla': []})), \
                mock.patch.object(mc, 'instrument_id', return_value='i'), \
                mock.patch.object(mc, 'chapter_sides', return_value={'ours': side,
                                                                     'vanilla': side}), \
                mock.patch.object(mc, 'kept_walls', return_value={}), \
                mock.patch.object(mc, 'cell_pairs', return_value={
                    'pairs': [(None, False)] * 50, 'problems': [problem], 'cpu_s': 0.0,
                    'reach': {}, 'results': {}}), \
                contextlib.redirect_stdout(out):
            self.assertEqual(mc.main(['pilot', '--chapter', '2']), 1)
        self.assertIn('refused: no pilot pair has a game result', out.getvalue())
        self.assertIn('Lua error: x', out.getvalue())

    def test_a_cell_with_no_resolved_pair_prints_its_withheld_verdict(self):
        # review of #582: no resolved pair leaves the rates None, and that must not crash
        v = mc.paired_verdict([(None, None)] * 50, 24, 'paired', look=50)
        self.assertEqual((v['verdict'], v['ours'], v['table']), ('WITHHELD', None, (0, 0, 0, 0)))
        d = tempfile.mkdtemp()
        for n in ('o', 'v'):
            with open(os.path.join(d, n), 'w') as fh:
                json.dump({'last': [3]}, fh)
        reach = {n: {'reached': 50, 'unreached': 0, 'unresolved': 0} for n in ('ours', 'vanilla')}
        out = io.StringIO()
        with mock.patch.object(mc, 'load_suite', return_value={'cells': 24}), \
                mock.patch.object(mc, 'simdir', return_value=d), \
                mock.patch.object(mc, 'bot_hash', return_value='b'), \
                mock.patch.object(mc, 'run_cell', return_value=dict(
                    v, reach=reach, problems=[], played={'ours': 50, 'vanilla': 50},
                    validity={'failed': [], 'withheld': []}, results={}, seeds=[],
                    paired=[])), \
                mock.patch.object(mc, 'CELLS_FILE', os.path.join(d, 'cells.jsonl')), \
                contextlib.redirect_stdout(out):
            self.assertEqual(mc.main(['cell', '--analysis', 'paired', '--ours',
                                      os.path.join(d, 'o'), '--vanilla', os.path.join(d, 'v'),
                                      '--ours-chapter', '4', '--vanilla-chapter', '3']), 0)
        self.assertIn('WITHHELD at 50', out.getvalue())
        self.assertIn('validity (FR-029): every invariant holds in both arms', out.getvalue())
        # the cell's record, for `report`: a campaign cell, its verdict, its twin's index
        with open(os.path.join(d, 'cells.jsonl')) as fh:
            cell = json.loads(fh.read())
        self.assertEqual((cell['kind'], cell['cell_kind'], cell['verdict'], cell['twin_index']),
                         ('cell', 'campaign', 'WITHHELD', 3))

    def test_a_campaign_cell_at_no_written_chapter_is_refused_before_it_plays(self):
        d = tempfile.mkdtemp()
        out = io.StringIO()
        with mock.patch.object(mc, 'load_suite', return_value={'cells': 24}), \
                mock.patch.object(mc, 'run_cell') as run, contextlib.redirect_stdout(out):
            self.assertEqual(mc.main(['cell', '--analysis', 'paired', '--ours', d, '--vanilla',
                                      d, '--ours-chapter', '99', '--vanilla-chapter', '3']), 1)
        run.assert_not_called()
        self.assertIn("refused: --ours-chapter 99 is no written chapter's index", out.getvalue())

    def pilot(self, results, bench=()):
        """`pilot --chapter 2` over fake sides and pairs: (exit code, printed, cell records)."""
        d = tempfile.mkdtemp()
        side = {'kept': dict, 'tasks': lambda seeds: [], 'chapter': 2, 'pinned': True,
                'store': os.path.join(d, 'runs.jsonl')}
        got = {'pairs': [(r['ours']['died'], r['vanilla']['died']) for r in results.values()],
               'paired': list(results), 'results': results, 'cpu_s': 1.0, 'problems': [],
               'reach': {}}
        suite = {'cells': 24, 'seed_sets': {'pilot': [1, len(results)]}, 'starts': []}
        out, cells = io.StringIO(), os.path.join(d, 'cells.jsonl')
        argv = ['pilot', '--chapter', '2'] + [x for c in bench for x in ('--bench-vanilla', c)]
        with mock.patch.object(mc, 'cell_setup', return_value=(
                    suite, {'ours': d, 'vanilla': d}, dict, {'ours': [], 'vanilla': []})), \
                mock.patch.object(mc, 'chapter_sides', return_value={'ours': side,
                                                                     'vanilla': side}), \
                mock.patch.object(mc, 'instrument_id', return_value='i+v2'), \
                mock.patch.object(mc, 'suite_estimate', return_value=0.1), \
                mock.patch.object(mc, 'kept_walls', return_value={}), \
                mock.patch.object(mc, 'cell_pairs', return_value=got), \
                mock.patch.object(mc, 'games_line', return_value='over 1 game'), \
                mock.patch.object(mc, 'CELLS_FILE', cells), contextlib.redirect_stdout(out):
            code = mc.main(argv)
        recs = mc.report_cells(cells)
        return code, out.getvalue(), recs

    def test_a_pilot_files_its_cell_record_and_a_not_readable_one_fails(self):
        def res(died, detail=None):
            deaths = [{'cause': 'other' if detail else 'rng_tail', 'charId': 1,
                       'detail': detail}] if died else []
            return dict(played(deaths), rec=dict(played(deaths)['rec'], trace='t', seed=1,
                                                 suite={'start_id': 'cs-s4001/2'}))
        ok = {s: {'ours': res(s % 3 == 0), 'vanilla': res(s % 5 == 0)} for s in range(1, 21)}
        code, out, recs = self.pilot(ok)
        self.assertEqual(code, 0)
        self.assertEqual([(r['cell_kind'], r['verdict']) for r in recs], [('pilot', None)])
        # an experiment with a benched unit is not the instrument's pilot: no record
        code, out, recs = self.pilot(ok, bench=['5'])
        self.assertEqual(recs, [])
        self.assertIn('no cell record: a benched experiment', out)
        bad = dict(ok)
        bad[1] = {'ours': res(True, 'missing_prediction'), 'vanilla': res(False)}
        code, out, recs = self.pilot(bad)
        self.assertEqual(code, 1)
        self.assertTrue(out.splitlines()[1].startswith('NOT READABLE (sandbox_fault): this '
                                                       "pilot's analysis choice cannot be used"))
        self.assertEqual(recs[0]['verdict'], 'NOT_READABLE')

    def test_the_pilot_and_confirmatory_seeds_never_meet(self):
        # T092, FR-025 (the tuning and held-out seeds' clash is test_a_seed_in_two_sets_raises)
        inst = self.suite()
        inst['seed_sets']['pilot'] = [150, 199]
        self.refuses(inst, 'confirmatory and pilot seeds meet at 150')

    def test_the_frozen_cell_count_is_a_positive_count(self):
        for bad in (0, 2.5, True, 'x'):
            inst = self.suite()
            inst['cells'] = bad
            self.refuses(inst, 'frozen N')
        inst = self.suite()
        del inst['cells']
        self.refuses(inst, 'cells')
        self.assertEqual(mc.load_suite()['cells'], 24, 'ch00-ch07 in three modes (ADR 0385)')

    def test_a_start_that_no_longer_matches_is_refused(self):
        d = tempfile.mkdtemp()
        inst = self.suite()
        inst['shops_from'] = [d]
        for s in inst['starts']:
            s['state_path'] = s['state_path'].replace('references/sim', d)
        suite = self.load(inst)
        a, b = suite['starts']
        os.makedirs(os.path.dirname(a['state_path']))
        with open(a['state_path'], 'wb') as fh:
            fh.write(b'not the state')
        simdirs = {'vanilla': os.path.join(d, 'vanilla', 'c25b145e3745'),
                   'ours': os.path.join(d, 'ours', '000000000000')}
        why = mc.check_starts(suite, simdirs, emulator_sha1='e' * 40)
        self.assertEqual(len(why), 2)
        self.assertIn('vanilla-ch3', why[0])
        self.assertIn('no longer hashes to', why[0])
        self.assertIn('ours-ch02', why[1])
        self.assertIn('ROM built now is 000000000000', why[1])
        inst['starts'][0]['state_sha1'] = mc.sha1_file(a['state_path'])
        self.assertEqual(mc.check_starts(self.load(inst), simdirs, emulator_sha1='e' * 40),
                         [why[1]])
        moved = mc.check_starts(self.load(inst), simdirs, emulator_sha1='f' * 40)
        self.assertIn('the emulator', moved[0])
        inst['shops_from'] = [os.path.join(d, 'gone')]
        self.assertIn('the shops store', mc.check_starts(self.load(inst), simdirs,
                                                         emulator_sha1='e' * 40)[0])

    def test_the_estimate_reads_kept_runs_first(self):
        suite = self.load(self.suite())
        tasks = mc.suite_tasks(suite, {'vanilla': {}, 'ours': {}}, 'i', {})
        kept = {'vanilla-ch3': [30.0, 50.0]}   # measured: 40 s a run; ours-ch02 is not
        hours = mc.suite_estimate(suite, tasks, kept, jobs=2)
        self.assertAlmostEqual(hours, (4 * 40 + 4 * 600) / 2 / 3600)
        self.assertGreater(mc.suite_estimate(suite, tasks * 30, {}, jobs=1), mc.MAX_WALL_H)

    def suite_lines(self, play, held_out=True, jobs=4, **kw):
        """The lines run_suite prints for `play`, with no ROM, env or kept run behind it."""
        return mc.run_suite(self.load(self.suite()),
                            envs=lambda: {'vanilla': {}, 'ours': {}}, simdirs={}, play=play,
                            jobs=jobs, held_out=held_out, instrument='i', check=lambda *a: [],
                            kept={}, **kw)

    def test_a_job_over_eight_hours_is_refused_before_it_runs(self):
        played = []
        lines = self.suite_lines(lambda tasks: played.extend(tasks) or [], jobs=1, wall_limit_h=0.5)
        self.assertEqual(played, [])
        self.assertIn('refused', lines[-1])
        self.assertIn('8 wall-hours'.replace('8', '0.5'), lines[-1])

    def test_the_baseline_says_each_starts_cost_in_a_sentence(self):
        def play(tasks):
            # each worker also leaves its campaign's end, stamped alike: never a second run
            for i, t in enumerate(tasks):
                yield dict(t['stamp'], outcome='won', seed=t['seed'], wall_s=10.0 + i,
                           costs={'cpu_s': 2.0, 'game_calls': {'AiDecideMain': 5 + i,
                                                               'RefreshEntityBmMaps': 99}})
                yield dict(t['stamp'], kind='campaign', outcome='played', seed=t['seed'],
                           wall_s=10.0 + i)
        text = '\n'.join(self.suite_lines(play, frozen=frozen_fixture(30, 30)))
        self.assertIn('vanilla-ch3 (vanilla chapter 3, fixture): 4 runs, 26 AiDecideMain calls, '
                      '8.0 CPU s and 46.0 wall s in all, 6.5 calls and 2.0 CPU s a run', text)
        self.assertIn('ours-ch02 (%s chapter 3, fixture): 4 runs' % 'ours', text)   # the game id
        # SC-003's measure (ADR 0384): the AI's decisions only, never another game call
        self.assertIn('the suite: 8 runs, 68 AiDecideMain calls, 16.0 CPU s', text)
        self.assertIn('SC-003 (tuning and held-out seeds): 68 AiDecideMain calls against a '
                      'budget of 72 (+13.3% on the frozen 60): within', text)
        for seed in (2001, 2002):   # FR-025: a held-out outcome is a count, never a run
            self.assertNotIn('seed %d' % seed, text)
        self.assertIn('vanilla-ch3 seed 1001:', text, 'a tuning run is said')

    def test_the_suite_reports_the_lookahead(self):
        # FR-018 / SC-003: the trigger rate, coverage, skipped extensions and CPU, per start and
        # summed; a record from before the lookahead has none and adds nothing
        look = {'decisions': 10, 'triggered': 2, 'extended': 1, 'skipped_budget': 1,
                'calls': 4, 'cpu_s': 0.25}
        text = self.sc003(lambda i, t: {'outcome': 'won', 'lookahead': look} if i % 2 == 0
                          else {'outcome': 'won'})
        self.assertIn('vanilla-ch3 (vanilla chapter 3, fixture): 4 runs', text)
        self.assertIn('lookahead: 4 of 20 decisions triggered (20.0%), 2 extended, 2 skipped '
                      'for budget, 8 calls, 0.5 CPU s', text)
        self.assertIn('the suite\'s lookahead: 8 of 40 decisions triggered (20.0%), 4 extended, '
                      '4 skipped for budget, 16 calls, 1.0 CPU s', text)

    def sc003(self, records, held_out=True, keep=lambda t: True, frozen=None):
        """The suite's lines when each task `keep` allows comes back as `records(i, task)`."""
        def play(tasks):
            for i, t in enumerate(tasks):
                if keep(t):
                    yield dict(t['stamp'], seed=t['seed'], wall_s=1.0, **records(i, t))
        return '\n'.join(self.suite_lines(play, held_out=held_out,
                                          frozen=frozen or frozen_fixture(30, 30)))

    def test_sc003_counts_a_record_without_game_calls_as_none(self):
        text = self.sc003(lambda i, t: {'outcome': 'won', 'costs': {'cpu_s': 1.0}})
        self.assertIn('the suite: 8 runs, 0 AiDecideMain calls', text)

    def test_sc003_leaves_a_run_without_a_result_out_and_is_not_judged(self):
        # a crashed run asked for fewer calls: counted, it would read as a saving
        text = self.sc003(lambda i, t: {
            'outcome': 'crashed' if i == 0 else 'won',
            'costs': {'cpu_s': 1.0, 'game_calls': {'AiDecideMain': 10}}})
        self.assertIn('the suite: 8 runs, 70 AiDecideMain calls', text)
        self.assertIn('SC-003: not judged, 1 run without a game result', text)

    def test_sc003_is_not_judged_when_a_start_sent_no_run(self):
        # a start missing from the total reads as a saving, as a crashed run does
        text = self.sc003(lambda i, t: {'outcome': 'won'},
                          keep=lambda t: t['stamp']['suite']['start_id'] != 'ours-ch02')
        self.assertIn('ours-ch02: no run came back', text)
        self.assertIn('SC-003: not judged, 4 of 8 runs came back', text)

    def test_sc003_judges_the_seeds_played_against_the_same_seeds_frozen(self):
        # the tuning seeds alone are half of the suite: judged on the tuning seeds' frozen calls,
        # never on the whole's
        text = self.sc003(lambda i, t: {'outcome': 'won', 'costs': {
            'game_calls': {'AiDecideMain': 10}}}, held_out=False, frozen=frozen_fixture(30, 1000))
        self.assertIn('SC-003 (tuning seeds): 40 AiDecideMain calls against a budget of 36 '
                      '(+33.3% on the frozen 30): OVER', text)

    def test_sc003_is_not_judged_without_a_frozen_baseline(self):
        text = '\n'.join(self.suite_lines(lambda tasks: (dict(t['stamp'], seed=t['seed'],
                                                             outcome='won') for t in tasks)))
        self.assertIn('SC-003: not judged, there is no frozen baseline yet', text)
        self.assertIn('regressions: none judged, there is no frozen baseline yet', text)
        self.assertNotIn('promotion', text, 'nothing to promote over')

    def test_sc003_says_over_when_the_calls_pass_the_budget(self):
        text = self.sc003(lambda i, t: {
            'outcome': 'won', 'costs': {'game_calls': {'AiDecideMain': 10}}})
        self.assertIn(': OVER', text)
        self.assertIn('promotion: refused, 1 deterministic regression', text)

    def test_a_worker_with_no_bot_record_is_one_run_without_a_result(self):
        def play(tasks):
            for t in tasks:
                yield dict(t['stamp'], kind='campaign', outcome='crashed', seed=t['seed'],
                           wall_s=1.0, why='arrive: no saved start')
        text = '\n'.join(self.suite_lines(play, held_out=False))
        self.assertIn('vanilla-ch3 (vanilla chapter 3, fixture): 2 runs', text)
        self.assertIn('2 without a game result', text)
        self.assertIn('vanilla-ch3 seed 1001: attempt 1: crashed before the bot reported '
                      '(arrive: no saved start)', text)

    def test_a_start_off_its_pin_refuses_the_whole_suite(self):
        suite = self.load(self.suite())
        lines = mc.run_suite(suite, envs=None, simdirs={}, play=None, jobs=1, held_out=True,
                             instrument='i', check=lambda *a: ['ours-ch02: its state is gone'])
        self.assertTrue(lines[0].startswith('refused'))
        self.assertIn('ours-ch02: its state is gone', lines[1])

    def test_a_seed_twice_in_one_set_raises(self):
        inst = self.suite()
        inst['starts'][1]['seeds']['tuning'] = [1003, 1003]
        self.refuses(inst, 'distinct')

    def test_a_manifest_without_its_seed_sets_names_them(self):
        inst = self.suite()
        del inst['seed_sets']
        self.refuses(inst, 'seed_sets')

    def test_a_start_with_no_budgets_anywhere_names_them(self):
        inst = self.suite()
        del inst['defaults']['budgets']
        self.refuses(inst, 'budgets.beam')
        inst = self.suite()
        inst['starts'][0]['seeds'] = [1001, 1002]
        self.refuses(inst, 'not a table')

    def test_a_suite_error_never_reaches_the_instrument_id(self):
        import yaml
        d = tempfile.mkdtemp()
        path = os.path.join(d, 'matrix.yaml')
        inst = self.suite()
        inst['starts'].append(dict(inst['starts'][0]))   # load_suite refuses this manifest
        with open(path, 'w') as fh:
            yaml.safe_dump({'instrument': inst}, fh)
        with self.assertRaises(matrix.ManifestError):
            mc.load_suite(path)
        self.assertTrue(mc.instrument_id(path).endswith('+v1'))
        del inst['version']
        path = os.path.join(d, 'unversioned.yaml')   # instrument_id is cached by its path
        with open(path, 'w') as fh:
            yaml.safe_dump({'instrument': inst}, fh)
        with self.assertRaises(matrix.ManifestError):
            mc.instrument_id(path)

    def test_a_set_simdir_is_refused(self):
        import contextlib
        import io

        def never(*a, **k):   # a guard that moved below these would play the real suite
            raise AssertionError('the suite went past its PT_SIMDIR guard')
        buf = io.StringIO()
        with mock.patch.dict(os.environ, {'PT_SIMDIR': '/tmp/elsewhere'}), \
                mock.patch.object(mc, 'simdir', never), \
                mock.patch.object(mc, 'load_suite', never), \
                mock.patch.object(mc, 'Pool', never), contextlib.redirect_stdout(buf):
            code = mc.main(['suite'])
        self.assertEqual(code, 1)
        self.assertTrue(buf.getvalue().startswith('refused: PT_SIMDIR is set'))

    def test_a_missing_twin_is_refused_in_words(self):
        suite = self.load(self.suite())

        def envs():
            raise FileNotFoundError('7.json: no record of the twin')
        lines = mc.run_suite(suite, envs=envs, simdirs={}, play=None, jobs=1, held_out=True,
                             instrument='i', check=lambda *a: [])
        self.assertEqual(lines, ['refused: a campaign env cannot be built: 7.json: no record '
                                 'of the twin'])

    def test_a_campaign_end_without_a_bot_record_is_no_result(self):
        def play(tasks):
            for t in tasks:
                yield dict(t['stamp'], kind='campaign', outcome='played', seed=t['seed'],
                           wall_s=1.0, why='played after 1 chapters', env_status=mc.unread())
        text = '\n'.join(self.suite_lines(play, held_out=False))
        self.assertIn('2 without a game result', text)
        self.assertIn('vanilla-ch3 seed 1001: attempt 1: the bot left no record; the campaign '
                      'ended played (played after 1 chapters)', text)
        self.assertNotIn(': None', text)

    def test_no_rom_built_says_so(self):
        d = tempfile.mkdtemp()
        why = mc.check_starts(self.load(self.suite()),
                              {'vanilla': os.path.join(d, 'vanilla', ''),
                               'ours': os.path.join(d, 'ours', '')}, emulator_sha1='e' * 40)
        self.assertIn('no vanilla ROM is built', why[-2])
        self.assertIn('no %s ROM is built' % 'ours', why[-1])   # the game id

    def test_the_estimate_keeps_only_this_instruments_results(self):
        d = tempfile.mkdtemp()
        path = os.path.join(d, 'runs.jsonl')
        base = {'suite': {'start_id': 'a'}, 'game': 'vanilla', 'rom_hash': 'h',
                'instrument': 'i', 'outcome': 'won', 'wall_s': 40.0}
        for r in (base, dict(base, wall_s=60.0),
                  dict(base, instrument='old', wall_s=5.0),       # other code
                  dict(base, rom_hash='g', wall_s=5.0),            # another ROM
                  dict(base, outcome='crashed', wall_s=5.0),       # died at boot
                  dict(base, kind='campaign', wall_s=40.0),        # the worker's other record
                  {'seed': 1, 'wall_s': 5.0}):                     # a cell's run
            mc.append_record(path, r)
        self.assertEqual(mc.kept_walls([path], 'i', {'vanilla': 'h'}), {'a': [40.0, 60.0]})

    def test_two_seeds_of_each_kind(self):
        inst = self.suite()
        inst['starts'][1]['seeds']['tuning'] = [1003]
        self.refuses(inst, 'two')


def outcome(**kw):
    """run_outcome's shape, every field defaulted to a clean run."""
    return dict({'invariant': True, 'deaths': [], 'stalls': 0, 'lost': False, 'unlabelled': 0},
                **kw)


SNAPSHOT = {'snapshot_id': 'ours-ch03-1002-r45', 'start_id': 'ours-ch02', 'invariant': 'pinned_board',
            'state_path': 'references/sim/ours/fd3cb9d8dca6/traces/diag/x-pinned-ours-3-a1-r45.ss',
            'state_sha1': 'c' * 40,
            'board_path': 'references/sim/ours/fd3cb9d8dca6/traces/diag/x-pinned-ours-3-a1-r45.json',
            'board_sha1': 'd' * 40,
            'provenance': {'seed': 1003, 'set': 'tuning', 'ref': 45, 'mode': 'deep', 'char': 3,
                           'source': 'ADR 0392'}}


class Frozen(unittest.TestCase):
    """#510 step 9 PR-G (T081-T083): the suite judged on its frozen baseline."""

    def load(self, inst):
        return Suite.load(self, inst)

    def suite(self):
        return json.loads(json.dumps(SUITE))

    def lines(self, records, held_out=True, frozen=None, again=None, snapshots=None,
              result=None, explain=None):
        """run_suite's text when task i comes back as `records(i, task)` (None: no run)."""
        def play(tasks):
            for i, t in enumerate(tasks):
                r = records(i, t)
                if r is not None:
                    yield dict(t['stamp'], seed=t['seed'], wall_s=1.0, **r)
        return '\n'.join(mc.run_suite(
            self.load(self.suite()), envs=lambda: {'vanilla': {}, 'ours': {}}, simdirs={},
            play=play, jobs=4, held_out=held_out, instrument='i', check=lambda *a: [], kept={},
            frozen=frozen, again=again, snapshots=snapshots, result=result, explain=explain))

    def clean(self, calls=10):
        return lambda i, t: {'outcome': 'won', 'costs': {'game_calls': {'AiDecideMain': calls}}}

    def frozen_all_clean(self, **over):
        tuning = {k: outcome() for k in ('vanilla-ch3/1001', 'vanilla-ch3/1002',
                                         'ours-ch02/1003', 'ours-ch02/1004')}
        tuning.update(over)
        return frozen_fixture(40, 40, tuning)

    # ---- T081: each of these is a regression (AS 1)

    def test_an_invariant_that_held_when_frozen_and_fails_now_is_a_regression(self):
        regs = mc.regressions({'a/1': outcome()}, {'a/1': outcome(invariant=False)})
        self.assertEqual(regs, [('a/1: its invariant held when frozen and fails now', True)])
        # one that failed when frozen is no regression: it never passed
        self.assertEqual(mc.regressions({'a/1': outcome(invariant=False)},
                                        {'a/1': outcome(invariant=False)}), [])
        text = self.lines(lambda i, t: {'outcome': 'crashed'} if i == 0 else self.clean()(i, t),
                          frozen=self.frozen_all_clean())
        self.assertIn('vanilla-ch3/1001: its invariant held when frozen and fails now', text)
        self.assertIn('promotion: refused, not every run came back with a game result; '
                      '1 deterministic regression', text)

    def test_a_new_stall_blocks_and_a_new_death_is_a_signal_that_never_blocks(self):
        frozen = {'a/1': outcome(deaths=[1]), 'b/1': outcome()}
        now = {'a/1': outcome(deaths=[1, 2]), 'b/1': outcome(stalls=1)}
        # T107a: an unexplained death flip is said and does not block
        self.assertEqual(mc.regressions(frozen, now), [
            ('a/1: 0x02 dies, and lived when frozen; unexplained (a signal, not a blocker)',
             False),
            ('b/1: 1 stall, 0 when frozen', True)])
        # the same death, witnessed by a replay, is said with its label and does not block
        regs = mc.regressions(frozen, now, lambda key, c: 'search_miss')
        self.assertEqual(regs[0], ('a/1: 0x02 dies, and lived when frozen; witnessed: '
                                   'search_miss (a signal, not a blocker)', False))
        # nothing witnesses a stall: it blocks whatever the explainer says (ADR 0395)
        self.assertEqual(regs[1], ('b/1: 1 stall, 0 when frozen', True))
        # a death the frozen run had too is no regression, nor a start the baseline lacks
        self.assertEqual(mc.regressions({'a/1': outcome(deaths=[1])}, {'a/1': outcome(deaths=[1]),
                                                                        'c/1': outcome()}),
                         [('c/1: not in the frozen baseline, nothing to compare it with', False)])
        # through the suite: the run's record is what the explainer is asked about
        asked = []
        text = self.lines(lambda i, t: dict(self.clean()(i, t), deaths=[{'charId': 5, 'turn': 2}])
                          if i == 1 else self.clean()(i, t), frozen=self.frozen_all_clean(),
                          explain=lambda rec, c: asked.append((rec['seed'], c)))
        self.assertEqual(asked, [(1002, 5)])
        self.assertIn('vanilla-ch3/1002: 0x05 dies, and lived when frozen; unexplained', text)
        # through the suite, the flip alone leaves the candidate promoted
        self.assertIn('promotion: PROMOTED', text)

    def test_calls_more_than_a_fifth_over_the_frozen_baseline_are_a_regression(self):
        # 8 runs of 12 calls = 96 against 80 frozen: 1.2x exactly is within
        text = self.lines(self.clean(12), frozen=self.frozen_all_clean())
        self.assertIn('budget of 96 (+20.0% on the frozen 80): within', text)
        self.assertIn('promotion: PROMOTED', text)
        text = self.lines(self.clean(13), frozen=self.frozen_all_clean())
        self.assertIn(': OVER', text)
        self.assertIn('the suite asked for more than 20% over the frozen calls', text)
        self.assertIn('promotion: refused, 1 deterministic regression', text)

    # ---- T082: promotion, and the held-out seeds (AS 2)

    def test_promotion_needs_no_regression_no_unlabelled_fallback_and_no_reproducible_loss(self):
        self.assertEqual(mc.promotion([], 0, 0, True), (True, []))
        self.assertEqual(mc.promotion([('x', False)], 0, 0, True), (True, []))
        self.assertEqual(mc.promotion([('x', True), ('y', True)], 1, 2, False)[1], [
            'not every run came back with a game result', '2 deterministic regressions',
            '1 unlabelled fallback', '2 reproducible held-out losses'])

    def test_an_unlabelled_fallback_is_an_over_cap_death_of_a_protected_unit_no_anomaly_names(self):
        rec = {'kind': 'bot', 'outcome': 'won', 'anomalies': [
            {'kind': 'fallback_sacrifice', 'turn': 3}], 'deaths': [
            {'charId': 1, 'turn': 3, 'over_cap': True},                    # labelled
            {'charId': 2, 'turn': 4, 'over_cap': True},                    # not: counted
            {'charId': 0xC9, 'turn': 4, 'over_cap': True, 'escort': False},  # not the bot's
            {'charId': 0xCA, 'turn': 4, 'over_cap': True, 'escort': True},   # escorted: counted
            {'charId': 3, 'turn': 4, 'over_cap': False}]}
        self.assertTrue(mc.is_bot(rec))
        got = mc.run_outcome(rec)
        # the non-escort green is no death the bot answers for: neither counted nor a regression
        self.assertEqual((got['unlabelled'], got['deaths']), (2, [1, 2, 3, 0xCA]))
        text = self.lines(lambda i, t: dict(self.clean()(i, t), **{
            k: rec[k] for k in ('anomalies', 'deaths')}) if i == 0 else self.clean()(i, t),
            frozen=self.frozen_all_clean(**{'vanilla-ch3/1001': outcome(deaths=[1, 2, 3, 0xCA])}))
        self.assertIn('regressions on the frozen baseline (instrument f+v1): none', text)
        self.assertIn('vanilla-ch3/1001: 2 unlabelled fallbacks', text)
        self.assertIn('promotion: refused, 2 unlabelled fallbacks', text)

    def test_held_out_seeds_never_run_in_tuning_mode(self):
        played = []

        def play(tasks):
            played.extend(tasks)
            return iter(())
        mc.run_suite(self.load(self.suite()), envs=lambda: {'vanilla': {}, 'ours': {}},
                     simdirs={}, play=play, jobs=1, held_out=False, instrument='i',
                     check=lambda *a: [], kept={}, frozen=self.frozen_all_clean())
        self.assertEqual({t['stamp']['suite']['set'] for t in played}, {'tuning'})
        text = self.lines(self.clean(), held_out=False, frozen=self.frozen_all_clean())
        self.assertNotIn('held-out', text)
        self.assertNotIn('promotion', text, 'no promotion without the held-out seeds')

    def test_a_new_held_out_loss_is_played_again_and_said_only_as_a_count(self):
        lost = lambda i, t: dict(self.clean()(i, t), outcome='lost') \
            if t['seed'] == 2001 else self.clean()(i, t)
        replayed = []

        def again(tasks):
            replayed.extend((t['stamp']['suite']['start_id'], t['seed']) for t in tasks)
            for t in tasks:
                yield dict(t['stamp'], seed=t['seed'], outcome='lost')
        text = self.lines(lost, frozen=self.frozen_all_clean(), again=again)
        self.assertEqual(sorted(replayed), [('ours-ch02', 2001), ('vanilla-ch3', 2001)])
        self.assertIn('the held-out runs: 2 of 4 lost, 2 of them new since the freeze; played '
                      'again, 2 lost again (reproducible)', text)
        self.assertIn('promotion: refused, 2 reproducible held-out losses', text)
        self.assertNotIn('2001', text, 'a held-out run is never named')
        # a loss the frozen baseline had is not new, and plays no second time
        known = frozen_fixture(40, 40, self.frozen_all_clean()['tuning'],
                               [mc.held_out_tag('vanilla-ch3', 2001),
                                mc.held_out_tag('ours-ch02', 2001)])
        replayed[:] = []
        text = self.lines(lost, frozen=known, again=again)
        self.assertEqual(replayed, [])
        self.assertIn('the held-out runs: 2 of 4 lost, none new since the freeze', text)
        self.assertIn('promotion: PROMOTED', text)

    def test_a_held_out_failure_becomes_a_fixture_only_after_its_seed_is_replaced(self):
        inst = self.suite()
        inst['starts'].append(dict(inst['starts'][0], start_id='from-held-out',
                                   state_path='references/sim/vanilla/c25b145e3745/states/c/4.ss',
                                   provenance={'campaign': 'c', 'seed': 2001, 'set': 'held_out',
                                               'source': 'x'},
                                   seeds={'tuning': [1005, 1006], 'held_out': [2005, 2006]}))
        with self.assertRaises(matrix.ManifestError) as cm:
            self.load(inst)
        self.assertIn('names no commit that froze its held-out seeds', str(cm.exception))
        inst['held_out_frozen_at'] = 'abc1234'
        with self.assertRaises(matrix.ManifestError) as cm:
            self.load(inst)   # 2001 is still vanilla-ch3's held-out seed
        self.assertIn('held-out seed 2001, which is still held out', str(cm.exception))
        # the seed decides, not the label: a fixture from 2001 mislabelled tuning is refused too
        inst['starts'][2]['provenance']['set'] = 'tuning'
        with self.assertRaises(matrix.ManifestError) as cm:
            self.load(inst)
        self.assertIn('held-out seed 2001, which is still held out', str(cm.exception))
        inst['starts'][2]['provenance']['set'] = 'held_out'
        for s in inst['starts'][:2]:
            s['seeds'] = dict(s.get('seeds') or {}, held_out=[2101 + 2 * inst['starts'].index(s),
                                                              2102 + 2 * inst['starts'].index(s)])
        self.assertEqual(len(self.load(inst)['starts']), 3)

    # ---- the snapshots (T084)

    def test_a_snapshot_names_its_start_provenance_and_invariant(self):
        inst = self.suite()
        inst['snapshots'] = [dict(SNAPSHOT)]
        got = self.load(inst)['snapshots'][0]
        self.assertEqual((got['game'], got['provenance']['ref']), ('ours', 45))
        for drop, words in (('board_path', 'board_path'), ('start_id', 'start_id')):
            inst['snapshots'] = [{k: v for k, v in SNAPSHOT.items() if k != drop}]
            Suite.refuses(self, inst, words)
        inst['snapshots'] = [dict(SNAPSHOT, start_id='nowhere')]
        Suite.refuses(self, inst, 'no start nowhere')
        inst['snapshots'] = [dict(SNAPSHOT, provenance=dict(SNAPSHOT['provenance'], ref=None))]
        Suite.refuses(self, inst, 'provenance.ref')
        inst['snapshots'] = [dict(SNAPSHOT), dict(SNAPSHOT)]
        Suite.refuses(self, inst, 'listed twice')

    def test_a_snapshot_loads_back_to_its_board_in_a_fresh_emulator(self):
        d = tempfile.mkdtemp()
        board = [{'id': 1, 'charId': 1, 'x': 2, 'y': 3, 'hp': 20, 'faction': 'blue'}]
        rel = os.path.relpath(os.path.join(d, 'b.json'), mc.REPO)
        with open(os.path.join(d, 'b.json'), 'w') as fh:
            json.dump(board, fh)
        inst = self.suite()
        inst['snapshots'] = [dict(SNAPSHOT, board_path=rel)]
        suite = self.load(inst)
        seen = []

        def launch(task, tag, log_path, printed=board):
            seen.append(task)
            return 'PINNED %s\n' % json.dumps({'file': task['pinned'], 'board': printed}), None
        lines, failed = mc.snapshot_check(suite, {'vanilla': {}, 'ours': {}}, 'i', launch=launch)
        self.assertEqual(failed, [])
        self.assertIn('snapshot ours-ch03-1002-r45 (ours-ch02, decision 45, deep): loads back to '
                      'its board', lines[0])
        self.assertTrue(seen[0]['pinned'].endswith(SNAPSHOT['state_path']))
        self.assertNotIn('out', seen[0], 'a check writes no record')
        self.assertEqual(seen[0]['campaign']['attempt'], 1)
        moved = [dict(board[0], hp=1)]
        lines, failed = mc.snapshot_check(suite, {'vanilla': {}, 'ours': {}}, 'i',
                                          launch=lambda *a: launch(*a, printed=moved))
        self.assertEqual(failed, ['ours-ch03-1002-r45'])
        self.assertIn('loads to a board other than its own', lines[0])
        lines, failed = mc.snapshot_check(suite, {'vanilla': {}, 'ours': {}}, 'i',
                                          launch=lambda *a: ('', None))
        self.assertIn('printed no PINNED line', lines[0])
        # never more emulators at once than the suite's --jobs
        import threading
        live, peak, lock = [0], [0], threading.Lock()

        def slow(task, tag, log_path):
            with lock:
                live[0] += 1
                peak[0] = max(peak[0], live[0])
            time.sleep(0.05)
            with lock:
                live[0] -= 1
            return launch(task, tag, log_path)
        inst['snapshots'] = [dict(SNAPSHOT, board_path=rel, snapshot_id='s%d' % i)
                             for i in range(4)]
        lines, failed = mc.snapshot_check(self.load(inst), {'vanilla': {}, 'ours': {}}, 'i',
                                          launch=slow, jobs=2)
        self.assertEqual((failed, peak[0]), ([], 2))
        self.assertEqual([ln.split(' ')[1] for ln in lines], ['s0', 's1', 's2', 's3'])

    def test_a_failing_snapshot_is_a_regression_and_refuses_a_freeze(self):
        def lines_with(snap):
            inst = self.suite()
            inst['snapshots'] = [dict(SNAPSHOT)]
            result = {}

            def play(tasks):
                for t in tasks:
                    yield dict(t['stamp'], seed=t['seed'], wall_s=1.0, **self.clean()(0, t))
            text = '\n'.join(mc.run_suite(
                self.load(inst), envs=lambda: {'vanilla': {}, 'ours': {}}, simdirs={}, play=play,
                jobs=4, held_out=True, instrument='i', check=lambda *a: [], kept={},
                frozen=self.frozen_all_clean(), snapshots=snap, result=result))
            return text, result
        text, result = lines_with(lambda envs: (['snapshot s: loads to a board other than its '
                                                 'own'], ['s']))
        self.assertIn('promotion: refused, 1 deterministic regression', text)
        self.assertEqual(mc.freeze_record(result, 'i', 1), (None, 'snapshot s fails its invariant'))
        text, result = lines_with(lambda envs: (['snapshot s: loads back to its board'], []))
        rec, why = mc.freeze_record(result, 'i+v1', 2, today='2026-11-07')
        self.assertIsNone(why)
        self.assertEqual((rec['instrument'], rec['manifest_version'], rec['frozen_on']),
                         ('i+v1', 2, '2026-11-07'))
        self.assertEqual(rec['calls'], {'tuning': 40, 'held_out': 40})
        self.assertEqual(sorted(rec['tuning']), ['ours-ch02/1003', 'ours-ch02/1004',
                                                 'vanilla-ch3/1001', 'vanilla-ch3/1002'])
        self.assertNotIn('promoted', rec)

    def test_a_freeze_needs_every_run_and_a_promotion(self):
        result = {}
        self.lines(lambda i, t: None if i == 0 else self.clean()(i, t), result=result)
        self.assertEqual(mc.freeze_record(result, 'i', 1)[1],
                         'not every run came back with a game result')
        result = {}
        self.lines(self.clean(99), frozen=self.frozen_all_clean(), result=result)
        self.assertEqual(mc.freeze_record(result, 'i', 1)[1], 'the candidate is not promoted')
        # Nicolas's explicit override freezes a refused candidate, and the file says why
        rec, why = mc.freeze_record(result, 'i', 1, override='accepted cost')
        self.assertIsNone(why)
        self.assertEqual(rec['override'], 'accepted cost')
        self.assertNotIn('override', mc.freeze_record({}, 'i', 1)[0] or {})
        # it never covers an incomplete run
        self.assertEqual(mc.freeze_record({}, 'i', 1, override='x')[1],
                         'not every run came back with a game result')
        # the first freeze has nothing to be promoted over
        result = {}
        self.lines(self.clean(), result=result)
        self.assertIsNone(mc.freeze_record(result, 'i', 1)[1])
        # an override given for a run that turns out promoted is still kept (PR #585 review)
        self.assertEqual(mc.freeze_record(result, 'i', 1, override='accepted cost')[0]['override'],
                         'accepted cost')
        # but a fallback no label names is never frozen as the reference
        result = {}
        self.lines(lambda i, t: dict(self.clean()(i, t), deaths=[
            {'charId': 1, 'turn': 4, 'over_cap': True}]) if i == 0 else self.clean()(i, t),
            result=result)
        self.assertEqual(mc.freeze_record(result, 'i', 1)[1], 'the candidate is not promoted')
        # a held-out loss is kept hashed: the file never names the held-out run
        result = {}
        self.lines(lambda i, t: dict(self.clean()(i, t), outcome='lost') if t['seed'] == 2002
                   else self.clean()(i, t), result=result)
        self.assertEqual(result['held_out_losses'], sorted(
            [mc.held_out_tag('vanilla-ch3', 2002), mc.held_out_tag('ours-ch02', 2002)]))
        self.assertNotIn('2002', json.dumps(result))

    def test_a_snapshot_whose_board_file_changed_is_off_its_pin(self):
        d = tempfile.mkdtemp()
        for name, body in (('s.ss', b'state'), ('b.json', b'[]')):
            with open(os.path.join(d, name), 'wb') as fh:
                fh.write(body)
        rel = lambda n: os.path.relpath(os.path.join(d, n), mc.REPO)
        sn = dict(SNAPSHOT, state_path=rel('s.ss'), state_sha1=mc.sha1_file(os.path.join(d, 's.ss')),
                  board_path=rel('b.json'), board_sha1=mc.sha1_file(os.path.join(d, 'b.json')))
        suite = {'shops_from': [], 'emulator': {'binary': 'x', 'sha1': 'e' * 40}, 'starts': [],
                 'snapshots': [sn]}
        self.assertEqual(mc.check_starts(suite, {}, emulator_sha1='e' * 40), [])
        with open(os.path.join(d, 'b.json'), 'w') as fh:
            fh.write('[{"hp": 1}]')   # a later replay wrote over the frozen board
        why = mc.check_starts(suite, {}, emulator_sha1='e' * 40)
        self.assertEqual(len(why), 1)
        self.assertIn('its board', why[0])
        self.assertIn('no longer hashes to', why[0])

    def test_the_snapshots_are_checked_with_the_envs_the_run_built(self):
        inst = self.suite()
        inst['snapshots'] = [dict(SNAPSHOT)]
        got = []
        built = {'vanilla': {'v': 1}, 'ours': {'o': 1}}
        mc.run_suite(self.load(inst), envs=lambda: built, simdirs={},
                     play=lambda tasks: iter(()), jobs=1, held_out=False, instrument='i',
                     check=lambda *a: [], kept={},
                     snapshots=lambda envs: got.append(envs) or ([], []))
        self.assertIs(got[0], built, 'no second build of every campaign env')

    def test_two_launches_in_one_second_never_share_a_tag(self):
        tags = []
        launch = lambda task, tag, log: tags.append((tag, log)) or ('', None)
        d = tempfile.mkdtemp()
        mc.launch_tagged({}, 'pinned', d, launch)
        mc.launch_tagged({}, 'pinned', d, launch)
        self.assertNotEqual(tags[0], tags[1])
        self.assertTrue(all(t.startswith('pinned-') and l.endswith(t + '.log') for t, l in tags))

    def test_kept_runs_are_judged_without_playing_again(self):
        d = tempfile.mkdtemp()
        path = os.path.join(d, 'runs.jsonl')
        stamp = {'start_id': 'vanilla-ch3', 'set': 'tuning', 'version': 1}
        with open(path, 'w') as fh:
            for i, inst in enumerate(('old', 'i', 'i')):
                fh.write(json.dumps({'kind': 'bot', 'suite': stamp, 'seed': 1001, 'n': i,
                                     'instrument': inst, 'game': 'vanilla',
                                     'rom_hash': 'h'}) + '\n')
        play = mc.kept_play([path], 'i', {'vanilla': 'h'})
        got = list(play([{'seed': 1001, 'stamp': {'suite': stamp}},
                         {'seed': 1002, 'stamp': {'suite': stamp}}]))
        self.assertEqual([r['n'] for r in got], [2], 'the newest of this instrument; none for 1002')


class Story(unittest.TestCase):
    def test_story_turn_tells_that_turn_and_the_one_before(self):
        d = tempfile.mkdtemp()
        path = os.path.join(d, 't.jsonl')
        with open(path, 'w') as fh:
            for t in ([{'t': 'start', 'turn': 0}]
                      + [{'t': 'phase', 'phase': 'player', 'turn': n} for n in range(1, 6)]
                      + [{'t': 'end', 'turn': 5, 'record': {'outcome': 'won', 'turns': 5}}]):
                fh.write(json.dumps(t) + '\n')
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            mc.main(['story', path, '--turn', '3'])
        turns = re.findall(r'Turn (\d+)', buf.getvalue())
        self.assertEqual(turns, ['2', '3'])
        self.assertIn('Result: won', buf.getvalue())

    def test_a_run_reads_as_plain_text(self):
        battle = {'actor': {'charId': 0x10, 'hit': 40, 'crit': -1, 'weapon': 0x01, 'hpBefore': 18,
                            'hp': 18, 'levelUp': False, 'broke': False},
                  'target': {'charId': 0x01, 'hit': 90, 'crit': 5, 'weapon': 0x02,
                             'hpBefore': 22, 'hp': 8, 'levelUp': False, 'broke': False},
                  'hits': [{'by': 'actor', 'miss': False, 'crit': True, 'dmg': 14},
                           {'by': 'target', 'miss': True, 'crit': False, 'dmg': 0}]}
        events = [
            {'t': 'start', 'turn': 0, 'info': {'game': 'ours', 'chapter': 4, 'mode': 'normal',
                                               'seed': 3}, 'style': {'aggression': 'careful'},
             'claims_played': ['a']},
            {'t': 'phase', 'turn': 2, 'phase': 'enemy'},
            {'t': 'act', 'turn': 2, 'phase': 'enemy', 'unit': 0x10, 'from': {'x': 1, 'y': 1},
             'to': {'x': 2, 'y': 1}, 'battles': [battle]},
            {'t': 'event', 'turn': 3, 'kind': 'arrive', 'charId': 0x11, 'x': 0, 'y': 9,
             'faction': 'red'},
            {'t': 'end', 'turn': 3, 'record': {'outcome': 'won', 'turns': 3, 'clean': True}}]
        text = '\n'.join(mc.story(events, {0x10: 'The Ogre', 0x01: 'Braulo'}, {0x01: 'Iron Axe'}))
        self.assertIn('Turn 2, enemy phase.', text)
        self.assertIn('The Ogre attacks Braulo, from 1,1 to 2,1.', text)
        self.assertIn('The Ogre hits Braulo for 14, a critical', text)
        self.assertIn('Braulo misses', text)
        self.assertIn('Braulo 22 -> 8 HP', text)
        self.assertIn('hit 40% crit 0% with Iron Axe', text)
        self.assertIn('unit 0x11 arrives at 0,9 (red).', text)
        events[3]['units'] = [{'charId': 0x12, 'classId': 0x0E}]
        events.insert(3, {'t': 'phase', 'turn': 3, 'phase': 'player',
                          'units': [{'charId': 0x11, 'classId': 0x0E}]})
        battle['target']['canCounter'] = False
        text = '\n'.join(mc.story(events, {}, {}, {0x0E: 'Soldier'}))
        self.assertIn('the Soldier arrives', text, 'a unit without a name is its class')
        self.assertIn('cannot strike back', text)
        events.insert(1, {'t': 'phase', 'turn': 2, 'phase': 'enemy',
                          'units': [{'id': 0x02, 'charId': 0x01}, {'id': 0x85, 'charId': 0x13}]})
        events.insert(4, {'t': 'act', 'turn': 2, 'phase': 'enemy', 'unit': 0x13, 'act': 'steal',
                          'targetId': 0x02, 'from': {'x': 4, 'y': 4}, 'to': {'x': 5, 'y': 4}})
        events.insert(5, {'t': 'act', 'turn': 2, 'phase': 'enemy', 'unit': 0x13, 'act': 'pick',
                          'tile': {'x': 6, 'y': 2}, 'from': {'x': 5, 'y': 4}, 'to': {'x': 6, 'y': 2}})
        text = '\n'.join(mc.story(events, {0x01: 'Braulo'}, {}, {}))
        self.assertIn('steals from Braulo', text, 'a target by unit index, through the snapshot')
        self.assertIn('pillages the tile at 6,2', text)
        self.assertIn('Result: won on turn 3, clean.', text)
        events[-1]['record'] = {'outcome': 'won', 'turns': 3, 'clean': False,
                                'clear': {'won': True, 'lost': [], 'recruits_missing': [0x01],
                                          'rewards_missing': []}}
        text = '\n'.join(mc.story(events, {0x01: 'Braulo'}, {}, {}))
        self.assertIn('Result: won on turn 3, not clean: missed Braulo.', text)

    def test_story_prints_goal_moves(self):
        # a new plan's goals (planner.lua's goalWorth): each one whose chance it moves, with
        # its worth; one it leaves as it was is not printed
        events = [
            {'t': 'start', 'turn': 0, 'info': {'game': 'vanilla', 'chapter': 6}, 'style': {}},
            {'t': 'plan', 'turn': 4, 'worth': [
                {'id': 'visit:5,1', 'kind': 'visit', 'gold': 3000, 'worth': 120,
                 'before': 0.61, 'after': 0.52},
                {'id': 'objective:7', 'kind': 'objective', 'gold': 0, 'worth': 111,
                 'before': 0.4, 'after': 0.4}]}]
        text = '\n'.join(mc.story(events, {}, {}, {}))
        self.assertIn('goal visit:5,1 (worth 120): chance 0.61 -> 0.52', text)
        self.assertNotIn('objective:7', text)

    def test_names_items_and_classes_come_from_the_decomp(self):
        self.assertEqual(mc._names('vanilla')[0x01], 'Eirika')
        self.assertTrue(mc._items())
        self.assertEqual(mc._classes()[0x01], 'Lord')

    def test_manchego_stars_names_and_claims_share_one_cast_lookup(self):
        # a run's id names the cast member a claim with that name resolves to, a scene-only
        # guest whose slot keeps its vanilla nameplate included (Duvessa rides SELENA)
        import campaign_env as ce
        from inject.scene_actors import cast_pids
        names = mc._names('ours')
        for name, pid in cast_pids().items():
            self.assertEqual(ce._unit_id(name, 'ours', None), pid)
            self.assertEqual(names[pid], name.replace('-', ' ').title())

    def test_a_renamed_chapter_unit_reads_the_name_the_rom_prints(self):
        # #590: ch02's Rime Spark rides KLIMT (0xC9) and a story printed "Klimt". Every pid the
        # build renamed reads the ROM's name, a name two rows share included (Ravisin rides both
        # of Riev's rows), and a pid it did not rename keeps the decomp's enum name
        import inject.decomp
        import inject.text
        vanilla = {0xC9: 'Klimt', 0x28: 'Riev', 0x57: 'Riev', 0x95: 'Enemy', 0x83: 'Soldier'}
        rom = {0xC9: 'Rime', 0x28: 'Ravisin', 0x57: 'Ravisin', 0x95: 'Raider', 0x83: 'Soldier'}
        tables = {inject.decomp.vanilla_decomp_text: vanilla, inject.decomp.rom_text: rom}
        mc._names.cache_clear()
        try:
            with mock.patch.object(inject.text, 'character_names', tables.__getitem__), \
                    mock.patch('inject.scene_actors.cast_pids', dict):
                names = mc._names('ours')
                vanilla_game = mc._names('vanilla')
        finally:
            mc._names.cache_clear()
        self.assertEqual((names[0xC9], names[0x28], names[0x57]), ('Rime', 'Ravisin', 'Ravisin'))
        self.assertEqual(names[0x95], 'Raider')
        self.assertEqual(names[0x83], 'Soldier 83')
        self.assertEqual(vanilla_game[0xC9], 'Klimt')

    def test_names_say_when_they_come_from_another_build(self):
        with tempfile.TemporaryDirectory() as d:
            rom = os.path.join(d, 'fireemblem8.gba')
            with open(rom, 'wb') as fh:
                fh.write(b'rom')
            built = mc.sha1_file(rom)
            with mock.patch.object(matrix, 'ROM_PATH', rom):
                self.assertIsNone(mc.names_note('ours', [built[:12]]))
                self.assertIsNone(mc.names_note('vanilla', ['abc']))
                self.assertIn('abc', mc.names_note('ours', [built[:12], 'abc']))
                # a run that recorded no ROM cannot be matched (#591 review)
                self.assertIn('unrecorded', mc.names_note('ours', [built[:12], None]))
                # the names' sources rewritten after the ROM was built (an injection in flight,
                # or a `git checkout` back to vanilla): the ROM's hash still matches
                src = os.path.join(d, 'src')
                os.makedirs(src)
                chars = os.path.join(src, 'data_characters.c')
                with open(chars, 'w') as fh:
                    fh.write('')
                os.utime(chars, (os.path.getmtime(rom) + 10,) * 2)
                self.assertIn('changed since', mc.names_note('ours', [built[:12]]))
            with mock.patch.object(matrix, 'ROM_PATH', os.path.join(d, 'none.gba')):
                self.assertIn('no ROM is built', mc.names_note('ours', [built[:12]]))

# ---- the failure audit (#510 step 9 PR-F, FR-019/FR-020, SC-004) ----

# a run's identity: the suite reruns a start under every instrument, so only its filed trace
# tells two runs of one campaign, seed, chapter and attempt apart
RUN = {'game': 'ours', 'chapter': 2, 'seed': 3, 'attempt': 1, 'trace': 't.jsonl'}


def _rec(*deaths, trace='t.jsonl'):
    return dict(RUN, outcome='lost', deaths=list(deaths), trace=trace)


def _death(cid=0x01, turn=4, ref=17, cause='fog'):
    return {'charId': cid, 'faction': 'blue', 'turn': turn, 'killer': 0x40, 'plan_ref': ref,
            'cause': cause}


def _plan(ref=17, considered=None):
    # the trace's `plan` event at decision `ref` (planner.lua, T076): `considered` is every judged
    # plan, the played ['a'] first, ['b'] ranked below it, ['c'] over the cap, ['e'] stalled;
    # ['d'] was offered and never judged as a plan (the beam cut it)
    if considered is None:
        considered = [{'acts': ['a'], 'played': True, 'rejected': None},
                      {'acts': ['b'], 'rejected': 'outranked'},
                      {'acts': ['c'], 'rejected': 'over_cap'},
                      {'acts': ['e'], 'rejected': 'stalled'}]
    return {'t': 'plan', 'turn': 4, 'ref': ref, 'considered': considered, 'audit': {
        'offered_n': 5, 'visibility': {'seen': 5, 'fogged': 2},
        'budget': {'exhausted': False, 'averaged': 0}}}


OFFERED = ('a', 'b', 'c', 'd', 'e')   # the acts the game offered on the boards they were played on


def _diag(mode='force', chosen=('b',), avoided=True, matched=True, cid=0x01, turn=4, ref=17,
          trace='t.jsonl', unoffered=None):
    # `unoffered` (harness.lua): each played act Bot.candidates did not offer on the board it
    # was played on
    chosen = list(chosen)
    if unoffered is None:
        unoffered = [k for k in chosen if k not in OFFERED]
    # `planned`: the diagnostic's whole plan; `chosen`: the acts of it actually played (all of
    # them here, as no line below is broken)
    return {'run': dict(RUN, trace=trace), 'ref': ref, 'mode': mode, 'matched': matched,
            'baseline': ['a'], 'planned': chosen, 'chosen': chosen, 'differs': chosen != ['a'],
            'avoided': avoided,
            'failure': {'charId': cid, 'turn': turn}, 'trace': 'diag-%s.jsonl' % mode,
            'unoffered': unoffered}


class Audit(unittest.TestCase):
    def audit(self, recs, diags, events=None):
        events = [_plan()] if events is None else events
        return mc.audit(recs, diags, lambda r: events)

    def test_a_label_is_witnessed_only_by_a_matched_replay_of_a_different_plan_that_avoids(self):
        # AS 1: the forced plan ['b'] was kept but ranked below the played ['a'], and it avoided
        # the death from the same pinned state: mis-scored, cited with its replay
        [f] = self.audit([_rec(_death())], [_diag()])
        self.assertEqual(f['labels'], ['mis_scored'])
        self.assertEqual(f['primary'], 'mis_scored')
        self.assertEqual([w['trace'] for w in f['witnesses']], ['diag-force.jsonl'])
        # none of these is a witness: the same plan, a fork that did not match the original's
        # board, a replay that did not avoid the death, a replay of another failure
        for d in (_diag(chosen=['a']), _diag(matched=False), _diag(avoided=False),
                  _diag(cid=0x02), _diag(turn=5), _diag(trace='another-run.jsonl')):
            [f] = self.audit([_rec(_death())], [d])
            self.assertEqual(f['labels'], [], d)
            self.assertIsNone(f['primary'], d)

    def test_a_line_from_before_planned_was_recorded_claims_nothing(self):
        # before the replay recorded `planned` and `broken`, a stop at the pin printed avoided
        # true, and a full-information plan could use acts only the fog-off board offered: such
        # a line is stale until it is re-run
        for mode in ('force', 'deep', 'full_info'):
            old = _diag(mode=mode)
            del old['planned']
            [f] = self.audit([_rec(_death())], [old])
            self.assertEqual(f['labels'], [], mode)
            self.assertIn('re-run it', ' '.join(f['notes']))

    def test_a_forced_plan_is_placed_by_its_whole_plan(self):
        # the plan the planner judged is the whole one (`planned`), whatever `chosen` holds
        [f] = self.audit([_rec(_death())], [dict(_diag(), chosen=['b', 'x'], planned=['b'])])
        self.assertEqual(f['labels'], ['mis_scored'])

    def test_a_replay_that_failed_is_shown_as_failed_not_as_not_avoiding(self):
        # vanilla chapter 7 (T079 re-run): the replay matched, then the planner raised; the unit
        # died because the run stopped, which says nothing about the plan
        line = dict(_diag(avoided=False), outcome='crashed',
                    why="Lua error: planner.lua:343: attempt to index nil")
        findings = self.audit([_rec(_death())], [line])
        self.assertIn('REPLAY FAILED: force: Lua error', ' '.join(findings[0]['notes']))
        self.assertIn('1 with a failed replay', mc.coverage(findings))
        # every replay that reached its pin ends with a reason: that is no failure
        [f] = self.audit([_rec(_death())], [dict(_diag(), outcome='diag',
                                                 why="the failure's turn is over")])
        self.assertEqual(f['labels'], ['mis_scored'])

    def test_a_broken_replay_is_no_witness(self):
        # the replay could not play the plan it chose to the end (`broken`): `chosen` is what it
        # did play, and a plan cut short avoided nothing on its own
        [f] = self.audit([_rec(_death())], [dict(_diag(), broken='the act was refused')])
        self.assertEqual(f['labels'], [])
        self.assertIn('broken', ' '.join(f['notes']))

    def test_a_missing_action_is_judged_on_the_board_each_act_was_played_on(self):
        # the pinned board offered 'b', the board it was played on did not: missing_action.
        # 'z', offered where it was played and never judged at the pin: the search cut it
        [f] = self.audit([_rec(_death())], [_diag(unoffered=['b'])])
        self.assertEqual(f['labels'], ['missing_action'])
        [f] = self.audit([_rec(_death())], [_diag(chosen=['z'], unoffered=[])])
        self.assertEqual(f['labels'], ['search_miss'])
        # a forced line that never checked (an older harness): nothing is claimed
        old = _diag()
        del old['unoffered']
        [f] = self.audit([_rec(_death())], [old])
        self.assertEqual(f['labels'], [])
        self.assertIn('unoffered', ' '.join(f['notes']))

    def test_a_trace_is_read_only_for_a_run_a_diag_line_replays(self):
        read = []
        recs = [_rec(_death(), trace='a.jsonl'), _rec(_death(), trace='b.jsonl')]
        mc.audit(recs, [_diag(trace='b.jsonl')], lambda r: read.append(r['trace']) or [_plan()])
        self.assertEqual(read, ['b.jsonl'])

    def test_a_replay_that_trades_the_death_for_another_is_no_witness(self):
        # ours-ch03 seed 1002 (T079): the forced plan saved unit 3, and the boss killed unit 5
        # instead. That moves the failure, it does not avoid it
        d = dict(_diag(avoided=False), traded=[0x05])
        [f] = self.audit([_rec(_death())], [d])
        self.assertEqual(f['labels'], [])
        self.assertIn('traded it for 0x05', ' '.join(f['notes']))
        # a line that says avoided while naming a trade is never read as a witness either
        [f] = self.audit([_rec(_death())], [dict(_diag(), traded=[0x05])])
        self.assertEqual(f['labels'], [])

    def test_the_newest_line_of_a_replay_supersedes_the_older(self):
        # a replay re-run (a stricter `avoided`) appends a new line; the newest one counts
        old, new = _diag(), _diag(avoided=False)
        [f] = self.audit([_rec(_death())], [old, new])
        self.assertEqual((f['labels'], f['notes']), ([], ['force: did not avoid it']))
        [f] = self.audit([_rec(_death())], [new, old])
        self.assertEqual(f['labels'], ['mis_scored'])
        # another plan forced at the same decision is another replay, kept beside it
        [f] = self.audit([_rec(_death())], [old, _diag(chosen=['z'], avoided=False)])
        self.assertEqual(f['labels'], ['mis_scored'])
        self.assertEqual(len(f['notes']), 1)

    def test_each_witness_says_which_label_it_supports(self):
        cases = {('force', 'b'): 'mis_scored', ('force', 'c'): 'mis_predicted_safety',
                 ('force', 'd'): 'search_miss', ('force', 'z'): 'missing_action',
                 ('force', 'b', 'z'): 'missing_action',
                 ('deep', 'b'): 'search_miss', ('full_info', 'b'): 'information_unavailable'}
        for (mode, *keys), label in cases.items():
            [f] = self.audit([_rec(_death())], [_diag(mode=mode, chosen=keys)])
            self.assertEqual(f['labels'], [label], (mode, keys))

    def test_a_forced_witness_without_the_plans_audit_stays_unresolved(self):
        # the trace has no audit at that decision: the replay avoided the death, but which
        # label it supports cannot be told, so none is claimed
        [f] = self.audit([_rec(_death())], [_diag()], events=[{'t': 'plan', 'ref': 17}])
        self.assertEqual(f['labels'], [])
        self.assertIn('no plan audit', ' '.join(f['notes']))
        # a stalled plan may not be played: that it avoided the death places nothing
        [f] = self.audit([_rec(_death())], [_diag(chosen=['e'])])
        self.assertEqual(f['labels'], [])
        self.assertIn('stalled', ' '.join(f['notes']))

    def test_an_unmatched_replay_is_shown_never_dropped(self):
        # the fork's board differed from the original's before the pinned decision (a hash
        # seeded per process, say): it witnesses nothing, and the audit and SC-004 say so
        findings = self.audit([_rec(_death())], [_diag(matched=False)])
        text = '\n'.join(mc.audit_lines(findings))
        self.assertIn('UNMATCHED', text)
        self.assertIn('1 with an UNMATCHED replay', mc.coverage(findings))

    def test_an_unwitnessed_explanation_stays_unresolved(self):
        # AS 2: the run's own grading says fog, and nothing replayed it: unclassified, and the
        # grading is shown as proposed, never as the label
        recs = [_rec(_death())]
        [f] = self.audit(recs, [])
        self.assertIsNone(f['primary'])
        text = '\n'.join(mc.audit_lines(self.audit(recs, [])))
        self.assertIn('unclassified', text)
        self.assertIn('proposed: fog, not witnessed', text)
        self.assertNotIn('information_unavailable', text)

    def test_every_supported_label_plus_a_primary_and_unclassified_kept(self):
        recs = [_rec(_death(), _death(cid=0x02, turn=6, ref=30))]
        diags = [_diag(mode='full_info'), _diag(mode='force', chosen=['z'])]
        f, g = self.audit(recs, diags, [_plan(), _plan(ref=30)])
        self.assertEqual(f['labels'], ['missing_action', 'information_unavailable'])
        self.assertEqual(f['primary'], 'missing_action', 'a defect the bot owns comes first')
        self.assertIsNone(g['primary'])
        text = '\n'.join(mc.audit_lines([f, g]))
        self.assertIn('primary missing_action; supported: missing_action, information_unavailable',
                      text)
        self.assertIn('unclassified', text)

    def test_the_audit_prints_the_sc004_coverage_sentence(self):
        recs = [_rec(_death(), _death(cid=0x02, turn=6, ref=30))]
        findings = self.audit(recs, [_diag()], [_plan(), _plan(ref=30)])
        self.assertEqual(mc.coverage(findings, 'abc+v1'),
                         'SC-004 (instrument abc+v1): 1 of 2 audited failures (50%) have a '
                         'witnessed label; 1 unclassified. The bar is 90%: not met.')
        self.assertEqual(mc.coverage([], 'abc+v1'),
                         'SC-004 (instrument abc+v1): no failures to audit.')

    def test_audit_reads_the_runs_traces_and_diag_logs(self):
        d = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, d)
        with open(os.path.join(d, 'runs.jsonl'), 'w') as fh:
            fh.write(json.dumps(_rec(_death(), trace='traces/t.jsonl')) + '\n')
            fh.write(json.dumps({'kind': 'campaign', 'outcome': 'done'}) + '\n')
        os.makedirs(os.path.join(d, 'traces'))
        with open(os.path.join(d, 'traces', 't.jsonl'), 'w') as fh:
            fh.write(json.dumps(_plan()) + '\n')
        log = os.path.join(d, 'mgba-stdout.log')
        with open(log, 'w') as fh:
            fh.write('[f120] noise\n[f121] DIAG %s\n' % json.dumps(_diag(trace='traces/t.jsonl')))
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            self.assertEqual(mc.main(['audit', os.path.join(d, 'runs.jsonl'), '--diag', log]), 0)
        out = buf.getvalue()
        self.assertIn('primary mis_scored', out)
        self.assertIn('story %s' % os.path.join(d, 'diag-force.jsonl'), out,
                      "a witness's trace, named relative to its diag file")
        self.assertIn('SC-004 (instrument None): 1 of 1 audited failures (100%)', out)

    def run_audit(self, recs, diags, *extra):
        d = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, d)
        with open(os.path.join(d, 'runs.jsonl'), 'w') as fh:
            for r in recs:
                fh.write(json.dumps(r) + '\n')
        log = os.path.join(d, 'diag.jsonl')
        with open(log, 'w') as fh:
            for g in diags:
                fh.write('DIAG %s\n' % json.dumps(g))
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            self.assertEqual(mc.main(['audit', os.path.join(d, 'runs.jsonl'), '--diag', log]
                                     + list(extra)), 0)
        return buf.getvalue()

    def test_audit_reads_one_instrument_the_newest_unless_asked(self):
        # the suite reruns a start under every instrument: two instruments' failures are two
        # different bots', and one SC-004 sentence over both would measure neither
        old = dict(_rec(_death(), trace='a.jsonl'), instrument='old')
        new = dict(_rec(_death(cid=0x02), trace='b.jsonl'), instrument='new')
        out = self.run_audit([old, new], [])
        self.assertIn('SC-004 (instrument new): 0 of 1 audited failures', out)
        self.assertNotIn('lost 0x01', out)
        out = self.run_audit([old, new], [], '--instrument', 'old')
        self.assertIn('SC-004 (instrument old): 0 of 1 audited failures', out)
        self.assertNotIn('lost 0x02', out)

    def test_a_diag_line_that_matches_no_record_is_an_orphan_never_dropped(self):
        # a stale line (its run gone from the store, or a death the run no longer has) is
        # counted apart, with its run, like an UNMATCHED replay; one for another instrument's
        # run belongs to that instrument's audit and is not an orphan here
        old = dict(_rec(_death(), trace='a.jsonl'), instrument='old')
        new = dict(_rec(_death(), trace='b.jsonl'), instrument='new')
        stale, other = _diag(trace='gone.jsonl'), _diag(trace='a.jsonl')
        out = self.run_audit([old, new], [stale, other, _diag(trace='b.jsonl', cid=0x07)])
        self.assertEqual(out.count('orphan (no record matches its run)'), 2, out)
        self.assertIn("'trace': 'gone.jsonl'", out)
        self.assertIn('2 orphan DIAG lines', out)


class Replay(unittest.TestCase):
    """`replay`: one diagnostic replay of a suite run's death (T074's driver). It plays the
    run's own suite task with PT_DIAG, and keeps only DIAG lines: never a record (FR-019)."""

    def rec(self, **kw):
        r = dict(RUN, campaign='e1-ours-ch07', outcome='lost', trace='traces/t.jsonl.gz',
                 deaths=[_death()], suite={'start_id': 'ours-ch02', 'set': 'tuning', 'version': 1})
        r.update(kw)
        return r

    def test_the_diag_names_the_death_its_decision_and_the_original_trace(self):
        d = mc.replay_diag(self.rec(), 'force', ['b'], base='/runs')
        self.assertEqual(d, {'ref': 17, 'ref_from': 'plan_ref', 'mode': 'force', 'force': ['b'],
                             'failure': {'charId': 0x01, 'turn': 4},
                             'original_trace': '/runs/traces/t.jsonl.gz',
                             'run': dict(RUN, campaign='e1-ours-ch07',
                                         trace='traces/t.jsonl.gz')})
        two = self.rec(deaths=[_death(), _death(cid=0x02, turn=6, ref=30)])
        self.assertEqual(mc.replay_diag(two, 'deep', char=0x02, base='/r')['ref'], 30)
        self.assertEqual(mc.replay_diag(two, 'deep', char=0x02, ref=29, base='/r')['ref'], 29)

    def test_a_replays_run_matches_its_record_and_no_other(self):
        # one owner of a run's identity: the run a replay names is the record it was made from
        rec, twin = self.rec(), self.rec(trace='traces/other.gz')
        d = mc.replay_diag(rec, 'deep', base='/r')
        line = {'run': d['run'], 'failure': d['failure']}
        self.assertTrue(mc.diag_of(line, rec, rec['deaths'][0]))
        self.assertFalse(mc.diag_of(line, twin, twin['deaths'][0]))
        self.assertEqual(mc.find_record([twin, rec], mc.run_name(rec)), rec)

    def test_a_death_with_no_decision_to_pin_is_refused(self):
        # a greedy phase's death: no plan committed to it and none moved the unit
        rec = self.rec(deaths=[dict(_death(), plan_ref=None)])
        with self.assertRaisesRegex(ValueError, 'no decision to pin'):
            mc.replay_diag(rec, 'deep', base='/r')

    def test_a_replay_under_another_instrument_is_refused(self):
        # a newer planner would play the diagnostic, and its witness count toward the old one
        rec = self.rec(instrument='old+v1')
        with self.assertRaisesRegex(ValueError, 'instrument'):
            mc.replay_diag(rec, 'deep', base='/r', instrument='new+v1')
        self.assertEqual(mc.replay_diag(rec, 'deep', base='/r', instrument='old+v1')['ref'], 17)

    def test_a_seed_gone_from_the_suite_is_refused_not_a_crash(self):
        suite = {'version': 1, 'starts': [
            {'start_id': 'ours-ch02', 'game': 'ours', 'chapter': 3,
             'provenance': {'campaign': 'e1-ours-ch07'},
             'seeds': {'tuning': [1001, 1002], 'held_out': [2001, 2002]}}]}
        for rec in (self.rec(seed=1003), self.rec(suite={'start_id': 'gone', 'set': 'tuning'})):
            with self.assertRaisesRegex(ValueError, 'no longer'):
                mc.replay_task(rec, suite, {'ours': {}}, {}, 'inst')

    def test_a_records_trace_is_read_relative_to_the_runs_file(self):
        d = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, d)
        with open(os.path.join(d, 't.jsonl'), 'w') as fh:
            fh.write(json.dumps(_plan()) + '\n')
        self.assertEqual(mc.record_events({'trace': 't.jsonl'}, d), [_plan()])
        self.assertEqual(mc.record_events({'trace': 'gone.jsonl'}, d), [])
        self.assertEqual(mc.record_events({}, d), [])

    def test_the_record_is_the_newest_of_its_name_unless_a_trace_picks_one(self):
        old, new = self.rec(trace='traces/old.gz'), self.rec(trace='traces/new.gz')
        other = self.rec(seed=9, trace='traces/x.gz')
        spec = 'e1-ours-ch07/3/2/1'
        self.assertIs(mc.find_record([old, other, new], spec), new)
        self.assertIs(mc.find_record([old, other, new], spec, 'traces/old.gz'), old)
        with self.assertRaisesRegex(ValueError, 'no record is'):
            mc.find_record([other], spec)
        with self.assertRaisesRegex(ValueError, 'no record is'):
            mc.find_record([old, new], spec, 'traces/gone.gz')

    def test_the_default_decision_is_the_last_that_moved_the_dead_unit(self):
        # ours-ch03 seed 1002 (T079): unit 3 struck under plan 45 as a KEPT act (a plan event
        # with no ref of its own), and died in the enemy phase plan 46 committed to; 46 never
        # moved it, so a replay pinned there could not change what killed it
        events = [{'t': 'plan', 'turn': 2, 'ref': 44},
                  {'t': 'act', 'turn': 2, 'phase': 'player', 'unit': 0x03},
                  {'t': 'plan', 'turn': 2, 'ref': 45},
                  {'t': 'act', 'turn': 2, 'phase': 'player', 'unit': 0x04},
                  {'t': 'plan', 'turn': 2, 'kept': True},
                  {'t': 'act', 'turn': 2, 'phase': 'player', 'unit': 0x03},
                  {'t': 'plan', 'turn': 2, 'ref': 46},
                  {'t': 'act', 'turn': 2, 'phase': 'player', 'unit': 0x05},
                  {'t': 'act', 'turn': 2, 'phase': 'enemy', 'unit': 0x03,
                   'fell': [{'charId': 0x03}]},
                  {'t': 'plan', 'turn': 3, 'ref': 47},
                  {'t': 'act', 'turn': 3, 'phase': 'player', 'unit': 0x03}]
        rec = self.rec(deaths=[_death(cid=0x03, turn=2, ref=46)])
        d = mc.replay_diag(rec, 'deep', base='/r', events=events)
        self.assertEqual((d['ref'], d['ref_from']), (45, 'act'))
        # nothing moved it: the plan that committed to its death, said so
        d = mc.replay_diag(rec, 'deep', base='/r', events=events[6:])
        self.assertEqual((d['ref'], d['ref_from']), (46, 'plan_ref'))
        d = mc.replay_diag(rec, 'deep', ref=40, base='/r', events=events)
        self.assertEqual((d['ref'], d['ref_from']), (40, 'asked'))

    def test_a_replay_is_refused_with_its_reason(self):
        two = self.rec(deaths=[_death(), _death(cid=0x02, turn=6, ref=30)])
        for rec, mode, force, char, why in (
                (self.rec(suite=None), 'deep', None, None, 'not a suite run'),
                (self.rec(suite={'start_id': 'x', 'set': 'held_out'}), 'deep', None, None,
                 'held-out'),
                (two, 'deep', None, None, 'name one with --char'),
                (self.rec(), 'deep', None, 0x09, 'no death of 0x09'),
                (self.rec(), 'force', None, None, 'needs --force'),
                (self.rec(), 'deep', ['b'], None, 'only with force'),
                (self.rec(trace=None), 'deep', None, None, 'no kept trace')):
            with self.assertRaisesRegex(ValueError, why):
                mc.replay_diag(rec, mode, force, char, base='/r')

    def test_the_task_is_the_runs_own_suite_task_plus_the_diag(self):
        suite = {'version': 1, 'starts': [
            {'start_id': 'ours-ch02', 'game': 'ours', 'chapter': 3,
             'provenance': {'campaign': 'e1-ours-ch07'},
             'seeds': {'tuning': [1001, 1002], 'held_out': [2001, 2002]}},
            {'start_id': 'other', 'game': 'ours', 'chapter': 4,
             'provenance': {'campaign': 'e1-ours-ch07'},
             'seeds': {'tuning': [1001, 1002], 'held_out': [2001, 2002]}}]}
        rec = self.rec(seed=1002)
        diag = {'ref': 17}
        t = mc.replay_task(rec, suite, {'ours': {'name': 'ours'}}, diag, 'inst')
        self.assertEqual((t['campaign']['from'], t['seed'], t['instrument'], t['diag']),
                         (3, 1002, 'inst', diag))
        self.assertNotIn('out', t, 'a replay never writes a runs file')
        self.assertNotIn('stamp', t)

    def test_launch_passes_the_diag_to_run_sh(self):
        seen = {}

        def run(cmd, env, **kw):
            seen.update(env)
        d = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, d)
        with mock.patch.object(mc.subprocess, 'run', run):
            mc.launch({'seed': 1, 'instrument': 'i', 'diag': {'ref': 3}}, 'tag',
                      os.path.join(d, 'log'))
        self.assertEqual(json.loads(seen['PT_DIAG']), {'ref': 3})
        seen.clear()
        with mock.patch.object(mc.subprocess, 'run', run):
            mc.launch({'seed': 1, 'instrument': 'i', 'bench': [2]}, 'tag',
                      os.path.join(d, 'log'))
        self.assertEqual(json.loads(seen['PT_BENCH']), [2])

    def test_only_diag_lines_are_kept_and_the_witness_trace_is_filed(self):
        base, root = tempfile.mkdtemp(), tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, base)
        self.addCleanup(shutil.rmtree, root)
        where = mc.run_dir('campaign', 'tag', root)

        def launch(task, tag, log_path):
            os.makedirs(where)
            with open(os.path.join(where, 'diag-trace.jsonl'), 'w') as fh:
                fh.write(json.dumps(_plan()) + '\n')
            with open(os.path.join(where, 'pinned-ours-2-a1-r17.ss'), 'wb') as fh:
                fh.write(b'state')
            text = ('[f1] BOTRUN {"outcome": "lost"}\n[f2] DIAG %s\n'
                    % json.dumps(dict(_diag(), trace='diag-trace.jsonl')))
            return text, where
        diags = mc.replay_run({'seed': 1}, base, launch=launch, run_root=root)
        self.assertEqual(len(diags), 1)
        self.assertFalse(os.path.exists(os.path.join(base, 'runs.jsonl')), 'no record written')
        with open(os.path.join(base, 'diag.jsonl')) as fh:
            [kept] = mc.parse_lines(fh.read(), mc.DIAG)
        self.assertTrue(kept['trace'].startswith('traces/diag/'))
        self.assertEqual(mc.read_trace(os.path.join(base, kept['trace'])), [_plan()])
        self.assertFalse(os.path.exists(where), "a replay that reported leaves no dir")
        # the pinned decision's state is a fixture (T084): filed beside the trace, and named
        self.assertTrue(kept['pinned'].startswith('traces/diag/'), kept['pinned'])
        self.assertTrue(kept['pinned'].endswith('pinned-ours-2-a1-r17.ss'))
        with open(os.path.join(base, kept['pinned']), 'rb') as fh:
            self.assertEqual(fh.read(), b'state')


def played(deaths=(), env='clean', outcome='won', **kw):
    """A played attempt-1 record as botrun.lua writes one, each death a dict (blue unless
    said), and its chapter_result."""
    rec = dict({'kind': 'bot', 'chapter': 4, 'attempt': 1, 'outcome': outcome,
                'env_status': env, 'deaths': [dict({'faction': 'blue', 'turn': 3}, **d)
                                              for d in deaths]}, **kw)
    return {'status': 'played', 'rec': rec, 'died': bool(deaths)}


class Validity(unittest.TestCase):
    """PR-I, T100 (FR-029, AS 1): each invariant, failed alone, makes the cell NOT READABLE
    and names it."""

    TAIL = {'cause': 'rng_tail', 'charId': 1, 'predicted': 0.2}

    def results(self, ours=None, vanilla=None, n=20):
        """{arm: [chapter_result]}: n attempts an arm, a fifth losing someone to a lost roll
        (valid everywhere), the first ones replaced by `ours`/`vanilla`."""
        def arm(first):
            got = list(first or [])
            return got + [played([self.TAIL] if i % 5 == 0 else []) for i in range(n - len(got))]
        return {'ours': arm(ours), 'vanilla': arm(vanilla)}

    def verdict(self, results):
        pairs = [(o['died'] if o['status'] == 'played' else None,
                  v['died'] if v['status'] == 'played' else None)
                 for o, v in zip(results['ours'], results['vanilla'])]
        return mc.judged(mc.paired_verdict(pairs * 10, 24, 'paired', look=200),
                         mc.validity(results))

    def test_a_valid_cell_keeps_its_verdict(self):
        v = self.verdict(self.results())
        self.assertEqual(v['verdict'], 'EQUIVALENT')
        self.assertEqual(mc.validity(self.results()), {'failed': [], 'withheld': [],
                                                       'unread': []})

    def test_each_invariant_failed_alone_is_not_readable_and_named(self):
        unresolved = {'status': 'unresolved', 'rec': {'outcome': 'crashed', 'env_status': {
            'fault': 'crash', 'outcome_dependent': True}}}
        cases = {
            # 3 of 20 attempts with no game result: 85% clean, under 0.90
            'environment_clean': self.results(ours=[unresolved] * 3),
            'sandbox_fault': self.results(ours=[played([{'cause': 'other', 'charId': 2,
                                                         'detail': 'missing_prediction'}])]),
            # 2 of 20 attempts (10%) lost someone the plan could not see: at the bar fails
            'blindspot': self.results(vanilla=[played([{'cause': 'other', 'charId': 2,
                                                        'detail': 'unrevealed_killer'}]),
                                               played([{'charId': 3}])]),   # unclassified
            'unlabelled_over_cap': self.results(ours=[played([{'cause': 'over_cap', 'charId': 2,
                                                               'over_cap': True}])]),
            'unjustified_seize_skip': self.results(ours=[played(seize_skips=[
                {'turn': 4, 'justified': False}])]),
            'vanilla_deaths': self.results(vanilla=[played([self.TAIL])] * 17),
        }
        for name, results in cases.items():
            with self.subTest(name):
                failed = [n for n, _ in mc.validity(results)['failed']]
                self.assertEqual(failed, [name])
                v = self.verdict(results)
                self.assertEqual((v['verdict'], v['failed_invariants'], v['settled']),
                                 ('NOT_READABLE', [name], True))
                self.assertIn('NOT READABLE', v['reason'])
        self.assertEqual(sorted(cases), sorted(mc.VALIDITY), 'every invariant is tested')

    def test_the_bars_are_the_specs(self):
        # just inside each bar holds: 18 of 20 clean, 1 of 20 blind, the twin losing 16 of 20
        self.assertEqual(mc.validity(self.results(
            ours=[{'status': 'unresolved', 'rec': {'env_status': {'fault': 'crash'}}}] * 2,
            vanilla=[played([{'cause': 'other', 'charId': 2, 'detail': 'noncombat'}])]
            + [played([self.TAIL])] * 14)), {'failed': [], 'withheld': [], 'unread': []})

    def test_an_over_cap_death_a_fallback_names_is_no_failure(self):
        ok = played([{'cause': 'over_cap', 'charId': 2, 'over_cap': True}],
                    anomalies=[{'kind': 'fallback_sacrifice', 'turn': 3}])
        self.assertEqual(mc.validity(self.results(ours=[ok]))['failed'], [])
        # a justified seize skip is no failure either
        self.assertEqual(mc.validity(self.results(ours=[played(seize_skips=[
            {'turn': 4, 'justified': True}])]))['failed'], [])

    def test_an_outcome_dependent_fault_in_a_played_attempt_withholds(self):
        watch = played(env={'fault': 'watch', 'outcome_dependent': True})
        valid = mc.validity(self.results(ours=[watch]))
        self.assertEqual(valid['failed'], [])
        self.assertEqual(len(valid['withheld']), 1)
        self.assertIn('outcome-dependent', valid['withheld'][0])
        v = mc.judged({'verdict': 'HARDER', 'look': 50, 'settled': True}, valid)
        # settled: the faulted attempt is in every later look, so more pairs never clear it
        self.assertEqual((v['verdict'], v['settled']), ('WITHHELD', True))
        # a pilot has no verdict to withhold
        self.assertIsNone(mc.judged({'verdict': None}, valid)['verdict'])
        # a verdict already withheld keeps its own reason, the fault appended
        v = mc.judged({'verdict': 'WITHHELD', 'look': 50, 'settled': False,
                       'reason': 'withheld at 50 replicates: reach unknown'}, valid)
        self.assertEqual((v['verdict'], v['settled']), ('WITHHELD', True))
        self.assertTrue(v['reason'].startswith('withheld at 50 replicates: reach unknown; '))
        self.assertIn('outcome-dependent', v['reason'])

    def test_an_arm_with_no_attempt_is_not_read_never_passed(self):
        valid = mc.validity({'ours': [played()] * 5, 'vanilla': [{'status': 'unreached'}]})
        self.assertEqual(valid, {'failed': [], 'withheld': [], 'unread': ['vanilla']})
        self.assertEqual(mc.validity_lines(valid),
                         ['validity (FR-029): not read, vanilla',
                          '  vanilla: not read, no attempt reached the chapter'])
        self.assertEqual(mc.validity_lines({'failed': [], 'withheld': ['w'], 'unread': []}),
                         ['validity (FR-029): withheld', '  withheld: w'])
        # a pilot's NOT READABLE reason has no look to name
        v = mc.judged({'verdict': None}, {'failed': [('blindspot', 'x')], 'withheld': []})
        self.assertEqual(v['reason'], 'NOT READABLE: x')

    def test_the_first_death_is_the_earliest(self):
        rec = played([{'cause': 'fog', 'charId': 1, 'turn': None},
                      {'cause': 'rng_tail', 'charId': 2, 'turn': 4},
                      {'cause': 'over_cap', 'charId': 3, 'turn': 4}])['rec']
        # no turn sorts last; a same-turn tie keeps the watch's order
        self.assertEqual(mc.first_death(rec)['charId'], 2)
        self.assertIsNone(mc.first_death(played()['rec']))

    def test_a_cell_that_fails_one_stops_at_that_look(self):
        def fate(name, seed, chapter):
            deaths = [{'charId': 1, 'faction': 'blue', 'cause': 'other', 'turn': 2,
                       'detail': 'forecast_desync'}] if name == 'ours' and seed == 7 else []
            return [{'chapter': chapter, 'attempt': 1, 'outcome': 'won', 'deaths': deaths,
                     'env_status': 'clean'}, {'kind': 'campaign', 'outcome': 'done'}]
        log = []
        v = mc.run_cell(Cell().sides(), Cell().play(fate, log), 24, 'paired')
        self.assertEqual((v['look'], v['verdict'], v['failed_invariants']),
                         (50, 'NOT_READABLE', ['sandbox_fault']))
        self.assertEqual(len(log), 100, 'no seed past the first look plays')
        self.assertEqual(mc.validity_lines(v['validity'])[0],
                         'validity (FR-029): NOT READABLE, sandbox_fault')


class Report(unittest.TestCase):
    """PR-I, T102 (FR-031, FR-032): the report in sentences, the anomalies' story
    commands, and each decision reading only its own components beside the twin."""

    def cell(self, verdict='HARDER', **kw):
        return dict({'kind': 'cell', 'cell_kind': 'chapter', 'chapter': 3, 'twin_index': 3,
                     'instrument': 'i+v2', 'verdict': verdict, 'lo': 0.04, 'hi': 0.19,
                     'diff': 0.12, 'pairs': 100, 'games': 'over 10 Manchego Stars games and 10 '
                     'vanilla games',
                     'failed_invariants': [], 'validity': {'failed': [], 'withheld': []},
                     'cpu_s': 7200.0}, **kw)

    def arms(self):
        boss = {'cause': 'rng_tail', 'charId': 2, 'flags': {'boss': True}, 'turn': 4}
        ours = [played([boss], turns_to_win=15, anomalies=[
                    {'kind': 'fallback_sacrifice', 'turn': 4,
                     'narrate': 'python3 tools/playtest/montecarlo.py story t.jsonl.gz --turn 4'}],
                       missed_rewards=[{'reason': 'skipped'}])['rec'],
                played([{'cause': 'over_cap', 'charId': 3, 'flags': {'boss': True}, 'turn': 9},
                        {'faction': 'green', 'charId': 0xC9, 'escort': True, 'cause': 'other',
                         'detail': 'noncombat', 'turn': 9}], outcome='lost')['rec'],
                played(turns_to_win=12)['rec']]
        twin = [played(turns_to_win=10)['rec'], played(turns_to_win=11)['rec'],
                played([dict(boss, flags={})], turns_to_win=14)['rec']]
        return {'ours': ours, 'vanilla': twin}

    def lines(self, cells=None, decision=None, components=None):
        return mc.report(cells or [self.cell()], lambda c: self.arms(), decision, components)

    def test_the_report_is_plain_sentences_one_a_cell_naming_what_drives_it(self):
        lines = self.lines([self.cell(), self.cell('NOT_READABLE', chapter=2, twin_index=2,
                                                   failed_invariants=['blindspot'])])
        self.assertEqual(lines[0], 'instrument i+v2: 2 cells, 200 pairs, 4.00 CPU-hours; '
                                   'HARDER 1, NOT_READABLE 1')
        sentences = [l for l in lines if ' vs vanilla ' in l]
        self.assertEqual(len(sentences), 2)
        self.assertEqual(sentences[0],
                         'Manchego Stars ch03 vs vanilla Ch3, 100 pairs over 10 Manchego Stars '
                         'games and 10 vanilla '
                         'games: harder, +4.0 to +19.0 points on any protected death; a '
                         'protected unit died in Manchego Stars 2 of 3, the twin 1 of 3, driven by '
                         'other deaths (Manchego Stars 0.33 an attempt, twin 0.00) and '
                         'over_cap, boss '
                         'deaths (Manchego Stars 0.33 an attempt, twin 0.00) and 1 escort-green '
                         'death '
                         '(twin 0)')
        # three causes tie at 0.33 an attempt: the first two by name, so the sentence is stable
        self.assertTrue(sentences[1].startswith('Manchego Stars ch02 vs vanilla Ch2, 100 pairs '
                                                'over 10 Manchego Stars '
                                                'games and 10 vanilla games: NOT READABLE '
                                                '(blindspot)'))
        self.assertFalse(any('|' in l for l in lines), 'it is not a table')

    def test_anomalies_carry_their_story_commands(self):
        text = '\n'.join(self.lines())
        self.assertIn('anomalies: 1 in 1 runs\n  ch03 Manchego Stars seed None: '
                      'fallback_sacrifice turn 4 '
                      '-> python3 tools/playtest/montecarlo.py story t.jsonl.gz --turn 4', text)
        self.assertIn('validity failures: none', text)
        text = '\n'.join(self.lines([self.cell('NOT_READABLE', validity={'failed': [
            ('blindspot', 'Manchego Stars: 2 of 3 attempts ...')], 'withheld': []})]))
        self.assertIn('validity failures: 1\n  ch03 Manchego Stars: 2 of 3 attempts ...', text)

    def test_each_decision_reads_only_its_own_components_beside_the_twin(self):
        def block(lines):
            return [l for l in lines if l.startswith('  ') and ': Manchego Stars ' in l]
        every = block(self.lines())
        self.assertEqual(len(every), len(mc.COMPONENTS))
        self.assertTrue(all('; twin ' in l for l in every), 'every result beside its twin')
        party = block(self.lines(decision='party'))
        # the escort green's death is the bot's to answer for, so it is a party death too
        self.assertEqual(party, ['  protected deaths by cause: Manchego Stars other 1, '
                                 'over_cap, boss 1, '
                                 'rng_tail, boss 1; twin rng_tail 1',
                                 '  protected deaths by unit: Manchego Stars 0x02 1, 0x03 1, '
                                 '0xC9 1; twin '
                                 '0x02 1'])
        enemy = block(self.lines(decision='enemy'))
        # boss-flagged deaths leave the over-cap one out; the twin's death is not the boss's
        self.assertEqual(enemy, ['  boss-flagged deaths by cause, over-cap left out: Manchego '
                                 'Stars '
                                 'rng_tail 1; twin none',
                                 '  rng_tail deaths: Manchego Stars 1; twin 1',
                                 '  turns to win: Manchego Stars 2 wins, turns 12 to 15, median '
                                 '15; twin 3 '
                                 'wins, turns 10 to 14, median 11'])
        chapter = block(self.lines(decision='chapter', components=['greens', 'missed']))
        self.assertEqual(chapter, ['  greens: Manchego Stars 1 lost, 1 of them escorts; twin 0 '
                                   'lost, 0 of '
                                   'them escorts',
                                   '  goals missed (rewards by reason, recruits): Manchego '
                                   'Stars skipped 1; '
                                   'twin none'])
        with self.assertRaises(ValueError):
            self.lines(decision='chapter')
        with self.assertRaises(ValueError):
            self.lines(decision='chapter', components=['luck'])

    def test_a_unit_no_name_table_knows_prints_its_id(self):
        arms = {a: mc.describe(r) for a, r in self.arms().items()}
        line = mc.component_line('by_unit', arms, {'ours': mc.namer({2: 'Pinky'})})
        self.assertEqual(line, '  protected deaths by unit: Manchego Stars Pinky 1, 0x03 1, '
                               '0xC9 1; twin 0x02 1')
        self.assertEqual((mc.plural(1, 'run'), mc.plural(2, 'run'), mc.plural(2, 'loss', 'losses')),
                         ('1 run', '2 runs', '2 losses'))

    def test_namer_falls_back_to_the_id_on_a_missing_or_empty_name(self):
        who = mc.namer({2: 'Pinky', 3: ''})
        self.assertEqual((who(2), who(3), who(0xC9)), ('Pinky', '0x03', '0xC9'))

    def test_the_descriptive_data(self):
        d = mc.describe(self.arms()['ours'])
        self.assertEqual((d['n'], d['died'], d['turn5'], d['nonluck'], d['rng_tail'],
                          d['stalls'], d['winner_turns'], d['greens']),
                         (3, 2, 1, 2, 1, 0, [12, 15], (1, 1)))
        self.assertEqual(d['survival'], [(1, 3), (3, 3), (5, 2), (10, 1), (15, 1), (20, 1)])

    def test_report_reads_the_runs_a_cell_record_names(self):
        d = tempfile.mkdtemp()
        stores = {a: os.path.join(d, a + '.jsonl') for a in ('ours', 'vanilla')}
        def named(r, a, i):
            # the vanilla seed-1 run lost its trace (keep_trace drops a missing file)
            return dict(r, campaign='cs-s400%d' % i, seed=3000 + i, attempt=1, instrument='i+v2',
                        trace=None if (a, i) == ('vanilla', 1) else 't/%s-%d' % (a, i))
        results = {}
        for a, recs in self.arms().items():
            for i, r in enumerate(recs):
                mc.append_record(stores[a], named(r, a, i))
                results.setdefault(i, {})[a] = {'status': 'played', 'rec': named(r, a, i)}
            # another instrument's trace-less run of another seed, filed later, is never read
            mc.append_record(stores[a], dict(recs[0], campaign='x', seed=9, attempt=1,
                                             instrument='old+v2', trace=None, turns_to_win=99))
        results[3] = {'ours': {'status': 'played', 'rec': {'trace': 't/unpaired'}},
                      'vanilla': {'status': 'unreached'}}
        cell = mc.cell_record('pilot', 3, 3, {'verdict': None, 'n': 3}, results, [0, 1, 2],
                              stores, 'i+v2')
        # only the paired seeds are named: an unpaired run never enters the descriptive data
        self.assertEqual(cell['runs']['ours'][0], ['cs-s4000/3000/4/1', 't/ours-0', 'i+v2'])
        self.assertEqual(cell['runs']['vanilla'][1], ['cs-s4001/3001/4/1', None, 'i+v2'])
        self.assertEqual(len(cell['runs']['ours']), 3)
        arms = mc.cell_arms(cell)
        self.assertEqual([r['turns_to_win'] for r in arms['vanilla']], [10, 11, 14])
        path = os.path.join(d, 'cells.jsonl')
        mc.append_record(path, dict(cell, instrument='old+v2'))
        mc.append_record(path, cell)
        mc.append_record(path, dict(cell, pairs=50))   # the same cell again: the last counts
        got = mc.report_cells(path)
        self.assertEqual([(c['instrument'], c['pairs']) for c in got], [('i+v2', 50)])
        self.assertEqual(len(mc.report_cells(path, 'old+v2')), 1)
        self.assertEqual(mc.report_cells(os.path.join(d, 'none')), [])
        cell['runs']['ours'].append(['gone/1/4/1', 't/gone', 'i+v2'])
        with self.assertRaises(ValueError) as err:
            mc.cell_arms(cell)
        self.assertIn('t/gone', str(err.exception))
        # a record from before run_ref named its runs by trace alone
        old = dict(cell, runs={'ours': ['t/ours-0'], 'vanilla': cell['runs']['vanilla']})
        with self.assertRaises(ValueError) as err:
            mc.cell_arms(old)
        self.assertIn('predates run_ref', str(err.exception))
        self.assertIn('rerun the pilot', str(err.exception))
        # a pilot's sentence says it has no verdict
        line = mc.cell_sentence(cell, {a: mc.describe(r) for a, r in self.arms().items()})
        self.assertIn(': a pilot, no verdict on any protected death', line)



class Look(unittest.TestCase):
    """`look` (#510 W1): each unit the look judged, binned by its chance, beside whether it died
    within the looked phases (that turn's enemy phase through the depth-th, our turns between
    included); each chapter's look cost; a play kept twice counts once."""

    @staticmethod
    def trace(die_turn=2, die_phase='enemy', chapter=6, run=True, turns=2):
        look = {'asked': True, 'run': run, 'depth': 2, 'die': {'1': 0.8, '2': 0.0},
                'calls': 40, 'between_calls': 10, 'cpu_s': 0.5}
        dead = [{'faction': 'blue', 'phase': die_phase, 'turn': die_turn, 'id': 1, 'charId': 1}]
        return [
            {'t': 'start', 'info': {'game': 'vanilla', 'chapter': chapter}},
            {'t': 'phase', 'phase': 'player', 'turn': 1},
            {'t': 'plan', 'ref': 1, 'look': look},
            {'t': 'act', 'phase': 'player', 'turn': 1, 'id': 1, 'act': 'wait', 'to': {'x': die_turn}},
            {'t': 'phase', 'phase': 'enemy', 'turn': 1},
        ] + [e for k in range(2, turns + 1) for e in (
            {'t': 'phase', 'phase': 'player', 'turn': k},
            {'t': 'phase', 'phase': 'enemy', 'turn': k})] + [
            {'t': 'end', 'record': {'deaths': dead,
                                    'look': {'asked': 1, 'run': int(run), 'skipped': int(not run),
                                             'calls': 40 if run else 0, 'between_calls': 10,
                                             'cpu_s': 0.5},
                                    'costs': {'cpu_s': 5, 'game_calls': {'AiDecideMain': 440}}}},
        ]

    def test_tables(self):
        t = mc.look_table([self.trace(), self.trace(),            # one play, kept twice
                           self.trace(die_turn=3)])               # died after the looked phases
        self.assertEqual((t['traces'], t['distinct']), (3, 2))
        self.assertEqual(t['bins']['over 50%'][:2], [2, 1], 'the second phase, not the third')
        self.assertEqual(t['bins']['0'][:2], [2, 0])
        # a death in our turn between counts; one in the looked turn's own player phase is
        # before the look
        t = mc.look_table([self.trace(die_turn=2, die_phase='player'),
                           self.trace(die_turn=1, die_phase='player', chapter=7)])
        self.assertEqual(t['bins']['over 50%'][:2], [2, 1])
        c = t['cost']['Ch5']
        self.assertEqual((c['attempts'], c['run'], c['calls'], c['ai_calls']), (1, 1, 40, 440))
        self.assertIn('| Ch5 | 1 | 1 | 1 | 0 | 0 | 40 | 10 | 440 | 10.0% |',
                      '\n'.join(mc.look_lines(t)))
        # a look not run judges no unit
        self.assertEqual(mc.look_table([self.trace(run=False)])['bins']['over 50%'][0], 0)

    def test_a_look_the_game_never_reached_is_cut_short(self):
        # the look at turn 1 runs to turn 2's enemy phase; the game ended in turn 1's: its
        # units are not binned (unplayed phases are no survival), and the look is counted cut
        tr = self.trace(die_turn=9, turns=1)
        t = mc.look_table([tr])
        self.assertEqual(t['bins']['over 50%'][0], 0, 'turn 2 never played')
        self.assertEqual(t['cost']['Ch5']['cut_short'], 1)
        tr[-1:-1] = [{'t': 'phase', 'phase': 'player', 'turn': 2},
                     {'t': 'phase', 'phase': 'enemy', 'turn': 2}]
        t = mc.look_table([tr])
        self.assertEqual(t['bins']['over 50%'][:2], [1, 0], 'played through: binned')
        self.assertEqual(t['cost']['Ch5']['cut_short'], 0)

    def test_turn_between_against_the_turn_played(self):
        # the look at turn 1 put unit 1 on (1,0) and unit 2 on (2,0) after its turn between;
        # turn 2 was then played: unit 1 there, unit 2 on (3,0); unit 3, not in the turn
        # between, and a red are not compared. The game ends before a second turn between's.
        tr = self.trace(die_turn=9, turns=1)
        tr[2]['look']['between'] = [{'1': {'x': 1, 'y': 0}, '2': {'x': 2, 'y': 0}},
                                    {'1': {'x': 1, 'y': 0}}]
        units = [{'id': 1, 'faction': 'blue', 'x': 1, 'y': 0},
                 {'id': 2, 'faction': 'blue', 'x': 3, 'y': 0},
                 {'id': 3, 'faction': 'blue', 'x': 5, 'y': 0},
                 {'id': 0x81, 'faction': 'red', 'x': 2, 'y': 0}]
        tr[-1:-1] = [{'t': 'phase', 'phase': 'player', 'turn': 2},
                     {'t': 'phase', 'phase': 'enemy', 'turn': 2, 'units': units}]
        c = mc.look_table([tr])['cost']['Ch5']
        self.assertEqual((c['between_turns'], c['between_turns_same']), (1, 0))
        self.assertEqual((c['between_units'], c['between_units_same']), (2, 1))
        self.assertIn('| Ch5 | 1 | 0 | 2 | 1 | 50.0% |', '\n'.join(mc.look_lines(mc.look_table([tr]))))

    def test_walker(self):
        # a walker at turn 1 strikes green 9 on phase 3 (turn 3); sending unit 2 brings it to
        # 10% and keeps the other green under 50%, unit 1 to 40%; green 9 died on turn 3
        tr = self.trace(die_turn=3)
        tr[-1]['record']['deaths'] = [{'faction': 'green', 'phase': 'enemy', 'turn': 3,
                                       'id': 9, 'charId': 9}]
        tr[1]['units'] = [{'id': 9, 'faction': 'green'}, {'id': 10, 'faction': 'green'},
                          {'id': 1, 'faction': 'blue'}]
        tr[2]['look']['walker'] = {
            'enemy': 0x81, 'target': 9, 'phase': 3, 'x': 5, 'y': 0, 'die': {'9': 0.9},
            'alts': [{'unit': 1, 'turns': 1, 'die': {'9': 0.4, '10': 0}},
                     {'unit': 2, 'turns': 2, 'die': {'9': 0.1, '10': 0.2, '1': 0.7}},
                     {'unit': 3, 'turns': 2}]}           # no turn to play: no chances
        t = mc.look_table([tr])
        w = t['walker'][0]
        self.assertEqual((w['turn'], w['strikes'], w['said'], w['unit'], w['alt']),
                         (1, 3, 0.9, 2, 0.1))
        self.assertTrue(w['greens_safe'], 'only the greens: our unit 1 at 70% is not one')
        self.assertTrue(w['fell'])
        self.assertIn('| 1 | Ch5 | 1 | 129 | 9 | 3 | 90% | 2 | 10% | yes | yes |',
                      '\n'.join(mc.look_lines(t)))
        self.assertEqual(mc.look_table([self.trace()])['walker'], [], 'no walker, no row')


class Calibration(unittest.TestCase):
    """`calibration` (#510 PR A): unit-phases binned by the phase's last plan; a death read by
    the plan that moved its unit; a play kept twice counts once."""

    @staticmethod
    def trace(style='careful', moved_die=0.3, last_die=0.9, chapter=6, dies=True, carried=False):
        blue = [{'id': 1, 'charId': 1, 'faction': 'blue'}, {'id': 2, 'charId': 2, 'faction': 'blue'}]
        if carried:
            blue = blue[1:]
        dead = [{'faction': 'blue', 'phase': 'enemy', 'turn': 1, 'id': 1, 'charId': 1,
                 'flags': {}}] if dies else []
        return [
            {'t': 'start', 'info': {'game': 'vanilla', 'chapter': chapter, 'instrument': 'i'},
             'style': {'aggression': style}},
            {'t': 'phase', 'phase': 'player', 'turn': 1},
            {'t': 'plan', 'ref': 1, 'predict': [{'id': 1, 'die': moved_die}, {'id': 2, 'die': 0}]},
            {'t': 'act', 'phase': 'player', 'turn': 1, 'id': 1, 'act': 'wait', 'to': {'x': 0}},
            {'t': 'plan', 'ref': 2, 'predict': [{'id': 1, 'die': last_die}, {'id': 2, 'die': 0}]},
            {'t': 'act', 'phase': 'player', 'turn': 1, 'id': 2, 'act': 'wait', 'to': {'x': 1}},
            {'t': 'phase', 'phase': 'enemy', 'turn': 1, 'units': blue},
            {'t': 'end', 'record': {'deaths': dead}},
        ]

    def test_tables(self):
        t = self.trace
        c = mc.calibration([t(), t(),                                # one play, kept twice
                            t(moved_die=0.0, last_die=0.0, dies=False, chapter=7)])
        self.assertEqual((c['traces'], c['distinct']), (3, 2))
        self.assertEqual(c['bins']['over 50%'][:2], [1, 1], "binned by the phase's last plan")
        self.assertEqual(c['bins']['0'][:2], [3, 0])
        self.assertEqual(dict(c['deaths']['Ch5']), {'moved over the cap': 1},
                         'careful caps at 1%: its mover said 30%')
        kinds = [next(iter(mc.calibration([x])['deaths']['Ch5'])) for x in (
            t(style='bold', moved_die=0.1),                      # mover under 15%, last 90%
            t(style='bold', moved_die=0.1, last_die=0.1),
            t(style='bold', moved_die=0.0, last_die=0.0),
            t(style='greedy'))]
        self.assertEqual(kinds, ['moved under, over by the phase end', 'under: dice',
                                 'under: blind spot', 'no cap'])
        c = mc.calibration([t(carried=True, dies=False)])
        self.assertEqual(sum(n for n, _, _ in c['bins'].values()), 1,
                         'a unit off the field in the phase is no unit-phase')
        self.assertIn('| Ch5 | 1 | 1 |', '\n'.join(mc.calibration_lines(mc.calibration([t()]))))

    def test_a_trace_index_is_named_as_the_game_names_it(self):
        # one owner of the name: the twin rows, then the route chapters' constants
        self.assertEqual([mc.vanilla_label(i) for i in (0, 5, 6, 7, 10, 999)],
                         ['Prologue', 'Ch5x', 'Ch5', 'Ch6', 'E_9', 'chapter 999'])
        self.assertEqual(mc.twin_name(6), 'vanilla Ch5')

    def test_caps_are_the_planners(self):
        caps, dust = mc.style_caps()
        self.assertEqual(caps, {'careful': 0.01, 'even': 0.05, 'bold': 0.15})
        self.assertLess(dust, 1e-6)


if __name__ == '__main__':
    unittest.main()
