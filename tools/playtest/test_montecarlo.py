"""montecarlo.py: the bot's run pool (#510 step 9 PR F, Task 11), its paired verdict and the
cell driver (Task 12)."""
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
            'BOTRUN {"attempt": 2, "outcome": "won", "clean": true}',
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
                                            'closed_by': 0x81}]}}
        line = mc.attempt_line(r, set())
        self.assertIn('lost 0x42 (green, turn 4, to 0x81)', line)
        self.assertIn('missed 0x30', line)
        self.assertIn('village 3,7 closed by 0x81', line)
        clean = mc.attempt_line({'attempt': 2, 'outcome': 'won', 'turns': 8, 'clean': True}, set())
        self.assertIn('won clean', clean)


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


class Story(unittest.TestCase):
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

    def test_names_come_from_the_decomp_and_our_cast(self):
        self.assertEqual(mc._names('vanilla')[0x01], 'Eirika')
        self.assertTrue(mc._items())
        self.assertEqual(mc._classes()[0x01], 'Lord')


if __name__ == '__main__':
    unittest.main()
