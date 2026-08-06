#!/usr/bin/env python3
"""Tests for tools/playtest/inspect_state.py -- the #236 state inspector's pure formatting
and first-divergence logic. No emulator, no ROM, no ELF: the renderer is handed the symbol
table it resolves against. Run: python3 tools/playtest/test_inspect.py
"""
import io
import os
import sys
import tempfile
import unittest
import contextlib

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import inspect_state as ins


SYMBOLS = {
    0x08007CA0: 'TalkWaitForInput_OnIdle',
    0x0801C9E0: 'PlayerPhase_MainIdle',
}

SNAPSHOT = {
    'event': 'inspect',
    'tag': 'reach_ch01-stall',
    'scenario': 'ch01',
    'state': 'transition',
    'matched_rule': 'passive_proc',
    'detail': 'std_event live (idle=event_engine)',
    'unclassified_wait': True,
    'considered': [
        {'rule': 'dialogue_wait', 'reason': 'talk_wait proc absent'},
        {'rule': 'menu', 'reason': 'menu proc absent'},
    ],
    'world': {'chapter': 2, 'turn': 0, 'faction': 0, 'host_chapter': 1},
    'procs': [
        {'slot': 3, 'script': '0x085A8858', 'script_name': 'ProcScr_StdEventEngine',
         'proc_name': 'E_config', 'step': 12, 'idle': '0x08007CA0',
         'sleep': 0, 'mark': 0, 'flags': 0, 'lock': 1, 'frozen': True},
        {'slot': 9, 'script': '0x085A7EF4', 'script_name': 'gProcScr_E_FACE',
         'proc_name': 'E_FACE', 'step': 2, 'idle': '0x00000000',
         'sleep': 0, 'mark': 0, 'flags': 0, 'lock': 0, 'frozen': False},
    ],
}


class ParseRecords(unittest.TestCase):
    """A playtest log interleaves plain lines with the JSON the harness emits."""

    def test_picks_json_events_out_of_a_mixed_log(self):
        log = ('booting to map with observed FE8 states\n'
               '{"event":"transition","state":"player_map_idle"}\n'
               'RESULT: PASS -- fine\n')
        got = ins.parse_records(log)
        self.assertEqual([r['event'] for r in got], ['transition'])

    def test_ignores_malformed_json_instead_of_raising(self):
        self.assertEqual(ins.parse_records('{"event":"transition"\nnot json\n'), [])

    def test_reads_the_frame_prefix_the_harness_actually_writes(self):
        # log() stamps every line with the frame it happened on: `[f021071] {...}`.
        log = '[f021071] {"event":"inspect","tag":"ch01-no-prep"}\n'
        self.assertEqual([r['tag'] for r in ins.parse_records(log)], ['ch01-no-prep'])

    def test_a_brace_inside_a_plain_log_line_is_not_a_record(self):
        self.assertEqual(ins.parse_records('[f001] freeze: gAnims[0]={x}\n'), [])

    def test_keeps_log_order(self):
        log = '{"event":"transition","n":1}\n{"event":"inspect","n":2}\n'
        self.assertEqual([r['n'] for r in ins.parse_records(log)], [1, 2])


class ResolveSymbol(unittest.TestCase):
    """Exact match or an honest unknown -- never a nearest-preceding guess."""

    def test_names_a_known_address(self):
        self.assertEqual(ins.resolve(SYMBOLS, '0x08007CA0'),
                         'TalkWaitForInput_OnIdle(0x08007CA0)')

    def test_reports_an_unmatched_address_as_unknown(self):
        self.assertEqual(ins.resolve(SYMBOLS, '0x08123456'), 'unknown@0x08123456')

    def test_null_is_not_an_unknown_symbol(self):
        self.assertEqual(ins.resolve(SYMBOLS, '0x00000000'), 'none')

    def test_a_thumb_pointer_resolves_to_its_function(self):
        """ARM/THUMB pointers carry bit 0 set. The Lua side masks it today, so this is
        correct only by convention -- and a raw pointer from any other caller would report
        a confident `unknown` for a symbol we have (#241)."""
        self.assertEqual(ins.resolve(SYMBOLS, '0x08007CA1'),
                         'TalkWaitForInput_OnIdle(0x08007CA0)')

    def test_a_malformed_address_is_reported_not_raised(self):
        """parse_records tolerates a truncated log; the renderer must be equally tolerant
        of one bad field, or a diagnostic tool dies on the run it exists to diagnose."""
        self.assertEqual(ins.resolve(SYMBOLS, '0xZZZZ'), 'unknown@0xZZZZ')


