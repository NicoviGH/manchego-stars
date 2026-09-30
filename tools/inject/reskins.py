"""Enemy class reskins (#21): cloned classes with their own map sprites and battle anims.
"""
import os
import re
import sys

from yaml_loader import yaml_load
import banim_palette
import feditor_to_banim
import map_sprite_tool
from inject.battle_anims import (
    _class_field_symbol, banim_append_row, banim_clone_conf, banim_repoint_conf)
from inject.decomp import _find_brace_block, _replace_brace_block, _table_close_line, REPO
from inject.paths import (
    BANIM_DATA_C, BANIM_DATA_DIR, BANIM_EKRBATTLE_H, BANIM_GFX_DIR, BANIM_LINKER, BANIM_POINTER_H,
    BANIMCONF_C, CLASSES_C, CLASSES_H, MOVE_GFX_DIR, UNIT_ICON_MOVE_C, UNIT_ICON_MOVE_S,
    UNIT_ICON_POINTER_H, UNIT_ICON_WAIT_C, UNIT_ICON_WAIT_S, WAIT_GFX_DIR)
from inject.sms import _write_wait_row, claim_sms_id
from inject.stats import _set_field


def _append_table_rows(path, decl, rows):
    """Append `rows` (source lines) before a C array's closing `};`, giving the
    previous last entry a separating comma if it lacks one."""
    with open(path, encoding='utf-8') as f:
        lines = f.read().splitlines(keepends=True)
    _, ci = _table_close_line(lines, decl)
    if '},' not in lines[ci - 1] and '}' in lines[ci - 1]:
        lines[ci - 1] = re.sub(r'\}(\s*)(/[/*][^\n]*)?\n$', r'},\1\2\n',
                               lines[ci - 1], count=1)
    lines[ci:ci] = [r + '\n' for r in rows]
    with open(path, 'w', encoding='utf-8') as f:
        f.write(''.join(lines))


# Give an ENEMY a themed overworld sprite without touching its shared vanilla class.
# Reskinning CLASS_SOLDIER/CLASS_FIGHTER directly is campaign-wide (every soldier/fighter
# in every chapter would change); instead we CLONE a base class into an otherwise-unused
# class slot (identical stats + battle anim -> gameplay unchanged) and swap only its MAP
# sprite. Grunts get assigned the cloned class; vanilla classes stay human. Reversible
# and reusable. Unlike the cast path (per-CHARACTER override, bespoke cast palette in its
# own OBJ bank), enemies render their class SMS under the standard ENEMY faction palette,
# so the donor sheet is remapped onto the standard SMS palette index layout (not the cast
# one). The "goblin"/chapter framing lives in campaign YAML; this code is class-agnostic.


def _parse_class_enum_values():
    """CLASS_X -> int value from constants/classes.h (move/class tables index by id-1)."""
    out = {}
    pat = re.compile(r'(CLASS_[A-Z0-9_]+)\s*=\s*(0x[0-9A-Fa-f]+|\d+)')
    with open(CLASSES_H, encoding='utf-8') as f:
        for line in f:
            m = pat.search(line)
            if m:
                out[m.group(1)] = int(m.group(2), 0)
    return out


def _class_field(class_enum, field):
    """Read a numeric field (e.g. SMSId) from a gClassData entry, as written in the C."""
    with open(CLASSES_C, encoding='utf-8') as f:
        text = f.read()
    bs, be = _find_brace_block(text, '[%s - 1]' % class_enum, CLASSES_C)
    m = re.search(r'\.' + field + r'\s*=\s*(0x[0-9A-Fa-f]+|\d+)', text[bs:be])
    if not m:
        sys.exit('ERROR: .%s not found in gClassData[%s]' % (field, class_enum))
    return int(m.group(1), 0)


