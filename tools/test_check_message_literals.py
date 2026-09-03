#!/usr/bin/env python3
"""Tests for bare-literal message-id discovery (#346).

The hole: `build_campaign.injector_message_ids` finds a message id by the NAME of the
constant holding it, so an id written as hex AT the `set_message_body` call site has no
name to be found by. Twelve exist on main -- the prologue's eight and ch01's four -- and
they reached the deadness guard only because someone grepped for them once and
hand-transcribed them into `PROLOGUE_LITERAL_MSGS` / `CH01_LITERAL_MSGS`. So the promise
in that docstring ("registering a new one is enough -- there is no second list to
remember") was false for exactly this class: the next bare literal was invisible until a
human noticed it.

`0xC25` is why it matters. It sits `0x33` above ch05's `0xBC5-0xBF2` pool, so extending
that range upward -- the obvious next move -- would have been accepted by every guard and
would have overwritten Scramsax's defeat quote.

Two halves, tested here:
  * `inject.hosts.literal_message_ids` DISCOVERS them from source, attributed to the
    injector that writes them, and `injector_message_ids` folds them in -- so deadness is
    checked with no human step at all.
  * `check.check_message_literals_are_registered` still requires the id to be CLAIMED in
    `HOSTED_CHAPTER_MESSAGE_IDS`, because discovery cannot invent an OWNER and ownership is
    what `assert_message_ids_unique` and `make chapter` headroom read.

Run: python3 tools/test_check_message_literals.py
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import check
from inject import hosts


# A miniature build_campaign.py: the writer's definition (without it `callsites` cannot bind
# a POSITIONAL msg_id, which is how all 71 real call sites pass it), one chapter's literal
# tuple, and the claims registry that gives the id an owner.
WRITER = """
def set_message_body(lines, msg_id, body, create=False):
    pass
"""

REGISTERED = WRITER + """
CH07_LITERAL_MSGS = (0xBF3, 0xBF4)
HOSTED_CHAPTER_MESSAGE_IDS = {
    'ch07': (*CH07_LITERAL_MSGS,),
}

def inject_ch07(campaign):
    set_message_body(lines, 0xBF3, body)
    set_message_body(lines, msg_id=0xBF4, body=body)
"""

UNREGISTERED = WRITER + """
CH07_LITERAL_MSGS = (0xBF3,)
HOSTED_CHAPTER_MESSAGE_IDS = {
    'ch07': (*CH07_LITERAL_MSGS,),
}

def inject_ch07(campaign):
    set_message_body(lines, 0xBF3, body)
    set_message_body(lines, 0xBF4, body)
"""

NAMED_ONLY = WRITER + """
CH07_TAUNT_MSG = 0xBF3
HOSTED_CHAPTER_MESSAGE_IDS = {
    'ch07': (CH07_TAUNT_MSG,),
}

def inject_ch07(campaign):
    set_message_body(lines, CH07_TAUNT_MSG, body)
"""

PROLOGUE = WRITER + """
PROLOGUE_LITERAL_MSGS = (0x664,)
HOSTED_CHAPTER_MESSAGE_IDS = {
    'ch00': PROLOGUE_LITERAL_MSGS,
}

def inject_prologue(campaign):
    set_message_body(lines, 0x664, body)
    set_message_body(lines, 0xC25, body)
"""

HOMELESS = WRITER + """
HOSTED_CHAPTER_MESSAGE_IDS = {'ch07': ()}

def _some_helper(lines):
    set_message_body(lines, 0xBF4, body)
