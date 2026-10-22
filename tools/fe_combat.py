#!/usr/bin/env python3
"""FE8 combat math -- the single source of truth for the difficulty engine's arbitration.

Every formula here is the decomp's own (fireemblem8u/src/bmbattle.c); the difficulty
analyzer (tools/difficulty.py) and any balance tooling import from here so there is ONE
place that knows how a Fire Emblem round resolves. Pure functions over plain dataclasses,
no I/O -- testable in isolation against hand-computed and canonical-vanilla oracles
(tools/test_fe_combat.py).

Combat model (bmbattle.c line cites):
  AS      = Spd - max(0, Wt - Con)                         (l.564-571, floored at 0)
  Hit     = Skl*2 + wpnHit + Lck//2 + triangleHit          (l.578)
  Avoid   = AS*2 + terrainAvoid + Lck                       (l.582)
  HitShown= clamp(atkHit - defAvoid, 0, 100)               (l.600-603)
  P(hit)  = Roll2RN(HitShown): floored mean of two 0-99 rolls < HitShown  (rng.c, l.1008)
  Crit    = max(0, wpnCrit + Skl//2 [+15 crit-bonus class] - defLck), rolled on 1RN once a strike connects; a crit
            deals Damage x3                                 (l.1030-1039)
  Atk     = Pow + (wpnMt + triangleDmg)  (the Mt+tri HALF x3 if effective, l.527-556:
            battleAttack = Mt + tri, tripled on effectiveness, THEN += Pow)
  Damage  = max(0, Atk - (Def | Res))                       Res for a tome
  Double  if (atkAS - defAS) >= 4                     (BATTLE_FOLLOWUP_SPEED_THRESHOLD)
Triangle (GBA FE8, `sWeaponTriangleRules`, l.38-55): advantage +1 Mt / +15 Hit, disadvantage
  -1 Mt / -15 Hit, for sword > axe > lance > sword AND anima > light > dark > anima.

A Combatant's stats may be numpy arrays instead of ints: one unit read over many careers at
once (difficulty.party_matchup, #510 step 4). Its weapon, tags and Con stay single values. The
formulas below are written once for both, through the helpers that follow, so there is
still one place that knows how a round resolves. numpy is imported only when an array arrives,
so the pyyaml-only CI checks job can import this module.
"""
import functools
from dataclasses import dataclass, field, replace


def is_array(x):
    return hasattr(x, 'shape')


def max0(x):
    """max(0, x), for an int or an array."""
    if is_array(x):
        import numpy
        return numpy.maximum(x, 0)
    return x if x > 0 else 0


def clamp(x, lo, hi):
    """x held to [lo, hi], for an int or an array."""
    if is_array(x):
        import numpy
        return numpy.clip(x, lo, hi)
    return lo if x < lo else hi if x > hi else x


def where(cond, a, b):
    """`a if cond else b`, elementwise when `cond` is an array (both sides are evaluated)."""
    if is_array(cond):
        import numpy
        return numpy.where(cond, a, b)
    return a if cond else b


def maximum(a, b):
    """The larger of two ints, or the elementwise larger of two arrays."""
    if is_array(a) or is_array(b):
        import numpy
        return numpy.maximum(a, b)
    return a if a >= b else b


def minimum(a, b):
    """The smaller of two ints, or the elementwise smaller of two arrays."""
    if is_array(a) or is_array(b):
        import numpy
        return numpy.minimum(a, b)
    return a if a <= b else b


@dataclass(frozen=True)
class Weapon:
    """name, Mt, Hit, Crit, Wt, kind, range, and what it is x3-effective against.

    kind is the item's FE8 weapon type (data_items.c `.weaponType`). It drives the triangle
    and the defence stat: a MAGIC_KINDS tome resolves vs Res, everything else vs Def;
    'bow'/'monster'/'staff' are off-triangle (neutral). effective is the set of defender
    tags the weapon triples damage on (e.g. a rapier vs {'armor','cav'})."""
    name: str
    mt: int
    hit: int
    crit: int
    wt: int
    kind: str
    rng: tuple = (1, 1)
    effective: frozenset = frozenset()


