# Handoff: Portrait pipeline PROVEN end-to-end + Braulo (1st portrait) shipped. NEXT = Prof. R.B. Geenius portrait — waiting on Nicolas to provide a clean frameless Gemini bust ref, then it's 2 commands to convert + insert.

**Date:** 2026-06-01
**Session focus:** Stood up and proved the entire custom-portrait pipeline (gbagfx round-trip → FE8 OAM tile format → bust↔sheet converter), then converted Nicolas's Nano-Banana/Gemini reference into the first game-ready portrait (Braulo) and committed reusable tooling.

## Accomplished this session

- **gbagfx round-trip PROVEN.** PNG → 4bpp → PNG is lossless (0/8192 pixel-index diffs; the grayscale you see on a raw decode is just a preview inversion — the ROM uses the separate `.gbapal`). Painted a test block into a vanilla portrait, rebuilt, ROM diverged from vanilla + booted in mGBA, then reverted → `make verify` = `OK` (byte-identical vanilla restored). The macOS shims in the submodule (`fireemblem8u/scripts/*` shebangs) are the known, expected drift — leave them.
- **FE8 portrait format reverse-engineered + verified.** A talking portrait is NOT a linear bitmap: the tracked `portrait_<Name>_tileset.png` (256×32, indexed 16-color) is a **32-tile-wide VRAM grid**, and **6 OAM sprite objects** (`gSprite_Face96x96` in `fireemblem8u/src/face.c`) composite it into the **96×80** bust. Palette index 0 = transparent chroma key. Confirmed by reconstructing vanilla Eirika pixel-perfect.
- **`tools/portrait_tool.py`** — `decode` (sheet→bust) / `encode` (bust→sheet) using that OAM layout. Verified byte-identical round-trip on Eirika (0 diffs across all 6144 covered px). Committed `0141a36`.
- **`tools/ref_to_bust.py`** — translates a clean Gemini reference into the 96×80 indexed bust: crop → flat-bg segmentation (bright+desaturated cream, border-flood seeded from top/left/right since the subject fills the bottom) → speck/hole cleanup → sharpen+downscale → 15-color quantize → clean silhouette. Committed `a35b329`.
- **Braulo's portrait shipped (v1, APPROVED).** Converted `References/PCs/Broulo Face Clean.png` → `campaigns/rime-of-the-frostmaiden/portraits/braulo.png` (+ `braulo_preview.png`). Verified through `portrait_tool.py encode/decode`. Nicolas approved the look as-is (kept the "curious" face; did NOT enforce the brief's berserker-fury). `portraits/README.md` documents the workflow.

## Major workflow changes this session (also in memory)

- **Nicolas is not an artist / can't pixel.** Claude generates the art via tooling; never propose "draw it in Aseprite."
- **Nano-Banana rule RELAXED:** Gemini/Nano-Banana images MAY originate the final art (the old "concept-ref only" rule is lifted for portraits). Nicolas's only worry was in-game fidelity — solved.
- **Assume the provided Gemini ref is APPROVED:** convert faithfully, don't re-litigate expression/aesthetics or push tweaks. Nicolas drives art by choosing what to generate on his side. Best source = clean **frameless head-and-shoulders bust on a flat background** (the roundel-framed first ref needed heavy segmentation; the frameless "Clean" version converted far better).

## Tried but didn't work (lessons)

- **Regenerating Braulo via the nanobanana MCP** — the MCP server is pinned to the retired model `gemini-2.5-flash-image-preview` (404); the API key only lives in the MCP server's env (not the shell), so direct `curl` regen is also blocked. **Don't try to generate images from here — Nicolas generates them on his side and drops them in `References/PCs/`.**
- **Background removal dead-ends:** color-distance flood = finicky; dark-frame removal leaked through the crab's own shadows and punched holes; a geometric ellipse mask clipped the eyestalks. **Winning recipe = HSV cream-key (bright+desaturated) + border-flood from top/sides only + connected-component speck/hole cleanup** (now baked into `ref_to_bust.py`).
- Naive 12-wide row-major tile reassembly = scrambled; the OAM layout is required.

## Current state

