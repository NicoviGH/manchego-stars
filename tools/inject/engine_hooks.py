"""Campaign-agnostic engine hooks: build-time string-replaces into the decomp C
source. Pipeline-owned (the content track never opens this file). Each hook is a
pure patch with its own `if orig not in text` guard; presence is also asserted by
tools/check.py check_engine_guards_present. See docs/decisions.md.
"""

import os
import sys

from inject.decomp import (
    DECOMP, _replace_brace_block,
    BATTLEQUOTES_C, BMUNIT_C, LORDSEL_FLAG_BASE)

# Decomp source files the engine hooks read or patch. One exception to "patched
# here": BANIM_DATA_C is only READ by the hooks (_vanilla_banim_count); the content
# side appends its rows (build_campaign.py inject_battle_anims).
BANIM_EKRBATTLEINTRO_C = os.path.join(DECOMP, 'src', 'banim-ekrbattleintro.c')
BANIM_EKRMAIN_C = os.path.join(DECOMP, 'src', 'banim-ekrmain.c')
BANIM_MAIN_C = os.path.join(DECOMP, 'src', 'banim-main.c')
BANIM_EFXMISC_C = os.path.join(DECOMP, 'src', 'banim-efxmisc.c')
EFXBATTLE_H = os.path.join(DECOMP, 'include', 'efxbattle.h')
BANIM_DATA_C = os.path.join(DECOMP, 'src', 'banim_data.c')
BANIM_EFXMAGIC_C = os.path.join(DECOMP, 'src', 'banim-efxmagic.c')
BANIM_EKRUTILS_C = os.path.join(DECOMP, 'src', 'banim-ekrutils.c')
BANIM_EKRBATTLE_C = os.path.join(DECOMP, 'src', 'banim-ekrbattle.c')
BANIM_EKRDISPUP_C = os.path.join(DECOMP, 'src', 'banim-ekrdispup.c')
BANIM_EKRBATTLE_H = os.path.join(DECOMP, 'include', 'ekrbattle.h')
BMCAMADJUST_C = os.path.join(DECOMP, 'src', 'bmcamadjust.c')
BMMAP_C = os.path.join(DECOMP, 'src', 'bmmap.c')
WORLDMAP_PATH_C = os.path.join(DECOMP, 'src', 'worldmap_path.c')
BMDIFFICULTY_C = os.path.join(DECOMP, 'src', 'bmdifficulty.c')
BMMENU_C = os.path.join(DECOMP, 'src', 'bmmenu.c')
DATA_EVENT_TRIGGER_C = os.path.join(DECOMP, 'src', 'data_event_trigger.c')
EVENTINFO_C = os.path.join(DECOMP, 'src', 'eventinfo.c')
PREP_SALLYCURSOR_C = os.path.join(DECOMP, 'src', 'prep_sallycursor.c')
BANIM_EFXHIT_C = os.path.join(DECOMP, 'src', 'banim-efxhit.c')
ICON_C = os.path.join(DECOMP, 'src', 'icon.c')
ICON_H = os.path.join(DECOMP, 'include', 'icon.h')
CHAPTER_TITLE_C = os.path.join(DECOMP, 'src', 'chapter_title.c')
LORDFLOOR_APPLIED_FLAG = 0xFA


def _swap_combat_anim_to_unique(text):
    """Pure transform: route the combat battle-anim lookup through the per-character
    GetBattleAnimationId_WithUnique (#65 M-B), and widen the out param (u32 animid -> int)
    to match its signature. Idempotent -- the swapped name no longer matches the search."""
    text = text.replace('u32 animid1, animid2;', 'int animid1, animid2;')
    return text.replace('GetBattleAnimationId(unit_bu',
                        'GetBattleAnimationId_WithUnique(unit_bu')


def _patch_banim_character_unique():
    """Route FE8 combat anim selection through the per-character unique table (#65 M-B).

    Vanilla FE8 picks the battle anim purely by CLASS (GetBattleAnimationId); the
    per-character _u25 -> gUnitSpecificBanimConfigs path (a FE7 holdover) is only wired to
    the weapon-triangle preview, not real combat. This swaps the four combat call sites to
    the _WithUnique variant so every NAMED unit (PCs, bosses) can carry a custom battle anim
    via data alone -- no cloned class slot per unit (the slot budget is only ~3). Generic
    enemy classes are unaffected (no unique character id). Campaign-agnostic; guarded here
    and asserted by check.py check_engine_guards_present."""
    with open(BANIM_EKRBATTLEINTRO_C, encoding='utf-8') as f:
        text = f.read()
    if 'GetBattleAnimationId(unit_bu' not in text:
        if 'GetBattleAnimationId_WithUnique(unit_bu' in text:
            return  # already swapped (idempotent)
        sys.exit('ERROR: banim combat call sites not in expected vanilla form in %s'
                 % BANIM_EKRBATTLEINTRO_C)
    with open(BANIM_EKRBATTLEINTRO_C, 'w', encoding='utf-8') as f:
        f.write(_swap_combat_anim_to_unique(text))


def _guard_banim_palette_custom(text, first_custom_banim):
    """Pure transform: in GetBanimPalette, short-circuit CUSTOM (appended) banim ids to
    their OWN palette before the vanilla archer/sniper class->palette redirect.

    Vanilla GetBanimPalette loads the combatant's banim palette from
    banim_data[GetBanimPalette(banim_id, pos)], but for CLASS_ARCHER/_F/SNIPER/_F it returns
    a hardcoded canonical bow palette row (0x25/0x27/0x29/0x2B) regardless of banim_id -- a
    palette-share that is correct ONLY when the unit runs the stock bow anim. A custom (#65)
    unit deployed AS a real archer via the per-character _u25 path runs an APPENDED banim
    whose tiles index its own palette in its own banim_data row; the redirect then paints
    those tiles with the vanilla archer palette -- the RBG 'cyan' mis-render. Appended rows
    are ids >= the vanilla banim count, so bypass the switch for them. Vanilla units (ids <
    the count) hit the switch byte-for-byte as before. Idempotent."""
    anchor = '    jid = bu->unit.pClassData->number;\n    switch (jid) {'
    guard = ('    if (banim_id >= 0x%X) /* MS #65: a custom (appended) banim keeps its own '
             'palette; the\n                              vanilla archer/sniper palette-share '
             'below is for stock bow anims only. */\n'
             '        return banim_id;\n' % first_custom_banim)
    if guard in text or anchor not in text:
        return text  # already guarded, or unexpected vanilla form (caller asserts)
    return text.replace(anchor, guard + anchor, 1)


def _vanilla_banim_count():
    """Count banim_data[] rows in the (vanilla, freshly-restored) banim_data.c. Engine hooks
    run after restore_vanilla_sources() and BEFORE inject_battle_anims appends our rows, so
    this is the vanilla count = the id of the first custom (appended) row."""
    with open(BANIM_DATA_C, encoding='utf-8') as f:
        return sum(1 for ln in f if ln.lstrip().startswith('{"'))


