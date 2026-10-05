"""Faked battle animations (#65): per-character battle anims built from reference art.
"""
import os
import re
import sys

from yaml_loader import yaml_load
import banim_palette
import feditor_to_banim
import ref_to_battleframe
from inject.cast import _chapter_unit, char_symbol, PORTRAIT_MAP, RAW_PID_BATTLE_ANIMS
from inject.decomp import _find_brace_block, REPO
from inject.paths import (
    BANIM_DATA_C, BANIM_DATA_DIR, BANIM_EKRBATTLE_H, BANIM_GFX_DIR, BANIM_LINKER, BANIM_POINTER_H,
    BANIMCONF_C, BANIMCONFUNK_C, CHARACTERS_C, CLASSES_C)



def append_banim_link_block(label, block):
    """Append one anim's assets to the ext compressing-linker script (engine patch 0016),
    starting the script with its format header if this build has not written it yet.
    restore_vanilla_sources deletes it, so every build writes it whole."""
    new = not os.path.exists(BANIM_LINKER)
    with open(BANIM_LINKER, 'a', encoding='utf-8') as f:
        if new:
            f.write('# Battle anims Manchego Stars adds, linked past the 16MB image (patch 0016)\n'
                    '# Format: file|section>compression\n')
        f.write('\n# Manchego Stars %s\n' % label)
        f.write('\n'.join(block) + '\n')

# Give a unit a custom battle anim from 1-3 static frames + the engine's effects, with
# NO hand-drawn motion. ref_to_battleframe generates the assets (sheets + agbpal + motion.s)
# cloning a donor class's timing; this injects them ADDITIVELY: append a banim_data[] row
# (-> a new animId), then -- so generic/enemy units of the class stay vanilla -- register a
# PRIVATE AnimConf for the CHARACTER in gUnitSpecificBanimConfigs and point its _u25 at it
# (the per-character path; _patch_banim_character_unique routes combat through
# GetBattleAnimationId_WithUnique). No class clone: the unit deploys as its plain vanilla
# class (deploy_class_for). Nothing vanilla is overwritten (donor class + AnimConf
# byte-unchanged). Reversible: the patched files restore each build.

