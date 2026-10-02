#!/usr/bin/env python3
"""Rescue-fuse forecast: for a protected tile (a rescue boat, a defend objective, a fragile
NPC), which declared pursuer gets a firing position on it, on what turn, for how much damage
per phase, and therefore when does it die.

The model is `danger_map`'s, calibrated against ch06's two instrumented runs (ADR 0312):
enemies walk through their own line, a pursuer engages the first hull it can hit and stops
there, hit is rolled on 2RN, crit on 1RN, and a venin hit poisons. This module asks that
model the one question each `rescue_pursuers:` entry declares, one (pursuer, hull) pair at a
time, and is what `check.py check_rescue_fuse_forecast` and `make chapter` read.

A fuse is a distribution, not a turn (ADR 0270), so the sink turn is reported as the 10th,
50th and 90th percentile of simulated fights against that pursuer alone. It is a forecast,
not a prophecy: a real playtest is still the arbiter.

    python3 tools/rescue_forecast.py ch06
"""
import argparse
import dataclasses
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'tools'))
import danger_map as dm                                              # noqa: E402
import difficulty as dif                                             # noqa: E402
import map_placement_preview as pp                                   # noqa: E402


# `firing_cells` is a terrain/range primitive -- the same family as `foot_reach` -- and
# `map_placement_preview.units_reaching` needs the identical rule for its own reachability
# check, so it lives there and this is an alias, not a second copy (#369 review).
firing_cells = pp.firing_cells

SINK_HORIZON = 30           # enemy phases a fight is simulated for; past it reads as inf


@dataclasses.dataclass(frozen=True)
class PursuerForecast:
    """One (enemy body, boat) pair's whole forecast. `arrival_turn` and the `sink_*` fields
    are `None` when the enemy never gets a firing position on this boat -- "never engages" is
    the finding, not a missing number. `sink_high` is inf when one fight in ten outlasts
    SINK_HORIZON phases."""
    enemy_id: str
    boat_id: str
    weapon_range: int
    arrival_turn: object
    damage_per_phase: object
    sink_low: object
    sink_expected: object
    sink_high: object


def target_combatant(boat):
    """The Combatant a `rescue_boats:` entry fights as, resolved through `difficulty._one_enemy`
    -- the SAME path every other enemy in this codebase resolves through, so a boat that ever
    declares a `level:`, a class carrying an effectiveness tag, or a `personal:` line is not
    silently understated the way a hand-rolled class-base read would leave it. Unarmed always
    (a rescue target never attacks back -- FE8's civilian hulls carry no weapon), regardless
    of what its class would otherwise wield."""
    return dif._one_enemy(boat.get('id', 'target'), boat['class'], boat.get('level', 1),
                          None, personal=boat.get('personal'))


def hull_board(chapter):
    """The chapter's board with its hulls as the targets the enemy wants, spared by the
    action bytes `check_rescue_targets` licenses."""
    from check import RESCUE_SAFE_ACTIONS
    return dm.Board(chapter, targets=[b['tile'] for b in chapter.get('rescue_boats') or ()],
                    spared_by=RESCUE_SAFE_ACTIONS)


def _strike_on(board, body, tile, target, avoid, phase):
    """`body`'s best strike on a `target` at `tile` from where it can stand on `phase`."""
    return max((dm.strike(arm, target, avoid) for c in board.stands(body, phase)
                for arm in body.arms if dm.in_range(arm, c, tile)),
               key=lambda s: s.expected, default=None)


def pursuer_forecast(board, body, boat):
    """The forecast for one pursuer BODY against one `rescue_boats:` entry: the first phase
    it can strike the hull, its expected damage that phase, and the sink percentiles of a
    fight against it alone."""
    tile = tuple(boat['tile'])
    weapon_range = max((arm.weapon.rng[1] for arm in body.arms), default=0)
    target, avoid = dif.on_terrain(target_combatant(boat),
                                   pp.NAME_BY_TERRAIN.get(board.terrain[tile[1]][tile[0]]))
    none_row = PursuerForecast(body.id, boat['id'], weapon_range, None, None, None, None, None)
    if body.action in board.spared_by:
        return none_row
    strikes = [_strike_on(board, body, tile, target, avoid, t)
               for t in range(1, SINK_HORIZON + 1)]
    arrival = next((t for t, s in enumerate(strikes, 1) if s is not None), None)
    if arrival is None:
        return none_row
    first = strikes[arrival - 1]
    if first.expected <= 0:
        return PursuerForecast(body.id, boat['id'], weapon_range, arrival, 0.0,
                               None, None, None)
    turns = dm.simulate_sink(target.hp, [[dm.Attack(body, s)] if s and s.expected > 0 else []
                                         for s in strikes])
    return PursuerForecast(body.id, boat['id'], weapon_range, arrival, first.expected,
                           dm.percentile(turns, 10), dm.percentile(turns, 50),
                           dm.percentile(turns, 90))


def chapter_forecast(chapter):
    """Every (declared pursuer body x rescue boat) forecast for one chapter. [] on a chapter
    with no `rescue_boats:` or no `rescue_pursuers:` -- there is no clock to forecast."""
    boats = chapter.get('rescue_boats') or []
    pursuers = {p['id'] for p in chapter.get('rescue_pursuers') or []}
    if not boats or not pursuers:
        return []
    board = hull_board(chapter)
    return [pursuer_forecast(board, body, boat)
            for body in board.bodies if body.id in pursuers for boat in boats]


def main(argv):
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('chapter', help='chapter id or prefix, e.g. ch06')
    args = ap.parse_args(argv)

    rows = chapter_forecast(pp.load_chapter(args.chapter))
    if not rows:
        print('%s: no rescue_boats/rescue_pursuers declared' % args.chapter)
        return
    for row in rows:
        if row.arrival_turn is None:
            print('%-22s -> %-10s never reaches a firing cell (weapon range %d)'
                  % (row.enemy_id, row.boat_id, row.weapon_range))
            continue
        print('%-22s -> %-10s arrives turn %-3d %.2f dmg/phase  sinks turn %s-%s (median %s)'
              % (row.enemy_id, row.boat_id, row.arrival_turn, row.damage_per_phase,
                 row.sink_low, row.sink_high, row.sink_expected))


if __name__ == '__main__':
    main(sys.argv[1:])
