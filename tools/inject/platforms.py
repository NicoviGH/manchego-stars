"""Battle ground platforms (#65): the ground a battle is drawn on, per chapter.
"""
import os
import re
import sys

from inject.decomp import REPO
from inject.hosts import (
    CH01_HOST_INDEX, CH02_HOST_INDEX, CH03_HOST_INDEX, CH04_HOST_INDEX, CH05_HOST_INDEX,
    CH06_HOST_INDEX, hosted_chapters, PROLOGUE_HOST_INDEX)
from inject.paths import (
    BANIM_BATTLEPARSE_C, BANIM_POINTER_H_TERR, BANIM_TERRAIN_DATA_C, BANIM_TERRAIN_GFX,
    BANIM_TERRAIN_INCBIN_S, CHAPTER_SETTINGS_JSON_PLAT, DATA_TERRAINS_C, VARIABLES_H)


# (campaign png stem, decomp symbol stem, twilight tint). Grounds get table indices in
# append order from PLATFORM_BASE_INDEX. Offsets: 0=Snowdrift, 1=rough(SnowUneven), 2=Ice,
# 3=snowed-over road. APPEND ONLY -- the offsets are addressed by _terrain_snow_ground and a
# reorder silently restages every fight in the campaign.
BATTLE_PLATFORMS = [
    ('snowdrift',         'snowdrift', 0.80),  # open windswept snow, cooled for twilight
    ('snow-uneven-light', 'snowrough', 1.00),  # rough snowy ground over rock
    ('ice-flat',          'snowice',   1.00),  # frozen lake/river
    ('snow-dirt-path',    'snowpath',  1.00),  # a snowed-over track: TERRAIN_ROAD's own ground
]
PLATFORM_BASE_INDEX = 115  # battle_terrain_table currently ends at 114
# Host slot -> battleTileSet, and it is REQUIRED to be total (check.py + the unit test):
# a hosted chapter that names no ground keeps its HOST SLOT's vanilla one, and vanilla's slots
# are not our world. Silence is what made that invisible for two chapters at once -- ch05's slot
# 6 carries vanilla Ch6's 6, whose table sends TERRAIN_ROAD to `michi1` and TERRAIN_PLAINS to
# `heichi1`, so every fight on a map that is 53% road happened on a dirt track and a green verge
# in a snowbound elven tomb (Nicolas, 2026-08-16); ch02's slot 3 (vanilla 5) was wrong the same
# way and nobody had looked. Values: 0x00 snow-OPEN (BanimTerrainGroundDefault, rewritten to the
# drift), 0x15 snow-ROUGH (Tileset15), 0x16 CAVE (Tileset16, vanilla stone).
# ROUGH vs OPEN is a read of the GROUND, not of the weather: `snow-uneven-light` is snow lying
# over rock, `snowdrift` is windswept open snow. It decides only the OPEN/flat terrain -- road,
# rough and water name their own grounds in _terrain_snow_ground and are the same either way.
CHAPTER_BATTLE_TILESETS = {
    PROLOGUE_HOST_INDEX: 0x00,   # the frozen lake: open windswept snow is the whole picture
    CH01_HOST_INDEX:     0x15,   # the iron trail: snow over trail rock
    CH02_HOST_INDEX:     0x15,   # Bryn Shander's approach, same winter tileset as ch01/ch04
    CH03_HOST_INDEX:     0x16,   # the Termalaine mine: indoors, vanilla stone rather than snow
    CH04_HOST_INDEX:     0x15,   # the moose forest: snow over forest floor
    CH05_HOST_INDEX:     0x15,   # the elven tomb: its flat ground is courtyard stone, not drift
                                 # (the roads, which are most of it, take the path ground)
    CH06_HOST_INDEX:     0x00,   # the frozen mouth of Maer Dualdon: open windswept snow over
                                 # lake ice, the prologue's own read. Nothing on this map is
                                 # snow-over-ROCK -- the flat ground IS the frozen lake -- and
                                 # its water fights already take the ice ground by terrain.
}
_PLAT_ICE = {'RIVER', 'SEA', 'LAKE', 'WATER', 'GLACIER', 'SNAG', 'DEEPS', 'SHIP_FLAT',
             'SHIP_WRECK'}
