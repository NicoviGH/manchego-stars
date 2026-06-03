# Handoff: Pinky shipped (Wave 1 = 8/10). Three-eye/ruby hand pass added. NEXT = chase separate Pepperjack + Brie refs.

**Date:** 2026-06-03
**Session focus:** Converted **Pinky** (RBG's homunculus 'son', the army's flier) to a 96×80 bust from the fresh ref `References/PCs/Pinky Art.png`. Pinky is a grey opossum-mouse with big magenta-pink ears, large blue eyes, a faceted **red ruby nose**, pink paws/tail, and silver armour segments + swirl etchings. Smooth downscale + a deterministic `pinky_cleanup.py` hand pass. Shipped + pushed.

## THE DECISIONS THIS SESSION (don't re-litigate)

1. **Framing = both ears fully in (`--crop 380,100,1675,1179`, smooth).** Nicolas iterated framing live: started face-dominant → "crop the arm in favour of the ear" → "move him right so the LEFT ear is fully in" → finally **"both ears fully in frame."** Both ears span ref x 401–1647 (~1246px); at 1.2 aspect that forces the face back near original size with the silver collar/arm + a pink paw at the bottom — **unavoidable** trade-off (only ~150px of headroom exists above the ears, so you can't fit both wide ears AND crop the arm). He accepted the arm to keep the ears.
2. **Smooth, not crisp.** This ref is already clean pixel-art so crisp was plausible, but crisp **speckled the grey fur + swirl etchings**; the tiny ruby + blue eyes survived smooth fine. Same call as the rest of the cast.
3. **`pinky_cleanup.py` is the deterministic touch-up** (run after `ref_to_bust.py`; reproduce cmd in its docstring; verified byte-identical on fresh reproduce). Five colour-keyed passes — the lever this session was **palette budget**: the ears (magenta) + ruby (red) are so saturated they eat the chroma-reservation slots, so both irises desaturate to a muddy blue-grey, AND the ruby shares the ears' exact 3 red slots so it doesn't pop. The fixes:
   - **Free two grey slots** — three near-identical darks (65,66,66 / 60,61,61 / 60,60,60) merge to one; the freed slots become two true blues.
   - **Repaint both irises** (near eye + a small far eye tucked by the right ear) inside scoped eye boxes: blue-grey iris → blue, shadow → dark blue. Catchlights/pupils untouched.
   - **Trim stray blue** — recolouring the whole box also turns eyelid/brow blue-grey flecks blue. **MAIN eye: keep only the largest connected blue blob** (the iris sits inside the dark eye-ring; brow/edge flecks are separate little blobs outside it → dropped). **FAR eye: drop its 5 leftmost blue pixels** (Nicolas's call — they read as loose specks, not eye).
   - **Eye-halo + gated cheek despeckle** — snap the faint mauve anti-alias halo around the eyes to grey; a Rootis-style >70-distance despeckle (eye + gem boxes EXCLUDED so it can't eat catchlights/facets).
   - **Ears/hands lighter + ruby pops** — lighten the two shared pink slots (ears, paws), repurpose the now-free iris-shadow slot as a **bright ruby red (≈185,40,58)**, and remap the gem's pixels to ruby + deep-red so the nose stays saturated and stands out against the lightened ears.

## DEAD ENDS THIS SESSION (don't retry)

- **Crisp mode** → speckled fur/etchings. Smooth + hand pass.
- **"Touches the dark ring" enclosure gate** to pick iris pixels → **under-painted the iris interior** (interior pixels don't touch the ring), so the eye read as a dark hole with a blue sliver. Reverted to **full-box recolour + keep-largest-blob** instead.
- **The >70 gated despeckle for the eye-halo specks** → those flecks are mauve-on-grey (~24 RGB apart), below the gate; needed the dedicated low-contrast halo pass instead.
- **Globally redefining a shared red slot to lighten ears** → would wash out the ruby too (gem shares idx 5/10/11 with ears). Must split spatially: lighten shared pinks, give the gem its own freed ruby slot.

## THE PIXEL-TOUCH-UP TEMPLATE (now THREE examples)

`marty_eye_fixup.py` (hand-drawn face on smooth body), `rootis_cleanup.py` (outline + faceted nose + halo), `pinky_cleanup.py` (palette-budget rescue: free slots → restore eyes/colour, connectivity to drop strays). **Pattern:** render faithful with `ref_to_bust.py`, then a deterministic colour-keyed companion script for what the ~17–23× downscale + 16-colour quantizer can't hold. README "Per-portrait hand passes" documents all three.

## PIPELINE KNOBS (all in `tools/ref_to_bust.py`) — unchanged

- `--downscale smooth|crisp` (default smooth). smooth = area-average + ink overlay (painterly/textured refs); crisp = NEAREST + source-true freq palette (clean flat cel art only; **muddies tiny coloured features** — avoid when a small accent must survive, e.g. Pinky's ruby).
- `--ink-lum N` (150) / `--ink-cov N` (4), `--crop x0,y0,x1,y1`, `--sharpen` (0), `--bg-thresh` (45), `--no-reserve-extremes`, `--preview`.
- Reserve logic (default ON): protects luminance extremes + up to 3 saturated-hue clusters. **Note:** when a ref has BOTH big saturated areas (ears) AND a tiny must-keep accent (ruby/eyes), the big areas win the reservation and the small accent needs a hand pass — Pinky is the worst case yet.

## PER-PORTRAIT RENDER SETTINGS

**Canonical home is now each unit's YAML `art.render:` block** (`ref` / `crop` / `downscale` / `hand_pass`) — added this session for all 8 and verified to reproduce every shipped bust **byte-identical**. The crop no longer lives only in this drift-prone handoff. The table below is a convenience mirror. Refs: `…/References/PCs/`. Ship → `campaigns/rime-of-the-frostmaiden/portraits/<unit>.png`.

| unit | ref file | --crop | mode + hand pass |
|---|---|---|---|
| braulo | `Broulo Face Clean.png` | `153,129,1888,1574` | smooth |
| marty | `Marty 3.png` | `0,35,2222,1887` | smooth + `marty_eye_fixup.py` |
| meesmickle | `Meesmickle Clean.png` | `0,255,1824,1775` | smooth |
| prof-rbg | `RBG Landscape.png` | `14,17,2258,1887` | smooth |
| wolfram | `womfram bust 3.png` (typo real) | `280,70,1980,1487` | smooth |
| sclorbo | `Sclorbo Portrait clean.png` | `342,297,1786,1500` | smooth |
| rootis | `Rootis Bust 1.png` | `126,100,1614,1340` | smooth + `rootis_cleanup.py` |
| **pinky** | `Pinky Art.png` | `380,100,1675,1179` | smooth + `pinky_cleanup.py` |

## Current state

- **Wave 1 portraits: 8 / 10** — braulo, prof-rbg, marty, wolfram, meesmickle, sclorbo, rootis, **pinky**. Remaining: **Pepperjack, Brie** (ref-blocked, see Blockers).
- **Pinky bust** = both magenta-pink ears fully in, two restored blue eyes (big near eye + small far-eye glint), bright faceted ruby nose, lightened ears/paws, silver collar/arm trailing off the bottom. Approved & shipped.
- **Build:** untouched. This session added only campaign assets/docs/YAML (a PNG, a hand-pass script, a README entry, an `art:` block) — zero C-build impact. `make verify` exercises only the decomp ROM (base ROM + toolchain not installed locally).
- **`fireemblem8u` submodule** still shows local changes in `git status` (pre-existing) — left untouched; **don't commit the submodule pointer.**

## Blockers / open

- **Pepperjack + Brie still share ONE combined ref** (`data/portraits/pepperjack-and-brie.jpeg`) — each needs its **own clean single bust** from Nicolas before converting. Their `fe_stats.class = null` (FE-legal class TBD post-MVP; art can proceed once refs exist).
- **32×32 `_chibi` mini-face + mouth frames** not produced for ANY unit yet (only the 96×80 busts). Frame spec = `fireemblem8u/include/types.h` `struct FaceData`. Study vanilla via `portrait_tool.py decode` before authoring. Part of build-campaign wiring (issues #13–15).
- **#16 (toolchain)** needs a manual GitHub close (agent close blocked by permission classifier).
- **Rootis & Sclorbo recruitment chapters / Sclorbo signature_moment** = TBD (Nicolas to recall; YAML `signature_moment.chapter = tbd`).

## Next steps (priority order)

1. **Chase separate Pepperjack + Brie refs from Nicolas**, then convert one-at-a-time (autocrop → render → pick framing → hand pass if needed → ship). **Wave 1 → 10/10.**
2. **After Wave 1 busts:** chibi + mouth-frame generation (extend `portrait_tool.py`), then build-campaign wiring (issues #13–15) to get portraits into a built ROM.
3. Wave 2 (map sprites) / Wave 3 (battle anims) — behind Wave 1.

## Key files

- `tools/ref_to_bust.py` — ref → 96×80 indexed bust (smooth default / crisp opt-in; reserve-extremes + chroma reservation). Knobs above.
- `campaigns/rime-of-the-frostmaiden/portraits/pinky_cleanup.py` — Pinky hand pass (free slots → blue eyes + bright ruby; keep-largest-blob to drop stray blue; halo + gated despeckle). Colour-keyed, reproducible, byte-identical on re-run.
- `campaigns/rime-of-the-frostmaiden/portraits/rootis_cleanup.py` / `marty_eye_fixup.py` — the other two hand-pass examples.
- `tools/portrait_tool.py` — bust↔FE8 256×32 tile-sheet OAM packer (`encode`/`decode`, byte-identical). Chibi/mouth still TODO.
- `tools/autoframe.py` — bottom-anchor + pad helper (for full-body refs; the cast uses direct `--crop` face-dominant framing instead).
- `/tmp/autocrop.py` (border-median-bg fg-dist≥45 bbox) + `/tmp/grid.py` (200-px coord grid on a thumbnail) — NOT committed; recreate. grid.py is the fastest way to place a face-dominant crop.
- `campaigns/.../{pcs,npcs}/*.yaml` `art:` block — per-character must-keep brief (read before each conversion). Pinky's now added.
- Vanilla portrait reference: `fireemblem8u/graphics/portrait/portrait_*_tileset.png` (decode with `portrait_tool.py decode`).

## Standing rules (how Nicolas wants this work done)

- **Follow the ref's colours faithfully; don't embellish** — but Pinky shows the exception: when the quantizer DROPS a ref-true feature (the blue eyes), the hand pass restores it to match the ref. Lightening the ears was an explicit Nicolas ask to improve ruby contrast, not embellishment.
- **Reference the DECOMP / the ref** for framing/render/colours. **Face-dominant** FE8 convention; use available headroom to zoom small faces (capped by the subject — Pinky's ears use it all).
- **Collaborative, one item at a time:** render → `open` preview → wait for Nicolas → iterate → commit/push. Show 2–3 options on real trade-offs (framing, ref choice). Framing especially is live back-and-forth.
- **Art = full custom for the 10 named cast** (portrait → map sprite → battle anim, wave order). **Enemies stay vanilla.**
- **Stock vanilla FE8 classes/weapons only**; **element = flavor, NEVER a mechanic**; combat RULES are vanilla FE.
- **Clean native doc rewrites** (no STALE/reverted banners). **Auto-push to main** (no need to ask).
- **Doc source-of-truth:** per-chapter/unit facts live ONLY in YAML; `docs/*` are GENERATED. **Lean repo**; backlog = GitHub issues (M0–M4).
- **`make` must be green at the end of every session.**
