# Handoff: Rootis shipped (Wave 1 = 7/10). Pixel-touch-up template generalized (outline + faceted nose + halo cleanup). NEXT = chase refs for Pinky / Pepperjack / Brie.

**Date:** 2026-06-02
**Session focus:** Converted **Rootis** (the two-segment snow-golem PC) to a 96×80 bust. Nicolas supplied two fresh refs ("Rootis Bust 1/2"); we picked **Bust 1** (cleaner pale-blue-white snow, characterful 3/4 tilt) and finished it with a deterministic **pixel-by-pixel hand pass** (Marty-style) instead of any recolour. Shipped + pushed (commit `5ac9a4e`).

## THE DECISIONS THIS SESSION (don't re-litigate)

1. **Rootis = faithful Bust 1 + a hand pass, NOT a hybrid recolour.** First attempt blended Bust 2's orange carrot + darkened blacks into Bust 1 → Nicolas: *"you did too much work here that reduced the fidelity."* The rule held: **follow the ref's true colours, don't embellish.** Final keeps Bust 1's own palette (red carrot included) and only *cleans/sharpens* what the downscale degraded.
2. **`rootis_cleanup.py` is the deterministic touch-up** (run after `ref_to_bust.py`, reproduce cmd in its docstring). Five passes, all colour-keyed so they survive quantizer drift:
   - **despeckle** — a lone pixel matching none of its 4 neighbours, neighbours agreeing ≥3, AND a *strong* colour outlier (RGB dist > 70) → snap to majority. **The distance gate is load-bearing:** an un-gated despeckle ate form-defining highlights (`14→1`) and facet transitions (`2→3`) and Nicolas said *"it got worse."* Gating to >70 fixes only true intrusions (a blue pixel inside the red carrot, purple flecks) and leaves highlights/shading intact (~18 px changed, not 64).
   - **faceted carrot** — the flat red blob → a geometric pyramid: detect the red mask (3× hole-fill to absorb trapped light specks), then paint outer-edge + bottom tip = **maroon (92,22,30)**, a bright **pink ridge (236,152,150)** ~40% in from the left, right-of-ridge = **dark facet (138,34,42)**, lit-left keeps the main red. Tones sampled from the ref's own carrot.
   - **continuous dark outline** — every body pixel touching transparent bg → coal. Gives the **strong unbroken silhouette line the ref has**. NB: an earlier version that only darkened the *purple* fringe (leaving white edge pixels light) looked jaggy/worse — you must darken the **whole** boundary uniformly, not a subset.
   - **mouth-halo cleanup** — the ragged **purple anti-alias halo** ringing the coal mouth dots is what read as "specks." Scoped to the mouth band (rows 49–66 so eyes/shadow purple are untouched), each purple pixel snaps to its dominant non-purple neighbour, ties breaking toward the **lighter face** colour so dots keep crisp edges instead of blobbing together.
   - **final despeckle** on the settled geometry.