# TERRAIN_ROAD is not a category we invented: it has its own slot in the 66-entry
# BanimTerrainGround_* array, and vanilla's own tables use it -- the slot-6 table ch05 was
# inheriting puts `michi1`, the dirt road, exactly here (Nicolas, 2026-08-16). Ours had been
# collapsing it into "everything else" and giving a paved winter town the open-snow ground.
_PLAT_ROAD = {'ROAD'}
_PLAT_ROUGH = {'MOUNTAIN', 'PEAK', 'CLIFF', 'VALLEY', 'RUINS_REGULAR', 'RUINS_VILLAGE',
               'RUBBLE', 'PILLAR', 'WALL_REGULAR', 'WALL_DAMAGED', 'FENCE_REGULAR',
               'FENCE_32', 'FORT', 'GATE_CASTLE', 'GATE_REGULAR', 'SKY', 'BARREL', 'BONE',
               'DARK', 'GUNNELS', 'BRACE', 'MAST', 'BALLISTA_REGULAR', 'BALLISTA_LONG',
               'BALLISTA_KILLER'}


def _ground_value(table_index):
    """The number a BanimTerrainGround_* array holds to select battle_terrain_table[index].

    It is index + 1, and that is the single easiest thing in #65 to get wrong:
    `GetBanimTerrainGround` (banim-battleparse.c) ends `return ret - 1`, so an array written
    with raw indices selects the row BELOW every platform it names. The snow arrays did exactly
    that from #65 until 2026-08-16 -- open ground resolved to `mizuiumi1`, a vanilla LAKE, and
    a chapter that asked for the rough ground got the drift. It survived because the drift is
    plausible snow and nothing in the build, the tests or any scenario read the ground.
    """
    return table_index + 1


def _terrain_snow_ground(terrain, base, rough_open):
    """Ground VALUE for TERRAIN_<terrain> on a snow map (see _ground_value -- this is not an
    index). rough_open=True (the Ch1 'rough' tileset) sends open/flat ground to the rough
    platform instead of the drift."""
    if terrain in _PLAT_ICE:
        return _ground_value(base + 2)
    if terrain in _PLAT_ROAD:
        return _ground_value(base + 3)
    if terrain in _PLAT_ROUGH:
        return _ground_value(base + 1)
    return _ground_value(base + (1 if rough_open else 0))


