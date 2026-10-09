"""Chapter maps and tilesets: registering a layout, map changes, fog banks, the winter tileset.
"""
import json
import os
import re
import shutil
import struct
import sys

import map_tileset_tool
from inject.asset_table import _asm_table_word_index, _claim_asm_table_words
from inject.boot import TEST_CHAPTER_INDEX
from inject.decomp import REPO, vanilla_decomp_text
from inject.paths import (
    ASSET_TABLE_S, CHAPTER_SETTINGS_JSON, CONST_MAPS_S, MAP_GFX_DIR, MAP_LAYOUT_DIR)


# A GBAFE map = 4 data pieces the decomp wires through gChapterDataAssetTable
# (data/data_8B363C.s) and incbins in data/const_data_chapter_maps.s: tile GRAPHICS
# (.4bpp.lz), PALETTE (.gbapal), tile CONFIG (.bin.lz = 8192B TSA + 1024B terrain),
# and a per-map LAYOUT (.bin.lz). A chapter's struct (chapter_settings.json -> jsonproc
# -> chapter_settings.h) holds u8 *indices* into the asset table for each piece.
#
# The Snowy Bern community tileset (FEU t/7204; see CREDITS.md) ships these pieces in
# FEBuilder's format, which is byte-identical to the decomp's, so registering it is a
# straight drop-in -- no grit/Map Hacking Suite recompile. We append its gfx/palette/
# config plus a test LAYOUT to the asset table and repoint the TEST chapter at them, so
# `make` + New Game load-tests the tileset in-engine (the same hijack inject_test_chapter
# uses). Authoring real Tiled layouts (.tmx -> .bin) is the next step (#40 task 2 / #20).


# The campaign's tilesets (maps/tilesets/<name>/, vendored via map_tileset_tool
# import). Each registers under ObjectType<Stem>/MapPalette<Stem>/
# TileConfiguration<Stem> asset labels (_register_tileset). Further tilesets
# (e.g. cave-interior, #40/#23) register in the chapter injector that first
# consumes them.
# The shared winter overworld (#41), stem Snow -- and the meaning of a keyless sidecar.
# It is IMPORTED rather than spelled again: `map_tileset_tool` owns tilesets, imports
# nothing but stdlib, and is therefore reachable by every reader including the
# deliberately stdlib-only `map_donor`. Five copies of this literal had accumulated
# across the read and write sides before #377, and repointing it moved some of them.
WINTER_TILESET = map_tileset_tool.DEFAULT_TILESET


def map_tileset(meta):
    """The tileset a compiled map is built against, from its sidecar `<stem>.json`.

    THE resolution rule, in one place. A sidecar that names no tileset gets
    `WINTER_TILESET`, which is not a guess: the three oldest maps (ch00-ch02) predate
    the key entirely and have always been compiled as snowy-bern by exactly this
    default. The chapter YAML's own `map.tileset` is DOCUMENTATION -- nothing in the
    build reads it -- so anything needing to know which tileset a map really uses asks
    HERE, and cannot end up drawing a picture of a tileset the cartridge does not use
    (`decisions.md` -> "A map's tileset has one home").
    """
    if not isinstance(meta, dict):
        # `null`, `[]` and a bare string are all valid JSON and none of them has `.get`.
        # Raising here rather than AttributeError-ing from inside means every caller --
        # including `check.py`'s guards, which would otherwise report a check that "could
        # not run" instead of naming the file -- can catch a malformed sidecar as the data
        # error it is instead of a traceback.
        raise ValueError('map sidecar is %s, not a JSON object' % type(meta).__name__)
    # `map_tileset_tool.DEFAULT_TILESET` read HERE rather than through the module-level
    # `WINTER_TILESET`, so the default is resolved at call time and there is exactly one
    # live source of it. A module-level copy is how the five spellings #377 removed got
    # made in the first place -- by assignment rather than by literal, but still a copy.
    return meta.get('tileset', map_tileset_tool.DEFAULT_TILESET)


