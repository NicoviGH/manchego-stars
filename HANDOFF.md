# Handoff: **Refining the Prologue (#20) — all wiring done; next = in-engine win/lose playtest.**

**Date:** 2026-06-09
**Session focus:** (a) the ch00 lose-condition decision + wiring (incl. a silent quote-table bug
found and fixed), (b) a delivery/docs audit with all follow-ups landed. **Active task = the
in-engine win/lose verification with Nicolas** (step 1 below) — it needs him driving mGBA.

**Live checklist = GitHub issue #20.** HANDOFF = current state + next steps; sub-steps -> TodoWrite.

---

## Current state
- ✅ Deploy crash fixed + regression-guarded + documented (`docs/decisions.md` → "Non-LORD-class
  lords need engine guards"; memory [[manchego_stars_non_lord_cursor_crash]]). Plays clean.
- ✅ Map built/rendering; units deploy correctly. Difficulty tuned to vanilla: **Hlin = unpromoted
  Fighter** (frail Eirika-analog lead), **Scramsax = Hero + Steel Sword** (Seth-analog Jeigan),
  Sephek = Myrmidon L5 boss + 2 Fighter guards.
- ✅ **Hlin female-Fighter map sprite wired + approved** (commit 2b0084f) via the
  `PROLOGUE_GUEST_SPRITES` guest path. Recipe: `docs/decisions.md` → "Guests reuse the STANDARD
  player palette" + memory [[manchego_stars_guest_map_sprite_wiring]].
- ✅ **Lose condition DECIDED (Nicolas) + WIRED: game over on Hlin ONLY** (commit 4105287).
  Scramsax's defeat = a **flag-less retreat quote** ("too weak to continue the fight") — battle
  continues, he's alive for Ch1 (vanilla Seth shape; Seth's death quote has no `EVFLAG_GAMEOVER`).
  Recorded: ch00 YAML NOTE 3 + `docs/decisions.md` → "Game over = the lord-analog only".
- ✅ **Silent quote-table bug fixed** (same commit): injected quotes were landing AFTER
  `gDefeatTalkList`'s `{.pid = -1}` terminator, where `GetDefeatTalkEntry` (eventinfo.c) never
  scans — **Hlin's game-over entry had never been live**. `inject_prologue` step 5 now inserts
  before the terminator (exact-match guarded). Both quote msgs are placeholders (0x0917 Hlin /
  0x0C25 Scramsax) until the dialogue pass.
- ✅ **Audit follow-ups landed** (commit 31bf9d0, CI green): index generators ported
  Ruby→Python (`tools/gen_chapter_index.py` / `gen_class_index.py`, byte-identical output);
  **check.py now fails if a generated index is stale vs the YAML** (pre-commit + CI); CI build
  job runs `verify_text.py` after `make`; sprite-exploration PNGs cleaned out of the working
  tree (process docs/keepers intact); CREDITS.md Tiger row fixed. Issues: #3 + #12 closed,
  #30 retitled (9-chapter MVP), #37 got a pre-distribution checklist (incl. credits format).

## Tried but didn't work / gotchas
- Appending rows to a terminator-scanned C table via `_append_table_rows` compiles fine but is
  dead code — for `gDefeatTalkList`-style lists, insert BEFORE the terminator. (The wait table
  is index-accessed, so appending there is still correct.)
- Synthetic keypresses (osascript) still do NOT reach mGBA — playtests need Nicolas on input.

## Blockers
- **Step 1 needs Nicolas at the controls** (mGBA input). Nothing else blocks.

## NEXT STEPS (priority order)
1. **In-engine win/lose verification** (playtest w/ Nicolas — active task): DefeatBoss fires on
   Sephek? Hlin death = game over (first time it can actually fire — see bug above)? Scramsax
   death = quote plays, battle continues? Guard AI sane? Launch cmd below (note: wipes the .sav).
2. **Title card** "A Dagger of Ice".
3. **Cutscenes + dialogue** — opening (cold open / corner Sephek), mid-fight frost line, ending
   (Sephek escapes → hard cut to The Northlook). Co-written w/ Nicolas
   ([[feedback_collaborative_story_planning]]), not committed solo. Includes the real Hlin death
   line + Scramsax retreat line (draft in ch00 YAML `defeat_quote`).
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
Credit the `{Artist}` from the filename in the asset dir's README + CREDITS.md.

## Build / run / debug
- Build: `make CAMPAIGN=rime-of-the-frostmaiden fireemblem8.gba` (must end green; `make check`
  = drift guard incl. engine-guard presence + generated-index freshness).
- Regenerate indexes after YAML edits: `python3 tools/gen_chapter_index.py` /
  `python3 tools/gen_class_index.py` (check.py fails the commit if stale).
- Run: `pkill -9 -i mgba; rm -f fireemblem8u/fireemblem8.sav; "/Applications/mGBA.app/Contents/MacOS/mGBA" "$PWD/fireemblem8u/fireemblem8.gba" &` then New Game.
- Screen capture works (`screencapture -x -o out.png`); synthetic input does not.
- Debug a map/render crash: `mGBA -g <rom>` + `arm-none-eabi-gdb -q fireemblem8u/fireemblem8.elf`,
  `target remote :2345`, hardware watchpoint on the suspect global (e.g. `watch gBmSt.playerCursor.y`).
- **Env note:** if `make` dies on a missing module, point `python3` at one with
  numpy/pillow/pyyaml (a gdb install once bumped Homebrew python past PIL).

## Key files
- `tools/build_campaign.py` — `inject_prologue` (step 5 = the two defeat quotes, inserted
  before the terminator), `inject_map_sprites`, the two engine guards, `patch_character_data`.
- `campaigns/rime-of-the-frostmaiden/chapters/ch00-prologue-a-dagger-of-ice.yaml` — design SoT
  (NOTE 2/3 = game-over mechanism + decision; Scramsax `defeat_quote` draft).
- `tools/check.py` — the drift guard (now incl. `check_generated_indexes_fresh`).
- `fireemblem8u/src/data_battlequotes.c` (build artifact) + `src/eventinfo.c GetDefeatTalkEntry`
  — the quote table + its terminator-scanning reader.

## Memory
- [[manchego-stars-project]] · [[manchego_stars_non_lord_cursor_crash]] · [[manchego_stars_guest_map_sprite_wiring]] · [[feedback_vendor_community_assets]] · [[feedback_chapter_vertical_slice]] · [[feedback_collaborative_story_planning]] · [[reference_fe_repo]]

## Standing rules
Combat = pure vanilla FE. Maps/sprites = vendor + reskin community/vanilla assets (not submodule).
Story/dialogue = collaborative with Nicolas. Engine guards stay campaign-agnostic. Auto-push to
main once green; don't commit the `fireemblem8u` submodule pointer.
