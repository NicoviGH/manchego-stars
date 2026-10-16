# lore/ — Narrative & Flavor

This folder holds the **story/flavor** layer for the campaign's characters. It is deliberately
kept **separate from mechanics** so the build pipeline never has to parse prose, and so flavor
can be edited freely without touching unit data.

## The split

| Layer | Where | Consumed by | Contains |
|---|---|---|---|
| **Mechanics** | [`../pcs/*.yaml`](../pcs), [`../npcs/*.yaml`](../npcs) | build pipeline | class, stats, growths, inventory, supports — stock vanilla FE8 |
| **Flavor** | `lore/*.md` (this folder) | humans | concept, personality, backstory, ability *fantasies*, relationships |
| **Raw D&D source** | `data/pc-sheets/*.json` | reference | unchanged D&D Beyond export |

## Profile: the one section a reader takes as-is

Each character's file opens with a **`## Profile`**: two short paragraphs of plain prose about who
they are, written to be read by someone who has not seen the rest of the file (no file links, ADR
numbers or drafting notes). The chapter wiki (`tools/gen_wiki.py`) prints it as the character's
Personality section, and its first sentence is their line in the character list. Everything else in
a file is for writers. Keep the Profile true when the character changes.

A **`## Trivia`** list, when a character has one, names the real things they are drawn from
(Marty's planter, RBG's rat, Rootis's snowman); the wiki prints each bullet as Trivia.

A character from *Rime of the Frostmaiden* also gets a **`## Book`** section right after the
Profile: what the book says of them, with the printed page and its own words quoted, and where
ours departs. The wiki prints it as a Trivia line. The book's illustration of them, when it has
one, is cropped into [`book-art/`](book-art) with its page and the book's caption in
`book-art/index.yaml` (credited in `CREDITS.md`). Book art only: the busts made as sprite sources
stay in References.

## Why

Manchego Stars units are **stock vanilla FE8 classes with no per-character abilities** (see
`CLAUDE.md` and `docs/decisions.md`). Individuality comes from flavor text, portrait/sprite art,
and palette — **not** mechanics. There are no skills, procs, timed buffs, special movement, or
element-as-mechanic effects.

The D&D ability "fantasies" each character used to have are preserved in these files as story
beats and dialogue/sprite inspiration. They were migrated from pre-strip commit `e6cc7a6` so the
flavor isn't lost to git history. **None of them drive gameplay** — every lore file says so up top.

## Contents

- [`braulo.md`](braulo.md), [`marty.md`](marty.md), [`meesmickle.md`](meesmickle.md),
  [`pinky.md`](pinky.md), [`prof-rbg.md`](prof-rbg.md), [`rootis.md`](rootis.md),
  [`sclorbo.md`](sclorbo.md), [`wolfram.md`](wolfram.md) — the 8 player characters.
- [`pepperjack-and-brie.md`](pepperjack-and-brie.md) — RBG's two cannon-construct automatons
  (vanilla **map ballistae** from ~Ch10, NOT roster recruits — see `docs/CLASSES.md`; units:
  [`../npcs/pepperjack.yaml`](../npcs/pepperjack.yaml), [`../npcs/brie.yaml`](../npcs/brie.yaml)).
- [`trex.md`](trex.md) — the Ch3 recruit (winged kobold thief), with a **§Voice**
  (unit: [`../npcs/trex.yaml`](../npcs/trex.yaml)).
- [`ravisin.md`](ravisin.md) — ch05 boss (frost druid); [`sahnar.md`](sahnar.md) — ch05
  recruit (moon-elf mummy, the Joshua beat); [`basil.md`](basil.md) — ch05 recruit
  (goodberry-shrub Priest, the Natasha beat). Each has a **§Voice**. **DRAFT (Phase 0,
  2026-07-23)** — §Voice pending Nicolas's red-pen; units:
  [`../npcs/sahnar.yaml`](../npcs/sahnar.yaml), [`../npcs/basil.yaml`](../npcs/basil.yaml).
- [`hlin-trollbane.md`](hlin-trollbane.md), [`scramsax.md`](scramsax.md),
  [`sephek-kaltro.md`](sephek-kaltro.md) — prologue guests/boss, each with a **§Voice**
  (diction rules, calibration lines, banned list) consumed by the `dialogue-pass` skill.
- [`dorbulgruf.md`](dorbulgruf.md) — Speaker of Bremen (ch06 quest-giver, ch07 boss).
- [`messie.md`](messie.md) — the maer monster (ch06 cutscene actor, ch07's new Speaker).
- [`nerra.md`](nerra.md) — elder of the Maer Dualdon merfolk (ch06 boss; she retreats).
- [`izobai.md`](izobai.md) — ch01 goblin boss; [`duvessa-shane.md`](duvessa-shane.md),
  [`vellynne-harpell.md`](vellynne-harpell.md) — recurring named NPCs;
  [`npc-bench.md`](npc-bench.md) — the minor-NPC bench.
- [`frostmaiden-voices.md`](frostmaiden-voices.md) — the campaign voice bible consumed by
  `dialogue-pass`.
- [`narration.md`](narration.md) — the narration register (lore crawl, town tour,
  location cards) + vanilla pacing budgets.

## Regenerating PC lore

The original PC lore files were generated in a one-time migration from the pre-strip YAML
(`git show e6cc7a6:.../pcs/<pc>.yaml` — the `dnd` concept + each ability's
`name`/`flavor`/`fe_mechanic`). The generator script was throwaway and is gone (the Ruby
toolchain was retired 2026-06-09 — see `docs/decisions.md` §Engine & Tech Stack). Edit the
`.md` files directly going forward.