- **Build:** green + reproducible on macOS. `make` → ROM, `make verify` → `OK`. No campaign data injected yet (build-campaign pipeline, issues #13–15, still unbuilt).
- **Portraits:** pipeline complete + reproducible. **1 of 8 done** (Braulo). 7 PCs + 2 recruits remain (briefs in each unit YAML `art:` block).
- **Story:** all 9 MVP chapters (ch00–ch08) authored. Ch9–20 still blocked on the rest of the DM notes.

## Blockers / open

- **Next portrait (Prof. R.B. Geenius) needs a clean Gemini bust ref from Nicolas** — frameless, flat background, head-and-shoulders. Then conversion is 2 commands. (Standing pattern: Nicolas generates each character's clean bust; Claude converts.)
- **#16 (toolchain)** still needs a manual GitHub close (agent close blocked by permission classifier).
- **pepperjack/brie `fe_stats.class = null`** — FE-legal class TBD post-MVP (art can still proceed).
- **Rootis & Sclorbo recruitment chapters = TBD** (Nicolas to recall). Sclorbo signature moment also TBD.
- **Ch 9–20 plot** blocked on the rest of the DM notes.

## Next steps (priority order) — PORTRAITS (7 remaining)

Order by story appearance: **Prof. R.B. Geenius (Ch1) → Wolfram (Ch3) → Marty (Ch6) → Meesmickle (Ch9) → Rootis/Sclorbo (TBD)**, then **Pepperjack & Brie** (recruits, build-now). Braulo (Ch8) was done first as the end-to-end test unit.

1. **Prof. R.B. Geenius portrait.** Ask Nicolas for a clean frameless Gemini bust ref (green-ratfolk manic grin, purple top-hat, yellow coat collar; face-forward, NO gun in the bust — per `pcs/prof-rbg.yaml` `art:`). Then:
   - `python3 tools/ref_to_bust.py "<ref.png>" campaigns/rime-of-the-frostmaiden/portraits/prof-rbg.png --crop x0,y0,x1,y1 --preview campaigns/.../portraits/prof-rbg_preview.png` (tune `--crop` to ~1.2 aspect, view the preview, iterate the box).
   - `python3 tools/portrait_tool.py encode <bust> /tmp/sheet.png` to confirm it packs.
   - Show Nicolas the `_preview.png`; commit + push.
2. Repeat for the remaining PCs as Nicolas supplies each clean ref.
3. **Map sprites** (16×16) — custom per cast member (pipeline TBD; chibi format in the same portrait table).
4. **Battle animations** — custom; hardest; likely post-MVP `stretch`.

## Key files

- `tools/portrait_tool.py` — bust↔sheet converter (the verified OAM packer). `decode`/`encode`.
- `tools/ref_to_bust.py` — Gemini ref → 96×80 indexed bust. `--crop x0,y0,x1,y1 [--preview ...]`.
- `campaigns/rime-of-the-frostmaiden/portraits/` — authored busts (`<unit>.png` 96×80 indexed + `_preview.png`) + `README.md` (workflow). `braulo.png` = done.
- `campaigns/rime-of-the-frostmaiden/{pcs,npcs}/*.yaml` `art:` block — per-character design brief (read before converting each).
- Gemini source refs: `/Users/Yonick/Documents/Claude/Projects/Manchego Stars / Fire Emblem Game/References/PCs/` (Nicolas drops clean busts here).
- `fireemblem8u/src/face.c` (`gSprite_Face96x96`) — the authoritative OAM portrait layout.
- `Makefile` (root) — macOS build shims; `make` / `make verify` / `make clean`.

## Standing rules (how Nicolas wants this work done)

- **Art = full custom**, generated by Claude via tooling (Nicolas can't pixel). **Gemini/Nano-Banana refs are the source and are pre-approved** — convert faithfully, don't re-litigate the look. Nicolas supplies a clean frameless bust per character; **Claude cannot generate images from here** (MCP model retired).
- **Stock vanilla FE8 classes/weapons only**; **element = flavor, NEVER a mechanic**. Combat RULES are vanilla FE; the d20 is cosmetic only.
- **Ground FE claims in `fireemblem8u/`**; **ground STORY in the two PDFs** (DM notes Ch1–7 only + the published book).
- **Clean native doc rewrites** (no STALE/reverted banners). **Auto-push to main.** **Collaborative, one-item-at-a-time** walkthroughs.
- **Doc source-of-truth:** per-chapter/unit facts live ONLY in YAML; `docs/CHAPTERS.md`/`CLASSES.md` are GENERATED (`ruby tools/gen-*.rb`, never hand-edit). **Lean repo**; backlog = GitHub issues (M0–M4).
- **`make` must be green at the end of every session. Never commit a broken build.**
