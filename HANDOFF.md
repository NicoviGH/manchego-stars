# Handoff: Ch3 polished + Ch4 split into two chapters (now 8 MVP chapters); NEXT = doc-consolidation pass

**Date:** 2026-05-31
**Session focus:** Finished the Ch3 walkthrough, then split the over-stuffed Ch4 into two chapters using the actual sources of truth (DM notes + the published Frostmaiden book). Decided a doc-consolidation strategy to stop story changes from rippling across many files. **The doc pass is decided but NOT yet started — that's the next task (todos below).**

## Standing rules (how Nicolas wants this work done)

- **Stock vanilla FE8 classes only** (verbatim decomp data). Element = flavor, never a mechanic. Individuality via flavor/art/palette, not stats.
- **Ground FE claims in `fireemblem8u/`** (see memory `feedback_use_decomp`). **Ground STORY in the two source-of-truth PDFs** (NEW memory `feedback_story_sources_of_truth`): the **DM notes** (`…/References/DungeonMasterNotesIcewindDale.pdf`, the party's actual playthrough, Ch1–7 only) AND the **published book** (`…/References/icewind-dale-rime-of-the-frostmaidenpdf_compress.pdf`, canon detail). The book is an **image-only scan** (pdftotext returns nothing — read with Read tool's PDF vision; **PDF page = printed page + 1**; Contents on printed p.3).
- **Clean native doc rewrites** (no STALE/reverted banners). **Auto-push to main.** **Collaborative, chapter-by-chapter** story work (FE8 parallel + our version). **Level design/balance: defer to FE convention, lean generous** for the friend-group audience.
- **Objective rotation (NEW, agreed this session):** don't bind each chapter's objective TYPE to FE8's exact slot order; just ensure the full SET of FE8 objective types appears across our campaign, rotated for pacing.

## Accomplished this session (all committed + pushed to main)

- **Ch3 (The Termalaine Mine) finalized.** Locked verticality-only pacing, seize-only objective (seize the deep workings — the descent IS the lesson), ungated **Energy Ring** (+2 Pow) instead of risk-gated, 2 Grells as the chokepoint threat. Added a **Pinky shaft-scout cutscene** (RBG sends his homunculus "son" to scout; the Grells are revealed via the cutscene; seeds the finale Wish). Committed + pushed.
- **Split the fused Ch4 → two chapters; renumbered the MVP to 8 chapters.** Nicolas correctly flagged the old Ch4 was doing two DM-note beats at once. The book (pp.78–83) revealed the **white moose, the frost druid (Ravisin), and Messie are ONE villain thread — Ravisin awakened them all.**
  - **NEW `ch04-the-white-moose.yaml`** — Lonelywood **fog-of-war forest hunt** (the FE8 Ch4 "Ancient Horrors" DefeatAll/monster-debut half). Wolf-pack parley = Marty's SECONDARY signature beat; **Lupin** (talking wolf leader) joins the **sled team as a non-combat NPC** (not playable — canon: he never fights). The white moose is a scripted neutral that flees to the tomb.
  - **`ch05-the-elven-tomb.yaml`** (was the fused ch04, now boss-only) — **Ravisin** the frost druid as our first clean **DefeatBoss**, wielding **Flux** (the Druid class's native dark tome, flavored cold) — this **fixed an illegal weapon** (the old `elwind-tome` doesn't exist in FE8, and a Druid can't use Anima-wind anyway). **3-offering brazier puzzle** (FE8-native: gather twig/pinecone/feather on the map → kindle the gazebo brazier → sarcophagus opens), which frees **Sahnar** the moon-elf mummy (playable recruit). **Basil** the goodberry shrub is folded into the **caravan shop as a Goodberry/Vulnerary NPC** (Nicolas's idea — not a fighting shrub). Drops the locked **crest of cold iron**.
  - **Renumbered** Maer→`ch06`, Bremen→`ch07`, Eastway→`ch08`; fixed all internal cross-refs, `unlocks_chapter` chains, the promotion seam (now **Ch8→9**), and the deployment NPC lists (Basil removed from deployables; Baxby/Lupin/Basil = caravan NPCs).
  - All 9 chapter YAMLs validate (`ruby -ryaml`).
- **Memory updated:** added `feedback_story_sources_of_truth`. (Still TODO: bump `project_manchego_stars_campaign_structure` from "MVP = Ch1-7" to "Ch1-8".)

## Current state

- Chapters Ch0–Ch8 exist as lean, valid, stock-vanilla YAML. The split is done and pushed (HEAD).
- **Docs are intentionally OUT OF SYNC with the renumber** — `chapter-outline.md`, `PRD.md §7`, and `fe8-pacing-reference.md` still describe the old 7-chapter numbering. This is deliberate: rather than hand-resync them, we decided to fix the root cause (see next steps).

