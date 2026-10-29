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
import json
import os
import random
import re

import campaign_chapters  # noqa: E402
import chapter_schema  # noqa: E402
import inject.cast  # noqa: E402
import inject.class_ids  # noqa: E402
import inject.chapter_settings  # noqa: E402
import inject.decomp  # noqa: E402
import inject.hosting  # noqa: E402
import inject.hosts  # noqa: E402
import inject.paths  # noqa: E402
import inject.raw_pids  # noqa: E402
import inject.stats  # noqa: E402
import inject.villages  # noqa: E402
import argparse
import sys
import ai_target
import fe_combat as fc
import unit_load
from inject.decomp import ITEM_ENUM   # the one item id -> ITEM_ enum table (#491)

# The class facts fe_combat reads, as tags (#510 audit). A DEFENDER's class sits on the
# effectiveness lists in data_itemuse.c (`IsItemEffectiveAgainst` is exact class-id
# membership); a weapon's `effective` tags name the lists it is effective against, so a
# Rapier ({'armor', 'cav'}) hits ItemEffectiveness_ArmorAndHorse = Armor + Horse. An
# ATTACKER's class gives 'critbonus' (CA_CRITBONUS, +15 crit, `ComputeBattleUnitCritRate`)
# and 'slayer' (x3 Mt against 'monster', `IsUnitEffectiveAgainst`, bmitem.c).
EFFECTIVENESS_LISTS = {'armor': 'Armor', 'cav': 'Horse', 'flier': 'Flier',
                       'monster': 'Monsters'}


@functools.lru_cache(maxsize=None)
def effectiveness_lists():
    """{list name: set of CLASS_ enums} for every `ItemEffectiveness_*` in data_itemuse.c."""
    text = inject.decomp.vanilla_decomp_text('src/data_itemuse.c')
    return {name: set(re.findall(r'CLASS_\w+', body)) - {'CLASS_NONE'}
            for name, body in re.findall(r'ItemEffectiveness_(\w+)\[\] = \{(.*?)\};', text, re.S)}


@functools.lru_cache(maxsize=None)
def class_tags(class_enum):
    """The fe_combat tags a unit of `class_enum` carries; see EFFECTIVENESS_LISTS."""
    lists = effectiveness_lists()
    tags = {tag for tag, name in EFFECTIVENESS_LISTS.items() if class_enum in lists[name]}
    import exp_curve                        # exp_curve imports this module
    try:
        if 'CA_CRITBONUS' in exp_curve.class_attributes(class_enum):
            tags.add('critbonus')
    except KeyError:                        # a raw class number: no class block to read
        pass
    if class_enum in inject.class_ids.slayer_classes():
        tags.add('slayer')
    return frozenset(tags)


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
    block = unit_load._class_block(class_enum)
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


