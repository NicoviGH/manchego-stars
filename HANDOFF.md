# Handoff: **Refining the Prologue (#20) — crash fixed, now building out the vertical slice.**

**Date:** 2026-06-09
**Focus:** ch00 "A Dagger of Ice" as a playable vertical slice. The deploy-time crash is fixed;
New Game boots straight onto the winter map and plays cleanly. Difficulty tuned to vanilla.
Currently mid-task on Hlin's custom map sprite (asset vendored, **not yet wired**).

**Live checklist = GitHub issue #20.** HANDOFF = current state + next steps; sub-steps -> TodoWrite.

---

## Current state
- ✅ Deploy crash fixed + regression-guarded + documented (`docs/decisions.md` → "Non-LORD-class
  lords need engine guards"; memory [[manchego_stars_non_lord_cursor_crash]]). Plays clean.
- ✅ Map built/rendering; units deploy correctly.
- ✅ Difficulty tuned to vanilla: **Hlin = unpromoted Fighter** (frail Eirika-analog lead),
  **Scramsax = Hero + Steel Sword** (dominant Seth-analog Jeigan), Sephek = Myrmidon L5 boss + 2
  Fighter guards. Diagnostics (`PROLOGUE_*` env flags) removed.
- ⏳ **Hlin female-Fighter map sprite — vendored, NOT wired** (she currently shares the male
  Fighter guards' sprite). Assets: `map_sprites/hlin-trollbane.png` (idle 16x48) +
  `hlin-trollbane_mu.png` (walk 32x480) — Alusq, from FE-Repo, RAW FE8 palette/format. Inert
  until wired (Hlin isn't in the cast `PORTRAIT_MAP` that `inject_map_sprites` processes).

## NEXT STEPS (priority order)
1. **Wire Hlin's custom map sprite** (the in-progress task):
   - `inject_map_sprites` only builds its idle/MU lists from `classed_cast()` (the 8 PORTRAIT_MAP
     PCs). Hlin is a guest on `CHARACTER_NATASHA`. **Extend it to include the prologue guest(s)**:
     add `(uid='hlin-trollbane', slot='NATASHA', class=FIGHTER)` so it emits a custom SMS (id 107+)
     + a `gMapSpriteOverride` entry keyed to `CHARACTER_NATASHA`, plus the MU (walk) override.
   - **Palette:** cast sprites share `cast_palette.png` in a purple OBJ bank (`gMapPaletteOverride`,
     `_inject_cast_palette`). The Alusq sheet has its own palette → either re-index it to the cast
     palette OR give Hlin her own bank. Inspect `map_sprite_tool` + `_read_cast_palette`.
   - Build → mGBA New Game → confirm Hlin renders as the woman Fighter, distinct from the guards.
2. **Lose condition** (decision needed): just Hlin = game over (vanilla lord-only), or Scramsax too?
   ch00 YAML marks both `required: true`; only Hlin's `EVFLAG_GAMEOVER` quote is wired today.
3. **In-engine win/lose verification** (playtest w/ Nicolas): DefeatBoss fires on Sephek? Hlin
   death = game over? Guard AI sane? (Crash is gone; gameplay untested.)
4. **Title card** "A Dagger of Ice".
5. **Cutscenes + dialogue** — opening (cold open / corner Sephek), mid-fight frost line, ending
   (Sephek escapes → hard cut to The Northlook). Co-written w/ Nicolas ([[feedback_collaborative_story_planning]]),
   not committed solo. `.ea` + MSG lines.
6. **Portraits** for Hlin / Scramsax / Sephek — placeholder or vendored from FE-Repo (#19).

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
- [[manchego-stars-project]] · [[manchego_stars_non_lord_cursor_crash]] · [[feedback_vendor_community_assets]] · [[feedback_chapter_vertical_slice]] · [[feedback_collaborative_story_planning]] · [[reference_fe_repo]]

## Standing rules
Combat = pure vanilla FE. Maps/sprites = vendor + reskin community/vanilla assets (not submodule).
Story/dialogue = collaborative with Nicolas. Engine guards stay campaign-agnostic. Auto-push to
main once green; don't commit the `fireemblem8u` submodule pointer.
