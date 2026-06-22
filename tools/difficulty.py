#!/usr/bin/env python3
"""Per-chapter difficulty analyzer -- the STATIC arbiter of party-side parity.

Generalizes the original one-off Ch1 study into a reusable per-chapter tool: it resolves
our cast's effective stats (class base + donor personal
line, the donor-base inheritance of #45) and the chapter's enemy table, then measures
whether the field sits at vanilla FE8 parity on the three things that decide a Fire
Emblem map -- can we survive, can we kill, can we crack the boss.

    python3 tools/difficulty.py --chapter ch01

HONEST LIMITS: this is a *static* proxy. It assumes every matchup happens, ignores
positioning, turn order, terrain choice, healing, and enemy AI. It is a fast guardrail
against authoring a chapter that drifts off vanilla parity -- NOT a substitute for the
dynamic playtest harness (tools/playtest/), which is the real arbiter.

All combat math is fe_combat.py (the decomp's own formulas, tested). Stat resolution
shares build_campaign.py's primitives so there is one source of truth for "what is this
unit's stat line".
"""
import dataclasses
import os
import re

import build_campaign as bc
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
        _vanilla_chars = bc.vanilla_decomp_text('src/data_characters.c')
    return _vanilla_chars


def _classes_text():
    global _vanilla_classes
    if _vanilla_classes is None:
        _vanilla_classes = bc.vanilla_decomp_text('src/data_classes.c')
    return _vanilla_classes


def _class_base(class_enum):
    return bc.class_base_stats(class_enum, _classes_text())


def _class_growths(class_enum):
    """Read a class's growth rates (for autoleveling enemies) from vanilla data_classes.c."""
    text = _classes_text()
    s, e = bc._find_brace_block(text, '[%s - 1]' % class_enum, bc.CLASSES_C)
    block = text[s:e]
    out = {}
    for gf in bc.GROWTH_FIELDS:
        m = re.search(r'\.' + gf + r'\s*=\s*(-?\d+)', block)
        out[gf] = int(m.group(1)) if m else 0
    return out


def autolevel(base, growths, level):
    """Project class-base stats up `level` (FE generic-enemy autolevel on class growths,
    bmunit.c:792). Per stat: base + round-half-up((level-1) * growth%). Con/Mov don't grow."""
    out = dict(base)
    gains = level - 1
    for gf in bc.GROWTH_FIELDS:
        field = 'base' + gf[len('growth'):]      # growthHP -> baseHP
        out[field] = base.get(field, 0) + int(gains * growths.get(gf, 0) / 100 + 0.5)
    return out


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


def player_combatant(campaign, uid):
    """Resolve a cast member's effective fe_combat.Combatant: class base + donor personal
    base (donor-base inheritance), at base level, wielding its first real weapon."""
    unit = bc.load_unit(campaign, uid)
    unit.setdefault('id', uid)
    class_enum = bc.class_enum_for(unit)
    cbase = _class_base(class_enum)
    dbase = bc.donor_base_stats(_characters_text(), bc.BASE_DONOR[uid])
    eff = {f: cbase.get(f, 0) + dbase.get(f, 0) for f in bc.BASE_FIELDS}
    weapon = _weapon_for(unit.get('inventory'))
    return _stats_to_combatant(uid, eff, weapon, CLASS_TAGS.get(class_enum, frozenset()))


def _enemy_class_enum(token):
    """'armor-knight' -> 'CLASS_ARMOR_KNIGHT'."""
    return 'CLASS_' + str(token).upper().replace('-', '_')


def _enemy_from_enum(name, class_enum, level, weapon):
    """One Combatant: class base autoleveled to `level`, wielding `weapon`. The vanilla
    enemy stat path -- generics AND named bosses alike are modeled off class base (so ours
    and the vanilla reference resolve on the same footing; a boss's personal line is the
    dynamic playtest's concern, not this static pressure proxy)."""
    stats = autolevel(_class_base(class_enum), _class_growths(class_enum), int(level))
    return _stats_to_combatant(name, stats, weapon, CLASS_TAGS.get(class_enum, frozenset()))


