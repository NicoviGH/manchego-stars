# Handoff: **Refining the Prologue (#20) — crash + sprite done, now win/lose logic.**

**Date:** 2026-06-09
**Focus:** ch00 "A Dagger of Ice" as a playable vertical slice. Crash fixed, map plays clean,
difficulty vanilla-tuned, Hlin's custom sprite wired + approved. **Active task = the lose-condition
decision + wiring** (step 1 below), then in-engine win/lose verification with Nicolas.

**Live checklist = GitHub issue #20.** HANDOFF = current state + next steps; sub-steps -> TodoWrite.

---

## Current state
- ✅ Deploy crash fixed + regression-guarded + documented (`docs/decisions.md` → "Non-LORD-class
  lords need engine guards"; memory [[manchego_stars_non_lord_cursor_crash]]). Plays clean.
- ✅ Map built/rendering; units deploy correctly.
- ✅ Difficulty tuned to vanilla: **Hlin = unpromoted Fighter** (frail Eirika-analog lead),
  **Scramsax = Hero + Steel Sword** (dominant Seth-analog Jeigan), Sephek = Myrmidon L5 boss + 2
  Fighter guards. Diagnostics (`PROLOGUE_*` env flags) removed.
- ✅ **Hlin female-Fighter map sprite — WIRED + approved** (2026-06-09, commit 2b0084f). Renders as
  the woman Fighter, distinct from the male guards, via a new `PROLOGUE_GUEST_SPRITES` guest path in
  `inject_map_sprites` (custom SMS + MU override keyed to `CHARACTER_NATASHA`). Her sheet uses FE8's
  standard player palette, so she's kept out of the cast-palette override — no palette work needed.
  **Full repeatable recipe** (the next guest sprite will reuse it): `docs/decisions.md` → "Guests
  reuse the STANDARD player palette" + memory [[manchego_stars_guest_map_sprite_wiring]].

## NEXT STEPS (priority order)
1. **Lose condition — DECIDE w/ Nicolas, then wire** (active task). Question: just Hlin = game over
   (vanilla lord-only feel), or Hlin AND Scramsax (both `required: true` in ch00 YAML)? Today only
   Hlin's death→game-over quote is wired. Wiring lives in `inject_prologue` (the Ch1 event group:
   `EventListScr_Ch1_Character` / the begin-scene script) — add the death/game-over event(s) for the
   chosen unit(s). Vanilla FE8 reference: a `CauseGameOverIfLordDies`-style check on unit death.
2. **In-engine win/lose verification** (playtest w/ Nicolas): DefeatBoss fires on Sephek? Hlin
   death = game over? Guard AI sane? (Crash is gone; gameplay untested.)
3. **Title card** "A Dagger of Ice".
4. **Cutscenes + dialogue** — opening (cold open / corner Sephek), mid-fight frost line, ending
   (Sephek escapes → hard cut to The Northlook). Co-written w/ Nicolas ([[feedback_collaborative_story_planning]]),
   not committed solo. `.ea` + MSG lines.
5. **Portraits** for Hlin / Scramsax / Sephek — placeholder or vendored from FE-Repo (#19).

## Asset access (IMPORTANT — established pattern)
Pull a specific file from the **Klokinator FE-Repo** by **vendoring** it (same as the snowy-bern
winter tileset) — the repo is **2.3 GB, do NOT submodule it**, and don't claim it's inaccessible
([[feedback_vendor_community_assets]]):
```
gh api "repos/Klokinator/FE-Repo/contents/<url-encoded path>?ref=main" \
  --jq '.[] | select(.name=="<exact filename>") | .download_url'
curl -fsSL "<download_url>" -o campaigns/rime-of-the-frostmaiden/<dir>/<dest>.png
```
Credit the `{Artist}` from the filename in the asset dir's README.

## Build / run / debug
- Build: `make CAMPAIGN=rime-of-the-frostmaiden fireemblem8.gba` (must end green; `make check`
  runs the drift guard incl. `check_engine_guards_present`).
- Run: `pkill -9 -i mgba; rm -f fireemblem8u/fireemblem8.sav; "/Applications/mGBA.app/Contents/MacOS/mGBA" "$PWD/fireemblem8u/fireemblem8.gba" &` then New Game.
- **macOS automation:** synthetic keypresses (osascript) do NOT reach mGBA — Nicolas must drive
  input. Screen-capture works: `screencapture -x -o out.png` (needs Screen Recording perm).
- Debug a map/render crash: `mGBA -g <rom>` + `arm-none-eabi-gdb -q fireemblem8u/fireemblem8.elf`,
  `target remote :2345`, hardware watchpoint on the suspect global (e.g. `watch gBmSt.playerCursor.y`).
- **Env note:** the gdb install bumped Homebrew `python3` to 3.14 (no PIL); restored a working
  `python3`. If `make` dies on a missing module, point `python3` at one with numpy/pillow/pyyaml.

## Key files
- `tools/build_campaign.py` — `inject_prologue`, `inject_map_sprites` (+ `_inject_idle_sprites`,
  `_inject_mu_sprites`, `_inject_cast_palette`), the two engine guards, `patch_character_data`.
- `tools/map_sprite_tool.py` — map-sprite conversion (`synth_mu_sheet`, palette handling).
- `campaigns/rime-of-the-frostmaiden/chapters/ch00-prologue-a-dagger-of-ice.yaml` — design SoT.
- `campaigns/rime-of-the-frostmaiden/map_sprites/hlin-trollbane*.png` — the vendored sprite.

## Memory
- [[manchego-stars-project]] · [[manchego_stars_non_lord_cursor_crash]] · [[manchego_stars_guest_map_sprite_wiring]] · [[feedback_vendor_community_assets]] · [[feedback_chapter_vertical_slice]] · [[feedback_collaborative_story_planning]] · [[reference_fe_repo]]

## Standing rules
Combat = pure vanilla FE. Maps/sprites = vendor + reskin community/vanilla assets (not submodule).
Story/dialogue = collaborative with Nicolas. Engine guards stay campaign-agnostic. Auto-push to
main once green; don't commit the `fireemblem8u` submodule pointer.
