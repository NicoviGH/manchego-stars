# Handoff: Full doc-consolidation DONE (steps 1–7, incl. class/rules audit); NEXT = the MVP level-cap decision (levels 1-5 vs 1-7) + its doc/YAML sweep

**Date:** 2026-05-31
**Session focus:** Executed the whole doc-consolidation pass (chapters AND class/rules docs) to stop the doc-sync churn. YAML is now the single source of truth; two generators produce the indexes; durable "why" lives in lean hand docs. All committed + pushed to main (`95441b3`). Nicolas signed off on the class-doc consolidation ("do whatever is best practice for rom hacking"). **The one remaining open item is the MVP level-cap question — Nicolas said "I don't understand what broke," so it still needs a plain-language decision from him before the level-range sweep can run.**

## Standing rules (how Nicolas wants this work done)

- **Stock vanilla FE8 classes only** (verbatim decomp data). Element = flavor, never a mechanic.
- **Ground FE claims in `fireemblem8u/`**; **ground STORY in the two PDFs** (DM notes Ch1–7 only + the published book, image-only scan, PDF page = printed+1).
- **Clean native doc rewrites** (no STALE/reverted banners). **Auto-push to main.** **Collaborative, chapter-by-chapter** story work. **Balance: defer to FE, lean generous.**
- **Doc source-of-truth model (NEW, now settled in `decisions.md`):** (1) per-chapter facts live ONLY in the chapter YAML; (2) `docs/CHAPTERS.md` is GENERATED from it — never hand-edit; (3) hand docs hold only durable rationale + forward planning. **Don't re-introduce chapter/roster tables into hand docs — point to the YAML / generated index.**

## Accomplished this session (committed + pushed — `b8198c9`)

