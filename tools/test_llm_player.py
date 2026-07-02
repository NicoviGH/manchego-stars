#!/usr/bin/env python3
"""Tests for the LLM-player pure cores (#63 M1, playtest platform brick 4).

M1 is the no-emulator slice: the three pure cores the sidecar will run -- a board
serializer (FE board state -> compact, deterministic JSON for the prompt + transcript
key), an order-schema validator (LLM JSON -> typed orders, rejecting illegal moves so a
bad LLM turn never soft-locks the harness), and a board-hash-keyed transcript
(record/replay so a soak replays identically on CI `lua` and mGBA and re-runs cost
nothing). No LLM calls here -- the transcript is exercised with a hand-written record.
Design + rationale: docs/decisions.md -> Playtest platform brick 4; epic #63.
"""
import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), 'playtest'))
import llm_player  # noqa: E402


def sample_board():
    """A minimal two-unit prologue-ish board (the shape the harness exports)."""
    return {
        'objective': 'DefeatBoss',
        'win': 'Defeat the boss',
        'map': {'w': 15, 'h': 10, 'terrain_notes': ['fort at 7,2']},
        'units': [
            {'id': 1, 'name': 'Braulo', 'faction': 'blue', 'class': 'Lord',
             'x': 3, 'y': 4, 'hp': 18, 'maxhp': 18, 'weapon': 'Iron Sword',
             'range': [1, 1], 'can_act': True, 'boss': False,
             'reach': [[3, 4], [4, 4], [3, 5], [5, 4]]},
            {'id': 104, 'name': 'Sephek', 'faction': 'red', 'class': 'Brigand',
             'x': 6, 'y': 4, 'hp': 22, 'maxhp': 22, 'weapon': 'Hand Axe',
             'range': [1, 2], 'can_act': True, 'boss': True, 'reach': []},
        ],
    }


class TestBoardSerializer(unittest.TestCase):
    def test_serialization_is_deterministic_regardless_of_key_order(self):
        a = sample_board()
        # Same board, dict built with keys inserted in a different order.
        b = {
            'units': list(reversed(a['units'])),
            'map': a['map'],
            'win': a['win'],
            'objective': a['objective'],
        }
        self.assertEqual(llm_player.serialize_board(a),
                         llm_player.serialize_board(b))

    def test_serialization_is_compact(self):
        out = llm_player.serialize_board(sample_board())
        self.assertNotIn(', ', out)
        self.assertNotIn(': ', out)

    def test_serialization_round_trips_to_equivalent_data(self):
        board = sample_board()
        got = json.loads(llm_player.serialize_board(board))
        self.assertEqual(got['objective'], 'DefeatBoss')
        self.assertEqual({u['id'] for u in got['units']}, {1, 104})