def _move_table_len():
    """Count rows in unit_icon_move_table[] -> the next contiguous class index. The move
    table is a POSITIONAL array indexed by classId-1 (no designated inits), so an appended
    class needs its row at exactly this index for the engine's GetMuImg lookup to line up."""
    with open(UNIT_ICON_MOVE_C, encoding='utf-8') as f:
        lines = f.read().splitlines()
    di, ci = _table_close_line(lines, 'unit_icon_move_table[]')
    return sum(1 for i in range(di + 1, ci) if lines[i].lstrip().startswith('{'))


def _move_row_at(class_value):
    """The `{sheet, motion}` pair on the move-table row at index class_value-1 (`// N`)."""
    idx = class_value - 1
    with open(UNIT_ICON_MOVE_C, encoding='utf-8') as f:
        for line in f:
            m = re.search(r'(\{[^}]+\}),?\s*//\s*%d\s*$' % idx, line)
            if m:
                return m.group(1)
    sys.exit('ERROR: no move-table row at index %d (class %#x)' % (idx, class_value))


def _wait_symbol_at(sms_id):
    """The donor `unit_icon_wait_<Name>_sheet` symbol at row `sms_id` (its `// N` comment),
    and the bare <Name>. The vanilla wait rows are emitted `{..., sym}, // N`."""
    with open(UNIT_ICON_WAIT_C, encoding='utf-8') as f:
        for line in f:
            m = re.search(r'(unit_icon_wait_(\w+)_sheet)\}.*//\s*%d\s*$' % sms_id, line)
            if m:
                return m.group(1), m.group(2)
    sys.exit('ERROR: no wait-table row at SMS id %d' % sms_id)


def _move_motion_at(class_value):
    """The motion script symbol on the move-table row at index class_value-1 (`// N`)."""
    idx = class_value - 1
    with open(UNIT_ICON_MOVE_C, encoding='utf-8') as f:
        for line in f:
            m = re.search(r'\{[^,]+,\s*(\w+)\}.*//\s*%d\s*$' % idx, line)
            if m:
                return m.group(1)
    sys.exit('ERROR: no move-table row at index %d (class %#x)' % (idx, class_value))


def _set_move_row(class_value, sheet_sym, motion_sym):
    """Rewrite the move-table row at index class_value-1 (located by its `// N` comment)."""
    idx = class_value - 1
    with open(UNIT_ICON_MOVE_C, encoding='utf-8') as f:
        text = f.read()
    pat = re.compile(r'^\t\{[^\n]*\}, // %d$' % idx, re.MULTILINE)
    new, n = pat.subn('\t{%s, %s}, // %d' % (sheet_sym, motion_sym, idx), text, count=1)
    if n == 0:
        sys.exit('ERROR: move-table row // %d not found to reskin' % idx)
    with open(UNIT_ICON_MOVE_C, 'w', encoding='utf-8') as f:
        f.write(new)


def enemy_class_reskins(campaign):
    """The campaign's declared enemy class reskins (campaign.yaml `enemy_class_reskins`),
    as a list of dicts {id, base, slot, sprite}. Empty if none declared."""
    cfg = os.path.join(REPO, 'campaigns', campaign, 'campaign.yaml')
    with open(cfg, encoding='utf-8') as f:
        return (yaml_load(f) or {}).get('enemy_class_reskins') or []


def set_class_field_symbol(text, class_enum, field, symbol):
    """Repoint a symbol-valued class field (e.g. .pBattleAnimDef = AnimConf_X) IN PLACE,
    within only [class_enum - 1]'s block. Returns the new text; errors if the field is
    absent. The class-level enemy battle-anim path (#90): a reskin clone's cloned body carries
    the base class's .pBattleAnimDef; this repoints it at the imported class-level AnimConf,
    leaving every sibling class (including the vanilla donor) byte-unchanged."""
    bs, be = _find_brace_block(text, '[%s - 1]' % class_enum, CLASSES_C)
    block = text[bs:be]
    new, n = re.subn(r'(\.%s\s*=\s*)\w+' % field, r'\g<1>' + symbol, block, count=1)
    if n == 0:
        sys.exit('ERROR: .%s not found in gClassData[%s]' % (field, class_enum))
    return text[:bs] + new + text[be:]


