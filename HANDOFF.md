# Handoff: Map-sprite injection path (#38) BUILT & confirmed in mGBA — each cast member can now wear a custom **idle** overworld sprite distinct from its stock class (per-character `GetUnitSMSId` override + custom SMS slot), validated with throwaway placeholders. Map-sprite art is **two sheets per character, grouped** — idle (wait) + hover/walk (MU) — and **both override paths are now built + proven in mGBA**; battle anims (#39) stay separate. No real map-sprite art exists yet. Next = the art loop only (shared cast palette → Braulo's idle + walk sheets, one character at a time).

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

## Map-sprite scope = TWO sheets per character, grouped (Nicolas's call 2026-06-04) — ENGINE DONE
All overworld sprite art is one deliverable per character; battle anims (#39) are the separate beast. Both override paths are **built + proven in mGBA** (Braulo placeholders: idle = Dancer, hover/walk = Mogall, greys out correctly on Wait). Only the art remains.
- **Idle** = small **wait** sheet (16×48 = 3× 16×16), `GetUnitSMSId` override.
- **Hover/selected + walking** = larger **MU** sheet (`gMuInfoTable` = `unit_icon_move_table[classId-1]`; **32×480 = 15× 32×32**). `GetMuImg` per-character override (proc->unit → custom sheet, reusing the class motion script → graphics-only). Gotcha handled: `StartMu`/`StartMuExt` decompress the sheet *before* setting `proc->unit`, so the patch **reloads the graphics after `proc->unit` is set** (else the override sees no unit and falls back to the class sheet — the "still shows Pirate" bug).
- **Injection:** drop `map_sprites/<id>.png` (idle) and/or `map_sprites/<id>_mu.png` (32×480 walk); `inject_map_sprites` wires each independently, one character at a time. Patched files now also include `src/mu.c`, `src/unit_icon_move_data.c`, `data/const_data_unit_icon_move.s`.

## Next Steps (priority) — only ART left for #38 (process decided; see decisions.md → Art & Audio)
**Approach (Nicolas 2026-06-04):** reskin a **vanilla FE map-sprite base** (NOT downscale generated art — that's mush at 16px). **Programmatic recolour first** (remap base → shared cast palette + light edits → mGBA → Nicolas judges); **fallback = Nicolas hand-edits in LibreSprite** (free). Idle (16×16, 3f) before walk MU (32×32, 15f). I do palette/assembly/injection; the creative pixel pass is the split.

1. **Step 0 — design the shared 16-colour cast palette** (must be fixed UP FRONT — see gotcha below). Union the 8 busts' key hues into 15 slots (index 0 transparent). Draft budget from the bust analysis already run (chroma-key `#00ff00` bg ignored):
   - braulo: orange/red `#e15a2e #c44729 #982724` + grey/white · marty: grey/white + red `#c72624 #891f2b` · meesmickle: black `#1c1b29` + red `#a20f1b #d5101f` · prof-rbg: gold `#cb9d02` + purple `#692977` + green `#4a7c49` · rootis: ice white/blue `#c9d0dc #617292 #1f1743` + cyan · sclorbo: cyan `#60d3db` + cream `#bfb198` · wolfram: brown `#593c2b` + slate greys · pinky: pink `#c25094` + grey.
   - **Fits 15 ≈** 4 neutrals (black, dk-grey, mid-grey, white) shared by all + 3 reds + 3 cool-blues + 1 pink + 1 gold + 1 purple + 1 green + 1 tan/brown. **Tight:** each character gets ~1–2 accent hues; most *shading* rides the shared neutral ramp (normal for FE micro-sprites). Show Nicolas the proposed ramp before building.
2. **Build the recolour tool** — pick Braulo's base (Pirate/Brigand map sprite: axe infantry build), remap its palette → cast palette, emit `map_sprites/braulo.png` (idle) + `braulo_mu.png` (walk) → build → show in mGBA. Iterate; hand off to LibreSprite if recolour alone reads poorly.
3. **Braulo proof, then scale** to the other 7 (marty, meesmickle, prof-rbg, rootis, sclorbo, wolfram, pinky), one at a time, show→OK→commit.
4. **(Queued, not current) Real maps from YAML** — Prologue (#20), Ch1 (#21).

### ⚠️ Palette-sequencing gotcha (decide next session)
The engine swaps ONE shared player palette (`unit_icon_pal_player.agbpal`) for **every** player map sprite. The moment we install the cast palette, the **not-yet-custom** cast (still on vanilla *class* wait sprites) render **off-colour** until their custom sprite exists. Options: (a) design the full palette up front + accept the other 7 look mis-tinted in the test chapter during rollout (fine for a Braulo *proof*); (b) hold the palette swap until enough sprites are done; (c) for the very first proof, recolour Braulo within the *existing* vanilla map palette (limits his colours). Lean (a) for the proof.

## Open / deferred
- **brie + pepperjack** — `class: null` (name-only) until their RBG-construct chapters are built; no map sprite until they have a class.
- Char-data follow-ups (weapon-rank LEVEL, gender/supports from YAML) — unchanged from last session.

## Blockers
None hard. Next is the art loop: design the shared cast palette, build the recolour-from-base tool, prove on Braulo. `map_sprite_tool.py` currently only validates (no recolour/assembly yet).

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
