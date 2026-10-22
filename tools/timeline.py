#!/usr/bin/env python3
"""Instrument v2, layer 2 (#430 step 2b): WHEN a chapter's force reaches the party, ours and
the vanilla twin's, turn by turn.

Layer 1 (`difficulty.chapter_matchup`) says how hard each force is against the party that
meets it. This says when they arrive, and `engagements` says which of them the party meets
together: the heaviest engagement is layer 1's threat (#510 step 7, ADR 0364). Both sides are
read on `danger_map.Board`: ours from the chapter YAML, the twin's from the decomp (its
layout through `gChapterDataAssetTable`, its red UnitDefinitions with their AI bytes and
REDA end tiles, and the turns its eventscript loads each wave).

  * THE FRONT is where the party deploys: our `deployment.deploy_slots` (the `player_units`
    tiles for a fixed-roster chapter), and the twin's `playerUnitsInNormal` table.
  * FIRST CONTACT is the first enemy phase a body can stand within weapon range of a front
    tile, with the party holding the front. A statue that starts out of range never makes
    contact; neither does a striker that cannot step into range.
  * PEAK THREAT is the expected damage on the front's most exposed tile that phase, read
    against the field's least durable member (`difficulty.durability`).

HONEST LIMITS: enemies path through each other (FE8 lets a red pass a red), and the party
holds its deploy tiles and never advances; it blocks them and fills them (`front_contacts`).
A chapter the party crosses meets its force earlier than this reads; the comparison holds
because the twin is read the same way.

    python3 tools/timeline.py ch04
"""
import argparse
import collections
import functools
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import danger_map as dm                                              # noqa: E402
import difficulty as dif                                             # noqa: E402
import fe_combat as fc                                               # noqa: E402
import map_placement_preview as pp                                   # noqa: E402

HORIZON = 8                 # enemy phases read; FE8's early chapters are won in about this


# ── Our board's front ─────────────────────────────────────────────────────────────

def our_front(chapter):
    deployment = chapter.get('deployment') or {}
    if deployment.get('deploy_slots'):
        return sorted({tuple(t) for t in deployment['deploy_slots']})
    return sorted({tuple(pu['position']) for pu in chapter.get('player_units') or ()
                   if pu.get('position')})


# ── The timeline ──────────────────────────────────────────────────────────────────

def striking(front, arms):
    """The tiles from which one of `arms` reaches a `front` tile (`danger_map.in_range`'s rule:
    Manhattan distance inside the weapon's range, no line of sight)."""
    return _striking(frozenset(tuple(t) for t in front),
                     frozenset(arm.weapon.rng for arm in arms))


@functools.lru_cache(maxsize=None)
def _striking(front, ranges):
    out = set()
    for x, y in front:
        for lo, hi in ranges:
            for d in range(max(lo, 1), hi + 1):
                for dx in range(-d, d + 1):
                    out.update({(x + dx, y + d - abs(dx)), (x + dx, y - d + abs(dx))})
    return frozenset(out)


def first_contact(board, body, front, horizon=HORIZON):
    """The first enemy phase `body` can strike a front tile from where it can stand, or None
    within `horizon`. Once its move budget covers its whole walk, it can reach no further, so
    a body that has not struck by then never will."""
    targets = striking(front, body.arms)
    walked = dm._moves_like(body) == 'pursuer' and max(board._walk(body).values(), default=0)
    for phase in range(body.arrives, horizon + 1):
        if board.stands(body, phase) & targets:
            return phase
        if not walked or board.budget(body, phase) >= walked:
            return None
    return None


def ai_priority(body):
    """The order FE8's AI moves a unit in: `SortAiUnitList` (cp_order.c) sorts ascending, and
    stably, on `GetUnitAiPriority`: Mov, plus 20 for a melee unit, 40 for one that can strike
    at range, 87 for one with no weapon. The leader's +87 and the shared leader term are left
    out: a chapter's leader is its boss, which waits rather than charges."""
    if not body.arms:
        return body.mov + 87
    return body.mov + (40 if any(a.weapon.rng[1] > 1 for a in body.arms) else 20)


def front_contacts(board, front, horizon=HORIZON):
    """{index into `board.bodies`: the enemy phase it first strikes the front, or None}.

    `first_contact` is when a body COULD stand in range; this is when it gets to. Each striker
    needs a firing tile of its own that the party is not standing on, and keeps it once it has
    struck (it stays in the fight). The AI moves units in `ai_priority` order and each takes
    the free tile nearest its own walk, not the one that leaves the most for the rest, so a
    body that finds every tile in its reach taken waits for the next phase. Read against `ch04waves` (#510 step 7): without it, four of six Mauthe Doogs that
    arrive beside the party's corner strike on phase 2, not all six."""
    front = {tuple(t) for t in front}
    first = {k: first_contact(board, b, front, horizon) for k, b in enumerate(board.bodies)}
    out = {k: None for k in first}
    held = set()
    for phase in range(1, horizon + 1):
        for k in sorted((k for k, p in first.items()
                         if p is not None and p <= phase and out[k] is None),
                        key=lambda k: (ai_priority(board.bodies[k]), k)):
            b = board.bodies[k]
            walk = board._walk(b)
            cells = [c for c in board.stands(b, phase) & striking(front, b.arms)
                     if c not in front and c not in held]
            if cells:
                held.add(min(cells, key=lambda c: (walk.get(c, 0), c)))
                out[k] = phase
    return out