def class_enum_insert(text, name, value):
    """Insert `NAME = 0xVALUE,` into the class enum after the last numeric-valued CLASS_
    entry (idempotent). Extends the vanilla 0x7F tail so an enemy reskin can ride a class
    slot beyond the three ballista-empties (#23). The value-less `= CLASS_OBSTACLE` alias
    tail is skipped -- we anchor on the last real id so the enum reader picks up the new
    constant. Class ids are a u8 with 0x80-0xFF free and gClassData is unsized (no count
    cap), so appending is safe (see decisions.md / HANDOFF #23)."""
    if re.search(r'\b' + re.escape(name) + r'\s*=', text):
        return text
    anchors = list(re.finditer(r'^([ \t]*)CLASS_[A-Z0-9_]+\s*=\s*(?:0x[0-9A-Fa-f]+|\d+)\s*,',
                               text, re.M))
    if not anchors:
        sys.exit('ERROR: class_enum_insert: no numeric CLASS_ entry to anchor on')
    m = anchors[-1]
    eol = text.find('\n', m.end())
    if eol < 0:
        eol = len(text)
    return text[:eol] + '\n%s%s = 0x%02X,' % (m.group(1), name, value) + text[eol:]


def classdata_append_clone(text, base_enum, new_enum):
    """Append a clone of gClassData[base_enum-1] as a NEW [new_enum-1] entry (idempotent).
    The clone carries the base body verbatim (stats + battle anim ride along); the reskin
    loop repoints .number/.SMSId afterward via the existing _set_field path. Used when a
    reskin's `slot` is a freshly-appended class id rather than a vanilla ballista-empty."""
    designator = '[%s - 1]' % new_enum
    if designator in text:
        return text
    bs, be = _find_brace_block(text, '[%s - 1]' % base_enum, CLASSES_C)
    body = text[bs:be]
    _, arr_e = _find_brace_block(text, 'gClassData[] =', CLASSES_C)
    entry = '    %s = %s,\n' % (designator, body)
    return text[:arr_e - 1] + entry + text[arr_e - 1:]


def _append_new_reskin_slots(reskins, verbose=True):
    """Append any reskin `slot`s declared with a `slot_id` (a fresh class id past 0x7F)
    that don't yet exist as classes -- extend the enum + clone the base into gClassData so
    the per-reskin clone loop can then ride the new slot (#23: the Lizardzerker, once the
    three ballista-empties are used up). Idempotent (build restores classes.h/.c each run);
    a reskin whose `slot` is already a real class (vanilla ballista-empty) is left alone."""
    values = _parse_class_enum_values()
    header = cdata = None
    for rk in reskins:
        if rk.get('slot_id') is None or rk['slot'] in values:
            continue
        slot, base, val = rk['slot'], rk['base'], int(str(rk['slot_id']), 0)
        if header is None:
            header = open(CLASSES_H, encoding='utf-8').read()
            cdata = open(CLASSES_C, encoding='utf-8').read()
        header = class_enum_insert(header, slot, val)
        cdata = classdata_append_clone(cdata, base, slot)
        # The positional (class-indexed) move table needs a contiguous row at index val-1
        # so the reskin loop's _set_move_row can rewrite it; fill any gap with the base's
        # row (never deployed) and keep the array dense for the engine's GetMuImg lookup.
        cur = _move_table_len()
        if val > cur:
            base_row = _move_row_at(values[base])
            _append_table_rows(UNIT_ICON_MOVE_C, 'unit_icon_move_table[]',
                               ['\t%s, // %d' % (base_row, i) for i in range(cur, val)])
        values[slot] = val
        if verbose:
            print('  %-16s = append class %s = 0x%X (clone of %s)'
                  % (rk['id'], slot, val, base))
    if header is not None:
        with open(CLASSES_H, 'w', encoding='utf-8') as f:
            f.write(header)
        with open(CLASSES_C, 'w', encoding='utf-8') as f:
            f.write(cdata)


