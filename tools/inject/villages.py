"""Villages: the visit scripts, rewards, location events, and their vanilla-parity guards.
"""
import re
import sys

from inject.decomp import vanilla_decomp_text
from inject.maps import terrain_ids
from inject.terrain import _map_terrain_grid


def village_script(msg, item, bg):
    """A village visit, in vanilla Ch4's own shape (EventScr_089F1BD8): one text box over the
    village BG, then the reward into the visitor's hands.

    `SVAL(EVT_SLOT_3, item)` + `GIVEITEMTO(CHAR_EVT_ACTIVE_UNIT)` is the engine's give-an-item
    idiom -- slot 3 carries the item id and the ACTIVE unit is the one who walked in, so the axe
    lands on the visitor (overflowing to the convoy if their pack is full), not on a fixed pid.

    `item` is None for a village whose reward IS its line -- ch04's economy is deliberately
    Ch4-lean (decisions.md: one Iron Axe, no gold, no chests), so the forest cottage pays in
    lore. That drops vanilla's give-item tail rather than handing over some default; the
    EVBIT_T(7) visit flag stays either way, or the door never shuts behind you.
    """
    give = ('' if item is None else
            '    SVAL(EVT_SLOT_3, %s)\n'
            '    GIVEITEMTO(CHAR_EVT_ACTIVE_UNIT)\n' % item)
    return ('{\n'
            '    MUSI\n'
            '    Text_BG(%s, 0x%X)\n'
            '    MUNO\n'
            '    CALL(EventScr_RemoveBGIfNeeded)\n'
            '%s'
            '    EVBIT_T(7)\n'
            '    ENDA\n}' % (bg, msg, give))


def village_reward_id(village):
    """The YAML id of what a village hands over, or None when its reward is the line alone."""
    reward = village.get('visit_reward')
    return reward[0]['id'] if reward else None


def village_reward_item(village, item_ids):
    """The FE item enum a village hands over, or None when its reward is the line alone.

    `item_ids` is the CHAPTER's id->enum map. It used to close over CH04_ITEM_IDS, which made a
    shared helper silently ch04-only: ch05's gifts (the two stat boosters) are not in that dict,
    so the first chapter to reuse it would have died on a KeyError naming ch04.
    """
    reward = village_reward_id(village)
    return item_ids[reward] if reward else None


SAVE_ALL_SKIP_LABEL = '0x2'     # vanilla Ch5's own label for "a site was lost -- skip the gift"


def save_all_bonus_script(subjects, item, check='CHECK_EVENTID'):
    """Vanilla's save-them-all payout, as event lines: one `check` per site, each branching PAST
    the gift the moment it reads 0, so the reward survives only a clean sweep.

    Vanilla spells it two ways and both read 0 for "lost": Ch5 (`EventScr_Ch5_EndingScene`) asks
    CHECK_EVENTID of each village's visit flag -- a raided site never set it, and neither did one
    the player walked past -- and Ch6 (`EventScr_Ch6_EndingScene`) asks CHECK_ALIVE of each
    civilian pid. `subjects` is {site id: flag or pid}; ch05 passes flags, ch06 its hulls' pids.

    CHAR_EVT_PLAYER_LEADER, not the village idiom's CHAR_EVT_ACTIVE_UNIT: nobody is standing on
    a tile at the ending, so there is no active unit for the item to land on."""
    if check not in ('CHECK_EVENTID', 'CHECK_ALIVE'):
        sys.exit('ERROR: save_all_bonus_script check %r is neither vanilla spelling' % check)
    lines = []
    for subject in subjects.values():
        lines += ['    %s(%s)' % (check, subject),
                  '    BEQ(%s, EVT_SLOT_C, EVT_SLOT_0)' % SAVE_ALL_SKIP_LABEL]
    lines += ['    SVAL(EVT_SLOT_3, %s)' % item,
              '    GIVEITEMTO(CHAR_EVT_PLAYER_LEADER)',
              'LABEL(%s)' % SAVE_ALL_SKIP_LABEL]
    return '\n'.join(lines) + '\n'


# Whom a bare `visit_text` string belongs to. ch04/ch05 author flat lists with one voice;
# ch02's south hut needs two, so a box may instead be `- who: "line"`.
DEFAULT_VILLAGE_SPEAKER = 'resident'


