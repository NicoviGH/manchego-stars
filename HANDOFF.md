# Handoff: Portrait pipeline overhauled to pngquant + reframing pass. 6/10 busts re-rendered vibrant & committed. NEXT = fitted "clean" refs for the last 4 (marty/pinky/pepperjack/brie), then resume the build pipeline (build-campaign.ts + Braulo end-to-end).

**Date:** 2026-06-03
**Session focus:** Started toward the build pipeline, pivoted into a deep portrait-quality overhaul. (1) Confirmed the toolchain is already installed & `make` is green. (2) Extended `portrait_tool.py` with chibi/mouth/palette generation + a `preview` (what-FE8-draws) subcommand. (3) Ran a reframing pass to clear FE8's dead corners. (4) Diagnosed that PIL's MEDIANCUT quantizer was washing out colors and **rewrote `ref_to_bust.py` to use pngquant** — a big quality jump. Re-rendered + committed 6 busts; 4 remain.

## ⚠️ FE8 DEAD-ZONE CONSTRAINT (still true — read before portrait work)

FE8's talking-portrait OAM does **not** draw the full 96×80. The **top-left & top-right 16px×48px corners (20% of the frame) are never drawn** (computed from `OBJECTS` in `tools/portrait_tool.py`, mirrored from `fireemblem8u/src/face.c`). Check any bust:
```
python3 tools/portrait_tool.py preview <bust.png> <out.png>   # [authored | what-FE8-draws | clipped-overlay] + clip count
```
**Fix = reframe** (this session's work, no longer deferred): `--zoom z<1` adds top headroom (shoulders pinned to bottom); shifting the crop box repositions left/right; or a **fitted/narrow ref**. Per Nicolas: **descale/zoom, NEVER crop a must-keep feature** (pinky's ears, the cannons' fuse+bore).

## MAJOR CHANGE THIS SESSION: pngquant pipeline (commit `458f3b5`)

`tools/ref_to_bust.py` was **rewritten** to a minimal pipeline:
**crop/zoom → segment background → area-average downscale → pngquant (≤16 colors, index 0 transparent).**
- **Why:** PIL's MEDIANCUT desaturated clean refs (grey crystals, muddy accents). pngquant keeps saturated accents at the 16-color ceiling. Proven with a diagnostic: downscale-only and +pngquant stayed vibrant; +our old full pipeline washed out.
- **Removed (no band-aids):** the PIL quantize / ink-overlay / reserve-extremes / crisp-mode / edge-erosion machinery — it existed only to rescue the weak quantizer and *over-edited* clean art.
- **CLI now:** `--crop`, `--zoom`, `--sharpen` (taste dial, default 0), `--bg-thresh`, `--preview`. (Removed: `--downscale`, `--no-reserve-extremes`, `--ink-*`.)
- Requires **pngquant** (installed via `brew install pngquant`, v3.0.3).
- Output is deterministic & byte-reproducible from each unit's YAML `art.render:` (ref/crop/zoom).

## REF-GENERATION SPEC (give this to Nano Banana / Gemini for the remaining 4)

> flat cel-shaded, bold black outlines, ~16 flat colors, no gradients / no fine texture, 3/4 view, large readable face, plain solid background, top corners empty.

**Do NOT ask for "sharpen" / "more detail"** — detail below 96×80 averages to mush; the lever is FLATTER + BOLDER + fewer colors. A fitted clean ref beats fighting a painterly ref's crop (proven on Wolfram: narrow → side → side-clean). Save refs to `…/References/PCs/<Name>.png`.

## WHAT'S DONE — 6/10 busts on pngquant (committed, byte-verified, dead-corners clear)

| unit | ref | crop | zoom | clip px | notes |
|---|---|---|---|---|---|
| braulo | `Broulo Face Clean.png` | 120,180,1960,1720 | 0.84 | 47 | taller "claw-crop" (more lower body) |
| prof-rbg | `RBG Landscape.png` | 14,17,2258,1887 | 1.0 | 18 | unchanged framing |
| wolfram | `Wolfram Side.png` | 60,80,2240,1840 | 0.90 | 19 | 3/4 side pose; pngquant from painterly "Side" (Nicolas: "keep it", didn't switch to Side Clean) |
| meesmickle | `Meesmickle Clean.png` | 40,255,1864,1775 | 0.88 | 9 | shifted left + zoom (both cape halves in) |
| sclorbo | `Sclorbo Portrait clean.png` | 342,297,1786,1500 | 1.0 | 12 | unchanged framing |
| rootis | `Rootis Bust 1.png` | 216,100,1704,1340 | 0.94 | 0 | shifted +90 (centre head) + zoom; **hand pass deleted** |

`rootis_cleanup.py` **deleted** — pngquant renders the carrot/coal/outline clean; the old hand pass (hardcoded to the PIL palette) broke on the new palette (pink garbage). First hand pass to fall.

## WHAT'S LEFT — 4 busts pending FITTED REFS (the immediate next task)

**marty, pinky, pepperjack, brie** still clip hard at their old wide framing (marty 410, pinky 984, pepperjack 854, brie 843 px). They need **fitted clean refs** (the spec above) → reframe + re-render through pngquant → **their hand passes drop too**:
- `marty_eye_fixup.py` — hand-DRAWS the face (eyes+smile) at fixed pixels because the face is ~20px. A bigger-face fitted ref may let pngquant render it; otherwise re-derive. (marty clips BOTH corners — wide cap.)
- `pinky_cleanup.py`, `pepperjack_cleanup.py`, `brie_cleanup.py` — accent-pop / palette-budget rescues. pngquant likely makes them unnecessary (it preserves pinky's blue eye, brie's cyan, pepperjack's star natively). Confirm per-character.
- pinky/pepperjack/brie YAML live in `campaigns/.../npcs/`; the rest in `pcs/`.

**Workflow Nicolas wants (standing rule, reinforced this session):** render → **show the final on-screen look → WAIT for his explicit OK → only then commit.** Do not auto-commit art. (He pushed back when a Wolfram bust was committed without sign-off.)

## ALSO DONE THIS SESSION (not portrait-quality)

- **`tools/portrait_tool.py`** gained: `generate <bust> <base> [--xmouth N --ymouth N]` → produces the 4 decomp assets (`_tileset.png` 256×32, `_mouth.png` 32×96 = 6 static frames, `_chibi.png` 32×32, `_palette.agbpal` 32-byte RGB555). gbagfx accepts all three PNGs (4096/1536/512 bytes). Mouth math mirrors `face.c` OAM: `bust_x=(xmouth-4)*8+32`, `bust_y=ymouth*8`. **Chibi is a naive face-crop placeholder** — revisit for quality. Also added `preview` (dead-zone visualizer, see above).
- **Toolchain confirmed installed** (agbcc, baserom, arm-none-eabi-gcc 16.1, numpy/pillow) — `make CAMPAIGN=rime-of-the-frostmaiden fireemblem8.gba` builds the byte-identical vanilla ROM. **#16 is effectively closed** (the prior handoff's "toolchain not installed" was stale).

## DEAD ENDS / DON'T RETRY

- **`crisp` downscale mode on painterly refs** → noise/speckle (it's for clean cel art only). Removed from the tool.
- **`--sharpen` to fix blur** → Gemini "sharpen the image" just ADDED detail (wrong); the blur was the weak PIL quantizer + downscaling a *painterly* ref. Real fix = clean flat ref + pngquant. Sharpen survives only as an optional taste dial.
- **Applying old hand passes to pngquant output** → they're hardcoded to the old PIL palette/slots → garbage. Delete or re-derive, don't reuse.
- **Re-rendering the 4 pending busts at their OLD crops** → they clip 400–984 px and (for marty) lose the hand-drawn face. Don't ship them until reframed with fitted refs.

## BLOCKERS / OPEN

- 🟡 **4 busts need fitted refs from Nicolas** (marty/pinky/pepperjack/brie) — the immediate next step; everything for those is on hold until the refs land.
- 🟢 **build pipeline still not started** — `build-campaign.ts` (#13), build-events.ts (#14), Braulo end-to-end (#15) remain. The original plan was to build a self-contained **test ROM / "visual-test" chapter** (reuse a vanilla map, spawn the roster, intro dialogue + a fight) to visualize portraits/sprites/anims without touching the real game. Resume after portraits settle (or in parallel).
- **fireemblem8u submodule** shows local changes in `git status` (pre-existing) — leave untouched, **don't commit the submodule pointer**.
- **YAML cleanup pending:** remove the now-vestigial `downscale:` field from all `art.render:` blocks once all 10 are migrated.
- **Untracked throwaway:** `portrait_clip_check.png` in repo root (a dead-zone contact sheet) — ignore or delete.

## NEXT STEPS (priority order)

1. **Reframe the last 4 busts** as Nicolas supplies fitted clean refs (spec above): reframe (`--zoom`/crop) → pngquant → `portrait_tool.py preview` to confirm dead-corners clear → **show final, get OK** → commit. Drop each hand pass.
2. **YAML sweep:** strip the dead `downscale:` field from all render blocks; update `portraits/README.md` (it still documents the deleted hand passes + old pipeline).
3. **Revisit chibi generation** in `portrait_tool.py` (current is a placeholder crop) before wiring portraits into the ROM.
4. **Build pipeline:** `build-campaign.ts` (#13) + the self-contained test chapter to see a bust in mGBA (Braulo end-to-end, #15). De-risks everything downstream.
5. Wave 2 (map sprites) / Wave 3 (battle anims) — full custom, behind portraits.

## KEY FILES

- `tools/ref_to_bust.py` — **rewritten** ref → 96×80 indexed bust (pngquant pipeline). Knobs: `--crop`, `--zoom`, `--sharpen`, `--bg-thresh`, `--preview`.
- `tools/portrait_tool.py` — bust↔FE8 tilesheet (`encode`/`decode`), `generate` (chibi/mouth/palette), `preview` (dead-zone). 
- `campaigns/rime-of-the-frostmaiden/{pcs,npcs}/*.yaml` `art.render:` — per-unit ref/crop/zoom (+ `hand_pass`, mostly being nulled). Source of truth; byte-reproduces each bust.
- `campaigns/rime-of-the-frostmaiden/portraits/<unit>.png` — shipped 96×80 indexed busts. Remaining hand-pass scripts: `marty_eye_fixup.py`, `pinky_cleanup.py`, `pepperjack_cleanup.py`, `brie_cleanup.py` (to be dropped).
- `…/References/PCs/` — hi-res refs (outside the repo, in the Documents source folder). Fitted refs go here.
- `tools/build-campaign.ts` — **does not exist yet** (#13); the campaign-data/portrait injector.

## STANDING RULES (how Nicolas wants this work done)

- **Art = full custom for the 10 named cast** (portrait → map sprite → battle anim). Enemies stay vanilla.
- **Collaborative, one item at a time:** render → show final → **WAIT for OK** → commit. Show 2–3 options on real trade-offs (framing/ref choice).
- **Clean native rewrites, NO band-aids** (no stale fields, no "kept old mode just in case", no reverted-on-DATE banners).
- **Auto-push to main** once a change is approved.
- **Doc source-of-truth:** per-unit facts in YAML; `docs/*` generated; lean repo; backlog = GitHub issues.
- **Stock vanilla FE8 classes/weapons; element = flavor never mechanic; combat RULES are vanilla FE.**
- **`make` green at the end of every session** (it is — no C/build changes this session).
