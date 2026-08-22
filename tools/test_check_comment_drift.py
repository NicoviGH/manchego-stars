#!/usr/bin/env python3
"""Tests for the comment-drift guards in tools/check.py (2026-07-02 ADR "Comments
are testimony, code is evidence").

The incident being pinned: a stale build_campaign.py header ("zeroed personal
growths ... pure class rate") outlived the donor-parity code that replaced it and
got copied into an ADR as fact. Two gaps let it survive: check_no_dead_concepts
scanned docs only (never code comments), and the registered growth patterns were
too narrow to match the comment's actual phrasing. These tests hold both fixes.

Run: python3 tools/test_check_comment_drift.py
"""
import os
import re
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import check


DEAD_PAT = re.compile('|'.join(check.DEAD_CONCEPTS), re.I)

# The exact stale comment text from the incident (build_campaign.py pre-fix).
INCIDENT_LINE = ('# and zeroed personal growths (so the unit grows at its pure '
                 'class rate). When')


class DeadConceptPatterns(unittest.TestCase):
    def test_the_incident_comment_is_now_caught(self):
        # both retired phrasings in the one line; either alone must fire
        self.assertIsNotNone(DEAD_PAT.search(INCIDENT_LINE))
        self.assertIsNotNone(DEAD_PAT.search('zeroed personal growths'))
        self.assertIsNotNone(DEAD_PAT.search('grows at its pure class rate'))

    def test_the_original_narrow_phrasings_still_fire(self):
        self.assertIsNotNone(DEAD_PAT.search('zeroed growths'))
        self.assertIsNotNone(DEAD_PAT.search('pure-class growth'))

    def test_live_donor_vocabulary_is_not_flagged(self):
        for ok in ('growths copied verbatim from the growth donor',
                   'the donor personal bases',
                   'class growths from data_classes.c',):
            self.assertIsNone(DEAD_PAT.search(ok), ok)


class HandwrittenSourceScan(unittest.TestCase):
    """check_no_dead_concepts must scan code comments, not just docs."""

    def _with_planted_file(self, contents, suffix='.py'):
        tmp = tempfile.NamedTemporaryFile('w', suffix=suffix, delete=False,
                                          dir=os.path.dirname(os.path.abspath(__file__)))
        tmp.write(contents)
        tmp.close()
        return tmp.name

    def test_dead_concept_in_a_code_comment_is_flagged(self):
        path = self._with_planted_file('# legacy: zeroed personal growths here\n')
        try:
            orig_docs, orig_src = check._docs, check._handwritten_sources
            check._docs = lambda: []
            check._handwritten_sources = lambda: [path]
            fail = []
            check.check_no_dead_concepts(fail)
            self.assertEqual(len(fail), 1)
            self.assertIn('zeroed personal growths', fail[0])
        finally:
            check._docs, check._handwritten_sources = orig_docs, orig_src
            os.unlink(path)

    def test_the_repo_scan_globs_cover_the_incident_file(self):
        sources = [os.path.relpath(p, check.REPO) for p in check._handwritten_sources()]
        self.assertIn('tools/build_campaign.py', sources)
        self.assertIn('tools/playtest/harness.lua', sources)
        self.assertNotIn('tools/check.py', sources)   # hosts the registry; exempt

    def test_the_live_repo_is_clean(self):
        fail = []
        check.check_no_dead_concepts(fail)
        self.assertEqual(fail, [])


class DanglingRefs(unittest.TestCase):
    def _run_on(self, contents):
        tmp = tempfile.NamedTemporaryFile('w', suffix='.py', delete=False,
                                          dir=os.path.dirname(os.path.abspath(__file__)))
        tmp.write(contents)
        tmp.close()
        try:
            orig_docs, orig_src = check._docs, check._handwritten_sources
            check._docs = lambda: []
            check._handwritten_sources = lambda: [tmp.name]
            fail = []
            check.check_tool_refs_exist(fail)
            return fail
        finally:
            check._docs, check._handwritten_sources = orig_docs, orig_src
            os.unlink(tmp.name)

    def test_a_dangling_tool_ref_in_a_comment_is_flagged(self):
        fail = self._run_on('# see tools/zzz-does-not-exist.py for the old flow\n')
        self.assertEqual(len(fail), 1)
        self.assertIn('tools/zzz-does-not-exist.py', fail[0])

    def test_a_dangling_doc_ref_is_flagged(self):
        fail = self._run_on('# rationale: docs/zzz-retired-plan.md\n')
        self.assertEqual(len(fail), 1)
        self.assertIn('docs/zzz-retired-plan.md', fail[0])

    def test_a_real_tool_and_doc_pass(self):
        self.assertEqual(self._run_on(
            '# see tools/build_campaign.py + docs/decisions.md\n'), [])

    def test_decomp_internal_paths_do_not_false_positive(self):
        # "texttools/textdecoder.py" must not read as tools/textdecoder.py
        # (the FP that surfaced the moment the scan was extended to code)
        self.assertEqual(self._run_on(
            '# decodes via scripts/texttools/textdecoder.py in the decomp\n'), [])

    def test_gitignored_generated_targets_are_declared_artifacts(self):
        # symbols.lua is generated by gen_symbols.py and gitignored -- a reference
        # to it is a build-artifact pointer, not rot
        self.assertEqual(self._run_on('# emits tools/playtest/symbols.lua\n'), [])

    def test_the_live_repo_is_clean(self):
        fail = []
        check.check_tool_refs_exist(fail)
        self.assertEqual(fail, [])


