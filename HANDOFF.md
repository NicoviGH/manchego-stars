# Handoff: Milestone B step 3 DONE & visually confirmed — the 8 classed cast spawn on a real map (vanilla Ch1 stripped to a sandbox), New Game boots straight onto it, and the long-standing portrait mouth-cutout is fixed. Next code step = author real maps/events (Prologue, Ch1) from YAML. Art track (map sprites + battle anims) still entirely vanilla.

**Date:** 2026-06-04
**Session Focus:** Stood up the first in-engine confirmation that names + portraits + classes + stats land together (Milestone B step 3), then fixed the two things that surfaced doing it: the new-game flow dumping you in the prologue + intro reels, and the portrait mouth-cutout/double-mouth.

**Scope of this file:** HANDOFF = the NOW (current state, next steps, blockers), rewritten each session. The **broader/long-term plan = GitHub issues** (milestones M0–M4, the actionable backlog) + `docs/PRD.md` (vision/phased roadmap) + `docs/roadmap.md` (post-MVP Act II–V). Settled decisions = `docs/decisions.md`. (See CLAUDE.md "Current State & Backlog".)

## Accomplished
- **Test-chapter spawn (`build_campaign.py:inject_test_chapter`).** Keeps vanilla **Ch1's map**, guts its scripting to a sandbox: rewrites the player roster (`UnitDef_Event_Ch1Ally`) to the **8 classed cast** (each on its `PORTRAIT_MAP` slot's `CHARACTER_` id so its injected identity shows; `redaCount=0` = static placement at `xPosition/yPosition`; stock per-class loadout via `CLASS_LOADOUT`); replaces the beginning scene with a minimal `LOAD1`/`ENUN`/`ENDA`; empties every per-chapter event list. The vanilla begin scene was deleting our units mid-cutscene → instant lord-death game over; gone now. **No cutscene, no enemies, no objective — a pure look-test; reset when done.**
- **Boot straight to the map (four cuts, each at its source).** A single early `chapterIndex` redirect does NOT work (reset before the world-map wrapper, so the Magvel tour still ran). Final: (1) drop `ProcScr_OpAnim` (boot character-flash attract reel); (2) early-return `gamecontrol.c:GameCtrlStartIntroMonologue` (the "long ago…" crawl); (3) `bmio.c:StartBattleMap` redirect `if (chapterIndex==0) chapterIndex=1` (authoritative map load); (4) gut `prologue-wm.h:EventScrWM_Prologue_Beginning` (`WM_TEXT(0x8DB)` = the nation-by-nation "continent of Magvel" world tour) to a `SKIPWN` no-op. New Game → difficulty → **straight onto the Ch1 map**.
- **Portrait mouth-cutout FIXED (was a known open bug) + the doubled-mouth it exposed.** Grounded in `face.c`: `PutFace80x72_Standard` stamps the mouth window from tileset tiles `0x1C-0x1F`/`0x3C-0x3F`, which `portrait_tool.encode` never fills (→ hole), at the slot's `FaceData.xMouth/yMouth`, which varies per slot (→ mouth one tile off = double). Fixes: `portrait_tool.generate(static_portrait)` pastes the neutral mouth into those tiles (+ all sprite frames for dialogue); `build_campaign.py:patch_portrait_geometry` normalizes every dressed slot's `FaceData` to our uniform bust framing **(xMouth 2, yMouth 6, xEyes 3, yEyes 4)**. **Nicolas confirmed all 10 read clean in mGBA.**

## Current State — what works
- `make CAMPAIGN=rime-of-the-frostmaiden` → ROM where **New Game lands on the Ch1 map with all 8 cast** (Braulo/Marty/Wolfram/Meesmickle/Prof. RBG/Rootis/Sclorbo/Pinky), correct names + portraits (clean mouths) + classes + stats + per-class weapons. Pepperjack/Brie stay name-only (no class yet, by design).
- `make check` clean · `make verify` 0 runaway · `make green` (ROM builds).
- All decomp edits are **restorable build artifacts** (`PATCHED_DECOMP_FILES`): now also `src/portrait_data.c`, `src/bmio.c`, `src/gamecontrol.c`, `src/events/{ch1-eventudefs,ch1-eventinfo,ch1-eventscript,prologue-wm}.h`.

## Conventions to follow (read `decisions.md` → Working Conventions)
- **Single source of truth — link, don't restate.** **Definition of Done:** docs/YAML in the same commit; `Closes #N`; `make check` + `make` green; record dated decisions in `decisions.md`; never commit the `fireemblem8u` submodule pointer.
- When you retire a concept, add its term to `DEAD_CONCEPTS` in `tools/check.py`.
- "Is it clean?" → run `make check`, report the result; don't eyeball.

