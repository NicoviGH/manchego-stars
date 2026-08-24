#!/usr/bin/env python3
"""Chapter-declared playtest cases: the reader, and the matrix rows derived from them (#314).

A chapter YAML declares what its scenarios PROVE; everything mechanical about them is
derived here rather than hand-written a second time in `matrix.yaml`:

    playtest:
      boot: ch05boot                 # the ROM configuration the chapter boots on
      cases:
        - name: ch05village
          proves: the south reliquary hands over its Dracoshield
          given: [on_map]
          when:  [{visit: {x: 12, y: 19}}]
          then:  [{gained_item: 0x60}]

        - name: ch05arena
          proves: the arena tutorial is one-shot on EVFLAG_TMP(13)
          lua: ch05arena             # the escape hatch: only the BODY opts out

`host_chapter` comes from `inject/hosts.py` -- the host-slot registry, which is already the
single declaration of which vanilla slot a chapter rides. Deriving it from the chapter
NUMBER instead would be right up to ch04 and wrong forever after: from slot 6 on, vanilla's
slot index leads the chapter number by one (FE8 inserts chapter 5X at slot 5), so ch05's
cases would boot ch04's slot and assert against the wrong map while looking well-formed.

`kind` is DECLARED and never inferred from the case NAME, even though `matrix.yaml`'s
timing classes still glob on it. That is `decisions.md` -> "A verdict scenario needs no
pixels": recordsupply and recordunitlist are verdict scenarios despite the prefix, and
`kind` drives both the headless split and `check_verdict_scenarios_are_guarded`. Timing may
be inferred from a name; what a scenario ASSERTS may not.

Stdlib + pyyaml only, so CI's lightweight `checks` job can import it -- same constraint as
`campaign_chapters` and `inject/hosts`, and for the same reason.
"""
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_TOOLS = os.path.dirname(_HERE)
if _TOOLS not in sys.path:
    sys.path.insert(0, _TOOLS)

import campaign_chapters                               # noqa: E402
from inject import hosts                               # noqa: E402


class CaseError(Exception):
    """A chapter's `playtest:` block does not describe a runnable case."""


# The keys a case may carry. Anything else is a typo, and a typo that resolved to a default
# would produce a case that runs and asserts something other than what was written.
CASE_KEYS = frozenset(('name', 'proves', 'boot', 'kind', 'headless', 'deadline',
                       'checkpoint', 'manual', 'given', 'when', 'then', 'lua'))

# What a case may carry INSTEAD of `lua`. A case is one or the other, never both and never
# neither -- see _body_kind.
BODY_KEYS = ('given', 'when', 'then')


def host_slots(campaign=campaign_chapters.CAMPAIGN):
    """{short chapter id: host slot index}, from the host registry."""
    return dict((h.name, h.host_index) for h in hosts.hosted_chapters())


def _body_kind(case, where):
    """'lua' or 'declared' -- and never both, never neither.

    Both would mean two descriptions of one scenario, which is the hand-sync this issue
    exists to delete. Neither would mean a row in the matrix with nothing to run: it would
    dispatch to the declared driver, find no steps, and PASS vacuously -- a green scenario
    that asserts nothing is worse than a missing one, because it reports coverage.
    """
    has_lua = 'lua' in case
    has_body = any(k in case for k in BODY_KEYS)
    if has_lua and has_body:
        raise CaseError('%s: declares both `lua` and %s -- a case is one or the other'
                        % (where, '/'.join(k for k in BODY_KEYS if k in case)))
    if not has_lua and not has_body:
        raise CaseError('%s: declares neither `lua` nor any of %s, so there is nothing to '
                        'run (a case with no steps PASSES vacuously)'
                        % (where, '/'.join(BODY_KEYS)))
    return 'lua' if has_lua else 'declared'


