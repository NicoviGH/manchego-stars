#!/usr/bin/env python3
"""Read a playtest log semantically: what FE8 was doing, why the controller classified it
that way, and where two runs first diverge (#236).

    tools/playtest/inspect_state.py render /tmp/playtest-ch01/playtest.log
    tools/playtest/inspect_state.py diff /tmp/accepted.log /tmp/playtest-ch01/playtest.log

The harness emits the state; this names and formats it. Addresses resolve against
symbols.json (written by gen_symbols.py after every make) by EXACT match -- idle callbacks
are ordinary functions, ~35k of them, which is why the Lua side dumps raw addresses and
the naming happens here. An address that matches no symbol is reported as unknown; a
nearest-preceding guess is what made #232's freeze reports untrustworthy.

Named inspect_state.py, not inspect.py: the playtest directory goes on sys.path, and a
module called `inspect` there would shadow the standard library's for everything that
imports it, unittest included.
"""
import argparse
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
SYMBOLS_JSON = os.path.join(HERE, 'symbols.json')

# The transition fields that make two runs meaningfully different, in the order a reader
# wants them: what state the game was in, what the controller did, what came of it.
DIVERGENCE_FIELDS = ('state', 'action', 'result')


def parse_records(text):
    """The JSON events in a playtest log, in order. Plain log lines are skipped, and so
    is anything malformed -- a truncated log (mGBA killed at its deadline) is normal
    input, not an error."""
    out = []
    for line in text.splitlines():
        # Every harness line is stamped with the frame it happened on -- `[f021071] {...}`
        # -- so a record never starts at column 0.
        brace = line.find('{')
        if brace < 0:
            continue
        try:
            record = json.loads(line[brace:])
        except ValueError:
            continue
        if isinstance(record, dict) and 'event' in record:
            out.append(record)
    return out


def load_symbols(path=SYMBOLS_JSON):
    if not os.path.exists(path):
        return {}
    with open(path, encoding='utf-8') as f:
        raw = json.load(f)
    return {int(a, 16): n for a, n in raw.get('code', {}).items()}


def resolve(symbols, addr):
    """An address (hex string or int) as `Symbol(0x...)`, `none`, or an honest unknown."""
    if addr is None:
        return 'none'
    value = addr if isinstance(addr, int) else int(str(addr), 16)
    if value == 0:
        return 'none'
    name = symbols.get(value)
    if name is None:
        return 'unknown@0x%08X' % value
    return '%s(0x%08X)' % (name, value)


def _world_line(world):
    if not world:
        return '  world:  -'
    return '  world:  chapter=%s turn=%s faction=0x%02X host_chapter=%s' % (
        world.get('chapter'), world.get('turn'), world.get('faction') or 0,
        world.get('host_chapter'))


def _cursor_line(cursor):
    if not cursor:
        return '  cursor: -  (no live map)'
    return '  cursor: (%s,%s) unit=0x%02X %s select=%s reachable=%s' % (
        cursor.get('x'), cursor.get('y'), cursor.get('unit') or 0,
        cursor.get('unit_faction') or '-', cursor.get('unit_select_kind') or '-',
        cursor.get('reachable'))


def _menu_line(menu):
    if not menu:
        return '  menu:   -'
    items = ' '.join('0x%02X%s' % (i.get('override_id') or 0,
                                   '' if i.get('availability') == 1 else '(disabled)')
                     for i in menu.get('items', []))
    return '  menu:   current=%s [%s] on_b=%s' % (
        menu.get('current'), items, menu.get('on_b') or '-')


