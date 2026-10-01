"""Map (overworld) sprites (#38): the cast's standing and moving map sprites.
"""
import os
import re
import shutil
import sys
import tempfile

from PIL import Image

import chapter_schema
from yaml_loader import yaml_load
import map_sprite_tool
from inject.cast import classed_cast, load_unit, SCRIPTED_NEUTRAL_SPRITES
from inject.chapter_ids import CH02_CHWINGA, CH02_CHWINGA_SPRITE_SRC, PROLOGUE_GUEST_SPRITES
from inject.decomp import BMUNIT_C, REPO
from inject.paths import (
    BMUDISP_C, MOVE_GFX_DIR, MU_C, PREP_UNITSELECT_C, UNIT_ICON_MOVE_C, UNIT_ICON_MOVE_S,
    UNIT_ICON_POINTER_H, UNIT_ICON_WAIT_C, UNIT_ICON_WAIT_S, UNITLISTSCREEN_C, WAIT_GFX_DIR)
from inject.sms import _write_wait_row, claim_sms_id


def _inject_sms_override_hook():
    """Patch GetUnitSMSId to consult the build-injected per-character override table
    before falling back to the unit's class map sprite."""
    with open(BMUNIT_C, encoding='utf-8') as f:
        text = f.read()
    orig = ('int GetUnitSMSId(struct Unit* unit) {\n'
            '    if (!(unit->state & US_IN_BALLISTA))\n'
            '        return unit->pClassData->SMSId;\n')
    hooked = (
        'extern unsigned short gMapSpriteOverride[];\n'
        + PRE_RECRUIT_STRUCT
        + 'extern struct PreRecruitVariant gPreRecruitVariant[];\n\n'
        'int GetUnitSMSId(struct Unit* unit) {\n'
        '    if (!(unit->state & US_IN_BALLISTA)) {\n'
        '        /* Campaign per-character map-sprite override (build-injected; the\n'
        '         * table is empty in vanilla). Lets a cast member wear a custom\n'
        '         * overworld sprite its stock class -- and any enemy of that class\n'
        '         * -- does not. A cast member who has not JOINED yet wears his\n'
        '         * pre-recruit sheet instead (drawn for his side\'s palette). */\n'
        '        const unsigned short * mso = gMapSpriteOverride;\n'
        '        int charId = UNIT_CHAR_ID(unit);\n'
        + _pre_recruit_lookup('unit', '        ')
        + '        if (prv != 0)\n'
        '            return prv->smsId;\n'
        '        while (*mso != 0xFFFF) {\n'
        '            if (mso[0] == charId)\n'
        '                return mso[1];\n'
        '            mso += 2;\n'
        '        }\n'
        '        return unit->pClassData->SMSId;\n'
        '    }\n')
    if orig not in text:
        sys.exit('ERROR: GetUnitSMSId not in expected vanilla form in %s' % BMUNIT_C)
    with open(BMUNIT_C, 'w', encoding='utf-8') as f:
        f.write(text.replace(orig, hooked, 1))


def _inject_mu_override_hook():
    """Patch GetMuImg to return a per-character custom MU (hover/walk) sheet before
    the class default, reusing the class motion script (only the graphics change)."""
    with open(MU_C, encoding='utf-8') as f:
        text = f.read()
    orig = ('const void * GetMuImg(struct MuProc * proc)\n'
            '{\n'
            '    return gMuInfoTable[proc->jid - 1].img;\n'
            '}\n')
    hooked = (
        'struct CharMuImg { unsigned short charId; const void * img; };\n'
        'extern struct CharMuImg gMuImgOverride[];\n'
        + PRE_RECRUIT_STRUCT
        + 'extern struct PreRecruitVariant gPreRecruitVariant[];\n\n'
        'const void * GetMuImg(struct MuProc * proc)\n'
        '{\n'
        '    /* Campaign per-character MU (hover/walk) sprite override (build-injected;\n'
        '     * empty in vanilla). Reuses the class motion script -- graphics only. The\n'
        '     * pre-recruit walk takes precedence while the unit has not joined you, so\n'
        '     * moving does not flip him back to his recruited colours. */\n'
        '    if (proc->unit) {\n'
        '        struct CharMuImg * it = gMuImgOverride;\n'
        '        int charId = UNIT_CHAR_ID(proc->unit);\n'
        + _pre_recruit_lookup('proc->unit', '        ')
        + '        if (prv != 0)\n'
        '            return prv->muImg;\n'
        '        while (it->charId != 0) {\n'
        '            if (it->charId == charId)\n'
        '                return it->img;\n'
        '            it++;\n'
        '        }\n'
        '    }\n'
        '    return gMuInfoTable[proc->jid - 1].img;\n'
        '}\n')
    if orig not in text:
        sys.exit('ERROR: GetMuImg not in expected vanilla form in %s' % MU_C)
    text = text.replace(orig, hooked, 1)

    # StartMu decompresses the MU graphics inside StartMuInternal -- BEFORE it sets
    # proc->unit. So the GetMuImg override (which keys on proc->unit) sees no unit on
    # that first load and falls back to the class sheet. Reload the graphics once
    # proc->unit is set so the per-character override actually applies.
    su_orig = ('    proc->unit = unit;\n'
               '    proc->cam_b = true;\n'
               '    return proc;\n')
    su_hooked = ('    proc->unit = unit;\n'
                 '    proc->cam_b = true;\n'
                 '    /* reload graphics now that proc->unit is set, so a per-character\n'
                 '     * MU override (GetMuImg) replaces the class sheet loaded above. */\n'
                 '    Decompress(GetMuImg(proc), GetMuImgBufById(proc->config->slot));\n'
                 '    return proc;\n')
    # Both StartMu and StartMuExt share this exact tail (StartMuInternal then set
    # proc->unit); patch both so any MU spawn honours the override.
    if su_orig not in text:
        sys.exit('ERROR: StartMu not in expected vanilla form in %s' % MU_C)
    text = text.replace(su_orig, su_hooked)

    with open(MU_C, 'w', encoding='utf-8') as f:
        f.write(text)


