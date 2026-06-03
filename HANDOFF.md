# Handoff: Pepperjack + Brie shipped → Wave 1 portraits = 10/10 (cast busts COMPLETE). NEXT = chibi/mouth frames + build wiring, then Wave 2 (map sprites).

**Date:** 2026-06-03
**Session focus:** Converted the final two cast refs to 96×80 busts and shipped them, closing Wave 1. Nicolas supplied the long-blocked **separate single-bust refs** (`References/PCs/Pixel Pepperjack.png` + `Pixel Brie.png`) — clean pixel-art of the two cannon-golems. Both converted, hand-passed, verified byte-identical, YAML/README updated, committed + pushed (`d5d4bff`).

## WHAT SHIPPED THIS SESSION

- **Pepperjack** (`portraits/pepperjack.png`) — gunmetal cannon-golem. **Whole-cannon framing** (`--crop 20,60,2130,1818`, smooth): tan fuse, orange/maroon angry eye, red star, full barrel + black bore, red chili-pepper grin, tank treads. Hand pass `pepperjack_cleanup.py` **pops the red star only**.
- **Brie** (`portraits/brie.png`) — hot-pink mirror. Same whole-cannon framing (`--crop 20,40,2150,1800`, smooth): pink fuse, glam eye (teal eyeshadow + purple iris + white catchlight), cyan star, toothy grin, grey treads. Hand pass `brie_cleanup.py` **restores the cyan eyeshadow + pops the cyan star**.
- Both `art.render:` YAML blocks added (ref/crop/downscale/hand_pass) and verified to reproduce the shipped bust **byte-identical**. `portrait_ref`/`portrait_source` repointed from the dead combined ref to each unit's own bust + single ref. README documents both new hand passes.

## THE DECISIONS THIS SESSION (don't re-litigate)