## Open / deferred
- **The whole test-chapter step is scaffolding.** Authored chapters (real maps/events/objectives from YAML) supersede `inject_test_chapter` and restore the prologue boot — delete/replace it then.
- **brie + pepperjack** — `class: null` (name-only) until their RBG-construct chapters are built.
- **Character-data follow-ups (from step 2):** weapon-rank LEVEL (flat E now), gender/attributes/supports still partly the vanilla slot's.
- **Supports** still point at the vanilla slot's data.

## Artwork — mostly undone (parallel track)
Custom-art lever = portrait **+ map sprite + battle anim** ([[feedback_custom_art_lever]]). Only **busts** exist + are injected (and now render cleanly).
- **Map (overworld) sprites** (#38) — NOT started; units walk as the vanilla slot's sprite.
- **Battle animations** (#39) — NOT started; biggest art lift.
- **Final portrait pass** (#35) — busts are 10/10 on framing + mouths; chibi (menu mini-face) still a naive crop (`_make_chibi`), rough for non-human faces.

## Next Steps (priority)
1. **ART PATH — current focus (Nicolas's call 2026-06-04).** Resume the custom-art track, leveraging the new fast in-game feedback loop (the test-chapter sandbox: New Game → see the cast on the Ch1 map in mGBA in seconds). Busts are done; open art is **map (overworld) sprites (#38)** then **battle animations (#39)** — neither started, no tooling yet (units use the vanilla slot's sprite/anim). One artwork at a time: render → show Nicolas → wait for OK → commit ([[feedback_show_before_committing_art]], [[feedback_custom_art_lever]]).
2. **Real maps from YAML** (queued, not current). Author Prologue (#20) and Ch1 (#21) — real tilemap, unit placements, objective, dialogue — from the chapter YAML; replaces the `inject_test_chapter` sandbox. Event scripting is error-prone; build incrementally and verify each beat in mGBA.
3. **Char-data follow-ups:** real weapon-rank levels, gender/supports from YAML.
4. **Pepperjack/Brie:** pick class + intro when their chapters are built (RBG-construct).

## Blockers
None hard. Real-map authoring needs care (event scripting).

## Build Hygiene
- **Build:** `make clean && make CAMPAIGN=rime-of-the-frostmaiden`. Injection is idempotent (auto-restores patched decomp files), so repeated `make`s are safe.
- **Checks:** `make check` (drift guard) · `make verify` (ROM text). CI runs both + a make-green build (mock baserom).
- **mGBA:** `pkill -9 -i mgba; "/Applications/mGBA.app/Contents/MacOS/mGBA" "$PWD/fireemblem8u/fireemblem8.gba" &` (`open -a mGBA` does NOT reload). Fresh New Game: `rm fireemblem8u/fireemblem8.sav`. With the test chapter active, New Game drops straight onto the Ch1 cast map.
- Build interpreter = brew python@3.12 (numpy/pillow/pyyaml via `setup-toolchain.sh`, which also enables the git hooks). Restore vanilla decomp source: `git -C fireemblem8u checkout <path>`. Never commit the submodule pointer.

## Key Files
- `tools/build_campaign.py` — inject portraits + names + character data + **portrait geometry** + **test-chapter spawn**. Chapter/event authoring (real maps) + map-sprite/battle-anim injection are future.
- `tools/portrait_tool.py` — bust → decomp assets; `generate(static_portrait=True)` now bakes the mouth into the engine's mouth tiles. `tools/ref_to_bust.py` — ref → bust.
- `tools/check.py` (`make check`) · `tools/verify_text.py` (`make verify`).
- `campaigns/rime-of-the-frostmaiden/{pcs,npcs}/*.yaml` — unit data; `portraits/*.png` — busts.
- `docs/decisions.md` — settled decisions (test-chapter spawn, static-portrait mouth/geometry, Class Mapping, Working Conventions). Decomp injection targets (build artifacts): `src/{portrait_data,data_characters,data_classes,bmio,gamecontrol}.c`, `src/events/{ch1-*,prologue-wm}.h`, `texts/texts.txt`.

## Memory
- [[project_manchego_stars]] · [[project_manchego_stars_portrait_pipeline]] · [[manchego-stars-text-terminator-parity]] · [[feedback_anti_drift_conventions]] · [[feedback_portrait_static_no_animation]] · [[feedback_custom_art_lever]] · [[feedback_show_before_committing_art]]

## Standing Rules
Custom art for the 10 named cast; enemies vanilla. Stock FE8 classes/weapons; combat = pure vanilla FE. `make check` + `make` green at session end. Auto-push to main once approved. Don't commit the fireemblem8u submodule pointer.
