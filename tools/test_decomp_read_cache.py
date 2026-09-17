#!/usr/bin/env python3
"""Tests that reading VANILLA out of the decomp costs one subprocess per file (#380).

The oracle is a measurement, not a preference. `vanilla_decomp_text` shells out to
`git -C fireemblem8u show HEAD:<file>`, and it used to do that on every call. One
`difficulty.curve_report` made 148 of those calls against 9 UNIQUE files -- reading
`src/events_udefs.c` (1.78 MB) 114 times, 199 MB of subprocess I/O to obtain 2.1 MB of
distinct content. In `tools/test_difficulty.py` that was 1,862 calls, ~50s of a 151s run,
and it is the reason a commit here took 6-10 minutes with the CPU near idle: the pre-commit
hook runs every test file, and they were all blocked on `git show`.

HEAD does not move inside a process, so these reads are pure and the count is a fact about
the code rather than about the chapter. That is what these tests pin:

  * a repeated read of one file spawns ONE `git show`;
  * a real `curve_report` reads each file it needs exactly once;
  * `vanilla_redas` -- a whole-file regex over that same 1.78 MB -- is not re-run per
    UnitDefinition array (it was, 5,507 times, 27.4s of pure CPU);
  * there is ONE head reader, because there were two identical ones.

These are regression tests. They fail loudly if someone reintroduces an uncached read, and
the number they assert is the number the profile measured.

Run: python3 tools/test_decomp_read_cache.py
"""
import os
import sys
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import build_campaign as bc                                           # noqa: E402
import difficulty as dif                                              # noqa: E402

CAMPAIGN = 'rime-of-the-frostmaiden'


def _clear():
    """Drop every memo so a test measures its own reads, not a previous test's."""
    for fn in (bc.vanilla_decomp_text, dif.vanilla_redas):
        clear = getattr(fn, 'cache_clear', None)
        if clear:
            clear()


class OneSubprocessPerFile(unittest.TestCase):
    """The narrow claim: the same relpath does not shell out twice."""

    def setUp(self):
        _clear()
        self.addCleanup(_clear)

    def test_reading_one_file_twice_spawns_one_git_show(self):
        real = bc.subprocess.check_output
        with mock.patch.object(bc.subprocess, 'check_output', side_effect=real) as spawn:
            first = bc.vanilla_decomp_text('include/constants/terrains.h')
            second = bc.vanilla_decomp_text('include/constants/terrains.h')
        self.assertEqual(1, spawn.call_count,
                         'a second read of the same decomp file shelled out again')
        self.assertEqual(first, second)

    def test_two_different_files_still_spawn_two(self):
        """The memo is per-relpath -- caching must not collapse distinct files."""
        real = bc.subprocess.check_output
        with mock.patch.object(bc.subprocess, 'check_output', side_effect=real) as spawn:
            terrains = bc.vanilla_decomp_text('include/constants/terrains.h')
            characters = bc.vanilla_decomp_text('include/constants/characters.h')
        self.assertEqual(2, spawn.call_count)
        self.assertNotEqual(terrains, characters)

    def test_the_cached_read_returns_the_same_object(self):
        """`vanilla_redas` memoises on the TEXT, and that is only O(1) to hash when the
        cached read hands back the same str object rather than an equal copy."""
        # Compare identity by id() so a failure prints two integers rather than two
        # copies of the file.
        self.assertEqual(id(bc.vanilla_decomp_text('include/constants/terrains.h')),
                         id(bc.vanilla_decomp_text('include/constants/terrains.h')),
                         'the cached read handed back an equal copy, not the same object')


class ARealWorkloadReadsEachFileOnce(unittest.TestCase):
    """The measurement that opened #380, turned into a gate."""

    def setUp(self):
        _clear()
        self.addCleanup(_clear)

    def test_a_curve_report_shells_out_once_per_distinct_decomp_file(self):
        """Calls may repeat freely -- that is what a memo is for. SPAWNS may not.

        Asking for `src/events_udefs.c` 114 times is fine; reading it off disk 114 times
        is the 199 MB. So the oracle is `git show` process count against the number of
        distinct files the report actually needs.
        """
        spawns = []
        real_spawn = bc.subprocess.check_output

        def counting_spawn(cmd, *a, **kw):
            if isinstance(cmd, (list, tuple)) and 'show' in cmd:
                spawns.append(cmd[-1])
            return real_spawn(cmd, *a, **kw)

        import contextlib
        import io
        with mock.patch.object(bc.subprocess, 'check_output', counting_spawn):
            with contextlib.redirect_stdout(io.StringIO()):
                dif.curve_report(CAMPAIGN)

        self.assertTrue(spawns, 'curve_report shelled out to git not once -- did it run?')
        duplicates = {p: spawns.count(p) for p in set(spawns) if spawns.count(p) > 1}
        self.assertEqual(
            {}, duplicates,
            'curve_report re-read %d decomp file(s) off disk; worst: %s'
            % (len(duplicates),
               max(duplicates.items(), key=lambda kv: kv[1]) if duplicates else None))


class RedasIsParsedOncePerSource(unittest.TestCase):
    """`vanilla_unit_defs` needs the file's REDA arrays; it used to re-parse the whole
    1.78 MB source for every array it was asked about."""

    def setUp(self):
        _clear()
        self.addCleanup(_clear)

    def test_many_unit_def_arrays_parse_redas_once(self):
        text = bc.vanilla_decomp_text('src/events_udefs.c')
        import re
        arrays = re.findall(r'CONST_DATA struct UnitDefinition (\w+)\[\]', text)[:6]
        self.assertGreaterEqual(len(arrays), 2, 'need >=2 UnitDefinition arrays to prove it')

        real = dif.vanilla_redas
        with mock.patch.object(dif, 'vanilla_redas', side_effect=real) as redas:
            for name in arrays:
                dif.vanilla_unit_defs(text, name)
        # Called once per array is fine; PARSING once is the point, so a memoised
        # vanilla_redas reports len(arrays) calls but only one cache miss.
        info = getattr(real, 'cache_info', None)
        self.assertIsNotNone(info, 'vanilla_redas is not memoised')
        self.assertEqual(1, info().misses,
                         'the same source text was re-parsed for REDA arrays %d times'
                         % info().misses)
        self.assertEqual(len(arrays), redas.call_count)


class OneHeadReader(unittest.TestCase):
    """There were two identical `git show HEAD:` helpers in build_campaign. A second
    copy is a second thing to forget to cache -- and it was not cached."""

    def test_the_private_duplicate_is_gone(self):
        self.assertFalse(
            hasattr(bc, '_vanilla_decomp_text_at_head'),
            '_vanilla_decomp_text_at_head is a duplicate of vanilla_decomp_text; '
            'call vanilla_decomp_text instead so the memo covers it too')

    def test_chapter_label_constants_reads_through_the_cached_reader(self):
        _clear()
        self.addCleanup(_clear)
        real = bc.subprocess.check_output
        with mock.patch.object(bc.subprocess, 'check_output', side_effect=real) as spawn:
            bc.chapter_label_constants()
            bc.chapter_label_constants()
        self.assertLessEqual(spawn.call_count, 1,
                             'chapter_label_constants re-read chapters.h from git')


if __name__ == '__main__':
    unittest.main()
