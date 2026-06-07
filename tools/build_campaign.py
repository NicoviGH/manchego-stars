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
import shutil
import subprocess
import sys
import tempfile

# portrait_tool lives next to us in tools/
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import portrait_tool  # noqa: E402
import map_sprite_tool  # noqa: E402
from PIL import Image  # noqa: E402
import yaml  # noqa: E402

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DECOMP = os.path.join(REPO, 'fireemblem8u')
PORTRAIT_DIR = os.path.join(DECOMP, 'graphics', 'portrait')
CHARACTERS_C = os.path.join(DECOMP, 'src', 'data_characters.c')
CLASSES_C = os.path.join(DECOMP, 'src', 'data_classes.c')
TEXTS_TXT = os.path.join(DECOMP, 'texts', 'texts.txt')
PORTRAIT_DATA_C = os.path.join(DECOMP, 'src', 'portrait_data.c')
# Our busts are all framed identically: the mouth window sits at tile (col 2, row 6)
# and eyes at (col 3, row 4) -- the geometry portrait_tool extracts the mouth from, and
# the same xMouth/yMouth/xEyes/yEyes the Eirika/Franz/Vanessa/Neimi slots already carry
# (those render our busts cleanly). Slots whose FaceData uses different coords (Seth,
# Gilliam, Moulder = 2,5; Ross = 3,6; Garcia = 2,5; Colm = 3,5) make the engine overwrite
# the mouth window one tile off -> a second, offset mouth. Normalize every dressed slot.
PORTRAIT_GEOMETRY = '2, 6, 3, 4'   # xMouth, yMouth, xEyes, yEyes
# Test-chapter spawn (Milestone B step 3): we hijack the vanilla Ch1 ally roster to
# stand up our classed cast on one real map -- the first in-engine confirmation of
# names + portraits + classes + stats together. These are the only two files it touches.
CH1_UDEFS_H = os.path.join(DECOMP, 'src', 'events', 'ch1-eventudefs.h')
CH1_EVENTINFO_H = os.path.join(DECOMP, 'src', 'events', 'ch1-eventinfo.h')
CH1_EVENTSCRIPT_H = os.path.join(DECOMP, 'src', 'events', 'ch1-eventscript.h')
PROLOGUE_WM_H = os.path.join(DECOMP, 'src', 'events', 'prologue-wm.h')
GAMECONTROL_C = os.path.join(DECOMP, 'src', 'gamecontrol.c')
BMIO_C = os.path.join(DECOMP, 'src', 'bmio.c')
# Map (overworld) sprites (#38). FE8 map sprites are CLASS-driven (GetUnitSMSId ->
# pClassData->SMSId), so two cast on the same class share one sprite and enemies of
# that class would inherit a swap. We instead give each cast member a custom SMS slot
# and a per-CHARACTER override in GetUnitSMSId -- stock classes and vanilla enemies
# untouched. Classes top out at SMSId 106 (verified), so 107+ is free in both the
# wait array (extended here) and the move table (dead tail; no class reaches it).
BMUNIT_C = os.path.join(DECOMP, 'src', 'bmunit.c')
UNIT_ICON_WAIT_C = os.path.join(DECOMP, 'src', 'unit_icon_wait_data.c')
UNIT_ICON_WAIT_S = os.path.join(DECOMP, 'data', 'const_data_unit_icon_wait.s')
UNIT_ICON_POINTER_H = os.path.join(DECOMP, 'include', 'unit_icon_pointer.h')
WAIT_GFX_DIR = os.path.join(DECOMP, 'graphics', 'unit_icon', 'wait')
CUSTOM_SMS_BASE = 107
# The hover/selected + walking sprite is the per-class MU sheet (gMuInfoTable ==
# unit_icon_move_table, a MuInfo{img, anim} view; 32x480 = 15x 32x32). MuProc carries
# ->unit, so a per-character override of GetUnitMU's .img (reusing the class .anim/motion)
# gives a custom walk without touching classes/enemies. Asset: map_sprites/<id>_mu.png.
MU_C = os.path.join(DECOMP, 'src', 'mu.c')
UNIT_ICON_MOVE_C = os.path.join(DECOMP, 'src', 'unit_icon_move_data.c')
UNIT_ICON_MOVE_S = os.path.join(DECOMP, 'data', 'const_data_unit_icon_move.s')
MOVE_GFX_DIR = os.path.join(DECOMP, 'graphics', 'unit_icon', 'move')
BMUDISP_C = os.path.join(DECOMP, 'src', 'bmudisp.c')
# New-game boots straight into the test chapter (skip the vanilla prologue) so the
# spawn is one "New Game" away. CHAPTER_L_1 = 0x01 (constants/chapters.h).
TEST_CHAPTER_INDEX = 1

