# Handoff: Art direction LOCKED to full-custom + all 8 cast/recruit portrait briefs authored. NEXT = start pixeling, Braulo first (gbagfx round-trip with a CUSTOM 96×80 indexed portrait). Toolchain is green & reproducible on macOS (byte-identical vanilla ROM).

**Date:** 2026-06-01
**Session focus:** Ran a chapter-style portrait *walkthrough* — looked at every reference artwork one-by-one with Nicolas, made the recolor-vs-custom call, and recorded a custom design brief for each of the 7 PCs + the two recruit cannon-golems. All committed + pushed to main (HEAD `672ec0b`).

## Accomplished this session

- **Art direction decided: FULL CUSTOM.** Every cast/recruit sprite part — portrait, map sprite, AND battle animation — is hand-drawn indexed-palette art, drawn *faithfully from each character's concept reference*. **No recolor baseline, no vanilla-anim reuse.** Rationale: combat is pure vanilla FE8, so the art is the single biggest lever for making the game feel like the campaign. Nicolas: "this is our biggest lever… let's take our time." Generative tools (Nano Banana) stay concept-ref only, never final assets.
  - Superseded the old "recolor-first" lean **and** the old "Phase C map sprites mostly free / Phase D reuse vanilla anims" plan.
- **Per-character design briefs authored** into each unit's YAML `art:` block (`campaigns/rime-of-the-frostmaiden/{pcs,npcs}/*.yaml`) — must-keep visual tells, face/animation approach, expression, rough 16-color palette plan. Decisions:
  - **Braulo** (Pirate→Berserker): faithful hermit-crab — red claws, tan carapace shoulders, conch shell, wicker basket-hat; face *per concept* (not humanized); expression = **berserker fury**.
  - **Prof. R.B. Geenius** (Archer): green-ratfolk manic grin, purple top-hat, yellow coat collar; **face-forward, NO gun in the bust** (pistols/magitech ride map+battle sprites).
  - **Sclorbo** (Priest): faceless Chwinga rune-mask STAYS; animate via **rune-pulse + aura** (no eyes/mouth); fur ruff, cyan staff.
  - **Marty** (Shaman): merry grey mushroom, red spotted cap, yellow eyes; **subtle elegant spore-hint** motes for the dark magic.
  - **Meesmickle** (Shaman): vampire-tabaxi **regal diva**, red cape + diamond bling; **clean neutral field** (drop the cosmic bg). Must read distinct from Marty (the other Shaman).
  - **Rootis** (Mage/Ice): pure jolly snowman, coal eyes + carrot nose; **armless, no aura** — cold magic on the battle anim.
  - **Wolfram** (Knight/Armor): mineral-scaled face + leather straps, no weapon in frame; **serious/preoccupied** (thinking about his ores), younger than the weathering suggests.
  - **Pepperjack & Brie** (recruits, FE class TBD post-MVP — but **art built now with the batch**): cannon-golems, **3/4 profile** as drawn, mirror palettes (Pepperjack grey+red+chili-stache / Brie pink+cyan+glam-eye).