# donor 'clone_from' -> (FE donor class enum, the AnimConf weapon entry to repoint in the
# clone, the cadence the faked motion.s is built with: 'ranged' draw-and-fire / 'melee'
# lunge-and-swing). The cadence is studied from the donor class's own vanilla motion.s.
# clone_from: (donor_class, weapon_type, motion, melee_cadence). `motion` picks the mode
# SHAPE (ranged draw-and-fire vs melee lunge-and-swing); `melee_cadence` picks the per-donor
# sound/FX punctuation within a melee body (ref_to_battleframe._MELEE_CADENCE) -- None for
# ranged donors, which never run a melee body.
BANIM_DONORS = {
    'archer': ('CLASS_ARCHER',       '0x0100 | ITYPE_BOW',   'ranged', None),
    'shaman': ('CLASS_SHAMAN',       '0x0100 | ITYPE_DARK',  'magic',  None),
    'mage':   ('CLASS_MAGE',         '0x0100 | ITYPE_ANIMA', 'magic',  None),
    'pirate': ('CLASS_PIRATE',       '0x0100 | ITYPE_AXE',   'melee',  'axe'),
    'knight': ('CLASS_ARMOR_KNIGHT', '0x0100 | ITYPE_LANCE', 'melee',  'lance'),
    # Pinky (the flier) -- his anim is an IMPORTED N-frame swoop (feditor_to_banim, #90), so
    # `motion`/`cadence` here are unused (the motion.s comes from the .txt); the donor only
    # supplies the AnimConf to clone + the ITYPE_LANCE slot to repoint for her per-character
    # _u25. A flier's hover-and-dive can't be faked from 3 static poses (decisions.md).
    'pegasus': ('CLASS_PEGASUS_KNIGHT', '0x0100 | ITYPE_LANCE', 'melee', 'lance'),
    # Sclorbo (the army's first healer, Priest->Bishop). Cloning the BISHOP AnimConf gives
    # BOTH a STAFF slot (drives the MVP: heal-cast + defense as a Priest) and a LIGHT slot
    # (the post-promotion attack). Both slots repoint to his ONE custom animId; call_spell_anim
    # resolves heal-efx vs light-efx from the equipped item at runtime. Basil (#25) reuses this.
    # ITYPE_ITEM joined the list on the #25 review: the Bishop AnimConf carries five slots
    # (STAFF/ANIMA/LIGHT/DARK/ITEM) and leaving ITEM vanilla means a healer holding no staff --
    # both spent, only a Vulnerary left -- renders as a HUMAN BISHOP in the close-up. That is
    # the cavalier row's rule ("every slot left vanilla is a slot where the wolf renders as a
    # man on a horse", #206) applied to the class that needed it next. ANIMA/DARK stay vanilla
    # deliberately: neither this line's Priest nor its Bishop promotion can equip those, so a
    # repoint there would be dead weight, not coverage.
    # Ravisin (ch05's frost-druid boss, #25). Her animation is an IMPORTED FE-native one
    # (feditor_to_banim), so `motion`/`cadence` are unused -- the .txt owns them; the donor only
    # supplies the AnimConf to clone and the slots to repoint for her per-character _u25.
    # WHICH SLOTS is the cavalier row's rule (#206) applied to a Druid: every slot left vanilla
    # is a slot where she renders as a HOODED MAN. data_classes.c gives CLASS_DRUID baseRanks
    # STAFF/ANIMA/DARK, so all three are reachable in play (DARK first -- her Flux is the fight),
    # and ITEM covers her holding a plain item with her tome spent. LIGHT is deliberately left
    # vanilla: no Druid can equip it, so repointing it would be dead weight, not coverage --
    # exactly the call the bishop row makes about ANIMA/DARK below.
    'druid': ('CLASS_DRUID', ['0x0100 | ITYPE_DARK', '0x0100 | ITYPE_ANIMA',
                              '0x0100 | ITYPE_STAFF', '0x0100 | ITYPE_ITEM'], 'magic', None),
    'bishop': ('CLASS_BISHOP', ['0x0100 | ITYPE_STAFF', '0x0100 | ITYPE_LIGHT',
                                '0x0100 | ITYPE_ITEM'], 'magic', None),
    # Lupin (the beast-cavalier) -- his anim is an IMPORTED N-frame POUNCE (feditor_to_banim, #90),
    # so `motion`/`cadence` are unused (the .txt owns them, and its cadence is read off FE8's own
    # wolf `banim_mdg_at1`, not off this donor). The donor supplies the AnimConf to clone; ALL
    # THREE of the Cavalier's weapon slots are repointed, because every slot left vanilla is a
    # slot where the wolf renders as A MAN ON A HORSE -- which is the whole defect in #206.
    # ITYPE_ITEM is the unarmed/item entry, reachable whenever he holds no weapon. Baxby (#206's
    # other half, the axe-beak) is the same class and reuses this row.
    'cavalier': ('CLASS_CAVALIER', ['0x0100 | ITYPE_SWORD', '0x0100 | ITYPE_LANCE',
                                    '0x0100 | ITYPE_ITEM'], 'melee', 'lance'),
    # Sahnar (the risen duelist, #25) -- an IMPORTED 12-mode Specter script (feditor_to_banim),
    # so `motion`/`cadence` go unused for HER: the .txt owns the cadence and the sound codes.
    # They are still filled in properly rather than left None, because the row is the donor for
    # the class, not for one unit -- and the 'sword' cadence it names is read off FE8's own
    # banim_myrm_sw1 (ref_to_battleframe._MELEE_CADENCE). BOTH of the donor's slots are
    # repointed: the Myrmidon AnimConf is SWORD + ITEM, and ITYPE_ITEM is the UNARMED entry --
    # reachable the moment both her swords break and she is carrying only a Vulnerary. Left
    # vanilla it draws a HUMAN MYRMIDON instead of the revenant, which is the cavalier row's
    # #206 defect exactly. Caught on review, not in play (#25).
    'myrmidon': ('CLASS_MYRMIDON', ['0x0100 | ITYPE_SWORD', '0x0100 | ITYPE_ITEM'],
                 'melee', 'sword'),
    # The white moose (#25) -- ch05's cornered miniboss, and the first BEAST to fight in a
    # close-up. Unlike every donor above it, the moose is not cast: it is the raw on-map pid
    # 0xb9, so its `_u25` binds to a gCharacterData GAP (see RAW_PID_BATTLE_ANIMS).
    # CLASS_GWYLLGI is the class it already deploys as, and its cadence is read off that
    # class's OWN anim, banim_cer_at1 -- Nicolas's call, 2026-08-15. Note cer_at1 (0xB1) is
    # the GWYLLGI's; banim_mdg_at1 (0xB0) is the Mauthe Doog's, and is the one Lupin's
    # imported pounce reads. They are different scripts for the unpromoted and promoted beast.
    # BOTH of the donor's slots are repointed: MONSTER is the antlers-and-hooves attack
    # (fe_base fire-fang) and ITEM is the UNARMED entry. Left vanilla, ITEM draws the stock
    # purple HOUND -- the cavalier row's #206 defect, on the one chapter whose miniboss is an
    # elk and whose YAML has said "the FE-Repo has NO elk art" since July.
    'gwyllgi': ('CLASS_GWYLLGI', ['0x0100 | ITYPE_MONSTER', '0x0100 | ITYPE_ITEM'],
                'melee', 'beast'),
}


