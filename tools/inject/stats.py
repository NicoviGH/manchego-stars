"""Milestone B: character stats and class -- donor bases, growths, personal lines.
"""
import re
import sys

from inject.cast import class_enum_for, deploy_class_for, load_unit, PORTRAIT_MAP
from inject.decomp import _find_brace_block, vanilla_decomp_text
from inject.paths import CHARACTERS_C, CLASSES_C


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
    'trex':       'CHARACTER_COLM',      # Thief (ch03 recruit) -- vanilla starter thief donor
    'baxby':      'CHARACTER_FRANZ',     # Cavalier (ch01 recruit) -- fresh-cavalier growth runway
    'lupin':      'CHARACTER_KYLE',      # Cavalier (ch04 red->blue parley recruit); Kyle = stat ref only
    # The ch05 pair (#25). Their donors are what makes the two Priests differ and what makes
    # Sahnar a duelist rather than a generic sword: decisions.md prices Sclorbo as the durable
    # war-priest (Moulder) against Basil as the frail mage-healer (Natasha), and that split
    # exists ONLY here -- the YAML design records show identical Priest CLASS data, because
    # they are the same class. Sahnar takes Joshua, the archetype she was locked to.
    'basil':      'CHARACTER_NATASHA',   # Cleric: frail/high-magic, opposite Sclorbo's Moulder
    'sahnar':     'CHARACTER_JOSHUA',    # Myrmidon: the crit-sword duelist; Joshua = stat ref only
}
GROWTH_FIELDS = ('growthHP', 'growthPow', 'growthSkl', 'growthSpd',
                 'growthDef', 'growthRes', 'growthLck')

# Personal-BASE donor (the starting stat line). Usually the same canonical unit as the
# rank donor (STAT_DONOR), but the two shamans take EWAN's Ch1-appropriate bases (Knoll's
# are lv9-inflated). docs/decisions.md "Party-side parity" / issue #45.
BASE_DONOR = dict(STAT_DONOR, marty='CHARACTER_EWAN', meesmickle='CHARACTER_EWAN')

# GROWTH donor (the level-up curve). Same as the rank donor except Meesmickle, who grows
# on EWAN's curve (-> Summoner: dodge/luck) while Marty keeps Knoll's (-> Druid: soak/nuke).
# Ranks stay on STAT_DONOR so both shamans keep Knoll's ITYPE_DARK rank (Ewan is Anima-only,
# so his tome wouldn't equip). docs/decisions.md "Party-side parity" / issue #45.
GROWTH_DONOR = dict(STAT_DONOR, meesmickle='CHARACTER_EWAN')


# Write each cast unit's vanilla-class identity into its portrait slot's
# gCharacterData[] entry: defaultClass, affinity (Anima, cosmetic), baseLevel --
# and the MECHANICAL character layer inherited from a class-matched VANILLA DONOR
# (STAT_DONOR / GROWTH_DONOR): personal bases = (YAML fe_stats - class base) + the
# donor's personal bases, growths copied verbatim from the growth donor, weapon
# ranks from the rank donor. So an FE-strict unit (fe_stats == class base, the
# default) lands exactly on its donor's statline -- vanilla character data under a
# new identity, not "naked class" frailty (decisions.md: even character-level
# mechanical data is vanilla; ours is the donor CHOICE + cosmetics + levels).
# Any deliberate YAML divergence still stacks on top so displayed stats ==
# fe_stats. Gender IS driven from YAML (_set_gender rewrites .attributes CA_FEMALE);
# only portraitId and pSupportData are left as the vanilla slot's -- supports are a
# later YAML-driven pass.

def _set_field(block, field, value, path, marker):
    """Replace `.field = ...,` within `block`. Errors if the field isn't present."""
    pat = re.compile(r'(\.' + field + r'\s*=\s*)[^,\n]*(,)')
    new, n = pat.subn(lambda m: m.group(1) + str(value) + m.group(2), block, count=1)
    if n == 0:
        sys.exit('ERROR: field .%s not found in %s entry %s' % (field, path, marker))
    return new




def class_base_stats(class_enum, classes_text=None):
    """Read a class's base stats, keyed by CharacterData field name (baseHP, basePow, ...).
    Luck is character-only, so baseLck defaults to 0. `classes_text` overrides the source
    (pass vanilla_decomp_text('src/data_classes.c') to be immune to reskin patching)."""
    text = classes_text if classes_text is not None else open(CLASSES_C, encoding='utf-8').read()
    s, e = _find_brace_block(text, '[%s - 1]' % class_enum, CLASSES_C)
    block = text[s:e]
    out = {'baseLck': 0}
    for cf in CLASS_BASE_FIELDS:
        m = re.search(r'\.' + cf + r'\s*=\s*(-?\d+)', block)
        out[cf] = int(m.group(1)) if m else 0
    return out


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


# A donor's personal base layer = the displayed-stat fields keyed as gCharacterData
# stores them (base* deltas the engine adds on top of the class base). Luck is
# character-only, so a missing field reads 0. baseMov is class-only -> excluded.
BASE_FIELDS = ('baseHP', 'basePow', 'baseSkl', 'baseSpd', 'baseDef',
               'baseRes', 'baseLck', 'baseCon')