def mode_stats(base, growths, level, mode, shifts, base_level=1, autolevel=True,
               promoted=False):
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

    `autolevel` is the UnitDefinition's flag: an unflagged unit loads at class + personal base
    and grows only by the shift, and on Normal the penalty's re-autolevel grows it anyway
    (#490, read on the ROM). `promoted` adds GetCurrentPromotedLevelBonus()'s 9 (19 on
    Difficult) levels. The branches are `unit_load.growth_steps`, which the wiki reads too.

    This is the mean-value line: the engine's real `GetAutoleveledStatIncrease` jitters by
    +/-(growth*n)/8 and resolves the remainder with a coin flip (`GetStatIncrease`,
    bmbattle.c:1241), so a single unit's stats are a random variable. The parity read rolls
    it instead (`enemy_careers`, #510 step 4); this line is the planning number.
    """
    if mode not in MODES:
        raise ValueError('unknown difficulty mode %r (want one of %s)'
                         % (mode, ', '.join(MODES)))
    return _project(base, growths, unit_load.growth_steps(
        level, autolevel, promoted, base_level, shifts[mode], mode))


def _project(base, growths, steps, personal_growths=None):
    """`base` grown by `unit_load.growth_steps`' chunks, each rounded on its own: the engine
    rolls each UnitAutolevelCore call apart, so Difficult is round(level-1) + round(bonus), not
    one rounding of the sum."""
    out = dict(base)
    for levels, source in steps:
        g = growths if source == 'class' else (personal_growths or {})
        for gf in inject.stats.GROWTH_FIELDS:
            field = 'base' + gf[len('growth'):]
            out[field] = out.get(field, 0) + _mean_increase(levels, g.get(gf, 0))
    return out


def _mean_increase(levels, growth):
    """What one growth chunk adds to a stat on the mean-value line: levels x growth%, rounded
    half up. `enemy_careers` undoes exactly this to roll the chunk instead."""
    return int(levels * growth / 100 + 0.5)


def _weapon_for(inventory):
    """First inventory entry that resolves (via fe_base, else id) to a real attacking
    weapon usable in the modeled (base-class) state. Staves/consumables aren't in
    fe_combat.W, so they're skipped; items with an `unlock` precondition (e.g. a base
    Priest's promotion-gated Light tomes) are skipped too -- so a staff-only healer
    resolves to None, the support path, instead of leaking promoted kit into base offense
    or crashing (#62). The YAML's own `unlock` flag is the data-driven gate."""
    weapons = _weapons_for(inventory)
    return weapons[0] if weapons else None


def _weapons_for(inventory):
    """Every weapon `_weapon_for` would accept, in inventory order: the unit's arsenal, which
    the AI chooses from per target (`fc.arms`)."""
    out = []
    for item in inventory or []:
        if item.get('unlock'):                    # not yet usable at base class
            continue
        key = item.get('fe_base') or item.get('id')
        weapon = item_weapon(ITEM_ENUM[key]) if key in ITEM_ENUM else fc.W.get(key)
        if weapon is not None:
            out.append(weapon)
    return tuple(out)


def _stats_to_combatant(name, stats, weapon, tags=frozenset(), arsenal=()):
    return fc.Combatant(name, hp=stats['baseHP'], pow=stats['basePow'],
                        skl=stats['baseSkl'], spd=stats['baseSpd'], df=stats['baseDef'],
                        res=stats['baseRes'], lck=stats.get('baseLck', 0),
                        con=stats['baseCon'], weapon=weapon, tags=tags, arsenal=arsenal)


def _class_caps(class_enum):
    """A PLAYER unit's stat ceilings in `class_enum` (`CheckBattleUnitStatCaps`, bmbattle.c,
    through bmunit.h's UNIT_*_MAX): the class's own max for Pow/Skl/Spd/Def/Res, and the two
    fixed ones -- 60 HP for a non-red unit, 30 Lck for everyone."""
    block = unit_load._class_block(class_enum)
    caps = {'baseHP': 60, 'baseLck': 30}
    for field in ('Pow', 'Skl', 'Spd', 'Def', 'Res'):
        m = re.search(r'\.max' + field + r'\s*=\s*(\d+)', block)
        if m:
            caps['base' + field] = int(m.group(1))
    return caps


_STAT_ORDER = ('HP', 'Pow', 'Skl', 'Spd', 'Def', 'Res', 'Lck')   # the order FE8 rolls them in


def level_up(growths, rng):
    """One player level-up's stat gains, transcribed from `CheckBattleUnitLevelUp`
    (bmbattle.c). Every stat rolls once; an EMPTY level then re-rolls up to twice, walking the
    stats in order and stopping at the first that gains. That re-roll couples the stats, which
    is why `grown` simulates rather than reading each stat off a binomial."""
    gains = {f: unit_load.stat_increase(growths.get('growth' + f, 0), rng) for f in _STAT_ORDER}
    if not any(gains.values()):
        for _ in range(2):
            for f in _STAT_ORDER:
                gains[f] = unit_load.stat_increase(growths.get('growth' + f, 0), rng)
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


def _player_weapon(campaign, uid):
    """The weapon a cast member actually fights with: the first attacking item of the kit every
    roster that LOADs it reads (`inject.cast.unit_items`), so the gate and the ROM share one
    filter."""
    return _weapon_from_item_enums(inject.cast.unit_items(campaign, uid))


def _player_lines(campaign, uid, gained):
    """(career stat lines, weapon, tags) for a cast member `gained` levels above its join
    level: the line its ROM slot loads with (`inject.stats.cast_loaded_line`), grown on its
    growth donor's growths."""
    class_enum, eff = inject.stats.cast_loaded_line(
        campaign, uid, _characters_text(), _classes_text())
    lines = [eff]
    if gained:
        growths, _ = inject.stats.donor_growths_and_ranks(
            _characters_text(), inject.stats.GROWTH_DONOR[uid])
        lines = careers(eff, growths, gained, _class_caps(class_enum))
    weapon = _player_weapon(campaign, uid)
    return lines, weapon, class_tags(class_enum)


def player_combatant(campaign, uid, gained=0):
    """Resolve a cast member's effective fe_combat.Combatant: class base + donor personal
    base (donor-base inheritance), wielding its first real weapon.

    `gained` is how many levels the unit has risen above the one it joined at, grown on its
    growth donor's growths (`grown`: the median of simulated level-ups). 0 is the join-level line, which is what the injector
    sizes ch01's lord floor from; `load_field(leveled=True)` passes the exp model's answer
    (#430 step 1)."""
    lines, weapon, tags = _player_lines(campaign, uid, gained)
    return _stats_to_combatant(uid, _median_line(lines), weapon, tags)


def player_careers(campaign, uid, gained=0, arsenal=None):
    """`player_combatant`, once per simulated career (`careers`). `arsenal`, from
    `kits.arsenals`, is what the unit carries (#510 step 8); it equips the first."""
    lines, weapon, tags = _player_lines(campaign, uid, gained)
    if arsenal is not None:
        weapon = arsenal[0] if arsenal else None
    return [_stats_to_combatant(uid, line, weapon, tags, tuple(arsenal or ()))
            for line in lines]


def _can_use(class_enum, char_index):
    """ITEM_ enum -> can a unit of `class_enum` with `char_index`'s ranks wield it (`_usable`),
    the rank gate `kits.arsenals` hands a pickup through. Ranks do not grow (ADR 0365)."""
    return functools.partial(_can_use_item, class_enum=class_enum, char_index=char_index)


@functools.lru_cache(maxsize=None)
def _can_use_item(item, class_enum, char_index):
    weapon = item_weapon(item)
    return weapon is not None and bool(_usable((weapon,), class_enum, char_index, False))


def _our_kits(campaign, uids, chapter, path):
    """{uid: arsenal} for our arriving `uids` (join order) entering `chapter` on `path`. Our
    units' ranks are their STAT_DONOR's (`inject.stats.cast_ranks`)."""
    import kits
    members = [kits.Member(uid, _can_use(inject.stats.cast_loaded_line(
                   campaign, uid, _characters_text(), _classes_text())[0],
                   inject.stats.STAT_DONOR[uid]), tuple(inject.cast.unit_items(campaign, uid)))
               for uid in uids]
    return kits.arsenals(kits.our_pickups(campaign), chapter, members, path)


_enemy_class_enum = inject.class_ids.vanilla_class_enum


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
        _char_numbers = inject.decomp.enum_values(text, 'CHARACTER_')
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
                     mode=None, shifts=None, shiftable=True, base_level=1, autolevel=True,
                     realistic=False, personal_growths=None, arsenal=(), char_index=None):
    """One Combatant as the engine loads it (`unit_load.growth_steps`): class base grown per
    the definition's `autolevel` flag, its class's promoted bonus and the `mode` shift, wielding
    `weapon`, plus any personal boss line (see above), capped at the class maxima
    (UnitCheckStatCaps). Generics carry no personal line, so they are unchanged.

    `shiftable=False` models the `>= 0x3C` gate; without `mode` and `shifts` the unit reads as
    Normal with no shift. `realistic` is the CA_BOSS / pid < 0x40 branch, which levels on
    `personal_growths` from `base_level`. The personal line stays a flat delta applied
    afterwards, which is faithful: the engine's penalty re-derives from charBase+classBase and
    its bonus adds onto them, and both compose additively."""
    base, growths = _class_base(class_enum), _class_growths(class_enum)
    _b, _g, caps, promoted = unit_load.class_line(class_enum)
    shift = shifts[mode] if mode and shifts and shiftable else 0
    steps = unit_load.growth_steps(int(level), autolevel, promoted, base_level, shift,
                                   mode or 'normal', realistic)
    stats = _project(base, growths, steps, personal_growths)
    c = _apply_personal(_stats_to_combatant(name, stats, weapon,
                                            class_tags(class_enum)), personal)
    capped = {f: min(getattr(c, f), caps[k]) for f, k in _GROWN_FIELDS
              if getattr(c, f) > caps[k]}
    if arsenal:
        # It carries what its definition lists; it can attack only with what it can use
        # (CanUnitUseWeapon), and it equips the first of those (#510 step 3).
        arsenal = _usable(arsenal, class_enum, char_index, autolevel)
        capped['weapon'] = arsenal[0] if arsenal else None
    chunks = tuple((n, tuple(sorted((growths if src == 'class' else personal_growths or {})
                                    .items())), src) for n, src in steps)
    roll = (chunks, tuple(
        (f, getattr(c, f) - capped.get(f, getattr(c, f)) - sum(
            _mean_increase(n, dict(g).get('growth' + k, 0)) for n, g, _s in chunks), caps[k])
        for f, k in _GROWN_FIELDS)) if chunks else None
    return LoadedUnit(**dict(vars(c), arsenal=tuple(arsenal), roll=roll, **capped))


# Combatant field -> the engine's stat name, for the seven stats a load grows.
_GROWN_FIELDS = (('hp', 'HP'), ('pow', 'Pow'), ('skl', 'Skl'), ('spd', 'Spd'), ('df', 'Def'),
                 ('res', 'Res'), ('lck', 'Lck'))


@dataclasses.dataclass
class LoadedUnit(fc.Combatant):
    """A red unit as `_enemy_from_enum` loads it: its mean-value line, plus `roll`, what it takes
    to roll it as the engine does (`enemy_careers`). `roll` is (chunks, fields): the growth
    steps as (levels, growths, 'class' | 'personal'), and per stat (field, offset, cap), where
    the offset takes the line back to its unrounded, uncapped base. None for a unit that loads
    without growing, which has one line. It is not part of the unit's identity (compare=False):
    two bodies with one line are the same opponent at the mean."""
    roll: tuple = dataclasses.field(default=None, compare=False)


ENEMY_TRIALS = GROWTH_TRIALS


@functools.lru_cache(maxsize=None)
def _rolled_gains(chunks):
    """ENEMY_TRIALS draws of what a load's growth `chunks` add to each stat: {stat: array},
    stats as _STAT_ORDER names them. A class chunk is one `UnitAutolevelCore` call
    (GetAutoleveledStatIncrease per stat, rolled in the engine's order); a personal chunk is
    `UnitAutolevelRealistic`'s real level-ups. Seeded on the chunks, so a reading is the same
    every run."""
    import numpy
    rng = random.Random('%d:%r' % (GROWTH_SEED, chunks))
    chunks = [(n, dict(g), src) for n, g, src in chunks]
    rows = []
    for _ in range(ENEMY_TRIALS):
        gains = dict.fromkeys(_STAT_ORDER, 0)
        for n, g, src in chunks:
            if src == 'class':
                for f in _STAT_ORDER:
                    gains[f] += unit_load.autolevel_increase(g.get('growth' + f, 0) * n, rng)
            else:
                for _ in range(n):
                    for f, up in level_up(g, rng).items():
                        gains[f] += up
        rows.append([gains[f] for f in _STAT_ORDER])
    columns = numpy.array(rows).T
    return dict(zip(_STAT_ORDER, columns))


def _rolled_stats(unit):
    """{field: array} of a rolled unit's stats over its ENEMY_TRIALS loads, each held to its
    class cap (UnitCheckStatCaps). None for a unit with nothing to roll."""
    import numpy
    roll = getattr(unit, 'roll', None)
    if not roll:
        return None
    chunks, fields = roll
    gains, names = _rolled_gains(chunks), dict(_GROWN_FIELDS)
    return {f: numpy.minimum(getattr(unit, f) + offset + gains[names[f]], cap)
            for f, offset, cap in fields}


def enemy_careers(unit):
    """A loaded unit once per simulated load (#510 step 4): its line rolled as the engine rolls
    it, ENEMY_TRIALS times, and held to its class caps. The counterpart of the party's
    `careers`. A unit with no growth to roll, or a plain Combatant, is one career, itself.
    `party_matchup` reads the same rolls as arrays (`_over_careers`)."""
    stats = _rolled_stats(unit)
    if stats is None:
        return [unit]
    # A career is one line: it carries no roll of its own, or a reader would roll it again.
    return [dataclasses.replace(unit, roll=None, **{f: int(v[i]) for f, v in stats.items()})
            for i in range(ENEMY_TRIALS)]


def _usable(weapons, class_enum, char_index, autolevel):
    """The `weapons` a unit of `class_enum` on `char_index` can wield as it loads
    (`unit_load.can_use_weapon`), in order. A weapon with no decomp item (a monster attack
    fc.W invents) is kept: there is nothing to judge it by."""
    import exp_curve                        # exp_curve imports this module
    try:
        attributes = exp_curve.class_attributes(class_enum)
    except KeyError:                        # a raw class number: no class block to read
        return tuple(weapons)
    attributes = attributes | exp_curve.character_attributes(char_index)
    block = _character_block(char_index)
    return tuple(w for w in weapons
                 if weapon_item(w) is None
                 or unit_load.can_use_weapon(weapon_item(w), class_enum, block, attributes,
                                             autolevel))


def weapon_item(weapon):
    """The ITEM_ enum a Weapon stands for, or None for one fc.W invents: its ITEM_ENUM entry,
    else the enum `item_weapon` read it from (it names those `sword-slim` for ITEM_SWORD_SLIM)."""
    if weapon.name in ITEM_ENUM:
        return ITEM_ENUM[weapon.name]
    enum = 'ITEM_' + weapon.name.upper().replace('-', '_')
    return enum if item_weapon(enum) == weapon else None


def _character_block(char_index):
    """A CHARACTER_ slot's vanilla data_characters.c entry, '' for a generic or unknown one."""
    if not str(char_index or '').startswith('CHARACTER_'):
        return ''
    try:
        s, e = inject.decomp._find_brace_block(_characters_text(), '[%s - 1]' % char_index,
                                               inject.paths.CHARACTERS_C)
    except SystemExit:
        return ''
    return _characters_text()[s:e]


def _loads_realistically(char_index, class_enum):
    """Does a FLAGGED red unit on this slot take UnitAutolevelRealistic (LoadUnit, bmunit.c:
    625)? CA_BOSS in its character's or class's attributes, or pid < 0x40. Vanilla's flagged
    bosses (Bazba, Saar, Tirado) do, and carry baseLevel >= their level, so they load bare."""
    import exp_curve                        # exp_curve imports this module
    number = _character_number(char_index) if char_index else None
    if number is not None and number < 0x40:
        return True
    try:
        if 'CA_BOSS' in exp_curve.class_attributes(class_enum):
            return True
    except KeyError:                                   # a raw class number: no block to read
        pass
    return 'CA_BOSS' in exp_curve.character_attributes(char_index)


def _vanilla_load_kwargs(d):
    """`_enemy_from_enum`'s load-path arguments for one vanilla UnitDefinition `d`."""
    ch = d.get('charIndex')
    realistic = d['autolevel'] and _loads_realistically(ch, d['classIndex'])
    growths = None
    if realistic and str(ch or '').startswith('CHARACTER_'):
        growths = inject.stats.donor_growths_and_ranks(_characters_text(), ch)[0]
    return dict(autolevel=d['autolevel'], realistic=realistic, personal_growths=growths,
                shiftable=_takes_difficulty_shift(ch), base_level=_character_base_level(ch),
                char_index=ch)


def _our_load_kwargs(ed):
    """The same for one of OUR entries: the flag is the YAML's `autolevel:`, which is what the
    injector emits (inject/units.py), and the slot is the donor a hostile cast member or a
    vanilla-slot boss rides. Every `is_boss` entry carries CA_BOSS, raw pid or not (#545)."""
    import exp_curve                        # exp_curve imports this module
    # ENEMY_CHARACTER_SLOT, not ENEMY_BASE_SLOT: the question is the slot's ATTRIBUTES
    # (CA_BOSS), and Sephek keeps ONEILL's though his stat line is zeroed (inject/cast.py).
    donor = (inject.stats.BASE_DONOR.get(ed.get('id'))
             or inject.cast.ENEMY_CHARACTER_SLOT.get(ed.get('id')))
    flagged = bool(ed.get('autolevel'))
    # Two different slots: the boss bit is the row the unit DEPLOYS on (ENEMY_CHARACTER_SLOT, or
    # its stamped boss row); `donor` may be a BASE_DONOR that lends only stats, and
    # _loads_realistically also takes its pid < 0x40 and its class's CA_BOSS.
    realistic = ('class' in ed and flagged
                 and (exp_curve.entry_carries_ca_boss(ed)
                      or (bool(donor)
                          and _loads_realistically(donor, _enemy_class_enum(ed['class'])))))
    growths = inject.stats.donor_growths_and_ranks(_characters_text(), donor)[0] \
        if realistic and str(donor).startswith('CHARACTER_') else None
    return dict(autolevel=flagged, realistic=realistic, personal_growths=growths,
                char_index=donor)


def _one_enemy(name, class_token, level, weapon, personal=None, mode=None, shifts=None,
               base_level=1, shiftable=True, **load):
    return _enemy_from_enum(name, _enemy_class_enum(class_token), level, weapon, personal,
                            mode=mode, shifts=shifts, base_level=base_level,
                            shiftable=shiftable, **load)


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
                           shiftable=shiftable, arsenal=_weapons_for(enemy_def.get('inventory')),
                           **_our_load_kwargs(enemy_def))]
    by_class = enemy_def.get('inventory_by_class', {})
    out = []
    for cls in dict.fromkeys(enemy_def.get('composition', [])):   # distinct, order-stable
        inventory = [{'id': w} for w in by_class.get(cls, [])]
        out.append(_one_enemy('%s-%s' % (name, cls), cls, level, _weapon_for(inventory),
                              mode=mode, shifts=shifts, base_level=base_level,
                              shiftable=shiftable, arsenal=_weapons_for(inventory),
                              **_our_load_kwargs(enemy_def)))
    return out


# ── Vanilla enemy extraction (the #48 parity reference force) ─────────────────────
# A chapter's `parity_reference` (e.g. "FE8 Ch1") names the vanilla chapter whose enemy
# pressure sets its bar. We resolve that to the decomp UnitDefinition array(s) holding the
# fightable red force and project each enemy off class base -- the same footing as ours.

# decomp item enum -> fe_combat weapon key: the ITEM_ENUM entries fe_combat models. Staves,
# consumables and keys are absent on purpose (an enemy carrying only those resolves to no
# modeled weapon and is skipped -- with a warning, see unmodeled_enemies). One table serves both
# directions and both sides, the cast's weapons and the twins' monster/exotic ones (#491).
ITEM_TO_WEAPON = {item: key for key, item in ITEM_ENUM.items() if key in fc.W}

_ITYPE_KIND = {'ITYPE_SWORD': 'sword', 'ITYPE_LANCE': 'lance', 'ITYPE_AXE': 'axe',
               'ITYPE_BOW': 'bow', 'ITYPE_ANIMA': 'anima', 'ITYPE_LIGHT': 'light',
               'ITYPE_DARK': 'dark'}


