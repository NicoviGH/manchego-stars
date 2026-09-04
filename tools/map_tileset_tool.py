#!/usr/bin/env python3
"""Map tileset helpers (#40 task 2): render a GBAFE tileset's metatiles so maps can
be authored by metatile index, and compile a hand-authored layout grid -> the
FEBuilder-format .mar the decomp build consumes (+ the matching .json); the decomp's
own scripts/mar_to_map.py turns that into the layout .bin at ROM-build time (writing
the .bin directly scrambles the map -- see compile_layout).

A GBAFE tileset is 3 raw pieces (the decomp/FEBuilder format, see maps/README.md):
  <name>.4bpp    1024 8x8 tiles, 4bpp (32768 B)
  <name>.gbapal  160 colors, BGR555 (320 B) = 10 banks x 16
  <name>.bin     tile config: 8192 B TSA (1024 metatiles x 4 tiles x 2 B) + 1024 B terrain

A metatile is 2x2 tiles (16x16 px). A TSA entry is a standard GBA BG map entry:
bits 0-9 tile index, bit 10 hflip, bit 11 vflip, bits 12-15 palette bank.

The layout .bin is: byte width, byte height, then width*height little-endian u16,
each = metatile_index * 4 (verified across vanilla Prologue/Ch1/Ch5X maps).
"""

import glob
import json
import os
import re
import struct
import sys

DEFAULT_TILESET = 'snowy-bern'   # what an absent `tileset` key means (see terrain_impact)
NUM_METATILES = 1024