def _layout_sidecar(maps_dir, stem):
    """Where the build reads a compiled map's sidecar `<stem>.json`.

    One home for the path, so the four places that read a sidecar -- `_register_chapter_map`
    (the map's asset indices), `_map_changes_tileset` (replacement metatiles),
    `_read_map_metatile` and `_map_terrain_grid` (both of which read a map's width) -- cannot
    end up reading two different files for one chapter. Keyed on the STEM rather than a
    layout tuple, because two of the four have only a stem to offer.
    """
    return os.path.join(maps_dir, '%s.json' % stem)


def _map_changes_tileset(maps_dir, layout):
    """The metatile table a chapter's scripted tile changes must resolve against: the one
    ITS OWN compiled map is built on (#374).

    `map_changes_asm` emits replacement METATILE NUMBERS, and a metatile number only means a
    terrain inside one tileset -- so the table has to be the map's own, read off its sidecar
    through `map_tileset`, the same route `_register_chapter_map` takes. The tiles a change
    writes and the tiles the cartridge loaded then come from one table by construction.

    Until #374 all three callers named a tileset in code instead: ch02 and ch04
    `WINTER_TILESET` outright, ch05 a `CH05_TILESET` constant, which is the same hardcode
    wearing a better name. Every one was CORRECT, because those chapters are those tilesets
    today -- and `check_documented_tileset` could not have caught them if they stopped being,
    since it compares the chapter YAML against the sidecar and neither of those is what these
    sites were reading. A right answer for a wrong reason, which is the shape #371 set out to
    close (`decisions.md` -> "A map's tileset has one home").
    """
    import map_tileset_tool as mt
    with open(_layout_sidecar(maps_dir, layout[1]), encoding='utf-8') as f:
        name = map_tileset(json.load(f))
    return mt._tileset_from_dir(os.path.join(maps_dir, 'tilesets', name))
WINTER_TEST_LAYOUT = ('ChTestSnowMap', 'ch-test-snowfield')  # (asset label, campaign source stem)


    # A tileset .gbapal is TWO sets of five banks, not ten independent ones. DisplayBmTile
# (bmmap.c) draws a VISIBLE tile from BG palette bank 6 and a FOGGED tile from bank 11,
# and UnpackChapterMapPalette loads our ten banks at BG 6..15 -- so banks 0-4 are the lit
# set and banks 5-9 are its fog copy. A vendored community tileset routinely recolours only
# the lit half, because most maps never turn fog on: Snowy Bern's lit half is winter and its
# fog half is still vanilla Bern, which is why ch04's fogged tiles showed the grass we
# winterized away (Nicolas, 2026-07-31). Derive the fog half from OUR lit half rather than
# trusting the vendor's.
#
# `haze` is the lerp-toward-white factor. Vanilla authors each tileset's fog half by hand and
# the direction depends on the setting -- its outdoor palette hazes WHITE (MapPalette1: median
# k = 0.5 measured across all five bank pairs) while interior palettes darken instead. Snow
# under fog is the outdoor case.
TILESET_FOG_HAZE = {'snowy-bern': 0.5}
FOG_BANK_OFFSET = 5             # banks 0-4 lit -> banks 5-9 fog


def derive_fog_banks(palette, haze):
    """Return `palette` (a 320 B .gbapal) with its fog half rebuilt from its lit half.

    Pure, so it is unit-testable without a build. Each lit colour is lerped toward white in
    BGR555 space; index 0 is the transparent/backdrop entry and is carried across untouched
    so the fog copy keeps the same key colour."""
    out = bytearray(palette)
    for bank in range(FOG_BANK_OFFSET):
        for i in range(16):
            lit = struct.unpack_from('<H', palette, bank * 32 + i * 2)[0]
            if i == 0:
                fog = lit
            else:
                ch = [(lit >> s) & 31 for s in (0, 5, 10)]
                ch = [min(31, int(round(c + (31 - c) * haze))) for c in ch]
                fog = ch[0] | (ch[1] << 5) | (ch[2] << 10)
            struct.pack_into('<H', out, (bank + FOG_BANK_OFFSET) * 32 + i * 2, fog)
    return bytes(out)


