#!/usr/bin/env python3
"""Danger map: the damage a unit standing on a tile can expect on each enemy phase (#430
step 1, #367 proposal 2).

`rescue_forecast` answers this for one protected tile and one declared pursuer. This answers
it for every tile and every enemy body, out of the same parts:

  * WHO CAN STAND WHERE on enemy phase t is the AI shape (`chapter_status.ai_shape`) walked
    over the contested map (`map_placement_preview.foot_reach`, turn-1 bodies block). A
    statue stays on its tile. A striker steps out within one turn's movement, every phase.
    A pursuer has walked t turns of movement by phase t. A reinforcement acts from the turn
    it arrives on.
  * WHO CAN HIT A TILE is the cells within each weapon's range of it (FE8 has no line of
    sight) that the attacker can stand on that phase. A cell a statue occupies is taken.
  * HOW MANY OF THEM HIT AT ONCE is a matching: one attacker per firing cell. ch06's east
    hull has one melee door, and a map that summed everyone in range would read four
    attackers where one fits (#367's warning). The attackers whose cells can all be filled
    at once form a transversal matroid, so taking them greedily by damage finds the
    heaviest set that fits.
  * HOW MUCH is the engine's own strike (`strike`): the 2RN hit (`Roll2RN`, bmbattle.c's
    `BattleGenerateHitAttributes`), the 1RN crit at x3, and a follow-up on a 4-AS lead.
    `fe_combat`'s metrics read displayed hit and no crit. This module is calibrated against
    real runs, so it reads what the cartridge rolls.

HONEST LIMITS. Enemies walk through each other, as FE8's flood fill lets them, and only
the green hulls block them; the player's own units, which do block, are where the player
puts them. Strikers that step out stay where they stepped. Every enemy is assumed to want this tile;
the real AI picks one target. That makes a tile's reading an UPPER bound on how many attack
it, and the matching is what keeps the bound honest. Crit-bonus classes (`CA_CRITBONUS`)
and weapon effects other than effectiveness are not modelled.

    python3 tools/danger_map.py ch06 --boats          # each hull, phase by phase
    python3 tools/danger_map.py ch06 --unit marty --phase 2
"""
import argparse
import dataclasses
import functools
import os
import random
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import chapter_status as cs                                          # noqa: E402
import difficulty as dif                                             # noqa: E402
import fe_combat as fc                                               # noqa: E402
import inject.chapter_settings                                       # noqa: E402
import inject.decomp                                                 # noqa: E402
import inject.raw_pids                                               # noqa: E402
import map_placement_preview as pp                                   # noqa: E402


# ── The engine's strike ──────────────────────────────────────────────────────────