# Canonical vanilla FE8 weapon stats and types (data_items.c, git HEAD;
# test_difficulty checks every kind against `.weaponType`).
W = {
    'iron-sword':   Weapon('iron-sword',   5, 90,  0, 5,  'sword'),
    'rapier':       Weapon('rapier',       7, 95, 10, 5,  'sword',
                           effective=frozenset({'cav', 'armor'})),
    'steel-sword':  Weapon('steel-sword',  8, 75,  0, 10, 'sword'),
    'iron-lance':   Weapon('iron-lance',   7, 80,  0, 8,  'lance'),
    'silver-lance': Weapon('silver-lance', 14, 75, 0, 10, 'lance'),
    'javelin':      Weapon('javelin',      6, 65,  0, 11, 'lance', rng=(1, 2)),
    'killing-edge': Weapon('killing-edge', 9, 75, 30, 7,  'sword'),
    'iron-axe':     Weapon('iron-axe',     8, 75,  0, 10, 'axe'),
    'steel-axe':    Weapon('steel-axe',    11, 65, 0, 15, 'axe'),
    'hand-axe':     Weapon('hand-axe',     7, 60,  0, 12, 'axe',   rng=(1, 2)),
    'killer-axe':   Weapon('killer-axe',   11, 65, 30, 11, 'axe'),
    'hatchet':      Weapon('hatchet',      4, 85,  0, 5,  'axe',   rng=(1, 2)),   # Ross's
    'iron-bow':     Weapon('iron-bow',     6, 85,  0, 5,  'bow',   rng=(2, 2),
                           effective=frozenset({'flier'})),
    'fire':         Weapon('fire',         5, 90,  0, 4,  'anima', rng=(1, 2)),
    'lightning':    Weapon('lightning',    4, 95,  5, 6,  'light', rng=(1, 2)),
    'flux':         Weapon('flux',         7, 80,  0, 8,  'dark', rng=(1, 2)),
    # Extended vanilla weapons carried only by enemy parity-reference forces (FE8 Ch4/Ch6),
    # never by our cast. The difficulty engine maps the decomp items to these for the static
    # threat proxy (difficulty.ITEM_TO_WEAPON, derived from inject.decomp.ITEM_ENUM, #491).
    'thunder':      Weapon('thunder',      8, 80,  5, 6,  'anima', rng=(1, 2)),
    'iron-blade':   Weapon('iron-blade',   9, 70,  0, 12, 'sword'),
    'steel-lance':  Weapon('steel-lance',  10, 70, 0, 13, 'lance'),
    'slim-lance':   Weapon('slim-lance',   4, 85,  5, 4,  'lance'),
    'short-spear':  Weapon('short-spear',  9, 60,  0, 12, 'lance', rng=(1, 2)),
    'steel-bow':    Weapon('steel-bow',    9, 70,  0, 9,  'bow',   rng=(2, 2),
                           effective=frozenset({'flier'})),
    'zanbato':      Weapon('zanbato',      6, 85,  0, 11, 'sword',
                           effective=frozenset({'cav'})),
    'elfire':       Weapon('elfire',       10, 85, 0, 10, 'anima', rng=(1, 2)),
    'venin-axe':    Weapon('venin-axe',    4, 60,  0, 10, 'axe'),
    'venin-lance':  Weapon('venin-lance',  4, 65,  0, 8,  'lance'),
    'halberd':      Weapon('halberd',      10, 60, 0, 15, 'axe',
                           effective=frozenset({'cav'})),
    'horseslayer':  Weapon('horseslayer',  7, 70,  0, 13, 'lance',
                           effective=frozenset({'cav'})),
    # Monster claws are plain physical might (off-triangle); Evil Eye is a dark tome
    # (ITYPE_DARK), so it sits on the magic triangle like Flux.
    # A venin hit deals its might like any weapon AND poisons (`BattleGenerateHitEffects`,
    # bmbattle.c): 1-3 HP a phase for 5 phases. These metrics count the hit only;
    # `danger_map` adds the poison.
    'fetid-claw':   Weapon('fetid-claw',   12, 75, 0, 10, 'monster'),
    'rotten-claw':  Weapon('rotten-claw',  7, 80,  0, 8,  'monster'),
    'venin-claw':   Weapon('venin-claw',   6, 65,  0, 10, 'monster'),
    # The Mauthe Doog's bite, and so the unpromoted tier of the Gwyllgi's own line
    # (data_classes.c: CLASS_MAUTHEDOOG.promotion = CLASS_GWYLLGI). decomp mt/hit/wt.
    'fire-fang':    Weapon('fire-fang',    5, 90, 0, 5,  'monster'),
    'hell-fang':    Weapon('hell-fang',    13, 80, 0, 8,  'monster'),
    'evil-eye':     Weapon('evil-eye',     7, 85,  0, 6,  'dark', rng=(1, 2)),
}


