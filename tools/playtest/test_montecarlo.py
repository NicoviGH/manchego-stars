"""montecarlo.py: the bot's run pool (#510 step 9 PR F, Task 11)."""
import json
import multiprocessing
import os
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import montecarlo as mc  # noqa: E402


def _append_many(path, who, n):
    # a record long enough that a torn write would show: 4 KB of payload
    for i in range(n):
        mc.append_record(path, {'who': who, 'i': i, 'pad': 'x' * 4096})


class Records(unittest.TestCase):
    def test_parse_botrun_line(self):
        text = '\n'.join([
            'engine noise',
            'BOTRUN {"attempt": 2, "outcome": "won", "all_alive": true}',
            '[f085128] BOTRUN {"attempt": 3, "outcome": "lost"}',
            'CAMPAIGN {"outcome": "played"}',
        ])
        got = mc.parse_lines(text, mc.BOTRUN)
        self.assertEqual([r['attempt'] for r in got], [2, 3])
        self.assertEqual(mc.parse_lines(text, mc.CAMPAIGN), [{'outcome': 'played'}])

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

    def test_crashed_worker_is_recorded(self):
        def launch(task, tag, log_path):
            if task['campaign']['attempt'] == 2:
                raise RuntimeError('mgba-headless exited early')
            k = task['campaign']['attempt']
            return 'BOTRUN {"attempt": %d, "outcome": "won", "all_alive": true}\n' % k, '/tmp/x'
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
        text = 'CAMPAIGN {"chapter": 4, "outcome": "no_style"}\n'
        recs, kept = self.run_pool(lambda t, tag, lp: (text, '/tmp/x'),
                                   mc.attempt_tasks({'from': 4}, 1))
        self.assertEqual(kept[0]['outcome'], 'no_style')

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

    def test_attempts_need_a_saved_start(self):
        with self.assertRaises(ValueError):
            mc.attempt_tasks({'id': 'c'}, 2)

    def test_first_clean_is_the_lowest_clean_attempt(self):
        recs = [{'attempt': 3, 'all_alive': True}, {'attempt': 1, 'all_alive': False},
                {'attempt': 2, 'all_alive': True}, {'attempt': None, 'outcome': 'crashed'}]
        self.assertEqual(mc.first_clean(recs), 2)
        self.assertIsNone(mc.first_clean([{'attempt': 1, 'all_alive': False}]))


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


if __name__ == '__main__':
    unittest.main()
