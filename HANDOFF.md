# Handoff: Map sprites (#38) are DONE — all 8 cast render correctly **standing and moving** (idle SMS + auto-synthesized "glide" MU; palette off-by-one fixed). **NOW: building real chapters.** First target is the **Prologue (ch00, "A Dagger of Ice")**, which needs a real map. The map path is scoped & tracked: a custom-map/**tileset insertion pipeline (#40)** + a shared **winter tileset (#41)**, both decomp-native. Battle anims (#39) still deferred (parked Kitsune for Meesmickle).

**Date:** 2026-06-07
**Session Focus:** (1) Hardened + verified the auto-MU "glide" (works for any donor incl. 488/504/512 MU sheets). (2) Recorded the Act II Ch 10 frozen-wreck beat + reconciled Braulo's "Ole Shipwrecker" + locked the dragon as Arveiaturace. (3) **Scoped the chapter+map build**: chose the map approach, created issues **#40/#41**, and added the maps decision to `docs/decisions.md`. Ready to execute the map pipeline on a fresh instance.

**Scope of this file:** HANDOFF = the NOW. Long-term plan = GitHub issues (M0–M4) + `docs/PRD.md` + `docs/roadmap.md`. Settled decisions = `docs/decisions.md`. Durable facts = memory.

## ACTIVE WORKSTREAM — Prologue chapter + the map pipeline
Goal: turn ch00 into a real, playable chapter (real map + units + cutscene/dialogue + DefeatBoss objective), then repeat for Ch1+.

