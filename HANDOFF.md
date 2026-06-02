# Handoff: Sclorbo shipped (Wave 1 = 6/10). Pipeline gained chroma-reservation + crisp mode. Marty/Braulo/Meesmickle re-rendered. NEXT = Rootis (chase ref).

**Date:** 2026-06-02
**Session focus:** Converted Sclorbo (the faceless rune-mask Chwinga). Doing so exposed two new color-fidelity gaps in `ref_to_bust.py`, both fixed this session, plus a clean-cel-art rendering mode. Marty, Braulo, and Meesmickle were re-rendered through the improved pipeline (Nicolas reviewed each).

## THE BIG DECISIONS THIS SESSION (don't re-litigate)

1. **Reserve palette slots for saturated HUES, not just luminance extremes (`reserve_extremes` path, default ON).** Last session's reserve-extremes only protects the brightest/darkest pixels. Area-based MEDIANCUT still starves a vivid *mid-tone* minority color (Sclorbo's red tassel stripes + tan robe folded to grey while six near-identical dark teals ate the palette). The pipeline now reserves up to **3** extra slots for dominant saturated clusters the area palette would drop: a *distinct-RGB-cluster* pass (catches a vivid shade sharing a hue with a duller dominant region, e.g. a dark sigil-cyan vs the pale mask) **plus** a *warm/red rescue* (red accents fragment across brightness so no single RGB bin clears the gate; reserve the mean of genuinely-red pixels). Gated on chroma + area + dedup → **cool/greyscale busts fire nothing and stay byte-identical** (verified: Marty/Wolfram/RBG unchanged; only Meesmickle's red cape changed → gained fold-shading, re-shipped).
2. **`--downscale crisp` for refs that are ALREADY clean cel art (Marty).** The smooth area-average downscale (default) is right for *painterly/textured* refs (the cats, Wolfram) — but on clean line art it invents grey anti-alias halos around clean eyes/mouths/edges across the ~23× reduction. Crisp mode = **NEAREST point-sample, skip the ink overlay**, with the palette built from the **source's own most-frequent flat colors** (true hues — Marty's terracotta scarf is `211,44,38`, not the MEDIANCUT centroid `166,72,62` rosy-pink) + a forced neutral-black slot. Default stays `smooth`; crisp is opt-in per clean ref. **No despeckle** (an earlier despeckle pass filled in eye catchlights → solid rectangular eyes; it can't tell a wanted catchlight from an unwanted speck — removed).
2b. **Marty = HYBRID (smooth body + hand-drawn face), not crisp.** FE8 portraits are face-DOMINANT (vanilla Eirika's eyes are 5–6px because the head fills the frame). Marty's framing keeps the whole mushroom (Nicolas won't compromise the framing / cut the cap), so his face is only ~20px and the eyes are ~2–3px — below what *any* downscale renders cleanly. Solution: render the **body** with the smooth downscale (clean gills/cap/scarf/tunic/staff, no crisp speckle) and **hand-draw the face** on top via `portraits/marty_eye_fixup.py` — it clears the blurry face band and draws two oval eyes (white catchlight spec INSIDE the black) + a wide flattish smile, matching the ref's eye/mouth proportions. Palette slots are found by colour so it survives quantizer drift. Re-apply after any Marty re-render. **This hybrid (smooth base + scripted hand-face) is the template for any future small-faced cast member.**
3. **Follow the ref's TRUE hues — the fix is always "track the ref better," never embellish.** Both fixes above make the palette represent colors genuinely in the source, not hand-added pop. (Same principle that vetoed eye-catchlight stamping last session.) When Marty looked pink/blurred, Nicolas's steer was "reference the Marty 3 image for true accurate color hues" — and the answer was a source-true frequency palette, not saturation boosting.
4. **Braulo IS reconvertible now (supersedes the old "leave as-is").** The original crop was never recorded, so it was recovered via **silhouette IoU search** (0.95 match → crop `153,129,1888,1574`) so framing is unchanged but the orange/grey now read vivid (old Braulo was pre-reserve-extremes = muddy). Nicolas: "match the original cropping" — done via the IoU recovery.

## NEW PIPELINE KNOBS (all in `tools/ref_to_bust.py`)

- `--downscale smooth|crisp` (default smooth). crisp = clean cel art (NEAREST + source-true palette + despeckle, no ink pass).
- `--ink-lum N` (default 150) / `--ink-cov N` (default 4) — line-definition dials for the **smooth** ink overlay. Raise ink-lum to snap darker-but-not-black lines; lower ink-cov so thinner lines survive. (Added when exploring Wolfram's crevice lines; defaults unchanged so nothing regressed.)
- Existing: `--crop`, `--sharpen` (default 0), `--bg-thresh` (45), `--no-reserve-extremes`, `--preview`.

## PER-PORTRAIT RENDER SETTINGS (so they're reproducible — re-run verbatim)

Refs live in `…/References/PCs/`. All ship to `campaigns/rime-of-the-frostmaiden/portraits/<unit>.png`.

| unit | ref file | --crop | mode |
|---|---|---|---|
| braulo | `Broulo Face Clean.png` | `153,129,1888,1574` | smooth |
| marty | `Marty 3.png` | `0,35,2222,1887` | **smooth** (default) + run `portraits/marty_eye_fixup.py` after (hybrid: smooth body + hand-drawn face) |
| meesmickle | `Meesmickle Clean.png` | `0,255,1824,1775` | smooth |
| prof-rbg | `RBG Landscape.png` | `14,17,2258,1887` | smooth |
| wolfram | `womfram bust 3.png` (typo real) | `280,70,1980,1487` | smooth |
| sclorbo | `Sclorbo Portrait clean.png` | `342,297,1786,1500` | smooth |

## Current state

- **Wave 1 portraits: 6 / 10** — braulo, prof-rbg, marty, wolfram, meesmickle, **sclorbo (this session)**. **NEXT = Rootis**, then Pinky, Pepperjack, Brie.
  - **Sclorbo** = faceless rune-mask Chwinga. Crop is a face-dominant mid-zoom (Nicolas picked framing "D"): mask dominant + sigil legible, vivid flame aura, fur ruff, red/cyan tassels, tan robe, staff tip; drops only the low pendant. The chroma fix is what made the red stripes / tan robe / darker sigil-cyan survive.
  - **Marty** = hybrid (smooth body + `marty_eye_fixup.py` hand face). Oval eyes w/ internal white catchlight, wide flattish smile, smooth gills/staff/tunic. Framing kept (whole mushroom). Approved 2026-06-02 after several iterations.
  - **Braulo** = re-rendered vivid at the IoU-recovered original framing.
  - **Meesmickle** = re-shipped; red cape gained fold-shading from the chroma fix.
  - **Wolfram, RBG** = byte-identical to last session (chroma fix didn't fire on them).
- **Build:** green (`make verify` → ROM OK). Portraits are authored assets, not yet wired into a built ROM (build-campaign pipeline, issues #13–15, unbuilt).

## Tried but abandoned

- **Wolfram line-definition bump** (`--ink-cov 3` / `--ink-lum 175`) → crevices crisped up but it **drowned the white in his eyes**; Nicolas didn't want that, so Wolfram stays as-shipped (smooth defaults). The `--ink-*` flags remain available if revisited *with* an eye-white guard (not built).
- **Pure NEAREST crisp with MEDIANCUT palette** → kept clean edges but quantized the scarf to rosy pink. Fixed by the source-true frequency palette.
- **Despeckle pass in crisp mode** → removed lone specks but also filled Marty's eye catchlights → solid rectangular eyes. Removed; tiny features use a per-portrait pixel touch-up instead (decision 2b).
- (Prior sessions) global crisp downscale, 170% UnsharpMask, etc. — still abandoned.

## Blockers / open

- **Missing/partial refs:** Pinky has NO ref; Rootis only a character sheet; Pepperjack + Brie share ONE combined image (each needs its own bust). **Sclorbo's ref is now consumed.**
- **32×32 `_chibi` mini-face + mouth frames** NOT produced yet (only the 96×80 bust). Part of build-campaign wiring (issues #13–15).
- **#16 (toolchain)** needs a manual GitHub close (agent close blocked by permission classifier).
- **pepperjack/brie `fe_stats.class = null`** — FE-legal class TBD post-MVP (art can still proceed).
- **Rootis & Sclorbo recruitment chapters / Sclorbo signature moment = TBD** (Nicolas to recall; `sclorbo.yaml signature_moment.chapter = tbd`).

## Next steps (priority order)

1. **Rootis portrait** — only a character-sheet ref exists; chase a clean bust ref from Nicolas first. Read `pcs/rootis.yaml` `art:` block, then autocrop → render 2-3 crops → pick → ship. Decide smooth vs crisp by whether the ref is clean cel art or painterly. (Wave 1 → 7/10.)
2. Continue Wave 1 one-at-a-time: Pinky, Pepperjack, Brie (chase the missing refs).
3. After Wave 1 busts: chibi + mouth frame generation, then build-campaign wiring (issues #13–15) to get portraits into a built ROM.
4. Wave 2 (map sprites) / Wave 3 (battle anims) — behind Wave 1.

## Key files

- `tools/ref_to_bust.py` — ref → 96×80 indexed bust. Two downscale modes (smooth default / crisp), reserve-extremes + chroma reservation (smooth), source-true freq palette + despeckle (crisp). See knobs above.
- `tools/portrait_tool.py` — bust↔FE8 256×32 tile-sheet OAM packer (`encode`/`decode`, byte-identical). **This IS the tile-sheet creator** (chibi/mouth still TODO).
- `/tmp/autocrop.py` — prints subject bbox + a 1.2-aspect crop for a ref (NOT committed; recreate from the border-median-bg / fg-dist≥45 / >1% coverage snippet). **For a lost crop, recover via silhouette IoU** against the committed bust (this session's Braulo method).
- `campaigns/rime-of-the-frostmaiden/portraits/` — busts + `_preview.png` + README. Done: braulo, prof-rbg, marty, wolfram, meesmickle, sclorbo.
- `campaigns/.../{pcs,npcs}/*.yaml` `art:` block — per-character must-keep brief (read before each conversion).
- Vanilla portrait reference: `fireemblem8u/graphics/portrait/portrait_*_tileset.png` (decode with `portrait_tool.py decode`). Gilliam = best heavy-unit framing reference.

## Standing rules (how Nicolas wants this work done)

- **Reference the DECOMP / the ref** — ground framing/render/colors in `fireemblem8u/` + the character ref. **Follow the ref's colors faithfully; don't embellish** — when a color looks off, make the pipeline track the ref's TRUE hue, don't hand-add pop.
- **Art = full custom for the 10 named cast** (portrait → map sprite → battle anim, in wave order). **Enemies stay vanilla.** Refs are pre-approved source — convert faithfully.
- **Collaborative, one-item-at-a-time:** convert → `open` preview → commit/push → wait. Show 2-3 options and let Nicolas pick when there's a real trade-off (framing especially).
- **Stock vanilla FE8 classes/weapons only**; **element = flavor, NEVER a mechanic**; combat RULES are vanilla FE.
- **Clean native doc rewrites** (no STALE/reverted banners). **Auto-push to main.**
- **Doc source-of-truth:** per-chapter/unit facts live ONLY in YAML; `docs/CHAPTERS.md`/`CLASSES.md` are GENERATED. **Lean repo**; backlog = GitHub issues (M0–M4).
- **`make` must be green at the end of every session.**
