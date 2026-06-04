# Map (overworld) sprites — `<unit-id>.png`

Custom **idle** overworld sprites for the cast (issue #38). Drop one indexed PNG per
cast member here, named by YAML id (`braulo.png`, `rootis.png`, …). The build picks it
up automatically — `tools/build_campaign.py:inject_map_sprites` gives that unit a custom
SMS slot and a per-character override in `GetUnitSMSId`, so it idles as this sprite while
its stock class and any enemy of that class stay vanilla. Units without a file here keep
their class sprite (so we add art one character at a time).

## Sheet spec
- **Indexed PNG (mode P), ≤16 colours**, index 0 = transparent.
- A **vertical strip of frames**: width 16 → 16×16 frames (most classes), width 16 height
  multiple of 32 → 16×32 (mounted/tall), width 32 → 32×32 (monsters). Mirror the size of
  the donor class's vanilla wait sheet in `fireemblem8u/graphics/unit_icon/wait/`.
- **Palette:** map sprites can't carry their own — every player sprite shares one 16-colour
  ramp (`graphics/unit_icon/palette/unit_icon_pal_player.agbpal`). Draw to the shared **cast
  ramp** (the bespoke union palette), not arbitrary colours. Validate with
  `python3 tools/map_sprite_tool.py <file>.png`.

## Scope
Only the **idle** sprite. The **hover/selected + walking** sprite is the bigger per-class MU
sheet (`gMuInfoTable[jid]`) and is a later art pass (see `docs/decisions.md` → Art & Audio).
