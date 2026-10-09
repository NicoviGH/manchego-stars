#!/usr/bin/env python3
"""Tests for tools/inject/chapter_settings.py.

Run:  python3 tools/test_inject_chapter_settings.py
"""
import json
import os
import re
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from inject.namespace import stubbed
import inject.chapter_settings
import inject.decomp
import inject.hosting
import inject.paths
from inject import source as injector  # the injector's source, every file of it (#389)


# NB keep this LAST. It sat at line ~4776 of a 5723-line file, so the twelve TestCase classes
# below it -- 88 tests, including all 26 of Ch04Stage4Scenes -- were defined after the runner
# had already exited and never ran under `make test`, which is what CI executes (it runs each
# file as a SCRIPT, not via `-m unittest`, so the two disagreed silently). Found 2026-08-15.
class ChapterDifficulty(unittest.TestCase):
    """Every hosted chapter DECLARES its difficulty triple rather than inheriting the
    donor host slot's (#303).

    FE8 implements difficulty as a per-chapter enemy stat re-projection, from three
    4-bit fields on the chapter (chapterdata.h:47-49). We never wrote them, so each
    hosted chapter carried whatever its squatted slot happened to ship -- numbers tuned
    for a different chapter. ch04 was the measurable casualty: it hosts on slot 5
    (`I05`, normal malus 0) while its parity twin FE8 Ch4 carries malus 2, which put
    ch04's Normal at x1.30 against the reference, outside the +/-25% band.

    Same lesson as the goal text ids (#207) and the battle grounds: what a donor slot
    silently carries has to become a declaration.
    """

    TRIPLE = {'tutorial': 4, 'normal': 2, 'difficult': 3}

    def test_a_declared_triple_is_read_back(self):
        self.assertEqual(inject.chapter_settings.chapter_difficulty_shifts({'difficulty': dict(self.TRIPLE)}),
                         self.TRIPLE)

    def test_a_chapter_that_declares_nothing_is_refused(self):
        # The whole point: silence must not resolve to the donor's numbers.
        with self.assertRaises(SystemExit) as cm:
            inject.chapter_settings.chapter_difficulty_shifts({'id': 'ch09-undeclared'})
        self.assertIn('difficulty', str(cm.exception))

    def test_a_missing_mode_is_refused(self):
        with self.assertRaises(SystemExit):
            inject.chapter_settings.chapter_difficulty_shifts({'difficulty': {'tutorial': 4, 'normal': 2}})

    def test_a_value_past_the_four_bit_field_is_refused(self):
        # 0..15: the fields are u16 bitfields 4 wide, so 16 silently truncates to 0.
        with self.assertRaises(SystemExit):
            inject.chapter_settings.chapter_difficulty_shifts(
                {'difficulty': {'tutorial': 16, 'normal': 2, 'difficult': 3}})

    def test_a_negative_shift_is_refused(self):
        with self.assertRaises(SystemExit):
            inject.chapter_settings.chapter_difficulty_shifts(
                {'difficulty': {'tutorial': -1, 'normal': 2, 'difficult': 3}})

    def test_every_hosted_chapter_declares_one(self):
        # The registry-driven guard: a chapter added later fails here rather than
        # quietly inheriting, which is the failure mode #241 taught for host slots.
        from inject import hosts
        for chapter in hosts.hosted_chapters():
            chap = inject.hosting._load_chapter_yaml('rime-of-the-frostmaiden',
                                         inject.hosting.chapter_yaml_for(chapter.name))
            shifts = inject.chapter_settings.chapter_difficulty_shifts(chap)
            self.assertEqual(set(shifts), {'tutorial', 'normal', 'difficult'},
                             '%s declares an incomplete triple' % chapter.name)

    def test_the_write_pass_lands_each_chapter_on_its_own_host_slot(self):
        from inject import hosts
        vanilla = json.loads(inject.decomp.vanilla_decomp_text('src/data/chapter_settings.json'))
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, 'chapter_settings.json')
            with open(path, 'w', encoding='utf-8') as f:
                json.dump(vanilla, f)
            with stubbed('CHAPTER_SETTINGS_JSON', path):
                inject.chapter_settings.apply_chapter_difficulty('rime-of-the-frostmaiden')
            with open(path, encoding='utf-8') as f:
                written = json.load(f)
        for chapter in hosts.hosted_chapters():
            chap = inject.hosting._load_chapter_yaml('rime-of-the-frostmaiden',
                                         inject.hosting.chapter_yaml_for(chapter.name))
            want = inject.chapter_settings.chapter_difficulty_shifts(chap)
            slot = written['chapters'][chapter.host_index]
            self.assertEqual(slot['easyModeLevelMalus'], want['tutorial'], chapter.name)
            self.assertEqual(slot['normalModeLevelMalus'], want['normal'], chapter.name)
            self.assertEqual(slot['difficultModeLevelBonus'], want['difficult'], chapter.name)

    def test_ch04_stops_inheriting_slot_fives_missing_normal_malus(self):
        # The founding case, pinned as a number: I05 ships normal malus 0, FE8 Ch4
        # carries 2. Declaring it is what pulls ch04's Normal back inside the band.
        chap = inject.hosting._load_chapter_yaml('rime-of-the-frostmaiden',
                                     inject.hosting.chapter_yaml_for('ch04'))
        self.assertEqual(inject.chapter_settings.chapter_difficulty_shifts(chap)['normal'], 2)


