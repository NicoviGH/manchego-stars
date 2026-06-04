#!/usr/bin/env python3
"""build_campaign.py -- inject campaign content into the fireemblem8u decomp build.

Reads campaign data (YAML + authored busts) and writes decomp-native source/asset
files into the fireemblem8u submodule working tree, so a plain `make` compiles a
ROM carrying our content. The generated files are reproducible build artifacts --
restore vanilla with `git -C fireemblem8u checkout <path>`.

Engine/Content boundary (CLAUDE.md): the GENERATOR knows character/chapter names;
the C/asm it EMITS is just data. No campaign name is ever hardcoded in engine C.

--- Milestone A (current): PORTRAITS ---------------------------------------------
For each named cast member, run the bust through portrait_tool.generate (4 decomp
assets) and overwrite a vanilla portrait slot's source files in
graphics/portrait/. The decomp's generic gbagfx pattern rules rebuild the
.4bpp/.4bpp.fk/.4bpp.lz on the next `make`; data_portrait[] is untouched, so the
mapped vanilla character simply wears our face. Zero C changes, fully reversible.

Milestones B+ (characters, chapter, dialogue codegen) hang off the same CLI.
"""

import argparse
import os
import re
import sys

# portrait_tool lives next to us in tools/
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import portrait_tool  # noqa: E402
from PIL import Image  # noqa: E402
import yaml  # noqa: E402

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DECOMP = os.path.join(REPO, 'fireemblem8u')
PORTRAIT_DIR = os.path.join(DECOMP, 'graphics', 'portrait')
CHARACTERS_C = os.path.join(DECOMP, 'src', 'data_characters.c')
CLASSES_C = os.path.join(DECOMP, 'src', 'data_classes.c')
TEXTS_TXT = os.path.join(DECOMP, 'texts', 'texts.txt')

# FE8's unit-name buffer; longer names overflow and garble the display.
FE_NAME_MAX = 12

# Our cast wear stock vanilla FE8 classes (docs/decisions.md Class Mapping). Map
# each unit YAML's display class -> the decomp CLASS_ enum. Parenthetical flavor
# like "Mage (Ice)" is stripped before lookup.
CLASS_MAP = {
    'Pirate':         'CLASS_PIRATE',
    'Shaman':         'CLASS_SHAMAN',
    'Archer':         'CLASS_ARCHER',
    'Mage':           'CLASS_MAGE',
    'Priest':         'CLASS_PRIEST',
    'Knight':         'CLASS_ARMOR_KNIGHT',
    'Pegasus Knight': 'CLASS_PEGASUS_KNIGHT',
}

# fe_stats key -> the gCharacterData personal-base field it feeds. FE8 unit stats
# are class base + this personal base. There is one attack stat (basePow), shown as
# STR for physical classes and MAG for magic ones. MOV is class-only (handled apart).
STAT_FIELD = {
    'HP': 'baseHP', 'STR': 'basePow', 'MAG': 'basePow', 'SKL': 'baseSkl',
    'SPD': 'baseSpd', 'DEF': 'baseDef', 'RES': 'baseRes', 'LCK': 'baseLck',
    'CON': 'baseCon',
}
# class-data base fields we read (classes carry no luck -> baseLck defaults 0).
CLASS_BASE_FIELDS = ('baseHP', 'basePow', 'baseSkl', 'baseSpd', 'baseDef',
                     'baseRes', 'baseCon', 'baseMov')

# The vanilla slot's weapon ranks belong to its old class (e.g. Seth's SWORD), so
# we replace them with our class's primary weapon type. Rank is a flat starting
# value for now (tunable later in a balance pass); E covers basic gear/tomes.
CLASS_WEAPON = {
    'CLASS_PIRATE':         'ITYPE_AXE',
    'CLASS_SHAMAN':         'ITYPE_DARK',
    'CLASS_ARCHER':         'ITYPE_BOW',
    'CLASS_MAGE':           'ITYPE_ANIMA',
    'CLASS_PRIEST':         'ITYPE_STAFF',
    'CLASS_ARMOR_KNIGHT':   'ITYPE_LANCE',
    'CLASS_PEGASUS_KNIGHT': 'ITYPE_LANCE',
}
WPN_RANK_START = 'WPN_EXP_E'


