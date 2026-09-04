#!/usr/bin/env python3
"""Render a chapter's map with a UNIT PLACEMENT drawn on it, so a placement can be
looked at before it is authored.

Enemy coordinates are the one part of a chapter that no vanilla source hands us where
the donor and the parity bar are different chapters (ch06: layout Ch13Ephraim, pressure
Ch6 -- neither one's tiles transfer). They are a design decision, and a design decision
Nicolas makes on a picture rather than on a list of pairs. This draws that picture.

It renders the real metatile art -- the same `render_grid` path `import_map_layout` uses
for its confirmation preview -- and overlays:

  * a coordinate ruler, because every placement conversation is in map coordinates
  * the deploy block, the crossings and the boats, read from the chapter YAML
  * one marker per placed unit, coloured by AI behaviour (the thing placement decides:
    a never-move unit is furniture, a pursuer is a clock)
  * optional per-cell shading -- turn-reach bands, or the cells a placement threatens

Placements come from the chapter YAML's own `positions:` once they are authored, or from
a concept JSON while they are still being chosen, so a concept and the shipped article
render through exactly one code path.

Usage:
    python3 tools/map_placement_preview.py ch06                      # what the YAML says
    python3 tools/map_placement_preview.py ch06 --concept a.json --out map-review/a.png
    python3 tools/map_placement_preview.py ch06 --shade reach        # foot turn bands
"""
import argparse
import json
import os
import re
import struct
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'tools'))
import map_tileset_tool as mt                                        # noqa: E402
import campaign_chapters                                             # noqa: E402

CAMPAIGN = os.path.join(ROOT, 'campaigns/rime-of-the-frostmaiden')
MAPS = os.path.join(CAMPAIGN, 'maps')
DECOMP = os.path.join(ROOT, 'fireemblem8u')

# Terrain ids by name, read from the decomp rather than restated -- the same source
# import_map_layout validates against.
TERRAIN = {}
for _line in open(os.path.join(DECOMP, 'include/constants/terrains.h')):
    _m = re.match(r'\s*(TERRAIN_\w+)\s*=\s*(0x[0-9A-Fa-f]+|\d+)', _line)
    if _m:
        TERRAIN[_m.group(1)] = int(_m.group(2), 0)
NAME_BY_TERRAIN = {v: k for k, v in TERRAIN.items()}

def mov_cost_row(table='TerrainTable_MovCost_CommonT1Normal'):
    """Terrain id -> movement cost, read from the ENGINE's own table (data_terrains.c).

    Read at HEAD, not from the working tree, for the reason `vanilla_decomp_text` exists:
    the build patches decomp sources in place. -1 and 0 are the impassable sentinels. Same
    derivation gen_map_editor's passability overlay uses, so the preview and the editor
    cannot disagree about what a class may enter -- but taken from the .c, which is in
    HEAD, rather than the .s, which is a build artifact and is not.

    Any class row works: PirateNormal is Braulo's, FlyNormal is Pinky's, HorseT1Normal is
    the cavalry's. A chapter whose whole shape is who-can-cross-what needs all of them."""
    import build_campaign as bc
    src = bc.vanilla_decomp_text('src/data_terrains.c')
    m = re.search(r'CONST_DATA s8 %s\[\]\s*=\s*\{(.*?)\n\};' % table, src, re.S)
    if not m:
        sys.exit('ERROR: no move-cost table %r in data_terrains.c' % table)
    costs = {}
    for name, val in re.findall(r'\[(TERRAIN_\w+)\]\s*=\s*(-?\d+)', m.group(1)):
        cost = int(val)
        if cost > 0 and name in TERRAIN:
            costs[TERRAIN[name]] = cost
    return costs


FOOT_COST = mov_cost_row()

# Marker colours by AI behaviour, because behaviour is what a placement decides: a
# never-move unit is furniture the player walks into, a pursuer is a clock.
BEHAVIOUR_COLOUR = {
    'never-move':     (206, 74, 74),      # red
    'charge-after-1': (232, 138, 46),     # orange
    'pursue':         (240, 208, 62),     # yellow
    'hold-position':  (150, 46, 140),     # purple -- the boss on its tile
}
BOAT_COLOUR = (86, 196, 120)
DEPLOY_COLOUR = (74, 138, 226)

