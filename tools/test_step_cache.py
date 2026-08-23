#!/usr/bin/env python3
"""Tests for tools/inject/step_cache.py -- the config-invariant injection cache (#309).

Every test runs a real step against a real temp tree: the unit under test is "what
happened to the files", and a mock cannot tell you that.

Run:

    python3 tools/test_step_cache.py
"""
import os
import shutil
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from inject import step_cache as sc


def read(path):
    with open(path, 'rb') as fh:
        return fh.read()


def write(path, data):
    if not os.path.isdir(os.path.dirname(path)):
        os.makedirs(os.path.dirname(path))
    with open(path, 'wb') as fh:
        fh.write(data if isinstance(data, bytes) else data.encode())


class StepCacheTest(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.tree = os.path.join(self.tmp, 'tree')
        self.store = os.path.join(self.tmp, 'store')
        os.makedirs(os.path.join(self.tree, 'data'))
        # a file the step OVERWRITES (an earlier step wrote it) and one it CREATES
        write(os.path.join(self.tree, 'data', 'shared.c'), 'from an earlier step\n')
        self.runs = []

    def cache(self, key='k1'):
        return sc.StepCache(self.tree, self.store, key, roots=('data',))

    def step(self, payload='anim rows\n'):
        """A stand-in for an injection step: overwrites one file, creates another."""
        def inject_battle_anims():
            self.runs.append(payload)
            write(os.path.join(self.tree, 'data', 'shared.c'), 'anims bound\n')
            write(os.path.join(self.tree, 'data', 'banim', 'rows.s'), payload)
        return inject_battle_anims

    # -- miss ---------------------------------------------------------------

    def test_a_cold_step_runs_and_is_recorded(self):
        outcome = self.cache().run(self.step())
        self.assertEqual(self.runs, ['anim rows\n'])
        self.assertFalse(outcome.hit)
        self.assertEqual(sorted(outcome.paths), ['data/banim/rows.s', 'data/shared.c'])

    # -- hit ----------------------------------------------------------------

    def test_a_second_run_restores_instead_of_running(self):
        self.cache().run(self.step())
        os.remove(os.path.join(self.tree, 'data', 'banim', 'rows.s'))
        write(os.path.join(self.tree, 'data', 'shared.c'), 'from an earlier step\n')

        outcome = self.cache().run(self.step())

        self.assertEqual(len(self.runs), 1, 'the step must not have run a second time')
        self.assertTrue(outcome.hit)
        self.assertEqual(read(os.path.join(self.tree, 'data', 'banim', 'rows.s')),
                         b'anim rows\n')
        self.assertEqual(read(os.path.join(self.tree, 'data', 'shared.c')), b'anims bound\n')

    def test_a_created_file_comes_back_even_though_it_was_absent_before(self):
        """The pre-state of a CREATED file is 'missing', which is a state like any other."""
        self.cache().run(self.step())
        shutil.rmtree(os.path.join(self.tree, 'data', 'banim'))
        write(os.path.join(self.tree, 'data', 'shared.c'), 'from an earlier step\n')

        self.cache().run(self.step())

        self.assertTrue(os.path.isfile(os.path.join(self.tree, 'data', 'banim', 'rows.s')))

    # -- what makes a hit unsound -------------------------------------------

    def test_a_different_key_does_not_hit(self):
        self.cache('k1').run(self.step())
        write(os.path.join(self.tree, 'data', 'shared.c'), 'from an earlier step\n')
        self.cache('k2').run(self.step('other rows\n'))
        self.assertEqual(len(self.runs), 2)

    def test_a_moved_pre_state_does_not_hit_even_on_the_same_key(self):
        """The licence to restore is that everything the step READS is unchanged. A file it
        overwrites is one of those reads, and an earlier step having written something else
        into it means this step's recorded output answers a question nobody asked."""
        self.cache().run(self.step())
        write(os.path.join(self.tree, 'data', 'shared.c'), 'an EARLIER STEP MOVED\n')

        outcome = self.cache().run(self.step())

        self.assertFalse(outcome.hit)
        self.assertEqual(len(self.runs), 2, 'the step must re-run when its input moved')

    def test_a_step_that_raises_records_nothing(self):
        """Half a step's writes cached as a whole step is a poisoned entry that would
        restore forever."""
        def explodes():
            write(os.path.join(self.tree, 'data', 'banim', 'rows.s'), 'half\n')
            raise RuntimeError('injection failed')

        with self.assertRaises(RuntimeError):
            self.cache().run(explodes)

        outcome = self.cache().run(self.step())
        self.assertFalse(outcome.hit)
        self.assertEqual(len(self.runs), 1)

    def test_one_step_s_entry_does_not_answer_for_another(self):
        self.cache().run(self.step())
        write(os.path.join(self.tree, 'data', 'shared.c'), 'from an earlier step\n')

        def inject_map_sprites():
            self.runs.append('sprites')
            write(os.path.join(self.tree, 'data', 'sprites.s'), 'sprite rows\n')

        outcome = self.cache().run(inject_map_sprites)
        self.assertFalse(outcome.hit)

    def test_a_tree_still_holding_last_build_s_output_hits(self):
        """The real case: nothing wipes the decomp between builds, so on the next build every
        file this step wrote is still sitting at its OUTPUT. That is a state restoring is
        correct from -- it writes the same bytes -- and treating it as a miss would mean the
        cache never hit in the tree it was built for."""
        self.cache().run(self.step())          # leaves data/banim/rows.s at its output
        write(os.path.join(self.tree, 'data', 'shared.c'), 'from an earlier step\n')

        outcome = self.cache().run(self.step())

        self.assertTrue(outcome.hit)
        self.assertEqual(len(self.runs), 1)

    def test_an_appending_step_is_not_applied_twice(self):
        """A banim table is APPENDED to (additive donor-prime, #65). Restoring the recorded
        output is what keeps that idempotent -- re-running it over its own output would double
        the rows, which is why a hit restores rather than re-runs."""
        table = os.path.join(self.tree, 'data', 'table.s')
        write(table, 'vanilla rows\n')

        def inject_battle_anims():
            self.runs.append('append')
            with open(table, 'a') as fh:
                fh.write('our rows\n')

        self.cache().run(inject_battle_anims)
        self.assertEqual(read(table), b'vanilla rows\nour rows\n')

        outcome = self.cache().run(inject_battle_anims)

        self.assertTrue(outcome.hit)
        self.assertEqual(read(table), b'vanilla rows\nour rows\n')

    def test_a_verbose_cache_says_what_it_restored(self):
        """The build log is where a cache is seen working; the call site should not have to
        wrap every step to get that line."""
        import contextlib, io as _io
        sc.StepCache(self.tree, self.store, 'k1', roots=('data',), verbose=True).run(self.step())
        buf = _io.StringIO()
        with contextlib.redirect_stdout(buf):
            sc.StepCache(self.tree, self.store, 'k1', roots=('data',),
                         verbose=True).run(self.step())
        self.assertIn('restored', buf.getvalue())
        self.assertIn('inject_battle_anims', buf.getvalue())

    def test_a_quiet_cache_says_nothing(self):
        import contextlib, io as _io
        buf = _io.StringIO()
        with contextlib.redirect_stdout(buf):
            self.cache().run(self.step())
            self.cache().run(self.step())
        self.assertEqual(buf.getvalue(), '')

    # -- reporting ----------------------------------------------------------

    def test_a_miss_saves_nothing_and_a_hit_saves_what_the_step_cost(self):
        """The build log has to be able to say what the cache saved, or nobody can tell
        whether it is working."""
        import json
        cold = self.cache().run(self.step())
        write(os.path.join(self.tree, 'data', 'shared.c'), 'from an earlier step\n')
        warm = self.cache().run(self.step())

        self.assertEqual(cold.saved, 0.0)
        recorded = json.load(open(os.path.join(
            self.store, 'inject_battle_anims', 'entry.json')))['seconds']
        self.assertTrue(warm.hit)
        self.assertEqual(warm.saved, recorded)


class DisabledCache(unittest.TestCase):
    """`NO_INJECT_CACHE=1` has to mean the step runs, not that the caller branches."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.runs = []

    def test_a_disabled_cache_always_runs_the_step_and_stores_nothing(self):
        cache = sc.disabled()

        def inject_battle_anims():
            self.runs.append(1)

        first = cache.run(inject_battle_anims)
        second = cache.run(inject_battle_anims)

        self.assertEqual(len(self.runs), 2)
        self.assertFalse(first.hit)
        self.assertFalse(second.hit)
        self.assertEqual(os.listdir(self.tmp), [], 'a disabled cache writes nothing')


if __name__ == '__main__':
    unittest.main()