class ChapterFog(unittest.TestCase):
    """#365: `initialFogLevel` was the last chapter_settings field with no total pass.

    Two chapters wrote it inline and the other five inherited whatever their squatted host
    slot shipped. That is survivable right up until it isn't: vanilla carries fog on five
    slots, one of which is SLOT 7 -- ch06's host -- and ch06's whole design is a route
    puzzle across concentric water with seven crossings and a snag. Inheriting three-tile vision
    would have hidden the map, failed nothing, and shipped.

    ch04 is the other half of the argument. It wanted fog and got it from a literal `3`
    inside its injector, so the fact that ch04 is a FOGGED CHAPTER was written down nowhere
    a reader of ch04 would look.
    """

    CAMPAIGN = 'rime-of-the-frostmaiden'

    def _chap(self, name):
        from inject import hosts
        for chapter in hosts.hosted_chapters():
            if chapter.name == name:
                return inject.hosting._load_chapter_yaml(self.CAMPAIGN,
                                             inject.hosting.chapter_yaml_for(chapter.name))
        self.fail('%s is not a hosted chapter' % name)

    def test_every_hosted_chapter_declares_its_fog(self):
        """Total, like the difficulty triple -- not "only the ones whose donor has fog"."""
        from inject import hosts
        for chapter in hosts.hosted_chapters():
            chap = inject.hosting._load_chapter_yaml(self.CAMPAIGN, inject.hosting.chapter_yaml_for(chapter.name))
            level = inject.chapter_settings.chapter_fog_level(chap)
            self.assertIsInstance(level, int, chapter.name)

    def test_ch06_declares_none_and_that_means_zero(self):
        self.assertEqual(0, inject.chapter_settings.chapter_fog_level(self._chap('ch06')))

    def test_ch04s_fog_is_declared_in_its_yaml_not_pinned_in_its_injector(self):
        """The literal that used to live in inject_ch04, now a fact about the chapter."""
        self.assertEqual(3, inject.chapter_settings.chapter_fog_level(self._chap('ch04')))

    def test_a_chapter_that_declares_nothing_is_refused(self):
        with self.assertRaises(SystemExit) as caught:
            inject.chapter_settings.chapter_fog_level({'id': 'chXX'})
        self.assertIn('fog', str(caught.exception))

    def test_a_level_wider_than_the_engine_field_is_refused(self):
        """initialFogLevel is a u8 (chapterdata.h:36), so 256 silently truncates to 0 --
        which reads as "no fog" and is the one wrong answer that looks deliberate."""
        with self.assertRaises(SystemExit):
            inject.chapter_settings.chapter_fog_level({'id': 'chXX', 'fog': 256})

    def test_a_nonsense_declaration_is_refused_rather_than_coerced(self):
        for bad in ('thick', True, 1.5, -1):
            with self.assertRaises(SystemExit):
                inject.chapter_settings.chapter_fog_level({'id': 'chXX', 'fog': bad})

    def test_the_write_pass_lands_each_chapters_declared_fog_on_its_own_slot(self):
        from inject import hosts
        vanilla = json.loads(inject.decomp.vanilla_decomp_text('src/data/chapter_settings.json'))
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, 'chapter_settings.json')
            with open(path, 'w', encoding='utf-8') as f:
                json.dump(vanilla, f)
            with stubbed('CHAPTER_SETTINGS_JSON', path):
                inject.chapter_settings.apply_chapter_fog(self.CAMPAIGN)
            with open(path, encoding='utf-8') as f:
                written = json.load(f)
        for chapter in hosts.hosted_chapters():
            chap = inject.hosting._load_chapter_yaml(self.CAMPAIGN, inject.hosting.chapter_yaml_for(chapter.name))
            self.assertEqual(inject.chapter_settings.chapter_fog_level(chap),
                             written['chapters'][chapter.host_index]['initialFogLevel'],
                             chapter.name)

    def test_ch06_stops_inheriting_slot_sevens_fog(self):
        """The founding case, pinned as the two numbers that differ."""
        from inject import hosts
        vanilla = json.loads(inject.decomp.vanilla_decomp_text('src/data/chapter_settings.json'))
        host = next(c.host_index for c in hosts.hosted_chapters() if c.name == 'ch06')
        self.assertEqual(3, vanilla['chapters'][host]['initialFogLevel'],
                         'slot 7 is supposed to be the fogged donor that made this a bug')
        self.assertEqual(0, inject.chapter_settings.chapter_fog_level(self._chap('ch06')))



