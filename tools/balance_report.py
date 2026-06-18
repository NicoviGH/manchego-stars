#!/usr/bin/env python3
"""Quantify Chapter 1 difficulty: our lordless cast vs vanilla FE8 Ch1, same enemies.

Why: friends found Ch1 harder than vanilla. Ch1 is a 1:1 field mirror of FE8 Ch1
"Escape!" (same Seize, same 7 enemies + 3 reinforcements, same lv1/lv4 spread), so the
difficulty delta is almost entirely on the PLAYER side -- vanilla fielded a promoted
Paladin juggernaut (Seth) + a fast effective-weapon lord (Eirika) + a mobile cavalier
+ a tanky armor; we field four lv1 unpromoted units with no carry. This script makes
that quantitative instead of vibes.

All formulas are the decomp's own (fireemblem8u/src/bmbattle.c), all stats are sourced:
  - our cast: campaigns/.../pcs/*.yaml (vanilla class bases, char layer = 0, Lck 0)
  - vanilla units / enemies / weapons: fireemblem8u git HEAD (data_classes.c,
    data_characters.c, data_items.c, events/ch1-eventudefs.h) -- citations inline.

Combat model (bmbattle.c):
  AS      = Spd - max(0, Wt - Con)                         (l.564-571, floored at 0)
  Hit     = Skl*2 + wpnHit + Lck//2 + triangleHit          (l.578)
  Avoid   = AS*2 + terrainAvoid + Lck                       (l.582)
  HitShown= clamp(atkHit - defAvoid, 0, 100)                (l.600-603)
  Atk     = Pow + wpnMt + triangleDmg   (x3 whole if effective, l.531)
  Damage  = max(0, Atk - (Def | Res))                       Res for magic
  Double  if (atkAS - defAS) >= 4                           (BATTLE_FOLLOWUP_THRESHOLD)
Triangle (GBA FE8): advantage +1 Mt / +15 Hit, disadvantage -1 / -15.

Run: python3 tools/balance_report.py
"""
import os
import yaml

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PCS = os.path.join(REPO, 'campaigns', 'rime-of-the-frostmaiden', 'pcs')

# ── Weapons: (Mt, Hit, Crit, Wt, kind, rng_min, rng_max) ── data_items.c (HEAD) ──────
# Magic 'kind' resolves to the Res defence; physical kinds resolve to Def. The triangle
# runs sword>axe>lance>sword; bows/magic are off-triangle (neutral).
W = {
    'iron-sword':   (5, 90, 0, 5,  'sword', 1, 1),
    'rapier':       (7, 95, 10, 5, 'sword', 1, 1),   # effective vs cavalry + armor
    'steel-sword':  (8, 75, 0, 10, 'sword', 1, 1),
    'iron-lance':   (7, 80, 0, 8,  'lance', 1, 1),
    'silver-lance': (14, 75, 0, 10,'lance', 1, 1),
    'javelin':      (6, 65, 0, 11, 'lance', 1, 2),
    'iron-axe':     (8, 75, 0, 10, 'axe',   1, 1),
    'hand-axe':     (7, 60, 0, 11, 'axe',   1, 2),
    'iron-bow':     (6, 85, 0, 5,  'bow',   2, 2),
    'fire':         (5, 90, 0, 4,  'magic', 1, 2),
    'lightning':    (4, 95, 5, 6,  'magic', 1, 2),
    'flux':         (7, 80, 0, 8,  'magic', 1, 2),
}
TRI = {'sword': 'axe', 'axe': 'lance', 'lance': 'sword'}  # key beats value


def triangle(a, d):
    """+1 (adv) / -1 (dis) / 0 for attacker weapon kind a vs defender kind d."""
    if a not in TRI or d not in TRI:
        return 0
    if TRI[a] == d:
        return 1
    if TRI[d] == a:
        return -1
    return 0


class U:
    def __init__(self, name, hp, pow_, skl, spd, df, res, lck, con, wpn, tags=()):
        self.name, self.hp, self.pow, self.skl, self.spd = name, hp, pow_, skl, spd
        self.df, self.res, self.lck, self.con, self.wpn = df, res, lck, con, wpn
        self.tags = set(tags)

    def AS(self):
        mt, *_ , wt, kind, _, _ = (W[self.wpn][0],) + W[self.wpn][1:]
        wt = W[self.wpn][3]
        return max(0, self.spd - max(0, wt - self.con))