- **Lore fix:** clarified RBG built **Brie *for* Pepperjack** (Adam/Eve framing) — they're a **couple, not twins/siblings** (`lore/pepperjack-and-brie.md`).
- **Docs rewritten natively** to the custom direction: `docs/decisions.md` (Art entry) + `docs/PRD.md §8`. Also fixed a stale PRD line that called Braulo a "Tortle" (he's a hermit crab).
- Commits: `874bf0d` (briefs + lore), `672ec0b` (doc rewrite).

## Tried but didn't work (lessons for next time)

- (No dead ends this session — it was a design/decision walkthrough.) Note from prior session still holds: the 3 macOS build gaps (Linux shebangs, py3.9 match/case, missing `<cstdlib>`) are permanently shimmed in the root `Makefile` Darwin block — won't recur.

## Current state

- **Build:** green + reproducible on macOS. `make` → `fireemblem8u/fireemblem8.gba`, `make verify` → `OK` (byte-identical vanilla FE8). Boots vanilla in mGBA; no campaign data injected yet (that's the unbuilt `build-campaign.ts` pipeline, issues #13–#15).
- **Art:** all 8 cast/recruit **design briefs done**, but **zero pixels drawn yet**. The gbagfx round-trip has NOT been proven.
- **Story:** all 9 MVP chapters (ch00–ch08) authored in YAML + walked through. Ch9–20 plot still blocked on the rest of the DM notes.

## Blockers / open

- **gbagfx round-trip not yet proven** — need to dump a vanilla 96×80 portrait → reinsert → see it in mGBA before drawing final custom art (so we work against real palette/size constraints).
- **Braulo's face reference is missing** — the current full-body ref hides his face under the carapace/basket-hat. Nicolas can supply more reference art; **ask him for a Braulo face/head ref before drawing his portrait.** (Standing offer: he can provide extra art for any character where a single body-shot leaves a gap.)
- **#16 (toolchain) needs manual close** on GitHub — done, but the agent close was blocked by the permission classifier.
- **pepperjack/brie `fe_stats.class = null`** — FE-legal vanilla class TBD post-MVP (art proceeds without it).
- **Sclorbo signature moment** still TBD (Nicolas to recall). Rootis pairs with Sclorbo (ice support / Targos snow-night).
- **Ch 9–20 plot** blocked on the rest of the DM notes.
- **Lingering lean candidates** (low priority): `docs/pc-spell-lists.md` / `docs/magic-items.md` → consume into YAML then delete.

## Next steps (priority order) — PIXEL ART (full custom)

Golden rules: **indexed-palette only** (16 colors/slot, 8×8 tiles); draw faithfully from the concept ref; Nano Banana = concept-ref only, never final. Draw in **Aseprite** (indexed mode); validate legality in **FEBuilder**; authoritative insertion is PNG → `gbagfx` → decomp.

1. **Prove the gbagfx round-trip (do FIRST, ~throwaway).** Dump one vanilla FE8 portrait → tweak pixels → reinsert → view in mGBA. Confirms the 96×80 / 16-color ceiling before we commit custom art. Scripts: `fireemblem8u/scripts/dump_portrait.py`, `gbagfx` (built at `fireemblem8u/tools/gbagfx`).
2. **Braulo portrait first** (he's the end-to-end test unit, issue #15). **Get a face reference from Nicolas first.** Then draw the custom 96×80 indexed portrait per the brief in `pcs/braulo.yaml` (`art:` block).
3. **Remaining 6 PC portraits**, ordered by story appearance, each per its YAML `art:` brief. Then Pepperjack & Brie (build-now).
4. **Map sprites** (16×16) — custom per cast member.
5. **Battle animations** (hardest) — custom; likely post-MVP `stretch`.

**Process note:** per-character art briefs now live in the unit YAML `art:` blocks — read those before drawing each character. **Roadmap issues** for this (Phase A round-trip + per-PC portrait issues) were never created; Nicolas to decide whether to file them or keep the roadmap in `docs/` — do not create GitHub issues unprompted (external-write classifier will likely block).

**Also flagged by Nicolas for "later":** an **architecture diagram** of the ROM hack (for his own learning). Not started; bring it up when he's ready.

## Key files

- `campaigns/rime-of-the-frostmaiden/pcs/*.yaml` + `npcs/{pepperjack,brie}.yaml` — each has an `art:` block with the per-character custom design brief (the spec for drawing them).
- `data/portraits/*.jpeg|jpg` — downloaded D&D Beyond concept refs; `data/pc-sheets/portraits.json` — source URLs.
- `fireemblem8u/scripts/dump_portrait.py`, `fireemblem8u/tools/gbagfx` — the portrait asset pipeline (Phase A round-trip).
- `Makefile` (root) — macOS build shims in the `ifeq ($(shell uname),Darwin)` block; `make` / `make verify` / `make clean`.
- `fireemblem8u/fireemblem8.gba` — built ROM (gitignored). View: `open -a /Applications/mGBA.app <path>`.
- `docs/decisions.md` (Art Direction entry) + `docs/PRD.md §8` — the full-custom art direction.

## Standing rules (how Nicolas wants this work done)

- **Art = full custom** for cast/recruits (portrait + map sprite + battle anim), drawn faithfully from concept refs; indexed-palette only; Nano Banana concept-ref only. Nicolas can supply more reference art on request.
- **Stock vanilla FE8 classes/weapons only**; **element = flavor, NEVER a mechanic** (incl. effectiveness — keyed to enemy CLASS). Combat RULES are vanilla FE; the d20 is cosmetic only.
- **Ground FE claims in `fireemblem8u/`**; **ground STORY in the two PDFs** (DM notes Ch1–7 only + the published book). Read them directly when planning story.
- **Clean native doc rewrites** (no STALE/reverted banners). **Auto-push to main.** **Collaborative, one-item-at-a-time** story/art walkthroughs. **Balance: defer to FE, lean generous.**
- **Doc source-of-truth:** per-chapter/unit facts live ONLY in YAML; `docs/CHAPTERS.md` + `CLASSES.md` are GENERATED (`ruby tools/gen-chapter-index.rb` + `gen-class-index.rb`, never hand-edit). **Lean repo**; backlog = **GitHub issues** (milestones M0–M4).
- **`make` must be green at the end of every session. Never commit a broken build.**
