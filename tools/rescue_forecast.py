#!/usr/bin/env python3
"""Rescue-fuse forecast: for a protected tile (a rescue boat, a defend objective, a fragile
NPC), which enemies can get a firing position on it, on what turn, for how much damage per
phase, and therefore when does it die.

This is deliberately NOT a full per-tile danger grid -- #367 asked whether the difficulty
model has an unwired spatial element, and a whole-map danger grid was explicitly cut from
this answer's scope. What is built instead is the narrower, reusable question every chapter
with a rescue clock actually asks, proven against ch06's two boats and meant to carry
forward to the campaign's other ~20 chapters unchanged.

Nothing here is a new combat model: every damage/hit number comes straight from
`fe_combat.py` (the decomp's own math), every stat resolution from `difficulty.py`, and
every walk from `map_placement_preview.foot_reach` (a Dijkstra over the engine's own
per-class movement-cost tables). This module is the GLUE between them:

  1. `firing_cells` -- every cell within a weapon's range that a foot unit can stand on.
     The throughput bound: at most one attacker per cell per phase, allies block each other.
  2. `arrival_to_cells` -- the turn an enemy first stands on ANY of those cells, walking the
     CONTESTED map (turn-1 enemy bodies block, same as `map_placement_preview.reached_on`'s
     own reading). `None` if no firing cell is reachable at all -- a first-class result, not
     an error: ch06's merfolk-thrower is exactly this case, corked by its own line.
  3. `fe_combat.damage_per_round` -- damage per phase, target resolved on its real terrain
     via `difficulty.on_terrain`.
  4. `sink_band` -- HP / damage-per-phase is a MEAN, not a fact, because a phase either
     connects or it does not (`docs/decisions.md` -> "A rescue clock is a HIT RATE, so a
     scenario MEASURES it and never asserts it"). Reported as a band; see its own docstring
     for exactly what the band means and how it's built.
  5. `concurrent_attacker_cap` -- when several enemies can reach one target, how many can
     attack it in the SAME phase is capped by the number of distinct firing cells a MATCHING
     can assign them to. ch06's two hulls each have exactly one melee door, so this is not
     load-bearing there yet -- it is built in for the wider targets later chapters will ship.

HONEST LIMITS, inherited from what this reuses: a turn-1 CONTESTED SNAPSHOT (strikers can
still step into the route on later phases, and the player kills bodies out of it -- see
`map_placement_preview.foot_reach`'s own docstring), and a static per-hit damage/hit-chance
read with no positioning or AI beyond "does it path to a firing cell" (`fe_combat`'s own
warning). It is a forecast, not a prophecy -- a real playtest is still the arbiter.

    python3 tools/rescue_forecast.py ch06
"""
import argparse
import dataclasses
import math
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'tools'))
import build_campaign as bc                                          # noqa: E402
import difficulty as dif                                             # noqa: E402
import fe_combat as fc                                                # noqa: E402
import map_placement_preview as pp                                   # noqa: E402


def firing_cells(terrain, target, weapon_range):
    """Every cell at Manhattan distance 1..`weapon_range` from `target` that a foot unit can
    stand on -- the set of tiles an attacker could occupy to hit it. FE8 has no line of
    sight (decisions.md -> "What terrain cannot do is stop a ranged weapon"), so this is
    pure Manhattan distance, not a walk: a range-2 firing cell three tiles out through a
    wall is exactly as live as the door directly beside the target.

    Standability is FOOT passability (`map_placement_preview.FOOT_COST`), a generic ground
    proxy rather than any one attacker's own class -- the cell has to exist for SOME ground
    unit to occupy it before who specifically reaches it is asked. The target's own tile
    (distance 0) is never a firing cell."""
    tx, ty = target
    h, w = len(terrain), len(terrain[0])
    out = []
    for y in range(h):
        for x in range(w):
            d = abs(x - tx) + abs(y - ty)
            if 1 <= d <= weapon_range and pp.FOOT_COST.get(terrain[y][x]) is not None:
                out.append((x, y))
    return sorted(out)


def arrival_to_cells(terrain, source, cost_table, mov, cells, blocked=()):
    """The turn an enemy at `source` (moving `mov` a turn on `cost_table`, a
    `pMovCostTable` symbol per `map_placement_preview.class_movement`) first stands on ANY
    of `cells`, walking the CONTESTED map (`blocked` -- turn-1 enemy bodies, which a unit
    may not enter or pass through). `None` if none of `cells` is reachable at all -- the
    enemy never gets a firing position, which is a first-class outcome (ch06's
    merfolk-thrower: its own line corks every one of its four javelin cells)."""
    if not cells:
        return None
    cost = pp.mov_cost_row(cost_table)
    dist = pp.foot_reach(terrain, [tuple(source)], blocked=blocked, cost=cost)
    reachable = [dist[c] for c in cells if c in dist]
    if not reachable:
        return None
    return pp.arrival_turn(min(reachable), mov)


