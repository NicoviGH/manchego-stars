# Handoff: Story/pacing pass — MVP objectives now FE8-mirrored & decomp-grounded

**Date:** 2026-05-28
**Session Focus:** Collaborative story/pacing pass. Built the FE8 pacing reference
+ 20-ch skeleton + the six missing MVP chapter YAMLs, then (with Nicolas, chapter
by chapter) reworked the MVP objectives to mirror FE8's actual win conditions.

## How Nicolas wants story/pacing work done (IMPORTANT)

**Collaboratively, chapter by chapter** — lead with what FE8 does in that slot,
then our take, then discuss. Don't go solo-produce docs. (Memory:
`feedback-collaborative-story-planning`.) Also: when a decision changes, **rewrite
docs natively — no band-aid banners / "reverted on DATE" scar tissue** (memory:
`feedback-clean-doc-rewrites`).

## Settled this session (do NOT re-litigate)

- **DM notes are PARTIAL** — they cover Ch 1–7 only *so far*; the campaign played
  past Revel's End. Do NOT invent Ch 8–20 plot from the published book (it diverged,
  e.g. Messie-as-Speaker). (Memory: `manchego-stars-dm-notes`.)
- **FE8 objectives are decomp-verified** (read from `src/events/<ch>-eventinfo.h`
  win-condition macros). FE8 has no "Rout" verb — it's `DefeatAll`. Full table is
  in `docs/fe8-pacing-reference.md §1`.
- **MVP objectives now mirror FE8** (agreed chapter-by-chapter):
  Prologue=DefeatBoss · Ch1 Seize · Ch2 DefeatAll(+escort constraint) · Ch3 Seize ·
  Ch4 DefeatAll · Ch5 DefeatBoss-or-Talk · Ch6 DefeatBoss · Ch7 Survive→scripted loss.
  Applied to all 7 chapter YAMLs **and** PRD §7 objective lines.
- **A tiny Prologue is being added** before Ch1 (2–3 units, DefeatBoss tutorial,
  mirrors FE8 Prologue). Ch1 graduates to the full-party Seize. **Prologue not yet
  designed** — that's the next collaborative step.
- **"20 chapters" is now a SOFT target** (content-driven, 18–22 OK). Add chapters by
  *splitting dense beats* (likely Xardorok's fortress + Ythryn), not padding. (Memory
  `manchego-stars-campaign-structure` updated.)

## Accomplished (NOT yet committed when this was written — committing now)

- **NEW `docs/fe8-pacing-reference.md`** — FE8 cadence + reward schedule + promotion-item
  →class mappings. Decomp-grounded: item names (`texts/texts.txt`), promotion classes
  (`data_itemuse.c`), **per-chapter objectives (`<ch>-eventinfo.h`)**.
- **NEW `docs/chapter-outline.md`** — 20-ch skeleton. Act I (Ch1–7) sourced; Act II
  (Ch8–20) explicitly a 🧩 structural placeholder pending DM notes. Promotion seam at Ch7→8.
- **NEW `chapters/ch02`–`ch07` YAMLs** — vanilla-FE style, FE8-mirrored objectives,
  cutscene/recruitment/reward beats. All 7 chapter YAMLs validate clean.
- **ch01 retrofitted to vanilla FE** — removed d20_fields/AC/weapon_dice; goblins now
  wield axes so the weapon-triangle teaching is FE-native (no band-aid banner).
- **Signature moments**: Marty filled (Ch5 Messie Talk, sourced); Meesmickle/Rootis/
  Sclorbo flagged "NICOLAS TO RECALL" with hooks. RBG+Wolfram anchored at Ch3.

## Blockers / open

- **Ch 8–20 plot blocked on the rest of the DM notes** (the #1 unblock).
- **Open design Qs** (`docs/chapter-outline.md`): main-lord PC? (Braulo is the pick) ·
  finale tone (Ch20) · Act II chapter budget · post-MVP Tower-of-Valni equivalent.
- **Leftover band-aid language** still exists across the ~21-file combat sweep from the
  prior session (banners/notes). Offered a dedicated cleanup pass — not yet done.
- Build toolchain still NOT installed (devkitARM/agbcc/ColorzCore/libpng).

## Next Steps (priority order)

1. **Design the new Prologue collaboratively** (which 2–3 PCs, the boss, the map),
   then revisit Ch1/Ch2 framing now that the Prologue carries the basics tutorial.
2. Continue the chapter-by-chapter walkthrough (Ch2 onward).
3. Get + integrate the rest of the DM notes → replace Act II placeholders → author ch08+.
4. (Optional) dedicated cleanup pass on the leftover combat-sweep band-aid language.
5. Later: map remaining `fe_mechanic`-less abilities; scaffold `tools/build-campaign.ts`;
   re-eval `party-balance.md`; finalize `magic-items.md`; decide build deps → Phase 1.

## Key Files

- [docs/fe8-pacing-reference.md](docs/fe8-pacing-reference.md) — cadence + reward + decomp objective table.
- [docs/chapter-outline.md](docs/chapter-outline.md) — 20-ch skeleton (Act II = placeholder).
- [campaigns/rime-of-the-frostmaiden/chapters/](campaigns/rime-of-the-frostmaiden/chapters/) — ch01–ch07.
- [docs/PRD.md](docs/PRD.md) §7 — narrative breakdown (objective lines now FE8-mirrored).
- Source PDFs: `…/References/DungeonMasterNotesIcewindDale.pdf` (**partial**, Ch1–7),
  `…/References/icewind-dale-rime-of-the-frostmaidenpdf_compress.pdf` (book, reference only).
- FE8 objectives: `fireemblem8u/src/events/<ch>-eventinfo.h`.
- Validate campaign YAML: `ruby -ryaml -e 'YAML.load_file("<path>")'`