def build_unit_battle_anim(cfg, anim_dir, abbr, motion, cadence):
    """Build a unit's battle-anim assets, returning {"sheets", "pal", "motion_s"}.

    Two sources, ONE asset shape (so the injector's binding is identical either way):
    - `import: {txt, frames_dir}` -> a real N-frame FE-native animation transcribed by
      feditor_to_banim (#90). Used when 3 faked poses can't carry the motion -- e.g. Pinky's
      flier swoop (launch/apex/dive/return). The `.txt` owns the cadence; each frame's canvas
      position is the on-screen motion. This is the enemy #90 path bound per-CHARACTER, not
      per-class.
      Optional `palette_edit: <path>` -- a HAND-EDITED palette written by
      tools/banim_palette.py, applied as build_import's `recolor`. A vendored anim arrives on
      the author's colours, and for a unit those can be wrong on faction (Ravisin's blue robe)
      while being right on everything else (her auburn hair, the reason her anim was chosen).
      The class path's `recolor:` names a FUNCTION for that; a character's look is a by-eye
      call, so this names a FILE instead. Either way it recolours the agbpal ONLY -- the sheet
      indices are untouched, so an edit is reversible and never a re-import (#25).
    - else `frames: [...]` -> the faked 3-pose generator (ref_to_battleframe, #65), whose mode
      bodies are built from the donor's `motion`/`cadence`.
    """
    imp = cfg.get('import')
    if imp:
        txt = os.path.join(anim_dir, imp['txt'])
        frames_dir = os.path.join(anim_dir, imp.get('frames_dir')
                                  or os.path.dirname(imp['txt']))
        recolor = (banim_palette.load_recolor(os.path.join(anim_dir, imp['palette_edit']))
                   if imp.get('palette_edit') else None)
        res = feditor_to_banim.build_import(abbr, txt, frames_dir, recolor=recolor)
        if recolor is not None:
            # The edit is stored per-INDEX and applied per-COLOUR; if the frames are ever
            # re-vendored under it, an entry it names can simply cease to exist and that
            # colour ships NATIVE behind a green build. Nothing else compares the two.
            banim_palette.assert_all_applied(recolor, 'battle_anim %s' % abbr)
        return res
    from PIL import Image
    frame_imgs = [Image.open(os.path.join(anim_dir, p)).convert('RGBA')
                  for p in cfg['frames']]
    palette = _banim_palette(frame_imgs)
    return ref_to_battleframe.build_battle_anim(abbr, frame_imgs, palette, motion=motion,
                                                cadence=cadence or 'axe')


def banim_append_row(text, abbr):
    """Append a banim_data[] row for `abbr`; return (new_text, anim_id).

    anim_id = the count of existing rows (the table is appended-to, so the donor rows are
    byte-unchanged and `banim_number = sizeof(...)` picks up the growth automatically)."""
    anim_id = text.count('\t{"')
    row = ('\t{"%s", &banim_%s_modes_bin, &banim_%s_motion_o, &banim_%s_oam_r_bin, '
           '&banim_%s_oam_l_bin, &banim_%s_agbpal}, // 0x%X (#65)\n'
           % (abbr, abbr, abbr, abbr, abbr, abbr, anim_id))
    close = text.rindex('};')
    return text[:close] + row + text[close:], anim_id


