# Handoff: Milestone B — portraits + names + character class/stats all DONE & ROM-verified. Next code step = a copied test chapter spawning the cast. Parallel art track (map sprites + battle anims) is still entirely vanilla and untouched.

**Date:** 2026-06-04
**Session Focus:** Recover Milestone B after the reset. Proved the text path, then implemented YAML-driven unit-name injection and gCharacterData class/stat injection. Both verified by decoding the built ROM (no mGBA needed). Two clean-build checkpoints, both green.

## Accomplished (this session)
- **Diagnosed the reset's "Huffman corruption"** — it was NOT a textprocess/huffman bug. It's a **string-terminator parity** issue: FE8 packs text 2 bytes/u16, `[X]`=0x00 terminator; an odd number of name bytes pairs the 0x00 into the last glyph so the decoder runs away. Vanilla pads odd names with `[.]` (`Franz[.][X]` vs `Seth[X]`). My first single-name test missed it because "Braulo" is even-length.
- **`tools/verify_text.py`** (new) — decodes message text straight from the built ROM by `.map` symbol; regression gate for any text change. Caught the parity bug instantly.
- **Name injection** — `build_campaign.py inject_names`: each cast `fe_name`/`name` (YAML) → the vanilla slot's `.nameTextId` message in `texts/texts.txt`, parity-padded. All 10 names render+terminate; full sweep 0 runaway.
- **Character injection** — `build_campaign.py patch_character_data`: rewrites each slot's `gCharacterData[]` entry (class/affinity/level/base stats/weapon ranks/growths). Verified in ROM: 8 classed slots correct.
- **fe_name** added to marty + prof-rbg (overflowed FE8's 12-char buffer). **PyYAML** added to the build interpreter + `setup-toolchain.sh`.
- **Docs/issues drift cleanup + drift-prevention harness.** Closed the done/obsolete issues (M0 + M2; #4/#6 obsolete), retitled #14 (decomp-native events), opened #38 (map sprites) + #39 (battle anims). Recorded the real toolchain in `decisions.md` (Python not TS; decomp-native not Event Assembler; no SRD pull) as dated ADRs, added a **Working Conventions / Definition of Done** section, pruned `PRD.md` to vision-only, made `CLAUDE.md` lean (pointers + DoD), fixed README/rules-mapping, and added a lightweight CI drift guard (`.github/workflows/checks.yml`).

## Current State — what works
- `make CAMPAIGN=rime-of-the-frostmaiden` builds a ROM carrying: 10 custom busts, 10 cast names, and 8 cast units' class+stats. `make green` = ROM builds (we diverge from vanilla sha1 on purpose; build the `fireemblem8.gba` target, not `compare`).
- **Verification without mGBA:** `python3 tools/verify_text.py` (text), and gCharacterData decodes correctly from the ROM (class IDs, affinity=7 Anima, L1, zeroed personal bases).

### How character injection works
`patch_character_data` rewrites each cast slot's `gCharacterData[]` (and `restore_vanilla_sources()` git-restores `texts.txt` + `data_characters.c` to vanilla at the start of every build, so injection is idempotent and stat-donor reads stay vanilla):
- **defaultClass** ← YAML `fe_stats.class` via `CLASS_MAP` (decisions.md Class Mapping). **affinity** = `UNIT_AFFIN_ANIMA`. **baseLevel** ← YAML.
- **personal base stats** = YAML stat − class base (from `data_classes.c`). FE8's one Pow stat shows as STR or MAG; both → `basePow`. Luck is character-only. fe_stats == class base for all units → deltas 0 → displayed stats = pure class base = YAML.
- **growths + weapon ranks** ← copied from a **class-matched vanilla donor** (`STAT_DONOR`: Shaman→Knoll, Mage→Lute, Archer→Neimi, Knight→Gilliam, Priest→Moulder, Pegasus→Vanessa, Pirate→Garcia proxy). "Do what the game does" — they level + fight like a real FE unit of their class. Verified: Franz(wolfram)=Gilliam Knight growths/Lance C; Gilliam(meesmickle)=Knoll Shaman growths/Dark C.
- **gender** ← `CA_FEMALE` from YAML `gender:` (default male). Cleared the leaked `CA_FEMALE` on the male slots (Braulo/Rootis/Pinky). Brie = the only female.
- brie + pepperjack have `class: null` → left vanilla, name-only (see below).

## Open / deferred (follow-ups)
- **brie + pepperjack** — RBG-crafted **constructs** (D&D ballistae/automatons), NOT a special class. FE8 has no playable Ballistician class, so they join the army the **normal FE8 way** via chapter events; their stock class + arrival chapter are chosen **when we build those chapters**. `class: null` (name-only) until then. (decisions.md Class Mapping.)
- **Supports** still point at the vanilla slot's data — rework later (inactive unless triggered).
- **Custom gendered/class battle sprites** — art track (#38/#39), not data.

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

## Blockers
- None hard. Step 3 needs care (event scripting) but no external dependency. Art track is gated on Nicolas's one-at-a-time art walkthroughs.

## Build Hygiene
- **Clean-build:** `make clean && make CAMPAIGN=rime-of-the-frostmaiden`. `build_campaign.py` now **git-restores** the decomp source files it patches (`texts.txt`, `data_characters.c`) to vanilla at the start of every build, so injection is idempotent — repeated `make`s are safe.
- **CI make-green gate:** `.github/workflows/checks.yml` runs the real `make` on a MOCK baserom (`/dev/urandom`, mirroring the decomp's own build.yml) — catches build breakage without the copyrighted ROM. Plus a fast lint/YAML/drift job.
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
Custom art for the 10 named cast; enemies vanilla. Stock FE8 classes/weapons; combat = pure vanilla FE. `make` green at session end. Auto-push to main once approved. Don't commit the fireemblem8u submodule pointer.
