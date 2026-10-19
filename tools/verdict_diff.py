#!/usr/bin/env python3
"""Every chapter's parity verdict, before and after a change (#510 step 0).

While #510 rebuilds the parity model, every chapter is unlocked, so the `difficulty-gate` lock
no longer says when a change moves a chapter. This is what replaces it as the regression
signal: the campaign curve read in the authored table and in each difficulty mode
(Tutorial / Normal / Difficult), on the base tree and on this one, and the rows that moved.
It never fails a build. A moved verdict is the point of a model step, and the table is what a
reviewer reads to decide whether it moved the way the step claimed.

The base tree is a throwaway `git worktree` of the base commit, with this checkout's
`fireemblem8u` linked into it: `difficulty.py` reads the decomp at the submodule's HEAD, and
the submodule pointer is never committed, so both trees read the same vanilla.

  python3 tools/verdict_diff.py run [--base REF]       # base (default origin/main) vs this tree
  python3 tools/verdict_diff.py needed [--base REF]    # does the change touch a parity input?
  python3 tools/verdict_diff.py snapshot TREE OUT.json
  python3 tools/verdict_diff.py diff BEFORE.json AFTER.json

Most PRs touch nothing the read depends on (a sprite, a Lua probe, a doc), so `needed` decides
first, from `parity_inputs()`: the read's import closure, derived from the source, and the data
it opens. `test_verdict_diff` traces a real read and fails if either list misses a file.

Each (tree, mode) is its own process, run in parallel: a curve read is ~20s, and eight of
them in series would make this the slowest job in CI.
"""
import argparse
import concurrent.futures
import contextlib
import io
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CAMPAIGN = 'rime-of-the-frostmaiden'
# The authored table first: it is what the lock graded, so it reads as the familiar column.
MODES = ('table', 'tutorial', 'normal', 'difficult')
FIELDS = ('verdict', 'threat_ratio', 'load_ratio', 'accepted_adr', 'boss_drop', 'role', 'ai')
TOOLS = os.path.join(REPO, 'tools')
# Where the read starts. This tool is one: a change to how it reads is a change to the read.
ENTRY_POINTS = ('tools/difficulty.py', 'tools/verdict_diff.py')
# The injector loads itself whole (`inject.namespace.injector_modules` walks the package), so
# reaching any module in it reaches all of them.
WHOLE_PACKAGES = ('tools/inject/',)
# What the read opens that is not a module (traced, 2026-10-19). The decomp is read at the
# submodule's HEAD, and the pointer is never committed, so a PR cannot change it.
DATA_PATTERNS = (r'campaigns/[^/]+/.*\.yaml$', r'engine/patches/')


def _module_file(name):
    """tools-relative file for a dotted module name, or None outside tools/."""
    base = os.path.join(TOOLS, *name.split('.'))
    for cand in (base + '.py', os.path.join(base, '__init__.py')):
        if os.path.isfile(cand):
            return os.path.relpath(cand, REPO)
    return None


def _imports(path):
    """Every module name `path` imports, at any depth (function-level imports included)."""
    import ast
    with open(os.path.join(REPO, path)) as f:
        tree = ast.parse(f.read(), path)
    pkg = os.path.relpath(os.path.dirname(os.path.join(REPO, path)), TOOLS)
    pkg = [] if pkg == '.' else pkg.split(os.sep)
    names = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names += [a.name for a in node.names]
        elif isinstance(node, ast.ImportFrom):
            if node.level:
                root = pkg[:len(pkg) - node.level + 1]
                mod = '.'.join(root + ([node.module] if node.module else []))
            else:
                mod = node.module or ''
            names.append(mod)
            # `from inject import stats` names a module, not only an attribute.
            names += ['%s.%s' % (mod, a.name) if mod else a.name for a in node.names]
    return names


def parity_inputs():
    """(module files, whole-package prefixes, data patterns) the curve read can depend on."""
    seen, todo = set(), list(ENTRY_POINTS)
    while todo:
        path = todo.pop()
        if path in seen:
            continue
        seen.add(path)
        for pkg in WHOLE_PACKAGES:
            if path.startswith(pkg):
                for dirpath, _dirs, files in os.walk(os.path.join(REPO, pkg)):
                    todo += [os.path.relpath(os.path.join(dirpath, f), REPO)
                             for f in files if f.endswith('.py')]
        for name in _imports(path):
            parts = name.split('.')
            # Every package on the way in runs its __init__.
            for i in range(1, len(parts) + 1):
                f = _module_file('.'.join(parts[:i]))
                if f:
                    todo.append(f)
    return seen


def touches_parity(paths, inputs=None):
    """The paths in `paths` the curve read depends on."""
    inputs = parity_inputs() if inputs is None else inputs
    return [p for p in paths
            if p in inputs or any(re.match(d, p) for d in DATA_PATTERNS)
            or any(p.startswith(w) and p.endswith('.py') for w in WHOLE_PACKAGES)]


def changed_files(base):
    """Repo paths that differ between `base` and the working tree."""
    out = subprocess.run(['git', '-C', REPO, 'diff', '--name-only', base],
                         capture_output=True, text=True, check=True).stdout
    return [l for l in out.splitlines() if l]


