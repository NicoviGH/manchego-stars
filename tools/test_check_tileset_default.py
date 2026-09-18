#!/usr/bin/env python3
"""Tests that the keyless-sidecar tileset default has ONE home (#377).

A sidecar that names no tileset means `snowy-bern` — the three oldest maps (ch00–ch02) predate
the key entirely. #371 gave that rule one home in `build_campaign.map_tileset`, #374 fixed
three `map_changes` sites that bypassed it and #376 a fourth. Two tools outside the build still
re-declared the rule AND spelled the literal themselves: `map_donor` (the READ side, whose
score decides which donor a map is reported to have) and `import_map_layout` (the WRITE side,
which bakes the answer into the sidecar it creates).

What makes this worth a gate rather than one more patch: the answer was already written down.
`map_tileset_tool.DEFAULT_TILESET` has existed all along, in the module that owns tilesets and
imports nothing but stdlib — so every reader, including the deliberately stdlib-only
`map_donor`, could always have reached it. Five copies were made anyway, because nothing said
they could not be.

Run: python3 tools/test_check_tileset_default.py
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import check
import map_tileset_tool as mt


class OneHome(unittest.TestCase):

    def test_the_home_is_the_module_that_owns_tilesets(self):
        self.assertEqual('snowy-bern', mt.DEFAULT_TILESET)

    def test_the_home_is_reachable_by_a_stdlib_only_tool(self):
        """`map_donor` commits to stdlib + map_tileset_tool, and reads `CHNN_LAYOUT` out of
        build_campaign's SOURCE with a regex rather than importing it. A default that lived in
        `build_campaign` would be unreachable from there; this one always was reachable."""
        import map_donor
        self.assertIs(map_donor.mt, mt)

    def test_the_live_repo_has_no_second_copy(self):
        fail = []
        check.check_one_tileset_default(fail)
        self.assertEqual([], fail)


class RepointingItMovesEveryReader(unittest.TestCase):
    """The property the copies broke: one edit, every reader.

    Not "the constant exists" -- five copies coexisted with the constant for months. What
    matters is that changing it is felt everywhere, which is only true once nobody spells the
    literal themselves.
    """

    def test_the_build_reads_the_shared_constant(self):
        import build_campaign as bc
        self.assertEqual(mt.DEFAULT_TILESET, bc.WINTER_TILESET)

    def test_a_keyless_sidecar_resolves_through_it_in_the_build(self):
        import build_campaign as bc
        original = mt.DEFAULT_TILESET
        try:
            mt.DEFAULT_TILESET = 'repointed-for-this-test'
            self.assertEqual('repointed-for-this-test', bc.map_tileset({}))
        finally:
            mt.DEFAULT_TILESET = original

    def test_no_reader_holds_its_own_copy_of_the_literal(self):
        """The gate, stated as the property rather than as a grep."""
        fail = []
        check.check_one_tileset_default(fail)
        self.assertEqual([], fail)


class TheGateCatchesACopy(unittest.TestCase):

    def _run_on(self, body):
        import tempfile
        d = tempfile.mkdtemp()
        path = os.path.join(d, 'copycat.py')
        with open(path, 'w') as fh:
            fh.write(body)
        original = check._tileset_default_readers
        try:
            check._tileset_default_readers = lambda: [path]
            fail = []
            check.check_one_tileset_default(fail)
            return fail
        finally:
            check._tileset_default_readers = original

    def test_a_re_declared_default_is_reported(self):
        fail = self._run_on("ts = meta.get('tileset', 'snowy-bern')\n")
        self.assertTrue(fail)

    def test_the_double_quoted_spelling_is_reported_too(self):
        fail = self._run_on('ts = meta.get("tileset", "snowy-bern")\n')
        self.assertTrue(fail)

    def test_reading_the_shared_constant_is_fine(self):
        self.assertEqual([], self._run_on(
            "ts = meta.get('tileset', mt.DEFAULT_TILESET)\n"))

    def test_a_keyless_get_with_no_default_is_fine(self):
        """Some callers want None and handle it themselves; that is not a second default."""
        self.assertEqual([], self._run_on("ts = meta.get('tileset')\n"))


if __name__ == '__main__':
    unittest.main(verbosity=2)