# our cast bust  ->  vanilla portrait slot whose graphic files we overwrite.
# Slots are FE8's earliest-available cast so one early chapter shows many faces.
# (portrait-only mapping; class/stat mapping comes in Milestone B.)
PORTRAIT_MAP = {
    'braulo':     'Eirika',    # the prologue lord -- first face the player sees
    'marty':      'Seth',
    'wolfram':    'Franz',
    'meesmickle': 'Gilliam',
    'prof-rbg':   'Moulder',
    'rootis':     'Vanessa',
    'sclorbo':    'Ross',
    'pinky':      'Neimi',
    'pepperjack': 'Garcia',
    'brie':       'Colm',
}


def inject_portraits(campaign, verbose=True):
    """Overwrite each mapped vanilla portrait slot with our authored bust."""
    bust_dir = os.path.join(REPO, 'campaigns', campaign, 'portraits')
    if not os.path.isdir(PORTRAIT_DIR):
        sys.exit('ERROR: decomp portrait dir not found: %s' % PORTRAIT_DIR)

    for unit, vanilla in PORTRAIT_MAP.items():
        bust_path = os.path.join(bust_dir, unit + '.png')
        if not os.path.isfile(bust_path):
            sys.exit('ERROR: missing bust for %s: %s' % (unit, bust_path))

        im = Image.open(bust_path)
        portrait_tool._check_indexed(im, bust_path)
        if im.size != (portrait_tool.BUST_W, portrait_tool.BUST_H):
            sys.exit('ERROR: %s is %s, expected %dx%d bust'
                     % (bust_path, im.size, portrait_tool.BUST_W, portrait_tool.BUST_H))

        # Busts are already canonical FE8 facing (screen-left) -- facing is baked
        # at the render stage (ref_to_bust --flip-h, recorded as art.render.flip_h).
        # static_portrait=True: custom busts are non-animated (no mouth flap, no
        # eye-blink) -- aligning per-frame mouth/eye art for custom portraits is
        # infeasible, so we lock them still. See portrait_tool.generate.
        tileset, mouth, chibi, pal_bytes = portrait_tool.generate(im, static_portrait=True)

        base = os.path.join(PORTRAIT_DIR, 'portrait_' + vanilla)
        tileset.save(base + '_tileset.png')
        mouth.save(base + '_mouth.png')
        chibi.save(base + '_chibi.png')
        with open(base + '_palette.agbpal', 'wb') as f:
            f.write(pal_bytes)

        if verbose:
            print('  %-10s -> portrait_%s (tileset/mouth/chibi/palette)' % (unit, vanilla))


# --- Milestone B: unit names ------------------------------------------------------
# Each cast member wears a vanilla character's slot (PORTRAIT_MAP). We overwrite that
# vanilla character's NAME message in texts/texts.txt with our unit's display name, so
# the recompressed gMsgTable carries it. The vanilla name's message index is the
# slot character's `.nameTextId` -- read it from the decomp, never hardcode (the data
# is the source of truth). Names live in YAML; the C/text we emit is just data.

def load_unit(campaign, unit_id):
    """Load a cast member's YAML from pcs/ or npcs/."""
    base = os.path.join(REPO, 'campaigns', campaign)
    for sub in ('pcs', 'npcs'):
        path = os.path.join(base, sub, unit_id + '.yaml')
        if os.path.isfile(path):
            with open(path, encoding='utf-8') as f:
                return yaml.safe_load(f)
    sys.exit('ERROR: no YAML for unit %r under %s/{pcs,npcs}' % (unit_id, base))


def display_name(unit):
    """The <=12-char name FE8 shows; fe_name overrides a too-long `name`."""
    name = unit.get('fe_name') or unit.get('name')
    if not name:
        sys.exit('ERROR: unit %r has no name/fe_name' % unit.get('id'))
    name = str(name).strip()
    if len(name) > FE_NAME_MAX:
        sys.exit('ERROR: name %r is %d chars (>%d); add a shorter fe_name'
                 % (name, len(name), FE_NAME_MAX))
    return name


def vanilla_name_text_id(slot):
    """nameTextId of vanilla CHARACTER_<slot>, scanned from data_characters.c."""
    marker = '[CHARACTER_%s - 1]' % slot.upper()
    with open(CHARACTERS_C, encoding='utf-8') as f:
        lines = f.read().splitlines()
    for i, line in enumerate(lines):
        if marker in line:
            for probe in lines[i:i + 12]:
                m = re.search(r'\.nameTextId\s*=\s*(0x[0-9a-fA-F]+|\d+)', probe)
                if m:
                    return int(m.group(1), 0)
    sys.exit('ERROR: could not find nameTextId for %s in %s' % (marker, CHARACTERS_C))