@functools.lru_cache(maxsize=None)
def item_weapon(item_enum):
    """The fe_combat Weapon an ITEM_ enum attacks with, or None (a staff, a consumable, a key).
    THE item -> weapon reader: its fc.W entry when fe_combat lists it, else read off its
    data_items.c block, so a kit can hold a weapon fc.W never needed (#510 step 8: a shop's
    Slim Sword, a village's Armorslayer). Brave, magic-sword and other effects stay unmodelled
    either way (logged on #510)."""
    if item_enum in ITEM_TO_WEAPON:
        return fc.W[ITEM_TO_WEAPON[item_enum]]
    try:
        block = unit_load._item_block(item_enum)
    except KeyError:
        return None
    kind = re.search(r'\.weaponType\s*=\s*(\w+)', block)
    if 'IA_WEAPON' not in unit_load.attributes_in(block) or not kind \
            or kind.group(1) not in _ITYPE_KIND:
        return None

    def num(field):
        m = re.search(r'\.%s\s*=\s*(\w+)' % field, block)
        return int(m.group(1), 0) if m else 0
    rng = num('encodedRange')
    eff = re.search(r'\.pEffectiveness\s*=\s*ItemEffectiveness_(\w+)', block)
    lists = effectiveness_lists()
    hits = lists.get(eff.group(1), set()) if eff else set()
    effective = frozenset(tag for tag, name in EFFECTIVENESS_LISTS.items()
                          if lists[name] and lists[name] <= hits)
    name = {e: k for k, e in ITEM_ENUM.items()}.get(
        item_enum, item_enum[len('ITEM_'):].lower().replace('_', '-'))
    return fc.Weapon(name, num('might'), num('hit'), num('crit'), num('weight'),
                     _ITYPE_KIND[kind.group(1)], (rng >> 4, rng & 0xF), effective)

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
    # Ch7 and Ch8 (our ch07 / ch08 -- the twin is the chapter NUMBER, whatever map a chapter
    # borrows; #459). Same rule: every array chN-eventscript.h loads whose RED units are armed.
    # The rule reproduces the hand-curated Ch6 entry above exactly.
    'FE8 Ch7': ('src/events_udefs.c', ['UnitDef_088B6F54']),
    'FE8 Ch8': ('src/events_udefs.c',
                ['UnitDef_088B73C8', 'UnitDef_088B77C4', 'UnitDef_088B7648',
                 'UnitDef_088B7698', 'UnitDef_088B7964', 'UnitDef_088B798C',
                 'UnitDef_088B79F0', 'UnitDef_088B79C8', 'UnitDef_088B7A54']),
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
    into a list of per-entry dicts (charIndex, classIndex, level, allegiance, itemDrop,
    autolevel, items).
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
            # Only a flagged unit grows past class + personal base (LoadUnit, bmunit.c:617).
            'autolevel': bool(re.search(r'\.autolevel\s*=\s*1', block)),
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
    reds = _vanilla_red_defs(parity_ref)
    return None if reds is None else [d for _a, _i, d in reds]


def _vanilla_red_defs(parity_ref):
    """(array, index in the array, UnitDefinition dict) for every RED unit in the twin's
    curated arrays, or None if the reference isn't curated. The one walk over them, so the
    one place scene-only arrays (`_cleared_scene_udefs`) are dropped for every reader."""
    spec = PARITY_REFERENCE_UDEFS.get(parity_ref)
    if spec is None:
        return None
    relpath, arrays = spec
    text = inject.decomp.vanilla_decomp_text(relpath)
    scenes = _cleared_scene_udefs(parity_ref)
    return [(array_name, i, d) for array_name in arrays if array_name not in scenes
            for i, d in enumerate(vanilla_unit_defs(text, array_name))
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
    weapons = _weapons_from_item_enums(item_enums)
    return weapons[0] if weapons else None


def _weapons_from_item_enums(item_enums):
    """Every decomp item enum that is a real attacking weapon (`item_weapon`), in inventory
    order."""
    return tuple(w for w in map(item_weapon, item_enums) if w is not None)


def vanilla_enemies(parity_ref, mode=None):
    """The vanilla reference chapter's fightable red force as a flat list of Combatants
    (each projected off class base to its level). None if the reference isn't curated yet;
    enemies with no modeled weapon (staff/throwaway only) are dropped."""
    bodies = vanilla_enemy_bodies(parity_ref, mode)
    return None if bodies is None else [u for u, _ai in bodies]


@functools.lru_cache(maxsize=None)
def _cleared_scene_udefs(parity_ref):
    """The UnitDefinition arrays the twin loads ONLY to stage a scene: every LOAD of the array
    in the chapter's scripts sits in an EventListScr that runs CLEE (EvtRemoveAllEimies)
    afterwards, stripping every enemy from the map before the scene ends. Ch8's TowerFall
    loads Caellach this way, has him fight a cutscene battle, and clears him; he is never on
    the player's map. An array that is also loaded live (after the script's last CLEE, or in a
    script with none) stays. The armed counterpart of the unarmed-cutscene rule the curated
    lists apply."""
    index = _vanilla_chapter_index(parity_ref)
    stem = None if index is None else chapter_event_stem(index)
    if stem is None:
        return frozenset()
    script = inject.decomp.vanilla_decomp_text('src/events/%s-eventscript.h' % stem)
    staged, live = set(), set()
    for block in re.split(r'CONST_DATA EventListScr', script)[1:]:
        last_clear = [m.start() for m in re.finditer(r'^\s*CLEE\b', block, re.M)][-1:]
        for m in re.finditer(r'LOAD\w*\(\s*\w+\s*,\s*(UnitDef_\w+)', block):
            (staged if last_clear and m.start() < last_clear[0] else live).add(m.group(1))
    return frozenset(staged - live)


def vanilla_loaded_units(parity_ref, mode=None, with_personal=True):
    """(array, index, UnitDefinition dict, Combatant) for every RED unit the twin fields with a
    modeled weapon, loaded as the engine loads it in `mode` (ADR 0354). None when the reference
    is uncurated. The one place the twin's force is built; every reader filters or reshapes it.

    The REAL ARTICLE (#285): a named vanilla unit fights as class base PLUS its own
    CharacterData line, symmetric with our side, which resolves its lines through
    unit_real_article(). `with_personal=False` reads the same unit off class base alone."""
    reds = _vanilla_red_defs(parity_ref)
    if reds is None:
        return None
    shifts = vanilla_chapter_shifts(parity_ref) if mode else None
    if mode and shifts is None:
        # Silently returning an UNSHIFTED vanilla force here would compare our shifted
        # side against vanilla's authored table and still print a verdict -- exactly the
        # unnamed-configuration bug #303 exists to kill. Refuse instead.
        sys.exit('ERROR: parity_reference %r does not resolve to a vanilla chapter, so '
                    'its difficulty numbers are unknown and a --mode read would compare '
                    'our SHIFTED force against an UNSHIFTED reference' % parity_ref)
    out = []
    for array_name, i, d in reds:
        weapon = _weapon_from_item_enums(d['items'])
        if weapon is None:
            continue
        ch = d.get('charIndex')
        unit = _enemy_from_enum(
            '%s#%d[%s]' % (array_name, i, ch), d['classIndex'], d['level'], weapon,
            vanilla_personal_line(ch) if with_personal else None,
            mode=mode, shifts=shifts, arsenal=_weapons_from_item_enums(d['items']),
            **_vanilla_load_kwargs(d))
        if unit.weapon is None:     # it carries weapons it cannot wield (Ch8's Steel-Blade
            continue                # Fighters): it attacks no one, like the itemless above
        out.append((array_name, i, d, unit))
    return out


def vanilla_enemy_bodies(parity_ref, mode=None):
    """`vanilla_enemies`, each unit paired with its 4 AI bytes: [(Combatant, ai)]."""
    units = vanilla_loaded_units(parity_ref, mode)
    return None if units is None else [(c, d['ai']) for _a, _i, d, c in units]


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


def _vanilla_chapter_index(parity_ref):
    """The chapter_settings index of the vanilla chapter `parity_ref` names, else None."""
    name = _vanilla_internal_name(parity_ref)
    chapters = json.loads(inject.decomp.vanilla_decomp_text('src/data/chapter_settings.json'))
    names = [c.get('internalName') for c in chapters['chapters']]
    return names.index(name) if name in names else None


def vanilla_chapter_shifts(parity_ref):
    """The parity reference chapter's OWN difficulty triple, in `mode_stats` shape.

    This is what makes a cross-mode parity read honest: our side and the vanilla side
    are shifted by the numbers each chapter actually carries, so a mode comparison is
    still comparing two tuned tables rather than one tuned table against a shifted one.
    None if the reference does not name a vanilla chapter."""
    index = _vanilla_chapter_index(parity_ref)
    if index is None:
        return None
    chapter = json.loads(
        inject.decomp.vanilla_decomp_text('src/data/chapter_settings.json'))['chapters'][index]
    return {'tutorial': chapter['easyModeLevelMalus'],
            'normal': chapter['normalModeLevelMalus'],
            'difficult': chapter['difficultModeLevelBonus']}


def vanilla_forced(parity_ref):
    """The twin's units FE8 deploys whatever the player picks: `IsCharacterForceDeployed_`
    (eventinfo.c) over `gForceDeploymentList` (data_event_trigger.c), for the common route the
    early chain runs on (prologue to Ch8) and the twin's chapter index. Eirika everywhere,
    Artur in Ch4, Natasha in Ch5. {name}, as `vanilla_party` names them."""
    index = _vanilla_chapter_index(parity_ref)
    if index is None:
        return set()
    text = inject.decomp.vanilla_decomp_text('src/data_event_trigger.c')
    s, e = inject.decomp._find_brace_block(text, 'gForceDeploymentList[]',
                                           'src/data_event_trigger.c')
    out = set()
    for char, route, chapter in re.findall(r'\{\s*(CHARACTER_\w+)\s*,\s*([\w-]+)\s*,\s*'
                                           r'(-?\w+)\s*\}', text[s:e]):
        if route in ('-1', 'CHAPTER_MODE_COMMON') and chapter in ('-1', str(index)):
            out.add(_ally_name(char))
    return out


def vanilla_named_bosses(parity_ref, with_personal=True, mode=None):
    """The twin's NAMED units as (name, Combatant). Used only by the role check -- see the
    note in vanilla_enemies about keeping the aggregate class-base-only."""
    return [(d['charIndex'].replace('CHARACTER_', '').title(), dataclasses.replace(c, name=d['charIndex']))
            for _a, _i, d, c in vanilla_loaded_units(parity_ref, mode, with_personal) or []
            if str(d.get('charIndex') or '').startswith('CHARACTER_')]


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
                               weapon, class_tags(class_enum))


# Eirika's route up to the last twin a hosted chapter is graded against. The vanilla party at
# any of these is everybody recruited so far, which the decomp states chapter by chapter.
VANILLA_CHAIN = ('FE8 Prologue', 'FE8 Ch1', 'FE8 Ch2', 'FE8 Ch3', 'FE8 Ch4', 'FE8 Ch5',
                 'FE8 Ch6', 'FE8 Ch7', 'FE8 Ch8')

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


def _in_recruit_order(talked, talk, ref):
    """A chapter's talk recruits in the order they can join: each after the unit that recruits
    it. Two recruits whose order nothing fixes (neither recruits the other, directly or down a
    chain) would join in the player's order, so that raises instead of guessing."""
    def depth(r):                           # how many talk recruits must join before this one
        n, actor, chain = 0, talk.get(r.char), {r.char}
        while actor in talk:
            if actor in chain:
                raise ValueError('%s: talk recruits %s recruit each other' % (ref, sorted(chain)))
            chain.add(actor)
            n, actor = n + 1, talk.get(actor)
        return n
    ranked = sorted(talked, key=depth)
    if len({depth(r) for r in ranked}) != len(ranked):
        raise ValueError('%s: talk recruits %s are independent, so their slot order depends on '
                         'the player' % (ref, [r.char for r in ranked]))
    return ranked


def _opening_udefs(stem):
    """The UnitDefinition arrays a vanilla chapter's opening scene (`*_BeginningScene`) loads:
    the units on the map before the player's first move."""
    script = inject.decomp.vanilla_decomp_text('src/events/%s-eventscript.h' % stem)
    m = re.search(r'EventScr_\w+_BeginningScene\[\]\s*=\s*\{(.*?)\n\};', script, re.S)
    return set(re.findall(r'\b(UnitDef_\w+)', m.group(1))) if m else set()


def _talk_recruits(stem):
    """Characters a chapter's talk events recruit, {target: actor}, from each `CHAR(flag,
    script, actor, target)` in its eventinfo (Eirika->Ross, Ross->Garcia, Neimi->Colm,
    Natasha->Joshua) whose script turns the target blue: `CUSA(target)` in it or in a script
    it CALLs. A talk that is only a conversation (ch15b's) recruits no one."""
    info = inject.decomp.vanilla_event_files().get('src/events/%s-eventinfo.h' % stem)
    if info is None:
        return {}
    scripts = inject.decomp.vanilla_event_scripts()

    def turns_blue(label, target, seen):
        body = scripts.get(label)
        if body is None or label in seen:
            return False
        seen.add(label)
        return (re.search(r'\bCUSA\(\s*%s\s*\)' % target, body) is not None
                or any(turns_blue(c, target, seen) for c in re.findall(r'\bCALL\(\s*(\w+)\s*\)', body)))
    return {target: actor for label, actor, target in re.findall(
        r'\bCHAR\([^,]+,\s*(\w+)\s*,\s*(\w+)\s*,\s*(CHARACTER_\w+)\s*\)', info)
        if turns_blue(label, target, set())}


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
    for _name, u in _chapter_udef_pairs(stem):
        yield u


