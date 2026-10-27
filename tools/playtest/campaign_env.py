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

--from N resumes at chapter index N's start as an earlier run of the same --id saved it
(references/sim/<game>/<rom-hash>/states/<id>/N.ss), so a fault in a late chapter is studied
without replaying the chapters before it. It needs --id: the default id names no earlier run.
"""
import argparse
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))

import campaign_chapters  # noqa: E402
import difficulty  # noqa: E402
import inject.cast  # noqa: E402
import inject.decomp  # noqa: E402
import inject.hosts  # noqa: E402
import team_groups  # noqa: E402

VANILLA_LAST = ('CHAPTER_E_21X', 'CHAPTER_I_21X')


def _chapter_enum():
    return inject.decomp.enum_values(
        inject.decomp.vanilla_decomp_text('include/constants/chapters.h'), 'CHAPTER_')


def vanilla_index(ref):
    """The vanilla chapter index of a VANILLA_CHAIN entry: 'FE8 Prologue' -> CHAPTER_L_PROLOGUE,
    'FE8 ChK' -> CHAPTER_L_K (the routes share Prologue to Ch8)."""
    tail = ref.split(' ', 1)[1]
    name = 'CHAPTER_L_PROLOGUE' if tail == 'Prologue' else 'CHAPTER_L_' + tail[2:]
    return _chapter_enum()[name]


def vanilla_env(route=1):
    enum = _chapter_enum()
    return dict(team_groups.env(), last=[enum[n] for n in VANILLA_LAST], route=route)


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
        twin = vanilla_index(difficulty.VANILLA_CHAIN[number])
        path = os.path.join(store, '%d.json' % twin)
        if not os.path.exists(path):
            raise FileNotFoundError('%s: no record of the twin (vanilla chapter %d) for our chapter '
                                    '%d -- run the vanilla campaign first' % (path, twin, number))
        with open(path) as f:
            shops[str(host)] = json.load(f)['shops']
    env = dict(team_groups.env(), last=[hosts[max(hosts)]], shops=shops)
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
