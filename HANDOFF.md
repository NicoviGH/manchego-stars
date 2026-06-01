# Handoff: Portrait Wave 1 in progress (3/10 cast done) + scope locked to custom art in 3 waves. NEXT = next "Face Clean" bust from Nicolas (Meesmickle/Rootis/Sclorbo/Wolfram/Pinky/Pepperjack/Brie), convert with the now-generalized `ref_to_bust.py`.

**Date:** 2026-06-01
**Session focus:** Shipped two more portraits (Prof. R.B. Geenius, Marty), generalized the ref→bust converter to handle any flat background color, and formally locked the art scope: full-custom portrait + map sprite + battle animation for all named cast, delivered in 3 waves.

## Accomplished this session

- **Scope locked + docs corrected.** Custom art (portrait + map sprite + battle animation) for **all 10 named cast** (7 PCs + 3 NPCs: Pinky, Pepperjack, Brie); **enemies keep vanilla FE8 map & battle sprites**. Delivered in **3 waves, in order: (1) all portraits → (2) all map sprites (16×16 chibis) → (3) battle animations.** Rewrote the stale "generative tools = concept-ref only / hand-drawn" language in `docs/decisions.md` and `docs/PRD.md`: the clean Gemini/Nano-Banana bust is the **pre-approved source**, tool-converted (not hand-pixeled) into the final indexed asset. Memory updated (`feedback_custom_art_lever`).
- **Prof. R.B. Geenius portrait shipped** (`8f6d129`; redone from a better ref in `4ddf695`). Final source = **`RBG Face Clean and Shoulders.png`** (proper bust composition; Nicolas regenerated it with shoulders after v1 read too head-only). Manic grin + fangs, purple top-hat, big ears, yellow lapels + gold cravat (all 4 `art:` must-keeps). **Final crop `0,20,2048,1727`** (head-and-shoulders). Verified packs.
- **Marty portrait shipped** (`d2318fb`, re-cropped after). Converted from `Marty Face Clean.png` — red spotted cap, grey gills, smiley dot-eyed face, red scarf + robe shoulders. **Final crop `0,216,2068,1938`** (head-and-shoulders framing).
- **`ref_to_bust.py` generalized** (`d2318fb`). Replaced the hardcoded bright-cream HSV key with: **sample the actual border color (median of top+left+right edges), key pixels within an RGB distance of it** (`--bg-thresh`, default 45), then the same border-connected flood. Now robust to ANY flat backdrop (Braulo/RBG cream *and* Marty's blue-grey). RBG cream-bg regression after the change = 11/7680 px (visually identical).

## Workflow established this session

- **Per-character cadence (Wave 1):** Nicolas uploads ONE clean frameless **"<Name> Face Clean"** PNG at a time into `…/References/PCs/`; Claude converts → shows `_preview.png` → commits + pushes → waits for the next. One character per round. **Full-body action refs convert poorly — wait for the Face Clean version.**
- **Refs are large (~2048²).** The Read-tool preview is downscaled — do NOT eyeball crop coords off it. Auto-detect the subject bbox on the full-res image first (sample border color → distance mask → dense row/col spans), then build a ~1.2-aspect crop from that. (RBG's first attempt failed because a 600-scale crop landed in an empty 2048-scale corner.)
- **Framing = HEAD-AND-SHOULDERS, BOTTOM-ANCHORED, like Braulo/Eirika.** FE busts fill to the bottom row with transparent **headroom on top** and small side margins (vanilla Eirika: opaque rows 11-79, cols 21-88). The subject must NOT float — transparent space goes on TOP, never the bottom (the green band you see in a preview is index-0 transparent = invisible in-game, but if it's at the BOTTOM the character floats in the textbox).
- **Use `tools/autoframe.py` for every ref** (don't hand-crop): it detects the subject, composites it onto a flat-bg 1.2-aspect canvas — bottom-anchored — then prints the exact `ref_to_bust.py … --crop 0,0,W,H` command to run on the framed file. Defaults (`--subj-h 0.90 --subj-w 0.90`) give ~88% vertical fill / ~9px headroom, matching Braulo. **Fill is tunable** via `--subj-h`/`--subj-w` (higher = bigger / less margin) — use this if a result reads too zoomed-in or too zoomed-out instead of hand-cropping.
- **Pipeline quality settings (in `ref_to_bust.py`, all dialed in this session):** (1) downscale the FULL-RES crop with BOX area-averaging to 2× target then LANCZOS, and **sharpen at the 96×80 target** (UnsharpMask r1/170%/1) — sharpening before the downscale blurs small features; (2) quantize with **MAXCOVERAGE not MEDIANCUT** (mediancut wasted ~6/15 slots on near-duplicate greys = the "blurry/muddy" look); (3) **contrast ×1.15, no saturation** boost (saturation tints neutral eyes/face purple/cyan); (4) **quantize foreground only** (fill bg with median fg colour so the backdrop doesn't eat a palette slot). Sanity-check after convert: `near-dup palette pairs` should be 0.
- **Tiny focal features (eyes, mouth) still need a manual pixel touch-up** after conversion even with the good pipeline — a 3px eye can't survive quantization cleanly. Recipe: dump the index grid for the region, clear muddy edge indices to the face colour, stamp symmetric dark eyes (+1px white highlight), solidify the mouth curve to black. **A reconvert regenerates from scratch and WIPES these touch-ups — always re-apply them last.**
- **DON'T reconvert already-approved portraits.** Braulo was reverted to its original (`a35b329`) because Nicolas preferred it; pipeline improvements apply to NEW portraits only unless he asks. (RBG is currently on the OLD mediancut quantizer + got manual watermark inpaint from `/tmp/rbg_clean2.png`; reconverting it with maxcoverage would improve it but needs re-doing the watermark removal — only if asked.)
- **Gemini sparkle watermark:** every Gemini ref has a 4-point sparkle in the bottom-right. It usually gets keyed out as background, but if it lands on a light/cream area it's too bright to key and survives into the bust (happened to RBG). After converting, check the bottom-right; if a sparkle remnant is there, inpaint it in the source first (bright `V>0.90 & S<0.18` pixels in the corner → bg color, dilate ~8px via PIL `MaxFilter`) then reconvert. (no scipy in this env — use PIL for the dilation.)
- **DEFAULT FRAMING RECIPE = "max zoom without cropping"** (use this for every portrait; supersedes autoframe-with-padding and the shoulder-width crop): detect the FULL subject bbox (low coverage threshold ~1% so nothing real is cut), then take the **tightest 1.2-aspect box that still contains the whole bbox** (if bbox is taller-relative-to-1.2, height-limited: crop_h = bbox_h, crop_w = 1.2·crop_h; else width-limited), centered on the subject and clamped to the image. The subject fills the frame in its limiting dimension with thin margins on the other axis and **nothing cropped**. The well-framed landscape refs already sit near 1.2 (RBG 1.19, Marty 1.17 incl. staff), so this fills ~90%+ and looks great. Quick check after: opaque should span ~rows 1-78, ~90%+ width. (autoframe.py still works but pads = less fill; the direct containing-crop is better.)
- **Tall narrow subjects (hats/caps) won't fill the width** like wide-bodied Braulo (RBG 62% wide, Marty 75% vs Braulo 98%) — that's correct and matches vanilla (Eirika is 70% wide). Don't force width fill; it would crop the hat/cap. Calibrate on VERTICAL fill (~82-88% tall, ~9-14px headroom) + bottom-anchoring, not width.

## Tried but didn't work (lessons)

- **Crop coords read off the displayed preview** → wrong; refs are ~2048² and the preview is downscaled. Always detect bbox on full-res first.
- **The old bright-cream HSV key** flooded Marty's whole frame transparent (his bg is a medium blue-grey, V≈0.47, below the V>0.72 cream threshold). Fixed by sampling the real border color instead — see above.
- **Image generation from this environment is still blocked** (nanobanana MCP pinned to a retired model; API key only in MCP env). Nicolas generates every ref on his side. Unchanged from last session.

## Current state

- **Build:** green + reproducible on macOS (`make` → ROM, `make verify` → OK). No campaign data injected yet (build-campaign pipeline, issues #13–15, still unbuilt). Portraits are authored assets; not yet wired into a built ROM.
- **Wave 1 portraits: 3 / 10 done** — Braulo, Prof. R.B. Geenius, Marty. Remaining 7: Meesmickle, Rootis, Sclorbo, Wolfram, Pinky, Pepperjack, Brie.
- **Wave 2 (map sprites) / Wave 3 (battle anims):** not started; blocked behind Wave 1.
- **Story:** all 9 MVP chapters (ch00–ch08) authored. Ch9–20 still blocked on the rest of the DM notes.
- Working tree clean except the known `fireemblem8u` submodule shim drift (leave it).

## Blockers / open

- **Next portrait needs a clean "Face Clean" bust from Nicolas** (any of the remaining 7; order doesn't matter). Then conversion is ~2 commands.
- **Refs still missing for some cast:** Pinky has NO ref at all; Rootis has only a character sheet; Pepperjack + Brie currently share ONE combined image — each will need its own Face Clean bust.
- **32×32 `_chibi` mini-face** (per-character, used in some unit UI) is NOT produced by the pipeline yet — only the 96×80 bust. Small gap to close later; not blocking.
- **#16 (toolchain)** still needs a manual GitHub close (agent close blocked by permission classifier).
- **pepperjack/brie `fe_stats.class = null`** — FE-legal class TBD post-MVP (art can still proceed).
- **Rootis & Sclorbo recruitment chapters / Sclorbo signature moment = TBD** (Nicolas to recall). **Ch 9–20 plot** blocked on the rest of the DM notes.

## Next steps (priority order)

1. **Finish Wave 1 portraits (7 left).** For each Face Clean ref Nicolas drops:
   - Detect bbox on full-res: sample border color, distance-mask, find dense row/col spans; build a ~1.2-aspect crop centered on head+shoulders.
   - `python3 tools/ref_to_bust.py "<ref>.png" campaigns/rime-of-the-frostmaiden/portraits/<unit>.png --crop x0,y0,x1,y1 --preview campaigns/.../<unit>_preview.png` (tune `--bg-thresh` only if the backdrop is low-contrast vs the subject).
   - `python3 tools/portrait_tool.py encode <unit>.png /tmp/sheet.png` to confirm it packs; show the `_preview.png`; commit + push.
2. **Wave 2 — map sprites (16×16 chibis):** custom per cast member; pipeline TBD. `portrait_<Name>_chibi` (32×32) lives in `fireemblem8u/graphics/portrait/`. The walking overworld sprite is class-keyed (`.SMSId`) — vanilla is free; custom per-character map sprites are the new scope.
3. **Wave 3 — battle animations:** custom; heaviest lift.
4. **(Parallel, non-art)** build-campaign pipeline #13–15 to actually inject portraits/units into a built ROM.

## FE sprite architecture (confirmed in decomp this session)

- **Portrait = the only per-CHARACTER art** in vanilla FE8 (96×80 bust; tracked sheet is a 256×32 tile grid composited by 6 OAM objects — `gSprite_Face96x96` in `fireemblem8u/src/face.c`). Plus a 32×32 `_chibi`.
- **Map sprite = per-CLASS** (`.SMSId` field, `fireemblem8u/src/data_classes.c`), shared by all units of a class, auto-recolored per faction.
- **Battle animation = per-CLASS + weapon** (resolved via `GetBattleAnimationId(unit, …)`, `include/anime.h`).
- ⇒ Vanilla classes give every unit a working map/battle sprite for free; **our new scope adds CUSTOM map sprites + battle anims for the 10 named cast** (Waves 2–3). Enemies stay vanilla.

## Key files

- `tools/ref_to_bust.py` — Gemini "Face Clean" → 96×80 indexed bust. `--crop x0,y0,x1,y1 [--bg-thresh N] [--preview …]`. Now backdrop-agnostic (samples border color).
- `tools/portrait_tool.py` — bust↔FE8 sheet (`gSprite_Face96x96` OAM packer). `encode`/`decode`, verified byte-identical round-trip.
- `campaigns/rime-of-the-frostmaiden/portraits/` — authored busts (`<unit>.png` 96×80 indexed + `_preview.png`) + `README.md`. Done: `braulo.png`, `prof-rbg.png`, `marty.png`.
- `campaigns/rime-of-the-frostmaiden/{pcs,npcs}/*.yaml` `art:` block — per-character must-keep design brief (read before converting each).
- Gemini source refs: `/Users/Yonick/Documents/Claude/Projects/Manchego Stars / Fire Emblem Game/References/PCs/` (Nicolas drops "<Name> Face Clean.png" here).
- `docs/decisions.md` §Art & Audio / `docs/PRD.md` §8 — the locked art scope + 3-wave plan.
- `fireemblem8u/src/face.c`, `src/data_classes.c`, `include/anime.h` — authoritative sprite-architecture sources.

## Standing rules (how Nicolas wants this work done)

- **Art = full custom for the 10 named cast** (portrait + map sprite + battle anim), in 3 waves (portraits → map → battle). **Enemies stay vanilla.** **Gemini/Nano-Banana "Face Clean" busts are the pre-approved source** — convert faithfully, don't re-litigate the look; **Claude cannot generate images from here**. One character per round; wait for each upload.
- **Stock vanilla FE8 classes/weapons only**; **element = flavor, NEVER a mechanic**. Combat RULES are vanilla FE; the d20 is cosmetic only.
- **Ground FE claims in `fireemblem8u/`**; **ground STORY in the two PDFs** (DM notes Ch1–7 only + the published book).
- **Clean native doc rewrites** (no STALE/reverted banners). **Auto-push to main.** **Collaborative, one-item-at-a-time** walkthroughs.
- **Doc source-of-truth:** per-chapter/unit facts live ONLY in YAML; `docs/CHAPTERS.md`/`CLASSES.md` are GENERATED (`ruby tools/gen-*.rb`, never hand-edit). **Lean repo**; backlog = GitHub issues (M0–M4).
- **`make` must be green at the end of every session. Never commit a broken build.**