def _chapter_udef_pairs(stem):
    """`_chapter_udefs`, each unit with the array it comes from: (array name, unit)."""
    script = inject.decomp.vanilla_decomp_text('src/events/%s-eventscript.h' % stem)
    for name in dict.fromkeys(re.findall(r'\b(UnitDef_\w+)', script)):
        for u in vanilla_udefs_named(stem, name):
            yield name, u


@functools.lru_cache(maxsize=None)
def vanilla_recruits():
    """Everyone FE8 recruits along VANILLA_CHAIN, assuming every recruit succeeds, in join order.

    Join order is the unit table's slot order: a unit takes the first free blue slot when it
    joins (`GetFreeBlueUnit` for a LOAD, `UnitChangeFaction` -> `GetFreeUnit` for a recruit,
    bmunit.c). So within a chapter, its BLUE loads join first, in script order, and its talk
    recruits after, each after the unit that recruits it (Ross before Garcia, whom Ross talks
    over). No two talk recruits of one early chapter are independent, so no order here waits
    on the player (#510 step 5).

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
        opening = _opening_udefs(stem)
        loaded, later, talked = [], [], []
        for name, u in _chapter_udef_pairs(stem):
            char = u['charIndex']
            if (not char or char in seen or not u['items']
                    or _character_number(char) not in PLAYABLE_PIDS):
                continue
            if u['allegiance'] == 'FACTION_ID_BLUE':
                (loaded if name in opening else later).append(VanillaRecruit(
                    char, u['classIndex'], u['level'], tuple(u['items']), index))
            elif char in talk:
                talked.append(VanillaRecruit(char, u['classIndex'], u['level'],
                                             tuple(u['items']), index + 1))
            else:
                continue
            seen.add(char)
        out.extend(loaded + later + _in_recruit_order(talked, talk, ref))
        if later and talked:
            # A mid-chapter arrival and a talk recruit join in whichever order the player
            # meets them, so their slot order is not the decomp's to give.
            raise ValueError('%s: %s arrive(s) mid-chapter and %s join(s) by talk, so their '
                             'slot order depends on the player' % (
                                 ref, [r.char for r in later], [r.char for r in talked]))
    return tuple(out)


def _vanilla_members(parity_ref, path='guaranteed'):
    """(char, class_enum, arsenal) for every vanilla recruit that can deploy into `parity_ref`,
    or None for a twin off VANILLA_CHAIN. The arsenal is `kits.arsenals` on `path`: the
    joining load plus what the chain hands the party (#510 step 8). The guaranteed path is the
    joining load plus the gifts a scene hands a NAMED character, like Eirika's Prologue
    Rapier, which is not on her joining load."""
    import kits
    if parity_ref not in VANILLA_CHAIN:
        return None
    index = VANILLA_CHAIN.index(parity_ref)
    recruits = [r for r in vanilla_recruits() if r.fields_from <= index]
    members = [kits.Member(r.char, _can_use(r.class_enum, r.char), tuple(r.items), r.char)
               for r in recruits]
    kit = kits.arsenals(kits.twin_pickups(index), index, members, path)
    return [(r.char, r.class_enum, kit[r.char]) for r in recruits]


def vanilla_party(parity_ref, levels=None):
    """The vanilla party that can deploy into `parity_ref`, as Combatants, or None for a twin off
    VANILLA_CHAIN. `levels` maps CHARACTER_* to the level it arrives at (`exp_curve.entering`);
    a character missing from it is at its join level. Weapon = the joining load's first
    attacking item, as our cast is armed; a staff-only healer is weaponless support (#62)."""
    members = _vanilla_members(parity_ref)
    if members is None:
        return None
    levels = levels or {}
    return [_ally_combatant(char, class_enum, arsenal[0] if arsenal else None, levels.get(char))
            for char, class_enum, arsenal in members]


def vanilla_party_careers(parity_ref, levels=None, path='guaranteed'):
    """`vanilla_party`, once per simulated career: {name: [Combatant]}, each carrying its
    arsenal on `path` (#510 step 8)."""
    members = _vanilla_members(parity_ref, path)
    if members is None:
        return None
    levels = levels or {}
    return {_ally_name(char): [_stats_to_combatant(_ally_name(char), line,
                                                   arsenal[0] if arsenal else None,
                                                   class_tags(class_enum), arsenal)
                               for line in _ally_lines(char, class_enum, levels.get(char))]
            for char, class_enum, arsenal in members}


def accept_residual(verdict, matchup, residual, band=0.25):
    """A clear-load the PARTY runs harder, accepted by decision (#430 step 6). ch01-ch02 carry
    vanilla's Seth-less cost (ADR 0042): our party clears their force at x1.41 the twin's
    rounds while the force itself copies its twin. `residual` is the chapter's
    `accepted_residual: {party_clear_load: <ceiling>, adr: <decision>}`.

    It excuses the party half of a harder clear-load, up to its ceiling, and nothing else.
    Threat is never excused, and the force half (what authoring controls) still has to hold
    the band, so a force that drifts fails the read as before. Returns `verdict` itself when
    nothing is excused, else a copy marked OK that carries `accepted`."""
    if not residual:
        return verdict
    if not isinstance(residual, dict) or 'adr' not in residual \
            or not isinstance(residual.get('party_clear_load'), (int, float)):
        raise ValueError('accepted_residual must name a numeric party_clear_load and the adr '
                         'that accepted it, got %r' % (residual,))
    if matchup is None or verdict['threat'] != 'OK' or verdict['load'] != 'harder':
        return verdict
    if abs(matchup['force'][1] - 1) > band or matchup['party'][1] > residual['party_clear_load']:
        return verdict
    return dict(verdict, verdict='OK', accepted=residual)


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
    generics on each chapter's own pid, a clone of a vanilla generic with baseLevel 1
    (ADR 0352), or on ch04's monster gaps, which carry baseLevel 1 too."""
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
        kit = {cls: [{'id': w} for w in by_class.get(cls, [])] for cls, _lv in bodies}
        units = [_one_enemy('%s-%s' % (name, cls), cls, lv, _weapon_for(kit[cls]),
                            mode=mode, shifts=shifts,
                            base_level=_our_base_level(dict(ed, level=lv)),
                            shiftable=_our_takes_difficulty_shift(ed),
                            arsenal=_weapons_for(kit[cls]), **_our_load_kwargs(ed))
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


ForceBody = collections.namedtuple('ForceBody', 'key entry index unit ai')


def chapter_force(chap, mode=None, shifts=None, with_ai=True):
    """THE our-side force walk: one `ForceBody` (roster key, entry, index in the entry,
    real-article Combatant, the 4 AI bytes of its own position's donor) per body our chapter
    fields, staff-only and weaponless bodies included, Difficult-only entries on every mode.

    It exists as one function because it was three. `solo_contributors` once kept a copy that
    collapsed a `composition` to its distinct classes (#285); the parity read's force and
    `danger_map.bodies` each re-walked the roster, so the board and the combat read could
    disagree about which body was which (#510 step 7). Every our-side reader reshapes this.
    `with_ai=False` leaves `ai` None for a reader that never asks how a body behaves, so it
    does not demand a donor of every entry."""
    return [ForceBody(key, ed, index, unit,
                      tuple(enemy_ai_bytes(chap, ed, index)) if with_ai else None)
            for key in inject.raw_pids.ENEMY_ROSTER_KEYS
            for ed in chap.get(key) or () if isinstance(ed, dict)
            for index, unit in enumerate(_entry_combatants(
                ed, mode=mode, shifts=shifts, real_article=True, drop_staff=False))]


def chapter_units(chap, mode=None, shifts=None):
    """(enemy_def, real-article Combatant) for every BODY our chapter fields, weapons modeled:
    `chapter_force` with the bodies that carry no modeled weapon left out."""
    return [(f.entry, f.unit) for f in chapter_force(chap, mode, shifts, with_ai=False)
            if f.unit.weapon is not None]


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
    if fc.is_array(rounds):                  # one read over many careers (`party_matchup`)
        import numpy
        connects = fc.expected_hits(yardstick, enemy)
        with numpy.errstate(divide='ignore'):
            floor = numpy.where(connects > 0, enemy.hp / numpy.where(connects > 0, connects, 1),
                                float('inf'))
        return numpy.where(numpy.isinf(rounds), floor, rounds)
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


def party_matchup(bodies, careers, deploy_cap=None, forced=(), engage=None):
    """Instrument v2, layer 1 (#430 step 2b): a force measured against the party that meets it.

    `bodies` is [(enemy Combatant, combat-weight table)], `careers` is {unit: [Combatant]} for
    the ARRIVING party in join order, once per simulated career (ADR 0311). Each joint career
    fields its own `deploy_cap` units, `forced` ones first (`_fielded`, #510 step 5); with no
    cap, everyone arriving fights. Per joint career:

      threat/slot = the HEAVIEST ENGAGEMENT (#510 step 7, ADR 0364): over `engagements`
                    (`timeline.engagements`, sets of indices into `bodies`), the largest sum
                    of its members' damage per round against the unit FE8's AI would attack,
                    with whichever carried weapon it picks for that target (`ai_target.
                    pick_attack`'s rule), / units fielded. Taken per joint career. `engage`
                    maps the modal field ({unit: [Combatant]}, as `fielded_careers` reads it)
                    to {'engagements', 'swung'} (`timeline.engage`); without it
                    every enemy is one engagement.
      clear-load  = sum over enemies of 1 / the field's COMBINED kill rate on it (the sum of
                    1 / rounds): the party-rounds the force takes to clear. Harmonic, because
                    a plain mean of rounds is dominated by whoever cannot dent the boss; a
                    member who cannot dent it, or carries no weapon, adds no rate but stays a
                    target. Only when NOBODY fielded can dent it does the rate fall back to
                    `metric_rounds_to_kill`'s floor, the one place the cliff it exists for
                    reappears.

    `swung` is the bodies that attack before the party fights them (a wave's members): FE8
    equips the item an AI attack used, so each DEFENDS in clear-load with the weapon it picked
    against the target it picked, per career, not its first. Every other body defends with
    its equipped weapon.

    Each side is normalised by its own field, so a twin that fields two units (vanilla's
    prologue) is not divided by our eight. Every enemy body is rolled per career (`_joint`).
    Returns {'threat', 'clear'} as averages over the joint careers, 'per_enemy': a (name,
    threat, clear, weapon) average for each body, in order, 'fielded': the share of careers
    each arriving unit is fielded in, and 'engagement': the engagement that is heaviest in the
    most careers (None without `engagements`)."""
    import numpy                            # not at the top: CI's checks job has no numpy
    names = _map_order(careers, forced)
    armed = [k for k, m in enumerate(names) if careers[m][0].weapon is not None]
    n, party, field = _joint(careers, names, [e for e, _w in bodies])
    fielded = _fielded(party, field, deploy_cap, forced)
    team = _modal_team(names, fielded)
    met = engage({m: careers[m] for m in team}) if engage else {}
    engagements, swung = met.get('engagements'), met.get('swung', frozenset())
    inf = float('inf')
    per = []
    targeted = [0] * len(names)             # how often the AI picks each unit, for the record
    with numpy.errstate(divide='ignore'):
        for j, (body, (e, weights)) in enumerate(zip(field, bodies)):
            arms = fc.arms(body)
            threat = numpy.zeros(n)
            defends = [(body, None)]        # (Combatant it defends as, careers it does)
            if arms and names:              # a weaponless body attacks no one
                # The enemy ATTACKS with whichever carried weapon the AI picks against a
                # FIELDED target (`fc.arms`, #510 step 3) and DEFENDS with its equipped one.
                # AiAttemptOffensiveAction: items outer, targets inner, kept on `>=`, so a tie
                # goes to the LATER weapon, then the later target in unit order, which is
                # `_map_order` (cp_battle.c): the last maximum in (weapon, target) order.
                pairs = [(a, party[m]) for a in arms for m in names]
                scores = numpy.array([ai_target.combat_score(a, u, weights) for a, u in pairs])
                scores = numpy.where(numpy.tile(fielded, (len(arms), 1)), scores, -inf)
                picked = len(pairs) - 1 - numpy.argmax(scores[::-1], axis=0)
                dprs = numpy.array([fc.damage_per_round(a, u) for a, u in pairs])
                threat = dprs[picked, numpy.arange(n)]
                for k, count in enumerate(numpy.bincount(picked % len(names),
                                                         minlength=len(names))):
                    targeted[k] += int(count)
                if j in swung and len(arms) > 1:
                    weapon = picked // len(names)
                    defends = [(a, weapon == w) for w, a in enumerate(arms)]

            def summed(term):
                return sum(term(d) if mask is None else numpy.where(mask, term(d), 0.0)
                           for d, mask in defends)
            # A member strikes with whichever carried weapon kills fastest (#510 step 8).
            rate = sum(numpy.where(fielded[k], summed(
                lambda d: 1.0 / fc.best_rounds_to_kill(party[names[k]], d)), 0.0)
                for k in armed)
            if armed and not numpy.all(rate > 0):   # the floor only reads where nobody dents it
                floor = sum(numpy.where(fielded[k], summed(
                    lambda d: 1.0 / fc.best_rounds_to_kill(
                        party[names[k]], d, rounds=lambda a, e: metric_rounds_to_kill(e, a))),
                    0.0) for k in armed)
                rate = numpy.where(rate > 0, rate, floor)
            elif not armed:
                rate = numpy.zeros(n)
            clear = float(numpy.where(rate > 0, 1.0 / numpy.where(rate > 0, rate, 1), inf).sum())
            per.append((threat, clear))
    slots = max(1, min(len(names), len(names) if deploy_cap is None else deploy_cap))
    heaviest = None
    if not engagements:                     # no board, or nothing on it groups: all at once
        worst = sum(p[0] for p in per)
    else:
        loads = numpy.array([sum((per[j][0] for j in g.members), numpy.zeros(n))
                             for g in engagements])
        worst = loads.max(axis=0)
        heaviest = engagements[int(numpy.bincount(loads.argmax(axis=0)).argmax())]
    return {'threat': float(numpy.sum(worst)) / n / slots,
            'clear': sum(p[1] for p in per) / n,
            'per_enemy': [(e.name, float(numpy.sum(p[0])) / n, p[1] / n, e.weapon.name)
                          for (e, _t), p in zip(bodies, per)],
            'engagement': heaviest,
            'fielded': {m: float(fielded[k].mean()) for k, m in enumerate(names)},
            'targeted': {m: targeted[k] / (n * max(1, len(bodies))) for k, m in enumerate(names)},
            'team': team}


def _modal_team(names, fielded):
    """The team fielded in the most joint careers, in map order (the first seen on a tie)."""
    picks = collections.Counter(tuple(names[k] for k in col.nonzero()[0]) for col in fielded.T)
    return list(picks.most_common(1)[0][0]) if picks else []


def _map_order(careers, forced=()):
    """The arriving party in the order its units sit in the ROM's unit table, which is the
    order FE8's AI breaks a tie in: `SortPlayerUnitsForPrepScreen` (prepscreen.c) pushes the
    force-deployed units first, then everyone else, each in their existing order, which is the
    order they joined (`careers` comes in join order: ours `inject.cast.load_order`, read off the
    ROM by `ch07blueorder`; the twin's `vanilla_recruits`, from the decomp's LOADs and talks)."""
    return ([m for m in careers if m in forced]
            + [m for m in careers if m not in forced])


def _joint(careers, names, force):
    """The joint careers (`career_pairing`) of a party and a force, each unit read over all of
    them at once: (n, {unit: Combatant with array stats}, [Combatant with array stats]).
    Every enemy body is rolled as the engine loads it (`_rolled_stats`, #510 step 4) and is a
    career of its own, independent of every other body's, identical bodies included."""
    rolled = [_rolled_stats(e) for e in force]
    counts = {m: len(careers[m]) for m in names}
    counts.update({'body#%d' % j: ENEMY_TRIALS if r else 1 for j, r in enumerate(rolled)})
    n, order = career_pairing(counts)
    party = {m: _over_careers(careers[m], order[m]) for m in names}
    return n, party, [_over_careers([e], order['body#%d' % j], r)
                      for j, (e, r) in enumerate(zip(force, rolled))]


def _fielded(party, field, deploy_cap, forced=()):
    """bool array (unit, joint career): who the player fields, chosen per career (#510 step 5).
    Every force-deployed unit, then the best of the rest by single-target kill rate (each unit's
    best `kills_per_round` against the enemies this career meets), up to `deploy_cap`; a tie
    goes to the earlier unit, as a stable sort does. Everyone, when the party fits under the
    cap."""
    import numpy
    names = list(party)
    n = len(next(iter(party.values())).hp) if party else 0
    if deploy_cap is None or deploy_cap >= len(names):
        return numpy.ones((len(names), n), dtype=bool)
    keys = numpy.array([
        numpy.full(n, float('inf')) if m in forced else
        numpy.max([numpy.zeros(n) + fc.kills_per_round(party[m], b) for b in field], axis=0)
        if field else
        numpy.zeros(n) for m in names])
    ranked = numpy.argsort(-keys, axis=0, kind='stable')
    out = numpy.zeros((len(names), n), dtype=bool)
    out[ranked[:deploy_cap], numpy.arange(n)] = True
    return out


_CAREER_STATS = ('hp', 'pow', 'skl', 'spd', 'df', 'res', 'lck', 'con')


def _over_careers(lines, index, stats=None):
    """One Combatant whose stats are arrays: `lines[index[i]]` at position i. `stats`, when
    given, is a rolled enemy's {field: array} (`_rolled_stats`) to read instead of `lines`."""
    import numpy
    index = numpy.asarray(index)
    if stats:           # its rolls, and its one line for what a load does not roll (Con)
        columns = {f: numpy.full(ENEMY_TRIALS, getattr(lines[0], f)) for f in _CAREER_STATS}
        columns.update(stats)
    else:
        columns = {f: numpy.array([getattr(u, f) for u in lines]) for f in _CAREER_STATS}
    return dataclasses.replace(lines[0], **{f: v[index] for f, v in columns.items()})


def _median_combatant(careers):
    """A unit's per-stat median over its careers (`_median_line`'s rule), as one Combatant.
    The careers come in the order they were rolled, so any one of them is a random draw."""
    first = careers[0]
    mid = len(careers) // 2
    return dataclasses.replace(first, **{
        f: sorted(getattr(c, f) for c in careers)[mid]
        for f in ('hp', 'pow', 'skl', 'spd', 'df', 'res', 'lck', 'con')})


def fielded_careers(careers, force, deploy_cap, forced=()):
    """The field a player most often deploys against `force` (`_fielded`, chosen per career),
    in map order, with all of its units' careers: {unit: [Combatant]}. The one team the
    readers that want one (the timeline, the boss checks, the report) read; the parity read
    itself fields per career."""
    names = _map_order(careers, forced)
    _n, party, field = _joint(careers, names, list(force))
    return {m: careers[m] for m in _modal_team(names, _fielded(party, field, deploy_cap, forced))}


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
    magic = fc.is_magic(binding.weapon.kind)
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
    hits = sorted(glob.glob(os.path.join(campaign_chapters.chapters_dir(campaign), ch + '*.yaml')))
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
    n = int(chap['chapter_number'])
    return _party_careers(campaign, exp_curve.entering(campaign, n)['party'], n)


def _party_careers(campaign, party, chapter, path='guaranteed'):
    """{uid: careers} for an arriving party, in the order the ROM loads it
    (`inject.cast.load_order`): the order the AI breaks a target tie in (`_map_order`). Each
    unit carries its kit entering `chapter` on `path` (`_our_kits`, #510 step 8); the default
    is the guaranteed path, as `vanilla_party_careers`'s is, so a report compares like with
    like. The parity read passes the path it grades."""
    order = inject.cast.load_order(campaign)
    unknown = sorted(set(party) - set(order))
    if unknown:
        sys.exit('ERROR: %s arrive(s) in the party but the build loads no such unit '
                 '(inject.cast.load_order reads PORTRAIT_MAP)' % ', '.join(unknown))
    uids = sorted(party, key=order.index)
    kit = _our_kits(campaign, uids, chapter, path)
    return {uid: player_careers(campaign, uid, party[uid][1] - party[uid][0], kit[uid])
            for uid in uids}


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


def _report_unwritten(chap, campaign):
    """The per-chapter report of a chapter not written yet: there is none. A chapter is read
    as it is built (Nicolas, 2026-10-23, ADR 0363): neither its draft nor its twin is read
    for it until it is written."""
    bar = '=' * 80
    print(bar)
    print('CH%s "%s" -- NOT WRITTEN YET (status: planned)'
          % (chap.get('chapter_number'), chap.get('title', '?')))
    print(bar)
    print('No difficulty reading until it is written; its draft YAML and its twin (%s) are '
          'not read.' % (chap.get('parity_reference') or '?'))


def report(campaign, ch, mode=None):
    import exp_curve                        # exp_curve imports this module
    head = chapter_schema.load(chapter_path(campaign, ch))
    if head.get('status') == 'planned':
        _report_unwritten(head, campaign)
        return
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
    print('Field: deploy %d of %d cast   Enemies: %s' % (deploy_limit, len(roster),
                                                          '; '.join(labels)))

    ours_lv = {uid: lv for uid, (_j, lv) in arriving['party'].items()} if arriving else {}
    ours_careers = (_party_careers(campaign, arriving['party'], int(num)) if arriving
                    else {u.name: [u] for u in roster})
    if guests:
        ours_careers = guests
        ours_lv = {pu['id']: pu.get('level', 1) for pu in chap.get('player_units') or []}
    profiles = {uid: dice_profile(c, line, bosses) for uid, c in ours_careers.items()}
    _print_cast('OUR CAST, AS IT ARRIVES (class base + donor line, grown to the exp model\'s '
                'typical level)', roster, ours_lv, line, profiles)

    picked = fielded_careers(ours_careers, line, deploy_limit)
    field = [u for u in roster if u.name in picked]
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
        picked = fielded_careers(vanilla_party_careers(ref, vanilla_lv), line, deploy_limit,
                                 vanilla_forced(ref))
        van = [u for u in roster_van if u.name in picked]
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
    _print_kit_paths(chap, campaign, mode)
    print_role_findings(chap, chap.get('parity_reference'), campaign, mode)
    import strategy                         # strategy imports this module
    strategy.print_strategy(chap, campaign, mode)
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
        out['verdict'] = accept_residual(pressure_verdict(out['ours'], out['vanilla'], band),
                                         matchup, chap.get('accepted_residual'), band)
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
                                             class_tags(class_enum))]
    return out


def chapter_matchup(chap, campaign, mode=None, path='happy'):
    """The headline parity ratio (#430 step 2b): (our force vs our arriving party) /
    (the twin's force vs the twin's arriving party), threat and clear-load.

    None for a twin off VANILLA_CHAIN (vanilla's party there is not
    simulated), or when the exp model refuses to price our party -- the caller falls back
    to the fixed YARDSTICK and says so."""
    ref = chap.get('parity_reference')
    if ref not in VANILLA_CHAIN:
        return None
    # Keyed on the chapter's CONTENT, not its id: a test or canary that doctors a chapter
    # dict must not be served the undoctored reading.
    key = (campaign, mode, path, json.dumps(chap, sort_keys=True, default=str))
    if key not in _MATCHUPS:
        _MATCHUPS[key] = _chapter_matchup(chap, campaign, mode, path)
    return _MATCHUPS[key]


_MATCHUPS = {}


def _chapter_matchup(chap, campaign, mode, path):
    fields = arriving_fields(chap, campaign, mode, path)
    if fields is None:
        return None
    import timeline                         # timeline imports this module
    cap, forced = fields['cap'], fields['van_forced']
    # Threat is the heaviest engagement each party meets on its own board (#510 step 7).
    met = timeline.matchup_engagements(chap, fields)
    ours = party_matchup(fields['our_force'], fields['our_party'], cap, engage=met['ours'])
    van = party_matchup(fields['van_force'], fields['van_party'], cap, forced,
                        engage=met['vanilla'])
    # The twin's force against OUR party splits the headline in two: the force effect is
    # what authoring controls, the party effect is what the party brings (#430 step 3).
    cross = party_matchup(fields['van_force'], fields['our_party'], cap, engage=met['cross'])

    def ratio(a, b, key):
        return a[key] / b[key] if b[key] else float('inf')
    return {'ours': ours, 'vanilla': van,
            'field': (ours['team'], van['team']),
            'threat_ratio': ratio(ours, van, 'threat'), 'load_ratio': ratio(ours, van, 'clear'),
            'force': (ratio(ours, cross, 'threat'), ratio(ours, cross, 'clear')),
            'party': (ratio(cross, van, 'threat'), ratio(cross, van, 'clear')),
            'cross': cross,
            'forces': ([b for b, _w in fields['our_force']], [b for b, _w in fields['van_force']]),
            'arrivals': ([b.arrives for b in fields['our_bodies']],
                         [b.arrives for b in fields['van_bodies']]),
            'lines': {m: _median_combatant(fields['our_party'][m]) for m in ours['team']},
            'lines_vanilla': {m: _median_combatant(fields['van_party'][m]) for m in van['team']}}


def arriving_fields(chap, campaign, mode=None, path='happy'):
    """Both sides of a parity read: each force as [(Combatant, combat-weight table)] and, index
    for index, as the `danger_map.Body`s it came from ('our_bodies', 'van_bodies'), each
    ARRIVING party in join order, {unit: [Combatant]} over the careers, the deploy `cap` and
    the twin's `van_forced` units. Each party carries its kit on `path` ('happy' graded,
    'guaranteed' printed beside it, ADR 0365). A reader that wants one team asks
    `fielded_careers`. None
    for a twin off VANILLA_CHAIN or a party the exp model cannot price -- `chapter_matchup`'s
    fallback."""
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
    import danger_map                       # danger_map imports this module
    # One list per side, read by the board and the combat read alike, so an index into the
    # force is an index onto the map (#510 step 7). A body with no modeled weapon is in
    # neither: it attacks no one and the clear-load has never counted it.
    our_bodies = [b for b in danger_map.bodies(chap, mode, every_mode=True)
                  if b.unit.weapon is not None]
    van_bodies = danger_map.vanilla_bodies(ref, mode)
    our_force = [(b.unit, ai_target.combat_weight_table(b.ai)) for b in our_bodies]
    van_force = [(b.unit, ai_target.combat_weight_table(b.ai)) for b in van_bodies]
    # Each party carries its kit on `path` (#510 step 8): the verdict reads 'happy'.
    our_party = fixed_roster_careers(chap) or _party_careers(
        campaign, arriving['party'], int(chap['chapter_number']), path)
    van_party = vanilla_party_careers(ref, arriving['vanilla'], path)
    van_forced = vanilla_forced(ref)
    return {'our_force': our_force, 'van_force': van_force,
            'our_bodies': our_bodies, 'van_bodies': van_bodies,
            'our_party': our_party, 'van_party': van_party, 'cap': cap, 'van_forced': van_forced}


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
        load[_label(name, weapon)] += clear
    total = sum(load.values()) or 1.0
    return ', '.join('%s %.0f%%' % (n, 100 * c / total) for n, c in load.most_common(top))


def _label(name, weapon):
    """A body's name for the report: a named vanilla body by its charIndex
    (`...#3[CHARACTER_SAAR]`), a vanilla generic (a bare pid) by the weapon it carries."""
    label = name[name.index('[') + 1:-1] if '[' in name else name
    label = '%s generic' % weapon if label.startswith('0x') else label
    return label.replace('CHARACTER_', '').lower()


def _engagement(side):
    """The engagement a side's threat is read from (#510 step 7), in words."""
    g = side.get('engagement')
    if g is None:
        return 'all at once (no board)'
    names = collections.Counter(_label(side['per_enemy'][k][0], side['per_enemy'][k][3])
                                for k in g.members)
    where = ('wave on enemy phase %d' % g.phase if g.kind == 'wave' else
             'pocket pulled from %s' % (g.tile,) if g.tile else 'pocket')
    return '%s, %d bodies: %s' % (where, len(g.members), ', '.join(
        '%s x%d' % (n, c) if c > 1 else n for n, c in sorted(names.items())))


def _print_kit_paths(chap, campaign, mode=None):
    """The verdict reads the HAPPY path, every pickup taken; this prints the GUARANTEED path
    beside it (ADR 0365). A wide gap is a chapter whose difficulty hinges on optional pickups.
    Only this report reads the guaranteed path: the curve and the verdict diff never do."""
    happy = chapter_matchup(chap, campaign, mode)
    sure = chapter_matchup(chap, campaign, mode, path='guaranteed')
    if happy is None or sure is None:
        return
    print('  kits: happy path (graded) threat x%.2f · clear-load x%.2f;  guaranteed only '
          'threat x%.2f · clear-load x%.2f'
          % (happy['threat_ratio'], happy['load_ratio'], sure['threat_ratio'],
             sure['load_ratio']))
    import kits
    if any(p.projected for p in kits.our_pickups(campaign)):
        print('        (our world-map stock projected from the twin\'s until campaign.yaml '
              'stocks a town)')


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
              'damage/round\n  on the unit FE8\'s AI targets, summed over the heaviest '
              'engagement (#510 step 7),\n  per unit fielded · clear-load = party-rounds to '
              'clear')
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
        for tag, side in (('ours', mu['ours']), ('vanilla', mu['vanilla'])):
            print('  engagement (%s): %s' % (tag, _engagement(side)))
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
    if v.get('accepted'):
        print('  verdict: PARITY with an accepted residual -- party clear-load x%.2f within the '
              'x%.2f ADR %04d accepted;\n           the force holds the band'
              % (p['matchup']['party'][1], v['accepted']['party_clear_load'],
                 int(v['accepted']['adr'])))
    else:
        print('  verdict: %s' % ('PARITY (within band)' if v['verdict'] == 'OK'
                                 else 'OFF-PARITY -- threat %s, clear-load %s'
                                 % (v['threat'], v['load'])))
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
    ids, by_table = _terrain_data()
    return ids, by_table['Avo_Common'], by_table['Def_Common']


