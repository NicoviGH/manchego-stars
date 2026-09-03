#!/usr/bin/env python3
"""What does editing X actually re-run? (#255)

The verdict cache is only worth having if its answers are RIGHT in both directions, and
unit tests cannot show that: they exercise the key arithmetic against synthetic manifests,
while the failures that actually bit us came from the real build -- shared whole-campaign
tables, and a path set that churned depending on which ROM configuration was built before.
Comparing keys by hand missed both.

So this drives the real thing. For each edit it makes the edit, regenerates whatever the
edit can move (the scope manifest, via `build_campaign.py` -- the injector only, no
compile), recomputes every scenario's verdict key, and reports which scenarios a matrix run
would re-execute. Then it puts the tree back.

    python3 tools/probe_invalidation.py                 # every case
    python3 tools/probe_invalidation.py --case ch05     # one
    python3 tools/probe_invalidation.py --suite gate    # against a different scenario set

Each case declares what it EXPECTS -- `must_run` and `must_cache` -- so a surprise is a
failure with a name, not a table somebody has to read carefully. Cases whose edit cannot
change a ROM input skip the rebuild entirely and answer in milliseconds.

This mutates the working tree while it runs and restores with `git checkout`. It is a
diagnostic, deliberately NOT part of `make test`: it costs real builds.
"""
import argparse
import json
import os
import re
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(HERE, 'playtest'))
sys.path.insert(0, HERE)
import matrix as mx                                     # noqa: E402
import build_scopes                                     # noqa: E402

CAMPAIGNS = os.path.join(REPO, 'campaigns', 'rime-of-the-frostmaiden')
CHAPTERS = os.path.join(CAMPAIGNS, 'chapters')


# -- edits ------------------------------------------------------------------

def bump_first_level(path):
    """Nudge the first `level:` in a chapter YAML -- the smallest real content edit."""
    def edit():
        with open(path) as fh:
            text = fh.read()
        m = re.search(r'^(\s+level: )(\d+)', text, re.M)
        with open(path, 'w') as fh:
            fh.write(text[:m.start()] + m.group(1) + str(int(m.group(2)) + 1) + text[m.end():])
    return edit, path


def bump_enemy_level(path):
    """Nudge the first level under `enemy_units:` -- content the injector really writes."""
    def edit():
        with open(path) as fh:
            text = fh.read()
        start = text.index('\nenemy_units:')
        m = re.search(r'^(\s+level: )(\d+)', text[start:], re.M)
        at = start + m.start()
        with open(path, 'w') as fh:
            fh.write(text[:at] + m.group(1) + str(int(m.group(2)) + 1)
                     + text[start + m.end():])
    return edit, path


def append_line(path, line):
    def edit():
        with open(path, 'a') as fh:
            fh.write(line)
    return edit, path


def rewrite(path, old, new):
    def edit():
        with open(path) as fh:
            text = fh.read()
        assert old in text, 'probe anchor missing in %s: %r' % (path, old)
        with open(path, 'w') as fh:
            fh.write(text.replace(old, new, 1))
    return edit, path


CASES = [
    # name, (edit, path to restore), rebuild?, must_run, must_cache
    ('ch01', bump_first_level(os.path.join(CHAPTERS, 'ch01-the-iron-trail.yaml')), True,
     ['ch01', 'ch01win', 'lordfloor'], []),
    ('ch05', bump_first_level(os.path.join(CHAPTERS, 'ch05-the-elven-tomb.yaml')), True,
     ['ch05arena', 'ch05raid'], ['ch01win', 'ch04moose', 'recordunitlist']),
    # NOT `level:` in the chapter roster -- that is a PC annotation, and real PC stats live
    # in campaigns/.../pcs/, so editing it changes no injected byte and the cache is RIGHT to
    # skip. (First run of this probe asserted otherwise and was wrong.) `enemy_units` is
    # prologue-scoped content the injector genuinely consumes.
    # SETTLED 2026-08-13, and the cache was NOT at fault. This case was red because bumping
    # `level: 5 -> 6` under the prologue's `enemy_units` moved no injected byte at all. Two
    # full ROM builds, edited and not, came out byte-identical (sha256), and the injector
    # wrote zero differing files across the whole 20k-file decomp tree -- so the cache was
    # right to serve every PASS. The bug was upstream: inject_prologue emitted the roster as
    # C literals under a comment claiming it read the chapter YAML, and every literal
    # happened to match the YAML, so nothing looked wrong. `_prologue_roster_blocks` now
    # sources levels/positions/head-count (verified byte-neutral: same ROM sha256), and the
    # field is live. The prologue is HOSTED on chapter 1, which is why ch01's scenarios move
    # with it. Long form: decisions.md -> "A cache can be right for the wrong reason".
    ('prologue', bump_enemy_level(os.path.join(CHAPTERS, 'ch00-prologue-a-dagger-of-ice.yaml')),
     True, ['win', 'ch01win', 'lordfloor'], ['ch05arena', 'ch04moose']),
    ('docs', append_line(os.path.join(REPO, 'docs', 'decisions.md'), '\n<!-- probe -->\n'),
     False, [], ['ch01win', 'ch05arena', 'ch04moose', 'win']),
    ('harness-one-scenario',
     rewrite(mx.HARNESS, 'scenarios.ch05arena = function()',
             'scenarios.ch05arena = function()\n    local probe = 1'), False,
     ['ch05arena'], ['ch01win', 'ch04moose', 'win']),
    ('harness-shared-helper',
     rewrite(mx.HARNESS, 'guardedInput = function(intention, key, expected, predicate, frames)',
             'guardedInput = function(intention, key, expected, predicate, frames)\n    local probe = 1'),
     False, ['ch01win', 'ch05arena', 'ch04moose'], []),
    ('clearbot', append_line(os.path.join(HERE, 'playtest', 'clearbot.lua'), '\n-- probe\n'),
     False, ['clear_ch04_parley'], ['ch05arena', 'ch01win', 'win']),
    ('controller', append_line(os.path.join(HERE, 'playtest', 'controller.lua'), '\n-- probe\n'),
     False, ['ch01win', 'ch05arena', 'ch04moose'], []),
    ('run.sh', append_line(os.path.join(HERE, 'playtest', 'run.sh'), '\n# probe\n'),
     False, ['ch01win', 'ch05arena'], []),
    ('matrix.yaml-one-row',
     rewrite(mx.MANIFEST, '  ch05arena:\n    rom: ch05boot',
             '  ch05arena:\n    deadline: 999\n    rom: ch05boot'), False,
     ['ch05arena'], ['ch01win', 'ch05raid']),
    ('portrait-global',
     bump_first_level(os.path.join(CAMPAIGNS, 'pcs', sorted(
         f for f in os.listdir(os.path.join(CAMPAIGNS, 'pcs')) if f.endswith('.yaml'))[0])),
     True, ['ch01win', 'ch05arena'], []),
]


