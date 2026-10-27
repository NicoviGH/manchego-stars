#!/usr/bin/env python3
"""PT_CAMPAIGN for the `campaign` scenario (#510 step 9 PR E): where a campaign ends and, for
ours, which world map shops are open before each chapter.

    python3 tools/playtest/campaign_env.py vanilla
    python3 tools/playtest/campaign_env.py ours --store references/sim/vanilla/<hash>/states/<id>

Vanilla ends after either route's last chapter (constants/chapters.h CHAPTER_E_21X /
CHAPTER_I_21X); its world map is its own. Ours ends after its last WRITTEN chapter (ADR 0363:
a `status: planned` chapter is never played) and has no world map yet, so before each chapter
it gets the twin's: the nodes the vanilla campaign found open at the twin's start, read from
that campaign's `<chapter>.json` records (Nicolas, 2026-10-27). The twin of our chapter N is
difficulty.VANILLA_CHAIN[N], the chain the kit model already reads (ADR 0365).
"""
import argparse
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))

import campaign_chapters  # noqa: E402
import difficulty  # noqa: E402
import inject.decomp  # noqa: E402
import inject.hosts  # noqa: E402

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


def vanilla_env():
    enum = _chapter_enum()
    return {'last': [enum[n] for n in VANILLA_LAST]}


def ours_env(store, campaign=campaign_chapters.CAMPAIGN):
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
    return {'last': [hosts[max(hosts)]], 'shops': shops}


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('game', choices=('vanilla', 'ours'))
    ap.add_argument('--store', help="the vanilla campaign's states directory (ours only)")
    ap.add_argument('--id', help='the campaign id (default: <mode>-s<seed>, set by the harness)')
    args = ap.parse_args(argv)
    if args.game == 'ours' and not args.store:
        ap.error('ours needs --store: its shops are the vanilla campaign\'s')
    env = vanilla_env() if args.game == 'vanilla' else ours_env(args.store)
    if args.id:
        env['id'] = args.id
    print(json.dumps(env, sort_keys=True))


if __name__ == '__main__':
    main()