# FE8's unit-name buffer; longer names overflow and garble the display.
FE_NAME_MAX = 12

# Decomp source files we patch in place. We git-restore them to vanilla at the start
# of every build so injection always runs from a clean base -- idempotent across
# repeated `make`s, and stat-donor growths/ranks always read vanilla values.
PATCHED_DECOMP_FILES = ['texts/texts.txt', 'src/data_characters.c', 'src/portrait_data.c',
                        'src/events/ch1-eventudefs.h', 'src/events/ch1-eventinfo.h',
                        'src/events/ch1-eventscript.h', 'src/events/prologue-wm.h',
                        'src/gamecontrol.c', 'src/bmio.c', 'src/bmunit.c',
                        'src/unit_icon_wait_data.c', 'src/unit_icon_move_data.c', 'src/mu.c',
                        'src/bmudisp.c',
                        'data/const_data_unit_icon_wait.s', 'data/const_data_unit_icon_move.s',
                        'include/unit_icon_pointer.h']


def restore_vanilla_sources():
    subprocess.run(['git', '-C', DECOMP, 'checkout', '--'] + PATCHED_DECOMP_FILES,
                   check=True)

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

# "Do what the actual game does": each cast unit takes the GROWTHS and starting
# WEAPON RANKS of a canonical vanilla FE8 unit of the same class (its stat donor),
# so it levels and fights like a real FE unit of that class -- not an invented
# scheme. Donor data is read from VANILLA data_characters.c (a snapshot taken before
# any patching), so it's correct even when the donor is itself a portrait slot we
# repurpose. Pirate has no permanent PC in FE8 -> Garcia (axe fighter) is the proxy.
STAT_DONOR = {
    'braulo':     'CHARACTER_GARCIA',    # Pirate: no PC pirate in FE8; axe-fighter proxy
    'marty':      'CHARACTER_KNOLL',     # Shaman
    'meesmickle': 'CHARACTER_KNOLL',     # Shaman
    'wolfram':    'CHARACTER_GILLIAM',   # Armor Knight
    'prof-rbg':   'CHARACTER_NEIMI',     # Archer
    'rootis':     'CHARACTER_LUTE',      # Mage
    'sclorbo':    'CHARACTER_MOULDER',   # Priest
    'pinky':      'CHARACTER_VANESSA',   # Pegasus Knight
}
GROWTH_FIELDS = ('growthHP', 'growthPow', 'growthSkl', 'growthSpd',
                 'growthDef', 'growthRes', 'growthLck')


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


def patch_portrait_geometry(verbose=True):
    """Normalize the mouth/eye window coords of every dressed portrait slot to our
    bust framing, so the engine's mouth-window overwrite lands on our baked mouth
    (not one tile off, which doubles it). See PORTRAIT_GEOMETRY."""
    slots = sorted(set(PORTRAIT_MAP.values()))
    with open(PORTRAIT_DATA_C, encoding='utf-8') as f:
        lines = f.read().split('\n')
    # FaceData tail: `, 0, xMouth, yMouth, xEyes, yEyes, FACE_BLINK_*`. The `, 0,`
    # constant anchors the four geometry fields uniquely on each entry line.
    geom = re.compile(r'(,\s*0,\s*)\d+,\s*\d+,\s*\d+,\s*\d+(,\s*FACE_BLINK)')
    n = 0
    for i, line in enumerate(lines):
        if any('portrait_%s_tileset' % s in line for s in slots):
            new = geom.sub(r'\g<1>%s\2' % PORTRAIT_GEOMETRY, line)
            if new != line:
                lines[i] = new
                n += 1
    if n == 0:
        sys.exit('ERROR: no portrait_data.c entries matched for geometry patch')
    with open(PORTRAIT_DATA_C, 'w', encoding='utf-8') as f:
        f.write('\n'.join(lines))
    if verbose:
        print('  normalized %d slot entries to mouth/eye (%s)' % (n, PORTRAIT_GEOMETRY))


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