def _terrain_data():
    """(id->name, {'Avo_Common': {name: bonus}, ...}) for the Common and Fly avoid, defense
    and resistance tables, parsed from the decomp at HEAD."""
    if 'tables' not in _TERRAIN_CACHE:
        ids = {int(v, 16): k for k, v in re.findall(
            r'(TERRAIN_\w+)\s*=\s*(0x[0-9A-Fa-f]+)',
            inject.decomp.vanilla_decomp_text('include/constants/terrains.h'))}
        text = inject.decomp.vanilla_decomp_text('src/data_terrains.c')

        def table(name):
            i = text.find('s8 TerrainTable_%s[] = {' % name)
            return {k: int(v) for k, v in re.findall(
                r'\[(TERRAIN_\w+)\]\s*=\s*(-?\d+)', text[i:text.find('};', i)])}
        _TERRAIN_CACHE['tables'] = (ids, {t: table(t) for t in (
            'Avo_Common', 'Def_Common', 'Res_Common', 'Avo_Fly', 'Def_Fly', 'Res_Fly')})
    return _TERRAIN_CACHE['tables']


def _terrain_key(terrain_name):
    key = str(terrain_name or '').upper()
    return key if not key or key.startswith('TERRAIN_') else 'TERRAIN_' + key


def terrain_bonus(terrain_name):
    """(avoid, defense) a foot unit gains on `terrain_name` (e.g. 'TERRAIN_THRONE')."""
    _ids, avo, dfn = _terrain_tables()
    key = _terrain_key(terrain_name)
    return avo.get(key, 0), dfn.get(key, 0)