def hit_dmg(att, dfn, terrain_avo=0):
    """Return (hit%, dmg_per_hit, doubles, dpr) for att striking dfn (dfn on terrain)."""
    amt, ahit, acrit, awt, akind, *_ = W[att.wpn]
    dkind = W[dfn.wpn][4]
    tri = triangle(akind, dkind)
    atk = att.pow + amt + tri
    effective = ('cav' in dfn.tags or 'armor' in dfn.tags) and att.wpn == 'rapier'
    if effective:
        atk = (att.pow + amt + tri) * 3
    defence = dfn.res if akind == 'magic' else dfn.df
    dmg = max(0, atk - defence)
    a_as, d_as = att.AS(), dfn.AS()
    doubles = (a_as - d_as) >= 4
    acc = att.skl * 2 + ahit + att.lck // 2 + (15 if tri > 0 else (-15 if tri < 0 else 0))
    avo = d_as * 2 + terrain_avo + dfn.lck
    hit = max(0, min(100, acc - avo))
    hits = 2 if doubles else 1
    dpr = dmg * hits * hit / 100.0
    return hit, dmg, doubles, dpr


def rtk(att, dfn, terrain_avo=0):
    """Rounds to kill (expected, accounting for hit%). inf if can't damage."""
    hit, dmg, dbl, dpr = hit_dmg(att, dfn, terrain_avo)
    if dpr <= 0:
        return float('inf')
    return dfn.hp / dpr


# ── Our deployable cast (lv1; stats = vanilla class base, char layer 0, Lck 0) ───────
def load_cast():
    out = {}
    weap = {'braulo': 'iron-axe', 'wolfram': 'iron-lance', 'marty': 'flux',
            'meesmickle': 'flux', 'prof-rbg': 'iron-bow', 'rootis': 'fire',
            'sclorbo': 'lightning'}
    for uid, wpn in weap.items():
        d = yaml.safe_load(open(os.path.join(PCS, uid + '.yaml')))
        s = d['fe_stats']
        pow_ = s.get('STR') or {'Shaman': 2, 'Mage (Ice)': 1, 'Priest': 1}.get(s['class'], 0)
        out[uid] = U(uid, s['HP'], pow_, s['SKL'], s['SPD'], s['DEF'], s['RES'],
                     s.get('LCK') or 0, s['CON'], wpn)
    return out


OURS = load_cast()

# ── Vanilla FE8 Ch1 fielded units (char base + class base; HEAD) ─────────────────────
# Seth/Eirika reproduce their canonical stats exactly under char+class, validating the model.
VANILLA = {
    'Eirika':  U('Eirika',  16, 4, 8, 9, 3, 1, 5, 5,  'rapier'),     # Lord lv1, eff Rapier
    'Seth':    U('Seth',    30, 14, 13, 12, 11, 8, 13, 11, 'silver-lance'),  # Paladin lv1
    'Franz':   U('Franz',   20, 7, 5, 7, 6, 1, 2, 9,  'iron-lance'), # Cavalier lv1
    'Gilliam': U('Gilliam', 25, 9, 6, 3, 9, 3, 3, 13, 'iron-lance'), # Armor lv4
}

# ── Enemy set (shared field). OUR line enemies are lv1 (class base); VANILLA's were
#    lv2-3 -- so ours are if anything marginally EASIER. Boss = Breguet (Armor lv4),
#    identical in both. data_classes.c + events/ch1-eventudefs.h (HEAD). ──────────────
ENEMIES = {
    'Goblin Spear (Soldier l1)':  U('spear',  20, 3, 0, 1, 0, 0, 0, 6,  'iron-lance'),
    'Goblin Raider (Fighter l1)': U('raider', 20, 5, 2, 4, 2, 0, 0, 11, 'iron-axe'),
    'Izobai (Armor l4 boss)':     U('izobai', 20, 8, 2, 1, 9, 0, 2, 13, 'iron-lance',
                                    tags=('armor',)),
}
LINE = ['Goblin Spear (Soldier l1)', 'Goblin Raider (Fighter l1)']


def party_table(party, terrain_avo=0):
    print('  %-16s %-26s %-26s %-26s' % ('unit', *ENEMIES.keys()))
    for nm, u in party.items():
        cells = []
        for en, e in ENEMIES.items():
            hit, dmg, dbl, dpr = hit_dmg(u, e, 0)          # we attack enemy (enemy no cover here)
            ehit, edmg, edbl, edpr = hit_dmg(e, u, terrain_avo)  # enemy attacks us
            r = rtk(u, e, 0)
            htk = (u.hp / edpr) if edpr > 0 else float('inf')
            cells.append('%2d%%x%s %2ddmg RTK%s|takes%2d' % (
                hit, '2' if dbl else '1', dmg, ('%.1f' % r if r != float('inf') else 'inf'), edmg))
        print('  %-16s %s' % (u.name, '  '.join('%-26s' % c for c in cells)))


def durability(party, terrain_avo=0):
    """min enemy-rounds-to-down each unit across the line enemies (the survival metric)."""
    rows = []
    for nm, u in party.items():
        worst = min((u.hp / hit_dmg(ENEMIES[e], u, terrain_avo)[3])
                    if hit_dmg(ENEMIES[e], u, terrain_avo)[3] > 0 else 99
                    for e in LINE)
        rows.append((u.name, worst))
    return rows


