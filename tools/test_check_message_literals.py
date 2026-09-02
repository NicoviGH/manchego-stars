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

    def test_the_live_tree_has_exactly_the_twelve_the_issue_names(self):
        found = hosts.literal_message_ids()
        self.assertEqual(12, len(found), found)
        self.assertEqual({'ch00': 8, 'ch01': 4},
                         {c: len([l for l in found if l.chapter == c]) for c in ('ch00', 'ch01')})
        self.assertIn(0xC25, [lit.msg_id for lit in found])

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


class MessageLiteralsAreRegistered(unittest.TestCase):
    """The ownership half: discovery finds the id, but only the registry can OWN it."""

    def _fail(self, source):
        fail = []
        check.check_message_literals_are_registered(fail, source=source)
        return fail

    def test_a_registered_literal_passes(self):
        self.assertEqual([], self._fail(REGISTERED))

    def test_an_unregistered_bare_literal_is_caught(self):
        bad = self._fail(UNREGISTERED)
        self.assertEqual(1, len(bad), bad)
        self.assertIn('0xBF4', bad[0])
        self.assertIn('ch07', bad[0])

    def test_the_complaint_names_the_tuple_to_add_it_to(self):
        self.assertIn('CH07_LITERAL_MSGS', self._fail(UNREGISTERED)[0])

    def test_the_prologue_complaint_names_PROLOGUE_LITERAL_MSGS(self):
        """ch00's tuple is not CH00_-shaped, and a guard that told the author to create
        CH00_LITERAL_MSGS would be inventing a second registry beside the one that works."""
        bad = self._fail(PROLOGUE)
        self.assertEqual(1, len(bad), bad)
        self.assertIn('0xC25', bad[0])
        self.assertIn('PROLOGUE_LITERAL_MSGS', bad[0])

    def test_a_named_id_is_none_of_this_guards_business(self):
        self.assertEqual([], self._fail(NAMED_ONLY))

    def test_a_literal_with_no_injector_must_at_least_have_a_NAME(self):
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

    def test_the_check_is_registered_in_the_drift_gate(self):
        """Defined-but-unregistered is how check_tile_changes_outlive_the_retarget shipped:
        it ran only via the test subprocess, which check_tests_pass skips whenever
        fireemblem8u/src is absent -- exactly the lightweight CI job it was meant to protect
        (decisions.md 2026-09-02)."""
        import inspect
        self.assertIn('check_message_literals_are_registered',
                      inspect.getsource(check.main))

    def test_the_static_registry_read_is_not_empty(self):
        """The claims dict is names and splats, so `literal_eval` refuses it outright. If the
        static read came back empty the guard would police nothing and say so."""
        import ast
        with open(os.path.join(check.REPO, 'tools', 'build_campaign.py'), encoding='utf-8') as fh:
            tree = ast.parse(fh.read(), 'build_campaign.py')
        claims = check._chapter_message_claims(tree, check._module_int_table(tree))
        self.assertIn('ch00', claims)
        self.assertIn(0xC25, claims['ch00'])

    def test_the_live_tree_is_clean(self):
        fail = []
        check.check_message_literals_are_registered(fail)
        self.assertEqual([], fail)


if __name__ == '__main__':
    unittest.main()