@functools.lru_cache(maxsize=None)
def true_hit(displayed):
    """P(hit) for a displayed hit rate: `Roll2RN` (rng.c) hits when the floored average of
    two 0-99 rolls is below the threshold. 47 displayed is 45% true; 80 is 92%."""
    displayed = max(0, min(100, displayed))
    return sum(1 for a in range(100) for b in range(100) if (a + b) // 2 < displayed) / 1e4


def crit_rate(atk, dfn):
    """`ComputeBattleUnitCritRate` less `ComputeBattleUnitEffectiveCritRate`'s dodge: weapon
    crit + Skl/2 - the defender's Lck, floored at 0. Rolled on 1RN, so the rate is the
    probability. The +15 of a crit-bonus class is not modelled."""
    if atk.weapon is None:
        return 0
    return max(0, min(100, atk.weapon.crit + atk.skl // 2 - dfn.lck))


@functools.lru_cache(maxsize=None)
def poison_weapons():
    """Our weapon keys whose decomp item carries `WPN_EFFECT_POISON` (data_items.c). A hit
    from one deals its damage AND poisons (`BattleGenerateHitEffects`)."""
    text = inject.decomp.vanilla_decomp_text('src/data_items.c')
    return frozenset(dif.ITEM_TO_WEAPON[item]
                     for item, body in re.findall(r'\[(ITEM_\w+)\] = \{(.*?)\n\t\},', text, re.S)
                     if 'WPN_EFFECT_POISON' in body and item in dif.ITEM_TO_WEAPON)


# Poison (`SetUnitStatus`, bmunit.c) lasts 5 of the victim's phases and takes NextRN_N(3)+1,
# 1 to 3 HP, at the start of each (`MakePoisonDamageTargetList`, bmtarget.c). A new
# poisoning hit refreshes it.
POISON_PHASES = 5
POISON_TICK = (1, 3)


@dataclasses.dataclass(frozen=True)
class Strike:
    """One attacker's combat against one defender: `strikes` swings (2 on a follow-up),
    each hitting with `p_hit` for `damage`, tripled with `p_crit` once it hits. A hit with a
    `poisons` weapon also poisons."""
    strikes: int
    p_hit: float
    p_crit: float
    damage: int
    poisons: bool = False

    @property
    def expected(self):
        return self.strikes * self.p_hit * self.damage * (1 + 2 * self.p_crit)


def strike(atk, dfn, terrain_avoid=0):
    if atk.weapon is None:
        return Strike(0, 0.0, 0.0, 0)
    return Strike(2 if fc.doubles(atk, dfn) else 1,
                  true_hit(fc.hit_chance(atk, dfn, terrain_avoid)),
                  crit_rate(atk, dfn) / 100.0,
                  fc.damage(atk, dfn),
                  atk.weapon.name in poison_weapons())


# ── Who is on the board, and where each can stand ───────────────────────────────

@dataclasses.dataclass(frozen=True)
class Body:
    """One enemy body: its tile, AI shape and ACTION byte, the turn it arrives, how it moves,
    and one Combatant per weapon it carries (the AI equips whichever lets it attack)."""
    id: str
    index: int
    source: tuple
    shape: str
    action: int
    arrives: int
    table: str
    mov: int
    arms: tuple


def _arms(enemy, combatant):
    weapons = [dif._weapon_for([item]) for item in (enemy.get('inventory') or ())]
    weapons = [w for w in weapons if w is not None and w.kind != 'staff']
    if not weapons and combatant.weapon is not None:
        weapons = [combatant.weapon]
    return tuple(dataclasses.replace(combatant, weapon=w) for w in weapons)


def bodies(chapter, mode=None, every_mode=False):
    """Every enemy body the chapter fields on `mode` (None reads the authored table, as
    `make difficulty` does). `every_mode` keeps the Difficult-only entries on any mode, for
    a question asked of the chapter rather than of one playthrough. An AI vector the decomp
    does not name reads as a pursuer, the worst case, and keeps its shape None so the report
    can say so."""
    shifts = inject.chapter_settings.chapter_difficulty_shifts(chapter) if mode else None
    out = []
    for key in inject.raw_pids.ENEMY_ROSTER_KEYS:
        for enemy in chapter.get(key) or ():
            if not isinstance(enemy, dict) or (enemy.get('hard_mode_only') and not every_mode
                                               and mode != 'difficult'):
                continue
            arrives = (1 if inject.raw_pids.entry_is_turn1(key, enemy) else
                       int(enemy.get('arrives_turn') or enemy.get('trigger_turn') or 1))
            units = dif._entry_combatants(enemy, mode=mode, shifts=shifts, real_article=True,
                                          drop_staff=False)
            table, mov = pp.class_movement(enemy.get('deploy_class') or enemy['class'])
            for index, tile in enumerate(enemy.get('positions') or ()):
                ai = dif.enemy_ai_bytes(chapter, enemy, index)
                out.append(Body(enemy.get('id'), index, tuple(tile), cs.ai_shape(ai), ai[0],
                                arrives, table, mov,
                                _arms(enemy, units[min(index, len(units) - 1)])))
    return out


def _moves_like(body):
    """The shape a body moves as. own-errand moves, but not at the player: a striker's
    reach is the honest reading of what it can hit on the way. Unnamed reads as pursuer."""
    return {'statue': 'statue', 'striker': 'striker', 'own-errand': 'striker'}.get(
        body.shape, 'pursuer')


def green_bodies(chapter):
    """The tiles that stop an enemy's walk. `MapFloodCoreStep` (bmidoten.c) refuses a cell
    whose unit's index differs from the walker's in bit 0x80, so a red walks through reds
    and is stopped by blue and green alike. The player's units are where the player puts
    them, so the green ones, the rescue hulls, are what a static read can block on."""
    return {tuple(b['tile']) for b in chapter.get('rescue_boats') or ()}


ENGAGE_HORIZON = 30         # phases a pursuer is walked looking for its first target


def in_range(arm, cell, tile):
    """Can `arm` strike `tile` from `cell`? Manhattan distance inside its range; FE8 has no
    line of sight."""
    d = abs(cell[0] - tile[0]) + abs(cell[1] - tile[1])
    return d > 0 and arm.weapon.rng[0] <= d <= arm.weapon.rng[1]


class Board:
    """A chapter's terrain and bodies, and each body's standable cells per enemy phase.

    With no `targets` it is FE's own danger zone: every pursuer may be anywhere its walk has
    reached, so a tile's reading is an upper bound on who can be there. With `targets` (tiles
    the enemy is known to want, the rescue hulls) a pursuer ENGAGES the first one it can hit
    and stops advancing: from that phase on it reaches no further than it did then. That is
    what the ch06 runs show: the crab worked the west door from phase 2 to the end, and an
    unconstrained walk would have it cross the map to the east hull as well."""

    def __init__(self, chapter, mode=None, terrain=None, targets=(), spared_by=(),
                 every_mode=False):
        self.chapter = chapter
        self.targets = tuple(tuple(t) for t in targets)
        self.spared_by = tuple(spared_by)
        self.terrain = terrain if terrain is not None else pp.terrain_grid(chapter)
        self.bodies = bodies(chapter, mode, every_mode)
        self.blocked = green_bodies(chapter)
        self.statues = {b.source for b in self.bodies
                        if _moves_like(b) == 'statue' and b.arrives <= 1}
        self._walks, self._stands, self._engaged = {}, {}, {}

    def _walk(self, body):
        key = (body.id, body.index)
        if key not in self._walks:
            self._walks[key] = pp.foot_reach(self.terrain, [body.source], blocked=self.blocked,
                                             cost=pp.mov_cost_row(body.table))
        return self._walks[key]

    def _reach(self, body, phase):
        """Where `body` can stand on enemy phase `phase`, ignoring engagement."""
        if phase < body.arrives or not body.arms:
            return frozenset()
        moves = _moves_like(body)
        if moves == 'statue':
            return frozenset({body.source})
        budget = body.mov * (1 if moves == 'striker' else phase - body.arrives + 1)
        return frozenset(c for c, points in self._walk(body).items()
                         if points <= budget and (c == body.source or c not in self.statues))

    def engaged(self, body):
        """The first phase a pursuer can hit one of the `targets`, or None. A body whose
        action spares the targets never engages them. "Can hit" is `attacks_on`'s own rule:
        a cell it can reach, with a weapon whose range spans the distance."""
        key = (body.id, body.index)
        if key not in self._engaged:
            def hits(cell):
                return any(in_range(arm, cell, t) for t in self.targets for arm in body.arms)
            self._engaged[key] = None if body.action in self.spared_by else next(
                (p for p in range(body.arrives, body.arrives + ENGAGE_HORIZON)
                 if any(hits(c) for c in self._reach(body, p))), None)
        return self._engaged[key]

    def stands(self, body, phase):
        """The cells `body` can attack from on enemy phase `phase`."""
        key = (body.id, body.index, phase)
        if key not in self._stands:
            if _moves_like(body) == 'pursuer' and self.targets and self.engaged(body):
                phase = min(phase, self.engaged(body))
            self._stands[key] = self._reach(body, phase)
        return self._stands[key]


# ── A tile's danger ─────────────────────────────────────────────────────────────

@dataclasses.dataclass(frozen=True)
class Attack:
    body: Body
    strike: Strike


def _matchable(adjacency):
    """Can every attacker in `adjacency` (a list of cell sets) hold a cell of its own?"""
    owner = {}

    def place(i, seen):
        for c in adjacency[i]:
            if c not in seen:
                seen.add(c)
                if c not in owner or place(owner[c], seen):
                    owner[c] = i
                    return True
        return False

    return all(place(i, set()) for i in range(len(adjacency)))


INERT_ACTION = 0x06          # AI_A_06 DoNothing: vanilla Ch6's villagers; never attacks


def attacks_on(board, tile, defender, phase, spared_by=()):
    """The attacks that land on a `defender` standing on `tile` on enemy phase `phase`: the
    heaviest set of attackers that can each hold a firing cell of their own, greedily by
    expected damage (optimal on the transversal matroid the cells make).

    `spared_by` is the ACTION bytes that refuse this defender: a rescue target is spared by
    `check.RESCUE_SAFE_ACTIONS` (AI_A_08, repointed at the boat pids), a player unit by none."""
    tx, ty = tile
    name = pp.NAME_BY_TERRAIN.get(board.terrain[ty][tx])
    target, avoid = dif.on_terrain(defender, name)
    candidates = []
    for body in board.bodies:
        if body.action == INERT_ACTION or body.action in spared_by:
            continue
        cells = {}
        for c in board.stands(body, phase):
            for arm in body.arms:
                if in_range(arm, c, tile):
                    s = strike(arm, target, avoid)
                    if s.expected > 0 and (c not in cells or s.expected > cells[c].expected):
                        cells[c] = s
        if cells:
            best = max(cells.values(), key=lambda s: s.expected)
            candidates.append((best, body, set(cells)))
    chosen, adjacency = [], []
    for best, body, cells in sorted(candidates, key=lambda x: -x[0].expected):
        if _matchable(adjacency + [cells]):
            adjacency.append(cells)
            chosen.append(Attack(body, best))
    return chosen


def expected_damage(attacks):
    return sum(a.strike.expected for a in attacks)


def danger_grid(board, defender, phase):
    """{tile: expected damage} for every foot-standable tile on enemy phase `phase`."""
    out = {}
    for y, row in enumerate(board.terrain):
        for x, terrain in enumerate(row):
            if pp.FOOT_COST.get(terrain) is not None:
                out[(x, y)] = expected_damage(attacks_on(board, (x, y), defender, phase))
    return out


SINK_TRIALS = 4001
SINK_SEED = 430


def sink_turns(board, tile, defender, horizon, spared_by=(), trials=SINK_TRIALS):
    """The enemy phase a `defender` that never moves off `tile`, never heals and never
    fights back drops on, over `trials` simulated fights; None for a run it survives
    `horizon` phases. A rescue hull is exactly this target."""
    return simulate_sink(defender.hp, [attacks_on(board, tile, defender, t, spared_by)
                                       for t in range(1, horizon + 1)], trials)


def simulate_sink(hp, per_phase, trials=SINK_TRIALS):
    """`sink_turns` over a given list of each enemy phase's attacks (phase 1 first). Poison
    ticks at the start of the defender's own phase, which follows the enemy phase it was
    poisoned on, so a tick that drops it counts to that turn."""
    rng = random.Random(SINK_SEED)
    out = []
    for _ in range(trials):
        left, sunk, poisoned = hp, None, 0
        for t, attacks in enumerate(per_phase, 1):
            for a in attacks:
                for _ in range(a.strike.strikes):
                    if rng.random() < a.strike.p_hit:
                        left -= a.strike.damage * (3 if rng.random() < a.strike.p_crit else 1)
                        if a.strike.poisons:
                            poisoned = POISON_PHASES
            if poisoned and left > 0:
                left -= rng.randint(*POISON_TICK)
                poisoned -= 1
            if left <= 0:
                sunk = t
                break
        out.append(sunk)
    return out


def percentile(turns, q):
    """The `q`th percentile sink turn, inf for one past the horizon."""
    finite = sorted(t if t is not None else float('inf') for t in turns)
    return finite[min(len(finite) - 1, len(finite) * q // 100)]


# ── CLI ─────────────────────────────────────────────────────────────────────────

def _boats_report(chapter, mode, horizon):
    import rescue_forecast as rf
    from check import RESCUE_SAFE_ACTIONS
    board = Board(chapter, mode, targets=[b['tile'] for b in chapter.get('rescue_boats') or ()],
                  spared_by=RESCUE_SAFE_ACTIONS)
    for boat in board.chapter.get('rescue_boats') or ():
        tile = tuple(boat['tile'])
        hull = rf.target_combatant(boat)
        print('%s at %s, %d HP' % (boat['id'], tile, hull.hp))
        for t in range(1, horizon + 1):
            attacks = attacks_on(board, tile, hull, t, RESCUE_SAFE_ACTIONS)
            print('  EP%-2d %5.2f  %s' % (t, expected_damage(attacks), ', '.join(
                '%s#%d %dx%d@%.0f%%%s' % (a.body.id, a.body.index, a.strike.strikes,
                                          a.strike.damage, 100 * a.strike.p_hit,
                                          ' +poison' if a.strike.poisons else '')
                for a in attacks) or '-'))
        turns = sink_turns(board, tile, hull, horizon, RESCUE_SAFE_ACTIONS)
        afloat = sum(1 for t in turns if t is None) / len(turns)
        print('  sinks: p10 EP%s  median EP%s  p90 EP%s  afloat after EP%d: %.0f%%'
              % (percentile(turns, 10), percentile(turns, 50), percentile(turns, 90),
                 horizon, 100 * afloat))


def _grid_report(board, defender, phase):
    grid = danger_grid(board, defender, phase)
    h, w = len(board.terrain), len(board.terrain[0])
    print('%s (%d HP) on enemy phase %d: expected damage per tile ("#" = lethal, "." = none,'
          ' blank = no ground)' % (defender.name, defender.hp, phase))
    print('    ' + ''.join('%3d' % x for x in range(w)))
    for y in range(h):
        cells = []
        for x in range(w):
            v = grid.get((x, y))
            cells.append('   ' if v is None else '  .' if v == 0 else
                         '  #' if v >= defender.hp else '%3d' % round(v))
        print('%3d ' % y + ''.join(cells))


def main(argv):
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('chapter', help='chapter id or prefix, e.g. ch06')
    ap.add_argument('--mode', choices=dif.MODES, help='difficulty mode (default: authored)')
    ap.add_argument('--boats', action='store_true', help='each rescue hull, phase by phase')
    ap.add_argument('--horizon', type=int, default=12, help='enemy phases to forecast')
    ap.add_argument('--unit', help='a cast member, at the level it arrives at')
    ap.add_argument('--phase', type=int, default=1)
    ap.add_argument('--campaign', default='rime-of-the-frostmaiden')
    args = ap.parse_args(argv)

    board = Board(pp.load_chapter(args.chapter), args.mode)
    unnamed = sorted({b.id for b in board.bodies if b.shape is None})
    if unnamed:
        print('!! AI unnamed in the decomp, read as pursuers: %s' % ', '.join(unnamed))
    if args.boats:
        _boats_report(board.chapter, args.mode, args.horizon)
    if args.unit:
        ch = str(board.chapter['id'])[:4]
        roster = dif.load_field(args.campaign, ch, leveled=True)[1]
        unit = next((u for u in roster if u.name == args.unit), None)
        if unit is None:
            sys.exit('ERROR: %s is not in the party arriving at %s' % (args.unit, ch))
        _grid_report(board, unit, args.phase)


if __name__ == '__main__':
    main(sys.argv[1:])