def _read_cast_palette(path):
    """Read cast_palette.png (indexed) -> 16 GBA15 u16 colours (index 0 transparent).
    Pads short palettes with black; errors if any pixel USES an index above 15 (a
    carried-but-unused longer palette, e.g. PIL's padded 256, is tolerated -- only
    the first 16 entries are read)."""
    im = Image.open(path)
    if im.mode != 'P':
        sys.exit('ERROR: %s must be indexed (mode P) so it defines the cast palette' % path)
    raw = im.getpalette() or []
    n = min(len(raw) // 3, 256)
    used = max((px for px in im.getdata()), default=0) + 1
    if used > 16:
        sys.exit('ERROR: %s uses %d palette indices; the cast bank holds 16' % (path, used))
    out = []
    for i in range(16):
        r, g, b = (raw[3 * i], raw[3 * i + 1], raw[3 * i + 2]) if i < n else (0, 0, 0)
        out.append((r >> 3) | ((g >> 3) << 5) | ((b >> 3) << 10))
    # The engine loads this 16-colour block into the OBJ palette bank shifted one slot high:
    # empirically (rainbow test), every sprite index k displayed cast colour k-1. Pre-rotate
    # the palette up by one so each colour lands on its intended index (k -> cast[k]).
    return out[1:] + out[:1]


# Screens that load the unit-sprite palettes and then immediately ZERO the purple OBJ bank
# (0x0B). In vanilla that bank is scratch -- no vanilla unit renders from it -- but our custom
# cast map sprites do, and a zeroed 16-colour bank draws every index as colour 0, so the cast
# come out as correctly shaped BLACK SILHOUETTES (#218). Every entry is (file, exact vanilla
# text, replacement); the fill is DELETED, never re-spelled, because ApplyUnitSpritePalettes
# has already left the correct cast palette in the bank.
#
# This is a LIST and not a grep because the same idiom is spelled differently per screen --
# `PAL_OBJ(0x0B)` in prep_unitselect, the raw `gPaletteBuffer + 0x1B0` (0x100 + 0x0B*0x10) in
# unitlistscreen. Missing the second spelling is exactly how the Pick Units fix failed to
# generalise to the Character screen. A new roster screen goes here, not in a new hook.
PURPLE_BANK_BLANKERS = (
    (PREP_UNITSELECT_C,                                  # PrepUnit_InitSMS -- Pick Units
     '    ApplyUnitSpritePalettes();\n'
     '    CpuFastFill(0, PAL_OBJ(0x0B), 0x20);\n',
     '    ApplyUnitSpritePalettes();\n'
     '    /* Manchego Stars: vanilla zeros the purple OBJ bank (0x0B) here -- unused in\n'
     '     * vanilla prep -- but our custom cast map sprites render from it, so keep the\n'
     '     * cast palette ApplyUnitSpritePalettes just loaded instead of blanking it\n'
     '     * (else the roster goes black). */\n'),
    (UNITLISTSCREEN_C,                                   # UnitList_Init -- the Character list
     '    ApplyUnitSpritePalettes();\n'
     '\n'
     '    CpuFastFill(0, gPaletteBuffer + 0x1B0, PLTT_SIZE_4BPP);\n',
     '    ApplyUnitSpritePalettes();\n'
     '\n'
     '    /* Manchego Stars (#218): same blanking as PrepUnit_InitSMS, spelled as a raw\n'
     '     * gPaletteBuffer offset -- 0x1B0 == 0x100 + 0x0B*0x10 == OBJ bank 0x0B. The\n'
     '     * unit list draws each row with PutUnitSprite, so zeroing the cast bank here\n'
     '     * turned the whole roster into black silhouettes. */\n'),
)


def _drop_purple_bank_fills():
    """Delete every vanilla "zero the purple OBJ bank" fill listed in PURPLE_BANK_BLANKERS.

    Fails the build loudly if a site no longer matches verbatim: a decomp bump that reworks
    one of these screens must not silently leave that screen's roster black."""
    for path, orig, hooked in PURPLE_BANK_BLANKERS:
        with open(path, encoding='utf-8') as f:
            text = f.read()
        if orig not in text:
            sys.exit('ERROR: purple-bank (0x0B) fill not in expected form in %s -- the cast '
                     'map-sprite palette would be blanked on that screen (#218)' % path)
        with open(path, 'w', encoding='utf-8') as f:
            f.write(text.replace(orig, hooked, 1))


def _inject_palette_bank_hook():
    """Patch bmudisp.c so the custom cast share a bespoke palette in the campaign-unused
    purple OBJ bank (0xB / OBJPAL_UNITSPRITE_PURPLE), leaving the shared player palette
    (blue bank) untouched -- so the not-yet-custom cast still render correctly:
      * GetUnitSpritePalette -- per-character override returning the purple bank before
        the faction switch. StartMu uses this too, so it covers idle + hover/walk; the
        grey "acted" tint is handled upstream in GetUnitDisplayedSpritePalette.
      * ApplyUnitSpritePalettes -- load gCastMapPalette into the purple bank (replacing
        the single-player Light-Rune load; Light Rune is an unused DUMMY item).

    Loading the bank is only half the job: several screens blank it again right after.
    _drop_purple_bank_fills (PURPLE_BANK_BLANKERS) is what keeps it loaded."""
    with open(BMUDISP_C, encoding='utf-8') as f:
        text = f.read()

    gsp_orig = ('int GetUnitSpritePalette(const struct Unit * unit)\n'
                '{\n'
                '    switch (UNIT_FACTION(unit)) {\n')
    gsp_hooked = (
        'extern unsigned short gMapPaletteOverride[];\n'
        + PRE_RECRUIT_STRUCT
        + 'extern struct PreRecruitVariant gPreRecruitVariant[];\n\n'
        'int GetUnitSpritePalette(const struct Unit * unit)\n'
        '{\n'
        '    /* Campaign per-character map-palette override (build-injected; empty in\n'
        '     * vanilla). Custom cast wear a bespoke palette in the purple bank so the\n'
        '     * shared player (blue) palette stays untouched -- but a cast member who\n'
        '     * has not JOINED yet must read as his SIDE (FE colours an enemy red), so\n'
        '     * he skips the override and falls through to the faction switch, wearing\n'
        '     * the pre-recruit sheet drawn for those standard palettes. */\n'
        '    const unsigned short * mp = gMapPaletteOverride;\n'
        '    int charId = UNIT_CHAR_ID(unit);\n'
        + _pre_recruit_lookup('unit')
        + '    if (prv == 0) {\n'
        '        while (*mp != 0xFFFF) {\n'
        '            if (*mp == charId)\n'
        '                return OBJPAL_UNITSPRITE_PURPLE;\n'
        '            mp++;\n'
        '        }\n'
        '    }\n'
        '    switch (UNIT_FACTION(unit)) {\n')
    if gsp_orig not in text:
        sys.exit('ERROR: GetUnitSpritePalette not in expected vanilla form in %s' % BMUDISP_C)
    text = text.replace(gsp_orig, gsp_hooked, 1)

    au_sig_orig = 'void ApplyUnitSpritePalettes(void)\n{\n'
    au_sig_hooked = ('extern unsigned short gCastMapPalette[];\n\n'
                     'void ApplyUnitSpritePalettes(void)\n{\n')
    if au_sig_orig not in text:
        sys.exit('ERROR: ApplyUnitSpritePalettes not in expected vanilla form in %s' % BMUDISP_C)
    text = text.replace(au_sig_orig, au_sig_hooked, 1)

    au_orig = ('    else\n'
               '        ApplyPalette(gPal_LightRune, 0x10 + OBJPAL_UNITSPRITE_PURPLE);\n')
    au_hooked = ('    else\n'
                 '        /* Manchego Stars: custom cast share a bespoke 16-colour palette\n'
                 '         * in the (campaign-unused) purple bank; vanilla loads the unused\n'
                 '         * Light Rune palette here. */\n'
                 '        ApplyPalette(gCastMapPalette, 0x10 + OBJPAL_UNITSPRITE_PURPLE);\n')
    if au_orig not in text:
        sys.exit('ERROR: ApplyUnitSpritePalettes Light-Rune load not found in %s' % BMUDISP_C)
    text = text.replace(au_orig, au_hooked, 1)

    with open(BMUDISP_C, 'w', encoding='utf-8') as f:
        f.write(text)

    _drop_purple_bank_fills()


def _inject_cast_palette(palette_u16, char_slots, extra_char_ids=()):
    """Emit gCastMapPalette (the bespoke 16-colour bank) + gMapPaletteOverride (the
    charIds that wear it, 0xFFFF-terminated) into the kept .data file, then patch the
    bmudisp palette hooks. char_slots = portrait-slot names (-> CHARACTER_<SLOT>);
    extra_char_ids = RAW charId literals for units with no portrait slot (scripted
    neutrals, which wear this palette precisely because they never change faction)."""
    with open(UNIT_ICON_WAIT_C, encoding='utf-8') as f:
        wait_c = f.read()
    if 'constants/characters.h' not in wait_c:
        wait_c = wait_c.replace('#include "unit_icon_data.h"',
                                '#include "unit_icon_data.h"\n#include "constants/characters.h"', 1)
    pal = ', '.join('0x%04X' % c for c in palette_u16)
    ov = '\n'.join(['\tCHARACTER_%s,' % s.upper() for s in char_slots]
                   + ['\t%s,' % c for c in extra_char_ids])
    wait_c += ('\n/* injected: bespoke cast map-sprite palette (loaded into the purple OBJ\n'
               ' * bank) + the charIds that wear it (0xFFFF-terminated). Non-const so they\n'
               ' * share unit_icon_wait_table\'s kept .data section. */\n'
               'unsigned short gCastMapPalette[16] = { %s };\n' % pal
               + 'unsigned short gMapPaletteOverride[] = {\n' + ov + '\n\t0xFFFF\n};\n')
    with open(UNIT_ICON_WAIT_C, 'w', encoding='utf-8') as f:
        f.write(wait_c)
    _inject_palette_bank_hook()


# Cast members rendered through the SIDE (faction) palette -- green as an NPC, then the
# standard blue PLAYER palette once recruited -- instead of the bespoke cast OBJ palette.
# Their custom SHAPE still ships (SMS + MU overrides), but the sheet is remapped onto the
# donor class's standard SMS role layout (cf. enemy reskins / the ch02 chwinga) and the
# unit is kept OUT of gMapPaletteOverride, so GetUnitSpritePalette falls through to the
# faction switch and tints it per side. Needed for a unit that CHANGES faction colour in
# play: Trex stands GREEN, then the talk-recruit CUSA flips him to the BLUE player palette
# (#23). A charId-keyed cast override is unconditional -- it would pin one colour, so a
# green Trex would wrongly render in his blue player palette (Nicolas, 2026-07-10).
FACTION_TINTED_CAST = frozenset({'trex'})


def inject_map_sprites(campaign, verbose=True):
    """Give cast members a custom overworld sprite distinct from their class.

    Two sheets per character, both optional and added one at a time (no asset -> the
    unit keeps its stock-class sprite; stock classes and vanilla enemies untouched):
      * map_sprites/<id>.png      -> IDLE (wait sheet): a custom SMS slot (id 107+)
        plus a GetUnitSMSId per-character override.
      * map_sprites/<id>_mu.png   -> HOVER/WALK (MU sheet, 32x480): a custom move sheet
        plus a GetMuImg per-character override (reuses the class motion script)."""
    asset_dir = os.path.join(REPO, 'campaigns', campaign, 'map_sprites')
    # An id is claimed only for a member that actually HAS a sheet, i.e. only where a wait
    # row is about to be written -- see claim_sms_id (#227).
    idle = [(uid, slot, cls, claim_sms_id()) for (uid, slot, cls, _) in classed_cast(campaign)
            if os.path.isfile(os.path.join(asset_dir, uid + '.png'))]

    # Cold-open guests (PROLOGUE_GUEST_SPRITES) get the same SMS/MU overrides but render
    # through FE8's standard player palette -- so they are kept out of custom_slots (no
    # cast-palette override) below.
    guest_idle, guest_bases = [], {}
    for uid, slot, cls, base in PROLOGUE_GUEST_SPRITES:
        if os.path.isfile(os.path.join(asset_dir, uid + '.png')):
            guest_idle.append((uid, slot, cls, claim_sms_id()))
            guest_bases[uid] = base

    if not idle and not guest_idle:
        if verbose:
            print('  (no map_sprites/*.png assets yet; cast keep their class sprites)')
        return

    # MU (hover/walk) sheet per idle character: a committed <id>_mu.png if hand-authored,
    # else a static "glide" sheet synthesized from the finished idle frame so a MOVING
    # unit keeps its custom sprite instead of reverting to the stock class one (idle-only
    # decision -- map_sprite_tool.synth_mu_sheet). Synthesized sheets go to a temp dir so
    # no derived asset lands in the working tree; the single source of truth is the idle.
    # Faction-tinted cast (Trex): remap the cast-palette idle + committed walk onto the
    # donor class's standard SMS role layout so the faction switch tints them (green NPC ->
    # blue player on recruit). Same remap as enemy reskins, using the donor WAIT sheet's
    # palette for BOTH sheets so idle/walk share role indices. Temp dir -> no derived asset
    # in the tree (single source of truth stays map_sprites/<id>.png).
    tinted_idle_src, tinted_mu_src, tint_tmp = {}, {}, None
    for uid, slot, cls, sms in idle:
        if uid not in FACTION_TINTED_CAST:
            continue
        if tint_tmp is None:
            tint_tmp = tempfile.mkdtemp(prefix='manchego_tint_')
        donor_png = os.path.join(WAIT_GFX_DIR,
                                 'unit_icon_wait_%s_sheet.png' % _donor_base(campaign, uid))
        r_idle = os.path.join(tint_tmp, uid + '.png')
        map_sprite_tool.remap_sms_palette(os.path.join(asset_dir, uid + '.png'), donor_png, r_idle)
        tinted_idle_src[uid] = r_idle
        committed_mu = os.path.join(asset_dir, uid + '_mu.png')
        if os.path.isfile(committed_mu):
            r_mu = os.path.join(tint_tmp, uid + '_mu.png')
            map_sprite_tool.remap_sms_palette(committed_mu, donor_png, r_mu)
            tinted_mu_src[uid] = r_mu

    mu, mu_tmp = [], None
    for uid, slot, cls, sms in idle:
        if uid in tinted_mu_src:                     # faction-tinted committed walk (remapped)
            mu.append((uid, slot, cls, tinted_mu_src[uid]))
            continue
        committed = os.path.join(asset_dir, uid + '_mu.png')
        if uid not in FACTION_TINTED_CAST and os.path.isfile(committed):
            mu.append((uid, slot, cls, committed))
            continue
        if mu_tmp is None:
            mu_tmp = tempfile.mkdtemp(prefix='manchego_mu_')
        src = os.path.join(mu_tmp, uid + '_mu.png')
        nudge = ((load_unit(campaign, uid).get('art') or {}).get('map_sprite') or {}).get(
            'glide_nudge', 0)
        # A tinted unit with no committed walk glides from its REMAPPED role idle (so the
        # glide tints too); everyone else glides from their raw cast-palette idle.
        idle_for_synth = tinted_idle_src.get(uid, os.path.join(asset_dir, uid + '.png'))
        map_sprite_tool.synth_mu_sheet(idle_for_synth,
                                       _donor_base(campaign, uid), src,
                                       y_nudge=nudge, verbose=verbose)
        mu.append((uid, slot, cls, src))

    # Guests must ship a committed hover/walk sheet (no synth path -- that machinery reads
    # the cast palette / unit YAML, neither of which a standard-palette guest carries).
    guest_mu = []
    for uid, slot, cls, sms in guest_idle:
        committed = os.path.join(asset_dir, uid + '_mu.png')
        if not os.path.isfile(committed):
            sys.exit('ERROR: guest sprite %s needs a committed map_sprites/%s_mu.png '
                     '(hover/walk sheet; guests have no synth path)' % (uid, uid))
        guest_mu.append((uid, slot, cls, committed))

    pointer_externs = []
    _inject_idle_sprites(campaign, asset_dir, idle + guest_idle, pointer_externs, guest_bases,
                         src_override=tinted_idle_src)
    _inject_mu_sprites(mu + guest_mu, pointer_externs)
    # Second look for a cast member who is on the field BEFORE he joins you (appends its
    # own wait rows, so it must follow the cast/guest rows that name their own SMS ids).
    _inject_pre_recruit_variants(campaign, idle, pointer_externs, verbose=verbose)
    # Scripted neutrals (ch04's white moose): custom art on a unit that is not cast, so
    # classed_cast never sees it. Must follow the cast/guest passes -- it appends its own
    # wait rows and reaches into the override tables those passes emit.
    neutral_ids = _inject_scripted_neutral_sprites(campaign, asset_dir, pointer_externs,
                                                   verbose=verbose)
    if pointer_externs:
        with open(UNIT_ICON_POINTER_H, 'a', encoding='utf-8') as f:
            f.write('\n/* Manchego Stars custom map sprites (#38) */\n'
                    + '\n'.join(pointer_externs) + '\n')

    # Any cast with a custom sprite (idle and/or MU) wears the bespoke cast palette in
    # its own OBJ bank -- its sheet is drawn to the cast-palette indices, so it must be
    # viewed through that palette (decisions.md Art & Audio).
    # Faction-tinted cast wear the side palette, not the cast override -> excluded here.
    custom_slots = [slot for uid, slot, _, _ in idle if uid not in FACTION_TINTED_CAST]
    custom_slots += [slot for uid, slot, _, _ in mu
                     if uid not in FACTION_TINTED_CAST and slot not in custom_slots]
    if custom_slots or neutral_ids:
        pal_png = os.path.join(asset_dir, 'cast_palette.png')
        if not os.path.isfile(pal_png):
            sys.exit('ERROR: custom map sprites need campaigns/%s/map_sprites/cast_palette.png'
                     % campaign)
        # Scripted neutrals join the override by RAW charId -- they have no portrait slot.
        _inject_cast_palette(_read_cast_palette(pal_png), custom_slots,
                             extra_char_ids=[cid for _, cid, _ in neutral_ids])

    # ch02 green chwinga: reskin minor NPC slots with Sclorbo's chwinga map sprite, tinted
    # by the green faction palette (no bespoke palette -- they're green faction). Runs here
    # because inject_map_sprites owns the gMapSpriteOverride / gMuImgOverride tables.
    _inject_ch02_chwinga_sprites(campaign, verbose=verbose)

    # Everything declared + committed must have landed in one of the passes above.
    assert_declared_map_sprites_injected(campaign, {uid for uid, _, _, _ in idle + guest_idle}
                                         | {uid for uid, _, _, _ in mu + guest_mu}
                                         | {uid for uid, _, _ in neutral_ids}
                                         | {CH02_CHWINGA_SPRITE_SRC})

    if verbose:
        guest_uids = {uid for uid, _, _, _ in guest_idle}
        for uid, slot, class_enum, sms in idle + guest_idle:
            tag = ' [guest, std palette]' if uid in guest_uids else ''
            print('  %-14s -> idle SMS %d (%s)%s' % (uid, sms, slot, tag))
        for uid, slot, class_enum, src in mu + guest_mu:
            kind = 'committed' if os.path.dirname(src) == asset_dir else 'glide'
            print('  %-14s -> hover/walk MU sheet (%s, %s)' % (uid, slot, kind))
        if custom_slots:
            print('  cast palette -> purple OBJ bank for: %s' % ', '.join(custom_slots))


def _insert_table_head(path, decl, rows_text):
    """Insert `rows_text` right after a C array's `decl ... = {` opener (front of the
    table). Used to add entries to an already-emitted, terminator-closed override table
    without keying on the terminator (which several tables in the same file share)."""
    with open(path, encoding='utf-8') as f:
        text = f.read()
    m = re.search(re.escape(decl) + r'[^\n]*\{\n', text)
    if not m:
        sys.exit('ERROR: %r opener not found in %s' % (decl, path))
    text = text[:m.end()] + rows_text + text[m.end():]
    with open(path, 'w', encoding='utf-8') as f:
        f.write(text)


# A charId-keyed cast override is UNCONDITIONAL, so a cast member placed on a hostile/NPC
# side renders in his bespoke cast palette regardless -- the Trex bug (decisions.md Art &
# Audio). FACTION_TINTED_CAST solves it by giving up the cast palette entirely, which is
# right when the joined look may be the side's standard blue. It is NOT right when the
# joined look IS the bespoke sheet (Lupin: red as the pack's leader, the finalized grey
# once recruited). So: a SECOND sheet in the standard SMS role layout, worn only while the
# unit is not on the player side, derived at build time from the cast sheet by an index
# remap (art.map_sprite.pre_recruit_roles) -- single source of truth stays the cast sheet.
# The engine picks between them in the three per-character override hooks below.
PRE_RECRUIT_STRUCT = ('struct PreRecruitVariant { unsigned short charId; '
                      'unsigned short smsId; const void * muImg; };\n')


def _pre_recruit_lookup(unit_expr, indent='    ', char_var='charId'):
    """C (agbcc/C89: declarations first) resolving `unit_expr` to its pre-recruit variant
    row, or NULL when the unit has joined / has no variant.

    `char_var` names an int the CALLER has already set to the unit's charId -- all three
    override hooks compute one for their own table scan, so the lookup reuses it rather
    than recomputing UNIT_CHAR_ID into a second local."""
    i = indent
    return (i + 'struct PreRecruitVariant * prv = 0;\n'
            + i + 'if (UNIT_FACTION(%s) != FACTION_BLUE) {\n' % unit_expr
            + i + '    struct PreRecruitVariant * prvIt = gPreRecruitVariant;\n'
            + i + '    while (prvIt->charId != 0) {\n'
            + i + '        if (prvIt->charId == %s) {\n' % char_var
            + i + '            prv = prvIt;\n'
            + i + '            break;\n'
            + i + '        }\n'
            + i + '        prvIt++;\n'
            + i + '    }\n'
            + i + '}\n')


def pre_recruit_roles(campaign, uid):
    """{cast index: standard SMS role index} for a unit that stands on a non-player side
    before it joins, or None. Declared in the unit YAML (art.map_sprite.pre_recruit_roles)."""
    ms = ((load_unit(campaign, uid).get('art') or {}).get('map_sprite') or {})
    roles = ms.get('pre_recruit_roles')
    return {int(k): int(v) for k, v in roles.items()} if roles else None


def _inject_pre_recruit_variants(campaign, idle, pointer_externs, verbose=True):
    """Emit the pre-recruit (not-yet-joined) sheets + gPreRecruitVariant for every cast
    member declaring `pre_recruit_roles`. Runs inside inject_map_sprites, which owns the
    override tables; the table is always emitted (empty == vanilla behaviour)."""
    rows = []
    for uid, slot, _cls, _sms in idle:
        roles = pre_recruit_roles(campaign, uid)
        if not roles:
            continue
        asset_dir = os.path.join(REPO, 'campaigns', campaign, 'map_sprites')
        donor = _donor_base(campaign, uid)
        _, dfw, dfh = map_sprite_tool.donor_sms_geometry(donor)
        sym = 'unit_icon_wait_manchego_%s_pre_sheet' % uid.replace('-', '_')
        move_sym = 'unit_icon_move_manchego_%s_pre_sheet' % uid.replace('-', '_')
        wait_png = os.path.join(WAIT_GFX_DIR, sym + '.png')
        move_png = os.path.join(MOVE_GFX_DIR, move_sym + '.png')
        donor_png = os.path.join(WAIT_GFX_DIR, 'unit_icon_wait_%s_sheet.png' % donor)
        for src, dst in ((uid + '.png', wait_png), (uid + '_mu.png', move_png)):
            src = os.path.join(asset_dir, src)
            if not os.path.isfile(src):
                sys.exit('ERROR: %s declares pre_recruit_roles but has no map_sprites/%s'
                         % (uid, os.path.basename(src)))
            _remap_indices(src, roles, donor_png, dst)
        map_sprite_tool.validate_mu_sheet(move_png)
        macro, _, _, _ = map_sprite_tool.sheet_info(wait_png, (dfw, dfh))

        sms = claim_sms_id()
        _write_wait_row(sms,
            '\t{0, %s, %s}, // %d %s (pre-recruit)' % (macro, sym, sms, uid))
        with open(UNIT_ICON_WAIT_S, 'a', encoding='utf-8') as f:
            f.write('\n/* Manchego Stars pre-recruit idle sprite: %s (#24) */\n'
                    '\t.global %s\n%s:\n\t.incbin "graphics/unit_icon/wait/%s.4bpp.lz"\n'
                    '\t.align 2, 0\n' % (uid, sym, sym, sym))
        with open(UNIT_ICON_MOVE_S, 'a', encoding='utf-8') as f:
            f.write('\n/* Manchego Stars pre-recruit hover/walk (MU) sprite: %s (#24) */\n'
                    '\t.global %s\n%s:\n\t.incbin "graphics/unit_icon/move/%s.4bpp.lz"\n'
                    '\t.align 2, 0\n' % (uid, move_sym, move_sym, move_sym))
        pointer_externs += ['extern char %s[];' % sym, 'extern char %s[];' % move_sym]
        rows.append('\t{CHARACTER_%s, %d, %s},' % (slot.upper(), sms, move_sym))
        if verbose:
            print('  %-12s -> pre-recruit sheet (SMS %d) worn until he joins you' % (uid, sms))

    with open(UNIT_ICON_MOVE_C, encoding='utf-8') as f:
        move_c = f.read()
    move_c += ('\n/* injected: pre-recruit (not-yet-joined) map sprites -- a cast member on a\n'
               ' * hostile/NPC side wears THIS standard-palette sheet under his side\'s\n'
               ' * faction colour instead of the bespoke cast palette. charId 0 terminates;\n'
               ' * an empty table is exactly vanilla behaviour. */\n'
               + PRE_RECRUIT_STRUCT
               + 'struct PreRecruitVariant gPreRecruitVariant[] = {\n'
               + ('\n'.join(rows) + '\n' if rows else '') + '\t{0, 0, 0}\n};\n')
    with open(UNIT_ICON_MOVE_C, 'w', encoding='utf-8') as f:
        f.write(move_c)


def _remap_indices(src_path, roles, palette_png, out_path):
    """Rewrite an indexed sheet's pixel INDICES through `roles` (index -> index), saving it
    under `palette_png`'s palette. Index 0 (transparent) is fixed. Unlike
    map_sprite_tool.remap_sms_palette this is an explicit ROLE map, not nearest-RGB: the
    cast sheets are a grey ramp, and nearest-RGB against a coloured standard palette
    collapses them onto the constant/secondary entries (a grey Lupin barely changes colour
    by faction). Every non-zero index present must be declared."""
    im = Image.open(src_path)
    if im.mode != 'P':
        sys.exit('ERROR: %s is mode %s; expected an indexed (mode P) sheet' % (src_path, im.mode))
    missing = sorted({v for v in im.getdata() if v and v not in roles})
    if missing:
        sys.exit('ERROR: %s uses cast index/indices %s with no pre_recruit_roles entry'
                 % (os.path.basename(src_path), ', '.join(str(m) for m in missing)))
    out = Image.new('P', im.size)
    out.putpalette(map_sprite_tool.read_palette(palette_png))
    out.putdata([0 if v == 0 else roles[v] for v in im.getdata()])
    out.save(out_path)


def declared_map_sprite_units(campaign):
    """Every campaign unit that DECLARES custom map-sprite art -- cast (pcs/npcs YAML) and
    chapter-level scripted neutrals alike -- as {id: where-it-was-declared}."""
    declared = {}
    root = os.path.join(REPO, 'campaigns', campaign)
    for sub in ('pcs', 'npcs'):
        d = os.path.join(root, sub)
        if not os.path.isdir(d):
            continue
        for name in sorted(os.listdir(d)):
            if not name.endswith('.yaml'):
                continue
            with open(os.path.join(d, name), encoding='utf-8') as f:
                unit = yaml_load(f) or {}
            ms = (unit.get('art') or {}).get('map_sprite')
            if ms and (ms or {}).get('wiring') != 'pending':
                declared[unit.get('id') or name[:-5]] = '%s/%s' % (sub, name)
    chapters = os.path.join(root, 'chapters')
    for name in sorted(os.listdir(chapters)):
        if not name.endswith('.yaml'):
            continue
        chap = chapter_schema.load(os.path.join(chapters, name)) or {}
        # enemy_units too: Ravisin is ch05's BOSS and carries a full art.map_sprite block,
        # so scanning only the friendly-side keys left her (and every future enemy with our
        # own art) outside the "declared art must actually get wired" guard entirely. She
        # was covered only by a hand-added assert_custom_art_pid_wired call (#25).
        for key in ('neutral_units', 'green_units', 'enemy_units'):
            for unit in (chap.get(key) or []):
                if ((unit.get('art') or {}).get('map_sprite')) and unit.get('id'):
                    declared[unit['id']] = 'chapters/%s (%s)' % (name, key)
    return declared


def assert_declared_map_sprites_injected(campaign, wired):
    """Custom map art that is DECLARED and COMMITTED must actually get wired, or the unit
    silently wears its stock class sprite and nothing anywhere complains.

    That is precisely how ch04's white moose shipped: a full `art:` block on the chapter YAML,
    two committed Wyrdeer sheets, and an injector that only ever walked PORTRAIT_MAP -- so the
    chapter's title creature rendered as CLASS_GWYLLGI's stock hound. There was no error to
    read, because nothing tried and failed; nothing tried at all. A missing ASSET stays a
    no-op (art lands before wiring, deliberately) -- what fails here is art that exists on
    disk and is described in YAML, yet ends up in no sprite table.

    Art routinely lands one slice AHEAD of its wiring (Basil/Sahnar shipped with #179/#181;
    their wiring is #25 ch05 work). That deferral is legitimate, but it has to be WRITTEN
    DOWN or this guard cannot tell it from the moose -- so say `wiring: pending` on the unit's
    map_sprite block and name the issue there.
    """
    asset_dir = os.path.join(REPO, 'campaigns', campaign, 'map_sprites')
    missing = sorted(
        (uid, where) for uid, where in declared_map_sprite_units(campaign).items()
        if os.path.isfile(os.path.join(asset_dir, uid + '.png')) and uid not in wired)
    if missing:
        sys.exit('ERROR: these units declare art.map_sprite and ship map_sprites/<id>.png, '
                 'but no injector wired them -- they would render their stock class sprite:\n'
                 + '\n'.join('       %-16s declared in %s' % (uid, where) for uid, where in missing)
                 + '\n       Cast go in PORTRAIT_MAP; scripted neutrals in '
                   'SCRIPTED_NEUTRAL_SPRITES.')


def _inject_scripted_neutral_sprites(campaign, asset_dir, pointer_externs, verbose=True):
    """Map sprites for SCRIPTED NEUTRALS -- units that stand on a map wearing our own art but
    are NOT cast members (no PORTRAIT_MAP slot, no bust/stat/prep wiring), so `classed_cast`
    never sees them and `inject_map_sprites` used to walk straight past their assets.

    That gap is how ch04's white moose shipped: its Wyrdeer sheets and a full `art:` block
    were committed on the chapter YAML, nothing read them, and the engine fell back to
    CLASS_GWYLLGI's stock hound -- a green dog standing in for the chapter's title creature.
    Nothing failed; the art was simply never asked for. `assert_declared_map_sprites_injected`
    now closes that door.

    They wear the CAST palette, not the faction one, which is the whole reason they can't ride
    the chwinga path: a scripted neutral never changes faction, and the green NPC palette turns
    index 3 pale-green and index 11 blue -- a green-tinted animal with green blood. Keyed by a
    RAW charId (a pid the injector allocated), not a portrait-slot name.

    A row names SEVERAL charIds, because the same creature is a different pid in each chapter
    that stages it -- and a missing one reopens the exact hole above for one chapter only. See
    SCRIPTED_NEUTRAL_SPRITES.
    """
    neutral_ids = []
    for uid, char_ids, donor in SCRIPTED_NEUTRAL_SPRITES:
        idle_png = os.path.join(asset_dir, uid + '.png')
        if not os.path.isfile(idle_png):
            continue
        mu_png = os.path.join(asset_dir, uid + '_mu.png')
        if not os.path.isfile(mu_png):
            sys.exit('ERROR: scripted neutral %s needs a committed map_sprites/%s_mu.png '
                     '(hover/walk sheet; neutrals have no synth path -- synth_mu_sheet reads '
                     'the unit YAML, which a chapter-level neutral has none of)' % (uid, uid))
        map_sprite_tool.validate_mu_sheet(mu_png)
        _, dfw, dfh = map_sprite_tool.donor_sms_geometry(donor)
        macro, _, _, _ = map_sprite_tool.sheet_info(idle_png, (dfw, dfh))
        stem = uid.replace('-', '_')
        wait_sym = 'unit_icon_wait_manchego_%s_sheet' % stem
        move_sym = 'unit_icon_move_manchego_%s_sheet' % stem
        shutil.copyfile(idle_png, os.path.join(WAIT_GFX_DIR, wait_sym + '.png'))
        shutil.copyfile(mu_png, os.path.join(MOVE_GFX_DIR, move_sym + '.png'))
        sms = claim_sms_id()
        _write_wait_row(sms,
            '\t{0, %s, %s}, // %d %s (scripted neutral)' % (macro, wait_sym, sms, uid))
        with open(UNIT_ICON_WAIT_S, 'a', encoding='utf-8') as f:
            f.write('\n/* Manchego Stars scripted-neutral idle sprite: %s (#24) */\n'
                    '\t.global %s\n%s:\n\t.incbin "graphics/unit_icon/wait/%s.4bpp.lz"\n'
                    '\t.align 2, 0\n' % (uid, wait_sym, wait_sym, wait_sym))
        with open(UNIT_ICON_MOVE_S, 'a', encoding='utf-8') as f:
            f.write('\n/* Manchego Stars scripted-neutral hover/walk (MU) sprite: %s (#24) */\n'
                    '\t.global %s\n%s:\n\t.incbin "graphics/unit_icon/move/%s.4bpp.lz"\n'
                    '\t.align 2, 0\n' % (uid, move_sym, move_sym, move_sym))
        pointer_externs += ['extern char %s[];' % wait_sym, 'extern char %s[];' % move_sym]
        # ONE sheet pair and ONE SMS slot for the asset; one override row per PID that wears it.
        # A second chapter reusing the creature costs two table rows, not a second sprite.
        for char_id in char_ids:
            _insert_table_head(UNIT_ICON_WAIT_C, 'gMapSpriteOverride[]',
                               '\t%s, %d,\n' % (char_id, sms))
            _insert_table_head(UNIT_ICON_MOVE_C, 'gMuImgOverride[]',
                               '\t{%s, %s},\n' % (char_id, move_sym))
            neutral_ids.append((uid, char_id, sms))
        if verbose:
            print('  %-12s -> scripted-neutral idle SMS %d + MU (charIds %s, cast palette)'
                  % (uid, sms, ', '.join(char_ids)))
    return neutral_ids


def _inject_ch02_chwinga_sprites(campaign, verbose=True):
    """The 3 green chwinga (CH02_CHWINGA slots) wear Sclorbo's chwinga map sprite,
    recoloured by the GREEN NPC faction palette. They are green-faction, so they are kept
    OUT of the cast palette override (gMapPaletteOverride) -- GetUnitSpritePalette falls to
    the faction switch and tints the standard role layout green automatically (cf. the
    enemy reskins, which do the same for the red faction). Sclorbo's cast-palette sheet is
    remapped onto his SMS base's standard role layout at build time, so the single source
    of truth stays sclorbo.png (no committed derived asset); one shared SMS slot + MU sheet
    serve all three identical NPC slots. Must run inside inject_map_sprites (it owns the
    gMapSpriteOverride / gMuImgOverride tables)."""
    asset_dir = os.path.join(REPO, 'campaigns', campaign, 'map_sprites')
    src_idle = os.path.join(asset_dir, CH02_CHWINGA_SPRITE_SRC + '.png')
    if not os.path.isfile(src_idle):
        if verbose:
            print('  (no %s.png yet; chwinga keep their class sprite)' % CH02_CHWINGA_SPRITE_SRC)
        return
    donor = _donor_base(campaign, CH02_CHWINGA_SPRITE_SRC)        # 'Civilian_F1'
    donor_png = os.path.join(WAIT_GFX_DIR, 'unit_icon_wait_%s_sheet.png' % donor)
    _, dfw, dfh = map_sprite_tool.donor_sms_geometry(donor)

    wait_sym = 'unit_icon_wait_manchego_chwinga_sheet'
    move_sym = 'unit_icon_move_manchego_chwinga_sheet'
    role_idle = os.path.join(WAIT_GFX_DIR, wait_sym + '.png')
    move_png = os.path.join(MOVE_GFX_DIR, move_sym + '.png')
    # Remap Sclorbo's cast-palette tiles onto the donor's standard role layout (so the
    # green faction palette tints them), then synth the idle-only glide MU sheet from it.
    map_sprite_tool.remap_sms_palette(src_idle, donor_png, role_idle)
    map_sprite_tool.synth_mu_sheet(role_idle, donor, move_png, verbose=False)
    macro, _, _, _ = map_sprite_tool.sheet_info(role_idle, (dfw, dfh))

    sms = claim_sms_id()
    _write_wait_row(sms,
        '\t{0, %s, %s}, // %d chwinga (green NPC)' % (macro, wait_sym, sms))
    with open(UNIT_ICON_WAIT_S, 'a', encoding='utf-8') as f:
        f.write('\n/* Manchego Stars green chwinga idle sprite (#38) */\n'
                '\t.global %s\n%s:\n\t.incbin "graphics/unit_icon/wait/%s.4bpp.lz"\n'
                '\t.align 2, 0\n' % (wait_sym, wait_sym, wait_sym))
    with open(UNIT_ICON_MOVE_S, 'a', encoding='utf-8') as f:
        f.write('\n/* Manchego Stars green chwinga hover/walk (MU) sprite (#38) */\n'
                '\t.global %s\n%s:\n\t.incbin "graphics/unit_icon/move/%s.4bpp.lz"\n'
                '\t.align 2, 0\n' % (move_sym, move_sym, move_sym))
    with open(UNIT_ICON_POINTER_H, 'a', encoding='utf-8') as f:
        f.write('\n/* Manchego Stars green chwinga map sprite (#38) */\n'
                'extern char %s[];\nextern char %s[];\n' % (wait_sym, move_sym))

    # The three NPC slots all override onto the one shared chwinga slot/sheet. Insert at
    # the front of each table (linear scan; chwinga charIds are distinct from cast slots).
    slots = [slot for _, slot in CH02_CHWINGA]
    _insert_table_head(UNIT_ICON_WAIT_C, 'gMapSpriteOverride[]',
                       ''.join('\tCHARACTER_%s, %d,\n' % (s.upper(), sms) for s in slots))
    _insert_table_head(UNIT_ICON_MOVE_C, 'gMuImgOverride[]',
                       ''.join('\t{CHARACTER_%s, %s},\n' % (s.upper(), move_sym) for s in slots))
    if verbose:
        print('  chwinga (green NPC) -> idle SMS %d + MU, slots: %s'
              % (sms, ', '.join(slots)))


def _donor_base(campaign, uid, guest_bases=None):
    """The vanilla class/monster a cast member reskins (YAML art.map_sprite.base) -- the
    key that lets us read the sprite's SMS size from the decomp instead of guessing it.
    Cold-open guests have no pcs/npcs YAML, so their base comes from guest_bases
    (PROLOGUE_GUEST_SPRITES) instead of a unit YAML."""
    if guest_bases and uid in guest_bases:
        return guest_bases[uid]
    unit = load_unit(campaign, uid)
    try:
        return unit['art']['map_sprite']['base']
    except (KeyError, TypeError):
        sys.exit('ERROR: %s has map_sprites/%s.png but no art.map_sprite.base in its YAML '
                 '(needed to read the SMS size from the decomp)' % (uid, uid))


def _inject_idle_sprites(campaign, asset_dir, idle, pointer_externs, guest_bases=None,
                         src_override=None):
    """Wait-table slot + GetUnitSMSId override for each idle (<id>.png) asset. `src_override`
    ({uid: path}) supplies a pre-processed sheet (e.g. a faction-tinted unit's role-remapped
    idle) in place of the raw map_sprites/<id>.png."""
    src_override = src_override or {}
    wait_rows, incbin, overrides = [], [], []
    for uid, slot, class_enum, sms in idle:
        raw = src_override.get(uid) or os.path.join(asset_dir, uid + '.png')
        # Frame size from the decomp wait table for the donor base -- not guessed.
        _, dfw, dfh = map_sprite_tool.donor_sms_geometry(
            _donor_base(campaign, uid, guest_bases))
        macro, fw, fh, nframes = map_sprite_tool.sheet_info(raw, (dfw, dfh))
        sym = 'unit_icon_wait_manchego_%s_sheet' % uid.replace('-', '_')
        shutil.copyfile(raw, os.path.join(WAIT_GFX_DIR, sym + '.png'))
        wait_rows.append((sms, '\t{0, %s, %s}, /* %d %s */' % (macro, sym, sms, uid)))
        incbin += ['\t.global %s' % sym, '%s:' % sym,
                   '\t.incbin "graphics/unit_icon/wait/%s.4bpp.lz"' % sym,
                   '\t.align 2, 0']
        pointer_externs.append('extern char %s[];' % sym)
        overrides.append('\tCHARACTER_%s, %d,' % (slot.upper(), sms))

    for sms, row in wait_rows:
        _write_wait_row(sms, row)
    with open(UNIT_ICON_WAIT_S, 'a', encoding='utf-8') as f:
        f.write('\n/* Manchego Stars custom idle sprites (#38) */\n' + '\n'.join(incbin) + '\n')

    # Override table (campaign data) -> needs the CHARACTER_ enum. Non-const so it
    # shares unit_icon_wait_table's kept .data section (the ldscript drops its .rodata).
    with open(UNIT_ICON_WAIT_C, encoding='utf-8') as f:
        wait_c = f.read()
    if 'constants/characters.h' not in wait_c:
        wait_c = wait_c.replace('#include "unit_icon_data.h"',
                                '#include "unit_icon_data.h"\n#include "constants/characters.h"', 1)
    wait_c += ('\n/* injected: per-character idle-sprite overrides\n'
               ' * (charId, smsId pairs; 0xFFFF-terminated). Empty == vanilla. */\n'
               'unsigned short gMapSpriteOverride[] = {\n'
               + '\n'.join(overrides) + '\n\t0xFFFF\n};\n')
    with open(UNIT_ICON_WAIT_C, 'w', encoding='utf-8') as f:
        f.write(wait_c)

    _inject_sms_override_hook()


def _inject_mu_sprites(mu, pointer_externs):
    """Custom MU sheet + GetMuImg override for each hover/walk asset. `mu` items are
    (uid, slot, class_enum, src_path); src is a committed <id>_mu.png or a synthesized
    glide sheet (see inject_map_sprites)."""
    incbin, overrides = [], []
    for uid, slot, class_enum, src in mu:
        map_sprite_tool.validate_mu_sheet(src)
        sym = 'unit_icon_move_manchego_%s_sheet' % uid.replace('-', '_')
        shutil.copyfile(src, os.path.join(MOVE_GFX_DIR, sym + '.png'))
        incbin += ['\t.global %s' % sym, '%s:' % sym,
                   '\t.incbin "graphics/unit_icon/move/%s.4bpp.lz"' % sym,
                   '\t.align 2, 0']
        pointer_externs.append('extern char %s[];' % sym)
        overrides.append('\t{CHARACTER_%s, %s},' % (slot.upper(), sym))

    with open(UNIT_ICON_MOVE_S, 'a', encoding='utf-8') as f:
        f.write('\n/* Manchego Stars custom hover/walk (MU) sprites (#38) */\n'
                + '\n'.join(incbin) + '\n')

    # Override table -> needs the CHARACTER_ enum and the sheet externs. Non-const so it
    # shares unit_icon_move_table's kept .data section.
    with open(UNIT_ICON_MOVE_C, encoding='utf-8') as f:
        move_c = f.read()
    if 'constants/characters.h' not in move_c:
        move_c = move_c.replace('#include "unit_icon_data.h"',
                                '#include "unit_icon_data.h"\n#include "constants/characters.h"', 1)
    move_c += ('\n/* injected: per-character MU (hover/walk) sprite overrides\n'
               ' * (charId -> custom sheet; charId 0 terminates). Empty == vanilla. */\n'
               'struct CharMuImg { unsigned short charId; const void * img; };\n'
               'struct CharMuImg gMuImgOverride[] = {\n'
               + '\n'.join(overrides) + '\n\t{0, 0}\n};\n')
    with open(UNIT_ICON_MOVE_C, 'w', encoding='utf-8') as f:
        f.write(move_c)

    _inject_mu_override_hook()