def inject_battle_platforms(campaign, verbose=True):
    """Vendor the snow/ice battle platforms + remap snow chapters' terrain->ground (#65).

    ADDING A PLATFORM (the repeatable how):
      1. Source from the FE-Repo `{Cynon} Battle Platforms` pack (F2E; back-up `{WAve}`). Pull one
         file without cloning the 2.3GB repo:
           gh api "repos/Klokinator/FE-Repo/contents/<URL-encoded path>" \\
             | python3 -c "import sys,json;[print(e['download_url']) for e in json.load(sys.stdin)]"
           curl -fsSL "<download_url>" -o campaigns/<c>/platforms/<stem>.png
         It MUST be indexed mode P, 256x32, <=16 colours, dense indices 0-15 (vanilla platform format).
         CREDIT the author in CREDITS.md. Pick the look book-grounded (Everlasting Rime = twilight ->
         Medium/Night palettes, not bright Light); record the per-chapter pick in decisions.md.
      2. Add it to BATTLE_PLATFORMS `(png stem, symbol stem, tint)` -- tint 0.80 cools a bright
         platform to twilight, 1.0 = as-is. It vendors (PNG->.4bpp.lz via the Makefile gbagfx rule +
         a generated .agbpal), appends an extern (banim_pointer.h), an .incbin (data_banim_terrain.s),
         and a battle_terrain_table row (banim_terrain_data.c; indices from PLATFORM_BASE_INDEX).

    PER-CHAPTER look: set a chapter's `battleTileSet` in chapter_settings.json to 0 (snow-OPEN ->
    Snowdrift, via BanimTerrainGroundDefault) or 0x15 (snow-ROUGH -> Uneven, via Tileset15). A third
    look (e.g. a frozen-lake chapter -> Ice) = add a BanimTerrainGround_Tileset16 + a `case 0x16` in
    banim-battleparse.c + point the chapter at it. Terrain category -> ground = _terrain_snow_ground
    (_PLAT_ICE / _PLAT_ROUGH / else drift). All patched decomp files are in PATCHED_DECOMP_FILES.
    Decisions/rationale: decisions.md (Art & Audio).
    """
    import json as _json
    import re as _re
    import struct as _struct
    from PIL import Image
    base = PLATFORM_BASE_INDEX
    plat_dir = os.path.join(REPO, 'campaigns', campaign, 'platforms')

    # 1. vendor each platform: png -> decomp (Makefile gbagfx makes .4bpp.lz) + agbpal
    externs, incbins, rows = [], [], []
    for n, (stem, sym, tint) in enumerate(BATTLE_PLATFORMS):
        im = Image.open(os.path.join(plat_dir, stem + '.png'))
        if im.mode != 'P':
            sys.exit('ERROR: platform %s must be indexed (mode P), got %s' % (stem, im.mode))
        tsym, psym = 'battle_terrain_ms_%s_tileset' % sym, 'battle_terrain_ms_%s_pal' % sym
        im.save(os.path.join(BANIM_TERRAIN_GFX, tsym + '.png'))
        pal = im.getpalette()
        blob = bytearray()
        for i in range(16):
            r, g, b = pal[i * 3], pal[i * 3 + 1], pal[i * 3 + 2]
            if i != 0 and tint != 1.0:
                r, g, b = r * tint, g * tint, min(255, b * tint + 16)
            blob += _struct.pack('<H', (min(31, int(r) >> 3)) | (min(31, int(g) >> 3) << 5)
                                 | (min(31, int(b) >> 3) << 10))
        with open(os.path.join(BANIM_TERRAIN_GFX, psym + '.agbpal'), 'wb') as f:
            f.write(blob)
        externs += ['extern short %s[];' % psym, 'extern char %s[];' % tsym]
        incbins += ['\t.global %s' % tsym, '%s:' % tsym,
                    '\t.incbin "graphics/banim/terrain/%s.4bpp.lz"' % tsym, '\t.align 2, 0',
                    '\t.global %s' % psym, '%s:' % psym,
                    '\t.incbin "graphics/banim/terrain/%s.agbpal"' % psym, '\t.align 2, 0']
        rows.append('\t{"ms_%s", %s, %s, 0}, // %d  (FE-Repo {Cynon}, F2E)'
                    % (sym, tsym, psym, base + n))

    with open(BANIM_POINTER_H_TERR, 'a', encoding='utf-8') as f:
        f.write('\n/* Manchego Stars battle platforms (#65) */\n' + '\n'.join(externs) + '\n')
    with open(BANIM_TERRAIN_INCBIN_S, 'a', encoding='utf-8') as f:
        f.write('\n/* Manchego Stars battle platforms (#65) */\n' + '\n'.join(incbins) + '\n')

    # 2. append rows to battle_terrain_table[] (before its closing };). DRIFT GUARD: our grounds
    #    get indices from PLATFORM_BASE_INDEX, which assumes the (restored-vanilla) table holds
    #    exactly that many entries (0..base-1). If a submodule bump ever resizes the vanilla table,
    #    fail loudly here rather than silently mis-index the new grounds.
    with open(BANIM_TERRAIN_DATA_C, encoding='utf-8') as f:
        td = f.read()
    last = base - 1
    table_body = re.search(r'battle_terrain_table\[\]\s*=\s*\{(.*?)\n\};', td, re.S)
    vanilla_count = len(re.findall(r'^\s*\{".*?\}, //', table_body.group(1), re.M)) if table_body else -1
    if vanilla_count != base or ('// %d\n};' % last) not in td:
        sys.exit('ERROR: battle_terrain_table has %d entries, expected PLATFORM_BASE_INDEX=%d '
                 '(vanilla table size shifted -- update PLATFORM_BASE_INDEX)' % (vanilla_count, base))
    td = td.replace('// %d\n};' % last, '// %d\n' % last + '\n'.join(rows) + '\n};', 1)
    with open(BANIM_TERRAIN_DATA_C, 'w', encoding='utf-8') as f:
        f.write(td)

    # 3. terrain->ground remap. Default = snow-OPEN (prologue/sandbox, tileset 0);
    #    a new Tileset15 = snow-ROUGH (Ch1). Both reference the new grounds.
    with open(DATA_TERRAINS_C, encoding='utf-8') as f:
        dt = f.read()

    def _snow_body(default_body, rough_open):
        return _re.sub(
            r'\[TERRAIN_(\w+)\]\s*=\s*-?\d+,',
            lambda mm: '[TERRAIN_%s] = %d,'
            % (mm.group(1), _terrain_snow_ground(mm.group(1), base, rough_open)),
            default_body)

    m = _re.search(r'(BanimTerrainGroundDefault\[\] =\s*\{)(.*?)(\n\};)', dt, _re.S)
    open_body, rough_body = _snow_body(m.group(2), False), _snow_body(m.group(2), True)
    dt = dt[:m.start()] + m.group(1) + open_body + m.group(3) + dt[m.end():]
    rough_arr = 'CONST_DATA s8 BanimTerrainGround_Tileset15[] = {%s\n};\n\n' % rough_body
    dt = dt.replace('CONST_DATA s8 BanimTerrainGroundDefault[] = {',
                    rough_arr + 'CONST_DATA s8 BanimTerrainGroundDefault[] = {', 1)
    # Tileset16 = CAVE (ch03 Termalaine mine). Unlike snow, this uses EXISTING VANILLA platforms:
    # the mine floor -> siroyuka1 (the vanilla neutral STONE ground, battle_terrain_table[20]) and
    # rock walls/cliffs -> gake1 (table[4]). No PNG/append/FE-Repo pull needed. Both go through
    # _ground_value for the same reason the snow path now does: this desk knew the +1 convention
    # and the snow desk did not, and one of them was silently wrong for two months.
    def _cave_body(default_body):
        return _re.sub(
            r'\[TERRAIN_(\w+)\]\s*=\s*-?\d+,',
            lambda mm: '[TERRAIN_%s] = %d,'
            % (mm.group(1), _ground_value(4 if mm.group(1) in _PLAT_ROUGH else 20)),
            default_body)
    cave_arr = 'CONST_DATA s8 BanimTerrainGround_Tileset16[] = {%s\n};\n\n' % _cave_body(m.group(2))
    dt = dt.replace('CONST_DATA s8 BanimTerrainGroundDefault[] = {',
                    cave_arr + 'CONST_DATA s8 BanimTerrainGroundDefault[] = {', 1)
    with open(DATA_TERRAINS_C, 'w', encoding='utf-8') as f:
        f.write(dt)

    # 4. extern (variables.h) + switch case (banim-battleparse.c) for Tileset15
    with open(VARIABLES_H, encoding='utf-8') as f:
        vh = f.read()
    vh = vh.replace('extern CONST_DATA s8 BanimTerrainGround_Tileset01[];',
                    'extern CONST_DATA s8 BanimTerrainGround_Tileset15[];\n'
                    'extern CONST_DATA s8 BanimTerrainGround_Tileset16[];\n'
                    'extern CONST_DATA s8 BanimTerrainGround_Tileset01[];', 1)
    with open(VARIABLES_H, 'w', encoding='utf-8') as f:
        f.write(vh)
    with open(BANIM_BATTLEPARSE_C, encoding='utf-8') as f:
        bp = f.read()
    bp = bp.replace(
        '    case 0:\n    default:\n        return BanimTerrainGroundDefault[terrain];',
        '    case 0x15:\n        return BanimTerrainGround_Tileset15[terrain];\n\n'
        '    case 0x16:\n        return BanimTerrainGround_Tileset16[terrain];\n\n'
        '    case 0:\n    default:\n        return BanimTerrainGroundDefault[terrain];', 1)
    with open(BANIM_BATTLEPARSE_C, 'w', encoding='utf-8') as f:
        f.write(bp)

    # 5. Point every hosted chapter at its ground. One registry rather than a write per
    #    chapter: the chapters that were WRONG were the ones nobody had written a line for,
    #    so the fix is a table that has to mention them all (CHAPTER_BATTLE_TILESETS).
    missing = [c.name for c in hosted_chapters() if c.host_index not in CHAPTER_BATTLE_TILESETS]
    if missing:
        sys.exit('ERROR: %s host no battleTileSet -- a chapter that names none keeps its slot\'s '
                 'VANILLA ground (grass/road under snow). Add it to CHAPTER_BATTLE_TILESETS'
                 % ', '.join(missing))
    with open(CHAPTER_SETTINGS_JSON_PLAT, encoding='utf-8') as f:
        cs = _json.load(f)
    for host_index, tileset in sorted(CHAPTER_BATTLE_TILESETS.items()):
        cs['chapters'][host_index]['battleTileSet'] = tileset
    with open(CHAPTER_SETTINGS_JSON_PLAT, 'w', encoding='utf-8') as f:
        _json.dump(cs, f, indent=2)

    if verbose:
        print('  %d platforms -> battle_terrain_table[%d..%d] (FE-Repo {Cynon}, F2E)'
              % (len(BATTLE_PLATFORMS), base, base + len(BATTLE_PLATFORMS) - 1))
        print('  terrain->ground: Default=snow-open (Snowdrift); Tileset15=snow-rough; '
              'Tileset16=CAVE (vanilla siroyuka1 stone / gake1 rock)')
        print('  chapter grounds: %s' % ', '.join(
            '%s->0x%02X' % (c.name, CHAPTER_BATTLE_TILESETS[c.host_index])
            for c in hosted_chapters()))