def inject_enemy_class_reskins(campaign, verbose=True):
    """Clone each declared base class into its unused slot with a custom MAP sprite only.

    Per reskin (campaign.yaml): clone gClassData[base-1] into [slot-1] (full copy so the
    battle anim/stats ride along -> combat unchanged), repoint .number/.SMSId; append the
    reskin's idle sheet as a new wait-table row at that SMSId; repoint the move-table row
    at slot-1 to the reskin's walk sheet (reusing the base class's motion script). Sheets
    are remapped onto the BASE class's standard SMS palette (map_sprite_tool) so the enemy
    faction palette colours them. Sprites are de-duped: reskins that share a `sprite` share
    one wait row / move sheet (one goblin sprite, two classes)."""
    reskins = enemy_class_reskins(campaign)
    if not reskins:
        if verbose:
            print('  (no enemy_class_reskins declared)')
        return
    asset_dir = os.path.join(REPO, 'campaigns', campaign, 'map_sprites')
    # Append any freshly-declared class slots (slot_id present) before resolving enum
    # values, so a reskin can ride a slot beyond the three vanilla ballista-empties (#23).
    _append_new_reskin_slots(reskins, verbose)
    values = _parse_class_enum_values()
    pointer_externs = []
    sprite_sms = {}        # sprite stem -> SMS id of its (shared) wait row
    sprite_move_sym = {}   # sprite stem -> move-sheet symbol

    for rk in reskins:
        base, slot, sprite = rk['base'], rk['slot'], rk['sprite']
        for key in ('base', 'slot'):
            if rk[key] not in values:
                sys.exit('ERROR: enemy_class_reskins %s: unknown class %r' % (rk['id'], rk[key]))

        # Donor SMS palette + geometry come from the base class's vanilla wait sheet.
        base_sms = _class_field(base, 'SMSId')
        donor_sym, donor_name = _wait_symbol_at(base_sms)
        donor_png = os.path.join(WAIT_GFX_DIR, donor_sym + '.png')

        # Graphics once per unique sprite (shared across reskins of the same sprite).
        if sprite not in sprite_sms:
            stand = os.path.join(asset_dir, sprite + '.png')
            walk = os.path.join(asset_dir, sprite + '_mu.png')
            for p in (stand, walk):
                if not os.path.isfile(p):
                    sys.exit('ERROR: enemy_class_reskins %s: missing map_sprites/%s'
                             % (rk['id'], os.path.basename(p)))
            sym = sprite.replace('-', '_')
            wait_sym = 'unit_icon_wait_manchego_%s_sheet' % sym
            move_sym = 'unit_icon_move_manchego_%s_sheet' % sym
            # Remap onto the base class's standard SMS palette (enemy faction recolours it).
            map_sprite_tool.remap_sms_palette(stand, donor_png,
                                              os.path.join(WAIT_GFX_DIR, wait_sym + '.png'))
            map_sprite_tool.remap_sms_palette(walk, donor_png,
                                              os.path.join(MOVE_GFX_DIR, move_sym + '.png'))
            # Idle frame geometry: a `frame` override (e.g. "16x32") when the sprite is a
            # different size class than the base (the Fire Imp is a tall 16x32 sprite on a
            # 16x16 soldier/fighter -- the engine draws it via the wait-row size flag);
            # else the base class's own SMS size.
            if rk.get('frame'):
                dfw, dfh = (int(v) for v in str(rk['frame']).lower().split('x'))
            else:
                _, dfw, dfh = map_sprite_tool.donor_sms_geometry(donor_name)
            macro, fw, fh, _ = map_sprite_tool.sheet_info(
                os.path.join(WAIT_GFX_DIR, wait_sym + '.png'), (dfw, dfh))
            map_sprite_tool.validate_mu_sheet(os.path.join(MOVE_GFX_DIR, move_sym + '.png'))

            sms_id = claim_sms_id()
            _write_wait_row(sms_id,
                '\t{0, %s, %s}, // %d %s (reskin)' % (macro, wait_sym, sms_id, sprite))
            with open(UNIT_ICON_WAIT_S, 'a', encoding='utf-8') as f:
                f.write('\n/* Manchego Stars enemy class reskin idle (#21) */\n'
                        '\t.global %s\n%s:\n'
                        '\t.incbin "graphics/unit_icon/wait/%s.4bpp.lz"\n\t.align 2, 0\n'
                        % (wait_sym, wait_sym, wait_sym))
            with open(UNIT_ICON_MOVE_S, 'a', encoding='utf-8') as f:
                f.write('\n/* Manchego Stars enemy class reskin walk (#21) */\n'
                        '\t.global %s\n%s:\n'
                        '\t.incbin "graphics/unit_icon/move/%s.4bpp.lz"\n\t.align 2, 0\n'
                        % (move_sym, move_sym, move_sym))
            pointer_externs += ['extern char %s[];' % wait_sym, 'extern char %s[];' % move_sym]
            sprite_sms[sprite] = sms_id
            sprite_move_sym[sprite] = move_sym

        # Clone base class -> slot (full body), repoint number + SMSId.
        with open(CLASSES_C, encoding='utf-8') as f:
            text = f.read()
        bs, be = _find_brace_block(text, '[%s - 1]' % base, CLASSES_C)
        body = text[bs:be]
        body = _set_field(body, 'number', slot, CLASSES_C, base)
        body = _set_field(body, 'SMSId', '0x%x' % sprite_sms[sprite], CLASSES_C, base)
        text = _replace_brace_block(text, '[%s - 1]' % slot, body, CLASSES_C)
        with open(CLASSES_C, 'w', encoding='utf-8') as f:
            f.write(text)

        # Repoint the cloned class's move-table row to the reskin walk sheet, reusing the
        # base class's motion script (so it animates like the base class).
        _set_move_row(values[slot], sprite_move_sym[sprite], _move_motion_at(values[base]))

        if verbose:
            print('  %-16s = clone %s -> %s (SMS %d, sprite %s)'
                  % (rk['id'], base, slot, sprite_sms[sprite], sprite))

    if pointer_externs:
        with open(UNIT_ICON_POINTER_H, 'a', encoding='utf-8') as f:
            f.write('\n/* Manchego Stars enemy class reskin sprites (#21) */\n'
                    + '\n'.join(pointer_externs) + '\n')