def donor_growths_and_ranks(vanilla_text, donor_char):
    """Read a stat-donor unit's growths + baseRanks initializer from VANILLA
    data_characters.c text (so it's unaffected by patches we apply this run)."""
    s, e = _find_brace_block(vanilla_text, '[%s - 1]' % donor_char, CHARACTERS_C)
    block = vanilla_text[s:e]
    growths = {}
    for gf in GROWTH_FIELDS:
        m = re.search(r'\.' + gf + r'\s*=\s*(-?\d+)', block)
        growths[gf] = int(m.group(1)) if m else 0
    rm = re.search(r'\.baseRanks\s*=\s*(\{.*?\})', block, re.DOTALL)
    ranks = re.sub(r'\s+', ' ', rm.group(1)).strip() if rm else '{}'
    return growths, ranks


def _set_gender(block, female):
    """Set the CA_FEMALE attribute. Replaces .attributes if present; if absent,
    inserts it only when female (absent already means 0 == male)."""
    val = 'CA_FEMALE' if female else '0'
    pat = re.compile(r'(\.attributes\s*=\s*)[^,\n]*(,)')
    new, n = pat.subn(lambda m: m.group(1) + val + m.group(2), block, count=1)
    if n:
        return new
    if not female:
        return block  # no attributes field => already 0 => male; nothing to do
    idx = block.rfind('}')
    return block[:idx] + '    .attributes = CA_FEMALE,\n    ' + block[idx:]


def patch_character_data(campaign, verbose=True):
    """Inject class + base stats into each cast slot's gCharacterData entry."""
    with open(CHARACTERS_C, encoding='utf-8') as f:
        text = f.read()
    vanilla = text  # snapshot for reading stat-donor growths/ranks (pre-patch)

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

        # Growths + weapon ranks: take a class-matched vanilla unit's (the donor),
        # so the unit levels and fights like a real FE unit of its class.
        donor = STAT_DONOR[unit_id]
        growths, ranks = donor_growths_and_ranks(vanilla, donor)
        for gf, gv in growths.items():
            block = _set_field(block, gf, gv, CHARACTERS_C, marker)
        block, n = re.subn(r'(\.baseRanks\s*=\s*)\{.*?\}',
                           lambda m: m.group(1) + ranks, block, count=1, flags=re.DOTALL)
        if n == 0:
            sys.exit('ERROR: .baseRanks not found in %s %s' % (CHARACTERS_C, marker))

        # Gender flag (CA_FEMALE): drive from YAML (default male). Some vanilla entries
        # omit .attributes (absent == 0 == male), so set tolerantly. Clears CA_FEMALE
        # leaking from the slot; custom gendered sprites are a separate art pass.
        female = str(unit.get('gender', 'male')).lower() == 'female'
        block = _set_gender(block, female)

        text = text[:s] + block + text[e:]
        if verbose:
            shown = ' '.join('%s%d' % (k, int(st[k])) for k in
                             ('HP', 'STR', 'MAG', 'SKL', 'SPD', 'DEF', 'RES', 'LCK', 'CON')
                             if k in st)
            nz = {k: v for k, v in deltas.items() if v != 0}
            tag = '' if not nz else '  (deltas %s)' % nz
            print('  %-10s -> %-8s: %s L%s  %s  growths+ranks<-%s%s%s'
                  % (unit_id, slot, class_enum, st.get('level', 1), shown,
                     donor.replace('CHARACTER_', ''),
                     '  [F]' if female else '', tag))

    with open(CHARACTERS_C, 'w', encoding='utf-8') as f:
        f.write(text)


# --- Milestone B step 3: test-chapter spawn ---------------------------------------
# First in-engine confirmation that names + portraits + classes + stats land together.
# We keep vanilla Ch1's MAP but strip its scripting to a bare sandbox: the original
# beginning scene choreographs specific vanilla units (scripted Breguet fight, forced
# moves, MoveUnitS2ToLeader) and was deleting our cast mid-cutscene -> instant lord-
# death game over. Instead we:
#   * rewrite the player roster (UnitDef_Event_Ch1Ally) to our classed cast,
#   * replace the beginning scene with a minimal "load the cast, hand over control",
#   * empty every per-chapter event list (turn/character/location/misc/tutorial) so
#     nothing references removed units or fires a win/lose condition,
#   * cut the boot attract reel + redirect prologue->Ch1 so a fresh boot lands on the
#     title and New Game drops straight onto the map (dev loop).
# Result: New Game -> Ch1 map with the 8 cast, no cutscene, no game over -- a pure
# look-test (no enemies, no objective; reset when done). Each cast unit rides its
# PORTRAIT_MAP slot's CHARACTER_ id, so its injected name/portrait/class/stats show.
# redaCount=0 places a unit statically at xPosition/yPosition (eventscr.c sub_800F8A8).
# All edits are restorable build artifacts (PATCHED_DECOMP_FILES). Authored chapters
# (real maps/events/objectives from YAML) supersede this whole step.

