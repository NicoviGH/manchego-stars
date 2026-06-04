# Handoff: Milestone B — portraits + names + character class/stats all DONE & ROM-verified. Next code step = a copied test chapter spawning the cast. Parallel art track (map sprites + battle anims) is still entirely vanilla and untouched.

**Date:** 2026-06-04
**Session Focus:** Recover Milestone B after the reset. Proved the text path, then implemented YAML-driven unit-name injection and gCharacterData class/stat injection. Both verified by decoding the built ROM (no mGBA needed). Two clean-build checkpoints, both green.

## Accomplished (this session)
- **Diagnosed the reset's "Huffman corruption"** — it was NOT a textprocess/huffman bug. It's a **string-terminator parity** issue: FE8 packs text 2 bytes/u16, `[X]`=0x00 terminator; an odd number of name bytes pairs the 0x00 into the last glyph so the decoder runs away. Vanilla pads odd names with `[.]` (`Franz[.][X]` vs `Seth[X]`). My first single-name test missed it because "Braulo" is even-length.
- **`tools/verify_text.py`** (new) — decodes message text straight from the built ROM by `.map` symbol; regression gate for any text change. Caught the parity bug instantly.
- **Name injection** — `build_campaign.py inject_names`: each cast `fe_name`/`name` (YAML) → the vanilla slot's `.nameTextId` message in `texts/texts.txt`, parity-padded. All 10 names render+terminate; full sweep 0 runaway.
- **Character injection** — `build_campaign.py patch_character_data`: rewrites each slot's `gCharacterData[]` entry (class/affinity/level/base stats/weapon ranks/growths). Verified in ROM: 8 classed slots correct.
- **fe_name** added to marty + prof-rbg (overflowed FE8's 12-char buffer). **PyYAML** added to the build interpreter + `setup-toolchain.sh`.

## Current State — what works
- `make CAMPAIGN=rime-of-the-frostmaiden` builds a ROM carrying: 10 custom busts, 10 cast names, and 8 cast units' class+stats. `make green` = ROM builds (we diverge from vanilla sha1 on purpose; build the `fireemblem8.gba` target, not `compare`).
- **Verification without mGBA:** `python3 tools/verify_text.py` (text), and gCharacterData decodes correctly from the ROM (class IDs, affinity=7 Anima, L1, zeroed personal bases).

### How character injection works
`patch_character_data` rewrites each cast slot's `gCharacterData[]`:
- **defaultClass** ← YAML `fe_stats.class` via `CLASS_MAP` (decisions.md Class Mapping). **affinity** = `UNIT_AFFIN_ANIMA`. **baseLevel** ← YAML.
- **personal base stats** = YAML stat − class base (from `data_classes.c`). FE8's one Pow stat shows as STR or MAG; both → `basePow`. Luck is character-only. fe_stats == class base for all units → deltas 0 → displayed stats = pure class base = YAML.
- **baseRanks** ← class weapon type (`CLASS_WEAPON`) at flat `WPN_EXP_E`. **growths** ← zeroed (unit grows at pure class rate, not the slot's).
- brie + pepperjack have `class: null` → left vanilla, name-only.

## Open / deferred (decisions + follow-ups)
- **brie + pepperjack classes** — `class: null`, TBD. Name-only until FE8 classes chosen.
- **Weapon-rank level** — flat `E` for everyone; balance pass needs real ranks (vanilla L1 casters ~C). Likely YAML-driven. *Decision: per-unit vs per-class default.*
- **Gender / attributes / supports** — still the vanilla slot's. `CA_FEMALE` leaks onto Braulo/Rootis/Pinky slots (no dangerous flags like CA_LORD/CA_SUMMON). Needs a YAML-driven gender pass incl. `_F` class variants; supports still point at the slot's data. Note Pinky is male but rides the Neimi(F)/Pegasus-Knight (female-anim) slot — flavor handwave for now.

## ARTWORK — still mostly undone (parallel track)
The custom-art lever is portrait **+ map sprite + battle anim** for all 10 cast ([[feedback_custom_art_lever]]). Only the **portraits/busts** exist and are injected. Remaining:
- **Map (overworld) sprites** — NOT started. Units currently walk around as the vanilla slot's sprite (Braulo looks like Eirika on the map). Needs custom indexed sprites + an injection path in `build_campaign.py` (parallel to portraits).
- **Battle animations** — NOT started. Units fight with the vanilla class/slot anim. Biggest art lift; custom battle anims per cast member.
- **Bust refinement / final portrait pass (#35)** — some busts flagged for fitted-ref re-renders ([[project_manchego_stars_portrait_pipeline]]); a final quality pass remains.
- Pipeline tools exist for portraits (`tools/portrait_tool.py`, `tools/ref_to_bust.py`); map-sprite + battle-anim tooling does NOT exist yet.

## Next Steps (priority order)
1. **Milestone B step 3 — test chapter (code).** COPY a normal chapter's `-event*.h` (NOT the tutorial Prologue), minimally edit unit defs to spawn the 8 classed cast on one map. First real visual confirmation of names + classes + stats + portraits together in mGBA. Event-script authoring is error-prone — copy a known-good chapter, don't hand-write the opening scene.
2. **Real maps** — Prologue (#20) + Ch1 (#21), once the test chapter proves the spawn pipeline.
3. **Art track (can run in parallel):** map sprites, then battle anims; final portrait pass. Walkthrough one artwork at a time with Nicolas; render → show → wait for OK → commit ([[feedback_show_before_committing_art]]).
4. **Cleanup decisions above** (brie/pepperjack classes, weapon ranks, gender).

## Blockers
- None hard. Step 3 needs care (event scripting) but no external dependency. Art track is gated on Nicolas's one-at-a-time art walkthroughs.

## Build Hygiene
- **Clean-build:** `make clean && make CAMPAIGN=rime-of-the-frostmaiden`. `build_campaign.py` re-injects (idempotent) into the submodule working tree each build; `make clean` does NOT restore vanilla decomp source — reset with `git -C fireemblem8u checkout <path>`.
- **Verify text:** `python3 tools/verify_text.py`. **mGBA:** `pkill -9 -i mgba; "/Applications/mGBA.app/Contents/MacOS/mGBA" "$PWD/fireemblem8u/fireemblem8.gba" &` (`open -a mGBA` does NOT reload a running instance). Fresh game: `rm fireemblem8u/fireemblem8.sav`.
- **Never commit the fireemblem8u submodule pointer.** Build interpreter is brew python@3.12 (needs numpy/pillow/pyyaml via setup-toolchain.sh).

## Key Files
- `tools/build_campaign.py` — portraits + names (`inject_names`) + character class/stats (`patch_character_data`). Chapter/event injection next; map-sprite/battle-anim injection later.
- `tools/verify_text.py` — ROM text decoder / regression gate.
- `tools/portrait_tool.py`, `tools/ref_to_bust.py` — bust pipeline (only the portrait art part exists).
- `campaigns/rime-of-the-frostmaiden/{pcs,npcs}/*.yaml` — unit data (class, `fe_stats`, `fe_name`, art briefs).
- `campaigns/rime-of-the-frostmaiden/portraits/*.png` — the 10 authored busts.
- `fireemblem8u/src/data_characters.c`, `src/data_classes.c`, `texts/texts.txt` — decomp injection targets (build artifacts; restore with git checkout).
- `docs/decisions.md` §Class Mapping — authoritative class→FE8 mapping.

## Memory
- [[manchego-stars-text-terminator-parity]] — the odd-length `[.]` terminator gotcha.
- [[feedback_fe_name_truncation]] — short `fe_name` (≤12).
- [[feedback_custom_art_lever]] — custom art on portrait + map sprite + battle anim.
- [[project_manchego_stars_portrait_pipeline]] — bust pipeline, portraitId-1, mGBA reload trap.
- [[feedback_show_before_committing_art]] — render→show→OK→commit for art.

## Standing Rules
Custom art for the 10 named cast; enemies vanilla. Stock FE8 classes/weapons; combat = vanilla FE; element = flavor. `make` green at session end. Auto-push to main once approved. Don't commit the fireemblem8u submodule pointer.
