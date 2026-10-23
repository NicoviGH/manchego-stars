#!/usr/bin/env python3
"""What the ROM loads a red unit with, per difficulty mode, as min~max ranges.

A wiki table shows what the player will actually meet, so this transcribes the engine's load
path, and keeps its randomness as a range the way the Fire Emblem Wiki prints generic enemies
("22~24"). The parity model (difficulty.py) rolls the same path once per career instead
(`autolevel_increase`, #510 step 4):

  LoadUnit (bmunit.c:617)        stats = character base + class base (luck is personal only);
                                 only a definition with `.autolevel` grows past that.
  UnitAutolevel (bmunit.c:823)   a generic grows (level-1) levels of CLASS growths, plus
                                 GetCurrentPromotedLevelBonus() levels -- 9, or 19 on
                                 Difficult (bmdifficulty.c:53) -- when its class is promoted.
  UnitAutolevelRealistic         an autolevelled CA_BOSS or pid < 0x40 levels up from its
                                 baseLevel on its PERSONAL growths instead (vanilla Ch13's
                                 Amelia and Cormag; none of ours).
  eventscr.c:2328                every red unit with pid >= 0x3C then takes the chapter's
                                 shift, flagged or not: Difficult adds `bonus` levels of class
                                 growths (UnitAutolevelCore); Easy/Normal run
                                 UnitAutolevelPenalty, which re-derives the unit from base and
                                 re-autolevels it at (level - malus), but only when level >
                                 baseLevel, and grows it only when level - malus > baseLevel.
  GetAutoleveledStatIncrease     growth*n jittered by +-1/8, then the remainder rolled
  (bmbattle.c:1241)              (GetStatIncrease) -- the source of the range.

Stats are capped at the class maximum (UnitCheckStatCaps). `growth_steps` is that path as
data, and difficulty.py's model reads the same steps (#490), so the two agree.
"""
import functools
import re

import inject.decomp
import inject.stats

MODES = ('tutorial', 'normal', 'difficult')
STATS = ('HP', 'Pow', 'Skl', 'Spd', 'Lck', 'Def', 'Res', 'Con', 'Mov')
GROWN = ('HP', 'Pow', 'Skl', 'Spd', 'Def', 'Res', 'Lck')
SHIFT_MIN_PID = 0x3C


@functools.lru_cache(maxsize=None)
def _class_block(class_enum):
    """A class's whole `gClassData` entry. Brace-balanced: the entry nests `.baseRanks = {...},`,
    and a match that stopped at the first `},` dropped every field from the ranks on (#493:
    it read every class as rankless, and Ravisin's Druid as unable to wield her Flux)."""
    text = inject.decomp.vanilla_decomp_text('src/data_classes.c')
    marker = '[%s - 1]' % class_enum
    if marker not in text:
        raise KeyError(class_enum)
    s, e = inject.decomp._find_brace_block(text, marker, 'src/data_classes.c')
    return text[s:e]


@functools.lru_cache(maxsize=None)
def rank_thresholds():
    """{rank letter: weapon exp}, from the decomp's own enum (include/bmitem.h)."""
    text = inject.decomp.vanilla_decomp_text('include/bmitem.h')
    return {k: int(v) for k, v in re.findall(r'\bWPN_EXP_([SABCDE])\s*=\s*(\d+)', text)}


def _wexp(token):
    letter = re.match(r'WPN_EXP_([SABCDE0])$', token)
    if letter:
        return 0 if letter.group(1) == '0' else rank_thresholds()[letter.group(1)]
    return int(token, 0)


def unit_ranks(class_enum, char_block=''):
    """{ITYPE: wexp} a unit loads with: its class's baseRanks, each non-zero rank of its
    character's own over them (UnitInitFromDefinition, bmunit.c). `char_block` is the
    character's data_characters.c entry, '' for none."""
    out = {}
    for b in (_class_block(class_enum), char_block or ''):
        m = re.search(r'\.baseRanks\s*=\s*\{(.*?)\}', b, re.S)
        for t, v in re.findall(r'\[(ITYPE_\w+)\]\s*=\s*(\w+)', m.group(1) if m else ''):
            if _wexp(v):
                out[t] = _wexp(v)
    return out