def terrain_cover(terrain_name, flier=False):
    """(avoid, defense, resistance) a unit gains on `terrain_name`: the Common tables for a
    foot or mounted unit, the Fly tables for a flier (who gets nothing from a forest)."""
    _ids, t = _terrain_data()
    key, kind = _terrain_key(terrain_name), 'Fly' if flier else 'Common'
    return tuple(t['%s_%s' % (stat, kind)].get(key, 0) for stat in ('Avo', 'Def', 'Res'))


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
    """`combatant` as it fights while standing on `terrain_name`, and the tile's avoid, which
    the metrics take as `terrain_avoid`: (combatant, avoid). The tile's Def and Res are folded
    into df and res: FE8's `ComputeBattleUnitDefense` adds terrainDefense, or
    terrainResistance against magic (bmbattle.c)."""
    avo, dfn, res = terrain_cover(terrain_name, 'flier' in combatant.tags)
    return dataclasses.replace(combatant, df=combatant.df + dfn, res=combatant.res + res), avo


def _tile_text(tile, combatant):
    """' on TILE (+avo/+def[/+res])', what `on_terrain` gives `combatant` there; '' off a tile."""
    if not tile:
        return ''
    avo, dfn, res = terrain_cover(tile, 'flier' in combatant.tags)
    return ' on %s (+%d avo/+%d def%s)' % (tile, avo, dfn, '/+%d res' % res if res else '')


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


# Where a chapter's red force is authored (inject.raw_pids.ENEMY_ROSTER_KEYS), waves included.
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


def role_findings(chap, parity_ref, campaign=None, mode=None):
    """Per-unit role warnings: outlier threat vs the twin's ceiling, and a boss that is not
    the chapter's real centre of gravity. Returns a list of strings (empty == clean).

    With a `campaign` and a twin the party model reaches, every arm reads both forces against
    the party that meets ours (`_role_findings_vs_party`), each side loaded for `mode` (#510
    step 2): a boss that holds on Normal can still fold on Tutorial. Otherwise it falls back to
    the fixed YARDSTICK on the declared levels, as the aggregate does off VANILLA_CHAIN."""
    if campaign and parity_ref in VANILLA_CHAIN:
        matchup = chapter_matchup(chap, campaign, mode=mode)
        if matchup is not None:
            return _role_findings_vs_party(chap, parity_ref, matchup, mode)
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
        where = _tile_text(tile, b)
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


def _boss_durability_vs_party(entries, parity_ref, lines, mode=None, shifts=None):
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
    twin = [party_rounds(c) for n, c in vanilla_named_bosses(parity_ref, with_personal=True,
                                                               mode=mode)
            if 'CA_BOSS' in exp_curve.character_attributes('CHARACTER_' + n.upper())]
    bar = max((r for r in twin if r != inf), default=0.0) or \
        max((r for r in map(party_rounds, vanilla_enemies(parity_ref, mode) or []) if r != inf),
            default=0.0)
    out = []
    for ed in entries:
        if not ed.get('is_boss'):
            continue
        tile = ed.get('tile_terrain')
        for c in _entry_combatants(ed, mode=mode, shifts=shifts, real_article=True,
                                   drop_staff=False, distinct=True):
            body, avoid = on_terrain(c, tile)
            where = _tile_text(tile, c)
            rounds = party_rounds(body, avoid)
            if rounds == inf:
                out.append('boss %s%s cannot be damaged by the party that meets it'
                           % (ed.get('id'), where))
            elif bar and rounds < bar * 0.5:
                out.append("boss %s takes %.2f party-rounds to kill%s; %s's boss takes %.2f "
                           'against the same party -- the climax may fold too fast'
                           % (ed.get('id'), rounds, where, parity_ref, bar))
    return out


def _role_findings_vs_party(chap, parity_ref, matchup, mode=None):
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
    shifts = inject.chapter_settings.chapter_difficulty_shifts(chap) if mode else None
    out.extend(_boss_durability_vs_party(entries, parity_ref, list(matchup['lines'].values()),
                                         mode, shifts))
    out.extend(_boss_census(e.get('id') for e in entries if e.get('is_boss')))
    return list(dict.fromkeys(out))


def print_role_findings(chap, parity_ref, campaign=None, mode=None):
    findings = role_findings(chap, parity_ref, campaign, mode)
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
    'FE8 Ch4': 'ch4', 'FE8 Ch5': 'ch5', 'FE8 Ch6': 'ch6', 'FE8 Ch7': 'ch7',
    'FE8 Ch8': 'ch8', 'FE8 Ch13': 'ch13a',
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


def shop_stock(list_sym):
    """The ITEM_x enums an in-map shop's ShopList_ stocks (src/events_shoplist.c, HEAD): the
    one reader of a shop's stock, for the economy, the kits and the wiki."""
    return _shoplist_items(inject.decomp.vanilla_decomp_text('src/events_shoplist.c'), list_sym)


