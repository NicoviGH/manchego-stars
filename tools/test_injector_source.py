#!/usr/bin/env python3
"""The injector's source is every file of it, not build_campaign.py (#389).

#389 moves code out of build_campaign.py into tools/inject/. Every reader that scanned the
old file by path would have gone QUIET when its target moved -- a `NotIn` with nothing left
to object to, a discovery scan that finds one chapter fewer. These tests move code for real,
into a second file of a throwaway injector, and watch each reader follow it.

Run:  python3 tools/test_injector_source.py
"""
import os
import shutil
import sys
import tempfile
import textwrap
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import check                                                         # noqa: E402
from inject import hosts                                             # noqa: E402
from inject import source                                            # noqa: E402

# build_campaign.py's stand-in: defines the writer, and one chapter still at home.
HOME = textwrap.dedent('''\
    def set_message_body(text_id, msg_id, body):
        pass


    def inject_ch01(campaign):
        set_message_body(1, 0x901, 'stays home')
''')

# A module #389 moved a chapter into. Its header IMPORTS the helpers the tile-change guard
# searches for, which is exactly what a whole-file concatenation would spill into.
MOVED = textwrap.dedent('''\
    """A chapter that moved."""
    from build_campaign import set_message_body, _retarget_host_chapter


    def inject_ch09(campaign):
        _retarget_host_chapter(campaign)
        set_message_body(1, 0x9A0, 'moved')
        _inject_tile_changes(campaign)
''')


class _TwoFileInjector(unittest.TestCase):
    """A real injector on disk: a build_campaign.py and one module under inject/."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        home = os.path.join(self.tmp, 'build_campaign.py')
        inject = os.path.join(self.tmp, 'inject')
        os.makedirs(inject)
        with open(home, 'w', encoding='utf-8') as f:
            f.write(HOME)
        with open(os.path.join(inject, 'chapters.py'), 'w', encoding='utf-8') as f:
            f.write(MOVED)
        patches = [mock.patch.object(source, 'BUILD_CAMPAIGN_PY', home),
                   mock.patch.object(source, 'INJECT_DIR', inject)]
        for p in patches:
            p.start()
            self.addCleanup(p.stop)
        hosts._literal_cache.clear()
        self.addCleanup(hosts._literal_cache.clear)

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)


class ReadersFollowMovedCode(_TwoFileInjector):

    def test_discovery_finds_an_injector_that_moved(self):
        self.assertEqual(['ch01', 'ch09'], hosts.injector_chapters())

    def test_a_literal_in_a_moved_file_is_found_and_owned(self):
        """Bound against the writer's signature in ANOTHER file -- a call site has no local
        definition to bind a positional id against, which is what made it invisible."""
        found = {(lit.msg_id, lit.chapter, os.path.basename(lit.path))
                 for lit in hosts.literal_message_ids()}
        self.assertEqual({(0x901, 'ch01', 'build_campaign.py'),
                          (0x9A0, 'ch09', 'chapters.py')}, found)

    def test_one_definition_is_found_wherever_it_lives(self):
        self.assertTrue(source.defining_file('inject_ch09').endswith('chapters.py'))
        self.assertIn('_inject_tile_changes', source.def_source('inject_ch09'))
        self.assertIsNone(source.def_source('inject_ch42'))

    def test_the_function_view_carries_no_module_header(self):
        """The spill a concatenated view would cause: inject_ch01 is the last function of
        its file, and over whole files its `^def ...(?=^def )` body runs on into the moved
        module's import line -- which names _retarget_host_chapter."""
        text = source.defs_source()
        self.assertNotIn('import', text)
        body = text[text.index('def inject_ch01'):text.index('def inject_ch09')]
        self.assertNotIn('_retarget_host_chapter', body)

    def test_the_tile_change_guard_sees_the_moved_chapter(self):
        self.assertIn('inject_ch09', check._tile_change_injectors_seen(source.defs_source()))

    def test_the_code_view_blanks_module_docstrings_and_imports_but_keeps_lines(self):
        """An import line names the very helpers a guard searches for, and a docstring can
        spell a table's assignment; neither is the real thing."""
        text = source.injector_source()
        self.assertNotIn('import', text)
        self.assertNotIn('A chapter that moved', text)
        moved = source.code_text(os.path.join(self.tmp, 'inject', 'chapters.py'))
        self.assertEqual(MOVED.count('\n'), moved.count('\n'), 'line numbers must survive')

    def test_a_subscript_assignment_defines_nothing(self):
        """`TABLE[KEY] = v` binds neither TABLE nor KEY. Counting them made def_source('KEY')
        either return that line or raise a false 'defined in two files'."""
        with open(os.path.join(self.tmp, 'inject', 'tables.py'), 'w', encoding='utf-8') as f:
            f.write('TABLE = {}\nTABLE[KEY] = 1\nA, (B, *C) = 1, (2, 3)\n')
        with open(source.BUILD_CAMPAIGN_PY, 'a', encoding='utf-8') as f:
            f.write('\nKEY = 3\n')
        self.assertEqual('KEY = 3\n', source.def_source('KEY'))
        self.assertEqual('TABLE = {}\n', source.def_source('TABLE'))
        for name in ('A', 'B', 'C'):
            self.assertTrue(source.defining_file(name).endswith('tables.py'), name)

    def test_a_name_defined_in_two_files_is_an_error_not_a_coin_toss(self):
        with open(os.path.join(self.tmp, 'inject', 'copy.py'), 'w', encoding='utf-8') as f:
            f.write('def inject_ch09(campaign):\n    pass\n')
        with self.assertRaises(ValueError):
            source.def_source('inject_ch09')


