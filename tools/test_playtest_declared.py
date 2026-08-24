#!/usr/bin/env python3
"""Tests for tools/playtest/declared.py -- chapter-declared playtest cases (#314).

Two layers, the same split test_playtest_matrix.py uses:

  * the PURE layer runs against synthetic chapter documents, so a test never reads the
    campaign, builds a ROM or launches mGBA;
  * the REAL-DATA layer asserts the shipped chapter YAML derives rows byte-identical to
    the hand-written `matrix.yaml` rows they replaced. That oracle is the whole proof
    that this is a DERIVATION and not a rewrite -- see PORTED_ORACLE below.

Run:

    python3 tools/test_playtest_declared.py
"""
import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, 'playtest'))
import declared                                        # noqa: E402


def chapter(**over):
    """A minimal chapter document carrying a `playtest:` block."""
    doc = {
        'id': 'ch05-the-elven-tomb',
        'chapter_number': 5,
        'playtest': {
            'boot': 'ch05boot',
            'cases': [{
                'name': 'ch05village',
                'proves': 'the south reliquary hands over its Dracoshield',
                'given': ['on_map'],
                'when': [{'visit': {'x': 12, 'y': 19}}],
                'then': [{'gained_item': 0x60}],
            }],
        },
    }
    doc.update(over)
    return doc


class TestRowDerivation(unittest.TestCase):
    """A case declares WHAT IT PROVES; every mechanical field is derived."""

    def test_rom_comes_from_the_chapter_boot(self):
        rows = declared.matrix_rows([chapter()], slots={'ch05': 6})
        self.assertEqual(rows['ch05village']['rom'], 'ch05boot')

    def test_host_chapter_comes_from_the_host_registry_not_the_chapter_number(self):
        # ch05 is chapter 5 and rides host slot 6. Deriving PT_HOST_CHAPTER from the
        # chapter NUMBER would boot slot 5 -- ch04's -- and every ch05 case would assert
        # against the wrong map while looking perfectly well-formed (inject/hosts.py:
        # from slot 6 on, vanilla's slot index leads the chapter number by one).
        rows = declared.matrix_rows([chapter()], slots={'ch05': 6})
        self.assertEqual(rows['ch05village']['host_chapter'], 6)

    def test_kind_defaults_to_verdict_and_is_declarable(self):
        rows = declared.matrix_rows([chapter()], slots={'ch05': 6})
        self.assertEqual(rows['ch05village']['kind'], 'verdict')
        doc = chapter()
        doc['playtest']['cases'][0]['kind'] = 'record'
        rows = declared.matrix_rows([doc], slots={'ch05': 6})
        self.assertEqual(rows['ch05village']['kind'], 'record')

    def test_a_case_may_override_the_chapter_boot(self):
        # ch05lupinbenched rides ch05lupinboot -- the only ROM with Lupin on the roster.
        doc = chapter()
        doc['playtest']['cases'][0]['boot'] = 'ch05lupinboot'
        rows = declared.matrix_rows([doc], slots={'ch05': 6})
        self.assertEqual(rows['ch05village']['rom'], 'ch05lupinboot')

    def test_a_case_with_no_name_is_an_error_not_a_silent_skip(self):
        doc = chapter()
        del doc['playtest']['cases'][0]['name']
        with self.assertRaises(declared.CaseError):
            declared.matrix_rows([doc], slots={'ch05': 6})

    def test_an_unhosted_chapter_is_an_error(self):
        # A chapter with no slot in inject/hosts.py cannot be booted at all, so a case on
        # it would inherit host_chapter 1 and silently assert against the prologue.
        with self.assertRaises(declared.CaseError):
            declared.matrix_rows([chapter()], slots={})

    def test_a_chapter_with_no_playtest_block_declares_nothing(self):
        self.assertEqual(declared.matrix_rows([{'id': 'ch09-x', 'chapter_number': 9}],
                                              slots={'ch09': 10}), {})


class TestSuiteDerivation(unittest.TestCase):
    """The chapter suite stops being hand-kept.

    HANDOFF recorded ch05's suite as "the weakest of the five" because scenarios landed in
    `gate` and nobody back-filled `suites: ch05`. A derived suite cannot fall behind.
    """

    def test_the_chapter_suite_is_every_declared_verdict_case(self):
        doc = chapter()
        doc['playtest']['cases'].append({
            'name': 'recordch05opening', 'proves': 'x', 'kind': 'record', 'lua': 'recordch05opening'})
        suites = declared.matrix_suites([doc], slots={'ch05': 6})
        self.assertEqual(suites['ch05'], ['ch05village'])