def village_boxes(village):
    """A village's line, as the GBA boxes it was AUTHORED in -- one `visit_text` entry per
    A-press.

    Village text is dialogue, so its buttons belong on its beats. Flowed as a single scalar it
    reflows wherever the pixel budget runs out and buttons mid-sentence: the axe village's
    "vanilla 1:1" text came out as THREE boxes breaking on "a handy bridge if / you could knock
    it over", where vanilla's own MSG_9B5 is FOUR broken on its sentences -- 1:1 in words but
    not on screen, which is not what 1:1 meant (Nicolas, 2026-08-02). A flowed scalar is
    therefore rejected outright rather than silently reflowed.
    """
    text = village.get('visit_text')
    if isinstance(text, str) or not text:
        sys.exit('ERROR: village %r must author `visit_text` as a LIST -- one entry per GBA '
                 'box. A flowed scalar reflows at the wrap width and puts the A-press breaks '
                 'mid-sentence.' % village['id'])
    boxes = []
    for box in text:
        if isinstance(box, dict):
            # `- who: "line"` -- the same form the chapter scene scripts use. Two keys in one
            # box would be two speakers sharing an A-press, which drops a line on the floor.
            if len(box) != 1:
                sys.exit('ERROR: village %r has a visit_text box naming %d speakers; one box '
                         'is one A-press by one person' % (village['id'], len(box)))
            who, line = next(iter(box.items()))
        else:
            who, line = DEFAULT_VILLAGE_SPEAKER, box
        boxes.append((who, ' '.join(line.split())))
    return boxes


def location_events(villages, village_slots, shops=(), flags=None):
    """The host slot's Location list: everything the player can VISIT.

    One `Village` per authored village, at the tile the chapter YAML names, each running its OWN
    script (`village_slots[id]`) -- two doors sharing one script show the same line at both.

    `Village(eid, scr, x, y)` expands to VILL + a LOCA on the tile ABOVE (EAstdlib) carrying
    TILE_COMMAND_20 -- and that second entry is the DESTRUCTION hook: a raider that reaches the
    door runs AiPillageAction, which calls StartAvailableTileEvent(x, y - 1) (cp_perform.c) and
    flips the tile through the chapter's MapChange array. Both entries carry the same `eid`.

    `flags` is {village id: event-flag expression} -- the id FE8 sets when the site is visited.
    It defaults to 0, which is EVFLAG_ALWAYS_FALSE: CheckChapterFlag(0) returns 0 forever
    (eventinfo.c), so SearchAvailableEvent never skips a 0 entry. A chapter that only needs
    doors can leave it alone; a chapter that RACES for its sites cannot, because the same flag
    is what records the visit, disarms that site's raider hook, and answers the save-all
    CHECK_EVENTID at the ending (#25).

    `shops` are `(macro, shoplist_symbol, x, y)` -- `Armory`/`Vendor` take their stock DIRECTLY
    and run no script and show no text, so a shop is fully wired the moment its tile is listed.

    **An empty Location list makes every reward on the map unobtainable while the map still draws
    it.** That is how ch04 shipped an unreachable Iron Axe (#205), and it is why this returns a
    list built from the YAML rather than something a chapter has to remember to fill in.
    """
    flags = flags or {}
    rows = ''.join(
        '    Village(%s, %s, %d, %d) /* %s -- %s */\n'
        % (flags.get(v['id'], '0'), village_slots[v['id']], v['tile'][0], v['tile'][1],
           v['id'], village_reward_id(v) or 'the line is the reward')
        for v in villages)
    rows += ''.join('    %s(%s, %d, %d)\n' % shop for shop in shops)
    return '{\n' + rows + '    END_MAIN\n}'


def assert_village_tiles_visitable(chap, maps_dir, stem):
    """Guard (#205): a village the YAML declares must stand on terrain FE8 will let a unit visit.

    `CanUnitVisit`/the Visit menu item (bmmenu.c:735) checks the TERRAIN under the unit before it
    ever looks at the location event -- HOUSE, INN, RUINS_VILLAGE or VILLAGE_REGULAR -- so a
    `Village()` entry on scenery is a reward that silently does not exist. That is precisely what
    shipped: the snowy reskin mapped vanilla's village metatile onto ruins, the map still drew a
    cottage, and ch04's only material reward was unobtainable for the whole slice.
    """
    width, height, terrain = _map_terrain_grid(maps_dir, stem)
    ids = terrain_ids()
    visitable = {ids[name] for name in
                 ('TERRAIN_HOUSE', 'TERRAIN_INN', 'TERRAIN_RUINS_VILLAGE',
                  'TERRAIN_VILLAGE_REGULAR')}
    for village in chap.get('villages', []):
        x, y = village['tile']
        if not (0 <= x < width and 0 <= y < height):
            sys.exit('ERROR: village %r is at (%d, %d), off the %dx%d %s map'
                     % (village['id'], x, y, width, height, stem))
        if terrain[y][x] not in visitable:
            sys.exit('ERROR: village %r at (%d, %d) stands on terrain 0x%02x -- FE8 offers Visit '
                     'only on house/inn/village terrain (bmmenu.c), so its reward is '
                     'unobtainable. Paint a village tile there (#205).'
                     % (village['id'], x, y, terrain[y][x]))