class ChapterMusic(unittest.TestCase):
    """A chapter plays its vanilla TWIN's music (Nicolas, 2026-10-09). Hosted on another slot,
    it played that slot's: ch04 sits on Ch5x's and played Follow Me, and the prologue's green
    phase was Ch1's."""

    CAMPAIGN = 'rime-of-the-frostmaiden'

    def test_the_write_pass_lands_each_twins_music_on_its_host_slot(self):
        from inject import hosts
        text = inject.decomp.vanilla_decomp_text('src/data/chapter_settings.json')
        vanilla = json.loads(text)
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, 'chapter_settings.json')
            with open(path, 'w', encoding='utf-8') as f:
                json.dump(vanilla, f)
            with stubbed('CHAPTER_SETTINGS_JSON', path):
                inject.chapter_settings.apply_chapter_music(self.CAMPAIGN)
            with open(path, encoding='utf-8') as f:
                written = json.load(f)
        for chapter in hosts.hosted_chapters():
            chap = inject.hosting._load_chapter_yaml(
                self.CAMPAIGN, inject.hosting.chapter_yaml_for(chapter.name))
            twin = inject.chapter_settings.twin_settings_index(chap)
            self.assertEqual(vanilla['chapters'][twin]['bgm'],
                             written['chapters'][chapter.host_index]['bgm'], chapter.name)

    def test_each_twin_is_vanillas_own_row_by_name(self):
        """Vanilla row 5 is Ch5x, so from Ch5 on chapter N is row N+1 -- a number guess put
        ch05 on Ch5x's music. Pinned to the rows' own internal names (L00..L06)."""
        from inject import hosts
        rows = json.loads(inject.decomp.vanilla_decomp_text('src/data/chapter_settings.json'))
        for chapter in hosts.hosted_chapters():
            chap = inject.hosting._load_chapter_yaml(
                self.CAMPAIGN, inject.hosting.chapter_yaml_for(chapter.name))
            n = re.match(r'FE8 (?:Prologue|Ch(\d+))$', chap['parity_reference']).group(1)
            row = rows['chapters'][inject.chapter_settings.twin_settings_index(chap)]
            self.assertEqual('L%02d' % int(n or 0), row['internalName'], chapter.name)

    def test_ch04_stops_playing_ch5xs_follow_me(self):
        """The founding case: ch04 is hosted on Ch5x's slot, whose player phase is Follow Me."""
        rows = json.loads(inject.decomp.vanilla_decomp_text('src/data/chapter_settings.json'))
        from inject import hosts
        host = next(c.host_index for c in hosts.hosted_chapters() if c.name == 'ch04')
        self.assertEqual('I05', rows['chapters'][host]['internalName'])
        chap = inject.hosting._load_chapter_yaml(self.CAMPAIGN, inject.hosting.chapter_yaml_for('ch04'))
        self.assertNotEqual(rows['chapters'][host]['bgm']['bluePhase'],
                            inject.chapter_settings.chapter_bgm(chap)['bluePhase'])

    def test_the_pass_writes_every_bgm_leaf_the_census_says_it_owns(self):
        import inject.chapter_data as cd
        owned = sorted(f.split('.', 1)[1] for f, p in cd.OWNED_BY_PASS.items()
                       if p == 'apply_chapter_music')
        self.assertEqual(sorted(inject.chapter_settings.BGM_FIELDS), owned)
        vanilla = json.loads(inject.decomp.vanilla_decomp_text('src/data/chapter_settings.json'))
        self.assertEqual(set(inject.chapter_settings.BGM_FIELDS),
                         set(vanilla['chapters'][0]['bgm']))

    def test_a_twin_past_the_route_split_is_refused_not_guessed(self):
        with self.assertRaises(SystemExit):
            inject.chapter_settings.twin_settings_index(
                {'id': 'chXX', 'parity_reference': 'FE8 Ch10'})


if __name__ == '__main__':
    unittest.main()
