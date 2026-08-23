#!/usr/bin/env python3
"""Tests for tools/playtest/gen_symbols.py pure helpers -- nm parsing and the two
generated symbol tables the inspector resolves addresses against (#236). Run:
python3 tools/playtest/test_gen_symbols.py
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import gen_symbols as gs


NM = '\n'.join([
    '085b1890 T gProcScr_PlayerPhase',
    '085a7ef4 T gProcScr_E_FACE',
    '085a7f2c T gProcScr_E_FACE_ExtraFrame',
    '08a39190 T ProcScr_PrepMenu',
    '0801c9e0 T PlayerPhase_MainIdle',
    '08007ca0 T TalkWaitForInput_OnIdle',
    '0202bcf0 B gPlaySt',
    '         U SomeUndefined',
    '00000004 a .gcc2_compiled.',
])


class ParseNm(unittest.TestCase):
    def test_keeps_addressed_symbols_with_their_type(self):
        syms = gs.parse_nm(NM)
        self.assertIn(('gPlaySt', 'B', 0x0202BCF0), [(s.name, s.type, s.addr) for s in syms])

    def test_drops_undefined_symbols_that_carry_no_address(self):
        self.assertNotIn('SomeUndefined', [s.name for s in gs.parse_nm(NM)])


class WantedSymbols(unittest.TestCase):
    def test_resolves_each_wanted_name_to_its_address(self):
        got = gs.wanted_symbols(gs.parse_nm(NM), ['gPlaySt', 'ProcScr_PrepMenu'])
        self.assertEqual(got, {'gPlaySt': 0x0202BCF0, 'ProcScr_PrepMenu': 0x08A39190})

    def test_missing_symbol_is_reported_not_silently_dropped(self):
        with self.assertRaises(KeyError) as raised:
            gs.wanted_symbols(gs.parse_nm(NM), ['gPlaySt', 'NoSuchSymbol'])
        self.assertIn('NoSuchSymbol', str(raised.exception))


class ProcScripts(unittest.TestCase):
    """The #236 defect: proc identity came from the PROC_NAME string at proc+0x10, and
    the decomp reuses those (E_FACE twice, bmenu three times). Script ADDRESSES are
    unique, so the table is keyed by address and resolution is exact-match only."""

    def test_collects_proc_script_symbols_by_address(self):
        got = gs.proc_scripts(gs.parse_nm(NM))
        self.assertEqual(got[0x085B1890], 'gProcScr_PlayerPhase')
        self.assertEqual(got[0x08A39190], 'ProcScr_PrepMenu')

    def test_separates_scripts_that_share_one_proc_name_string(self):
        got = gs.proc_scripts(gs.parse_nm(NM))
        self.assertEqual(got[0x085A7EF4], 'gProcScr_E_FACE')
        self.assertEqual(got[0x085A7F2C], 'gProcScr_E_FACE_ExtraFrame')

    def test_excludes_ordinary_functions(self):
        self.assertNotIn(0x0801C9E0, gs.proc_scripts(gs.parse_nm(NM)))

    def test_excludes_functions_that_merely_mention_proc(self):
        """The unanchored pattern pulled ~51 non-scripts into the table (Proc_Init,
        Proc_Start, GetSpellAssocMapAnimProcScript...). Inert, but a proc-script table
        whose entries are not proc scripts makes every reader check twice (#241)."""
        nm = NM + ('08002c08 T Proc_Init\n'
                   '08002d10 T Proc_Start\n'
                   '0808f120 T GetSpellAssocMapAnimProcScript\n')
        got = gs.proc_scripts(gs.parse_nm(nm))
        for addr in (0x08002C08, 0x08002D10, 0x0808F120):
            self.assertNotIn(addr, got)
        self.assertEqual(got[0x085B1890], 'gProcScr_PlayerPhase')

    def test_excludes_ram_symbols(self):
        self.assertNotIn(0x0202BCF0, gs.proc_scripts(gs.parse_nm(NM)))


class CodeSymbols(unittest.TestCase):
    """Idle callbacks are ordinary functions -- ~35k of them, too many for a Lua table,
    so they resolve Python-side out of symbols.json."""

    def test_collects_rom_code_symbols_by_address(self):
        got = gs.code_symbols(gs.parse_nm(NM))
        self.assertEqual(got[0x0801C9E0], 'PlayerPhase_MainIdle')
        self.assertEqual(got[0x08007CA0], 'TalkWaitForInput_OnIdle')

    def test_excludes_ram_symbols(self):
        self.assertNotIn(0x0202BCF0, gs.code_symbols(gs.parse_nm(NM)))

    def test_prefers_the_shorter_name_when_two_symbols_share_an_address(self):
        syms = gs.parse_nm('08000100 T Foo_Alias_LongName\n08000100 T Foo\n')
        self.assertEqual(gs.code_symbols(syms)[0x08000100], 'Foo')


class RenderLua(unittest.TestCase):
    def test_emits_a_do_not_edit_header_and_sorted_hex_keys(self):
        out = gs.render_lua('PROCSCR', {0x085B1890: 'gProcScr_PlayerPhase',
                                        0x08007CA0: 'Early'})
        self.assertIn('do not edit', out.splitlines()[0])
        self.assertLess(out.index('0x08007CA0'), out.index('0x085B1890'))
        self.assertIn('[0x085B1890] = "gProcScr_PlayerPhase",', out)
        self.assertTrue(out.rstrip().endswith('}'))

    def test_output_is_loadable_lua(self):
        out = gs.render_lua('PROCSCR', {0x085B1890: 'gProcScr_PlayerPhase'})
        self.assertRegex(out, r'PROCSCR = \{')



class WriteAtomic(unittest.TestCase):
    """Since #310 four scenarios start at once, and every run.sh regenerates these three
    files. A half-written symbols.lua read by a sibling is a scenario that dies for reasons
    nobody can reproduce."""

    def setUp(self):
        import shutil
        import tempfile
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.path = os.path.join(self.tmp, 'symbols.lua')

    def test_it_writes_the_whole_file(self):
        gs.write_atomic(self.path, 'SYM = {}\n')
        with open(self.path) as fh:
            self.assertEqual(fh.read(), 'SYM = {}\n')

    def test_a_failed_write_leaves_the_previous_file_intact(self):
        """The point of writing through a temp file: a reader never sees a partial one, and a
        writer that dies leaves the last good table in place."""
        gs.write_atomic(self.path, 'GOOD\n')

        class Boom(str):
            def encode(self, *a, **k):
                raise RuntimeError('disk full')

        with self.assertRaises(RuntimeError):
            gs.write_atomic(self.path, Boom('PARTIAL'))

        with open(self.path) as fh:
            self.assertEqual(fh.read(), 'GOOD\n')

    def test_the_temp_file_does_not_survive(self):
        gs.write_atomic(self.path, 'SYM = {}\n')
        self.assertEqual(os.listdir(self.tmp), ['symbols.lua'])

if __name__ == '__main__':
    unittest.main()
