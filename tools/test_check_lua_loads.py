#!/usr/bin/env python3
"""Tests for check.py's Lua load gate (#236 -> #138).

The gate exists because harness.lua is one ~6,700-line main chunk sitting AT Lua's
ceiling of 200 locals per function. Crossing it is a COMPILE error, so it does not fail
one scenario -- every scenario dies at once, minutes later, inside mGBA. Nothing else
catches it: check_playtest_matrix only parses the file textually for scenario names.

Run: python3 tools/test_check_lua_loads.py
"""
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


class LiveRepo(unittest.TestCase):
    def test_every_declared_chunk_exists(self):
        for rel in check.LUA_CHUNKS:
            self.assertTrue(os.path.isfile(os.path.join(check.REPO, rel)),
                            '%s is declared in LUA_CHUNKS but does not exist' % rel)

    def test_harness_is_covered(self):
        self.assertIn('tools/playtest/harness.lua', check.LUA_CHUNKS)

    def test_the_live_repo_compiles(self):
        fail = []
        check.check_lua_chunks_load(fail)
        self.assertEqual(fail, [])


if __name__ == '__main__':
    unittest.main()
