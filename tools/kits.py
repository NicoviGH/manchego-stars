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
import functools
import os
import re
from dataclasses import dataclass

import difficulty
import fe_combat
import inject.chapter_settings
import inject.decomp

GUARANTEED = frozenset({'scene', 'interlude'})



@dataclass(frozen=True)
class Pickup:
    item: str                   # ITEM_ enum
    vehicle: str
    chapter: int
    to: tuple = ()              # named recipients (CHARACTER_*); empty = whoever takes it
    projected: bool = False     # ours, borrowed from the twin until our data exists


# FE8's inventory is 5 slots; the model counts weapons only (a careful player leaves the
# vulnerary behind before a sword).
SLOTS = 5


@dataclass(frozen=True)
class Member:
    name: str                   # the careers key
    can_use: object             # ITEM_ enum -> bool, from the side's own rank source
    items: tuple = ()           # the join kit, ITEM_ enums in slot order
    char: str = None            # CHARACTER_*, for a gift with a named recipient


def arsenals(pickups, chapter, party, path):
    """{member name: (Weapon, ...)} for `party` ([Member], join order) entering `chapter` on
    `path` ('happy' or 'guaranteed'). A pickup is in hand from the chapter AFTER it is handed
    out, except a scene gift, which is in hand in its own chapter (the Prologue's opening hands
    Eirika the Rapier she fights it with). A named gift goes to its recipient or to nobody; a shop item to every member who can
    wield it and lacks it; any other weapon to the first such member. The join kit stays
    first, in its order (its first weapon is the one equipped); past SLOTS, the rest that no
    carried weapon beats outright are kept first, by Mt."""
    if path not in ('happy', 'guaranteed'):
        raise ValueError(path)
    held = {m.name: [w for w in map(difficulty.item_weapon, m.items) if w is not None]
            for m in party}
    for p in pickups:
        later = p.chapter > chapter or (p.chapter == chapter and p.vehicle != 'scene')
        if later or (path == 'guaranteed' and p.vehicle not in GUARANTEED):
            continue
        weapon = difficulty.item_weapon(p.item)
        if weapon is None:
            continue
        takers = [m for m in party if m.can_use(p.item) and weapon not in held[m.name]
                  and (not p.to or m.char in p.to)]
        if p.to:                    # either of two named: the first LISTED, as the script runs
            takers.sort(key=lambda m: p.to.index(m.char))
        if p.vehicle not in ('shop', 'worldmap_shop'):
            takers = takers[:1]
        for m in takers:
            held[m.name].append(weapon)
    out = {}
    for m in party:
        kit = sum(1 for it in m.items if difficulty.item_weapon(it) is not None)
        own, rest = held[m.name][:kit], held[m.name][kit:]
        # A weapon some other one beats outright goes first, then the lowest Mt: a careful
        # player keeps the Armorslayer over a Steel Sword the Silver Sword already beats.
        best = fe_combat.undominated(tuple(held[m.name]))
        keep = sorted(rest, key=lambda w: (w not in best, -w.mt))[:max(0, SLOTS - len(own))]
        out[m.name] = tuple(own + [w for w in rest if w in keep])
    return out


def chapter_pickups(chap, n):
    """What one of our chapters hands out, as chapter `n`: `chapter_economy`'s pickups, each
    resolved through its own entry so a flavored item reads its `fe_base`, then its shops."""
    econ = difficulty.chapter_economy(chap)
    out = [Pickup(inject.decomp.fe_item_enum(entry), vehicle, n)
           for vehicle, entry in econ['pickups']]
    for sym in econ['shops']:
        out += [Pickup(it, 'shop', n) for it in difficulty.shop_stock(sym)]
    return out


def our_pickups(campaign):
    """Every pickup our WRITTEN chapters hand out. A `status: planned` chapter does not exist
    for the difficulty math (ADR 0363). Cached on the chapter files' and campaign.yaml's
    mtimes: every parity read asks for it, and an edit mid-session is still picked up."""
    import campaign_chapters
    files = campaign_chapters.paths(campaign) + [campaign_chapters.campaign_yaml_path(campaign)]
    return _our_pickups(campaign, tuple((f, os.stat(f).st_mtime_ns) for f in files))


@functools.lru_cache(maxsize=4)
def _our_pickups(campaign, _key):
    import campaign_chapters
    out = []
    for chap in campaign_chapters.load_all(campaign):
        if chap.get('status') != 'planned':
            out += chapter_pickups(chap, int(chap['chapter_number']))
    return tuple(out + _our_worldmap_pickups(campaign))


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
                for p in twin_pickups() if p.vehicle == 'worldmap_shop']
    out = []
    for node in nodes:
        after = node.get('unlocks_after')
        n = int(after[2:]) if after else 0
        out += [Pickup(inject.decomp.fe_item_enum(i if isinstance(i, dict) else {'id': i}),
                       'worldmap_shop', n) for i in node.get('stock') or ()]
    return out


def _twin_worldmap_pickups():
    """Each Eirika-route node's Armory, Vendor and Secret Shop stock
    (src/worldmap_node_data.c, worldmap_shop_data.c), from the chapter its map is played."""
    nodes = inject.decomp.vanilla_decomp_text('src/worldmap_node_data.c')
    stock = inject.decomp.vanilla_decomp_text('src/worldmap_shop_data.c')
    out = []
    for body in re.split(r'\[NODE_\w+\]\s*=', nodes)[1:]:
        ch = re.search(r'\.chapteridx_eirika\s*=\s*(\w+)', body)
        twin = ch and inject.chapter_settings.shared_route_twin(ch.group(1))
        if twin not in difficulty.VANILLA_CHAIN:     # off the chain we compare
            continue
        n = difficulty.VANILLA_CHAIN.index(twin)
        for sym in re.findall(r'\.(?:armory|vendor|secretShop)\s*=\s*(\w+)', body):
            out += [Pickup(it, 'worldmap_shop', n) for it in difficulty._shoplist_items(stock, sym)]
    return out


@functools.lru_cache(maxsize=None)
def twin_pickups(through=None):
    """Every pickup the twin's chain hands out up to chain position `through` (all of it when
    None), by the same vehicles as ours. A chapter's kit needs nothing past itself, so a read
    never opens a twin chapter it has not reached. Read at HEAD, so cached; a shared tuple."""
    chain = difficulty.VANILLA_CHAIN[:None if through is None else through + 1]
    out = []
    for n, ref in enumerate(chain):
        t = difficulty.twin_event_payload(difficulty.PARITY_REFERENCE_STEM[ref])
        out += [Pickup(it, 'village', n) for it in t['village_gifts']]
        out += [Pickup(it, 'scene', n, _named(to))
                for it, to in zip(t['scene_gifts'], t['scene_gift_to'])]
        out += [Pickup(it, 'interlude', n, _named(to))
                for it, to in zip(t['interlude_gifts'], t['interlude_gift_to'])]
        out += [Pickup(it, 'chest', n) for it in t['chests']]
        out += [Pickup(it, 'drop', n) for it, _gold in difficulty.vanilla_drops(ref) or ()]
        out += [Pickup(it, 'shop', n) for _sym, items in t['shops'] for it in items]
    return tuple(out + [p for p in _twin_worldmap_pickups() if p.chapter < len(chain)])


def _named(to):
    return tuple(t for t in to if t.startswith('CHARACTER_'))
