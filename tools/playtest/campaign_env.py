#!/usr/bin/env python3
"""PT_CAMPAIGN for the `campaign` scenario (#510 step 9 PR E): where a campaign ends, the team
caps (team_groups.py), which route or lead it plays, and, for ours, which world map shops are
open before each chapter.

    python3 tools/playtest/campaign_env.py vanilla --route 1
    python3 tools/playtest/campaign_env.py ours --store references/sim/vanilla/<hash>/states/<id> \
        [--lord <pc id>]
    ... [--id <campaign id> --from <chapter index>]

The route (vanilla's Ch8 split, 1 = Eirika, 2 = Ephraim) and the lead (ours, ADR 0062's ch01
menu) are campaign SETTINGS, never drawn (#510 plan comment, "Lords"). A lead is passed as its
row in the menu, the classed cast on the field at ch01 in PORTRAIT_MAP order -- the list the
build makes the menu from; no --lord takes the highlighted lead.

Vanilla ends after either route's last chapter (constants/chapters.h CHAPTER_E_21X /
CHAPTER_I_21X); its world map is its own. Ours ends after its last WRITTEN chapter (ADR 0363:
a `status: planned` chapter is never played) and has no world map yet, so before each chapter
it gets the twin's: the nodes the vanilla campaign found open at the twin's start, read from
that campaign's `<chapter>.json` records (Nicolas, 2026-10-27). The twin of our chapter N is
difficulty.VANILLA_CHAIN[N], the chain the kit model already reads (ADR 0365).

Each env also carries `claims`: {chapter index: [claim]}, every Strategy claim of that chapter
(ours: the chapter YAML's `strategy_claims`; vanilla: `twin_strategy.yaml`, the route's keys)
RESOLVED to game ids for the bot, which maps no name (bot.lua, Claims): a unit to its
character id, a class to its id and every reskin built on it (a reskin plays as its base, ADR
0362), one of our enemy ids to its class's, a terrain name to its TERRAIN_ id. A name that
resolves to nothing raises. A claim whose fields need a model the runner has not got
(`reinforcements`' arrival turns) goes as kind `unresolved`, so the run reports it unplayed.

--from N resumes at chapter index N's start as an earlier run of the same --id saved it
(references/sim/<game>/<rom-hash>/states/<id>/N.ss), so a fault in a late chapter is studied
without replaying the chapters before it. It needs --id: the default id names no earlier run.
"""
import argparse
import functools
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))

import campaign_chapters  # noqa: E402
import strategy  # noqa: E402
from inject import class_ids, reskins  # noqa: E402
from inject.scene_actors import cast_pids, character_pid  # noqa: E402
import difficulty  # noqa: E402
import inject.cast  # noqa: E402
import inject.chapter_settings  # noqa: E402
import inject.decomp  # noqa: E402
import inject.hosts  # noqa: E402
import inject.villages  # noqa: E402
import team_groups  # noqa: E402

VANILLA_LAST = ('CHAPTER_E_21X', 'CHAPTER_I_21X')


def _chapter_enum():
    return inject.decomp.enum_values(
        inject.decomp.vanilla_decomp_text('include/constants/chapters.h'), 'CHAPTER_')


def twin_index(ref, route):
    """The vanilla chapter a twin_strategy key names on `route` (1 Eirika, 2 Ephraim), or None
    when that key belongs to the other route. Up to Ch8 the routes share chapters
    (inject.chapter_settings.twin_rows, the one owner); a plain `FE8 ChN` with an `FE8 ChN
    Ephraim` twin is Eirika's own, one without is shared; `Final` / `Final 2` are Ch21 / Ch21x."""
    shared = inject.chapter_settings.twin_rows()
    if ref in shared:
        return shared[ref]
    enum = _chapter_enum()
    tail = ref.split(' ', 1)[1]
    side = 'E' if route == 1 else 'I'
    if tail.endswith(' Ephraim'):
        return enum['CHAPTER_I_' + tail[2:-len(' Ephraim')]] if route == 2 else None
    if tail in ('Final', 'Final 2'):
        return enum['CHAPTER_%s_21%s' % (side, 'X' if tail == 'Final 2' else '')]
    if route == 2 and ref + ' Ephraim' in strategy._twin_file():
        return None
    return enum['CHAPTER_%s_%s' % (side, tail[2:])]


