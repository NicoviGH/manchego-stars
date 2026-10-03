#!/usr/bin/env python3
"""Per-chapter difficulty analyzer -- the STATIC arbiter of party-side parity.

Generalizes the original one-off Ch1 study into a reusable per-chapter tool: it resolves
our cast's effective stats (class base + donor personal
line, the donor-base inheritance of #45) and the chapter's enemy table, then measures
whether the field sits at vanilla FE8 parity on the three things that decide a Fire
Emblem map -- can we survive, can we kill, can we crack the boss.

    python3 tools/difficulty.py --chapter ch01

HONEST LIMITS: this is a *static* proxy. It assumes every matchup happens and ignores
positioning, turn order, terrain choice and healing; of the enemy AI it models only whom a
unit would attack (`ai_target`), not where it walks or when. It is a fast guardrail
against authoring a chapter that drifts off vanilla parity -- NOT a substitute for the
dynamic playtest harness (tools/playtest/), which is the real arbiter.

All combat math is fe_combat.py (the decomp's own formulas, tested). Stat resolution
shares build_campaign.py's primitives so there is one source of truth for "what is this
unit's stat line".
"""
import collections
import dataclasses
import functools
import os
import random
import re

import chapter_schema  # noqa: E402
import inject.cast  # noqa: E402
import inject.chapter_settings  # noqa: E402
import inject.decomp  # noqa: E402
import inject.hosting  # noqa: E402
import inject.hosts  # noqa: E402
import inject.paths  # noqa: E402
import inject.raw_pids  # noqa: E402
import inject.stats  # noqa: E402
import argparse
import json
import sys
import ai_target
import fe_combat as fc
from inject.decomp import WEAPON_ITEM_ENUM   # shared weapon<->ITEM map (seam-neutral)

# Class -> effectiveness tag a unit carries as a DEFENDER (so enemy effective weapons
# and our rapier resolve). Only the classes our cast/enemies use need entries.
CLASS_TAGS = {
    'CLASS_ARMOR_KNIGHT': frozenset({'armor'}),
    'CLASS_GENERAL': frozenset({'armor'}),
    'CLASS_GREAT_KNIGHT': frozenset({'armor', 'cav'}),
    'CLASS_CAVALIER': frozenset({'cav'}),
    'CLASS_PALADIN': frozenset({'cav'}),
    'CLASS_PEGASUS_KNIGHT': frozenset({'flier'}),
    'CLASS_FALCON_KNIGHT': frozenset({'flier'}),
    'CLASS_WYVERN_RIDER': frozenset({'flier'}),
}

# The engine models VANILLA, so every decomp read is the committed (HEAD) source, never
# the working tree the build mutates (donor portrait slots + reskinned classes). Cached.
_vanilla_chars = None
_vanilla_classes = None


def _characters_text():
    global _vanilla_chars
    if _vanilla_chars is None:
        _vanilla_chars = inject.decomp.vanilla_decomp_text('src/data_characters.c')
    return _vanilla_chars


def _classes_text():
    global _vanilla_classes
    if _vanilla_classes is None:
        _vanilla_classes = inject.decomp.vanilla_decomp_text('src/data_classes.c')
    return _vanilla_classes


def _class_base(class_enum):
    return inject.stats.class_base_stats(class_enum, _classes_text())


def _class_growths(class_enum):
    """Read a class's growth rates (for autoleveling enemies) from vanilla data_classes.c."""
    text = _classes_text()
    s, e = inject.decomp._find_brace_block(text, '[%s - 1]' % class_enum, inject.paths.CLASSES_C)
    block = text[s:e]
    out = {}
    for gf in inject.stats.GROWTH_FIELDS:
        m = re.search(r'\.' + gf + r'\s*=\s*(-?\d+)', block)
        out[gf] = int(m.group(1)) if m else 0
    return out


def autolevel(base, growths, level):
    """Project class-base stats up `level` (FE generic-enemy autolevel on class growths,
    UnitAutolevelCore, bmunit.c:776-786, applied with level-1 by UnitAutolevel). Per
    stat: base + round-half-up((level-1) * growth%). Con/Mov don't grow."""
    out = dict(base)
    gains = level - 1
    for gf in inject.stats.GROWTH_FIELDS:
        field = 'base' + gf[len('growth'):]      # growthHP -> baseHP
        out[field] = base.get(field, 0) + int(gains * growths.get(gf, 0) / 100 + 0.5)
    return out


MODES = ('tutorial', 'normal', 'difficult')


def mode_stats(base, growths, level, mode, shifts, base_level=1):
    """`base` autoleveled to `level`, then shifted by a chapter's difficulty `shifts`
    for `mode` -- the engine's own difficulty mechanism, modeled (#303).

    FE8 does not author three enemy tables. It authors ONE, stores three per-chapter
    numbers, and re-projects stats at unit-load time: `UnitApplyBonusLevels`
    (bmunit.c) dispatches to `UnitAutolevelCore` for the Difficult bonus and to
    `UnitAutolevelPenalty` for the Tutorial/Normal malus. `shifts` is that triple,
    keyed by MODES -- {'tutorial': easyModeLevelMalus, 'normal': normalModeLevelMalus,
    'difficult': difficultModeLevelBonus} (chapterdata.h:47-49, each a 4-BIT field, so
    0..15). NB the field FE8 calls "easy" is the Tutorial slot: menu option 0 sets
    controller=0/HARD=0, which is both the `-easyModeLevelMalus` branch
    (eventscr.c:2328) and the only state where CHECK_TUTORIAL fires.

    Two engine details a naive `level - malus` gets wrong:

      * the penalty FLOORS. `UnitAutolevelPenalty` re-derives stats from base and
        re-autolevels only `if (level - malus > baseLevel)`, and does nothing at all
        unless `level > baseLevel` -- so a shifted unit never reads below pure class
        base. Every generic and boss pid we field has baseLevel 1 (data_characters.c).
      * the bonus rounds TWICE. Difficult is `inc(level-1)` then `inc(bonus)` as two
        separate roundings, not one rounding of `inc(level-1+bonus)`.

    This is a mean-value proxy, as the rest of the model is: the engine's real
    `GetAutoleveledStatIncrease` jitters by +/-(growth*n)/8 and resolves the remainder
    with a coin flip (`GetStatIncrease`, bmbattle.c:1241), so a single unit's stats are
    a random variable. Both sides of a parity read go through this same function, so
    the comparison stays apples-to-apples.
    """
    if mode not in MODES:
        raise ValueError('unknown difficulty mode %r (want one of %s)'
                         % (mode, ', '.join(MODES)))
    shift = shifts[mode]
    projected = autolevel(base, growths, level)
    if not shift:
        return projected
    if mode == 'difficult':
        out = dict(projected)
        for gf in inject.stats.GROWTH_FIELDS:
            field = 'base' + gf[len('growth'):]
            out[field] = projected[field] + int(shift * growths.get(gf, 0) / 100 + 0.5)
        return out
    if level <= base_level:                  # `level > baseLevel` gate: no penalty at all
        return projected
    target = level - shift
    if target > base_level:
        return autolevel(base, growths, target)
    return dict(base)                        # re-derived from base, re-autolevel skipped


def _weapon_for(inventory):
    """First inventory entry that resolves (via fe_base, else id) to a real attacking
    weapon usable in the modeled (base-class) state. Staves/consumables aren't in
    fe_combat.W, so they're skipped; items with an `unlock` precondition (e.g. a base
    Priest's promotion-gated Light tomes) are skipped too -- so a staff-only healer
    resolves to None, the support path, instead of leaking promoted kit into base offense
    or crashing (#62). The YAML's own `unlock` flag is the data-driven gate."""
    for item in inventory or []:
        if item.get('unlock'):                    # not yet usable at base class
            continue
        key = item.get('fe_base') or item.get('id')
        if key in fc.W:
            return fc.W[key]
    return None


def _stats_to_combatant(name, stats, weapon, tags=frozenset()):
    return fc.Combatant(name, hp=stats['baseHP'], pow=stats['basePow'],
                        skl=stats['baseSkl'], spd=stats['baseSpd'], df=stats['baseDef'],
                        res=stats['baseRes'], lck=stats.get('baseLck', 0),
                        con=stats['baseCon'], weapon=weapon, tags=tags)


def _class_caps(class_enum):
    """A PLAYER unit's stat ceilings in `class_enum` (`CheckBattleUnitStatCaps`, bmbattle.c,
    through bmunit.h's UNIT_*_MAX): the class's own max for Pow/Skl/Spd/Def/Res, and the two
    fixed ones -- 60 HP for a non-red unit, 30 Lck for everyone."""
    text = _classes_text()
    s, e = inject.decomp._find_brace_block(text, '[%s - 1]' % class_enum, inject.paths.CLASSES_C)
    block = text[s:e]
    caps = {'baseHP': 60, 'baseLck': 30}
    for field in ('Pow', 'Skl', 'Spd', 'Def', 'Res'):
        m = re.search(r'\.max' + field + r'\s*=\s*(\d+)', block)
        if m:
            caps['base' + field] = int(m.group(1))
    return caps


_STAT_ORDER = ('HP', 'Pow', 'Skl', 'Spd', 'Def', 'Res', 'Lck')   # the order FE8 rolls them in


def _stat_increase(growth, rng):
    """`GetStatIncrease` (bmbattle.c): +1 per whole 100 of growth, then one `Roll1RN` on the
    rest (rng.c: `threshold > NextRN_100()`)."""
    result = 0
    while growth > 100:
        result += 1
        growth -= 100
    return result + (1 if growth > rng.randrange(100) else 0)


def level_up(growths, rng):
    """One player level-up's stat gains, transcribed from `CheckBattleUnitLevelUp`
    (bmbattle.c). Every stat rolls once; an EMPTY level then re-rolls up to twice, walking the
    stats in order and stopping at the first that gains. That re-roll couples the stats, which
    is why `grown` simulates rather than reading each stat off a binomial."""
    gains = {f: _stat_increase(growths.get('growth' + f, 0), rng) for f in _STAT_ORDER}
    if not any(gains.values()):
        for _ in range(2):
            for f in _STAT_ORDER:
                gains[f] = _stat_increase(growths.get('growth' + f, 0), rng)
                if gains[f]:
                    return gains
    return gains


GROWTH_TRIALS = 1001        # odd, so a median is one career's value and never a midpoint
GROWTH_SEED = 430           # fixed: the report is a reading, and it reads the same every run


@functools.lru_cache(maxsize=None)
def _careers_cached(stats, growths, gained, caps):
    stats, growths, caps = dict(stats), dict(growths), dict(caps)
    rng = random.Random(GROWTH_SEED)
    rows = []
    for _ in range(GROWTH_TRIALS):
        line = {f: stats.get('base' + f, 0) for f in _STAT_ORDER}
        for _ in range(gained):
            for f, up in level_up(growths, rng).items():
                cap = caps.get('base' + f)
                line[f] = min(line[f] + up, cap) if cap is not None else line[f] + up
        rows.append(tuple(line[f] for f in _STAT_ORDER))
    return tuple(rows)


def careers(stats, growths, gained, caps):
    """`stats` after `gained` player level-ups, once per simulated career: GROWTH_TRIALS stat
    lines of the engine's own level-up (`level_up`), held to `caps` after every level as
    `CheckBattleUnitStatCaps` holds them. A unit that has not levelled has one career, its own
    line. These are the dice the absolute metrics are averaged over (`dice_profile`)."""
    if gained <= 0:
        return [dict(stats)]
    rows = _careers_cached(tuple(sorted(stats.items())), tuple(sorted(growths.items())),
                           int(gained), tuple(sorted(caps.items())))
    return [dict(stats, **{'base' + f: v for f, v in zip(_STAT_ORDER, row)}) for row in rows]