class WrapWidthsArePixels(unittest.TestCase):
    """`_wrap_fe_lines`/`_script_to_message` take a PIXEL budget. They used to take a CHARACTER
    count, and the numbers overlap -- 29 is a legal pixel budget and a legal character count --
    so a stale call site still runs, still passes every test, and silently wraps a scene to
    seven characters a line (ch05's moose beat, 2026-08-21). A parameter that changed MEANING
    rather than name is invisible to the compiler, to the tests, and to grep. Hence a guard.
    """

    def _fail(self, source):
        fail = []
        check.check_wrap_widths_are_pixels(fail, sources={'x.py': source})
        return fail

    def test_a_bare_character_width_is_rejected(self):
        self.assertTrue(self._fail("_wrap_fe_lines(text, 29)"))
        self.assertTrue(self._fail("_script_to_message(beat, staging, width=42)"))

    def test_a_positional_character_width_is_rejected_too(self):
        """The one that shipped: no `width=` for a text search to find."""
        bad = self._fail("_ch05_opening_body(script, slot, what, podiums, fid, 29)")
        self.assertTrue(bad)
        self.assertIn('29', bad[0])

    def test_a_named_budget_is_accepted(self):
        self.assertEqual([], self._fail(
            "_wrap_fe_lines(text, fe8_talk_font.TALK_BUDGET_PX)"))
        self.assertEqual([], self._fail(
            "_script_to_message(beat, staging, width=fe8_talk_font.BATTLE_QUOTE_BUDGET_PX)"))

    def test_a_character_width_is_allowed_when_it_SAYS_it_is_characters(self):
        """The lord-select card is a 20-column panel drawn by its own font. Declaring the
        measure at the call site is what makes a small number honest rather than stale."""
        self.assertEqual([], self._fail("_wrap_fe_lines(text, width=20, measure=len)"))

    def test_a_forwarded_width_is_not_a_literal_and_is_left_alone(self):
        self.assertEqual([], self._fail("_wrap_fe_lines(text, width, measure)"))

    def test_the_live_tree_is_clean(self):
        fail = []
        check.check_wrap_widths_are_pixels(fail)
        self.assertEqual([], fail)


class VanillaReadsComeFromHEAD(unittest.TestCase):
    """A decomp file the build PATCHES holds OUR text after any `make`, so reading it from the
    working tree and calling the result "vanilla" is self-deception that reads as evidence.

    This has now bitten three times: `vanilla_scene.py` (fixed in `46f8b12`, and #25 still
    carries an open item to re-mine every number taken before it), `difficulty.py` (which
    warns about it in prose), and a 2026-08-21 session that read the GENERATED `events_info.s`
    and reasoned about our own injected output as if it were the reference. `bc.vanilla_decomp_text`
    has existed the whole time; nothing made anyone use it.
    """

    def _fail(self, source):
        fail = []
        check.check_vanilla_reads_come_from_head(fail, sources={'x.py': source})
        return fail

    def test_opening_a_patched_decomp_file_directly_is_rejected(self):
        bad = self._fail("open(os.path.join(DECOMP, 'texts/texts.txt'))")
        self.assertTrue(bad)
        self.assertIn('texts/texts.txt', bad[0])

    def test_the_helper_is_named_in_the_complaint(self):
        self.assertIn('vanilla_decomp_text', self._fail("open(DECOMP + '/texts/texts.txt')")[0])

    def test_going_through_the_helper_is_accepted(self):
        self.assertEqual([], self._fail("vanilla_decomp_text('texts/texts.txt')"))

    def test_an_unpatched_decomp_file_is_none_of_this_guards_business(self):
        """Most of the decomp is never touched by the build and reads fine from disk.
        (`src/bmmap.c` looks like a fine example and is NOT one -- it is on the patched list.)"""
        self.assertEqual([], self._fail("open(os.path.join(DECOMP, 'src/eventscr.c'))"))

    def test_a_deliberate_current_tree_read_can_SAY_so(self):
        """The map editor has to see the maps WE registered. Marking the line is the price --
        it turns a silent assumption into a claim someone made and can be challenged on."""
        self.assertEqual([], self._fail(
            "open(os.path.join(DECOMP, 'texts/texts.txt'))  # CURRENT-TREE: ours on purpose"))

    def test_the_live_tree_is_clean(self):
        fail = []
        check.check_vanilla_reads_come_from_head(fail)
        self.assertEqual([], fail)


if __name__ == '__main__':
    unittest.main()
