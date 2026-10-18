#!/usr/bin/env python3
"""The wiki is the Fire Emblem Wiki's chapter page, cloned and filled from the chapter YAML and
the decomp (#487). These pin that it builds from the real repo, that every chapter gets its page
and its subpages, that open decisions stay off it, and that the numbers it prints are the ones the game produces."""
import collections
import os
import re
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import difficulty                                      # noqa: E402
import gen_wiki                                        # noqa: E402
import unit_load                                       # noqa: E402


def section(page, pid):
    return re.search(r'<section class="page" id="%s".*?</section>' % re.escape(pid), page,
                     re.S).group(0)


class TestGenWiki(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        out, cls.n = gen_wiki.build()
        with open(out, encoding='utf-8') as f:
            cls.page = f.read()
        cls.chapters = gen_wiki.chapters()

    def test_every_chapter_has_a_page_and_design_notes(self):
        for c in self.chapters:
            self.assertIn('<section class="page" id="%s"' % c['_slug'], self.page)
            self.assertIn('<section class="page" id="%s/design"' % c['_slug'], self.page)
        self.assertEqual(self.n, len(self.chapters))

    def test_sections_follow_the_wiki_s_order_and_nothing_else(self):
        # Plot, Chapter data (Character, Item, Shop, Enemy + Reinforcements, Boss), Strategy:
        # the cloned page carries only the original's sections, in its order.
        order = ['Plot', 'Chapter_data', 'Character_data', 'Item_data', 'Shop_data',
                 'Enemy_data', 'Reinforcements', 'Boss_data', 'Strategy']
        for c in self.chapters:
            got = re.findall(r'class="mw-headline" id="%s-([A-Za-z_]+)"' % c['_slug'],
                             section(self.page, c['_slug']))
            self.assertEqual(got, [x for x in order if x in got], c['_slug'])
            self.assertTrue(set(got) <= set(order), c['_slug'])

    def test_the_home_page_is_the_game_article(self):
        # The Fire Emblem Wiki's game page: Plot by act (each chapter names its `act:`),
        # Gameplay, Chapters, Characters; every chapter's story lands under its act.
        home = section(self.page, 'home')
        got = re.findall(r'class="mw-headline" id="home-([A-Za-z_]+)"', home)
        self.assertEqual([g for g in got if not g.startswith('Act_') and g in
                          ('Plot', 'Gameplay', 'Chapters', 'Characters')],
                         ['Plot', 'Gameplay', 'Chapters', 'Characters'])
        for c in self.chapters:
            self.assertTrue(c.get('act'), c['_slug'])

    def test_every_page_ends_on_the_game_navbox(self):
        # Template:Nav8's shape, at the foot of every page (#493).
        pages = re.findall(r'<section class="page".*?</section>', self.page, re.S)
        self.assertTrue(pages)
        for p in pages:
            self.assertIn('mw-collapsed navbox', p, p[:80])

    def test_lord_select_lists_ch01s_candidates(self):
        import inject.cast
        lord = section(self.page, 'lord-select')
        for uid, *_ in inject.cast._classed_cast(gen_wiki.CAMPAIGN, available_at=1)[0]:
            self.assertIn(gen_wiki.load_yaml(os.path.join(
                gen_wiki.CAMP, 'pcs', uid + '.yaml')).get('lord_pitch'), lord.replace('&#39;', "'"))

    def test_a_faceless_pid_shows_its_class_card(self):
        # GetUnitPortraitId: the grell's raw pid has no portrait, so the ROM shows the Mogall's.
        chap = next(c for c in self.chapters if c['_slug'] == 'ch03')
        grell = next(e for e in chap['enemy_units'] if e['id'] == 'grell')
        self.assertEqual(gen_wiki.rom_portrait(chap, grell).size, (80, 72))

    def test_book_characters_cite_the_book_in_trivia(self):
        for stem in ('hlin-trollbane', 'scramsax', 'sephek-kaltro', 'duvessa-shane',
                     'vellynne-harpell', 'trex', 'izobai', 'ravisin', 'dorbulgruf', 'messie',
                     'sahnar', 'basil', 'grell'):
            self.assertRegex(gen_wiki.lore_book(stem) or '', r"Rime of the Frostmaiden'' \(pp?\. ",
                             stem)

    def test_open_decisions_stay_off_the_wiki(self):
        # They live in each chapter's `open_questions` and on #486 (Nicolas, 2026-10-14).
        self.assertNotIn('id="decisions"', self.page)
        self.assertNotIn('Open questions', self.page)

    def test_twin_payload_is_read_from_the_decomp(self):
        # vanilla Ch5's village/clear gifts all reach ch05 (ADR 0049's 1:1 economy)
        ch05 = section(self.page, 'ch05/design')
        self.assertIn('ITEM_GUIDINGRING', ch05)
        self.assertNotIn('not found in ours</span>', ch05)

    def test_item_names_are_the_games_own(self):
        self.assertEqual(gen_wiki.item_name('ITEM_BOOSTER_POW'), 'Energy Ring')
        self.assertEqual(gen_wiki.our_item('iron-blade')[1], 'ITEM_BLADE_IRON')
        # FE8 keeps one name per item id: a campaign rename is what the ROM shows
        self.assertEqual(gen_wiki.rom_item_name('ITEM_VULNERARY'), 'Goodberry')


class TestEnemySlots(unittest.TestCase):
    def test_the_prologue_boss_reads_the_slot_he_rides(self):
        # The prologue is not in CHAPTER_ENEMY_PIDS: its injector rewrites O'Neill's slot for
        # Sephek (a Myrmidon, Sword C from Joshua). Reading no slot printed the bare class's
        # Sword D on his page (#493).
        chap = next(c for c in gen_wiki.chapters() if c.get('is_prologue'))
        boss = next(e for e in chap['enemy_units'] if e.get('is_boss'))
        self.assertEqual(gen_wiki.enemy_token(chap, boss), 'CHARACTER_ONEILL')


class TestStrategyNames(unittest.TestCase):
    def test_strategies_name_items_as_the_rom_does(self):
        # FE8 keeps one name per item id; where the campaign renames one (campaign.yaml
        # item_names), the vanilla name never appears in game, so prose must not use it either.
        renamed = gen_wiki.campaign_yaml().get('item_names') or {}
        vanilla = {gen_wiki.item_name(e): new for e, new in renamed.items()}
        for c in gen_wiki.chapters():
            for old, new in vanilla.items():
                self.assertNotIn(old, c.get('strategy') or '', '%s: says %r, the game says %r'
                                 % (c['_slug'], old, new))


class TestPayloadCounts(unittest.TestCase):
    def test_a_twin_item_given_twice_needs_two_of_ours(self):
        got = gen_wiki.payload_verdicts(['ITEM_ELIXIR', 'ITEM_ELIXIR', 'ITEM_TORCH'],
                                        collections.Counter({'ITEM_ELIXIR': 1}),
                                        {'ITEM_TORCH': 'kept for ch09'})
        self.assertEqual(got, ['delivered', 'missing', 'deviation'])


class TestUnitLoad(unittest.TestCase):
    """unit_load against the Fire Emblem Wiki's own Distant Blade tables (FE8 Ch9, Eirika),
    which print what the game loads in each mode."""

    def stats(self, mode, cls, level, **kw):
        got = unit_load.load(cls, level, shifts=difficulty.vanilla_chapter_shifts('FE8 Ch9'),
                             mode=mode, **kw)
        return [unit_load.show(got[s]) for s in unit_load.STATS]

    def test_a_generic_mercenary_matches_the_wiki_in_every_mode(self):
        self.assertEqual(self.stats('tutorial', 'CLASS_MERCENARY', 9),
                         ['20~22', '5~6', '9~10', '9~10', '1~2', '4~5', '0~1', '9', '5'])
        self.assertEqual(self.stats('normal', 'CLASS_MERCENARY', 9),
                         ['22~24', '6~7', '10~11', '9~11', '1~3', '4~6', '1~2', '9', '5'])
        # The wiki prints Luck 2~5 on Difficult; NextRN_N(k) is 0..k-1 (rng.c), so the
        # engine's ceiling is 4. Every other cell agrees.
        self.assertEqual(self.stats('difficult', 'CLASS_MERCENARY', 9),
                         ['25~29', '7~10', '11~14', '10~13', '2~4', '5~7', '1~3', '9', '5'])

    def test_an_unflagged_boss_loads_flat_and_takes_only_the_difficult_bonus(self):
        binks = dict(personal=difficulty.vanilla_personal_line('CHARACTER_BINKS'),
                     autolevel=False, base_level=5)
        flat = ['42', '16', '10', '8', '3', '12', '8', '13', '6']
        self.assertEqual(self.stats('tutorial', 'CLASS_WARRIOR', 5, **binks), flat)
        self.assertEqual(self.stats('normal', 'CLASS_WARRIOR', 5, **binks), flat)
        self.assertEqual(self.stats('difficult', 'CLASS_WARRIOR', 5, **binks),
                         ['44~45', '17~18', '10~11', '8~9', '3~4', '12~13', '8~9', '13', '6'])

    def test_a_promoted_generic_takes_the_promotion_bonus(self):
        # UnitAutolevel: +9 levels of class growths on Normal, +19 on Difficult (#490)
        plain = unit_load.load('CLASS_SNIPER', 1, mode='normal')
        self.assertGreater(plain['HP'][0], unit_load.class_line('CLASS_SNIPER')[0]['HP'])


if __name__ == '__main__':
    unittest.main()
