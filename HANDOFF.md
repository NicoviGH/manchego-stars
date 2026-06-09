# Handoff: **ch00 title card + GLACIAL BLUE banner theme LANDED; next = cutscenes/dialogue + portraits; opening montage (#43) = next slice after the Prologue.**

**Date:** 2026-06-09
**Session focus:** (a) Built the chapter title-card pipeline — FE8 titles are 4bpp IMAGES,
so `tools/gen_chapter_title.py` recomposes them from vanilla glyphs — and landed the real
"Prologue: A Dagger of Ice" card (commit 0f2b1ff, pushed); (b) added a `titlecard` playtest
scenario that machine-verifies it via the Status screen; (c) Nicolas asked for an Icewind
Dale-themed look — three recolor mockups are in `map-review/` awaiting his pick.

**Live checklist = GitHub issue #20.** HANDOFF = current state + next steps; sub-steps -> TodoWrite.

---

## Current state
- ✅ **ch00 title card DONE and machine-verified** (commit 0f2b1ff, pushed):
  - `tools/gen_chapter_title.py` cuts verified glyphs from vanilla cards (hand-read cut
    columns; unknown glyph = hard error) and recomposes at vanilla's optical center (x≈99).
  - `inject_prologue` writes the card over the host slot's PNG (restored build artifact),
    sets `chapTitleTextId`, and fixes the copied goal block's `statusObjectiveTextId`
    (Status screen said "Defeat O'Neill"; now "Defeat Sephek" from the YAML boss fe_name).
  - `tools/playtest/run.sh titlecard` → PASS: opens map menu → Status screen (which draws
    the card), asserts `gProcScr_ChapterStatusScreen`, screenshots it.
  - Full decision entry: `docs/decisions.md` → "Chapter title cards are IMAGES".
- ✅ **Glacial-blue banner theme DONE and approved** (commit 7ccc631, pushed): Nicolas picked
  option A from 4 in-game mockups; plaque recolor approved on the render. Pure PALETTE job —
  `inject_title_theme` reads `title_theme.letter_colors` from `campaign.yaml`, maps the six
  vanilla letter greens 1:1, hue-maps other greens (plaque leaf ramp `Pal_PlayStatusSprites`
  pal 0, dim variant) into the ice family, repoints the `.s` incbins at generated bins.
  In-map intro (gray pair) untouched. Full entry: `docs/decisions.md` → "Title banner theme".
  The `titlecard` scenario now dumps BG+OBJ palette RAM (how the plaque palette was traced).
- ✅ **Opening montage backlogged as the NEXT SLICE after the Prologue:** issue **#43** —
  recreate the cut Magvel-tour intro as an Icewind Dale world overview (replaces boot cuts
  2+4; coordinate with #29; blocker for distribution #37). Slice checklist on the issue.
- ✅ ch00 win/lose wiring verified (7cbe18c + 6f79c73): `run.sh win|gameover|retreat` all PASS.
- ✅ Earlier state intact: map renders, deploy clean, Hlin sprite approved, difficulty tuned.
- ⚠️ Win still ends in the placeholder victory sting + `MNC2(0x2)` hop; real ending cutscene
  comes with the dialogue pass.
- ⚠️ All quote msgs are placeholders (Sephek 0x0936 / Hlin 0x0917 / Scramsax 0x0C25) until
  the dialogue pass.

## Tried but didn't work / gotchas
- Naive glyph extraction (min-ink column cuts, connected-component cleaning) left neighbor
  serif/shadow debris between letters — hand-read cut columns from ASCII pixel dumps was the
  reliable path. Kerned neighbors DO bleed into a glyph's columns (e.g. P's shadow into 'r',
  scrubbed in the atlas); "It's a Trap!" has a standalone clean 'a'.
- Recoloring the in-game screenshot by color-matching leaked onto the banner plaque art
  (shares greens with the letters) — composite mockups from the title PNG's own indices at
  the correlated screen offset instead (exact, no bleed).
- (Carried) Synthetic macOS keypresses don't reach mGBA; stable 0.10.x lacks `--script`.
- (Carried) March via `gBmMapMovement` reachable tiles, not naive closest-tile.

## Blockers
- Icy style pick = Nicolas's call (art). Everything else can proceed.

## NEXT STEPS (priority order)
1. **Cutscenes + dialogue** — opening (cold open / corner Sephek), mid-fight frost line,
   ending (Sephek "defeated" → escapes → hard cut to The Northlook; replaces the MNC2
   placeholder). Co-written w/ Nicolas ([[feedback_collaborative_story_planning]]), not
   committed solo. Includes real lines for the three placeholder quote msgs.