def _github_output(key, value):
    path = os.environ.get('GITHUB_OUTPUT')
    if path:
        with open(path, 'a') as f:
            f.write('%s=%s\n' % (key, value))


def _numbers_from_text(text, label):
    """(threat_ratio, load_ratio, accepted_adr) off the printed curve row for `label`.

    Only for a base tree older than this tool, whose `curve_report` rows carry the verdict
    and not the numbers: the printed row has had both ratios as `(xN.NN)` since #48, and
    an accepted residual as `[accepted ADR NNNN]`."""
    for line in text.splitlines():
        if line.startswith('  ' + label):
            pairs = re.findall(r'\(x([\d.]+|inf)\)', line)
            adr = re.search(r'\[accepted ADR (\d+)\]', line)
            if len(pairs) >= 2:
                return float(pairs[0]), float(pairs[1]), int(adr.group(1)) if adr else None
    return None, None, None


def snapshot_mode(tree, mode):
    """{label: row} for one mode of `tree`'s curve, as plain JSON data."""
    sys.path.insert(0, os.path.join(tree, 'tools'))
    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        import difficulty
        rows = difficulty.curve_report(CAMPAIGN, mode=None if mode == 'table' else mode)
    text = out.getvalue()
    snap = {}
    for r in rows:
        if not r.get('has_ref'):
            continue
        tr, lr, adr = r.get('threat_ratio'), r.get('load_ratio'), r.get('accepted_adr')
        if 'threat_ratio' not in r:
            tr, lr, adr = _numbers_from_text(text, r['label'])
        snap[r['label']] = {
            'verdict': r['verdict'], 'threat_ratio': tr, 'load_ratio': lr,
            'accepted_adr': adr, 'boss_drop': bool(r.get('boss_drop')),
            'role': list(r.get('role') or []), 'ai': list(r.get('ai') or []),
            'locked': bool(r.get('locked'))}
    return snap


def _snapshot_one(tree, mode):
    """Run snapshot_mode in a fresh interpreter: two trees' `difficulty` modules cannot share
    one, and neither can its content memo."""
    res = subprocess.run([sys.executable, os.path.abspath(__file__), '_mode', tree, mode],
                         capture_output=True, text=True)
    if res.returncode != 0:
        raise RuntimeError('curve read failed for %s (%s):\n%s' % (tree, mode, res.stderr))
    return json.loads(res.stdout)


def snapshot(trees, jobs=None):
    """{tree: {mode: {label: row}}} for every tree, every mode, in parallel."""
    work = [(t, m) for t in trees for m in MODES]
    with concurrent.futures.ThreadPoolExecutor(max_workers=jobs or len(work)) as pool:
        futs = {w: pool.submit(_snapshot_one, *w) for w in work}
        return {t: {m: futs[(t, m)].result() for m in MODES} for t in trees}


def _moved(before, after):
    """The FIELDS that differ between two rows (None stands for a row that is absent)."""
    if before is None or after is None:
        return ['row']
    moved = []
    for f in FIELDS:
        b, a = before.get(f), after.get(f)
        # A ratio moves when the curve would PRINT it differently (two places): a delta
        # test would miss 1.064 -> 1.066, and an old tree's ratios are already rounded.
        if f.endswith('_ratio') and isinstance(b, float) and isinstance(a, float):
            if '%.2f' % a != '%.2f' % b:
                moved.append(f)
        elif b != a:
            moved.append(f)
    return moved


def _ratio(r, f):
    v = (r or {}).get(f)
    return '--' if v is None else 'x%.2f' % v


def _cell(before, after):
    if before is None and after is None:
        return ''
    if before is None:
        return 'new: %s' % after['verdict']
    if after is None:
        return '%s: gone' % before['verdict']
    if before['verdict'] != after['verdict']:
        return '**%s → %s**' % (before['verdict'], after['verdict'])
    return after['verdict'] + (' ·' if _moved(before, after) else '')


def _chapter_key(label):
    m = re.match(r'CH(\d+)', label)
    return (int(m.group(1)) if m else 999, label)


def moved_cells(before, after):
    """How many chapter-by-mode cells moved between two snapshots."""
    labels = set().union(*(before.get(m, {}).keys() | after.get(m, {}).keys() for m in MODES))
    return sum(1 for lab in labels for m in MODES
               if _moved(before.get(m, {}).get(lab), after.get(m, {}).get(lab))
               and (before.get(m, {}).get(lab) or after.get(m, {}).get(lab)))