def _patch_banim_palette_custom_guard():
    """Make GetBanimPalette honour a custom unit's OWN palette (#65 M-B, the RBG cyan fix).

    Companion to _patch_banim_character_unique: that routes the combat ANIM lookup through
    the per-character _u25 table, but the PALETTE still loads via GetBanimPalette, whose
    vanilla archer/sniper class special-case mis-redirects a custom-anim archer to the stock
    bow palette (cyan). This guards it so appended banim rows keep their own palette.
    Campaign-agnostic; guarded here and asserted by check.py check_engine_guards_present."""
    with open(BANIM_EKRMAIN_C, encoding='utf-8') as f:
        text = f.read()
    out = _guard_banim_palette_custom(text, _vanilla_banim_count())
    if out == text:
        if 'MS #65: a custom (appended) banim keeps its own palette' in text:
            return  # already guarded (idempotent)
        sys.exit('ERROR: GetBanimPalette not in expected vanilla form in %s'
                 % BANIM_EKRMAIN_C)
    with open(BANIM_EKRMAIN_C, 'w', encoding='utf-8') as f:
        f.write(out)


def _spell_palette_tint_start(text):
    """Record the current caster's tint in the dedicated spell-tint global."""
    line = '    s16 index = gEkrSpellAnimIndex[GetAnimPosition(anim)];\n'
    # This decomp targets C89: keep all local declarations before executable
    # statements in StartSpellAnimation.
    injected = line + '    gMSSpellTint = GetBanimSpellPaletteTint(anim);\n'
    if injected in text:
        return text
    return text.replace(line, injected, 1)


def _patch_banim_spell_palette_tint():
    """Add a data-driven, caster-scoped spell-palette tint seam.

    Campaign data appends character/weapon-type rows. The engine records the matching
    tint for that spell dispatch in a dedicated EWRAM_OVERLAY(banim) global gMSSpellTint
    (declared beside gEfxSpellAnimExists, the proven-writable overlay section), recolors
    the spell's BG/OBJ palette uploads, and clears it with the existing SpellFx lifecycle.
    gEfxSpellAnimExists stays byte-vanilla. Normal effects and every unconfigured combatant
    remain vanilla.
    """
    with open(BANIM_EKRBATTLE_H, encoding='utf-8') as f:
        header = f.read()
    if 'struct BanimSpellPaletteTint' not in header:
        anchor = 'enum ekr_hit_identifer {'
        decl = ('enum BanimSpellPaletteTintId {\n'
                '    BANIM_SPELL_TINT_NONE = 0,\n'
                '    BANIM_SPELL_TINT_GREEN = 1,\n'
                '    BANIM_SPELL_TINT_BLUE = 2,\n'
                '};\n\n'
                'struct BanimSpellPaletteTint {\n'
                '    u8 character;\n'
                '    u8 weapon_type;\n'
                '    u8 tint;\n'
                '};\n\n'
                'extern CONST_DATA struct BanimSpellPaletteTint gBanimSpellPaletteTints[];\n'
                'extern u8 gMSSpellTint;\n\n')
        if anchor not in header:
            sys.exit('ERROR: spell palette tint header anchor missing in %s' % BANIM_EKRBATTLE_H)
        with open(BANIM_EKRBATTLE_H, 'w', encoding='utf-8') as f:
            f.write(header.replace(anchor, decl + anchor, 1))

    with open(BANIM_EKRBATTLE_C, encoding='utf-8') as f:
        battle = f.read()
    if 'gMSSpellTint' not in battle:
        anchor = 'EWRAM_OVERLAY(banim) u32 gEfxSpellAnimExists = 0;\n'
        if anchor not in battle:
            sys.exit('ERROR: spell-tint global anchor missing in %s' % BANIM_EKRBATTLE_C)
        battle = battle.replace(
            anchor,
            anchor + 'EWRAM_OVERLAY(banim) u8 gMSSpellTint = BANIM_SPELL_TINT_NONE;\n', 1)
        with open(BANIM_EKRBATTLE_C, 'w', encoding='utf-8') as f:
            f.write(battle)

    with open(BANIM_EFXMAGIC_C, encoding='utf-8') as f:
        magic = f.read()
    if 'GetBanimSpellPaletteTint(struct Anim *anim)' not in magic:
        anchor = 'CONST_DATA SpellAnimFunc gEkrSpellAnimLut[] = {'
        support = ('static u8 GetBanimSpellPaletteTint(struct Anim *anim)\n'
                   '{\n'
                   '    struct BattleUnit *bu;\n'
                   '    const struct BanimSpellPaletteTint *it;\n\n'
                   '    if (GetAnimPosition(anim) == EKR_POS_L)\n'
                   '        bu = gpEkrBattleUnitLeft;\n'
                   '    else\n'
                   '        bu = gpEkrBattleUnitRight;\n\n'
                   '    for (it = gBanimSpellPaletteTints; it->character != 0; it++) {\n'
                   '        if (it->character == bu->unit.pCharacterData->number\n'
                   '            && it->weapon_type == GetItemType(bu->weaponBefore))\n'
                   '            return it->tint;\n'
                   '    }\n\n'
                   '    return BANIM_SPELL_TINT_NONE;\n'
                   '}\n\n')
        if anchor not in magic:
            sys.exit('ERROR: spell palette tint magic anchor missing in %s' % BANIM_EFXMAGIC_C)
        magic = magic.replace('#include "bmlib.h"', '#include "bmlib.h"\n#include "bmbattle.h"', 1)
        magic = magic.replace(anchor, support + anchor, 1)
    magic = _spell_palette_tint_start(magic)
    if 'gMSSpellTint = GetBanimSpellPaletteTint(anim);' not in magic:
        sys.exit('ERROR: StartSpellAnimation seam missing in %s' % BANIM_EFXMAGIC_C)
    with open(BANIM_EFXMAGIC_C, 'w', encoding='utf-8') as f:
        f.write(magic)

    with open(BANIM_EKRUTILS_C, encoding='utf-8') as f:
        utils = f.read()
    if 'BanimSpellPaletteCopy' not in utils:
        anchor = 'void SpellFx_RegisterObjGfx(const u16 * img, u32 size)\n'
        support = ('static u16 BanimSpellTintGreen(u16 color)\n'
                   '{\n'
                   '    int r = color & 0x1F;\n'
                   '    int g = (color >> 5) & 0x1F;\n'
                   '    int b = (color >> 10) & 0x1F;\n'
                   '    int high = r;\n'
                   '    int low = r;\n\n'
                   '    if (g > high) high = g;\n'
                   '    if (b > high) high = b;\n'
                   '    if (g < low) low = g;\n'
                   '    if (b < low) low = b;\n'
                   '    if (high - low < 3)\n'
                   '        return color;\n\n'
                   '    return (low + (high - low) / 4)\n'
                   '        | (high << 5)\n'
                   '        | ((low + (high - low) / 6) << 10);\n'
                   '}\n\n'
                   # Ice/frost: blue channel dominant, green kept mid so the tint reads as a
                   # bright cyan-white frost rather than a dark navy; red suppressed.
                   'static u16 BanimSpellTintBlue(u16 color)\n'
                   '{\n'
                   '    int r = color & 0x1F;\n'
                   '    int g = (color >> 5) & 0x1F;\n'
                   '    int b = (color >> 10) & 0x1F;\n'
                   '    int high = r;\n'
                   '    int low = r;\n\n'
                   '    if (g > high) high = g;\n'
                   '    if (b > high) high = b;\n'
                   '    if (g < low) low = g;\n'
                   '    if (b < low) low = b;\n'
                   '    if (high - low < 3)\n'
                   '        return color;\n\n'
                   '    return (low + (high - low) / 6)\n'
                   '        | ((low + (high - low) / 2) << 5)\n'
                   '        | (high << 10);\n'
                   '}\n\n'
                   'static void BanimSpellPaletteCopy(const u16 *src, u16 *dst, u32 size)\n'
                   '{\n'
                   '    u32 i;\n\n'
                   '    if (gMSSpellTint == BANIM_SPELL_TINT_NONE) {\n'
                   '        CpuFastCopy(src, dst, size);\n'
                   '        return;\n'
                   '    }\n\n'
                   '    for (i = 0; i < size / sizeof(u16); i++) {\n'
                   '        if (gMSSpellTint == BANIM_SPELL_TINT_BLUE)\n'
                   '            dst[i] = BanimSpellTintBlue(src[i]);\n'
                   '        else\n'
                   '            dst[i] = BanimSpellTintGreen(src[i]);\n'
                   '    }\n'
                   '}\n\n')
        if anchor not in utils:
            sys.exit('ERROR: spell palette copy anchor missing in %s' % BANIM_EKRUTILS_C)
        utils = utils.replace(anchor, support + anchor, 1)
        utils = utils.replace('    CpuFastCopy(pal, PAL_OBJ(OBJPAL_BANIM_SPELL_OBJ), size);\n',
                              '    BanimSpellPaletteCopy(pal, PAL_OBJ(OBJPAL_BANIM_SPELL_OBJ), size);\n', 1)
        utils = utils.replace('    CpuFastCopy(pal, PAL_BG(OBJPAL_BANIM_SPELL_BG), size);\n',
                              '    BanimSpellPaletteCopy(pal, PAL_BG(OBJPAL_BANIM_SPELL_BG), size);\n', 1)
    with open(BANIM_EKRUTILS_C, 'w', encoding='utf-8') as f:
        f.write(utils)

    # Clear the tint at spell teardown, alongside the vanilla gEfxSpellAnimExists reset.
    with open(BANIM_EKRDISPUP_C, encoding='utf-8') as f:
        dispup = f.read()
    reset = '    gMSSpellTint = BANIM_SPELL_TINT_NONE;\n'
    if reset not in dispup:
        anchor = '    gEfxSpellAnimExists = 0;\n'
        if anchor not in dispup:
            sys.exit('ERROR: spell-tint reset anchor missing in %s' % BANIM_EKRDISPUP_C)
        dispup = dispup.replace(anchor, anchor + reset, 1)
        with open(BANIM_EKRDISPUP_C, 'w', encoding='utf-8') as f:
            f.write(dispup)


