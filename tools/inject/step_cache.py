"""Restore an injection step's output instead of recomputing it (#309).

A `make` costs ~50s, and **26 of them are battle-anim injection** (`inject_enemy_class_battle_anims`
17.1s + `inject_battle_anims` 8.5s, measured 2026-08-23) -- two steps that no boot flag reaches,
producing byte-identical data for all twelve `rom_configs`. The matrix builds five configurations
for one gate, so those 26 seconds are paid five times over for nothing.

This is the same bargain the ROM cache and the verdict cache already make one level up: when the
inputs have not moved, restore what was produced last time. Here the unit is one injection STEP.

WHAT MAKES A RESTORE SOUND. A step's output is a function of (a) the inputs in the cache key --
campaign data, the injector's own source, the decomp revision -- and (b) the state of the tree
when it runs, which earlier steps produced from those same inputs. Equal key therefore implies
equal output. The key is the argument; the `pre` map below is the CHECK on that argument, and it
exists because a key that silently misses an input is exactly the failure this repo cannot see:
the ROM would be wrong and everything would still be green.

`pre` records, for every file the step wrote, the digest that file had BEFORE it ran, and `post`
what the step left there. A restore requires every one of those files to be sitting at one of
those two digests right now: at `pre`, meaning this build has reached exactly the state the
recorded run started from, or at `post`, meaning an identical run already left its output there
and the tree was never rewound. Restoring writes the same bytes either way.

Anything else is a MISS -- and the case that matters is an earlier step writing something ELSE
into a file this step overwrites (`src/data_characters.c` and `src/data_classes.c` are both
written by earlier passes), which is caught even when the key says hit. Both digests are needed
because a step may APPEND: for those, `pre` is what makes "already applied" distinguishable from
"not yet applied", and getting that backwards would double the rows.

Which paths to hash is DERIVED, never declared: they are the paths the step wrote last time. The
first run for a step has no such list, so it hashes `roots` outright to bootstrap one. `roots` is
therefore a cost hint, not a correctness boundary -- a write outside it is recorded with an
`unknown` pre-state, which forces a miss on the next build and fixes itself on the one after.
"""
import hashlib
import json
import os
import shutil
import time

# The decomp subtrees a step can write into. Same roots as build_scopes, and for the same
# reason: build OUTPUTS live elsewhere and are not sources.
SCOPE_ROOTS = ('src', 'data', 'include', 'graphics', 'scripts')

MISSING = 'missing'     # the file did not exist before the step ran
UNKNOWN = 'unknown'     # it did, but nothing had told us to hash it -- never restorable


def digest_file(path):
    try:
        with open(path, 'rb') as fh:
            return hashlib.sha256(fh.read()).hexdigest()[:16]
    except OSError:
        return MISSING


def snapshot(root, roots=SCOPE_ROOTS):
    """{abs path: mtime_ns} over the watched roots -- how a write is detected.

    Same mechanism as `build_scopes.BuildScopes`: `stat` is cheap enough to do this around
    every step, and only files that actually moved are ever hashed.
    """
    seen = {}
    for rel in roots:
        base = os.path.join(root, rel)
        for dirpath, dirnames, names in os.walk(base):
            dirnames[:] = [d for d in dirnames if not d.startswith('.')]
            for name in names:
                path = os.path.join(dirpath, name)
                try:
                    seen[path] = os.stat(path).st_mtime_ns
                except OSError:
                    pass
    return seen


class Outcome(object):
    """What one `run` did, so the build log can say whether the cache is working."""

    def __init__(self, step, hit, paths, seconds, recorded_seconds):
        self.step = step
        self.hit = hit
        self.paths = list(paths)
        self.seconds = seconds                    # what this call cost
        self.recorded_seconds = recorded_seconds  # what the cached run cost when it ran

    @property
    def saved(self):
        """Seconds this restore bought. Zero on a miss -- a miss saves nothing."""
        return self.recorded_seconds if self.hit else 0.0

    def __repr__(self):
        return '<Outcome %s %s %.1fs>' % (self.step, 'hit' if self.hit else 'miss', self.seconds)


def disabled():
    """A cache that always runs the step. `NO_INJECT_CACHE=1` resolves to one of these so the
    build has a single call shape and no branch at the call site."""
    return NullCache()


class NullCache(object):

    def __init__(self, verbose=False):
        self.verbose = verbose

    def run(self, fn, *args, **kwargs):
        step = kwargs.pop('name', None) or getattr(fn, '__name__', '')
        started = time.time()
        fn(*args, **kwargs)
        return Outcome(step, False, (), time.time() - started, 0.0)


