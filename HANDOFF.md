# Handoff: Meesmickle shipped (Wave 1 = 5/10). Portrait pipeline hardened twice (reserve-extremes + hybrid smooth/ink downscale). NEXT = Sclorbo.

**Date:** 2026-06-02
**Session focus:** Converted Meesmickle (vampire-tabaxi bust). Then fixed two recurring quantization problems in `ref_to_bust.py` — washed-out highlights/darks, and blurry "mush" on thin facial features — and re-rendered Marty/Meesmickle/Wolfram/RBG through the fixed pipeline. Sclorbo's clean ref is now on disk; he's next.

## THE BIG DECISIONS THIS SESSION (don't re-litigate)

1. **Reserve palette slots for extremes (`reserve_extremes`, default ON).** MEDIANCUT picks the 15-color palette by pixel *area*, so tiny high-contrast details (Meesmickle's white gems, Marty's black eyes/mouth) get starved into grey. The pipeline now reserves two slots for the foreground's brightest + darkest pixels, and forces the deepest dark to **neutral black (20,17,24)** so eyes/outlines read black, not muddy navy.
2. **Hybrid downscale: smooth base + ink overlay.** The old BOX→LANCZOS area-average blurs thin 1px features into mush; but a *global* crisp/ink pass speckles textured fur and KILLS eye definition on the cats/Wolfram (tried, reverted — see below). The keeper: keep the **smooth area-average everywhere** (clean skin/fur gradients = eyes read), and only **override** a pixel where a genuine near-black line runs (quantize a 3× crop; if ≥4/9 of a 3×3 block is a <150-luminance "ink" color, snap it solid). Marty's eyes/mouth/outlines stay crisp 1px black; everyone else stays smooth.
3. **Follow the reference's colors — don't embellish.** When a detail looks grey/off, the fix is making the pipeline track the ref's TRUE colors, NOT hand-adding white/catchlights or shifting hues. Nicolas corrected me mid-session when I started stamping eye catchlights ("I didn't mean to alter the design… just follow the portrait reference colors"). Faithful-to-ref over "pop."
4. **Framing (unchanged):** face-dominant, shoulders/cape TRAIL OFF the corners (Gilliam convention), mid zoom. Show 2-3 crops when there's a real trade-off. For a tall portrait ref, an FE bust is landscape (96×80) so you can't show the full body — seat the max-height crop low, keep ears/collar uncut. Meesmickle wanted "more body, nothing clipped top/sides" → full-width crop seated low.

## THE SETTLED PORTRAIT RECIPE (use for Sclorbo and the rest)

1. **Ref:** Nicolas uploads a flat cel-shaded **bust** named `<Name> … clean/Clean.png` → `…/References/PCs/`. (These are already near-final pixel art; the tool just makes them FE-legal.)
2. **Crop:** `/tmp/autocrop.py "<ref>"` prints the subject bbox + a 1.2 full-bbox box. If the ref is a tall portrait, that box clamps weird — instead pick a **face-dominant mid-zoom** by hand (full ears/collar in, shoulders trail off corners). Render 2-3 candidate crops, `open` previews, let Nicolas pick.
3. **Convert:** `python3 tools/ref_to_bust.py "<ref>.png" campaigns/rime-of-the-frostmaiden/portraits/<unit>.png --crop x0,y0,x1,y1 --preview <unit>_preview.png` (reserve-extremes + hybrid downscale are the defaults; sharpen defaults 0).
4. **Watermark:** Gemini puts a 4-pt sparkle bottom-right, on the flat bg → keyed out automatically. If it ever lands on the subject, inpaint it in the SOURCE first.
5. **Verify + ship:** `python3 tools/portrait_tool.py encode <unit>.png /tmp/sheet.png` (must pack, ≤16 colors incl. index-0 transparent); `open …_preview.png`; commit + push.

## Current state

- **Wave 1 portraits: 5 / 10** — Braulo (`a35b329`, ORIGINAL, untouched), Prof. R.B. Geenius, Marty, Wolfram, **Meesmickle (this session)**. Marty/Meesmickle/Wolfram/RBG all re-rendered through the new reserve-extremes + hybrid pipeline (`76d881a`). **NEXT = Sclorbo**, then Rootis, Pinky, Pepperjack, Brie.
  - **Meesmickle** = `Meesmickle Clean.png`, crop `0,255,1824,1775` (full width, seated low for max body). Vampire tabaxi: black fur, red Dracula cape + high collar, silvery rhinestone bib, pale-green eyes.
  - **Marty** = `Marty 3.png`, crop `0,35,2222,1887`. Eyes/mouth now solid black via the ink overlay (was blurry maroon mush). The old manual staff pixel-pass from last session is baked into the committed PNG history but is re-derived cleanly by the current pipeline.
  - **Wolfram** = `womfram bust 3.png` (filename typo is real), crop `280,70,1980,1487`.
  - **RBG** = `RBG Landscape.png`, crop `14,17,2258,1887`.
