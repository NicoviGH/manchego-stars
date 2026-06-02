# Handoff: Portrait render quality settled (sharpen OFF = vanilla-flat). Wolfram done (4/10), RBG + Marty re-rendered clean. NEXT = Meesmickle.

**Date:** 2026-06-01
**Session focus:** Shipped Wolfram, then made a project-wide render-quality fix (dropped portrait sharpening to match vanilla FE8) and re-rendered RBG + Marty. Fixed Marty's staff (was a quantization artifact). Settled the framing philosophy by grounding it in the decomp.

## THE BIG DECISIONS THIS SESSION (don't re-litigate)

1. **Sharpen is OFF by default.** The old pipeline ran `UnsharpMask(170%)` which added crunchy speckle that looks nothing like FE. Grounded in the decomp (`fireemblem8u/graphics/portrait/`, e.g. Gilliam/Eirika): vanilla busts are **flat hand-drawn art — large clean color regions, dark outlines do the edge work, zero high-freq noise.** `ref_to_bust.py` now has a `--sharpen` flag, **default 0**. Use 0. (See memory [[feedback_portrait_framing]].)
2. **Framing = face-dominant, shoulders TRAIL OFF the corners** (Gilliam convention), NOT sliced flat across the mid-shoulder. A full-shoulder crop shrinks the face to an unreadable blob at 96×80. **Mid zoom is the sweet spot** — render 2-3 crops and let Nicolas pick.
3. **If a ref can't give big face AND contained shoulders** (Gemini keeps drawing huge shoulders / small head), the fix is the **REF** (regen: "larger head, narrower/lower shoulders"), not the crop.

## THE SETTLED PORTRAIT RECIPE (use for Meesmickle and the rest)

1. **Ref:** Nicolas generates a flat cel-shaded **head-and-shoulders BUST** (~6:5 landscape) per character → `…/References/PCs/`. Send him the bust-framing prompt (bakes in FE 1.2 aspect, face large/centered, shoulders inside frame, character tells, flat bg, no watermark) — it removes the face-vs-shoulders crop fight. Action/full-body refs force the broad-shoulder/small-face problem.
2. **Crop = "max zoom without cropping":** detect the subject bbox on full-res (border-median bg; fg = RGB-dist ≥45; rows/cols >1% coverage), take the tightest **1.2** box containing it, centred + clamped. A well-made bust ref sits near 1.2 so this fills ~90%+. Helper: `/tmp/autocrop.py` (this session) prints the crop box for a ref. For broad-shoulder refs, pull to **mid zoom** (face readable, shoulders trail off) instead of full-bbox.
3. **Convert:** `python3 tools/ref_to_bust.py "<ref>.png" campaigns/.../portraits/<unit>.png --crop x0,y0,x1,y1 --preview …_preview.png` (sharpen defaults to 0).
4. **Watermark:** Gemini puts a 4-pt sparkle bottom-right. On flat bg it's keyed out; if it lands on the subject, inpaint it in the SOURCE with the local colour first. (Bust refs this session had it on bg → auto-removed.)
5. **Verify + ship:** `python3 tools/portrait_tool.py encode <unit>.png /tmp/sheet.png` (must pack, ≤16 colors incl. index-0 transparent); `open …_preview.png`; commit + push.

## Current state

- **Wave 1 portraits: 4 / 10** — Braulo (`a35b329`, ORIGINAL, untouched), Prof. R.B. Geenius, Marty, **Wolfram (done this session)**. RBG + Marty + Wolfram all at sharpen-0 / vanilla-flat. **NEXT = Meesmickle.** Then Rootis, Sclorbo, Pinky, Pepperjack, Brie.
  - **Wolfram** = `womfram bust 3.png` (note the typo in the filename), mid-zoom crop `280,70,1980,1487`, sharpen 0. Shoulders trail off corners, crystal pauldrons mostly in frame, face readable. Took ~10 iterations across 3 refs to land — the win was the dedicated bust ref + face-dominant framing.
  - **Marty** = `Marty 3.png`, crop `0,35,2222,1887`, sharpen 0, **+ manual staff pixel pass** (see below).
  - **RBG** = `RBG Landscape.png`, crop `14,17,2258,1887`, sharpen 0.