1. **Framing = whole cannon (option A), both units.** These are "face-golems": the round cannon body IS the face (eye + grin + star + fuse), the barrel is an iconic snout, the treads are the "legs/shoulders." A tight face-dominant crop (option B) couldn't hold the fuse-top AND the grin without including the barrel anyway, and clipped the grin — so A (the full recognizable silhouette: fuse → barrel + bore → grin → treads) won. Applied identically to both since they're a mirror pair.
2. **Smooth, not crisp.** Clean pixel-art refs, but the must-keep accents are tiny coloured features (eye, star, fuse, chili-stache); crisp muddies those (same call as the rest of the cast). Smooth + a hand pass.
3. **Pepperjack's eye is left AS RENDERED (reads dark maroon, not the ref's orange).** An orange-eye hand pass was tried and **reverted** — see Dead Ends. Nicolas accepted the maroon eye over the speckle artifact.
4. **Pop the stars** (Nicolas's call): the star decals desaturate badly at this ~22× downscale. Pepperjack's red star gets a dedicated brighter-red slot; Brie's cyan star gets a dedicated brighter-cyan slot.

## DEAD ENDS THIS SESSION (don't retry)

- **Pepperjack orange eye via box-scoped recolour** (idx13 red + idx10 brown → orange inside an eye box) → the box also contained stray outline/shadow pixels of those same shared indices, which turned into **orange specks that weren't in the ref**. Reverted; eye left as rendered. (If ever retried: needs connectivity/largest-blob gating like Pinky's iris, not a flat box recolour — but Nicolas was fine with the maroon eye, so low priority.)
- **Brie: re-saturating the shared grey slot (idx6) globally** → idx6 is BOTH the desaturated teal (eyeshadow + star) AND **her grey tread metal**, so the treads turned teal. **Snapping idx6 strays to neighbours** (to protect non-eyeshadow pixels) then **gutted the treads to dark blobs**. Fix that worked: **free a NEW slot** (merge two near-identical cream specks idx2≈idx4, Pinky's trick) and **recolour only the eyeshadow/star boxes**, leaving idx6 = tread grey untouched.
- First two crop passes were **far too tight** — eyeballed off the 200px grid thumbnail and under-shot badly (chili-grin is at ref-y≈1170, barrel bore out at x≈2124). Lesson: **measure the content bbox + feature positions programmatically** (border-median bg, fg-dist>45 mask, colour-keyed feature hunts) before designing a crop — don't trust the grid thumbnail's scale.

## THE PIXEL-TOUCH-UP TEMPLATE (now FIVE examples)

`marty_eye_fixup.py` (hand-drawn face on smooth body), `rootis_cleanup.py` (outline + faceted nose + halo), `pinky_cleanup.py` (palette-budget rescue), **`pepperjack_cleanup.py`** (single scoped accent pop — free slot → brighter red in a star box), **`brie_cleanup.py`** (chroma rescue where the desat slot is SHARED with a real grey feature → free a slot via cream-merge, recolour only scoped boxes, leave the shared grey alone). **Pattern:** render faithful with `ref_to_bust.py`, then a deterministic colour-keyed companion for what the downscale + 16-colour quantizer can't hold. README "Per-portrait hand passes" documents all five.

**Recurring chroma-budget lesson:** when a ref has big saturated areas (pink body / grey body) plus small must-keep accents (eye / star / eyeshadow), the big areas win the chroma-reservation slots and the small accents desaturate. The hand pass frees slots (merge near-dup colours) and repaints the accent **scoped to a box** — and must check whether the desaturated slot is shared with a *legitimate* feature (Brie's treads) before touching it.

## PIPELINE KNOBS (`tools/ref_to_bust.py`) — unchanged

- `--downscale smooth|crisp` (default smooth). smooth = area-average + ink overlay; crisp = NEAREST + source-true freq palette (clean flat cel art only; **muddies tiny coloured features** — avoid here).
- `--crop x0,y0,x1,y1` (per-character, ~1.2 aspect), `--sharpen` (0), `--ink-lum` (150) / `--ink-cov` (4), `--bg-thresh` (45), `--no-reserve-extremes`, `--preview`.
- Reserve logic (default ON): protects luminance extremes + up to 3 saturated-hue clusters; big saturated areas beat small accents (the chroma-budget lesson above).

## PER-PORTRAIT RENDER SETTINGS

Canonical home = each unit's YAML `art.render:` block (ref / crop / downscale / hand_pass), byte-verified. Refs in `…/References/PCs/`; ship → `campaigns/rime-of-the-frostmaiden/portraits/<unit>.png`. Convenience mirror:

| unit | ref file | --crop | mode + hand pass |
|---|---|---|---|
| braulo | `Broulo Face Clean.png` | `153,129,1888,1574` | smooth |
| marty | `Marty 3.png` | `0,35,2222,1887` | smooth + `marty_eye_fixup.py` |
| meesmickle | `Meesmickle Clean.png` | `0,255,1824,1775` | smooth |
| prof-rbg | `RBG Landscape.png` | `14,17,2258,1887` | smooth |
| wolfram | `womfram bust 3.png` (typo real) | `280,70,1980,1487` | smooth |
| sclorbo | `Sclorbo Portrait clean.png` | `342,297,1786,1500` | smooth |
| rootis | `Rootis Bust 1.png` | `126,100,1614,1340` | smooth + `rootis_cleanup.py` |
| pinky | `Pinky Art.png` | `380,100,1675,1179` | smooth + `pinky_cleanup.py` |
| **pepperjack** | `Pixel Pepperjack.png` | `20,60,2130,1818` | smooth + `pepperjack_cleanup.py` |
| **brie** | `Pixel Brie.png` | `20,40,2150,1800` | smooth + `brie_cleanup.py` |

## Current state

- **Wave 1 portraits: 10 / 10 — COMPLETE.** braulo, prof-rbg, marty, wolfram, meesmickle, sclorbo, rootis, pinky, **pepperjack, brie**. All 96×80 indexed busts, ≤16 colours, index-0 transparent, byte-verified reproduction, render params in YAML.
- **Build:** untouched. This session added only campaign assets/docs/YAML (2 PNGs, 2 preview PNGs, 2 hand-pass scripts, README + 2 YAML edits) — **zero C-build impact.** `make` exercises only the decomp ROM (base ROM + toolchain not installed locally).
- **`fireemblem8u` submodule** still shows local changes in `git status` (pre-existing) — left untouched; **don't commit the submodule pointer.**

## Blockers / open

- **No more PC/cast ref blockers** — the Pepperjack/Brie combined-ref blocker is CLOSED (separate refs delivered + shipped).
- **32×32 `_chibi` mini-face + mouth frames** not produced for ANY of the 10 units yet (only the 96×80 busts). Frame spec = `fireemblem8u/include/types.h` `struct FaceData`. Study vanilla via `tools/portrait_tool.py decode` before authoring. Part of build-campaign wiring (issues #13–15).
- **#16 (toolchain)** still needs a manual GitHub close (agent close blocked by permission classifier).
- **Pepperjack/Brie `fe_stats.class = null`** (FE-legal class TBD post-MVP) and **Rootis & Sclorbo recruitment chapters / Sclorbo signature_moment** = TBD (Nicolas to recall).
- **Enemy portraits: NOT a Wave-1 gap.** Standing rule = enemies stay vanilla FE8; only the 10 named cast get custom art. A handful of *named* story bosses could optionally get a custom bust later, but that's a deliberate post-MVP decision (see the next-waves discussion), not a missing deliverable.

## Next steps (priority order)

1. **Chibi + mouth-frame generation** for all 10 busts — extend `tools/portrait_tool.py` (it already does the 96×80 bust↔FE8 sheet round-trip; add the 32×32 chibi mini-face + the mouth/blink frames per `struct FaceData`). Study a vanilla portrait with `portrait_tool.py decode` first. This is the gate to seeing any portrait in a built ROM.
2. **Build-campaign wiring (issues #13–15)** — get a bust + chibi + mouth frames onto a unit through `tools/build-campaign.ts` → `fireemblem8u/graphics/portrait/` → `gbagfx` → ROM. Prove it end-to-end on ONE unit (braulo) before batching the other 9.
3. **Wave 2 — map sprites** (full custom, same cast of 10): the standing/walking overworld sprites. New tooling likely needed (map-sprite sheet format differs from portraits).
4. **Wave 3 — battle animations** (full custom): biggest effort; behind Waves 1–2.

## Key files

- `tools/ref_to_bust.py` — ref → 96×80 indexed bust (smooth default / crisp opt-in). Knobs above.
- `campaigns/rime-of-the-frostmaiden/portraits/<unit>_cleanup.py` (+ `marty_eye_fixup.py`) — the five deterministic, byte-identical hand passes. Read the docstring for each before editing a bust.
- `tools/portrait_tool.py` — bust↔FE8 256×32 tile-sheet OAM packer (`encode`/`decode`, byte-identical). **Chibi/mouth frames still TODO** — extend here for step 1.
- `tools/build-campaign.ts` — campaign-data injector (step 2; portrait wiring lives here).
- `tools/autoframe.py` / `/tmp/grid.py` / `/tmp/autocrop.py` — framing helpers (grid/autocrop NOT committed; recreate. **Prefer the programmatic bbox + colour-keyed feature hunt over the grid thumbnail** — see Dead Ends).
- `campaigns/.../{pcs,npcs}/*.yaml` `art:` block — per-character must-keep brief + the byte-verified `render:` sub-block. All 10 cast now have both.
- Vanilla portrait reference: `fireemblem8u/graphics/portrait/portrait_*_tileset.png` (decode with `portrait_tool.py decode`).

## Standing rules (how Nicolas wants this work done)

- **Follow the ref's colours faithfully; don't embellish** — exception: when the quantizer DROPS a ref-true feature (Pinky's blue eyes, Brie's cyan eyeshadow/star), the hand pass restores it to match the ref. Popping the stars + lightening (Pinky's ears) were explicit Nicolas asks.
- **Face-dominant** FE8 convention; use available headroom to zoom small faces (capped by the subject — these face-golems use the full silhouette).
- **Collaborative, one item at a time:** render → `open` preview → wait for Nicolas → iterate → commit/push. Show 2–3 options on real trade-offs (framing, ref choice). Framing is live back-and-forth.
- **Art = full custom for the 10 named cast** (portrait → map sprite → battle anim, wave order). **Enemies stay vanilla.**
- **Stock vanilla FE8 classes/weapons only**; **element = flavor, NEVER a mechanic**; combat RULES are vanilla FE.
- **Clean native doc rewrites** (no STALE/reverted banners). **Auto-push to main** (no need to ask).
- **Doc source-of-truth:** per-chapter/unit facts live ONLY in YAML; `docs/*` are GENERATED. **Lean repo**; backlog = GitHub issues (M0–M4).
- **`make` must be green at the end of every session.**
