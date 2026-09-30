#!/usr/bin/env python3
"""Tests for tools/inject/map_sprites.py.

Run:  python3 tools/test_inject_map_sprites.py
"""
import os
import re
import shutil
import sys
import tempfile
import unittest

from PIL import Image

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import inject.decomp
import inject.map_sprites
from inject import source as injector  # the injector's source, every file of it (#389)


class CastPaletteBankSurvivesEveryRosterScreen(unittest.TestCase):
    """The cast map-sprite palette lives in the purple OBJ bank (0x0B), which vanilla
    treats as scratch: several screens call ApplyUnitSpritePalettes() and then
    immediately ZERO that bank, because no vanilla unit renders from it. A zeroed
    16-colour bank draws every index as colour 0 -- our cast come out as correctly
    shaped BLACK SILHOUETTES (#218; the same failure was fixed once for Pick Units).

    The idiom is spelled differently per screen (`PAL_OBJ(0x0B)` in prep_unitselect,
    `gPaletteBuffer + 0x1B0` in unitlistscreen), so it must be listed per site rather
    than grepped for -- hence PURPLE_BANK_BLANKERS, which is what these tests pin.
    """

    def test_every_known_blanker_names_a_real_decomp_site(self):
        """Each entry must match the CURRENT vanilla source, read from HEAD -- the
        working tree is a build artifact of our own injections."""
        for path, orig, _ in inject.map_sprites.PURPLE_BANK_BLANKERS:
            vanilla = inject.decomp.vanilla_decomp_text(os.path.relpath(path, inject.decomp.DECOMP))
            self.assertIn(orig, vanilla,
                          '%s no longer contains its purple-bank fill verbatim'
                          % os.path.basename(path))

    def test_the_unit_list_screen_is_covered(self):
        """The regression this class exists for: the Character screen players open
        constantly blanked the whole cast (#218)."""
        sites = [os.path.basename(p) for p, _, _ in inject.map_sprites.PURPLE_BANK_BLANKERS]
        self.assertIn('unitlistscreen.c', sites)
        self.assertIn('prep_unitselect.c', sites)

    def test_each_patch_drops_the_fill_and_keeps_the_palette_load(self):
        """The fix is to delete the zeroing, NOT to reorder or re-load: whatever
        ApplyUnitSpritePalettes just put in bank 0x0B is already correct."""
        for path, orig, hooked in inject.map_sprites.PURPLE_BANK_BLANKERS:
            where = os.path.basename(path)
            self.assertIn('ApplyUnitSpritePalettes();', orig, where)
            self.assertIn('ApplyUnitSpritePalettes();', hooked, where)
            self.assertNotIn('CpuFastFill', hooked,
                             '%s must DROP the fill, not re-spell it' % where)
            self.assertIn('/*', hooked, '%s: say WHY the fill is gone' % where)

    def test_the_hook_rejects_a_site_that_drifted(self):
        """A decomp bump that reworks one of these screens must FAIL the build loudly,
        not silently leave that screen's roster black."""
        body = injector.def_source('_drop_purple_bank_fills')
        self.assertIn('sys.exit', body)


