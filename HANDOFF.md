# Handoff: Portrait Wave 1 in progress (3/10 cast done) + scope locked to custom art in 3 waves. NEXT = next "Face Clean" bust from Nicolas (Meesmickle/Rootis/Sclorbo/Wolfram/Pinky/Pepperjack/Brie), convert with the now-generalized `ref_to_bust.py`.

**Date:** 2026-06-01
**Session focus:** Shipped two more portraits (Prof. R.B. Geenius, Marty), generalized the ref→bust converter to handle any flat background color, and formally locked the art scope: full-custom portrait + map sprite + battle animation for all named cast, delivered in 3 waves.

## Accomplished this session

- **Scope locked + docs corrected.** Custom art (portrait + map sprite + battle animation) for **all 10 named cast** (7 PCs + 3 NPCs: Pinky, Pepperjack, Brie); **enemies keep vanilla FE8 map & battle sprites**. Delivered in **3 waves, in order: (1) all portraits → (2) all map sprites (16×16 chibis) → (3) battle animations.** Rewrote the stale "generative tools = concept-ref only / hand-drawn" language in `docs/decisions.md` and `docs/PRD.md`: the clean Gemini/Nano-Banana bust is the **pre-approved source**, tool-converted (not hand-pixeled) into the final indexed asset. Memory updated (`feedback_custom_art_lever`).
- **Prof. R.B. Geenius portrait shipped** (`8f6d129`, re-cropped after). Converted from `RBG Face Clean.png` — manic toothy grin + fangs, purple top-hat w/ gold band, big ears, yellow coat shoulders + gold cravat (all 4 `art:` must-keeps). **Final crop `0,120,2068,1843`** (head-and-shoulders framing). Verified packs.
- **Marty portrait shipped** (`d2318fb`, re-cropped after). Converted from `Marty Face Clean.png` — red spotted cap, grey gills, smiley dot-eyed face, red scarf + robe shoulders. **Final crop `0,216,2068,1938`** (head-and-shoulders framing).
- **`ref_to_bust.py` generalized** (`d2318fb`). Replaced the hardcoded bright-cream HSV key with: **sample the actual border color (median of top+left+right edges), key pixels within an RGB distance of it** (`--bg-thresh`, default 45), then the same border-connected flood. Now robust to ANY flat backdrop (Braulo/RBG cream *and* Marty's blue-grey). RBG cream-bg regression after the change = 11/7680 px (visually identical).

## Workflow established this session

- **Per-character cadence (Wave 1):** Nicolas uploads ONE clean frameless **"<Name> Face Clean"** PNG at a time into `…/References/PCs/`; Claude converts → shows `_preview.png` → commits + pushes → waits for the next. One character per round. **Full-body action refs convert poorly — wait for the Face Clean version.**
- **Refs are large (~2048²).** The Read-tool preview is downscaled — do NOT eyeball crop coords off it. Auto-detect the subject bbox on the full-res image first (sample border color → distance mask → dense row/col spans), then build a ~1.2-aspect crop from that. (RBG's first attempt failed because a 600-scale crop landed in an empty 2048-scale corner.)
- **Framing = HEAD-AND-SHOULDERS, like Braulo** (head in the top ~40–55%, shoulders/torso filling the rest). Do NOT crop tight to the head/collar — that reads as "zoomed in" (the v1 RBG/Marty mistake). These refs are near-square with the subject filling the frame, so the widest 1.2-aspect crop that fits is ~full-width (≈2068) × ~1723 tall; center that on the subject to pull the shoulders in (accept a tiny hat-crown trim if needed).

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
