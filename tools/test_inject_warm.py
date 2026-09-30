#!/usr/bin/env python3
"""Tests for tools/inject/warm.py.

Run:  python3 tools/test_inject_warm.py
"""
import hashlib
import os
import re
import shutil
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from inject.namespace import stubbed
import inject.decomp
import inject.warm
import platform
from inject import source as injector  # the injector's source, every file of it (#389)


class IdempotentInjectionMtimes(unittest.TestCase):
    """The warm-rebuild speed-up: rewind mtimes only for byte-identical files, so
    `make` skips unchanged targets while the ROM stays bit-identical (#build-speed)."""

    def _tmpfile(self, data=b'hello'):
        import tempfile
        fd, path = tempfile.mkstemp()
        self.addCleanup(lambda: os.path.exists(path) and os.remove(path))
        with os.fdopen(fd, 'wb') as f:
            f.write(data)
        return path

    def test_snapshot_records_mtime_and_hash(self):
        p = self._tmpfile(b'abc')
        snap = inject.warm._snapshot_mtimes([p])
        self.assertIn(p, snap)
        mtime_ns, digest = snap[p]
        self.assertEqual(mtime_ns, os.stat(p).st_mtime_ns)
        self.assertEqual(digest, hashlib.sha1(b'abc').digest())

    def test_snapshot_skips_missing_files(self):
        # A path that does not exist is simply not tracked (no raise).
        self.assertEqual(inject.warm._snapshot_mtimes(['/no/such/file/xyz']), {})

    def test_rewinds_mtime_when_content_unchanged(self):
        # Rewriting a file with IDENTICAL bytes normally bumps mtime; the rewind
        # must restore the snapshot mtime so make treats the target as up to date.
        p = self._tmpfile(b'same-bytes')
        snap = inject.warm._snapshot_mtimes([p])
        os.utime(p, ns=(snap[p][0] + 5_000_000_000, snap[p][0] + 5_000_000_000))
        with open(p, 'wb') as f:          # rewrite identical content (new mtime)
            f.write(b'same-bytes')
        self.assertNotEqual(os.stat(p).st_mtime_ns, snap[p][0])
        n = inject.warm._rewind_unchanged_mtimes(snap)
        self.assertEqual(n, 1)
        self.assertEqual(os.stat(p).st_mtime_ns, snap[p][0])

    def test_does_not_rewind_when_content_changed(self):
        # A genuinely changed file KEEPS its fresh mtime, so make rebuilds it.
        p = self._tmpfile(b'original')
        snap = inject.warm._snapshot_mtimes([p])
        with open(p, 'wb') as f:
            f.write(b'CHANGED')
        changed_mtime = os.stat(p).st_mtime_ns
        n = inject.warm._rewind_unchanged_mtimes(snap)
        self.assertEqual(n, 0)
        self.assertEqual(os.stat(p).st_mtime_ns, changed_mtime)  # not rewound

    def test_footprint_lists_modified_and_untracked_sources(self):
        # The footprint comes from `git status` on the decomp: an mtime rewind is only
        # meaningful for files git already sees as part of the injection (source, not
        # the .gitignored build outputs). Just assert it returns decomp-rooted paths.
        for p in inject.warm._decomp_footprint():
            self.assertTrue(p.startswith(inject.decomp.DECOMP), p)


class DecompShebangsSurviveASubmoduleCheckout(unittest.TestCase):
    """The decomp ships Linux `#!/bin/python3` shebangs that do not exist on macOS, and ANY
    `git checkout` inside the submodule reverts the fix -- so the next build dies on
    `bad interpreter`, minutes in, from a Makefile rule that looks unrelated.

    tools/build.sh handled it, but CLAUDE.md documents plain `make`, which bypassed the
    wrapper -- so the failure kept recurring. Every build runs build_campaign, so the fix
    lives there now and this pins it.
    """

    def test_the_build_normalises_shebangs_before_injecting(self):
        body = injector.def_source('main')
        self.assertIn('normalise_decomp_shebangs(', body,
                      'every build must re-apply the fix, not just tools/build.sh')

    def test_it_rewrites_only_the_linux_shebang_and_is_idempotent(self):
        tmp = tempfile.mkdtemp()
        try:
            scripts = os.path.join(tmp, 'scripts')
            os.makedirs(scripts)
            broken = os.path.join(scripts, 'gen.py')
            fine = os.path.join(scripts, 'ok.py')
            other = os.path.join(scripts, 'nohash.py')
            with open(broken, 'w') as f:
                f.write('#!/bin/python3\nprint(1)\n')
            with open(fine, 'w') as f:
                f.write('#!/usr/bin/env python3\nprint(2)\n')
            with open(other, 'w') as f:
                f.write('print(3)\n')
            with stubbed('DECOMP', tmp), \
                    mock.patch.object(platform, 'system', lambda: 'Darwin'):
                self.assertEqual(inject.warm.normalise_decomp_shebangs(), 1)
                self.assertEqual(inject.warm.normalise_decomp_shebangs(), 0, 'must be idempotent')
            self.assertTrue(open(broken).read().startswith('#!/usr/bin/env python3'))
            self.assertEqual(open(broken).read().splitlines()[1], 'print(1)',
                             'only the shebang line may change')
            self.assertTrue(open(fine).read().startswith('#!/usr/bin/env python3'))
            self.assertEqual(open(other).read(), 'print(3)\n')
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_it_is_a_no_op_off_macos(self):
        with mock.patch.object(platform, 'system', lambda: 'Linux'):
            self.assertEqual(inject.warm.normalise_decomp_shebangs(), 0)


if __name__ == '__main__':
    unittest.main()
