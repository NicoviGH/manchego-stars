# Handoff: Doc-consolidation pass DONE (steps 1–5,7); NEXT = class/rules-doc audit sign-off (step 6) + the discovered levels 1-5 vs 1-7 conflict

**Date:** 2026-05-31
**Session focus:** Executed the decided doc-consolidation pass to stop the doc-sync churn. YAML is now the single source of truth for per-chapter facts; the chapter index is generated; durable "why" lives in lean hand docs. All committed + pushed to main (`b8198c9`). **The remaining task is step 6 — the class/rules-doc audit — which is a PROPOSAL awaiting Nicolas's sign-off (no deletions without it), plus a real contradiction I surfaced (MVP feature scope = levels 1-5 vs 1-7).**

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

## NEXT TASK — Step 6: class/rules-doc audit (PROPOSAL — needs sign-off, no deletions without it)

**Finding:** `class-mapping.md` and `PRD §6.7/§6.8` are the *same* duplicate-stale-table antipattern the chapter pass just fixed. The PC/NPC **YAMLs already are the source of truth** for FE class + promotion (`campaigns/.../pcs/*.yaml`, `npcs/*.yaml` — `fe_base`, `fe_stats.class`, `promotion.branch`, all vanilla, dated 2026-05-29/30), and `decisions.md §Class Mapping & Promotions` already holds the current rationale. The hand tables duplicate it and are badly stale:

- **`class-mapping.md` "Notes on Specific Mappings"** describes only SUPERSEDED designs: Marty=Monk, Sclorbo=Lore Bishop/Dancer, Rootis=Manakete Dragon-Wings transform, Pepperjack/Brie="RBG's cannons," "Wolfram & RBG have spell access." All reverted (see `decisions.md`).
- **`PRD §6.7`** table repeats the same stale customs (custom Summoner/Artillerist, "Dark Sage" (non-existent), Dragon Wings transform, Dancer/Lore Bishop, Wolfram Mystic Arcanums/Shield, Pepperjack as a deployable AC-18 100-HP cannon, Basil=Ch4 Cleric, Mummy=Sage). NPC join-chapters are pre-split.
- **`PRD §6.8`** ("all spell tomes refill to max each chapter — long rest") **directly contradicts** `PRD §6.9` and `decisions.md` decision B (deplete + gold restock, NO free refill).

**Proposed fix (mirrors the chapter consolidation) — for sign-off:**
1. **Write `tools/gen-class-index.rb`** → generate **`docs/CLASSES.md`** (PC + NPC roster: name, FE base, promotion branch+default, primary stat, D&D source) from the unit YAMLs.
2. **Retire the hand tables:** delete `class-mapping.md` (rationale already in `decisions.md`; table → generated `CLASSES.md`); replace `PRD §6.7` with a pointer (like §7); **delete the contradictory `PRD §6.8` table** (keep §6.9 + `decisions.md` decision B as canonical) or rewrite §6.8 to match decision B.
3. **`class-progression-tables.md`: KEEP** — it's the D&D-source-of-record for *when 5e features unlock* (no FE duplicate). But reconcile it to the levels-1-5-vs-1-7 answer + the Ch1-8 renumber.
4. **`rules-mapping.md`: KEEP** (generic engine 5e→FE spec) but spot-fix any advantage/saves residue; it already headers "resolution is vanilla FE."
5. **`combat-formulas.md`: KEEP as the concise combat quick-ref** OR fold into `decisions.md §Combat` + `rules-mapping §A` (they overlap). Recommend keep — it's short and useful.
6. **`party-balance.md`: KEEP** (analysis snapshot) but fix stale bits (Wolfram "Breath Weapon," Dragon Wings post-MVP, Basil/Mummy Ch4 joins) and the level-range.
7. Update PC-YAML header comments that point at `class-mapping.md`/`PRD §6.7` → point to `CLASSES.md`/`decisions.md`.

**Recommendation:** do (1)+(2) (kills the worst stale duplication), then the level-range sweep (3/6) after Nicolas confirms the ceiling. `campaign-brief.md` also has its own stale Ch1-7 breakdown — fold into the same sweep.

## Other blockers / open (unchanged)

- **Signature moments TBD** for Meesmickle, Rootis, Sclorbo (Marty done: primary=ch06 Messie Talk, secondary=ch04 wolf parley).
- **pepperjack/brie `fe_stats.class` = null** (FE-legal class TBD post-MVP).
- **Ch 9–20 plot** blocked on the rest of the DM notes (cover Ch1–7 only).
- **Build toolchain still NOT installed** (devkitARM/agbcc/ColorzCore/libpng); `tools/build-campaign.ts` also unbuilt.

## Key files

- Generator: `tools/gen-chapter-index.rb` → `docs/CHAPTERS.md`. (To write: `tools/gen-class-index.rb` → `docs/CLASSES.md`.)
- Chapters: `campaigns/rime-of-the-frostmaiden/chapters/ch00…ch08-*.yaml` (source of truth).
- Units: `campaigns/rime-of-the-frostmaiden/pcs/*.yaml`, `npcs/*.yaml` (source of truth for class/promotion).
- Durable docs: `docs/decisions.md` (settled why), `docs/roadmap.md` (post-MVP scaffold), `docs/fe8-pacing-reference.md` (FE8-only).
- Audit targets: `docs/{class-mapping.md, PRD.md §6.7/§6.8, class-progression-tables.md, rules-mapping.md, combat-formulas.md, party-balance.md, campaign-brief.md}`.
- Validate YAML: `ruby -ryaml -e 'YAML.load_file("<path>")'`.