def read(board, front, defender, horizon=HORIZON):
    """{'contact': {body: phase or None}, 'statues': n, 'waves': {turn: bodies},
    'peak': [expected damage on the most exposed front tile, per phase 1..horizon]}."""
    struck = front_contacts(board, front, horizon)
    contact = {(b.id, b.index): struck[k] for k, b in enumerate(board.bodies)}
    waves = collections.Counter(b.arrives for b in board.bodies if b.arrives > 1)
    statues = sum(1 for b in board.bodies if dm._moves_like(b) == 'statue')
    peak = [max((dm.expected_damage(dm.attacks_on(board, t, defender, phase)) for t in front),
                default=0.0) for phase in range(1, horizon + 1)]
    return {'contact': contact, 'statues': statues, 'waves': dict(sorted(waves.items())),
            'peak': peak, 'bodies': len(board.bodies)}


# ── Engagements (#510 step 7) ─────────────────────────────────────────────────────

Engagement = collections.namedtuple('Engagement', 'kind members phase tile')


def engagements(board, front, defender, reach):
    """The sets of enemies the party faces together, as frozensets of indices into
    `board.bodies` (ADR 0364).

      * A WAVE is every pursuer that first strikes the deploy `front` on one enemy phase
        (`front_contacts`, read to `danger_map.ENGAGE_HORIZON`). It comes to the party
        wherever the party stands, so the phase only says which wave it rides in.
      * A POCKET is one waiting enemy X (a striker or statue, or a pursuer that never reaches
        the front) and the waiting enemies that can hit the tile the party pulls it from. The
        party pulls from the CHEAPEST tile: among the free tiles at a distance in `reach` from
        X, the one where those enemies carry the least expected damage on `defender`. A careful
        player reading FE's danger zone (Nicolas, 2026-10-22): a careless attempt ends in a
        restart, so the run that clears the chapter is the careful one.

    Pockets are read once every waiting body has arrived. A wave and a pocket are never merged,
    and a body may sit in several pockets. Unarmed, inert and own-errand bodies are in none."""
    waves = collections.defaultdict(set)
    waiting = []
    struck = front_contacts(board, front, dm.ENGAGE_HORIZON)
    for k, b in enumerate(board.bodies):
        if not b.arms or b.action == dm.INERT_ACTION or b.shape == 'own-errand':
            continue
        if dm._moves_like(b) == 'pursuer':
            phase = struck[k]
            if phase is not None:
                waves[phase].add(k)
                continue
        waiting.append(k)
    out = [Engagement('wave', frozenset(m), p, None) for p, m in sorted(waves.items())]
    if not waiting:
        return out
    phase = max(board.bodies[k].arrives for k in waiting)
    # Only waiting bodies are in a pocket, so their danger is read on a board of their own.
    pockets = dm.Board(board.chapter, terrain=board.terrain,
                       fielded=[board.bodies[k] for k in waiting])
    index = {id(b): k for k, b in zip(waiting, pockets.bodies)}
    taken = {b.source for b in pockets.bodies}
    rows, cols = len(board.terrain), len(board.terrain[0])
    for k in waiting:
        x0, y0 = board.bodies[k].source
        best = None
        for d in sorted(reach):
            for dx in range(-d, d + 1):
                for dy in {d - abs(dx), abs(dx) - d}:
                    x, y = x0 + dx, y0 + dy
                    if (not (0 <= x < cols and 0 <= y < rows) or (x, y) in taken
                            or pp.FOOT_COST.get(board.terrain[y][x]) is None):
                        continue
                    hits = dm.attacks_on(pockets, (x, y), defender, phase)
                    cost = dm.expected_damage(hits)
                    if best is None or cost < best[0]:
                        best = (cost, (x, y), {index[id(a.body)] for a in hits})
        members, tile = ({k}, None) if best is None else (best[2] | {k}, best[1])
        out.append(Engagement('pocket', frozenset(members), phase, tile))
    return out


def _softest(field, force):
    medians = [dif._median_combatant(c) for c in field.values()]
    return min(medians, key=lambda u: dif.durability(u, force))


def _reach(field):
    """The distances the field's carried weapons strike from: where it can pull an enemy."""
    return frozenset(d for careers in field.values() for a in fc.arms(careers[0])
                     for d in range(a.weapon.rng[0], a.weapon.rng[1] + 1)) or frozenset({1})


