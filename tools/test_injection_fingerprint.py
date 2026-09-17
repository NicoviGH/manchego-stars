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
    written files notices that stopping, so a removed path is recorded as `DELETED`.

Plus the `-z` parse: a rename is two records, and slicing `[3:]` off both corrupts the second.

Run: python3 tools/test_injection_fingerprint.py
"""
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

    def test_no_longer_removing_it_is_a_difference(self):
        now = time.time()
        removed = self._run([], [], now, ignored_before={'graphics/title/pal.gbapal'})
        # ...refactor stops deleting it: it survives the run, untouched and old.
        self._write('graphics/title/pal.gbapal', b'old', mtime=now - 3600)
        kept = self._run([], ['graphics/title/pal.gbapal'], time.time(),
                         ignored_before={'graphics/title/pal.gbapal'})
        self.assertNotEqual(removed, kept)

    def test_a_tracked_file_is_judged_by_CONTENT_not_mtime(self):
        """git status already proved it changed; an old mtime must not exclude it."""
        now = time.time()
        self._write('src/events_udefs.c', b'injected', mtime=now - 3600)
        got = self._run(['src/events_udefs.c'], [], now)
        self.assertIn('src/events_udefs.c', got)


class TheBuildStateItTouches(unittest.TestCase):

    def test_the_rom_stamp_is_stashed_with_the_caches(self):
        """A fingerprint run injects without building, so it must not relabel the ROM.

        `.build-config.json` is what `playtest/matrix.py` reads to know which ROM is in the
        tree. Injection rewrites it, so leaving it in place hands `matrix.check_rom` a stamp
        for a ROM that was never built.
        """
        self.assertIn('.build-config.json', fp.CACHES)

    def test_the_restore_comes_from_HEAD_not_the_index(self):
        with open(os.path.abspath(fp.__file__)) as fh:
            src = fh.read()
        self.assertIn("'checkout', 'HEAD', '--'", src)
        self.assertNotIn("'checkout', '--', '.'", src)


if __name__ == '__main__':
    unittest.main(verbosity=2)