def donor_base_stats(vanilla_text, donor_char):
    """Read a stat-donor unit's personal BASE stats from VANILLA data_characters.c
    text. These are the personal line a class-matched canonical unit carries on top
    of its class base -- inheriting them lifts our cast off "naked class" frailty to
    vanilla parity. Mirrors donor_growths_and_ranks (same snapshot discipline)."""
    s, e = _find_brace_block(vanilla_text, '[%s - 1]' % donor_char, CHARACTERS_C)
    block = vanilla_text[s:e]
    bases = {}
    for bf in BASE_FIELDS:
        m = re.search(r'\.' + bf + r'\s*=\s*(-?\d+)', block)
        bases[bf] = int(m.group(1)) if m else 0
    return bases


def twin_line_deltas(twin_char, class_enum):
    """The personal layer that puts a `class_enum` unit on `twin_char`'s vanilla combat line:
    the twin's effective base (its defaultClass base + its personal base) minus our class's
    base, for every BASE_FIELD but Con. Negative where our class out-stats the twin's (a
    Fighter has more HP than Eirika); the fields are signed. Con stays our class's: it is the
    body that carries OUR weapon, and Eirika's Con 5 under a Hand Axe would let everything
    double her. Both read at HEAD, so no slot this build patches can leak in. ch00's guests
    fight on Seth's and Eirika's lines this way (#430)."""
    chars = vanilla_decomp_text('src/data_characters.c')
    classes = vanilla_decomp_text('src/data_classes.c')
    s, e = _find_brace_block(chars, '[%s - 1]' % twin_char, CHARACTERS_C)
    twin_class = re.search(r'\.defaultClass\s*=\s*(\w+)', chars[s:e]).group(1)
    twin_class_base = class_base_stats(twin_class, classes)
    ours = class_base_stats(class_enum, classes)
    personal = donor_base_stats(chars, twin_char)
    return {f: twin_class_base.get(f, 0) + personal[f] - ours.get(f, 0)
            for f in BASE_FIELDS if f != 'baseCon'}


def guest_personal_line(unit, class_enum):
    """The personal base layer a ch00 guest's slot carries: its `twin:` vanilla character's
    line on `class_enum` (`twin_line_deltas`), or {} -- a bare class base -- with no twin.
    The one source for the injector and `difficulty.fixed_roster_careers` (#430)."""
    return twin_line_deltas(unit['twin'], class_enum) if unit.get('twin') else {}


def personal_base_deltas(fe_stats, class_base, donor_base):
    """The personal-base layer to patch into a cast slot's gCharacterData, keyed by base
    field. FE8 shows class base + this layer, so each field is (authored fe_stat - class
    base) + the donor's personal base: an FE-strict unit (fe_stats == class base) lands on
    its donor's line, and any deliberate authored divergence stacks on top. MOV is class-
    only (no STAT_FIELD entry) and is skipped."""
    out = {}
    for fe, value in fe_stats.items():
        field = STAT_FIELD.get(fe)
        if field is None:
            continue
        out[field] = int(value) - class_base.get(field, 0) + donor_base.get(field, 0)
    return out


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
    # Donor bases/growths/ranks are read from the committed (HEAD) source, NOT `text`:
    # several donors (Gilliam, Neimi, Moulder, Vanessa) ride portrait slots this very pass
    # overwrites, so a working-tree read could see an already-patched donor.
    vanilla = vanilla_decomp_text('src/data_characters.c')

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
        block = _set_field(block, 'defaultClass', deploy_class_for(unit), CHARACTERS_C, marker)
        block = _set_field(block, 'affinity', 'UNIT_AFFIN_ANIMA', CHARACTERS_C, marker)
        block = _set_field(block, 'baseLevel', int(st.get('level', 1)), CHARACTERS_C, marker)

        # Personal base layer = (authored - class) + the donor's personal line, so the
        # cast lands at vanilla parity instead of "naked class" (donor-base inheritance, #45).
        dbase = donor_base_stats(vanilla, BASE_DONOR[unit_id])
        deltas = personal_base_deltas(st, cbase, dbase)
        for field, delta in deltas.items():
            block = _set_field(block, field, delta, CHARACTERS_C, marker)

        # Growths from the growth donor, weapon ranks from the rank donor (usually the same
        # unit; the shamans split -- Mees grows on Ewan but keeps Knoll's Dark rank). Both
        # read from VANILLA so the unit levels and fights like a real FE unit of its class.
        growths, _ = donor_growths_and_ranks(vanilla, GROWTH_DONOR[unit_id])
        _, ranks = donor_growths_and_ranks(vanilla, STAT_DONOR[unit_id])
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
            short = lambda d: d.replace('CHARACTER_', '')
            donors = 'base<-%s grow<-%s rank<-%s' % (
                short(BASE_DONOR[unit_id]), short(GROWTH_DONOR[unit_id]),
                short(STAT_DONOR[unit_id]))
            print('  %-10s -> %-8s: %s L%s  %s  %s%s%s'
                  % (unit_id, slot, class_enum, st.get('level', 1), shown,
                     donors, '  [F]' if female else '', tag))

    with open(CHARACTERS_C, 'w', encoding='utf-8') as f:
        f.write(text)