def render_inspect(record, symbols):
    """One snapshot as a human-readable block."""
    lines = ['== INSPECT (%s) scenario=%s ==' % (record.get('tag') or '?',
                                                 record.get('scenario') or '?')]
    verdict = '  state:  %s' % (record.get('state') or 'unsupported')
    if record.get('matched_rule'):
        verdict += '   [rule: %s]' % record['matched_rule']
    if record.get('unclassified_wait'):
        verdict += '   *** UNCLASSIFIED WAIT ***'
    lines.append(verdict)
    if record.get('classification_error'):
        lines.append('  error:  %s' % record['classification_error'])
    if record.get('detail'):
        lines.append('  detail: %s' % record['detail'])
    lines.append(_world_line(record.get('world')))
    lines.append(_cursor_line(record.get('cursor')))
    lines.append(_menu_line(record.get('menu')))
    if record.get('target'):
        target = record['target']
        lines.append('  target: kind=%s at (%s,%s) uid=0x%02X frozen=%s' % (
            target.get('kind'), target.get('x'), target.get('y'),
            target.get('uid') or 0, target.get('frozen')))
    if record.get('prep'):
        prep = record['prep']
        lines.append('  prep:   current=%s help_open=%s on_start=%s' % (
            prep.get('current'), prep.get('help_open'), prep.get('on_start')))

    considered = record.get('considered') or []
    if considered:
        lines.append('  considered (in order, all rejected before the verdict):')
        for entry in considered:
            lines.append('    %-18s %s' % (entry.get('rule'), entry.get('reason')))

    procs = record.get('procs') or []
    if procs:
        # FROZEN means the proc held the same script command, sleep and lock across both
        # samples -- the difference between a scene that is slow and one that is waiting.
        lines.append('  live procs (sampled twice):')
        for p in procs:
            lines.append('    [%02d] %-32s cmd#%-4s idle=%-34s sleep=%-4s lock=%s%s' % (
                p.get('slot') or 0, p.get('script_name') or '?', p.get('step'),
                resolve(symbols, p.get('idle')), p.get('sleep'), p.get('lock'),
                '  FROZEN' if p.get('frozen') else ''))
    return '\n'.join(lines)


def render_log(text, symbols):
    snapshots = [r for r in parse_records(text) if r.get('event') == 'inspect']
    if not snapshots:
        return 'no inspect snapshots in this log (the run never faulted or stalled)'
    return '\n\n'.join(render_inspect(r, symbols) for r in snapshots)


def _steps(records):
    return [r for r in records if r.get('event') == 'transition']


def first_divergence(baseline, candidate):
    """The first step where two runs stop agreeing, or None. Only `transition` records
    count as steps -- inspect snapshots are diagnostics and may appear in one run and not
    the other without meaning the runs differ."""
    left, right = _steps(baseline), _steps(candidate)
    for index in range(max(len(left), len(right))):
        if index >= len(left) or index >= len(right):
            return {
                'index': index,
                'field': 'length',
                'baseline': left[index].get('state') if index < len(left) else None,
                'candidate': right[index].get('state') if index < len(right) else None,
                'baseline_record': left[index] if index < len(left) else None,
                'candidate_record': right[index] if index < len(right) else None,
            }
        for field in DIVERGENCE_FIELDS:
            if left[index].get(field) != right[index].get(field):
                return {
                    'index': index,
                    'field': field,
                    'baseline': left[index].get(field),
                    'candidate': right[index].get(field),
                    'baseline_record': left[index],
                    'candidate_record': right[index],
                }
    return None


def _evidence(record):
    if not record:
        return '      (the run had no step here)'
    before = (record.get('before') or {}).get('classification')
    after = (record.get('after') or {}).get('classification')
    return ('      state=%s action=%s input=%s result=%s\n'
            '      before=%s after=%s expected=%s' % (
                record.get('state'), record.get('action'), record.get('input'),
                record.get('result'), before, after, record.get('expected')))


def format_divergence(divergence, baseline_name, candidate_name):
    if divergence is None:
        return 'no divergence: both runs took the same semantic steps'
    lines = [
        'first divergence at step %d (%s)' % (divergence['index'], divergence['field']),
        '  %s: %s' % (baseline_name, divergence['baseline']),
        _evidence(divergence['baseline_record']),
        '  %s: %s' % (candidate_name, divergence['candidate']),
        _evidence(divergence['candidate_record']),
    ]
    return '\n'.join(lines)


def _read(path):
    with open(path, encoding='utf-8') as f:
        return f.read()


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    parser.add_argument('--symbols', default=SYMBOLS_JSON,
                        help='symbols.json from gen_symbols.py (default: alongside this tool)')
    sub = parser.add_subparsers(dest='command', required=True)
    render = sub.add_parser('render', help='human-readable state snapshots from a log')
    render.add_argument('log')
    diff = sub.add_parser('diff', help='first semantic divergence between two runs')
    diff.add_argument('baseline')
    diff.add_argument('candidate')
    args = parser.parse_args(argv)

    if args.command == 'render':
        print(render_log(_read(args.log), load_symbols(args.symbols)))
        return 0
    divergence = first_divergence(parse_records(_read(args.baseline)),
                                  parse_records(_read(args.candidate)))
    print(format_divergence(divergence, args.baseline, args.candidate))
    return 1 if divergence else 0


if __name__ == '__main__':
    sys.exit(main())