@dataclass
class Combatant:
    name: str
    hp: int
    pow: int
    skl: int
    spd: int
    df: int
    res: int
    lck: int
    con: int
    weapon: Weapon
    # Class facts (difficulty.class_tags). As a DEFENDER: armor/cav/flier/monster, the
    # effectiveness lists a weapon's `effective` names. As an ATTACKER: critbonus, slayer.
    tags: frozenset = field(default_factory=frozenset)
    # Every weapon the unit carries, in inventory order; `weapon` is the one it has equipped,
    # which is what it counters with. Empty means `weapon` alone. See `arms`.
    arsenal: tuple = ()


def arms(c):
    """One Combatant per weapon `c` carries, in inventory order: the order FE8's AI tries
    them in (`AiAttemptOffensiveAction`'s item loop, cp_battle.c). A unit attacks with whichever
    the AI picks against that target; it defends with its equipped `weapon`."""
    weapons = c.arsenal or ((c.weapon,) if c.weapon is not None else ())
    return tuple(replace(c, weapon=w) for w in weapons)


def attack_speed(c):
    """Spd minus the weight the unit can't carry (Wt over Con), floored at 0. A weaponless
    support unit (weapon=None, a fielded healer) bears no weight, so its AS is just Spd."""
    if c.weapon is None:
        return max0(c.spd)
    return max0(c.spd - max0(c.weapon.wt - c.con))


# A 4-point attack-speed lead earns a follow-up attack (BATTLE_FOLLOWUP_SPEED_THRESHOLD).
FOLLOWUP_THRESHOLD = 4


def doubles(atk, dfn):
    """True if atk strikes twice -- AS lead of FOLLOWUP_THRESHOLD or more over dfn."""
    return attack_speed(atk) - attack_speed(dfn) >= FOLLOWUP_THRESHOLD


# The weapon types that are tomes: they resolve against Res (IA_MAGIC, bmbattle.c).
MAGIC_KINDS = frozenset({'anima', 'light', 'dark'})


def is_magic(kind):
    return kind in MAGIC_KINDS


# `sWeaponTriangleRules` (bmbattle.c l.38-55): (attacker type, defender type) -> (hit, Mt).
# A pair it does not list is neutral: bows, monster weapons, staves, and physical vs tome.
TRIANGLE_RULES = {
    ('sword', 'lance'): (-15, -1), ('sword', 'axe'): (15, 1),
    ('lance', 'axe'): (-15, -1), ('lance', 'sword'): (15, 1),
    ('axe', 'sword'): (-15, -1), ('axe', 'lance'): (15, 1),
    ('anima', 'dark'): (-15, -1), ('anima', 'light'): (15, 1),
    ('light', 'anima'): (-15, -1), ('light', 'dark'): (15, 1),
    ('dark', 'light'): (-15, -1), ('dark', 'anima'): (15, 1),
}


def triangle(atk_kind, def_kind):
    """The Mt bonus for atk_kind striking def_kind: +1 advantage, -1 disadvantage, 0."""
    return TRIANGLE_RULES.get((atk_kind, def_kind), (0, 0))[1]


def triangle_hit(atk_kind, def_kind):
    """The hit bonus for atk_kind striking def_kind: +15, -15 or 0."""
    return TRIANGLE_RULES.get((atk_kind, def_kind), (0, 0))[0]