class TestOrderValidator(unittest.TestCase):
    """validate_orders(orders, board, faction) -> (accepted, rejected).

    Never raises on a bad LLM turn: illegal orders are dropped into `rejected` with a
    reason (a play-quality signal) so the harness can execute the survivors and log the
    rest instead of soft-locking.
    """

    def test_accepts_a_legal_move_and_attack(self):
        board = sample_board()
        orders = [{'unit': 1, 'move_to': {'x': 5, 'y': 4},
                   'action': 'attack', 'target': 104}]
        accepted, rejected = llm_player.validate_orders(orders, board, 'blue')
        self.assertEqual(rejected, [])
        self.assertEqual(len(accepted), 1)
        self.assertEqual(accepted[0]['action'], 'attack')

    def test_accepts_a_bare_wait(self):
        board = sample_board()
        orders = [{'unit': 1, 'move_to': {'x': 3, 'y': 4}, 'action': 'wait'}]
        accepted, rejected = llm_player.validate_orders(orders, board, 'blue')
        self.assertEqual(rejected, [])
        self.assertEqual(len(accepted), 1)

    def test_rejects_unknown_unit(self):
        board = sample_board()
        orders = [{'unit': 999, 'move_to': {'x': 3, 'y': 4}, 'action': 'wait'}]
        accepted, rejected = llm_player.validate_orders(orders, board, 'blue')
        self.assertEqual(accepted, [])
        self.assertIn('unit', rejected[0]['reason'])

    def test_rejects_commanding_the_wrong_faction(self):
        board = sample_board()
        orders = [{'unit': 104, 'move_to': {'x': 6, 'y': 4}, 'action': 'wait'}]
        accepted, rejected = llm_player.validate_orders(orders, board, 'blue')
        self.assertEqual(accepted, [])
        self.assertIn('faction', rejected[0]['reason'])

    def test_rejects_a_unit_that_cannot_act(self):
        board = sample_board()
        board['units'][0]['can_act'] = False
        orders = [{'unit': 1, 'move_to': {'x': 3, 'y': 4}, 'action': 'wait'}]
        accepted, rejected = llm_player.validate_orders(orders, board, 'blue')
        self.assertEqual(accepted, [])
        self.assertIn('act', rejected[0]['reason'])

    def test_rejects_an_unreachable_move(self):
        board = sample_board()
        orders = [{'unit': 1, 'move_to': {'x': 9, 'y': 9}, 'action': 'wait'}]
        accepted, rejected = llm_player.validate_orders(orders, board, 'blue')
        self.assertEqual(accepted, [])
        self.assertIn('reach', rejected[0]['reason'])

    def test_rejects_an_unknown_action(self):
        board = sample_board()
        orders = [{'unit': 1, 'move_to': {'x': 3, 'y': 4}, 'action': 'dance'}]
        accepted, rejected = llm_player.validate_orders(orders, board, 'blue')
        self.assertEqual(accepted, [])
        self.assertIn('action', rejected[0]['reason'])

    def test_rejects_an_out_of_range_attack(self):
        board = sample_board()
        # Move to own tile (3,4): boss at (6,4) is 3 tiles away, sword range 1.
        orders = [{'unit': 1, 'move_to': {'x': 3, 'y': 4},
                   'action': 'attack', 'target': 104}]
        accepted, rejected = llm_player.validate_orders(orders, board, 'blue')
        self.assertEqual(accepted, [])
        self.assertIn('range', rejected[0]['reason'])

    def test_rejects_an_attack_with_no_target(self):
        board = sample_board()
        orders = [{'unit': 1, 'move_to': {'x': 4, 'y': 4}, 'action': 'attack'}]
        accepted, rejected = llm_player.validate_orders(orders, board, 'blue')
        self.assertEqual(accepted, [])
        self.assertIn('target', rejected[0]['reason'])

    def test_rejects_attacking_a_friendly_unit(self):
        board = sample_board()
        board['units'].append({'id': 2, 'name': 'Marty', 'faction': 'blue',
                               'class': 'Fighter', 'x': 4, 'y': 5, 'hp': 20,
                               'maxhp': 20, 'range': [1, 1], 'can_act': True,
                               'boss': False, 'reach': []})
        orders = [{'unit': 1, 'move_to': {'x': 4, 'y': 4},
                   'action': 'attack', 'target': 2}]
        accepted, rejected = llm_player.validate_orders(orders, board, 'blue')
        self.assertEqual(accepted, [])
        self.assertIn('friendly', rejected[0]['reason'])

    def test_staff_needs_a_friendly_target(self):
        board = sample_board()
        board['units'].append({'id': 2, 'name': 'Marty', 'faction': 'blue',
                               'class': 'Fighter', 'x': 4, 'y': 5, 'hp': 20,
                               'maxhp': 20, 'range': [1, 1], 'can_act': True,
                               'boss': False, 'reach': []})
        heal = [{'unit': 1, 'move_to': {'x': 3, 'y': 5}, 'action': 'staff', 'target': 2}]
        accepted, rejected = llm_player.validate_orders(heal, board, 'blue')
        self.assertEqual(len(accepted), 1)
        zap = [{'unit': 1, 'move_to': {'x': 5, 'y': 4}, 'action': 'staff', 'target': 104}]
        accepted, rejected = llm_player.validate_orders(zap, board, 'blue')
        self.assertEqual(accepted, [])
        self.assertIn('friendly', rejected[0]['reason'])

    def test_rejects_an_attack_from_a_rangeless_unit(self):
        # the exporter omits 'range' for staff-only/weaponless units: they can target
        # NOTHING (a defaulted melee range would send the blind-A executor into the
        # wrong submenu)
        board = sample_board()
        del board['units'][0]['range']
        orders = [{'unit': 1, 'move_to': {'x': 5, 'y': 4},
                   'action': 'attack', 'target': 104}]
        accepted, rejected = llm_player.validate_orders(orders, board, 'blue')
        self.assertEqual(accepted, [])
        self.assertIn('range', rejected[0]['reason'])

    def test_seize_is_gated_on_the_objective(self):
        board = sample_board()                               # objective: DefeatBoss
        orders = [{'unit': 1, 'move_to': {'x': 4, 'y': 4}, 'action': 'seize'}]
        accepted, rejected = llm_player.validate_orders(orders, board, 'blue')
        self.assertEqual(accepted, [])
        self.assertIn('objective', rejected[0]['reason'])
        board['objective'] = 'Seize'
        accepted, rejected = llm_player.validate_orders(orders, board, 'blue')
        self.assertEqual(len(accepted), 1)

    def test_keeps_the_good_order_and_drops_the_bad_one(self):
        board = sample_board()
        orders = [
            {'unit': 1, 'move_to': {'x': 5, 'y': 4}, 'action': 'attack', 'target': 104},
            {'unit': 999, 'move_to': {'x': 0, 'y': 0}, 'action': 'wait'},
        ]
        accepted, rejected = llm_player.validate_orders(orders, board, 'blue')
        self.assertEqual(len(accepted), 1)
        self.assertEqual(len(rejected), 1)
        self.assertEqual(accepted[0]['unit'], 1)


