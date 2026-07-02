# Maps & tilesets

Chapter maps are built **decomp-native** — no ROM hex, no FEBuilder patching. A GBAFE map
is 4 data pieces the decomp already wires through `gChapterDataAssetTable`
(`fireemblem8u/data/data_8B363C.s`) and incbins in
`fireemblem8u/data/const_data_chapter_maps.s`:

| Piece | Decomp form | What it is |
|---|---|---|
| **graphics** | `*.4bpp.lz` | the tile sheet (1024 8×8 tiles, 4bpp) |
| **palette** | `*.gbapal` (raw, uncompressed) | 160 colors = 10 banks × 16 (BGR555) |
| **tile config** | `*.bin.lz` | 9216 B = 8192 TSA (1024 metatiles × 4 tiles × 2 B) + 1024 terrain bytes |
| **layout** | `layout/*.bin.lz` | the map: `width, height`, then `w·h` little-endian u16, each = **metatile_index × 4** |

A chapter's `fireemblem8u/src/data/chapter_settings.json` entry holds u8 **indices** into the
asset table (`obj1Id`, `paletteId`, `tileConfigId`, `mainLayerId`, …); jsonproc regenerates
`chapter_settings.h` every build. The layout source is `.mar` + `.json` (FEBuilder export
format the decomp already consumes); `scripts/mar_to_map.py` turns it into `.bin`, then the
Makefile `%.lz` rule compresses it.

`tools/build_campaign.py` injects all of this at build time (the decomp is a submodule whose
edits are build artifacts — never committed). The campaign owns the *sources*; build_campaign
copies them in, appends asset-table entries, and points a chapter at them.

## Layout

```
maps/
  tilesets/<name>/        tileset sources (decomp-format pieces)
    <name>.4bpp           raw 4bpp tile sheet (32768 B)
    <name>.gbapal         raw palette (320 B)
    <name>.bin            raw tile config (9216 B)
  <map-name>.mar          a layout (FEBuilder export; metatile grid)
  <map-name>.json         {"id": "...", "width": W, "height": H}
```

## The shared winter tileset (#41)

`tilesets/snowy-bern/` is **Snowy Bern / Snowy Peaks** (FEUniverse t/7204; credits in
`/CREDITS.md`). It shipped in FEBuilder's format, which is **byte-identical** to the decomp's,
so it dropped in with no grit / Map Hacking Suite recompile:

- `SnowyPalette.bin` → `snowy-bern.gbapal` (raw, as-is)
- `SnowyBern.mapchip_config` → `snowy-bern.bin` (raw, as-is)
- `SnowyBernObj.bin` (GBA-LZ 4bpp) → decompressed to `snowy-bern.4bpp`

`build_campaign.inject_winter_tileset()` registers it as asset-table entries
`ObjectTypeSnow` / `MapPaletteSnow` / `TileConfigurationSnow` and repoints the **test chapter**
(the `inject_test_chapter` target) at it, so `make` + New Game load-tests the tileset in-engine.

## Add a tileset (#40)

Vendor any FEBuilder/FE-Repo-format tileset (a `.mapchip_config` + a 256×256 mode-P
object-palette PNG — the format every FE-Repo tileset ships in) with one command:

```sh
python3 tools/map_tileset_tool.py import <config.mapchip_config> <object-palette.png> \
    campaigns/rime-of-the-frostmaiden/maps/tilesets/<name>
```

The config is byte-identical to the decomp's (copied through, after a palette-bank
sanity check); the PNG packs to `.4bpp` + `.gbapal`. Copy the asset's bundled
`CREDITS.txt` into the tileset dir and add the author to `/CREDITS.md`. If the asset
ships a Tiled test map, vendor that too and verify the import end-to-end:

```sh
python3 tools/map_tileset_tool.py render-tmx tilesets/<name> tilesets/<name>/test-map.tmx out.png
```

`tilesets/cave-interior/` (Cynon's Mineshaft, Gray — Ch3's mine, #23) was vendored this
way; its test-map render is pinned pixel-exact against
`docs/demo/ch03-mineshaft-tileset-demo.png` in `tools/test_map_tileset.py`.

## Add a map (current path)

1. Drop the tileset sources in `tilesets/<name>/` (see **Add a tileset** above, if new).
2. Author a layout in the browser editor (`tools/gen_map_editor.py`):
   - **Reskin flow** (winter chapters): `gen_map_editor.py <VanillaLayout> out.html <dl.json>`
     seeds a winter-reskinned vanilla layout, vanilla map in the reference pane.
   - **Custom-canvas flow** (#40, ch03+): `gen_map_editor.py --tileset=<name> --blank=WxH
     [--fill=N] [--ref=book-map.png] out.html <dl.json>` starts a blank canvas on a vendored
     tileset, with any reference image (e.g. the flattened book-map blockout) in the pane.
     A trailing `seed.mar` arg resumes an existing layout in either flow.
   - Export downloads a layout JSON (stamped with its tileset); `import_map_layout.py`
     compiles it to `<map>.mar` + `<map>.json` and renders a preview on that tileset.
   Hand-encoding, if ever needed: each `.mar` cell is 2 bytes encoding `metatile_index × 32`
   (so `mar_to_map`'s `>>3` yields the `.bin` value `metatile_index × 4`); the `atlas`
   subcommand renders which metatile is which.
3. Register + wire it in `build_campaign.py`: `_register_tileset(campaign, '<name>', '<Stem>', …)`
   once per tileset; per chapter, `_register_chapter_map(maps_dir, layout, comment)` reads the
   tileset from the layout's own `.json` `tileset` stamp (resolved via `TILESET_STEMS`), then
   `_retarget_host_chapter` sets the chapter's `chapter_settings.json` map indices. The winter
   tileset rides `inject_winter_tileset`; `cave-interior` registers with the ch03 injector (#23).
4. `make CAMPAIGN=rime-of-the-frostmaiden fireemblem8.gba` and load-test in mGBA.