def banim_unique_append(text, conf_sym):
    """Append `conf_sym` to gUnitSpecificBanimConfigs[] (#65 M-B); return (text, index).

    The character-unique path (no class slot): a unit's AnimConf is registered here and the
    character's _u25 points at the returned index. Self-sizing, so existing rows are
    byte-unchanged. index = the count of existing entries (each carries a trailing comma)."""
    marker = 'gUnitSpecificBanimConfigs[] = {'
    bs = text.index(marker) + len(marker)
    be = text.index('};', bs)
    block = text[bs:be]
    index = block.count(',')
    return text[:bs] + block.rstrip() + '\n    %s,\n' % conf_sym + text[be:], index


def banim_spell_palette_tint_append(text, rows):
    """Append the campaign-declared character/weapon spell-tint rows once."""
    character_include = '#include "constants/characters.h"\n'
    if character_include not in text:
        anchor = '#include "constants/items.h"\n'
        if anchor not in text:
            raise ValueError('battle-animation data file is missing constants/items.h include')
        text = text.replace(anchor, anchor + character_include, 1)
    marker = 'gBanimSpellPaletteTints[]'
    if marker in text:
        return text
    block = '\nCONST_DATA struct BanimSpellPaletteTint %s = {\n' % marker
    for character, weapon_type, tint in rows:
        block += '    { %s, %s, %s },\n' % (character, weapon_type, tint)
    block += '    { 0, 0, BANIM_SPELL_TINT_NONE },\n};\n'
    return text + block


def banim_charge_flash_append(text, rows):
    """Append the campaign-declared per-caster charge-flash rows once (#183, #191 waveform).

    Each row is (character, weapon_type, target_bgr555, waveform) -- the caster's own sprite
    pulses toward `target_bgr555` on the wind-up beat, using LUT `waveform` (0 = pulse, the
    existing 3-throb throb; 1 = build, a single slow swell). The colour rides as a raw BGR555
    u16 so the engine blends toward any hue without a per-colour enum. Zero-character row
    terminates."""
    character_include = '#include "constants/characters.h"\n'
    if character_include not in text:
        anchor = '#include "constants/items.h"\n'
        if anchor not in text:
            raise ValueError('battle-animation data file is missing constants/items.h include')
        text = text.replace(anchor, anchor + character_include, 1)
    marker = 'gMSChargeFlashes[]'
    if marker in text:
        return text
    block = '\nCONST_DATA struct BanimChargeFlash %s = {\n' % marker
    for character, weapon_type, target, waveform in rows:
        block += '    { %s, %s, %s, %d },\n' % (character, weapon_type, target, waveform)
    block += '    { 0, 0, 0, 0 },\n};\n'
    return text + block


def banim_set_char_u25(block, index):
    """Set a character block's `._u25 = { index, index }` (#65 M-B), inserting after
    `.number` if absent, overwriting in place if already present (both promote states)."""
    val = '._u25 = { %d, %d },' % (index, index)
    if '._u25' in block:
        return re.sub(r'\._u25 = \{[^}]*\},', val, block)
    m = re.search(r'\n([ \t]*)\.number = [^\n]*\n', block)
    return block[:m.end()] + m.group(1) + val + '\n' + block[m.end():]


def banim_repoint_conf(text, conf_sym, wtype_literal, new_index):
    """In AnimConf `conf_sym`, set the `.index` of the entry matching `wtype_literal`."""
    bs, be = _find_brace_block(text, '%s[] =' % conf_sym, BANIMCONF_C)
    block = text[bs:be]
    pat = re.compile(r'(\.wtype\s*=\s*' + re.escape(wtype_literal) +
                     r'\s*,\s*\.index\s*=\s*)(0x[0-9A-Fa-f]+|\d+)')
    new_block, n = pat.subn(lambda m: '%s0x%X' % (m.group(1), new_index), block, count=1)
    if n == 0:
        sys.exit('ERROR: banim repoint: wtype %r not found in %s' % (wtype_literal, conf_sym))
    return text[:bs] + new_block + text[be:]


def banim_clone_conf(text, src_sym, new_sym, wtype_literal, new_index):
    """Append a COPY of AnimConf `src_sym` as `new_sym`, with the `wtype_literal` entry's
    `.index` set to `new_index`. `src_sym` is left byte-unchanged (the donor class keeps the
    vanilla anim). Returns the new text (declaration appended)."""
    bs, be = _find_brace_block(text, '%s[] =' % src_sym, BANIMCONF_C)
    block = text[bs:be]
    pat = re.compile(r'(\.wtype\s*=\s*' + re.escape(wtype_literal) +
                     r'\s*,\s*\.index\s*=\s*)(0x[0-9A-Fa-f]+|\d+)')
    new_block, n = pat.subn(lambda m: '%s0x%X' % (m.group(1), new_index), block, count=1)
    if n == 0:
        sys.exit('ERROR: banim clone: wtype %r not found in %s' % (wtype_literal, src_sym))
    return text + '\nCONST_DATA struct BattleAnimDef %s[] = %s;\n' % (new_sym, new_block)


