#!/usr/bin/env python3
"""Tests for check.py's Lua local-headroom measurement (#327).

The measurement is the thing everything else in #327 rests on, and it was WRONG for every
chunk that ends in `return M` -- which is every module. It appended probe locals to the end
of the file, and in Lua `return` must be the last statement in a block, so the probe was an
instant syntax error and the chunk reported 0 free. Not "no room": a broken measurement.

That mattered because it only ever ran against `harness.lua`, which happens not to end in a
`return`. Redirecting growth into modules without fixing this would move every local into a
file whose ceiling nobody can measure.

Run: python3 tools/test_check_lua_headroom.py
"""
import os
import shutil
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import check                                            # noqa: E402


def write(body):
    d = tempfile.mkdtemp()
    p = os.path.join(d, 'chunk.lua')
    with open(p, 'w', encoding='utf-8') as fh:
        fh.write(body)
    return p


class TestHeadroomMeasurement(unittest.TestCase):
    def setUp(self):
        self.dirs = []

    def tearDown(self):
        for p in self.dirs:
            shutil.rmtree(os.path.dirname(p), ignore_errors=True)

    def chunk(self, body):
        p = write(body)
        self.dirs.append(p)
        return p

    def test_an_empty_chunk_has_room(self):
        self.assertEqual(check.lua_local_headroom(self.chunk('local a = 1\n'), probe_max=4), 4)

    def test_a_module_ending_in_return_is_measured_not_reported_as_zero(self):
        """The bug. `return M` is the last statement, so an appended local is a syntax
        error and the old probe read that as 'no slots left'."""
        p = self.chunk('local M = {}\nM.x = 1\nreturn M\n')
        self.assertEqual(check.lua_local_headroom(p, probe_max=4), 4)

    def test_a_return_with_a_trailing_comment_and_blank_lines_still_measures(self):
        p = self.chunk('local M = {}\nreturn M   -- the module table\n\n')
        self.assertEqual(check.lua_local_headroom(p, probe_max=4), 4)

    def test_a_chunk_at_the_ceiling_reports_zero(self):
        body = ''.join('local v%d = %d\n' % (i, i) for i in range(200))
        self.assertEqual(check.lua_local_headroom(self.chunk(body), probe_max=4), 0)

    def test_a_module_at_the_ceiling_reports_zero_too(self):
        body = ''.join('local v%d = %d\n' % (i, i) for i in range(200)) + 'return v0\n'
        self.assertEqual(check.lua_local_headroom(self.chunk(body), probe_max=4), 0)

    def test_one_slot_short_of_the_ceiling_reports_one(self):
        body = ''.join('local v%d = %d\n' % (i, i) for i in range(199)) + 'return v0\n'
        self.assertEqual(check.lua_local_headroom(self.chunk(body), probe_max=4), 1)

    def test_a_syntactically_broken_chunk_raises_rather_than_reporting_zero(self):
        """A file that does not compile at all must not be reported as 'full'. Zero is a
        build failure with a specific fix attached, and it would be the wrong one."""
        with self.assertRaises(check.LuaChunkError):
            check.lua_local_headroom(self.chunk('local M = {\n'), probe_max=2)


class TestTheCounterAgreesWithTheProber(unittest.TestCase):
    """Two independent mechanisms measure the same ceiling, so they must agree.

    The counter reads the source; the prober asks the Lua compiler. Neither is checkable on
    its own -- and the counter WAS wrong by one when written, because `\\s` matched a newline
    and merged `local controllerFault` with the `local function log` under it. The ratchet
    runs on the counter, so a quiet off-by-one there loosens the ratchet by one every time
    somebody re-measures.
    """

    def test_counted_plus_free_is_exactly_the_lua_ceiling(self):
        if shutil.which('lua') is None:
            self.skipTest('no lua on PATH')
        path = os.path.join(check.REPO, 'tools/playtest/harness.lua')
        counted = check.lua_top_level_locals(path)
        free = check.lua_local_headroom(path, probe_max=8)
        self.assertLess(free, 8, 'probe capped out; this cross-check needs a real number')
        self.assertEqual(counted + free, 200,
                         'the source counter and the compiler disagree about harness.lua')

    def test_multi_name_declarations_count_every_name(self):
        p = write('local a, b, c = 1, 2, 3\nlocal function f() end\n')
        self.assertEqual(check.lua_top_level_locals(p), 4)

    def test_a_declaration_on_the_line_after_another_is_not_swallowed(self):
        p = write('local controllerFault\nlocal function log(s) end\n')
        self.assertEqual(check.lua_top_level_locals(p), 2)

    def test_an_indented_local_is_not_top_level(self):
        p = write('local a = 1\nlocal function f()\n    local inner = 2\nend\n')
        self.assertEqual(check.lua_top_level_locals(p), 2)


class TestTheRatchet(unittest.TestCase):
    def test_the_live_harness_is_at_its_ratcheted_count(self):
        fail = []
        check.check_harness_local_ratchet(fail)
        self.assertEqual(fail, [])

    def test_the_ratchet_fails_in_BOTH_directions(self):
        """Growth is the regression. A reduction that does not land here loosens the
        ratchet to whatever the file last happened to reach."""
        real = check.HARNESS_TOP_LEVEL_LOCALS
        try:
            check.HARNESS_TOP_LEVEL_LOCALS = real - 1        # file now looks GROWN
            fail = []
            check.check_harness_local_ratchet(fail)
            self.assertEqual(len(fail), 1, fail)
            self.assertIn('goes in a MODULE', fail[0])

            check.HARNESS_TOP_LEVEL_LOCALS = real + 1        # file now looks THINNED
            fail = []
            check.check_harness_local_ratchet(fail)
            self.assertEqual(len(fail), 1, fail)
            self.assertIn('Lower HARNESS_TOP_LEVEL_LOCALS', fail[0])
        finally:
            check.HARNESS_TOP_LEVEL_LOCALS = real


class TestEveryChunkIsMeasured(unittest.TestCase):
    def test_the_guard_covers_every_playtest_chunk(self):
        """It defaulted to a one-element tuple naming harness.lua. Growth is being pushed
        INTO the other chunks, so measuring only the one it leaves is backwards."""
        fail = []
        check.check_lua_local_headroom(fail)
        self.assertEqual(fail, [])

    def test_the_live_modules_report_real_headroom(self):
        if shutil.which('lua') is None:
            self.skipTest('no lua on PATH')
        for rel in ('tools/playtest/cases.lua', 'tools/playtest/ch05.lua',
                    'tools/playtest/json.lua'):
            free = check.lua_local_headroom(os.path.join(check.REPO, rel))
            self.assertGreater(free, 0, '%s reported no headroom; it is nearly empty' % rel)


if __name__ == '__main__':
    unittest.main(verbosity=2)
