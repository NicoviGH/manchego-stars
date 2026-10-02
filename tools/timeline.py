#!/usr/bin/env python3
"""Instrument v2, layer 2 (#430 step 2b): WHEN a chapter's force reaches the party, ours and
the vanilla twin's, turn by turn.

Layer 1 (`difficulty.chapter_matchup`) says how hard each force is against the party that
meets it, as if every enemy attacked on turn 1. This says when they arrive. Both sides are
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

HONEST LIMITS are `danger_map`'s: enemies path through each other, the party does not
block, and the party never advances. A chapter the party crosses meets its force earlier
than this reads; the comparison holds because the twin is read the same way.

    python3 tools/timeline.py ch04
"""
import argparse
import collections
import dataclasses
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import chapter_status as cs                                          # noqa: E402
import danger_map as dm                                              # noqa: E402
import difficulty as dif                                             # noqa: E402
import fe_combat as fc                                               # noqa: E402
import inject.decomp                                                 # noqa: E402
import map_placement_preview as pp                                   # noqa: E402

HORIZON = 8                 # enemy phases read; FE8's early chapters are won in about this


# ── The twin's board ──────────────────────────────────────────────────────────────

def vanilla_bodies(parity_ref, mode=None):
    """The twin's red force as `danger_map.Body`s: each unit at the end of its REDA walk,
    arriving on the turn its eventscript loads its array, armed with every attacking item it
    carries. Named units carry their personal line, as `difficulty.vanilla_enemies` reads
    them."""
    relpath, arrays = dif.PARITY_REFERENCE_UDEFS[parity_ref]
    turns = dif._vanilla_reinforcement_turns(dif.PARITY_REFERENCE_STEM[parity_ref])
    shifts = dif.vanilla_chapter_shifts(parity_ref) if mode else None
    text = inject.decomp.vanilla_decomp_text(relpath)
    out = []
    for array in arrays:
        for i, d in enumerate(dif.vanilla_unit_defs(text, array)):
            if d['allegiance'] != 'FACTION_ID_RED':
                continue
            keys = [dif.ITEM_TO_WEAPON.get(it) or dif.VANILLA_ONLY_ITEM_TO_WEAPON.get(it)
                    for it in d['items']]
            weapons = [fc.W[k] for k in keys if k and fc.W[k].kind != 'staff']
            if not weapons:
                continue
            ch = d['charIndex']
            unit = dif._enemy_from_enum('%s#%d[%s]' % (array, i, ch), d['classIndex'],
                                        d['level'], weapons[0], dif.vanilla_personal_line(ch),
                                        mode=mode, shifts=shifts,
                                        shiftable=dif._takes_difficulty_shift(ch),
                                        base_level=dif._character_base_level(ch))
            table, mov = pp.class_movement(d['classIndex'][len('CLASS_'):].lower())
            out.append(dm.Body(array, i, tuple(d['position']), cs.ai_shape(d['ai']),
                               d['ai'][0], turns.get(array, 1), table, mov,
                               tuple(dataclasses.replace(unit, weapon=w) for w in weapons)))
    return out


def our_front(chapter):
    deployment = chapter.get('deployment') or {}
    if deployment.get('deploy_slots'):
        return sorted({tuple(t) for t in deployment['deploy_slots']})
    return sorted({tuple(pu['position']) for pu in chapter.get('player_units') or ()
                   if pu.get('position')})


# ── The timeline ──────────────────────────────────────────────────────────────────

def first_contact(board, body, front, horizon=HORIZON):
    """The first enemy phase `body` can strike a front tile from where it can stand, or None
    within `horizon`."""
    for phase in range(body.arrives, horizon + 1):
        cells = board.stands(body, phase)
        if any(dm.in_range(arm, c, t) for c in cells for t in front for arm in body.arms):
            return phase
    return None


def read(board, front, defender, horizon=HORIZON):
    """{'contact': {body: phase or None}, 'statues': n, 'waves': {turn: bodies},
    'peak': [expected damage on the most exposed front tile, per phase 1..horizon]}."""
    contact = {(b.id, b.index): first_contact(board, b, front, horizon) for b in board.bodies}
    waves = collections.Counter(b.arrives for b in board.bodies if b.arrives > 1)
    statues = sum(1 for b in board.bodies if dm._moves_like(b) == 'statue')
    peak = [max((dm.expected_damage(dm.attacks_on(board, t, defender, phase)) for t in front),
                default=0.0) for phase in range(1, horizon + 1)]
    return {'contact': contact, 'statues': statues, 'waves': dict(sorted(waves.items())),
            'peak': peak, 'bodies': len(board.bodies)}


def _softest(field, force):
    medians = [dif._median_combatant(c) for c in field.values()]
    return min(medians, key=lambda u: dif.durability(u, force))


def chapter_timeline(chapter, campaign, mode=None, horizon=HORIZON):
    """Both sides' `read`, or None where layer 1 has no parties to field (a twin off
    VANILLA_CHAIN) or our map is not compiled."""
    fields = dif.arriving_fields(chapter, campaign, mode)
    if fields is None:
        return None
    try:
        # Hard-only waves ride on both sides, as `difficulty` folds them: the twin's curated
        # force carries its Hard array unconditionally.
        ours_board = dm.Board(chapter, mode, every_mode=True)
    except pp.MapNotCompiled:
        return None
    ref = chapter['parity_reference']
    van_board = dm.Board(None, terrain=dif.vanilla_terrain(ref),
                         fielded=vanilla_bodies(ref, mode))
    ours_force = [u for u, _t in fields['our_force']]
    van_force = [u for u, _t in fields['van_force']]
    return {
        'ours': read(ours_board, our_front(chapter),
                     _softest(fields['our_field'], ours_force), horizon),
        'vanilla': read(van_board, dif.vanilla_front(ref),
                        _softest(fields['van_field'], van_force), horizon),
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