# Stock starting loadout per class enum (vanilla ITEM_ ids; see constants/items.h).
CLASS_LOADOUT = {
    'CLASS_PIRATE':         ['ITEM_AXE_IRON', 'ITEM_AXE_HANDAXE', 'ITEM_VULNERARY'],
    'CLASS_SHAMAN':         ['ITEM_DARK_FLUX', 'ITEM_VULNERARY'],
    'CLASS_ARCHER':         ['ITEM_BOW_IRON', 'ITEM_VULNERARY'],
    'CLASS_MAGE':           ['ITEM_ANIMA_FIRE', 'ITEM_VULNERARY'],
    'CLASS_PRIEST':         ['ITEM_STAFF_HEAL', 'ITEM_VULNERARY'],
    'CLASS_ARMOR_KNIGHT':   ['ITEM_LANCE_IRON', 'ITEM_VULNERARY'],
    'CLASS_PEGASUS_KNIGHT': ['ITEM_LANCE_SLIM', 'ITEM_LANCE_JAVELIN', 'ITEM_VULNERARY'],
}
# Centered, spread-out formation on the Ch1 map (a 4x2 grid, 2-tile gaps), clear of the
# houses (13,6)/(10,4) and seize (2,2). Pulled in from the old bottom-right cluster so the
# cast reads spaced out toward the middle for the look-test. Roster fills in order.
TEST_SPAWN_POSITIONS = [(5, 4), (7, 4), (9, 4), (11, 4),
                        (5, 6), (7, 6), (9, 6), (11, 6)]


def _replace_brace_block(text, marker, new_body, path):
    """Replace the `{...}` after `marker` with `new_body` (a `{...}` string)."""
    s, e = _find_brace_block(text, marker, path)
    return text[:s] + new_body + text[e:]


