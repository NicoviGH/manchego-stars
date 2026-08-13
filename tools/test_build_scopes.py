#!/usr/bin/env python3
"""Tests for tools/build_scopes.py -- #255 phase 2's build-attributed impact scoping.

The property under test is SOUNDNESS, not cleverness: a scope's digest must move whenever
anything that step wrote moves, and a file written by two steps must belong to both. The
optimistic direction (a write nobody claims, so nobody re-runs) is the only kind of bug
this module is not allowed to have -- so every "cannot tell" path is asserted to land in
`global`.

Run:

    python3 tools/test_build_scopes.py
"""
import os
import shutil
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import build_scopes as bs


def _write(path, text):
    with open(path, 'w') as fh:
        fh.write(text)


class StepScope(unittest.TestCase):
    """A step's scope comes from its own function NAME -- nothing hand-declared."""

    def test_a_chapter_injector_is_scoped_to_its_chapter(self):
        self.assertEqual(bs.scope_of_step('inject_ch05'), 'chapter:ch05')
        self.assertEqual(bs.scope_of_step('inject_ch05_visit_faces'), 'chapter:ch05')

    def test_the_prologue_is_a_chapter_of_its_own(self):
        self.assertEqual(bs.scope_of_step('inject_prologue'), 'chapter:prologue')

    def test_a_global_injector_is_global(self):
        for name in ('inject_portraits', 'inject_names', 'inject_battle_anims'):
            self.assertEqual(bs.scope_of_step(name), 'global')

    def test_a_step_naming_TWO_chapters_is_global(self):
        """`chain_ch04_to_ch05` writes for both sides of a seam. Guessing one of them
        would leave the other's scenarios reading a stale digest, so it is global --
        unknown means conservative, never optimistic."""
        self.assertEqual(bs.scope_of_step('chain_ch04_to_ch05'), 'global')

    def test_an_unrecognised_name_is_global(self):
        self.assertEqual(bs.scope_of_step('_configure_boot'), 'global')
        self.assertEqual(bs.scope_of_step(''), 'global')


class Attribution(unittest.TestCase):
    """What the build ACTUALLY wrote, observed rather than declared."""

    def setUp(self):
        self.tree = tempfile.mkdtemp()
        os.makedirs(os.path.join(self.tree, 'data'))
        self.addCleanup(shutil.rmtree, self.tree, True)
        self.scopes = bs.BuildScopes(root=self.tree, roots=('data',))

    def write(self, name, text):
        with open(os.path.join(self.tree, 'data', name), 'w') as fh:
            fh.write(text)

    def manifest(self):
        return self.scopes.finish()

    def test_a_file_written_inside_a_step_belongs_to_that_step(self):
        self.scopes.run(lambda: self.write('a.s', 'one'), name='inject_ch05')
        m = self.manifest()
        self.assertIn('chapter:ch05', m)
        self.assertIn('data/a.s', m['chapter:ch05']['paths'])

    def test_a_file_written_OUTSIDE_every_step_is_global(self):
        """The build is a script with loose statements between the steps. Anything they
        write is unattributable, and unattributable means shared."""
        self.write('loose.s', 'x')
        self.scopes.run(lambda: self.write('a.s', 'one'), name='inject_ch05')
        m = self.manifest()
        self.assertIn('data/loose.s', m['global']['paths'])
        self.assertNotIn('data/loose.s', m['chapter:ch05']['paths'])

    def test_a_file_written_after_the_last_step_is_still_seen(self):
        self.scopes.run(lambda: self.write('a.s', 'one'), name='inject_ch05')
        self.write('late.s', 'x')
        self.assertIn('data/late.s', self.manifest()['global']['paths'])

    def test_a_file_written_by_TWO_steps_belongs_to_BOTH(self):
        """The soundness case. If a shared table is written by the portrait pass and then
        again by ch05, attributing it to the last writer alone means a portrait edit moves
        only ch05's digest -- and every global scenario is served a stale PASS."""
        self.scopes.run(lambda: self.write('shared.s', 'one'), name='inject_portraits')
        self.scopes.run(lambda: self.write('shared.s', 'two'), name='inject_ch05')
        m = self.manifest()
        self.assertIn('data/shared.s', m['global']['paths'])
        self.assertIn('data/shared.s', m['chapter:ch05']['paths'])

    def test_a_step_that_writes_nothing_claims_nothing(self):
        self.scopes.run(lambda: None, name='inject_ch01')
        self.assertNotIn('chapter:ch01', self.manifest())

    def test_a_step_that_RAISES_still_keeps_what_it_wrote(self):
        """A build that dies half-way must not leave those writes looking unattributed on
        the next pass -- and the digest must describe what is on disk now."""
        def boom():
            self.write('half.s', 'partial')
            raise RuntimeError('build failed')
        with self.assertRaises(RuntimeError):
            self.scopes.run(boom, name='inject_ch03')
        self.assertIn('data/half.s', self.manifest()['chapter:ch03']['paths'])


