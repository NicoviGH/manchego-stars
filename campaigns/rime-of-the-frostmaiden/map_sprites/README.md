# Map (overworld) sprites

Custom overworld sprites for the cast (issue #38). The build picks files up
automatically — `tools/build_campaign.py:inject_map_sprites` — one character at a time;
a cast member with no file here keeps its stock-class sprite, and stock classes / vanilla
enemies stay untouched.

- `<unit-id>.png`      → **idle** (wait sheet): custom SMS slot + a `GetUnitSMSId` override.
- `<unit-id>_mu.png`   → **hover/selected + walk** (MU sheet, 32×480): a `GetMuImg` override.

Named by YAML id (`braulo.png`, `rootis.png`, …). Each character's chosen **base sprite**
(which vanilla class/monster we reskin) + the edits live in that unit's YAML `art.map_sprite`
block — the per-unit source of truth.

## `cast_palette.png` — the shared cast palette
The custom cast share one bespoke 16-colour palette loaded into their own (campaign-unused)
OBJ bank, so the shared player palette is untouched and the not-yet-custom cast still render
correctly (see `docs/decisions.md` → Art & Audio). **Draw every cast sheet to this palette**
— it's both the injected bank palette and the recolour target for each base. Index 0 = transparent.

## Sheet spec
- **Indexed PNG (mode P), ≤16 colours**, using `cast_palette.png`'s entries; index 0 = transparent.
- **Idle:** a vertical strip of frames — width 16 → 16×16, width 16 / height mult of 32 →
  16×32, width 32 → 32×32. Mirror the donor class's vanilla wait sheet
  (`fireemblem8u/graphics/unit_icon/wait/`).
- **Walk (MU):** 32×480 (15 frames of 32×32), mirroring the donor's vanilla move sheet.
- Validate with `python3 tools/map_sprite_tool.py <file>.png`.