2. **Portraits** for Hlin / Scramsax / Sephek — placeholder or vendored from FE-Repo (#19).
3. **Prologue done ⇒ start #43 (opening montage)** — the next vertical slice; checklist on
   the issue. Then ch01 (#21).
4. (When ch01 starts) extend the playtest harness per chapter objective; consider a
   `make playtest` target running all scenarios. New chapter titles = extend the glyph
   atlas in `gen_chapter_title.py` (needs C/h/digits for "Ch.N:" prefixes).

## Asset access (IMPORTANT — established pattern)
Pull a specific file from the **Klokinator FE-Repo** by **vendoring** it (2.3 GB — do NOT
submodule; never claim inaccessible) ([[feedback_vendor_community_assets]]):
```
gh api "repos/Klokinator/FE-Repo/contents/<url-encoded path>?ref=main" \
  --jq '.[] | select(.name=="<exact filename>") | .download_url'
curl -fsSL "<download_url>" -o campaigns/rime-of-the-frostmaiden/<dir>/<dest>.png
```
Credit the `{Artist}` from the filename in the asset dir's README + CREDITS.md.
(Checked for chapter-title fonts: FE-Repo's `BGs, Interface Elements` has none usable —
icy theming is a recolor/own-pixels job, not a vendor job.)

## Build / run / playtest / debug
- Build: `make CAMPAIGN=rime-of-the-frostmaiden fireemblem8.gba` (green at session end;
  `make check` = drift guard). Regenerate indexes after YAML edits (`tools/gen_*_index.py`).
- **Automated playtest:** `tools/playtest/run.sh win|gameover|retreat|titlecard` (exit 0 =
  PASS; log + screenshots in `/tmp/playtest-<scenario>/`; wipes the .sav; kills running mGBA).
- Manual run (art/feel): `pkill -9 -i mgba; rm -f fireemblem8u/fireemblem8.sav; "/Applications/mGBA.app/Contents/MacOS/mGBA" "$PWD/fireemblem8u/fireemblem8.gba" &` then New Game.
- Visual drafts for Nicolas: save PNGs to `map-review/` and `open` them (he can't see inline
  renders) ([[feedback_sharing_visual_drafts]]).
- Debug a crash: `mGBA -g <rom>` + `arm-none-eabi-gdb -q fireemblem8u/fireemblem8.elf`,
  `target remote :2345`, hardware watchpoint on the suspect global.
- **Env note:** if `make` dies on a missing module, point `python3` at one with
  numpy/pillow/pyyaml.

## Key files
- `tools/gen_chapter_title.py` — glyph atlas + title-card composer (extend per chapter).
- `tools/build_campaign.py` — `inject_prologue` step 4a: title card PNG + chapTitleTextId +
  statusObjectiveTextId; step 2 rosters/AI, step 3 Misc win/lose, step 5 defeat quotes.
- `tools/playtest/{run.sh,harness.lua,gen_symbols.py}` — playtest harness (+ `titlecard`
  scenario; symbols.lua generated; mGBA nightly in `tools/emulator/`, gitignored).
- `map-review/title-card-icy-options{,-zoom}.png` — the 4 style variants for Nicolas.
- `fireemblem8u/src/chapter_title.c`, `src/uichapterstatus.c` — how cards are drawn
  (decompress `chap_title_data[chapTitleId]`; status palette = `gPal_08A07C58` via
  `sub_80895B4(0x80, 0x13)`).
- `campaigns/rime-of-the-frostmaiden/chapters/ch00-prologue-a-dagger-of-ice.yaml` — design SoT.
- `docs/decisions.md` — "Chapter title cards are IMAGES" + "Automated playtests" entries.

## Memory
- [[manchego-stars-project]] · [[manchego-stars-automated-playtests]] · [[feedback_vendor_community_assets]] · [[feedback_chapter_vertical_slice]] · [[feedback_collaborative_story_planning]] · [[feedback_sharing_visual_drafts]] · [[feedback_show_before_committing_art]] · [[reference_fe_repo]]

## Standing rules
Combat = pure vanilla FE. Maps/sprites = vendor + reskin community/vanilla assets (not
submodule). Story/dialogue = collaborative with Nicolas; art look-picks (like the icy style)
wait for his OK. Engine guards stay campaign-agnostic. Auto-push to main once green; don't
commit the `fireemblem8u` submodule pointer. Playtests: machine-run for logic, Nicolas for
art/feel.