def _banim_palette(frame_imgs):
    """A <=16-colour palette for the frames: index 0 transparent + each opaque colour."""
    pal = [(0, 0, 0)]
    for im in frame_imgs:
        # 1<<24 is load-bearing, not slack: it fixes getcolors' bucket order, and hence this
        # palette's order (feditor_to_banim._palette carries the long note; decisions.md ->
        # "The injector was slow in Python, not in work").
        for cnt, rgba in im.getcolors(1 << 24):
            rgb = rgba[:3]
            # OBJ palette index 0 is transparent even when its BGR555 colour is black.
            # Retain an opaque black as a duplicate at index 1+ rather than mapping it
            # to that transparent slot.
            if rgba[3] > 0 and (rgb not in pal or (rgb == pal[0] and pal.count(rgb) == 1)):
                pal.append(rgb)
    return pal


def units_with_battle_anim(campaign):
    """(unit_id, unit) for every unit carrying a `battle_anim:` block.

    Two sources, because a battle anim is not the cast's alone. Cast members declare it on
    their own pcs/npcs YAML. A named RAW-PID creature (RAW_PID_BATTLE_ANIMS) declares it on
    the chapter YAML that already owns the rest of its identity -- pid, class, AI, art recipe,
    death quote -- rather than gaining a second definition site in npcs/, which would also
    make `classed_cast` treat a miniboss as a deployable cast member.
    """
    out = []
    for sub in ('pcs', 'npcs'):
        d = os.path.join(REPO, 'campaigns', campaign, sub)
        if not os.path.isdir(d):
            continue
        for fn in sorted(os.listdir(d)):
            if not fn.endswith('.yaml'):
                continue
            with open(os.path.join(d, fn), encoding='utf-8') as f:
                u = yaml_load(f)
            if u and u.get('battle_anim'):
                out.append((u.get('id', fn[:-5]), u))
    for uid, (chapter_yaml, _pid) in sorted(RAW_PID_BATTLE_ANIMS.items()):
        unit = _chapter_unit(campaign, chapter_yaml, uid)
        if unit.get('battle_anim'):
            out.append((uid, unit))
    return out


def banim_u25_marker(unit_id):
    """The gCharacterData designator whose `._u25` binds this unit's private AnimConf.

    A cast member rides a vanilla CHARACTER_ slot (PORTRAIT_MAP) and is addressed by enum. A
    named raw-pid creature is a gCharacterData GAP with no enum at all, and is addressed by
    its raw pid -- the same `[0xNN - 1]` designator raw_pid_portrait_data already writes
    through. The engine draws no distinction: GetBattleAnimationId_WithUnique reads
    `unit->pCharacterData->_u25`, which is the same field on either row.
    """
    raw = RAW_PID_BATTLE_ANIMS.get(unit_id)
    if raw:
        return '[%s - 1]' % raw[1].lower()
    slot = PORTRAIT_MAP.get(unit_id)
    if not slot:
        sys.exit('ERROR: battle_anim %s: no PORTRAIT_MAP slot and no raw pid for _u25'
                 % unit_id)
    return '[CHARACTER_%s - 1]' % slot.upper()