class StepCache(object):
    """Cache of what injection steps wrote, keyed on everything they read."""

    def __init__(self, root, store, key, roots=SCOPE_ROOTS, scope_roots=None, verbose=False):
        self.root = root
        self.store = store
        self.key = key
        self.roots = tuple(roots)                                  # bootstrap hashing only
        self.scope_roots = tuple(scope_roots or SCOPE_ROOTS)       # write detection
        # A cache nobody can see working is a cache nobody trusts, and the number it prints is
        # what the next measurement argues with. The REPORT lives here rather than at the call
        # site so a cached step reads as a plain call to itself -- which is also what keeps it
        # visible to check.py's injection-order gate.
        self.verbose = verbose

    # -- entries ------------------------------------------------------------

    def _entry_dir(self, step):
        return os.path.join(self.store, step)

    def _meta_path(self, step):
        return os.path.join(self._entry_dir(step), 'entry.json')

    def _load(self, step):
        try:
            with open(self._meta_path(step)) as fh:
                return json.load(fh)
        except (OSError, ValueError):
            return None

    # -- the check ----------------------------------------------------------

    def _hash_paths(self, rels):
        return dict((rel, digest_file(os.path.join(self.root, rel))) for rel in rels)

    def _restorable(self, entry, now):
        """A hit needs the same key AND every recorded file sitting at its `pre` or `post`
        digest -- the two states from which restoring writes the right bytes."""
        if not entry or entry.get('key') != self.key:
            return False
        pre, post = entry.get('pre') or {}, entry.get('post') or {}
        if not pre or UNKNOWN in pre.values():
            return False
        return all(now.get(rel) in (was, post.get(rel)) for rel, was in pre.items())

    # -- running ------------------------------------------------------------

    def run(self, fn, *args, **kwargs):
        """Restore `fn`'s recorded output, or run it and record what it wrote."""
        step = kwargs.pop('name', None) or getattr(fn, '__name__', '')
        entry = self._load(step)
        started = time.time()
        pre_now = self._hash_paths(entry.get('paths', ())) if entry else self._bootstrap()

        if self._restorable(entry, pre_now):
            self._restore(step, entry)
            outcome = Outcome(step, True, entry['paths'], time.time() - started,
                              entry.get('seconds', 0.0))
            if self.verbose:
                print('  %s: restored from cache -- %d files, %.1fs saved'
                      % (outcome.step, len(outcome.paths), outcome.saved))
            return outcome

        before = snapshot(self.root, self.scope_roots)
        ran = time.time()
        fn(*args, **kwargs)
        # A step that raises records NOTHING: half a step's writes stored as a whole step is a
        # poisoned entry that would restore forever.
        seconds = time.time() - ran
        after = snapshot(self.root, self.scope_roots)
        moved = sorted(os.path.relpath(path, self.root) for path, mtime in after.items()
                       if before.get(path) != mtime)
        self._record(step, moved, pre_now, before, seconds)
        return Outcome(step, False, moved, time.time() - started, seconds)

    def _bootstrap(self):
        """No entry yet, so nothing knows which paths to hash: hash `roots` outright, once."""
        return dict((os.path.relpath(path, self.root), digest_file(path))
                    for path in snapshot(self.root, self.roots))

    def _record(self, step, moved, pre_now, before, seconds):
        entry_dir = self._entry_dir(step)
        shutil.rmtree(entry_dir, ignore_errors=True)
        pre = {}
        for rel in moved:
            if rel in pre_now:
                pre[rel] = pre_now[rel]
            elif os.path.join(self.root, rel) not in before:
                pre[rel] = MISSING          # the step created it; absence is a state
            else:
                pre[rel] = UNKNOWN          # it existed and went unhashed -> never restorable
            src = os.path.join(self.root, rel)
            dst = os.path.join(entry_dir, 'files', rel)
            if not os.path.isdir(os.path.dirname(dst)):
                os.makedirs(os.path.dirname(dst))
            shutil.copyfile(src, dst)
        post = self._hash_paths(moved)
        with open(self._meta_path(step), 'w') as fh:
            json.dump({'key': self.key, 'step': step, 'paths': moved, 'pre': pre,
                       'post': post, 'seconds': round(seconds, 2)}, fh, indent=1)

    def _restore(self, step, entry):
        files = os.path.join(self._entry_dir(step), 'files')
        for rel in entry['paths']:
            dst = os.path.join(self.root, rel)
            if not os.path.isdir(os.path.dirname(dst)):
                os.makedirs(os.path.dirname(dst))
            shutil.copyfile(os.path.join(files, rel), dst)