- **Braulo:** LEFT AS-IS. Do not reconvert (hand-tuned crop can't be reproduced; Nicolas's call).
- **Eye-definition knobs** if Nicolas revisits: the ink threshold (`<150` luminance) and coverage (`≥4/9`) in `ref_to_bust.py` are the two dials. Raising coverage / lowering the lum threshold = less ink override (smoother); opposite = crisper/more solid lines.
- **Build:** green + reproducible (`make` → ROM, `make verify` → OK). Portraits are authored assets, not yet wired into a built ROM (build-campaign pipeline, issues #13–15, unbuilt).

## Tried but abandoned

- **Hand-added eye catchlights / color shifts** (Meesmickle) → Nicolas vetoed: follow the ref, don't embellish. The real fix was reserve-extremes tracking the ref's true colors.
- **Global crisp downscale** (`a8b1a17`, superseded by `76d881a`) → a dark-preference on every block speckled textured fur and made the cats'/Wolfram's eyes read LESS defined. Replaced by the hybrid (smooth base + ink-only override).
- (Prior sessions) 170% UnsharpMask, `maxcoverage`/contrast hacks → all reverted; simple pipeline + good ref + the two quantization fixes is the answer.

## Blockers / open

- **Missing/partial refs:** Pinky has NO ref; Rootis only a character sheet; Pepperjack + Brie share ONE combined image (each needs its own bust). Sclorbo's clean ref is NOW on disk.
- **32×32 `_chibi` mini-face + mouth frames** NOT produced yet (only the 96×80 bust). Part of build-campaign wiring (issues #13–15).
- **#16 (toolchain)** needs a manual GitHub close (agent close blocked by permission classifier).
- **pepperjack/brie `fe_stats.class = null`** — FE-legal class TBD post-MVP (art can still proceed).
- **Rootis & Sclorbo recruitment chapters / Sclorbo signature moment = TBD** (Nicolas to recall).

## Next steps (priority order)

1. **Sclorbo portrait** — ref `Sclorbo Portrait clean.png` is on disk. Read `campaigns/rime-of-the-frostmaiden/pcs/sclorbo.yaml` `art:` block first, autocrop, render 2-3 crops, let Nicolas pick, ship. (Wave 1 → 6/10.)
2. Continue Wave 1 one-at-a-time: Rootis, Pinky, Pepperjack, Brie (chase the missing refs).
3. After Wave 1 busts: chibi + mouth frame generation, then build-campaign wiring (issues #13–15) to get portraits into a built ROM.
4. Wave 2 (map sprites) / Wave 3 (battle anims) — behind Wave 1.

## Key files

- `tools/ref_to_bust.py` — ref → 96×80 indexed bust. `--crop x0,y0,x1,y1 [--sharpen N (default 0)] [--bg-thresh N] [--no-reserve-extremes] [--preview …]`. Defaults: reserve-extremes ON + hybrid smooth/ink downscale.
- `tools/portrait_tool.py` — bust↔FE8 256×32 tile sheet OAM packer. `encode`/`decode`, byte-identical. **This IS the tile-sheet creator** (chibi/mouth still TODO).
- `/tmp/autocrop.py` — prints the subject bbox + 1.2 crop for a ref. NOT committed; re-create from the snippet if missing (border-median bg, fg = RGB-dist ≥45, rows/cols >1% coverage).
- `campaigns/rime-of-the-frostmaiden/portraits/` — busts (`<unit>.png` + `_preview.png`) + README. Done: braulo, prof-rbg, marty, wolfram, meesmickle.
- `campaigns/.../{pcs,npcs}/*.yaml` `art:` block — per-character must-keep brief (read before each conversion).
- Refs: `/Users/Yonick/Documents/Claude/Projects/Manchego Stars / Fire Emblem Game/References/PCs/`.
- Vanilla portrait reference: `fireemblem8u/graphics/portrait/portrait_*_tileset.png` (decode with `portrait_tool.py decode`). Gilliam = best heavy-unit framing reference.

## Standing rules (how Nicolas wants this work done)

- **Reference the DECOMP / the ref** — "they should look like the [vanilla] portraits." Ground framing/render/colors in `fireemblem8u/` + the character ref, never guess. **Follow the ref's colors faithfully; don't embellish.**
- **Art = full custom for the 10 named cast** (portrait → map sprite → battle anim, in wave order). **Enemies stay vanilla.** Refs are pre-approved source — convert faithfully.
- **Collaborative, one-item-at-a-time:** convert → `open` preview → commit/push → wait. Show 2-3 options and let Nicolas pick when there's a real trade-off.
- **DON'T reconvert already-approved portraits** (Braulo).
- **Stock vanilla FE8 classes/weapons only**; **element = flavor, NEVER a mechanic**; combat RULES are vanilla FE.
- **Clean native doc rewrites** (no STALE/reverted banners). **Auto-push to main.**
- **Doc source-of-truth:** per-chapter/unit facts live ONLY in YAML; `docs/CHAPTERS.md`/`CLASSES.md` are GENERATED. **Lean repo**; backlog = GitHub issues (M0–M4).
- **`make` must be green at the end of every session.**
