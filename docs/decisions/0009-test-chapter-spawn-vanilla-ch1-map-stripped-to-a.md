---
id: 9
title: "Test-chapter spawn = vanilla Ch1 map stripped to a sandbox (not a hand-authored chapter)."
date: "2026-06-04"
section: "Engine & Tech Stack"
issues: []
---

# Test-chapter spawn = vanilla Ch1 map stripped to a sandbox (not a hand-authored chapter).

The first in-engine check that names + portraits + classes + stats land together (Milestone B step 3) keeps vanilla Ch1's **map** but guts its scripting, via `build_campaign.py:inject_test_chapter`:
- rewrites the player roster (`UnitDef_Event_Ch1Ally`) to our 8 classed cast (each rides its `PORTRAIT_MAP` slot's `CHARACTER_` id, so its injected name/portrait/class/stats show; `redaCount = 0` places it statically at `xPosition/yPosition`, per `eventscr.c:sub_800F8A8`);
- replaces the **beginning scene** with a minimal `LOAD1`/`ENUN`/`ENDA` (deploy the cast, hand over control). The vanilla scene ran a scripted Breguet fight + forced moves that *deleted our units mid-cutscene* → instant lord-death game over;
- empties every per-chapter event list (turn/character/location/misc/tutorial) so nothing references removed units or fires a win/lose condition.

**Boot straight to the map (four cuts, each at the source that plays it).** A single early hook does *not* work: setting `chapterIndex` at `gamecontrol.c:GameControl_RememberChapterId` gets reset before the world-map wrapper, so the Magvel tour still ran. Each pre-map sequence is therefore cut at its own source:
1. `gamecontrol.c` drops `PROC_START_CHILD_BLOCKING(ProcScr_OpAnim)` — the boot character-flash attract reel;
2. `gamecontrol.c:GameCtrlStartIntroMonologue` early-returns — the "long ago…" lore crawl;
3. `bmio.c:StartBattleMap` redirects `if (chapterIndex == 0) chapterIndex = 1` — the authoritative map load (feeds `InitChapterMap`/fog/weather); `chapterIndex == 0` here can only be a fresh game's prologue (skirmishes use `PLAY_FLAG`s; later chapters nonzero);
4. `prologue-wm.h` guts `EventScrWM_Prologue_Beginning` (it runs `WM_TEXT(0x8DB)`, the nation-by-nation "continent of Magvel" world tour) to a `SKIPWN` no-op — the world-map wrapper runs this *before* (3), so (3) alone can't stop it. Dead ends ruled out: `bmsave.c`'s save field only feeds the title card; `gamecontrol.c:sub_8009C5C` is unreferenced.

Net result: New Game → Ch1 map with the 8 cast, no cutscene, no game over — a pure look-test (no enemies, no objective; reset when done). Test loadouts are stock vanilla weapons by class (`CLASS_LOADOUT`); per-unit YAML inventory is a later pass. All edited decomp files are restorable build artifacts (`PATCHED_DECOMP_FILES`). Authored chapters (real maps/events/objectives from YAML) supersede this whole step.
_Decided: 2026-06-04_

**Static custom portraits need the mouth baked into the engine's mouth tiles + uniform mouth/eye geometry.** Custom busts are non-animated ([[feedback_portrait_static_no_animation]]), but "bake the full face, emit transparent mouth frames" alone leaves a **mouth cutout** (a transparent hole over the mouth) on every portrait. Two decomp facts, both in `face.c`: (a) the status-screen face reader `PutFace80x72_Standard` always draws the 32×16 mouth window from tileset tiles `0x1C–0x1F`/`0x3C–0x3F` (sheet cols 28–31), which `portrait_tool.encode()`'s `OBJECTS` never fill → blank → hole; (b) it draws that window at the slot's `FaceData.xMouth/yMouth`, which varies per vanilla slot. Fixes: `portrait_tool.generate(static_portrait)` now pastes the neutral mouth into tiles `0x1C–0x1F`/`0x3C–0x3F` (and into all sprite frames for dialogue); and `build_campaign.py:patch_portrait_geometry` normalizes every dressed slot's `FaceData` mouth/eye window to our single bust framing (`xMouth 2, yMouth 6, xEyes 3, yEyes 4` — the coords the Eirika/Franz/Vanessa/Neimi slots already used). Without the geometry pass, slots at row 5 (Seth/Gilliam/Moulder/Garcia) or shifted column (Ross/Colm) painted the mouth one tile off → a doubled mouth.
_Decided: 2026-06-04_