def inject_test_chapter(campaign, verbose=True):
    """Rewrite Ch1's ally roster to our classed cast and disable Ch1 tutorials."""
    # Build the cast roster in PORTRAIT_MAP order, skipping name-only units (no class).
    units = []
    for unit_id, slot in PORTRAIT_MAP.items():
        unit = load_unit(campaign, unit_id)
        unit.setdefault('id', unit_id)
        class_enum = class_enum_for(unit)
        if class_enum is None:
            continue
        if class_enum not in CLASS_LOADOUT:
            sys.exit('ERROR: no test loadout for %s (unit %s)' % (class_enum, unit_id))
        units.append((unit_id, slot, class_enum, unit))
    if len(units) > len(TEST_SPAWN_POSITIONS):
        sys.exit('ERROR: %d classed cast > %d test spawn positions'
                 % (len(units), len(TEST_SPAWN_POSITIONS)))

    leader = 'CHARACTER_%s' % units[0][1].upper()  # the lord slot anchors the roster
    entries = []
    for (unit_id, slot, class_enum, unit), (x, y) in zip(units, TEST_SPAWN_POSITIONS):
        items = ', '.join(CLASS_LOADOUT[class_enum])
        entries.append(
            '    {\n'
            '        .charIndex = CHARACTER_%s,\n'
            '        .classIndex = %s,\n'
            '        .leaderCharIndex = %s,\n'
            '        .allegiance = FACTION_ID_BLUE,\n'
            '        .level = %d,\n'
            '        .xPosition = %d,\n'
            '        .yPosition = %d,\n'
            '        .redaCount = 0,\n'
            '        .items = { %s },\n'
            '    },' % (slot.upper(), class_enum, leader,
                        int(unit.get('fe_stats', {}).get('level', 1)),
                        x, y, items))
    roster = '{\n' + '\n'.join(entries) + '\n    { 0 },\n}'

    with open(CH1_UDEFS_H, encoding='utf-8') as f:
        udefs = f.read()
    udefs = _replace_brace_block(
        udefs, 'UnitDef_Event_Ch1Ally[] =', roster, CH1_UDEFS_H)
    with open(CH1_UDEFS_H, 'w', encoding='utf-8') as f:
        f.write(udefs)

    # Empty every per-chapter event list so nothing references the removed cutscene
    # units or triggers a win/lose condition. Each is an EventListScr[] terminated by
    # END_MAIN; the tutorial list is a pointer array terminated by NULL.
    with open(CH1_EVENTINFO_H, encoding='utf-8') as f:
        info = f.read()
    for name in ('EventListScr_Ch1_Turn', 'EventListScr_Ch1_Character',
                 'EventListScr_Ch1_Location', 'EventListScr_Ch1_Misc'):
        info = _replace_brace_block(info, name + '[] =', '{\n    END_MAIN\n}',
                                    CH1_EVENTINFO_H)
    info = _replace_brace_block(
        info, 'EventListScr_Ch1_Tutorial[] =', '{\n    NULL\n}', CH1_EVENTINFO_H)
    with open(CH1_EVENTINFO_H, 'w', encoding='utf-8') as f:
        f.write(info)

    # Minimal beginning scene: deploy the cast and hand over control. (Vanilla's scene
    # ran a scripted fight + forced moves that wiped our units.) LOAD1 deploys the
    # chapter's player UnitDefinition; ENUN waits for the placement; ENDA ends.
    with open(CH1_EVENTSCRIPT_H, encoding='utf-8') as f:
        script = f.read()
    minimal_begin = ('{\n'
                     '    LOAD1(1, UnitDef_Event_Ch1Ally)\n'
                     '    ENUN\n'
                     '    ENDA\n'
                     '}')
    script = _replace_brace_block(
        script, 'EventScr_Ch1_BeginningScene[] =', minimal_begin, CH1_EVENTSCRIPT_H)
    with open(CH1_EVENTSCRIPT_H, 'w', encoding='utf-8') as f:
        f.write(script)

    # Dev loop: cut every pre-map sequence so a fresh boot lands on the title and New
    # Game drops straight onto the map. Four cuts, each at the source that actually
    # plays the thing (a previous single-hook attempt at GameControl_RememberChapterId
    # was reset before the world-map wrapper, so the Magvel tour still ran):
    #   (a) gamecontrol.c: drop the boot OP anim (ProcScr_OpAnim, the character-flash +
    #       attract reel) so boot falls through to the title;
    #   (b) gamecontrol.c: skip the post-New-Game intro monologue (the "long ago..."
    #       lore crawl) -- GameCtrlStartIntroMonologue runs it only while chapterIndex
    #       == 0; force it to bail;
    #   (c) bmio.c: redirect prologue -> Ch1 at the authoritative map-load point,
    #       StartBattleMap (feeds gPlaySt.chapterIndex into InitChapterMap/fog/weather):
    #       if (chapterIndex == 0) chapterIndex = 1. chapterIndex == 0 there can only be
    #       a fresh game's prologue (skirmishes use PLAY_FLAGs; later chapters nonzero);
    #   (d) prologue-wm.h: gut the prologue's world-map intro (EventScrWM_Prologue_
    #       Beginning runs WM_TEXT(0x8DB) -- the "continent of Magvel" nation-by-nation
    #       tour). The WM wrapper runs it BEFORE StartBattleMap's redirect, so (c) alone
    #       doesn't stop it; replace its body with Ch1's no-op (EVBIT_MODIFY/SKIPWN/ENDA).
    with open(GAMECONTROL_C, encoding='utf-8') as f:
        gc = f.read()
    gc, n1 = re.subn(r'[ \t]*PROC_START_CHILD_BLOCKING\(ProcScr_OpAnim\),\n',
                     '', gc, count=1)
    if n1 == 0:
        sys.exit('ERROR: ProcScr_OpAnim start not found in %s' % GAMECONTROL_C)
    gc, n2 = re.subn(r'\n(\s*)StartIntroMonologue\(proc\);',
                     r'\n\1return; /* test-chapter: skip intro monologue */',
                     gc, count=1)
    if n2 == 0:
        sys.exit('ERROR: StartIntroMonologue call not found in %s' % GAMECONTROL_C)
    with open(GAMECONTROL_C, 'w', encoding='utf-8') as f:
        f.write(gc)

    with open(BMIO_C, encoding='utf-8') as f:
        bmio = f.read()
    bmio, n3 = re.subn(
        r'(void StartBattleMap\(struct GameCtrlProc\* gameCtrl\) \{\n    int i;\n)',
        r'\1\n    if (gPlaySt.chapterIndex == 0) /* test-chapter spawn: prologue -> Ch1 */\n'
        r'        gPlaySt.chapterIndex = %d;\n' % TEST_CHAPTER_INDEX,
        bmio, count=1)
    if n3 == 0:
        sys.exit('ERROR: StartBattleMap signature not found in %s' % BMIO_C)
    with open(BMIO_C, 'w', encoding='utf-8') as f:
        f.write(bmio)

    with open(PROLOGUE_WM_H, encoding='utf-8') as f:
        wm = f.read()
    wm = _replace_brace_block(
        wm, 'EventScrWM_Prologue_Beginning[] =',
        '{\n    EVBIT_MODIFY(0x1)\n    SKIPWN\n    ENDA\n}', PROLOGUE_WM_H)
    with open(PROLOGUE_WM_H, 'w', encoding='utf-8') as f:
        f.write(wm)

    if verbose:
        for unit_id, slot, class_enum, _ in units:
            print('  %-10s -> Ch1 ally (%s as %s)'
                  % (unit_id, slot, class_enum.replace('CLASS_', '')))
        print('  Ch1 stripped to sandbox; boot attract + Magvel intro cut; '
              'New Game boots into Ch1')


