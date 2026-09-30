"""The injector's SOURCE, wherever it lives -- the one reader every source-scanning guard uses.

About sixty sites read the injector as TEXT rather than importing it: `check.py`'s lints (the
lean `checks` CI job has no Pillow, so it cannot import build_campaign), the host-slot and
message-literal scans in `hosts.py`, `map_donor`'s layout labels, and the shape tests. Each
used to open `tools/build_campaign.py` by path. #389 decomposes that file into this package,
and a guard that keeps reading the old path does not fail when its target moves -- it goes
quiet: a `NotIn` stops finding anything to object to, a scan finds nothing and reports
nothing wrong. That is ADR 0296's vacuous-pass shape, arriving by code movement.

So the injector is one thing here, however many files it spans: `build_campaign.py` plus
every module under `tools/inject/`. Three views, because the readers want three things:

  * `injector_source()`   -- every file, concatenated. For a pattern that names ONE thing
                             (`RAW_PID_BATTLE_ANIMS = {`, `engine_hooks.X(`, a call text).
  * `def_source(name)`    -- one top-level definition, wherever it lives. For a reader that
                             inspects a single function's body.
  * `defs_source()`       -- every top-level function, and nothing between them. For a regex
                             that walks `^def NAME(.*?(?=^def |\\Z)`: over whole files that
                             lookahead runs the last function of one module on into the next
                             module's docstring and imports, and an import line names exactly
                             the helpers these guards search for.

Stdlib-only, like `hosts.py` and `decomp.py` beside it: `check.py` imports this in CI.
"""
import ast
import functools
import glob
import os

_TOOLS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BUILD_CAMPAIGN_PY = os.path.join(_TOOLS, 'build_campaign.py')
INJECT_DIR = os.path.join(_TOOLS, 'inject')


def injector_files():
    """`build_campaign.py` first, then every module under `tools/inject/`, sorted."""
    modules = sorted(glob.glob(os.path.join(INJECT_DIR, '**', '*.py'), recursive=True))
    return [BUILD_CAMPAIGN_PY] + modules


def _stamp(path):
    stat = os.stat(path)
    return stat.st_mtime_ns, stat.st_size


@functools.lru_cache(maxsize=None)
def _read(path, _stamp):
    with open(path, encoding='utf-8') as f:
        return f.read()


def read(path):
    """One file's text, memoised until it changes on disk."""
    return _read(path, _stamp(path))


@functools.lru_cache(maxsize=None)
def _parse(path, _stamp):
    return ast.parse(read(path), path)


def parse(path):
    return _parse(path, _stamp(path))


@functools.lru_cache(maxsize=None)
def _lines(path, _stamp):
    return read(path).splitlines(keepends=True)


def segment(path, node):
    """A top-level node's full lines. `ast.get_source_segment` re-splits the whole file on
    every call, which over build_campaign's ~400 functions cost two minutes."""
    return ''.join(_lines(path, _stamp(path))[node.lineno - 1:node.end_lineno])


def _stamps():
    return tuple((path, _stamp(path)) for path in injector_files())


def injector_sources():
    """[(path, text)] for every injector file, in `injector_files()` order."""
    return [(path, read(path)) for path in injector_files()]


def injector_source():
    """Every injector file's text, concatenated."""
    return '\n'.join(text for _path, text in injector_sources())


def _top_level_names(node):
    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
        return [node.name]
    if isinstance(node, ast.Assign):
        return [n.id for t in node.targets for n in ast.walk(t) if isinstance(n, ast.Name)]
    if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
        return [node.target.id]
    return []


def top_level_definitions():
    """{name: [(path, node), ...]} for every module-level def, class and assignment."""
    return _definitions(_stamps())


@functools.lru_cache(maxsize=None)
def _definitions(_stamps):
    found = {}
    for path in injector_files():
        for node in parse(path).body:
            for name in _top_level_names(node):
                found.setdefault(name, []).append((path, node))
    return found


def _one(name):
    """The single definition of `name`, or None. Two FILES defining it is a move that left a
    copy behind, so it raises rather than letting whichever file sorts first silently win.
    (Private helpers like `_TOOLS` repeat across modules legitimately; they are only an error
    when someone asks for them by name.)"""
    hits = top_level_definitions().get(name)
    if not hits:
        return None
    paths = sorted({path for path, _node in hits})
    if len(paths) > 1:
        raise ValueError('%s is defined at top level in more than one injector file: %s'
                         % (name, ', '.join(os.path.relpath(p, _TOOLS) for p in paths)))
    return hits[-1]


def defining_file(name):
    """The injector file that defines `name` at top level, or None."""
    hit = _one(name)
    return hit[0] if hit else None


def def_source(name):
    """The source text of one top-level definition, wherever it lives. None when absent."""
    hit = _one(name)
    if hit is None:
        return None
    path, node = hit
    return segment(path, node)


def defs_source():
    """Every top-level FUNCTION's source, joined by blank lines and nothing else."""
    parts = []
    for path in injector_files():
        for node in parse(path).body:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                parts.append(segment(path, node))
    return '\n\n'.join(parts) + '\n'
