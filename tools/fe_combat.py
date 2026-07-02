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
  Atk     = Pow + wpnMt + triangleDmg   (x3 whole if effective, l.531)
  Damage  = max(0, Atk - (Def | Res))                       Res for magic
  Double  if (atkAS - defAS) >= 4                           (BATTLE_FOLLOWUP_THRESHOLD)
Triangle (GBA FE8): advantage +1 Mt / +15 Hit, disadvantage -1 Mt / -15 Hit.
"""
from dataclasses import dataclass, field


@dataclass(frozen=True)
class Weapon:
    """name, Mt, Hit, Crit, Wt, kind, range, and what it is x3-effective against.

    kind drives the triangle and the defence stat: 'magic' resolves vs Res, everything
    else vs Def; 'bow'/'magic'/'staff' are off-triangle (neutral). effective is the set
    of defender tags the weapon triples damage on (e.g. a rapier vs {'armor','cav'})."""
    name: str
    mt: int
    hit: int
    crit: int
    wt: int
    kind: str
    rng: tuple = (1, 1)
    effective: frozenset = frozenset()


# Canonical vanilla FE8 weapon stats (data_items.c, git HEAD). The triangle runs
# sword > axe > lance > sword; bows/magic/staves are neutral.
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
    'hand-axe':     Weapon('hand-axe',     7, 60,  0, 11, 'axe',   rng=(1, 2)),
    'iron-bow':     Weapon('iron-bow',     6, 85,  0, 5,  'bow',   rng=(2, 2),
                           effective=frozenset({'flier'})),
    # fire-line tomes carry the campaign's ONE iconic matchup (#8, campaign.yaml
    # iconic_matchups): x3 vs ice trolls (cyclops reskin) + frost druids. Vanilla
    # parity-reference forces are unaffected (their targets carry neither tag).
    'fire':         Weapon('fire',         5, 90,  0, 4,  'magic', rng=(1, 2),
                           effective=frozenset({'cyclops', 'druid'})),
    'elfire':       Weapon('elfire',       10, 85, 0, 10, 'magic', rng=(1, 2),
                           effective=frozenset({'cyclops', 'druid'})),
    'lightning':    Weapon('lightning',    4, 95,  5, 6,  'magic', rng=(1, 2)),
    'flux':         Weapon('flux',         7, 80,  0, 8,  'magic', rng=(1, 2)),
    # Extended vanilla weapons carried only by enemy parity-reference forces (FE8 Ch4/Ch6),
    # never by our cast. The difficulty engine maps the decomp items to these for the static
    # threat proxy; they are NOT in build_campaign.WEAPON_ITEM_ENUM (content-owned). #53.
    'thunder':      Weapon('thunder',      8, 80,  5, 6,  'magic', rng=(1, 2)),
    'iron-blade':   Weapon('iron-blade',   9, 70,  0, 12, 'sword'),
    'venin-axe':    Weapon('venin-axe',    4, 60,  0, 10, 'axe'),
    'halberd':      Weapon('halberd',      10, 60, 0, 15, 'axe',
                           effective=frozenset({'cav'})),
    'horseslayer':  Weapon('horseslayer',  7, 70,  0, 13, 'lance',
                           effective=frozenset({'cav'})),
    # Monster claws are plain physical might (off-triangle); Evil Eye is monster dark magic.
    # Venin weapons poison rather than deal HP damage in vanilla -- modeled at base might as a
    # low static-DPR proxy (#53 note) so the unit still resolves and counts as modeled.
    'fetid-claw':   Weapon('fetid-claw',   12, 75, 0, 10, 'monster'),
    'rotten-claw':  Weapon('rotten-claw',  7, 80,  0, 8,  'monster'),
    'venin-claw':   Weapon('venin-claw',   6, 65,  0, 10, 'monster'),
    'evil-eye':     Weapon('evil-eye',     7, 85,  0, 6,  'magic', rng=(1, 2)),
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
    tags: frozenset = field(default_factory=frozenset)


def attack_speed(c):
    """Spd minus the weight the unit can't carry (Wt over Con), floored at 0. A weaponless
    support unit (weapon=None, a fielded healer) bears no weight, so its AS is just Spd."""
    if c.weapon is None:
        return max(0, c.spd)
    return max(0, c.spd - max(0, c.weapon.wt - c.con))


# A 4-point attack-speed lead earns a follow-up attack (BATTLE_FOLLOWUP_THRESHOLD).
FOLLOWUP_THRESHOLD = 4


def doubles(atk, dfn):
    """True if atk strikes twice -- AS lead of FOLLOWUP_THRESHOLD or more over dfn."""
    return attack_speed(atk) - attack_speed(dfn) >= FOLLOWUP_THRESHOLD


# Weapon triangle: each key beats its value (sword > axe > lance > sword). Bows,
# magic, and staves aren't in the dict -> neutral against everything.
_BEATS = {'sword': 'axe', 'axe': 'lance', 'lance': 'sword'}


def triangle(atk_kind, def_kind):
    """+1 advantage / -1 disadvantage / 0 neutral for atk_kind striking def_kind."""
    if _BEATS.get(atk_kind) == def_kind:
        return 1
    if _BEATS.get(def_kind) == atk_kind:
        return -1
    return 0


def damage(atk, dfn):
    """Damage atk deals to dfn on a single connecting hit (max 0). Magic resolves
    against Res, everything else against Def; an effective weapon triples the whole
    attack (Pow + Mt + triangle) before the defence is subtracted."""
    if atk.weapon is None:                # a weaponless support unit can't attack
        return 0
    tri = triangle(atk.weapon.kind, dfn.weapon.kind) if dfn.weapon else 0
    raw = atk.pow + atk.weapon.mt + tri
    if atk.weapon.effective & dfn.tags:
        raw *= 3
    defence = dfn.res if atk.weapon.kind == 'magic' else dfn.df
    return max(0, raw - defence)


def hit_chance(atk, dfn, terrain_avoid=0):
    """Displayed hit% (0-100): atk's accuracy minus dfn's avoid, on dfn's terrain."""
    tri = triangle(atk.weapon.kind, dfn.weapon.kind) if dfn.weapon else 0
    accuracy = atk.skl * 2 + atk.weapon.hit + atk.lck // 2 + tri * 15
    avoid = attack_speed(dfn) * 2 + terrain_avoid + dfn.lck
    return max(0, min(100, accuracy - avoid))


def damage_per_round(atk, dfn, terrain_avoid=0):
    """Expected damage atk deals dfn over one combat round: per-hit damage x hit count
    (2 on a follow-up) x hit probability. A static proxy -- no positioning or AI."""
    if atk.weapon is None:                # weaponless support unit -> no offense
        return 0.0
    hits = 2 if doubles(atk, dfn) else 1
    return damage(atk, dfn) * hits * hit_chance(atk, dfn, terrain_avoid) / 100.0


def rounds_to_kill(atk, dfn, terrain_avoid=0):
    """Expected rounds for atk to drop dfn (inf if it can't deal damage)."""
    dpr = damage_per_round(atk, dfn, terrain_avoid)
    return float('inf') if dpr <= 0 else dfn.hp / dpr


def kills_per_round(atk, dfn, terrain_avoid=0):
    """Kill throughput, capped at 1.0 per unit (overkill doesn't count twice). One-
    rounding an enemy is worth exactly one kill; a two-round matchup is worth 0.5."""
    dpr = damage_per_round(atk, dfn, terrain_avoid)
    return 0.0 if dpr <= 0 else min(1.0, dpr / dfn.hp)
