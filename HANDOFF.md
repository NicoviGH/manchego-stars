# Handoff: **NEXT = the ch00 dialogue pass (opening / mid-fight / ending cutscenes + real quote lines), co-written with Nicolas. Portraits are DONE for the whole prologue cast+guests.**

**Date:** 2026-06-09
**Last session:** Shipped all three ch00 guest portraits. Wired guest slots into the bust
pipeline (`GUEST_PORTRAIT_MAP` — optional-by-file, so wiring lands ahead of art), then
walked look-picks with Nicolas: **Sephek** = custom bust from his "Sephak Bust Dagger"
cel-shaded ref (book art tried first, rejected as style mismatch); **Hlin** = FE-Repo
Pirate Lady v3 with a silver-hair age recolor; **Scramsax** = FE-Repo Hero mug as-is.
All pushed: a313095 (wiring) + a383c5c (busts/credits/decision).

**Live checklist = GitHub issue #20.** HANDOFF = current state + next steps; sub-steps -> TodoWrite.
⚠️ Couldn't tick #20's boxes this session (permission denial): **Objective wiring**,
**Title card**, and the **art/placeholder line** are all DONE — tick them on next touch.

---

## NEXT SESSION: cutscenes + dialogue (co-written — do NOT draft solo, walk it beat by beat)
1. **Opening cutscene** — cold open / Hlin+Scramsax corner Sephek (`.ea` + dialogue).
   Book brief for voice: Hlin quest text pp.22-23 ("elderly shield dwarf with a nasty
   scar across her nose… smoking her pipe"); Sephek = undead charmer, "kiss of the
   Frostmaiden".
2. **Mid-fight frost line** — Sephek bleeds frost at low HP.
3. **Ending cutscene** — Sephek "defeated" → misty-step escape → hard cut to The
   Northlook + the seven (replaces the placeholder `MUSC(SONG_VICTORY)` + `MNC2(0x2)`
   hop in `EventScr_Ch1_EndingScene`).
4. **Real lines for the three placeholder quote msgs** (Sephek 0x0936 / Hlin 0x0917 /
   Scramsax 0x0C25; Scramsax already has a draft retreat line in the chapter YAML).
5. After any text change: `python3 tools/verify_text.py`. Quote/dialogue scenes will
   show the new guest portraits — first real in-game look; have Nicolas eyeball one.

## Then (priority order)
1. **#20 load-test** — full manual New Game → win → cutscene playthrough once dialogue is in.
2. **Prologue done ⇒ #43 opening montage** — next vertical slice (replaces boot cuts 2+4;
   coordinate with #29; blocker for #37). Then ch01 (#21).
3. (When ch01 starts) playtest scenario per chapter objective; `make playtest` target.
   New chapter titles = extend the glyph atlas in `gen_chapter_title.py` (needs C/h/digits
   for "Ch.N:" prefixes).

## Current state (all machine-verified, pushed)
- ✅ ch00 guest portraits IN: Hlin/Scramsax/Sephek slots (NATASHA/KYLE/O_Neill files)
  dressed by `inject_portraits` via `GUEST_PORTRAIT_MAP`; geometry normalized; dead-zone
  clean on Sephek. `make` green, `make check` clean, verify_text 0 runaway, playtest
  win + gameover PASS.
- ✅ Reproducibility: Sephek render params in the chapter YAML `art:` block +
  `portraits/sephek-kaltro_dagger_trim.py`; vendor busts regenerate via
  `portraits/guest_vendor_busts.py` from `portraits/vendor/` (originals + credits;
  also CREDITS.md). Decision recorded: decisions.md → Art & Audio → "Guest portraits".
- ✅ Title card + glacial banner theme + win/lose wiring + map: all PASS (see a313095⁻).
- ⚠️ Quote msgs + win ending are placeholders until the dialogue pass (see above).
- ⚠️ Hero mug has **no [F2E] tag in its filename** — license recheck before distribution
  (flagged in CREDITS.md + vendor/README.md).

## Tried but didn't work (this session)
- **Book scan as Sephek ref:** extracted p.23 art at 300dpi (`pdftoppm`; raw `pdfimages`
  scan is stored rotated), pipeline output was recognizable but murky — Nicolas called
  style mismatch and supplied a cel-shaded ref instead. Book art = concept reference,
  not pipeline input.
- **Green pre-key for segmentation:** keying the ref bg to pure green poisons the
  downscale (green blends into every edge). Fix the real problem instead: the flat gray
  bg sat close to the cream sleeve → `--bg-thresh 25`.
- **"Sleeve eaten" was actually crop framing** — the window ended above the arm. When a
  feature is missing, check the crop box before blaming segmentation.
- **No-blade Sephek variant:** erasing the blade dropped cyan from pngquant's palette and
  killed his glowing eyes. Accent colors can ride on other features' pixels.

## Gotchas (carried)
- Glyph extraction: hand-read cut columns from ASCII pixel dumps; kerned neighbors bleed
  into glyph columns (scrub list in the atlas); "It's a Trap!" has a standalone clean 'a'.
- The Status plaque art is a SPRITE; its palette is `Pal_PlayStatusSprites` pal 0 (OBJ
  rows 8–9) — NOT the title palettes. The `titlecard` scenario dumps BG+OBJ palette RAM.
- Synthetic macOS keypresses don't reach mGBA; in-emulator Lua is the path (0.11 nightly).
- Unit marching: read `gBmMapMovement` reachable tiles, not naive closest-tile.

## Blockers
- None. (Dialogue writing is collaborative with Nicolas — that's the next session's mode.)

## Asset access (IMPORTANT — established pattern)
Pull a specific file from the **Klokinator FE-Repo** by **vendoring** it (2.3 GB — do NOT
submodule; never claim inaccessible) ([[feedback_vendor_community_assets]]):
```
gh api "repos/Klokinator/FE-Repo/contents/<url-encoded path>?ref=main" \
  --jq '.[] | select(.name=="<exact filename>") | .download_url'
curl -fsSL "<download_url>" -o campaigns/rime-of-the-frostmaiden/<dir>/<dest>.png
```
Tip: for browsing, `--jq '.[] | [.name, .download_url] | @tsv'` on a directory gives a
greppable candidate list. Credit the `{Artist}` in the asset dir README + CREDITS.md.

## Build / run / playtest / debug
- Build: `make CAMPAIGN=rime-of-the-frostmaiden fireemblem8.gba` (green at session end;
  `make check` = drift guard). Regenerate indexes after YAML edits (`tools/gen_*_index.py`).
- **Automated playtest:** `tools/playtest/run.sh win|gameover|retreat|titlecard` (exit 0 =
  PASS; artifacts in `/tmp/playtest-<scenario>/`; wipes the .sav; kills running mGBA).
- Manual run (art/feel): `pkill -9 -i mgba; rm -f fireemblem8u/fireemblem8.sav; "/Applications/mGBA.app/Contents/MacOS/mGBA" "$PWD/fireemblem8u/fireemblem8.gba" &` then New Game.
- Visual drafts for Nicolas: save PNGs to `map-review/` and `open` them — he can't see
  inline renders ([[feedback_sharing_visual_drafts]]). Guest-portrait review set lives in
  `map-review/ch00-guest-portraits/`.
- Debug a crash: `mGBA -g <rom>` + `arm-none-eabi-gdb -q fireemblem8u/fireemblem8.elf`,
  `target remote :2345`, hardware watchpoint on the suspect global.
- **Env note:** if `make` dies on a missing module, point `python3` at one with
  numpy/pillow/pyyaml.

## Key files
- `tools/build_campaign.py` — `PORTRAIT_MAP` + `GUEST_PORTRAIT_MAP` (+`dressed_guest_slots`),
  `inject_portraits`, `patch_portrait_geometry(campaign)`, `inject_prologue` (cutscene hooks:
  `EventScr_Ch1_EndingScene`, quote msgs in step 5).
- `campaigns/rime-of-the-frostmaiden/chapters/ch00-prologue-a-dagger-of-ice.yaml` — design
  SoT incl. guest `art:` blocks (render params / vendor sources).
- `campaigns/.../portraits/` — busts + previews; `vendor/` (originals + credits);
  `guest_vendor_busts.py`, `sephek-kaltro_dagger_trim.py` (regen scripts).
- `tools/ref_to_bust.py`, `tools/portrait_tool.py` — pipeline; `portrait_tool.py preview` =
  dead-zone check (Nicolas asks for this — show it with every bust).
- `tools/playtest/{run.sh,harness.lua,gen_symbols.py}` — playtest harness.
- `docs/decisions.md` — settled decisions incl. NEW "Guest portraits" entry (Art & Audio).
- Frostmaiden book PDF (story voice): `References/icewind-dale-rime-of-the-frostmaidenpdf_compress.pdf`
  (PDF page = printed+1; Sephek/Hlin brief at printed pp.22-23).

## Memory
- [[manchego-stars-project]] · [[project_manchego_stars_portrait_pipeline]] · [[feedback_portrait_framing]] · [[feedback_portrait_descale_not_crop]] · [[feedback_portrait_static_no_animation]] · [[feedback_show_before_committing_art]] · [[feedback_vendor_community_assets]] · [[reference_fe_repo]] · [[feedback_collaborative_story_planning]] · [[manchego-stars-automated-playtests]] · [[feedback_chapter_vertical_slice]]

## Standing rules
Combat = pure vanilla FE. Maps/sprites = vendor + reskin community/vanilla assets (not
submodule). Story/dialogue = collaborative with Nicolas; art look-picks wait for his OK.
Engine guards stay campaign-agnostic. Auto-push to main once green; don't commit the
`fireemblem8u` submodule pointer. Playtests: machine-run for logic, Nicolas for art/feel.
