#!/usr/bin/env python3
"""Tests for check.py's Lua load gate (#236 -> #138).

The gate exists because harness.lua is one ~6,700-line main chunk sitting AT Lua's
ceiling of 200 locals per function. Crossing it is a COMPILE error, so it does not fail
one scenario -- every scenario dies at once, minutes later, inside mGBA. Nothing else
catches it: check_playtest_matrix only parses the file textually for scenario names.

Run: python3 tools/test_check_lua_loads.py
"""
import glob
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import check

HAVE_LUA = shutil.which('lua') is not None


@unittest.skipUnless(HAVE_LUA, 'no lua on PATH')
class LuaCompileError(unittest.TestCase):
    def _write(self, body):
        fd, path = tempfile.mkstemp(suffix='.lua')
        with os.fdopen(fd, 'w') as f:
            f.write(body)
        self.addCleanup(os.unlink, path)
        return path

    def test_a_valid_chunk_reports_no_error(self):
        self.assertIsNone(check.lua_compile_error(self._write('local x = 1\nreturn x\n')))

    def test_a_syntax_error_is_reported(self):
        err = check.lua_compile_error(self._write('local x = = 1\n'))
        self.assertIsNotNone(err)

    def test_crossing_the_200_local_ceiling_is_caught(self):
        """The exact failure mode this gate is for -- valid syntax, dead file."""
        body = ''.join('local v%d = %d\n' % (i, i) for i in range(205))
        err = check.lua_compile_error(self._write(body))
        self.assertIsNotNone(err, '205 top-level locals must not compile')
        self.assertIn('too many local variables', err)

    def test_199_locals_still_compiles(self):
        """Guards the boundary from the other side: the gate must not cry wolf."""
        body = ''.join('local v%d = %d\n' % (i, i) for i in range(199))
        self.assertIsNone(check.lua_compile_error(self._write(body)))

    def test_it_compiles_rather_than_executes(self):
        """The trap that made the first version of this gate useless: `lua -e CODE FILE`
        RUNS the file. A chunk that compiles but explodes on load must still pass --
        harness.lua is exactly that (it needs emulator globals that do not exist here)."""
        path = self._write('error("this chunk must never be executed")\n')
        self.assertIsNone(check.lua_compile_error(path))


@unittest.skipUnless(HAVE_LUA, 'no lua on PATH')
class LocalHeadroom(unittest.TestCase):
    """The 200-local margin must be MEASURED, never written down.

    It was documented as "two free slots" in three places at once (harness.lua, check.py,
    HANDOFF.md) and was wrong in all three within one PR of being written -- #240 spent a
    slot and updated no comment. A number a human maintains by hand about a limit that
    kills every scenario at once is the wrong shape (#241).
    """

    def _write(self, locals_count):
        fd, path = tempfile.mkstemp(suffix='.lua')
        with os.fdopen(fd, 'w') as f:
            f.write(''.join('local v%d = %d\n' % (i, i) for i in range(locals_count)))
        self.addCleanup(os.unlink, path)
        return path

    def test_an_empty_chunk_reports_the_probe_cap(self):
        self.assertEqual(check.lua_local_headroom(self._write(0), probe_max=4), 4)

    def test_a_chunk_one_short_of_the_ceiling_reports_one(self):
        self.assertEqual(check.lua_local_headroom(self._write(199)), 1)

    def test_a_chunk_at_the_ceiling_reports_zero(self):
        self.assertEqual(check.lua_local_headroom(self._write(200)), 0)

    def test_the_gate_fails_when_nothing_is_left(self):
        fail = []
        check.check_lua_local_headroom(fail, paths=(self._write(200),))
        self.assertTrue(fail, 'a chunk with no slots left must fail the build')
        self.assertIn('200-local', fail[0])

    def test_the_live_harness_still_has_room(self):
        fail = []
        check.check_lua_local_headroom(fail)
        self.assertEqual(fail, [])


class LiveRepo(unittest.TestCase):
    def test_every_declared_chunk_exists(self):
        for rel in check.LUA_CHUNKS:
            self.assertTrue(os.path.isfile(os.path.join(check.REPO, rel)),
                            '%s is declared in LUA_CHUNKS but does not exist' % rel)

    def test_harness_is_covered(self):
        self.assertIn('tools/playtest/harness.lua', check.LUA_CHUNKS)

    def test_every_playtest_chunk_is_covered(self):
        """A hand-written list covered 4 of the 9 chunks harness.lua dofiles, so a syntax
        error in recorder.lua or liveness.lua killed every scenario with the gate green --
        the same "list you must remember to update" defect #138 closed for chapters."""
        on_disk = {os.path.relpath(p, check.REPO)
                   for p in glob.glob(os.path.join(check.REPO, 'tools/playtest/*.lua'))}
        self.assertEqual(on_disk - set(check.LUA_CHUNKS) - set(check.GENERATED_LUA), set())

    def test_generated_tables_are_excluded(self):
        """symbols.lua/procscr.lua are gitignored build outputs -- absent in CI, and a
        gate that fails on a missing generated file is a gate nobody can keep green."""
        for name in check.GENERATED_LUA:
            self.assertNotIn(name, check.LUA_CHUNKS)

    def test_the_live_repo_compiles(self):
        fail = []
        check.check_lua_chunks_load(fail)
        self.assertEqual(fail, [])


if __name__ == '__main__':
    unittest.main()