- **Braulo:** LEFT AS-IS per Nicolas. A sharpen-0 reconvert exists in concept, but the original `a35b329` framing can't be exactly reproduced (hand-tuned crop) and Nicolas chose to keep the original. **Do not reconvert Braulo.**
- **Build:** green + reproducible (`make` → ROM, `make verify` → OK). Portraits are authored assets, not yet wired into a built ROM (build-campaign pipeline, issues #13–15, unbuilt).

## Marty's staff fix (the fiddly bit — a model for palette-limited touch-ups)

- **Problem:** the staff read RED. Confirmed a **15-color quantization artifact** — the ref staff has NO red. Marty 3 shows a **brown wooden shaft + green magic wisps at the tip + Marty's HAND gripping it** (NOT grey stone — Nicolas corrected me twice: "grey was wrong, check Marty 3", then "that grip is his hand not stone").
- **Fix (committed):** palette had 3 near-identical blue-greys (idx 4/6/7, dist 2-6). Collapsed 6+7→4 to free two slots; repurposed idx 6=light wood, idx 7=wisp green, idx 10=dark wood. Repainted the staff zone (x≤21, y34-79) **driven by the ref's true colors** (ref crop downscaled to the 96×80 grid, classify each pixel green/wood/hand-flesh/outline). Grip = Marty's body flesh tones (light grey/cream), not stone-grey. Packs clean at 15 colors.
- **Lesson:** for small mis-quantized details, repurpose redundant palette slots + repaint from the ref's downscaled true-color grid. Don't guess colors — `open` the ref region zoomed and match it.

## Tried but abandoned (this + prior session)

- **170% UnsharpMask** to "sharpen" busts → crunchy noise, un-FE. Reverted to sharpen 0.
- Earlier `maxcoverage`/contrast/fg-quantize hacks (prior session, commit `19ddbff`) → reverted; the simple pipeline + a good ref is the answer.
- Wolfram from action-shot refs (`Wolfram Clean`, `Wolfram 2 no hammer`) → broad shoulders forced a tiny face OR side-cutoff. Solved only by a dedicated **bust** ref + mid-zoom.

## Blockers / open

- **Meesmickle (next):** needs a flat cel-shaded **bust** ref (use the bust-framing prompt). Read `campaigns/.../{pcs,npcs}/meesmickle.yaml` `art:` block before converting. Ref on hand: `Meesmickle Portrait.jpeg` (likely an action shot — ask for a bust).
- **Missing/partial refs:** Pinky has NO ref; Rootis only a character sheet; Pepperjack + Brie share ONE combined image (each needs its own bust).
- **32×32 `_chibi` mini-face + mouth frames** NOT produced yet (only the 96×80 bust). Vanilla portraits also have these. Part of build-campaign wiring (issues #13–15).
- **#16 (toolchain)** needs a manual GitHub close (agent close blocked by permission classifier).
- **pepperjack/brie `fe_stats.class = null`** — FE-legal class TBD post-MVP (art can still proceed).
- **Rootis & Sclorbo recruitment chapters / Sclorbo signature moment = TBD** (Nicolas to recall).

## Next steps (priority order)

1. **Meesmickle portrait** — get a bust ref, autocrop, sharpen 0, mid-zoom if broad-shouldered, ship. (Wave 1 → 5/10.)
2. Continue Wave 1 one-at-a-time: Rootis, Sclorbo, Pinky, Pepperjack, Brie (chase the missing refs).
3. After Wave 1 busts: chibi + mouth frame generation, then build-campaign wiring (issues #13–15) to get portraits into a built ROM.
4. Wave 2 (map sprites) / Wave 3 (battle anims) — behind Wave 1.

## Key files

- `tools/ref_to_bust.py` — ref → 96×80 indexed bust. `--crop x0,y0,x1,y1 [--sharpen N (default 0)] [--bg-thresh N] [--preview …]`. Simple mediancut pipeline, no sharpening by default.
- `tools/portrait_tool.py` — bust↔FE8 256×32 tile sheet OAM packer. `encode`/`decode`, byte-identical. **This IS the tile-sheet creator** (Nicolas asked — yes, we make tile sheets; chibi/mouth still TODO).
- `/tmp/autocrop.py` — (this session, NOT committed) prints the max-zoom 1.2 bbox crop for a ref. Re-create if needed.
- `campaigns/rime-of-the-frostmaiden/portraits/` — busts (`<unit>.png` + `_preview.png`) + README. Done: braulo, prof-rbg, marty, wolfram.
- `campaigns/.../{pcs,npcs}/*.yaml` `art:` block — per-character must-keep brief (read before each conversion).
- Refs: `/Users/Yonick/Documents/Claude/Projects/Manchego Stars / Fire Emblem Game/References/PCs/`.
- Vanilla portrait reference: `fireemblem8u/graphics/portrait/portrait_*_tileset.png` (decode with `portrait_tool.py decode` to view as 96×80). Gilliam = best heavy-unit framing reference.

## Standing rules (how Nicolas wants this work done)

- **Reference the DECOMP** — "they should look like the [vanilla] portraits." Ground framing/render/colors in `fireemblem8u/`, never guess. (Drove the sharpen-0 + Marty-staff fixes this session.)
- **Art = full custom for the 10 named cast** (portrait → map sprite → battle anim, in wave order). **Enemies stay vanilla.** Gemini refs are pre-approved source — convert faithfully.
- **Collaborative, one-item-at-a-time:** convert → `open` preview → commit/push → wait. Show 2-3 options and let Nicolas pick when there's a real trade-off.
- **DON'T reconvert already-approved portraits** (Braulo).
- **Stock vanilla FE8 classes/weapons only**; **element = flavor, NEVER a mechanic**; combat RULES are vanilla FE.
- **Clean native doc rewrites** (no STALE/reverted banners). **Auto-push to main.**
- **Doc source-of-truth:** per-chapter/unit facts live ONLY in YAML; `docs/CHAPTERS.md`/`CLASSES.md` are GENERATED. **Lean repo**; backlog = GitHub issues (M0–M4).
- **`make` must be green at the end of every session.**
