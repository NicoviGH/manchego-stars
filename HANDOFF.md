# Handoff: All 10 portrait busts now on the pngquant pipeline, dead corners cleared. The portrait-quality phase is DONE. NEXT = revisit chibi generation (placeholder), then the build pipeline (build-campaign.ts + a self-contained test chapter to see a bust in mGBA).

**Date:** 2026-06-03
**Session focus:** Finished the 4 pending busts (marty/pinky/pepperjack/brie) — the immediate task the prior handoff left open. Reframed each clear of FE8's dead corners via `--zoom`, dropped 3 of 4 hand passes (pngquant renders the accents natively), and re-derived Marty's. Then swept the vestigial `downscale:` field out of all YAMLs and rewrote the portraits README to the pngquant reality. `make` green (byte-identical vanilla ROM).

## WHAT'S DONE THIS SESSION — 10/10 busts on pngquant, all committed + pushed

The 4 fitted refs had already landed in `…/References/PCs/` since the last handoff. Each was reframed with `--zoom` until `portrait_tool.py preview` reported ~0 clipped px:

| unit | ref | crop | zoom | clip | hand pass |
|---|---|---|---|---|---|
| **marty** | `MartyFlat.png` | 0,35,2222,1887 | 0.74 | 0px | **re-derived** `marty_eye_fixup.py` (kept) |
| **pinky** | `Pinky Art.png` | 380,100,1675,1179 | 0.65 | 0px | dropped |
| **pepperjack** | `Pixel Pepperjack.png` | 20,60,2130,1818 | 0.72 | 30px | dropped |
| **brie** | `Pixel Brie.png` | 20,40,2150,1800 | 0.72 | 30px | dropped |

- **MartyFlat beats Marty 3:** the flat/bold-outline ref downscales visibly crisper than the painterly one. Nicolas confirmed — **switch any future re-gen to a flatter ref** (the standing ref-spec lesson, now proven a 2nd time after Wolfram).
- **`marty_eye_fixup.py` rewritten** (face is ~17px, below any downscale): now auto-locates the face from the rendered FACE-grey blob and picks palette slots by colour (no hardcoded coords, no PIL-palette dependency). Eye/mouth positions were **measured from the ref's own downscale** (Nicolas: eyes wider apart + higher, mouth closer — don't guess, count pixels). Mouth kept the first wide-corner/long-flat shape, just shifted up.
- **pinky/pepperjack/brie hand passes deleted** — pngquant holds the blue eye, ruby nose, orange eye, red/cyan stars, glam eye, chili-mustache at the 16-colour ceiling natively.
- **Pinky framing note:** her ref is a full-body action pose with ears that are tall AND wide. Widening the crop only centralises the ears and ends up showing the whole body tiny; aggressive zoom-out (0.65) is the real lever. Nicolas picked the 0.65 full-body framing (ears intact) over a big-head bust with chopped ears.
- **pepperjack/brie:** Nicolas chose zoom 0.72 (bigger/bolder face, 30px residual on the fuse/bore TIPS) over the fully-clean 0.66 — a tiny tip-clip is acceptable for a bigger face. Brie mirrors Pepperjack exactly.

### Also done
- **Swept the dead `downscale:` field** out of all 6 remaining YAML `art.render:` blocks (braulo, prof-rbg, meesmickle, sclorbo, rootis, wolfram) — every bust is on pngquant now, the field did nothing.
- **Rewrote `portraits/README.md`** natively to the pngquant pipeline: documents the `--zoom` dead-zone reframe and the single surviving hand pass (marty); drops the old PIL-quantizer rescue passes.
- **Deleted** the throwaway `portrait_clip_check.png` from repo root.
- Commits: marty `1c79646`, pinky `196ba35`, pepperjack `5f95d11`, brie `d0e427b`, sweep+README `371ae4e`. All pushed to main.

## FE8 DEAD-ZONE CONSTRAINT (still true — read before any portrait work)
FE8's talking-portrait OAM never draws the top-left & top-right **16px×48px** corners (~20% of the frame; computed from `OBJECTS` in `tools/portrait_tool.py`, mirrored from `fireemblem8u/src/face.c`).
```
python3 tools/portrait_tool.py preview <bust.png> <out.png>   # [authored | what-FE8-draws | clip overlay] + clip count
```
Reframe with `--zoom z<1` (shrinks subject, adds top headroom, shoulders pinned to bottom). **Descale, never crop a must-keep feature.** All 10 busts now pass at ~0 clipped px.