def name_message_body(name):
    """Format a name as a terminated FE8 message, matching vanilla's convention.

    FE8 text packs printable bytes two-at-a-time into u16s (see textprocess.py
    text_to_utf8_u16_array). `[X]` is the 0x00 string terminator. If an odd number
    of name bytes precede it, that 0x00 gets paired into the last character's high
    byte instead of standing alone as 0x0000 -- so the in-game decoder never hits
    its terminator and runs away into the next message (the "Huffman corruption"
    that bit the earlier reset). Vanilla pads odd-length names with `[.]` (0x1F,
    absorbed into the last glyph) to keep the byte count even: "Seth[X]" but
    "Franz[.][X]". We do the same.
    """
    pad = '[.]' if len(name.encode('utf-8')) % 2 == 1 else ''
    return name + pad + '[X]'


def set_message_body(lines, msg_id, body):
    """Replace the content lines of `## MSG_<id>` with `body` (in place). Idempotent:
    matches the header and rewrites whatever non-blank lines follow it."""
    header = '## MSG_%03X' % msg_id
    for i, line in enumerate(lines):
        if line.strip() == header:
            j = i + 1
            while j < len(lines) and lines[j].strip() != '' \
                    and not lines[j].lstrip().startswith('#'):
                j += 1
            lines[i + 1:j] = [body]
            return True
    sys.exit('ERROR: message header %r not found in %s' % (header, TEXTS_TXT))


def inject_names(campaign, verbose=True):
    """Write each cast member's display name into its vanilla slot's name message."""
    with open(TEXTS_TXT, encoding='utf-8') as f:
        lines = f.read().split('\n')
    for unit_id, slot in PORTRAIT_MAP.items():
        unit = load_unit(campaign, unit_id)
        unit.setdefault('id', unit_id)
        name = display_name(unit)
        text_id = vanilla_name_text_id(slot)
        set_message_body(lines, text_id, name_message_body(name))
        if verbose:
            print('  %-10s -> MSG_%03X (was %s): %s' % (unit_id, text_id, slot, name))
    with open(TEXTS_TXT, 'w', encoding='utf-8') as f:
        f.write('\n'.join(lines))


# --- Milestone B: character stats / class -----------------------------------------
# Write each cast unit's vanilla-class identity into its portrait slot's
# gCharacterData[] entry: defaultClass, affinity (Anima, cosmetic), baseLevel,
# personal base stats = (YAML fe_stats - class base), the class's weapon-type rank,
# and zeroed personal growths (so the unit grows at its pure class rate). When
# fe_stats match the class verbatim (the FE-strict default) the personal bases come
# out 0; any deliberate YAML divergence is still honored so displayed stats ==
# fe_stats. portraitId, attributes (gender), and pSupportData are left as the
# vanilla slot's -- gender/supports are a later YAML-driven pass.

def _find_brace_block(text, marker, path):
    """Return (start, end) covering the `{...}` (brace-balanced) after `marker`."""
    at = text.find(marker)
    if at < 0:
        sys.exit('ERROR: %r not found in %s' % (marker, path))
    brace = text.find('{', at)
    depth = 0
    i = brace
    while i < len(text):
        if text[i] == '{':
            depth += 1
        elif text[i] == '}':
            depth -= 1
            if depth == 0:
                return brace, i + 1
        i += 1
    sys.exit('ERROR: unbalanced braces for %r in %s' % (marker, path))


def _set_field(block, field, value, path, marker):
    """Replace `.field = ...,` within `block`. Errors if the field isn't present."""
    pat = re.compile(r'(\.' + field + r'\s*=\s*)[^,\n]*(,)')
    new, n = pat.subn(lambda m: m.group(1) + str(value) + m.group(2), block, count=1)
    if n == 0:
        sys.exit('ERROR: field .%s not found in %s entry %s' % (field, path, marker))
    return new


def class_base_stats(class_enum):
    """Read a class's base stats from data_classes.c, keyed by CharacterData field
    name (baseHP, basePow, ...). Luck is character-only, so baseLck defaults to 0."""
    with open(CLASSES_C, encoding='utf-8') as f:
        text = f.read()
    s, e = _find_brace_block(text, '[%s - 1]' % class_enum, CLASSES_C)
    block = text[s:e]
    out = {'baseLck': 0}
    for cf in CLASS_BASE_FIELDS:
        m = re.search(r'\.' + cf + r'\s*=\s*(-?\d+)', block)
        out[cf] = int(m.group(1)) if m else 0
    return out