def _one_enemy(name, class_token, level, weapon):
    return _enemy_from_enum(name, _enemy_class_enum(class_token), level, weapon)


def enemy_combatants(enemy_def):
    """One representative Combatant per DISTINCT enemy type in a chapter enemy_units entry
    (its `count`/positions are tactical detail the metrics don't model). Class base
    autoleveled to the entry's `level`. Handles both a single `class` and a mixed
    `composition` (with per-class weapons in `inventory_by_class`)."""
    level = enemy_def.get('level', 1)
    name = enemy_def.get('id', enemy_def.get('name', 'enemy'))
    if 'class' in enemy_def:
        return [_one_enemy(name, enemy_def['class'], level,
                           _weapon_for(enemy_def.get('inventory')))]
    by_class = enemy_def.get('inventory_by_class', {})
    out = []
    for cls in dict.fromkeys(enemy_def.get('composition', [])):   # distinct, order-stable
        weapon = _weapon_for([{'id': w} for w in by_class.get(cls, [])])
        out.append(_one_enemy('%s-%s' % (name, cls), cls, level, weapon))
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
    'ITEM_BLADE_IRON':        'iron-blade',
    'ITEM_AXE_VENIN':         'venin-axe',
    'ITEM_AXE_HALBERD':       'halberd',
    'ITEM_LANCE_HORSESLAYER': 'horseslayer',
    'ITEM_MONSTER_FETIDCLW':  'fetid-claw',
    'ITEM_MONSTER_ROTTENCLW': 'rotten-claw',
    'ITEM_MONSTER_VENINCLW':  'venin-claw',
    'ITEM_MONSTER_EVILEYE':   'evil-eye',
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
    'FE8 Ch6': ('src/events_udefs.c',
                ['UnitDef_088B61A8', 'UnitDef_088B64F0']),
}

# parity_reference -> (decomp relpath, [UnitDefinition array names]) for its vanilla PLAYER
# deploy field (#61) -- the player-side analogue of PARITY_REFERENCE_UDEFS. The blue force the
# reference chapter force-deploys (its force-deploy + reinforcement arrays), derived from HEAD
# so the party-side yardstick stays honest with no hand-maintained stat table. Each named ally
# resolves to class base + its personal line (the same donor-base inheritance our cast uses);
# a staff-only ally (Moulder) resolves to weaponless support (#62). Extend as references curate.
PARITY_REFERENCE_ALLY_UDEFS = {
    'FE8 Ch1': ('src/events/ch1-eventudefs.h',
                ['UnitDef_Event_Ch1Ally', 'UnitDef_Event_Ch1AllyReinforce']),
    'FE8 Ch2': ('src/events_udefs.c', ['UnitDef_Event_Ch2Ally']),
}


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


def vanilla_unit_defs(text, array_name):
    """Parse `CONST_DATA struct UnitDefinition <array_name>[] = { ... };` from decomp text
    into a list of per-entry dicts (charIndex, classIndex, level, allegiance, items). The
    trailing `{ 0 }` terminator (no .classIndex) is skipped. `charIndex` is the named
    character enum for allies/bosses (a numeric token for generics, None if absent)."""
    s, e = bc._find_brace_block(text, array_name + '[]', '<udef:%s>' % array_name)
    body = text[s + 1:e - 1]
    out = []
    for block in _brace_entries(body):           # top-level { ... } per unit (handles
        cls = re.search(r'\.classIndex\s*=\s*(\w+)', block)   # nested .items/.ai braces
        if not cls:                              # the { 0 } terminator
            continue
        chi = re.search(r'\.charIndex\s*=\s*(\w+)', block)
        lvl = re.search(r'\.level\s*=\s*(\d+)', block)
        alg = re.search(r'\.allegiance\s*=\s*(\w+)', block)
        items = re.search(r'\.items\s*=\s*\{(.*?)\}', block, re.S)
        out.append({
            'charIndex': chi.group(1) if chi else None,
            'classIndex': cls.group(1),
            'level': int(lvl.group(1)) if lvl else 1,
            'allegiance': alg.group(1) if alg else None,
            'items': [t.strip() for t in items.group(1).split(',') if t.strip()]
                     if items else [],
        })
    return out