def _median_line(lines):
    out = dict(lines[0])
    for f in _STAT_ORDER:
        out['base' + f] = sorted(line.get('base' + f, 0) for line in lines)[len(lines) // 2]
    return out


def grown(stats, growths, gained, caps):
    """`stats` after `gained` player level-ups: each stat's MEDIAN over the simulated
    `careers`.

    The median rather than the mean, at Nicolas's suggestion (2026-10-01): a rounded mean is
    not a value the dice land on most, and it differs from the median by a point in about one
    stat line in seven (an 80% HP growth over three levels is +2 rounded, +3 median). It is a
    per-stat median, so the line is a planning number and not one unit anybody will roll; the
    report's absolute metrics are averaged over the careers instead (ADR 0311)."""
    return _median_line(careers(stats, growths, gained, caps))


def placed_entry(campaign, uid, unit, recruited):
    """The roster entry that PLACES `uid` in its recruit chapter, or None.

    The ROM builds a placed recruit from that entry's UnitDefinition -- its level and its
    items -- so wherever the entry speaks, it outranks the unit YAML (sahnar is placed RED at
    Joshua's level with his Killing Edge). `recruited` is the recruit chapter number, or None
    for a founding unit."""
    if recruited is None:
        return None
    chapter = next((c for c in inject.hosts.hosted_chapters() if c.number == int(recruited)),
                   None)
    if chapter is None:
        return None
    chap = inject.hosting._load_chapter_yaml(campaign,
                                             inject.hosting.chapter_yaml_for(chapter.name))
    return next((ed for ed in inject.raw_pids.placed_entries(chap) if ed.get('id') == uid),
                None)


def _player_weapon(campaign, uid, unit, class_enum):
    """The weapon a cast member actually fights with, read where the ROM reads it.

    The unit YAML's `inventory:` where it has one. A recruit without one is armed by the ROM
    elsewhere: a placed recruit by its placing entry, an off-map join by the join-LOAD's
    `CLASS_LOADOUT` kit (ch05's join-LOAD, `inject.cast`). Reading only the YAML scored lupin
    and sahnar as weaponless -- 0 kills/round for a Cavalier and a sword duelist."""
    if unit.get('inventory'):
        return _weapon_for(unit['inventory'])
    entry = placed_entry(campaign, uid, unit,
                         inject.hosting.recruit_chapter_number(campaign, unit))
    if entry and entry.get('inventory'):
        return _weapon_for(entry['inventory'])
    return _weapon_from_item_enums(inject.cast.CLASS_LOADOUT.get(class_enum, ()))


def _player_lines(campaign, uid, gained):
    """(career stat lines, weapon, tags) for a cast member `gained` levels above its join
    level: class base + donor personal base (donor-base inheritance), grown on its growth
    donor's growths."""
    unit = inject.cast.load_unit(campaign, uid)
    unit.setdefault('id', uid)
    class_enum = inject.cast.class_enum_for(unit)
    cbase = _class_base(class_enum)
    dbase = inject.stats.donor_base_stats(_characters_text(), inject.stats.BASE_DONOR[uid])
    eff = {f: cbase.get(f, 0) + dbase.get(f, 0) for f in inject.stats.BASE_FIELDS}
    lines = [eff]
    if gained:
        growths, _ = inject.stats.donor_growths_and_ranks(
            _characters_text(), inject.stats.GROWTH_DONOR[uid])
        lines = careers(eff, growths, gained, _class_caps(class_enum))
    weapon = _player_weapon(campaign, uid, unit, class_enum)
    return lines, weapon, CLASS_TAGS.get(class_enum, frozenset())


def player_combatant(campaign, uid, gained=0):
    """Resolve a cast member's effective fe_combat.Combatant: class base + donor personal
    base (donor-base inheritance), wielding its first real weapon.

    `gained` is how many levels the unit has risen above the one it joined at, grown on its
    growth donor's growths (`grown`: the median of simulated level-ups). 0 is the join-level line, which is what the injector
    sizes ch01's lord floor from; `load_field(leveled=True)` passes the exp model's answer
    (#430 step 1)."""
    lines, weapon, tags = _player_lines(campaign, uid, gained)
    return _stats_to_combatant(uid, _median_line(lines), weapon, tags)


def player_careers(campaign, uid, gained=0):
    """`player_combatant`, once per simulated career (`careers`)."""
    lines, weapon, tags = _player_lines(campaign, uid, gained)
    return [_stats_to_combatant(uid, line, weapon, tags) for line in lines]


def _enemy_class_enum(token):
    """'armor-knight' -> 'CLASS_ARMOR_KNIGHT'."""
    return 'CLASS_' + str(token).upper().replace('-', '_')


# A named boss is NOT just its class: FE8 layers a personal stat line on top (Saar is an
# Armor Knight *plus* HP+13/Pow+6/Skl+5/Spd+3/Def+2/Res+3/Lck+4 -- that line is most of why a
# boss reads as a wall). This used to be skipped on both sides, which kept the comparison
# honest but understated every boss; now it is modeled on BOTH sides, so `personal` on one of
# our units is measured against the vanilla boss's real line rather than its naked class.
_PERSONAL_FIELDS = (('baseHP', 'hp'), ('basePow', 'pow'), ('baseSkl', 'skl'),
                    ('baseSpd', 'spd'), ('baseDef', 'df'), ('baseRes', 'res'),
                    ('baseLck', 'lck'), ('baseCon', 'con'))


def vanilla_personal_line(char_enum):
    """The personal base stats a named vanilla character carries on top of its class.
    {} for generics (a numeric charIndex token) or an unknown name."""
    if not char_enum or not str(char_enum).startswith('CHARACTER_'):
        return {}
    try:
        return inject.stats.donor_base_stats(_characters_text(), char_enum)
    except Exception:
        return {}


def _apply_personal(combatant, personal):
    """Fold a personal stat line (decomp `base*` names, or our YAML's short names) into a
    Combatant. Missing/zero fields are no-ops, so a generic is untouched."""
    if not personal:
        return combatant
    delta = {}
    for decomp_name, field in _PERSONAL_FIELDS:
        v = personal.get(decomp_name) or personal.get(field) or 0
        if v:
            delta[field] = getattr(combatant, field) + int(v)
    return dataclasses.replace(combatant, **delta) if delta else combatant


DIFFICULTY_SHIFT_MIN_PID = 0x3C   # eventscr.c:2328 -- see _takes_difficulty_shift
_char_numbers = None


def _character_number(token):
    """A `.charIndex` token -> its numeric character slot. Handles both spellings the
    UnitDefinition arrays use: a CHARACTER_* enum (named cast and bosses) and a bare
    numeric literal (the generic autolevelled-trash pids). None if unresolvable."""
    global _char_numbers
    if _char_numbers is None:
        text = inject.decomp.vanilla_decomp_text('include/constants/characters.h')
        _char_numbers = {m.group(1): int(m.group(2), 0) for m in re.finditer(
            r'(CHARACTER_\w+)\s*=\s*(0x[0-9A-Fa-f]+|\d+)', text)}
    if token in _char_numbers:
        return _char_numbers[token]
    try:
        return int(str(token), 0)
    except (TypeError, ValueError):
        return None


def _takes_difficulty_shift(char_index):
    """Does the engine apply a difficulty shift to a RED unit on this character slot?

    `if (def->allegiance == FACTION_ID_RED && unit->pCharacterData->number >= 0x3C)`
    (eventscr.c:2328). Slots below 0x3C are the playable cast and their summons, so a
    unit deployed hostile on a PLAYABLE slot is difficulty-immune -- vanilla Ch5's
    pre-recruit Joshua (0x20) is exactly that, and so is our Sahnar, who rides Joshua's
    own slot. Both sides of the Ch5 read therefore carry one unshifted unit."""
    if char_index is None:
        return False                       # absent field reads 0, which is below the gate
    number = _character_number(char_index)
    return number is None or number >= DIFFICULTY_SHIFT_MIN_PID


def _character_base_level(char_index):
    """`pCharacterData->baseLevel` for a charIndex token, or 1 when it has none.

    This is the field that decides whether the difficulty MALUS touches a unit at all
    (`if (level > baseLevel)`, UnitAutolevelPenalty). Vanilla sets it >= the deploy level
    on every named boss, which is how a hand-authored boss line survives into Tutorial and
    Normal unchanged; generics carry 1 and are re-projected normally."""
    if char_index is None:
        return 1
    text = _characters_text()
    for marker in ('[%s - 1]' % char_index, '[%s - 1]' % str(char_index).lower()):
        try:
            start, end = inject.decomp._find_brace_block(text, marker, inject.paths.CHARACTERS_C)
        except SystemExit:
            continue
        found = re.search(r'\.baseLevel\s*=\s*(-?\d+)', text[start:end])
        return int(found.group(1)) if found else 1
    return 1


def _enemy_from_enum(name, class_enum, level, weapon, personal=None,
                     mode=None, shifts=None, shiftable=True, base_level=1):
    """One Combatant: class base autoleveled to `level`, wielding `weapon`, plus any
    personal boss line (see above). Generics carry no personal line, so they are unchanged.

    With `mode` and `shifts` both given the class projection runs through `mode_stats`
    instead, so the unit reads as the engine would load it in that difficulty mode.
    `shiftable=False` models the `>= 0x3C` gate. The personal line stays a flat delta
    applied afterwards, which is faithful either way: the engine's penalty re-derives
    from charBase+classBase and its bonus adds onto them, and both compose additively."""
    base, growths = _class_base(class_enum), _class_growths(class_enum)
    if mode and shifts and shiftable:
        stats = mode_stats(base, growths, int(level), mode, shifts, base_level=base_level)
    else:
        stats = autolevel(base, growths, int(level))
    c = _stats_to_combatant(name, stats, weapon, CLASS_TAGS.get(class_enum, frozenset()))
    return _apply_personal(c, personal)


def _one_enemy(name, class_token, level, weapon, personal=None, mode=None, shifts=None,
               base_level=1, shiftable=True):
    return _enemy_from_enum(name, _enemy_class_enum(class_token), level, weapon, personal,
                            mode=mode, shifts=shifts, base_level=base_level,
                            shiftable=shiftable)


# "What bodies does this entry place" is chapter-SCHEMA knowledge, so it lives beside the
# roster keys on build_campaign's desk -- the ROM emitters, the raw-pid registry and every
# metric here have to agree on it, and they did not (decisions.md -> "A parity ratio does not
# say how much of the twin it COPIED").
_body_levels = inject.raw_pids.entry_body_levels


def _entry_body_count(enemy_def):
    """How many BODIES one entry places -- one per declared level, and `composition` is a
    bag of generics whose length IS that count."""
    return len(_body_levels(enemy_def))


def enemy_combatants(enemy_def, mode=None, shifts=None, base_level=1, shiftable=True):
    """One representative Combatant per DISTINCT enemy type in a chapter enemy_units entry
    (its `count`/positions are tactical detail the metrics don't model). Class base
    autoleveled to the entry's `level`. Handles both a single `class` and a mixed
    `composition` (with per-class weapons in `inventory_by_class`)."""
    level = enemy_def.get('level', 1)
    name = enemy_def.get('id', enemy_def.get('name', 'enemy'))
    # NB `personal:` is intentionally NOT applied here -- the aggregate stays class-base on
    # both sides (see vanilla_enemies). role_findings() applies it for the boss comparison.
    if 'class' in enemy_def:
        return [_one_enemy(name, enemy_def['class'], level,
                           _weapon_for(enemy_def.get('inventory')),
                           mode=mode, shifts=shifts, base_level=base_level,
                           shiftable=shiftable)]
    by_class = enemy_def.get('inventory_by_class', {})
    out = []
    for cls in dict.fromkeys(enemy_def.get('composition', [])):   # distinct, order-stable
        weapon = _weapon_for([{'id': w} for w in by_class.get(cls, [])])
        out.append(_one_enemy('%s-%s' % (name, cls), cls, level, weapon,
                              mode=mode, shifts=shifts, base_level=base_level,
                              shiftable=shiftable))
    return out


# ── Vanilla enemy extraction (the #48 parity reference force) ─────────────────────
# A chapter's `parity_reference` (e.g. "FE8 Ch1") names the vanilla chapter whose enemy
# pressure sets its bar. We resolve that to the decomp UnitDefinition array(s) holding the
# fightable red force and project each enemy off class base -- the same footing as ours.

# decomp item enum -> fe_combat weapon key. The inverse of build_campaign's canonical
# weapon->ITEM map (one source for both directions). Only attacking weapons are listed there;
# staves/consumables/keys are absent on purpose (an enemy carrying only those resolves to no
# modeled weapon and is skipped -- with a warning, see unmodeled_enemies).
# Vanilla-only (monster/exotic) weapons that ONLY the parity-reference forces carry -- our
# cast never authors these, so they stay out of the content-owned WEAPON_ITEM_ENUM (#53,
# HANDOFF "Watch out") and live here, merged into the reverse map below.
VANILLA_ONLY_ITEM_TO_WEAPON = {
    'ITEM_ANIMA_THUNDER':     'thunder',
    'ITEM_ANIMA_ELFIRE':      'elfire',       # Ch13 Pablo (plain vanilla stats; the #8
                                              # effectiveness experiment stays reverted)
    'ITEM_LANCE_STEEL':       'steel-lance',
    'ITEM_LANCE_SLIM':        'slim-lance',
    'ITEM_LANCE_SHORTSPEAR':  'short-spear',
    'ITEM_BOW_STEEL':         'steel-bow',
    'ITEM_SWORD_ZANBATO':     'zanbato',
    'ITEM_BLADE_IRON':        'iron-blade',
    'ITEM_AXE_VENIN':         'venin-axe',
    'ITEM_AXE_HALBERD':       'halberd',
    'ITEM_LANCE_HORSESLAYER': 'horseslayer',
    'ITEM_MONSTER_FETIDCLW':  'fetid-claw',
    'ITEM_MONSTER_ROTTENCLW': 'rotten-claw',
    'ITEM_MONSTER_VENINCLW':  'venin-claw',
    'ITEM_MONSTER_FIREFANG':  'fire-fang',
    'ITEM_MONSTER_HELLFANG':  'hell-fang',
    'ITEM_MONSTER_EVILEYE':   'evil-eye',
    # Carried by the vanilla PARTY (`vanilla_party`): Ross joins with a Hatchet, Artur with
    # Lightning. Without them both read as weaponless support.
    'ITEM_AXE_HATCHET':       'hatchet',
    'ITEM_LIGHT_LIGHTNING':   'lightning',
}
ITEM_TO_WEAPON = {item: key for key, item in WEAPON_ITEM_ENUM.items()}
ITEM_TO_WEAPON.update(VANILLA_ONLY_ITEM_TO_WEAPON)

# parity_reference -> (decomp relpath, [UnitDefinition array names]) for its red force.
# The single curation point: which vanilla arrays ARE a chapter's fightable enemies (named
# *Enemy arrays for the decompiled-to-C early chapters; cutscene/throne-room/skirmish arrays
# are deliberately excluded). Extend as later references are curated (#48).
PARITY_REFERENCE_UDEFS = {
    'FE8 Prologue': ('src/events/prologue-eventudefs.h',
                     ['UnitDef_Event_PrologueEnemy']),
    'FE8 Ch1': ('src/events/ch1-eventudefs.h',
                ['UnitDef_Event_Ch1Enemy', 'UnitDef_Event_Ch1EnemyReinforce']),
    # Ch2+ enemies live in the monolithic events_udefs.c with address-named arrays. The
    # right ones are those a chapter's eventscript references AND whose RED units carry
    # weapons -- which excludes the interleaved skirmish/tower data (not referenced) and the
    # cutscene/preview arrays (villains placed with empty .items). Method per chapter:
    # `grep UnitDef_ src/events/chN-eventscript.h`, keep arrays with armed FACTION_ID_RED
    # entries. Verified all-modeled: Ch2=9, Ch3=10, Ch5=23 enemies.
    'FE8 Ch2': ('src/events_udefs.c',
                ['UnitDef_088B4344', 'UnitDef_088B4470', 'UnitDef_088B44AC']),
    'FE8 Ch3': ('src/events_udefs.c', ['UnitDef_088B463C']),
    'FE8 Ch5': ('src/events_udefs.c',
                ['UnitDef_088B5798', 'UnitDef_088B56F8', 'UnitDef_088B5860',
                 'UnitDef_088B589C', 'UnitDef_088B58D8', 'UnitDef_088B5914']),
    # Ch4 "Ancient Horrors" -- all-monster force (#53). The three ch4-eventscript.h arrays whose
    # RED units are armed; the rest are green/NPC/cutscene placements (red=0). Needs the monster
    # claws + Evil Eye modeled (Bonewalker/Revenant carry iron-sword/iron-lance too).
    'FE8 Ch4': ('src/events_udefs.c',
                ['UnitDef_088B4A80', 'UnitDef_088B4C24', 'UnitDef_088B4C88']),
    # Ch6 "Victims of War" -- mixed force (#53). The two armed-RED arrays ch6 references; needs
    # thunder/halberd/venin-axe/iron-blade/horseslayer + the venin-claw Bael. Staff-only healers
    # in the main array carry no weapon and are dropped by design (not an unmodeled-weapon drop).
    # Ch13 "Hamill Canyon" (Eirika route; our ch08's bar, #123). The 11 armed-RED arrays
    # ch13a-eventscript.h loads: Aias's boss squad + the 20-unit main force + Pablo's
    # reinforcement wave + cavalry/merc/wyvern packs + Amelia (armed red recruit; she
    # fights if unrecruited). Excluded: the unarmed cutscene loads (Cormag/Caellach/
    # Aias-L9 scene arrays) per the registry rule; 2 staff-only healers drop as intended.
    'FE8 Ch13': ('src/events_udefs.c',
                 ['UnitDef_088BAA4C', 'UnitDef_088BAA74', 'UnitDef_088BAC18',
                  'UnitDef_088BACA4', 'UnitDef_088BAD80', 'UnitDef_088BADBC',
                  'UnitDef_088BADF8', 'UnitDef_088BAE48', 'UnitDef_088BAE84',
                  'UnitDef_088BAEC0', 'UnitDef_088BAF10']),
    'FE8 Ch6': ('src/events_udefs.c',
                ['UnitDef_088B61A8', 'UnitDef_088B64F0']),
}

# The decomp's own AI vector macros, read from the header the decomp COMPILES
# (include/EA_Standard_Library/AI_Helpers.h, pulled in by events_udefs.c through EAstdlib.h
# -- which is why vanilla's unit data reads `.ai = {AttackInRangeAI, 0x0, 0x0}`). Parsed
# rather than copied: a local table would be a second source of truth for the exact bytes
# #335 exists to keep faithful, and the copy that drifts is always the one nobody reads.
AI_HELPERS_H = 'include/EA_Standard_Library/AI_Helpers.h'


def _ai_macros():
    """`{macro name: (byte, ...)}` from the decomp's AI helper header.

    Only the multi-byte AI-vector macros and the single-byte field constants matter here;
    both are plain `#define NAME 0x..[,0x..]` lines, so one regex covers them."""
    out = {}
    for line in inject.decomp.vanilla_decomp_text(AI_HELPERS_H).splitlines():
        m = re.match(r'\s*#define\s+(\w+)\s+((?:0x[0-9A-Fa-f]+)(?:\s*,\s*0x[0-9A-Fa-f]+)*)\s*$',
                     line)
        if m:
            out[m.group(1)] = tuple(int(t, 16) for t in m.group(2).split(','))
    return out


AI_MACROS = _ai_macros()


def ai_bytes(spec):
    """An AI vector as vanilla writes it -> its 4 engine bytes.

    `spec` is the text between the braces (with or without them), or None. A UnitDefinition
    with NO `.ai` block is {0,0,0,0} -- ActionInRange + MoveToEnemy, i.e. a PURSUER, not an
    inert default; two of vanilla Ch6's red force are exactly that, and reading them as
    static would invert a chapter's shape. Short vectors zero-fill as the C initialiser does."""
    if not spec:
        return (0x00, 0x00, 0x00, 0x00)
    out = []
    for token in (t.strip() for t in spec.strip().strip('{}').split(',')):
        if not token:
            continue
        out.extend(AI_MACROS[token] if token in AI_MACROS else (int(token, 0),))
    return tuple((out + [0, 0, 0, 0])[:4])


# parity_reference -> (decomp relpath, [UnitDefinition arrays]) for its vanilla GREEN units
# (#335). Greens are the units a "protect" chapter is ABOUT, and their AI is a design decision
# as much as an enemy's -- vanilla Ch2 gives Garcia {AttackInRangeAI, 0, 0} (hold the tile and
# strike what reaches him) and Ross the scripted-approach AI_B_0A. Curated as references need
# them, like the red and ally registries above.
PARITY_REFERENCE_GREEN_UDEFS = {
    'FE8 Ch2': ('src/events_udefs.c', ['UnitDef_088B4434']),   # Ross + Garcia
}


def _udef_registry(allegiance):
    return {'RED': PARITY_REFERENCE_UDEFS,
            'GREEN': PARITY_REFERENCE_GREEN_UDEFS}[allegiance]


def _brace_entries(body):
    """Yield each top-level `{...}` group's inner text from an array body, tracking brace
    depth so a unit's nested `.items = {...}` / `.ai = {...}` don't split it early."""
    depth, start = 0, None
    for i, ch in enumerate(body):
        if ch == '{':
            if depth == 0:
                start = i + 1
            depth += 1
        elif ch == '}':
            depth -= 1
            if depth == 0:
                yield body[start:i]


@functools.lru_cache(maxsize=None)
def vanilla_redas(text):
    """`{REDA symbol: [(x, y), ...]}` for every REDA array in a decomp source.

    REDA is the scripted movement a unit walks when it loads. It matters here because a
    UnitDefinition's `xPosition`/`yPosition` is frequently a SPAWN tile rather than a battle
    post: vanilla Ch1's entire force enters on (1,9)/(2,9) and Ch5's on (0,0)/(10,0)/(12,0).
    The last point is where the unit actually ends up.

    MEMOISED on the source text: `vanilla_unit_defs` needs this for every UnitDefinition
    array it parses, and re-ran the whole-file `re.finditer` each time -- 5,507 scans of the
    same 1.78 MB `events_udefs.c` in one `test_difficulty.py` run, 27.4s of pure CPU for an
    answer that never changed. Keying on the text is O(1) in practice because
    `inject.decomp.vanilla_decomp_text` is memoised too and hands back the same str object, whose hash
    Python caches after the first call (#380). The returned dict is shared, so callers must
    not mutate it."""
    return {m.group(1): [(int(x), int(y)) for x, y in
                         re.findall(r'\.x = (\d+),\s*\.y = (\d+)', m.group(2))]
            for m in re.finditer(
                r'CONST_DATA struct REDA (REDA_\w+)\[\] = \{(.*?)\n\};', text, re.S)}


def vanilla_unit_defs(text, array_name):
    """Parse `CONST_DATA struct UnitDefinition <array_name>[] = { ... };` from decomp text
    into a list of per-entry dicts (charIndex, classIndex, level, allegiance, itemDrop, items).
    The trailing `{ 0 }` terminator (no .classIndex) is skipped. `charIndex` is the named
    character enum for allies/bosses (a numeric token for generics, None if absent). `itemDrop`
    is the `.itemDrop = 1` bit -- when set, the unit drops its LAST item on death (US_DROP_ITEM,
    statscreen.c:726), the enemy-drop channel the economy reads (#176)."""
    s, e = inject.decomp._find_brace_block(text, array_name + '[]', '<udef:%s>' % array_name)
    body = text[s + 1:e - 1]
    redas = vanilla_redas(text)
    out = []
    for block in _brace_entries(body):           # top-level { ... } per unit (handles
        cls = re.search(r'\.classIndex\s*=\s*(\w+)', block)   # nested .items/.ai braces
        if not cls:                              # the { 0 } terminator
            continue
        chi = re.search(r'\.charIndex\s*=\s*(\w+)', block)
        lvl = re.search(r'\.level\s*=\s*(\d+)', block)
        alg = re.search(r'\.allegiance\s*=\s*(\w+)', block)
        items = re.search(r'\.items\s*=\s*\{(.*?)\}', block, re.S)
        ai = re.search(r'\.ai\s*=\s*\{(.*?)\}', block, re.S)
        xpos = re.search(r'\.xPosition\s*=\s*(\d+)', block)
        ypos = re.search(r'\.yPosition\s*=\s*(\d+)', block)
        reda = re.search(r'\.redas\s*=\s*(REDA_\w+)', block)
        placed = (int(xpos.group(1)) if xpos else None,
                  int(ypos.group(1)) if ypos else None)
        walked = redas.get(reda.group(1)) if (reda and redas) else None
        out.append({
            'ai': ai_bytes(ai.group(1) if ai else None),
            'redas': reda.group(1) if reda else None,
            # Where the unit FIGHTS: the end of its REDA walk, or its placed tile when it
            # does not walk. Donors match on this, never on the spawn tile (#335).
            'position': walked[-1] if walked else placed,
            'xPosition': placed[0],
            'yPosition': placed[1],
            'charIndex': chi.group(1) if chi else None,
            'classIndex': cls.group(1),
            'level': int(lvl.group(1)) if lvl else 1,
            'allegiance': alg.group(1) if alg else None,
            'itemDrop': bool(re.search(r'\.itemDrop\s*=\s*1', block)),
            'items': [t.strip() for t in items.group(1).split(',') if t.strip()]
                     if items else [],
        })
    return out


def vanilla_units(parity_ref, allegiance='RED'):
    """Every UnitDefinition of one allegiance in the twin, parsed. None if uncurated.

    RED by default because that is the force the difficulty math grades. GREEN matters for
    donors: our protected units have vanilla counterparts too (ch02's chwinga stand in for
    Ross and Garcia), and their AI is as much a design decision as an enemy's."""
    spec = _udef_registry(allegiance).get(parity_ref)
    if spec is None:
        return None
    relpath, arrays = spec
    text = inject.decomp.vanilla_decomp_text(relpath)
    want = 'FACTION_ID_%s' % allegiance
    return [d for array_name in arrays
            for d in vanilla_unit_defs(text, array_name)
            if d['allegiance'] == want]


def vanilla_red_units(parity_ref):
    """Every RED UnitDefinition in the twin, parsed. None if the reference isn't curated.

    Unlike vanilla_enemies(), nothing is dropped for carrying no modeled weapon: a
    staff-only healer contributes nothing to the threat math and everything to the map's
    shape -- vanilla Ch6 gives its Troubadour the same delayed charge as the cavalry she
    rides with, and a chapter borrowing her AI needs to find her."""
    spec = PARITY_REFERENCE_UDEFS.get(parity_ref)
    if spec is None:
        return None
    relpath, arrays = spec
    text = inject.decomp.vanilla_decomp_text(relpath)
    return [d for array_name in arrays
            for d in vanilla_unit_defs(text, array_name)
            if d['allegiance'] == 'FACTION_ID_RED']


def resolve_donor(parity_ref, spec):
    """One of our enemies' `donor:` reference -> the vanilla unit(s) it stands in for.

    `spec` is a match over the twin's red force: a bare `[x, y]` coordinate, or a mapping of
    any of `at` / `class` / `level`. It resolves when everything it matches SHARES one AI --
    vanilla's three L2 soldiers behave identically, so "the L2 soldiers" is a well-formed
    donor for our group of three. Returns the representative unit.

    Two reasons a coordinate alone is not enough, both from real data: ch01 and ch06 sit on a
    different MAP donor from their parity twin, so not one of their tiles lines up with it;
    and where the map IS the twin's, a tile can still collide by accident -- ch05's
    bone-archer reinforcements stand on (13,0), where vanilla Ch5 parks an ARMOR_KNIGHT
    boss. Borrowing that boss's throne AI would have looked entirely reasonable.

    Disagreement RAISES rather than taking the first match. Vanilla Ch2 puts an archer and a
    brigand both on (14,7) with different AI, and a silent first-match would borrow the wrong
    behaviour while looking perfectly correct -- the exact failure #335 exists to end."""
    allegiance = spec.get('allegiance', 'RED') if isinstance(spec, dict) else 'RED'
    units = vanilla_units(parity_ref, allegiance)
    if units is None:
        raise ValueError('parity_reference %r has no curated UnitDefinition arrays, so a '
                         'donor cannot be resolved against it' % parity_ref)
    if isinstance(spec, dict):
        at = spec.get('at')
        want = {'classIndex': spec.get('class'), 'level': spec.get('level')}
    elif isinstance(spec, (list, tuple)) and len(spec) == 2:
        at, want = spec, {'classIndex': None, 'level': None}
    else:
        raise ValueError('donor %r is not a coordinate [x, y] nor a {at/class/level} '
                         'reference' % (spec,))
    if at is not None and not (isinstance(at, (list, tuple)) and len(at) == 2):
        raise ValueError('donor %r: `at` must be a coordinate [x, y]' % (spec,))
    found = [u for u in units
             if (at is None or u['position'] == tuple(at))
             and all(v is None or u[k] == v for k, v in want.items())]
    if not found:
        raise ValueError('donor %r matches no %s unit of %s'
                         % (spec, allegiance.lower(), parity_ref))
    behaviours = {u['ai'] for u in found}
    if len(behaviours) > 1:
        raise ValueError(
            'donor %r matches %d red units of %s whose AI DISAGREE (%s) -- narrow it with '
            '`at`, `class` or `level`, or declare an `ai_override:`'
            % (spec, len(found), parity_ref,
               '; '.join('%s L%d @(%s,%s) %s'
                         % (u['classIndex'], u['level'], u['xPosition'], u['yPosition'],
                            '{%s}' % ','.join('0x%02X' % b for b in u['ai']))
                         for u in found)))
    return found[0]


def _weapon_from_item_enums(item_enums):
    """First decomp item enum that maps to a real attacking weapon (else None)."""
    for it in item_enums:
        key = ITEM_TO_WEAPON.get(it)
        if key:
            return fc.W[key]
    return None


def vanilla_enemies(parity_ref, mode=None):
    """The vanilla reference chapter's fightable red force as a flat list of Combatants
    (each projected off class base to its level). None if the reference isn't curated yet;
    enemies with no modeled weapon (staff/throwaway only) are dropped."""
    bodies = vanilla_enemy_bodies(parity_ref, mode)
    return None if bodies is None else [u for u, _ai in bodies]


def vanilla_enemy_bodies(parity_ref, mode=None):
    """`vanilla_enemies`, each unit paired with its 4 AI bytes: [(Combatant, ai)]."""
    spec = PARITY_REFERENCE_UDEFS.get(parity_ref)
    if spec is None:
        return None
    relpath, arrays = spec
    text = inject.decomp.vanilla_decomp_text(relpath)
    shifts = vanilla_chapter_shifts(parity_ref) if mode else None
    if mode and shifts is None:
        # Silently returning an UNSHIFTED vanilla force here would compare our shifted
        # side against vanilla's authored table and still print a verdict -- exactly the
        # unnamed-configuration bug #303 exists to kill. Refuse instead.
        sys.exit('ERROR: parity_reference %r does not resolve to a vanilla chapter, so '
                    'its difficulty numbers are unknown and a --mode read would compare '
                    'our SHIFTED force against an UNSHIFTED reference' % parity_ref)
    out = []
    for array_name in arrays:
        for i, d in enumerate(vanilla_unit_defs(text, array_name)):
            if d['allegiance'] != 'FACTION_ID_RED':
                continue
            weapon = _weapon_from_item_enums(d['items'])
            if weapon is None:
                continue
            # The REAL ARTICLE (#285): a named vanilla unit fights as class base PLUS its own
            # CharacterData line, so the aggregate reads it that way -- symmetric with our side,
            # which resolves its lines through unit_real_article(). Measured off class base,
            # both sides understated their named units and did so unevenly, because the two
            # sides carry lines through different mechanisms. `inf` is no longer a hazard here:
            # metric_rounds_to_kill floors the damage rather than dropping the unit.
            ch = d.get('charIndex')
            out.append((_enemy_from_enum('%s#%d[%s]' % (array_name, i, ch),
                                         d['classIndex'], d['level'],
                                         weapon, vanilla_personal_line(ch),
                                         mode=mode, shifts=shifts,
                                         shiftable=_takes_difficulty_shift(ch),
                                         base_level=_character_base_level(ch)),
                        d['ai']))
    return out


def _vanilla_internal_name(parity_ref):
    """'FE8 Ch5' -> the chapter_settings `internalName` that IS vanilla Ch5 ('L05').

    The main-story chapters are L00 (prologue) through L08; the Eirika-route chapters
    from 9 on are E09..E20. Resolving by name rather than by index is the point: slot 5
    is `I05`, the inserted Ch5x, so every chapter from 5 on sits one slot past its own
    number."""
    if parity_ref == 'FE8 Prologue':
        return 'L00'
    m = re.match(r'^FE8 Ch(\d+)$', parity_ref)
    if not m:
        return None
    n = int(m.group(1))
    return ('L%02d' if n <= 8 else 'E%02d') % n


def vanilla_chapter_shifts(parity_ref):
    """The parity reference chapter's OWN difficulty triple, in `mode_stats` shape.

    This is what makes a cross-mode parity read honest: our side and the vanilla side
    are shifted by the numbers each chapter actually carries, so a mode comparison is
    still comparing two tuned tables rather than one tuned table against a shifted one.
    None if the reference does not name a vanilla chapter."""
    name = _vanilla_internal_name(parity_ref)
    if name is None:
        return None
    settings = json.loads(inject.decomp.vanilla_decomp_text('src/data/chapter_settings.json'))
    for chapter in settings['chapters']:
        if chapter.get('internalName') == name:
            return {'tutorial': chapter['easyModeLevelMalus'],
                    'normal': chapter['normalModeLevelMalus'],
                    'difficult': chapter['difficultModeLevelBonus']}
    return None


def vanilla_named_bosses(parity_ref, with_personal=True):
    """The twin's NAMED units as (name, Combatant). Used only by the role check -- see the
    note in vanilla_enemies about keeping the aggregate class-base-only."""
    spec = PARITY_REFERENCE_UDEFS.get(parity_ref)
    if spec is None:
        return []
    relpath, arrays = spec
    text = inject.decomp.vanilla_decomp_text(relpath)
    out = []
    for array_name in arrays:
        for d in vanilla_unit_defs(text, array_name):
            ch = d.get('charIndex')
            if d['allegiance'] != 'FACTION_ID_RED' or not str(ch or '').startswith('CHARACTER_'):
                continue
            weapon = _weapon_from_item_enums(d['items'])
            if weapon is None:
                continue
            out.append((ch.replace('CHARACTER_', '').title(),
                        _enemy_from_enum(ch, d['classIndex'], d['level'], weapon,
                                         vanilla_personal_line(ch) if with_personal else None)))
    return out


def vanilla_boss_bar(parity_ref):
    """(name, rounds-to-kill, used_personal) for the twin's toughest named boss. Prefers the
    real article (class + personal line); falls back to class-base-only when that boss is
    undentable by the fixed yardstick -- Saar at Def 13 exactly matches the yardstick's attack,
    which says more about the yardstick being a weak average unit (the chapter hands you an
    Armorslayer for exactly this) than about the boss. (None, 0.0, True) when uncurated."""
    base = {n: fc.rounds_to_kill(YARDSTICK, c)
            for n, c in vanilla_named_bosses(parity_ref, with_personal=False)}
    rows = []
    for n, c in vanilla_named_bosses(parity_ref, with_personal=True):
        val = fc.rounds_to_kill(YARDSTICK, c)
        if val == float('inf'):                  # fall back PER BOSS, not all-or-nothing:
            val, used = base.get(n, 0.0), False  # one undentable boss must not hand the bar
        else:                                    # to a weaker named unit that happens to be
            used = True                          # dentable (Ch5's bandit vs Saar).
        if val and val != float('inf'):
            rows.append((n, val, used))
    return max(rows, key=lambda r: r[1]) if rows else (None, 0.0, True)


def vanilla_projection(parity_ref, deploy_cap):
    """Forward target for a PLANNED chapter (#123): its vanilla reference's own pressure,
    printed as the bar the authored chapter must land within the parity band of. Both halves
    count the FULL force: `proof` still reports how many units the fixed YARDSTICK cannot dent,
    because that is worth knowing about a chapter you are about to write, but they are no longer
    SKIPPED -- metric_rounds_to_kill floors them (#285). Skipping made a chapter with a wall
    look cheaper to clear than one without. None if the reference isn't curated. Purely
    informational: planned chapters never gate."""
    van = vanilla_enemies(parity_ref)
    if van is None:
        return None
    cap = max(1, deploy_cap)
    threat = sum(fc.damage_per_round(e, YARDSTICK) for e in van) / cap
    clearload = sum(metric_rounds_to_kill(e) for e in van) / cap
    return {'threat': threat, 'clearload': clearload, 'n': len(van),
            'proof': sum(1 for e in van if fc.damage(YARDSTICK, e) <= 0)}


def _ally_lines(char_enum, class_enum, level):
    """Career stat lines for one vanilla ally: class base + the named character's personal
    line, grown on its OWN curve above its join level (one line when it is not above it)."""
    cbase = _class_base(class_enum)
    dbase = inject.stats.donor_base_stats(_characters_text(), char_enum)
    eff = {f: cbase.get(f, 0) + dbase.get(f, 0) for f in inject.stats.BASE_FIELDS}
    gained = level - _character_base_level(char_enum) if level is not None else 0
    if gained <= 0:
        return [eff]
    growths, _ = inject.stats.donor_growths_and_ranks(_characters_text(), char_enum)
    return careers(eff, growths, gained, _class_caps(class_enum))


def _ally_name(char_enum):
    return char_enum.replace('CHARACTER_', '').title()


def _ally_combatant(char_enum, class_enum, weapon, level=None):
    """One vanilla ally Combatant: class base + the named character's personal line (the same
    donor-base inheritance our cast uses, mirroring player_combatant). Allies aren't
    autoleveled: their CharacterData stats are already the join-level display. `level`, when
    it is above that join level, grows them on their OWN curve the way `player_combatant`
    grows ours, so a leveled read compares like with like.
    Named off charIndex (CHARACTER_EIRIKA -> 'Eirika')."""
    return _stats_to_combatant(_ally_name(char_enum),
                               _median_line(_ally_lines(char_enum, class_enum, level)),
                               weapon, CLASS_TAGS.get(class_enum, frozenset()))


# Eirika's route up to the last twin a hosted chapter is graded against. The vanilla party at
# any of these is everybody recruited so far, which the decomp states chapter by chapter.
VANILLA_CHAIN = ('FE8 Prologue', 'FE8 Ch1', 'FE8 Ch2', 'FE8 Ch3', 'FE8 Ch4', 'FE8 Ch5',
                 'FE8 Ch6')

# include/constants/characters.h: Eirika (0x01) to Tana (0x22) are the playable characters.
# From 0x23 up are cutscene and creature-campaign copies (LYON_CC ...) and bosses.
PLAYABLE_PIDS = range(0x01, 0x23)


@dataclasses.dataclass(frozen=True)
class VanillaRecruit:
    char: str              # CHARACTER_* enum
    class_enum: str
    level: int             # the level its joining UnitDefinition places it at
    items: tuple
    fields_from: int       # VANILLA_CHAIN index of the first chapter it can be deployed in


def _talk_recruits(stem):
    """Characters a chapter's talk events recruit: the TARGET of each `CHAR(flag, script,
    actor, target)` in its eventinfo (Eirika->Ross, Ross->Garcia, Neimi->Colm,
    Natasha->Joshua)."""
    relpath = 'src/events/%s-eventinfo.h' % stem
    if not os.path.exists(os.path.join(inject.decomp.SUBMODULE, relpath)):
        return set()
    info = inject.decomp.vanilla_decomp_text(relpath)
    return set(re.findall(r'\bCHAR\([^,]+,[^,]+,\s*\w+\s*,\s*(CHARACTER_\w+)\s*\)', info))


def _udef_sources(stem):
    sources = [inject.decomp.vanilla_decomp_text('src/events_udefs.c')]
    own = 'src/events/%s-eventudefs.h' % stem      # only the Prologue and Ch1 have their own
    if os.path.exists(os.path.join(inject.decomp.SUBMODULE, own)):
        sources.insert(0, inject.decomp.vanilla_decomp_text(own))
    return sources


def vanilla_udefs_named(stem, name):
    """One UnitDefinition array of a vanilla chapter, parsed from wherever the decomp defines
    it ([] if nowhere)."""
    text = next((t for t in _udef_sources(stem) if re.search(re.escape(name) + r'\[\]', t)),
                None)
    return vanilla_unit_defs(text, name) if text is not None else []


def _chapter_udefs(stem):
    """Every UnitDefinition a vanilla chapter's eventscript loads, in the order it names them,
    parsed from wherever the decomp defines them."""
    script = inject.decomp.vanilla_decomp_text('src/events/%s-eventscript.h' % stem)
    for name in dict.fromkeys(re.findall(r'\b(UnitDef_\w+)', script)):
        yield from vanilla_udefs_named(stem, name)


@functools.lru_cache(maxsize=None)
def vanilla_recruits():
    """Everyone FE8 recruits along VANILLA_CHAIN, assuming every recruit succeeds, in join order.

    A character joins at its first ARMED load. Cutscene loads carry no items (the throne room
    stands Moulder and Vanessa up as Generals, Ephraim appears as a Soldier), the same rule the
    red registry uses to drop cutscene villains. A BLUE load is on the field that chapter. A
    GREEN or RED load joins only if a talk event recruits it, and fields from the next chapter,
    which is our own convention for a recruit too (`exp_curve.party_classes`). That second rule
    keeps out Ch4's Larachel, Dozla and Rennac, who are armed green cameos there and join much
    later."""
    seen, out = set(), []
    for index, ref in enumerate(VANILLA_CHAIN):
        stem = PARITY_REFERENCE_STEM[ref]
        talk = _talk_recruits(stem)
        for u in _chapter_udefs(stem):
            char = u['charIndex']
            if (not char or char in seen or not u['items']
                    or _character_number(char) not in PLAYABLE_PIDS):
                continue
            if u['allegiance'] == 'FACTION_ID_BLUE':
                fields_from = index
            elif char in talk:
                fields_from = index + 1
            else:
                continue
            seen.add(char)
            out.append(VanillaRecruit(char, u['classIndex'], u['level'], tuple(u['items']),
                                      fields_from))
    return tuple(out)


def _named_item_grants(stem):
    """[(CHARACTER_*, ITEM_*)] a chapter's script hands to a NAMED character -- Eirika's Rapier
    is `SVAL(EVT_SLOT_3, ITEM_SWORD_RAPIER)` + `GIVEITEMTO(CHARACTER_EIRIKA)` in the Prologue,
    not on her joining load. Village gifts go to whoever visits (`CHAR_EVT_ACTIVE_UNIT`), so
    they are left out, as our own cast leaves them out."""
    script = inject.decomp.vanilla_decomp_text('src/events/%s-eventscript.h' % stem)
    out = []
    for item, char in re.findall(r'SVAL\(EVT_SLOT_3,\s*(\w+)\)\s*GIVEITEMTO\((CHARACTER_\w+)\)',
                                 script):
        if not item.startswith('ITEM_'):
            item = _item_id_to_enum().get(int(item, 0), item)
        out.append((char, item))
    return out


def _vanilla_members(parity_ref):
    """(char, class_enum, weapon) for every vanilla recruit that can deploy into `parity_ref`,
    or None for a twin off VANILLA_CHAIN."""
    if parity_ref not in VANILLA_CHAIN:
        return None
    index = VANILLA_CHAIN.index(parity_ref)
    granted = collections.defaultdict(list)
    for ref in VANILLA_CHAIN[:index + 1]:
        for char, item in _named_item_grants(PARITY_REFERENCE_STEM[ref]):
            granted[char].append(item)
    return [(r.char, r.class_enum, _weapon_from_item_enums(r.items + tuple(granted[r.char])))
            for r in vanilla_recruits() if r.fields_from <= index]


def vanilla_party(parity_ref, levels=None):
    """The vanilla party that can deploy into `parity_ref`, as Combatants, or None for a twin off
    VANILLA_CHAIN. `levels` maps CHARACTER_* to the level it arrives at (`exp_curve.entering`);
    a character missing from it is at its join level. Weapon = the joining load's first
    attacking item, as our cast is armed; a staff-only healer is weaponless support (#62)."""
    members = _vanilla_members(parity_ref)
    if members is None:
        return None
    levels = levels or {}
    return [_ally_combatant(char, class_enum, weapon, levels.get(char))
            for char, class_enum, weapon in members]


def vanilla_party_careers(parity_ref, levels=None):
    """`vanilla_party`, once per simulated career: {name: [Combatant]}."""
    members = _vanilla_members(parity_ref)
    if members is None:
        return None
    levels = levels or {}
    return {_ally_name(char): [_stats_to_combatant(_ally_name(char), line, weapon,
                                                   CLASS_TAGS.get(class_enum, frozenset()))
                               for line in _ally_lines(char, class_enum, levels.get(char))]
            for char, class_enum, weapon in members}


def pressure_verdict(ours, vanilla, band=0.25):
    """Compare our (threat/slot, clear-load/slot) to the vanilla reference's. Each metric
    is tagged OK / harder / easier by whether its ratio sits inside ±band of parity; the
    overall verdict is OFF if either metric strays. The band is tunable (#48 ~±25%)."""
    (ot, ol), (vt, vl) = ours, vanilla
    tr = ot / vt if vt else float('inf')
    lr = ol / vl if vl else float('inf')

    def tag(r):
        return 'OK' if abs(r - 1) <= band else ('harder' if r > 1 else 'easier')

    threat, load = tag(tr), tag(lr)
    return {'threat_ratio': tr, 'load_ratio': lr, 'threat': threat, 'load': load,
            'verdict': 'OK' if threat == 'OK' and load == 'OK' else 'OFF'}


def chapter_enemy_force(chap, mode=None, shifts=None):
    """Our chapter's full enemy force as a flat per-unit Combatant list (bosses included),
    honoring each entry's `count`/`composition` -- the multiplicity enemy_combatants drops.
    This is the our-side input to enemy_pressure (the parity comparand to vanilla_enemies).

    Every unit resolves to its REAL ARTICLE (#285) -- class base plus whichever of the three
    personal-line sources applies (`personal:`, BASE_DONOR, ENEMY_BASE_SLOT). A `composition`
    entry is a mixed bag of GENERICS, so no personal line is applied to its members -- a
    `personal:` or a donor-matching id on such an entry describes the group, and adding a full
    character line to every body in the bag would be a silent multiplier."""
    return [u for _ed, u in chapter_units(chap, mode=mode, shifts=shifts)]


def bosses_over_their_donor_base_level(campaign):
    """Bosses that deploy ABOVE their vanilla donor slot's baseLevel (sorted ids).

    `_our_base_level` treats every boss as malus-immune. For raw pids that is ENFORCED
    (RAW_PID_LEVEL_SOURCES writes baseLevel = deploy level). For the ones riding vanilla
    CHARACTER_ slots it is merely true today, and at ZERO margin -- Breguet 4/4, Bone 4/4,
    Bazba 6/6. One level bump and the ROM starts applying the malus while the model still
    assumes it does not, which is the silent model/ROM divergence in miniature."""
    return sorted(uid for chapter in inject.hosts.hosted_chapters()
                  for uid in _boss_entries_over_donor_base_level(
                      inject.hosting._load_chapter_yaml(campaign, inject.hosting.chapter_yaml_for(chapter.name))))


def _boss_entries_over_donor_base_level(chap):
    """The same question for ONE loaded chapter, over every roster key and every declared
    body level. `_entry_combatants` applies the malus-immunity assumption to a boss wherever
    it is declared, so the guard has to look wherever it is declared."""
    out = []
    for enemy in chapter_roster_entries(chap):
        if not (enemy.get('is_boss') or enemy.get('is_miniboss')):
            continue
        donor = inject.cast.ENEMY_BASE_SLOT.get(enemy.get('id'))
        if not donor:
            continue
        if max(_body_levels(enemy)) > _character_base_level(donor):
            out.append(enemy.get('id'))
    return out


def _our_takes_difficulty_shift(enemy_def):
    """Does the engine shift THIS unit of ours? The `>= 0x3C` gate, our side.

    Resolved through the same donor lookup `unit_real_article` uses, because it answers the
    same question -- which character SLOT the unit rides. A cast member deployed hostile
    (BASE_DONOR) rides a playable slot and is therefore difficulty-immune: ch05's Sahnar is
    the live case, and the ROM agrees, reading identical stats in all three modes. An enemy
    on a vanilla boss slot (ENEMY_BASE_SLOT) or on a raw pid sits well above the gate."""
    donor = inject.stats.BASE_DONOR.get(enemy_def.get('id')) or inject.cast.ENEMY_BASE_SLOT.get(enemy_def.get('id'))
    return _takes_difficulty_shift(donor) if donor else True


def _our_base_level(enemy_def):
    """The baseLevel OUR unit carries, for the malus gate.

    Every boss and miniboss we field is penalty-immune, and that is an enforced invariant
    rather than a coincidence: the four on raw pids get baseLevel = their deploy level from
    RAW_PID_LEVEL_SOURCES (guarded by unregistered_raw_pid_bosses), and the rest ride
    vanilla CHARACTER_ slots that already ship baseLevel >= deploy level. Line units are
    generics on pid 0x80/0x8e/0xaa, whose gaps carry baseLevel 1."""
    if enemy_def.get('is_boss') or enemy_def.get('is_miniboss'):
        return int(enemy_def.get('level', 1))
    return 1


# ch06 ran into this first and worked around it privately, by declaring its turn-4 wave
# inside `enemy_units` -- its own YAML says declaring them "is what makes the two sides count
# the same force". ch02 used the `reinforcements:` key instead and was simply never counted.
# The definition lives in the injector (inject/raw_pids.py), which owns the chapter schema, so the parity
# metric, the AI guard, the personal-line routes and the raw-pid registry cannot drift apart
# on which units a chapter fields.
chapter_roster_entries = inject.raw_pids.chapter_roster_entries


def _entry_combatants(ed, mode=None, shifts=None, real_article=False, drop_staff=True,
                      distinct=False):
    """Every BODY one enemy entry places.

    `drop_staff` drops a unit carrying no modeled weapon, which is what every PARITY metric
    wants (it can contribute no damage, and `unmodeled_enemies` warns about it separately).
    The cast tables want the opposite: a chapter's healer is a body our units can kill and
    walk past, so `load_field` keeps it.

    `distinct` collapses identical bodies to one, for readers asking a per-unit-TYPE
    question: whether a unit's threat is an outlier is a property of the unit, not of how
    many copies of it stand on the map. Two bodies of one entry differ only when `levels:`
    gives them different levels.

    THE entry expander. It was three near-copies -- one in `chapter_units`, one in
    `_entry_combatants`, one in `role_findings` -- which is how `levels:` came to be honored
    in one reader and defaulted to L1 in the others.

    `real_article` folds in the entry's personal line (#285); the aggregate metrics want
    class base on both sides and pass it False. A `composition` entry is a bag of GENERICS,
    so it never takes one.
    """
    if 'composition' in ed and 'class' not in ed:
        name = ed.get('id', ed.get('name', 'enemy'))
        by_class = ed.get('inventory_by_class', {})
        bodies = list(zip(ed.get('composition', []), _body_levels(ed)))
        # A bag NEVER takes a personal line, `real_article` or not: it is a mixed bag of
        # GENERICS, and RAW_PID_PERSONAL_SOURCES routes one pid per unit id -- so at most
        # one member could carry a line in the ROM while all N would be credited here. A
        # `personal:` or donor-matching id on such an entry describes the GROUP.
        # `base_level`/`shiftable` are resolved the same way the class branch resolves them,
        # so a bag boss is not handed a malus the engine never applies.
        units = [_one_enemy('%s-%s' % (name, cls), cls, lv,
                            _weapon_for([{'id': w} for w in by_class.get(cls, [])]),
                            mode=mode, shifts=shifts,
                            base_level=_our_base_level(dict(ed, level=lv)),
                            shiftable=_our_takes_difficulty_shift(ed))
                 for cls, lv in (dict.fromkeys(bodies) if distinct else bodies)]
    else:
        # One body per DECLARED level, not `count` copies of one: a wave authored as
        # `levels: [2, 3]` is an L2 and an L3, which is what the ROM emits. `base_level` is
        # THIS body's level for a boss, since that is the floor the difficulty malus tests
        # against -- reading it off `level:` while the body comes from `levels:` invents a
        # malus the engine never applies.
        units = []
        levels = _body_levels(ed)
        for lv in (dict.fromkeys(levels) if distinct else levels):
            units.extend(enemy_combatants(
                dict(ed, level=lv), mode=mode, shifts=shifts,
                base_level=_our_base_level(dict(ed, level=lv)),
                shiftable=_our_takes_difficulty_shift(ed)))
        if real_article:
            units = [unit_real_article(ed, c) for c in units]
    return [u for u in units if u.weapon is not None or not drop_staff]


def chapter_units(chap, mode=None, shifts=None):
    """(enemy_def, real-article Combatant) for every BODY our chapter fields, weapons modeled.

    THE our-side force builder. It exists as one function because it was two: `solo_contributors`
    kept a second copy that expanded `count` over `enemy_combatants` -- which collapses a
    `composition` to its DISTINCT classes -- so on ch01 it counted 6 bodies where this counts 3
    and printed a share that contradicted the verdict directly above it (#285).
    """
    return [(ed, u) for ed in chapter_roster_entries(chap)
            for u in _entry_combatants(ed, mode=mode, shifts=shifts, real_article=True)]


def chapter_enemy_bodies(chap, mode=None, shifts=None):
    """`chapter_units`' force, each body paired with its combat-weight table (#430 step 2b):
    [(Combatant, table)]. A body's AI is its own position's donor, so an entry whose donors
    run different tables (ch01) is read body by body."""
    out = []
    for ed in chapter_roster_entries(chap):
        bodies = _entry_combatants(ed, mode=mode, shifts=shifts, real_article=True,
                                   drop_staff=False)
        for index, unit in enumerate(bodies):
            if unit.weapon is not None:
                out.append((unit, ai_target.combat_weight_table(
                    enemy_ai_bytes(chap, ed, index))))
    return out


def unmodeled_enemies(chap):
    """Enemy entries that contribute NO modeled-weapon units (so chapter_enemy_force drops
    them) -- returned as {id, is_boss} so the report can warn instead of silently skewing the
    verdict (#51). A boss here means the parity read for that chapter is untrustworthy."""
    out = []
    for ed in chapter_roster_entries(chap):
        if 'composition' in ed and 'class' not in ed:
            by_class = ed.get('inventory_by_class', {})
            modeled = any(_weapon_for([{'id': w} for w in by_class.get(cls, [])])
                          for cls in ed.get('composition', []))
        else:
            modeled = _weapon_for(ed.get('inventory')) is not None
        if not modeled:
            out.append({'id': ed.get('id', ed.get('name', 'enemy')),
                        'is_boss': bool(ed.get('is_boss'))})
    return out


# ── mirror% -- how much of the twin a chapter TRANSCRIBES (#367) ─────────────────
# The parity ratio is an aggregate over stats, so it cannot tell a chapter that copies its
# twin unit for unit from one that composes a different force arriving at the same per-slot
# pressure. Both read x1.00, and only one of them is a measurement. ch06 is the live case:
# it reproduces 100% of vanilla Ch6's force, so its perfect score is a checksum on the donor
# pipeline rather than evidence about the chapter. mirror% prints beside every ratio so the
# difference is visible without re-deriving it.
#
# A body is (class, level) -- the unit, not just its class: an L9 fighter is not the twin's
# L1 one. The intersection is a MULTISET, so doubling a body cannot score it twice, and the
# denominator is the TWIN's body count, so fielding more than the twin never reads above
# 100%. Both sides count every body: ours line + reinforcements, the twin every red
# UnitDefinition in its curated arrays (reinforcement waves included). Nothing is dropped
# for carrying no modeled weapon the way the pressure metric drops a staff-only healer --
# this measures the force's SHAPE, and a healer the twin fields is a unit we did or did not
# reproduce.


def _force_signature(chap):
    """Every enemy BODY the chapter fields, as a Counter of (class enum, level).

    Line and reinforcements both, `count`/`composition` expanded -- the multiplicity the
    metrics layer collapses is exactly what a shape comparison needs."""
    out = collections.Counter()
    for ed in chapter_roster_entries(chap):
        if 'class' in ed:
            for lv in _body_levels(ed):
                out[(_enemy_class_enum(ed['class']), lv)] += 1
        else:
            for cls, lv in zip(ed.get('composition', []), _body_levels(ed)):
                out[(_enemy_class_enum(cls), lv)] += 1
    return out


def mirror_share(chap):
    """Share of the twin's force this chapter reproduces exactly, as
    {shared, ours, twin, pct}. None when the reference isn't curated (#48 registry).

    Takes no `mode`, and that is not an omission: a difficulty mode re-projects the SAME
    level through a chapter's malus/bonus (`mode_stats`), so it moves stats and never a
    unit's class or level, and the Hard-only waves are folded into both sides
    unconditionally. The force's shape is identical in all three modes."""
    van = vanilla_red_units(chap.get('parity_reference'))
    if van is None:
        return None
    twin = collections.Counter((u['classIndex'], u['level']) for u in van)
    ours = _force_signature(chap)
    shared = sum((twin & ours).values())
    n = sum(twin.values())
    return {'shared': shared, 'ours': sum(ours.values()), 'twin': n,
            'pct': 100.0 * shared / n if n else 0.0}


# ── Pure metrics layer (no I/O; operates on fe_combat.Combatant) ──────────────────
# The three FE survival questions, each a single number so a chapter can be compared
# to vanilla at a glance.

def durability(unit, enemies, terrain_avoid=0):
    """Worst-case enemy-rounds to drop `unit` across `enemies` (lower = frailer).

    `terrain_avoid` is the cover the unit is standing on. inf if nothing can hurt it."""
    return min((enemy_rounds_to_down(e, unit, terrain_avoid) for e in enemies),
               default=float('inf'))


def enemy_rounds_to_down(enemy, unit, terrain_avoid=0):
    """Rounds for `enemy` to drop `unit` (unit on `terrain_avoid` cover)."""
    dpr = fc.damage_per_round(enemy, unit, terrain_avoid)
    return float('inf') if dpr <= 0 else unit.hp / dpr


def party_throughput(party, enemies, terrain_avoid=0):
    """Sum of each unit's BEST kills/round (capped 1.0/unit) over the enemy set.

    A unit can only kill one enemy a round, so it counts its single best matchup --
    not raw damage summed across every target. This is the party's kill ceiling."""
    return sum(max((fc.kills_per_round(u, e, terrain_avoid) for e in enemies),
                   default=0.0) for u in party)


def carry(boss, party, terrain_avoid=0):
    """The party's best answer to `boss`: (unit, expected rounds-to-kill). The 'do we
    have a carry?' check -- some unit must crack the chapter's wall in good time."""
    ranked = sorted(party, key=lambda u: fc.rounds_to_kill(u, boss, terrain_avoid))
    best = ranked[0]
    return best, fc.rounds_to_kill(best, boss, terrain_avoid)


# ── Over the dice: the same metrics, once per simulated career (ADR 0311) ───────────
# A per-stat median line is a planning number nobody rolls. Near a doubling breakpoint it
# misreads the metric a party actually meets, so the report averages each metric over the
# careers and pairs it with a bad-luck reading.

BAD_LUCK_PERCENTILE = 10    # the bad-luck reading: the career one in ten does worse than


def spread(values, low_is_bad=True):
    """(average, bad-luck) of a metric over the careers. Bad luck is the
    BAD_LUCK_PERCENTILE-th career counted from the bad side: the low end for durability and
    kill rate, the high end (`low_is_bad=False`) for rounds to kill a boss."""
    values = sorted(values, reverse=not low_is_bad)
    return sum(values) / len(values), values[len(values) * BAD_LUCK_PERCENTILE // 100]


def dice_profile(careers, line, bosses):
    """One unit's metrics, once per career: durability on open ground and in a forest
    (20 avoid), its best kill rate against the line, and its fastest kill of any boss.

    A unit's careers repeat themselves, but rarely as whole lines, so each half of the fight
    is keyed on the stats `fe_combat` reads for it: being hit reads Def, Res, Spd, Con and Lck
    (HP only divides), hitting reads Pow, Skl, Spd, Con and Lck. `MetricsOverTheDice` checks
    this against the plain metrics, so a new stat read in `fe_combat` fails a test."""
    inf = float('inf')
    struck, striking, out = {}, {}, {'open': [], 'forest': [], 'kill': [], 'boss': []}
    for u in careers:
        dk = (u.df, u.res, u.spd, u.con, u.lck)
        if dk not in struck:
            struck[dk] = [[fc.damage_per_round(e, u, avoid) for e in line] for avoid in (0, 20)]
        ok = (u.pow, u.skl, u.spd, u.con, u.lck)
        if ok not in striking:
            striking[ok] = (max((fc.kills_per_round(u, e) for e in line), default=0.0),
                            min((fc.rounds_to_kill(u, b) for b in bosses), default=inf))
        for key, dprs in zip(('open', 'forest'), struck[dk]):
            out[key].append(min((u.hp / d if d > 0 else inf for d in dprs), default=inf))
        out['kill'].append(striking[ok][0])
        out['boss'].append(striking[ok][1])
    return out


def career_pairing(counts):
    """(n, {name: [career index] * n}) pairing each unit's careers into n joint careers.
    `counts` maps a unit to how many careers it has. Each unit's careers are shuffled on a
    seed of its own, so career i of one unit is independent of career i of another (they
    share the growth RNG's seed); a unit with fewer careers wraps."""
    n = max(counts.values())
    order = {}
    for name, k in counts.items():
        perm = list(range(k))
        random.Random('%d:%s' % (GROWTH_SEED, name)).shuffle(perm)
        order[name] = [perm[i % k] for i in range(n)]
    return n, order


def dice_party(profiles):
    """A fielded party's metrics, once per joint career. `profiles` maps a unit to its
    `dice_profile`. Each unit's careers are shuffled on a seed of its own before they are
    paired, so career i of one unit is independent of career i of another (they share the
    growth RNG's seed). A unit with one career, one that has not levelled, is that career in
    every pairing."""
    n, order = career_pairing({name: len(p['open']) for name, p in profiles.items()})
    def joint(key, combine):
        return [combine(profiles[u][key][order[u][i]] for u in profiles) for i in range(n)]
    return {'throughput': joint('kill', sum),
            'min_durability': joint('open', min),
            'carry': joint('boss', min)}


# A fixed, campaign-neutral reference attacker/defender. enemy_pressure measures every
# enemy against THIS unit, so a chapter's pressure is comparable to its vanilla reference's
# on the same scale; the yardstick's exact stats cancel in an ours-vs-vanilla ratio. Chosen
# as a plain mid-game footsoldier (iron sword -- triangle-ACTIVE like any sword, so it
# reads +1Mt/+15Hit vs axe foes and -1/-15 vs lances; modest bulk/offense).
YARDSTICK = fc.Combatant('yardstick', hp=24, pow=8, skl=8, spd=8, df=6, res=4, lck=4,
                         con=10, weapon=fc.W['iron-sword'])


def metric_rounds_to_kill(enemy, yardstick=YARDSTICK):
    """`rounds_to_kill` with a MEASUREMENT floor: a unit the yardstick cannot dent is scored as
    if each hit chipped 1, instead of reading `inf`.

    FE8 really does deal 0 damage there -- this floor is a property of the metric, not a claim
    about the game. It exists because `rounds_to_kill` is a CLIFF at the damage boundary: one
    more point of Def takes a unit from 12.9 rounds to infinite, and a ratio against infinity is
    undefined. The old answer was to EXCLUDE such units from clear-load, and that is what made
    the aggregate asymmetric (#285): vanilla Ch5's Saar dropped out of the twin's sum entirely
    while our Ravisin -- deliberately built to Saar's own bar, 13.4 rounds against his 12.9 --
    stayed in, moving ch05 from x0.84 to x1.34 without a single unit changing.

    The floor keeps every unit in the comparison on both sides, keeps the load monotonic in Def
    (more armour is never less work), and preserves the ordering that matters: Saar at Def 13
    scores 22.8 against Ravisin's 13.4, which is the truth about which is the harder wall.

    It must carry the SAME divisor `rounds_to_kill` uses (`fe_combat.expected_hits`: strikes,
    true hit, crit), or it is not a floor at all: dropping it makes the load jump DOWN across
    the cliff (real Saar read 46.8 rounds at Def 11 and 36.0 at Def 12 -- tougher unit, less
    work), which is the exact pathology this function exists to remove. With it the floor is
    not merely monotonic but CONTINUOUS: a unit taking exactly 1 damage per hit already scores
    hp/expected_hits, so the floor meets the last dentable value instead of stepping at it.
    """
    rounds = fc.rounds_to_kill(yardstick, enemy)
    if rounds != float('inf'):
        return rounds
    connects = fc.expected_hits(yardstick, enemy)
    if connects <= 0:                 # cannot connect at all -- no finite load to report
        return float('inf')
    return float(enemy.hp) / connects


def enemy_pressure(enemies, deploy_cap, yardstick=YARDSTICK):
    """Per-deploy-slot enemy pressure of an enemy list, as (threat/slot, clear-load/slot).

    threat/slot = Σ damage_per_round(enemy -> yardstick) ÷ deploy_cap -- how much incoming
    damage each of our slots must weather. clear-load/slot = Σ metric_rounds_to_kill(enemy)
    ÷ deploy_cap -- how much killing each slot must do to clear the map. Both measured against
    the fixed YARDSTICK so ours and the vanilla reference land on one scale; the metric is a
    static proxy (no positioning/AI/terrain), read as a ratio within a tolerance band."""
    cap = max(1, deploy_cap)
    threat = sum(fc.damage_per_round(e, yardstick) for e in enemies) / cap
    clearload = sum(metric_rounds_to_kill(e, yardstick) for e in enemies) / cap
    return threat, clearload


def _stat_key(u):
    return (u.hp, u.pow, u.skl, u.spd, u.df, u.res, u.lck, u.con, u.weapon, u.tags)


def party_matchup(bodies, careers):
    """Instrument v2, layer 1 (#430 step 2b): a force measured against the party that meets it.

    `bodies` is [(enemy Combatant, combat-weight table)], `careers` is {unit: [Combatant]} for
    the FIELDED party, once per simulated career (ADR 0311). Per joint career:

      threat/slot = sum over enemies of its damage per round against the unit FE8's AI would
                    attack (`ai_target.pick_target`), / units fielded
      clear-load  = sum over enemies of 1 / the field's COMBINED kill rate on it (the sum of
                    1 / rounds): the party-rounds the force takes to clear. Harmonic, because
                    a plain mean of rounds is dominated by whoever cannot dent the boss; a
                    member who cannot dent it, or carries no weapon, adds no rate but stays a
                    target. Only when NOBODY fielded can dent it does the rate fall back to
                    `metric_rounds_to_kill`'s floor, the one place the cliff it exists for
                    reappears.

    Each side is normalised by its own field, so a twin that fields two units (vanilla's
    prologue) is not divided by our eight. Returns {'threat', 'clear'} as averages over the
    joint careers, and 'per_enemy': a (name, threat, clear, weapon) average for each body, in
    order."""
    names = list(careers)
    armed = [m for m in names if careers[m][0].weapon is not None]
    inf = float('inf')
    # A pairing is read once per DISTINCT (enemy, member line) on the stats it reads, as
    # `dice_profile` does: the AI's score reads the whole line, being hit reads Def, Res, Spd,
    # Con and Lck, and hitting reads Pow, Skl, Spd, Con and Lck. The joint careers are then
    # lookups. Identical enemy bodies share one read.
    full = {m: [_stat_key(u) for u in careers[m]] for m in names}
    struck = {m: [(u.df, u.res, u.spd, u.con, u.lck) for u in careers[m]] for m in names}
    striking = {m: [(u.pow, u.skl, u.spd, u.con, u.lck) for u in careers[m]] for m in names}

    def table(keys, fn):
        return {m: {k: fn(u) for k, u in dict(zip(keys[m], careers[m])).items()}
                for m in keys}

    reads = {}
    for e, weights in bodies:
        key = (_stat_key(e), weights)
        if key not in reads:
            reads[key] = (
                table(full, lambda u: ai_target.combat_score(e, u, weights)),
                table(struck, lambda u: fc.damage_per_round(e, u)),
                table({m: striking[m] for m in armed},
                      lambda u: (fc.damage_per_round(u, e) / e.hp,
                                 (lambda r: 0.0 if r == inf else 1.0 / r)(
                                     metric_rounds_to_kill(e, u)))))
    read = [reads[(_stat_key(e), weights)] for e, weights in bodies]
    n, order = career_pairing({m: len(careers[m]) for m in names})
    rank = {m: -i for i, m in enumerate(names)}         # ties go to the first, as in FE8
    per = [[0.0, 0.0] for _ in bodies]
    for i in range(n):
        at = {m: order[m][i] for m in names}
        for j, (score, dpr, inv) in enumerate(read):
            target = max(names, key=lambda m: (score[m][full[m][at[m]]], rank[m]))
            rates = [inv[m][striking[m][at[m]]] for m in armed]
            rate = sum(r for r, _floor in rates) or sum(f for _r, f in rates)
            per[j][0] += dpr[target][struck[target][at[target]]]
            per[j][1] += 1.0 / rate if rate else inf
    slots = max(1, len(names))
    return {'threat': sum(p[0] for p in per) / n / slots,
            'clear': sum(p[1] for p in per) / n,
            'per_enemy': [(e.name, p[0] / n, p[1] / n, e.weapon.name)
                          for (e, _t), p in zip(bodies, per)]}


def _median_combatant(careers):
    """A unit's per-stat median over its careers (`_median_line`'s rule), as one Combatant.
    The careers come in the order they were rolled, so any one of them is a random draw."""
    first = careers[0]
    mid = len(careers) // 2
    return dataclasses.replace(first, **{
        f: sorted(getattr(c, f) for c in careers)[mid]
        for f in ('hp', 'pow', 'skl', 'spd', 'df', 'res', 'lck', 'con')})


def fielded_careers(careers, force, deploy_cap):
    """The `deploy_cap` units of an arriving party a player fields, ranked on each unit's
    median line by `_best_field`'s rule, with all of their careers: {unit: [Combatant]}."""
    field = _best_field([_median_combatant(c) for c in careers.values()], force, deploy_cap)
    return {u.name: careers[u.name] for u in field}


def bulk_durability(unit, enemies):
    """Worst-case enemy-rounds-to-down: like durability but assuming every hit CONNECTS
    (no avoid/RNG), still counting doubling. The right lens for a must-survive lord -- you
    design for the bad case, not the average -- so a dodge-tank isn't credited for luck."""
    worst = float('inf')
    for e in enemies:
        dmg = fc.damage(e, unit)
        if dmg <= 0:
            continue
        per_round = dmg * (2 if fc.doubles(e, unit) else 1)
        worst = min(worst, unit.hp / per_round)
    return worst


@dataclasses.dataclass
class LordFloor:
    """A per-lord survivability top-up: +HP / +Def / +Res, the bulk-durability it reaches,
    and whether the caps got there. `reached=False` flags a lord stats can't save from the
    chapter's threat (e.g. effective weapons) -- a positioning answer, not a stat one."""
    hp: int
    df: int
    res: int
    bulk: float
    reached: bool


def lord_floor_delta(unit, enemies, target=3.5, def_cap=4, res_cap=4, hp_cap=12):
    """Smallest HP/Def/Res bump lifting `unit` to `target` worst-case rounds-to-down.

    Survival-only stats (never Spd/Lck -- those add offense/dodge). The threat-appropriate
    defence (Res if the binding enemy is magic, else Def) is spent up to its cap, then HP
    fills the rest -- which keeps defence bumps modest and reproduces the hand-set +7/+4 on
    a Ch1 shaman. 0 for units already at/above target; `reached=False` if the caps fall
    short. The floor is computed ONCE (early game) and then fades as the party levels."""
    def with_delta(dh, dd, dr):
        return dataclasses.replace(unit, hp=unit.hp + dh, df=unit.df + dd, res=unit.res + dr)

    if bulk_durability(unit, enemies) >= target:
        return LordFloor(0, 0, 0, bulk_durability(unit, enemies), True)

    # Binding threat sets which defence stat blunts the most damage.
    binding = min(enemies, key=lambda e: bulk_durability(unit, [e]))
    magic = binding.weapon.kind == 'magic'
    dh = dd = dr = 0
    cap = res_cap if magic else def_cap
    while bulk_durability(with_delta(dh, dd, dr), enemies) < target and (dr if magic else dd) < cap:
        if magic:
            dr += 1
        else:
            dd += 1
    while bulk_durability(with_delta(dh, dd, dr), enemies) < target and dh < hp_cap:
        dh += 1
    b = bulk_durability(with_delta(dh, dd, dr), enemies)
    return LordFloor(dh, dd, dr, b, b >= target)


def lord_team_sweep(roster, line_enemies, bosses, deploy_limit, terrain_avoid=0):
    """For each candidate lord, the best `deploy_limit`-unit field anchored on that lord
    (the rest are the highest-throughput others), with the field's headline metrics.

    Models the #42 lord choice: any cast member can be forced-deployed as the must-survive
    lord, and we want to see that every choice yields a viable field (not just the obvious
    one). Until #42 fixes the candidate set, every rostered unit is treated as eligible."""
    def unit_throughput(u):
        return max((fc.kills_per_round(u, e, terrain_avoid) for e in line_enemies),
                   default=0.0)

    rows = []
    for lord in roster:
        others = sorted((u for u in roster if u is not lord),
                        key=unit_throughput, reverse=True)
        team = [lord] + others[:max(0, deploy_limit - 1)]
        row = {
            'lord': lord,
            'team': team,
            'throughput': party_throughput(team, line_enemies, terrain_avoid),
            'min_durability': min((durability(u, line_enemies, terrain_avoid)
                                   for u in team), default=float('inf')),
        }
        if bosses:
            row['carry_rounds'] = min(carry(b, team, terrain_avoid)[1] for b in bosses)
        rows.append(row)
    return sorted(rows, key=lambda r: r['throughput'], reverse=True)


# ── Chapter loading + report (I/O + presentation) ─────────────────────────────────
import glob       # noqa: E402

ROSTER = list(inject.stats.BASE_DONOR.keys())     # the playable cast (each has a stat donor)


def chapter_path(campaign, ch):
    """Resolve a short id ('ch01') to its chapter YAML path."""
    hits = sorted(glob.glob(os.path.join(
        inject.decomp.REPO, 'campaigns', campaign, 'chapters', ch + '*.yaml')))
    if not hits:
        raise SystemExit('ERROR: no chapter YAML matching %r' % ch)
    return hits[0]


def chapter_deploy_limit(chap, default):
    """The chapter's field cap from its `deployment:` block (#107 normalized schema);
    chapters without one (the fixed-roster prologue, prose-only seeds) fall back to
    `default` (= whole roster). The retired top-level shape is rejected loudly --
    silently modeling a mis-placed cap as "whole roster" would bake wrong parity
    numbers into a tuning session before the pre-commit gate ever runs."""
    if 'deploy_limit' in chap or 'deploy_slots' in chap:
        sys.exit('ERROR: %s: top-level deploy_limit/deploy_slots -- move under the '
                 '`deployment:` block (#107 schema; check.py explains)'
                 % chap.get('id', 'chapter'))
    limit = (chap.get('deployment') or {}).get('deploy_limit')
    return int(limit) if limit is not None else int(default)


def load_field(campaign, ch, leveled=False):
    """Assemble (roster, line_enemies, bosses, deploy_limit, enemy_labels) for a chapter.

    `leveled` fields the party the exp model says arrives: only the units that have joined by
    this chapter, each grown to its expected level on entering it (`exp_curve.entering`).
    Off, it is the whole cast at join level -- the line the injector's lord floor is sized
    from, so `--lord-floor` keeps reading it."""
    chap = chapter_schema.load(chapter_path(campaign, ch))
    if leveled:
        import exp_curve                    # exp_curve imports this module
        party = exp_curve.entering(campaign, int(chap['chapter_number']))['party']
        roster = [player_combatant(campaign, uid, level - joined)
                  for uid, (joined, level) in party.items()]
    else:
        roster = [player_combatant(campaign, uid) for uid in ROSTER]
    line, bosses, labels = [], [], []
    for ed in chapter_roster_entries(chap):
        units = _entry_combatants(ed, drop_staff=False)
        kind = ed.get('class') or '+'.join(dict.fromkeys(ed.get('composition', ['?'])))
        labels.append('%dx %s (%s l%s)'
                      % (_entry_body_count(ed), ed.get('name', ed.get('id', '?')), kind,
                         ed.get('level') or ','.join(str(lv) for lv in _body_levels(ed))))
        (bosses if ed.get('is_boss') else line).extend(units)
    return chap, roster, line, bosses, chapter_deploy_limit(chap, len(roster)), labels


def arriving_careers(campaign, ch):
    """{uid: [Combatant]}: the party the exp model says arrives at `ch` (`exp_curve.entering`),
    each unit once per simulated career (`player_careers`)."""
    import exp_curve                        # exp_curve imports this module
    chap = chapter_schema.load(chapter_path(campaign, ch))
    return _party_careers(campaign,
                          exp_curve.entering(campaign, int(chap['chapter_number']))['party'])


def _party_careers(campaign, party):
    return {uid: player_careers(campaign, uid, level - joined)
            for uid, (joined, level) in party.items()}


def _metrics(field, profiles):
    """Headline numbers for a fielded party, over the dice: each is (average, bad luck)
    (`spread`), and the carry names the unit with the fastest median-line kill."""
    joint = dice_party({u.name: profiles[u.name] for u in field})
    m = {'throughput': spread(joint['throughput']),
         'min_durability': spread(joint['min_durability'])}
    if not all(r == float('inf') for r in joint['carry']):
        m['carry'] = spread(joint['carry'], low_is_bad=False)
    return m


def _fmt_spread(pair, fmt=None):
    avg, bad = pair
    if fmt:
        return '%s (bad %s)' % (fmt % avg, fmt % bad)
    return '%s (bad %s)' % (_fmt_rounds(avg), _fmt_rounds(bad))


def _print_metrics(label, field, m, bosses):
    carrier = (' · carry %s %s rounds vs boss'
               % (min(field, key=lambda u: min(fc.rounds_to_kill(u, b) for b in bosses)).name,
                  _fmt_spread(m['carry']))) if 'carry' in m else ''
    print('  %sthroughput %s kills/round (cap 1/unit) · durability(min) %s%s'
          % (label, _fmt_spread(m['throughput'], '%.2f'), _fmt_spread(m['min_durability']),
             carrier))


def _best_field(party, line, deploy_limit):
    """The deploy_limit units with the highest single-target throughput."""
    return sorted(party, key=lambda u: max(
        (fc.kills_per_round(u, e) for e in line), default=0.0), reverse=True)[:deploy_limit]


def _fmt_rounds(r):
    return 'inf' if r == float('inf') else '%.1f' % r


def _fmt_dura_delta(ours, van):
    """Signed ours-vs-vanilla delta for a rounds-like metric, inf-safe (inf - inf is 0, not
    nan; a lone inf reads as +/-inf)."""
    if ours == float('inf') and van == float('inf'):
        return '+0.0'
    if ours == float('inf'):
        return '+inf'
    if van == float('inf'):
        return '-inf'
    return '%+.1f' % (ours - van)


def _print_cast(title, roster, levels, line, profiles):
    """One arriving cast as a table: each unit's level, its median stat line and weapon, then
    over the dice its durability on open ground / in a forest and its best kill rate against
    the chapter's line, each an average with its bad-luck reading."""
    print('\n-- %s --' % title)
    print('  stats: each stat\'s median career · metrics: average (bad luck: %d%% of careers '
          'do worse)' % BAD_LUCK_PERCENTILE)
    print('  %-11s %3s %3s%3s%3s%3s%3s%3s%3s%3s  %-12s  %-11s  %-11s  %s'
          % ('unit', 'Lv', 'HP', 'Pw', 'Sk', 'Sp', 'Df', 'Rs', 'Lk', 'Cn',
             'weapon', 'durab open', 'forest', 'best kill/round'))
    for u in sorted(roster, key=lambda x: spread(profiles[x.name]['kill'])[0], reverse=True):
        best = max(((fc.kills_per_round(u, e), e) for e in line),
                   key=lambda x: x[0], default=(0.0, None))
        p = profiles[u.name]
        cells = [spread(p['open']), spread(p['forest']), spread(p['kill'])]
        print('  %-11s %3s %3d%3d%3d%3d%3d%3d%3d%3d  %-12s  %4s (%4s)  %4s (%4s)  %.2f (%.2f)%s'
              % (u.name, levels.get(u.name, '?'), u.hp, u.pow, u.skl, u.spd, u.df, u.res,
                 u.lck, u.con, u.weapon.name if u.weapon else '(staff)',
                 _fmt_rounds(cells[0][0]), _fmt_rounds(cells[0][1]),
                 _fmt_rounds(cells[1][0]), _fmt_rounds(cells[1][1]),
                 cells[2][0], cells[2][1],
                 (' vs ' + best[1].name) if best[1] else ''))


def report(campaign, ch, mode=None):
    import exp_curve                        # exp_curve imports this module
    head = chapter_schema.load(chapter_path(campaign, ch))
    number, parity_ref = int(head['chapter_number']), head.get('parity_reference')
    try:
        arriving = exp_curve.entering(campaign, number, parity_ref)
    except ValueError as refusal:           # the exp model refuses a body it cannot price
        print('!! no arriving party -- the exp model refused: %s\n'
              '!! every absolute reading below is the JOIN line, not the arriving party\n'
              % refusal)
        arriving = None
    chap, roster, line, bosses, deploy_limit, labels = load_field(
        campaign, ch, leveled=arriving is not None)
    guests = fixed_roster_careers(chap)     # a fixed-roster chapter fields its guests, not us
    if guests:
        roster, deploy_limit = [c[0] for c in guests.values()], len(guests)
    num = chap.get('chapter_number')
    bar = '=' * 80
    print(bar)
    print('CH%s "%s" -- difficulty / vanilla parity   [STATIC proxy -- playtest is arbiter]'
          % (num, chap.get('title', ch)))
    print('  difficulty mode: %s'
          % ('%s (both sides shifted by their own chapter\'s numbers)' % mode.upper()
             if mode else 'AUTHORED TABLE (unshifted -- the level each side DECLARES)'))
    print(bar)
    if chap.get('status') == 'planned':
        print('** PLANNED chapter -- brainstorm SEED, NOT authoritative. The enemy roster/levels'
              '\n   below are ungrounded and will be re-grounded against vanilla + party data when'
              '\n   this slice is built; treat the numbers as a sketch, not a parity reading. **\n')
    print('Field: deploy %d of %d cast   Enemies: %s' % (deploy_limit, len(roster),
                                                          '; '.join(labels)))

    ours_lv = {uid: lv for uid, (_j, lv) in arriving['party'].items()} if arriving else {}
    ours_careers = (_party_careers(campaign, arriving['party']) if arriving
                    else {u.name: [u] for u in roster})
    if guests:
        ours_careers = guests
        ours_lv = {pu['id']: pu.get('level', 1) for pu in chap.get('player_units') or []}
    profiles = {uid: dice_profile(c, line, bosses) for uid, c in ours_careers.items()}
    _print_cast('OUR CAST, AS IT ARRIVES (class base + donor line, grown to the exp model\'s '
                'typical level)', roster, ours_lv, line, profiles)

    field = _best_field(roster, line, deploy_limit)
    m = _metrics(field, profiles)
    print('\n-- PARTY (best %d fielded: %s) %s' % (
        deploy_limit, ', '.join(u.name for u in field), '-' * 12))
    _print_metrics('', field, m, bosses)

    print('\n-- LORD x TEAM SWEEP (each candidate forced-deployed as the must-survive lord; '
          'median lines) --')
    for r in lord_team_sweep(roster, line, bosses, deploy_limit):
        boss = (' boss %s' % _fmt_rounds(r['carry_rounds'])) if 'carry_rounds' in r else ''
        print('  lord=%-11s thru %.2f  dura %.1f%s   team[%s]'
              % (r['lord'].name, r['throughput'], r['min_durability'], boss,
                 ', '.join(u.name for u in r['team'])))

    ref = chap.get('parity_reference')
    vanilla_lv = arriving['vanilla'] if arriving else None
    roster_van = vanilla_party(ref, vanilla_lv)
    if roster_van:
        van_profiles = {name: dice_profile(c, line, bosses)
                        for name, c in vanilla_party_careers(ref, vanilla_lv).items()}
        _print_cast('VANILLA %s PARTY, AS IT ARRIVES (every recruit so far, its own exp history)'
                    % ref, roster_van,
                    {_ally_name(k): v for k, v in (vanilla_lv or {}).items()},
                    line, van_profiles)
        van = _best_field(roster_van, line, deploy_limit)
        vm = _metrics(van, van_profiles)
        print('\n-- VANILLA Ch%s PARITY DELTA (best %d of each arriving party; averages over '
              'the dice, bad luck in brackets) ' % (num, deploy_limit) + '-' * 4)
        print('  vanilla (%s):' % '/'.join(u.name for u in van))
        _print_metrics('  ', van, vm, bosses)
        print('  ours (best %d), average delta: thru %+.2f · dura(min) %s%s'
              % (deploy_limit, m['throughput'][0] - vm['throughput'][0],
                 _fmt_dura_delta(m['min_durability'][0], vm['min_durability'][0]),
                 ' · carry %s' % _fmt_dura_delta(m['carry'][0], vm['carry'][0])
                 if 'carry' in m and 'carry' in vm else ''))
    else:
        print('\n(no vanilla reference field for Ch%s (parity_reference=%r) -- delta skipped)'
              % (num, ref))

    _print_pressure(_chapter_pressure(chap, campaign=campaign))
    print_role_findings(chap, chap.get('parity_reference'), campaign)  # authored table
    _print_economy(chap)
    _print_dynamics(chap)
    import timeline                         # timeline imports this module (via danger_map)
    t = timeline.chapter_timeline(chap, campaign, mode=mode)
    if t is not None:
        timeline.print_timeline(t, chap.get('parity_reference'))


def _chapter_pressure(chap, band=0.25, mode=None, campaign='rime-of-the-frostmaiden'):
    """Enemy-pressure parity for one loaded chapter dict: our force vs its parity_reference's
    vanilla force, threat + clear-load, with a verdict. `vanilla` is None when the reference
    isn't curated yet (#48 registry).

    The instrument is instrument v2 (#430 step 2b, `chapter_matchup`): each force against the
    party that meets it. `instrument` says which one graded the row; 'yardstick' -- every
    force against one fixed swordsman -- remains only for a twin off VANILLA_CHAIN, whose
    party is not simulated.

    `mode` grades a DIFFICULTY MODE instead of the authored table (#303). Each side is
    shifted by its own chapter's numbers -- ours from the YAML `difficulty:` block, the
    reference's from vanilla chapter_settings -- so a mode read still compares two tuned
    tables. None (the default) is the authored table, which is what every parity verdict
    before #303 graded; the difference matters because a chapter whose normal malus is
    non-zero ships a force the authored read never describes."""
    deploy_cap = chapter_deploy_limit(chap, len(ROSTER))
    shifts = inject.chapter_settings.chapter_difficulty_shifts(chap) if mode else None
    ours_force = chapter_enemy_force(chap, mode=mode, shifts=shifts)
    ours = enemy_pressure(ours_force, deploy_cap)
    ref = chap.get('parity_reference')
    van = vanilla_enemies(ref, mode=mode)
    out = {'reference': ref, 'deploy_cap': deploy_cap, 'ours': ours, 'mode': mode,
           'n_ours': len(ours_force), 'vanilla': None, 'mirror': mirror_share(chap),
           'dropped': unmodeled_enemies(chap)}
    out['instrument'] = 'yardstick'
    if van is not None:
        out['vanilla'] = enemy_pressure(van, deploy_cap)
        out['n_vanilla'] = len(van)
        out['solo'] = solo_contributors(chap, ref, deploy_cap)
        matchup = chapter_matchup(chap, campaign, mode=mode)
        if matchup is not None:
            out.update(instrument='party', matchup=matchup,
                       ours=(matchup['ours']['threat'], matchup['ours']['clear']),
                       vanilla=(matchup['vanilla']['threat'], matchup['vanilla']['clear']))
        out['verdict'] = pressure_verdict(out['ours'], out['vanilla'], band)
    return out


def fixed_roster_careers(chap):
    """{unit: [Combatant]} for a fixed-roster chapter's `player_units` (ch00's guests), or {}
    for a chapter the party deploys into. The prologue's injector writes each guest slot's
    personal line from its `twin:` (`inject.stats.guest_personal_line`), and its UnitDefinition
    carries no `.autolevel` (`_prologue_roster_blocks`), so a guest fights at class base plus
    that line at any level: one career, no growth."""
    out = {}
    for pu in chap.get('player_units') or []:
        class_enum = _enemy_class_enum(pu['class'])
        base = _class_base(class_enum)
        line = inject.stats.guest_personal_line(pu, class_enum)
        stats = {f: base.get(f, 0) + line.get(f, 0) for f in inject.stats.BASE_FIELDS}
        out[pu['id']] = [_stats_to_combatant(pu['id'], stats,
                                             _weapon_for(pu.get('inventory')),
                                             CLASS_TAGS.get(class_enum, frozenset()))]
    return out


def chapter_matchup(chap, campaign, mode=None):
    """The headline parity ratio (#430 step 2b): (our force vs our arriving party) /
    (the twin's force vs the twin's arriving party), threat and clear-load.

    None for a twin off VANILLA_CHAIN (ch08 -> FE8 Ch13: vanilla's party there is not
    simulated), or when the exp model refuses to price our party -- the caller falls back
    to the fixed YARDSTICK and says so."""
    ref = chap.get('parity_reference')
    if ref not in VANILLA_CHAIN:
        return None
    # Keyed on the chapter's CONTENT, not its id: a test or canary that doctors a chapter
    # dict must not be served the undoctored reading.
    key = (campaign, mode, json.dumps(chap, sort_keys=True, default=str))
    if key not in _MATCHUPS:
        _MATCHUPS[key] = _chapter_matchup(chap, campaign, mode)
    return _MATCHUPS[key]


_MATCHUPS = {}


def _chapter_matchup(chap, campaign, mode):
    fields = arriving_fields(chap, campaign, mode)
    if fields is None:
        return None
    ours = party_matchup(fields['our_force'], fields['our_field'])
    van = party_matchup(fields['van_force'], fields['van_field'])
    # The twin's force against OUR party splits the headline in two: the force effect is
    # what authoring controls, the party effect is what the party brings (#430 step 3).
    cross = party_matchup(fields['van_force'], fields['our_field'])

    def ratio(a, b, key):
        return a[key] / b[key] if b[key] else float('inf')
    return {'ours': ours, 'vanilla': van,
            'field': (list(fields['our_field']), list(fields['van_field'])),
            'threat_ratio': ratio(ours, van, 'threat'), 'load_ratio': ratio(ours, van, 'clear'),
            'force': (ratio(ours, cross, 'threat'), ratio(ours, cross, 'clear')),
            'party': (ratio(cross, van, 'threat'), ratio(cross, van, 'clear')),
            'cross': cross,
            'lines': {m: _median_combatant(c) for m, c in fields['our_field'].items()}}


def arriving_fields(chap, campaign, mode=None):
    """Both sides of a parity read: each force as [(Combatant, combat-weight table)] and the
    party each side fields against it, {unit: [Combatant]} over the careers. None for a twin
    off VANILLA_CHAIN or a party the exp model cannot price -- `chapter_matchup`'s fallback."""
    import exp_curve                        # exp_curve imports this module
    ref = chap.get('parity_reference')
    if ref not in VANILLA_CHAIN:
        return None
    try:
        arriving = exp_curve.entering(campaign, int(chap['chapter_number']), ref)
    except ValueError:
        return None
    if not arriving['party'] or arriving['vanilla'] is None:
        return None
    cap = chapter_deploy_limit(chap, len(ROSTER))
    shifts = inject.chapter_settings.chapter_difficulty_shifts(chap) if mode else None
    our_force = chapter_enemy_bodies(chap, mode=mode, shifts=shifts)
    van_force = [(u, ai_target.combat_weight_table(ai))
                 for u, ai in vanilla_enemy_bodies(ref, mode)]
    our_field = fielded_careers(
        fixed_roster_careers(chap) or _party_careers(campaign, arriving['party']),
        [u for u, _t in our_force], cap)
    van_field = fielded_careers(vanilla_party_careers(ref, arriving['vanilla']),
                                [u for u, _t in van_force], cap)
    return {'our_force': our_force, 'our_field': our_field,
            'van_force': van_force, 'van_field': van_field}


def planned_target(chap, campaign):
    """The parity target a `status: planned` chapter must hit: its twin's force against the
    twin's arriving party, as {'threat', 'clear'}. None off VANILLA_CHAIN or where the exp
    model cannot place the chapter."""
    import exp_curve                        # exp_curve imports this module
    ref = chap.get('parity_reference')
    if ref not in VANILLA_CHAIN:
        return None
    try:
        levels = exp_curve.entering(campaign, int(chap['chapter_number']), ref)['vanilla']
    except ValueError:
        return None
    if levels is None:
        return None
    force = [(u, ai_target.combat_weight_table(ai)) for u, ai in vanilla_enemy_bodies(ref)]
    field = fielded_careers(vanilla_party_careers(ref, levels), [u for u, _t in force],
                            chapter_deploy_limit(chap, len(ROSTER)))
    return party_matchup(force, field)


def _warn_dropped(dropped, indent='  '):
    """Emit a warning per enemy the metric couldn't model (no FE-base weapon). A dropped
    boss means the verdict is unreliable for that chapter -- say so loudly (#51)."""
    for d in dropped:
        tag = '!! BOSS DROPPED -- verdict UNRELIABLE' if d['is_boss'] else 'dropped'
        print('%sWARN: %s (%s -- no modeled weapon; add fe_base in its YAML inventory)'
              % (indent, d['id'], tag))


def _heaviest(side, top=3):
    """The units carrying the most of a side's clear-load, bodies of one unit summed, with
    their share of it. A named vanilla body reads by its charIndex (`...#3[CHARACTER_SAAR]`);
    a generic's charIndex is a bare pid, so it reads by the weapon it carries."""
    load = collections.Counter()
    for name, _t, clear, weapon in side['per_enemy']:
        label = name[name.index('[') + 1:-1] if '[' in name else name
        load['%s generic' % weapon if label.startswith('0x') else label] += clear
    total = sum(load.values()) or 1.0
    return ', '.join('%s %.0f%%' % (n.replace('CHARACTER_', '').lower(), 100 * c / total)
                     for n, c in load.most_common(top))


def _print_pressure(p):
    ot, ol = p['ours']
    print('\n-- ENEMY-PRESSURE PARITY (vs %s) ' % (p['reference'] or '?') + '-' * 30)
    _warn_dropped(p['dropped'])
    if p['vanilla'] is None:
        print('  ours (%d enemies / %d slots): threat/slot %.1f · clear-load/slot %.1f'
              % (p['n_ours'], p['deploy_cap'], ot, ol))
        print('  (no curated vanilla force for %r yet -- parity delta skipped)'
              % p['reference'])
        return
    vt, vl = p['vanilla']
    v = p['verdict']
    if p['instrument'] == 'party':
        mu = p['matchup']
        ours_field, van_field = mu['field']
        print('  each force against the party that meets it (instrument v2, #430): threat = '
              'damage/round\n  on the unit FE8\'s AI targets, per unit fielded · clear-load = '
              'party-rounds to clear')
        print('  vanilla %-11s (%2d enemies vs %s): threat %4.1f · clear-load %4.1f'
              % (p['reference'], p['n_vanilla'], '/'.join(van_field), vt, vl))
        print('  ours    %-11s (%2d enemies vs %s): threat %4.1f (x%.2f %s) · '
              'clear-load %4.1f (x%.2f %s)'
              % ('', p['n_ours'], '/'.join(ours_field), ot, v['threat_ratio'], v['threat'],
                 ol, v['load_ratio'], v['load']))
        print('  split: force x%.2f / x%.2f (our force vs the twin\'s, both against our party)'
              ' · party x%.2f / x%.2f\n         (our party vs vanilla\'s, both against the '
              'twin\'s force) -- threat / clear-load' % (mu['force'] + mu['party']))
        for tag, side in (('ours', mu['ours']), ('vanilla', mu['vanilla'])):
            print('  heaviest (%s): %s' % (tag, _heaviest(side)))
    else:
        print('  vanilla %-11s (%2d enemies): threat/slot %4.1f · clear-load/slot %4.1f'
              % (p['reference'], p['n_vanilla'], vt, vl))
        print('  ours    %-11s (%2d enemies): threat/slot %4.1f (x%.2f %s) · '
              'clear-load/slot %4.1f (x%.2f %s)'
              % ('', p['n_ours'], ot, v['threat_ratio'], v['threat'],
                 ol, v['load_ratio'], v['load']))
        print('  (fixed YARDSTICK -- %s)'
              % ('%s is off VANILLA_CHAIN, so its party is not simulated' % p['reference']
                 if p['reference'] not in VANILLA_CHAIN else
                 'the exp model could not field an arriving party for this chapter'))
    m = p.get('mirror')
    if m:
        # WHAT THE RATIOS ABOVE CANNOT SAY (#367): a ratio is an aggregate over stats, so a
        # transcribed force and a composed one that lands on the same pressure read alike.
        print('  mirror: %.0f%% of %s\'s force reproduced exactly (%d of %d bodies, class '
              '+ level)' % (m['pct'], p['reference'], m['shared'], m['twin']))
        if m['pct'] >= 90:
            print('          -- at this share the two forces are near-identical, so the ratio '
                  'measures the\n             PARTIES that meet them, not the force.' if
                  p['instrument'] == 'party' else
                  '          -- at this share the verdict is largely a CHECKSUM on the donor '
                  'pipeline,\n             not evidence about the chapter.')
    print('  verdict: %s' % ('PARITY (within band)' if v['verdict'] == 'OK'
                             else 'OFF-PARITY -- threat %s, clear-load %s' % (v['threat'], v['load'])))
    for line in p.get('solo') or []:
        print('  %s' % line)


# ── Terrain (#25) ───────────────────────────────────────────────────────────────
# Every metric here already takes a `terrain_avoid`; nothing ever passed one, so every
# reading silently assumed open ground. FE8's own numbers (bmbattle.c):
#     battleAvoidRate = battleSpeed*2 + terrainAvoid + lck
#     battleDefense   = terrainDefense + unit.def
# and the bonuses are a PER-CLASS lookup (fliers ignore forests) indexed by terrain id:
#     gBmMapTerrain[y][x] = gTilesetTerrainLookup[gBmMapBaseTiles[y][x] >> 2]
# We model the Common (foot) tables -- the yardstick is a foot unit. All read from the
# decomp at HEAD, so this is ROM-free: for a 1:1 retile the vanilla layout IS our layout.

_TERRAIN_CACHE = {}


def _terrain_tables():
    """(id->name, name->avoid, name->defense) parsed from the decomp at HEAD."""
    if 'tables' not in _TERRAIN_CACHE:
        ids = {int(v, 16): k for k, v in re.findall(
            r'(TERRAIN_\w+)\s*=\s*(0x[0-9A-Fa-f]+)',
            inject.decomp.vanilla_decomp_text('include/constants/terrains.h'))}
        text = inject.decomp.vanilla_decomp_text('src/data_terrains.c')

        def table(name):
            i = text.find('s8 %s[] = {' % name)
            return {k: int(v) for k, v in re.findall(
                r'\[(TERRAIN_\w+)\]\s*=\s*(-?\d+)', text[i:text.find('};', i)])}
        _TERRAIN_CACHE['tables'] = (ids, table('TerrainTable_Avo_Common'),
                                    table('TerrainTable_Def_Common'))
    return _TERRAIN_CACHE['tables']


def terrain_bonus(terrain_name):
    """(avoid, defense) a foot unit gains on `terrain_name` (e.g. 'TERRAIN_THRONE')."""
    _ids, avo, dfn = _terrain_tables()
    key = str(terrain_name or '').upper()
    if key and not key.startswith('TERRAIN_'):
        key = 'TERRAIN_' + key
    return avo.get(key, 0), dfn.get(key, 0)


def vanilla_terrain_at(layout_name, x, y):
    """The TERRAIN_* name of a tile on a vanilla map layout, or None if unreadable."""
    try:
        import map_tileset_tool as mtt
        key = ('layout', layout_name)
        if key not in _TERRAIN_CACHE:
            _TERRAIN_CACHE[key] = mtt.vanilla_layout_data(inject.decomp.SUBMODULE, layout_name)
        w, h, cells, terrain = _TERRAIN_CACHE[key]
        if not (0 <= x < w and 0 <= y < h):
            return None
        ids, _avo, _dfn = _terrain_tables()
        return ids.get(terrain[cells[y * w + x]])
    except Exception:                        # missing layout/tileset -- degrade to open ground
        return None


def on_terrain(combatant, terrain_name):
    """`combatant` as it fights while standing on `terrain_name`: terrain Defense folded
    into df (FE8 adds it to battleDefense). The avoid half is passed separately to the
    metrics, which already accept a `terrain_avoid`."""
    avo, dfn = terrain_bonus(terrain_name)
    return dataclasses.replace(combatant, df=combatant.df + dfn), avo


# ── Per-unit ROLE check (#25 post-mortem) ───────────────────────────────────────
# The parity verdict above is an AGGREGATE: threat/slot sums the whole force and divides by
# the deploy cap, so a single monstrous unit dissolves into the average and a boss that dies
# in three rounds never shows up at all. ch05 shipped a "PARITY (within band)" force in which
# the white moose out-threatened the boss 1.7x and sat 2.2x above the vanilla twin's scariest
# unit -- invisible to every number we printed. These checks compare the EXTREMES unit-to-unit
# instead, which is what catches a role inversion.

def unit_real_article(enemy_def, combatant):
    """`combatant` as it actually fights: class base PLUS its personal line, if it has one.

    A named unit's personal line is most of what makes it named -- FE8 adds those
    CharacterData values on top of the deployed class bases -- and it reaches our units from
    THREE places:
      * `personal:` on the chapter YAML, for a raw-pid enemy authored there (Ravisin);
      * BASE_DONOR, for a CAST member deployed hostile, whose donor's line is written into its
        character slot by the build (Sahnar rides Joshua's, Lupin rides Franz's);
      * ENEMY_BASE_SLOT, for an enemy deployed on a VANILLA character slot, which keeps that
        slot's own line because nothing patches it (ch02's Halvar rides Bazba's).
    Reading only the first is why ch05's red Myrmidon measured 6.2 against the 21.4 she
    actually fights at; missing the third is why ch02's boss measured 1.2 rounds against a
    3.6 bar while the ROM had been fighting it at 3.6 the whole time (#284). Units with none
    of the three are unchanged -- which is the honest answer for a raw pid, whose
    CharacterData gap really is all zeros.

    The sources do not stack: an authored `personal:` is the explicit article and wins, or a
    unit riding a named slot would count its bases twice.
    """
    personal = enemy_def.get('personal')
    if not personal:
        uid = enemy_def.get('id')
        donor = inject.stats.BASE_DONOR.get(uid) or inject.cast.ENEMY_BASE_SLOT.get(uid)
        if donor:
            personal = vanilla_personal_line(donor)
    return _apply_personal(combatant, personal) if personal else combatant


def vanilla_threat_ceiling(parity_ref):
    """The twin's HIGHEST single-unit threat, its named units included at full strength.

    The outlier bar used to be the max over `vanilla_enemies()`, which projects every unit off
    class base -- so it excluded the twin's own bosses and recruits (FE8 Ch5: 6.3, a generic
    Soldier, while Joshua actually fights at 21.4). Measuring OUR named units against a bar
    made only of THEIR generics flagged every named unit we ever field.
    """
    van = vanilla_enemies(parity_ref)
    if not van:
        return 0.0
    best = max(fc.damage_per_round(e, YARDSTICK) for e in van)
    for _name, c in vanilla_named_bosses(parity_ref, with_personal=True):
        best = max(best, fc.damage_per_round(c, YARDSTICK))
    return best


def solo_contributors(chap, parity_ref, deploy_cap, floor=1.0, share=0.10):
    """Name any SINGLE unit carrying an outsized share of the force's threat.

    Information, not a threshold verdict -- there is no honest bar to set here, and the two
    obvious candidates were both tried and rejected: a unit's SHARE of the total barely moves
    when you strengthen it (it inflates the denominator too -- ch05 read 16.4% with the shipped
    moose and 17.2% with the rejected one), and leave-one-out by unit id just names whichever
    group has the biggest `count`.

    What it prints is the sentence that had to be computed by hand to catch this: ch05 measured
    "PARITY (within band)" at x1.20 while the moose ALONE was the whole overage -- x0.97 without
    it. `threat/slot` sums the force and divides by the deploy cap, so one unit's 24.6 becomes
    +2.7 a slot and disappears under a +-25% band. Only `count: 1` units are considered: a big
    number from an 8-strong line is a composition choice, not a single monster.

    Tightening the band itself belongs with the aggregate rework (#285).
    """
    van = vanilla_enemies(parity_ref)
    if not van:
        return []
    cap = max(1, deploy_cap)
    vt = sum(fc.damage_per_round(e, YARDSTICK) for e in van) / cap
    if vt <= 0:
        return []
    # Built from the SAME force builder as the verdict this note is printed under (#285) -- a
    # note computed on a different footing than the number it explains is worse than none.
    rows = [(ed.get('id') or u.name, _entry_body_count(ed),
             fc.damage_per_round(u, YARDSTICK)) for ed, u in chapter_units(chap)]
    total = sum(t for _u, _n, t in rows)
    full = (total / cap) / vt
    if full <= floor:
        return []
    solo = [(t, uid) for uid, count, t in {(u, n, t) for u, n, t in rows}
            if count == 1 and t / total >= share]
    if not solo:
        return []
    t, uid = max(solo)          # the biggest only -- one line per chapter, not a tail
    without = ((total - t) / cap) / vt
    return ['NOTE: %s alone is %.0f%% of this force\'s threat -- without it the chapter is '
            'x%.2f, not x%.2f. One unit inside a +-25%% band can BE the overage.'
            % (uid, 100 * t / total, without, full)]


# Where a chapter's red force is authored. ch02 puts two of its nine under
# `reinforcements:`, and a guard reading only `enemy_units:` would grade a chapter that
# does not ship.
AI_ROSTER_KEYS = inject.raw_pids.ENEMY_ROSTER_KEYS   # the AI guard was this roster's first reader


def _donor_specs(enemy):
    """An entry's `donor:` -> one spec per position it places.

    A bare `[x, y]` is ONE coordinate covering every position; a list whose ELEMENTS are
    themselves specs is one donor per position, in order. The distinction is by element
    type, because `donor: [11, 6]` and `donor: [[11, 6], [13, 7]]` must not be confused --
    reading the first as two donors would make every single-donor entry per-position."""
    donor = enemy.get('donor')
    if isinstance(donor, list) and donor and all(isinstance(d, (list, dict)) for d in donor):
        return donor
    return None


def enemy_ai_bytes(chap, enemy, index=0):
    """The 4 AI bytes one of our enemies emits: its vanilla donor's, or a declared override.

    This is the whole of #335. Our chapters pick a vanilla twin so their difficulty is
    grounded rather than guessed, and we derive that twin's classes, levels, inventories and
    drops from its `UnitDefinition` structs -- but the `.ai` field of those same structs was
    never read, and got authored by feel instead. It measured fine, because #48 computes
    threat from stats and weapons and AI is behavioural. Borrowing the donor's bytes closes
    that by construction: there is no vocabulary in the middle to mistranslate.

    `donor:` may be a single spec covering the whole entry, or one spec per position where
    vanilla varies within a group -- ch04's four mogalls stand on vanilla's four mogall tiles
    and those run three different AIs.

    An `ai_override:` is how a chapter says it means to differ -- our map changed the
    dynamics, or we field a unit vanilla does not. It carries the vector and a `why`, and it
    may stand alone where no single donor applies. The `why` is REQUIRED here, not merely
    reported by the curve gate: that gate only reaches balance_locked chapters, so an
    override authored in a chapter still being written could skip its reason entirely. Neither donor nor override RAISES: a
    default is exactly how ch00 shipped an `ai_pattern` its injector never read."""
    override = enemy.get('ai_override')
    if override:
        if not str(override.get('why') or '').strip():
            raise ValueError('enemy %r declares an `ai_override:` with no `why` -- an '
                             'undeclared reason is a silenced guard, not a decision'
                             % enemy.get('id'))
        return ai_bytes(override.get('ai'))
    per_position = _donor_specs(enemy)
    if per_position is not None:
        if index >= len(per_position):
            raise ValueError('enemy %r places %d unit(s) but lists %d donor(s), so position '
                             '%d is not grounded in anything'
                             % (enemy.get('id'), len(enemy.get('positions') or []),
                                len(per_position), index))
        return resolve_donor(chap.get('parity_reference'), per_position[index])['ai']
    if enemy.get('donor') is not None:
        return resolve_donor(chap.get('parity_reference'), enemy['donor'])['ai']
    raise ValueError('enemy %r declares neither a `donor:` nor an `ai_override:`, so its AI '
                     'is not grounded in anything' % enemy.get('id'))


def ai_donor_findings(chap):
    """#335's guard: every enemy's AI is borrowed from a vanilla donor or declared as a
    deliberate departure. Returns a list of strings (empty == clean), the same contract
    role_findings() uses so the parity gate can read both.

    Silent on an uncurated twin -- there is nothing to borrow from, and that is a
    `parity_reference` gap rather than an AI one."""
    ref = chap.get('parity_reference')
    if PARITY_REFERENCE_UDEFS.get(ref) is None:
        return []
    findings = []
    for key in AI_ROSTER_KEYS:
        for enemy in chap.get(key) or []:
            if not isinstance(enemy, dict):
                continue
            override = enemy.get('ai_override')
            if override and not override.get('why'):
                findings.append('%s: ai_override has no `why` -- an undeclared reason is a '
                                'silenced guard, not a decision' % enemy.get('id'))
            for index in range(max(1, len(enemy.get('positions') or []))):
                try:
                    enemy_ai_bytes(chap, enemy, index)
                except ValueError as error:
                    findings.append('%s: %s' % (enemy.get('id'), error))
                    break
    return findings


def role_findings(chap, parity_ref, campaign=None):
    """Per-unit role warnings: outlier threat vs the twin's ceiling, and a boss that is not
    the chapter's real centre of gravity. Returns a list of strings (empty == clean).

    With a `campaign` and a twin the party model reaches, every arm reads both forces against
    the party that meets ours (`_role_findings_vs_party`). Otherwise it falls back to the fixed
    YARDSTICK, as the aggregate does off VANILLA_CHAIN."""
    if campaign and parity_ref in VANILLA_CHAIN:
        matchup = chapter_matchup(chap, campaign)
        if matchup is not None:
            return _role_findings_vs_party(chap, parity_ref, matchup)
    van = vanilla_enemies(parity_ref)
    if not van:
        return []
    ours, personal_by_id = [], {}
    for ed in chapter_roster_entries(chap):
        if ed.get('personal'):
            personal_by_id[ed.get('id')] = ed['personal']
        # THREAT comparisons run on the real article (class base + personal line), the same
        # footing the durability check below has always used. The AGGREGATE metric stays
        # class-base on both sides -- that is a different question and a fair one.
        # per-unit questions, so one row per unit TYPE: whether a unit's threat is an
        # outlier does not depend on how many copies of it the map holds, and counting
        # copies made a `count: 4` boss entry read as four bosses.
        for c in _entry_combatants(ed, real_article=True, drop_staff=False, distinct=True):
            ours.append((ed.get('id') or c.name, bool(ed.get('is_boss')), c,
                         bool(ed.get('convertible')), ed.get('tile_terrain')))
    if not ours:
        return []
    out = []
    van_threat = vanilla_threat_ceiling(parity_ref)
    # Floored (#285): vanilla_enemies now carries personal lines, so the twin's tankiest unit can
    # be undentable -- FE8 Ch5 went 12.9 -> inf. This is the fallback bar used when the twin has
    # no named boss, and an `inf` bar would flag every boss we ever field as folding too fast.
    van_tank = max(metric_rounds_to_kill(e) for e in van)
    for uid, _is_boss, c, conv, _tile in ours:
        t = fc.damage_per_round(c, YARDSTICK)
        if van_threat > 0 and t > van_threat * 1.25:
            out.append('%s threat %.1f is %.1fx the %s ceiling (%.1f)%s'
                       % (uid, t, t / van_threat, parity_ref, van_threat,
                          ' -- convertible, so the player can neutralize it without fighting'
                          if conv else ' -- no vanilla unit hits that hard'))
    bosses = [(uid, c, tile) for uid, is_boss, c, _, tile in ours if is_boss]
    # A convertible is recruited/neutralized rather than ground down, so it out-hitting the
    # boss is a deliberate "avoid me" hazard, not a role inversion -- don't flag it as one.
    line = [(uid, c) for uid, is_boss, c, conv, _ in ours if not is_boss and not conv]
    # Hoisted: the twin's bar is a property of the REFERENCE, not of our boss, and computing it
    # walks the decomp twice (once with personal lines, once without). Inside the loop that was
    # two full scans per boss for an answer that cannot change between iterations.
    bar_name, bar, bar_personal = vanilla_boss_bar(parity_ref)
    for uid, b, tile in bosses:
        bt = fc.damage_per_round(b, YARDSTICK)
        harder = [n for n, c in line if fc.damage_per_round(c, YARDSTICK) > bt]
        if harder:
            out.append('boss %s (threat %.1f) is out-threatened by %d non-boss unit(s): %s'
                       % (uid, bt, len(harder), ', '.join(harder[:4])))
        # Boss durability is measured boss-to-boss WITH personal lines on both sides (FE8's
        # own boss mechanism), on the tile each actually holds. The aggregate above stays
        # class-base-only; this is the one place the real article is compared.
        b_on, b_avo = on_terrain(b, tile)   # `b` is already the real article
        bk = fc.rounds_to_kill(YARDSTICK, b_on, b_avo)
        where = (' on %s (+%d avo/+%d def)' % ((tile,) + terrain_bonus(tile))) if tile else ''
        if bk == float('inf'):
            out.append('boss %s%s cannot be damaged by the parity yardstick at all -- '
                       'terrain and a personal line are stacking too far' % (uid, where))
        elif bar > 0 and bk < bar * 0.5:
            out.append("boss %s takes %.1f rounds to kill%s; %s's boss (%s) takes %.1f%s "
                       '-- the climax may fold too fast'
                       % (uid, bk, where, parity_ref, bar_name, bar,
                          '' if bar_personal else ' (class base; its own line is undentable here)'))
        elif not bar and van_tank > 0 and bk < van_tank * 0.5:
            out.append("boss %s takes %.1f rounds to kill%s; %s's tankiest unit takes %.1f -- "
                       'the climax may fold too fast' % (uid, bk, where, parity_ref, van_tank))
    # The census counts ENTRIES, not bodies: `distinct` splits one entry into a row per
    # declared level, and every row carries that entry's id -- so a boss authored
    # `levels: [19, 20]` would otherwise read as two bosses named the same thing. The
    # per-unit warnings above are deduped for the same reason.
    out.extend(_boss_census(n for n, _c, _t in bosses))
    return list(dict.fromkeys(out))


def _boss_census(ids):
    boss_ids = list(dict.fromkeys(ids))
    if len(boss_ids) > 1:
        return ['%d units flagged is_boss (%s) -- only the objective target should be a boss; '
                'use a miniboss/convertible role for the others'
                % (len(boss_ids), ', '.join(boss_ids))]
    return []


def _boss_durability_vs_party(entries, parity_ref, lines):
    """The durability arms on the party's median lines, in the yardstick's place. Read here
    rather than off the matchup, whose clear-load floors an undentable body to a finite chip
    read and stands every body on open ground: the throne and the wall are what these arms
    exist to catch (#284)."""
    import exp_curve                        # exp_curve imports this module
    inf = float('inf')

    def party_rounds(body, avoid=0):
        rate = sum(1.0 / r for r in (fc.rounds_to_kill(u, body, avoid)
                                     for u in lines if u.weapon is not None) if r != inf)
        return 1.0 / rate if rate else inf
    twin = [party_rounds(c) for n, c in vanilla_named_bosses(parity_ref, with_personal=True)
            if 'CA_BOSS' in exp_curve.character_attributes('CHARACTER_' + n.upper())]
    bar = max((r for r in twin if r != inf), default=0.0) or \
        max((r for r in map(party_rounds, vanilla_enemies(parity_ref) or []) if r != inf),
            default=0.0)
    out = []
    for ed in entries:
        if not ed.get('is_boss'):
            continue
        tile = ed.get('tile_terrain')
        where = (' on %s (+%d avo/+%d def)' % ((tile,) + terrain_bonus(tile))) if tile else ''
        for c in _entry_combatants(ed, real_article=True, drop_staff=False, distinct=True):
            body, avoid = on_terrain(c, tile)
            rounds = party_rounds(body, avoid)
            if rounds == inf:
                out.append('boss %s%s cannot be damaged by the party that meets it'
                           % (ed.get('id'), where))
            elif bar and rounds < bar * 0.5:
                out.append("boss %s takes %.2f party-rounds to kill%s; %s's boss takes %.2f "
                           'against the same party -- the climax may fold too fast'
                           % (ed.get('id'), rounds, where, parity_ref, bar))
    return out


def _role_findings_vs_party(chap, parity_ref, matchup):
    """The role check on instrument v2 (#430 step 6): our force and the twin's, BOTH met by our
    arriving party (the matchup's `cross` read), so each comparison isolates what authoring
    controls. Reading the twin against vanilla's own party would charge it for Lute's Res: the
    same Shaman with the same Flux hits ours for 31.3 and vanilla's for 19.6.

    Each arm asks the yardstick arm's question, relative to the twin rather than in absolute
    terms. A line unit out-hitting the boss is common in FE8 itself (Ch2's archer out-hits
    Bone), so an inversion is flagged only when ours runs past the twin's own by the band. The
    twin's boss is the body whose CHARACTER carries CA_BOSS, which is where FE8 records it."""
    import exp_curve                        # exp_curve imports this module
    band = 1.25
    entries = list(chapter_roster_entries(chap))
    boss_ids = {e.get('id') for e in entries if e.get('is_boss')}
    conv_ids = {e.get('id') for e in entries if e.get('convertible')}
    stem = PARITY_REFERENCE_STEM.get(parity_ref)
    van_conv = _vanilla_convertible_chars(stem) if stem else set()

    def char(name):
        return name[name.index('[') + 1:-1] if '[' in name else None

    def by_unit(rows, is_boss, is_conv):
        """{name: (max threat, min clear)} for the bosses and for the fought line."""
        bosses, line = {}, {}
        for name, threat, clear, _weapon in rows:
            if is_conv(name) and not is_boss(name):
                continue
            side = bosses if is_boss(name) else line
            t, c = side.get(name, (0.0, float('inf')))
            side[name] = (max(t, threat), min(c, clear))
        return bosses, line

    ours_b, ours_l = by_unit(matchup['ours']['per_enemy'],
                             lambda n: n in boss_ids, lambda n: n in conv_ids)
    van_b, van_l = by_unit(matchup['cross']['per_enemy'],
                           lambda n: 'CA_BOSS' in exp_curve.character_attributes(char(n)),
                           lambda n: char(n) in van_conv)
    out = []
    ceiling = max(t for _n, t, _c, _w in matchup['cross']['per_enemy'])
    for name, threat, _clear, _weapon in matchup['ours']['per_enemy']:
        if ceiling > 0 and threat > ceiling * band:
            out.append('%s threat %.1f is %.1fx the %s ceiling (%.1f) against the party that '
                       'meets it%s' % (name, threat, threat / ceiling, parity_ref, ceiling,
                                       ' -- convertible, so the player can neutralize it '
                                       'without fighting' if name in conv_ids else
                                       ' -- no vanilla unit hits that hard'))
    van_boss_t = max((t for t, _c in van_b.values()), default=0.0)
    van_line_t = max((t for t, _c in van_l.values()), default=0.0)
    van_ratio = van_line_t / van_boss_t if van_boss_t else 1.0
    for name, (threat, _clear) in ours_b.items():
        if threat > 0:
            harder = sorted(((t, n) for n, (t, _c) in ours_l.items()
                             if t > threat and t / threat > van_ratio * band), reverse=True)
            if harder:
                out.append('boss %s (threat %.1f) is out-threatened by %d non-boss unit(s): %s '
                           '-- %.2fx, where %s\'s line tops its boss at %.2fx'
                           % (name, threat, len(harder),
                              ', '.join('%s (%.1f)' % (n, t) for t, n in harder[:4]),
                              harder[0][0] / threat, parity_ref, van_ratio))
    out.extend(_boss_durability_vs_party(entries, parity_ref, list(matchup['lines'].values())))
    out.extend(_boss_census(e.get('id') for e in entries if e.get('is_boss')))
    return list(dict.fromkeys(out))


def print_role_findings(chap, parity_ref, campaign=None):
    findings = role_findings(chap, parity_ref, campaign)
    print('\n-- PER-UNIT ROLE CHECK (what the per-slot averages hide) ' + '-' * 12)
    if not findings:
        print('  clean -- no threat outliers, boss is the chapter\'s hardest hitter')
        return
    for f in findings:
        print('  WARN: %s' % f)


# ── Item-economy parity (#170) ──────────────────────────────────────────────────
# The vanilla twin's payout, read from HEAD via inject.decomp.vanilla_decomp_text -- NEVER the working
# tree, which the build injects our own chapters into (reading the tree by hand once had our
# ch03 chests reported as vanilla Ch4's). Same ground-truth discipline as the enemy rosters:
# chests + village/house gifts + shops + enemy drops, valued from data_items.c. (#170 shipped
# the first three; #176 added the drop channel -- a red unit flagged .itemDrop drops its last
# item; the curated Ch4/Ch5 twins carry none, but Ch2/Ch3/Ch6/Ch13 do.)

# parity_reference -> the decomp chapter file stem (shared by the economy #170 and the
# battlefield-dynamics #171 extractors -- both read that chapter's event data from HEAD).
PARITY_REFERENCE_STEM = {
    'FE8 Prologue': 'prologue', 'FE8 Ch1': 'ch1', 'FE8 Ch2': 'ch2', 'FE8 Ch3': 'ch3',
    'FE8 Ch4': 'ch4', 'FE8 Ch5': 'ch5', 'FE8 Ch6': 'ch6', 'FE8 Ch13': 'ch13a',
}

_ITEM_VALUES = None
_ITEM_IDS = None


def _item_gold_values():
    """ITEM_x enum -> buy gold (costPerUse * maxUses) from vanilla data_items.c (HEAD). A
    gem/booster's value is that product; sell is ~half. Cached (one decomp read)."""
    global _ITEM_VALUES
    if _ITEM_VALUES is None:
        text = inject.decomp.vanilla_decomp_text('src/data_items.c')
        _ITEM_VALUES = {}
        for m in re.finditer(r'\[(ITEM_\w+)\]\s*=\s*\{(.*?)\n\s*\},', text, re.S):
            body = m.group(2)
            cpu = re.search(r'\.costPerUse\s*=\s*(\d+)', body)
            uses = re.search(r'\.maxUses\s*=\s*(\d+)', body)
            _ITEM_VALUES[m.group(1)] = ((int(cpu.group(1)) if cpu else 0)
                                        * (int(uses.group(1)) if uses else 1))
    return _ITEM_VALUES


def item_gold_value(item_enum):
    """Buy-gold of a vanilla ITEM_x enum (0 if unknown or valueless)."""
    return _item_gold_values().get(item_enum, 0)


def _item_id_to_enum():
    """Numeric item id -> ITEM_x enum, from vanilla constants/items.h (HEAD). Village/house
    GIVEITEMTO gifts name their item by numeric id (SVAL), so we resolve id -> enum -> value."""
    global _ITEM_IDS
    if _ITEM_IDS is None:
        text = inject.decomp.vanilla_decomp_text('include/constants/items.h')
        _ITEM_IDS = {}
        val = -1
        for line in text.splitlines():
            s = line.strip()
            if not s.startswith('ITEM_'):
                continue
            m = re.match(r'(ITEM_\w+)\s*(?:=\s*(0x[0-9a-fA-F]+|\d+))?', s)
            if not m:
                continue
            val = int(m.group(2), 0) if m.group(2) else val + 1
            _ITEM_IDS[val] = m.group(1)
    return _ITEM_IDS


def _shoplist_items(shoplist_text, list_sym):
    """The ITEM_x enums a ShopList_ array stocks (ITEM_NONE terminator dropped)."""
    m = re.search(re.escape(list_sym) + r'\[\]\s*=\s*\{(.*?)\}', shoplist_text, re.S)
    if not m:
        return []
    return [it for it in re.findall(r'ITEM_\w+', m.group(1)) if it != 'ITEM_NONE']


def _gift_items(eventscript_text):
    """Every item handed out in the chapter script: for each GIVEITEMTO, the nearest preceding
    SVAL(EVT_SLOT_3, <id>) sets its item. Catches village/house gifts AND conditional/clear
    rewards given outside a Village macro (e.g. Ch5's all-villages-saved Guiding Ring, handed to
    the leader). Returns the ITEM_x enums. An event village that only spawns a unit (SVAL to a
    different slot, no GIVEITEMTO) contributes nothing, as it should."""
    id2e = _item_id_to_enum()
    out = []
    for g in re.finditer(r'GIVEITEMTO', eventscript_text):
        pre = re.findall(r'SVAL\(EVT_SLOT_3,\s*(0x[0-9a-fA-F]+|\d+)\)',
                         eventscript_text[:g.start()])
        if pre:
            enum = id2e.get(int(pre[-1], 0))
            if enum:
                out.append(enum)
    return out


def vanilla_drops(parity_ref):
    """The vanilla twin's enemy DROPS, read from HEAD: for each red unit flagged `.itemDrop`
    in the chapter's curated UnitDefinition arrays, its LAST item (US_DROP_ITEM drops the final
    inventory slot -- statscreen.c:726), valued in buy-gold. None if the reference isn't curated;
    [] if it carries no drops (the Ch4/Ch5 lock twins). The channel #170 v1 skipped (#176)."""
    spec = PARITY_REFERENCE_UDEFS.get(parity_ref)
    if spec is None:
        return None
    relpath, arrays = spec
    text = inject.decomp.vanilla_decomp_text(relpath)
    out = []
    for array_name in arrays:
        for d in vanilla_unit_defs(text, array_name):
            if d['allegiance'] != 'FACTION_ID_RED' or not d['itemDrop'] or not d['items']:
                continue
            item = d['items'][-1]
            out.append((item, item_gold_value(item)))
    return out


def vanilla_economy(parity_ref):
    """The vanilla twin's item economy, read from HEAD: chests, gifts (villages/houses/clear
    rewards), shops, and enemy drops, each valued in buy-gold. None if the reference has no
    mapped economy source (#170/#176). Delivery context (# of villages/houses) is kept for the
    vehicle story."""
    stem = PARITY_REFERENCE_STEM.get(parity_ref)
    if stem is None:
        return None
    info = inject.decomp.vanilla_decomp_text('src/events/%s-eventinfo.h' % stem)
    script = inject.decomp.vanilla_decomp_text('src/events/%s-eventscript.h' % stem)
    shoptext = inject.decomp.vanilla_decomp_text('src/events_shoplist.c')
    chests = [(it, item_gold_value(it)) for it in re.findall(r'Chest\((ITEM_\w+)', info)]
    gifts = [(it, item_gold_value(it)) for it in _gift_items(script)]
    drops = vanilla_drops(parity_ref) or []
    shops = [(sym, _shoplist_items(shoptext, sym))
             for sym in re.findall(r'(?:Armory|Vendor)\(\s*(\w+)', info)]
    total = sum(v for _, v in chests) + sum(v for _, v in gifts) + sum(v for _, v in drops)
    return {'reference': parity_ref, 'chests': chests, 'gifts': gifts, 'drops': drops,
            'shops': shops, 'n_villages': len(re.findall(r'Village\(', info)),
            'n_houses': len(re.findall(r'House\(', info)), 'total_gold': total}


def chapter_economy(chap):
    """Our chapter's declared economy from its YAML: explicit gold + item ids by vehicle.
    Campaign item ids aren't valued here (they aren't vanilla enums) -- the vanilla bar is the
    gold target; ours is listed alongside for a same-glance compare.

    Every DELIVERY VEHICLE we ship has to be listed here, not just the vanilla-shaped ones. ch06
    hands out FE8 Ch6's own two rewards -- an Antitoxin and the Orion's Bolt gated on keeping
    everyone alive -- through a Talk on a rescue boat and a save-them-all clear bonus, because it
    has no villages at all. Counting only villages/chests/drops/post-chapter gold scored it at
    400g against the twin's ~15,240g and reported a faithful chapter as an impoverished one
    (#26). A vehicle the reader does not know reads as a reward we never gave.
    """
    gold = 0
    gifts, chests, drops = [], [], []

    def take(rewards):
        """Fold one reward list into gold + gifts. Same shape wherever it is carried."""
        nonlocal gold
        for r in rewards or []:
            if r.get('id') == 'gold':
                gold += int(r.get('amount') or 0)
            elif r.get('id'):
                gifts.append(r['id'])

    for v in chap.get('villages') or []:
        take(v.get('visit_reward'))
    for boat in chap.get('rescue_boats') or []:
        take((boat.get('talk') or {}).get('reward'))
    bonus = (chap.get('economy') or {}).get('save_all_bonus')
    if bonus:
        gifts.append(bonus)
    for c in chap.get('chests') or []:
        for it in c.get('contents') or []:
            if it.get('id'):
                chests.append(it['id'])
    for ed in chapter_roster_entries(chap):
        if ed.get('item_drop'):
            drops.append(ed['item_drop'])
    pc = chap.get('post_chapter') or {}
    gold += int(pc.get('gold_reward') or 0)
    shops = list(pc.get('available_shops') or chap.get('available_shops') or [])
    return {'gold': gold, 'gifts': gifts, 'chests': chests, 'drops': drops, 'shops': shops}


def _print_economy(chap):
    ref = chap.get('parity_reference')
    van = vanilla_economy(ref)
    print('\n-- ITEM-ECONOMY PARITY (vs %s) [from HEAD, not the injected worktree] '
          % (ref or '?') + '-' * 6)
    if van is None:
        print('  (no mapped vanilla economy for %r -- skipped)' % ref)
    else:
        def fmt(pairs):
            return ', '.join('%s %dg' % (it.replace('ITEM_', ''), v)
                             for it, v in pairs) or 'none'
        print('  vanilla %-11s ~%dg total in gifts+chests+drops' % (ref, van['total_gold']))
        print('    chests: %s' % fmt(van['chests']))
        print('    gifts:  %s  (via %d village/%d house + clear rewards)'
              % (fmt(van['gifts']), van['n_villages'], van['n_houses']))
        print('    drops:  %s  (enemy .itemDrop -- last item)' % fmt(van['drops']))
        print('    shops:  %s' % (', '.join('%s (%d items)'
              % (s.replace('ShopList_Event_', ''), len(items))
              for s, items in van['shops']) or 'none'))
    ours = chapter_economy(chap)
    parts = ['%dg declared' % ours['gold']]
    for label in ('chests', 'gifts', 'drops', 'shops'):
        if ours[label]:
            parts.append('%s[%s]' % (label, ', '.join(map(str, ours[label]))))
    print('  ours:   %s' % ' · '.join(parts))
    print('  (advisory target: match the twin\'s magnitude + delivery vehicle; not a hard gate)')


# ── Battlefield dynamics (#171): recruit-flips + reinforcement timing ────────────
# The static bar counts every enemy as a turn-1 kill. Two vanilla set-pieces break that: a
# CONVERTIBLE enemy (Joshua/Sahnar) you recruit rather than grind, and REINFORCEMENTS that
# arrive over turns instead of alpha-striking. Both auto-detected from HEAD for the twin (CHAR
# macro targets / TurnEventPlayer-loaded arrays) and read from `convertible` and the declared
# arrival turn (`entry_arrival_turn`) in our YAML. Additive view: the static ENEMY-PRESSURE verdict is unchanged (so already-locked
# chapters don't shift) -- this shows, alongside it, what that static proxy can't see.

CONVERT_CLEAR_DISCOUNT = 0.5   # a convertible is neutralized by recruiting, not ground down;
                               # still part clear-load for the risk window before the flip.


def _event_block(script_text, sym):
    """The body of a CONST_DATA EventListScr <sym>[] = { ... }; block ('' if absent)."""
    m = re.search(re.escape(sym) + r'\[\]\s*=\s*\{(.*?)\n\};', script_text, re.S)
    return m.group(1) if m else ''


def _vanilla_convertible_chars(stem):
    """CHARACTER_ enums that are recruitable enemies (a CHAR macro's target) in the twin --
    they flip to allies, so they aren't a kill the player must make."""
    info = inject.decomp.vanilla_decomp_text('src/events/%s-eventinfo.h' % stem)
    return {m.group(1) for m in re.finditer(
        r'CHAR\([^,]+,\s*\w+,\s*CHARACTER_\w+,\s*(CHARACTER_\w+)\)', info)}


# ── The twin's board (#430 step 2b) ──────────────────────────────────────────────

def vanilla_layout(parity_ref):
    """The twin's map layout: its chapter settings' `mainLayerId` into `gChapterDataAssetTable`,
    both read at HEAD so our repointed chapters cannot shift the index."""
    import map_tileset_tool
    name = _vanilla_internal_name(parity_ref)
    settings = json.loads(inject.decomp.vanilla_decomp_text('src/data/chapter_settings.json'))
    chapter = next(c for c in settings['chapters'] if c.get('internalName') == name)
    return map_tileset_tool._asset_names(inject.decomp.SUBMODULE, vanilla=True)[chapter['map']['mainLayerId']]


def vanilla_terrain(parity_ref):
    """The twin's terrain grid, [y][x] terrain ids."""
    import map_tileset_tool
    w, h, cells, terrain = map_tileset_tool.vanilla_layout_data(inject.decomp.SUBMODULE,
                                                   vanilla_layout(parity_ref))
    return [[terrain[cells[y * w + x]] for x in range(w)] for y in range(h)]


def vanilla_front(parity_ref):
    """The twin's deploy front: every tile of the table its `ChapterEventGroup` names as
    `playerUnitsInNormal` -- the decomp's own answer. Scanning the eventscript for blue units
    instead finds cutscene arrays (the Prologue's throne room) and another chapter's table
    (vanilla Ch5 also loads `UnitDef_Event_Ch4Ally`)."""
    return sorted({tuple(d['position']) for d in vanilla_deploy_party(parity_ref)
                   if None not in d['position']})


def vanilla_deploy_party(parity_ref):
    """The twin's `playerUnitsInNormal` table, parsed (`vanilla_unit_defs`)."""
    stem = PARITY_REFERENCE_STEM[parity_ref]
    info = inject.decomp.vanilla_decomp_text('src/events/%s-eventinfo.h' % stem)
    table = re.search(r'\.playerUnitsInNormal\s*=\s*(UnitDef_\w+)', info).group(1)
    return vanilla_udefs_named(stem, table)


# A wave that waits for a ZONE: an AREA entry fires when a player unit ENDS its move inside its
# box (`EvCheck0B_AREA`, bounds inclusive). Its script either loads the wave itself (it acts
# that enemy phase) or clears the temp flag a gated TURN event waits on (it loads the next
# player phase: Ch1's wave on EVFLAG_TMP(11), Ch4's Revenants on 8). The turn is the party's
# EARLIEST entry, walking at full pace from the twin's deploy front on an empty map -- the
# same floor `foot_reach` reads everywhere else. #177 modelled it as a flat turn 2; #440's
# timeline then read that placeholder as vanilla's turn and misfiled ch01's wave as late.
_ZONE_HORIZON = 30          # turns walked before a zone counts as unreachable
_UNPLACED_TURN = 2          # a wave whose trigger the walk cannot place: still not turn 1


def _flag_number(token):
    """`EVFLAG_TMP(11)` / `11` / `0xb` -> 11 (EVFLAG_TMP(flag) is (flag), event-flags.h); a
    named flag (`EVFLAG_WIN`) stays its name."""
    m = re.fullmatch(r'\s*(?:EVFLAG_TMP\(\s*(\w+)\s*\)|(\w+))\s*', token)
    if not m:
        return token.strip()
    word = m.group(1) or m.group(2)
    try:
        return int(word, 0)
    except ValueError:
        return word


def _area_events(info):
    """[(script, (x1, y1, x2, y2))] for every AREA entry of an eventinfo."""
    return [(m.group(1), tuple(int(v, 0) for v in m.group(2, 3, 4, 5)))
            for m in re.finditer(r'AREA\(\s*[^,]+?\s*,\s*(\w+)\s*,\s*(\w+)\s*,\s*(\w+)\s*,'
                                 r'\s*(\w+)\s*,\s*(\w+)\s*\)', info)]


def _zone_trigger(block):
    """The CHARACTER_ an AREA script answers to (`EventScr_UnTriggerIfNotUnit`), or None when
    any player unit sets it off (Ch4 guards on the faction only)."""
    m = re.search(r'SVAL\(\s*EVT_SLOT_2\s*,\s*(CHARACTER_\w+)\s*\)\s*'
                  r'CALL\(\s*EventScr_UnTriggerIfNotUnit\s*\)', block)
    return m.group(1) if m else None


def _zone_entry_turn(parity_ref, box, trigger=None):
    """The first player turn a unit of the twin's deploy party (`trigger` alone, if named) can
    end its move inside `box`, walking its class's cost table turn by turn. None if no one
    can within _ZONE_HORIZON."""
    import map_placement_preview as pp
    terrain = vanilla_terrain(parity_ref)
    x1, y1, x2, y2 = box
    inside = lambda c: min(x1, x2) <= c[0] <= max(x1, x2) and min(y1, y2) <= c[1] <= max(y1, y2)
    best = None
    for d in vanilla_deploy_party(parity_ref):
        if None in d['position'] or (trigger and d['charIndex'] != trigger):
            continue
        table, mov = pp.class_movement(d['classIndex'][len('CLASS_'):].lower())
        cost = pp.mov_cost_row(table)
        reached = {tuple(d['position'])}
        for turn in range(1, _ZONE_HORIZON + 1):
            walk = pp.foot_reach(terrain, sorted(reached), cost=cost)
            reached = {c for c, spent in walk.items() if spent <= mov}
            if any(inside(c) for c in reached):
                best = turn if best is None else min(best, turn)
                break
    return best


def _is_flag_gated(eid):
    """A turn event with a flag fires only while that flag is CLEAR, and sets it when it runs.
    The twins set it in the opening scene and an AREA script clears it, so a flag-gated turn
    event is a zone-triggered wave, not a turn-1 spawn. `0` / EVFLAG_NONE mean unconditional."""
    return _flag_number(eid) not in (0, 'EVFLAG_NONE')


def _player_turn_events(info):
    """Yield (eid, script_sym, turn) for each PLAYER-phase turn event -- both the TurnEventPlayer
    macro (Ch5's waves) and its raw `TURN(eid, scr, turn, end, FACTION_BLUE)` expansion (Ch4's
    wave). Enemy/green-phase TURN(...) entries (allies, NPC spawns) are excluded."""
    for m in re.finditer(r'TurnEventPlayer\(\s*([^,]+?)\s*,\s*(\w+)\s*,\s*(\d+)\s*\)', info):
        yield m.group(1), m.group(2), int(m.group(3))
    for m in re.finditer(r'(?<![A-Za-z_])TURN\(\s*([^,]+?)\s*,\s*(\w+)\s*,\s*(\d+)\s*,'
                         r'\s*\d+\s*,\s*(FACTION_\w+)\s*\)', info):
        if 'BLUE' in m.group(4):
            yield m.group(1), m.group(2), int(m.group(3))


def _vanilla_reinforcement_turns(stem):
    """{UnitDef array -> arrival turn} for enemy arrays that are NOT on the field at turn 1:
    player-phase turn events past turn 1 (Ch5's 2/6/8 waves), plus zone-triggered waves (Ch1's
    west wave, Ch4 "Ancient Horrors"' Revenants), which arrive on the party's earliest entry
    into their AREA (#177; see _zone_entry_turn). Turn-1 unconditional events (the initial
    line force) contribute nothing.

    A flagged turn event is DORMANT only when the opening scene sets its flag; otherwise the
    flag just marks it fired (Ch3's) and it runs on its own turns. A wave whose trigger this
    cannot place -- a zone nobody in the deploy table can set off, a flag an AFEV/CHAR script
    clears, an AFEV script that loads it -- still arrives after turn 1, at _UNPLACED_TURN or
    its own start turn: it is never on the opening board."""
    info = inject.decomp.vanilla_decomp_text('src/events/%s-eventinfo.h' % stem)
    script = inject.decomp.vanilla_decomp_text('src/events/%s-eventscript.h' % stem)
    ref = {v: k for k, v in PARITY_REFERENCE_STEM.items()}[stem]
    areas = [(box, _event_block(script, scr)) for scr, box in _area_events(info)]
    opening = re.search(r'\.beginningSceneEvents\s*=\s*(\w+)', info)
    armed = {_flag_number(f) for f in re.findall(r'ENUT\(\s*([^)]*\)?)\s*\)',
                                                    _event_block(script, opening.group(1))
                                                    if opening else '')}

    def clears(block, flag):
        return any(_flag_number(f) == flag
                   for f in re.findall(r'ENUF\(\s*([^)]*\)?)\s*\)', block))

    def entry(box, block):
        return _zone_entry_turn(ref, box, _zone_trigger(block))

    out = {}
    for eid, scr, turn in _player_turn_events(info):
        flag = _flag_number(eid)
        if _is_flag_gated(eid) and flag in armed:
            # dormant until an AREA clears its flag: it loads the player phase after the entry
            opens = [t + 1 for t in (entry(box, block) for box, block in areas
                                     if clears(block, flag)) if t is not None]
            arrival = max(turn, min(opens) if opens else _UNPLACED_TURN)
        elif turn > 1:
            arrival = turn
        else:
            continue                       # turn-1 event = the initial line
        for arr in re.findall(r'UnitDef_\w+', _event_block(script, scr)):
            out[arr] = arrival
    for box, block in areas:               # an AREA script that loads a force directly
        turn = entry(box, block)
        for arr in re.findall(r'UnitDef_\w+', block):
            out.setdefault(arr, _UNPLACED_TURN if turn is None else turn)
    for scr in re.findall(r'AFEV\(\s*[^,]+?\s*,\s*(\w+)', info):   # loaded on a flag
        for arr in re.findall(r'UnitDef_\w+', _event_block(script, scr)):
            out.setdefault(arr, _UNPLACED_TURN)
    return out


def chapter_enemy_groups(chap):
    """Our force split by battlefield role (#171): line (turn-1 must-kill), reinforcements
    (arriving after turn 1, `inject.raw_pids.entry_arrival_turn`), convertibles
    (recruitable). Each a Combatant list."""
    g = {'line': [], 'reinforcements': [], 'convertibles': []}
    for key in AI_ROSTER_KEYS:
        for ed in (chap.get(key) or []):
            if not isinstance(ed, dict):
                continue
            units = _entry_combatants(ed)
            if ed.get('convertible'):
                g['convertibles'].extend(units)
            elif not inject.raw_pids.entry_is_turn1(key, ed):
                # the KEY makes ch02's `reinforcements:` wave one, and the declared turn
                # makes ch01's `enemy_units` wave one, under whichever of its four
                # spellings it uses. `entry_is_turn1` is the one place that knows both
                # (#367, #440) -- `map_placement_preview.enemy_bodies` and `danger_map`
                # share it.
                g['reinforcements'].extend(units)
            else:
                g['line'].extend(units)
    return g


def vanilla_enemy_groups(parity_ref):
    """Vanilla twin force split by role, with convertibles (CHAR targets) and reinforcement
    turns (TurnEventPlayer-loaded arrays) auto-detected from HEAD. None if uncurated."""
    spec = PARITY_REFERENCE_UDEFS.get(parity_ref)
    if spec is None:
        return None
    relpath, arrays = spec
    stem = PARITY_REFERENCE_STEM.get(parity_ref)
    conv_chars = _vanilla_convertible_chars(stem) if stem else set()
    reinf_turns = _vanilla_reinforcement_turns(stem) if stem else {}
    text = inject.decomp.vanilla_decomp_text(relpath)
    g = {'line': [], 'reinforcements': [], 'convertibles': []}
    for arr in arrays:
        turn = reinf_turns.get(arr, 1)
        for i, d in enumerate(vanilla_unit_defs(text, arr)):
            if d['allegiance'] != 'FACTION_ID_RED':
                continue
            weapon = _weapon_from_item_enums(d['items'])
            if weapon is None:
                continue
            u = _enemy_from_enum('%s#%d' % (arr, i), d['classIndex'], d['level'], weapon)
            if d['charIndex'] in conv_chars:
                g['convertibles'].append(u)
            elif turn > 1:
                g['reinforcements'].append(u)
            else:
                g['line'].append(u)
    return g


def dynamic_pressure(groups, deploy_cap, yardstick=YARDSTICK):
    """Pressure honoring battlefield dynamics (#171): turn-1 threat counts only units on the
    field at the start (line + convertibles), NOT reinforcements; clear-load counts the full
    line + all reinforcements + a discounted convertible (you mostly recruit it, not grind it).
    Returns (threat/slot, clear-load/slot)."""
    cap = max(1, deploy_cap)
    present = groups['line'] + groups['convertibles']
    threat = sum(fc.damage_per_round(e, yardstick) for e in present) / cap
    clear = (sum(fc.rounds_to_kill(yardstick, e) for e in groups['line'])
             + sum(fc.rounds_to_kill(yardstick, e) for e in groups['reinforcements'])
             + CONVERT_CLEAR_DISCOUNT
             * sum(fc.rounds_to_kill(yardstick, e) for e in groups['convertibles'])) / cap
    return threat, clear


def recruit_swing(groups):
    """Post-flip ally throughput a chapter's convertibles add if recruited (kills/round, capped
    1/unit vs the line+reinforcements) -- the 'advantage' half of risk-turned-advantage."""
    line = groups['line'] + groups['reinforcements']
    if not line:
        return 0.0
    return sum(min(1.0, max((fc.kills_per_round(c, e) for e in line), default=0.0))
               for c in groups['convertibles'])


def _print_dynamics(chap):
    ref = chap.get('parity_reference')
    ours = chapter_enemy_groups(chap)
    van = vanilla_enemy_groups(ref)
    cap = chapter_deploy_limit(chap, len(ROSTER))
    dyn = (ours['reinforcements'] or ours['convertibles']
           or (van and (van['reinforcements'] or van['convertibles'])))
    if not dyn:
        return   # nothing dynamic here -- keep the report quiet
    print('\n-- BATTLEFIELD DYNAMICS (#171 -- what the static bar can\'t see) ' + '-' * 9)

    def row(tag, g):
        dt, dc = dynamic_pressure(g, cap)
        print('  %-8s line %2d · reinf %2d · convertible %d  ->  threat/slot %.1f (turn-1) · '
              'clear-load/slot %.1f' % (tag, len(g['line']), len(g['reinforcements']),
                                        len(g['convertibles']), dt, dc))
        if g['convertibles']:
            print('           convertible x%.1f in clear-load · recruit swing +%.2f kills/round if flipped'
                  % (CONVERT_CLEAR_DISCOUNT, recruit_swing(g)))
    if van:
        row('vanilla', van)
    row('ours', ours)
    print('  (additive -- the ENEMY-PRESSURE verdict above is still the static all-turn-1 bar)')


def curve_gate_failures(rows):
    """The --check gate: return the labels of chapters that should fail the build. PER-CHAPTER
    opt-in (#48 (b)): the gate enforces a chapter only once content marks it balance-final with
    `balance_locked: true` in its YAML -- so we can author chapters as we go without an
    unwritten or mid-authoring chapter reddening CI. A LOCKED chapter fails when it is off-parity
    (`verdict != 'OK'`), unreliably measured (`boss_drop` -- its scariest unit carries an
    unmodeled weapon, so even an 'OK' verdict can't be trusted), has no curated reference at
    all (`not has_ref` -- you can't lock a chapter the metric can't measure; a config mistake,
    surfaced loudly), or carries an open per-unit `role` finding. UNLOCKED chapters are
    informational and never gate; with zero locks the gate passes, so --check can ship before
    any chapter is locked.

    The `ai` arm is #335's, and it rides the same opt-in because AI IS part of parity: a
    chapter picks a vanilla twin so its difficulty is grounded rather than guessed, and the
    twin's `UnitDefinition.ai` is as much of that grounding as its class and level. #48
    computes threat from stats and weapons, so behaviour was invisible to it -- five chapters
    measured at parity while fielding a force that played nothing like its twin.

    The `role` arm is #284's lesson. ch02 and ch03 shipped bosses that folded in a third of
    their twin's time, for months, while this gate read OK -- the aggregate sums the whole force
    and divides by the deploy cap, so one paper boss dissolves into a 23-unit average. The
    per-unit check had been PRINTING the warning the entire time and nothing read it. A chapter
    marked balance-final while a per-unit check still has something to say is a contradiction,
    so locking one now means clearing them first."""
    return [r['label'] for r in rows
            if r['locked'] and (not r['has_ref'] or r['verdict'] != 'OK' or r['boss_drop']
                                or r.get('role') or r.get('ai'))]


def curve_report(campaign, band=0.25, mode=None):
    """Campaign-wide enemy-pressure curve: one row per authored chapter, ours vs its vanilla
    reference, so spikes/sags across the arc are visible at a glance (#48). Returns the per-chapter
    rows (label / has_ref / verdict / boss_drop) so the --check gate can act on them.

    `mode` grades a difficulty mode on BOTH sides instead of the authored table (#303). The
    banner says which, because a verdict that does not name its configuration is the thing
    #303 set out to fix."""
    paths = sorted(glob.glob(os.path.join(
        inject.decomp.REPO, 'campaigns', campaign, 'chapters', 'ch*.yaml')))
    bar = '=' * 86
    print(bar)
    print('CAMPAIGN ENEMY-PRESSURE CURVE -- ours vs vanilla parity_reference   '
          '[STATIC proxy]')
    print('  difficulty mode: %s'
          % ('%s (both sides shifted by their own chapter\'s numbers)' % mode.upper()
             if mode else 'AUTHORED TABLE (unshifted -- the level each side DECLARES)'))
    if mode:
        print('  NB per-unit role findings and planned-chapter targets below are graded on the'
              '\n     AUTHORED table, not on %s -- only the parity rows are mode-shifted.'
              '\n     mirror%% is INVARIANT: a mode shifts stats, never a unit\'s class or level,'
              '\n     and the Hard-only waves are folded into both sides unconditionally.'
              % mode.upper())
    print(bar)
    print('  %-22s %-13s %-15s %-17s %-7s %s'
          % ('chapter', 'reference', 'threat', 'clear-load', 'mirror', 'verdict'))
    chaps = []
    for path in paths:
        chaps.append(chapter_schema.load(path))
    rows = []
    any_dropped_boss = False
    for chap in sorted(chaps, key=lambda c: c.get('chapter_number', 99)):
        label = 'CH%s %s' % (chap.get('chapter_number'), chap.get('id', ''))
        # `status: planned` chapters are brainstorm SEED, not authoritative -- their enemy
        # roster/levels are re-grounded against vanilla + party data when the slice is reached
        # (the brainstorming skill digests them). The static proxy can't model an ungrounded
        # sketch, so list it as planned rather than printing a phantom 0.0/OFF. It never gates
        # (not added to `rows`); a planned chapter that is also balance_locked is a config error
        # caught by check.py's chapter-status lint.
        if chap.get('status') == 'planned':
            # our side is an ungrounded seed, but the VANILLA side of the comparison is
            # computable now (#123): print the reference's own pressure as the forward
            # target the authored chapter must hit within the band. Never gates.
            ref = chap.get('parity_reference', '?') or '?'
            target = planned_target(chap, campaign)
            if target is not None:
                print('  %-22s %-13s %4.1f (target)    %4.1f (target)      %-7s planned'
                      % (label[:22], ref[:13], target['threat'], target['clear'], '--'))
                continue
            proj = vanilla_projection(ref, chapter_deploy_limit(chap, len(ROSTER)))
            if proj is None:
                print('  %-22s %-13s   -- planned (seed; reference not curated yet) --'
                      % (label[:22], ref[:13]))
            else:
                note = (' (%d yardstick-proof units, clear-load floored)'
                        % proj['proof']) if proj['proof'] else ''
                note = ' [fixed YARDSTICK: off VANILLA_CHAIN]' + note
                print('  %-22s %-13s %4.1f (target)    %4.1f (target)      %-7s planned%s'
                      % (label[:22], ref[:13], proj['threat'], proj['clearload'], '--', note))
            continue
        p = _chapter_pressure(chap, band, mode=mode, campaign=campaign)
        ot, ol = p['ours']
        boss_drop = any(d['is_boss'] for d in p['dropped'])
        any_dropped_boss = any_dropped_boss or boss_drop
        locked = bool(chap.get('balance_locked', False))
        flag = '  !!boss dropped' if boss_drop else ''
        if locked:
            flag += '  [locked]'
        has_ref = p['vanilla'] is not None
        verdict = p['verdict']['verdict'] if has_ref else None
        # The per-unit findings ride along so the gate can read them (#284) -- the aggregate
        # above cannot see a single soft unit, which is exactly how two paper bosses shipped.
        role = role_findings(chap, p['reference'], campaign) if has_ref else []
        if role:
            flag += '  !!role'
        # ... and whether every enemy's AI is grounded in a vanilla donor (#335). Invisible
        # to everything above, which is computed from stats and weapons.
        ai = ai_donor_findings(chap) if has_ref else []
        if ai:
            flag += '  !!ai'
        rows.append({'label': label[:22].strip(), 'locked': locked, 'has_ref': has_ref,
                     'verdict': verdict, 'boss_drop': boss_drop, 'role': role, 'ai': ai,
                     'mirror': p['mirror']})
        if not has_ref:
            print('  %-22s %-13s %5.1f           %5.1f             %-7s (no ref)%s'
                  % (label[:22], (p['reference'] or '?')[:13], ot, ol, '--', flag))
            continue
        vt, vl = p['vanilla']
        v = p['verdict']
        print('  %-22s %-13s %4.1f (x%.2f)     %4.1f (x%.2f)       %-7s %s%s'
              % (label[:22], (p['reference'] or '?')[:13], ot, v['threat_ratio'],
                 ol, v['load_ratio'], '%.0f%%' % p['mirror']['pct'] if p['mirror'] else '--',
                 v['verdict'], flag))
    if any_dropped_boss:
        print('\n  !! a dropped boss means that row\'s verdict is unreliable -- its scariest '
              'unit\n     carries an unmodeled weapon. Add fe_base to its YAML inventory (#51/#52).')
    ungrounded = [r for r in rows if r.get('ai')]
    if ungrounded:
        print('\n  !! AI not grounded in the vanilla twin (#335) -- every enemy borrows its')
        print('     donor\'s `UnitDefinition.ai` unless the chapter declares an `ai_override:`')
        print('     with a reason:')
        for r in ungrounded:
            for f in r['ai']:
                print('     %-6s %s%s' % (r['label'].split()[0], f,
                                          '' if r['locked'] else '   [not locked -- advisory]'))
    flagged = [r for r in rows if r.get('role')]
    if flagged:
        print('\n  !! per-unit findings the per-slot averages above cannot show (#284):')
        for r in flagged:
            for f in r['role']:
                print('     %-6s %s%s' % (r['label'].split()[0], f,
                                          '' if r['locked'] else '   [not locked -- advisory]'))
    return rows


def _fmt_delta(f):
    parts = [('%+d HP' % f.hp) if f.hp else '', ('%+d Def' % f.df) if f.df else '',
             ('%+d Res' % f.res) if f.res else '']
    return ' '.join(p for p in parts if p) or '(none)'


def lord_floor_report(campaign, ch, target=3.5, def_cap=4, res_cap=4, hp_cap=12):
    chap, roster, line, bosses, deploy_limit, labels = load_field(campaign, ch)
    threat = line + bosses
    bar = '=' * 80
    print(bar)
    print('CH%s "%s" -- LORD SURVIVABILITY FLOOR'
          % (chap.get('chapter_number'), chap.get('title', ch)))
    print(bar)
    print('Metric: bulk durability (worst-case enemy-rounds-to-down -- hits assumed to')
    print('connect, doubling counted, avoid ignored). Survival-only stats (HP/Def/Res; never')
    print('Spd/Lck). Target %.1f. Caps: Def +%d, Res +%d, HP +%d. Computed ONCE, then fades.'
          % (target, def_cap, res_cap, hp_cap))
    print('Threat: %s\n' % '; '.join(labels))
    print('  %-12s %5s   %-22s %6s   %s'
          % ('lord', 'bulk', 'floor delta', '->bulk', 'note'))
    for u in sorted(roster, key=lambda x: bulk_durability(x, threat)):
        f = lord_floor_delta(u, threat, target, def_cap, res_cap, hp_cap)
        note = 'already a tank' if (f.hp, f.df, f.res) == (0, 0, 0) else (
            '' if f.reached else 'UNREACHABLE by stats -- positioning/item answer')
        print('  %-12s %5.1f   %-22s %6.1f   %s'
              % (u.name, bulk_durability(u, threat), _fmt_delta(f), f.bulk, note))


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument('--chapter', help='chapter id, e.g. ch01 (omit with --curve)')
    ap.add_argument('--campaign', default='rime-of-the-frostmaiden')
    ap.add_argument('--curve', action='store_true',
                    help='emit the campaign-wide enemy-pressure curve (all chapters)')
    ap.add_argument('--check', action='store_true',
                    help='with --curve: the hard CI gate (#48 (b)) -- exit non-zero if any '
                         'balance_locked chapter is off-parity, unreliably measured, '
                         'missing its reference, or carrying an open per-unit role '
                         'finding (UNLOCKED chapters never gate)')
    ap.add_argument('--mode', choices=MODES,
                    help='grade a DIFFICULTY MODE instead of the authored table (#303). Both '
                         'sides are shifted by their own chapter\'s declared numbers, so the '
                         'read still compares two tuned tables. Omitted = the authored table, '
                         'which is what every verdict before #303 graded')
    ap.add_argument('--lord-floor', action='store_true',
                    help='emit the per-lord survivability-floor table instead of the parity report')
    ap.add_argument('--target', type=float, default=3.5, help='floor: target bulk rounds-to-down')
    ap.add_argument('--def-cap', type=int, default=4, help='floor: max +Def')
    ap.add_argument('--res-cap', type=int, default=4, help='floor: max +Res')
    ap.add_argument('--hp-cap', type=int, default=12, help='floor: max +HP')
    args = ap.parse_args()
    if args.curve:
        rows = curve_report(args.campaign, mode=args.mode)
        if args.check:
            fails = curve_gate_failures(rows)
            if fails:
                print('\n!! PARITY GATE: %d locked chapter(s) off-parity, unreliable, or '
                      'carrying a role finding: %s'
                      % (len(fails), ', '.join(fails)))
                sys.exit(1)
            print('\nPARITY GATE: all referenced chapters at parity.')
        return
    if not args.chapter:
        ap.error('--chapter is required (or pass --curve for the campaign-wide report)')
    elif args.lord_floor:
        lord_floor_report(args.campaign, args.chapter, args.target,
                          args.def_cap, args.res_cap, args.hp_cap)
    else:
        report(args.campaign, args.chapter, mode=args.mode)


if __name__ == '__main__':
    main()
