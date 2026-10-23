#!/usr/bin/env python3
"""What each side picks up, chapter by chapter, and what its units carry (#510 step 8, ADR 0365).

A pickup is an item, the VEHICLE that hands it out, and the chapter it comes in: chapter
numbers on our side, the position in `difficulty.VANILLA_CHAIN` on the twin's (the Prologue is
0, Ch5 is 5). The parity read grades the HAPPY path, a careful player taking everything, and
prints the GUARANTEED path beside it: only what no player can miss. The two sides are read by
the same rules, from the readers the economy report already uses (`chapter_economy`,
`twin_event_payload`, `vanilla_drops`), so the kit and the economy cannot disagree about
what a chapter hands out.

Not here, by decision (ADR 0365): healing, durability, the arena, and stat boosters. Steals
are not a vehicle at all: FE8 lets a thief take only plain items (`IsItemStealable`,
bmitem.c), so a steal never changes what a unit fights with.
"""
import re
from dataclasses import dataclass

import difficulty
import inject.decomp

GUARANTEED = frozenset({'join', 'scene', 'interlude'})

# A vanilla node's chapter, read by NAME: CHAPTER_L_5 is Ch5 although its value is 6 (Ch5x
# sits before it). Off the Eirika chain's shared stretch, a node is past what we compare.
_CHAIN_ROW = re.compile(r'CHAPTER_L_(PROLOGUE|\d+)$')


@dataclass(frozen=True)
class Pickup:
    item: str                   # ITEM_ enum
    vehicle: str
    chapter: int
    to: tuple = ()              # named recipients (CHARACTER_*); empty = whoever takes it
    projected: bool = False     # ours, borrowed from the twin until our data exists


def is_weapon(p):
    return p.item in difficulty.ITEM_TO_WEAPON


def _shop_items(sym):
    return difficulty._shoplist_items(
        inject.decomp.vanilla_decomp_text('src/events_shoplist.c'), sym)


def our_pickups(campaign):
    """Every pickup our WRITTEN chapters hand out. A `status: planned` chapter does not exist
    for the difficulty math (ADR 0363). Every gift `chapter_economy` lists is player-earned (a
    village, a boat talk, a green ally kept alive, a save-them-all bonus), so it is `village`."""
    import campaign_chapters
    out = []
    for chap in campaign_chapters.load_all(campaign):
        if chap.get('status') == 'planned':
            continue
        n = int(chap['chapter_number'])
        econ = difficulty.chapter_economy(chap)
        for vehicle, ids in (('village', econ['gifts']), ('chest', econ['chests']),
                             ('drop', econ['drops'])):
            out += [Pickup(inject.decomp.fe_item_enum({'id': i}), vehicle, n) for i in ids]
        for sym in econ['shops']:
            out += [Pickup(it, 'shop', n) for it in _shop_items(sym)]
    return out + _our_worldmap_pickups(campaign)


def _our_world_map(campaign):
    import campaign_chapters
    return campaign_chapters.campaign_yaml(campaign).get('world_map') or []


def _our_worldmap_pickups(campaign):
    """Our towns' stock from the chapter after they open. Until any town carries a `stock:`
    list, the world map is the twin's (ADR 0363's rule: what is not built yet is its twin's),
    marked `projected` so a report can say so."""
    nodes = _our_world_map(campaign)
    if not any(node.get('stock') for node in nodes):
        return [Pickup(p.item, p.vehicle, p.chapter, projected=True)
                for p in _twin_worldmap_pickups()]
    out = []
    for node in nodes:
        after = node.get('unlocks_after')
        n = int(after[2:]) if after else 0
        out += [Pickup(inject.decomp.fe_item_enum({'id': i}), 'worldmap_shop', n)
                for i in node.get('stock') or ()]
    return out


def _twin_worldmap_pickups():
    """Each Eirika-route node's Armory, Vendor and Secret Shop stock
    (src/worldmap_node_data.c, worldmap_shop_data.c), from the chapter its map is played."""
    nodes = inject.decomp.vanilla_decomp_text('src/worldmap_node_data.c')
    stock = inject.decomp.vanilla_decomp_text('src/worldmap_shop_data.c')
    out = []
    for body in re.split(r'\[NODE_\w+\]\s*=', nodes)[1:]:
        ch = re.search(r'\.chapteridx_eirika\s*=\s*(\w+)', body)
        m = ch and _CHAIN_ROW.match(ch.group(1))
        if not m:
            continue
        n = 0 if m.group(1) == 'PROLOGUE' else int(m.group(1))
        for sym in re.findall(r'\.(?:armory|vendor|secretShop)\s*=\s*(\w+)', body):
            out += [Pickup(it, 'worldmap_shop', n) for it in difficulty._shoplist_items(stock, sym)]
    return out


def twin_pickups():
    """Every pickup the twin's chain hands out, by the same vehicles as ours."""
    out = []
    for n, ref in enumerate(difficulty.VANILLA_CHAIN):
        t = difficulty.twin_event_payload(difficulty.PARITY_REFERENCE_STEM[ref])
        village = list(t['village_gifts'])
        for item, to in zip(t['gifts'], t['gift_to']):
            if item in village:
                village.remove(item)
                out.append(Pickup(item, 'village', n))
            else:
                out.append(Pickup(item, 'scene', n, _named(to)))
        out += [Pickup(it, 'interlude', n, _named(to))
                for it, to in zip(t['interlude_gifts'], t['interlude_gift_to'])]
        out += [Pickup(it, 'chest', n) for it in t['chests']]
        out += [Pickup(it, 'drop', n) for it, _gold in difficulty.vanilla_drops(ref) or ()]
        out += [Pickup(it, 'shop', n) for _sym, items in t['shops'] for it in items]
    return out + _twin_worldmap_pickups()


def _named(to):
    return tuple(t for t in to if t.startswith('CHARACTER_'))
