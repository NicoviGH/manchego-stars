"""Terrain reachability: whether a scripted move can actually walk its route.
"""
import json
import os
import re
import struct
import sys

from inject.decomp import vanilla_decomp_text
from inject.maps import _layout_sidecar, map_tileset


def reda_route_move(pid, route, why, who='this unit'):
    """A MULTI-LEG scripted walk, as vanilla's REDA queue: `MOVE_DEFINED` + `ENUN`.

    `MOVE(0x0, pid, x, y)` takes ONE destination and lets the pathfinder choose the shape, which
    is right for a step aside and wrong for a walk whose PATH is the point -- vanilla's own
    Glen/Cormag exits and ch04's moose both queue waypoints instead, so the unit turns where the
    author says rather than wherever the search happens to cut the corner.

    One (x, y) pair per waypoint, each followed by a 0 (the REDA's second half-word), then a
    single `MOVE_DEFINED`. Every leg must be WALKABLE for the unit -- `MOVE_DEFINED` + `ENUN`
    on a route it cannot take never returns (see `assert_scripted_move_reachable`).

    Shared by ch04's flee and ch05's charge rather than written twice: they are the same animal
    doing the same thing in opposite directions.
    """
    if not route:
        sys.exit('ERROR: %s needs at least one authored route waypoint' % who)
    lines = ['    SVAL(EVT_SLOT_D, 0x0) /* authored REDA route; one pair per waypoint */']
    for x, y in route:
        lines += [
            '    SVAL(EVT_SLOT_1, 0x%X) /* (%d, %d), normal unit movement */'
            % ((y << 6) | x, x, y),
            '    SENQUEUE1',
            '    SVAL(EVT_SLOT_1, 0x0)',
            '    SENQUEUE1',
        ]
    return lines + ['    MOVE_DEFINED(%s) /* %s */' % (pid, why), '    ENUN']


TERRAIN_TABLE_OFFSET = 8192     # a tile config is 8192 B TSA + 1024 B terrain (map_tileset_tool)


def _map_terrain_grid(maps_dir, stem):
    """(width, height, terrain[y][x]) for a painted chapter layout, resolved through its OWN
    tileset's terrain table. Reads the campaign tileset asset, not the decomp's copy of it --
    ours is the committed source, the decomp's is the untracked artifact injection writes."""
    with open(_layout_sidecar(maps_dir, stem), encoding='utf-8') as f:
        meta = json.load(f)
    width, tileset = meta['width'], map_tileset(meta)
    with open(os.path.join(maps_dir, 'tilesets', tileset, tileset + '.bin'), 'rb') as f:
        terrain = f.read()[TERRAIN_TABLE_OFFSET:]
    with open(os.path.join(maps_dir, stem + '.mar'), 'rb') as f:
        mar = f.read()
    height = len(mar) // 2 // width
    return width, height, [
        [terrain[struct.unpack_from('<H', mar, (y * width + x) * 2)[0] >> 5]
         for x in range(width)] for y in range(height)]


def _class_terrain_move_costs(table):
    """One class's terrain movement-cost row, indexed by terrain id (entry <= 0 = the class may
    not enter that terrain), read from the decomp at HEAD -- data_terrains.c is a PATCHED file,
    so the working tree is not the vanilla answer.

    The rows are DESIGNATED initializers keyed by name (`[TERRAIN_FOREST] = 2`), not a positional
    list, so they must be resolved through the terrain enum. Reading them positionally silently
    produces a table that is wrong in a way that still looks plausible -- every terrain walkable,
    because the names themselves carry digits (TERRAIN_C_ROOM_09, TERRAIN_TILE_2E) that a naive
    number scan picks up as costs."""
    text = vanilla_decomp_text('src/data_terrains.c')
    match = re.search(r'\b%s\[\]\s*=\s*\{(.*?)\};' % re.escape(table), text, re.S)
    if not match:
        sys.exit('ERROR: no movement-cost table %s in the decomp' % table)
    ids = {name: int(value, 0) for name, value in re.findall(
        r'(TERRAIN_[A-Z0-9_]+)\s*=\s*(0[xX][0-9A-Fa-f]+|\d+)',
        vanilla_decomp_text('include/constants/terrains.h'))}
    costs = [-1] * (max(ids.values()) + 1)   # a terrain the row omits stays impassable
    for name, value in re.findall(r'\[(TERRAIN_[A-Z0-9_]+)\]\s*=\s*(-?\d+)', match.group(1)):
        costs[ids[name]] = int(value)
    return costs


def reachable_tiles(terrain, costs, start):
    """The set of tiles a unit with `costs` can WALK to from `start` (4-neighbour flood fill,
    the engine's own rule: costs[terrain] < 0 means it may not enter)."""
    height, width = len(terrain), len(terrain[0])
    seen, queue = {start}, [start]
    while queue:
        x, y = queue.pop()
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            nx, ny = x + dx, y + dy
            if (0 <= nx < width and 0 <= ny < height and (nx, ny) not in seen
                    and costs[terrain[ny][nx]] > 0):
                seen.add((nx, ny))
                queue.append((nx, ny))
    return seen


def assert_scripted_move_reachable(maps_dir, stem, start, dest, mov_table, who):
    """A scripted MOVE(...)+ENUN to a tile its unit cannot WALK to NEVER RETURNS: the event
    engine waits on a path that does not exist and the chapter hangs, with the unit standing
    exactly where it was. Nothing upstream catches it -- the destination can be perfectly good
    terrain, `make` stays green, and the beat only wedges the game when it actually fires.

    Found the hard way (ch04 #24 Stage 4): the white moose flees to the map's NE corner, which
    is TERRAIN_PLAINS and looks fine, but is sealed off from its own clearing by a wall of
    TERRAIN_CLIFF. The sighting soft-locked the chapter the first time a party unit triggered
    it -- and `smoke_ch04` stayed green throughout, because an idling party never walks into the
    clearing to trigger it.

    So: flood-fill the map with the unit's class movement-cost row and reject any destination
    outside the region reachable from where the script loads it.
    """
    _, _, terrain = _map_terrain_grid(maps_dir, stem)
    costs = _class_terrain_move_costs(mov_table)
    reachable = reachable_tiles(terrain, costs, start)
    if dest not in reachable:
        north_east = sorted(reachable, key=lambda t: (t[1] - t[0]))[0]
        sys.exit(
            'ERROR: %s cannot walk from %s to %s on %s -- the MOVE would hang the chapter.\n'
            '       destination terrain is 0x%02X (cost %d); it is simply cut off from the '
            'start.\n'
            '       most north-east tile it CAN reach: %s'
            % (who, start, dest, stem, terrain[dest[1]][dest[0]],
               costs[terrain[dest[1]][dest[0]]], north_east))
