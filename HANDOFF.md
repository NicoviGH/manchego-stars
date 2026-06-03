# Handoff: Build pipeline STARTED (Phase 2). Portrait injection is live in-ROM — all 10 custom busts now appear in mGBA on the early vanilla cast, STATIC (no mouth/eye animation) and facing the correct way. 3 open refinements from Nicolas's first in-game look: (1) menu mouth-hole, (2) chibi quality, (3) broader in-game test. Committed + pushed `95d46c9`.

**Date:** 2026-06-03 (session 2 of the day)
**Session focus:** Kicked off `build_campaign.py` (the generator — Python, not .ts; see below). Milestone A = inject all 10 busts onto vanilla portrait slots so we can SEE them in mGBA. Done end-to-end: build green, ROM boots, Nicolas confirmed busts show in conversations. Then two fixes from his feedback (static portraits, facing) landed; three refinements remain.

## DECISIONS THIS SESSION (settled — don't re-litigate)
- **Generator language = Python (`tools/build_campaign.py`), NOT TypeScript.** The decomp output (C/asm/text/graphics) is fixed regardless of generator language; Python reuses `portrait_tool.py`/`ref_to_bust.py` directly and pyyaml is already there. The old "build-campaign.ts" backlog name is retired.
- **Injection strategy = overwrite vanilla slots** (not extend FE8 tables). Byte-stable, minimal engine surface, satisfies the Engine/Content boundary (the GENERATOR knows names; emitted C is just data).
- **Custom portraits are STATIC** (no talking-mouth, no eye-blink). FE8 always runs both animations from the `imgMouth` frame strip; aligning custom per-frame art is infeasible. We defeat it: bake the whole neutral face into the tileset + emit transparent overlay frames (`portrait_tool.generate(static_portrait=True)`). Confirmed good in-game.
- **"make green" no longer means byte-identical-to-vanilla** — it means the ROM builds. We build the decomp's `fireemblem8.gba` target directly, skipping its vanilla-sha1 `compare` goal. Restore vanilla art: `git -C fireemblem8u checkout graphics/portrait`.
- **FE8 portraits face screen-LEFT** (engine HFLIPs for the right speaker). Busts are stored CANONICAL (left-facing): a right-facing ref is flipped at the RENDER stage (`ref_to_bust --flip-h`, recorded as `art.render.flip_h: true`), NOT at injection. So the bust `.png`, its `_preview.png`, and the in-game face all agree.
- **`_preview.png` (3× NN review aid) must stay fresh** — Nicolas reviews busts on GitHub; regenerate whenever a bust changes (they had gone stale; refreshed all 10 this session).

