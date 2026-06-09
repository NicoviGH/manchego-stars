# Handoff: **Refining the Prologue (#20) — win/lose wired, now in-engine verification.**

**Date:** 2026-06-09
**Focus:** ch00 "A Dagger of Ice" as a playable vertical slice. Crash fixed, map plays clean,
difficulty vanilla-tuned, Hlin's custom sprite wired, lose condition decided + wired. **Active
task = in-engine win/lose verification with Nicolas** (step 1 below), then title card + cutscenes.

**Live checklist = GitHub issue #20.** HANDOFF = current state + next steps; sub-steps -> TodoWrite.

---

## Current state
- ✅ Deploy crash fixed + regression-guarded + documented (`docs/decisions.md` → "Non-LORD-class
  lords need engine guards"; memory [[manchego_stars_non_lord_cursor_crash]]). Plays clean.
- ✅ Map built/rendering; units deploy correctly.
- ✅ Difficulty tuned to vanilla: **Hlin = unpromoted Fighter** (frail Eirika-analog lead),
  **Scramsax = Hero + Steel Sword** (dominant Seth-analog Jeigan), Sephek = Myrmidon L5 boss + 2
  Fighter guards. Diagnostics (`PROLOGUE_*` env flags) removed.
- ✅ **Hlin female-Fighter map sprite — WIRED + approved** (2026-06-09, commit 2b0084f), via the
  `PROLOGUE_GUEST_SPRITES` guest path. Repeatable recipe: `docs/decisions.md` → "Guests reuse the
  STANDARD player palette" + memory [[manchego_stars_guest_map_sprite_wiring]].
- ✅ **Lose condition DECIDED (Nicolas, 2026-06-09) + WIRED: game over on Hlin ONLY.** Scramsax's
  defeat = a **flag-less retreat quote** ("too weak to continue the fight") — battle continues,
  and he's out of the fight, not dead, so he tends The Northlook in Ch1 regardless. Vanilla Seth
  shape (his death quote carries no `EVFLAG_GAMEOVER`). Recorded: ch00 YAML NOTE 3 +
  `docs/decisions.md` → "Game over = the lord-analog only".
- ✅ **Silent quote-table bug found + fixed:** `_append_table_rows` put injected quotes AFTER
  `gDefeatTalkList`'s `{.pid = -1}` terminator — `GetDefeatTalkEntry` (eventinfo.c) stops there,
  so **Hlin's game-over entry had never actually been live**. `inject_prologue` step 5 now
  inserts before the terminator (exact-match guarded). Both quote msgs are placeholders until
  the dialogue pass.

## NEXT STEPS (priority order)
1. **In-engine win/lose verification** (playtest w/ Nicolas — active task): DefeatBoss fires on
   Sephek? Hlin death = game over (first time it can actually fire — see bug above)? Scramsax
   death = quote plays, battle continues? Guard AI sane? Nicolas must drive input (synthetic
   keypresses don't reach mGBA).
2. **Title card** "A Dagger of Ice".
3. **Cutscenes + dialogue** — opening (cold open / corner Sephek), mid-fight frost line, ending
   (Sephek escapes → hard cut to The Northlook). Co-written w/ Nicolas ([[feedback_collaborative_story_planning]]),
   not committed solo. `.ea` + MSG lines. Includes the real Hlin death line + Scramsax retreat
   line (placeholder msgs 0x0917 / 0x0C25 today; draft retreat line in ch00 YAML `defeat_quote`).
4. **Portraits** for Hlin / Scramsax / Sephek — placeholder or vendored from FE-Repo (#19).

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
- `tools/build_campaign.py` — `inject_prologue` (step 5 = the two defeat quotes),
  `inject_map_sprites`, the two engine guards, `patch_character_data`.
- `campaigns/rime-of-the-frostmaiden/chapters/ch00-prologue-a-dagger-of-ice.yaml` — design SoT
  (NOTE 2/3 = the game-over mechanism + decision).
- `fireemblem8u/src/data_battlequotes.c` (build artifact) + `src/eventinfo.c GetDefeatTalkEntry`
  — the quote table + its terminator-scanning reader.

## Memory
- [[manchego-stars-project]] · [[manchego_stars_non_lord_cursor_crash]] · [[manchego_stars_guest_map_sprite_wiring]] · [[feedback_vendor_community_assets]] · [[feedback_chapter_vertical_slice]] · [[feedback_collaborative_story_planning]] · [[reference_fe_repo]]

## Standing rules
Combat = pure vanilla FE. Maps/sprites = vendor + reskin community/vanilla assets (not submodule).
Story/dialogue = collaborative with Nicolas. Engine guards stay campaign-agnostic. Auto-push to
main once green; don't commit the `fireemblem8u` submodule pointer.
