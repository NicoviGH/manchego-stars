#!/usr/bin/env python3
"""LLM-player pure cores -- soak/balance driver that replaces the clear-bot policy.

Playtest platform brick 4 (#49 spine; epic #63). This module is the *policy + transport*
sidecar that runs OUTSIDE mGBA (the emulator's embedded Lua can't make network calls):
the harness exports the board to a file and blocks, this process decides, writes the
orders back. Per the platform doctrine -- pure core, driver owns I/O -- everything here
is plain Python, unit-testable on CI with no emulator (test_llm_player.py).

M1 ships the three pure cores only, no LLM calls yet:
  * serialize_board  -- FE board state -> compact, deterministic JSON (prompt + hash key)
  * (M1 continues with the order validator + transcript, added below as TDD proceeds)

Design + settled decisions: docs/decisions.md -> Playtest platform brick 4; epic #63.
"""
import hashlib
import json


def serialize_board(board):
    """FE board state -> a compact, deterministic JSON string.

    Deterministic (``sort_keys`` + units ordered by id) and compact (no whitespace) so the
    same board always produces the same bytes -- this string is both what the LLM prompt
    carries and what the transcript hash keys on, so two structurally-identical boards must
    serialize byte-identically regardless of dict insertion order or unit-array iteration
    order (the harness reads the live unit arrays, whose order we don't control).
    """
    normalized = dict(board)
    if 'units' in normalized:
        normalized['units'] = sorted(normalized['units'], key=lambda u: u['id'])
    return json.dumps(normalized, sort_keys=True, separators=(',', ':'))


VALID_ACTIONS = ('attack', 'wait', 'seize', 'staff')
TARGETED_ACTIONS = ('attack', 'staff')


def _reject(order, reason):
    return {'order': order, 'reason': reason}


def validate_orders(orders, board, faction):
    """Split LLM-emitted orders into (accepted, rejected) against the live board.

    The harness executes `accepted` with its existing primitives and logs `rejected`
    (each `{order, reason}`) as a play-quality signal -- a bad LLM turn is dropped, never
    soft-locked. An order is `{unit, move_to:{x,y}, action, target?}`. Rejections, in the
    order checked: unknown unit; not the commanded faction; unit can't still act;
    `move_to` outside the unit's reachable set; unknown action; a targeted action
    (attack/staff) whose target is missing, unknown, dead, or out of weapon range from
    `move_to`.
    """
    by_id = {u['id']: u for u in board.get('units', [])}
    accepted, rejected = [], []

    for order in orders:
        unit = by_id.get(order.get('unit'))
        if unit is None:
            rejected.append(_reject(order, 'no such unit on the board'))
            continue
        if unit.get('faction') != faction:
            rejected.append(_reject(order, 'unit is not on the commanded faction'))
            continue
        if not unit.get('can_act'):
            rejected.append(_reject(order, 'unit cannot still act this turn'))
            continue

        dest = order.get('move_to') or {}
        tile = [dest.get('x'), dest.get('y')]
        if tile not in [list(t) for t in unit.get('reach', [])]:
            rejected.append(_reject(order, 'move_to is not in the unit\'s reach'))
            continue

        action = order.get('action')
        if action not in VALID_ACTIONS:
            rejected.append(_reject(order, 'unknown action %r' % (action,)))
            continue

        if action in TARGETED_ACTIONS:
            target = by_id.get(order.get('target'))
            if target is None:
                rejected.append(_reject(order, 'action needs a valid target'))
                continue
            if target.get('hp', 0) <= 0:
                rejected.append(_reject(order, 'target is already dead'))
                continue
            lo, hi = unit.get('range', [1, 1])
            dist = abs(tile[0] - target['x']) + abs(tile[1] - target['y'])
            if dist < lo or dist > hi:
                rejected.append(_reject(order, 'target is out of weapon range'))
                continue

        accepted.append(order)

    return accepted, rejected


def transcript_key(board, seed, chapter, turn):
    """Stable cache key for one decision: hash(serialized board) + seed + chapter + turn.

    Keying on the *serialized* board (not object identity) means two structurally
    identical positions share a key, so a replay reproduces the same decision the soak
    recorded -- identical on the CI `lua` mock and on mGBA -- and re-runs cost nothing.
    """
    digest = hashlib.sha256(serialize_board(board).encode('utf-8')).hexdigest()[:16]
    return '%s:%s:%s:%s' % (seed, chapter, turn, digest)


class TranscriptMiss(Exception):
    """A decision wasn't in the transcript while replaying (CI/replay is closed-world)."""


class Transcript:
    """Board-hash-keyed record/replay of per-turn decisions -- cache + replay in one.

    `mode='replay'` is closed-world: a hit returns the recorded orders (deterministic,
    free, no policy call); a miss raises `TranscriptMiss` (the CI/replay guarantee).
    `mode='record'` (local soak) calls the policy on a miss, stores the result, and serves
    it from cache thereafter. `save`/`load` persist the entries as JSON under `transcripts/`.
    """

    def __init__(self, entries=None, mode='replay'):
        self.entries = dict(entries or {})
        self.mode = mode

    def decide(self, board, seed, chapter, turn, decide_fn=None):
        key = transcript_key(board, seed, chapter, turn)
        if key in self.entries:
            return self.entries[key]
        if self.mode == 'replay':
            raise TranscriptMiss(key)
        if decide_fn is None:
            raise ValueError('record mode needs a decide_fn to fill a cache miss')
        orders = decide_fn(board)
        self.entries[key] = orders
        return orders

    def save(self, path):
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(self.entries, f, indent=2, sort_keys=True)

    @classmethod
    def load(cls, path, mode='replay'):
        with open(path, encoding='utf-8') as f:
            return cls(entries=json.load(f), mode=mode)
