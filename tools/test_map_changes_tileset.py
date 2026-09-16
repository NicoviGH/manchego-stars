"""Regression tests for #374: a chapter's scripted tile changes resolve their replacement
metatiles from THAT chapter's own map, never from a tileset named in the code.

#371 made `build_campaign.map_tileset(meta)` the one place the rule
`meta.get('tileset', WINTER_TILESET)` lives, and claimed every caller used it. Three did not.
`ch02_map_changes` and `ch04_map_changes` resolved their metatiles from `WINTER_TILESET`
outright; `ch05_map_changes` from a `CH05_TILESET` constant, which is the same hardcode
wearing a better name. All three were CORRECT for the wrong reason: ch02's and ch04's maps
happen to be snowy-bern and ch05's happens to be port-or-town-winter.

What the wrong reason would cost if a chapter were ever repainted onto another tileset: its
scripted changes -- ch02's sacked huts, ch04's falling snag and closing village doors, ch05's
desecrated reliquaries -- would resolve their replacement metatiles from the WRONG terrain
table, and `check_documented_tileset` would stay green throughout, because it compares the
chapter YAML with the sidecar and neither of those is what these sites were reading.

**These tests assert the ROUTE, not the tile numbers**, and that is deliberate. The numbers
are proven unchanged by #374's output diff (all three emitted change lists byte-identical
before and after). They cannot be asserted against a *different* real tileset here, because
`_drawn_block` and `_snowy_metatile_for` `sys.exit` when a tileset cannot express a terrain
with painted art -- pointing ch02 at port-or-town-winter ends the process instead of
returning different tiles. A sidecar naming a tileset that is not on disk is the clean
discriminator: that call can only fail if the sidecar is what got read.
"""
import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import build_campaign as bc
import campaign_chapters

MAPS = os.path.join(bc.REPO, 'campaigns', campaign_chapters.CAMPAIGN, 'maps')

# Every site that emits a `map_changes_asm` change list, with the layout whose sidecar names
# the table it must resolve against. A fourth chapter's map changes belong in this tuple.
SITES = (('ch02', bc.ch02_map_changes, bc.CH02_LAYOUT),
         ('ch04', bc.ch04_map_changes, bc.CH04_LAYOUT),
         ('ch05', bc.ch05_map_changes, bc.CH05_LAYOUT))


def _maps_dir_naming(tmp, stem, tileset):
    """A maps_dir that IS the campaign's, except `<stem>.json` names `tileset`.

    `tileset=None` writes the sidecar with no `tileset` key at all -- the shape ch00-ch02's
    sidecars predate the field in. It is written here rather than read off a live sidecar on
    purpose: `compile_layout` stamps the key on every export, so re-importing a map through
    the documented pipeline would turn a test that pins a live sidecar as keyless red on a
    correct build.
    """
    os.symlink(os.path.join(MAPS, 'tilesets'), os.path.join(tmp, 'tilesets'))
    with open(os.path.join(MAPS, stem + '.json'), encoding='utf-8') as fh:
        meta = json.load(fh)
    if tileset is None:
        meta.pop('tileset', None)
    else:
        meta['tileset'] = tileset
    with open(os.path.join(tmp, stem + '.json'), 'w', encoding='utf-8') as fh:
        json.dump(meta, fh)
    return tmp


class MapChangesReadTheirOwnChaptersSidecar(unittest.TestCase):

    def test_every_site_resolves_the_tileset_its_own_sidecar_names(self):
        """The bug itself: a site that names its own tileset cannot see this at all."""
        for short, changes_for, layout in SITES:
            with self.subTest(short):
                with tempfile.TemporaryDirectory() as tmp:
                    maps = _maps_dir_naming(tmp, layout[1], 'not-a-vendored-tileset')
                    with self.assertRaises(FileNotFoundError) as caught:
                        changes_for(campaign_chapters.load(short), maps)
                self.assertIn('not-a-vendored-tileset', str(caught.exception))

    def test_a_keyless_sidecar_resolves_exactly_as_naming_the_winter_set_does(self):
        """Pins the case the hardcode got right, and the reason it got it right.

        ch00-ch02's sidecars predate the `tileset` key, so reading the sidecar has to arrive
        at the DEFAULT `map_tileset` documents -- a keyless one must not become a crash or a
        different table. Equivalence with an explicit `snowy-bern` is the assertion, rather
        than a tile number nobody would recognise.
        """
        chap = campaign_chapters.load('ch02')
        stem = bc.CH02_LAYOUT[1]
        with tempfile.TemporaryDirectory() as a, tempfile.TemporaryDirectory() as b:
            keyless = bc.ch02_map_changes(chap, _maps_dir_naming(a, stem, None))
            explicit = bc.ch02_map_changes(chap, _maps_dir_naming(b, stem, bc.WINTER_TILESET))
        self.assertEqual(keyless, explicit)

    def test_each_site_asks_layout_sidecar_for_its_own_chapters_stem(self):
        """One function owns where a sidecar lives, and these sites go through it.

        Asserting what `_layout_sidecar` returns would only restate its body. What is worth
        holding is that each site CONSULTS it, and with its own chapter's stem -- a site that
        went back to inlining the path, or reached for another chapter's, fails here.
        """
        for short, changes_for, layout in SITES:
            with self.subTest(short):
                seen = []
                real = bc._layout_sidecar
                bc._layout_sidecar = lambda d, stem: seen.append(stem) or real(d, stem)
                try:
                    changes_for(campaign_chapters.load(short), MAPS)
                finally:
                    bc._layout_sidecar = real
                self.assertEqual(seen, [layout[1]])


if __name__ == '__main__':
    unittest.main()