# -- machinery --------------------------------------------------------------

# make-flag -> the build_campaign.py switch that sets it (Makefile line 39).
FLAG_ARGS = {'TESTCH': '--test-chapter', 'LORDBOOT': '--lord-boot', 'MONTAGE': '--montage',
             'CH01BOOT': '--ch01-boot',
             'CH03BOOT': '--ch03-boot', 'CH04BOOT': '--ch04-boot', 'CH05BOOT': '--ch05-boot',
             'CH05LUPIN': '--ch05-lupin', 'CH05MOOSE': '--ch05-moose',
             'CH05ENDING': '--ch05-ending'}

# Switches that take a VALUE rather than being a bare on/off flag. `--ch05-ending` without its
# arm is an argparse error 2, surfacing as an opaque CalledProcessError three frames away.
VALUED_FLAGS = frozenset({'CH05ENDING'})


def keys_for(names, manifests):
    out = {}
    for name in names:
        s = mx.Manifest.load().resolve(name)
        if s.kind != 'verdict':
            continue
        digest = mx.rom_input_hash(s.make_flags)
        out[name] = mx.scenario_fingerprint(
            s, digest, scopes=manifests.get(s.rom),
            observed=mx.load_observed_chapters(name))
    return out


def build_manifests(roms):
    """Run the injector for each ROM configuration and collect its scope manifest.

    Runs them in the matrix's own order, and that ordering is the point: the churn bug
    this probe exists to catch only appears when configurations alternate.
    """
    out = {}
    for rom in roms:
        flags = mx.Manifest.load().resolve_rom(rom)
        cmd = [sys.executable, os.path.join(HERE, 'build_campaign.py'),
               '--campaign', 'rime-of-the-frostmaiden']
        # A VALUED switch has to carry its value: `--ch05-ending` bare exits argparse 2, and
        # the caller only sees an opaque CalledProcessError (#357 review). resolve_rom yields
        # "CH05ENDING=full" for those, so keep the arm.
        for flag in flags:
            name, _, value = flag.partition('=')
            switch = FLAG_ARGS[name]
            cmd.append('%s=%s' % (switch, value) if name in VALUED_FLAGS else switch)
        subprocess.run(cmd, cwd=REPO, check=True, capture_output=True)
        out[rom] = build_scopes.load_manifest(
            os.path.join(REPO, '.build-scopes.json'))
    return out


def restore(path):
    subprocess.run(['git', 'checkout', '--', path], cwd=REPO, capture_output=True)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument('--case', action='append', help='run only these cases')
    ap.add_argument('--suite', default='gate')
    args = ap.parse_args(argv)

    names = [n for n in mx.Manifest.load().select(suite=args.suite)
             if mx.Manifest.load().resolve(n).kind == 'verdict']
    roms = sorted({mx.Manifest.load().resolve(n).rom for n in names})
    print('probing %d scenario(s) across %d ROM configuration(s)\n' % (len(names), len(roms)))

    base_manifests = build_manifests(roms)
    base = keys_for(names, base_manifests)

    failures = []
    for case, (edit, path), rebuild, must_run, must_cache in CASES:
        if args.case and case not in args.case:
            continue
        edit()
        try:
            manifests = build_manifests(roms) if rebuild else base_manifests
            after = keys_for(names, manifests)
        finally:
            restore(path)
        ran = sorted(n for n in names if base.get(n) != after.get(n))
        cached = [n for n in names if n not in ran]
        print('%-22s %2d run, %2d cached   %s' % (case, len(ran), len(cached),
                                                  ' '.join(ran) if len(ran) < 8 else ''))
        for want in must_run:
            if want in names and want not in ran:
                failures.append('%s: %s should have re-run' % (case, want))
        for want in must_cache:
            if want in names and want in ran:
                failures.append('%s: %s should have stayed cached' % (case, want))
    # Leave the tree's manifest describing unedited sources, whatever ran above. Cases that
    # rebuild already start from restored sources, so this is only needed once, at the end.
    build_manifests(roms)

    print('')
    if failures:
        print('SURPRISES (%d):' % len(failures))
        for f in failures:
            print('  - ' + f)
        return 1
    print('every case matched expectation')
    return 0


if __name__ == '__main__':
    sys.exit(main())