# --- Map (overworld) sprites (#38) ------------------------------------------------
# FE8 draws map sprites by class (GetUnitSMSId -> pClassData->SMSId). To give each
# cast member a distinct overworld sprite without touching stock classes or vanilla
# enemies, we add a custom SMS slot per cast member (ids CUSTOM_SMS_BASE+) and a
# per-CHARACTER override in GetUnitSMSId. Colours come from the one shared cast
# palette (unit_icon_pal_player.agbpal) -- map sprites can't carry their own.


def classed_cast(campaign):
    """Cast (PORTRAIT_MAP order) that carry an FE class, each paired with a stable
    custom SMS id (CUSTOM_SMS_BASE + position). Name-only units are skipped. Ids are
    position-based so a unit keeps the same id whether or not its sprite is authored."""
    out, i = [], 0
    for unit_id, slot in PORTRAIT_MAP.items():
        unit = load_unit(campaign, unit_id)
        unit.setdefault('id', unit_id)
        if class_enum_for(unit) is None:
            continue
        out.append((unit_id, slot, class_enum_for(unit), CUSTOM_SMS_BASE + i))
        i += 1
    return out


def _table_close_line(lines, decl):
    """(decl line index, closing `};` line index) for a C array `decl`."""
    di = next((i for i, ln in enumerate(lines) if decl in ln), None)
    if di is None:
        sys.exit('ERROR: %r not found' % decl)
    ci = next((i for i in range(di + 1, len(lines)) if lines[i].strip() == '};'), None)
    if ci is None:
        sys.exit('ERROR: close of %r not found' % decl)
    return di, ci


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


