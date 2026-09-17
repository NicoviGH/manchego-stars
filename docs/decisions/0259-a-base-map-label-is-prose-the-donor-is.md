---
id: 259
title: "A base-map LABEL is prose — the donor is DERIVED"
date: "2026-08-26"
section: "Operational Gotchas (durable)"
issues: [26]
---

# A base-map LABEL is prose — the donor is DERIVED

`fe8_base_map` in a chapter YAML is documentation. Nothing reads it, so nothing has ever checked
it, and ch01's said **"FE8 Ch13a — Fluorspar's Oath"** for months. It is wrong twice over:
`chapters.h` has `CHAPTER_E_13 // Hamill Canyon` against `CHAPTER_I_13 // Fluorspar's Oath`, so
13a is the EIRIKA route and Fluorspar's Oath is 13b; and our ch01 map is 25x16, which matches
`Ch13EirikaMap` and cannot be `Ch13EphraimMap` (22x22) at all.

**Cost when it bit:** during ch06's donor search the label read as *"ch01 already spent the
Ephraim layout"*, and `Ch13EphraimMap` was nearly struck off the candidate list on the strength of
a sentence. A retile is the one decision in this repo where the source of truth is a binary we
own, and we were reading a caption instead.

**Derive it instead, with `tools/map_donor.py`.** A retile preserves geometry, so the donor is
recoverable from the artifact: compare our `.mar`'s blocked-cell pattern against every vanilla
layout of the SAME DIMENSIONS, each read through its own tile config. What it reports today:

| ours | dims | vanilla candidates | donor | agreement |
|---|---|---|---|---|
| ch00 | 15x10 | 14 | `PrologueMap` | 100% |
| ch01 | 25x16 | **1** | `Ch13EirikaMap` — Hamill Canyon | 97.8% |
| ch02 | 15x15 | 2 | `Ch2Map` | 100% |
| ch03 | 17x16 | **1** | `Ch3Map` — Borgo | 84.9% |
| ch04 | 15x15 | 2 | `Ch4Map` | 100% |
| ch05 | 15x21 | 2 | `Ch5Map` **tied with `Ch5TownMapPast`** | 100% |

**Read the candidate COUNT before the percentage.** For ch01 and ch03 exactly one vanilla layout
has those dimensions, so the geometry never identified anything — the size did, and the score is
measuring how far we DIVERGED from the donor. ch03's 84.9% is that: ch03 edited the geometry. A
low score is a fact about our repaint, never evidence of the wrong donor.