def _register_tileset(campaign, tileset, label_stem, comment):
    """Copy a vendored tileset's 3 pieces (maps/tilesets/<tileset>/, the
    map_tileset_tool import format) into the decomp, register their incbins in
    CONST_MAPS_S under `comment` + fresh gChapterDataAssetTable slots, and return
    {'obj','pal','cfg'} asset indices. Labels are ObjectType<Stem> /
    MapPalette<Stem> / TileConfiguration<Stem>; gfx + config ride the Makefile
    %.lz rule, the palette stays raw like vanilla MapPaletteN.gbapal."""
    ts_dir = os.path.join(REPO, 'campaigns', campaign, 'maps', 'tilesets', tileset)
    assets = [  # (asset-table label, source ext, incbin ext)
        ('ObjectType%s' % label_stem, '4bpp', '4bpp.lz'),
        ('MapPalette%s' % label_stem, 'gbapal', 'gbapal'),
        ('TileConfiguration%s' % label_stem, 'bin', 'bin.lz'),
    ]
    incbin = ['\n/* %s */' % comment]
    haze = TILESET_FOG_HAZE.get(tileset)
    for label, src_ext, inc_ext in assets:
        src = os.path.join(ts_dir, '%s.%s' % (tileset, src_ext))
        dst = os.path.join(MAP_GFX_DIR, '%s.%s' % (label, src_ext))
        if src_ext == 'gbapal' and haze is not None:
            # Rebuild the fog half from our winterized lit half (see TILESET_FOG_HAZE).
            # Derived at build time, so the vendored .gbapal stays the one source of truth
            # and a future repaint of the lit banks carries into fog for free. Only the COPY
            # changes -- the incbin/label registration below still has to happen, or the
            # asset table references a symbol nothing defines.
            with open(src, 'rb') as f:
                pal = f.read()
            with open(dst, 'wb') as f:
                f.write(derive_fog_banks(pal, haze))
        else:
            shutil.copyfile(src, dst)
        incbin += ['\t.align 2, 0', '\t.global %s' % label, '%s:' % label,
                   '\t.incbin "graphics/map/%s.%s"' % (label, inc_ext)]
    with open(CONST_MAPS_S, 'a', encoding='utf-8') as f:
        f.write('\n'.join(incbin) + '\n')
    # Claimed one by one rather than as a contiguous run: past the table's 8-bit ceiling a
    # piece lands in whatever reclaimed slot is free, so `base + 1` stopped being its palette.
    obj, pal, cfg = _claim_asm_table_words(ASSET_TABLE_S, 'gChapterDataAssetTable',
                                           [a[0] for a in assets])
    return {'obj': obj, 'pal': pal, 'cfg': cfg}