def battle_spell_palette_tints(campaign):
    """(character enum, weapon type, tint enum) rows declared by battle_anim YAML.

    A block declares either a single `weapon_type:` (one row -- Marty/Rootis, unchanged) or a
    `weapon_types:` LIST (one row per type -- Sclorbo's staff + light both cyan). If neither key
    is present, auto-emit a row for each of the donor's bound weapon types."""
    tint_enums = {
        'green': 'BANIM_SPELL_TINT_GREEN',
        'blue': 'BANIM_SPELL_TINT_BLUE',
        'cyan': 'BANIM_SPELL_TINT_CYAN',   # Sclorbo's flame cyan -- bright equal G+B (#191)
        'gold': 'BANIM_SPELL_TINT_GOLD',   # Basil's goodberry gold -- cyan's mirror (#25)
    }
    type_enums = {
        'dark': 'ITYPE_DARK',
        'anima': 'ITYPE_ANIMA',
        'staff': 'ITYPE_STAFF',
        'light': 'ITYPE_LIGHT',
    }
    out = []
    for uid, unit in units_with_battle_anim(campaign):
        tint = unit['battle_anim'].get('spell_palette_tint')
        if not tint:
            continue
        try:
            if 'weapon_types' in tint:
                wtypes = [type_enums[w] for w in tint['weapon_types']]
            elif 'weapon_type' in tint:
                wtypes = [type_enums[tint['weapon_type']]]
            else:
                donor = BANIM_DONORS[unit['battle_anim']['clone_from']]
                donor_wtypes = donor[1] if isinstance(donor[1], list) else [donor[1]]
                wtypes = [w.split('|')[-1].strip() for w in donor_wtypes]
            color = tint_enums[tint['color']]
            slot = PORTRAIT_MAP[uid]
        except KeyError as e:
            sys.exit('ERROR: battle_anim %s spell_palette_tint: unsupported %s' %
                     (uid, e))
        for weapon_type in wtypes:
            out.append((char_symbol(slot), weapon_type, color))
    return out


# Per-caster charge-flash colours (#183): the sprite pulses toward this hue on the wind-up
# beat. Each caster's identity colour; blended additively (a wash), so any hue works.
CHARGE_FLASH_RGB = {
    'blue':   (120, 205, 255),   # ice (Rootis)
    'green':  (110, 255, 120),   # (Marty)
    'purple': (200, 120, 255),   # (Meesmickle)
    'cyan':   (31, 219, 219),    # flame cyan (Sclorbo, #191, Nicolas-approved -> BGR555 0x6F63)
    'gold':   (255, 205, 70),    # goodberry gold (Basil, #25) -- warm, and far enough off
                                 # Sclorbo's cyan that the two healers never read alike
}


def charge_flash_target(color):
    """A named charge-flash colour -> its BGR555 hex string (the blend target)."""
    r, g, b = CHARGE_FLASH_RGB[color]
    return '0x%04X' % ((r >> 3) | ((g >> 3) << 5) | ((b >> 3) << 10))


def battle_charge_flashes(campaign):
    """(character, weapon_type, target_bgr555, waveform) rows from battle_anim `charge_flash`
    blocks. waveform: 0 = pulse (default, the existing 3-throb LUT), 1 = build (a single slow
    swell), from `charge_flash.waveform: 'pulse'|'build'`.

    The weapon type is the caster's DONOR weapon type (the flash arms for whatever tome the
    faked anim is bound to), so a `charge_flash` block only needs a colour. A donor's weapon
    type may be a single string (one row) or a LIST (e.g. Sclorbo's bishop donor -- staff +
    light) -- emit one row per weapon type so the glow arms on every bound tome/staff."""
    waveform_ids = {'pulse': 0, 'build': 1}
    out = []
    for uid, unit in units_with_battle_anim(campaign):
        flash = unit['battle_anim'].get('charge_flash')
        if not flash:
            continue
        try:
            donor = BANIM_DONORS[unit['battle_anim']['clone_from']]
            target = charge_flash_target(flash['color'])
            waveform = waveform_ids[flash.get('waveform', 'pulse')]
            slot = PORTRAIT_MAP[uid]
        except KeyError as e:
            sys.exit('ERROR: battle_anim %s charge_flash: unsupported %s' % (uid, e))
        donor_wtypes = donor[1] if isinstance(donor[1], list) else [donor[1]]
        for wtype_literal in donor_wtypes:
            weapon_type = wtype_literal.split('|')[-1].strip()   # '0x0100 | ITYPE_ANIMA' -> 'ITYPE_ANIMA'
            out.append((char_symbol(slot), weapon_type, target, waveform))
    return out


