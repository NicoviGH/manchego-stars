# Handoff: Portrait Wave 1 at 3/10 (Braulo, RBG, Marty — all clean). NEXT = Wolfram. Recipe is settled; convert from a flat cel-shaded landscape ref.

**Date:** 2026-06-01
**Session focus:** Settled the portrait pipeline + framing recipe and shipped Braulo, Prof. R.B. Geenius, and Marty. Locked the art scope (custom art for all 10 named cast, 3 waves). Next character: **Wolfram**.

## THE SETTLED PORTRAIT RECIPE (use this for Wolfram and the rest)

1. **Ref:** Nicolas generates ONE **flat cel-shaded landscape bust** per character and drops it in `…/References/PCs/`. The proven prompt (it produced "Marty 3" first try):
   > Fire Emblem GBA-style pixel-art bust, **BOLD FLAT CEL-SHADED**, ~15 flat colours, clean dark outline, **NO soft gradients**; smooth even face with 2-3 close tones and **NO white hotspots**; fine detail (gills/fur/etc.) = a **FEW bold thick shapes, not many thin lines**; head-and-shoulders **filling a 6:5 landscape frame**; flat single-colour background; no frame/text/watermark.
   - A blurry/muddy/noisy conversion = the REF is wrong (soft-shaded / too-fine detail). **Fix the ref, never the pipeline.** (I wasted a session adding maxcoverage/contrast/fg-quantize to compensate for bad refs — all reverted. The flat ref + simple pipeline just works.)
2. **Framing — "max zoom without cropping":** detect the FULL subject bbox on the **full-res** image (sample border colour = median of top/left/right edges; fg = RGB-distance ≥45 from it; bbox = rows/cols with >1% coverage). Take the **tightest 1.2-aspect box that still contains the whole bbox** (taller-than-1.2 subject → `crop_h=bbox_h, crop_w=1.2·crop_h`; else width-driven), centred + clamped to the image. Well-made landscape refs sit near 1.2 so this fills ~90%+ with nothing cropped. (Don't eyeball crops off the Read-tool preview — refs are ~2272×1888 and the preview is downscaled.)
3. **Convert:** `python3 tools/ref_to_bust.py "<ref>.png" campaigns/rime-of-the-frostmaiden/portraits/<unit>.png --crop x0,y0,x1,y1 --preview campaigns/.../<unit>_preview.png`
4. **Watermark check:** every Gemini ref has a 4-point sparkle bottom-right. If it lands on the flat bg it's keyed out; if it lands on the subject (or a bright area) it survives. Check the corner; if present, inpaint it **in the source** before converting — fill with the **local** colour (bg colour if on background, the surrounding art colour if on the subject, e.g. RBG's was on the gold coat), then reconvert. (No scipy here — dilate masks with PIL `MaxFilter`.)
5. **Verify + ship:** `python3 tools/portrait_tool.py encode <unit>.png /tmp/sheet.png` (must pack); `open <unit>_preview.png` for Nicolas; commit + push.

**PIPELINE IS SIMPLE — DON'T ADD STEPS.** `ref_to_bust.py` = BOX area-downscale of the full-res crop to 2× target → LANCZOS to 96×80 → UnsharpMask at target (r1/170%/1) → plain **MEDIANCUT** 15-colour quantize. This converted RBG, Braulo, and Marty 3 cleanly.

## Framing facts (FE convention)

- FE busts are **bottom-anchored**: subject fills to the bottom row, transparent **headroom on top**, small side margins (vanilla Eirika: opaque rows 11-79, cols 21-88). Never let the subject float (transparent at the bottom = floating in the textbox). The preview's green = index-0 transparent (invisible in-game).
- **Tall narrow subjects (hats/caps) won't fill the width** and that's correct (Eirika is only ~70% wide). Calibrate on vertical fill, never force width.
- `tools/autoframe.py` exists (pads + bottom-anchors a ref to 1.2) but the **direct containing-crop in step 2 is preferred** (more fill, no padding).

## Workflow rules

- **One character per round:** convert → `open` preview → commit/push → wait for Nicolas's next ref/feedback. Collaborative, not batch.
- **DON'T reconvert already-approved portraits.** Braulo is the original (`a35b329`); Nicolas preferred it over a reconvert. Leave shipped portraits alone unless asked.
- **Claude cannot generate images here** (nanobanana MCP pinned to a retired model). Nicolas generates every ref.

## Current state