def inject_winter_tileset(campaign, verbose=True):
    """Register the winter tileset (#41) + a flat test layout and repoint the test
    chapter at them, so a build load-tests the tileset in-engine (#40)."""
    maps_dir = os.path.join(REPO, 'campaigns', campaign, 'maps')

    # 1. Tileset pieces -> decomp + asset table (shared path, #40).
    ts_idx = _register_tileset(campaign, WINTER_TILESET, 'Snow',
                               'Manchego Stars winter tileset (#40/#41)')

    # 2. Copy the test layout source (.mar + .json -> Makefile mar_to_map -> .bin -> .lz),
    #    register its incbin + asset-table slot.
    layout_label, stem = WINTER_TEST_LAYOUT
    # The test chapter's asset ids come from the tileset registered just above, while the
    # layout's own sidecar was copied and never read -- the same assumed agreement #374
    # closed at the map-change sites, and here it is load-bearing for what the load test
    # actually proves: a flat field built on some other tileset would render through Snow's
    # tile config and the in-engine check would be vacuous.
    declared = map_tileset(json.load(open(_layout_sidecar(maps_dir, stem), encoding='utf-8')))
    if declared != WINTER_TILESET:
        sys.exit('ERROR: %s.json names tileset %r, but inject_winter_tileset registers %r and '
                 'points the test chapter at it -- the load-test layout must be built on the '
                 'tileset it load-tests' % (stem, declared, WINTER_TILESET))
    for ext in ('mar', 'json'):
        shutil.copyfile(os.path.join(maps_dir, '%s.%s' % (stem, ext)),
                        os.path.join(MAP_LAYOUT_DIR, '%s.%s' % (layout_label, ext)))
    with open(CONST_MAPS_S, 'a', encoding='utf-8') as f:
        f.write('\n'.join([
            '', '/* Manchego Stars winter test layout (#40/#41) */',
            '\t.align 2, 0', '\t.global %s' % layout_label, '%s:' % layout_label,
            '\t.incbin "graphics/map/layout/%s.bin.lz"' % layout_label]) + '\n')
    layout_idx, = _claim_asm_table_words(ASSET_TABLE_S, 'gChapterDataAssetTable',
                                         [layout_label])

    # 3. Repoint the TEST chapter (the inject_test_chapter target) at the winter tileset
    #    + flat layout. obj2/anim/changes off -> the flat field needs none.
    with open(CHAPTER_SETTINGS_JSON, encoding='utf-8') as f:
        settings = json.load(f)
    cmap = settings['chapters'][TEST_CHAPTER_INDEX]['map']
    cmap.update({'obj1Id': ts_idx['obj'], 'obj2Id': 0,
                 'paletteId': ts_idx['pal'], 'tileConfigId': ts_idx['cfg'],
                 'mainLayerId': layout_idx, 'objAnimId': 0, 'paletteAnimId': 0,
                 'changeLayerId': 0})
    with open(CHAPTER_SETTINGS_JSON, 'w', encoding='utf-8') as f:
        json.dump(settings, f, indent=2)

    if verbose:
        print('  %s tileset -> asset table [%d..%d]; test chapter (idx %d) repointed'
              % (WINTER_TILESET, ts_idx['obj'], layout_idx, TEST_CHAPTER_INDEX))


# Vendored tileset -> _register_tileset label stem. A chapter map's tileset comes
# from its layout .json (stamped by the editor-export/import pipeline), so the map
# can never silently register against the wrong tileset's gfx/palette/terrain.
# 'port-or-town-winter' is ch05's (#25). The stem is claimed here so _register_chapter_map
# resolves it; the _register_tileset call that actually writes the asset entries lands with
# inject_ch05, the same way 'Cave' rides inject_ch03.
TILESET_STEMS = {'snowy-bern': 'Snow', 'cave-interior': 'Cave',
                 'port-or-town-winter': 'PortTown',
                 # ch06's chapter-local variant: snowy-bern's geometry with a colder palette
                 # and ch06's own metatiles in slots snowy-bern leaves unused. It needs its OWN
                 # asset-table entry rather than riding 'Snow' -- same tiles, different palette,
                 # so sharing Snow's slot would draw ch06 in ch04's colours (and vice versa).
                 'snowy-bern-ice': 'SnowIce'}


def _register_chapter_map(maps_dir, layout, comment):
    """Copy a painted chapter layout (maps/<stem>.{mar,json}) into the decomp, register
    its incbin in CONST_MAPS_S under `comment` + a fresh gChapterDataAssetTable slot,
    and return the (obj, pal, cfg, layout) asset indices for the layout's OWN tileset
    (read from its .json; absent = the legacy snowy-bern maps). The tileset must
    already be registered -- Snow rides inject_winter_tileset, Cave lands with the
    ch03 injector; an unregistered label sys.exits by name in _asm_table_word_index."""
    label, stem = layout
    for ext in ('mar', 'json'):
        shutil.copyfile(os.path.join(maps_dir, '%s.%s' % (stem, ext)),
                        os.path.join(MAP_LAYOUT_DIR, '%s.%s' % (label, ext)))
    with open(_layout_sidecar(maps_dir, stem), encoding='utf-8') as f:
        tileset = map_tileset(json.load(f))
    if tileset not in TILESET_STEMS:
        sys.exit('ERROR: %s.json names tileset %r -- add it to TILESET_STEMS and '
                 'register it (_register_tileset) first' % (stem, tileset))
    ts = TILESET_STEMS[tileset]
    with open(CONST_MAPS_S, 'a', encoding='utf-8') as f:
        f.write('\n'.join([
            '', '/* %s */' % comment,
            '\t.align 2, 0', '\t.global %s' % label, '%s:' % label,
            '\t.incbin "graphics/map/layout/%s.bin.lz"' % label]) + '\n')
    layout_idx, = _claim_asm_table_words(ASSET_TABLE_S, 'gChapterDataAssetTable', [label])
    obj_idx = _asm_table_word_index(ASSET_TABLE_S, 'gChapterDataAssetTable',
                                    'ObjectType%s' % ts)
    pal_idx = _asm_table_word_index(ASSET_TABLE_S, 'gChapterDataAssetTable',
                                    'MapPalette%s' % ts)
    cfg_idx = _asm_table_word_index(ASSET_TABLE_S, 'gChapterDataAssetTable',
                                    'TileConfiguration%s' % ts)
    return obj_idx, pal_idx, cfg_idx, layout_idx