# Several smooth throbs over the charge window, as a fixed-point wash factor out of 32.
# A raised cosine (0 -> peak -> 0) repeated `_CHARGE_FLASH_THROBS` times -- matching the
# approved multi-pulse mockup, NOT a single throb. Peak ~0.72 (23/32); starts and ends at 0
# (clean restore). Precomputed so the engine needs no sin(); index by the proc timer.
_CHARGE_FLASH_FRAMES = 40
_CHARGE_FLASH_THROBS = 3
def _charge_flash_sine_lut():
    import math
    peak = 23
    return [int(round((0.5 - 0.5 * math.cos(
                2 * math.pi * _CHARGE_FLASH_THROBS * i / _CHARGE_FLASH_FRAMES)) * peak))
            for i in range(_CHARGE_FLASH_FRAMES + 1)]


def _patch_banim_charge_flash():
    """Per-caster charge flash (#183): the caster's OWN battle sprite pulses toward a signature
    colour on the wind-up beat, WITHOUT altering the donor-matched animation script.

    Armed by the elec-charge command (0x28, `case 40`) ALREADY present in the faked magic body
    -- so no motion.s change. The arm looks up the current attacker (character + equipped weapon
    type) in the campaign-declared gMSChargeFlashes table; a configured caster spawns a proc that
    snapshots its OBJ palette and blends it toward the target BGR555 by a precomputed sine each
    frame, restoring it when the throb completes (bleeding into the cast). Vanilla casters hit the
    same command, find no row, and are byte-unchanged. Character binding + colour live in data."""
    # 1. data contract in the banim header (beside the spell-tint struct).
    with open(BANIM_EKRBATTLE_H, encoding='utf-8') as f:
        header = f.read()
    if 'struct BanimChargeFlash' not in header:
        anchor = 'enum ekr_hit_identifer {'
        decl = ('struct BanimChargeFlash {\n'
                '    u8 character;\n'
                '    u8 weapon_type;\n'
                '    u16 target;   /* BGR555 blend target */\n'
                '};\n\n'
                'extern CONST_DATA struct BanimChargeFlash gMSChargeFlashes[];\n\n')
        if anchor not in header:
            sys.exit('ERROR: charge-flash header anchor missing in %s' % BANIM_EKRBATTLE_H)
        with open(BANIM_EKRBATTLE_H, 'w', encoding='utf-8') as f:
            f.write(header.replace(anchor, decl + anchor, 1))

    # 2. the extern arm prototype, beside the vanilla flash effect.
    with open(EFXBATTLE_H, encoding='utf-8') as f:
        efxh = f.read()
    if 'MSChargeFlashArm' not in efxh:
        anchor = 'void NewEfxFlashFX(struct Anim * anim);\n'
        if anchor not in efxh:
            sys.exit('ERROR: charge-flash efxbattle.h anchor missing in %s' % EFXBATTLE_H)
        with open(EFXBATTLE_H, 'w', encoding='utf-8') as f:
            f.write(efxh.replace(anchor, anchor + 'void MSChargeFlashArm(struct Anim * anim);\n', 1))

    # 3. the blend helper + pulse proc + arm, beside the vanilla flash effect handler.
    with open(BANIM_EFXMISC_C, encoding='utf-8') as f:
        efx = f.read()
    if 'MSChargeFlashArm' not in efx:
        lut = ', '.join(str(v) for v in _charge_flash_sine_lut())
        support = (
            'static const u8 sMSChargeFlashSine[%d] = { %s };\n\n'
            'static u16 MSChargeBlend(u16 base, u16 target, int f)\n'
            '{\n'
            '    int r = base & 0x1F;\n'
            '    int g = (base >> 5) & 0x1F;\n'
            '    int b = (base >> 10) & 0x1F;\n'
            '    r += ((target & 0x1F) - r) * f / 32;\n'
            '    g += (((target >> 5) & 0x1F) - g) * f / 32;\n'
            '    b += (((target >> 10) & 0x1F) - b) * f / 32;\n'
            '    return r | (g << 5) | (b << 10);\n'
            '}\n\n'
            'struct ProcMSChargeFlash {\n'
            '    PROC_HEADER;\n'
            '    int timer;\n'
            '    u16 target;\n'
            '    u16 *pal;\n'
            '    u16 saved[16];   /* snapshot of the actor palette (no .bss statics allowed here) */\n'
            '};\n\n'
            'void MSChargeFlashMain(struct ProcMSChargeFlash *proc);\n\n'
            'CONST_DATA struct ProcCmd ProcScr_msChargeFlash[] = {\n'
            '    PROC_NAME("msChargeFlash"),\n'
            '    PROC_REPEAT(MSChargeFlashMain),\n'
            '    PROC_END,\n'
            '};\n\n'
            'void MSChargeFlashMain(struct ProcMSChargeFlash *proc)\n'
            '{\n'
            '    int i;\n'
            '    int f = sMSChargeFlashSine[proc->timer];\n\n'
            '    for (i = 0; i < 16; i++)\n'
            '        proc->pal[i] = MSChargeBlend(proc->saved[i], proc->target, f);\n'
            '    EnablePaletteSync();\n\n'
            '    if (++proc->timer > %d) {\n'
            '        for (i = 0; i < 16; i++)\n'
            '            proc->pal[i] = proc->saved[i];\n'
            '        EnablePaletteSync();\n'
            '        Proc_Break(proc);\n'
            '    }\n'
            '}\n\n'
            'void MSChargeFlashArm(struct Anim *anim)\n'
            '{\n'
            '    struct BattleUnit *bu;\n'
            '    const struct BanimChargeFlash *it;\n'
            '    struct ProcMSChargeFlash *proc;\n'
            '    u16 *pal;\n'
            '    int i;\n'
            '    int pos = GetAnimPosition(anim);\n\n'
            '    if (pos == EKR_POS_L) {\n'
            '        bu = gpEkrBattleUnitLeft;\n'
            '        pal = PAL_OBJ(0x7);\n'
            '    } else {\n'
            '        bu = gpEkrBattleUnitRight;\n'
            '        pal = PAL_OBJ(0x9);\n'
            '    }\n\n'
            '    for (it = gMSChargeFlashes; it->character != 0; it++) {\n'
            '        if (it->character == bu->unit.pCharacterData->number\n'
            '            && it->weapon_type == GetItemType(bu->weaponBefore)) {\n'
            '            proc = Proc_Start(ProcScr_msChargeFlash, PROC_TREE_3);\n'
            '            proc->timer = 0;\n'
            '            proc->target = it->target;\n'
            '            proc->pal = pal;\n'
            '            for (i = 0; i < 16; i++)\n'
            '                proc->saved[i] = pal[i];\n'
            '            return;\n'
            '        }\n'
            '    }\n'
            '}\n\n'
            % (_CHARGE_FLASH_FRAMES + 1, lut, _CHARGE_FLASH_FRAMES))
        anchor = '/**\n * C51: banim_code_flash_white\n */\n'
        if anchor not in efx:
            sys.exit('ERROR: charge-flash efxmisc anchor missing in %s' % BANIM_EFXMISC_C)
        efx = efx.replace(anchor, support + anchor, 1)
        with open(BANIM_EFXMISC_C, 'w', encoding='utf-8') as f:
            f.write(efx)

    # 4. arm from the existing elec-charge command (case 40) -- NO motion.s change.
    with open(BANIM_MAIN_C, encoding='utf-8') as f:
        main = f.read()
    if 'MSChargeFlashArm(anim)' not in main:
        anchor = '                case 40:\n                case 41:\n'
        if anchor not in main:
            sys.exit('ERROR: charge-flash case-40 anchor missing in %s' % BANIM_MAIN_C)
        armed = ('                case 40:\n'
                 '                    if (GetAISLayerId(anim) == 0)\n'
                 '                        MSChargeFlashArm(anim);\n'
                 '                    /* MS #183: arm the per-caster charge flash, then fall'
                 ' through to the SE */\n'
                 '                case 41:\n')
        main = main.replace(anchor, armed, 1)
        with open(BANIM_MAIN_C, 'w', encoding='utf-8') as f:
            f.write(main)


