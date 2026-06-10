# Handoff: **#43 lore crawl SHIPPED (GIF-approved twice: cards + aurora mural). NEXT = the #43 world-map TOUR half: convert the book's regional Icewind Dale map into the WM drawn-map backdrop (bootstraps #29), then rewrite `EventScrWM_Prologue_Beginning` with the 6 locked tour cards.**

**Date:** 2026-06-10
**Last session:** Wired the #43 opening-montage lore crawl end-to-end: the 7 locked YAML
cards re-rendered as vanilla's 7 opening slides (`tools/gen_subtitle_cards.py`, Georgia 13
+1px tracking quantized into the vanilla ramp), display LUT retimed, and vanilla's brown
rune-wall backdrop replaced with the book's aurora-township painting via montage-LOCAL
symbols (the rune wall is shared by shops/chapter-intro/endings — never overwrite it).
Both rounds GIF-reviewed and approved by Nicolas. Pushed through `12b7756`.

**Live checklist = GitHub issue #43 (montage) / #20 (ch00).** HANDOFF = state + next steps.

---

## NEXT SESSION (in order)
1. **#43 tour half** — Nicolas picked the backdrop: the book's regional Icewind Dale map
   (`References/Ten-Towns-Maps/icewind-dale-rime-of-the-frostmaiden-maps_compress.pdf`
   p.1, render with `pdftoppm -r 200`; all ten towns + three lakes labeled, engraving
   style ≈ FE8's drawn map). Steps: study FE8's WM drawn-map format
   (`WM_SHOWDRAWNMAP`, worldmap.c / graphics/world_map) → convert the map (show Nicolas
   conversion drafts BEFORE wiring) → rewrite `EventScrWM_Prologue_Beginning` with the 6
   locked `town_tour` cards (msg 0x8DB body + camera pans per card; skip vanilla's
   nation-highlight overlays — they're Magvel-shaped polygons). This bootstraps #29.
2. ch01 dialogue pass (`/dialogue-pass`, Northlook hiring scene owns the location card +
   hiring beat) — the other parked track.
3. Scramsax Hero mug still needs the [F2E] license recheck before distribution (carried).

## Current state
- ✅ **#43 crawl half SHIPPED** (`d05384c` wiring, `12b7756` mural): New Game plays the
  7-card crawl over the aurora township, then (tour still SKIPWN'd) loads the ch00 map.
- ✅ **Build modes:** default `make` = dev straight-to-map boot (unchanged playtests);
  `MONTAGE=1 make` = crawl wired. **Distribution (#37) must set MONTAGE=1.** Both modes
  build green; win playtest passes both (bootToMap's START self-skips the crawl).
- ✅ ch00 remains DONE end-to-end (see #20); `verify_text` 0 runaway.
- ⚠️ Tour text (`town_tour:` in `events/opening-montage.yaml`) stays YAML-parked until
  the drawn-map backdrop lands.
- ⚠️ ch01+ chapter YAMLs still carry aspirational `ea_file:` fields (schema cleanup
  candidate).
- ℹ️ nanobanana MCP image-gen is broken (retired Gemini model id) — book art extraction
  via pdftoppm worked better anyway.

## Key facts for the tour (decomp-traced this session)
- The crawl is 7 PRERENDERED slides (`gOpSubtitleGfxLut`, opsubtitle.c) with hardcoded
  transitions (fades 0-1, flare on 2, cross-blends 3-4, mural close 5-6; START skips) —
  our 7-card budget rides it with ZERO proc changes. The TOUR is real message text:
  `WM_TEXT(0x8DB)` inside `EventScrWM_Prologue_Beginning` (src/events/prologue-wm.h),
  TEXTCONT segments interleaved with `WM_MOVECAM2` pans + portrait/highlight calls.
- Slide gfx pipeline: PNG → FETSATOOL (`%.feimg2.bin %.fetsa2.bin: %.png`) → `%.lz` —
  drop PNGs in `fireemblem8u/graphics/op_subtitle/`, delete stale intermediates, make
  reconverts. Slide PNG index 0 is GBA-transparent (black backdrop) — slate bg in the
  PNG is a converter placeholder only.
- Mural shape: 640 sequential 4bpp tiles (256×160) on palette row 15
  (`sub_80C48F0`), palette faded to `Pal_MontageMural` during the flare slide.

## Working agreements (this session)
- Backdrop/mural swaps for shared vanilla assets = patch the CONSUMER to local symbols,
  never overwrite the shared gfx (decisions.md §Story & Dialogue, lore-crawl entry).
- Montage builds are flag-gated, not default — keeps playtest/dev loop byte-identical.

## Blockers
- None.

## Key files
- `tools/gen_subtitle_cards.py` — card renderer + mural treatment (vanilla metrics in
  constants; extend here for any future slide-style screens).
- `tools/build_campaign.py` — `inject_opening_montage` (+ `_cut_boot_intro(montage=)`),
  PATCHED_DECOMP_FILES now covers opsubtitle.c, data_opsubtitle.s, slide PNGs.
- `campaigns/.../events/opening-montage.yaml` — locked crawl + tour text (SoT).
- `campaigns/.../events/opening-mural.png` — mural source art (book ch1 opener).
- `docs/decisions.md` §Story & Dialogue — lore-crawl entry (build modes, mural rule).
- `map-review/43-*` — review GIFs/mockups from this session (gitignored).

## Gotchas (carried)
- Story text: YAML `script:` → build_campaign generates bodies; `make` reruns
  build_campaign and overwrites manual decomp edits. Gate: `python3 tools/verify_text.py`.
- Odd-length NAME strings: pad with [.] (terminator parity; `name_message_body` does it).
- Synthetic macOS keypresses don't reach mGBA; in-emulator Lua is the path.
- Bash cwd drifts between tool calls — `git commit` once landed in the fireemblem8u
  submodule; always `cd` to repo root in git commands.
- Frostmaiden book: `references/References/icewind-dale-...pdf` (symlink →
  `/Users/Yonick/Documents/D&D/5E/`); DM notes:
  `/Users/Yonick/Documents/Claude/Projects/Manchego Stars / Fire Emblem Game/References/DungeonMasterNotesIcewindDale.pdf`.
- PDF page = printed page + 1 (Cold Open boxed text: printed p.22 → PDF 23).

## Memory
- [[manchego-stars-project]] · [[feedback_collaborative_story_planning]] ·
  [[feedback_answer_before_picker]] · [[feedback_sharing_visual_drafts]] ·
  [[feedback_use_decomp]] · [[feedback_show_before_committing_art]] ·
  [[manchego-stars-automated-playtests]] · [[feedback_vendor_community_assets]]

## Standing rules
Combat = pure vanilla FE. Story/dialogue = collaborative (variants → Nicolas picks; full
quotes in picker descriptions); in-engine review = GIFs via `record`, wait for his OK
before committing art-visible content. Auto-push to main once green; never commit the
`fireemblem8u` submodule pointer. Playtests machine-run for logic, Nicolas for feel.
