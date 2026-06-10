# Handoff: **NEXT = the ch00 dialogue pass — opening / mid-fight / ending cutscenes + real quote lines, co-written with Nicolas (walk it beat by beat, do NOT draft solo).**

**Date:** 2026-06-09
**Last session:** Shipped all three ch00 guest portraits (Sephek custom from Nicolas's
"Sephak Bust Dagger" ref; Hlin = FE-Repo Pirate Lady v3 silver-hair recolor; Scramsax =
FE-Repo Hero mug) + the `GUEST_PORTRAIT_MAP` wiring, credits, decision record, and
issue #20 ticks. Pushed through de0d795. Portraits are now DONE for the whole prologue;
the only ch00 work left is story/dialogue, then the end-to-end load-test.

**Live checklist = GitHub issue #20** (objective wiring / title card / guest portraits all
ticked 2026-06-09). HANDOFF = current state + next steps; sub-steps -> TodoWrite.

---

## NEXT SESSION: ch00 cutscenes + dialogue (collaborative mode)
Co-written with Nicolas ([[feedback_collaborative_story_planning]]) — bring beat options,
iterate line by line; he OKs voice. Read the book pages FIRST ([[feedback_story_sources_of_truth]]).
1. **Opening cutscene** — cold open / Hlin+Scramsax corner Sephek (`.ea` + dialogue).
   Voice sources: book printed pp.22-23 (Hlin: "elderly shield dwarf with a nasty scar
   across her nose… smoking her pipe"; her hired-killer quest monologue is verbatim
   there). Sephek: undead charmer, "kiss of the Frostmaiden". PDF page = printed+1.
2. **Mid-fight frost line** — Sephek bleeds frost at low HP.
3. **Ending cutscene** — Sephek "defeated" → misty-step escape → hard cut to The
   Northlook + the seven. Replaces the placeholder `MUSC(SONG_VICTORY)` + `MNC2(0x2)`
   hop in `EventScr_Ch1_EndingScene` (`inject_prologue` step 3 area patches it).
4. **Real lines for the three placeholder quote msgs** — Sephek 0x0936 / Hlin 0x0917 /
   Scramsax 0x0C25 (Scramsax has a draft retreat line in the chapter YAML already;
   Sephek has a draft `death_quote` there too — start from those).
5. After any text change: `python3 tools/verify_text.py`. Dialogue scenes are the first
   real in-game showing of the guest portraits — have Nicolas eyeball one scene.

## Then (priority order)
1. **#20 load-test** — full manual New Game → win → cutscene playthrough (last open box
   besides dialogue on #20).
2. **Prologue done ⇒ #43 opening montage** — next vertical slice (replaces boot cuts 2+4;
   coordinate with #29; blocker for #37). Then ch01 (#21).
3. (When ch01 starts) playtest scenario per chapter objective; `make playtest` target.
   New chapter titles = extend the glyph atlas in `gen_chapter_title.py` (needs C/h/digits
   for "Ch.N:" prefixes).

## Current state (all machine-verified, pushed)
- ✅ ch00 playable end-to-end with full art: map, units, win/lose wiring, title card,
  glacial banner theme, cast + guest portraits. `make` green, `make check` clean,
  verify_text 0 runaway, playtest win/gameover PASS.
- ✅ Guest-portrait machinery: `GUEST_PORTRAIT_MAP` (optional-by-file) + geometry patch;
  vendor originals/credits in `campaigns/.../portraits/vendor/`; regen scripts
  (`guest_vendor_busts.py`, `sephek-kaltro_dagger_trim.py`); render params in the chapter
  YAML `art:` blocks. Policy + lessons: decisions.md → "Guest portraits" and
  [[project_manchego_stars_portrait_pipeline]].
- ⚠️ Quote msgs + win ending are placeholders — THE next task (above).
- ⚠️ Scramsax's Hero mug has **no [F2E] tag in its filename** — license recheck before
  distribution (flagged in CREDITS.md + vendor/README.md).

## Gotchas (carried)
- Story text lives in `texts/texts.txt` via `set_message_body` + msg ids read from the
  decomp (never hardcode); `make` reruns build_campaign and overwrites manual decomp edits.
- Synthetic macOS keypresses don't reach mGBA; in-emulator Lua is the path (0.11 nightly).
- Unit marching: read `gBmMapMovement` reachable tiles, not naive closest-tile.
- Glyph extraction (for future title cards): hand-read cut columns from ASCII pixel dumps;
  kerned neighbors bleed; "It's a Trap!" has a standalone clean 'a'.