"""


class LiteralMessageIdScan(unittest.TestCase):
    """The discovery half: a bare literal registers ITSELF, with the chapter that writes it."""

    def test_a_bare_literal_is_found_and_attributed(self):
        found = hosts.literal_message_ids(source=REGISTERED)
        self.assertEqual([(0xBF3, 'ch07'), (0xBF4, 'ch07')],
                         [(lit.msg_id, lit.chapter) for lit in found])

    def test_a_positional_id_is_bound_by_SIGNATURE_not_by_position_guessing(self):
        """Every real call site passes msg_id POSITIONALLY, so `grep msg_id=` finds none of
        them. `callsites` binds the argument against the definition instead."""
        found = hosts.literal_message_ids(source=REGISTERED)
        self.assertIn(0xBF3, [lit.msg_id for lit in found])

    def test_a_NAMED_id_is_not_a_literal(self):
        self.assertEqual((), hosts.literal_message_ids(source=NAMED_ONLY))

    def test_the_prologue_is_ch00(self):
        """HOSTED_CHAPTER_MESSAGE_IDS keys the prologue 'ch00' while its injector and its
        constants say PROLOGUE, so the attribution has to translate or nothing lines up."""
        self.assertEqual({'ch00'},
                         {lit.chapter for lit in hosts.literal_message_ids(source=PROLOGUE)})

    def test_a_literal_outside_every_injector_has_no_chapter(self):
        found = hosts.literal_message_ids(source=HOMELESS)
        self.assertEqual([None], [lit.chapter for lit in found])

    def test_a_source_that_does_not_define_the_writer_fails_LOUDLY(self):
        """An unresolvable signature switches positional binding OFF in `callsites.scan`, so
        this would return () for a file full of literals -- a scan that quietly stops
        scanning, which is the failure decisions.md 2026-09-02 names."""
        with self.assertRaises(ValueError):
            hosts.literal_message_ids(source='def inject_ch07(c):\n    '
                                             'set_message_body(lines, 0xBF4, body)\n')

    def test_the_live_tree_s_literals_are_all_attributed(self):
        """Count-free on purpose: a hardcoded 12 fails the moment someone adds a THIRTEENTH
        and registers it correctly, which is the behaviour this guard exists to permit."""
        found = hosts.literal_message_ids()
        self.assertTrue(found, 'the live tree writes bare literals; finding none means a broken scan')
        self.assertTrue(all(lit.chapter for lit in found),
                        [l for l in found if not l.chapter])
        self.assertIn(0xC25, [lit.msg_id for lit in found],
                      "0xC25 is the id whose invisibility motivated #346")

    def test_injector_message_ids_folds_the_literals_in(self):
        """The deadness half. With this, a block drawn over 0xC25 is refused whether or not
        anybody wrote the id down -- which is the whole ask of #346."""
        try:
            import build_campaign as bc
        except ImportError as exc:                # pragma: no cover - lean environment
            self.skipTest('build_campaign does not import here: %s' % exc)
        spent = bc.injector_message_ids()
        for lit in hosts.literal_message_ids():
            self.assertIn(lit.msg_id, spent, hex(lit.msg_id))
        self.assertTrue(bc.live_ids_in_declared_blocks(blocks={'zz': ((0xC25, 0xC25),)}),
                        'a block over the prologue\'s 0xC25 literal must be refused')