def _weapon_from_item_enums(item_enums):
    """First decomp item enum that maps to a real attacking weapon (else None)."""
    for it in item_enums:
        key = ITEM_TO_WEAPON.get(it)
        if key:
            return fc.W[key]
    return None


def vanilla_enemies(parity_ref):
    """The vanilla reference chapter's fightable red force as a flat list of Combatants
    (each projected off class base to its level). None if the reference isn't curated yet;
    enemies with no modeled weapon (staff/throwaway only) are dropped."""
    spec = PARITY_REFERENCE_UDEFS.get(parity_ref)
    if spec is None:
        return None
    relpath, arrays = spec
    text = bc.vanilla_decomp_text(relpath)
    out = []
    for array_name in arrays:
        for i, d in enumerate(vanilla_unit_defs(text, array_name)):
            if d['allegiance'] != 'FACTION_ID_RED':
                continue
            weapon = _weapon_from_item_enums(d['items'])
            if weapon is None:
                continue
            out.append(_enemy_from_enum('%s#%d' % (array_name, i),
                                        d['classIndex'], d['level'], weapon))
    return out


def _ally_combatant(char_enum, class_enum, weapon):
    """One vanilla ally Combatant: class base + the named character's personal line (the same
    donor-base inheritance our cast uses, mirroring player_combatant), at its stored base --
    allies aren't autoleveled, their CharacterData stats are already the join-level display.
    Named off charIndex (CHARACTER_EIRIKA -> 'Eirika')."""
    cbase = _class_base(class_enum)
    dbase = bc.donor_base_stats(_characters_text(), char_enum)
    eff = {f: cbase.get(f, 0) + dbase.get(f, 0) for f in bc.BASE_FIELDS}
    name = char_enum.replace('CHARACTER_', '').title()
    return _stats_to_combatant(name, eff, weapon, CLASS_TAGS.get(class_enum, frozenset()))


def vanilla_allies(parity_ref):
    """The vanilla reference chapter's PLAYER deploy field as a list of Combatants -- the
    party-side parity yardstick (#61), derived from the decomp (HEAD) the same way the enemy
    force is. None if the reference isn't curated yet. Each named blue unit resolves off class
    base + personal line; a staff-only ally (Moulder) resolves to weaponless support (#62),
    kept as a body for durability. Weapon = first attacking item (as our cast is modeled)."""
    spec = PARITY_REFERENCE_ALLY_UDEFS.get(parity_ref)
    if spec is None:
        return None
    relpath, arrays = spec
    text = bc.vanilla_decomp_text(relpath)
    out = []
    for array_name in arrays:
        for d in vanilla_unit_defs(text, array_name):
            if d['allegiance'] != 'FACTION_ID_BLUE' or not d['charIndex']:
                continue
            weapon = _weapon_from_item_enums(d['items'])
            out.append(_ally_combatant(d['charIndex'], d['classIndex'], weapon))
    return out


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


def chapter_enemy_force(chap):
    """Our chapter's full enemy force as a flat per-unit Combatant list (bosses included),
    honoring each entry's `count`/`composition` -- the multiplicity enemy_combatants drops.
    This is the our-side input to enemy_pressure (the parity comparand to vanilla_enemies)."""
    out = []
    for ed in chap.get('enemy_units', []):
        if 'composition' in ed and 'class' not in ed:
            level = ed.get('level', 1)
            name = ed.get('id', ed.get('name', 'enemy'))
            by_class = ed.get('inventory_by_class', {})
            for cls in ed.get('composition', []):
                weapon = _weapon_for([{'id': w} for w in by_class.get(cls, [])])
                out.append(_one_enemy('%s-%s' % (name, cls), cls, level, weapon))
        else:
            out.extend(enemy_combatants(ed) * int(ed.get('count', 1)))
    return [u for u in out if u.weapon is not None]   # drop unmodeled-weapon (staff) enemies