def vanilla_village_gifts(layout, eventinfo=None, eventscript=None):
    """{(x, y): ITEM_ enum} -- what vanilla hands out at each village on `layout`'s chapter.

    Read from HEAD, like every other vanilla fact. The tile comes from the Location list's
    `Village(flag, script, x, y)` entries; the ITEM is a RAW id inside that script's
    `SVAL(EVT_SLOT_3, <id>)`, which is why it is easy to have and never look at.
    """
    stem = re.sub(r'Map$', '', layout).lower()          # Ch5Map -> ch5
    if eventinfo is None:
        eventinfo = vanilla_decomp_text('src/events/%s-eventinfo.h' % stem)
    if eventscript is None:
        eventscript = vanilla_decomp_text('src/events/%s-eventscript.h' % stem)
    by_id = {int(v, 16): n for n, v in re.findall(
        r'(ITEM_\w+)\s*=\s*(0x[0-9A-Fa-f]+)',
        vanilla_decomp_text('include/constants/items.h'))}
    gifts = {}
    for script, x, y in re.findall(
            r'Village\(\s*[^,]+,\s*(\w+),\s*(\d+),\s*(\d+)\s*\)', eventinfo):
        body = eventscript.split('EventListScr %s[] = {' % script, 1)
        if len(body) < 2:
            continue                                    # script lives elsewhere; nothing to read
        match = re.search(r'SVAL\(EVT_SLOT_3,\s*(0x[0-9A-Fa-f]+|\d+)\)', body[1].split('};', 1)[0])
        if match:
            gifts[(int(x), int(y))] = by_id.get(int(match.group(1), 0))
    return gifts


def assert_village_gifts_match_vanilla(chap, item_ids, gifts=None):
    """Guard (#25): on a RETILE, which gift sits on which tile is vanilla's decision.

    A retile inherits vanilla's terrain (`validate_terrain_matches_vanilla`); this is the same
    rule one layer up, for the rewards standing on that terrain. It is worth a gate because the
    failure is invisible to every other one: swap two gifts and the item set is identical, the
    economy total is identical, and `difficulty.py` counts the SET, not the tiles -- so the
    parity read still says PARITY while the chapter's risk/reward is inverted.

    That is exactly what ch05 shipped. `(12,19)` is the south-east site and the turn-2 eruption
    pair spawns at `(14,16)/(14,15)`, right beside it: vanilla puts its RICHEST gift there
    (Dracoshield, 8000g) and its cheapest at `(5,1)` (Torch, 500g), which sits behind the whole
    enemy line. Ours had them swapped, paying the most for the safest errand in a chapter whose
    structure IS the race for the reward-sites.

    Deliberate divergence stays cheap -- a village may carry `vanilla_gift_divergence: <why>` and
    is then skipped by name. The default is inheritance because exceptions are rarer than
    re-deriving four placements every time (Nicolas, 2026-08-07).

    Only runs for a chapter whose `map:` block names a `vanilla_layout:`; a from-scratch canvas
    has no vanilla to inherit from.
    """
    layout = (chap.get('map') or {}).get('vanilla_layout')
    if not layout:
        return
    if gifts is None:
        gifts = vanilla_village_gifts(layout)
    for village in chap.get('villages', []):
        why = village.get('vanilla_gift_divergence')
        if why:
            continue
        tile = tuple(village['tile'])
        want = gifts.get(tile)
        if want is None:
            continue        # vanilla has no village on that tile -- a site we ADDED, not moved
        reward = (village.get('visit_reward') or [{}])[0].get('id')
        got = item_ids.get(reward)
        if got is None:
            sys.exit('ERROR: village %r gives %r, which is not in this chapter\'s item map -- '
                     'add it to CHNN_ITEM_IDS so the gift can be checked and injected'
                     % (village['id'], reward))
        if got != want:
            sys.exit(
                'ERROR: village %r at (%d, %d) gives %s, but vanilla %s hands out %s there. On a '
                'retile the gift PLACEMENT is vanilla\'s -- swapping two gifts keeps the item set '
                'and the economy total identical (so the parity read still says PARITY) while '
                'inverting which site is worth defending. If the move is deliberate, say so with '
                '`vanilla_gift_divergence: <why>` on that village.'
                % (village['id'], tile[0], tile[1], got, layout, want))