def _shoplist_items(shoplist_text, list_sym):
    """The ITEM_x enums a ShopList_ (or world-map ItemList_) array stocks (ITEM_NONE
    terminator dropped)."""
    m = re.search(re.escape(list_sym) + r'\[\]\s*=\s*\{(.*?)\}', shoplist_text, re.S)
    if not m:
        return []
    return [it for it in re.findall(r'ITEM_\w+', m.group(1)) if it != 'ITEM_NONE']


CHAPTER_MODE_EIRIKA = 2   # include/types.h; the route VANILLA_CHAIN and gen_wiki's twins follow


@functools.lru_cache(maxsize=None)
def _shared_give_scripts():
    """The shared EventListScrs that GIVEITEMTO slot 3: a chapter that CALLs one gives the
    item as surely as with its own GIVEITEMTO. Ch15's nine desert treasures go through
    EventScr_GiveTreasureToLuckyDog, and a chapter-local scan never saw them. It hands the item
    to a Thief or Rogue always (anyone else by a roll), and vanilla's party has one, so the
    treasures count as given. Gold has no such vehicle: the one shared script that moves gold
    (common-events.h's EventScr_9EEB00) charges Rennac's 9,980-gold hire."""
    names = set()
    for rel in ('src/events_script_utils.c', 'src/events/common-events.h'):
        text = inject.decomp.vanilla_decomp_text(rel)
        for m in re.finditer(r'EventListScr\s+(\w+)\[\]\s*=\s*\{(.*?)\n\};', text, re.S):
            if re.search(r'GIVEITEMTO\(', m.group(2)):
                names.add(m.group(1))
    return frozenset(names)


def _merge_gives(a, b):
    """Two alternatives' gives, as `_script_gives` keeps them: per (kind, value), the larger
    count, and every recipient either names."""
    out = dict(a)
    for key, (n, to) in b.items():
        m, was = out.get(key, (0, ()))
        out[key] = (max(n, m), was + tuple(t for t in to if t not in was))
    return out


def _walk_gives(cmds, labels, start, slot3, mode, give):
    """{(kind, value): (count, recipients)} from cmds[start] to the script's end, along the
    path that gives the most per value. The route is known, so a CHECK_MODE branch takes one
    edge; every other branch takes both."""
    memo, active = {}, set()

    def walk(pc, slot3, cmode, slot1):
        key = (pc, slot3, cmode, slot1)
        if key in memo:
            return memo[key]
        if key in active:              # a loop back: its gives are already on this path
            return {}
        active.add(key)
        got = {}
        while pc < len(cmds):
            c = cmds[pc]
            if c.startswith(('ENDA', 'ENDB')):
                break
            m = re.match(r'SVAL\(EVT_SLOT_(\w),\s*(\w+)\)', c)
            if m and m.group(1) == '3':
                slot3 = m.group(2)
            elif m and m.group(1) == '1':
                slot1 = int(m.group(2), 0) if m.group(2)[0].isdigit() else None
            elif c.startswith('CHECK_MODE'):
                cmode = True
            elif c.startswith(('CHECK_', 'Evt', 'CALL', 'RANDOMNUMBER')):   # slot C rewritten
                cmode = False
            g = give(c)
            if g and slot3:
                n, to = got.get((g[0], slot3), (0, ()))
                got[(g[0], slot3)] = (n + 1, to + (() if g[1] in to else (g[1],)))
            m = re.match(r'(GOTO|B[A-Z]{2})\((0x[0-9a-fA-F]+|\d+)(.*)\)', c)
            if m and int(m.group(2), 0) in labels:
                target = labels[int(m.group(2), 0)]
                if m.group(1) == 'GOTO':
                    pc = target
                    continue
                if cmode and slot1 is not None and re.match(r',\s*EVT_SLOT_C,\s*EVT_SLOT_1',
                                                            m.group(3)):
                    if (mode == slot1) == (m.group(1) == 'BEQ'):   # the route's edge jumps
                        pc = target
                        continue
                else:
                    jumped = walk(target, slot3, cmode, slot1)
                    rest = walk(pc + 1, slot3, cmode, slot1)
                    got = _add_gives(got, _merge_gives(rest, jumped))   # source order
                    break
            pc += 1
        active.discard(key)
        memo[key] = got
        return got

    return walk(start, slot3, False, None)


def _add_gives(a, b):
    """Gives made one after the other: counts add."""
    out = dict(a)
    for key, (n, to) in b.items():
        m, was = out.get(key, (0, ()))
        out[key] = (n + m, was + tuple(t for t in to if t not in was))
    return out


@functools.lru_cache(maxsize=None)
def _script_gives(eventscript_text, mode=CHAPTER_MODE_EIRIKA):
    """[(kind, slot-3 value, recipients)] every EventListScr in the text hands out, kind 'item'
    (GIVEITEMTO, or a CALL to a `_shared_give_scripts` script, whose name is the recipient) or
    'gold' (GIVEITEMTOMAIN / GIVETOSLOT3: eventscr.c adds slot 3 to the party's gold). Each
    script is walked as it runs (`_walk_gives`): a give reads the slot-3 value set last on its
    path. Only one arm of a branch runs, so per value a script gives the most any one path
    gives: Ch13a pays 5,000 on each arm of a CHECK_ALIVE, Ch14 hands Audhulma to Joshua if he
    lives and to Eirika if not, and from Ch15 the two routes share a script that gives Eirika
    Gleipnir and Garm and Ephraim Audhulma and Excalibur."""
    shared = _shared_give_scripts()

    def give(c):
        m = re.match(r'(GIVEITEMTO|GIVEITEMTOMAIN|GIVETOSLOT3)\((\w*)\)', c)
        if m:
            return ('item' if m.group(1) == 'GIVEITEMTO' else 'gold', m.group(2))
        m = re.match(r'CALL\((\w+)\)', c)
        return ('item', m.group(1)) if m and m.group(1) in shared else None

    out = []
    for block in re.split(r'CONST_DATA EventListScr', eventscript_text)[1:]:
        cmds = [ln.split('//')[0].strip() for ln in block.splitlines()]
        cmds = [c for c in cmds if c]
        labels = {int(m.group(1), 0): i for i, c in enumerate(cmds)
                  for m in [re.match(r'LABEL\((0x[0-9a-fA-F]+|\d+)\)', c)] if m}
        for (kind, value), (n, to) in _walk_gives(cmds, labels, 0, None, mode, give).items():
            out += [(kind, value, to)] * n
    return out


def _gift_records(eventscript_text):
    """[(ITEM_x, recipients)] for every item the chapter script hands out: village and house
    gifts, clear rewards outside a Village macro (Ch5's all-villages-saved Guiding Ring), gifts
    to a named unit (the Prologue's Rapier, spelled ITEM_SWORD_RAPIER), and the items a shared
    script gives. An event village that only spawns a unit (SVAL to another slot, no give)
    contributes nothing, as it should."""
    id2e = _item_id_to_enum()
    out = []
    for kind, v, to in _script_gives(eventscript_text):
        enum = v if v.startswith('ITEM_') else id2e.get(int(v, 0)) if v[0].isdigit() else None
        if kind == 'item' and enum:
            out.append((enum, tuple(t for t in to if t)))
    return out


def _gift_gold(eventscript_text):
    """Every gold amount the chapter script hands out (`_script_gives`' 'gold')."""
    return sorted(int(v, 0) for kind, v, _ in _script_gives(eventscript_text)
                  if kind == 'gold' and v[0].isdigit())


@functools.lru_cache(maxsize=None)
def _event_group_stems():
    """{ChapterEventGroup symbol: event-file stem}, every eventinfo the decomp includes. One
    `git grep` at HEAD, not a `git show` of each of the ~60 files: this sits on the curve's
    path (the twin's interludes, #510 step 8)."""
    import subprocess
    info = inject.decomp.vanilla_decomp_text('src/events_info.c')
    included = set(re.findall(r'#include "events/(\w+)-eventinfo\.h"', info))
    hits = subprocess.check_output(
        ['git', '-C', inject.decomp.SUBMODULE, 'grep', '-F', 'ChapterEventGroup', 'HEAD',
         '--', 'src/events'], encoding='utf-8', env=inject.decomp.git_env())
    out = {}
    for stem, group in re.findall(r'^HEAD:src/events/(\w+)-eventinfo\.h:.*?ChapterEventGroup\s+(\w+)',
                                  hits, re.M):
        if stem in included:
            out[group] = stem
    return out


def chapter_event_stem(index):
    """The event-file stem of FE8 chapter `index`, through the decomp's own tables: its
    chapter_settings `mapEventDataId` indexes the chapter asset table (data_8B363C.s), whose
    word names a ChapterEventGroup, defined in exactly one events/<stem>-eventinfo.h."""
    table = inject.decomp.asset_table_names(
        inject.decomp.vanilla_decomp_text('data/data_8B363C.s'))
    chapters = json.loads(inject.decomp.vanilla_decomp_text('src/data/chapter_settings.json'))
    chapters = chapters if isinstance(chapters, list) else chapters['chapters']
    if not 0 <= index < len(chapters):
        return None
    return _event_group_stems().get(table[chapters[index]['mapEventDataId']])


def twin_interlude_scripts(eventscript_text):
    """[(stem, script)] for the event-only chapters a twin's ending moves to before the next
    battle. Vanilla Ch1 ends with MoveToChapter(0x38), Castle Frelia (the decomp files it as
    `lordsplit`), and THAT scene pays Ch1's 5,000 gold -- measured on the retail ROM
    (`vanillagold`). A battle chapter is a `prologue`/`chNN` file; anything else reached by a
    hop is the twin's interlude, and what it gives is the twin's."""
    out = []
    for idx in re.findall(r'MoveToChapter\((0x[0-9a-fA-F]+|\d+)\)', eventscript_text):
        stem = chapter_event_stem(int(idx, 0))
        if stem and not re.match(r'(prologue|ch\d)', stem) and stem not in [s for s, _ in out]:
            out.append((stem, inject.decomp.vanilla_decomp_text(
                'src/events/%s-eventscript.h' % stem)))
    return out


def vanilla_drops(parity_ref):
    """The vanilla twin's enemy DROPS, read from HEAD: for each red unit flagged `.itemDrop`
    in the chapter's curated UnitDefinition arrays, its LAST item (US_DROP_ITEM drops the final
    inventory slot -- statscreen.c:726), valued in buy-gold. None if the reference isn't curated;
    [] if it carries no drops (the Ch4/Ch5 lock twins). The channel #170 v1 skipped (#176)."""
    reds = _vanilla_red_defs(parity_ref)
    if reds is None:
        return None
    return [(d['items'][-1], item_gold_value(d['items'][-1]))
            for _a, _i, d in reds if d['itemDrop'] and d['items']]


def twin_event_payload(stem):
    """What a vanilla chapter's events hand out, by vehicle, read once for every consumer
    (vanilla_economy here, gen_wiki's twin payload): chest items and chest gold, scene gifts
    and scene gold, what the interlude after it gives (twin_interlude_scripts), and its shops
    of every kind the eventinfo macros name (Armory, Vendor, SecretShop). `gifts` splits into
    `village_gifts`, what a Village or House script hands out, and `scene_gifts`, every other
    script's (#510 step 8), each with its recipients."""
    info = inject.decomp.vanilla_decomp_text('src/events/%s-eventinfo.h' % stem)
    script = inject.decomp.vanilla_decomp_text('src/events/%s-eventscript.h' % stem)
    gifts = _gift_records(script)
    # Split by the script that gives it, never by matching items (#510 step 8): a Village or
    # House script's gives are the visit's; every other block's are a scene's.
    visits, scenes = [], script
    for name in re.findall(r'(?:Village|House)\(\s*[^,]+,\s*(\w+)', info):
        marker = 'CONST_DATA EventListScr %s[]' % name
        if marker in scenes:
            at = scenes.index(marker)
            s, e = inject.decomp._find_brace_block(scenes, marker, stem)
            end = scenes.index(';', e) + 1 if ';' in scenes[e:e + 3] else e
            visits.append(scenes[at:end])
            scenes = scenes[:at] + scenes[end:]
    village = _gift_records('\n'.join(visits))
    scene = _gift_records(scenes)
    out = {'chests': re.findall(r'Chest\((ITEM_\w+)', info),
           'chest_gold': [int(g) for g in re.findall(r'ChestMoney\(\s*(\d+)', info)],
           'gifts': [e for e, _ in gifts], 'gift_to': [to for _, to in gifts],
           'gift_gold': _gift_gold(script),
           'village_gifts': [e for e, _ in village], 'village_gift_to': [to for _, to in village],
           'scene_gifts': [e for e, _ in scene], 'scene_gift_to': [to for _, to in scene],
           'interlude_gifts': [], 'interlude_gift_to': [], 'interlude_gold': [],
           'shops': [(sym, shop_stock(sym)) for sym in
                     re.findall(r'(?:Armory|Vendor|SecretShop)\(\s*(\w+)', info)],
           'n_villages': len(re.findall(r'Village\(', info)),
           'n_houses': len(re.findall(r'House\(', info))}
    for _stem, inter in twin_interlude_scripts(script):
        for item, to in _gift_records(inter):
            out['interlude_gifts'].append(item)
            out['interlude_gift_to'].append(to)
        out['interlude_gold'] += _gift_gold(inter)
    return out