def _names(v):
    return list(v) if isinstance(v, list) else [v]


@functools.lru_cache(maxsize=None)
def _terrains():
    return inject.decomp.enum_values(
        inject.decomp.vanilla_decomp_text('include/constants/terrains.h'), 'TERRAIN_')


def reskin_class_id(rk):
    """The class id a declared enemy reskin (campaign.yaml) takes on the board."""
    if rk.get('slot_id') is not None:
        return int(str(rk['slot_id']), 0)
    return class_ids.vanilla_class_values()[rk['slot']]


def class_ids_of(token, game, campaign=campaign_chapters.CAMPAIGN):
    """A class token's ids on the board: the vanilla class, and for ours every reskin whose base
    it is. None when `token` is no vanilla class."""
    values = class_ids.vanilla_class_values()
    enum = class_ids.vanilla_class_enum(token)
    if enum not in values:
        return None
    out = {values[enum]}
    if game == 'ours':
        for rk in reskins.enemy_class_reskins(campaign):
            if rk['base'] == enum:
                out.add(reskin_class_id(rk))
    return sorted(out)


def _unit_id(name, game, campaign):
    if game == 'ours':
        pid = cast_pids().get(name)
    else:
        pid = character_pid('CHARACTER_' + name.upper().replace('-', '_'))
    if pid is None:
        raise ValueError('claim unit %r names no %s character' % (name, game))
    return pid


def _vs(v, game, chap, campaign):
    if v in ('boss', 'all'):
        return v
    out = set()
    for name in _names(v):
        ids = class_ids_of(name, game, campaign)
        if ids is None and chap is not None:
            # one of our enemy ids: the class it is written with (deploy_class only dresses it)
            for e in chap.get('enemy_units') or []:
                if e.get('id') == name:
                    ids = class_ids_of(e['class'], game, campaign)
        if ids is None:
            raise ValueError('claim vs %r is no class%s' % (
                name, ' and no enemy of %s' % chap.get('id') if chap else ''))
        out.update(ids)
    return sorted(out)


def resolve(claim, key, game, chap=None, campaign=campaign_chapters.CAMPAIGN, ref=None):
    """One claim as bot.lua takes it (its Claims section): id `key`, game ids for every name.
    `chap` is our chapter (ours), `ref` the twin's parity reference (vanilla): a reinforcements
    claim resolves to the waves that chapter loads (difficulty.arrival_waves), and goes
    `unresolved` where they are not read (no chapter, or an uncurated twin)."""
    kind = claim['kind']
    out = {'id': key, 'kind': kind}
    if kind == 'reinforcements':
        where = chap if game == 'ours' else ref
        if where is None:
            return {'id': key, 'kind': 'unresolved', 'was': kind}
        waves = difficulty.arrival_waves(where, game)
        if waves is None:
            return {'id': key, 'kind': 'unresolved', 'was': kind}
        return dict(out, turns=[w['turn'] for w in waves], waves=waves)
    if kind == 'reward':
        enum = inject.decomp.ITEM_ENUM.get(claim['item'])
        ids = {e: i for i, e in difficulty._item_id_to_enum().items()}
        if enum not in ids:
            raise ValueError('claim reward item %r names no item' % claim['item'])
        return dict(out, item=ids[enum], needs=claim['needs'])
    for field in ('unit', 'by'):
        if field in claim:
            out[field] = [_unit_id(n, game, campaign) for n in _names(claim[field])]
    if 'vs' in claim:
        out['vs'] = _vs(claim['vs'], game, chap, campaign)
    if 'tile' in claim:
        out['tile'] = _terrains()['TERRAIN_' + claim['tile'].upper()]
    if 'topic' in claim:
        out['topic'] = claim['topic']
    return out


def twin_claims_env(route):
    """{vanilla chapter index (str): [resolved claim]} for every twin key on `route`."""
    out = {}
    for ref in strategy._twin_file():
        index = twin_index(ref, route)
        if index is not None:
            out[str(index)] = [resolve(c, '%s#%d' % (ref, i), 'vanilla', ref=ref)
                               for i, c in enumerate(strategy.twin_claims(ref))]
    return out


