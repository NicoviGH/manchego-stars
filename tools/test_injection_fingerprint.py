#!/usr/bin/env python3
"""Tests that the refactor gate can actually FAIL (#389).

`injection_fingerprint.py` is the gate every later extraction of `build_campaign.py` is
measured against, so the thing worth pinning is not that it prints IDENTICAL on an unchanged
tree -- a gate that always passes does that too. It is that each way the injector's output can
change produces a difference.

Three of those ways were invisible to the first version, and each has a test here:

  * the injector writes files the decomp GITIGNORES (`MontageMural.gbapal`, the world-map
    `.4bpp`/`.tsa`/`.gbapal` copies). `git status` never lists an ignored path, so a manifest
    built from it alone would call a refactor that stopped writing them byte-identical;
  * `make` writes 3,431 `.lz` and 2,424 `.4bpp` files into those same directories, so the
    ignored sweep has to be keyed on THIS RUN (mtime) rather than on extension, or a build
    between two fingerprints reads as an injection change;
  * the injector DELETES stale artifacts so `make` regenerates them. Nothing about hashing
    written files notices that stopping, so a removed path is recorded as `DELETED` -- and
    weighed only against a run that HAD the file to delete, because `git clean` without `-x`
    never restores one and a straight set difference would fail an unchanged tree.

And the scope the manifest is taken over is DERIVED from `inject/paths.py`, not listed: the
listed form dropped `linker_script_banim.txt`, which lives at the decomp root and which two
injection steps append to.

Plus the `-z` parse: a rename is two records, and slicing `[3:]` off both corrupts the second.

Run: python3 tools/test_injection_fingerprint.py
"""
import json
import os
import sys
import tempfile
import time
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import injection_fingerprint as fp                                   # noqa: E402


class ThePorcelainParse(unittest.TestCase):
    """A rename is TWO -z records and both halves are paths."""

    def _paths(self, records):
        blob = '\0'.join(records) + '\0'
        real = fp.subprocess.run
        try:
            fp.subprocess.run = lambda *a, **k: type('R', (), {'stdout': blob})()
            return fp._status()
        finally:
            fp.subprocess.run = real

    def test_plain_records_keep_their_path(self):
        self.assertEqual(['src/a.c', 'data/b.s'],
                         self._paths([' M src/a.c', '?? data/b.s']))

    def test_a_rename_yields_both_halves_intact(self):
        got = self._paths(['R  src/new.c', 'src/old.c', ' M data/b.s'])
        self.assertEqual(['src/new.c', 'src/old.c', 'data/b.s'], got)

    def test_the_source_half_is_not_sliced(self):
        """The bug this replaces: `[3:]` on the second record ate its first three chars."""
        got = self._paths(['R  src/new.c', 'graphics/map/Tiles.4bpp'])
        self.assertIn('graphics/map/Tiles.4bpp', got)
        self.assertNotIn('phics/map/Tiles.4bpp', got)