# Reskinned enemy CLASSES carry a custom map sprite (inject_enemy_class_reskins) but animate
# as their vanilla donor (Brigand/Soldier/...) in the battle close-up. This imports a real
# FE-native community animation (feditor_to_banim) and binds it at the CLASS via
# ClassData.pBattleAnimDef -- the generic-enemy analogue of the PC per-character _u25 path.
# Additive + reversible: the imported anims append banim_data[] rows; a PRIVATE class-level
# AnimConf (a clone of the donor's, weapon entries repointed) is appended and the reskin clone
# class's .pBattleAnimDef points at it. The donor class + its AnimConf stay byte-vanilla.


# Named enemy-faction palette passes a `battle_anim: {recolor: <name>}` may select. Kept a
# registry (not free-form) so the campaign YAML stays declarative and the transforms are tested.
BANIM_RECOLORS = {
    'enemy_red': feditor_to_banim.enemy_red_recolor,
}


def _write_imported_banim_assets(abbr, res, uid):
    """Write one imported anim's assets into the decomp and register it: motion.s + per-frame
    sheet PNGs + agbpal (step 1), the linker block (2), and the banim_data[] row + pointer
    externs (3). Returns the new animId. Shared shape with the faked path (inject_battle_anims
    steps 1-3); only the asset SOURCE differs (transcribed FEditor vs faked 3-pose)."""
    with open(os.path.join(BANIM_DATA_DIR, 'banim_%s_motion.s' % abbr), 'w',
              encoding='utf-8') as f:
        f.write(res['motion_s'])
    for i, sheet in enumerate(res['sheets']):
        sheet.save(os.path.join(BANIM_GFX_DIR, 'banim_%s_sheet_%d.png' % (abbr, i)))
    with open(os.path.join(BANIM_GFX_DIR, 'banim_%s.agbpal' % abbr), 'wb') as f:
        f.write(res['pal'])

    block = (['graphics/banim/banim_%s_sheet_%d.4bpp.lz' % (abbr, i)
              for i in range(len(res['sheets']))]
             + ['graphics/banim/banim_%s.agbpal.lz' % abbr,
                'data/banim/banim_%s_oam_l.bin.lz' % abbr,
                'data/banim/banim_%s_oam_r.bin.lz' % abbr,
                'data/banim/banim_%s_motion.o|.data.script>lz' % abbr,
                'data/banim/banim_%s_modes.bin' % abbr])
    with open(BANIM_LINKER, 'a', encoding='utf-8') as f:
        f.write('\n# Manchego Stars imported battle anim (#90): %s\n' % uid)
        f.write('\n'.join(block) + '\n')

    with open(BANIM_DATA_C, encoding='utf-8') as f:
        text = f.read()
    text, anim_id = banim_append_row(text, abbr)
    with open(BANIM_DATA_C, 'w', encoding='utf-8') as f:
        f.write(text)
    with open(BANIM_POINTER_H, 'a', encoding='utf-8') as f:
        f.write('// battle animation 0x%X (Manchego Stars #90: %s)\n' % (anim_id, uid))
        for sym, ty in [('modes_bin', 'int'), ('motion_o', 'char'),
                        ('oam_r_bin', 'char'), ('oam_l_bin', 'char'), ('agbpal', 'char')]:
            f.write('extern %s banim_%s_%s;\n' % (ty, abbr, sym))
    return anim_id