def boards(chapter, fields):
    """{'ours', 'vanilla'}: (Board, front) for each side, on the parity read's own bodies
    (`arriving_fields`), so a body on the board is the force's body at the same index. Hard-only
    waves ride on both sides, as `difficulty` folds them. None when our map is not compiled."""
    try:
        terrain = pp.terrain_grid(chapter)
    except pp.MapNotCompiled:
        return None
    front = our_front(chapter)
    return {'ours': (dm.Board(chapter, terrain=terrain, fielded=fields['our_bodies'],
                              blocked=front), front),
            'vanilla': twin_board(chapter['parity_reference'], fields['van_bodies'])}


def twin_board(parity_ref, bodies):
    """(Board, front) for the twin's force `bodies` on its own map and deploy table. The party
    holds the front, so no red walks through it or stands on it."""
    front = dif.vanilla_front(parity_ref)
    return (dm.Board(None, terrain=dif.vanilla_terrain(parity_ref), fielded=bodies,
                     blocked=front), front)


def engage(board_front, force):
    """`party_matchup`'s `engage`: for the field a party deploys ({unit: [Combatant]}), the
    engagements it meets on one board, {'engagements', 'swung'}. The pull is read against the
    field's least durable member and the distances its weapons strike from; a wave's members
    are the bodies that swing before the party fights them."""
    board, front = board_front

    def read(field):
        found = engagements(board, front, _softest(field, force), _reach(field))
        return {'engagements': found,
                'swung': frozenset(k for g in found if g.kind == 'wave' for k in g.members)}
    return read


def matchup_engagements(chapter, fields):
    """{'ours', 'vanilla', 'cross'}: the `engage` of each of `chapter_matchup`'s three reads,
    or None for all three when our map is not compiled, so the two sides are never read two
    different ways."""
    sides = boards(chapter, fields)
    if sides is None:
        return {'ours': None, 'vanilla': None, 'cross': None}
    ours = [u for u, _t in fields['our_force']]
    van = [u for u, _t in fields['van_force']]
    return {'ours': engage(sides['ours'], ours), 'vanilla': engage(sides['vanilla'], van),
            'cross': engage(sides['vanilla'], van)}


def chapter_timeline(chapter, campaign, mode=None, horizon=HORIZON):
    """Both sides' `read`, or None where layer 1 has no parties to field (a twin off
    VANILLA_CHAIN) or our map is not compiled."""
    fields = dif.arriving_fields(chapter, campaign, mode)
    if fields is None:
        return None
    sides = boards(chapter, fields)
    if sides is None:
        return None
    ours_force = [u for u, _t in fields['our_force']]
    van_force = [u for u, _t in fields['van_force']]
    return {
        'ours': read(*sides['ours'],
                     _softest(dif.fielded_careers(fields['our_party'], ours_force,
                                                  fields['cap']), ours_force), horizon),
        'vanilla': read(*sides['vanilla'],
                        _softest(dif.fielded_careers(fields['van_party'], van_force,
                                                     fields['cap'], fields['van_forced']),
                                 van_force), horizon),
        'horizon': horizon}


def _per_phase(side, horizon):
    met = collections.Counter(p for p in side['contact'].values() if p is not None)
    return [met.get(p, 0) for p in range(1, horizon + 1)]


def print_timeline(t, reference):
    h = t['horizon']
    print('\n-- TIMELINE (instrument v2 layer 2, #430: the party holds its deploy front) '
          + '-' * 4)
    print('  %-8s %5s %7s %5s  %s' % ('', 'bodies', 'statues', 'never',
                                       'reinforcement waves (turn: bodies)'))
    for tag, side in (('ours', t['ours']), ('vanilla', t['vanilla'])):
        never = sum(1 for p in side['contact'].values() if p is None)
        waves = ', '.join('%d: %d' % kv for kv in side['waves'].items()) or 'none'
        print('  %-8s %5d %7d %5d  %s' % (tag, side['bodies'], side['statues'], never, waves))
    print('  enemy phase        ' + ''.join('%6d' % p for p in range(1, h + 1)))
    for tag, side in (('ours', t['ours']), ('vanilla', t['vanilla'])):
        print('  %-8s contacts ' % tag + ''.join('%6d' % n for n in _per_phase(side, h)))
        print('  %-8s peak dmg ' % tag + ''.join('%6.1f' % d for d in side['peak']))
    print('  (contacts: bodies first in range of the front that phase; peak dmg: expected damage'
          '\n   on the most exposed front tile, against the field\'s least durable unit; vs %s)'
          % reference)


def main(argv):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument('chapter', help='chapter id prefix, e.g. ch04')
    ap.add_argument('--campaign', default='rime-of-the-frostmaiden')
    ap.add_argument('--mode', choices=dif.MODES)
    ap.add_argument('--horizon', type=int, default=HORIZON)
    args = ap.parse_args(argv)
    chapter = pp.load_chapter(args.chapter)
    t = chapter_timeline(chapter, args.campaign, args.mode, args.horizon)
    if t is None:
        print('no timeline: %s has no simulated twin party or no compiled map'
              % chapter.get('id'))
        return 1
    print_timeline(t, chapter.get('parity_reference'))
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