class TheIgnoredSweep(unittest.TestCase):
    """What the injector wrote into gitignored paths is output, and must be seen."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.decomp = fp.DECOMP
        fp.DECOMP = self.tmp
        self.addCleanup(setattr, fp, 'DECOMP', self.decomp)

    def _write(self, rel, body, mtime=None):
        path = os.path.join(self.tmp, rel)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, 'wb') as fh:
            fh.write(body)
        if mtime is not None:
            os.utime(path, (mtime, mtime))
        return path

    def _run(self, tracked, ignored, started, ignored_before=frozenset()):
        real_status, real_ignored = fp._status, fp._ignored_paths
        try:
            fp._status = lambda *a: list(tracked)
            fp._ignored_paths = lambda: set(ignored)
            return fp.fingerprint(started, set(ignored_before))
        finally:
            fp._status, fp._ignored_paths = real_status, real_ignored

    def test_an_ignored_file_this_run_wrote_is_in_the_manifest(self):
        now = time.time()
        self._write('graphics/map/MapPaletteSnow.gbapal', b'\x01\x02', mtime=now)
        got = self._run([], ['graphics/map/MapPaletteSnow.gbapal'], now)
        self.assertIn('graphics/map/MapPaletteSnow.gbapal', got)

    def test_a_make_artifact_from_before_the_run_is_not(self):
        """Extension cannot separate these -- `make` writes .4bpp into the same directory."""
        now = time.time()
        self._write('graphics/map/Vanilla.4bpp', b'stale', mtime=now - 3600)
        got = self._run([], ['graphics/map/Vanilla.4bpp'], now)
        self.assertEqual({}, got)

    def test_dropping_an_ignored_write_is_a_DIFFERENCE(self):
        """The regression the gate exists to catch, end to end through the manifest."""
        now = time.time()
        self._write('graphics/map/MapPaletteSnow.gbapal', b'\x01\x02', mtime=now)
        before = self._run([], ['graphics/map/MapPaletteSnow.gbapal'], now)
        # ...refactor stops writing it: the file is stale on disk, not rewritten.
        os.utime(os.path.join(self.tmp, 'graphics/map/MapPaletteSnow.gbapal'),
                 (now - 3600, now - 3600))
        after = self._run([], ['graphics/map/MapPaletteSnow.gbapal'], time.time())
        self.assertNotEqual(before, after)
        self.assertEqual(['graphics/map/MapPaletteSnow.gbapal'],
                         sorted(set(before) - set(after)))

    def test_a_stale_artifact_the_injector_REMOVES_is_recorded(self):
        now = time.time()
        got = self._run([], [], now, ignored_before={'graphics/title/pal.gbapal'})
        self.assertEqual({'graphics/title/pal.gbapal': 'DELETED'}, got)

    def test_a_tracked_file_is_judged_by_CONTENT_not_mtime(self):
        """git status already proved it changed; an old mtime must not exclude it."""
        now = time.time()
        self._write('src/events_udefs.c', b'injected', mtime=now - 3600)
        got = self._run(['src/events_udefs.c'], [], now)
        self.assertIn('src/events_udefs.c', got)


class TheBuildStateItTouches(unittest.TestCase):

    def test_the_rom_stamp_is_stashed_at_every_speed(self):
        """A fingerprint run injects without building, so it must not relabel the ROM.

        `.build-config.json` is what `playtest/matrix.py` reads to know which ROM is in the
        tree. Injection rewrites it, so leaving it in place hands `matrix.check_rom` a stamp
        for a ROM that was never built. It is NOT in CACHES, because `--keep-caches` is a
        speed choice and this is a correctness one -- a run must not be able to opt out.
        """
        self.assertIn('.build-config.json', fp.BUILD_STATE)
        self.assertNotIn('.build-config.json', fp.CACHES)

    def test_keep_caches_does_not_reach_the_rom_stamp(self):
        """--keep-caches is a SPEED choice; the stamp is a correctness one."""
        tmp = tempfile.mkdtemp()
        for name in fp.BUILD_STATE + fp.CACHES:
            with open(os.path.join(tmp, name), 'w') as fh:
                fh.write('{}')
        stashed = []
        saved = (fp.REPO, fp.restore_decomp, fp.inject, fp._ignored_paths, fp.fingerprint)
        try:
            fp.REPO = tmp
            fp.restore_decomp = lambda: None
            fp.inject = lambda: stashed.extend(
                n for n in fp.BUILD_STATE + fp.CACHES
                if not os.path.exists(os.path.join(tmp, n)))
            fp._ignored_paths = lambda: set()
            fp.fingerprint = lambda *a: {}
            fp.build(stash_caches=False)
        finally:
            (fp.REPO, fp.restore_decomp, fp.inject,
             fp._ignored_paths, fp.fingerprint) = saved
        self.assertIn('.build-config.json', stashed)      # hidden while the injector ran
        self.assertNotIn('.injectcache', stashed)         # deliberately left in place

    def test_the_restore_comes_from_HEAD_not_the_index(self):
        with open(os.path.abspath(fp.__file__)) as fh:
            src = fh.read()
        self.assertIn("'checkout', 'HEAD', '--'", src)
        self.assertNotIn("'checkout', '--', '.'", src)


class DeletionIsOnlyComparableWhereBothRunsCouldDelete(unittest.TestCase):
    """The marker must not cry wolf, which is the failure mode that matters most.

    `git clean` without `-x` does not restore an ignored file, so after one run removes a
    stale artifact the next run has nothing to delete. Comparing the two as sets reports
    `only before` on a tree nobody touched -- and a gate that fails on an unchanged tree
    teaches people to stop reading it.
    """

    def _man(self, files, precondition):
        return {'files': dict(files), 'precondition': sorted(precondition)}

    def test_an_unchanged_tree_is_identical_even_though_the_artifact_is_gone(self):
        stale = 'graphics/op_subtitle/OpSubtitle_00.feimg2.bin'
        first = self._man({'src/a.c': 'aa', stale: 'DELETED'}, [stale])
        second = self._man({'src/a.c': 'aa'}, [])       # it was already gone this time
        self.assertEqual(([], [], []), fp.compare(first, second))

    def test_a_real_content_change_still_fails(self):
        first = self._man({'src/a.c': 'aa'}, [])
        second = self._man({'src/a.c': 'bb'}, [])
        self.assertEqual(['src/a.c'], fp.compare(first, second)[2])

    def test_where_both_runs_had_the_file_a_dropped_deletion_IS_caught(self):
        stale = 'graphics/title/pal.gbapal'
        deleted = self._man({stale: 'DELETED'}, [stale])
        kept = self._man({}, [stale])                   # same start, not deleted this time
        self.assertEqual([stale], fp.compare(deleted, kept)[1])

    def test_a_manifest_without_a_precondition_is_refused_not_guessed(self):
        """An older manifest cannot answer the deletion question, and must not pretend to."""
        path = os.path.join(tempfile.mkdtemp(), 'old.json')
        with open(path, 'w') as fh:
            json.dump({'src/a.c': 'aa'}, fh)          # the pre-precondition shape
        with self.assertRaises(SystemExit) as caught:
            fp.load_manifest(path)
        self.assertIn('predates the precondition field', str(caught.exception))

    def test_an_unreadable_manifest_is_refused_BEFORE_the_injection_runs(self):
        """50 seconds is a long time to wait for an error knowable at the start."""
        with open(os.path.abspath(fp.__file__)) as fh:
            src = fh.read()
        self.assertLess(src.index('load_manifest(args.check)'),
                        src.index('manifest = build('))


class TheStash(unittest.TestCase):

    def test_an_interrupted_run_s_backup_is_never_clobbered(self):
        """The backup IS the real file. Overwriting it destroys what it was saving."""
        tmp = tempfile.mkdtemp()
        real, bak = os.path.join(tmp, '.build-config.json'), None
        with open(real, 'w') as fh:
            fh.write('{"rom": "current"}')
        bak = real + '.fingerprint-bak'
        with open(bak, 'w') as fh:
            fh.write('{"rom": "from the killed run"}')
        repo = fp.REPO
        fp.REPO = tmp
        self.addCleanup(setattr, fp, 'REPO', repo)
        with self.assertRaises(SystemExit):
            fp.build()
        with open(bak) as fh:
            self.assertIn('killed run', fh.read())


class TheScopeIsDerivedNotListed(unittest.TestCase):
    """A hand-kept directory list is a blind spot waiting for the next path constant."""

    def test_the_root_level_banim_linker_is_in_scope(self):
        """The regression: it is not under src/data/include/graphics/texts, and IS injected."""
        self.assertIn('linker_script_banim.txt', fp.INJECTED_SCOPE)

    def test_every_decomp_path_constant_is_covered(self):
        from inject import paths
        for name in dir(paths):
            value = getattr(paths, name)
            if not isinstance(value, str) or name in ('REPO', 'DECOMP'):
                continue
            rel = os.path.relpath(value, fp.DECOMP)
            if rel.startswith('..') or rel == '.':
                continue
            self.assertIn(rel.split(os.sep)[0], fp.INJECTED_SCOPE, name)


if __name__ == '__main__':
    unittest.main(verbosity=2)