def village_gifts(macro='Village'):
    """What every vanilla village (or House) gives (inject.villages.village_rewards over
    src/events/ at HEAD): {items: [item ids], gold: [amounts]}, a House that only talks as gold
    0. The planner's worth of a village or House whose gift a new player cannot know is their
    mean, each item at the game's own GetItemCost (#510)."""
    scripts = inject.decomp.vanilla_event_scripts()
    out = {'items': [], 'gold': []}
    for path, text in sorted(inject.decomp.vanilla_event_files().items()):
        if path.endswith('-eventinfo.h'):
            # a House that only talks gives nothing (0); a village's gift the parse cannot
            # read is unknown, not nothing, and stays out of the mean
            for _x, _y, kind, v in inject.villages.village_rewards(
                    text, scripts, macro, nothing=macro == 'House'):
                out['items' if kind == 'item' else 'gold'].append(v)
    return out


def vanilla_env(route=1):
    enum = _chapter_enum()
    return dict(team_groups.env(), last=[enum[n] for n in VANILLA_LAST], route=route,
                claims=twin_claims_env(route), village_gifts=village_gifts(),
                house_gifts=village_gifts('House'))


def lead_row(uid, campaign=campaign_chapters.CAMPAIGN):
    """The lead menu's row for `uid`: its place in the cast on the field at ch01 (chapter 1,
    where the menu is), as gen_symbols counts LORD_CANDIDATES."""
    lords = [u for u, *_ in inject.cast._classed_cast(campaign, available_at=1)[0]]
    if uid not in lords:
        raise ValueError('%s is not a lead candidate (the menu offers %s)' % (uid, ', '.join(lords)))
    return lords.index(uid)


def ours_env(store, lord=None, campaign=campaign_chapters.CAMPAIGN):
    """`store`: a vanilla campaign's states directory, holding `<chapter>.json` per chapter
    start. Raises when a twin's record is missing: a run without its shops would be a different
    campaign, not a smaller one."""
    written = {int(c['chapter_number']) for c in campaign_chapters.load_all(campaign)
               if c.get('status') != 'planned'}
    hosts = {h.number: h.host_index for h in inject.hosts.hosted_chapters() if h.number in written}
    shops = {}
    for number, host in sorted(hosts.items()):
        twin = inject.chapter_settings.twin_rows()[difficulty.VANILLA_CHAIN[number]]
        path = os.path.join(store, '%d.json' % twin)
        if not os.path.exists(path):
            raise FileNotFoundError('%s: no record of the twin (vanilla chapter %d) for our chapter '
                                    '%d -- run the vanilla campaign first' % (path, twin, number))
        with open(path) as f:
            shops[str(host)] = json.load(f)['shops']
    claims = {}
    for chap in campaign_chapters.load_all(campaign):
        number = int(chap['chapter_number'])
        if number in hosts:
            claims[str(hosts[number])] = [
                resolve(c, '%s#%d' % (chap['id'], i), 'ours', chap, campaign)
                for i, c in enumerate(strategy.our_claims(chap))]
    env = dict(team_groups.env(), last=[hosts[max(hosts)]], shops=shops, claims=claims,
               village_gifts=village_gifts(), house_gifts=village_gifts('House'))
    if lord is not None:
        env['lord'] = lead_row(lord, campaign)
    return env


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('game', choices=('vanilla', 'ours'))
    ap.add_argument('--store', help="the vanilla campaign's states directory (ours only)")
    ap.add_argument('--id', help='the campaign id (default: <mode>-s<seed>, set by the harness)')
    ap.add_argument('--route', type=int, choices=(1, 2), default=1,
                    help="vanilla: the Ch8 split's route (1 Eirika, 2 Ephraim)")
    ap.add_argument('--lord', help='ours: the lead, a PC id (default: the highlighted lead)')
    ap.add_argument('--from', dest='start', type=int,
                    help='resume at this chapter index, from the start state --id saved')
    args = ap.parse_args(argv)
    if args.start is not None and not args.id:
        ap.error('--from needs --id: the states it resumes from are filed under the campaign id')
    if args.game == 'ours' and not args.store:
        ap.error('ours needs --store: its shops are the vanilla campaign\'s')
    env = vanilla_env(args.route) if args.game == 'vanilla' else ours_env(args.store, args.lord)
    if args.id:
        env['id'] = args.id
    if args.start is not None:
        env['from'] = args.start
    print(json.dumps(env, sort_keys=True))


if __name__ == '__main__':
    main()