class TestTranscriptKey(unittest.TestCase):
    def test_key_is_stable_for_the_same_board_and_coords(self):
        b = sample_board()
        self.assertEqual(llm_player.transcript_key(b, seed=7, chapter='ch00', turn=2),
                         llm_player.transcript_key(b, seed=7, chapter='ch00', turn=2))

    def test_key_ignores_unit_iteration_order(self):
        a = sample_board()
        b = sample_board()
        b['units'] = list(reversed(b['units']))
        self.assertEqual(llm_player.transcript_key(a, seed=7, chapter='ch00', turn=2),
                         llm_player.transcript_key(b, seed=7, chapter='ch00', turn=2))

    def test_key_varies_with_turn_seed_chapter_and_board(self):
        b = sample_board()
        base = llm_player.transcript_key(b, seed=7, chapter='ch00', turn=2)
        self.assertNotEqual(base, llm_player.transcript_key(b, seed=7, chapter='ch00', turn=3))
        self.assertNotEqual(base, llm_player.transcript_key(b, seed=8, chapter='ch00', turn=2))
        self.assertNotEqual(base, llm_player.transcript_key(b, seed=7, chapter='ch01', turn=2))
        moved = sample_board()
        moved['units'][0]['x'] = 4
        self.assertNotEqual(base, llm_player.transcript_key(moved, seed=7, chapter='ch00', turn=2))


class TestTranscriptReplay(unittest.TestCase):
    def test_replay_hit_returns_recorded_orders_without_deciding(self):
        b = sample_board()
        key = llm_player.transcript_key(b, seed=7, chapter='ch00', turn=2)
        orders = [{'unit': 1, 'move_to': {'x': 3, 'y': 4}, 'action': 'wait'}]
        t = llm_player.Transcript(entries={key: orders}, mode='replay')

        def boom(board):
            raise AssertionError('replay must not call the policy on a hit')

        got = t.decide(b, seed=7, chapter='ch00', turn=2, decide_fn=boom)
        self.assertEqual(got, orders)

    def test_replay_miss_raises(self):
        t = llm_player.Transcript(entries={}, mode='replay')
        with self.assertRaises(llm_player.TranscriptMiss):
            t.decide(sample_board(), seed=7, chapter='ch00', turn=2)


