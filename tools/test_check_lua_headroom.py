#!/usr/bin/env python3
"""Tests for the Lua local-headroom probe's FILE SHAPES, and for the ratchet (#327).

The plain count cases -- empty chunk, one short of the ceiling, at the ceiling, the gate
failing at zero -- live in `test_check_lua_loads.py::LocalHeadroom` and are not repeated
here. What this file covers is the thing that was actually broken: the probe worked on
`harness.lua` and on nothing else, because every attempt to insert probes near the END of a
chunk is ambiguous, and each ambiguity read as the OPPOSITE of the truth.

  * appended after a trailing `return` -> syntax error -> "0 free" on a nearly empty module,
    and 0 is the number that fails the build;
  * inserted before the last column-0 `return` -> misses an INDENTED one (same lie), and
    lands inside a nested function when that return is in one, where the probe measures the
    FUNCTION's budget -- so a chunk at exactly 200 locals reports FULL HEADROOM and passes;
  * a file with no trailing newline -> `end` + `local __p` became `endlocal __p`.

Probes are prepended now, which has none of those cases. Each shape below is one of the
lies, kept so the fix cannot silently regress into any of them.

Run: python3 tools/test_check_lua_headroom.py
"""
import os
import shutil
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import check                                            # noqa: E402

AT_CEILING = ''.join('local v%d = %d\n' % (i, i) for i in range(199))


class ChunkCase(unittest.TestCase):
    def chunk(self, body):
        d = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, d, True)
        path = os.path.join(d, 'chunk.lua')
        with open(path, 'w', encoding='utf-8') as fh:
            fh.write(body)
        return path

    def free(self, body, probe_max=4):
        return check.lua_local_headroom(self.chunk(body), probe_max=probe_max)


class TestFileShapesThatUsedToLie(ChunkCase):
    def test_a_module_ending_in_a_return_is_measured(self):
        self.assertEqual(self.free('local M = {}\nM.x = 1\nreturn M\n'), 4)

    def test_a_module_whose_return_expression_spans_many_lines(self):
        # ch05.lua's return spans forty lines, which defeated a single-line `return M` regex.
        body = 'local M = {}\nreturn {\n  a = 1,\n  b = 2,\n  c = {\n    d = 3,\n  },\n}\n'
        self.assertEqual(self.free(body), 4)

    def test_a_final_top_level_return_that_is_INDENTED(self):
        self.assertEqual(self.free('local M = {}\nif true then\n  return M\nend\n  return M\n'), 4)

    def test_a_chunk_with_no_trailing_newline(self):
        # `end` + `local __p` became `endlocal __p`: 74 locals reported as full.
        self.assertEqual(self.free('local a = 1\nif a then\nprint(a)\nend'), 4)

    def test_a_shebang_stays_the_first_line(self):
        # Lua accepts `#` only as line 1, so a prepended probe must go after it.
        self.assertEqual(self.free('#!/usr/bin/env lua\nlocal a = 1\nreturn a\n'), 4)

    def test_a_FULL_chunk_whose_returns_sit_inside_a_function_still_reports_zero(self):
        """The dangerous direction. Probing before a column-0 `return` that lives inside a
        function measures that function's budget, so a chunk at exactly 200 top-level locals
        reported FULL headroom and passed the guard in silence."""
        body = AT_CEILING + 'local function f(x)\nif x then\nreturn 1\nend\nreturn 2\nend\n'
        self.assertEqual(self.free(body), 0)

    def test_a_nearly_full_module_reports_its_real_margin(self):
        self.assertEqual(self.free(AT_CEILING + 'return v0\n'), 1)

    def test_a_broken_chunk_raises_rather_than_reporting_zero(self):
        """Zero is a build failure with a specific fix attached, and it would be the wrong
        one: the chunk does not compile, which is check_lua_chunks_load's finding."""
        with self.assertRaises(check.LuaChunkError):
            self.free('local M = {\n')


class TestEveryChunkIsMeasured(unittest.TestCase):
    def test_the_guard_covers_every_playtest_chunk(self):
        """It defaulted to a one-element tuple naming harness.lua. Growth is being pushed
        INTO the other chunks (#314), so measuring only the one it leaves is backwards."""
        fail = []
        check.check_lua_local_headroom(fail)
        self.assertEqual(fail, [])

    def test_the_live_modules_report_real_headroom(self):
        if shutil.which('lua') is None:
            self.skipTest('no lua on PATH')
        for rel in ('tools/playtest/cases.lua', 'tools/playtest/ch05.lua',
                    'tools/playtest/json.lua', 'tools/playtest/test_controller.lua'):
            free = check.lua_local_headroom(os.path.join(check.REPO, rel), probe_max=4)
            self.assertGreater(free, 0, '%s reported no headroom; it is nearly empty' % rel)


class TestTheCounterAgreesWithTheProber(ChunkCase):
    """Two independent mechanisms measure the same ceiling, so they must agree.

    The counter reads the source; the prober asks the compiler. Neither is checkable alone,
    and the counter WAS wrong by one when written -- `\\s` matches a newline, so
    `local controllerFault` merged with the `local function log` under it. The ratchet runs
    on the counter, so a quiet off-by-one there loosens it by one on every re-measure.
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
        self.assertEqual(
            check.lua_top_level_locals(self.chunk('local a, b, c = 1, 2, 3\n'
                                                  'local function f() end\n')), 4)

    def test_a_declaration_on_the_line_after_another_is_not_swallowed(self):
        self.assertEqual(
            check.lua_top_level_locals(
                self.chunk('local controllerFault\nlocal function log(s) end\n')), 2)

    def test_an_indented_local_is_not_top_level(self):
        self.assertEqual(
            check.lua_top_level_locals(
                self.chunk('local a = 1\nlocal function f()\n    local inner = 2\nend\n')), 2)


class TestTheRatchet(unittest.TestCase):
    def test_the_live_harness_is_at_its_ratcheted_count(self):
        fail = []
        check.check_harness_local_ratchet(fail)
        self.assertEqual(fail, [])

    def test_the_ratchet_fails_in_BOTH_directions(self):
        """Growth is the regression. A reduction that does not land in the constant loosens
        the ratchet to whatever the file last happened to reach."""
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


if __name__ == '__main__':
    unittest.main(verbosity=2)
