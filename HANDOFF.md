# Handoff: Map-sprite ART loop now runs in a custom offline pixel editor; the cast donors/recolours are staged and Nicolas is hand-recolouring idles. Big scope cut locked: **idle-only** map sprites (movement auto-derives from the idle — option b), so no hand-authored walk cycles. #18 enemy audit done. Battle-anim (#39) tooling plan settled (decomp-native inserter + FE-Repo reskin bases); not built yet. prof-rbg's gunslinger base **chosen** (FE-Repo "Cowboy Gun" map sprite). **CREDITS.md started.**

**Date:** 2026-06-06
**Session Focus:** Built the in-browser map-sprite editor + the recolour/geometry tooling; locked the idle-only scope decision; completed the #18 enemy-roster audit; evaluated battle-animation tooling (FEBuilder vs decomp-native) and FE-Repo as the reskin-base source; chose prof-rbg's gun donor + started CREDITS.md.

**Scope of this file:** HANDOFF = the NOW. Long-term plan = GitHub issues (M0–M4) + `docs/PRD.md` + `docs/roadmap.md`. Settled decisions = `docs/decisions.md`. Durable facts = memory (e.g. [[manchego-stars-fe-repo]], [[manchego-stars-use-decomp]]).

## Accomplished (this session)
- **`tools/map_sprite_editor.py` — a local, offline, stdlib-only browser pixel editor** (Aseprite-style), the surface Nicolas now uses for all cast map sprites. Multi-character picker; **Idle/Walk toggle** (wait sheet + 32×32 MU sheet in one page); pencil/eraser/fill/eyedropper/pan, zoom, **onion skin**, **donor reference / A-B overlay**, **motion map**, live idle preview, frame timeline, undo/redo, palette locked to `cast_palette.png`. **Save** = local WIP; **Finish** = approved-to-commit (gitignored `.done` marker); **Reset** = revert to the clean-recolour `.base/` snapshot. **Follow-motion** = an edit rides a pixel's movement across frames (offsets measured per-row from each donor; lazy+cached). **Auto-saves before any character/mode switch** (fixed a real data-loss bug), `●` unsaved dot, beforeunload guard. `--extra uid=Donor[@WxH]` adds scratch variants without touching the real cast (currently: `marty-boy`=Civilian_M1, `prof-rbg-man`=Civilian_M2, `pinky-fly`=Manakete_Myrrh@32x32, and `cyclops/berserker/brigand/warrior-action` sandboxes).
- **`tools/map_sprite_tool.py`** gained `recolour` (donor→cast palette, nearest + `d:c` overrides), `preview`, `grid`, `palette`, `setpx`, and **`donor_sms_geometry()` — frame size READ FROM THE DECOMP wait table per donor, never guessed** (a 16×96 sheet is ambiguous; Cyclops/Berserker/Mauthedoog/Manakete_Myrrh are 16×32). `build_campaign.inject_map_sprites` uses it too.
- **Cast palette finalised** (`cast_palette.png`, committed): added a light grey + light tan (repurposed navy + dark-red slots), kept near-black (outlines + Meesmickle). Idle timing/geometry grounded in the decomp (`bmudisp.c` `GetGameClock()%72`).
- **All 8 cast donors recoloured** into neutral starting sheets (idle + walk) with `.base/` reset snapshots (local, uncommitted — in-progress art).
- **#18 enemy-roster audit — done & pushed.** Every enemy `class` across all 9 chapters now maps deterministically to a real `CLASS_*` (rule: `CLASS_`+UPPER, `-`/space→`_`); fixed `wolf`→`mauthedoog`/`gwyllgi` (White Moose flagged for custom art), `knight`→`armor-knight`; bumped boss chapters ch05/ch06 to 9. Counts: `3/10/8/10/8/9/9/9/24`.
- **Battle-anim (#39) tooling evaluated** + **FE-Repo** catalogued as our reskin-base source (see Decisions + memory).

## Decisions locked this session
- **Map sprites are IDLE-ONLY (option b):** Nicolas authors only idle sheets; the movement/MU sheet is **auto-generated from the idle** at build time (units glide in their idle pose). No hand-authored walk cycles. Wire-up deferred until idles are finalised. **Pinky** is the built-in exception — her "idle" is the 32×32 wing-flapping flight (she flaps standing + moving).
- **Battle animations (#39, post-MVP / M4):** author in the standard GBAFE **sheet+script** format and write a **decomp-native build-time inserter** (same pattern as map sprites) — NOT FEBuilder (Windows-only, GUI, edits a built ROM → breaks the reproducible decomp build; keep it only as a reference/preview/validation tool). **Reskin F2E community animations from FE-Repo**, don't draw from scratch. De-risk by proving the pipeline on ONE reskinned anim before mass production.
- **White Moose** (ch05 boss): `gwyllgi` now, custom "moose" art later.

## Current State — what works
- Editor running at **http://127.0.0.1:8765/** (launched `--campaign rime-of-the-frostmaiden` + the four `--extra` sandboxes). All 8 cast + sandboxes load; idle + walk per character.
- `make CAMPAIGN=rime-of-the-frostmaiden` is a clean no-op for map sprites (no `<id>.png` is committed yet), so the build stays green. #18 YAML changes are committed; `make check` clean.
- Recoloured cast sheets + `.base/` + scratch variants are **local/uncommitted by design** (in-progress art; committed per-character when Nicolas hits **Finish**).

## Blockers
None hard. The one real unknown is the **decomp-native battle-anim inserter** (#39) — feasible (format documented, mirrors the map-sprite injector) but net-new tooling; it's post-MVP.

## Next Steps (priority)
1. **prof-rbg gun sandbox is staged — Nicolas reskins it.** Base = FE-Repo **`Cowboy (M) Gun` by MeatofJustice** (F2E), a hatted figure holding a pistol (vanilla FE8 has no gun). It's in the editor picker as **`prof-rbg-gun`** (16×16 idle, neutral recolour, original-cowboy reference underlay). Reskin = make it the dapper rat (green face/ears, gold coat, keep the pistol). When locked: set `pcs/prof-rbg.yaml` `art.map_sprite.base` + confirm the CREDITS line.
2. **Mine the other hard cast cases** from FE-Repo (same flow — preview → pick → `--extra` sandbox): rootis→`Yetizerker`, pinky→`Mech`/flier, braulo→`Oni Chieftain`, marty/sclorbo→Magi shelves, wolfram→crystal-recolour of a Knight/General.
2. **Finish the idle recolours** (Nicolas, in the editor) → **Finish** each → I commit per-character (after a `make` check).
3. **Wire auto-MU-from-idle into `build_campaign`** (the idle-only scope cut) once idles are finalised.
4. **Battle-anim pipeline spike (#39):** build the decomp-native inserter, prove it on one reskinned FE-Repo anim in mGBA.
5. (Queued) Real maps/events from YAML — Prologue (#20), Ch1 (#21); enemy *injection* (the #14/#18 second half) using the now-validated classes.

## Build / Run Hygiene
- **Editor:** `pkill -f map_sprite_editor.py; python3 tools/map_sprite_editor.py --campaign rime-of-the-frostmaiden --extra marty-boy=Civilian_M1 --extra prof-rbg-man=Civilian_M2 --extra "prof-rbg-gun=Cowboy@16x16" --extra "pinky-fly=Manakete_Myrrh@32x32" --extra "cyclops-action=Cyclops@32x32" --extra "berserker-action=Berserker@32x32" --extra "brigand-action=Brigand@32x32" --extra "warrior-action=Warrior@32x32" --port 8765 --no-browser` (then open the URL; `--no-browser` avoids spawning tabs). The `prof-rbg-gun=Cowboy@16x16` extra needs `prof-rbg-gun.png` generated first (Next Steps #1); its underlay comes from `.base/prof-rbg-gun.ref.png` (a non-decomp donor, so geometry is explicit and the ref is the original cowboy).
- **Build:** `make clean && make CAMPAIGN=rime-of-the-frostmaiden`. **Checks:** `make check` (drift) · `make verify` (ROM text). Never commit the `fireemblem8u` submodule pointer.
- **mGBA:** `pkill -9 -i mgba; "/Applications/mGBA.app/Contents/MacOS/mGBA" "$PWD/fireemblem8u/fireemblem8.gba" &`.
- **Committing art:** recolour sheets stay uncommitted until Finished; `.base/` is gitignored.

## Key Files
- `tools/map_sprite_editor.py` — the browser pixel editor (campaign + `--extra` + `--mu`).
- `tools/map_sprite_tool.py` — recolour/preview/grid/setpx + `donor_sms_geometry` (decomp-grounded).
- `tools/build_campaign.py` — `inject_map_sprites` (idle + MU + cast-palette bank), now donor-geometry-grounded.
- `campaigns/rime-of-the-frostmaiden/map_sprites/` — `cast_palette.png` + per-cast `<id>.png`/`<id>_mu.png` (+ `.base/` snapshots, gitignored).
- `campaigns/rime-of-the-frostmaiden/chapters/ch*.yaml` — enemy rosters (post-#18 audit).
- `docs/decisions.md` → Art & Audio — map-sprite mechanism, editor, decomp-grounded geometry/timing, battle-anim plan.
- `CREDITS.md` — running credit list (decomp team, FE-Repo authors incl. MeatofJustice/ObsidianDaddy, AI-art disclosure); align to the community format before distribution.

## Memory
- [[manchego-stars-project]] · [[manchego-stars-fe-repo]] · [[manchego-stars-use-decomp]] · [[feedback_custom_art_lever]] · [[feedback_show_before_committing_art]] · [[feedback_nicolas_not_an_artist]] · [[feedback_handoff_vs_memory]]

## Standing Rules
Custom art for the 10 named cast; enemies vanilla (FE8 classes, #18-validated). Stock FE8 classes/weapons; combat = pure vanilla FE. Map sprites are **idle-only** (movement auto-derived). Show art → wait for OK → then commit; recolour sheets uncommitted until **Finish**ed. Auto-push to main once approved. Don't commit the `fireemblem8u` submodule pointer. Read SMS geometry + anim timing from the decomp, never guess.