class OneReader(unittest.TestCase):
    """check_injector_source_has_one_reader, watched failing both ways."""

    def test_a_reader_of_the_old_path_fails(self):
        fail = check.check_injector_source_has_one_reader([], sources={
            'tools/some_guard.py':
                "import os\nsrc = open(os.path.join(REPO, 'tools', 'build_campaign.py')).read()\n"})
        self.assertEqual(1, len(fail))
        self.assertIn('tools/some_guard.py:2', fail[0])

    def test_naming_the_file_in_prose_is_free(self):
        self.assertEqual([], check.check_injector_source_has_one_reader([], sources={
            'tools/doc.py': '"""Reads build_campaign.py, once."""\n# see build_campaign.py\n'}))

    def test_a_stale_excuse_fails(self):
        fail = check.check_injector_source_has_one_reader([], sources={
            'tools/probe_invalidation.py': 'x = 1\n'})
        self.assertEqual(1, len(fail))
        self.assertIn('INJECTOR_PATH_NAMERS', fail[0])

    def test_the_live_tree_passes(self):
        self.assertEqual([], check.check_injector_source_has_one_reader([]))

    def test_it_is_registered(self):
        self.assertIn(check.check_injector_source_has_one_reader, check.CHECKS)


class TheLiveInjector(unittest.TestCase):

    def test_it_spans_the_package(self):
        files = [os.path.basename(p) for p in source.injector_files()]
        self.assertEqual('build_campaign.py', files[0])
        self.assertIn('engine_patches.py', files)
        self.assertIn('source.py', files)

    def test_a_table_appears_once_however_many_modules_describe_it(self):
        """inject/source.py's own docstring names `RAW_PID_BATTLE_ANIMS = {`; a first-match
        regex over the code view must still land on the real table."""
        self.assertEqual(1, source.injector_source().count('RAW_PID_BATTLE_ANIMS = {'))

    def test_a_definition_resolves_to_its_real_home(self):
        self.assertTrue(source.defining_file('apply_engine_patches')
                        .endswith(os.path.join('inject', 'engine_patches.py')))


if __name__ == '__main__':
    unittest.main()
