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

## Add a map (current path)

1. Drop the tileset sources in `tilesets/<name>/` (if new).
2. Author a layout. Today: a `<map>.mar` + `<map>.json` on that tileset's metatiles. Each
   `.mar` cell is 2 bytes encoding `metatile_index × 32` (so `mar_to_map`'s `>>3` yields the
   `.bin` value `metatile_index × 4`). To see which metatile index is which terrain, render the
   tileset's metatile **atlas** (4bpp + palette + TSA) — see the atlas snippet used to pick the
   snow-ground tile (index 6) for the test field.
3. Register + wire it in `build_campaign.py` (model on `inject_winter_tileset`): copy pieces in,
   append asset-table words, set the chapter's `chapter_settings.json` map indices.
4. `make CAMPAIGN=rime-of-the-frostmaiden fireemblem8.gba` and load-test in mGBA.

**Next (#40 task 2 / #20):** a Tiled `.tmx` → `.bin` converter so real maps (e.g. the Prologue
Bryn Shander street) can be drawn visually instead of hand-encoding `.mar`.
