#!/usr/bin/env python3
"""Which ROM configurations can a change move? The fingerprint gate's aim (#424).

`injection_fingerprint.py` gates a refactor one configuration at a time, ~2.5 min each, and
there are as many configurations as `playtest/matrix.yaml` has `rom_configs`. Most of them
build the default tree plus one boot step, so fingerprinting all of them for every change
pays for the same answer over and over. This reads the answer off the step declarations
(ADR 0304) instead:

    python3 tools/fingerprint_reach.py                 # this branch against origin/main
    python3 tools/fingerprint_reach.py --base HEAD~1

A configuration other than the default is reached when a step that RUNS under it either
reads a flag it sets (the step's `flags`) or does not run in the default build at all, and the
change lands in that step's code: the module that defines the step's function, plus every
module it imports. That last part is what catches `inject/montage.py`, which the prologue
imports and the default build never exercises, because it runs with `--montage` off.

Three kinds of change reach every configuration: `inject/steps.py` and `build_campaign.py`
(they hold each step's `when` and `call`, which is where a flag is read), and any ROM input
that is not Python -- campaign data, engine patches, the Makefile -- because no step declares
what it READS, so a data file cannot be charged to one step.

WHAT THIS DOES NOT SEE. A step reads the tree the steps before it wrote, so a flag-reading
step can in principle change what a later, flagless one produces. And `inject.namespace`
imports every injector module to collect constants, which is not followed here: those
registries run in every configuration, so the default build already measures them. Both are
the default build's job, and it is always in the answer when anything is.
"""
import argparse
import ast
import collections
import functools
import glob
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, 'playtest'))

CAMPAIGN = 'rime-of-the-frostmaiden'
# Reach every configuration: the step list itself, and the CLI that parses the flags.
EVERYWHERE = ('tools/inject/steps.py', 'tools/build_campaign.py')


def configurations():
    """{name: build_campaign switches} for every matrix ROM configuration, canonical first."""
    import matrix as mx
    import probe_invalidation
    manifest = mx.Manifest.load()
    names = sorted(manifest.rom_configs, key=lambda n: n != 'canonical')
    return collections.OrderedDict(
        (name, probe_invalidation.switches(manifest.resolve_rom(name))) for name in names)


def _module_files():
    """{module name: repo-relative path} for every module the injector can import."""
    out = {}
    for path in glob.glob(os.path.join(HERE, '*.py')) + glob.glob(
            os.path.join(HERE, 'inject', '**', '*.py'), recursive=True):
        rel = os.path.relpath(path, HERE)[:-3].replace(os.sep, '.')
        out[rel[:-len('.__init__')] if rel.endswith('.__init__') else rel] = \
            os.path.relpath(path, REPO)
    return out


def _imports(path, modules):
    """The modules in `modules` that the file at `path` imports, by name."""
    with open(os.path.join(REPO, path)) as fh:
        tree = ast.parse(fh.read(), path)
    found = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            found.update(a.name for a in node.names if a.name in modules)
        elif isinstance(node, ast.ImportFrom) and node.module and not node.level:
            if node.module in modules:
                found.add(node.module)
            found.update(node.module + '.' + a.name for a in node.names
                         if node.module + '.' + a.name in modules)
    return found


@functools.lru_cache(maxsize=None)
def _closures():
    """{module: the files it and everything it imports live in}, over what the CLI imports.

    Only modules reachable from `build_campaign` are parsed: tools/ also holds the checks and
    the tests, and parsing those too doubled the cost for modules no step can import."""
    modules = _module_files()
    graph = {}
    todo = ['build_campaign']
    while todo:
        name = todo.pop()
        if name not in graph:
            graph[name] = _imports(modules[name], modules)
            todo.extend(graph[name])

    def closure(name):
        seen, todo = set(), [name]
        while todo:
            current = todo.pop()
            if current not in seen:
                seen.add(current)
                todo.extend(graph[current])
        return frozenset(modules[m] for m in seen)
    return {name: closure(name) for name in graph}


def _rom_input(path):
    import build_scopes
    return any(path == root or path.startswith(root + '/')
               for root in build_scopes.ROM_INPUT_PATHS)


def reach(changed, configs=None):
    """{configuration: [why, ...]} for the configurations `changed` (repo-relative) can move.

    Empty when no change is something the injection reads."""
    import build_campaign
    from inject import steps
    configs = configurations() if configs is None else configs
    closures = _closures()
    injector = closures['build_campaign']
    default, _ = build_campaign.parse_args(['--campaign', CAMPAIGN])
    out = collections.OrderedDict()

    def charge(config, why):
        out.setdefault(config, [])
        if why not in out[config]:
            out[config].append(why)

    for path in changed:
        python = path.endswith('.py')
        if (python and path not in injector) or (not python and not _rom_input(path)):
            continue
        charge('canonical', '%s is read by the injection' % path)
        if path in EVERYWHERE or not python:
            why = ('%s holds every step\'s `when` and `call`' % path if python else
                   '%s is data, and no step declares what it reads' % path)
            for config in configs:
                charge(config, why)
            continue
        for config, switches in configs.items():
            args, _ = build_campaign.parse_args(['--campaign', CAMPAIGN] + switches)
            for step in steps.STEPS:
                if path not in closures[step.fn.__module__]:
                    continue
                if not _runs(step, args):
                    continue
                read = [f for f in step.flags if getattr(args, f) != getattr(default, f)]
                if read:
                    charge(config, '%s -> %s reads %s' % (path, step.name, ', '.join(read)))
                elif not _runs(step, default):
                    charge(config, '%s -> %s runs only here' % (path, step.name))
    order = list(configs)
    return collections.OrderedDict(sorted(out.items(), key=lambda kv: order.index(kv[0])))


def _runs(step, args):
    from inject import steps
    return step.when is None or step.when(steps.FlagView(args, step))


def changed_since(base):
    """Repo-relative paths this branch and its working tree change against `base`."""
    def lines(*cmd):
        return subprocess.run(['git', '-C', REPO] + list(cmd), capture_output=True, text=True,
                              check=True).stdout.split()
    since = lines('merge-base', base, 'HEAD')[0]
    return sorted(set(lines('diff', '--name-only', since))
                  | set(lines('ls-files', '--others', '--exclude-standard')))


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument('--base', default='origin/main',
                    help='what the change is measured against (default origin/main)')
    args = ap.parse_args(argv)
    configs = configurations()
    reached = reach(changed_since(args.base), configs)
    if not reached:
        print('nothing to fingerprint: no change against %s is read by the injection'
              % args.base)
        return 0
    print('fingerprint %d of %d configuration(s):' % (len(reached), len(configs)))
    for config, reasons in reached.items():
        flags = ' '.join(configs[config])
        print('\n  %-20s --flags="%s"' % (config, flags))
        for why in reasons[:3]:
            print('      %s' % why)
        if len(reasons) > 3:
            print('      ... and %d more' % (len(reasons) - 3))
    return 0


if __name__ == '__main__':
    sys.exit(main())