def unmodeled_enemies(chap):
    """Enemy entries that contribute NO modeled-weapon units (so chapter_enemy_force drops
    them) -- returned as {id, is_boss} so the report can warn instead of silently skewing the
    verdict (#51). A boss here means the parity read for that chapter is untrustworthy."""
    out = []
    for ed in chap.get('enemy_units', []):
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


# A fixed, campaign-neutral reference attacker/defender. enemy_pressure measures every
# enemy against THIS unit, so a chapter's pressure is comparable to its vanilla reference's
# on the same scale; the yardstick's exact stats cancel in an ours-vs-vanilla ratio. Chosen
# as a plain mid-game footsoldier (iron sword, no triangle bias, modest bulk/offense).
YARDSTICK = fc.Combatant('yardstick', hp=24, pow=8, skl=8, spd=8, df=6, res=4, lck=4,
                         con=10, weapon=fc.W['iron-sword'])


def enemy_pressure(enemies, deploy_cap, yardstick=YARDSTICK):
    """Per-deploy-slot enemy pressure of an enemy list, as (threat/slot, clear-load/slot).

    threat/slot = Σ damage_per_round(enemy -> yardstick) ÷ deploy_cap -- how much incoming
    damage each of our slots must weather. clear-load/slot = Σ yardstick rounds_to_kill(enemy)
    ÷ deploy_cap -- how much killing each slot must do to clear the map. Both measured against
    the fixed YARDSTICK so ours and the vanilla reference land on one scale; the metric is a
    static proxy (no positioning/AI/terrain), read as a ratio within a tolerance band."""
    cap = max(1, deploy_cap)
    threat = sum(fc.damage_per_round(e, yardstick) for e in enemies) / cap
    clearload = sum(fc.rounds_to_kill(yardstick, e) for e in enemies) / cap
    return threat, clearload


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

ROSTER = list(bc.BASE_DONOR.keys())     # the playable cast (each has a stat donor)


def chapter_path(campaign, ch):
    """Resolve a short id ('ch01') to its chapter YAML path."""
    hits = sorted(glob.glob(os.path.join(
        bc.REPO, 'campaigns', campaign, 'chapters', ch + '*.yaml')))
    if not hits:
        raise SystemExit('ERROR: no chapter YAML matching %r' % ch)
    return hits[0]


def load_field(campaign, ch):
    """Assemble (roster, line_enemies, bosses, deploy_limit, enemy_labels) for a chapter."""
    with open(chapter_path(campaign, ch), encoding='utf-8') as f:
        chap = bc.yaml.safe_load(f)
    roster = [player_combatant(campaign, uid) for uid in ROSTER]
    line, bosses, labels = [], [], []
    for ed in chap.get('enemy_units', []):
        units = enemy_combatants(ed)
        count = int(ed.get('count', 1))
        kind = ed.get('class') or '+'.join(dict.fromkeys(ed.get('composition', ['?'])))
        labels.append('%dx %s (%s l%s)' % (count, ed.get('name', ed.get('id', '?')),
                                           kind, ed.get('level', 1)))
        (bosses if ed.get('is_boss') else line).extend(units)
    return chap, roster, line, bosses, int(chap.get('deploy_limit', len(roster))), labels


def _metrics(party, line, bosses):
    """Headline numbers for a fielded party."""
    m = {'throughput': party_throughput(party, line),
         'min_durability': min((durability(u, line) for u in party), default=float('inf'))}
    if bosses:
        u, r = min((carry(b, party) for b in bosses), key=lambda x: x[1])
        m['carry'] = (u.name, r)
    return m


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