def inject_enemy_class_battle_anims(campaign, verbose=True):
    """Import + class-bind a battle animation for every enemy_class_reskins entry carrying a
    `battle_anim:` block (#90). MUST run after inject_enemy_class_reskins (the reskin clone
    class it repoints must already exist).

    campaign.yaml (on a reskin entry):
        battle_anim:
          source: wildling               # dir under engine/battle_anims/_vendored/
          weapons:                        # one per weapon-mode the donor AnimConf keys
            - {dir: axe,     txt: Axe.txt,     abbr: kgru_ax, wtypes: ["0x0100 | ITYPE_AXE"]}
            - {dir: handaxe, txt: Handaxe.txt, abbr: kgru_ha,
               wtypes: ["ITEM_AXE_HANDAXE", "ITEM_AXE_TOMAHAWK", "ITEM_AXE_HATCHET"]}
            - {dir: unarmed, txt: Unarmed.txt, abbr: kgru_un, wtypes: ["0x0100 | ITYPE_ITEM"]}
    Each `wtypes` literal must match an entry in the donor class's AnimConf verbatim (they are
    repointed by literal). A class's weapons share ONE palette (same creature, one colour set).

    !! OFF-BY-ONE (as in inject_battle_anims): the AnimConf `.index` is animId + 1
       (GetBattleAnimationId returns idx - 1). Encode anim_id + 1."""
    reskins = [r for r in enemy_class_reskins(campaign) if r.get('battle_anim')]
    if not reskins:
        if verbose:
            print('  (no class battle_anim blocks declared)')
        return
    os.makedirs(BANIM_DATA_DIR, exist_ok=True)
    os.makedirs(BANIM_GFX_DIR, exist_ok=True)
    vendored = os.path.join(REPO, 'engine', 'battle_anims', '_vendored')

    for rk in reskins:
        ba = rk['battle_anim']
        src_dir = os.path.join(vendored, ba['source'])
        weapons = ba['weapons']
        # Optional enemy-faction palette pass: a community anim ships its NATIVE (often
        # ally-blue) palette, but a reskin is always hostile, so recolour to the enemy ramp
        # (the engine reads agbpal bank BANIMPAL_RED for enemies). `recolor:` names a
        # feditor_to_banim recolour fn; absent -> the anim keeps its native colours.
        # Two ways to leave the author's colours, and a class may use either: `recolor:`
        # names a FUNCTION (a rule over RGB -- right when the only question is which side
        # the unit is on), `palette_edit:` names a hand-edited FILE (right when the ramp has
        # to be looked at). Reading only the first made an edit dropped beside a class anim a
        # silent no-op -- the inverse of load_recolor's "a typo must fail the build" (#25).
        recolor = BANIM_RECOLORS[ba['recolor']] if ba.get('recolor') else None
        if ba.get('palette_edit'):
            if recolor:
                sys.exit('ERROR: enemy_class_reskins %s declares BOTH recolor: and '
                         'palette_edit:; they are two answers to one question' % rk['id'])
            recolor = banim_palette.load_recolor(os.path.join(src_dir, ba['palette_edit']))

        # Import each weapon-mode anim -> a new animId; collect (wtype, animId) repoints. Each
        # anim carries its OWN agbpal (the engine loads a battle sprite's palette per-animation),
        # so weapons keep their native <=15-colour set -- the same creature's body reads
        # consistently across them without forcing all weapons into one shared 16-colour bank.
        repoints = []
        for w in weapons:
            wdir = os.path.join(src_dir, w['dir'])
            res = feditor_to_banim.build_import(w['abbr'], os.path.join(wdir, w['txt']), wdir,
                                                recolor=recolor)
            if ba.get('palette_edit'):
                banim_palette.assert_all_applied(recolor, 'enemy_class %s' % rk['id'])
            anim_id = _write_imported_banim_assets(w['abbr'], res, rk['id'])
            for wt in w['wtypes']:
                repoints.append((wt, anim_id))
            if verbose:
                print('  %-16s = import %s (animId 0x%X, %d frame(s))'
                      % (rk['id'], w['abbr'], anim_id, len(res['sheets'])))

        # A private class-level AnimConf = clone of the donor's, each weapon entry repointed.
        base_conf = _class_field_symbol(rk['base'], 'pBattleAnimDef')
        new_conf = 'AnimConf_%s' % rk['id'].replace('-', '_')
        with open(BANIMCONF_C, encoding='utf-8') as f:
            conf = f.read()
        first_wt, first_id = repoints[0]
        conf = banim_clone_conf(conf, base_conf, new_conf, first_wt, first_id + 1)
        for wt, aid in repoints[1:]:
            conf = banim_repoint_conf(conf, new_conf, wt, aid + 1)
        with open(BANIMCONF_C, 'w', encoding='utf-8') as f:
            f.write(conf)
        with open(BANIM_EKRBATTLE_H, 'a', encoding='utf-8') as f:
            f.write('extern CONST_DATA struct BattleAnimDef %s[]; /* Manchego Stars #90 */\n'
                    % new_conf)

        # Point the reskin clone class's .pBattleAnimDef at the new class-level AnimConf.
        with open(CLASSES_C, encoding='utf-8') as f:
            ctext = f.read()
        ctext = set_class_field_symbol(ctext, rk['slot'], 'pBattleAnimDef', new_conf)
        with open(CLASSES_C, 'w', encoding='utf-8') as f:
            f.write(ctext)
        if verbose:
            print('  %-16s = %s bound on %s' % (rk['id'], new_conf, rk['slot']))