class MessageLiteralDiscoveryGuard(unittest.TestCase):
    """check.py owns DISCOVERY: the scan runs, and every hit can name an owner."""

    def _fail(self, source):
        fail = []
        check.check_message_literals_are_registered(fail, source=source)
        return fail

    def test_a_literal_inside_an_injector_is_not_this_guard_s_business(self):
        """Ownership moved to build time (#356 review). Here, an attributed literal is fine."""
        self.assertEqual([], self._fail(UNREGISTERED))

    def test_a_named_id_is_none_of_this_guards_business(self):
        self.assertEqual([], self._fail(NAMED_ONLY))

    def test_a_literal_with_no_injector_is_caught(self):
        bad = self._fail(HOMELESS)
        self.assertEqual(1, len(bad), bad)
        self.assertIn('outside every injector', bad[0])

    def test_a_broken_scan_fails_instead_of_passing_vacuously(self):
        """The live scan finding zero literals means the scan broke, not that the campaign
        stopped writing them -- and silence is what both look like from outside."""
        real = hosts.literal_message_ids
        hosts.literal_message_ids = lambda *a, **kw: ()
        try:
            fail = []
            check.check_message_literals_are_registered(fail)
        finally:
            hosts.literal_message_ids = real
        self.assertTrue(fail)
        self.assertIn('vacuously', fail[0])

    def test_a_malformed_source_is_REPORTED_not_raised(self):
        """callsites.signature turns SyntaxError into callsites.ParseError, which is not a
        SyntaxError -- so an `except (ValueError, SyntaxError)` let it escape and killed the
        whole drift gate with a traceback, skipping every check after it (#356 review)."""
        fail = self._fail('def inject_ch07(c):\n    set_message_body(lines, 0x1,\n')
        self.assertEqual(1, len(fail), fail)
        self.assertIn('cannot scan', fail[0])

    def test_the_check_is_registered_in_the_drift_gate(self):
        """Defined-but-unregistered is how check_tile_changes_outlive_the_retarget shipped:
        it ran only via the test subprocess, which check_tests_pass skips whenever
        fireemblem8u/src is absent -- exactly the lightweight CI job it was meant to protect
        (decisions.md 2026-09-02)."""
        import inspect
        self.assertIn('check_message_literals_are_registered',
                      inspect.getsource(check.main))

    def test_the_live_tree_is_clean(self):
        fail = []
        check.check_message_literals_are_registered(fail)
        self.assertEqual([], fail)


class LiteralOwnershipAtBuildTime(unittest.TestCase):
    """build_campaign owns OWNERSHIP, because there the registry is a real dict.

    The static version died in #356's review: HOSTED_CHAPTER_MESSAGE_IDS is written as
    generators, subscripts and tuple-unpacked constants, so an AST evaluator of it was wrong
    in both directions -- it missed ch04's 0x9C3/0x9C6 and demanded a registration that makes
    assert_message_ids_unique exit, and it over-collected ch05's box counts and passed an
    unclaimed 0x13.
    """

    def setUp(self):
        try:
            import build_campaign as bc
        except ImportError as exc:                # pragma: no cover - lean environment
            self.skipTest('build_campaign does not import here: %s' % exc)
        self.bc = bc
        self.lit = hosts.MessageLiteral

    def test_a_claimed_literal_passes(self):
        self.bc.assert_literals_are_claimed(
            literals=[self.lit(0xBF4, 'ch07', 10)], claims={'ch07': (0xBF4,)})

    def test_an_unclaimed_literal_exits_the_BUILD(self):
        with self.assertRaises(SystemExit) as caught:
            self.bc.assert_literals_are_claimed(
                literals=[self.lit(0xBF4, 'ch07', 10)], claims={'ch07': (0x1,)})
        self.assertIn('0xBF4', str(caught.exception))
        self.assertIn('CH07_LITERAL_MSGS', str(caught.exception))

    def test_the_prologue_complaint_names_PROLOGUE_LITERAL_MSGS(self):
        """ch00's tuple is not CH00_-shaped, and telling the author to create CH00_LITERAL_MSGS
        would invent a second registry beside the one that works."""
        with self.assertRaises(SystemExit) as caught:
            self.bc.assert_literals_are_claimed(
                literals=[self.lit(0xC25, 'ch00', 10)], claims={'ch00': ()})
        self.assertIn('PROLOGUE_LITERAL_MSGS', str(caught.exception))

    def test_an_unattributed_literal_is_left_to_the_discovery_guard(self):
        self.bc.assert_literals_are_claimed(
            literals=[self.lit(0xBF4, None, 10)], claims={})

    def test_the_LIVE_tree_passes_against_the_REAL_registry(self):
        """The whole point of moving here: ch04's tuple-unpacked claims resolve exactly."""
        self.bc.assert_literals_are_claimed()

    def test_it_runs_in_the_build(self):
        import inspect
        self.assertIn('assert_literals_are_claimed', inspect.getsource(self.bc.main))


if __name__ == '__main__':
    unittest.main()