- **Wave 1 portraits: 3 / 10** — Braulo (`a35b329`), Prof. R.B. Geenius (`23fa446`), Marty (`3578741`). All clean/approved. **NEXT = Wolfram.** Then Meesmickle, Rootis, Sclorbo, Pinky, Pepperjack, Brie.
- **Build:** green + reproducible on macOS (`make` → ROM, `make verify` → OK). Portraits are authored assets, not yet wired into a built ROM (build-campaign pipeline, issues #13–15, unbuilt).
- **Wave 2 (map sprites) / Wave 3 (battle anims):** not started; behind Wave 1.
- **Story:** ch00–ch08 authored; Ch9–20 blocked on the rest of the DM notes.
- Working tree clean except the known `fireemblem8u` submodule shim drift (leave it).

## Blockers / open

- **Wolfram (next):** needs a flat cel-shaded landscape ref. Existing `Wolfram Portrait.jpeg` is a full-body action shot — **ask Nicolas for a "Marty 3"-style flat bust** (his `art:` brief: mineral/crystalline scales). Read `campaigns/.../pcs/wolfram.yaml` `art:` block before converting.
- **Missing/partial refs:** Pinky has NO ref; Rootis only a character sheet; Pepperjack + Brie share ONE combined image (each needs its own bust).
- **32×32 `_chibi` mini-face** is NOT produced by the pipeline yet (only the 96×80 bust). Small gap; not blocking.
- **#16 (toolchain)** needs a manual GitHub close (agent close blocked by permission classifier).
- **pepperjack/brie `fe_stats.class = null`** — FE-legal class TBD post-MVP (art can still proceed).
- **Rootis & Sclorbo recruitment chapters / Sclorbo signature moment = TBD** (Nicolas to recall).

## FE sprite architecture (for Waves 2–3)

- **Portrait = the only per-CHARACTER art** in vanilla FE8 (96×80 bust = 256×32 tile sheet composited by 6 OAM objects, `gSprite_Face96x96` in `fireemblem8u/src/face.c`; plus a 32×32 `_chibi`).
- **Map sprite = per-CLASS** (`.SMSId`, `src/data_classes.c`); **battle anim = per-CLASS+weapon** (`GetBattleAnimationId`, `include/anime.h`). Vanilla classes give every unit working map/battle sprites for free; **our scope adds CUSTOM ones for the 10 named cast** (Waves 2–3). Enemies stay vanilla.

## Key files

- `tools/ref_to_bust.py` — ref → 96×80 indexed bust. `--crop x0,y0,x1,y1 [--bg-thresh N] [--preview …]`. Backdrop-agnostic (samples border colour). Simple mediancut pipeline.
- `tools/portrait_tool.py` — bust↔FE8 sheet OAM packer. `encode`/`decode`, verified byte-identical.
- `tools/autoframe.py` — optional ref auto-framer (containing-crop preferred instead).
- `campaigns/rime-of-the-frostmaiden/portraits/` — busts (`<unit>.png` + `_preview.png`) + `README.md`. Done: braulo, prof-rbg, marty.
- `campaigns/.../{pcs,npcs}/*.yaml` `art:` block — per-character must-keep brief (read before each conversion).
- Refs: `/Users/Yonick/Documents/Claude/Projects/Manchego Stars / Fire Emblem Game/References/PCs/`.
- `docs/decisions.md` §Art & Audio / `docs/PRD.md` §8 — locked art scope + 3-wave plan.

## Standing rules (how Nicolas wants this work done)

- **Art = full custom for the 10 named cast** (portrait → map sprite → battle anim, in that wave order). **Enemies stay vanilla.** Gemini refs are the **pre-approved source** — convert faithfully, don't re-litigate the look.
- **Stock vanilla FE8 classes/weapons only**; **element = flavor, NEVER a mechanic**. Combat RULES are vanilla FE; the d20 is cosmetic only.
- **Ground FE claims in `fireemblem8u/`**; **ground STORY in the two PDFs** (DM notes Ch1–7 only + the published book).
- **Clean native doc rewrites** (no STALE/reverted banners). **Auto-push to main.** **Collaborative, one-item-at-a-time.**
- **Doc source-of-truth:** per-chapter/unit facts live ONLY in YAML; `docs/CHAPTERS.md`/`CLASSES.md` are GENERATED (`ruby tools/gen-*.rb`, never hand-edit). **Lean repo**; backlog = GitHub issues (M0–M4).
- **`make` must be green at the end of every session. Never commit a broken build.**