def _patch_player_start_cursor_guard():
    """Guard GetPlayerStartCursorPosition against a non-deployed player leader.

    At chapter start ProcFun_ResetCursorPosition centers the cursor on the player leader:
    GetUnitFromCharId(GetPlayerLeaderPid()). FE8 assumes the leader (a LORD-class unit) is
    always deployed -- but our campaign's lords ride ordinary slots, so that lookup returns
    NULL and the original code dereferences it (`unit->xPos`), reading BIOS garbage and
    parking the cursor OFF-MAP. The off-map cursor then drives out-of-bounds map/terrain
    reads -> a runaway text decode -> gBmSt corruption (garbage band) -> crash. Watchpoint-
    confirmed root cause. Fix: if the leader isn't deployed, fall back to the first valid
    player unit, and never dereference NULL. Campaign-agnostic engine hardening.
    """
    with open(BMCAMADJUST_C, encoding='utf-8') as f:
        text = f.read()
    orig = (
        'void GetPlayerStartCursorPosition(int *px, int *py)\n'
        '{\n'
        '    struct Unit *unit;\n'
        '    if (1 == gPlaySt.chapterTurnNumber) {\n'
        '        unit = GetUnitFromCharId(GetPlayerLeaderPid());\n'
        '        gPlaySt.xCursor = unit->xPos;\n'
        '        gPlaySt.yCursor = unit->yPos;\n'
        '    }\n'
        '\n'
        '    if (1 != gPlaySt.config.autoCursor) {\n'
        '        unit = GetUnitFromCharId(GetPlayerLeaderPid());\n'
        '        *px = unit->xPos;\n'
        '        *py = unit->yPos;\n'
        '    } else {\n'
        '        *px = gPlaySt.xCursor;\n'
        '        *py = gPlaySt.yCursor;\n'
        '    }\n'
        '}')
    fixed = (
        'void GetPlayerStartCursorPosition(int *px, int *py)\n'
        '{\n'
        '    struct Unit *unit;\n'
        '    int i;\n'
        '\n'
        '    /* Leader may ride a non-LORD slot (campaign): if not deployed, fall back to\n'
        '     * the first valid player unit so the cursor never lands off-map. */\n'
        '    unit = GetUnitFromCharId(GetPlayerLeaderPid());\n'
        '    if (unit == NULL) {\n'
        '        for (i = 1; i < 0x40; ++i) {\n'
        '            struct Unit *u = GetUnit(i);\n'
        '            if (UNIT_IS_VALID(u)) {\n'
        '                unit = u;\n'
        '                break;\n'
        '            }\n'
        '        }\n'
        '    }\n'
        '    if (unit == NULL)\n'
        '        return;\n'
        '\n'
        '    if (1 == gPlaySt.chapterTurnNumber) {\n'
        '        gPlaySt.xCursor = unit->xPos;\n'
        '        gPlaySt.yCursor = unit->yPos;\n'
        '    }\n'
        '\n'
        '    if (1 != gPlaySt.config.autoCursor) {\n'
        '        *px = unit->xPos;\n'
        '        *py = unit->yPos;\n'
        '    } else {\n'
        '        *px = gPlaySt.xCursor;\n'
        '        *py = gPlaySt.yCursor;\n'
        '    }\n'
        '}')
    if orig not in text:
        sys.exit('ERROR: GetPlayerStartCursorPosition not in expected form in %s' % BMCAMADJUST_C)
    with open(BMCAMADJUST_C, 'w', encoding='utf-8') as f:
        f.write(text.replace(orig, fixed, 1))


def _patch_terrain_name_guard():
    """Bounds-guard GetTerrainName against out-of-range terrain ids.

    gUnknown_0880D374 (the terrain -> name-message-id table) has only 65 entries.
    An out-of-range id -- e.g. the terrain-display window reading gBmMapTerrain at an
    OFF-MAP cursor position (which happens at chapter start when the lord rides a
    non-LORD-class slot, so the auto-cursor never centers it) -- indexes past the table,
    yielding a garbage gMsgTable[] pointer. The text decompressor then runs away and
    overruns gBmSt (camera/cursor), corrupting the screen and soft-locking. Vanilla never
    hit this because its lords are LORD-class; our campaign's aren't. Campaign-agnostic
    engine hardening: an invalid terrain id renders as terrain 0 instead of crashing.
    """
    with open(BMMAP_C, encoding='utf-8') as f:
        text = f.read()
    orig = ('char* GetTerrainName(int terrainId) {\n'
            '    return GetStringFromIndex(gUnknown_0880D374[terrainId]);\n'
            '}')
    guarded = ('char* GetTerrainName(int terrainId) {\n'
               '    /* Guard OOB ids (e.g. off-map cursor); table has 65 entries. */\n'
               '    if ((unsigned int)terrainId >= 65)\n'
               '        terrainId = 0;\n'
               '    return GetStringFromIndex(gUnknown_0880D374[terrainId]);\n'
               '}')
    if orig not in text:
        sys.exit('ERROR: GetTerrainName not in expected vanilla form in %s' % BMMAP_C)
    with open(BMMAP_C, 'w', encoding='utf-8') as f:
        f.write(text.replace(orig, guarded, 1))


