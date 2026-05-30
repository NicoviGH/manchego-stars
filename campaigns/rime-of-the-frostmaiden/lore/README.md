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
  [`prof-rbg.md`](prof-rbg.md), [`rootis.md`](rootis.md), [`sclorbo.md`](sclorbo.md),
  [`wolfram.md`](wolfram.md) — the 7 player characters.
- [`pepperjack-and-brie.md`](pepperjack-and-brie.md) — the two recruitable automatons RBG builds
  (units: [`../npcs/pepperjack.yaml`](../npcs/pepperjack.yaml),
  [`../npcs/brie.yaml`](../npcs/brie.yaml)).

## Regenerating PC lore

The 7 PC lore files were generated from the pre-strip YAML by `/tmp/genlore.rb` (Ruby; `pyyaml`
is not installed). It loads `git show e6cc7a6:.../pcs/<pc>.yaml`, pulls the `dnd` concept and each
ability's `name`/`flavor`/`fe_mechanic`, and writes the markdown. Edit the `.md` files directly
going forward — the generator was a one-time migration.