class TestTranscriptRecord(unittest.TestCase):
    def test_record_miss_calls_policy_once_and_caches(self):
        t = llm_player.Transcript(entries={}, mode='record')
        calls = []
        orders = [{'unit': 1, 'move_to': {'x': 4, 'y': 4}, 'action': 'wait'}]

        def policy(board):
            calls.append(1)
            return orders

        b = sample_board()
        first = t.decide(b, seed=7, chapter='ch00', turn=2, decide_fn=policy)
        second = t.decide(b, seed=7, chapter='ch00', turn=2, decide_fn=policy)
        self.assertEqual(first, orders)
        self.assertEqual(second, orders)
        self.assertEqual(len(calls), 1)  # second call was a cache hit

    def test_save_and_load_round_trip(self):
        t = llm_player.Transcript(entries={}, mode='record')
        b = sample_board()
        orders = [{'unit': 1, 'move_to': {'x': 4, 'y': 4}, 'action': 'wait'}]
        t.decide(b, seed=7, chapter='ch00', turn=2, decide_fn=lambda board: orders)
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, 'run.json')
            t.save(path)
            reloaded = llm_player.Transcript.load(path, mode='replay')
        got = reloaded.decide(b, seed=7, chapter='ch00', turn=2)
        self.assertEqual(got, orders)


class TestBuildPrompt(unittest.TestCase):
    def test_prompt_carries_faction_board_and_schema(self):
        system, user = llm_player.build_prompt(sample_board(), 'blue')
        self.assertIn('blue army', system)
        self.assertIn('"orders"', system)                     # the reply schema
        self.assertIn('DefeatBoss', user)                     # the objective
        self.assertIn(llm_player.serialize_board(sample_board()), user)

    def test_prompt_is_reproducible(self):
        self.assertEqual(llm_player.build_prompt(sample_board(), 'blue'),
                         llm_player.build_prompt(sample_board(), 'blue'))


class TestParseOrders(unittest.TestCase):
    """parse_orders never raises: prose-wrapped, fenced, or garbage model output all
    resolve to a (possibly empty) list of dict orders."""

    ORDERS = [{'unit': 1, 'move_to': {'x': 5, 'y': 4}, 'action': 'attack', 'target': 104}]

    def test_bare_object_with_orders_key(self):
        self.assertEqual(llm_player.parse_orders(json.dumps({'orders': self.ORDERS})),
                         self.ORDERS)

    def test_bare_array(self):
        self.assertEqual(llm_player.parse_orders(json.dumps(self.ORDERS)), self.ORDERS)

    def test_json_inside_a_code_fence(self):
        text = 'Here is my plan:\n```json\n%s\n```\nGood luck!' % json.dumps(
            {'orders': self.ORDERS})
        self.assertEqual(llm_player.parse_orders(text), self.ORDERS)

    def test_json_wrapped_in_prose(self):
        text = 'I will attack. %s That is all.' % json.dumps({'orders': self.ORDERS})
        self.assertEqual(llm_player.parse_orders(text), self.ORDERS)

    def test_garbage_returns_empty(self):
        self.assertEqual(llm_player.parse_orders('I surrender.'), [])
        self.assertEqual(llm_player.parse_orders(''), [])
        self.assertEqual(llm_player.parse_orders(None), [])
        self.assertEqual(llm_player.parse_orders('{"orders": "all of them"}'), [])

    def test_non_dict_entries_are_dropped(self):
        text = json.dumps({'orders': [self.ORDERS[0], 'retreat!', 7]})
        self.assertEqual(llm_player.parse_orders(text), self.ORDERS)

    def test_non_finite_numbers_are_rejected(self):
        # json.loads accepts NaN/Infinity by default (and 1e999 overflows to inf via
        # the ordinary float path); letting one through would write a resp/transcript
        # the strict Lua-side reader cannot parse -- permanently
        self.assertEqual(llm_player.parse_orders(
            '{"orders": [{"unit": 1, "move_to": {"x": NaN, "y": 0}}]}'), [])
        self.assertEqual(llm_player.parse_orders(
            '{"orders": [{"unit": 1e999, "move_to": {"x": 3, "y": 0}}]}'), [])
        # a finite sibling order survives the cull
        got = llm_player.parse_orders(
            '{"orders": [{"unit": 1e999}, {"unit": 1, "action": "wait"}]}')
        self.assertEqual(got, [{'unit': 1, 'action': 'wait'}])


