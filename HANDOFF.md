# Handoff: Map-sprite injection path (#38) BUILT & confirmed in mGBA — each cast member can now wear a custom **idle** overworld sprite distinct from its stock class (per-character `GetUnitSMSId` override + custom SMS slot), validated with a throwaway placeholder. No real map-sprite art exists yet. Next = the actual art loop: design the shared 16-colour cast palette, then Braulo's idle sprite (one character at a time).

**Date:** 2026-06-04
**Session Focus:** Stood up the map-sprite (#38) injection path — the tooling + engine hook that lets a cast member's overworld sprite differ from its class — and proved it in-engine. Decided the colour approach (one shared bespoke cast palette, no palette-bank hacking) after finding the GBA constraints.

**Scope of this file:** HANDOFF = the NOW (current state, next steps, blockers), rewritten each session. The **broader/long-term plan = GitHub issues** (milestones M0–M4) + `docs/PRD.md` (vision/phased roadmap) + `docs/roadmap.md` (post-MVP Act II–V). Settled decisions = `docs/decisions.md`.

## Accomplished
- **Map-sprite injection path (#38), parallel to portraits.** FE8 draws overworld sprites by **class** (`GetUnitSMSId → pClassData->SMSId`), so a class swap would also hit enemies and couldn't separate two cast on one class (Marty & Meesmickle = Shaman). Instead:
  - **`GetUnitSMSId` hook** (`src/bmunit.c`, injected): consults a generic, campaign-agnostic override table (charId→smsId, 0xFFFF-term), else falls back to class sprite. Stock classes + vanilla enemies untouched.
  - **Custom SMS slots** at ids 107+ (classes top out at SMSId 106, verified): new wait-table rows (`src/unit_icon_wait_data.c`) + incbin (`data/const_data_unit_icon_wait.s`) + extern (`include/unit_icon_pointer.h`), built from `campaigns/.../map_sprites/<id>.png` assets. The override table (campaign data) is generated from `PORTRAIT_MAP`; ids are position-stable.
  - **`tools/map_sprite_tool.py`** — validates a sheet (indexed, ≤16 colours, 16×16/16×32/32×32 frame strip).
  - **`tools/build_campaign.py:inject_map_sprites`** — copies sheets + patches the four decomp files; one-artwork-at-a-time (only injects cast who have a `map_sprites/*.png`; no asset → unit keeps class sprite). All five files git-restored each build (idempotent).
- **Validated in mGBA** with a throwaway placeholder (Braulo idling as the Dancer sheet — clearly not his Pirate class sprite). Placeholder since removed; nothing fake committed.
- **Colour approach decided (no palette-bank hack).** Every player map sprite shares ONE 16-colour OBJ palette (`unit_icon_pal_player.agbpal`); sprites can't carry their own. Custom colours = redesign that one shared ramp to **union-cover the cast's hues** (the cast overlaps heavily: reds/blacks/whites/greys, + Rootis ice-blue, Pinky pink, RBG green). `docs/decisions.md` → Art & Audio records this + the scope seam below.

## Current State — what works
- `make CAMPAIGN=rime-of-the-frostmaiden` green; `make check` clean. With **no** `map_sprites/*.png` assets, `inject_map_sprites` is a clean no-op (cast keep class sprites) — the committed state.
- The 8 classed cast still spawn on the Ch1 sandbox (New Game → straight onto the map); portraits/names/classes/stats unchanged from last session.

## Scope seam (important, by design)
The override swaps only the **idle** sprite (the small 16×16 wait sheet). The **hover/selected + walking** sprite is a *separate, larger per-class MU sheet* (`gMuInfoTable[jid]`: standing + 4-dir walk frames) — so a unit idles as its custom sprite but **bounces/walks as its stock class** when you cursor over or move it. Making the MU sheet custom is a bigger asset that overlaps the battle-anim track (#39); deferred. "Idle-custom / class-walk" is the deliberate first cut.

## Next Steps (priority) — the ART loop now that the path exists
1. **Design the shared 16-colour cast map-sprite palette.** Collect each cast member's key hues, pack into 15 usable slots (index 0 transparent) so all 8 idle sprites can draw from it. This becomes the new `unit_icon_pal_player.agbpal` (data swap, no code). Show Nicolas, get OK.
2. **Braulo's idle sprite first** (one character at a time, `[[feedback_custom_art_lever]]`): generate a 16×16 idle from his bust/concept ref within the shared ramp → `campaigns/.../map_sprites/braulo.png` → build → **show Nicolas → wait for OK → commit** (`[[feedback_show_before_committing_art]]`). Then the rest of the cast.
   - **No tooling yet** for ref→16×16 idle sheet (portrait pipeline is 96×80). Need a small generator/downscaler to the wait-sheet layout + shared palette. `tools/map_sprite_tool.py` currently only validates.
3. **(Later) Custom MU sheet** for hover/walk consistency — bigger, overlaps #39.
4. **(Queued, not current) Real maps from YAML** — Prologue (#20), Ch1 (#21); replaces the `inject_test_chapter` sandbox.

## Open / deferred
- **brie + pepperjack** — `class: null` (name-only) until their RBG-construct chapters are built; no map sprite until they have a class.
- Char-data follow-ups (weapon-rank LEVEL, gender/supports from YAML) — unchanged from last session.

## Blockers
None hard. Next is art generation (needs a small idle-sprite tool + Nicolas's per-character sign-off).

## Build Hygiene
- **Build:** `make clean && make CAMPAIGN=rime-of-the-frostmaiden`. Injection idempotent (auto-restores patched decomp files).
- **Checks:** `make check` (drift) · `make verify` (ROM text). Never commit the `fireemblem8u` submodule pointer (all decomp edits are build artifacts).
- **mGBA:** `pkill -9 -i mgba; "/Applications/mGBA.app/Contents/MacOS/mGBA" "$PWD/fireemblem8u/fireemblem8.gba" &`. Fresh New Game: `rm fireemblem8u/fireemblem8.sav`.
- **Map-sprite assets:** drop `campaigns/.../map_sprites/<id>.png` (spec in that dir's README); validate with `python3 tools/map_sprite_tool.py <file>`.

## Key Files
- `tools/build_campaign.py` — `inject_map_sprites` (+ portraits, names, character data, test-chapter spawn). New patched files: `src/bmunit.c`, `src/unit_icon_wait_data.c`, `data/const_data_unit_icon_wait.s`, `include/unit_icon_pointer.h`.
- `tools/map_sprite_tool.py` — wait-sheet validator. `tools/portrait_tool.py` / `ref_to_bust.py` — bust pipeline.
- `campaigns/rime-of-the-frostmaiden/map_sprites/` — drop custom idle sprites here (README = spec).
- `docs/decisions.md` → Art & Audio — map-sprite mechanism, shared-palette colour rule, idle/MU seam.

## Memory
- [[project_manchego_stars]] · [[feedback_custom_art_lever]] · [[feedback_show_before_committing_art]] · [[feedback_nicolas_not_an_artist]] · [[project_manchego_stars_portrait_pipeline]] · [[feedback_handoff_vs_memory]]

## Standing Rules
Custom art for the 10 named cast; enemies vanilla. Stock FE8 classes/weapons; combat = pure vanilla FE. `make check` + `make` green at session end. Auto-push to main once approved. Don't commit the fireemblem8u submodule pointer.