METATILES_PER_ROW = 32          # tileset atlas stride, for reading a drawn multi-tile block


def _drawn_block(tileset, origin, size, terrain_name, what):
    """The `size`-shaped run of metatiles starting at `origin`, checked to be real art of the
    right terrain -- for a map change that must draw a STRUCTURE rather than a repeated tile.

    `_snowy_metatile_for` resolves one terrain to one metatile, which is all a door or a bridge
    needs. A ruined building is a picture: six adjacent metatiles the tileset artist drew to fit
    together, and picking "the lowest painted ruins tile" six times would tile one corner across
    the whole footprint. So the origin is named, and then VERIFIED -- every cell must carry
    `terrain_name` and be painted, which is what turns a renumbered tileset into a loud build
    failure instead of a silently wrong picture (#205's lesson, kept)."""
    want = terrain_ids()[terrain_name]
    width, height = size
    tiles = [origin + row * METATILES_PER_ROW + col
             for row in range(height) for col in range(width)]
    for m in tiles:
        if tileset.terrain(m) != want:
            sys.exit('ERROR: %s expects %s across %dx%d from metatile %d, but %d carries '
                     'terrain 0x%02x -- the tileset was renumbered, so re-pick the origin'
                     % (what, terrain_name, width, height, origin, m, tileset.terrain(m)))
        if _is_blank_metatile(tileset, m):
            sys.exit('ERROR: %s writes blank metatile %d (a declared-but-unpainted tile renders '
                     'as a solid block)' % (what, m))
    return tiles


def _is_blank_metatile(tileset, metatile):
    """True if a metatile is a single flat colour -- i.e. DECLARED in the terrain table but never
    painted. snowy-bern has one of these on TERRAIN_BRIDGE_SNAG, and writing it into a map change
    put a black square in the river while every terrain byte read correctly (#214)."""
    return len(set(tileset.metatile_image(metatile).convert('RGB').getdata())) <= 1


def _snowy_metatile_for(tileset, terrain_name, prefer=None):
    """The lowest PAINTED metatile carrying `terrain_name` (or `prefer` if it qualifies).

    Map-change tiles are chosen by the TERRAIN they must produce, not copied as numbers: the
    reskin renumbers everything, so a hardcoded metatile is a stale tile waiting to happen (#205
    is the whole cautionary tale). Blank metatiles are skipped -- a tileset can carry a terrain id
    on an unpainted tile, and the terrain byte alone reads as correct while the map shows a hole.
    Fails loudly if the tileset cannot express the terrain with real art."""
    want = terrain_ids()[terrain_name]
    if (prefer is not None and tileset.terrain(prefer) == want
            and not _is_blank_metatile(tileset, prefer)):
        return prefer
    for m in range(1024):
        if tileset.terrain(m) == want and not _is_blank_metatile(tileset, m):
            return m
    sys.exit('ERROR: the tileset has no PAINTED metatile carrying %s -- a map change needs one '
             '(a declared-but-unpainted tile renders as a solid block)' % terrain_name)


def terrain_ids():
    """{TERRAIN_NAME: id} from the decomp's own enum at HEAD -- so a terrain is named, never a
    bare number, and the names track the decomp rather than a copy of it."""
    return {name: int(value, 0) for name, value in re.findall(
        r'(TERRAIN_[A-Z0-9_]+)\s*=\s*(0[xX][0-9A-Fa-f]+|\d+)',
        vanilla_decomp_text('include/constants/terrains.h'))}