@dataclasses.dataclass(frozen=True)
class SinkBand:
    """Phases FROM ARRIVAL, not turns -- the caller adds the arrival turn. See `sink_band`."""
    low: int
    expected: int
    high: int


def sink_band(hp, attacker, target, terrain_avoid=0, z=1.0):
    """How many PHASES of continuous attack it takes `attacker` to sink a `hp`-HP target,
    as a band, not a point -- because a phase either connects or it does not, and "HP /
    damage-per-phase" is the MEAN of a random variable, not its value
    (`docs/decisions.md` -> "A rescue clock is a HIT RATE").

    Modeled as the first-passage time of a random walk with the phase's own mean and
    variance (the Wald / inverse-Gaussian approximation for a Brownian motion with drift):
    a phase deals `hits` (1, or 2 on a follow-up) independent Bernoulli(p) connects worth
    `dmg` each, so its damage has mean `mu = dmg * hits * p` (exactly
    `fe_combat.damage_per_round` -- the point estimate this band is built around IS that
    number, per the literal spec "forecast sink turn = arrival + HP / damage_per_phase") and
    variance `sigma2 = dmg**2 * hits * p * (1-p)`. For a target needing `hp` total damage:

        E[phases]   = hp / mu
        Var[phases] = hp * sigma2 / mu**3

    `z` widens or narrows the band (default 1.0: mean +/- one modeled standard deviation).
    This is a HEURISTIC width, not a claimed exact percentile -- HP is discrete and the true
    process is closer to a negative binomial than a Brownian motion, but that is the same
    order of approximation `damage_per_round` itself already is (a static, mean-only combat
    proxy the rest of this codebase accepts). The low end is additionally floored at the
    deterministic BEST case -- every attack connects -- since no amount of luck sinks a
    target faster than that.

    Returns `None` if `attacker` cannot damage `target` at all (no weapon, or 0 true
    damage): "never sinks it" is a fact worth a `None`, not a divide-by-zero.
    """
    if attacker.weapon is None:
        return None                                 # a weaponless body threatens nothing
    dmg = fc.damage(attacker, target)
    p = fc.hit_chance(attacker, target, terrain_avoid) / 100.0
    if dmg <= 0 or p <= 0:
        return None
    hits = 2 if fc.doubles(attacker, target) else 1
    mu = dmg * hits * p
    sigma2 = dmg ** 2 * hits * p * (1 - p)
    hits_needed = -(-hp // dmg)                     # ceil(hp / dmg)
    floor_phases = -(-hits_needed // hits)          # every hit connects -- the fastest case
    mean_phases = hp / mu
    var_phases = hp * sigma2 / mu ** 3
    sd_phases = var_phases ** 0.5
    low = max(floor_phases, math.ceil(mean_phases - z * sd_phases))
    high = math.ceil(mean_phases + z * sd_phases)
    expected = math.ceil(mean_phases)
    return SinkBand(low=low, expected=expected, high=max(high, expected))


def _bipartite_matching_size(adjacency):
    """Maximum bipartite matching (Kuhn's algorithm) between `adjacency`'s left nodes
    (indices into it) and whatever right-side tokens its lists name. Small inputs only --
    a chapter's simultaneous attackers and a target's firing cells are a handful, never a
    graph this needs to be fast on."""
    match_right = {}

    def augment(u, seen):
        for v in adjacency[u]:
            if v in seen:
                continue
            seen.add(v)
            if v not in match_right or augment(match_right[v], seen):
                match_right[v] = u
                return True
        return False

    count = 0
    for u in range(len(adjacency)):
        if augment(u, set()):
            count += 1
    return count


def concurrent_attacker_cap(terrain, target, weapon_ranges):
    """How many attackers, with these `weapon_ranges` (one entry per attacker), can occupy
    DISTINCT firing cells for `target` in the SAME phase.

    Not every attacker can use every cell -- a melee attacker needs the one door, a range-2
    attacker can use any of the wider ring -- so this is a bipartite MATCHING between
    attackers and the cells within each one's own range, not a single number divided
    between them. ch06's two hulls each have exactly one melee door (cap 1 for any group of
    melee attackers), so this has nothing to prove there yet; it exists for the wider
    targets later chapters will field, and is pinned on synthetic mixed-range groups for
    that reason (`test_rescue_forecast.py`)."""
    if not weapon_ranges:
        return 0
    cells_by_range = {r: firing_cells(terrain, target, r) for r in set(weapon_ranges)}
    adjacency = [cells_by_range[r] for r in weapon_ranges]
    return _bipartite_matching_size(adjacency)


@dataclasses.dataclass(frozen=True)
class PursuerForecast:
    """One (enemy, boat) pair's whole forecast. `arrival_turn` and the `sink_*` fields are
    `None` when the enemy cannot reach any firing cell for this boat -- "never engages" is
    the finding, not a missing number."""
    enemy_id: str
    boat_id: str
    weapon_range: int
    arrival_turn: object
    damage_per_phase: object
    sink_low: object
    sink_expected: object
    sink_high: object


def target_combatant(boat):
    """The Combatant a `rescue_boats:` entry fights as: its declared class's base stats,
    unarmed (a rescue target never attacks back -- FE8's civilian hulls carry no weapon)."""
    enum = dif._enemy_class_enum(boat['class'])
    base = dif._class_base(enum)
    return dif._stats_to_combatant(boat.get('id', 'target'), base, weapon=None)


def _boat_terrain_name(terrain, boat):
    tx, ty = boat['tile']
    return pp.NAME_BY_TERRAIN.get(terrain[ty][tx])


def pursuer_forecast(chapter, terrain, enemy_def, index, boat):
    """The full forecast for one enemy BODY (`enemy_def`'s `index`'th position) against one
    `rescue_boats:` entry -- arrival, damage/phase, and the sink band, or all `None` past
    `arrival_turn` when the enemy never gets a firing position at all."""
    combatants = dif._entry_combatants(enemy_def, real_article=True)
    attacker = combatants[index]
    weapon_range = attacker.weapon.rng[1] if attacker.weapon else 0
    boat_tile = tuple(boat['tile'])
    none_row = PursuerForecast(enemy_def.get('id'), boat['id'], weapon_range,
                               None, None, None, None, None)
    if weapon_range <= 0:
        return none_row                          # a staff/unarmed body threatens nothing
    positions = enemy_def.get('positions') or ()
    if index >= len(positions):
        return none_row
    source = positions[index]
    table, mov = pp.class_movement(enemy_def.get('deploy_class') or enemy_def['class'])
    blocked = pp.enemy_bodies(chapter)
    cells = firing_cells(terrain, boat_tile, weapon_range)
    arrival = arrival_to_cells(terrain, source, table, mov, cells, blocked)
    if arrival is None:
        return none_row
    terrain_name = _boat_terrain_name(terrain, boat)
    target, terrain_avoid = dif.on_terrain(target_combatant(boat), terrain_name)
    dpr = fc.damage_per_round(attacker, target, terrain_avoid)
    band = sink_band(target.hp, attacker, target, terrain_avoid)
    if band is None:
        return PursuerForecast(enemy_def.get('id'), boat['id'], weapon_range,
                               arrival, dpr, None, None, None)
    return PursuerForecast(enemy_def.get('id'), boat['id'], weapon_range, arrival, dpr,
                           arrival + band.low, arrival + band.expected, arrival + band.high)


def chapter_forecast(chapter):
    """Every (declared pursuer x rescue boat) forecast for one chapter. [] on a chapter with
    no `rescue_boats:` or no `rescue_pursuers:` -- there is no clock to forecast."""
    boats = chapter.get('rescue_boats') or []
    pursuers = chapter.get('rescue_pursuers') or []
    if not boats or not pursuers:
        return []
    terrain = pp.terrain_grid(chapter)
    roster = {e.get('id'): e for e in bc.chapter_roster_entries(chapter)}
    out = []
    for pursuer in pursuers:
        enemy_def = roster.get(pursuer['id'])
        if enemy_def is None:
            continue                # a chapter-schema problem another guard already catches
        for index in range(len(enemy_def.get('positions') or ())):
            for boat in boats:
                out.append(pursuer_forecast(chapter, terrain, enemy_def, index, boat))
    return out


def main(argv):
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('chapter', help='chapter id or prefix, e.g. ch06')
    args = ap.parse_args(argv)

    import campaign_chapters
    chapter = pp.load_chapter(args.chapter)
    rows = chapter_forecast(chapter)
    if not rows:
        print('%s: no rescue_boats/rescue_pursuers declared' % args.chapter)
        return
    for row in rows:
        if row.arrival_turn is None:
            print('%-22s -> %-10s never reaches a firing cell (weapon range %d)'
                 % (row.enemy_id, row.boat_id, row.weapon_range))
            continue
        print('%-22s -> %-10s arrives turn %-3d %.2f dmg/phase  sinks turn %s-%s (expect %s)'
             % (row.enemy_id, row.boat_id, row.arrival_turn, row.damage_per_phase,
                row.sink_low, row.sink_high, row.sink_expected))


if __name__ == '__main__':
    main(sys.argv[1:])