def class_enum_for(unit):
    raw = unit.get('fe_stats', {}).get('class')
    if not raw:
        return None
    base = re.sub(r'\s*\(.*?\)', '', str(raw)).strip()
    if base not in CLASS_MAP:
        sys.exit('ERROR: unit %r class %r not in CLASS_MAP' % (unit.get('id'), base))
    return CLASS_MAP[base]


def patch_character_data(campaign, verbose=True):
    """Inject class + base stats into each cast slot's gCharacterData entry."""
    with open(CHARACTERS_C, encoding='utf-8') as f:
        text = f.read()

    for unit_id, slot in PORTRAIT_MAP.items():
        unit = load_unit(campaign, unit_id)
        unit.setdefault('id', unit_id)
        class_enum = class_enum_for(unit)
        if class_enum is None:
            if verbose:
                print('  %-10s -> %-8s: no class yet (name only)' % (unit_id, slot))
            continue

        st = unit['fe_stats']
        cbase = class_base_stats(class_enum)
        # MOV is class-only; we can't set it per-character -- just sanity-check it.
        if 'MOV' in st and int(st['MOV']) != cbase['baseMov']:
            print('  WARN %s: MOV %s != class %s base MOV %d (MOV is class-fixed)'
                  % (unit_id, st['MOV'], class_enum, cbase['baseMov']))

        marker = '[CHARACTER_%s - 1]' % slot.upper()
        s, e = _find_brace_block(text, marker, CHARACTERS_C)
        block = text[s:e]
        block = _set_field(block, 'defaultClass', class_enum, CHARACTERS_C, marker)
        block = _set_field(block, 'affinity', 'UNIT_AFFIN_ANIMA', CHARACTERS_C, marker)
        block = _set_field(block, 'baseLevel', int(st.get('level', 1)), CHARACTERS_C, marker)

        deltas = {}
        for fe in st:
            field = STAT_FIELD.get(fe)
            if field is None:
                continue
            delta = int(st[fe]) - cbase.get(field, 0)
            deltas[field] = delta
            block = _set_field(block, field, delta, CHARACTERS_C, marker)

        # Swap the slot's inherited weapon ranks for our class's weapon type.
        itype = CLASS_WEAPON[class_enum]
        ranks = '{ [%s] = %s, }' % (itype, WPN_RANK_START)
        block, n = re.subn(r'(\.baseRanks\s*=\s*)\{.*?\}',
                           lambda m: m.group(1) + ranks, block, count=1, flags=re.DOTALL)
        if n == 0:
            sys.exit('ERROR: .baseRanks not found in %s %s' % (CHARACTERS_C, marker))

        # Zero the slot's personal growths so the unit grows at its pure class rate
        # (total growth = class + character). Per-unit growth tuning is a later pass;
        # we don't want Braulo silently inheriting Eirika's growths.
        for gf in ('growthHP', 'growthPow', 'growthSkl', 'growthSpd',
                   'growthDef', 'growthRes', 'growthLck'):
            block = _set_field(block, gf, 0, CHARACTERS_C, marker)

        text = text[:s] + block + text[e:]
        if verbose:
            shown = ' '.join('%s%d' % (k, int(st[k])) for k in
                             ('HP', 'STR', 'MAG', 'SKL', 'SPD', 'DEF', 'RES', 'LCK', 'CON')
                             if k in st)
            nz = {k: v for k, v in deltas.items() if v != 0}
            tag = '' if not nz else '  (personal deltas %s)' % nz
            print('  %-10s -> %-8s: %s L%s  %s  %s %s%s'
                  % (unit_id, slot, class_enum, st.get('level', 1), shown,
                     CLASS_WEAPON[class_enum], WPN_RANK_START, tag))

    with open(CHARACTERS_C, 'w', encoding='utf-8') as f:
        f.write(text)


def main():
    ap = argparse.ArgumentParser(description='Inject campaign content into the decomp build.')
    ap.add_argument('--campaign', default='rime-of-the-frostmaiden')
    ap.add_argument('--portraits-only', action='store_true',
                    help='only inject portrait assets (skip names + characters)')
    args = ap.parse_args()

    print('build_campaign: injecting "%s" into %s' % (args.campaign, DECOMP))
    print('portraits:')
    inject_portraits(args.campaign)
    if not args.portraits_only:
        print('names:')
        inject_names(args.campaign)
        print('characters:')
        patch_character_data(args.campaign)
    print('done. Run `make` to compile the ROM.')


if __name__ == '__main__':
    main()