def damage(atk, dfn):
    """Damage atk deals to dfn on a single connecting hit (max 0). Magic resolves
    against Res, everything else against Def; an effective weapon triples the WEAPON
    half only (Mt + triangle) -- Pow is added after, per the decomp
    (bmbattle.c ComputeBattleUnitAttack: battleAttack = Mt + tri, x3 on
    effectiveness, then += Pow; the sacred-twins x2 special case is not modeled). A
    'slayer' attacker (a Bishop, `IsUnitEffectiveAgainst`) triples the same half on a monster."""
    if atk.weapon is None:                # a weaponless support unit can't attack
        return 0
    tri = triangle(atk.weapon.kind, dfn.weapon.kind) if dfn.weapon else 0
    raw = atk.weapon.mt + tri
    if atk.weapon.effective & dfn.tags or ('slayer' in atk.tags and 'monster' in dfn.tags):
        raw *= 3
    raw += atk.pow
    defence = dfn.res if is_magic(atk.weapon.kind) else dfn.df
    return max0(raw - defence)


def hit_chance(atk, dfn, terrain_avoid=0):
    """Displayed hit% (0-100): atk's accuracy minus dfn's avoid, on dfn's terrain."""
    tri = triangle_hit(atk.weapon.kind, dfn.weapon.kind) if dfn.weapon else 0
    accuracy = atk.skl * 2 + atk.weapon.hit + atk.lck // 2 + tri
    avoid = attack_speed(dfn) * 2 + terrain_avoid + dfn.lck
    return clamp(accuracy - avoid, 0, 100)


@functools.lru_cache(maxsize=None)
def true_hit(displayed):
    """P(hit) for a displayed hit rate: `Roll2RN` (rng.c) hits when the floored average of
    two 0-99 rolls is below the threshold. 47 displayed is 45% true; 80 is 92%."""
    displayed = max(0, min(100, displayed))
    return sum(1 for a in range(100) for b in range(100) if (a + b) // 2 < displayed) / 1e4


@functools.lru_cache(maxsize=None)
def _true_hit_table():
    import numpy
    return numpy.array([true_hit(d) for d in range(101)])


def _true_hit(displayed):
    """`true_hit` for a displayed rate already held to 0-100, int or array."""
    return _true_hit_table()[displayed] if is_array(displayed) else true_hit(displayed)


def crit_rate(atk, dfn):
    """`ComputeBattleUnitCritRate` less `ComputeBattleUnitEffectiveCritRate`'s dodge: weapon
    crit + Skl/2 - the defender's Lck, floored at 0. Rolled on 1RN, so the rate is the
    probability. A crit-bonus class (Swordmaster, Berserker, the trainees' third tier) adds 15."""
    if atk.weapon is None:
        return 0
    bonus = 15 if 'critbonus' in atk.tags else 0
    return clamp(atk.weapon.crit + atk.skl // 2 + bonus - dfn.lck, 0, 100)


def expected_hits(atk, dfn, terrain_avoid=0):
    """Damage multiples atk lands on dfn per round: strikes (2 on a follow-up) x P(hit) on
    2RN x (1 + 2 x P(crit)), since a crit triples a strike that connects."""
    if atk.weapon is None:                # weaponless support unit -> no offense
        return 0.0
    strikes = where(doubles(atk, dfn), 2, 1)
    return (strikes * _true_hit(hit_chance(atk, dfn, terrain_avoid))
            * (1 + 2 * crit_rate(atk, dfn) / 100.0))


def damage_per_round(atk, dfn, terrain_avoid=0):
    """Expected damage atk deals dfn over one combat round, as the cartridge rolls it:
    per-hit damage x `expected_hits`. A static proxy -- no positioning or AI."""
    return damage(atk, dfn) * expected_hits(atk, dfn, terrain_avoid)


def rounds_to_kill(atk, dfn, terrain_avoid=0):
    """Expected rounds for atk to drop dfn (inf if it can't deal damage)."""
    dpr = damage_per_round(atk, dfn, terrain_avoid)
    if is_array(dpr):
        import numpy
        with numpy.errstate(divide='ignore'):
            return numpy.where(dpr > 0, dfn.hp / numpy.where(dpr > 0, dpr, 1), float('inf'))
    return float('inf') if dpr <= 0 else dfn.hp / dpr


def kills_per_round(atk, dfn, terrain_avoid=0):
    """Kill throughput, capped at 1.0 per unit (overkill doesn't count twice). One-
    rounding an enemy is worth exactly one kill; a two-round matchup is worth 0.5."""
    dpr = damage_per_round(atk, dfn, terrain_avoid)
    return where(dpr > 0, minimum(1.0, dpr / dfn.hp), 0.0)