3. **Zoom into the headroom.** Nicolas: there's vertical space above the head — use it. Crop tightened from `54,40,1686,1400` → **`126,100,1614,1340`** (~9% zoom), keeping ~2 px headroom so the top isn't cut (he earlier vetoed any top crop). Bigger face = carrot/eyes/mouth render at more pixels = the pixel touch-ups are cleaner. **This "use the headroom" move is reusable for any small-featured cast member.**
4. **Crisp mode is OUT for Rootis** — it muddied the orange carrot (the source-true freq palette won't reserve a feature that small). Smooth + hand pass wins (same conclusion as Marty).

## THE PIXEL-TOUCH-UP TEMPLATE (now two examples — established path for degraded small features)

`marty_eye_fixup.py` (hand-drawn face on a smooth body) and `rootis_cleanup.py` (outline + faceted nose + halo cleanup) are the two reference scripts. **Pattern:** render faithful with `ref_to_bust.py`, then a deterministic, colour-keyed companion script for the features the ~23× downscale can't hold. Reproduce command lives in each docstring. README ("Per-portrait hand passes") documents both.

## PIPELINE KNOBS (all in `tools/ref_to_bust.py`)

- `--downscale smooth|crisp` (default smooth). smooth = area-average + ink overlay (painterly/textured refs, incl. Rootis's low-poly gradients). crisp = NEAREST + source-true freq palette (clean flat cel art only; **muddies tiny coloured features like a carrot** — avoid when a small accent must survive).
- `--ink-lum N` (150) / `--ink-cov N` (4) — smooth ink-overlay line dials.
- `--crop x0,y0,x1,y1`, `--sharpen` (0), `--bg-thresh` (45), `--no-reserve-extremes`, `--preview`.
- Reserve logic (default ON): protects luminance extremes **plus** up to 3 saturated-hue clusters (distinct-RGB + warm/red rescue) the area palette would drop. Cool/greyscale busts fire nothing → byte-identical.

## PER-PORTRAIT RENDER SETTINGS (re-run verbatim). Refs: `…/References/PCs/`. Ship → `campaigns/rime-of-the-frostmaiden/portraits/<unit>.png`.

| unit | ref file | --crop | mode + hand pass |
|---|---|---|---|
| braulo | `Broulo Face Clean.png` | `153,129,1888,1574` | smooth |
| marty | `Marty 3.png` | `0,35,2222,1887` | smooth + `marty_eye_fixup.py` (hybrid face) |
| meesmickle | `Meesmickle Clean.png` | `0,255,1824,1775` | smooth |
| prof-rbg | `RBG Landscape.png` | `14,17,2258,1887` | smooth |
| wolfram | `womfram bust 3.png` (typo real) | `280,70,1980,1487` | smooth |
| sclorbo | `Sclorbo Portrait clean.png` | `342,297,1786,1500` | smooth |
| **rootis** | `Rootis Bust 1.png` | `126,100,1614,1340` | smooth + `rootis_cleanup.py` |

## Current state

- **Wave 1 portraits: 7 / 10** — braulo, prof-rbg, marty, wolfram, meesmickle, sclorbo, **rootis**. Remaining: Pinky, Pepperjack, Brie (all ref-blocked, see Blockers).
- **Build:** green last verified (`make verify` → ROM OK). Portraits are authored assets, not yet wired into a built ROM (build-campaign pipeline, issues #13–15, unbuilt).
- **Rootis bust** = faithful Bust 1 at the zoomed crop: strong coal silhouette outline, faceted carrot (pink ridge / red lit facet / dark right facet / maroon tip), clean coal eye squares + mouth dots, two-segment body, ~2 px headroom. Approved.
- **`fireemblem8u` submodule** shows local changes in `git status` (pre-existing, not from this work) — left untouched; don't blindly commit the submodule pointer.

## Tried but abandoned (this session)

- **Hybrid recolour of Rootis** (Bust 2 orange carrot + darker blacks onto Bust 1) → rejected, *reduced fidelity*. Keep the ref's own colours.
- **Un-gated despeckle** (any lone pixel → neighbour majority, 64 px) → ate highlights/facet transitions, *"got worse."* Fixed with the >70 colour-distance gate (~18 px).
- **Outline tidy that only darkened the purple fringe** → jagged (white edge pixels stayed light). Fixed by darkening the *entire* bg-adjacent boundary uniformly.
- **Crisp mode for Rootis** → muddied the carrot. Smooth + hand pass instead.
- (Carried from before) Marty crisp/reframe, Wolfram ink bump, global crisp downscale, UnsharpMask — still abandoned.

## Blockers / open

- **Missing/partial refs for the last 3 Wave-1 busts:** **Pinky** has NO ref; **Pepperjack + Brie** share ONE combined image (`data/portraits/pepperjack-and-brie.jpeg`) — each needs its own clean single bust. **Chase these from Nicolas before converting.**
- **32×32 `_chibi` mini-face + mouth frames** not produced for ANY unit yet (only the 96×80 busts). Frame spec = `fireemblem8u/include/types.h` `struct FaceData` (img/imgChibi/pal/imgMouth/xMouth/yMouth/xEyes/yEyes/blinkKind). Study vanilla via `portrait_tool.py decode` before authoring. Part of build-campaign wiring (issues #13–15).
- **#16 (toolchain)** needs a manual GitHub close (agent close blocked by permission classifier).
- **pepperjack/brie `fe_stats.class = null`** — FE-legal class TBD post-MVP (art can still proceed once refs exist).
- **Rootis & Sclorbo recruitment chapters / Sclorbo signature_moment** = TBD (Nicolas to recall; `rootis.yaml`/`sclorbo.yaml` `signature_moment.chapter = tbd`).

## Next steps (priority order)

1. **Chase the last 3 Wave-1 refs from Nicolas** (Pinky bust; separate Pepperjack + Brie busts). Then convert one-at-a-time: autocrop → render → pick → hand pass if needed → ship. (Wave 1 → 10/10.)
2. **After Wave 1 busts:** chibi + mouth-frame generation (extend `portrait_tool.py`), then build-campaign wiring (issues #13–15) to get portraits into a built ROM.
3. Wave 2 (map sprites) / Wave 3 (battle anims) — behind Wave 1.

## Key files

- `tools/ref_to_bust.py` — ref → 96×80 indexed bust (smooth default / crisp opt-in; reserve-extremes + chroma reservation). Knobs above.
- `campaigns/rime-of-the-frostmaiden/portraits/rootis_cleanup.py` — Rootis hand pass (despeckle + faceted carrot + continuous outline + mouth-halo cleanup). Colour-keyed, reproducible.
- `campaigns/rime-of-the-frostmaiden/portraits/marty_eye_fixup.py` — the other hand-pass example (smooth body + hand-drawn face).
- `tools/portrait_tool.py` — bust↔FE8 256×32 tile-sheet OAM packer (`encode`/`decode`, byte-identical). Chibi/mouth still TODO.
- `/tmp/autocrop.py` + `/tmp/grid.py` — NOT committed; recreate. autocrop = border-median-bg / fg-dist≥45 bbox; grid.py overlays a 200-px coordinate grid on a thumbnail (the fastest way to place a face-dominant crop). For a lost crop, recover via silhouette IoU vs the committed bust.
- `campaigns/rime-of-the-frostmaiden/portraits/` — busts + `_preview.png` + README (incl. "Per-portrait hand passes").
- `campaigns/.../{pcs,npcs}/*.yaml` `art:` block — per-character must-keep brief (read before each conversion).
- Vanilla portrait reference: `fireemblem8u/graphics/portrait/portrait_*_tileset.png` (decode with `portrait_tool.py decode`).

## Standing rules (how Nicolas wants this work done)

- **Follow the ref's colours faithfully; don't embellish.** When something looks off, make the pipeline/hand-pass track the ref's TRUE hue — never hand-add pop or blend refs. (Re-confirmed hard this session.)
- **Reference the DECOMP / the ref** for framing/render/colours. **Face-dominant** FE8 convention; use available headroom to zoom small faces.
- **Art = full custom for the 10 named cast** (portrait → map sprite → battle anim, wave order). **Enemies stay vanilla.**
- **Collaborative, one item at a time:** render → `open` preview → wait for Nicolas → iterate → commit/push. Show 2–3 options on real trade-offs (framing, ref choice).
- **Stock vanilla FE8 classes/weapons only**; **element = flavor, NEVER a mechanic**; combat RULES are vanilla FE.
- **Clean native doc rewrites** (no STALE/reverted banners). **Auto-push to main** (no need to ask).
- **Doc source-of-truth:** per-chapter/unit facts live ONLY in YAML; `docs/*` are GENERATED. **Lean repo**; backlog = GitHub issues (M0–M4).
- **`make` must be green at the end of every session.**