def _patch_draw_icon_pal2_text(text):
    """Pure icon.c transform for the additive custom item palette hook.

    LoadIconPalettes preserves the vanilla two-bank load everywhere. DrawIcon loads source palette 2
    into reserved BG bank 15 only while drawing an opted-in standard item icon, after the caller has
    initialized its own UI palettes. Callers using other palette bases retain their vanilla selection.
    """
    if '#include "hardware.h"' not in text:
        sys.exit('ERROR: icon.c not in expected form (no hardware.h include) for the pal-2 hook')
    text = text.replace(
        '#include "hardware.h"',
        '#include "hardware.h"\n\n'
        '/* MS (#23): iconIds that draw from the additive custom item palette. */\n'
        'extern const u16 gMSPal2IconIds[];', 1)
    load_orig = ('void LoadIconPalettes(u32 Dest)\n'
                 '{\n'
                 '    ApplyPalettes(item_icon_palette[0], Dest, 2);\n'
                 '}')
    load_patched = load_orig
    if load_orig not in text:
        sys.exit('ERROR: LoadIconPalettes not in expected vanilla form in %s' % ICON_C)
    text = text.replace(load_orig, load_patched, 1)
    orig = ('    } else {\n'
            '        u16 Tile = GetIconTileIndex(IconIndex) + OamPalBase;')
    if orig not in text:
        sys.exit('ERROR: DrawIcon not in expected vanilla form in %s' % ICON_C)
    patched = ('    } else {\n'
               '        u16 Tile;\n'
               '        const u16* msPal2 = gMSPal2IconIds;\n'
               '        /* MS (#23): only the normal item-UI base (BG bank 4) can move to the\n'
               "           dedicated custom bank 15. Loading here follows the caller's UI setup. */\n"
               '        while (*msPal2 != 0xFFFF) {\n'
               '            if (*msPal2++ == IconIndex) {\n'
               '                if ((OamPalBase & 0xF000) == 0x4000) {\n'
               '                    ApplyPalette(item_icon_palette[2], 15);\n'
               '                    OamPalBase = (OamPalBase & 0x0FFF) | 0xF000;\n'
               '                }\n'
               '                break;\n'
               '            }\n'
               '        }\n'
               '        Tile = GetIconTileIndex(IconIndex) + OamPalBase;')
    return text.replace(orig, patched, 1)


def _patch_draw_icon_pal2():
    """Append a custom item palette without repurposing the two vanilla icon palettes.

    The palette asset grows from two to three source banks. An opted-in standard item icon loads the
    custom source into reserved BG bank 15 after the UI's own palette setup; the stock banks remain at
    4/5. Campaign-specific icon ids live in gMSPal2IconIds, not in this hook.
    """
    with open(ICON_C, encoding='utf-8') as f:
        text = f.read()
    with open(ICON_C, 'w', encoding='utf-8') as f:
        f.write(_patch_draw_icon_pal2_text(text))

    with open(ICON_H, encoding='utf-8') as f:
        header = f.read()
    orig = 'extern const u16 item_icon_palette[2][16]; // Item Icon Palette'
    patched = 'extern const u16 item_icon_palette[3][16]; // Item Icon Palette + custom bank'
    if orig not in header:
        sys.exit('ERROR: icon.h not in expected vanilla form for the pal-2 hook')
    with open(ICON_H, 'w', encoding='utf-8') as f:
        f.write(header.replace(orig, patched, 1))


def _patch_battle_map_kind_fallback():
    """A chapter load that resolves no world-map node is a STORY chapter, not a
    skirmish.

    GetBattleMapKind (worldmap_path.c) classifies most chapter slots by scanning
    gGMData's world-map node states and falls back to BATTLEMAP_KIND_SKIRMISH when
    no node matches. Vanilla can rely on that: story chapters on node slots are
    always entered THROUGH the world map, so a node always matches. Our campaign
    has no world map (boot and MNC2 go straight to the battle map), so gGMData is
    never populated and every node-slot chapter (slot 2+) misclassified as a
    SKIRMISH -- which swaps in EventScr_SkirmishCommonBeginning instead of the
    chapter's own beginning scene (bm.c CallBeginningEvents), hides the ally
    unit-definition table, and disables force-deployment. Campaign-agnostic
    hardening: the no-node fallback becomes STORY. (Skirmishes are unreachable
    without a world map, so the old fallback had no remaining legitimate hit.)
    """
    with open(WORLDMAP_PATH_C, encoding='utf-8') as f:
        text = f.read()
    orig = '    return BATTLEMAP_KIND_SKIRMISH;'
    if text.count(orig) != 1:
        sys.exit('ERROR: GetBattleMapKind fallback not in expected vanilla form in %s'
                 % WORLDMAP_PATH_C)
    patched = ('    /* No world map in this hack: a load that resolves no node is a\n'
               '       story chapter (vanilla only reached this via WM skirmishes). */\n'
               '    return BATTLEMAP_KIND_STORY;')
    with open(WORLDMAP_PATH_C, 'w', encoding='utf-8') as f:
        f.write(text.replace(orig, patched, 1))


def _patch_chapter_title_wm_fallback():
    """A story chapter's title banner is always its ROM chapTitleId card, never a
    world-map skirmish name.

    GetChapterTitleWM (chapter_title.c) -- the source for both the chapter-intro
    banner (chapterintrofx*) AND the map Status screen (uichapterstatus) -- returns
    the skirmish name card (0x46 + i) when the chapter's node is a monster-spawn
    location AND `GetNextUnclearedNode(&gGMData) != unk`. Vanilla only takes that
    branch on a postgame revisit; during a story playthrough the node IS the next
    uncleared one, so the branch is skipped and it returns chapTitleId. Our campaign
    has no world map (see _patch_battle_map_kind_fallback), so gGMData's node states
    are never populated -> GetNextUnclearedNode never matches -> every story chapter
    whose slot maps to a spawn node (e.g. ch03 hosts vanilla slot 4 = WM_NODE_ZahaWoods,
    the first spawn location) renders the "Za'ha Woods" skirmish name instead of its
    own "Ch.3: ..." card. Slots whose node isn't a spawn location (ch01/ch02) escaped
    it by luck. Campaign-agnostic hardening: neuter the guard so the WM/monster-spawn
    branch never fires and the function always returns the ROM chapTitleId. (The dead
    loop body still references `i`/`unk`, so no unused-variable warning.)
    """
    with open(CHAPTER_TITLE_C, encoding='utf-8') as f:
        text = f.read()
    orig = ('    if ((chapterData->chapterStateBits & PLAY_FLAG_POSTGAME) || '
            'GetNextUnclearedNode(&gGMData) != unk)')
    if text.count(orig) != 1:
        sys.exit('ERROR: GetChapterTitleWM guard not in expected vanilla form in %s'
                 % CHAPTER_TITLE_C)
    patched = ('    if (0) /* MS: no world map -> the title is always the ROM chapTitleId\n'
               '             (never a WM skirmish name for a spawn-node story chapter) */')
    with open(CHAPTER_TITLE_C, 'w', encoding='utf-8') as f:
        f.write(text.replace(orig, patched, 1))


