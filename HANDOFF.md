# Handoff: All 8 cast map sprites are reskinned, folded onto their real cast IDs, and **rendering correctly in-game** both **standing AND moving** (test chapter). The cast-palette off-by-one is fixed (pre-rotate). The auto-MU "glide" is now **wired & verified in-game**: a moving unit keeps its custom sprite instead of reverting to the stock class one. Map sprites stay **idle-only by design** (static glide, no walk-cycle). Battle anims (#39) still deferred; Kitsune fox-laguz anim parked for Meesmickle.

**Date:** 2026-06-07
**Session Focus:** Wired **auto-MU-from-idle (the "glide")** — `map_sprite_tool.synth_mu_sheet` builds a 32×480 MU sheet from the finished idle frame (idle pose anchored to the donor's standing MU frame, tiled into all 15 blocks); `build_campaign.inject_map_sprites` auto-synthesizes one per idle cast member at build time (into a temp dir — no derived asset in git; a committed `<id>_mu.png` still wins). Built green, verified all 8 move correctly in mGBA. Also recorded the Act II Ch 10 frozen-wreck beat + reconciled Braulo's "Ole Shipwrecker" (earlier this session).

**Scope of this file:** HANDOFF = the NOW. Long-term plan = GitHub issues (M0–M4) + `docs/PRD.md` + `docs/roadmap.md`. Settled decisions = `docs/decisions.md`. Durable facts = memory (e.g. [[manchego-stars-fe-repo]], [[manchego-stars-use-decomp]]).

## Accomplished (this session)
- **All 8 cast map sprites finished & live in-game** (test chapter, New Game drops straight onto the map). Reskins: marty (mushroom mage), braulo (red hermit-crab brute), wolfram (grey crystal brute), meesmickle (black aristocat + red cape), prof-rbg (purple-hat gunslinger), rootis (snowman), sclorbo (icy flame-spirit), pinky (clockwork rat). Verified visually in mGBA.
- **Palette off-by-one FIXED.** First in-game test showed cast colours shifted by one index (snowman white→yellow, meesmickle cape red→cyan, …). A **rainbow-palette test** + Nicolas's colour-by-colour readout proved it: the engine loads the 16-colour OBJ bank **one slot high** (sprite index `k` rendered cast colour `k-1`). Data (4bpp indices, `gCastMapPalette`, override tables) was all byte-correct — the shift is in the engine load. **Fix:** `build_campaign._read_cast_palette` pre-rotates the palette up by one (`out[1:]+out[:1]`). Recorded in `docs/decisions.md` (don't "un-rotate" `gCastMapPalette`).
- **Folded Finished sandboxes → real cast IDs** + set **geometry-token bases**: braulo/wolfram/meesmickle → `Gargoyle` (32×32), pinky → `Gorgonegg` (16×16); marty (`Civilian_M1`/`Priest`), prof-rbg (`Peer`), rootis (`Gorgonegg`), sclorbo (`Civilian_F1`) unchanged. Each YAML names the real FE-Repo art donor in a comment → `CREDITS.md`.
- **FE-Repo donor mining** (this session's picks, all F2E, credited): wolfram→**Lizardzerker** (Seliost1), meesmickle→**Tiger** (RandomWizard, Squaresoft), pinky→**Rat** (Squaresoft, RandomWizard), prof-rbg→**Cowboy Gun** (MeatofJustice). sclorbo & rootis were reskinned directly on their decomp donors.
- **Auto-MU "glide" wired & verified** — the build now synthesizes a 32×480 MU sheet per cast member from the finished idle frame (`map_sprite_tool.synth_mu_sheet`; idle pose anchored to the donor's standing MU frame, tiled into all 15 blocks), so a moving unit keeps its custom sprite. The idle stays the single source of truth (synth goes to a temp dir, nothing derived in git; a hand-authored `<id>_mu.png` overrides). All 8 verified moving in mGBA.
- **Spawn formation spread** to a centered 4×2 grid (`TEST_SPAWN_POSITIONS` in `build_campaign.py`), was a bottom-right cluster.
- **Kitsune (fox-laguz) battle anim parked** for Meesmickle at `campaigns/.../battle_anims/_parked/meesmickle-kitsune-fox/` (sheets+script+gif+credits) — the closest sleek-quadruped reskin base; no cat/tiger anim exists in the GBAFE community. For #39, deferred.
- **Committed + pushed to main** (`62239bd`); drift check clean; submodule pointer untouched.

## Current State — what works
- `make CAMPAIGN=rime-of-the-frostmaiden` builds green; New Game → test map with all 8 cast in their **correct custom colours**, spread toward centre, keeping their custom sprite both **standing and moving**.
- The map-sprite injection pipeline (`inject_map_sprites` + the SMS/palette overrides in `bmunit.c`/`bmudisp.c`) is **proven end-to-end** for the first time.
- Committed: the 8 cast `<id>.png`, YAML base/donor notes, the off-by-one fix, spread formation, CREDITS, decisions, parked anim. The editor sandboxes (`*-drake`, `*-tiger`, `*-rat`, `*-action`, …) remain **uncommitted scratch** by design.

## Known issues / partial
- The editor's `--extra` action/side sandboxes (32×32) are exploratory; the current engine has no slot for them (only the idle SMS + the synthesized glide MU).
- The glide is a **static** pose (idle-only decision), so movement reads as a slide, not a walk. A real walk-cycle would need hand-authored `<id>_mu.png` sheets (the build already honors a committed one over the synthesized glide). Per-character feet alignment is tunable via `art.map_sprite.glide_nudge` (px, +down) if any unit ever sits high/low.

## Blockers
None hard. Battle anims (#39) need the net-new decomp-native inserter (still unbuilt) — post-MVP/M4.

## Next Steps (priority)
1. **Commit/clean the editor scratch** if desired, or leave as-is (it's gitignored-by-convention working state).
2. (Queued) Real maps/events from YAML — Prologue (#20), Ch1 (#21) — and enemy *injection* (#14/#18 second half) using the #18-validated classes.
3. **Battle-anim pipeline spike (#39):** build the decomp-native inserter, prove it on one reskinned FE-Repo anim (start with the parked Kitsune for meesmickle).

## Build / Run Hygiene
- **Build:** `make CAMPAIGN=rime-of-the-frostmaiden fireemblem8.gba -j$(sysctl -n hw.ncpu)`. **Checks:** `make check` (drift) · `make verify` (ROM text). Never commit the `fireemblem8u` submodule pointer (decomp edits are build artifacts).
- **mGBA:** `pkill -9 -i mgba; rm -f fireemblem8u/fireemblem8.sav; "/Applications/mGBA.app/Contents/MacOS/mGBA" "$PWD/fireemblem8u/fireemblem8.gba" &` then New Game. (Delete the `.sav` for a clean boot.)
- **Editor (still available for tweaks):** `pkill -f map_sprite_editor.py; python3 tools/map_sprite_editor.py --campaign rime-of-the-frostmaiden [--extra uid=Donor[@WxH] ...] --port 8765 --no-browser` then open http://127.0.0.1:8765/.
- **Debugging palettes:** rebuilds shift symbol addresses — re-query `arm-none-eabi-nm fireemblem8.elf | grep gCastMapPalette` before dumping ROM bytes. The rainbow-palette test (distinct hue per index) is the way to read any index/order issue off-screen.

## Key Files
- `campaigns/rime-of-the-frostmaiden/map_sprites/<id>.png` — the 8 finished cast idle sheets (committed). `cast_palette.png` = the shared 16-colour cast palette. `.base/` = gitignored snapshots + `.done` markers.
- `tools/build_campaign.py` — `inject_map_sprites`, `_read_cast_palette` (**off-by-one rotate lives here**), `inject_test_chapter` + `TEST_SPAWN_POSITIONS`.
- `tools/map_sprite_editor.py` / `tools/map_sprite_tool.py` — the editor + recolour/geometry tooling.
- `fireemblem8u/src/bmudisp.c` (`GetUnitSpritePalette` override, `ApplyUnitSpritePalettes` cast-bank load) · `fireemblem8u/src/bmunit.c` (`GetUnitSMSId` override). Build-injected; restored+re-patched each build.
- `docs/decisions.md` → Art & Audio (map-sprite mechanism, **palette off-by-one**, idle-only fold, geometry-token bases).
- `CREDITS.md` — FE-Repo asset authors (per-donor). `campaigns/.../battle_anims/_parked/` — deferred #39 anims.

## Memory
- [[manchego-stars-project]] · [[manchego-stars-fe-repo]] · [[manchego-stars-use-decomp]] · [[feedback_custom_art_lever]] · [[feedback_show_before_committing_art]] · [[feedback_nicolas_not_an_artist]] · [[feedback_handoff_vs_memory]]

## Standing Rules
Custom art for the named cast; enemies vanilla (FE8 classes, #18-validated). Stock FE8 classes/weapons; combat = pure vanilla FE. Map sprites are **idle-only** (static glide synthesized for movement — no walk-cycle). Show art → wait for OK → then commit; editor scratch stays uncommitted until **Finish**ed. Auto-push to main once approved. Don't commit the `fireemblem8u` submodule pointer. Read SMS geometry + anim timing from the decomp, never guess. **`gCastMapPalette` is intentionally rotated +1 — don't "fix" it to match `cast_palette.png` order.**