- Status plaque palette = `Pal_PlayStatusSprites` pal 0 (OBJ rows 8-9), not title palettes.

## Blockers
- None. (Dialogue is collaborative — that IS the next session's working mode.)

## Asset access (IMPORTANT — established pattern)
Pull a specific file from the **Klokinator FE-Repo** by **vendoring** it (2.3 GB — do NOT
submodule; never claim inaccessible) ([[feedback_vendor_community_assets]]):
```
gh api "repos/Klokinator/FE-Repo/contents/<url-encoded path>?ref=main" \
  --jq '.[] | select(.name=="<exact filename>") | .download_url'
curl -fsSL "<download_url>" -o campaigns/rime-of-the-frostmaiden/<dir>/<dest>.png
```
For browsing, `--jq '.[] | [.name, .download_url] | @tsv'` on a directory gives a
greppable candidate list. Credit the `{Artist}` in the asset dir README + CREDITS.md.

## Build / run / playtest / debug
- Build: `make CAMPAIGN=rime-of-the-frostmaiden fireemblem8.gba` (green at session end;
  `make check` = drift guard). Regenerate indexes after YAML edits (`tools/gen_*_index.py`).
- Text gate after any text change: `python3 tools/verify_text.py`.
- **Automated playtest:** `tools/playtest/run.sh win|gameover|retreat|titlecard` (exit 0 =
  PASS; artifacts in `/tmp/playtest-<scenario>/`; wipes the .sav; kills running mGBA).
- Manual run (art/feel): `pkill -9 -i mgba; rm -f fireemblem8u/fireemblem8.sav; "/Applications/mGBA.app/Contents/MacOS/mGBA" "$PWD/fireemblem8u/fireemblem8.gba" &` then New Game.
- Visual drafts for Nicolas: save PNGs to `map-review/` and `open` them — he can't see
  inline renders ([[feedback_sharing_visual_drafts]]).
- Debug a crash: `mGBA -g <rom>` + `arm-none-eabi-gdb -q fireemblem8u/fireemblem8.elf`,
  `target remote :2345`, hardware watchpoint on the suspect global.
- **Env note:** if `make` dies on a missing module, point `python3` at one with
  numpy/pillow/pyyaml.

## Key files
- `tools/build_campaign.py` — `inject_prologue` (quote msgs step 5, `EventScr_Ch1_EndingScene`
  ending block, name/title text via `set_message_body`); portrait machinery
  (`PORTRAIT_MAP`/`GUEST_PORTRAIT_MAP`, `inject_portraits`, `patch_portrait_geometry`).
- `campaigns/rime-of-the-frostmaiden/chapters/ch00-prologue-a-dagger-of-ice.yaml` — design
  SoT: narrative beats, draft quote lines, guest `art:` blocks.
- `fireemblem8u/` decomp: event-script reference for cutscenes (vanilla prologue scenes =
  the shape to copy; ground every claim in source per [[feedback_use_decomp]]).
- Frostmaiden book PDF (voice): `References/icewind-dale-rime-of-the-frostmaidenpdf_compress.pdf`
  (PDF page = printed+1; Hlin/Sephek brief at printed pp.22-23). DM notes PDF beside it.
- `tools/playtest/{run.sh,harness.lua,gen_symbols.py}` — playtest harness.
- `docs/decisions.md` — settled decisions; record any new dialogue/cutscene mechanism choice.

## Memory
- [[manchego-stars-project]] · [[feedback_collaborative_story_planning]] · [[feedback_story_sources_of_truth]] · [[feedback_use_decomp]] · [[project_manchego_stars_dm_notes]] · [[feedback_fe_name_truncation]] · [[manchego_stars_text_terminator_parity]] · [[project_manchego_stars_portrait_pipeline]] · [[manchego-stars-automated-playtests]] · [[feedback_chapter_vertical_slice]]

## Standing rules
Combat = pure vanilla FE. Maps/sprites = vendor + reskin community/vanilla assets (not
submodule). Story/dialogue = collaborative with Nicolas; art look-picks wait for his OK.
Engine guards stay campaign-agnostic. Auto-push to main once green; don't commit the
`fireemblem8u` submodule pointer. Playtests: machine-run for logic, Nicolas for art/feel.
