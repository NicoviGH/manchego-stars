#!/usr/bin/env python3
"""Tests for tools/inject/hosts.py.

Run:  python3 tools/test_inject_hosts.py
"""
import os
import re
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import inject.hosts


class HostedChapterEnumeration(unittest.TestCase):
    """Which chapters are hosted must be DISCOVERED, not listed by hand.

    HostChapterEventGroup below is the guard written after the ch04 disaster, and it
    iterated a hand-written tuple of (HOST_INDEX, EVENT_GROUP) pairs. A hand-written
    list does not extend: ch05 would have been the first chapter NOT covered by the very
    test written to prevent that class of failure -- and ch05 hosts deeper into the slot
    divergence than ch04 did, since vanilla's slot index stops tracking chapter number
    at 4. Enumerating from the registry's constants closes that (#138).

    The registry itself moved to inject/hosts.py so a CI job without Pillow can lint it;
    its behaviour (collisions, missing groups, self-enrolment) is tested in tools/
    test_hosts.py. What is asserted HERE is that every chapter
    the injector injects is enrolled in it (#241).
    """

    def test_finds_every_currently_hosted_chapter(self):
        got = {c.name: c.host_index for c in inject.hosts.hosted_chapters()}
        self.assertEqual(got, {'prologue': inject.hosts.PROLOGUE_HOST_INDEX,
                               'ch01': inject.hosts.CH01_HOST_INDEX, 'ch02': inject.hosts.CH02_HOST_INDEX,
                               'ch03': inject.hosts.CH03_HOST_INDEX, 'ch04': inject.hosts.CH04_HOST_INDEX,
                               'ch05': inject.hosts.CH05_HOST_INDEX, 'ch06': inject.hosts.CH06_HOST_INDEX})

    def test_each_entry_carries_the_event_group_its_injector_fills(self):
        groups = {c.name: c.event_group for c in inject.hosts.hosted_chapters()}
        self.assertEqual(groups['ch04'], inject.hosts.CH04_EVENT_GROUP)
        self.assertEqual(groups['ch01'], inject.hosts.CH01_EVENT_GROUP)
        self.assertEqual(groups['prologue'], inject.hosts.PROLOGUE_EVENT_GROUP)

    def test_it_is_ordered_by_chapter_number(self):
        """Not by name -- 'ch01' sorts before 'prologue', and a name sort against a
        sorted() scan is a test that cannot fail."""
        self.assertEqual([c.name for c in inject.hosts.hosted_chapters()],
                         ['prologue', 'ch01', 'ch02', 'ch03', 'ch04', 'ch05', 'ch06'])

    def test_every_injector_in_this_module_is_enrolled(self):
        """Discovery only covers a chapter that spells its constants right. An
        inject_ch06 with a typo'd CH06_HOST_INDEX would be silently unhosted, and every
        guard built on the registry would pass with one chapter fewer."""
        self.assertEqual(inject.hosts.undeclared_injectors(), [])


if __name__ == '__main__':
    unittest.main()
