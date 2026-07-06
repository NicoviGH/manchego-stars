#!/usr/bin/env python3
"""Ch3 "The Termalaine Mine" (#40) — programmatic Borgo->cave-interior retile.

Reskins the vanilla FE8 Ch3 (Bandits of Borgo) layout onto Cynon's Mineshaft
(`cave-interior`) by TERRAIN, not by index — cave-interior is a foreign tileset
whose metatile indices are unrelated to vanilla's, so each vanilla cell is mapped
by its terrain role (wall/floor/road/chest/...). Emits the decomp .mar + .json.

WIP checkpoint (co-designed with Nicolas, 2026-07-05): furniture LOCKED (chest,
door, throne dais, barrel, pillar); still open = stairs orientation, road
cart-tracks, the E1 well, and a floor-detail scatter pass. Re-run after edits.

Inputs (from the fireemblem8u submodule, so run after `git submodule update`):
  graphics/map/layout/Ch3Map.mar   vanilla Ch3 layout (metatile grid, <<5)
  graphics/map/TileConfiguration2.bin  Ch3's real tile config (terrain table)
Output: this dir's ch03-the-termalaine-mine.mar + .json (tileset cave-interior).
Run:  python3 campaigns/rime-of-the-frostmaiden/maps/ch03-retile.py [--preview out.png]
"""
import sys, os, struct

ROOT = os.path.dirname(os.path.abspath(__file__)).split('/campaigns/')[0]
sys.path.insert(0, os.path.join(ROOT, 'tools'))
from map_tileset_tool import Tileset, compile_layout, render_grid
DEC = os.path.join(ROOT, 'fireemblem8u')
MAPS = os.path.dirname(os.path.abspath(__file__))
CAVE = os.path.join(MAPS, 'tilesets', 'cave-interior')

W, H = 17, 16
mar = open(os.path.join(DEC, 'graphics/map/layout/Ch3Map.mar'), 'rb').read()
cells = [struct.unpack_from('<H', mar, i * 2)[0] // 32 for i in range(W * H)]
terr = open(os.path.join(DEC, 'graphics/map/TileConfiguration2.bin'), 'rb').read()[8192:]
T = [[terr[cells[y * W + x]] for x in range(W)] for y in range(H)]

# --- tile choices by vanilla terrain role (LOCKED unless noted) --------------
GREY = [33, 65, 64, 98, 66, 99]      # gallery-floor family (FLOOR + PLAINS + ROAD)
FEAT = {
    0x0c: 177,   # FOREST  -> moss
    0x1d: 739,   # PILLAR  -> timber support
    0x1e: 812,   # DOOR    -> single door (813+814 = double)
    0x1f: 784,   # THRONE  -> dais seat (frame via OVERLAY below)
    0x20: 17, 0x21: 17,   # CHEST -> imported FF5 navy chest (closed 17 / open 29)
    0x2d: 302,   # STAIRS  -> ladder  (orientation TBD)
    0x39: 822,   # BARREL  -> barrel  (E1 is really a well - TBD)
}
WALLSET = {0x1a, 0x1b}   # WALL + WALL_DAMAGED read as rock
# wall-rim autotile: solid-neighbour-dir set -> cave rim tile (learned from
# Cynon's test map; a cell's "solid" dirs are neighbours that are also wall).
LEARNED = {frozenset(['N']): 673, frozenset(['S']): 481, frozenset(['E']): 610,
           frozenset(['W']): 521, frozenset(['E', 'N']): 578, frozenset(['N', 'W']): 611,
           frozenset(['S', 'E']): 546, frozenset(['S', 'W']): 486,
           frozenset(['N', 'S']): 610, frozenset(['E', 'W']): 673}
OPP = {'N': 'S', 'S': 'N', 'E': 'W', 'W': 'E'}
NB = {'N': (0, -1), 'S': (0, 1), 'E': (1, 0), 'W': (-1, 0)}

def iswall(x, y):
    if not (0 <= x < W and 0 <= y < H):
        return True   # off-map = solid rock
    return T[y][x] in WALLSET

def wall_tile(x, y):
    s = set(d for d, (dx, dy) in NB.items() if iswall(x + dx, y + dy))
    fs = frozenset(s)
    if len(s) >= 4:
        return 3                              # fully enclosed interior rock
    if fs in LEARNED:
        return LEARNED[fs]
    if len(s) == 0:
        return 673                            # isolated boulder
    if len(s) == 3:
        return LEARNED[frozenset([OPP[(set('NSEW') - s).pop()]])]
    return LEARNED.get(fs, 673)

grid = [[0] * W for _ in range(H)]
for y in range(H):
    for x in range(W):
        t = T[y][x]
        if t in WALLSET:
            grid[y][x] = wall_tile(x, y)
        elif t in (0x17, 0x01, 0x02):
            grid[y][x] = GREY[(x * 5 + y * 3) % len(GREY)]
        elif t in FEAT:
            grid[y][x] = FEAT[t]
        else:
            grid[y][x] = GREY[0]

# Throne dais overlay: cave-interior's pool structure, 784 seat on the O1 seize
# cell. Terrain-matched to vanilla (rows 0-3, cols M-Q: wall frame + walkable
# tiled floor), so the room stays mechanically identical to vanilla Borgo.
OVERLAY = {
    'M0': 751, 'N0': 688, 'O0': 752, 'P0': 690, 'Q0': 755,
    'M1': 783, 'N1': 843, 'O1': 784, 'P1': 845, 'Q1': 785,
    'M2': 783, 'N2': 875, 'O2': 880, 'P2': 881, 'Q2': 785,
    'M3': 783, 'N3': 907, 'O3': 912, 'P3': 913, 'Q3': 785,
}
for coord, tile in OVERLAY.items():
    grid[int(coord[1:])][ord(coord[0]) - ord('A')] = tile

# Chests: single-tile closed FF5 navy chest (17). When the ch03 map-changes are
# authored, each chest cell gets a TILECHANGE that swaps 17 -> 29 (open) on loot.
for c in ['G3', 'I3', 'K3', 'G12']:
    grid[int(c[1:])][ord(c[0]) - ord('A')] = 17

compile_layout(grid, os.path.join(MAPS, 'ch03-the-termalaine-mine.mar'),
               'ch03-the-termalaine-mine', tileset='cave-interior')
print('wrote ch03-the-termalaine-mine.mar + .json')
if '--preview' in sys.argv:
    out = sys.argv[sys.argv.index('--preview') + 1]
    cave = Tileset(CAVE + '/cave-interior.4bpp', CAVE + '/cave-interior.gbapal',
                   CAVE + '/cave-interior.bin')
    render_grid(cave, grid, out, zoom=6)
    print('wrote preview', out)