- **Wrote `tools/gen-chapter-index.rb`** (ruby, stdlib) → generates **`docs/CHAPTERS.md`** (overview table: #, title, cadence, objective, recruits, unlocks). Regenerate with `ruby tools/gen-chapter-index.rb`. Added a `cadence:` token→emoji map; added the missing `cadence:` to ch01.
- **Retired `docs/chapter-outline.md`:** MVP table → generated `CHAPTERS.md`; the post-MVP **Act II–V scaffold + open questions → new `docs/roadmap.md`** (renumbered +1 for the Ch4 split — its old "promotions Ch9-11" now reads Ch10-12, which reconciles with the campaign-structure memory); the **promotion seam + cadence taxonomy + the 3-tier doc model → `decisions.md`**.
- **Trimmed `PRD.md §7`** (stale 7-chapter breakdown) → a pointer to `CHAPTERS.md`/the YAML.
- **Trimmed `fe8-pacing-reference.md`** to FE8-only facts (dropped the OUR-per-chapter mapping rows + §5).
- **Fixed cross-refs from the Ch4 split:** `ch03` now unlocks `ch04-the-white-moose` (was the stale `ch04-the-elven-tomb`). Redirected all YAML header/cadence/seam comments off the retired outline (→ `CHAPTERS.md` / `decisions.md` / `roadmap.md`).
- **`decisions.md`:** recount **MVP scope 7→8 chapters** (Prologue–Ch 8); added Documentation Model, cadence taxonomy, promotion-seam (Ch 8→9) decisions.
- All 9 chapter YAMLs re-validated (`ruby -ryaml`). Generator runs clean.
- **Memory:** `project_manchego_stars_campaign_structure` already carried MVP=Ch1-8 (the step-7 bump was already in place) — no change needed.

## ⚠️ Conflict surfaced this session (needs Nicolas) — MVP feature scope: levels 1-5 vs 1-7

The campaign-structure memory **contradicts itself**: its frontmatter + the MEMORY.md index say **"MVP feature scope = 5e levels 1-5 only,"** but the memory BODY (and `class-progression-tables.md`, `pc-spell-lists.md`, `party-balance.md`, `PRD §goals`) all say **"MVP = Ch 1-7 = 5e levels 1-7."** These can't both be right, and the Ch4 split (MVP is now Ch 1-**8**) means the old 1:1 "Ch N = 5e level N" curve also needs a re-look (the memory body line 12 already flags this). **Do not silently resolve — confirm the intended MVP level ceiling with Nicolas**, then sweep the affected docs/YAML in one pass. This is upstream of the class/rules audit below.

## Step 6 — class/rules-doc audit: DONE (`95441b3`)

Nicolas delegated ("do whatever is best practice for rom hacking"), so the class-doc
consolidation was executed (same single-source pattern as the chapters):
- **Added `tools/gen-class-index.rb` → `docs/CLASSES.md`** (PC+NPC roster from the unit YAMLs).
- **Deleted `docs/class-mapping.md`** (rationale already in `decisions.md`; table now generated). Redirected all PC-YAML headers + doc refs to `CLASSES.md`/`decisions.md`.
- **PRD §6.7** class table → pointer; **PRD §6.8** rewritten to decision B (deplete + gold restock; cantrips high-count, not infinite) — it had contradicted §6.9.
- Fixed split cross-refs: braulo signature ch07→ch08, marty signature ch05→ch06, marty "stock Monk"→"stock Shaman"; party-balance magic-triangle (Marty is Dark, not Light).
- **Kept** (correctly scoped, not duplicates): `rules-mapping.md` (generic engine 5e→FE spec), `combat-formulas.md` (concise combat quick-ref), `class-progression-tables.md` (D&D-source-of-record for when 5e features unlock), `party-balance.md` (analysis snapshot). These still need the level-range reconciliation below.

## ⚠️ THE ONE OPEN ITEM (needs Nicolas) — MVP level cap: levels 1-5 vs 1-7

The campaign-structure memory **contradicts itself**: its frontmatter + the MEMORY.md index say **"MVP feature scope = 5e levels 1-5 only,"** but the memory BODY (and `class-progression-tables.md`, `pc-spell-lists.md`, `party-balance.md`, `PRD §goals`) all say **"MVP = 5e levels 1-7."** Plain version: this number sets how strong the party gets by the MVP finale — which spells/subclass features are in vs. cut. "1-5" = simpler, no 3rd/4th-level spells; "1-7" = richer, up to 4th-level. They can't both be the live spec. The Ch4 split (MVP is now Ch 1-**8**) also broke the old 1:1 "Ch N = 5e level N" curve, so the curve needs a re-look regardless. **Do NOT silently resolve.** Once Nicolas picks the ceiling, sweep in one pass: the memory frontmatter+index, `class-progression-tables.md`, `pc-spell-lists.md`, `party-balance.md`, `magic-items.md`, `PRD §goals/milestones/issues` (still say "7 chapters" / "Chapter 7" finale), and `campaign-brief.md` (its own stale Ch1-7 breakdown).

## Other blockers / open (unchanged)

- **Signature moments TBD** for Meesmickle, Rootis, Sclorbo (Marty done: primary=ch06 Messie Talk, secondary=ch04 wolf parley).
- **pepperjack/brie `fe_stats.class` = null** (FE-legal class TBD post-MVP).
- **Ch 9–20 plot** blocked on the rest of the DM notes (cover Ch1–7 only).
- **Build toolchain still NOT installed** (devkitARM/agbcc/ColorzCore/libpng); `tools/build-campaign.ts` also unbuilt.

## Key files

- Generators: `tools/gen-chapter-index.rb` → `docs/CHAPTERS.md`; `tools/gen-class-index.rb` → `docs/CLASSES.md`. Re-run after editing any chapter/unit YAML.
- Chapters: `campaigns/rime-of-the-frostmaiden/chapters/ch00…ch08-*.yaml` (source of truth).
- Units: `campaigns/rime-of-the-frostmaiden/pcs/*.yaml`, `npcs/*.yaml` (source of truth for class/promotion).
- Durable docs: `docs/decisions.md` (settled why — incl. the doc model, cadence taxonomy, promotion seam, class mapping), `docs/roadmap.md` (post-MVP scaffold), `docs/fe8-pacing-reference.md` (FE8-only).
- Level-sweep targets (after the cap decision): `docs/{class-progression-tables.md, pc-spell-lists.md, party-balance.md, magic-items.md, campaign-brief.md, PRD.md}` + the campaign-structure memory.
- Validate YAML: `ruby -ryaml -e 'YAML.load_file("<path>")'`.