def vanilla_economy(parity_ref):
    """The vanilla twin's item economy, read from HEAD: chests, gifts (villages/houses/clear
    rewards), shops, and enemy drops, each valued in buy-gold. None if the reference has no
    mapped economy source (#170/#176). Delivery context (# of villages/houses) is kept for the
    vehicle story."""
    stem = PARITY_REFERENCE_STEM.get(parity_ref)
    if stem is None:
        return None
    t = twin_event_payload(stem)
    chests = [(it, item_gold_value(it)) for it in t['chests']]
    gifts = [(it, item_gold_value(it)) for it in t['gifts'] + t['interlude_gifts']]
    drops = vanilla_drops(parity_ref) or []
    shops = t['shops']
    gold = t['chest_gold'] + t['gift_gold'] + t['interlude_gold']
    total = (sum(v for _, v in chests) + sum(v for _, v in gifts) + sum(v for _, v in drops)
             + sum(gold))
    return {'reference': parity_ref, 'chests': chests, 'gifts': gifts, 'drops': drops,
            'gold': gold,
            'shops': shops, 'n_villages': t['n_villages'], 'n_houses': t['n_houses'],
            'total_gold': total}


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
    # (vehicle, the YAML entry) per item, `fe_base` kept: what the kits read (#510 step 8). A
    # visit (village, boat talk) is `village`; what a scene hands out is `scene`.
    pickups = []

    def take(rewards, vehicle):
        """Fold one reward list into gold + gifts. Same shape wherever it is carried."""
        nonlocal gold
        for r in rewards or []:
            if r.get('id') == 'gold':
                gold += int(r.get('amount') or 0)
            elif r.get('id'):
                gifts.append(r['id'])
                pickups.append((vehicle, r))

    for v in chap.get('villages') or []:
        take(v.get('visit_reward'), 'village')
    for boat in chap.get('rescue_boats') or []:
        take((boat.get('talk') or {}).get('reward'), 'village')
    # A green ally's gift for surviving (ch02's chwinga), handed over at the ending (#495).
    for ally in (chap.get('deployment') or {}).get('green_allies') or []:
        if ally.get('gift'):
            take([{'id': ally['gift']}], 'scene')
    bonus = (chap.get('economy') or {}).get('save_all_bonus')
    if bonus:
        take([{'id': bonus}], 'scene')
    # Gold a scene pays (#495): vanilla Ch1's 5,000 after the map, Ch8's 10,000 in its ending.
    for g in (chap.get('economy') or {}).get('scene_gold') or []:
        gold += int(g['amount'])
    for c in chap.get('chests') or []:
        for it in c.get('contents') or []:
            if it.get('id'):
                chests.append(it['id'])
                pickups.append(('chest', it))
    for ed in chapter_roster_entries(chap):
        if ed.get('item_drop'):
            drops.append(ed['item_drop'])
            pickups.append(('drop', {'id': ed['item_drop']}))
    # The in-map shops' stock lists, the same thing vanilla_economy reports for the twin. Not
    # `available_shops`: that is a world-map TOWN label, and reading it made ch02 look stocked
    # beside vanilla Ch2's Armory while ch02 had no shop at all.
    shops = [sym for _macro, sym, _x, _y in inject.villages.chapter_shops(chap)]
    return {'gold': gold, 'gifts': gifts, 'chests': chests, 'drops': drops, 'shops': shops,
            'pickups': pickups}


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
    return inject.decomp.flag_number(eid) not in (0, 'EVFLAG_NONE')


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
    opened = _event_block(script, opening.group(1)) if opening else ''
    armed = {inject.decomp.flag_number(f)
             for f in re.findall(r'ENUT\(\s*([^)]*\)?)\s*\)', opened)}

    def clears(block, flag):
        return any(inject.decomp.flag_number(f) == flag
                   for f in re.findall(r'ENUF\(\s*([^)]*\)?)\s*\)', block))

    def entry(box, block):
        return _zone_entry_turn(ref, box, _zone_trigger(block))

    out = {}
    for eid, scr, turn in _player_turn_events(info):
        flag = inject.decomp.flag_number(eid)
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
                # a declared `arrives_turn` makes it a wave. `entry_is_turn1` is the one
                # place that decides (#367, #440) -- `map_placement_preview.enemy_bodies`
                # and `danger_map` share it.
                g['reinforcements'].extend(units)
            else:
                g['line'].extend(units)
    return g


def vanilla_enemy_groups(parity_ref, mode=None):
    """Vanilla twin force split by role, with convertibles (CHAR targets) and reinforcement
    turns (TurnEventPlayer-loaded arrays) auto-detected from HEAD. None if uncurated."""
    units = vanilla_loaded_units(parity_ref, mode, with_personal=False)
    if units is None:
        return None
    stem = PARITY_REFERENCE_STEM.get(parity_ref)
    conv_chars = _vanilla_convertible_chars(stem) if stem else set()
    reinf_turns = _vanilla_reinforcement_turns(stem) if stem else {}
    g = {'line': [], 'reinforcements': [], 'convertibles': []}
    for arr, i, d, u in units:
        u = dataclasses.replace(u, name='%s#%d' % (arr, i))
        if d['charIndex'] in conv_chars:
            g['convertibles'].append(u)
        elif reinf_turns.get(arr, 1) > 1:
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
    print('  (additive -- turn-1 counts the opening board; the ENEMY-PRESSURE threat above is '
          'the heaviest engagement)')


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


def locked_chapters(campaign):
    """The ids of the chapters content has marked balance-final (`balance_locked: true`)."""
    return {c['id'] for c in map(chapter_schema.load, campaign_chapters.paths(campaign))
            if c.get('balance_locked')}


def gate_failures(campaign, modes=MODES):
    """(locked ids, failures): the --check gate over every difficulty mode (#510 step 2). The
    finished game ships all three of vanilla's modes, so a locked chapter holds parity only if
    it holds in each; a failure is labelled with the mode it failed in. The authored table is
    not one of them: no player meets the levels a chapter declares before its mode's shift.
    Only locked chapters are read, so with none locked the gate costs nothing."""
    locked = locked_chapters(campaign)
    fails = []
    for mode in (modes if locked else ()):
        fails += ['%s (%s)' % (label, mode)
                  for label in curve_gate_failures(curve_report(campaign, mode=mode, only=locked))]
    return locked, fails


def curve_report(campaign, band=0.25, mode=None, only=None):
    """Campaign-wide enemy-pressure curve: one row per authored chapter, ours vs its vanilla
    reference, so spikes/sags across the arc are visible at a glance (#48). Returns the per-chapter
    rows (label / has_ref / verdict / boss_drop) so the --check gate can act on them.

    `mode` grades a difficulty mode on BOTH sides instead of the authored table (#303). The
    banner says which, because a verdict that does not name its configuration is the thing
    #303 set out to fix. `only`, a set of chapter ids, reads just those chapters: the gate
    needs its locked ones and nothing else."""
    paths = campaign_chapters.paths(campaign)
    bar = '=' * 86
    print(bar)
    print('CAMPAIGN ENEMY-PRESSURE CURVE -- ours vs vanilla parity_reference   '
          '[STATIC proxy]')
    print('  difficulty mode: %s'
          % ('%s (both sides shifted by their own chapter\'s numbers)' % mode.upper()
             if mode else 'AUTHORED TABLE (unshifted -- the level each side DECLARES)'))
    if mode:
        print('  NB the role findings of a twin off VANILLA_CHAIN (the yardstick fallback)'
              '\n     are graded on the AUTHORED table, not on %s.'
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
        if only is not None and chap.get('id') not in only:
            continue
        label = 'CH%s %s' % (chap.get('chapter_number'), chap.get('id', ''))
        # `status: planned` chapters are brainstorm SEED, not authoritative -- their enemy
        # roster/levels are re-grounded against vanilla + party data when the slice is reached
        # (the brainstorming skill digests them). The static proxy can't model an ungrounded
        # sketch, so list it as planned rather than printing a phantom 0.0/OFF. It never gates
        # (not added to `rows`); a planned chapter that is also balance_locked is a config error
        # caught by check.py's chapter-status lint.
        if chap.get('status') == 'planned':
            # A chapter is read as it is built (ADR 0363): nothing, its twin included.
            print('  %-22s %-13s   -- planned -- not read until it is written --'
                  % (label[:22], (chap.get('parity_reference', '?') or '?')[:13]))
            continue
        p = _chapter_pressure(chap, band, mode=mode, campaign=campaign)
        ot, ol = p['ours']
        boss_drop = any(d['is_boss'] for d in p['dropped'])
        any_dropped_boss = any_dropped_boss or boss_drop
        locked = bool(chap.get('balance_locked', False))
        flag = '  !!boss dropped' if boss_drop else ''
        if locked:
            flag += '  [locked]'
        if (p.get('verdict') or {}).get('accepted'):
            flag += '  [accepted ADR %04d]' % int(p['verdict']['accepted']['adr'])
        has_ref = p['vanilla'] is not None
        verdict = p['verdict']['verdict'] if has_ref else None
        # The per-unit findings ride along so the gate can read them (#284) -- the aggregate
        # above cannot see a single soft unit, which is exactly how two paper bosses shipped.
        role = role_findings(chap, p['reference'], campaign, mode) if has_ref else []
        if role:
            flag += '  !!role'
        # ... and whether every enemy's AI is grounded in a vanilla donor (#335). Invisible
        # to everything above, which is computed from stats and weapons.
        ai = ai_donor_findings(chap) if has_ref else []
        if ai:
            flag += '  !!ai'
        # The numbers ride along for tools/verdict_diff.py (#510 step 0), which diffs every
        # chapter's row before and after a change instead of trusting the lock.
        v = p.get('verdict') or {}
        rows.append({'label': label[:22].strip(), 'locked': locked, 'has_ref': has_ref,
                     'verdict': verdict, 'boss_drop': boss_drop, 'role': role, 'ai': ai,
                     'mirror': p['mirror'], 'threat': ot, 'clear': ol,
                     'threat_ratio': v.get('threat_ratio'), 'load_ratio': v.get('load_ratio'),
                     'accepted_adr': (int(v['accepted']['adr']) if v.get('accepted')
                                      else None)})
        if not has_ref:
            print('  %-22s %-13s %5.1f           %5.1f             %-7s (no ref)%s'
                  % (label[:22], (p['reference'] or '?')[:13], ot, ol, '--', flag))
            continue
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
                         'finding, in ANY of the three modes (#510 step 2; --mode grades one). '
                         'UNLOCKED chapters never gate')
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
    if args.curve and args.check:
        locked, fails = gate_failures(args.campaign, (args.mode,) if args.mode else MODES)
        if not locked:
            print('PARITY GATE: no chapter is balance_locked, so it enforces nothing; '
                  '`make verdict-diff` shows what a change moves (ADR 0353).')
        elif fails:
            print('\n!! PARITY GATE: %d locked chapter-mode(s) off-parity, unreliable, or '
                  'carrying a role finding: %s' % (len(fails), ', '.join(fails)))
            sys.exit(1)
        else:
            print('\nPARITY GATE: every locked chapter holds parity in %s.'
                  % ', '.join(m.title() for m in ((args.mode,) if args.mode else MODES)))
        return
    if args.curve:
        curve_report(args.campaign, mode=args.mode)
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