class TestEscapeHatch(unittest.TestCase):
    """Code is the exception you NAME, not the default you copy (the DECORATE lesson)."""

    def test_a_lua_case_still_derives_every_mechanical_field(self):
        doc = chapter()
        doc['playtest']['cases'] = [{'name': 'ch05arena', 'proves': 'the arena is one-shot',
                                     'lua': 'ch05arena'}]
        rows = declared.matrix_rows([doc], slots={'ch05': 6})
        self.assertEqual(rows['ch05arena']['rom'], 'ch05boot')
        self.assertEqual(rows['ch05arena']['host_chapter'], 6)

    def test_a_case_may_not_be_both_declared_and_lua(self):
        doc = chapter()
        doc['playtest']['cases'][0]['lua'] = 'ch05village'
        with self.assertRaises(declared.CaseError):
            declared.matrix_rows([doc], slots={'ch05': 6})

    def test_a_case_must_be_one_or_the_other(self):
        doc = chapter()
        doc['playtest']['cases'] = [{'name': 'ch05village', 'proves': 'x'}]
        with self.assertRaises(declared.CaseError):
            declared.matrix_rows([doc], slots={'ch05': 6})


class TestSubsumption(unittest.TestCase):
    """"Is A already covered by B" becomes computable once a case is DATA (#302 gate work).

    It was previously answerable only by a human reading two Lua functions, which is how
    ch05village sat in the merge gate fully covered by ch05reliquaries.
    """

    BIG = {'name': 'big', 'proves': 'x', 'boot': 'ch05boot', 'given': ['on_map'],
           'when': [{'visit': {'x': 5, 'y': 1}}, {'visit': {'x': 12, 'y': 19}}],
           'then': [{'gained_item': 0x70}, {'gained_item': 0x60}]}
    SMALL = {'name': 'small', 'proves': 'x', 'boot': 'ch05boot', 'given': ['on_map'],
             'when': [{'visit': {'x': 12, 'y': 19}}], 'then': [{'gained_item': 0x60}]}

    def test_a_superset_subsumes_a_subset(self):
        self.assertTrue(declared.subsumes(self.BIG, self.SMALL))

    def test_a_subset_does_not_subsume_its_superset(self):
        self.assertFalse(declared.subsumes(self.SMALL, self.BIG))

    def test_a_case_does_not_subsume_itself(self):
        self.assertFalse(declared.subsumes(self.BIG, self.BIG))

    def test_a_different_boot_is_never_subsumed(self):
        # ch05lupinbenched and ch05recruit walk the same tiles on DIFFERENT ROMs -- the
        # whole point of the pair. Ignoring the boot would delete the only run that ever
        # walks the Lupin arm.
        other = dict(self.SMALL, boot='ch05lupinboot')
        self.assertFalse(declared.subsumes(self.BIG, other))

    def test_an_assertion_the_bigger_case_does_not_make_blocks_it(self):
        other = dict(self.SMALL, then=[{'gained_item': 0x60}, {'spoke': True}])
        self.assertFalse(declared.subsumes(self.BIG, other))

    def test_an_opaque_lua_case_is_never_compared(self):
        # Guessing what a hand-written body covers is exactly the derived claim not to make.
        self.assertFalse(declared.subsumes(self.BIG, {'name': 'l', 'proves': 'x',
                                                      'boot': 'ch05boot', 'lua': 'l'}))
        self.assertFalse(declared.subsumes({'name': 'l', 'proves': 'x', 'boot': 'ch05boot',
                                            'lua': 'l'}, self.SMALL))

    def test_repeated_steps_are_counted_not_merely_present(self):
        twice = dict(self.SMALL, when=[{'visit': {'x': 12, 'y': 19}},
                                       {'visit': {'x': 12, 'y': 19}}])
        self.assertFalse(declared.subsumes(self.BIG, twice),
                         'one visit cannot cover two')

    def test_the_shipped_campaign_reports_the_known_redundancy(self):
        pairs = declared.subsumed_pairs()
        self.assertIn(('ch05reliquaries', 'ch05village', 'ch05'), pairs)


# What the three ported scenarios resolved to BEFORE the port, read off the shipped
# matrix.yaml at d4aeafc. The derivation has to reproduce these exactly: that is gate one
# of the two the port is held to (the other is a real mGBA run, diffed against its
# pre-port log). A hand-written oracle rather than a captured snapshot, so a wrong
# derivation cannot quietly re-bless itself.
PORTED_ORACLE = {
    'ch04village':     {'rom': 'ch04boot', 'host_chapter': 5, 'kind': 'verdict'},
    'ch05village':     {'rom': 'ch05boot', 'host_chapter': 6, 'kind': 'verdict'},
    'ch05reliquaries': {'rom': 'ch05boot', 'host_chapter': 6, 'kind': 'verdict'},
}


class TestPortedScenariosResolveIdentically(unittest.TestCase):
    def test_the_derivation_reproduces_the_hand_written_rows(self):
        rows = declared.matrix_rows()
        for name, want in sorted(PORTED_ORACLE.items()):
            self.assertIn(name, rows, '%s is no longer chapter-declared' % name)
            for field, value in sorted(want.items()):
                self.assertEqual(rows[name][field], value,
                                 '%s.%s drifted from the row it replaced' % (name, field))


if __name__ == '__main__':
    unittest.main(verbosity=2)
