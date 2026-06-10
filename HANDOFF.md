# Handoff: **#43 CLOSED — full opening montage SHIPPED (crawl + world-map tour, GIF-approved end-to-end). NEXT = PC voice interviews, then the FULL Ch1 slice (#21) — dialogue pass comes LAST in the slice (Nicolas's correction 2026-06-10).**

**Date:** 2026-06-10
**Last session:** Wired the #43 tour half end-to-end and closed the issue: the book's
regional map became TWO drawn-map backdrops (Gemini Magvel-style repaint of the whole
dale + the purchased hand-drawn ten-towns close-up, icy duotone, all towns/lakes
re-lettered in 3×5 micro-caps), converted by the new `tools/gen_drawnmap.py`;
`EventScrWM_Prologue_Beginning` rewritten with the 6 locked tour cards (msg 0x8DB) on
vanilla's rhythm — A→B map swap under FADI/FADU, WM_MOVECAM2 pan for the Redwaters card.
Plus Nicolas's review nit: save-slot select banners now all theme-blue (title-theme
recolor extended through `gUnknown_08A07AEA/B0A`). Pushed through `6865c9a` (Closes #43).

**Live checklist = GitHub issues (#20 ch00 done, #43 closed).** HANDOFF = state + next steps.

---

## NEXT SESSION (in order)
1. **PC voice interviews** (in progress 2026-06-10) — structured interview with Nicolas
   per PC → §Voice sections in `lore/*.md` (format = hlin's: summary, diction rules,
   calibration lines, banned list). Chapter-independent prep for ALL dialogue passes.
   Pepperjack & Brie are done by design (each says only their own name).
2. **Full Ch1 slice (#21, The Iron Trail)** — same order as ch00: map → roster/enemies →
   objectives/events → playtests → dialogue pass LAST (Northlook hiring scene opens ch01
   and owns the location card + hiring beat). Don't start with dialogue.
3. **#29 world map** — the tour's drawn maps bootstrap it; the actual WM screen (nodes,
   travel) is still vanilla Magvel. Next art-path slice candidate.
4. Scramsax Hero mug still needs the [F2E] license recheck before distribution (carried).

## Current state
- ✅ **#43 CLOSED**: New Game (MONTAGE=1) plays 7-card crawl over the aurora mural →
  6-card Icewind Dale tour over the two drawn maps → ch00. Full GIF approved ("perfect").
- ✅ **Build modes:** default `make` = dev straight-to-map boot; `MONTAGE=1 make` = full
  montage. **Distribution (#37) must set MONTAGE=1.** Both green; win playtest passes
  both; `verify_text` 3404 msgs / 0 runaway both.
- ✅ Save-slot select: all three slot banners theme-blue (was: only the selected one).
- ✅ ch00 remains DONE end-to-end (see #20).
- ⚠️ ch01+ chapter YAMLs still carry aspirational `ea_file:` fields (schema cleanup
  candidate).
- ℹ️ nanobanana MCP image-gen is broken (retired Gemini model id); Nicolas runs Gemini
  by hand instead (that's how the dale repaint was made — prompt recipe in
  `map-review/43-tour-map/gemini-prompt.md`, gitignored).

## Key facts (decomp-traced this session — also in decisions.md §Story & Dialogue)
- Drawn map = `WM_SHOWDRAWNMAP` → `StartGmapRm` (worldmap_rm.c): one 240×160 screen,
  30×20 TSA over ≤640 4bpp tiles at BG VRAM 0, pal rows 5-8 (TSA +0x5000). Gotchas that
  each cost a debug loop: **tile 0 must be all-transparent** (BG2 parks cleared-to-tile-0
  over the map during blocking display) and **TSA rows are stored bottom-up**
  (`TmApplyTsa` walks dest upward).
- `GMAPRM_FLAG_4` (0x10) on the SHOWDRAWNMAP mask is never read by engine code → our
  map-B selector in the patched consumer (montage-local `*_MontageDrawnMap{A,B}`).
- `WM_MOVECAM2` during drawn-map display scrolls BG1 (the map), not the camera — that's
  how vanilla shows regions hidden under the WM text window (~bottom 50 rows).
- `sub_80895B4`'s `config&1` palette table extends past the 9-color `gPal_08A07AD8`
  label into `gUnknown_08A07AEA/B0A` (save-slot pair 0 normal+dim rows).

## Working agreements (this session)
- Image-model output gets the same treatment as any source art: erase its lettering
  (it melts at GBA scale / models garble glyphs) and re-letter in the pipeline.
- Visual-debug loop that worked: draft render → view → fix coords/rects → re-render;
  and for in-engine bugs, mGBA Lua register/VRAM dumps over theorizing.

## Blockers
- None.

## Key files
- `tools/gen_drawnmap.py` — map-art → drawn-map converter (sources, label-erase rects,
  micro-font, quantizer, `--emit`). Extend here for any future drawn-map screen (#29).
- `tools/build_campaign.py` — `inject_world_tour` (assets, worldmap_rm.c selector patch,
  tour event script, msg 0x8DB) + `inject_title_theme` save-slot palette extension.
- `campaigns/.../events/tour-map-{a-dale,b-towns}.{png,4bpp,tsa,gbapal}` — locked
  backdrops (PNG = review artifact, trio = ROM data).
- `campaigns/.../events/opening-montage.yaml` — crawl + tour text (SoT, fully wired).
- `docs/decisions.md` §Story & Dialogue — lore-crawl + world-map-tour entries.
- `map-review/43-tour-map/` — drafts, Gemini prompt, in-game GIF (gitignored).
- `References/NPCs/2410173-Icewind_Dale_NPCs.pdf` — NEW resource (came with the
  hand-drawn maps): NPC builder + inter-town travel times; useful for story pacing.

## Gotchas (carried)
- Story text: YAML `script:` → build_campaign generates bodies; `make` reruns
  build_campaign and overwrites manual decomp edits. Gate: `python3 tools/verify_text.py`.
- Odd-length NAME strings: pad with [.] (terminator parity; `name_message_body` does it).
- Synthetic macOS keypresses don't reach mGBA; in-emulator Lua is the path.
- Bash cwd drifts between tool calls — always `cd` to repo root in git/make commands.
- GIFs must be opened in **Safari** (Preview shows only the first frame).
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
quotes in picker descriptions); in-engine review = GIFs via `record`, opened in Safari,
wait for his OK before committing art-visible content. Auto-push to main once green;
never commit the `fireemblem8u` submodule pointer. Playtests machine-run for logic,
Nicolas for feel.