## Key decision this session: stop the doc-sync churn

Nicolas (a PM, new to game design) noticed every story change forces edits across many docs. Investigation: `docs/` is **15 files / ~3,700 lines**; the entire decomp documents itself in **~458 lines** ("the data is the doc"). Per-chapter facts are duplicated across the YAML + PRD §7 + chapter-outline + pacing-ref. Also **`tools/build-campaign.ts` does not exist yet**, so the YAML is currently just another hand-maintained layer.

**Agreed model:** (1) **YAML is the single source of truth** for per-chapter facts; (2) **generate** the chapter index from YAML; (3) keep only durable "why" docs (decisions.md, a trimmed PRD = vision/scope/roadmap, pacing-ref = FE8-only); (4) audit the overlapping class/rules docs. Toolchain available: **node v22, ruby 2.6, python 3.9** (no pyyaml; no package.json). Recommend the generator be a standalone **Ruby** script (Ruby's YAML is confirmed working).

## Blockers / open

- **Signature moments TBD** for Marty (primary=ch06 Messie Talk; secondary=ch04 wolf parley now set), Meesmickle, Rootis, Sclorbo — Nicolas to recall; not in DM notes.
- **pepperjack/brie `fe_stats.class` = null** (FE-legal class TBD post-MVP).
- **Ch 9–20 plot** blocked on the rest of the DM notes (cover Ch1–7 only).
- **Build toolchain still NOT installed** (devkitARM/agbcc/ColorzCore/libpng) — gates any ROM build/test. `tools/build-campaign.ts` also unbuilt.
- **Pinky omission:** older chapter deployment notes never listed Pinky (deployable flier from Ch1); fixed in the new ch04/05/06/07/08 notes, but ch00–ch02 may still omit her.

## Next steps (priority order) — THE DOC-CONSOLIDATION PASS (decided, not started)

1. **Write `tools/gen-chapter-index.rb`** — reads `campaigns/rime-of-the-frostmaiden/chapters/ch*.yaml`, emits `docs/CHAPTERS.md` (the overview table: #, title, cadence, objective, recruits, unlocks).
2. **Generate `docs/CHAPTERS.md`; retire `chapter-outline.md`** — migrate its durable design notes (promotion seam, Act II foreshadow, emoji/cadence legend) into `decisions.md`, then delete the hand-maintained table.
3. **Trim `PRD.md`** — delete §7 chapter breakdown, replace with a pointer to `CHAPTERS.md` / the YAML.
4. **Trim `fe8-pacing-reference.md`** to FE8-only (remove OUR per-chapter mapping rows; keep the FE8 facts).
5. **Record the doc source-of-truth model in `decisions.md`** (the 3-tier model above).
6. **Audit the class/rules docs** (`class-mapping`, `class-progression-tables`, `rules-mapping`, `combat-formulas`, `party-balance`, + PRD §6.7 — which is ALSO flagged stale from last session) → come back with a consolidation proposal; **no deletions without Nicolas's sign-off**.
7. **Update memory** (`project_manchego_stars_campaign_structure` → MVP = Ch1-8) and **commit + push**.

(Then, eventually: resume the collaborative walkthrough at **Ch6 — The Maer Monster** onward, now with the leaner doc model in place.)

## Key files

- Chapters: `campaigns/rime-of-the-frostmaiden/chapters/ch00…ch08-*.yaml` (Ch0–8; ch04/ch05 are the new split).
- Recruit/NPC units: `campaigns/rime-of-the-frostmaiden/npcs/{pepperjack,brie,pinky}.yaml`; **Lupin/Sahnar/Basil still need stub YAMLs** if we want them as data (Lupin/Basil = NPC, Sahnar = recruit).
- Flavor: `campaigns/rime-of-the-frostmaiden/lore/*.md`.
- Docs to consolidate: `docs/{PRD.md(§6.7,§7),chapter-outline.md,fe8-pacing-reference.md,decisions.md,class-mapping.md,class-progression-tables.md,rules-mapping.md,combat-formulas.md,party-balance.md}`.
- Sources of truth (story): the two PDFs in `…/Fire Emblem Game/References/` (DM notes + Frostmaiden book).
- FE8 reference: `fireemblem8u/src/data_classes.c` (e.g. `[CLASS_DRUID]` = Anima D / Dark C / Staff E), `classchg-data.c`, `data_items.c`, `texts/texts.txt`, `include/constants/terrains.h` (DOOR/WALL_DAMAGED/SNAG — FE8's only "puzzle" vocabulary).
- Validate YAML: `ruby -ryaml -e 'YAML.load_file("<path>")'`.
- New generator (to write): `tools/gen-chapter-index.rb`.