**Map approach (decided — see `docs/decisions.md` → Art & Audio "Maps"):** ~8 of 9 MVP maps are snow, so bring in **one community winter tileset** (candidate **Snowy Bern/Peaks**, FEU) and author each layout in **Tiled**. Insertion is **decomp-native** — a GBAFE map = 4 pieces the decomp already wires in `data/const_data_chapter_maps.s` (tile graphics, `.gbapal` palette, `TileConfigurationN.bin.lz` config, `graphics/map/layout/*.bin.lz` layout), and the decomp already ships a Tiled pipeline (`.json/.mar/.bin` in `graphics/map/layout/`). Reuse that for layouts; use grit / the GBAFE Map Hacking Suite only to compile the tileset once. **No ROM hex / FEBuilder.** (We rejected palette-swapping a temperate tileset; ready-made snow town maps don't exist in the FE-Repo or FEU.)

**The chapter machinery is already understood** (no need to re-derive):
- The Prologue has a **native slot** `src/events/prologue-event*.h`. Its objective list `EventListScr_Prologue_Misc` is already `DefeatBoss(EndingScene)` + `CauseGameOverIfLordDies` — i.e. ch00's win/lose for free. `struct ChapterEventGroup PrologueEvents` wires units → beginning/ending scenes → map.
- **Dialogue** = `Text(msgId)` / `Text_BG(...)` macros pointing at `## MSG_<id>` in `texts/texts.txt`. Text injection is proven: `build_campaign.set_message_body` / `inject_names` already overwrite vanilla message slots (that's how cast names work).
- The **test-hijack** `build_campaign.inject_test_chapter` already proves the plumbing (strip cutscenes, empty event lists, minimal beginning scene, skip boot attract / WM intro, redirect to a chapter). Real-chapter injection (#14) reuses these patterns on the Prologue slot instead of Ch1.
- **Hlin = Warrior** (axe; "unarmored veteran, battleaxe/handaxe", book p.23). **Sephek = Myrmidon** (Ice Longsword; undead/cold-regen/fire-vuln are FLAVOR only). Give each an `npcs/` YAML with real class + identity (vanilla portraits for now). Map **Sephek → a boss-flagged enemy slot** (e.g. `CHARACTER_ONEILL`) so `DefeatBoss` just fires; **Hlin → a spare slot**, name injected like the cast.

## Next Steps (priority) — execution order
1. **#41 → start: source/register the winter tileset.** Pull Snowy Bern/Peaks, confirm F2U + credit (→ `CREDITS.md`), compile to the decomp's 4 pieces, confirm it renders.
2. **#40: build the map/tileset insertion pipeline.** Task 1 first = **confirm the decomp's native map build** (`graphics/map/layout/` `.json/.mar/.bin`; how `const_data_chapter_maps.s` + `src/chapterdata.c` pick tileset/palette/config/layout per chapter). Then the `build_campaign` register-tileset + `.tmx`→layout + wire-chapter step; prove with one snow map load-test.
3. **#20 Prologue content** (uses #14 injection on the Prologue slot): `npcs/hlin-trollbane.yaml` + `npcs/sephek-kaltro.yaml`; author `maps/ch00-prologue.tmx` (Bryn Shander street) on the tileset; beginning/ending cutscene + dialogue; turn on DefeatBoss + lose-if-Hlin-dies.
4. Then Ch1+ (#21–#28) repeat. Battle-anim spike (#39) remains post-MVP.

**Dialogue is collaborative** ([[feedback_collaborative_story_planning]]): draft the cold-open from the book (p.21–23) + the ch00 YAML narrative and get Nicolas's line-by-line OK; don't commit final script solo.

## Sources (story) — how to read them
- **DM notes** `References/DungeonMasterNotesIcewindDale.pdf` = **real text** → use `pdftotext` (NOT page-vision). Authority on what the party did; covers our Ch1–7 only.
- **Published Frostmaiden book** `References/icewind-dale-rime-of-the-frostmaidenpdf_compress.pdf` = **image-only scan** → Read-tool PDF vision by page range; **PDF page = printed + 1**. Canonical detail. (See [[feedback_story_sources_of_truth]].)

## Done / what works
- `make CAMPAIGN=rime-of-the-frostmaiden` builds green; New Game → test map with all 8 cast in correct custom colours, custom sprite both standing and moving.
- Map-sprite pipeline (idle SMS + glide MU + palette overrides) proven end-to-end (#38 done).
- Recent commits pushed to main; drift clean; submodule pointer untouched. Editor scratch (`*-action`, `*-tiger`, …) left uncommitted by design.

## Blockers
None hard. #40/#41 are net-new but scoped. Battle anims (#39) need the unbuilt decomp-native anim inserter — post-MVP/M4.

## Build / Run Hygiene
- **Build:** `make CAMPAIGN=rime-of-the-frostmaiden fireemblem8.gba -j$(sysctl -n hw.ncpu)`. **Checks:** `make check` (drift) · `make verify` (ROM text). Never commit the `fireemblem8u` submodule pointer (decomp edits are build artifacts).
- **mGBA:** `pkill -9 -i mgba; rm -f fireemblem8u/fireemblem8.sav; "/Applications/mGBA.app/Contents/MacOS/mGBA" "$PWD/fireemblem8u/fireemblem8.gba" &` then New Game.
- **Commit msgs with body:** write to a temp file + `git commit -F` (heredocs in the Bash tool mangle multi-line `-m`).

## Key Files
- **Maps/chapters:** `data/const_data_chapter_maps.s` (map↔tileset↔palette↔config↔layout wiring) · `graphics/map/layout/` (`.json/.mar/.bin.lz`) · `src/chapterdata.c` (chapter→data) · `src/events/prologue-event{info,script,udefs}.h` (Prologue native slot) · `texts/texts.txt` (dialogue `## MSG_`).
- **Injection tooling:** `tools/build_campaign.py` — `inject_test_chapter` (plumbing template), `set_message_body`/`inject_names` (text), `inject_map_sprites` + `_read_cast_palette` (palette +1 rotate). `tools/map_sprite_tool.py` (`synth_mu_sheet`, `validate_mu_sheet`).
- **Issues:** #40 (map/tileset pipeline) · #41 (winter tileset) · #14 (decomp-native event injection) · #20 (Prologue map+events) · #21–#28 (Ch1–8).
- **Docs:** `docs/decisions.md` → Art & Audio (maps decision, map-sprite mechanism, palette off-by-one) · `CREDITS.md` (asset authors).

## Memory
- [[manchego-stars-project]] · [[manchego-stars-fe-repo]] · [[manchego-stars-use-decomp]] · [[feedback_story_sources_of_truth]] · [[feedback_collaborative_story_planning]] · [[feedback_show_before_committing_art]] · [[feedback_handoff_vs_memory]] · [[project_manchego_stars_shipwreck_encounter]]

## Standing Rules
Custom art for the named cast; enemies vanilla (FE8 classes, #18-validated). Stock FE8 classes/weapons; combat = pure vanilla FE. **Maps = community winter tileset + Tiled, decomp-native (#40/#41); no ROM hex.** Ground FE/map/event mechanics in the decomp, never guess. Story from the DM notes (text) + book (scan), reconciled; dialogue co-written with Nicolas. Show art → wait for OK → then commit. Auto-push to main once approved. Don't commit the `fireemblem8u` submodule pointer. **`gCastMapPalette` is intentionally rotated +1 — don't "fix" it.**
