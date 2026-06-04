# Handoff: Map-sprite injection path (#38) BUILT & confirmed in mGBA — each cast member can now wear a custom **idle** overworld sprite distinct from its stock class (per-character `GetUnitSMSId` override + custom SMS slot), validated with a throwaway placeholder. Map-sprite art is now scoped as **two sheets per character, grouped** — idle (wait, done) + hover/walk (MU, engine hook still to build); battle anims (#39) stay separate. No real map-sprite art exists yet. Next = build the MU override path, then the art loop (shared cast palette → Braulo, one character at a time).

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

## Map-sprite scope = TWO sheets per character, grouped (Nicolas's call 2026-06-04)
All overworld sprite art is one deliverable per character; battle anims (#39) are the separate beast.
- **Idle** = small **wait** sheet (16×48 = 3× 16×16), `GetUnitSMSId` override — **DONE/proven** (engine + tooling + mGBA).
- **Hover/selected + walking** = larger **MU** sheet (`gMuInfoTable` = `unit_icon_move_table[classId-1]`; **32×480 = 15× 32×32**). `MuProc` carries `->unit`, and both in-chapter MU draws go through `GetMuImg(proc)` — so one `GetMuImg` override (per-character custom sheet, reusing the class's motion script → graphics-only swap) covers hover + walk. **Engine hook NOT built yet** (scoped; mirror the wait override: a `gMuImgOverride` charId→sheet table + a `GetMuImg` patch + custom `unit_icon_move_manchego_<id>_sheet` incbin). Until then, hover/walk shows the stock class sprite (what you saw revert to Pirate).

## Next Steps (priority)
1. **Build the MU (hover/walk) override engine path** — parallel to the wait path, so the grouped map-sprite *engine* is complete. Patch `GetMuImg` (`src/mu.c`) to consult a per-character `gMuImgOverride` (proc->unit → custom 32×480 sheet), reuse class motion; inject custom MU sheets from `map_sprites/<id>_mu.png`; add `src/mu.c` + `src/unit_icon_move_data.c` + `data/const_data_unit_icon_move.s` to PATCHED_DECOMP_FILES. Validate with a placeholder (Braulo walks as a non-Pirate). *Then both sheets just need art.*
2. **The ART loop** (one character at a time, `[[feedback_custom_art_lever]]`, `[[feedback_show_before_committing_art]]`):
   a. **Shared 16-colour cast palette** — union of the cast's key hues into 15 slots (index 0 transparent); becomes the new `unit_icon_pal_player.agbpal` (data swap, no code). Show Nicolas.
   b. **Braulo first:** his **idle** (16×16) + **MU walk** (15× 32×32) sheets, both in the shared ramp → `map_sprites/braulo.png` + `braulo_mu.png` → build → **show → OK → commit**. Then the rest.
   - **No art-gen tooling yet.** `map_sprite_tool.py` only validates. The portrait pipeline is 96×80 stills; a 15-frame 32×32 **walk cycle** is real animation (hard to auto-gen from a static bust) — the MU art approach itself needs a decision (hand-anim vs adapt a community walk template vs AI-gen frames). Raise with Nicolas before generating.
3. **(Queued, not current) Real maps from YAML** — Prologue (#20), Ch1 (#21); replaces the `inject_test_chapter` sandbox.

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