def _inject_lord_select_engine():
    """Lord select (#42), engine side: make the player-chosen lead real.

    The ch01 menu (inject_ch01) records the pick as permanent flag
    LORDSEL_FLAG_BASE + menu index. Six campaign-agnostic hooks consume it:
      1. LordSelect_GetPid (new, eventinfo.c): scan the flags over the
         build-generated gLordSelectCandidates pid table (events_udefs.c);
         fallback = first candidate while nothing is set, so a debug entry
         straight into a chapter never soft-locks (issue #42's requirement).
      2. IsCharacterForceDeployed_ (eventinfo.c): the chosen lead is always
         fielded by the prep flow.
      3. CanUnitSeize (bmdifficulty.c): Seize belongs to the chosen lead
         (vanilla hardcoded Eirika/Ephraim by route/chapter).
      4. UnitKill (bmunit.c): the chosen lead's death raises EVFLAG_GAMEOVER --
         caught by each chapter's CauseGameOverIfLordDies AFEV -- whatever the
         death path. The vanilla route-wide Eirika/Ephraim defeat entries
         (chapter 0xFF + EVFLAG_GAMEOVER, data_battlequotes.c) are demoted to
         plain quotes: the cast members riding those slots must be able to die
         like anyone else when they are not the chosen lead.
      5. SupplyUsability (bmmenu.c): convoy/supply access belongs to the chosen
         lead (vanilla hardcoded Eirika/Ephraim by route) -- otherwise a cast
         member on the Eirika slot inherits free convoy access.
      6. gForceDeploymentList (data_event_trigger.c): cleared. Vanilla's static
         by-slot force-deploy table would force-field cast riding those slots
         (e.g. whoever rides CHARACTER_EIRIKA in COMMON mode, every chapter) on top of hook 2's
         chosen lead. Hook 2 is now the ONLY force-deploy.
    """
    # 1 + 2: eventinfo.c -- GetPid above the force-deploy lookup, hook inside it.
    with open(EVENTINFO_C, encoding='utf-8') as f:
        text = f.read()
    orig = ('//! FE8U = 0x08084800\n'
            'bool IsCharacterForceDeployed_(u16 pid)\n'
            '{\n'
            '    struct ForceDeploymentEnt * it;\n'
            '\n'
            '    for (it = gForceDeploymentList; it->pid != (u16)-1; it++)\n')
    if text.count(orig) != 1:
        sys.exit('ERROR: IsCharacterForceDeployed_ not in expected vanilla form in %s'
                 % EVENTINFO_C)
    hooked = (
        '/* Lord select (campaign engine, #42): resolve the player-chosen lead.\n'
        '   gLordSelectCandidates (events_udefs.c, build-generated) lists the cast\n'
        '   pids in menu order; the ch01 menu records the pick as permanent flag\n'
        '   0x%X + index (saved with the file; zeroed on New Game by\n'
        '   ResetPermanentFlags). Fallback while nothing is set (debug entry\n'
        '   before the menu has run): the first candidate. */\n'
        'u16 LordSelect_GetPid(void)\n'
        '{\n'
        '    extern const u16 gLordSelectCandidates[];\n'
        '    int i;\n'
        '\n'
        '    for (i = 0; gLordSelectCandidates[i] != 0xFFFF; i++) {\n'
        '        if (CheckFlag(0x%X + i)) {\n'
        '            return gLordSelectCandidates[i];\n'
        '        }\n'
        '    }\n'
        '\n'
        '    return gLordSelectCandidates[0];\n'
        '}\n'
        '\n'
        '//! FE8U = 0x08084800\n'
        'bool IsCharacterForceDeployed_(u16 pid)\n'
        '{\n'
        '    struct ForceDeploymentEnt * it;\n'
        '\n'
        '    /* Lord select (campaign engine, #42): the chosen lead is always\n'
        '       fielded. */\n'
        '    if (pid == LordSelect_GetPid())\n'
        '        return true;\n'
        '\n'
        '    for (it = gForceDeploymentList; it->pid != (u16)-1; it++)\n'
        % (LORDSEL_FLAG_BASE, LORDSEL_FLAG_BASE))
    with open(EVENTINFO_C, 'w', encoding='utf-8') as f:
        f.write(text.replace(orig, hooked, 1))

    # 3: bmdifficulty.c -- Seize gate.
    with open(BMDIFFICULTY_C, encoding='utf-8') as f:
        text = f.read()
    orig = ('s8 CanUnitSeize(struct Unit* unit) {\n'
            '    int leaderId;\n'
            '\n'
            '    switch (gPlaySt.chapterModeIndex) {\n'
            '        case 2: // Eirika\n'
            '            leaderId = CHARACTER_EIRIKA;\n'
            '            break;\n'
            '        case 1: // tutorial (chapter 0-8)\n'
            '            leaderId = CHARACTER_EIRIKA;\n'
            '            break;\n'
            '        case 3: // Ephraim\n'
            '            leaderId = CHARACTER_EPHRAIM;\n'
            '            break;\n'
            '    }\n'
            '\n'
            '    if (gPlaySt.chapterIndex == 5) {\n'
            '        leaderId = CHARACTER_EPHRAIM;\n'
            '    }\n'
            '\n'
            '    return unit->pCharacterData->number == leaderId;\n'
            '}')
    if text.count(orig) != 1:
        sys.exit('ERROR: CanUnitSeize not in expected vanilla form in %s'
                 % BMDIFFICULTY_C)
    patched = ('s8 CanUnitSeize(struct Unit* unit) {\n'
               '    /* Lord select (campaign engine, #42): Seize belongs to the\n'
               '       player-chosen lead (vanilla hardcoded Eirika/Ephraim by\n'
               '       route/chapter). */\n'
               '    extern u16 LordSelect_GetPid(void);\n'
               '\n'
               '    return unit->pCharacterData->number == LordSelect_GetPid();\n'
               '}')
    with open(BMDIFFICULTY_C, 'w', encoding='utf-8') as f:
        f.write(text.replace(orig, patched, 1))

    # 4a: bmunit.c -- death hook.
    with open(BMUNIT_C, encoding='utf-8') as f:
        text = f.read()
    orig = ('        else {\n'
            '            unit->state |= US_DEAD | US_HIDDEN;\n'
            '            InitUnitsupports(unit);\n'
            '        }\n')
    if text.count(orig) != 1:
        sys.exit('ERROR: UnitKill blue-death branch not in expected vanilla form in %s'
                 % BMUNIT_C)
    hooked = ('        else {\n'
              '            /* Lord select (campaign engine, #42): the chosen lead\'s\n'
              '               fall ends the run whatever killed them -- raise the\n'
              '               game-over flag the chapter Misc AFEV\n'
              '               (CauseGameOverIfLordDies) fires on. */\n'
              '            extern u16 LordSelect_GetPid(void);\n'
              '            extern void SetFlag(int flag);\n'
              '\n'
              '            if (UNIT_CHAR_ID(unit) == LordSelect_GetPid())\n'
              '                SetFlag(0x65); /* EVFLAG_GAMEOVER */\n'
              '\n'
              '            unit->state |= US_DEAD | US_HIDDEN;\n'
              '            InitUnitsupports(unit);\n'
              '        }\n')
    with open(BMUNIT_C, 'w', encoding='utf-8') as f:
        f.write(text.replace(orig, hooked, 1))

    # 4b: data_battlequotes.c -- demote the route-wide lord game-over entries.
    with open(BATTLEQUOTES_C, encoding='utf-8') as f:
        text = f.read()
    for msg in ('0x0C23', '0x0C24'):  # vanilla Eirika / Ephraim farewell quotes
        orig = ('        .flag    = EVFLAG_GAMEOVER,\n'
                '        .msg     = %s,\n' % msg)
        if text.count(orig) != 1:
            sys.exit('ERROR: route-wide lord defeat entry (%s) not in expected '
                     'vanilla form in %s' % (msg, BATTLEQUOTES_C))
        text = text.replace(orig, (
            '        .flag    = 0x0000, /* lord select (#42): game over is keyed\n'
            '                              to the chosen lead (UnitKill hook), not\n'
            '                              this slot; quote stays */\n'
            '        .msg     = %s,\n' % msg), 1)
    with open(BATTLEQUOTES_C, 'w', encoding='utf-8') as f:
        f.write(text)

    # 5: bmmenu.c -- convoy/supply gate. SupplyUsability hardcodes the route lord
    #    (Eirika/Ephraim) as the unit that can open the supply anywhere; a cast member
    #    riding that slot (e.g. CHARACTER_EIRIKA) inherits free convoy access.
    #    Route it through the chosen lead instead (mirrors the Seize gate).
    with open(BMMENU_C, encoding='utf-8') as f:
        text = f.read()
    orig = ('    switch (gPlaySt.chapterModeIndex)\n'
            '    {\n'
            '        case CHAPTER_MODE_EIRIKA:\n'
            '            pid = CHARACTER_EIRIKA;\n'
            '            break;\n'
            '\n'
            '        case CHAPTER_MODE_EPHRAIM:\n'
            '            pid = CHARACTER_EPHRAIM;\n'
            '            break;\n'
            '\n'
            '        default:\n'
            '            pid = CHARACTER_EIRIKA;\n'
            '            break;\n'
            '    }\n')
    if text.count(orig) != 1:
        sys.exit('ERROR: SupplyUsability lord switch not in expected vanilla form in %s'
                 % BMMENU_C)
    patched = ('    /* Lord select (campaign engine, #42): convoy access belongs to the\n'
               '       player-chosen lead (vanilla hardcoded Eirika/Ephraim by route). The\n'
               '       cast ride ordinary slots, so a unit on the Eirika slot must NOT get\n'
               '       free supply unless they ARE the chosen lord. */\n'
               '    {\n'
               '        extern u16 LordSelect_GetPid(void);\n'
               '        pid = LordSelect_GetPid();\n'
               '    }\n')
    with open(BMMENU_C, 'w', encoding='utf-8') as f:
        f.write(text.replace(orig, patched, 1))

    # 6: data_event_trigger.c -- the vanilla static force-deploy table. It hard-fields
    #    Eirika/Ephraim (and later-route units) BY SLOT; our cast ride those slots, so
    #    e.g. CHARACTER_EIRIKA in COMMON mode force-fields whoever rides it every chapter, on top
    #    of the player's chosen lead. Clear it: the ONLY forced unit is the chosen lead
    #    (the IsCharacterForceDeployed_ hook, #2 above). Any future per-chapter forced
    #    unit is added our way, not via this vanilla table.
    with open(DATA_EVENT_TRIGGER_C, encoding='utf-8') as f:
        text = f.read()
    cleared = ('{\n'
               '    /* Lord select (campaign engine, #42): cleared -- the chosen lead is\n'
               '       force-fielded by IsCharacterForceDeployed_; vanilla\'s by-slot\n'
               '       entries would wrongly force cast members riding those slots. */\n'
               '    {-1, 0, 0},\n'
               '}')
    text = _replace_brace_block(text, 'gForceDeploymentList[] =', cleared,
                                DATA_EVENT_TRIGGER_C)
    with open(DATA_EVENT_TRIGGER_C, 'w', encoding='utf-8') as f:
        f.write(text)