def report(campaign, ch):
    chap, roster, line, bosses, deploy_limit, labels = load_field(campaign, ch)
    num = chap.get('chapter_number')
    bar = '=' * 80
    print(bar)
    print('CH%s "%s" -- difficulty / vanilla parity   [STATIC proxy -- playtest is arbiter]'
          % (num, chap.get('title', ch)))
    print(bar)
    if chap.get('status') == 'planned':
        print('** PLANNED chapter -- brainstorm SEED, NOT authoritative. The enemy roster/levels'
              '\n   below are ungrounded and will be re-grounded against vanilla + party data when'
              '\n   this slice is built; treat the numbers as a sketch, not a parity reading. **\n')
    print('Field: deploy %d of %d cast   Enemies: %s' % (deploy_limit, len(roster),
                                                          '; '.join(labels)))

    print('\n-- OUR CAST (effective = class base + donor personal line) ' + '-' * 21)
    print('  %-11s %3s%3s%3s%3s%3s%3s%3s%3s  %-9s  %-13s  %s'
          % ('unit', 'HP', 'Pw', 'Sk', 'Sp', 'Df', 'Rs', 'Lk', 'Cn',
             'weapon', 'durab open/for', 'best kill/round'))
    for u in sorted(roster, key=lambda x: max((fc.kills_per_round(x, e) for e in line),
                                              default=0.0), reverse=True):
        best = max(((fc.kills_per_round(u, e), e) for e in line),
                   key=lambda x: x[0], default=(0.0, None))
        do = durability(u, line, 0)
        dfst = durability(u, line, 20)
        print('  %-11s %3d%3d%3d%3d%3d%3d%3d%3d  %-9s  %4.1f /%4.1f    %.2f%s'
              % (u.name, u.hp, u.pow, u.skl, u.spd, u.df, u.res, u.lck, u.con,
                 u.weapon.name if u.weapon else '(staff)', do, dfst, best[0],
                 (' vs ' + best[1].name) if best[1] else ''))

    field = _best_field(roster, line, deploy_limit)
    m = _metrics(field, line, bosses)
    print('\n-- PARTY (best %d fielded: %s) %s' % (
        deploy_limit, ', '.join(u.name for u in field), '-' * 12))
    print('  throughput %.2f kills/round (cap 1/unit) · durability(min) %.1f%s'
          % (m['throughput'], m['min_durability'],
             ' · carry %s %s rounds vs boss' % (m['carry'][0], _fmt_rounds(m['carry'][1]))
             if 'carry' in m else ''))

    print('\n-- LORD x TEAM SWEEP (each candidate forced-deployed as the must-survive lord) --')
    for r in lord_team_sweep(roster, line, bosses, deploy_limit):
        boss = (' boss %s' % _fmt_rounds(r['carry_rounds'])) if 'carry_rounds' in r else ''
        print('  lord=%-11s thru %.2f  dura %.1f%s   team[%s]'
              % (r['lord'].name, r['throughput'], r['min_durability'], boss,
                 ', '.join(u.name for u in r['team'])))

    ref = chap.get('parity_reference')
    van = vanilla_allies(ref)
    if van:
        vm = _metrics(van, line, bosses)
        print('\n-- VANILLA Ch%s PARITY DELTA (%s deploy, from HEAD) ' % (num, ref) + '-' * 24)
        print('  vanilla (%s): thru %.2f · dura(min) %.1f%s'
              % ('/'.join(u.name for u in van), vm['throughput'], vm['min_durability'],
                 ' · carry %s' % _fmt_rounds(vm['carry'][1]) if 'carry' in vm else ''))
        print('  ours (best %d):  thru %.2f (%+.2f) · dura(min) %s (%s)%s'
              % (deploy_limit, m['throughput'], m['throughput'] - vm['throughput'],
                 _fmt_rounds(m['min_durability']),
                 _fmt_dura_delta(m['min_durability'], vm['min_durability']),
                 ' · carry %s' % _fmt_rounds(m['carry'][1]) if 'carry' in m else ''))
    else:
        print('\n(no vanilla reference field for Ch%s (parity_reference=%r) -- delta skipped)'
              % (num, ref))

    _print_pressure(_chapter_pressure(chap))