@functools.lru_cache(maxsize=None)
def _item_block(item_enum):
    """One item's gItemData entry, from `.number = ITEM_X` to the next entry."""
    text = inject.decomp.vanilla_decomp_text('src/data_items.c')
    m = re.search(r'\.number\s*=\s*%s\s*,(.*?)(?=\.number\s*=|\Z)' % re.escape(item_enum),
                  text, re.S)
    if not m:
        raise KeyError(item_enum)
    return m.group(1)


def attributes_in(block):
    """The flags on a decomp entry's `.attributes` line (a class, character or item block), as
    a frozenset. Empty when the entry has none, or writes `0`: absent means zero, not
    inherited. Reads one line, so a trailing comment or CRLF cannot pull in the next field."""
    m = re.search(r'\.attributes\s*=\s*([^,\n]+)', block)
    return frozenset(t.strip() for t in (m.group(1) if m else '').split('|')
                     if t.strip() and t.strip() != '0')


def item_attributes(item_enum):
    return attributes_in(_item_block(item_enum))


def can_use_weapon(item_enum, class_enum, char_block='', attributes=frozenset(), autolevel=True):
    """`CanUnitUseWeapon` (bmitem.c) for a red unit as it loads. `attributes` is the unit's
    CA_* set (class | character). A lock bit needs its CA_LOCK; the monster lock (IA_LOCK_3)
    then admits the weapon outright. Otherwise the unit's rank in the weapon's type must reach
    its requirement, and an autolevelled unit gets there for any type it holds a rank in
    (`UnitAutolevelWExp` raises it; a rank of 0 stays 0). A sealed weapon (IA_UNUSABLE) is
    never usable here: nothing we model unseals one."""
    attrs = item_attributes(item_enum)
    if 'IA_WEAPON' not in attrs:
        return False
    for n in (1, 2, 4, 5, 6, 7):
        if 'IA_LOCK_%d' % n in attrs and 'CA_LOCK_%d' % n not in attributes:
            return False
    if 'IA_LOCK_3' in attrs:
        return 'CA_LOCK_3' in attributes
    if 'IA_UNUSABLE' in attrs:
        return False
    block = _item_block(item_enum)
    kind = re.search(r'\.weaponType\s*=\s*(\w+)', block)
    need = re.search(r'\.weaponRank\s*=\s*(\w+)', block)
    have = unit_ranks(class_enum, char_block).get(kind.group(1) if kind else '', 0)
    need = _wexp(need.group(1)) if need else 0
    return have >= need or (autolevel and have > 0)


def _field(block, name):
    m = re.search(r'\.%s\s*=\s*(-?(?:0x[0-9a-fA-F]+|\d+))' % name, block)
    return int(m.group(1), 0) if m else 0


def class_line(class_enum):
    """(base, growths, caps, promoted) for a class, from vanilla data_classes.c."""
    b = _class_block(class_enum)
    base = {s: _field(b, 'base' + s) for s in STATS if s != 'Lck'}
    base['Lck'] = 0
    growths = {s: _field(b, 'growth' + s) for s in GROWN}
    caps = {s: _field(b, 'max' + s) for s in ('HP', 'Pow', 'Skl', 'Spd', 'Def', 'Res', 'Con')}
    caps['Lck'] = 30                                   # UnitCheckStatCaps: luck caps at 30
    return base, growths, caps, 'CA_PROMOTED' in b