class Tileset:
    def __init__(self, gfx_path, pal_path, cfg_path):
        # Closed explicitly: a Tileset is built per test and per map change, and leaking three
        # handles each time buried `make test` under 277 ResourceWarnings.
        with open(gfx_path, 'rb') as f:
            self.gfx = f.read()
        with open(pal_path, 'rb') as f:
            pal = f.read()
        with open(cfg_path, 'rb') as f:
            self.cfg = f.read()
        self.palettes = [[self._color(pal, bank * 16 + c) for c in range(16)]
                         for bank in range(10)]

    @staticmethod
    def _color(pal, i):
        v = pal[i * 2] | (pal[i * 2 + 1] << 8)
        return ((v & 31) << 3, ((v >> 5) & 31) << 3, ((v >> 10) & 31) << 3)

    def _tile_px(self, tidx, bank):
        """64 RGB pixels (row-major) of one 8x8 4bpp tile under palette `bank`."""
        base = tidx * 32
        pal = self.palettes[bank if bank < 10 else 0]
        px = []
        for row in range(8):
            for b in range(4):
                byte = self.gfx[base + row * 4 + b]
                px.append(pal[byte & 0xF])
                px.append(pal[byte >> 4])
        return px

    def metatile_image(self, m):
        """16x16 RGB image of metatile `m` (2x2 tiles, order TL,TR,BL,BR)."""
        from PIL import Image
        img = Image.new('RGB', (16, 16))
        for sub in range(4):
            entry = struct.unpack_from('<H', self.cfg, m * 8 + sub * 2)[0]
            tidx = entry & 0x3FF
            hflip = (entry >> 10) & 1
            vflip = (entry >> 11) & 1
            bank = (entry >> 12) & 0xF
            px = self._tile_px(tidx, bank)
            ox, oy = (sub % 2) * 8, (sub // 2) * 8
            for yy in range(8):
                for xx in range(8):
                    sx = 7 - xx if hflip else xx
                    sy = 7 - yy if vflip else yy
                    img.putpixel((ox + xx, oy + yy), px[sy * 8 + sx])
        return img

    def terrain(self, m):
        """The metatile's terrain-type byte (TSA is 8192 B, terrain follows)."""
        return self.cfg[8192 + m]

    def atlas(self, out_path, zoom=2, label=False):
        """Render all 1024 metatiles to a 32x32 grid PNG. label=True overlays the
        metatile index every 4th cell (legible authoring reference)."""
        from PIL import Image, ImageDraw
        cell = 16 * zoom
        img = Image.new('RGB', (32 * cell, 32 * cell), (255, 0, 255))
        for m in range(NUM_METATILES):
            mt = self.metatile_image(m).resize((cell, cell), Image.NEAREST)
            img.paste(mt, ((m % 32) * cell, (m // 32) * cell))
        if label:
            d = ImageDraw.Draw(img)
            for m in range(0, NUM_METATILES, 4):
                d.text(((m % 32) * cell + 1, (m // 32) * cell + 1), str(m),
                       fill=(255, 255, 0))
        img.save(out_path)
        return out_path

    def uniform_candidates(self, min_bright=170, top=20):
        """Most-uniform bright metatiles (low color variance) -> plain ground tiles."""
        import statistics
        out = []
        for m in range(NUM_METATILES):
            px = []
            for sub in range(4):
                e = struct.unpack_from('<H', self.cfg, m * 8 + sub * 2)[0]
                px += self._tile_px(e & 0x3FF, (e >> 12) & 0xF)
            r = [p[0] for p in px]
            g = [p[1] for p in px]
            b = [p[2] for p in px]
            bright = (sum(r) + sum(g) + sum(b)) / (len(px) * 3)
            if bright < min_bright:
                continue
            var = statistics.pvariance(r) + statistics.pvariance(g) + statistics.pvariance(b)
            out.append((round(var, 1), round(bright, 1), m))
        out.sort()
        return out[:top]


def compile_layout(grid, out_bin, map_id, tileset='snowy-bern'):
    """grid = list of rows of metatile indices -> decomp FEBuilder .mar + .json.

    The build runs this .mar through scripts/mar_to_map.py (Makefile %.bin: %.mar),
    which prepends width/height from the .json and emits each tile value >> 3. FE8
    then reads a .bin tile as metatile = value >> 2 (bmmap.c GetTrueTerrainAt). So the
    .mar must carry NO header (mar_to_map adds it) and store each tile as
    metatile_index << 5, so >>3 yields the engine's index<<2. (Writing index*4 + a
    header here scrambles the map: mar_to_map eats the header as a tile and halves the
    magnitudes.)"""
    h = len(grid)
    w = len(grid[0])
    if any(len(row) != w for row in grid):
        sys.exit('ERROR: ragged grid (rows differ in width)')
    if w > 255 or h > 255:
        sys.exit('ERROR: map %dx%d exceeds 255' % (w, h))
    data = bytearray()
    for row in grid:
        for m in row:
            data += struct.pack('<H', m << 5)
    with open(out_bin, 'wb') as f:
        f.write(data)
    with open(os.path.splitext(out_bin)[0] + '.json', 'w') as f:
        json.dump({'id': map_id, 'width': w, 'height': h, 'tileset': tileset}, f)
    return out_bin


def tilesets_are_compatible_variants(maps_root, base, variant):
    """True when ``variant`` is ``base`` plus edits confined to unused slots.

    A metatile index and a terrain byte both live in the `.bin`, and the art lives in the
    `.4bpp`. A variant is safe to inherit a learned reskin, a protected-terrain target or a
    seed `.mar` from its base when, and only when:

      * the `.4bpp` is byte-identical -- so no metatile's ART has moved, and a copied
        metatile costs no new tile ids; and
      * the `.bin` differs ONLY at metatiles the BASE declares unused (`TERRAIN_NONE`).

    That second clause is the campaign rule made mechanical: a variant may ADD into empty
    slots (ch06's snow piles, stamped FOREST, live in `snowy-bern-ice` alone) but may never
    alter a slot the base actually uses -- which is what would silently restyle or re-terrain
    a chapter that already shipped on the base tileset. Palettes are free to differ; that is
    the whole point of a variant.

    Derived rather than declared (`decisions.md` -> "A base-map LABEL is prose -- the donor
    is DERIVED"): compatibility is recomputed from the files every time, so there is no list
    to keep in sync and a future edit that breaks the rule fails loudly instead of quietly.
    """
    if base == variant:
        return True

    def read(name, ext):
        path = os.path.join(maps_root, 'tilesets', name, '%s.%s' % (name, ext))
        if not os.path.exists(path):
            return None
        with open(path, 'rb') as handle:
            return handle.read()

    base_gfx, var_gfx = read(base, '4bpp'), read(variant, '4bpp')
    if base_gfx is None or var_gfx is None or base_gfx != var_gfx:
        return False
    base_cfg, var_cfg = read(base, 'bin'), read(variant, 'bin')
    if base_cfg is None or var_cfg is None or len(base_cfg) != len(var_cfg):
        return False
    if base_cfg == var_cfg:
        return True

    touched = set()
    for offset in range(min(8192, len(base_cfg))):
        if base_cfg[offset] != var_cfg[offset]:
            touched.add(offset // 8)
    for offset in range(8192, len(base_cfg)):
        if base_cfg[offset] != var_cfg[offset]:
            touched.add(offset - 8192)
    # every touched slot must be one the BASE declared unused
    return all(base_cfg[8192 + m] == 0 for m in touched if 8192 + m < len(base_cfg))


def _tileset_from_dir(d):
    name = os.path.basename(d.rstrip('/'))
    return Tileset(os.path.join(d, name + '.4bpp'),
                   os.path.join(d, name + '.gbapal'),
                   os.path.join(d, name + '.bin'))


def _asset_names(decomp_root, vanilla=False):
    """The asset-name table. `vanilla=True` reads HEAD.

    Both callers need a DIFFERENT tree and the difference is load-bearing: an editor listing
    what it can edit must see the maps WE registered (`_register_chapter_map` appends here),
    while a lookup that resolves a VANILLA layout id must not, or our appended entries shift
    the indices it is about to match against vanilla chapter settings."""
    names = []
    if vanilla:
        source = _vanilla_decomp_text(decomp_root, 'data/data_8B363C.s').splitlines()
    else:
        # CURRENT-TREE: the editor must see the maps WE registered -- vanilla's copy would
        # not list our own chapters.
        with open(os.path.join(decomp_root, 'data/data_8B363C.s')) as fh:
            source = fh.readlines()
    for line in source:
        match = re.match(r'\s*\.word\s+(\w+)', line)
        if match:
            names.append(match.group(1))
    return names


def _vanilla_tileconfig_path(decomp_root, layout_name):
    """Return the tile config selected by a vanilla layout's chapter settings."""
    default = os.path.join(decomp_root, 'graphics/map/TileConfiguration1.bin')
    try:
        # BOTH READS COME FROM HEAD, and that is the whole correctness of this function. It
        # says VANILLA, and `_retarget_host_chapter` rewrites host slots in chapter_settings
        # while `_register_chapter_map` appends to the asset table -- so read from the working
        # tree, a vanilla layout name resolves against OUR repointed chapters, silently misses,
        # and falls back to TileConfiguration1 with a warning. `vanilla_layout_data` then
        # decodes metatiles against the wrong TSA. (#300)
        names = _asset_names(decomp_root, vanilla=True)
        layout_id = names.index(layout_name)
        settings = json.loads(
            _vanilla_decomp_text(decomp_root, 'src/data/chapter_settings.json'))
        for chapter in settings['chapters']:
            map_data = chapter.get('map') or {}
            if map_data.get('mainLayerId') == layout_id:
                return os.path.join(decomp_root, 'graphics/map',
                                    names[map_data['tileConfigId']] + '.bin')
    except (OSError, ValueError, KeyError, IndexError):
        pass
    sys.stderr.write('WARN: could not resolve vanilla tile config for %r; '
                     'using TileConfiguration1\n' % layout_name)
    return default


def vanilla_layout_data(decomp_root, layout_name):
    """Return a vanilla layout's dimensions, metatiles, and own terrain table."""
    layout_dir = os.path.join(decomp_root, 'graphics/map/layout')
    with open(os.path.join(layout_dir, layout_name + '.json')) as source:
        layout_info = json.load(source)
    width, height = layout_info['width'], layout_info['height']
    with open(os.path.join(layout_dir, layout_name + '.mar'), 'rb') as source:
        layout = source.read()
    cells = [struct.unpack_from('<H', layout, cell * 2)[0] >> 5
             for cell in range(width * height)]
    with open(_vanilla_tileconfig_path(decomp_root, layout_name), 'rb') as source:
        terrain = source.read()[8192:]
    return width, height, cells, terrain


def preserved_terrain_targets(source_cells, source_terrain, target_tileset, rules, width):
    """Map protected source-terrain cells, rejecting incomplete or invalid variants."""
    protected = rules['preserve_terrain_variants']
    targets = {}
    errors = []
    for cell, source_metatile in enumerate(source_cells):
        terrain = source_terrain[source_metatile]
        if terrain not in protected:
            continue
        target = rules['map'].get(str(source_metatile))
        x, y = cell % width, cell // width
        if target is None:
            errors.append('metatile %d at (%d, %d) has protected terrain 0x%02x '
                          'but no mapping' % (source_metatile, x, y, terrain))
            continue
        target_terrain = target_tileset.terrain(target)
        if target_terrain != terrain:
            errors.append('target metatile %d at (%d, %d) has terrain 0x%02x; '
                          'expected 0x%02x' % (target, x, y, target_terrain, terrain))
            continue
        targets[cell] = target
    if errors:
        raise ValueError('; '.join(errors))
    return targets
def _vanilla_decomp_text(dec, relative_path):
    """Read committed vanilla source, not build-injected worktree output."""
    import subprocess
    # Strip inherited GIT_* vars (GIT_DIR/GIT_INDEX_FILE/GIT_WORK_TREE) so `git -C dec`
    # resolves against dec's own repo. Otherwise, when this runs inside a git hook
    # (e.g. the pre-commit drift check), the ambient GIT_DIR would override -C and
    # point HEAD at the outer repo -- silently falling back to the dirty worktree.
    env = {k: v for k, v in os.environ.items() if not k.startswith('GIT_')}
    try:
        return subprocess.check_output(
            ['git', '-C', dec, 'show', 'HEAD:' + relative_path],
            stderr=subprocess.DEVNULL,
            text=True,
            env=env,
        )
    except (OSError, subprocess.CalledProcessError):
        with open(os.path.join(dec, relative_path)) as f:
            return f.read()


def vanilla_layout_tileset_assets(dec, layout):
    """Return the object, palette, and tile-config assets assigned to ``layout``.

    Asset-table proximity is not authoritative: some layouts reuse an earlier
    tileset instead of the nearest assets in gChapterDataAssetTable. Read both
    sources from vanilla HEAD because campaign injection dirties the decomp.
    """
    import re
    names = []
    for line in _vanilla_decomp_text(dec, 'data/data_8B363C.s').splitlines():
        match = re.match(r'\s*\.word\s+(\w+)', line)
        if match:
            names.append(match.group(1))
    layout_idx = names.index(layout)
    settings = json.loads(_vanilla_decomp_text(
        dec, 'src/data/chapter_settings.json'))
    for chapter in settings['chapters']:
        chapter_map = chapter.get('map') or {}
        if chapter_map.get('mainLayerId') == layout_idx:
            return (names[chapter_map['obj1Id']],
                    names[chapter_map['paletteId']],
                    names[chapter_map['tileConfigId']])
    raise ValueError('no chapter settings use vanilla layout %r' % layout)


# ── FEBuilder/FE-Repo tileset import (#40) ────────────────────────────────────────

CONFIG_SIZE = 9216          # 8192 B TSA + 1024 B terrain -- byte-identical to ours
OBJECT_SHEET_PX = 256       # object PNG: 256x256 mode-P, 4-bit local pixel indices
PALETTE_BANKS = 10          # FE8 map BG palette: 10 banks x 16 (the .gbapal 320 B)
LIT_PALETTE_BANKS = 5       # banks 5-9 are derived fog copies, never TSA authoring banks


def convert_object_png(png_path):
    """FE-Repo object PNG -> (raw 4bpp tile sheet bytes, .gbapal bytes).

    The PNG is 256x256 mode-P: pixel values are the 4-bit within-bank color index
    (0-15); the BANK for each on-screen use comes from the TSA entry's bits 12-15,
    and the PNG's 256-color palette is those banks stacked 16-at-a-time. So the
    sheet packs straight to 4bpp (low nibble = left pixel, GBA order) and the
    palette's first 10 banks (160 colors) quantize RGB888 -> BGR555."""
    from PIL import Image
    img = Image.open(png_path)
    if img.mode != 'P' or img.size != (OBJECT_SHEET_PX, OBJECT_SHEET_PX):
        sys.exit('ERROR: %s must be a %dx%d indexed (mode-P) PNG, got %s %s'
                 % (png_path, OBJECT_SHEET_PX, OBJECT_SHEET_PX, img.mode, img.size))
    px = list(img.getdata())
    if max(px) > 15:
        sys.exit('ERROR: %s has pixel indices > 15 -- not 4-bit local indices '
                 '(re-export from FEBuilder/usenti in the banked mode-P form)'
                 % png_path)
    gfx = bytearray()
    tiles_per_row = OBJECT_SHEET_PX // 8
    for t in range(tiles_per_row * tiles_per_row):
        tx, ty = (t % tiles_per_row) * 8, (t // tiles_per_row) * 8
        for row in range(8):
            base = (ty + row) * OBJECT_SHEET_PX + tx
            for b in range(4):
                left, right = px[base + b * 2], px[base + b * 2 + 1]
                gfx.append(left | (right << 4))
    rgb = img.getpalette()
    rgb = rgb + [0] * (PALETTE_BANKS * 16 * 3 - len(rgb))   # PIL trims short palettes
    pal = bytearray()
    for c in range(PALETTE_BANKS * 16):
        r, g, b = rgb[c * 3], rgb[c * 3 + 1], rgb[c * 3 + 2]
        pal += struct.pack('<H', (r >> 3) | ((g >> 3) << 5) | ((b >> 3) << 10))
    return bytes(gfx), bytes(pal)


def import_febuilder_tileset(config_path, object_png, out_dir):
    """Vendor a community tileset (FEBuilder/FE-Repo format) as decomp-format
    pieces under maps/tilesets/<name>/ (the shape _tileset_from_dir and
    build_campaign's tileset injection consume).

    The .mapchip_config is byte-identical to the decomp tile config (verified on
    Snowy Bern #41 and Cynon's Mineshaft #40) -- copied through. The object PNG
    converts via convert_object_png. Rejects a config whose TSA references a
    palette bank the 10-bank .gbapal can't carry."""
    cfg = open(config_path, 'rb').read()
    if len(cfg) != CONFIG_SIZE:
        sys.exit('ERROR: %s is %d B; a mapchip_config is exactly %d (8192 TSA + '
                 '1024 terrain)' % (config_path, len(cfg), CONFIG_SIZE))
    banks = {struct.unpack_from('<H', cfg, i * 2)[0] >> 12 for i in range(4096)}
    if max(banks) >= PALETTE_BANKS:
        sys.exit('ERROR: %s TSA uses palette bank(s) %s; the FE8 map BG palette '
                 'carries only banks 0-%d' % (config_path,
                                              sorted(b for b in banks
                                                     if b >= PALETTE_BANKS),
                                              PALETTE_BANKS - 1))
    gfx, pal = convert_object_png(object_png)
    name = os.path.basename(out_dir.rstrip('/'))
    os.makedirs(out_dir, exist_ok=True)
    for ext, data in (('bin', cfg), ('4bpp', gfx), ('gbapal', pal)):
        with open(os.path.join(out_dir, '%s.%s' % (name, ext)), 'wb') as f:
            f.write(data)
    return out_dir


def set_metatile_terrain(tileset_dir, metatiles, terrain):
    """Change only the TERRAIN byte of one or more metatiles, leaving the art untouched.

    A metatile carries two independent things: what it looks like (the TSA entries) and
    what it MEANS to movement (the terrain byte after the TSA). Retiling a map to change
    a cell's role therefore repaints art that was already right. ch06's boat outcrops are
    the case that forced this: the donor has impassable village bodies there, we painted
    them walkable, and the fix is one byte per metatile -- no repaint, no .mar edit, and
    the art stays pixel-identical.

    Terrain lives in the SHARED tileset, so this changes the meaning of those metatiles for
    every map riding this tileset. `terrain_impact` reports exactly which cells those are;
    call it before writing, and read what it prints.

    Returns [(metatile, before, after)] for the metatiles that actually changed.
    """
    if not 0 <= terrain <= 0xFF:
        raise ValueError('terrain must be in 0..255')
    name = os.path.basename(tileset_dir.rstrip('/'))
    cfg_path = os.path.join(tileset_dir, name + '.bin')
    with open(cfg_path, 'rb') as source:
        cfg = bytearray(source.read())
    changed = []
    for metatile in metatiles:
        if not 0 <= metatile < NUM_METATILES:
            raise ValueError('metatile must be in 0..%d' % (NUM_METATILES - 1))
        before = cfg[8192 + metatile]
        if before == terrain:
            continue
        cfg[8192 + metatile] = terrain
        changed.append((metatile, before, terrain))
    with open(cfg_path, 'wb') as output:
        output.write(cfg)
    return changed


def terrain_impact(maps_root, tileset, metatiles):
    """Which compiled maps ride `tileset`, and which of their cells use `metatiles`.

    The audit that has to happen BEFORE a terrain byte moves: the byte is shared, so the
    blast radius is every map on the tileset, not the one you had in mind.

    Returns {map_stem: {metatile: [(x, y), ...]}}, maps with no hit omitted.
    """
    out = {}
    for path in sorted(glob.glob(os.path.join(maps_root, '*.json'))):
        stem = os.path.splitext(os.path.basename(path))[0]
        with open(path) as source:
            meta = json.load(source)
        # An ABSENT `tileset` key means snowy-bern -- the repo-wide default (map_donor,
        # import_map_layout, gen_map_editor all spell it `get('tileset', 'snowy-bern')`),
        # and four of our eight maps omit it. Comparing a bare .get() against the name
        # made those four invisible, so a snowy-bern terrain flip would have printed a
        # clean blast radius while silently re-terraining ch00, ch01 and ch02. The whole
        # point of this function is to be believed before a destructive write.
        if meta.get('tileset', DEFAULT_TILESET) != tileset or 'width' not in meta:
            continue
        with open(os.path.join(maps_root, stem + '.mar'), 'rb') as source:
            raw = source.read()
        width, height = meta['width'], meta['height']
        hits = {}
        for index in range(width * height):
            cell = struct.unpack_from('<H', raw, index * 2)[0] >> 5
            if cell in metatiles:
                hits.setdefault(cell, []).append((index % width, index // width))
        if hits:
            out[stem] = hits
    return out


def paint_metatile(tileset_dir, metatile, png_path, bank, terrain=None,
                   write_bank=False):
    """Paint one 16x16 PNG into a vendored tileset without touching shared tiles.

    Every source pixel must already be an exact colour in ``bank``. Existing 8x8
    tiles are reused byte-for-byte; new quadrants claim tile ids that no metatile
    references. The target's terrain byte is preserved unless ``terrain`` is given.
    """
    from PIL import Image

    if not 0 <= metatile < NUM_METATILES:
        raise ValueError('metatile must be in 0..%d' % (NUM_METATILES - 1))
    if not 0 <= bank < LIT_PALETTE_BANKS:
        raise ValueError('lit palette bank must be in 0..%d; banks %d..%d are derived fog copies'
                         % (LIT_PALETTE_BANKS - 1, LIT_PALETTE_BANKS,
                            PALETTE_BANKS - 1))
    if terrain is not None and not 0 <= terrain <= 0xFF:
        raise ValueError('terrain must be in 0..255')

    ts = _tileset_from_dir(tileset_dir)
    source = Image.open(png_path)
    image = source.convert('RGB')
    if image.size != (16, 16):
        raise ValueError('%s must be exactly 16x16, got %s'
                         % (png_path, image.size))

    name = os.path.basename(tileset_dir.rstrip('/'))
    pal_path = os.path.join(tileset_dir, name + '.gbapal')
    with open(pal_path, 'rb') as palette_source:
        palette_blob = bytearray(palette_source.read())
    if write_bank:
        if source.mode != 'P' or max(source.getdata()) > 15:
            raise ValueError('--write-bank needs a mode-P PNG using indices 0..15')
        used_elsewhere = any(
            entry // 4 != metatile
            and struct.unpack_from('<H', ts.cfg, entry * 2)[0] >> 12 == bank
            for entry in range(NUM_METATILES * 4)
        )
        if used_elsewhere:
            raise ValueError('palette bank %d is already used by another metatile' % bank)
        rgb = source.getpalette() or []
        rgb += [0] * (16 * 3 - len(rgb))
        for index in range(16):
            r, g, b = rgb[index * 3:index * 3 + 3]
            struct.pack_into('<H', palette_blob, (bank * 16 + index) * 2,
                             (r >> 3) | ((g >> 3) << 5) | ((b >> 3) << 10))
        source_indices = list(source.getdata())
    else:
        palette_indices = {}
        for index, color in enumerate(ts.palettes[bank]):
            palette_indices.setdefault(color, index)
        missing = sorted(set(image.getdata()) - set(palette_indices))
        if missing:
            raise ValueError('%s uses %d colour(s) outside snowy palette bank %d: %s'
                             % (png_path, len(missing), bank, missing[:4]))
        source_indices = [palette_indices[color] for color in image.getdata()]

    painted = []
    for sub in range(4):
        ox, oy = (sub % 2) * 8, (sub // 2) * 8
        raw = bytearray()
        for y in range(8):
            for x in range(0, 8, 2):
                left = source_indices[(oy + y) * 16 + ox + x]
                right = source_indices[(oy + y) * 16 + ox + x + 1]
                raw.append(left | (right << 4))
        painted.append(bytes(raw))

    cfg = bytearray(ts.cfg)
    gfx = bytearray(ts.gfx)
    referenced = set()
    for entry in range(NUM_METATILES * 4):
        if metatile * 4 <= entry < metatile * 4 + 4:
            continue
        referenced.add(struct.unpack_from('<H', cfg, entry * 2)[0] & 0x3FF)
    free = [tile for tile in range(1024) if tile not in referenced]

    tile_ids = []
    for raw in painted:
        matches = [tile for tile in range(1024)
                   if gfx[tile * 32:(tile + 1) * 32] == raw]
        if matches:
            tile = matches[0]
            if tile in free:
                free.remove(tile)
        else:
            if not free:
                raise ValueError('tileset has no unreferenced 8x8 tile for new art')
            tile = free.pop(0)
            gfx[tile * 32:(tile + 1) * 32] = raw
        tile_ids.append(tile)

    for sub, tile in enumerate(tile_ids):
        struct.pack_into('<H', cfg, metatile * 8 + sub * 2,
                         tile | (bank << 12))
    if terrain is not None:
        cfg[8192 + metatile] = terrain

    with open(os.path.join(tileset_dir, name + '.4bpp'), 'wb') as output:
        output.write(gfx)
    with open(os.path.join(tileset_dir, name + '.bin'), 'wb') as output:
        output.write(cfg)
    if write_bank:
        with open(pal_path, 'wb') as output:
            output.write(palette_blob)
    return tile_ids


def tmx_grid(tmx_path):
    """Metatile grid of a Tiled .tmx (the FE-Repo test-map format: 16px tiles,
    one layer, <tile gid=N/> entries, firstgid=1 -> metatile = gid - 1)."""
    import xml.etree.ElementTree as ET
    root = ET.parse(tmx_path).getroot()
    layer = root.find('layer')
    w, h = int(layer.get('width')), int(layer.get('height'))
    first = int(root.find('tileset').get('firstgid'))
    gids = [int(t.get('gid', first)) for t in layer.find('data').iter('tile')]
    if len(gids) != w * h:
        sys.exit('ERROR: %s layer holds %d tiles; expected %dx%d'
                 % (tmx_path, len(gids), w, h))
    empty = gids.count(0)
    if empty:
        # Tiled writes gid="0" for an EMPTY cell (its map-change layers are full of
        # them); an FE map layer has no empty -- passing it through would index
        # metatile -1 (renders garbage, crashes compile_layout).
        sys.exit('ERROR: %s main layer has %d empty cells (gid 0) -- fill the '
                 'layer before importing' % (tmx_path, empty))
    return [[gids[y * w + x] - first for x in range(w)] for y in range(h)]


def render_grid(ts, grid, out_png, zoom=2):
    """Assemble a metatile grid on tileset `ts` into a PNG (the in-engine look,
    sans sprites) -- the load-test-on-paper for a vendored tileset."""
    from PIL import Image
    cell = 16 * zoom
    h, w = len(grid), len(grid[0])
    img = Image.new('RGB', (w * cell, h * cell))
    for y, row in enumerate(grid):
        for x, m in enumerate(row):
            img.paste(ts.metatile_image(m).resize((cell, cell), Image.NEAREST),
                      (x * cell, y * cell))
    img.save(out_png)
    return out_png


if __name__ == '__main__':
    import argparse
    ap = argparse.ArgumentParser(description=__doc__)
    sub = ap.add_subparsers(dest='cmd', required=True)
    a = sub.add_parser('atlas', help='render the metatile atlas')
    a.add_argument('tileset_dir')
    a.add_argument('out')
    a.add_argument('--label', action='store_true')
    a.add_argument('--zoom', type=int, default=2)
    c = sub.add_parser('candidates', help='list uniform ground-tile candidates')
    c.add_argument('tileset_dir')
    i = sub.add_parser('import', help='vendor an FEBuilder/FE-Repo tileset '
                       '(mapchip_config + object PNG -> decomp pieces)')
    i.add_argument('config', help='the .mapchip_config (9216 B)')
    i.add_argument('object_png', help='the 256x256 mode-P object-palette PNG')
    i.add_argument('out_dir', help='maps/tilesets/<name>/ (dir name = piece stem)')
    r = sub.add_parser('render-tmx', help='assemble a Tiled .tmx on a vendored '
                       'tileset -> PNG (verifies the import end-to-end)')
    r.add_argument('tileset_dir')
    r.add_argument('tmx')
    r.add_argument('out')
    r.add_argument('--zoom', type=int, default=2)
    p = sub.add_parser('paint-metatile', help='paint one 16x16 PNG into a vendored '
                       'tileset using private or byte-identical 8x8 tiles')
    p.add_argument('tileset_dir')
    p.add_argument('metatile', type=int)
    p.add_argument('png')
    p.add_argument('--bank', type=int, required=True)
    p.add_argument('--terrain', type=lambda value: int(value, 0))
    p.add_argument('--write-bank', action='store_true')
    t = sub.add_parser('set-terrain', help='change only the TERRAIN byte of metatiles '
                       '(art untouched); prints the blast radius first')
    t.add_argument('tileset_dir')
    t.add_argument('metatiles', help='comma-separated metatile indices')
    t.add_argument('terrain', type=lambda value: int(value, 0), help='terrain id, e.g. 0x2E')
    t.add_argument('--apply', action='store_true', help='write it (default: report only)')
    args = ap.parse_args()
    if args.cmd == 'import':
        print(import_febuilder_tileset(args.config, args.object_png, args.out_dir))
    elif args.cmd == 'render-tmx':
        ts = _tileset_from_dir(args.tileset_dir)
        print(render_grid(ts, tmx_grid(args.tmx), args.out, zoom=args.zoom))
    elif args.cmd == 'set-terrain':
        wanted = [int(v) for v in args.metatiles.split(',') if v.strip()]
        maps_root = os.path.dirname(os.path.dirname(os.path.abspath(args.tileset_dir)))
        tileset = os.path.basename(args.tileset_dir.rstrip('/'))
        impact = terrain_impact(maps_root, tileset, set(wanted))
        ts_before = _tileset_from_dir(args.tileset_dir)
        for metatile in wanted:
            print('  metatile %4d  terrain 0x%02X -> 0x%02X'
                  % (metatile, ts_before.terrain(metatile), args.terrain))
        for stem, hits in impact.items():
            cells = sum(len(v) for v in hits.values())
            print('  %s: %d cell(s) change meaning' % (stem, cells))
        if not impact:
            print('  no compiled map on this tileset uses them')
        if args.apply:
            for metatile, before, after in set_metatile_terrain(
                    args.tileset_dir, wanted, args.terrain):
                print('  WROTE %4d: 0x%02X -> 0x%02X' % (metatile, before, after))
        else:
            print('  (report only -- pass --apply to write)')
    elif args.cmd == 'paint-metatile':
        print(paint_metatile(args.tileset_dir, args.metatile, args.png,
                             bank=args.bank, terrain=args.terrain,
                             write_bank=args.write_bank))
    else:
        ts = _tileset_from_dir(args.tileset_dir)
        if args.cmd == 'atlas':
            print(ts.atlas(args.out, zoom=args.zoom, label=args.label))
        elif args.cmd == 'candidates':
            for var, bright, m in ts.uniform_candidates():
                print('idx %4d (r%d,c%d) var=%-8s bright=%-6s terrain=0x%02x'
                      % (m, m // 32, m % 32, var, bright, ts.terrain(m)))
