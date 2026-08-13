#!/usr/bin/env python3
"""Build-attributed impact scoping for the playtest matrix (#255 phase 2).

Phase 1's verdict cache keys every scenario on `rom_input_hash` -- a digest of everything
the ROM is built FROM. That is sound, and it is also far too coarse: nearly every feature
task touches `build_campaign.py` or campaign data, so nearly every task invalidates all 17
scenarios and the cache stops paying. What we actually want to say is "this edit only
changed ch05, so only ch05's scenarios need re-running".

**The manifest is DERIVED from what the builder did, never hand-declared.** A hand-kept
impact map rots silently and lets real regressions through, which is the exact failure
#255 exists to avoid. So this module watches the decomp tree while the build runs and
records, per injection step, the files that step actually wrote and a digest of their
contents.

Two rules keep it honest, and both are the conservative direction:

  * **A file written by more than one step belongs to EVERY step that wrote it.** Blaming
    the last writer alone is the subtle killer: a shared table written by the portrait pass
    and then again by ch05 would be charged to ch05, and a portrait edit would then move
    only ch05's digest while every global scenario was served a stale PASS.
  * **Unattributable means `global`.** Writes between steps, writes outside the walked
    roots, and any step whose name does not identify exactly one chapter all land in
    `global`, which every scenario depends on. Over-attributing costs a re-run;
    under-attributing costs a green nobody earned.

This is the same shape as `matrix.py`'s `harness_shared`, and for the same reason.
"""
import hashlib
import json
import os
import re

# The decomp subtrees the injectors write into. Build OUTPUTS (.o/.lz/.4bpp) are elsewhere
# and are not sources, so they are not walked. Anything written outside these roots is not
# lost -- `finish(touched=...)` reconciles it into `global`.
SCOPE_ROOTS = ('src', 'data', 'include', 'graphics', 'scripts')

_CHAPTER = re.compile(r'ch\d\d')


def scope_of_step(name):
    """The scope a step's writes belong to, read off the step's own function name.

    `inject_ch05` and `inject_ch05_visit_faces` are ch05's; `inject_portraits` is global.
    A name mentioning TWO chapters (`chain_ch04_to_ch05`) is global rather than a guess at
    which side owns the seam -- picking one would leave the other's scenarios reading a
    digest that never moved.
    """
    if name == 'inject_prologue':
        return 'chapter:prologue'
    chapters = sorted(set(_CHAPTER.findall(name or '')))
    if len(chapters) == 1:
        return 'chapter:' + chapters[0]
    return 'global'


def _digest_file(path):
    try:
        with open(path, 'rb') as fh:
            return hashlib.sha256(fh.read()).hexdigest()[:16]
    except OSError:
        return 'missing'