def _chapter_pressure(chap, band=0.25):
    """Enemy-pressure parity for one loaded chapter dict: our force vs its parity_reference's
    vanilla force, threat/slot + clear-load/slot, with a verdict. `vanilla` is None when the
    reference isn't curated yet (#48 registry)."""
    deploy_cap = int(chap.get('deploy_limit', len(ROSTER)))
    ours_force = chapter_enemy_force(chap)
    ours = enemy_pressure(ours_force, deploy_cap)
    ref = chap.get('parity_reference')
    van = vanilla_enemies(ref)
    out = {'reference': ref, 'deploy_cap': deploy_cap, 'ours': ours,
           'n_ours': len(ours_force), 'vanilla': None,
           'dropped': unmodeled_enemies(chap)}
    if van is not None:
        out['vanilla'] = enemy_pressure(van, deploy_cap)
        out['n_vanilla'] = len(van)
        out['verdict'] = pressure_verdict(ours, out['vanilla'], band)
    return out


def _warn_dropped(dropped, indent='  '):
    """Emit a warning per enemy the metric couldn't model (no FE-base weapon). A dropped
    boss means the verdict is unreliable for that chapter -- say so loudly (#51)."""
    for d in dropped:
        tag = '!! BOSS DROPPED -- verdict UNRELIABLE' if d['is_boss'] else 'dropped'
        print('%sWARN: %s (%s -- no modeled weapon; add fe_base in its YAML inventory)'
              % (indent, d['id'], tag))


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
    print('  vanilla %-11s (%2d enemies): threat/slot %4.1f · clear-load/slot %4.1f'
          % (p['reference'], p['n_vanilla'], vt, vl))
    print('  ours    %-11s (%2d enemies): threat/slot %4.1f (x%.2f %s) · '
          'clear-load/slot %4.1f (x%.2f %s)'
          % ('', p['n_ours'], ot, v['threat_ratio'], v['threat'],
             ol, v['load_ratio'], v['load']))
    print('  verdict: %s' % ('PARITY (within band)' if v['verdict'] == 'OK'
                             else 'OFF-PARITY -- threat %s, clear-load %s' % (v['threat'], v['load'])))


def curve_gate_failures(rows):
    """The --check gate: return the labels of chapters that should fail the build. PER-CHAPTER
    opt-in (#48 (b)): the gate enforces a chapter only once content marks it balance-final with
    `balance_locked: true` in its YAML -- so we can author chapters as we go without an
    unwritten or mid-authoring chapter reddening CI. A LOCKED chapter fails when it is off-parity
    (`verdict != 'OK'`), unreliably measured (`boss_drop` -- its scariest unit carries an
    unmodeled weapon, so even an 'OK' verdict can't be trusted), or has no curated reference at
    all (`not has_ref` -- you can't lock a chapter the metric can't measure; a config mistake,
    surfaced loudly). UNLOCKED chapters are informational and never gate; with zero locks the
    gate passes, so --check can ship before any chapter is locked."""
    return [r['label'] for r in rows
            if r['locked'] and (not r['has_ref'] or r['verdict'] != 'OK' or r['boss_drop'])]


