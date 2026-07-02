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
- [`hlin-trollbane.md`](hlin-trollbane.md), [`scramsax.md`](scramsax.md),
  [`sephek-kaltro.md`](sephek-kaltro.md) — prologue guests/boss, each with a **§Voice**
  (diction rules, calibration lines, banned list) consumed by the `dialogue-pass` skill.
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