## PIPELINE (current, minimal — over-editing washes out clean refs)
`tools/ref_to_bust.py`: **crop/zoom → segment flat background → area-average downscale to 96×80 → pngquant (≤16 colours, index 0 transparent).** CLI: `--crop`, `--zoom`, `--sharpen` (taste dial, default 0), `--bg-thresh`, `--preview`. Requires `pngquant` (brew, v3.0.3). Each bust byte-reproduces from its unit YAML `art.render:` (ref/crop/zoom).
**Ref-gen spec for Nano Banana / Gemini:** "flat cel-shaded, bold black outlines, ~16 flat colours, no gradients/no fine texture, 3/4 view, large readable face, plain solid background, top corners empty." Do NOT ask for "sharpen"/"more detail" — the lever is FLATTER + BOLDER + fewer colours.

## STANDING WORKFLOW (how Nicolas wants portrait work done)
- **Previews don't render inline for him** — `open <png>` them in Preview.app (macOS) so he can actually see them. (Discovered this session.)
- **Collaborative, one bust at a time:** render → **`open` the final on-screen look → WAIT for explicit OK → only then commit.** Show 2–3 framings on real trade-offs. He often picks a specific candidate by filename ("do the .72 one").
- **Don't guess pixel positions** — measure from the ref's own downscale and count.
- **Auto-push to main** once approved. **Clean native rewrites, no band-aid fields/banners.**

## DEAD ENDS / DON'T RETRY
- **Applying old hand passes to pngquant output** → hardcoded to the dead PIL palette → garbage. Re-derive against the live palette (as done for marty) or delete.
- **Widening the crop to fit a wide-AND-tall feature** (pinky's ears) → only centralises it, then reveals the whole body small. Use zoom-out instead.
- **`--sharpen` / "more detail" to fix blur** → adds noise; the fix is a flatter ref + the hand pass for sub-resolution faces.
- **`crisp` downscale mode on painterly refs** → speckle (removed from the tool).

## BLOCKERS / OPEN
- 🟢 **Build pipeline still not started** — `build-campaign.ts` (#13), build-events.ts (#14), Braulo end-to-end (#15). Plan: a self-contained **test/"visual-test" chapter** (reuse a vanilla map, spawn the roster, intro dialogue + a fight) to see portraits/sprites/anims in mGBA without touching the real game. This de-risks everything downstream and is the natural next focus now that portraits are settled.
- 🟡 **Chibi generation is a placeholder** — `portrait_tool.py generate` produces a naive face-crop `_chibi.png`. Revisit for quality before wiring portraits into the ROM.
- **fireemblem8u submodule** shows pre-existing local changes in `git status` — leave untouched, **don't commit the submodule pointer**.

## NEXT STEPS (priority order)
1. **Revisit chibi generation** in `portrait_tool.py` (current is a placeholder crop) before ROM wiring.
2. **Build pipeline:** `build-campaign.ts` (#13) + the self-contained test chapter → see a bust in mGBA (Braulo end-to-end, #15). The big de-risker.
3. **Wave 2 (map sprites)** / **Wave 3 (battle anims)** — full custom for the 10 named cast, behind portraits.

## KEY FILES
- `tools/ref_to_bust.py` — ref → 96×80 indexed bust (pngquant). Knobs: `--crop`, `--zoom`, `--sharpen`, `--bg-thresh`, `--preview`.
- `tools/portrait_tool.py` — bust↔FE8 tilesheet (`encode`/`decode`), `generate` (chibi/mouth/palette — chibi is a placeholder), `preview` (dead-zone clip census).
- `campaigns/rime-of-the-frostmaiden/{pcs,npcs}/*.yaml` `art.render:` — per-unit ref/crop/zoom; byte-reproduces each bust. (`downscale:` field now gone everywhere.)
- `campaigns/rime-of-the-frostmaiden/portraits/<unit>.png` — the 10 shipped 96×80 indexed busts. Only surviving script: `marty_eye_fixup.py`.
- `campaigns/rime-of-the-frostmaiden/portraits/README.md` — rewritten to the pngquant pipeline.
- `…/References/PCs/` — hi-res refs (outside the repo, in the Documents source folder). Flatter refs win.
- `tools/build-campaign.ts` — **does not exist yet** (#13); the campaign-data/portrait injector.

## STANDING RULES (project-wide)
- **Art = full custom for the 10 named cast** (portrait → map sprite → battle anim). Enemies stay vanilla.
- **Stock vanilla FE8 classes/weapons; element = flavor never mechanic; combat RULES are vanilla FE.**
- **Doc source-of-truth:** per-unit facts in YAML; `docs/*` generated; lean repo; backlog = GitHub issues.
- **`make` green at the end of every session** (it is — no C/build changes this session; `fireemblem8.gba: OK`).