class TestPolicyConfig(unittest.TestCase):
    def test_defaults_to_anthropic_sonnet(self):
        cfg = llm_player.policy_config(env={})
        self.assertEqual(cfg['provider'], 'anthropic')
        self.assertEqual(cfg['model'], 'claude-sonnet-5')

    def test_openai_provider_defaults_to_a_free_local_model(self):
        cfg = llm_player.policy_config(env={'PT_PROVIDER': 'openai'})
        self.assertEqual(cfg['provider'], 'openai')
        self.assertEqual(cfg['model'], 'llama3.1')
        self.assertIsNone(cfg['base_url'])   # transport falls back to OLLAMA_BASE_URL

    def test_env_knobs_override(self):
        cfg = llm_player.policy_config(env={
            'PT_PROVIDER': 'openai', 'PT_MODEL': 'gemma3:12b',
            'PT_BASE_URL': 'http://gpubox:8080/v1', 'PT_API_KEY': 'k'})
        self.assertEqual(cfg['model'], 'gemma3:12b')
        self.assertEqual(cfg['base_url'], 'http://gpubox:8080/v1')
        self.assertEqual(cfg['api_key'], 'k')

    def test_unknown_provider_fails_loudly(self):
        with self.assertRaises(ValueError):
            llm_player.policy_config(env={'PT_PROVIDER': 'skynet'})

    def test_anthropic_without_a_key_fails_loudly(self):
        with self.assertRaises(ValueError):
            llm_player.make_policy('blue', env={})

    def test_anthropic_key_never_feeds_the_openai_provider(self):
        # ANTHROPIC_API_KEY as the openai fallback would Bearer-leak the Anthropic
        # secret to whatever host PT_BASE_URL names
        cfg = llm_player.policy_config(env={
            'PT_PROVIDER': 'openai', 'ANTHROPIC_API_KEY': 'sk-ant-secret'})
        self.assertIsNone(cfg['api_key'])
        cfg = llm_player.policy_config(env={'ANTHROPIC_API_KEY': 'sk-ant-secret'})
        self.assertEqual(cfg['api_key'], 'sk-ant-secret')    # anthropic still gets it

    def test_anthropic_with_an_injected_transport_needs_no_key(self):
        # the keyless-test carve-out: a stub transport must bypass the key check
        policy = llm_player.make_policy(
            'blue', env={}, transport=lambda cfg, s, u: '{"orders": [{"unit": 1}]}')
        self.assertEqual(policy(sample_board()), [{'unit': 1}])


class TestTransports(unittest.TestCase):
    """The two HTTP transports, with _post_json stubbed -- asserts each provider's wire
    shape (URL, auth header, payload) and response extraction."""

    def _capture(self, response):
        calls = []

        def fake_post(url, headers, payload, timeout=120):
            calls.append({'url': url, 'headers': headers, 'payload': payload})
            return response
        return calls, fake_post

    def test_anthropic_wire_shape(self):
        calls, fake = self._capture(
            {'content': [{'type': 'text', 'text': '{"orders": []}'}]})
        orig = llm_player._post_json
        llm_player._post_json = fake
        try:
            got = llm_player._call_anthropic(
                {'model': 'claude-sonnet-5', 'api_key': 'sk-test', 'base_url': None},
                'sys', 'user')
        finally:
            llm_player._post_json = orig
        self.assertEqual(got, '{"orders": []}')
        self.assertEqual(calls[0]['url'], llm_player.ANTHROPIC_URL)
        self.assertEqual(calls[0]['headers']['x-api-key'], 'sk-test')
        self.assertEqual(calls[0]['payload']['system'], 'sys')
        self.assertEqual(calls[0]['payload']['messages'][0]['content'], 'user')

    def test_openai_wire_shape_defaults_to_ollama(self):
        calls, fake = self._capture(
            {'choices': [{'message': {'content': '{"orders": []}'}}]})
        orig = llm_player._post_json
        llm_player._post_json = fake
        try:
            got = llm_player._call_openai(
                {'model': 'llama3.1', 'api_key': None, 'base_url': None}, 'sys', 'user')
        finally:
            llm_player._post_json = orig
        self.assertEqual(got, '{"orders": []}')
        self.assertEqual(calls[0]['url'],
                         llm_player.OLLAMA_BASE_URL + '/chat/completions')
        self.assertEqual(calls[0]['headers']['authorization'], 'Bearer ollama')
        self.assertEqual(calls[0]['payload']['messages'][0]['role'], 'system')

    def test_make_policy_runs_prompt_through_transport_and_parse(self):
        board = sample_board()

        def transport(cfg, system, user):
            self.assertIn(llm_player.serialize_board(board), user)
            return 'Sure! ```json\n{"orders": [{"unit": 1}]}\n```'
        policy = llm_player.make_policy(
            'blue', env={'PT_PROVIDER': 'openai'}, transport=transport)
        self.assertEqual(policy(board), [{'unit': 1}])


