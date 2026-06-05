# Handoff: Map-sprite ART loop — colour path + every cast member's base sprite are now LOCKED. The custom cast share a bespoke 16-colour palette in their own (campaign-unused) OBJ bank (0xB) so nothing else retints (the old palette-sequencing "gotcha" is gone), and the per-character `GetUnitSpritePalette` hook is built + compile-proven. All 8 classed cast have a chosen vanilla base to reskin (recorded in each unit's YAML `art.map_sprite`). **No real sprite art exists yet** — next = build the recolour tool and produce Braulo's idle (Cyclops → cast palette) as the first in-mGBA proof.

**Date:** 2026-06-05
**Session Focus:** Decided + built the map-sprite COLOUR mechanism (dedicated OBJ bank, not the shared player palette), designed the bespoke cast palette, and ran a full walkthrough with Nicolas to pick each cast member's base sprite.

**Scope of this file:** HANDOFF = the NOW (current state, next steps, blockers), rewritten each session. Broader/long-term plan = GitHub issues (M0–M4) + `docs/PRD.md` + `docs/roadmap.md`. Settled decisions = `docs/decisions.md`.

## Accomplished
- **Colour mechanism = dedicated OBJ bank (Option B), built + compile-proven** (commit `21b1a6c`). A map sprite picks its palette by faction (`GetUnitSpritePalette → bank`); we add a per-character override there (sibling to `GetUnitSMSId`) pointing custom cast at the **purple bank `0xB` / `OBJPAL_UNITSPRITE_PURPLE`**, into which `ApplyUnitSpritePalettes` loads `cast_palette.png`. **Bank 0xB is free in single-player play** — its only consumers are the Light Rune (unused DUMMY item) and the link-arena 4th-player colour (multiplayer only; our ROM is single-player); verified in decomp + web. The shared player palette (blue, 0xC) is untouched → not-yet-custom cast always render correctly (no rollout gotcha). Greying still works (`GetUnitDisplayedSpritePalette` short-circuits acted units to 0xF before our hook). `StartMu` also routes through `GetUnitSpritePalette`, so **one hook covers idle + hover/walk**.
  - `tools/build_campaign.py`: `_read_cast_palette` / `_inject_cast_palette` / `_inject_palette_bank_hook`; emits `gCastMapPalette` + `gMapPaletteOverride` into the kept `.data` file; patches `src/bmudisp.c` (added to `PATCHED_DECOMP_FILES`, git-restored each build). No-op when no sprite assets exist.
  - `docs/decisions.md` → Art & Audio rewritten to the dedicated-bank approach (supersedes the old "modify the shared player palette" plan); `map_sprite_tool.py` docstring updated.
- **Bespoke cast palette designed + approved** (commit `bfe3561`): `campaigns/.../map_sprites/cast_palette.png` (16-colour union of the 8 busts' hues; Nicolas OK'd the swatch). It is BOTH the injected bank palette AND the recolour target for every base.
- **All 8 base sprites picked** (walkthrough w/ Nicolas), recorded in each unit's YAML `art.map_sprite` (per-unit source of truth). Bases chosen for silhouette, decoupled from FE class; depicted weapons are cosmetic (FE weapon economy untouched):

  | Unit | Base | Notes / reskin adds |
  |---|---|---|
  | braulo | **Cyclops** (16×16) | hermit-crab-man: eyestalks, shoulder shell, segmented belly, red; stock axe |
  | marty | **Priest** | mushroom: toadstool cap + scarf; staff matches his twig (mechanically Shaman) |
  | meesmickle | **Mauthedoog** (16×16 quadruped) | cat: ears, red cape, restyle flame-mane, black fur |
  | wolfram | **Berserker** | crystal golem: asymmetric arm = crystal arm, crystal crown, grey stone; stock axe (canon hammer) |
  | prof-rbg | **Peer** | dapper rat: top hat, green rat face/ears, gold coat, **drawn pistol** (gunslinger) |
  | rootis | **Gorgonegg** (egg) | snowman: pinch ovoid into 2 snowballs, coal eyes/buttons, carrot nose |
  | sclorbo | **Civilian_F1** (smaller girl) | frost wraith: ponytail → cyan flame head, fur ruff, add ice staff |
  | pinky | **Manakete_Myrrh** (small dragon) | clockwork rat: **flies (matches Pegasus)**, wings → big pink ears, dragon tail → curly tail, grey metal |

