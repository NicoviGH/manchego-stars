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


if __name__ == '__main__':
    unittest.main()