# A two-letter code per unit, from its CLASS -- what the player will actually be fighting.
# Names do not work here: ch06 fields four different roles all called "Mermaid".
ROLE_CODE = {'soldier': 'Sp', 'fighter': 'Ax', 'cavalier': 'Cv', 'mercenary': 'Sw',
             'armor-knight': 'Kn', 'shaman': 'Mg', 'mage': 'Mg', 'priest': 'St',
             'troubadour': 'St', 'archer': 'Bw', 'bael': 'Bs'}
ROLE_LEGEND = [('Sp', 'spear'), ('Ax', 'axe'), ('Sw', 'sword'), ('Cv', 'cavalry'),
               ('Kn', 'armour'), ('Mg', 'magic, range 2'), ('Bw', 'bow, range 2'),
               ('St', 'staff'), ('Bs', 'beast')]


def load_map(stem):
    """(grid, terrain, tileset) for one of our compiled maps."""
    meta = json.load(open(os.path.join(MAPS, stem + '.json')))
    w, h = meta['width'], meta['height']
    raw = open(os.path.join(MAPS, stem + '.mar'), 'rb').read()
    cells = [struct.unpack_from('<H', raw, i * 2)[0] >> 5 for i in range(w * h)]
    ts = mt._tileset_from_dir(os.path.join(MAPS, 'tilesets', meta['tileset']))
    grid = [[cells[y * w + x] for x in range(w)] for y in range(h)]
    terrain = [[ts.terrain(m) for m in row] for row in grid]
    return grid, terrain, ts


def foot_reach(terrain, sources):
    """Movement-point distance from any source cell, for a walking class."""
    import heapq
    h, w = len(terrain), len(terrain[0])
    dist, pq = {}, []
    for s in sources:
        dist[s] = 0
        heapq.heappush(pq, (0, s))
    while pq:
        c, (x, y) = heapq.heappop(pq)
        if c > dist.get((x, y), 1 << 30):
            continue
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            nx, ny = x + dx, y + dy
            if not (0 <= nx < w and 0 <= ny < h):
                continue
            step = FOOT_COST.get(terrain[ny][nx])
            if step is None:
                continue
            if c + step < dist.get((nx, ny), 1 << 30):
                dist[(nx, ny)] = c + step
                heapq.heappush(pq, (c + step, (nx, ny)))
    return dist


def deploy_cells(chapter, terrain):
    """The deploy block, parsed from `deployment.start_area`'s "x4-10, y0-2" form."""
    area = (chapter.get('deployment') or {}).get('start_area') or ''
    m = re.search(r'x(\d+)\s*-\s*(\d+)\s*,\s*y(\d+)\s*-\s*(\d+)', area)
    if not m:
        return []
    x0, x1, y0, y1 = (int(g) for g in m.groups())
    return [(x, y) for x in range(x0, x1 + 1) for y in range(y0, y1 + 1)
            if FOOT_COST.get(terrain[y][x]) is not None]


def placed_units(chapter, concept=None):
    """[(tile, label, behaviour)] for every unit a placement puts on the map.

    From a concept JSON when one is given -- `{"units": {"<enemy id>": [[x, y], ...]}}` --
    and otherwise from each enemy entry's own `positions:`. Behaviour comes from the
    chapter's own AI resolution either way, so a concept cannot drift from what the
    build would emit."""
    import difficulty as dif
    import chapter_status as cs
    override = (json.load(open(concept))['units'] if concept else {})
    out = []
    for enemy in chapter.get('enemy_units') or []:
        eid = enemy.get('id')
        tiles = override.get(eid, enemy.get('positions') or [])
        for i, tile in enumerate(tiles):
            ai = dif.enemy_ai_bytes(chapter, enemy, i)
            # Derived from the WHOLE vector, never patched by role: `is_boss` was standing in
            # for the AI_A half this could not see, and it was wrong in both directions -- a
            # non-boss statue read as mobile, and a boss with an engaging action read as static.
            behaviour = cs.ai_shape(ai) or cs.ai_family(ai[1]) or '?'
            code = 'B' if enemy.get('is_boss') else ROLE_CODE.get(enemy.get('class'), '??')
            late = enemy.get('arrives_turn') or enemy.get('hard_mode_only')
            out.append((tuple(tile), code, behaviour, eid, late))
    return out


def _font(size, bold=False):
    """A real font if the system has one -- PIL's built-in bitmap font is unreadable at
    the sizes a 22x22 board needs."""
    from PIL import ImageFont
    for path in ('/System/Library/Fonts/Supplemental/Arial Bold.ttf' if bold else
                 '/System/Library/Fonts/Supplemental/Arial.ttf',
                 '/System/Library/Fonts/Helvetica.ttc',
                 '/Library/Fonts/Arial.ttf'):
        try:
            return ImageFont.truetype(path, size)
        except OSError:
            continue
    return ImageFont.load_default()