def inject_battle_anims(campaign, verbose=True):
    """Generate + inject each unit's faked battle animation (additive donor-prime, #65).

    ADDING A UNIT (the repeatable how): give its YAML a `battle_anim:` block --
        clone_from: archer                  # donor class: timing/effects/modes + the weapon slot
        abbr: <stem>                        # banim asset stem (<=12 chars)
        frames: [<unit>/ready.png, <unit>/windup.png, <unit>/peak.png]  # 1-3, Ready->Windup->Peak
        # (+ optional motion/cadence per BANIM_DONORS; no class key -- see below)
    Frames: BOX-descale the hi-res (e.g. 1920x1080) source poses onto a ~88x64 canvas with a COMMON
    feet-anchor + a protected ~15-colour palette. NEVER re-shrink an already-small frame (non-integer
    re-shrink looks muddy) -- to rescale a unit, re-descale from the hi-res master.

    This APPENDS a banim_data[] row (table self-sizes) and registers a PRIVATE AnimConf for the
    CHARACTER (gUnitSpecificBanimConfigs + the character's _u25, routed by
    _patch_banim_character_unique) -- the donor class, its AnimConf, and every generic/enemy unit
    of it stay byte-vanilla, and the unit deploys as its PLAIN vanilla class (deploy_class_for;
    the earlier clone-class approach is retired). Stats ride STAT_DONOR/
    BASE_DONOR/GROWTH_DONOR; PORTRAIT_MAP ties the unit id -> its vanilla character slot.

    !! OFF-BY-ONE: the private AnimConf `.index` MUST be `anim_id + 1` (GetBattleAnimationId returns
       idx - 1). Get it wrong and a PURPLE DRAGON renders instead of the unit.
    Decisions/rationale: decisions.md (Art & Audio, the per-character _u25 call).
    """
    units = units_with_battle_anim(campaign)
    if not units:
        if verbose:
            print('  (no battle_anim blocks declared)')
        return
    anim_dir = os.path.join(REPO, 'campaigns', campaign, 'battle_anims')
    os.makedirs(BANIM_DATA_DIR, exist_ok=True)
    os.makedirs(BANIM_GFX_DIR, exist_ok=True)

    for uid, unit in units:
        cfg = unit['battle_anim']
        clone_from = cfg['clone_from']
        if clone_from not in BANIM_DONORS:
            sys.exit('ERROR: battle_anim %s: unsupported clone_from %r' % (uid, clone_from))
        donor_class, wtype, motion, cadence = BANIM_DONORS[clone_from]
        motion = cfg.get('motion', motion)            # YAML may override the donor default
        cadence = cfg.get('cadence', cadence)         # ...and its melee cadence
        abbr = cfg.get('abbr') or (uid.replace('-', '').replace('prof', '')[:5] + '_ar1')
        res = build_unit_battle_anim(cfg, anim_dir, abbr, motion, cadence)

        # 1. assets into the decomp (motion.s, per-frame sheet PNGs, agbpal blob)
        with open(os.path.join(BANIM_DATA_DIR, 'banim_%s_motion.s' % abbr), 'w',
                  encoding='utf-8') as f:
            f.write(res['motion_s'])
        for i, sheet in enumerate(res['sheets']):
            sheet.save(os.path.join(BANIM_GFX_DIR, 'banim_%s_sheet_%d.png' % (abbr, i)))
        with open(os.path.join(BANIM_GFX_DIR, 'banim_%s.agbpal' % abbr), 'wb') as f:
            f.write(res['pal'])

        # 2. linker block (sheets, palette, oam, script, modes), in build order
        block = (['graphics/banim/banim_%s_sheet_%d.4bpp.lz' % (abbr, i)
                  for i in range(len(res['sheets']))]
                 + ['graphics/banim/banim_%s.agbpal.lz' % abbr,
                    'data/banim/banim_%s_oam_l.bin.lz' % abbr,
                    'data/banim/banim_%s_oam_r.bin.lz' % abbr,
                    'data/banim/banim_%s_motion.o|.data.script>lz' % abbr,
                    'data/banim/banim_%s_modes.bin' % abbr])
        append_banim_link_block('faked battle anim (#65): %s' % uid, block)

        # 3. banim_data[] row -> new animId, plus its pointer externs
        with open(BANIM_DATA_C, encoding='utf-8') as f:
            text = f.read()
        text, anim_id = banim_append_row(text, abbr)
        with open(BANIM_DATA_C, 'w', encoding='utf-8') as f:
            f.write(text)
        with open(BANIM_POINTER_H, 'a', encoding='utf-8') as f:
            f.write('// battle animation 0x%X (Manchego Stars #65: %s)\n' % (anim_id, uid))
            for sym, ty in [('modes_bin', 'int'), ('motion_o', 'char'),
                            ('oam_r_bin', 'char'), ('oam_l_bin', 'char'),
                            ('agbpal', 'char')]:
                f.write('extern %s banim_%s_%s;\n' % (ty, abbr, sym))

        # 4. CHARACTER-UNIQUE (no class slot, #65 M-B): build the unit's private AnimConf,
        #    register it in the per-character table, and point the character's _u25 at it.
        #    The donor class + every generic/enemy unit of it stay byte-vanilla; only THIS
        #    named character animates custom (the _patch_banim_character_unique engine hook
        #    routes combat through GetBattleAnimationId_WithUnique, which reads _u25). Scales
        #    to every PC + named boss -- bounded by the anim table, not the ~3 class slots.
        new_conf = 'AnimConf_%s' % abbr
        src_conf = _class_field_symbol(donor_class, 'pBattleAnimDef')  # e.g. AnimConf_088AF150
        # 4a. a private AnimConf = copy of the donor's, with the weapon entry -> new animId.
        #     NOTE: AnimConf `.index` is animId+1 -- GetBattleAnimationId returns `idx - 1`
        #     (vanilla archer bow .index 0x26 -> animId 0x25). So encode anim_id + 1.
        with open(BANIMCONF_C, encoding='utf-8') as f:
            conf = f.read()
        wtypes = wtype if isinstance(wtype, list) else [wtype]
        conf = banim_clone_conf(conf, src_conf, new_conf, wtypes[0], anim_id + 1)
        for wt in wtypes[1:]:
            conf = banim_repoint_conf(conf, new_conf, wt, anim_id + 1)
        with open(BANIMCONF_C, 'w', encoding='utf-8') as f:
            f.write(conf)
        with open(BANIM_EKRBATTLE_H, 'a', encoding='utf-8') as f:
            f.write('extern CONST_DATA struct BattleAnimDef %s[]; /* Manchego Stars #65 */\n'
                    % new_conf)
        # 4b. register the AnimConf in gUnitSpecificBanimConfigs[] -> its table index.
        with open(BANIMCONFUNK_C, encoding='utf-8') as f:
            unk = f.read()
        unk, u25 = banim_unique_append(unk, new_conf)
        with open(BANIMCONFUNK_C, 'w', encoding='utf-8') as f:
            f.write(unk)
        # 4c. point the character's _u25 (both promote states) at that index. A cast PC rides a
        #     vanilla character slot (PORTRAIT_MAP); a named raw-pid creature rides its own
        #     gCharacterData gap. The engine hook makes combat consult it either way.
        marker = banim_u25_marker(uid)
        with open(CHARACTERS_C, encoding='utf-8') as f:
            ctext = f.read()
        cs, ce = _find_brace_block(ctext, marker, CHARACTERS_C)
        ctext = ctext[:cs] + banim_set_char_u25(ctext[cs:ce], u25) + ctext[ce:]
        with open(CHARACTERS_C, 'w', encoding='utf-8') as f:
            f.write(ctext)

        if verbose:
            print('  %-14s = banim %s (animId 0x%X); _u25[%d] -> %s on char %s (%s)'
                  % (uid, abbr, anim_id, u25, new_conf, marker, wtype))

    tint_rows = battle_spell_palette_tints(campaign)
    if tint_rows:
        with open(BANIMCONFUNK_C, encoding='utf-8') as f:
            tint_text = f.read()
        with open(BANIMCONFUNK_C, 'w', encoding='utf-8') as f:
            f.write(banim_spell_palette_tint_append(tint_text, tint_rows))
        if verbose:
            print('  spell palette tints: %d character/weapon row(s)' % len(tint_rows))

    flash_rows = battle_charge_flashes(campaign)
    if flash_rows:
        with open(BANIMCONFUNK_C, encoding='utf-8') as f:
            flash_text = f.read()
        with open(BANIMCONFUNK_C, 'w', encoding='utf-8') as f:
            f.write(banim_charge_flash_append(flash_text, flash_rows))
        if verbose:
            print('  charge flashes (#183): %d caster(s) pulse on the wind-up beat' % len(flash_rows))


def _class_field_symbol(class_enum, field):
    """Read a symbol-valued field (e.g. .pBattleAnimDef = AnimConf_X) from gClassData."""
    with open(CLASSES_C, encoding='utf-8') as f:
        text = f.read()
    bs, be = _find_brace_block(text, '[%s - 1]' % class_enum, CLASSES_C)
    m = re.search(r'\.' + field + r'\s*=\s*(\w+)', text[bs:be])
    if not m:
        sys.exit('ERROR: .%s symbol not found in gClassData[%s]' % (field, class_enum))
    return m.group(1)
