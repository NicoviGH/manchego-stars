---
id: 293
title: "The keyless-sidecar default already had a home, and five copies had been made anyway"
date: "2026-09-17"
section: "Operational Gotchas (durable)"
issues: [377]
---

# The keyless-sidecar default already had a home, and five copies had been made anyway

A compiled map's sidecar may name no tileset; that means `snowy-bern`, because the three oldest
maps (ch00–ch02) predate the key entirely. #371 gave the rule one home in
`build_campaign.map_tileset`, #374 fixed three `map_changes` sites that bypassed it and #376 a
fourth.

#377 was filed as a **decision** — where can a campaign's keyless default live such that a
deliberately stdlib-only tool can reach it, `map_tileset_tool`, the campaign YAML, or a third
home? That question was already answered. **`map_tileset_tool.DEFAULT_TILESET` has existed all
along**: the module that owns tilesets, importing nothing but `glob`/`json`/`os`/`re`/`struct`/
`sys`, and already a dependency of every reader — `map_donor` imports it as `mt`.

So there was nothing to decide. There were seven copies to delete.

## What the copies actually cost

Not style. The two sides fail differently:

- **`map_donor` is the READ side.** Its keyless resolution picks the tileset a map is scored
  against, which picks the `IMPASSABLE` set, which picks the donor it **reports** — the number
  an ADR quotes. It also lost `map_tileset`'s non-dict guard.
- **`import_map_layout` is the WRITE side.** A divergence there is baked into the sidecar it
  creates rather than merely misread.

And three more sat in `gen_map_editor`, which #377 did not list — found by the gate, not by
reading the issue.

## A copy made by assignment is still a copy

The first fix here wrote `WINTER_TILESET = map_tileset_tool.DEFAULT_TILESET`, which binds the
value at import and reads as obviously correct. A test that repointed the constant and asked
what the build resolved caught it: **one literal in the tree, but still a snapshot.**
`map_tileset` now reads `map_tileset_tool.DEFAULT_TILESET` at call time, so there is one *live*
source rather than one spelling of a copy. That is the same mistake as the seven, made one level
up, and it is worth naming because it looks like the fix.

It was made twice: `compile_layout(..., tileset=DEFAULT_TILESET)` binds the same snapshot in a
signature, on the **write** side, where it is stamped into the sidecar. It takes `None` and
resolves in the body.

## Gated, because the constant alone was not enough

`check_one_tileset_default` rejects any `.get(..., '<the default>')` outside the home module.
The constant already existed and five copies coexisted with it for months — nothing said they
could not. The gate is what makes the home load-bearing instead of advisory.

It matches by **AST, and on the default VALUE rather than the key name**, because the first cut
matched text line-by-line against `get('tileset', ...)` and that version had three holes at
once: it missed a default that **wrapped** onto the next line, it missed
`FLAGS.get('--tileset', 'snowy-bern')` — the same literal under a different key, which would
have left the blank-canvas editor on the old tileset after a repoint — and it would have fired
on **prose**, since the home module explains this very rule in the words the scan looks for. A
guard that rejects its own warning is worse than none.

The `maps/tilesets/None/` message is fixed with it: a keyless export told the author to
re-author terrain in `maps/tilesets/None/` while having validated against the default.

## Verified by output, not by the suite

Per *"We wrapped on-map talk at 29 CHARACTERS"* §HOW THE ROLLOUT MUST BE GATED, a mechanical
sweep is gated on output before tests:

- `tools/map_donor.py` reports **identical donors for all nine chapters** before and after;
- the injected decomp is **byte-identical over 975 files**;
- 65 test files pass, `tools/check.py` clean.
