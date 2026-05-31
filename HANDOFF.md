# Handoff: Lean-repo cleanup DONE — 8 drift-prone docs deleted, PRD slimmed, backlog moved to GitHub. NEXT = resume the Ch6 walkthrough (or start building from the GitHub backlog)

**Date:** 2026-05-31
**Session focus:** Big lean-repo + doc-consolidation pass. YAML is the single source of truth; two generators produce the indexes; the backlog now lives in **GitHub issues** (the repo reads like a mature ROM-hack repo). All committed + pushed to main (`ace9cd0`).

**Working principle locked in (memory `feedback_lean_repo_structure`):** match the decomp / experienced-hacker repo structure — **the data IS the doc** — and **delete drift-prone planning-prose** rather than re-patching it. No staleness banners (`feedback_clean_doc_rewrites`).

**Deleted this session (8 docs, all restorable from git):** `chapter-outline.md`, `class-mapping.md` (→ generated CHAPTERS.md/CLASSES.md + decisions.md), `party-balance.md` + `class-progression-tables.md` (pre-purge snapshots / derivable from `data/pc-sheets/*.json`), `combat-formulas.md` (engine self-documents; in decisions.md + rules-mapping), `campaign-brief.md` + `research.md` (pre-PRD scaffolding), `session-log.md` (git history covers it).

**Also resolved:** the old "MVP = 5e levels 1-5 vs 1-7" question — it was the wrong frame. We ship FE classes/levels/promotions; **progression is FE-native (MVP unpromoted, promotions post-MVP ~Ch 10-12); 5e levels/features are flavor only.** Do NOT reintroduce a "5e-level scope." PRD slimmed 847→594 lines (combat/triangle/§7/§6.7 → pointers; §15/§16 backlog → GitHub). CLAUDE.md source-of-truth block rewritten as the data-is-the-doc table.

**Backlog is now GitHub issues** (37 open: 6 scaffold + 31 created this session across milestones M0–M4). Track work there, not in markdown.

## Standing rules (how Nicolas wants this work done)

- **Stock vanilla FE8 classes only** (verbatim decomp data). Element = flavor, never a mechanic.
- **Ground FE claims in `fireemblem8u/`**; **ground STORY in the two PDFs** (DM notes Ch1–7 only + the published book, image-only scan, PDF page = printed+1).
- **Clean native doc rewrites** (no STALE/reverted banners). **Auto-push to main.** **Collaborative, chapter-by-chapter** story work. **Balance: defer to FE, lean generous.**
- **Doc source-of-truth model (settled in `decisions.md`):** (1) per-chapter/unit facts live ONLY in the YAML; (2) `docs/CHAPTERS.md` + `CLASSES.md` are GENERATED — never hand-edit; (3) hand docs hold only durable rationale + forward planning. **Don't re-introduce chapter/roster tables into hand docs.**
- **Lean repo** (memory `feedback_lean_repo_structure`): match the decomp / experienced-hacker structure; the data IS the doc; **delete drift-prone planning-prose rather than re-patch it.** Work backlog lives in **GitHub issues**, not markdown.

## Current repo / doc state (post-cleanup)

- **`docs/` now:** `decisions.md` (settled why — doc model, cadence taxonomy, promotion seam, class mapping, combat, economy), `CHAPTERS.md` + `CLASSES.md` (GENERATED — never hand-edit), `roadmap.md` (post-MVP Act II–V scaffold), `fe8-pacing-reference.md` (FE8-only), `rules-mapping.md` (generic 5e→FE engine spec), `PRD.md` (vision/architecture/roadmap, 594 lines), `pc-spell-lists.md` + `magic-items.md` (D&D-source flavor worksheets — consume-then-prune as caster tomes / reward items get authored during the walkthrough), `frostmaiden-resources.md` (external map refs).
- **Generators:** `ruby tools/gen-chapter-index.rb` → CHAPTERS.md; `ruby tools/gen-class-index.rb` → CLASSES.md. Re-run after editing any chapter/unit YAML. Validate YAML: `ruby -ryaml -e 'YAML.load_file("<path>")'`.
- **Source of truth:** chapter facts = `campaigns/.../chapters/ch00…ch08-*.yaml`; unit class/promotion = `campaigns/.../{pcs,npcs}/*.yaml`. Backlog = **GitHub issues** (M0–M4).

## NEXT TASK

**Resume the collaborative chapter walkthrough at Ch 6 — The Maer Monster** (memory `feedback_collaborative_story_planning`: interactive, FE8-parallel + our version, not solo doc dumps), now with the lean doc model in place. Alternatively, start building from the GitHub backlog — the first real blocker is **"Install the build toolchain"** (devkitARM/agbcc/ColorzCore/libpng), which gates every ROM build/test.

## Blockers / open

- **Signature moments TBD** for Meesmickle, Rootis, Sclorbo (Marty done: primary=ch06 Messie Talk, secondary=ch04 wolf parley).
- **pepperjack/brie `fe_stats.class` = null** (FE-legal class TBD post-MVP).
- **Ch 9–20 plot** blocked on the rest of the DM notes (cover Ch1–7 of the playthrough only).
- **Build toolchain not installed** + `tools/build-campaign.ts`/`build-events.ts` unbuilt (GitHub issues exist for both).
- **Lingering lean candidates** (low priority): `pc-spell-lists.md` / `magic-items.md` should be consumed into YAML then deleted; `PRD.md` could slim further (§8 art / §9 audio partly overlap decisions.md §Art & Audio) if it stops earning its keep.
