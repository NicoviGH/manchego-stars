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
import os
import re

import build_campaign as bc
import fe_combat as fc

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
    weapon. Staves/consumables aren't in fe_combat.W, so they're skipped."""
    for item in inventory or []:
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


def _one_enemy(name, class_token, level, weapon):
    class_enum = _enemy_class_enum(class_token)
    stats = autolevel(_class_base(class_enum),
                      _class_growths(class_enum), int(level))
    return _stats_to_combatant(name, stats, weapon, CLASS_TAGS.get(class_enum, frozenset()))


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

# Vanilla FE8 reference fields, by chapter number -- the parity yardstick. Ch1 is the
# 4 units vanilla actually deploys at "Escape!"; stats are char+class from git HEAD.
# Extend as later chapters are mirrored.
VANILLA_FIELDS = {
    1: [
        fc.Combatant('Eirika', 16, 4, 8, 9, 3, 1, 5, 5, fc.W['rapier']),
        fc.Combatant('Seth', 30, 14, 13, 12, 11, 8, 13, 11, fc.W['silver-lance']),
        fc.Combatant('Franz', 20, 7, 5, 7, 6, 1, 2, 9, fc.W['iron-lance']),
        fc.Combatant('Gilliam', 25, 9, 6, 3, 9, 3, 3, 13, fc.W['iron-lance']),
    ],
}

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


def report(campaign, ch):
    chap, roster, line, bosses, deploy_limit, labels = load_field(campaign, ch)
    num = chap.get('chapter_number')
    bar = '=' * 80
    print(bar)
    print('CH%s "%s" -- difficulty / vanilla parity   [STATIC proxy -- playtest is arbiter]'
          % (num, chap.get('title', ch)))
    print(bar)
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
                 u.weapon.name, do, dfst, best[0],
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

    van = VANILLA_FIELDS.get(num)
    if van:
        vm = _metrics(van, line, bosses)
        print('\n-- VANILLA Ch%s PARITY DELTA ' % num + '-' * 49)
        print('  vanilla (%s): thru %.2f · dura(min) %.1f%s'
              % ('/'.join(u.name for u in van), vm['throughput'], vm['min_durability'],
                 ' · carry %s' % _fmt_rounds(vm['carry'][1]) if 'carry' in vm else ''))
        print('  ours (best %d):  thru %.2f (%+.2f) · dura(min) %.1f (%+.1f)%s'
              % (deploy_limit, m['throughput'], m['throughput'] - vm['throughput'],
                 m['min_durability'], m['min_durability'] - vm['min_durability'],
                 ' · carry %s' % _fmt_rounds(m['carry'][1]) if 'carry' in m else ''))
    else:
        print('\n(no vanilla reference field recorded for Ch%s yet -- delta skipped)' % num)


def main():
    ap = bc.argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument('--chapter', required=True, help='chapter id, e.g. ch01')
    ap.add_argument('--campaign', default='rime-of-the-frostmaiden')
    args = ap.parse_args()
    report(args.campaign, args.chapter)


if __name__ == '__main__':
    main()
