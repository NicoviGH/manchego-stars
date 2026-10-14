#!/usr/bin/env python3
"""inject.unit_art is the one answer to "what does this unit look like" (#491): the injector's
passes take their members from it, and every other reader asks it. These pin that it covers every
path the passes used to decide on their own, in the order they claim SMS ids."""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import inject.cast                                     # noqa: E402
import inject.map_sprites                              # noqa: E402
import inject.portraits                                # noqa: E402
import inject.unit_art as art                          # noqa: E402

CAMPAIGN = 'rime-of-the-frostmaiden'


class Registry(unittest.TestCase):
    def test_cast_sprites_follow_the_portrait_map(self):
        # SMS ids are claimed in this order, so the order is part of the build.
        order = list(inject.cast.PORTRAIT_MAP)
        got = [s.uid for s in art.cast_sprites(CAMPAIGN)]
        self.assertEqual(got, [u for u in order if u in got])

    def test_every_declared_map_sprite_has_an_answer(self):
        # The wiring guard's own list: art declared in YAML with a committed sheet. Each must
        # resolve here, or a reader would draw the stock class sprite (the white moose, twice).
        sheets = os.path.join(art.REPO, 'campaigns', CAMPAIGN, 'map_sprites')
        declared = [u for u in inject.map_sprites.declared_map_sprite_units(CAMPAIGN)
                    if os.path.isfile(os.path.join(sheets, u + '.png'))]
        self.assertTrue(declared)
        for uid in declared:
            self.assertIsNotNone(art.unit_sprite(CAMPAIGN, 'ch05', uid=uid), uid)

    def test_the_palette_rules(self):
        self.assertEqual(art.unit_sprite(CAMPAIGN, 'ch05', uid='ravisin').palette, 'cast')
        self.assertEqual(art.unit_sprite(CAMPAIGN, 'ch05', uid='white-moose').palette, 'cast')
        self.assertEqual(art.unit_sprite(CAMPAIGN, 'ch00', uid='hlin-trollbane').palette,
                         'faction')
        self.assertEqual(art.unit_sprite(CAMPAIGN, 'ch03', uid='trex').palette, 'remap')
        self.assertEqual(art.unit_sprite(CAMPAIGN, 'ch02', uid='chwinga-mote').palette, 'remap')
        # a class reskin is the chapter's, by token
        self.assertEqual(art.unit_sprite(CAMPAIGN, 'ch01', token='soldier').kind, 'reskin')
        self.assertIsNone(art.unit_sprite(CAMPAIGN, 'ch02', token='soldier'))

    def test_every_sprite_draws(self):
        sprites = (art.cast_sprites(CAMPAIGN) + art.guest_sprites(CAMPAIGN)
                   + art.neutral_sprites(CAMPAIGN) + [art.chwinga_sprite(CAMPAIGN)]
                   + list(art.reskin_sprites(CAMPAIGN).values()))
        for s in sprites:
            frame = art.idle_frame(CAMPAIGN, s, 'enemy')
            self.assertTrue(frame.getbbox(), s.uid)
        self.assertIsNotNone(art.class_sprite('CLASS_SOLDIER', 'enemy'))


class Busts(unittest.TestCase):
    def test_dressed_slots_are_the_registry(self):
        self.assertEqual(inject.portraits.dressed_portrait_slots(CAMPAIGN),
                         sorted({b.slot for b in art.busts(CAMPAIGN)}))

    def test_every_bust_kind_is_present(self):
        kinds = {b.kind for b in art.busts(CAMPAIGN)}
        self.assertEqual(kinds, {'cast', 'guest', 'chwinga', 'visit', 'arena'})

    def test_a_unit_s_bust_is_what_the_build_dresses(self):
        self.assertEqual(art.unit_bust(CAMPAIGN, 'sephek-kaltro').size, (96, 80))
        self.assertEqual(art.unit_bust(CAMPAIGN, 'chwinga-mote').size, (96, 80))


if __name__ == '__main__':
    unittest.main()
