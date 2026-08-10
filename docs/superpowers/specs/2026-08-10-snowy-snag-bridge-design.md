# Snowy-Bern Downed Snag Bridge Design

**Issue:** #24
**Approved by:** Nicolas, 2026-08-10

## Goal

When the ch04 snag at `(4,8)` is destroyed, replace the current masonry crossing with the
three-metatile downed-log composition used by vanilla FE8 Ch4, winterized for snowy-bern.

## Visual design

The map change keeps vanilla's vertical `7 / 4 / 11` composition while using snowy-bern's
corresponding target slots and terrain:

1. Upper plains metatile: snowy-bern snow with vanilla's lower-edge wood fragments.
2. Center bridge-snag metatile 36: vanilla's fallen-log silhouette over snowy-bern river water.
3. Lower plains metatile: snowy-bern snow with vanilla's upper-edge wood fragments.

All log and debris pixels use the muted brown/gray palette ramp from snowy-bern's upright snag
metatile 35. Vanilla's brighter yellow-brown ramp is not retained. Snow and water remain native
snowy-bern pixels so the result belongs to the surrounding map.

## Asset workflow

Add a reusable metatile-painting operation to `tools/map_tileset_tool.py`. It must update the
tileset through explicit 8x8 tile/TSA data rather than a one-off binary patch. The operation will
support composing the three target metatiles from existing snowy-bern bases plus transplanted,
palette-remapped vanilla wood pixels.

The authored result remains in snowy-bern's three source assets:

- `snowy-bern.4bpp` for changed or newly allocated 8x8 pixel tiles;
- `snowy-bern.bin` for the affected TSA entries while retaining the existing terrain bytes;
- `snowy-bern.gbapal` unchanged unless inspection proves the upright-snag ramp is not already
  available to the target palette bank.

## Runtime wiring

Point `CH04_SNAG_BRIDGE_TILE` at painted `TERRAIN_BRIDGE_SNAG` metatile 36 and remove the masonry
metatile-2 fallback. `ch04_map_changes` continues resolving the three cells by terrain and
position; the content remains campaign-owned and no engine behavior changes.

## Validation

- Unit tests cover the metatile-paint operation, terrain preservation, and binary round-trip.
- Render the completed `7 / 36 / 11` strip at an enlarged nearest-neighbor scale for visual review.
- Confirm metatile 36 is nonblank and all three cells retain plains / bridge-snag / plains terrain.
- Run only the affected ch04 snag scenario; do not run the full local matrix.
- Capture one in-engine frame after the axe lands. Mechanical success is insufficient: Nicolas
  reviews the rendered strip and live frame before merge.

## Non-goals

- No new terrain type, map geometry, palette bank, or engine hook.
- No redraw of the upright snag.
- No unrelated snowy-bern cleanup.
- No changes to ch04's reward, obstacle, or map-change mechanics.