def render(before, after, base_name='base', head_name='head'):
    """Markdown: a summary line, the verdict grid, and every moved row in detail."""
    labels = sorted(set().union(*(before.get(m, {}).keys() | after.get(m, {}).keys()
                                  for m in MODES)), key=_chapter_key)
    changed, flipped = [], 0
    for lab in labels:
        for m in MODES:
            b, a = before.get(m, {}).get(lab), after.get(m, {}).get(lab)
            mv = _moved(b, a) if (b or a) else []
            if mv:
                changed.append((lab, m, b, a, mv))
                if not b or not a or b['verdict'] != a['verdict']:
                    flipped += 1
    out = ['## Parity verdict diff (#510)', '',
           '`%s` → `%s`: %d chapter×mode cells; **%d verdict(s) changed**, %d row(s) moved.'
           % (base_name, head_name, len(labels) * len(MODES), flipped, len(changed)), '']
    out += ['| chapter | ' + ' | '.join(MODES) + ' |',
            '|---|' + '---|' * len(MODES)]
    for lab in labels:
        out.append('| %s | %s |' % (lab, ' | '.join(
            _cell(before.get(m, {}).get(lab), after.get(m, {}).get(lab)) for m in MODES)))
    if not changed:
        out += ['', 'No verdict, ratio or finding moved.']
        return '\n'.join(out) + '\n'
    out += ['', '`·` = the verdict held but a ratio or finding moved.', '',
            '| chapter | mode | verdict | threat | clear-load | also moved |',
            '|---|---|---|---|---|---|']
    for lab, m, b, a, mv in changed:
        rest = [f for f in mv if f not in ('verdict', 'threat_ratio', 'load_ratio', 'row')]
        out.append('| %s | %s | %s → %s | %s → %s | %s → %s | %s |' % (
            lab, m, (b or {}).get('verdict', '--'), (a or {}).get('verdict', '--'),
            _ratio(b, 'threat_ratio'), _ratio(a, 'threat_ratio'),
            _ratio(b, 'load_ratio'), _ratio(a, 'load_ratio'), ', '.join(rest)))
    return '\n'.join(out) + '\n'


@contextlib.contextmanager
def base_tree(ref):
    """A detached worktree of `ref` with this checkout's submodule linked in; removed after."""
    tmp = tempfile.mkdtemp(prefix='verdict-diff-')
    path = os.path.join(tmp, 'base')
    subprocess.run(['git', '-C', REPO, 'worktree', 'add', '--detach', '--quiet', path, ref],
                   check=True)
    try:
        sub = os.path.join(path, 'fireemblem8u')
        if os.path.isdir(sub) and not os.listdir(sub):
            os.rmdir(sub)
        if not os.path.exists(sub):
            os.symlink(os.path.join(REPO, 'fireemblem8u'), sub)
        yield path
    finally:
        subprocess.run(['git', '-C', REPO, 'worktree', 'remove', '--force', path],
                       check=False)
        shutil.rmtree(tmp, ignore_errors=True)


def _short(ref, tree=REPO):
    return subprocess.run(['git', '-C', tree, 'rev-parse', '--short', ref],
                          capture_output=True, text=True).stdout.strip() or ref


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest='cmd', required=True)
    r = sub.add_parser('run', help='diff the base ref against this tree')
    r.add_argument('--base', default='origin/main')
    r.add_argument('--out', help='also write the markdown here')
    s = sub.add_parser('snapshot', help='write one tree\'s verdicts as JSON')
    s.add_argument('tree')
    s.add_argument('out')
    d = sub.add_parser('diff', help='render two snapshots')
    d.add_argument('before')
    d.add_argument('after')
    n = sub.add_parser('needed', help='exit 0 if the change touches a parity input, 3 if not')
    n.add_argument('--base', default='origin/main')
    m = sub.add_parser('_mode')
    m.add_argument('tree')
    m.add_argument('mode', choices=MODES)
    args = ap.parse_args(argv)

    if args.cmd == '_mode':
        snap = snapshot_mode(args.tree, args.mode)
        sys.stdout.write(json.dumps(snap))
        return 0
    if args.cmd == 'needed':
        hits = touches_parity(changed_files(args.base))
        _github_output('needed', 'true' if hits else 'false')
        if not hits:
            print('verdict diff: no parity input changed since %s; skipped.' % args.base)
            return 3
        print('verdict diff: %d parity input(s) changed since %s, e.g. %s'
              % (len(hits), args.base, ', '.join(hits[:5])))
        return 0
    if args.cmd == 'snapshot':
        with open(args.out, 'w') as f:
            json.dump(snapshot([args.tree])[args.tree], f, indent=1, sort_keys=True)
        return 0
    if args.cmd == 'diff':
        with open(args.before) as f:
            before = json.load(f)
        with open(args.after) as f:
            after = json.load(f)
        sys.stdout.write(render(before, after, args.before, args.after))
        return 0
    with base_tree(args.base) as base:
        snaps = snapshot([base, REPO])
        md = render(snaps[base], snaps[REPO], '%s (%s)' % (args.base, _short(args.base)),
                    _short('HEAD') + ('+dirty' if subprocess.run(
                        ['git', '-C', REPO, 'status', '--porcelain', '--untracked-files=no'],
                        capture_output=True, text=True).stdout.strip() else ''))
    _github_output('moved', moved_cells(snaps[base], snaps[REPO]))
    sys.stdout.write(md)
    if args.out:
        with open(args.out, 'w') as f:
            f.write(md)
    return 0


if __name__ == '__main__':
    sys.exit(main())
