#!/usr/bin/env python3
"""LLM-player pure cores -- soak/balance driver that replaces the clear-bot policy.

Playtest platform brick 4 (#49 spine; epic #63). This module is the *policy + transport*
sidecar that runs OUTSIDE mGBA (the emulator's embedded Lua can't make network calls):
the harness exports the board to a file and blocks, this process decides, writes the
orders back. Per the platform doctrine -- pure core, driver owns I/O -- everything here
is plain Python, unit-testable on CI with no emulator (test_llm_player.py).

M1 shipped the three pure cores (serialize_board, validate_orders, Transcript). M2 adds
the sidecar itself: the request/response FILE loop (`Sidecar`, `serve` CLI) plus the
provider-agnostic live policy -- prompt builder, robust order parsing, and two urllib
transports (Anthropic Messages API, or ANY OpenAI-compatible /chat/completions endpoint,
which is how a FREE local model plays: Ollama or llama.cpp serving Llama/Gemma). Replay
from a recorded transcript stays the default -- CI and re-soaks never call a model.

Handshake (epic #63): the harness writes `req-<n>.json` {seed, chapter, turn, faction,
board} and polls for `resp-<n>.json` {orders, rejected, reasoning?}; all writes on both
sides are tmp+rename so a half-written file is never read.

Design + settled decisions: docs/decisions.md -> Playtest platform brick 4; epic #63.
"""
import argparse
import hashlib
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request


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


# ---------------------------------------------------------------- prompt + parse (pure)

SYSTEM_PROMPT = """\
You are the commander of the %(faction)s army in a Fire Emblem (GBA) tactics battle.
Each turn you receive the full board as JSON and must order your units.

Rules:
- Order ONLY units of your faction with "can_act": true.
- "move_to" MUST be one of that unit's "reach" tiles (listed as [x, y] pairs).
- "attack" needs a "target" (an enemy unit id) whose Manhattan distance from your
  "move_to" tile is within the unit's weapon "range" [min, max].
- Units act in the order you list them. A unit not ordered simply stays put.
- Play to WIN without losing units: gang up to secure kills, keep the wounded out of
  enemy reach, and press toward the objective.

Reply with ONLY a JSON object, no other text:
{"orders": [{"unit": <id>, "move_to": {"x": <x>, "y": <y>},
             "action": "attack"|"wait"|"seize"|"staff", "target": <enemy id, if attacking>}]}
"""


def build_prompt(board, faction):
    """(system, user) prompt pair for one per-turn commander decision.

    Pure: the user half embeds `serialize_board` (the same bytes the transcript keys
    on), so a prompt is reproducible from the request file alone.
    """
    system = SYSTEM_PROMPT % {'faction': faction}
    user = 'Objective: %s\nBoard:\n%s\nGive your orders.' % (
        board.get('objective', 'defeat the boss'), serialize_board(board))
    return system, user


def parse_orders(text):
    """Model output text -> the orders list, or [] on anything unparseable.

    LLMs wrap JSON in prose or code fences despite instructions; a free local model
    (Llama/Gemma) does so more than most. Extraction ladder: whole text as JSON -> the
    first ```-fenced block -> the outermost {...} or [...] slice. Accepts either a bare
    orders array or an object with an "orders" key. Never raises -- a garbage turn
    returns [] and plays as all-wait (the soft-lock guard is the harness's timeout).
    """
    if not isinstance(text, str):
        return []
    candidates = [text.strip()]
    fence = re.search(r'```(?:json)?\s*(.*?)```', text, re.DOTALL)
    if fence:
        candidates.append(fence.group(1).strip())
    for opener, closer in (('{', '}'), ('[', ']')):
        start, end = text.find(opener), text.rfind(closer)
        if 0 <= start < end:
            candidates.append(text[start:end + 1])
    for cand in candidates:
        try:
            got = json.loads(cand)
        except ValueError:
            continue
        if isinstance(got, dict):
            got = got.get('orders')
        if isinstance(got, list):
            return [o for o in got if isinstance(o, dict)]
    return []


# ---------------------------------------------------------------- live policy (urllib)
# No SDK dependency on purpose: this repo's tooling is stdlib+{numpy,pillow,pyyaml} only,
# and the sidecar must run anywhere a playtester has python3. Both transports are thin
# enough that urllib is the smaller risk (vs. a new dep for two POSTs).