class SymbolTableIsMissing(unittest.TestCase):
    """An unknown must mean "this address matches no symbol", never "nobody loaded the
    symbols". Silently returning {} made every callback in the report read unknown@0x...,
    indistinguishable from a real one (#241)."""

    def test_it_says_so_on_stderr(self):
        err = io.StringIO()
        with contextlib.redirect_stderr(err):
            symbols = ins.load_symbols('/nonexistent/symbols.json')
        self.assertEqual(symbols, {})
        self.assertIn('gen_symbols.py', err.getvalue())

    def test_a_present_table_warns_about_nothing(self):
        fd, path = tempfile.mkstemp(suffix='.json')
        self.addCleanup(os.unlink, path)
        with os.fdopen(fd, 'w') as f:
            f.write('{"code": {"0x08007CA0": "TalkWaitForInput_OnIdle"}}')
        err = io.StringIO()
        with contextlib.redirect_stderr(err):
            symbols = ins.load_symbols(path)
        self.assertEqual(symbols, {0x08007CA0: 'TalkWaitForInput_OnIdle'})
        self.assertEqual(err.getvalue(), '')


class MenuWithoutItems(unittest.TestCase):
    def test_a_null_items_list_renders(self):
        """`items` present-but-null is what a truncated or in-between observation looks
        like; `.get('items', [])` returns None there and the renderer blows up."""
        self.assertIn('current=2', ins._menu_line({'current': 2, 'items': None}))


class Cli(unittest.TestCase):
    def test_symbols_may_follow_the_subcommand(self):
        """`render log --symbols X` is the order anyone types; it was rejected because
        --symbols only existed on the top-level parser."""
        fd, log = tempfile.mkstemp(suffix='.log')
        self.addCleanup(os.unlink, log)
        with os.fdopen(fd, 'w') as f:
            f.write('[f000001] {"event": "inspect", "tag": "t", "state": "transition"}\n')
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(ins.main(['render', log, '--symbols', '/nonexistent.json']), 0)

    def test_a_missing_log_is_an_error_not_a_traceback(self):
        err = io.StringIO()
        with contextlib.redirect_stderr(err):
            self.assertEqual(ins.main(['render', '/nonexistent/playtest.log']), 2)
        self.assertIn('/nonexistent/playtest.log', err.getvalue())


class RenderInspect(unittest.TestCase):
    def setUp(self):
        self.out = ins.render_inspect(SNAPSHOT, SYMBOLS)

    def test_leads_with_the_tag_and_the_verdict(self):
        self.assertIn('reach_ch01-stall', self.out)
        self.assertIn('transition', self.out)

    def test_flags_an_unclassified_wait_loudly(self):
        self.assertIn('UNCLASSIFIED WAIT', self.out)

    def test_names_the_rule_that_produced_the_verdict_and_its_detail(self):
        self.assertIn('passive_proc', self.out)
        self.assertIn('std_event live (idle=event_engine)', self.out)

    def test_lists_what_was_rejected_and_why(self):
        self.assertIn('dialogue_wait', self.out)
        self.assertIn('talk_wait proc absent', self.out)

    def test_names_procs_by_exact_script_symbol(self):
        self.assertIn('ProcScr_StdEventEngine', self.out)
        self.assertIn('gProcScr_E_FACE', self.out)

    def test_resolves_the_idle_callback_to_a_symbol(self):
        self.assertIn('TalkWaitForInput_OnIdle', self.out)

    def test_marks_the_frozen_proc(self):
        frozen = [l for l in self.out.splitlines() if 'ProcScr_StdEventEngine' in l][0]
        self.assertIn('FROZEN', frozen)
        moving = [l for l in self.out.splitlines() if 'gProcScr_E_FACE' in l][0]
        self.assertNotIn('FROZEN', moving)

    def test_carries_the_world_position(self):
        self.assertIn('chapter=2', self.out)
        self.assertIn('turn=0', self.out)

    def test_is_stable_across_renders(self):
        self.assertEqual(self.out, ins.render_inspect(SNAPSHOT, SYMBOLS))