class BuildScopes(object):
    """Watches a tree across a build and attributes each write to a step.

    Detection is by mtime, snapshotted around every step. `stat` is cheap enough to do this
    ~20 times over the decomp's source roots (measured: 50 ms a pass, ~1 s a build), and
    only the files that actually moved are ever hashed.
    """

    def __init__(self, root, roots=SCOPE_ROOTS, previous=None):
        self.root = root
        self.roots = tuple(roots)
        # scope -> {relpath: digest}. Seeded from the previous build's manifest so a scope
        # starts out owning what it has written before (see `finish`), with digests left
        # None until the scope's own step claims -- WHEN a path is hashed is the whole
        # point, so seeding must happen here and not after every step has run.
        self.scopes = {scope: dict.fromkeys(entry.get('paths', ()))
                       for scope, entry in (previous or {}).items()}
        self._prev = self._snapshot()

    def _snapshot(self):
        seen = {}
        for rel in self.roots:
            base = os.path.join(self.root, rel)
            for dirpath, dirnames, names in os.walk(base):
                dirnames[:] = [d for d in dirnames if not d.startswith('.')]
                for name in names:
                    path = os.path.join(dirpath, name)
                    try:
                        seen[path] = os.stat(path).st_mtime_ns
                    except OSError:
                        pass
        return seen

    def _claim(self, scope):
        """Charge everything written since the last snapshot to `scope`, and fix that
        scope's digests to THIS MOMENT -- the end of the step that just ran.

        The timing is the substance. A chapter scope's answer to "has my content changed"
        must be read before the chapters after it have written anything, or every shared
        whole-campaign table hands it the LAST chapter's bytes and a ch05 edit re-runs ch04,
        ch03, ch02 and ch01. `global` is the exception and is refreshed in `finish` instead:
        it means "the whole build", so its reference point is the end of it, not the middle.
        """
        now = self._snapshot()
        bucket = self.scopes.setdefault(scope, {})
        for path, mtime in now.items():
            if self._prev.get(path) != mtime:
                bucket.setdefault(os.path.relpath(path, self.root))
        if not bucket:
            del self.scopes[scope]
        elif scope != 'global':
            self._freeze(bucket)
        self._prev = now

    def _freeze(self, bucket):
        """Hash every path a scope owns as the tree stands right now."""
        for rel in bucket:
            bucket[rel] = _digest_file(os.path.join(self.root, rel))

    def run(self, fn, *args, **kwargs):
        """Run one injection step and charge its writes to the scope its name implies.

        `name` overrides the function's `__name__` (only tests need that; the build passes
        real functions so the scope is derived, not typed). Writes made since the previous
        step -- loose statements in `main()` -- are charged to `global` first.
        """
        name = kwargs.pop('name', None) or getattr(fn, '__name__', '')
        self._claim('global')
        try:
            return fn(*args, **kwargs)
        finally:
            # A build that dies half-way must still account for what it wrote, or those
            # files look unattributed to the next pass.
            self._claim(scope_of_step(name))

    def finish(self, touched=()):
        """Close the manifest: {scope: {'paths': [...], 'digest': ...}}.

        `touched` is the build's own footprint (git's view of the decomp), used as the
        SAFETY NET: any path in it that no step claimed is charged to `global`. That is
        what lets the per-step walk cover a few named roots instead of the whole tree
        without opening an optimistic gap.

        OWNERSHIP IS STICKY (seeded from the previous manifest in `__init__`): a scope
        keeps a file it has written before, even on a build that did not rewrite it. That
        is not tidiness, it is the difference between the feature working and not. Whether
        a build rewrites a given file depends on what was built BEFORE it -- the matrix
        alternates ROM configurations, and the mtime rewind hands the next build a
        different starting point -- so without this the path SET churns, the digest moves
        with no content behind it, and because every scenario depends on `global`,
        everything re-runs.

        Inherited paths are still hashed from the tree rather than copied forward, so
        sticky ownership never means a stale digest -- but they are hashed at the owning
        step's `_claim`, not here. Hashing them here was the bug: it read every scope's
        files after ALL steps had run, so a late chapter's writes to a shared table leaked
        into every earlier chapter's digest. A scope whose step did not run at all this
        build has nothing to fix its digests to and is filled in below, as it stands now.
        """
        self._claim('global')
        self._freeze(self.scopes.get('global', {}))
        claimed = {rel for bucket in self.scopes.values() for rel in bucket}
        stragglers = {rel: _digest_file(os.path.join(self.root, rel))
                      for rel in touched if rel not in claimed}
        if stragglers:
            self.scopes.setdefault('global', {}).update(stragglers)
        for bucket in self.scopes.values():
            for rel, digest in bucket.items():
                if digest is None:
                    bucket[rel] = _digest_file(os.path.join(self.root, rel))
        manifest = {}
        for scope, bucket in self.scopes.items():
            h = hashlib.sha256()
            for rel in sorted(bucket):
                h.update(('%s\0%s\0' % (rel, bucket[rel])).encode())
            manifest[scope] = {'paths': sorted(bucket), 'digest': h.hexdigest()[:32]}
        return manifest

    def write_manifest(self, path, touched=()):
        manifest = self.finish(touched=touched)
        with open(path, 'w') as fh:
            json.dump(manifest, fh, indent=2, sort_keys=True)
        return manifest


def load_manifest(path):
    """The manifest a build left behind, or None if there isn't a readable one.

    None means "we do not know what that build wrote", and every caller must treat it as a
    reason to fall back to the whole-ROM key -- an empty dict would read as "it wrote
    nothing", which is the optimistic answer to the same question.
    """
    try:
        with open(path) as fh:
            manifest = json.load(fh)
    except (OSError, ValueError):
        return None
    return manifest if isinstance(manifest, dict) else None