class PreRecruitVariant(unittest.TestCase):
    """A cast member on the field BEFORE it joins you (ch04's Lupin: red as the pack's
    leader, the finalized grey once Marty's parley brings him over; ch05's Basil green and
    Sahnar red until the tomb's two Talks).

    The failure this guards is the Trex bug's sibling: a charId-keyed cast-palette
    override is unconditional, so without the faction check Lupin renders in his bespoke
    grey while he is an ENEMY -- and FE reads grey as "already acted".
    """
    CAMPAIGN = 'rime-of-the-frostmaiden'
    # Every cast member placed on a NON-BLUE side before its recruit talk. The value is the
    # cast index carrying the unit's BODY mass -- the one that has to land on the faction
    # ramp, or the unit does not change colour when it joins.
    ON_FIELD_BEFORE_JOINING = {'lupin': (2, 3), 'basil': (10,), 'sahnar': (1, 10)}

    def test_every_pre_recruit_unit_covers_each_index_it_uses(self):
        ms = os.path.join(inject.decomp.REPO, 'campaigns', self.CAMPAIGN, 'map_sprites')
        for uid, body in self.ON_FIELD_BEFORE_JOINING.items():
            roles = inject.map_sprites.pre_recruit_roles(self.CAMPAIGN, uid)
            self.assertIsNotNone(
                roles, '%s.yaml must declare art.map_sprite.pre_recruit_roles' % uid)
            for stem in (uid + '.png', uid + '_mu.png'):
                used = {v for v in Image.open(os.path.join(ms, stem)).getdata() if v}
                self.assertTrue(used <= set(roles), '%s uses undeclared cast indices %s'
                                % (stem, sorted(used - set(roles))))
            # The body must land on the faction ramp (7-10) -- that is what makes it read red.
            self.assertTrue({roles[i] for i in body} & set(range(7, 11)),
                            '%s: no body index on the faction ramp -- it would not change '
                            'colour by side' % uid)

    def test_a_plain_cast_member_has_no_variant(self):
        self.assertIsNone(inject.map_sprites.pre_recruit_roles(self.CAMPAIGN, 'braulo'))

    def test_remap_indices_rewrites_by_role_and_rejects_an_undeclared_index(self):
        tmp = tempfile.mkdtemp(prefix='prv_')
        try:
            src, out = os.path.join(tmp, 's.png'), os.path.join(tmp, 'o.png')
            pal = os.path.join(tmp, 'p.png')
            for path, data in ((src, [0, 1, 3, 11]), (pal, list(range(16)))):
                im = Image.new('P', (len(data), 1))
                im.putpalette([0, 0, 0] * 16)
                im.putdata(data)
                im.save(path)
            inject.map_sprites._remap_indices(src, {1: 15, 3: 9, 11: 13}, pal, out)
            self.assertEqual(list(Image.open(out).getdata()), [0, 15, 9, 13])
            with self.assertRaises(SystemExit) as cm:          # index 11 not declared
                inject.map_sprites._remap_indices(src, {1: 15, 3: 9}, pal, out)
            self.assertIn('11', str(cm.exception))
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_every_override_hook_consults_the_variant_before_the_cast_override(self):
        src = injector.injector_source()
        self.assertIn('gPreRecruitVariant', src)
        # The lookup is gated on faction: a JOINED unit must fall through to the cast look.
        self.assertIn('UNIT_FACTION(%s) != FACTION_BLUE', inject.map_sprites._pre_recruit_lookup('%s'))
        for expr in ('unit', 'proc->unit'):
            self.assertIn('gPreRecruitVariant', inject.map_sprites._pre_recruit_lookup(expr))
        # Sprite + walk return the variant; the palette instead SKIPS the purple bank so
        # GetUnitSpritePalette falls through to the faction switch.
        self.assertIn('return prv->smsId;', src)
        self.assertIn('return prv->muImg;', src)
        self.assertIn('if (prv == 0) {', src)

    def test_the_lookup_is_c89_declarations_first(self):
        # agbcc (GCC 2.95.1) rejects mid-block declarations; AGENTS.md coding conventions.
        body = [ln.strip() for ln in inject.map_sprites._pre_recruit_lookup('unit').splitlines() if ln.strip()]
        self.assertTrue(body[0].startswith('struct PreRecruitVariant * prv'))
        self.assertNotIn('//', inject.map_sprites._pre_recruit_lookup('unit'))

    def test_the_lookup_reuses_the_caller_s_charId_and_shadows_nothing(self):
        """Every hook already computes the charId for its own table scan, and GetMuImg
        walks its override table with a cursor called `it` -- so the lookup must not
        recompute UNIT_CHAR_ID into a second local, nor name its cursor `it`."""
        c = inject.map_sprites._pre_recruit_lookup('proc->unit')
        self.assertIn('prvIt->charId == charId', c)
        self.assertEqual(c.count('UNIT_CHAR_ID'), 0, 'charId is the caller\'s to compute')
        self.assertNotIn(' it ', c)
        self.assertNotIn('it++', c.replace('prvIt++', ''))
        # Callers with a differently-named charId can say so.
        self.assertIn('prvIt->charId == cid', inject.map_sprites._pre_recruit_lookup('unit', char_var='cid'))

    def test_every_hook_defines_charId_before_the_lookup_uses_it(self):
        """C89 + the reuse above: `int charId = ...` must precede the emitted lookup in
        each of the three hooks, or the generated source will not compile."""
        for fn in ('_inject_sms_override_hook', '_inject_mu_override_hook',
                   '_inject_palette_bank_hook'):
            body = injector.def_source(fn)
            self.assertLess(body.index('int charId = UNIT_CHAR_ID'),
                            body.index('_pre_recruit_lookup('),
                            '%s must set charId before the pre-recruit lookup' % fn)


if __name__ == '__main__':
    unittest.main()