def _inject_sms_override_hook():
    """Patch GetUnitSMSId to consult the build-injected per-character override table
    before falling back to the unit's class map sprite."""
    with open(BMUNIT_C, encoding='utf-8') as f:
        text = f.read()
    orig = ('int GetUnitSMSId(struct Unit* unit) {\n'
            '    if (!(unit->state & US_IN_BALLISTA))\n'
            '        return unit->pClassData->SMSId;\n')
    hooked = (
        'extern unsigned short gMapSpriteOverride[];\n\n'
        'int GetUnitSMSId(struct Unit* unit) {\n'
        '    if (!(unit->state & US_IN_BALLISTA)) {\n'
        '        /* Campaign per-character map-sprite override (build-injected; the\n'
        '         * table is empty in vanilla). Lets a cast member wear a custom\n'
        '         * overworld sprite its stock class -- and any enemy of that class\n'
        '         * -- does not. */\n'
        '        const unsigned short * mso = gMapSpriteOverride;\n'
        '        int charId = UNIT_CHAR_ID(unit);\n'
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
        'extern struct CharMuImg gMuImgOverride[];\n\n'
        'const void * GetMuImg(struct MuProc * proc)\n'
        '{\n'
        '    /* Campaign per-character MU (hover/walk) sprite override (build-injected;\n'
        '     * empty in vanilla). Reuses the class motion script -- graphics only. */\n'
        '    if (proc->unit) {\n'
        '        struct CharMuImg * it = gMuImgOverride;\n'
        '        int charId = UNIT_CHAR_ID(proc->unit);\n'
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
    Pads short palettes with black; errors if it carries more than 16 entries."""
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


def _inject_palette_bank_hook():
    """Patch bmudisp.c so the custom cast share a bespoke palette in the campaign-unused
    purple OBJ bank (0xB / OBJPAL_UNITSPRITE_PURPLE), leaving the shared player palette
    (blue bank) untouched -- so the not-yet-custom cast still render correctly:
      * GetUnitSpritePalette -- per-character override returning the purple bank before
        the faction switch. StartMu uses this too, so it covers idle + hover/walk; the
        grey "acted" tint is handled upstream in GetUnitDisplayedSpritePalette.
      * ApplyUnitSpritePalettes -- load gCastMapPalette into the purple bank (replacing
        the single-player Light-Rune load; Light Rune is an unused DUMMY item)."""
    with open(BMUDISP_C, encoding='utf-8') as f:
        text = f.read()

    gsp_orig = ('int GetUnitSpritePalette(const struct Unit * unit)\n'
                '{\n'
                '    switch (UNIT_FACTION(unit)) {\n')
    gsp_hooked = (
        'extern unsigned short gMapPaletteOverride[];\n\n'
        'int GetUnitSpritePalette(const struct Unit * unit)\n'
        '{\n'
        '    /* Campaign per-character map-palette override (build-injected; empty in\n'
        '     * vanilla). Custom cast wear a bespoke palette in the purple bank so the\n'
        '     * shared player (blue) palette stays untouched. */\n'
        '    const unsigned short * mp = gMapPaletteOverride;\n'
        '    int charId = UNIT_CHAR_ID(unit);\n'
        '    while (*mp != 0xFFFF) {\n'
        '        if (*mp == charId)\n'
        '            return OBJPAL_UNITSPRITE_PURPLE;\n'
        '        mp++;\n'
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


def _inject_cast_palette(palette_u16, char_slots):
    """Emit gCastMapPalette (the bespoke 16-colour bank) + gMapPaletteOverride (the
    charIds that wear it, 0xFFFF-terminated) into the kept .data file, then patch the
    bmudisp palette hooks. char_slots = portrait-slot names (-> CHARACTER_<SLOT>)."""
    with open(UNIT_ICON_WAIT_C, encoding='utf-8') as f:
        wait_c = f.read()
    if 'constants/characters.h' not in wait_c:
        wait_c = wait_c.replace('#include "unit_icon_data.h"',
                                '#include "unit_icon_data.h"\n#include "constants/characters.h"', 1)
    pal = ', '.join('0x%04X' % c for c in palette_u16)
    ov = '\n'.join('\tCHARACTER_%s,' % s.upper() for s in char_slots)
    wait_c += ('\n/* injected: bespoke cast map-sprite palette (loaded into the purple OBJ\n'
               ' * bank) + the charIds that wear it (0xFFFF-terminated). Non-const so they\n'
               ' * share unit_icon_wait_table\'s kept .data section. */\n'
               'unsigned short gCastMapPalette[16] = { %s };\n' % pal
               + 'unsigned short gMapPaletteOverride[] = {\n' + ov + '\n\t0xFFFF\n};\n')
    with open(UNIT_ICON_WAIT_C, 'w', encoding='utf-8') as f:
        f.write(wait_c)
    _inject_palette_bank_hook()


def inject_map_sprites(campaign, verbose=True):
    """Give cast members a custom overworld sprite distinct from their class.

    Two sheets per character, both optional and added one at a time (no asset -> the
    unit keeps its stock-class sprite; stock classes and vanilla enemies untouched):
      * map_sprites/<id>.png      -> IDLE (wait sheet): a custom SMS slot (id 107+)
        plus a GetUnitSMSId per-character override.
      * map_sprites/<id>_mu.png   -> HOVER/WALK (MU sheet, 32x480): a custom move sheet
        plus a GetMuImg per-character override (reuses the class motion script)."""
    asset_dir = os.path.join(REPO, 'campaigns', campaign, 'map_sprites')
    cast = classed_cast(campaign)
    idle = [(uid, slot, cls, sms) for (uid, slot, cls, sms) in cast
            if os.path.isfile(os.path.join(asset_dir, uid + '.png'))]
    if not idle:
        if verbose:
            print('  (no map_sprites/*.png assets yet; cast keep their class sprites)')
        return

    # MU (hover/walk) sheet per idle character: a committed <id>_mu.png if hand-authored,
    # else a static "glide" sheet synthesized from the finished idle frame so a MOVING
    # unit keeps its custom sprite instead of reverting to the stock class one (idle-only
    # decision -- map_sprite_tool.synth_mu_sheet). Synthesized sheets go to a temp dir so
    # no derived asset lands in the working tree; the single source of truth is the idle.
    mu, mu_tmp = [], None
    for uid, slot, cls, sms in idle:
        committed = os.path.join(asset_dir, uid + '_mu.png')
        if os.path.isfile(committed):
            mu.append((uid, slot, cls, committed))
            continue
        if mu_tmp is None:
            mu_tmp = tempfile.mkdtemp(prefix='manchego_mu_')
        src = os.path.join(mu_tmp, uid + '_mu.png')
        nudge = ((load_unit(campaign, uid).get('art') or {}).get('map_sprite') or {}).get(
            'glide_nudge', 0)
        map_sprite_tool.synth_mu_sheet(os.path.join(asset_dir, uid + '.png'),
                                       _donor_base(campaign, uid), src,
                                       y_nudge=nudge, verbose=verbose)
        mu.append((uid, slot, cls, src))

    pointer_externs = []
    _inject_idle_sprites(campaign, asset_dir, idle, pointer_externs)
    _inject_mu_sprites(mu, pointer_externs)
    if pointer_externs:
        with open(UNIT_ICON_POINTER_H, 'a', encoding='utf-8') as f:
            f.write('\n/* Manchego Stars custom map sprites (#38) */\n'
                    + '\n'.join(pointer_externs) + '\n')

    # Any cast with a custom sprite (idle and/or MU) wears the bespoke cast palette in
    # its own OBJ bank -- its sheet is drawn to the cast-palette indices, so it must be
    # viewed through that palette (decisions.md Art & Audio).
    custom_slots = [slot for _, slot, _, _ in idle]
    custom_slots += [slot for _, slot, _, _ in mu if slot not in custom_slots]
    if custom_slots:
        pal_png = os.path.join(asset_dir, 'cast_palette.png')
        if not os.path.isfile(pal_png):
            sys.exit('ERROR: custom map sprites need campaigns/%s/map_sprites/cast_palette.png'
                     % campaign)
        _inject_cast_palette(_read_cast_palette(pal_png), custom_slots)

    if verbose:
        for uid, slot, class_enum, sms in idle:
            print('  %-10s -> idle SMS %d (%s)' % (uid, sms, slot))
        for uid, slot, class_enum, src in mu:
            kind = 'committed' if os.path.dirname(src) == asset_dir else 'glide'
            print('  %-10s -> hover/walk MU sheet (%s, %s)' % (uid, slot, kind))
        if custom_slots:
            print('  cast palette -> purple OBJ bank for: %s' % ', '.join(custom_slots))


def _donor_base(campaign, uid):
    """The vanilla class/monster a cast member reskins (YAML art.map_sprite.base) -- the
    key that lets us read the sprite's SMS size from the decomp instead of guessing it."""
    unit = load_unit(campaign, uid)
    try:
        return unit['art']['map_sprite']['base']
    except (KeyError, TypeError):
        sys.exit('ERROR: %s has map_sprites/%s.png but no art.map_sprite.base in its YAML '
                 '(needed to read the SMS size from the decomp)' % (uid, uid))


def _inject_idle_sprites(campaign, asset_dir, idle, pointer_externs):
    """Wait-table slot + GetUnitSMSId override for each idle (<id>.png) asset."""
    wait_rows, incbin, overrides = [], [], []
    for uid, slot, class_enum, sms in idle:
        # Frame size from the decomp wait table for the donor base -- not guessed.
        _, dfw, dfh = map_sprite_tool.donor_sms_geometry(_donor_base(campaign, uid))
        macro, fw, fh, nframes = map_sprite_tool.sheet_info(
            os.path.join(asset_dir, uid + '.png'), (dfw, dfh))
        sym = 'unit_icon_wait_manchego_%s_sheet' % uid.replace('-', '_')
        shutil.copyfile(os.path.join(asset_dir, uid + '.png'),
                        os.path.join(WAIT_GFX_DIR, sym + '.png'))
        wait_rows.append('\t{0, %s, %s}, /* %d %s */' % (macro, sym, sms, uid))
        incbin += ['\t.global %s' % sym, '%s:' % sym,
                   '\t.incbin "graphics/unit_icon/wait/%s.4bpp.lz"' % sym,
                   '\t.align 2, 0']
        pointer_externs.append('extern char %s[];' % sym)
        overrides.append('\tCHARACTER_%s, %d,' % (slot.upper(), sms))

    _append_table_rows(UNIT_ICON_WAIT_C, 'unit_icon_wait_table[]', wait_rows)
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
        restore_vanilla_sources()  # clean base each build (idempotent; vanilla donor reads)
        print('names:')
        inject_names(args.campaign)
        print('characters:')
        patch_character_data(args.campaign)
        print('portrait geometry:')
        patch_portrait_geometry()
        print('test chapter (Ch1 spawn):')
        inject_test_chapter(args.campaign)
        print('map sprites:')
        inject_map_sprites(args.campaign)
    print('done. Run `make` to compile the ROM.')


if __name__ == '__main__':
    main()