def party_output(party):
    """Sum of each unit's best damage-per-round vs the line enemies (open ground) -- a
    crude 'how fast does this party delete the gauntlet' number. Vanilla's is inflated by
    Seth alone; ours needs bodies to match."""
    return sum(max(hit_dmg(u, ENEMIES[e], 0)[3] for e in LINE) for u in party.values())


def levers():
    print('\n' + '=' * 78)
    print('LEVERS (quantified) -- what closes the gap, and by how much')
    print('=' * 78)

    van4 = party_output(VANILLA)
    print('\n── Party damage-output vs the line (sum of best DPR; Seth alone ~= 3 of ours)')
    print('   vanilla fielded 4: total DPR %.1f  (Seth = %.1f of it, %.0f%%)'
          % (van4, max(hit_dmg(VANILLA['Seth'], ENEMIES[e], 0)[3] for e in LINE),
             100 * max(hit_dmg(VANILLA['Seth'], ENEMIES[e], 0)[3] for e in LINE) / van4))
    best = sorted(OURS.values(), key=lambda u: -max(hit_dmg(u, ENEMIES[e], 0)[3] for e in LINE))
    for n in (4, 5, 6):
        tot = sum(max(hit_dmg(u, ENEMIES[e], 0)[3] for e in LINE) for u in best[:n])
        print('   ours fielding %d:  total DPR %.1f  (%.0f%% of vanilla\'s 4)'
              % (n, tot, 100 * tot / van4))

    print('\n── Anchor lever: Wolfram (the armor) +3 Spd so fighters stop doubling him')
    w = OURS['wolfram']
    base = min(w.hp / hit_dmg(ENEMIES[e], w, 0)[3] for e in LINE)
    w2 = U('wolfram+3spd', w.hp, w.pow, w.skl, w.spd + 3, w.df, w.res, w.lck, w.con, w.wpn)
    buffed = min(w2.hp / hit_dmg(ENEMIES[e], w2, 0)[3] for e in LINE)
    print('   Wolfram line-hits-to-down: %.1f -> %.1f  (+3 Spd dodges the fighter double:'
          ' AS %d->%d)' % (base, buffed, w.AS(), w2.AS()))

    print('\n── Start-at-level lever: cast at lv3 (2 deterministic class-growth levels)')
    print('   defensive growths are low (Def 5-15%, HP 50-80%), so +2 lv ~= +1-2 HP, ~0 Def')
    print('   -> levels barely move DURABILITY; bodies + forest + an anchor do the work.')

    print('\n── Forest cover lever (already in-map, +20 avo): squishy hits-to-down')
    for nm in ('marty', 'sclorbo', 'rootis'):
        u = OURS[nm]
        o = min(u.hp / hit_dmg(ENEMIES[e], u, 0)[3] for e in LINE)
        f = min(u.hp / hit_dmg(ENEMIES[e], u, 20)[3] for e in LINE)
        print('   %-9s %.1f (open) -> %.1f (forest)' % (u.name, o, f))


def main():
    print('=' * 78)
    print('CH1 DIFFICULTY: our lordless cast vs vanilla FE8 Ch1 "Escape!" (same field/enemies)')
    print('=' * 78)
    print('\nNote: OUR line enemies are lv1 (class base); vanilla\'s were lv2-3 + same lv4 boss.')
    print('So the ENEMY side is, if anything, slightly EASIER for us. The gap is the PARTY.\n')

    print('── OUR PARTY vs the enemy set (cell = our hit%xhits dmg, our RTK | dmg we take/hit)')
    print('   (player attacks: enemy on open ground; "takes" = enemy dmg to us per hit, open)')
    party_table(OURS, terrain_avo=0)
    print('\n── VANILLA PARTY vs the SAME enemy set')
    party_table(VANILLA, terrain_avo=0)

    print('\n── DURABILITY: enemy line-hits to down each unit (lower = frailer)')
    print('   open ground / forest +20 avo')
    for label, party in [('OURS', OURS), ('VANILLA', VANILLA)]:
        op = durability(party, 0)
        fo = durability(party, 20)
        print('  %-8s' % label, '  '.join('%s %.1f/%.1f' % (n, o, f)
                                           for (n, o), (_, f) in zip(op, fo)))

    print('\n── CARRY GAP: best single unit vs the boss (Izobai, Def9 Res0)')
    for label, party in [('OURS', OURS), ('VANILLA', VANILLA)]:
        best = min(party.values(), key=lambda u: rtk(u, ENEMIES['Izobai (Armor l4 boss)']))
        r = rtk(best, ENEMIES['Izobai (Armor l4 boss)'])
        hit, dmg, dbl, dpr = hit_dmg(best, ENEMIES['Izobai (Armor l4 boss)'])
        print('  %-8s %-9s %d%%x%s %ddmg/hit -> ~%.1f rounds to kill the boss'
              % (label, best.name, hit, '2' if dbl else '1', dmg, r))
    levers()


if __name__ == '__main__':
    main()
