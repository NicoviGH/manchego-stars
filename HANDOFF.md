# Handoff: **NEXT = ch00 portraits (Hlin / Scramsax / Sephek). Title card + glacial banner theme are DONE; dialogue pass and #43 (opening montage) queue behind portraits.**

**Date:** 2026-06-09
**Last session:** Built the chapter title-card pipeline (`gen_chapter_title.py` recomposes
FE8's 4bpp title images from vanilla glyphs), landed "Prologue: A Dagger of Ice", added a
`titlecard` playtest scenario, and shipped the campaign-driven GLACIAL BLUE banner theme
Nicolas picked (letters + Status plaque, pure palette recolor). Opening montage filed as
**#43**, the next vertical slice after the Prologue. All pushed: 0f2b1ff → ccd32f9.

**Live checklist = GitHub issue #20.** HANDOFF = current state + next steps; sub-steps -> TodoWrite.

---

## NEXT SESSION: portraits for the three ch00 guests
1. **Decide per character: custom-pipeline vs FE-Repo vendor** (#19 covers PC + key-NPC
   portraits). The custom-art-everywhere rule is about the CAST
   ([[feedback_custom_art_lever]]); Hlin/Scramsax/Sephek are campaign NPCs — Sephek recurs
   (escapes in the ending; worth a real face), Hlin/Scramsax are prologue-heavy. Bring
   Nicolas options before building ([[feedback_collaborative_map_design]] pattern).
2. **Wiring check first:** the guests ride vanilla slots NATASHA/HLIN, KYLE/SCRAMSAX,
   ONEILL/SEPHEK (`PROLOGUE_*_SLOT` in `tools/build_campaign.py`) — they currently show
   those vanilla FACES. `inject_portraits` only dresses `PORTRAIT_MAP` (cast) slots; guest
   portraits need the same treatment for their slots (mind `patch_portrait_geometry` —
   normalize FaceData to our 2,6,3,4 framing when replacing).
3. **Custom path** = the bust pipeline ([[project_manchego_stars_portrait_pipeline]]):
   Nano Banana ref → `tools/ref_to_bust.py` (crop/zoom → segment → downscale → pngquant)
   → `tools/portrait_tool.py` insert. Statics only ([[feedback_portrait_static_no_animation]]);
   framing rules in [[feedback_portrait_framing]] + [[feedback_portrait_descale_not_crop]];
   show crops, WAIT for OK before committing ([[feedback_show_before_committing_art]]).
4. **Vendor path** = FE-Repo `Portrait Repository` (pattern below); credit artists in the
   asset dir README + CREDITS.md.
5. Verify in-game: unit info screen via manual run, or extend the harness if a scenario
   makes sense. (Quote/dialogue portraits come with the dialogue pass.)

## Then (priority order)
1. **Cutscenes + dialogue** — opening (cold open / corner Sephek), mid-fight frost line,
   ending (Sephek "defeated" → escapes → hard cut to The Northlook; replaces the
   placeholder victory sting + `MNC2(0x2)` hop). Co-written w/ Nicolas
   ([[feedback_collaborative_story_planning]]). Includes real lines for the three
   placeholder quote msgs (Sephek 0x0936 / Hlin 0x0917 / Scramsax 0x0C25).
2. **Prologue done ⇒ #43 opening montage** — next vertical slice (checklist on the issue;
   replaces boot cuts 2+4; coordinate with #29; blocker for #37). Then ch01 (#21).
3. (When ch01 starts) playtest scenario per chapter objective; `make playtest` target.
   New chapter titles = extend the glyph atlas in `gen_chapter_title.py` (needs C/h/digits
   for "Ch.N:" prefixes).

## Current state (all machine-verified, pushed)
- ✅ ch00 win/lose wiring: `tools/playtest/run.sh win|gameover|retreat` all PASS.
- ✅ Title card "Prologue: A Dagger of Ice": recomposed from vanilla glyphs
  (`tools/gen_chapter_title.py`); `inject_prologue` step 4a sets card PNG +
  `chapTitleTextId` + `statusObjectiveTextId` ("Defeat Sephek"). `run.sh titlecard` PASS.
- ✅ Glacial-blue banner theme: `inject_title_theme` reads `title_theme.letter_colors`
  (campaign.yaml), maps vanilla's 6 letter greens 1:1, hue-maps other greens (plaque ramp
  `Pal_PlayStatusSprites` pal 0, dim variant) to ice; in-map intro (gray pair) untouched.
