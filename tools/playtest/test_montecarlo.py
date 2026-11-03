"""montecarlo.py: the bot's run pool (#510 step 9 PR F, Task 11), its paired verdict and the
cell driver (Task 12)."""
import contextlib
import io
import json
import multiprocessing
import os
import re
import sys
import tempfile
import unittest

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
        self.assertEqual(mc.chapter_result([v1], 3), mc.chapter_result([v2], 3))
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
    """paired_verdict: the #510 plan's Task 12 rule as amended 2026-10-27 (record 0022)."""

    def test_identical_runs_run_to_cap(self):
        pairs = [(True, True)] * 200
        self.assertFalse(mc.paired_verdict(pairs[:50])['settled'], 'no gap settles nothing early')
        self.assertFalse(mc.paired_verdict(pairs[:199])['settled'])
        v = mc.paired_verdict(pairs)
        self.assertTrue(v['settled'])
        self.assertFalse(v['differs'])
        self.assertEqual(v['diff'], 0)
        self.assertEqual(v['look'], 200)

    def test_large_gap_settles_early(self):
        v = mc.paired_verdict([(True, False)] * 30 + [(True, True)] * 20)
        self.assertTrue(v['settled'])
        self.assertTrue(v['differs'])
        self.assertEqual(v['look'], 50)
        self.assertAlmostEqual(v['diff'], 0.6)
        self.assertLess(v['lo'], 0.6)
        self.assertGreater(v['lo'], 0)

    def test_close_call_runs_to_cap(self):
        # ours clean 3 more times in every 50: a real but small gap
        block = [(True, False)] * 6 + [(False, True)] * 3 + [(True, True)] * 41
        for n in (50, 100):
            self.assertFalse(mc.paired_verdict(block * (n // 50))['settled'], n)
        v = mc.paired_verdict(block * 4)
        self.assertTrue(v['settled'])
        self.assertEqual(v['discordant'], 36)

    def test_no_look_between_planned_ones(self):
        # 70 pairs: the last 20 are a wall of ours-only clears, but the look is at 50, on the
        # first 50 alone, and those are even
        pairs = [(True, False), (False, True)] * 25 + [(True, False)] * 20
        v = mc.paired_verdict(pairs)
        self.assertEqual(v['look'], 50)
        self.assertFalse(v['settled'])
        self.assertEqual(v['diff'], 0)
        self.assertIn('next look is at 100', v['reason'])
        self.assertIsNone(mc.paired_verdict(pairs[:49])['look'])

    def test_intervals_match_published_values(self):
        lo, hi = mc.wilson(0, 10)              # the score interval's 0/n case: z^2 / (n + z^2)
        self.assertEqual(lo, 0.0)
        self.assertAlmostEqual(hi, 0.2775, places=4)
        # Newcombe 1998a's worked example, 56/70 vs 48/80 (method 10): 0.0524 to 0.3339
        lo, hi = mc.square_and_add(56, 70, 48, 80)
        self.assertAlmostEqual(lo, 0.0524, places=4)
        self.assertAlmostEqual(hi, 0.3339, places=4)
        self.assertAlmostEqual(mc.mcnemar_exact(0, 6), 2 / 64)   # all six discordant one way
        self.assertEqual(mc.mcnemar_exact(0, 0), 1.0)
        lo, hi = mc.newcombe_paired(10, 4, 4, 12)
        self.assertLess(lo, 0)
        self.assertGreater(hi, 0)
        self.assertAlmostEqual(lo, -hi)


class Cell(unittest.TestCase):
    """run_cell over a fake `play`: `fate(name, seed) -> records of that campaign` (each a
    BOTRUN of the cell's chapter, attempt 1, unless the fate says otherwise)."""

    def sides(self, store_dir=None):
        d = store_dir or tempfile.mkdtemp()
        out = {}
        for n, ch in (('ours', 4), ('vanilla', 3)):
            env = {'last': [ch], 'claims': {}, 'game': n}
            out[n] = {'env': env, 'chapter': ch, 'mode': 'normal', 'vanilla': n == 'vanilla',
                      'store': os.path.join(d, n + '.jsonl'),
                      'stamp': mc.cell_stamp(env, 'normal', 'bot1')}
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
    def clean(yes, chapter):
        return [{'chapter': chapter, 'attempt': 1, 'outcome': 'won', 'clean': yes},
                {'kind': 'campaign', 'outcome': 'done'}]

    def test_vanilla_pairs_read_from_the_store_first(self):
        sides = self.sides()
        for s in range(1, 51):
            for r in self.clean(True, 3):
                mc.append_record(sides['vanilla']['store'],
                                 dict(r, seed=s, **sides['vanilla']['stamp']))
        log = []
        v = mc.run_cell(sides, self.play(lambda n, s, ch: self.clean(False, ch), log))
        self.assertTrue(v['settled'], 'ours 0/50 vs vanilla 50/50 settles at the first look')
        self.assertEqual(v['played'], {'ours': 50, 'vanilla': 0})
        self.assertNotIn('vanilla', {n for n, _ in log})

    def test_a_kept_run_of_another_env_is_played_again(self):
        sides = self.sides()
        other = mc.cell_stamp(dict(sides['vanilla']['env'], claims={'3': ['x']}), 'normal', 'bot1')
        self.assertNotEqual(other, sides['vanilla']['stamp'], 'claims are in the stamp')
        for s in range(1, 51):
            for r in self.clean(True, 3):
                mc.append_record(sides['vanilla']['store'], dict(r, seed=s, **other))
        v = mc.run_cell(sides, self.play(lambda n, s, ch: self.clean(n == 'vanilla', ch), []))
        self.assertEqual(v['played']['vanilla'], 50)

    def test_identical_cell_runs_to_the_last_look(self):
        v = mc.run_cell(self.sides(), self.play(lambda n, s, ch: self.clean(s % 2 == 0, ch), []))
        self.assertEqual(v['look'], 200)
        self.assertTrue(v['settled'])
        self.assertFalse(v['differs'])
        self.assertEqual(v['played'], {'ours': 200, 'vanilla': 200})

    def test_the_pair_is_the_first_attempt(self):
        def fate(n, s, ch):
            return [{'chapter': ch, 'attempt': 1, 'outcome': 'lost', 'clean': False},
                    {'chapter': ch, 'attempt': 2, 'outcome': 'won', 'clean': True},
                    {'kind': 'campaign', 'outcome': 'done'}]
        v = mc.run_cell(self.sides(), self.play(fate, []))
        self.assertEqual((v['ours'], v['vanilla']), (0.0, 0.0), 'a later clean retry is not it')

    def test_a_crash_stops_the_cell_and_says_why(self):
        def fate(n, s, ch):
            if (n, s) == ('ours', 3):
                return [{'chapter': ch, 'attempt': 1, 'outcome': 'crashed', 'run_dir': '/tmp/r3',
                         'why': 'Lua error: boom', 'log_tail': ['RESULT: FAIL']},
                        {'kind': 'campaign', 'outcome': 'crashed', 'why': 'chapter 4 attempt 1'}]
            return self.clean(True, ch)
        log = []
        v = mc.run_cell(self.sides(), self.play(fate, log))
        self.assertFalse(v['settled'])
        self.assertIn('stopped at 50 pairs', v['reason'])
        p = v['problems']
        self.assertEqual([(x['side'], x['seed']) for x in p], [('ours', 3)])
        self.assertEqual(p[0]['why'], 'Lua error: boom')
        self.assertEqual(p[0]['log_tail'], ['RESULT: FAIL'])
        self.assertEqual(log.count(('ours', 3)), 1, 'never played again')
        self.assertNotIn(('ours', 51), log, 'and no seed stands in for it')

    def test_a_campaign_that_never_reached_the_chapter_says_where_it_stopped(self):
        def fate(n, s, ch):
            if (n, s) == ('vanilla', 7):
                return [{'chapter': 2, 'attempt': 1, 'outcome': 'lost', 'clean': False},
                        {'kind': 'campaign', 'outcome': 'infeasible',
                         'why': 'chapter 2: no clean clear in 300 attempts'}]
            return self.clean(True, ch)
        v = mc.run_cell(self.sides(), self.play(fate, []))
        p = v['problems'][0]
        self.assertEqual((p['side'], p['seed']), ('vanilla', 7))
        self.assertIn('never played chapter 3', p['why'])
        self.assertIn('300 attempts', p['why'])

    def test_an_earlier_crash_is_reported_in_its_own_words(self):
        def fate(n, s, ch):
            if (n, s) == ('ours', 1):
                return [{'chapter': 2, 'attempt': 1, 'outcome': 'crashed', 'why': 'Lua error: x'},
                        {'kind': 'campaign', 'outcome': 'crashed', 'why': 'chapter 2 crashed'}]
            return self.clean(True, ch)
        p = mc.run_cell(self.sides(), self.play(fate, []))['problems'][0]
        self.assertIn('crashed (chapter 2, attempt 1): Lua error: x', p['why'])

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
    'seed_sets': {'confirmatory': [1, 200], 'pilot': [3001, 3050]},
    'defaults': {'seeds': {'tuning': [1001, 1002], 'held_out': [2001, 2002]}, 'style': 'drawn',
                 'invariant': 'record', 'estimate_wall_s': 600,
                 'budgets': {'beam': 6, 'final': 4, 'branch': 8, 'lookahead_decision': 8,
                             'lookahead_attempt': 32}},
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
        self.assertEqual((a['style'], a['budgets']['lookahead_attempt']), ('drawn', 32))
        self.assertEqual(got['version'], 1)

    def test_the_shipped_manifest_loads(self):
        got = mc.load_suite()
        self.assertEqual(len(got['starts']), 13)   # FR-021: vanilla 6, ours 4, scout 3
        self.assertEqual(sum(len(s['seeds']['tuning']) + len(s['seeds']['held_out'])
                             for s in got['starts']), 52)   # SC-001
        lo, hi = got['seed_sets']['confirmatory']
        self.assertLessEqual(mc.LOOKS[-1], hi - lo + 1, 'a cell plays seeds 1..LOOKS[-1]')
        # the budgets the manifest records are the ones the planner plays (PR #560: `branch`
        # stayed 2 when planner.lua's M.BRANCH moved)
        src = open(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'planner.lua')).read()
        for key, const in (('beam', 'BEAM'), ('final', 'FINAL'), ('branch', 'BRANCH')):
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

    def test_a_job_over_eight_hours_is_refused_before_it_runs(self):
        suite = self.load(self.suite())
        played = []
        lines = mc.run_suite(suite, envs=lambda: {'vanilla': {}, 'ours': {}}, simdirs={},
                             play=lambda tasks: played.extend(tasks) or [], jobs=1,
                             baseline=True, instrument='i', check=lambda *a: [], kept={},
                             wall_limit_h=0.5)
        self.assertEqual(played, [])
        self.assertIn('refused', lines[-1])
        self.assertIn('8 wall-hours'.replace('8', '0.5'), lines[-1])

    def test_the_baseline_says_each_starts_cost_in_a_sentence(self):
        suite = self.load(self.suite())

        def play(tasks):
            # each worker also leaves its campaign's end, stamped alike: never a second run
            for i, t in enumerate(tasks):
                yield dict(t['stamp'], outcome='won', seed=t['seed'], wall_s=10.0 + i,
                           costs={'cpu_s': 2.0, 'game_calls': {'AiDecideMain': 5 + i,
                                                               'RefreshEntityBmMaps': 99}})
                yield dict(t['stamp'], kind='campaign', outcome='played', seed=t['seed'],
                           wall_s=10.0 + i)
        lines = mc.run_suite(suite, envs=lambda: {'vanilla': {}, 'ours': {}}, simdirs={}, play=play,
                             jobs=4, baseline=True, instrument='i', check=lambda *a: [],
                             kept={})
        text = '\n'.join(lines)
        self.assertIn('vanilla-ch3 (vanilla chapter 3, fixture): 4 runs, 26 AiDecideMain calls, '
                      '8.0 CPU s and 46.0 wall s in all, 2.0 CPU s a run', text)
        self.assertIn('ours-ch02 (ours chapter 3, fixture): 4 runs', text)
        # SC-003's measure (ADR 0384): the AI's decisions only, never another game call
        self.assertIn('the suite: 8 runs, 68 AiDecideMain calls (SC-003), 16.0 CPU s', text)
        self.assertNotIn('won', text, 'a baseline reports cost, never a held-out outcome')

    def test_a_worker_with_no_bot_record_is_one_run_without_a_result(self):
        suite = self.load(self.suite())

        def play(tasks):
            for t in tasks:
                yield dict(t['stamp'], kind='campaign', outcome='crashed', seed=t['seed'],
                           wall_s=1.0, why='arrive: no saved start')
        lines = mc.run_suite(suite, envs=lambda: {'vanilla': {}, 'ours': {}}, simdirs={}, play=play,
                             jobs=4, baseline=False, instrument='i', check=lambda *a: [],
                             kept={})
        text = '\n'.join(lines)
        self.assertIn('vanilla-ch3 (vanilla chapter 3, fixture): 2 runs', text)
        self.assertIn('2 without a game result', text)
        self.assertIn('vanilla-ch3 seed 1001: attempt 1: crashed before the bot reported '
                      '(arrive: no saved start)', text)

    def test_a_start_off_its_pin_refuses_the_whole_suite(self):
        suite = self.load(self.suite())
        lines = mc.run_suite(suite, envs=None, simdirs={}, play=None, jobs=1, baseline=True,
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
        from unittest import mock

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
        lines = mc.run_suite(suite, envs=envs, simdirs={}, play=None, jobs=1, baseline=True,
                             instrument='i', check=lambda *a: [])
        self.assertEqual(lines, ['refused: a campaign env cannot be built: 7.json: no record '
                                 'of the twin'])

    def test_a_campaign_end_without_a_bot_record_is_no_result(self):
        suite = self.load(self.suite())

        def play(tasks):
            for t in tasks:
                yield dict(t['stamp'], kind='campaign', outcome='played', seed=t['seed'],
                           wall_s=1.0, why='played after 1 chapters', env_status=mc.unread())
        lines = mc.run_suite(suite, envs=lambda: {'vanilla': {}, 'ours': {}}, simdirs={},
                             play=play, jobs=4, baseline=False, instrument='i',
                             check=lambda *a: [], kept={})
        text = '\n'.join(lines)
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
        self.assertIn('no ours ROM is built', why[-1])

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

    def test_names_come_from_the_decomp_and_our_cast(self):
        self.assertEqual(mc._names('vanilla')[0x01], 'Eirika')
        self.assertTrue(mc._items())
        self.assertEqual(mc._classes()[0x01], 'Lord')

    def test_ours_names_and_claims_share_one_cast_lookup(self):
        # a run's id names the cast member a claim with that name resolves to
        import campaign_env as ce
        from inject.scene_actors import cast_pids
        names = mc._names('ours')
        for name, pid in cast_pids().items():
            self.assertEqual(ce._unit_id(name, 'ours', None), pid)
            self.assertEqual(names[pid], name.replace('-', ' ').title())


if __name__ == '__main__':
    unittest.main()