def cases(docs=None, slots=None, campaign=campaign_chapters.CAMPAIGN):
    """Every declared case, validated, as (short chapter id, case dict) pairs."""
    docs = campaign_chapters.load_all(campaign) if docs is None else docs
    slots = host_slots(campaign) if slots is None else slots
    out = []
    for doc in docs:
        block = (doc or {}).get('playtest')
        if not block:
            continue
        short = campaign_chapters.short_id(doc)
        if short not in slots:
            raise CaseError(
                '%s declares playtest cases but is not hosted -- no slot in inject/hosts.py, '
                'so every case would inherit host_chapter 1 and assert against the prologue'
                % short)
        for i, case in enumerate(block.get('cases') or ()):
            where = '%s case %d' % (short, i)
            if not isinstance(case, dict):
                raise CaseError('%s: not a mapping' % where)
            name = case.get('name')
            if not name:
                raise CaseError('%s: has no `name`' % where)
            where = '%s case %s' % (short, name)
            unknown = set(case) - CASE_KEYS
            if unknown:
                raise CaseError('%s: unknown key(s) %s' % (where, ', '.join(sorted(unknown))))
            if not case.get('proves'):
                raise CaseError('%s: has no `proves` -- what a case proves is the one thing '
                                'nothing else can derive' % where)
            _body_kind(case, where)
            if not (case.get('boot') or block.get('boot')):
                raise CaseError('%s: no `boot`, and %s declares no chapter-wide one'
                                % (where, short))
            out.append((short, case))
    names = [c['name'] for _, c in out]
    dupes = sorted(set(n for n in names if names.count(n) > 1))
    if dupes:
        raise CaseError('declared twice: %s' % ', '.join(dupes))
    return out


def matrix_rows(docs=None, slots=None, campaign=campaign_chapters.CAMPAIGN):
    """{scenario name: matrix.yaml row} for every chapter-declared case.

    The row is emitted in `matrix.yaml`'s own vocabulary and resolved through the same
    defaults and timing classes, so a derived scenario and a hand-written one are the same
    kind of thing to every consumer downstream.
    """
    slots = host_slots(campaign) if slots is None else slots
    rows = {}
    for short, case in cases(docs, slots, campaign):
        row = {
            'rom': case.get('boot') or _block(docs, short, campaign)['boot'],
            'host_chapter': slots[short],
            'kind': case.get('kind', 'verdict'),
        }
        for optional in ('headless', 'deadline', 'checkpoint', 'manual'):
            if optional in case:
                row[optional] = case[optional]
        rows[case['name']] = row
    return rows


def _block(docs, short, campaign):
    docs = campaign_chapters.load_all(campaign) if docs is None else docs
    for doc in docs:
        if campaign_chapters.short_id(doc) == short:
            return doc['playtest']
    raise CaseError('no chapter %s' % short)


def matrix_suites(docs=None, slots=None, campaign=campaign_chapters.CAMPAIGN):
    """{short chapter id: [verdict case names]} -- the chapter suite, derived.

    Only VERDICT cases: a suite is what you run to know a chapter is sound, and a `record`
    capture has no verdict to be sound. `record`/`diagnostic` cases still resolve, still
    run by name, and still appear in `make chapter` -- they are simply not what a suite is.
    """
    suites = {}
    for short, case in cases(docs, slots, campaign):
        if case.get('kind', 'verdict') != 'verdict':
            continue
        suites.setdefault(short, []).append(case['name'])
    return suites


# -- emitting a case for the Lua driver ---------------------------------------------------

def _lua(value, indent=1):
    """A Python value as a Lua literal. Only the shapes a case can hold."""
    pad = '    ' * indent
    if value is True:
        return 'true'
    if value is False:
        return 'false'
    if isinstance(value, int):
        return str(value)
    if isinstance(value, str):
        return '"%s"' % value.replace('\\', '\\\\').replace('"', '\\"')
    if isinstance(value, list):
        if not value:
            return '{}'
        return '{\n%s%s,\n%s}' % (pad, (',\n' + pad).join(
            _lua(v, indent + 1) for v in value), '    ' * (indent - 1))
    if isinstance(value, dict):
        # `when`/`then` keys include Lua keywords (`then`), so every key is bracketed.
        return '{%s}' % ', '.join('["%s"] = %s' % (k, _lua(v, indent + 1))
                                  for k, v in sorted(value.items()))
    raise CaseError('cannot express %r as a Lua literal' % (value,))


def lua_case(name, docs=None, slots=None, campaign=campaign_chapters.CAMPAIGN):
    """One declared case as a Lua chunk returning its table.

    Emitted to the scenario's own run directory rather than committed: a generated file in
    the tree is a second copy of the chapter YAML that can be stale, which is the failure
    this issue exists to delete.
    """
    for _short, case in cases(docs, slots, campaign):
        if case['name'] != name:
            continue
        if 'lua' in case:
            raise CaseError('%s is a `lua:` case -- it has no declared body' % name)
        # Emitted key by key rather than as one nested literal: this file is what a human
        # opens when a declared case misbehaves, and `proves` is the first thing they want.
        out = ['-- GENERATED from the chapter YAML by tools/playtest/declared.py (#314).',
               '-- Do not edit: the chapter declares this case, and this file is rebuilt',
               '-- for every run.',
               'return {',
               '    ["name"]   = %s,' % _lua(name),
               '    ["proves"] = %s,' % _lua(campaign_chapters.squish(case['proves'])),
               '    ["given"]  = %s,' % _lua(case.get('given') or [], 2)]
        for key in ('when', 'then'):
            out.append('    ["%s"]%s = %s,' % (key, ' ' * (6 - len(key)),
                                               _lua(case.get(key) or [], 2)))
        out.append('}')
        return '\n'.join(out) + '\n'
    raise CaseError('no declared case %r (a `lua:` case is not one)' % name)


