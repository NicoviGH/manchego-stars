# Handoff: Milestone B content pipeline DONE & ROM-verified (portraits + names + class/stats/growths/ranks/gender). Repo now has a mechanized drift guard. Next code step = a copied test chapter spawning the cast. Art track (map sprites + battle anims) still entirely vanilla.

**Date:** 2026-06-04
**Session Focus:** Recovered Milestone B after the reset (text → names → character data), then a large hygiene pass: killed plan/doc drift and made the anti-drift discipline mechanical.

## Accomplished
- **Text path proven; the reset's "Huffman corruption" diagnosed** as a string-terminator **parity** bug (FE8 packs text 2 bytes/u16; `[X]`=0x00 terminator; odd-length names pair the 0x00 into the last glyph → decoder runs away). Vanilla pads odd names with `[.]`; `build_campaign.py` now does too. New `tools/verify_text.py` decodes message text from the built ROM (regression gate, no mGBA).
- **Name injection** (`inject_names`): each cast `fe_name`/`name` → the vanilla slot's `.nameTextId` message, parity-padded. All 10 render+terminate; sweep 0 runaway.
- **Character injection** (`patch_character_data`): class, affinity (Anima), level, pure-class base stats, plus **growths + weapon ranks copied from a class-matched vanilla donor**, and **gender** from YAML. Idempotent (`restore_vanilla_sources()` git-restores patched decomp files each build). Mechanism + donor list: `decisions.md` §Class Mapping (not restated here).
- **Dropped the damage-type / "element flavor" apparatus** as vestigial (cleaned from all docs; deferred to battle-anim art; issues #7/#10 closed).
- **Decided: Pepperjack & Brie are RBG-crafted constructs** that join as regular FE8 units via chapter events (no Ballistician class exists) — class + intro chosen at chapter-build time.
- **Drift cleanup + mechanized guard.** Reconciled GitHub (closed done/obsolete #1/2/5/13/15/4/6/7/10; retitled #14; opened #38 map sprites + #39 battle anims). Recorded real toolchain as dated ADRs; pruned `PRD.md` to vision-only; made `CLAUDE.md` lean; added **Working Conventions / Definition of Done**. Built `tools/check.py` (`make check`) run by a **git pre-commit hook** (drift can't be committed) and **CI**, which also runs a real **make-green build on a mock baserom**. Bumped CI actions (Node-20 deprecation).

## Current State — what works
- `make CAMPAIGN=rime-of-the-frostmaiden` builds a ROM with 10 custom busts, 10 names, and 8 cast units' full class/stats/growths/ranks/gender. (`make green` = it builds; we diverge from vanilla sha1 on purpose.)
- **Verify without mGBA:** `make verify` (text) decodes clean; gCharacterData decodes correctly from the ROM (right class, affinity 7, L1, pure-class bases). brie + pepperjack are name-only (no class yet).
- **Drift guard is green:** `make check` clean; CI `checks` + `build` both pass.

## Conventions to follow (read `decisions.md` → Working Conventions)
- **Single source of truth — link, don't restate.** (This session's drift came from copying one fact into 3 docs.)
- **Definition of Done:** docs/YAML updated in the *same* commit; `Closes #N` on completing tracked work; `make check` + `make` green; record new decisions in `decisions.md` (dated); never commit the `fireemblem8u` submodule pointer.
- **When you retire a concept, add its term to `DEAD_CONCEPTS` in `tools/check.py`** so it can't reappear.
- When asked "is it clean?", **run `make check`** and report the result — don't eyeball.

## Open / deferred
- **brie + pepperjack** — `class: null` (name-only) until their chapters are built (RBG-construct intro). See `decisions.md` §Class Mapping.
- **Supports** still point at the vanilla slot's data — rework later (inert unless triggered).
- **Custom gendered/class battle sprites** — art track (#39), not data.

## Artwork — mostly undone (parallel track)
Custom-art lever = portrait **+ map sprite + battle anim** ([[feedback_custom_art_lever]]). Only **busts** exist + are injected.
- **Map (overworld) sprites** (#38) — NOT started; units walk as the vanilla slot's sprite. Needs custom sprites + an injection path in `build_campaign.py`.
- **Battle animations** (#39) — NOT started; biggest art lift.
- **Final portrait pass** (#35) — some busts flagged for fitted-ref re-renders ([[project_manchego_stars_portrait_pipeline]]).
- Only portrait tooling exists (`tools/portrait_tool.py`, `tools/ref_to_bust.py`); map-sprite + battle-anim tooling does not.

## Next Steps (priority)
1. **Milestone B step 3 — test chapter (code).** COPY a normal chapter's `src/events/<ch>-event*.h` (NOT the tutorial Prologue), minimally edit unit defs to spawn the 8 classed cast on one map. First real visual confirmation of names + classes + stats + portraits together in mGBA. Event scripting is error-prone — copy a known-good chapter, don't hand-author the opening scene.
2. **Real maps** — Prologue (#20) + Ch1 (#21) once spawning is proven; design Pepperjack/Brie's introduction during their chapters.
3. **Art track (parallel):** map sprites → battle anims → final portrait pass. One artwork at a time; render → show Nicolas → wait for OK → commit ([[feedback_show_before_committing_art]]).

## Blockers
None hard. Step 3 needs care (event scripting). Art track is gated on Nicolas's one-at-a-time walkthroughs.

## Build Hygiene
- **Build:** `make clean && make CAMPAIGN=rime-of-the-frostmaiden`. Injection is idempotent (auto-restores patched decomp files), so repeated `make`s are safe.
- **Checks:** `make check` (drift guard) · `make verify` (ROM text). CI runs both + the make-green build (mock baserom).
- **mGBA:** `pkill -9 -i mgba; "/Applications/mGBA.app/Contents/MacOS/mGBA" "$PWD/fireemblem8u/fireemblem8.gba" &` (`open -a mGBA` does NOT reload). Fresh game: `rm fireemblem8u/fireemblem8.sav`.
- Build interpreter = brew python@3.12 (numpy/pillow/pyyaml via `setup-toolchain.sh`, which also enables the git hooks). Restore vanilla decomp source: `git -C fireemblem8u checkout <path>`. Never commit the submodule pointer.

## Key Files
- `tools/build_campaign.py` — inject portraits + names + character class/stats/growths/ranks/gender. Chapter/event + map-sprite/battle-anim injection are future.
- `tools/check.py` (`make check`) — drift guard; `tools/hooks/pre-commit` enables it on commit.
- `tools/verify_text.py` (`make verify`) — ROM text decoder.
- `tools/portrait_tool.py`, `tools/ref_to_bust.py` — bust pipeline.
- `campaigns/rime-of-the-frostmaiden/{pcs,npcs}/*.yaml` — unit data; `portraits/*.png` — busts.
- `docs/decisions.md` — settled decisions (Class Mapping, Working Conventions); `fireemblem8u/src/{data_characters,data_classes}.c`, `texts/texts.txt` — injection targets (build artifacts).

## Memory
- [[manchego-stars-text-terminator-parity]] · [[feedback_anti_drift_conventions]] · [[feedback_fe_name_truncation]] · [[feedback_custom_art_lever]] · [[project_manchego_stars_portrait_pipeline]] · [[feedback_show_before_committing_art]]

## Standing Rules
Custom art for the 10 named cast; enemies vanilla. Stock FE8 classes/weapons; combat = pure vanilla FE. `make check` + `make` green at session end. Auto-push to main once approved. Don't commit the fireemblem8u submodule pointer.