ANTHROPIC_URL = 'https://api.anthropic.com/v1/messages'
ANTHROPIC_VERSION = '2023-06-01'
OLLAMA_BASE_URL = 'http://localhost:11434/v1'   # OpenAI-compatible; llama.cpp/vLLM too
DEFAULT_MODELS = {
    # Epic #63 locked "Sonnet default" -- a weak player fires FALSE balance alarms.
    'anthropic': 'claude-sonnet-5',
    # The free happy medium (Nicolas 2026-07-02): a local model via Ollama. Weaker play
    # = plumbing/smoke value more than balance-signal value; see decisions.md.
    'openai': 'llama3.1',
}


def _post_json(url, headers, payload, timeout=120):
    """POST a JSON payload, return the parsed JSON response. Raises RuntimeError with
    the response body on an HTTP error (the body carries the useful message)."""
    req = urllib.request.Request(
        url, data=json.dumps(payload).encode('utf-8'),
        headers=dict(headers, **{'content-type': 'application/json'}), method='POST')
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode('utf-8'))
    except urllib.error.HTTPError as e:
        raise RuntimeError('%s -> HTTP %d: %s'
                           % (url, e.code, e.read().decode('utf-8', 'replace')[:500]))


def _call_anthropic(cfg, system, user):
    resp = _post_json(
        cfg.get('base_url') or ANTHROPIC_URL,
        {'x-api-key': cfg['api_key'], 'anthropic-version': ANTHROPIC_VERSION},
        {'model': cfg['model'], 'max_tokens': 2048, 'system': system,
         'messages': [{'role': 'user', 'content': user}]})
    return ''.join(b.get('text', '') for b in resp.get('content', [])
                   if b.get('type') == 'text')


def _call_openai(cfg, system, user):
    base = (cfg.get('base_url') or OLLAMA_BASE_URL).rstrip('/')
    resp = _post_json(
        base + '/chat/completions',
        # Ollama/llama.cpp ignore the key but the header keeps real OpenAI-compatible
        # hosts happy; "ollama" is the conventional placeholder.
        {'authorization': 'Bearer ' + (cfg.get('api_key') or 'ollama')},
        {'model': cfg['model'],
         'messages': [{'role': 'system', 'content': system},
                      {'role': 'user', 'content': user}]})
    return resp['choices'][0]['message']['content'] or ''

PROVIDERS = {'anthropic': _call_anthropic, 'openai': _call_openai}


def policy_config(env=None):
    """Resolve the live-policy knobs from the environment.

    PT_PROVIDER  anthropic (default; epic: Sonnet plays well enough to trust the signal)
                 | openai = any OpenAI-compatible endpoint -- Ollama/llama.cpp serving
                 Llama or Gemma is the FREE local soak.
    PT_MODEL     model id (defaults per provider, see DEFAULT_MODELS)
    PT_BASE_URL  endpoint override (openai default: OLLAMA_BASE_URL, localhost:11434)
    PT_API_KEY   key for openai-compatible hosts (unneeded for local Ollama);
                 anthropic reads ANTHROPIC_API_KEY.
    """
    env = os.environ if env is None else env
    provider = env.get('PT_PROVIDER', 'anthropic').lower()
    if provider not in PROVIDERS:
        raise ValueError('PT_PROVIDER must be one of %s, got %r'
                         % ('/'.join(sorted(PROVIDERS)), provider))
    return {
        'provider': provider,
        'model': env.get('PT_MODEL') or DEFAULT_MODELS[provider],
        'base_url': env.get('PT_BASE_URL') or None,
        'api_key': env.get('PT_API_KEY') or env.get('ANTHROPIC_API_KEY') or None,
    }


def make_policy(faction, env=None, transport=None):
    """A `decide_fn(board) -> orders` closure over the env-configured provider.

    `transport` (tests) replaces the HTTP call: (cfg, system, user) -> response text.
    """
    cfg = policy_config(env)
    if cfg['provider'] == 'anthropic' and not cfg['api_key'] and transport is None:
        raise ValueError('anthropic provider needs ANTHROPIC_API_KEY (or PT_API_KEY); '
                         'for a free local model: PT_PROVIDER=openai + an Ollama serve')
    call = transport or PROVIDERS[cfg['provider']]

    def decide(board):
        system, user = build_prompt(board, faction)
        return parse_orders(call(cfg, system, user))
    return decide