def is_declared(name, docs=None, slots=None, campaign=campaign_chapters.CAMPAIGN):
    """True if `name` is a chapter-declared case with a BODY (not a `lua:` one)."""
    return any(c['name'] == name and 'lua' not in c
               for _s, c in cases(docs, slots, campaign))


# -- subsumption ---------------------------------------------------------------------------

def _entries(case, key):
    """A case's `when`/`then` list as comparable (key, value) pairs."""
    out = []
    for entry in case.get(key) or ():
        if isinstance(entry, dict) and len(entry) == 1:
            k, v = list(entry.items())[0]
            out.append((k, repr(v) if isinstance(v, (dict, list)) else v))
    return out


def subsumes(a, b):
    """True if running case `a` proves everything case `b` does.

    Only DECLARED cases can be compared -- a `lua:` case is opaque, and guessing at what an
    opaque body covers is exactly the kind of derived claim that should not be made. Both
    must boot the same ROM, `a` must do at least everything `b` does, and `a` must assert at
    least everything `b` asserts.

    WHY THE COMPARISON IS SOUND, and what makes it unsound. It compares `when` and `then`
    as independent multisets, which is only valid because of where assertions live: an
    assertion ABOUT ONE STEP rides that step (`visit: {x, y, gains}`), and `then` holds only
    assertions about the WHOLE case (`spoke`, `event_flag`). So if b's steps are a subset of
    a's and b's whole-case assertions are a subset of a's, a really does prove everything b
    does. Move a per-step assertion back into `then` and this claim silently breaks -- a
    would then "cover" b while asserting nothing about the step b pinned.

    Coverage, not diagnosis. A subsumed case is often the better ISOLATOR: ch05reliquaries
    visits four doors in sequence, so a broken north door fails it before south is ever
    reached, where ch05village would have named south exactly. That is why this is a REPORT
    and not an automatic gate edit -- the gate only needs coverage, but which scenario a
    chapter suite keeps for diagnosis is a human call.
    """
    if 'lua' in a or 'lua' in b or a['name'] == b['name']:
        return False
    if (a.get('boot'), a.get('kind', 'verdict')) != (b.get('boot'), b.get('kind', 'verdict')):
        return False
    if not set(b.get('given') or ()) <= set(a.get('given') or ()):
        return False
    for key in ('when', 'then'):
        big, small = _entries(a, key), _entries(b, key)
        for item in small:
            if big.count(item) < small.count(item):
                return False
    return True


def subsumed_pairs(docs=None, slots=None, campaign=campaign_chapters.CAMPAIGN):
    """[(covering case, subsumed case, chapter)] over every declared case."""
    everything = cases(docs, slots, campaign)
    out = []
    for short_a, a in everything:
        for short_b, b in everything:
            if short_a == short_b and subsumes(a, b):
                out.append((a['name'], b['name'], short_a))
    return out


def main(argv):
    import argparse
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    sub = ap.add_subparsers(dest='cmd', required=True)
    e = sub.add_parser('emit', help='print one declared case as a Lua chunk')
    e.add_argument('name')
    sub.add_parser('list', help='every declared case, with what it proves')
    sub.add_parser('subsumed', help='cases another case already fully covers')
    args = ap.parse_args(argv)
    if args.cmd == 'emit':
        sys.stdout.write(lua_case(args.name))
        return 0
    if args.cmd == 'subsumed':
        pairs = subsumed_pairs()
        if not pairs:
            print('nothing subsumed: every declared case proves something no other one does')
            return 0
        print('These cases are fully covered by another case in the same chapter. Coverage '
              'only --\nthe subsumed one may still be the better ISOLATOR, so this is a '
              'report, not an edit.\n')
        for covering, subsumed, short in pairs:
            print('  %-10s %s  is fully covered by  %s' % (short, subsumed, covering))
        return 0
    for short, case in cases():
        how = 'lua:%s' % case['lua'] if 'lua' in case else 'declared'
        print('%-10s %-28s %-14s %s' % (short, case['name'], how,
                                        campaign_chapters.squish(case['proves'])))
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
