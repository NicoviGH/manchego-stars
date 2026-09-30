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


class RewindAgainstWhatMakeCompiled(unittest.TestCase):
    """#416: the rewind's baseline is what `make` last COMPILED, not what the injector last
    WROTE. An injector-only run between two builds (the fingerprint gate, a manual
    build_campaign.py, a config switch) used to become the baseline, so the next `make` saw
    every re-emitted file as newer than its object and rebuilt ~1,500 assets and every C file."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.elf = os.path.join(self.tmp, 'fireemblem8.elf')
        self._write(self.elf, b'elf')
        # Outside the decomp, as in the repo: the records are not decomp writes.
        state = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, state, True)
        self.compiled = os.path.join(state, 'compiled')
        self.injected = os.path.join(state, 'injected.json')
        for name, value in (('DECOMP', self.tmp), ('COMPILED_DIR', self.compiled),
                            ('INJECTED_PATHS', self.injected)):
            ctx = stubbed(name, value)
            ctx.__enter__()
            self.addCleanup(ctx.__exit__, None, None, None)
        self.tracked = []
        patcher = mock.patch.object(inject.warm, '_tracked', lambda: list(self.tracked))
        patcher.start()
        self.addCleanup(patcher.stop)

    def _write(self, path, data, mtime_ns=None):
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, 'wb') as f:
            f.write(data)
        if mtime_ns is not None:
            os.utime(path, ns=(mtime_ns, mtime_ns))
        return path

    def _compile(self, paths):
        # The Makefile's bracket: forget, compile (a no-op here), record.
        inject.warm.record_injected(paths)
        inject.warm.forget_compiled()
        inject.warm.record_compiled()

    def test_an_injector_only_run_does_not_become_the_baseline(self):
        src = self._write(os.path.join(self.tmp, 'src', 'a.c'), b'A', mtime_ns=10**18)
        self._compile([src])
        # The fingerprint gate: checkout + re-inject, no compile. Same bytes, fresh mtime.
        self._write(src, b'A', mtime_ns=2 * 10**18)
        snap = inject.warm._snapshot_mtimes([src])
        # The next build re-emits the same bytes again.
        self._write(src, b'A', mtime_ns=3 * 10**18)
        inject.warm._rewind_unchanged_mtimes(snap, inject.warm.load_compiled())
        self.assertEqual(os.stat(src).st_mtime_ns, 10**18,
                         'rewound to the injector-only run, not to what make compiled')

    def test_changed_content_is_never_rewound_to_the_compiled_mtime(self):
        src = self._write(os.path.join(self.tmp, 'src', 'a.c'), b'A', mtime_ns=10**18)
        self._compile([src])
        self._write(src, b'B', mtime_ns=3 * 10**18)
        inject.warm._rewind_unchanged_mtimes({}, inject.warm.load_compiled())
        self.assertEqual(os.stat(src).st_mtime_ns, 3 * 10**18)

    def test_a_compile_nobody_recorded_voids_the_manifest(self):
        # A bare `make -C fireemblem8u` that rebuilt f.o from other bytes and died before
        # relinking: trusting the record would rewind f and hide the stale object (review).
        src = self._write(os.path.join(self.tmp, 'src', 'a.c'), b'A', mtime_ns=10**18)
        self._compile([src])
        self._write(os.path.join(self.tmp, 'src', 'a.o'), b'from B', mtime_ns=4 * 10**18)
        self.assertEqual(inject.warm.load_compiled(), {})

    def test_injector_only_runs_do_not_void_the_manifest(self):
        # What an injector-only run writes (here a file the compile never saw) is its own,
        # so it must not read as a compile behind the Makefile's back.
        src = self._write(os.path.join(self.tmp, 'src', 'a.c'), b'A', mtime_ns=10**18)
        self._compile([src])
        other = self._write(os.path.join(self.tmp, 'graphics', 'ch05.png'), b'x',
                            mtime_ns=4 * 10**18)
        inject.warm.record_injected([other])
        inject.warm.record_injected([])        # a second run must not drop the first's
        self.assertIn(src, inject.warm.load_compiled())

    def test_a_compile_in_flight_leaves_no_manifest(self):
        # The Makefile forgets the manifest before compiling and records it only after a
        # successful compile, so a failed one leaves objects the manifest cannot describe.
        src = self._write(os.path.join(self.tmp, 'src', 'a.c'), b'A')
        self._compile([src])
        inject.warm.forget_compiled()
        self.assertEqual(inject.warm.load_compiled(), {})

    def test_it_falls_back_to_the_previous_injection(self):
        src = self._write(os.path.join(self.tmp, 'src', 'a.c'), b'A', mtime_ns=2 * 10**18)
        snap = inject.warm._snapshot_mtimes([src])
        self._write(src, b'A', mtime_ns=3 * 10**18)
        self.assertEqual(inject.warm._rewind_unchanged_mtimes(snap, {}), 1)
        self.assertEqual(os.stat(src).st_mtime_ns, 2 * 10**18)

    def test_the_record_covers_tracked_files_the_compile_regenerated(self):
        # include/constants/msg.h is tracked AND rewritten by the compile (textprocess). A
        # later `git checkout HEAD -- .` rewrites it -- same bytes, fresh mtime -- and 16 C
        # files recompiled for nothing.
        header = self._write(os.path.join(self.tmp, 'include', 'msg.h'), b'h', mtime_ns=10**18)
        untouched = self._write(os.path.join(self.tmp, 'include', 'x.h'), b'x', mtime_ns=10**18)
        inject.warm.record_injected([])
        inject.warm.forget_compiled(now_ns=2 * 10**18)
        self._write(header, b'h', mtime_ns=3 * 10**18)       # the compile regenerates it
        self.tracked = [header, untouched]
        inject.warm.record_compiled()
        self.assertEqual(set(inject.warm.load_compiled()), {header})

    def test_the_record_carries_forward_what_an_earlier_compile_regenerated(self):
        # msg.h is regenerated only when the texts change, so the compile that wrote it is
        # rarely the last one -- and a record of only the LAST compile's writes dropped it.
        header = self._write(os.path.join(self.tmp, 'include', 'msg.h'), b'h', mtime_ns=10**18)
        self.tracked = [header]
        inject.warm.record_injected([])
        inject.warm.forget_compiled(now_ns=10**18)
        inject.warm.record_compiled()                      # the compile that regenerated it
        self._compile([])                                  # a later one that did not
        self.assertIn(header, inject.warm.load_compiled())

    def test_a_checkout_that_reverts_a_compile_output_is_undone(self):
        # msg.h is textprocess's SIDE output, and ours differs from HEAD. A `git checkout
        # HEAD -- .` reverts it; the rewind then (rightly) keeps texts.txt older than
        # msg_data.c, so make never reruns textprocess and 16 files compile against the
        # VANILLA header. The rewind must put back what the compile wrote.
        header = self._write(os.path.join(self.tmp, 'include', 'msg.h'), b'vanilla',
                             mtime_ns=10**18)
        self.tracked = [header]
        inject.warm.record_injected([])
        inject.warm.forget_compiled(now_ns=2 * 10**18)
        self._write(header, b'ours', mtime_ns=3 * 10**18)    # the compile regenerates it
        inject.warm.record_compiled()
        self._write(header, b'vanilla', mtime_ns=4 * 10**18)  # the checkout reverts it
        inject.warm._rewind_unchanged_mtimes({}, inject.warm.load_compiled())
        with open(header, 'rb') as f:
            self.assertEqual(f.read(), b'ours')
        self.assertEqual(os.stat(header).st_mtime_ns, 3 * 10**18)

    def test_an_injected_file_is_never_restored_from_the_record(self):
        # Only what the COMPILE wrote is put back; the injector owns its own files.
        src = self._write(os.path.join(self.tmp, 'src', 'a.c'), b'A', mtime_ns=10**18)
        self.tracked = [src]
        self._compile([src])
        self._write(src, b'B', mtime_ns=4 * 10**18)
        inject.warm._rewind_unchanged_mtimes({}, inject.warm.load_compiled())
        with open(src, 'rb') as f:
            self.assertEqual(f.read(), b'B')

    def test_what_the_injector_wrote_includes_files_git_never_lists(self):
        # The map tilesets are copied into gitignored .4bpp files: `git status` never lists
        # them, so a git-derived footprint re-converted all four on every warm build.
        old = self._write(os.path.join(self.tmp, 'graphics', 'old.png'), b'o', mtime_ns=10**18)
        t0 = 2 * 10**18
        new = self._write(os.path.join(self.tmp, 'graphics', 'map', 'ObjectTypeSnow.4bpp'),
                          b'n', mtime_ns=3 * 10**18)
        git = self._write(os.path.join(self.tmp, '.git', 'index'), b'i', mtime_ns=3 * 10**18)
        written = inject.warm._written_since(t0)
        self.assertIn(new, written)
        self.assertNotIn(old, written)
        self.assertNotIn(git, written)

    def test_the_makefile_brackets_the_compile(self):
        with open(os.path.join(inject.decomp.REPO, 'Makefile'), encoding='utf-8') as f:
            recipe = f.read().split('\nfireemblem8.gba:\n', 1)[1].split('\n\n', 1)[0]
        lines = [l.strip() for l in recipe.splitlines()]
        compile_at = next(i for i, l in enumerate(lines) if l.startswith('$(MAKE) -C fireemblem8u'))
        self.assertTrue(any('compiled_manifest.py forget' in l for l in lines[:compile_at]),
                        'the manifest must be forgotten BEFORE the compile')
        self.assertTrue(any('compiled_manifest.py record' in l for l in lines[compile_at + 1:]),
                        'and recorded only AFTER it succeeds')


if __name__ == '__main__':
    unittest.main()