## Current State — what works
- `make CAMPAIGN=rime-of-the-frostmaiden` green; `make check` clean. With no `map_sprites/*.png` sprite assets, the whole map-sprite injection (idle + MU + palette bank) is a clean no-op (cast keep class sprites) — the committed state. Idle (#38), MU (hover/walk), and the palette-bank path are all built + proven in mGBA / compile-proven.
- Portraits/names/classes/stats unchanged.

## Next Steps (priority) — START THE ART-PRODUCTION LOOP
1. **Build the recolour tool** (`map_sprite_tool.py` currently only validates). It should: take a vanilla base wait/MU sheet + `cast_palette.png`, remap the base's palette → the cast palette (nearest-colour), and emit an indexed sheet drawn in the cast ramp. Programmatic recolour first; hand-edit (LibreSprite) is the fallback for the shape adds (eyestalks, ears, etc.) — Nicolas does the creative pixel pass, I do palette/assembly/injection (see decisions.md → Art & Audio process).
2. **Braulo first proof:** recolour the Cyclops idle (16×16) to the cast palette → drop as `map_sprites/braulo.png` → `make` → mGBA → Nicolas judges. Then the shape adds (eyestalks/shell/belly). **Show → wait for OK → commit** (don't auto-commit art).
3. Idle (16×16, 3f) before the walk MU (32×480, 15f) for each character. Then scale to the other 7, one at a time, show→OK→commit.
4. **(Queued, not current)** Real maps from YAML — Prologue (#20), Ch1 (#21).

## Blockers
None hard. The mechanism + palette + base picks are done; next is purely the art-production loop (build recolour tool, prove on Braulo).

## Build Hygiene
- **Build:** `make clean && make CAMPAIGN=rime-of-the-frostmaiden`. Injection idempotent (auto-restores `PATCHED_DECOMP_FILES`, now incl. `src/bmudisp.c`).
- **Checks:** `make check` (drift) · `make verify` (ROM text). Never commit the `fireemblem8u` submodule pointer.
- **mGBA:** `pkill -9 -i mgba; "/Applications/mGBA.app/Contents/MacOS/mGBA" "$PWD/fireemblem8u/fireemblem8.gba" &`. Fresh New Game: `rm fireemblem8u/fireemblem8.sav`.
- **Map-sprite assets:** drop `campaigns/.../map_sprites/<id>.png` (idle) and/or `<id>_mu.png` (32×480 walk), drawn to `cast_palette.png`; validate with `python3 tools/map_sprite_tool.py <file>`. Cleanup: the build copies sheets into `fireemblem8u/graphics/unit_icon/{wait,move}/` as `*manchego*` — remove leftovers there if a placeholder is abandoned.

## Key Files
- `tools/build_campaign.py` — `inject_map_sprites` (idle + MU + cast-palette bank). Patched decomp files: `src/bmunit.c`, `src/mu.c`, `src/bmudisp.c`, `src/unit_icon_wait_data.c`, `src/unit_icon_move_data.c`, `data/const_data_unit_icon_{wait,move}.s`, `include/unit_icon_pointer.h`.
- `tools/map_sprite_tool.py` — sheet validator (recolour helper = TODO, next step).
- `campaigns/rime-of-the-frostmaiden/map_sprites/` — `cast_palette.png` (the ramp + recolour target) + README (spec). Drop sprite assets here.
- Each cast YAML `art.map_sprite` block — per-character base + reskin brief (`pcs/*.yaml`, `npcs/pinky.yaml`).
- `docs/decisions.md` → Art & Audio — map-sprite mechanism + cast-palette/bank + ART process.

## Memory
- [[project_manchego_stars]] · [[feedback_custom_art_lever]] · [[feedback_show_before_committing_art]] · [[feedback_nicolas_not_an_artist]] · [[feedback_collaborative_story_planning]] · [[feedback_handoff_vs_memory]]

## Standing Rules
Custom art for the 10 named cast; enemies vanilla. Stock FE8 classes/weapons; combat = pure vanilla FE. Map-sprite *depicted* weapon is cosmetic (decoupled from class). `make check` + `make` green at session end. Show art → wait for OK → then commit. Auto-push to main once approved. Don't commit the fireemblem8u submodule pointer.
