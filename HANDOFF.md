# Handoff: **Prologue is PLAYABLE — the deploy-time crash is fixed.**

**Date:** 2026-06-09
**Status:** New Game → boots straight onto our winter Prologue map; Hlin + Scramsax deploy vs
Sephek + 2 guards; clean render, working cursor/terrain window, no garbage band, no crash.
Confirmed in-engine (mGBA) on the full build (no diagnostic flags). Build is green.

---

## What was wrong (the "garbage-band" crash) — now fixed
Root cause, debugger-confirmed: our cast ride **non-LORD-class** vanilla slots, and FE8's
chapter-start cursor centering (`GetPlayerStartCursorPosition`) assumes a deployed LORD. With
none, it deref'd a NULL leader unit → parked the cursor **off-map** → an out-of-bounds terrain
read ran the **Huffman text decoder away into `gBmSt`** → corrupted tiles + soft-lock + a wild
jump. Full debrief + the gdb method: **`docs/decisions.md`** → "Non-LORD-class lords need
engine guards". Durable summary in memory: [[manchego_stars_non_lord_cursor_crash]].

**The fix** (two campaign-agnostic engine guards in `tools/build_campaign.py`, applied every build):
- `_patch_player_start_cursor_guard` — leader-undeployed fallback to the first player unit (the real fix).
- `_patch_terrain_name_guard` — clamps OOB terrain ids (defensive).

**Regression-proofed:** each patch fails the build if the decomp source drifts; `tools/check.py`
(`check_engine_guards_present`, run by `make check`/CI/pre-commit) fails if either guard is removed.

## Prologue architecture (in `build_campaign.py:inject_prologue`)
- Hosts on **chapter 1 / Ch1 event group**, NOT the vanilla prologue slot 0; New Game redirects 0→1
  (`StartBattleMap`). Snow tileset + our `Ch00PrologueMap` layout (15×10), winter reskin.
- Guests ride vanilla slots: Hlin=**Natasha**, Scramsax=**Kyle**, Sephek(boss)=**O'Neill**; rosters,
  names, classes/stats, and the lord-death game-over quote are injected. Beginning scene = bare
  `LOAD1`/`ENUN`/`ENDA` (the engine fix handles camera/cursor centering).

## NEXT STEPS
1. **Commit this** — it finally plays (was held back until it did). Then auto-push to main
   ([[feedback_proactive-push]]). Don't commit the `fireemblem8u` submodule pointer.
2. **Verify the prologue's gameplay**, not just that it renders: DefeatBoss win on Sephek, Hlin's
   lord-death = game over, the 2 guards' AI, item/rank sanity. (Crash is gone; these are untested.)
3. **Dialogue/cutscene pass (#2)** — the ending where Sephek escapes; real death-quote line
   (placeholder `msg 0x0917`).
4. **Clean up diagnostic env flags** in `inject_prologue` (`PROLOGUE_FLAT_MAP`, `PROLOGUE_ALLIES_ONLY`,
   `PROLOGUE_NO_SPRITES`, `PROLOGUE_CAST_SLOTS`, `PROLOGUE_HLIN_CLASS`/`SCRAM_CLASS`) — kept through
   debugging; safe to delete now (or keep `FLAT_MAP`/`NO_SPRITES` as reusable map diagnostics).

## ENVIRONMENT NOTE
Installing `arm-none-eabi-gdb` pulled in Homebrew `python@3.14` and bumped the default `python3`
(no numpy/pillow/pyyaml) — `make` then failed with `No module named 'PIL'`. Restored a working
`python3` (build is green). If `make` ever fails on a missing module again, point `python3` at a
Homebrew interpreter with numpy/pillow/pyyaml (see `tools/setup-toolchain.sh`).

## BUILD / RUN
- Build: `make CAMPAIGN=rime-of-the-frostmaiden fireemblem8.gba` (runs `build_campaign` + decomp make).
- Launch: `pkill -9 -i mgba; rm -f fireemblem8u/fireemblem8.sav; "/Applications/mGBA.app/Contents/MacOS/mGBA" "$PWD/fireemblem8u/fireemblem8.gba" &` then New Game.
- Debug a map/render crash: launch `mGBA -g <rom>`, `arm-none-eabi-gdb -q fireemblem8u/fireemblem8.elf`,
  `target remote :2345`, then a hardware watchpoint on the suspect global (e.g. `watch gBmSt.playerCursor.y`).
  On macOS, capture the emulator screen with `screencapture -x -o out.png` (needs Screen Recording perm).

## KEY FILES
- `tools/build_campaign.py` — `inject_prologue`, `_patch_player_start_cursor_guard`,
  `_patch_terrain_name_guard`, `patch_character_data`, `inject_test_chapter` (proven-clean reference).
- `fireemblem8u/src/bmcamadjust.c` (`GetPlayerStartCursorPosition`), `src/bmmap.c` (`GetTerrainName`).
- `campaigns/rime-of-the-frostmaiden/chapters/ch00-prologue-a-dagger-of-ice.yaml` — design SoT.

## Memory
- [[manchego-stars-project]] · [[manchego_stars_non_lord_cursor_crash]] · [[manchego-stars-winter-reskin]] · [[feedback_use_decomp]]

## Standing Rules
Combat = pure vanilla FE. Maps = winter reskin of vanilla layouts via snowy-bern. Ground engine
claims in the decomp. Engine guards must stay campaign-agnostic. Don't commit the `fireemblem8u`
submodule pointer.
