#!/usr/bin/env python3
"""What the ROM loads a red unit with, per difficulty mode, as min~max ranges.

The parity model (difficulty.py) reads one mean-value line per unit. A wiki table shows what
the player will actually meet, so this transcribes the engine's load path instead, and keeps
its randomness as a range the way the Fire Emblem Wiki prints generic enemies ("22~24"):

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
data, and difficulty.py's mean-value model reads the same steps (#490), so the two agree.
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
    read only on the realistic branch."""
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