class Digests(unittest.TestCase):
    def setUp(self):
        self.tree = tempfile.mkdtemp()
        os.makedirs(os.path.join(self.tree, 'data'))
        self.addCleanup(shutil.rmtree, self.tree, True)

    def build(self, ch05_text, portrait_text='p'):
        scopes = bs.BuildScopes(root=self.tree, roots=('data',))
        scopes.run(lambda: self._write('port.s', portrait_text), name='inject_portraits')
        scopes.run(lambda: self._write('ch05.s', ch05_text), name='inject_ch05')
        return scopes.finish()

    def _write(self, name, text):
        with open(os.path.join(self.tree, 'data', name), 'w') as fh:
            fh.write(text)

    def test_the_same_build_gives_the_same_digests(self):
        self.assertEqual(self.build('a')['chapter:ch05']['digest'],
                         self.build('a')['chapter:ch05']['digest'])

    def test_a_chapter_edit_moves_only_that_chapters_digest(self):
        """The entire point of phase 2: a ch05 edit must stop re-running the prologue."""
        first, second = self.build('a'), self.build('b')
        self.assertNotEqual(first['chapter:ch05']['digest'], second['chapter:ch05']['digest'])
        self.assertEqual(first['global']['digest'], second['global']['digest'])

    def test_a_global_edit_moves_the_global_digest(self):
        first, second = self.build('a', portrait_text='p'), self.build('a', portrait_text='q')
        self.assertNotEqual(first['global']['digest'], second['global']['digest'])

    def test_the_digest_covers_CONTENT_not_just_the_path_list(self):
        first, second = self.build('a'), self.build('aa')
        self.assertEqual(first['chapter:ch05']['paths'], second['chapter:ch05']['paths'])
        self.assertNotEqual(first['chapter:ch05']['digest'],
                            second['chapter:ch05']['digest'])


class Reconciliation(unittest.TestCase):
    """The safety net. The per-step walk covers named roots; anything the build touched
    OUTSIDE them must still be accounted for, or it is a silent optimistic gap."""

    def setUp(self):
        self.tree = tempfile.mkdtemp()
        os.makedirs(os.path.join(self.tree, 'data'))
        os.makedirs(os.path.join(self.tree, 'elsewhere'))
        self.addCleanup(shutil.rmtree, self.tree, True)

    def test_a_touched_file_outside_the_walked_roots_lands_in_global(self):
        scopes = bs.BuildScopes(root=self.tree, roots=('data',))
        with open(os.path.join(self.tree, 'elsewhere', 'x.s'), 'w') as fh:
            fh.write('surprise')
        scopes.run(lambda: None, name='inject_ch05')
        m = scopes.finish(touched=['elsewhere/x.s'])
        self.assertIn('elsewhere/x.s', m['global']['paths'])

    def test_reconciliation_does_not_steal_a_file_a_step_already_claimed(self):
        scopes = bs.BuildScopes(root=self.tree, roots=('data',))
        scopes.run(lambda: _write(os.path.join(self.tree, 'data', 'a.s'), '1'),
                   name='inject_ch05')
        m = scopes.finish(touched=['data/a.s'])
        self.assertIn('data/a.s', m['chapter:ch05']['paths'])
        self.assertNotIn('data/a.s', m.get('global', {}).get('paths', []))

    def test_a_missing_reconciled_path_is_not_a_crash(self):
        scopes = bs.BuildScopes(root=self.tree, roots=('data',))
        scopes.finish(touched=['data/never-existed.s'])