def step(state, action, result, **kw):
    rec = {'event': 'transition', 'state': state, 'action': action, 'result': result}
    rec.update(kw)
    return rec


class FirstDivergence(unittest.TestCase):
    def test_identical_runs_do_not_diverge(self):
        run = [step('player_map_idle', 'select_unit', 'pass'),
               step('unit_selected', 'confirm_move', 'pass')]
        self.assertIsNone(ins.first_divergence(run, list(run)))

    def test_reports_the_first_differing_classification(self):
        a = [step('player_map_idle', 'select_unit', 'pass'),
             step('unit_selected', 'confirm_move', 'pass')]
        b = [step('player_map_idle', 'select_unit', 'pass'),
             step('target_selection', 'confirm_target', 'pass')]
        got = ins.first_divergence(a, b)
        self.assertEqual(got['index'], 1)
        self.assertEqual(got['field'], 'state')
        self.assertEqual(got['baseline'], 'unit_selected')
        self.assertEqual(got['candidate'], 'target_selection')

    def test_a_differing_action_diverges_even_when_the_state_matches(self):
        a = [step('unit_command_menu', 'attack', 'pass')]
        b = [step('unit_command_menu', 'wait', 'pass')]
        self.assertEqual(ins.first_divergence(a, b)['field'], 'action')

    def test_a_failed_postcondition_diverges_from_a_passing_one(self):
        a = [step('target_selection', 'confirm_target', 'pass')]
        b = [step('target_selection', 'confirm_target', 'fail:postcondition')]
        got = ins.first_divergence(a, b)
        self.assertEqual(got['field'], 'result')
        self.assertEqual(got['candidate'], 'fail:postcondition')

    def test_a_run_that_stops_early_diverges_at_the_missing_step(self):
        a = [step('player_map_idle', 'select_unit', 'pass'),
             step('unit_selected', 'confirm_move', 'pass')]
        b = [step('player_map_idle', 'select_unit', 'pass')]
        got = ins.first_divergence(a, b)
        self.assertEqual(got['index'], 1)
        self.assertEqual(got['field'], 'length')
        self.assertEqual(got['candidate'], None)

    def test_inspect_snapshots_do_not_count_as_steps(self):
        a = [step('player_map_idle', 'select_unit', 'pass')]
        b = [SNAPSHOT, step('player_map_idle', 'select_unit', 'pass')]
        self.assertIsNone(ins.first_divergence(a, b))


class FormatDivergence(unittest.TestCase):
    def test_no_divergence_says_so(self):
        self.assertIn('no divergence', ins.format_divergence(None, 'a.log', 'b.log').lower())

    def test_shows_both_sides_with_their_evidence(self):
        a = [step('unit_selected', 'confirm_move', 'pass',
                  before={'classification': 'unit_selected'},
                  after={'classification': 'player_map_idle'})]
        b = [step('target_selection', 'confirm_target', 'fail:postcondition',
                  before={'classification': 'target_selection'},
                  after={'classification': 'target_selection'})]
        out = ins.format_divergence(ins.first_divergence(a, b), 'base.log', 'cand.log')
        self.assertIn('base.log', out)
        self.assertIn('cand.log', out)
        self.assertIn('unit_selected', out)
        self.assertIn('target_selection', out)
        self.assertIn('step 0', out)


if __name__ == '__main__':
    unittest.main()