def curve_report(campaign, band=0.25):
    """Campaign-wide enemy-pressure curve: one row per authored chapter, ours vs its vanilla
    reference, so spikes/sags across the arc are visible at a glance (#48). Returns the per-chapter
    rows (label / has_ref / verdict / boss_drop) so the --check gate can act on them."""
    paths = sorted(glob.glob(os.path.join(
        bc.REPO, 'campaigns', campaign, 'chapters', 'ch*.yaml')))
    bar = '=' * 86
    print(bar)
    print('CAMPAIGN ENEMY-PRESSURE CURVE -- ours vs vanilla parity_reference   '
          '[STATIC proxy]')
    print(bar)
    print('  %-22s %-13s %-15s %-17s %s'
          % ('chapter', 'reference', 'threat/slot', 'clear-load/slot', 'verdict'))
    chaps = []
    for path in paths:
        with open(path, encoding='utf-8') as f:
            chaps.append(bc.yaml.safe_load(f))
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
            print('  %-22s %-13s   -- planned (seed; grounded on arrival, not modeled) --'
                  % (label[:22], (chap.get('parity_reference', '?') or '?')[:13]))
            continue
        p = _chapter_pressure(chap, band)
        ot, ol = p['ours']
        boss_drop = any(d['is_boss'] for d in p['dropped'])
        any_dropped_boss = any_dropped_boss or boss_drop
        locked = bool(chap.get('balance_locked', False))
        flag = '  !!boss dropped' if boss_drop else ''
        if locked:
            flag += '  [locked]'
        has_ref = p['vanilla'] is not None
        verdict = p['verdict']['verdict'] if has_ref else None
        rows.append({'label': label[:22].strip(), 'locked': locked, 'has_ref': has_ref,
                     'verdict': verdict, 'boss_drop': boss_drop})
        if not has_ref:
            print('  %-22s %-13s %5.1f           %5.1f             (no ref)%s'
                  % (label[:22], (p['reference'] or '?')[:13], ot, ol, flag))
            continue
        vt, vl = p['vanilla']
        v = p['verdict']
        print('  %-22s %-13s %4.1f (x%.2f)     %4.1f (x%.2f)       %s%s'
              % (label[:22], (p['reference'] or '?')[:13], ot, v['threat_ratio'],
                 ol, v['load_ratio'], v['verdict'], flag))
    if any_dropped_boss:
        print('\n  !! a dropped boss means that row\'s verdict is unreliable -- its scariest '
              'unit\n     carries an unmodeled weapon. Add fe_base to its YAML inventory (#51/#52).')
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
    ap = bc.argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument('--chapter', help='chapter id, e.g. ch01 (omit with --curve)')
    ap.add_argument('--campaign', default='rime-of-the-frostmaiden')
    ap.add_argument('--curve', action='store_true',
                    help='emit the campaign-wide enemy-pressure curve (all chapters)')
    ap.add_argument('--check', action='store_true',
                    help='with --curve: exit non-zero if any referenced chapter is off-parity '
                         'or unreliably measured (the hard CI gate, #48 (b))')
    ap.add_argument('--lord-floor', action='store_true',
                    help='emit the per-lord survivability-floor table instead of the parity report')
    ap.add_argument('--target', type=float, default=3.5, help='floor: target bulk rounds-to-down')
    ap.add_argument('--def-cap', type=int, default=4, help='floor: max +Def')
    ap.add_argument('--res-cap', type=int, default=4, help='floor: max +Res')
    ap.add_argument('--hp-cap', type=int, default=12, help='floor: max +HP')
    args = ap.parse_args()
    if args.curve:
        rows = curve_report(args.campaign)
        if args.check:
            fails = curve_gate_failures(rows)
            if fails:
                print('\n!! PARITY GATE: %d chapter(s) off-parity or unreliable: %s'
                      % (len(fails), ', '.join(fails)))
                bc.sys.exit(1)
            print('\nPARITY GATE: all referenced chapters at parity.')
        return
    if not args.chapter:
        ap.error('--chapter is required (or pass --curve for the campaign-wide report)')
    elif args.lord_floor:
        lord_floor_report(args.campaign, args.chapter, args.target,
                          args.def_cap, args.res_cap, args.hp_cap)
    else:
        report(args.campaign, args.chapter)


if __name__ == '__main__':
    main()