class StickyOwnership(unittest.TestCase):
    """A scope owns a file once it has written it, even on a later build that did not.

    Without this the path SET churns: whether a build rewrites a given file depends on what
    was built BEFORE it (the matrix alternates ROM configurations, and the mtime rewind
    hands the next build a different starting point), so a scope's digest moved with no
    content behind it -- and since every scenario depends on `global`, everything re-ran.
    Caught by functional test, not by comparing keys.
    """

    def setUp(self):
        self.tree = tempfile.mkdtemp()
        os.makedirs(os.path.join(self.tree, 'data'))
        self.addCleanup(shutil.rmtree, self.tree, True)
        _write(os.path.join(self.tree, 'data', 'sometimes.s'), 'stable')

    def build(self, rewrite, previous=None):
        scopes = bs.BuildScopes(root=self.tree, roots=('data',))
        def step():
            if rewrite:
                _write(os.path.join(self.tree, 'data', 'sometimes.s'), 'stable')
        scopes.run(step, name='inject_ch05')
        return scopes.finish(previous=previous)

    def test_a_scope_keeps_a_file_a_later_build_did_not_rewrite(self):
        first = self.build(rewrite=True)
        self.assertIn('data/sometimes.s', first['chapter:ch05']['paths'])
        second = self.build(rewrite=False, previous=first)
        self.assertIn('data/sometimes.s', second['chapter:ch05']['paths'])

    def test_the_digest_therefore_holds_still(self):
        first = self.build(rewrite=True)
        second = self.build(rewrite=False, previous=first)
        self.assertEqual(first['chapter:ch05']['digest'], second['chapter:ch05']['digest'])

    def test_inherited_ownership_still_tracks_CONTENT(self):
        """Sticky paths must not mean a stale digest: the file is re-hashed as it is now."""
        first = self.build(rewrite=True)
        _write(os.path.join(self.tree, 'data', 'sometimes.s'), 'CHANGED')
        second = self.build(rewrite=False, previous=first)
        self.assertNotEqual(first['chapter:ch05']['digest'], second['chapter:ch05']['digest'])

    def test_a_deleted_file_does_not_break_the_merge(self):
        first = self.build(rewrite=True)
        os.remove(os.path.join(self.tree, 'data', 'sometimes.s'))
        second = self.build(rewrite=False, previous=first)
        self.assertIn('data/sometimes.s', second['chapter:ch05']['paths'])


class ManifestFile(unittest.TestCase):
    def setUp(self):
        self.tree = tempfile.mkdtemp()
        os.makedirs(os.path.join(self.tree, 'data'))
        self.addCleanup(shutil.rmtree, self.tree, True)

    def test_it_round_trips_through_disk(self):
        scopes = bs.BuildScopes(root=self.tree, roots=('data',))
        scopes.run(lambda: _write(os.path.join(self.tree, 'data', 'a.s'), '1'),
                   name='inject_ch05')
        path = os.path.join(self.tree, 'scopes.json')
        written = scopes.write_manifest(path)
        self.assertEqual(bs.load_manifest(path), written)

    def test_a_missing_manifest_reads_as_None_not_an_empty_one(self):
        """None means "we do not know what this build wrote", which must fall back to the
        conservative whole-ROM key. An empty dict would read as "it wrote nothing"."""
        self.assertIsNone(bs.load_manifest(os.path.join(self.tree, 'nope.json')))

    def test_a_corrupt_manifest_reads_as_None(self):
        path = os.path.join(self.tree, 'bad.json')
        with open(path, 'w') as fh:
            fh.write('{ not json')
        self.assertIsNone(bs.load_manifest(path))


if __name__ == '__main__':
    unittest.main()
