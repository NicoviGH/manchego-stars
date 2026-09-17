---
id: 260
title: "Three ways the naive version of this lies, all handled in the tool and all worth knowing:"
date: "2026-08-26"
section: "Operational Gotchas (durable)"
issues: []
---

# Three ways the naive version of this lies, all handled in the tool and all worth knowing:

- **A tie can be unbreakable.** `Ch5Map.mar` and `Ch5TownMapPast.mar` are **byte-identical** (same
  md5), so ch05 scores 100% against both and no amount of geometry will ever separate them. The
  tool SAYS so. A version that printed the first hit would have invented a certainty it did not
  have — at exactly the 15x21-and-similar scale ch06 will be working in.
- **Our own maps live in the candidate directory.** The build copies each of ours into the decomp's
  `graphics/map/layout/`, so an unfiltered scan returns `Ch01IronTrailMap` as ch01's own donor at
  ~98%. Worse, `_vanilla_tileconfig_path` cannot resolve a tile config for them: it WARNs and falls
  back to `TileConfiguration1`, scoring against the wrong terrain table rather than failing. The
  exclusion is read from build_campaign's `CHNN_LAYOUT` constants, so registering a chapter map
  excludes it automatically.
- **The impassable set IS the result.** The percentages mean nothing without it and it is a
  judgement call, so it is declared in one place in the tool. Water and rivers are deliberately
  NOT counted: they stop foot units, but they are precisely what a retile repaints — ch06 turns
  sea into walkable ice — and counting them as walls scores a coast map against its own future.

⚠️ **Ask the tool before claiming a layout is spent, and never a label.** Two collisions it makes
visible: **ch05 and ch06 both declare `FE8 Ch5 — The Empire's Reach`** (the live one — ch06's
parity bar is being corrected to FE8 Ch6 in its own pass), and **ch08's seed claims Hamill Canyon**,
which ch01 has already used. Neither is a bug today; both are choices somebody should make on
purpose.

_Decided: 2026-08-26. Found during ch06's donor evaluation; ch01's label corrected and the tool
committed in the same PR. The first cut of this ADR published a hand-transcribed table with no
tool behind it — code review caught that the numbers did not reproduce, that ch05's tie was
suppressed, and that our own layouts were in the candidate pool._