def _inject_lord_floor_engine():
    """Lord survivability floor (#45 3c), engine side: bake the player-chosen lead's
    base-level top-up into its stats ONCE, the first player phase it is fielded.

    Consumes the build-generated gLordFloorDeltas[] table (inject_ch01, events_udefs.c):
    one { +maxHP, +Def, +Res } row per candidate, parallel to gLordSelectCandidates[]. Two
    campaign-agnostic hooks (string-replace + count-guard, like _inject_lord_select_engine,
    which MUST run first -- this anchors on its injected LordSelect_GetPid):

      1. LordFloor_ApplyOnce (new, eventinfo.c): find the chosen lead's index via the
         lord-select flags, look up its floor row, add it to maxHP/curHP/def/res, then set a
         permanent "applied" flag. No-op once applied; no-op until a pick exists (prologue:
         nothing chosen -> skip) and the lead is on the field. The applied flag is spent ONLY
         on a real application, so it can never be consumed early -> the floor always lands.

      2. EndPrepScreen (prep_sallycursor.c): call it once the prep "Fight!" has finalized
         deployment (right after ShrinkPlayerUnits compacts the roster). The chosen lead is
         deployed + VALID here and the pick is already recorded (the menu runs earlier, in the
         beginning scene). Phase-start seams (BmMain_StartPhase, the cursor reset) fire BEFORE
         prep deployment finalizes on turn 1 -- the lead isn't findable yet, so the floor lands
         a phase late (ch01 verified -- tools/playtest lordfloor showed +7 at turn 2, not turn
         1). Lord-select is always a prep chapter, so this single deployment seam suffices; the
         apply-once flag covers later Fight!s.
    """
    # 1: eventinfo.c -- LordFloor_ApplyOnce, right after the injected LordSelect_GetPid.
    with open(EVENTINFO_C, encoding='utf-8') as f:
        text = f.read()
    anchor = ('    return gLordSelectCandidates[0];\n'
              '}\n')
    if text.count(anchor) != 1:
        sys.exit('ERROR: LordSelect_GetPid tail not found in %s -- '
                 '_inject_lord_floor_engine must run after _inject_lord_select_engine'
                 % EVENTINFO_C)
    floor_fn = (
        '    return gLordSelectCandidates[0];\n'
        '}\n'
        '\n'
        '/* Lord survivability floor (campaign engine, #45 3c): once, at the first\n'
        '   player phase the chosen lead is fielded, add its base-level top-up\n'
        '   (gLordFloorDeltas, events_udefs.c -- { +maxHP, +Def, +Res } per candidate,\n'
        '   parallel to gLordSelectCandidates) to maxHP/curHP/Def/Res. A permanent\n'
        '   "applied" flag makes it happen exactly once and bake into the save, then\n'
        '   fade as the unit levels (Jagen-style). No-op until the ch01 menu has\n'
        '   recorded a pick (prologue: skip, flag stays clear) and the lead is on the\n'
        '   map -- the applied flag is spent ONLY on a real application, never early. */\n'
        'void LordFloor_ApplyOnce(void)\n'
        '{\n'
        '    extern const u16 gLordSelectCandidates[];\n'
        '    extern const s8 gLordFloorDeltas[];\n'
        '    struct Unit * unit;\n'
        '    int i;\n'
        '\n'
        '    if (CheckFlag(0x%X))\n'
        '        return;\n'
        '\n'
        '    /* the ch01 menu records the pick as permanent flag 0x%X + menu index */\n'
        '    for (i = 0; gLordSelectCandidates[i] != 0xFFFF; i++) {\n'
        '        if (CheckFlag(0x%X + i))\n'
        '            break;\n'
        '    }\n'
        '    if (gLordSelectCandidates[i] == 0xFFFF)\n'
        '        return; /* no pick yet (prologue) -- retry next chapter */\n'
        '\n'
        '    unit = GetUnitFromCharId(gLordSelectCandidates[i]);\n'
        '    if (unit == NULL)\n'
        '        return; /* chosen lead not on the field yet -- retry, flag stays clear */\n'
        '\n'
        '    unit->maxHP += gLordFloorDeltas[i * 3 + 0];\n'
        '    unit->curHP += gLordFloorDeltas[i * 3 + 0];\n'
        '    unit->def   += gLordFloorDeltas[i * 3 + 1];\n'
        '    unit->res   += gLordFloorDeltas[i * 3 + 2];\n'
        '\n'
        '    SetFlag(0x%X);\n'
        '}\n'
        % (LORDFLOOR_APPLIED_FLAG, LORDSEL_FLAG_BASE, LORDSEL_FLAG_BASE,
           LORDFLOOR_APPLIED_FLAG))
    with open(EVENTINFO_C, 'w', encoding='utf-8') as f:
        f.write(text.replace(anchor, floor_fn, 1))

    # 2: prep_sallycursor.c -- call it at the END of EndPrepScreen, right after
    #    ShrinkPlayerUnits() has compacted the deployed roster. This is the deployment-
    #    finalization point on the prep "Fight!" path: the chosen lead is force-deployed and
    #    VALID here, and the ch01 lord-select menu (which runs earlier, in the beginning scene)
    #    has already recorded the pick. Phase-start seams (BmMain_StartPhase, the cursor reset)
    #    fire BEFORE prep deployment finalizes on turn 1, so the lead isn't yet findable and
    #    the floor lands a phase late (ch01 verified via tools/playtest lordfloor: those seams
    #    gave +7 at turn 2, not turn 1). Lord-select is always a prep chapter, and the
    #    apply-once flag covers every later Fight!, so this single seam suffices.
    with open(PREP_SALLYCURSOR_C, encoding='utf-8') as f:
        text = f.read()
    orig = ('    ShrinkPlayerUnits();\n'
            '    Proc_EndEach(gProcScr_SALLYCURSOR);\n')
    if text.count(orig) != 1:
        sys.exit('ERROR: EndPrepScreen ShrinkPlayerUnits tail not in expected vanilla form '
                 'in %s' % PREP_SALLYCURSOR_C)
    hooked = ('    ShrinkPlayerUnits();\n'
              '\n'
              '    /* Lord survivability floor (campaign engine, #45 3c): now that the chosen\n'
              '       lead is deployed and the roster is finalized, bake its base-level top-up\n'
              '       in once. Apply-once flag makes later prep Fight!s no-ops. */\n'
              '    {\n'
              '        extern void LordFloor_ApplyOnce(void);\n'
              '        LordFloor_ApplyOnce();\n'
              '    }\n'
              '\n'
              '    Proc_EndEach(gProcScr_SALLYCURSOR);\n')
    with open(PREP_SALLYCURSOR_C, 'w', encoding='utf-8') as f:
        f.write(text.replace(orig, hooked, 1))