class TestSidecar(unittest.TestCase):
    """The file handshake, played from the harness's side of the directory."""

    GOOD = [{'unit': 1, 'move_to': {'x': 5, 'y': 4}, 'action': 'attack', 'target': 104}]
    BAD = [{'unit': 999, 'move_to': {'x': 0, 'y': 0}, 'action': 'wait'}]

    def _write_req(self, d, n, board=None, turn=2):
        req = {'seed': 7, 'chapter': 'ch00', 'turn': turn, 'faction': 'blue',
               'board': board or sample_board()}
        with open(os.path.join(d, 'req-%d.json' % n), 'w', encoding='utf-8') as f:
            json.dump(req, f)
        return req

    def _replay_sidecar(self, d, orders, turn=2):
        key = llm_player.transcript_key(sample_board(), seed=7, chapter='ch00', turn=turn)
        t = llm_player.Transcript(entries={key: orders}, mode='replay')
        return llm_player.Sidecar(d, t)

    def test_step_answers_a_request_with_validated_orders(self):
        with tempfile.TemporaryDirectory() as d:
            self._write_req(d, 1)
            sidecar = self._replay_sidecar(d, self.GOOD + self.BAD)
            self.assertEqual(sidecar.step(), 1)
            with open(os.path.join(d, 'resp-1.json'), encoding='utf-8') as f:
                resp = json.load(f)
            self.assertEqual(resp['orders'], self.GOOD)      # the bad order was culled
            self.assertEqual(len(resp['rejected']), 1)
            # atomic write: only the rename target remains, no .tmp left behind
            self.assertEqual([f for f in os.listdir(d) if f.endswith('.tmp')], [])

    def test_step_is_idle_when_nothing_is_pending(self):
        with tempfile.TemporaryDirectory() as d:
            sidecar = self._replay_sidecar(d, self.GOOD)
            self.assertIsNone(sidecar.step())

    def test_step_skips_already_answered_requests(self):
        with tempfile.TemporaryDirectory() as d:
            self._write_req(d, 1)
            sidecar = self._replay_sidecar(d, self.GOOD)
            self.assertEqual(sidecar.step(), 1)
            self.assertIsNone(sidecar.step())                # 1 is answered; nothing new

    def test_lowest_numbered_request_goes_first(self):
        with tempfile.TemporaryDirectory() as d:
            self._write_req(d, 2, turn=3)
            self._write_req(d, 1, turn=2)
            key2 = llm_player.transcript_key(sample_board(), seed=7, chapter='ch00', turn=3)
            key1 = llm_player.transcript_key(sample_board(), seed=7, chapter='ch00', turn=2)
            t = llm_player.Transcript(entries={key1: self.GOOD, key2: []}, mode='replay')
            sidecar = llm_player.Sidecar(d, t)
            self.assertEqual(sidecar.step(), 1)
            self.assertEqual(sidecar.step(), 2)

    def test_replay_miss_writes_an_error_response_then_raises(self):
        with tempfile.TemporaryDirectory() as d:
            self._write_req(d, 1)
            sidecar = llm_player.Sidecar(d, llm_player.Transcript(mode='replay'))
            with self.assertRaises(llm_player.TranscriptMiss):
                sidecar.step()
            with open(os.path.join(d, 'resp-1.json'), encoding='utf-8') as f:
                resp = json.load(f)
            self.assertEqual(resp['orders'], [])
            self.assertIn('transcript miss', resp['error'])

    def test_record_mode_calls_policy_and_fills_the_transcript(self):
        with tempfile.TemporaryDirectory() as d:
            self._write_req(d, 1)
            calls = []

            def policy(board):
                calls.append(1)
                return self.GOOD
            t = llm_player.Transcript(mode='record')
            sidecar = llm_player.Sidecar(d, t, policy=policy)
            self.assertEqual(sidecar.step(), 1)
            self.assertEqual(len(calls), 1)
            self.assertEqual(len(t.entries), 1)              # the decision was recorded
            # replaying the SAME board from the filled transcript needs no policy
            self._write_req(d, 2, turn=2)
            replay = llm_player.Sidecar(d, llm_player.Transcript(
                entries=t.entries, mode='replay'))
            self.assertEqual(replay.step(), 2)

    def test_serve_stops_on_the_stop_file(self):
        with tempfile.TemporaryDirectory() as d:
            self._write_req(d, 1)
            sidecar = self._replay_sidecar(d, self.GOOD)
            open(os.path.join(d, 'stop'), 'w').close()
            self.assertEqual(sidecar.serve(poll_interval=0.01), 1)

    def test_a_half_written_request_is_not_pending(self):
        # the harness writes tmp+rename; the .tmp must never be read as a request
        with tempfile.TemporaryDirectory() as d:
            with open(os.path.join(d, 'req-1.json.tmp'), 'w', encoding='utf-8') as f:
                f.write('{"seed": 7, "chap')
            sidecar = self._replay_sidecar(d, self.GOOD)
            self.assertIsNone(sidecar.step())

    def test_a_request_vanishing_mid_step_is_tolerated(self):
        # run.sh's stale-file cleanup can delete a request between the sidecar's
        # listdir and open (documented startup order starts the sidecar first)
        with tempfile.TemporaryDirectory() as d:
            self._write_req(d, 1)
            sidecar = self._replay_sidecar(d, self.GOOD)
            real_pending = sidecar._pending()
            self.assertEqual(real_pending, [1])
            os.unlink(os.path.join(d, 'req-1.json'))
            sidecar._pending = lambda: real_pending          # listdir already happened
            self.assertIsNone(sidecar.step())

    def test_a_policy_failure_still_answers_the_harness(self):
        # endpoint down (Ollama not running) must be a fast diagnosable FAIL on the
        # harness side, not a silent 90s handshake timeout
        with tempfile.TemporaryDirectory() as d:
            self._write_req(d, 1)

            def broken_policy(board):
                raise RuntimeError('http://localhost:11434/v1 -> unreachable')
            sidecar = llm_player.Sidecar(
                d, llm_player.Transcript(mode='record'), policy=broken_policy)
            with self.assertRaises(RuntimeError):
                sidecar.step()
            with open(os.path.join(d, 'resp-1.json'), encoding='utf-8') as f:
                resp = json.load(f)
            self.assertEqual(resp['orders'], [])
            self.assertIn('unreachable', resp['error'])


class TestPostJson(unittest.TestCase):
    """_post_json's error wrapping (the diagnostic text is the product here)."""

    def _patch_urlopen(self, exc):
        import urllib.request as ur
        orig = ur.urlopen

        def fake(req, timeout=None):
            raise exc
        ur.urlopen = fake
        self.addCleanup(setattr, ur, 'urlopen', orig)

    def test_http_error_carries_the_body(self):
        import io
        import urllib.error
        self._patch_urlopen(urllib.error.HTTPError(
            'http://x/v1', 401, 'unauthorized', {}, io.BytesIO(b'{"error":"bad key"}')))
        with self.assertRaises(RuntimeError) as cm:
            llm_player._post_json('http://x/v1', {}, {})
        self.assertIn('bad key', str(cm.exception))
        self.assertIn('401', str(cm.exception))

    def test_connection_error_names_the_ollama_hint(self):
        import urllib.error
        self._patch_urlopen(urllib.error.URLError('connection refused'))
        with self.assertRaises(RuntimeError) as cm:
            llm_player._post_json('http://localhost:11434/v1/chat/completions', {}, {})
        self.assertIn('unreachable', str(cm.exception))
        self.assertIn('ollama serve', str(cm.exception))


if __name__ == '__main__':
    unittest.main()