def render(chapter, stem, out_png, concept=None, shade=None, zoom=3):
    from PIL import Image, ImageDraw
    grid, terrain, ts = load_map(stem)
    h, w = len(grid), len(grid[0])
    cell = 16 * zoom
    pad = cell                       # a cell of margin for the coordinate ruler
    # The title strip grows with the premise: a concept's reasoning is the point of the
    # picture, so it must never be painted over the board.
    premise = ''
    if concept:
        premise = json.load(open(concept)).get('premise', '')
    prem_lines = []
    line = ''
    for word in premise.split():
        if len(line) + len(word) > 118:
            prem_lines.append(line)
            line = word + ' '
        else:
            line += word + ' '
    if line:
        prem_lines.append(line)
    head = (44 + 19 * len(prem_lines) + 10) if concept else 44
    foot = 158                       # legend strip

    board = Image.new('RGB', (w * cell, h * cell))
    for y in range(h):
        for x in range(w):
            board.paste(ts.metatile_image(grid[y][x]).resize((cell, cell), Image.NEAREST),
                        (x * cell, y * cell))

    units = placed_units(chapter, concept)

    if shade == 'reach':
        dist = foot_reach(terrain, deploy_cells(chapter, terrain))
        wash = Image.new('RGBA', board.size, (0, 0, 0, 0))
        wd = ImageDraw.Draw(wash)
        for (x, y), d in dist.items():
            turn = max(1, -(-d // 5))                 # mov 5, the party's foot speed
            wd.rectangle([x * cell, y * cell, (x + 1) * cell - 1, (y + 1) * cell - 1],
                         fill=(8, 12, 60, min(140, 16 * turn)))
        board = Image.alpha_composite(board.convert('RGBA'), wash).convert('RGB')

    img = Image.new('RGB', (w * cell + pad, h * cell + pad + head + foot), (22, 22, 26))
    img.paste(board, (pad, head))
    d = ImageDraw.Draw(img)
    f_small, f_mid, f_title = _font(15), _font(17), _font(26, bold=True)

    # ---- title -------------------------------------------------------------
    title = 'ch06 The Maer Monster -- enemy placement'
    if concept:
        con = json.load(open(concept))
        title = '%s placement: %s' % (campaign_chapters.short_id(chapter),
                                      con.get('name', os.path.basename(concept)))
        for i, line in enumerate(prem_lines):
            d.text((pad, 40 + i * 19), line, fill=(168, 172, 182), font=f_small)
    d.text((pad, 10), title, fill=(238, 238, 242), font=f_title)

    def box(x, y, colour, width=2):
        d.rectangle([pad + x * cell, head + y * cell,
                     pad + (x + 1) * cell - 1, head + (y + 1) * cell - 1],
                    outline=colour, width=width)

    for x in range(w):                                          # ruler
        d.text((pad + x * cell + cell // 3, head + h * cell + 8), str(x),
               fill=(190, 190, 198), font=f_small)
    for y in range(h):
        d.text((10, head + y * cell + cell // 3), str(y), fill=(190, 190, 198), font=f_small)
    for x in range(w + 1):                                      # grid
        d.line([pad + x * cell, head, pad + x * cell, head + h * cell], fill=(70, 70, 80))
    for y in range(h + 1):
        d.line([pad, head + y * cell, pad + w * cell, head + y * cell], fill=(70, 70, 80))

    for (x, y) in deploy_cells(chapter, terrain):
        box(x, y, DEPLOY_COLOUR, width=3)

    # A concept may PROPOSE a terrain change ("walls": cells that become impassable).
    # Drawn hatched, because it is not what the .mar says yet.
    for (x, y) in (json.load(open(concept)).get('walls') or []) if concept else []:
        x0, y0 = pad + x * cell, head + y * cell
        for k in range(-cell, cell, 7):
            d.line([x0 + max(0, k), y0 + max(0, -k),
                    x0 + min(cell - 1, k + cell), y0 + min(cell - 1, cell - k)],
                   fill=(255, 170, 60), width=2)
        box(x, y, (255, 170, 60), width=3)

    for y in range(h):                                          # crossings
        for x in range(w):
            if terrain[y][x] in (TERRAIN['TERRAIN_BRIDGE_REGULAR'],
                                 TERRAIN['TERRAIN_BRIDGE_SNAG']):
                box(x, y, (250, 250, 250), width=3)

    for boat in chapter.get('rescue_boats') or []:
        x, y = boat['tile']
        box(x, y, BOAT_COLOUR, width=4)
        d.rectangle([pad + x * cell + 4, head + y * cell + 4,
                     pad + (x + 1) * cell - 5, head + (y + 1) * cell - 5],
                    fill=BOAT_COLOUR)
        d.text((pad + x * cell + 8, head + y * cell + cell // 3), 'BOAT',
               fill=(12, 40, 20), font=f_small)

    for tile, code, behaviour, eid, late in units:
        x, y = tile
        colour = BEHAVIOUR_COLOUR.get(behaviour, (200, 200, 200))
        cx, cy = pad + x * cell + cell // 2, head + y * cell + cell // 2
        r = cell // 2 - 2
        if late:
            # Not on the board at turn 1 -- a hollow ring, so a reinforcement never reads
            # as opening pressure. ch06's three Hard-only crab riders arrive on turn 4.
            d.ellipse([cx - r, cy - r, cx + r, cy + r], outline=colour, width=4)
        else:
            d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=colour,
                      outline=(16, 16, 18), width=2)
        tw = d.textlength(code, font=f_mid)
        d.text((cx - tw / 2, cy - 9), code,
               fill=colour if late else (18, 18, 20), font=f_mid)

    # ---- legend ------------------------------------------------------------
    ly = head + h * cell + pad - 4
    d.text((pad, ly), 'behaviour, borrowed from each unit\'s vanilla donor (#335):',
           fill=(210, 210, 216), font=f_small)
    lx = pad + 390
    for name, colour in (('never-move -- you walk into it', BEHAVIOUR_COLOUR['never-move']),
                         ('charge after turn 1', BEHAVIOUR_COLOUR['charge-after-1']),
                         ('pursue from turn 1', BEHAVIOUR_COLOUR['pursue']),
                         ('B = boss, guards its tile', BEHAVIOUR_COLOUR['hold-position']),
                         ('hollow = arrives turn 4, Hard only', (150, 150, 158))):
        d.ellipse([lx, ly, lx + 15, ly + 15], fill=colour, outline=(16, 16, 18))
        d.text((lx + 22, ly), name, fill=(210, 210, 216), font=f_small)
        lx += 22 + int(d.textlength(name, font=f_small)) + 24
        if lx > img.width - 320:
            lx, ly = pad + 390, ly + 24
    d.text((pad, ly + 26), 'role:  ' + '   '.join('%s %s' % (c, n) for c, n in ROLE_LEGEND),
           fill=(210, 210, 216), font=f_small)
    d.text((pad, ly + 52),
           'orange hatch = PROPOSED wall (the donor\'s own TILE_2E: impassable to every '
           'ground class, cost 1 to a flier)', fill=(255, 170, 60), font=f_small)
    d.text((pad, ly + 78),
           'board:  blue = deploy block     white = the 8 crossings     '
           'green = a marooned boat (CLASS_FLEET, 19 HP, Res 0, in a +20-avoid drift)',
           fill=(210, 210, 216), font=f_small)

    os.makedirs(os.path.dirname(out_png) or '.', exist_ok=True)
    img.save(out_png)
    return out_png


def main(argv):
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('chapter', help='chapter id or prefix, e.g. ch06')
    ap.add_argument('--concept', help='a concept JSON of {"units": {id: [[x, y], ...]}}')
    ap.add_argument('--shade', choices=['reach'], help='per-cell shading')
    ap.add_argument('--out', help='output PNG (default map-review/<chapter>-placement.png)')
    ap.add_argument('--zoom', type=int, default=3)
    args = ap.parse_args(argv)

    chapters = campaign_chapters.load_all()
    match = [c for c in chapters if str(c.get('id', '')).startswith(args.chapter)]
    if not match:
        sys.exit('ERROR: no chapter id starts with %r' % args.chapter)
    chapter = match[0]
    stem = os.path.splitext(os.path.basename(chapter['map']['file']))[0]
    out = args.out or os.path.join(ROOT, 'map-review',
                                   '%s-placement.png' % args.chapter)
    print(render(chapter, stem, out, args.concept, args.shade, args.zoom))


if __name__ == '__main__':
    main(sys.argv[1:])