# ---------------------------------------------------------------- sidecar file loop

REQ_RE = re.compile(r'^req-(\d+)\.json$')


class Sidecar:
    """The request/response file loop the harness's `llm` scenario talks to.

    One `step()` answers the lowest-numbered unanswered request (testable without any
    filesystem watching or threads); `serve()` polls until a `stop` file appears. Every
    response is written tmp+rename so the polling harness never reads a partial file.
    Orders pass through `validate_orders` before they ship: the harness only ever sees
    legal orders in `orders`, with the culls in `rejected` (a play-quality signal it
    logs). A replay-mode transcript miss writes an error response (fast, diagnosable
    FAIL on the harness side) and then re-raises -- CI/replay is closed-world.
    """

    def __init__(self, dirpath, transcript, policy=None, faction='blue'):
        self.dir = dirpath
        self.transcript = transcript
        self.policy = policy
        self.faction = faction

    def _pending(self):
        reqs = []
        for name in os.listdir(self.dir):
            m = REQ_RE.match(name)
            if m and not os.path.exists(os.path.join(self.dir, 'resp-%s.json' % m.group(1))):
                reqs.append(int(m.group(1)))
        return sorted(reqs)

    def _write_resp(self, n, payload):
        final = os.path.join(self.dir, 'resp-%d.json' % n)
        tmp = final + '.tmp'
        with open(tmp, 'w', encoding='utf-8') as f:
            json.dump(payload, f)
        os.replace(tmp, final)

    def step(self):
        """Answer one pending request; returns its number, or None when idle."""
        pending = self._pending()
        if not pending:
            return None
        n = pending[0]
        with open(os.path.join(self.dir, 'req-%d.json' % n), encoding='utf-8') as f:
            req = json.load(f)
        board = req['board']
        faction = req.get('faction', self.faction)
        try:
            orders = self.transcript.decide(board, seed=req.get('seed'),
                                            chapter=req.get('chapter'),
                                            turn=req.get('turn'),
                                            decide_fn=self.policy)
        except TranscriptMiss as e:
            self._write_resp(n, {'orders': [], 'error': 'transcript miss: %s' % e})
            raise
        accepted, rejected = validate_orders(orders, board, faction)
        self._write_resp(n, {'orders': accepted, 'rejected': rejected})
        return n

    def serve(self, poll_interval=0.25, log=None):
        """Answer requests until `<dir>/stop` exists (pending requests are drained
        before the stop is honored). Returns the number of requests answered."""
        stop = os.path.join(self.dir, 'stop')
        answered = 0
        while True:
            n = self.step()
            if n is not None:
                answered += 1
                if log:
                    log('answered req-%d' % n)
                continue
            if os.path.exists(stop):
                return answered
            time.sleep(poll_interval)


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = p.add_subparsers(dest='cmd', required=True)
    s = sub.add_parser('serve', help='answer harness requests from a handshake dir')
    s.add_argument('--dir', required=True, help='handshake dir (harness PT_LLM_DIR)')
    s.add_argument('--transcript', required=True,
                   help='transcript JSON path (created in --record mode)')
    s.add_argument('--record', action='store_true',
                   help='record mode: cache miss -> live model call (env knobs: '
                        'PT_PROVIDER/PT_MODEL/PT_BASE_URL); default is replay-only')
    s.add_argument('--faction', default='blue')
    args = p.parse_args(argv)

    os.makedirs(args.dir, exist_ok=True)
    if args.record:
        transcript = (Transcript.load(args.transcript, mode='record')
                      if os.path.exists(args.transcript) else Transcript(mode='record'))
        policy = make_policy(args.faction)
        cfg = policy_config()
        print('record mode: %(provider)s %(model)s (base %(base_url)s)'
              % dict(cfg, base_url=cfg['base_url'] or 'default'))
    else:
        transcript = Transcript.load(args.transcript, mode='replay')
        policy = None
        print('replay mode: %d recorded decisions' % len(transcript.entries))
    sidecar = Sidecar(args.dir, transcript, policy=policy, faction=args.faction)
    try:
        answered = sidecar.serve(log=lambda s: print(s, flush=True))
    finally:
        if args.record:
            transcript.save(args.transcript)
            print('transcript saved: %s (%d entries)'
                  % (args.transcript, len(transcript.entries)))
    print('served %d requests' % answered)
    return 0


if __name__ == '__main__':
    sys.exit(main())