def _read_map_metatile(maps_dir, stem, x, y):
    """Return the metatile index painted at (x, y) on a compiled .mar layout. compile_layout
    stores each cell as metatile<<5 with no header (map_tileset_tool), row-major over the
    width from the paired .json -- so reading the door's OPEN tile off the map itself tracks
    any re-retile (no hand-copied tile numbers to drift)."""
    with open(_layout_sidecar(maps_dir, stem), encoding='utf-8') as f:
        w = json.load(f)['width']
    with open(os.path.join(maps_dir, stem + '.mar'), 'rb') as f:
        mar = f.read()
    return struct.unpack_from('<H', mar, (y * w + x) * 2)[0] >> 5


def map_changes_asm(symbol, changes):
    """The per-chapter MapChange array, for any chapter that flips tiles (#23 ch03 chests/doors,
    #214 ch04's snag + visited village).

    FE8 flips tiles through a per-chapter MapChange array: a chest runs
    CallChestOpeningEvent(GetMapChangeIdAt(x, y), item), a door CallTileChangeEvent(...)
    (eventinfo.c), and a destroyed obstacle -- a SNAG -- ApplyMapChangesById(GetMapChangeIdAt(...))
    from UpdateObstacleFromBattle (bmbattle.c). All three find the change whose region covers the
    tile and write its tiles into gBmMapBaseTiles. Lookup is by POSITION, so one array serves every
    kind and ids only need to stay unique.

    `changes` = [(x, y, w, h, [metatile, ...], why), ...] in ROW-MAJOR order per region.

    struct MapChange { s8 id; u8 xOrigin, yOrigin, xSize, ySize; u8 pad[3]; const void* data; }
    (12 B; data at 0x08). Tile data is metatile<<2 (the gBmMapBaseTiles encoding). The array
    terminates on id < 0. The caller registers `symbol` as a fresh gChapterDataAssetTable word and
    points the host slot's map.changeLayerId at it (_inject_tile_changes)."""
    lines = ['', '/* Manchego Stars %s */' % symbol,
             '\t.align 2, 0', '\t.global %s' % symbol, '%s:' % symbol]
    blobs = []
    for mid, (x, y, w, h, tiles, why) in enumerate(changes):
        if len(tiles) != w * h:
            sys.exit('ERROR: map change %d at (%d, %d) is %dx%d but carries %d tiles'
                     % (mid, x, y, w, h, len(tiles)))
        sym = '%s_tiles_%d' % (symbol, mid)
        lines.append('\t.byte %d, %d, %d, %d, %d, 0, 0, 0 /* %s */\n\t.word %s'
                     % (mid, x, y, w, h, why, sym))
        blobs.append('%s:\n%s' % (sym, '\n'.join(
            '\t.hword %d /* metatile %d */' % (m << 2, m) for m in tiles)))
    lines.append('\t.byte -1, 0, 0, 0, 0, 0, 0, 0 /* terminator (id < 0) */\n\t.word 0')
    return '\n'.join(lines + blobs)


def _inject_tile_changes(symbol, changes, host_index):
    """Emit `changes` as `symbol`, register it in gChapterDataAssetTable and point host slot
    `host_index` at it (GetChapterMapChangesPointer -> gChapterDataAssetTable[changeLayerId],
    chapterdata.c). Must run AFTER _retarget_host_chapter, which zeroes changeLayerId."""
    with open(CONST_MAPS_S, 'a', encoding='utf-8') as f:
        f.write(map_changes_asm(symbol, changes) + '\n')
    idx, = _claim_asm_table_words(ASSET_TABLE_S, 'gChapterDataAssetTable', [symbol])
    with open(CHAPTER_SETTINGS_JSON, encoding='utf-8') as f:
        settings = json.load(f)
    settings['chapters'][host_index]['map']['changeLayerId'] = idx
    with open(CHAPTER_SETTINGS_JSON, 'w', encoding='utf-8') as f:
        json.dump(settings, f, indent=2)
    return idx