## WHAT WORKS NOW (committed 95d46c9, pushed)
- `make` → runs `build_campaign.py` → injects 10 busts → builds ROM. Green.
- Portrait map (our bust → vanilla slot it rides on): braulo→Eirika, marty→Seth, wolfram→Franz, meesmickle→Gilliam, prof-rbg→Moulder, rootis→Vanessa, sclorbo→Ross, pinky→Neimi, pepperjack→Garcia, brie→Colm. (Hardcoded in `build_campaign.py PORTRAIT_MAP`; class/stat/name mapping is Milestone B.)
- `flip_h: true` set on braulo, wolfram, meesmickle, prof-rbg, pinky, brie (the 6 right-facers); their bust PNGs are flipped in-place to canonical left-facing and previews regenerated. marty/rootis/sclorbo/pepperjack already faced left.
- **fireemblem8u/graphics/portrait/** holds the injected build artifacts (NOT committed — reproducible from YAML; submodule pointer left untouched).

## OPEN REFINEMENTS (Nicolas's first in-game look — priority order)
1. **Menu mouth-hole → fold into Milestone B (portrait_data ownership).** Status/menu face shows a missing mouth rectangle. Traced fully: `PutFace80x72_Standard`/`_Raised` ([fireemblem8u/src/face.c:660](fireemblem8u/src/face.c)) fill the face from TSA `gUnknown_085A0838` (header-less u16 tile-entry array, 10-wide), then **stamp the mouth at the slot's `xMouth`/`yMouth`** (FaceData) using sheet tiles `0x1C-0x1F`/`0x3C-0x3F` (px (224,0)-(256,16)) — tiles our `encode` leaves empty. Deeper issue: the stamp draws at the *vanilla slot's* `xMouth`/`yMouth`, and **our busts (riding Eirika/Seth/… slots) don't have their mouths at those coords** — verified the vanilla stamp tiles are SEPARATELY authored (NOT a crop of the decoded bust: tested 8 slots, none match `bust(xMouth*8,yMouth*8)`), and per-slot coords vary (Eirika 2,6; Seth 2,5; …). So a pixel-copy alone still misplaces the mouth. **Proper fix = own `portrait_data[]`** (Milestone B): emit our rows with `xMouth`/`yMouth` matching our art + bake the matching stamp tiles in one place. Do NOT build per-vanilla-slot TSA-parsing for Milestone A — it gets thrown away. Engine stays vanilla; the fix is data.
2. **Chibi quality varies.** Marty's chibi looks great; Braulo's is rough (non-human/crab face crops poorly). `_make_chibi` is a naive center-crop + nearest-neighbor ([tools/portrait_tool.py:180](tools/portrait_tool.py)). Improve face-region detection or add a per-unit chibi crop knob. (This was already the deferred "chibi placeholder" item.)
3. **Broader in-game test.** Nicolas saw only braulo/wolfram/marty (the prologue cast). He wants to see the rest faster — options: pick a talky chapter, or also map our busts onto early ENEMY portraits so one fight shows more. Natural fit with Milestone B's visual-test chapter.

## FACING — needs Nicolas's eyes to finish
Set from the bust montage (I can view images): flipped the 6 above; left marty/rootis/sclorbo/pepperjack. **rootis (snowman) and sclorbo (flame) are near-symmetric — unconfirmed.** pepperjack faces left (barrel left). If any read backwards in-game, flip that bust PNG (`ref_to_bust --flip-h` from its ref, or mirror the PNG) and toggle `art.render.flip_h` to match — the PNG is the canonical artifact now, not the injection step. prof-rbg flip is INTERIM — Nicolas made new 3/4 refs (`RBG3/4`, `RBG3/4_Flat`, the Flat one downscales better per the standing ref-spec lesson); re-render prof-rbg from RBG3/4_Flat and drop its flip_h.

## NEXT STEPS (priority)
1. **Milestone B** — own `portrait_data[]`/`gCharacterData[]`, which also fixes the menu mouth-hole properly (#1) and enables the visual-test chapter (#3).
2. **Chibi pass** (#2).
3. **Milestone B:** the real generator — character names/stats from YAML + a spawn-them-all visual-test chapter (covers #3). This is where build_campaign starts emitting `gCharacterData[]` rows, `portrait_data[]`, event files, and text. Injection points already mapped:
   - characters → `fireemblem8u/src/data_characters.c` `gCharacterData[]`
   - portraits → `src/portrait_data.c` + `data/data_portrait.s`
   - chapter/units/dialogue → `src/events/chN-*.h` (`ChapterEventGroup`, REDA/UnitDef, EventListScr, FIGHT/Text_BG); included via `src/events_script.c`/`events_info.c`
   - text → `texts/texts.txt` (`## MSG_*` → numeric IDs)
   - chapter table → `src/chapterdata.c` + `src/data/chapter_settings.json`

## KEY FILES (this session)
- `tools/build_campaign.py` — the generator. `PORTRAIT_MAP`, `inject_portraits()`, `_load_unit_yaml()` (reads `art.render.flip_h`). Milestone B hangs off here.
- `tools/portrait_tool.py` — added `generate(..., static_portrait=True)` + `--static`. The `encode` packing is what needs extending for the menu mouth-stamp (#1).
- `Makefile` (project root) — generator step + builds decomp ROM target directly.
- `campaigns/.../{pcs,npcs}/*.yaml` `art.render.flip_h` — facing.

## STANDING (unchanged)
- Custom art for the 10 named cast (portrait→sprite→anim); enemies vanilla. Stock FE8 classes/weapons; combat RULES vanilla FE; element = flavor.
- Show art before committing; auto-push to main once approved; clean native rewrites.
- Don't commit the fireemblem8u submodule pointer (pre-existing local changes + our build artifacts live there).