- ✅ Map renders, deploy clean, Hlin map sprite approved, difficulty tuned.
- ⚠️ Quote msgs + win ending are placeholders until the dialogue pass (see above).
- Decisions recorded: `docs/decisions.md` → "Chapter title cards are IMAGES", "Title
  banner theme", "Automated playtests" (+ titlecard note).

## Gotchas (carried)
- Glyph extraction: hand-read cut columns from ASCII pixel dumps; kerned neighbors bleed
  into glyph columns (scrub list in the atlas); "It's a Trap!" has a standalone clean 'a'.
- The Status plaque art is a SPRITE; its palette is `Pal_PlayStatusSprites` pal 0 (OBJ
  rows 8–9) — NOT the title palettes. The `titlecard` scenario dumps BG+OBJ palette RAM
  for exactly this kind of trace.
- Synthetic macOS keypresses don't reach mGBA; in-emulator Lua is the path (0.11 nightly).
- Unit marching: read `gBmMapMovement` reachable tiles, not naive closest-tile.

## Blockers
- None. (Portrait look-choices and dialogue writing are collaborative with Nicolas.)

## Asset access (IMPORTANT — established pattern)
Pull a specific file from the **Klokinator FE-Repo** by **vendoring** it (2.3 GB — do NOT
submodule; never claim inaccessible) ([[feedback_vendor_community_assets]]):
```
gh api "repos/Klokinator/FE-Repo/contents/<url-encoded path>?ref=main" \
  --jq '.[] | select(.name=="<exact filename>") | .download_url'
curl -fsSL "<download_url>" -o campaigns/rime-of-the-frostmaiden/<dir>/<dest>.png
```
Credit the `{Artist}` from the filename in the asset dir's README + CREDITS.md.

## Build / run / playtest / debug
- Build: `make CAMPAIGN=rime-of-the-frostmaiden fireemblem8.gba` (green at session end;
  `make check` = drift guard). Regenerate indexes after YAML edits (`tools/gen_*_index.py`).
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
- `tools/portrait_tool.py`, `tools/ref_to_bust.py` — bust pipeline (insert + ref→indexed).
- `tools/build_campaign.py` — `inject_portraits` + `patch_portrait_geometry` (cast slots;
  guests need wiring), `PROLOGUE_*_SLOT` constants, `inject_prologue`, `inject_title_theme`.
- `campaigns/rime-of-the-frostmaiden/chapters/ch00-prologue-a-dagger-of-ice.yaml` — design
  SoT (guest classes/names); `campaigns/.../portraits/` — cast bust assets live here.
- `tools/gen_chapter_title.py` — title-card composer (extend atlas per chapter).
- `tools/playtest/{run.sh,harness.lua,gen_symbols.py}` — playtest harness.
- `docs/decisions.md` — settled decisions incl. portrait/static/geometry entries.

## Memory
- [[manchego-stars-project]] · [[project_manchego_stars_portrait_pipeline]] · [[feedback_portrait_framing]] · [[feedback_portrait_descale_not_crop]] · [[feedback_portrait_static_no_animation]] · [[feedback_show_before_committing_art]] · [[reference_fe8_portrait_resources]] · [[feedback_vendor_community_assets]] · [[reference_fe_repo]] · [[manchego-stars-automated-playtests]] · [[feedback_chapter_vertical_slice]]

## Standing rules
Combat = pure vanilla FE. Maps/sprites = vendor + reskin community/vanilla assets (not
submodule). Story/dialogue = collaborative with Nicolas; art look-picks wait for his OK.
Engine guards stay campaign-agnostic. Auto-push to main once green; don't commit the
`fireemblem8u` submodule pointer. Playtests: machine-run for logic, Nicolas for art/feel.