def _increase_bounds(gn):
    """(min, max) of GetAutoleveledStatIncrease for growth*levels = gn."""
    if gn <= 0:
        return 0, 0
    lo_g = gn - gn // 8                                # NextRN_N(k) is 0..k-1
    hi_g = gn + max(gn // 4 - 1, 0) - gn // 8

    def rolled(g, best):
        if g <= 0:
            return 0
        whole = (g - 1) // 100                         # the `while (growth > 100)` loop
        rest = g - 100 * whole
        return whole + (1 if best or rest >= 100 else 0)   # Roll1RN(rest): sure only at 100
    return rolled(lo_g, False), rolled(hi_g, True)


def stat_increase(growth, rng):
    """`GetStatIncrease` (bmbattle.c), one draw: +1 per whole 100 of growth, then one `Roll1RN`
    on the rest (rng.c: `threshold > NextRN_100()`)."""
    result = 0
    while growth > 100:
        result += 1
        growth -= 100
    return result + (1 if growth > rng.randrange(100) else 0)


def autolevel_increase(gn, rng):
    """`GetAutoleveledStatIncrease` (bmbattle.c) for growth*levels = gn, one draw: gn jittered
    by NextRN_N(gn/4) - gn/8, then `stat_increase`. NextRN_N(k) is NextRN() * k / 0x10000."""
    jitter = rng.randrange(0x10000) * (gn // 4) // 0x10000 - gn // 8
    return stat_increase(gn + jitter, rng)


def _grow(line, growths, levels):
    if levels <= 0:
        return line
    out = dict(line)
    for s in GROWN:
        lo, hi = _increase_bounds(growths[s] * levels)
        out[s] = (line[s][0] + lo, line[s][1] + hi)
    return out


def growth_steps(level, autolevel=True, promoted=False, base_level=1, shift=0, mode='normal',
                 realistic=False):
    """The growth the engine gives one red unit at load, as [(levels, growths)] chunks applied
    in order to class + personal base, each rolled (and, in the parity model, rounded) on its
    own. `growths` is 'class' or 'personal'. The one description of the load path this module
    and difficulty.py both read (#490); the docstring above says where each branch lives.

    `shift` is the chapter's level shift for `mode`, 0 for a unit under the pid >= 0x3C gate.
    `realistic` marks an autolevelled CA_BOSS or pid < 0x40 (vanilla Ch13's Amelia and Cormag):
    it levels on its personal growths from `base_level`, and the penalty's re-autolevel still
    runs UnitAutolevel on class growths."""
    hard = mode == 'difficult'

    def auto(lv, hard):                                # UnitAutolevel
        return ([(19 if hard else 9, 'class')] if promoted else []) \
            + ([(lv - 1, 'class')] if lv > 1 else [])

    if not autolevel:
        steps = []
    elif realistic:
        steps = [(level - base_level, 'personal')] if level > base_level else []
    else:
        steps = auto(level, hard)
    if shift and hard:
        steps = steps + [(shift, 'class')]             # UnitAutolevelCore
    elif shift and level > base_level:                 # UnitAutolevelPenalty: from base again
        steps = auto(level - shift, False) if level - shift > base_level else []
    return steps


def _grow_personal(line, growths, levels):
    """`levels` real level-ups on personal growths (CheckBattleUnitLevelUp): one roll per stat,
    +1 per whole 100%."""
    out = dict(line)
    for s in GROWN:
        g = growths.get(s, 0)
        out[s] = (line[s][0] + levels * (g // 100), line[s][1] + levels * -(-g // 100))
    return out


def load(class_enum, level, personal=None, autolevel=True, base_level=1, shiftable=True,
         shifts=None, mode='normal', realistic=False, personal_growths=None):
    """{stat: (min, max)} for one red unit loaded in `mode`. `personal` is the character's
    base line (decomp `base*` names, or the YAML's short names); `personal_growths` its growths,
    read only on the realistic branch.

    What the ROM actually loads is read off the map by `INSPECT.redStats` (`ch04redstats`), one
    run per `PT_DIFFICULTY`: compare these ranges against it before trusting either."""
    base, growths, caps, promoted = class_line(class_enum)
    personal = _personal(personal)
    line = {s: (base[s] + personal.get(s, 0),) * 2 for s in STATS}
    shift = (shifts or {}).get(mode, 0) if shiftable else 0
    for levels, source in growth_steps(level, autolevel, promoted, base_level, shift, mode,
                                       realistic):
        if source == 'class':
            line = _grow(line, growths, levels)
        else:
            line = _grow_personal(line, _personal_growths(personal_growths), levels)
    return {s: (min(lo, caps[s]), min(hi, caps[s])) if s in caps else (lo, hi)
            for s, (lo, hi) in line.items()}


def _personal_growths(g):
    return {s: (g or {}).get('growth' + s, (g or {}).get(s, 0)) for s in GROWN}


_SHORT = {'hp': 'HP', 'pow': 'Pow', 'str': 'Pow', 'skl': 'Skl', 'spd': 'Spd', 'lck': 'Lck',
          'df': 'Def', 'def': 'Def', 'res': 'Res', 'con': 'Con'}


def _personal(personal):
    out = {}
    for k, v in (personal or {}).items():
        key = k[4:] if k.startswith('base') else _SHORT.get(k.lower())
        if key in STATS and isinstance(v, int):
            out[key] = v
    return out


def show(rng):
    """'22~24', or '22' when the range is one value."""
    lo, hi = rng
    return str(lo) if lo == hi else '%d~%d' % (lo, hi)
