# Handoff: **Refining the Prologue (#20) — crash fixed, now building out the vertical slice.**

**Date:** 2026-06-09
**Focus:** ch00 "A Dagger of Ice" as a playable vertical slice. The deploy-time crash that
blocked everything is **fixed**; New Game boots straight onto the winter map and plays cleanly.
Now working down the slice checklist (objective → cutscenes → dialogue → end-to-end load-test).

**Live checklist = GitHub issue #20** (don't mirror it here). HANDOFF = current state + next steps;
active sub-steps go in TodoWrite ([[feedback_chapter_vertical_slice]]).

---

## Current state (where the slice stands)
- ✅ **Design locked** (ch00 YAML), **map concept** (dead-end alley).
- ✅ **Map built** — `Ch00PrologueMap` (15×10) compiled/registered, Prologue points at it, renders
  clean in-engine (winter reskin via snowy-bern).
- ✅ **Units placed** — Hlin→Natasha, Scramsax→Kyle, Sephek(boss)→O'Neill + 2 guards; classes/
  stats/items/positions + short `fe_name`s; all deploy correctly.
- ✅ **Deploy crash fixed** — non-LORD-class lord → off-map cursor → text-decoder runaway. Engine
  guards in `build_campaign.py` (`_patch_player_start_cursor_guard`, `_patch_terrain_name_guard`),
  regression-guarded by `tools/check.py`. Debrief: `docs/decisions.md` → "Non-LORD-class lords
  need engine guards"; durable note [[manchego_stars_non_lord_cursor_crash]]. Committed (b98290a).
- ⏳ **Objective / cutscenes / dialogue / load-test** — not done (see Next Steps + issue #20).

## Next steps (priority order — the remaining #20 items)
1. **Verify objective + lose condition in-engine** (crash is gone, gameplay untested): does
   DefeatBoss fire when Sephek(O'Neill) dies? Does Hlin's death = game over? Guard AI sane?
   Play it in mGBA. (Quickest path to "is the slice actually winnable".)
2. **Title card** — "A Dagger of Ice".
3. **Cutscenes + dialogue** — opening (cold open / corner Sephek), mid-fight frost line, ending
   (Sephek escapes → hard cut to The Northlook). Dialogue is **co-written with Nicolas**
   ([[feedback_collaborative_story_planning]]), not committed solo. `.ea` + MSG lines.
4. **End-to-end load-test** — New Game → play → win → ending → (ideally) hand to ch01.
5. **Housekeeping**: delete the now-obsolete `PROLOGUE_*` diagnostic env flags in `inject_prologue`
   (kept through debugging; `FLAT_MAP`/`NO_SPRITES` are arguably worth keeping as map diagnostics).
6. _(deferred)_ Placeholder busts for Hlin/Scramsax/Sephek (#19).

## Architecture (in `build_campaign.py:inject_prologue`)
Hosts on **chapter 1 / Ch1 event group** (NOT vanilla prologue slot 0); New Game redirects 0→1 in
`StartBattleMap`. Beginning scene is a bare `LOAD1`/`ENUN`/`ENDA` — the engine cursor guard handles
camera/cursor centering, so cutscene scripting can layer on top. Lord-death game-over quote wired on
Hlin (placeholder `msg 0x0917`). Proven-clean reference to diff against: `inject_test_chapter`.

## Build / run / debug
- Build: `make CAMPAIGN=rime-of-the-frostmaiden fireemblem8.gba` (runs `build_campaign` + decomp make).
  Must end green; `make check` runs the drift guard (incl. the engine-guard presence check).
- Run: `pkill -9 -i mgba; rm -f fireemblem8u/fireemblem8.sav; "/Applications/mGBA.app/Contents/MacOS/mGBA" "$PWD/fireemblem8u/fireemblem8.gba" &` then New Game.
- Debug a map/render crash: `mGBA -g <rom>` + `arm-none-eabi-gdb -q fireemblem8u/fireemblem8.elf`,
  `target remote :2345`, hardware watchpoint on the suspect global (e.g. `watch gBmSt.playerCursor.y`).
  Screen-capture the emulator on macOS: `screencapture -x -o out.png` (needs Screen Recording perm).
- **Env note:** the gdb install bumped Homebrew `python3` to 3.14 (no numpy/pillow/pyyaml), which
  breaks `make` (`No module named 'PIL'`). A working `python3` is restored; if it resurfaces, point
  `python3` at a Homebrew interpreter with the build deps (see `tools/setup-toolchain.sh`).

## Key files
- `tools/build_campaign.py` — `inject_prologue`, the two engine guards, `patch_character_data`.
- `fireemblem8u/src/bmcamadjust.c` (`GetPlayerStartCursorPosition`), `src/bmmap.c` (`GetTerrainName`).
- `campaigns/rime-of-the-frostmaiden/chapters/ch00-prologue-a-dagger-of-ice.yaml` — design SoT.
- `campaigns/rime-of-the-frostmaiden/maps/ch00-prologue.{mar,json}` — the map layout.

## Memory
- [[manchego-stars-project]] · [[manchego_stars_non_lord_cursor_crash]] · [[manchego_stars_text_terminator_parity]] · [[feedback_chapter_vertical_slice]] · [[feedback_collaborative_story_planning]] · [[feedback_use_decomp]]

## Standing rules
Combat = pure vanilla FE. Maps = winter reskin of vanilla layouts via snowy-bern. Story/dialogue =
collaborative with Nicolas (read DM notes + Frostmaiden book). Ground engine claims in the decomp.
Engine guards stay campaign-agnostic. Auto-push to main once green; don't commit the `fireemblem8u`
submodule pointer.