def _inject_crit_d20_flourish():
    """#11: the cosmetic nat-20 flourish. When an FE crit fires in a battle anim,
    a d20 showing 20 pops on the effect layer (BG1) the exact frame the vanilla
    crit flash tears down -- both the plain crit flash AND the pierce-crit flash
    (Silencer is deliberately excluded: it has its own distinctive Chill flourish,
    and no MVP cast member can Silencer anyway). FE crit math stays the SOLE
    trigger: these teardowns only ever run on a crit round.

    The die is PROC-LESS: registered once, then the vanilla effect lifecycle owns
    BG1 -- a successor effect (brave second hit, magic counter's spell background)
    simply draws over it, and the battle-scene exit resets the layer. Nothing of
    ours ever clears BG1 later, so no lingering proc can blank a newcomer's
    tilemap mid-display (the clobber class a timed teardown would create). It is
    a centered HUD overlay copied through the non-mirrored tilemap path, so the
    "20" never mirrors with attacker side. Asset symbols (Img/Pal/Tsa_MsD20Crit)
    are injected from the campaign by build_campaign.inject_crit_flourish -- this
    patch is campaign-agnostic."""
    with open(BANIM_EFXHIT_C, encoding='utf-8') as f:
        text = f.read()
    if 'MS #11' in text:
        return

    anchor = 'CONST_DATA struct ProcCmd ProcScr_efxCriricalEffect[] = {'
    if text.count(anchor) != 1:
        sys.exit('ERROR: ProcScr_efxCriricalEffect not in expected vanilla form '
                 'in %s' % BANIM_EFXHIT_C)
    block = (
        '#include "constants/video-banim.h" /* OBJPAL_BANIM_SPELL_BG (MS #11) */\n'
        '\n'
        '/* MS #11: cosmetic nat-20 flourish -- drawn once at a crit flash teardown;\n'
        '   the vanilla effect lifecycle owns BG1 from there (a successor effect\n'
        '   overwrites it, the scene exit resets it). */\n'
        'extern const u16 Img_MsD20Crit[];\n'
        'extern const u16 Pal_MsD20Crit[];\n'
        'extern const u16 Tsa_MsD20Crit[];\n'
        '\n'
        'static void MsD20CritShow(void)\n'
        '{\n'
        '    SpellFx_RegisterBgGfx(Img_MsD20Crit, 0x2000);\n'
        '    SpellFx_RegisterBgPal(Pal_MsD20Crit, 0x20);\n'
        '    LZ77UnCompWram(Tsa_MsD20Crit, gEkrTsaBuffer);\n'
        '    EfxTmCpyBG(gEkrTsaBuffer, gBG1TilemapBuffer, 30, 20,\n'
        '               OBJPAL_BANIM_SPELL_BG, 0x100);\n'
        '    BG_EnableSyncByMask(BG1_SYNC_BIT);\n'
        '}\n'
        '\n')
    text = text.replace(anchor, block + anchor, 1)

    # hook BOTH crit-flash teardowns (plain + pierce); the bare body appears in
    # more than one proc, so anchor on each enclosing function
    for fn in ('efxCriricalEffectBGMain', 'efxPierceCriticalEffectBGMain'):
        orig = ('void %s(struct ProcEfxBG * proc)\n'
                '{\n'
                '    if (++proc->timer == 0x11) {\n'
                '        SpellFx_ClearBG1();\n'
                '        SetDefaultColorEffects_();\n'
                '        Proc_Break(proc);\n'
                '    }\n'
                '}\n' % fn)
        if text.count(orig) != 1:
            sys.exit('ERROR: %s teardown not in expected vanilla form in %s'
                     % (fn, BANIM_EFXHIT_C))
        hooked = orig.replace(
            '        SetDefaultColorEffects_();\n',
            '        SetDefaultColorEffects_();\n'
            '        MsD20CritShow(); /* MS #11: the nat-20 die takes the cleared layer */\n')
        text = text.replace(orig, hooked, 1)
    with open(BANIM_EFXHIT_C, 'w', encoding='utf-8') as f:
        f.write(text)
