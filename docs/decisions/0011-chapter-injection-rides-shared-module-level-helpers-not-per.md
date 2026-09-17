---
id: 11
title: "Chapter injection rides shared module-level helpers, not per-chapter nested copies (#104/#105)."
date: "2026-07-02"
section: "Engine & Tech Stack"
issues: [104, 105]
---

# Chapter injection rides shared module-level helpers, not per-chapter nested copies (#104/#105).

`inject_ch01`/`inject_ch02` grew as copy-paste siblings (the 2026-07-02 audit's top scaling risk
before ch03--ch08). The truly-twin nested helpers are hoisted to module level in
`tools/build_campaign.py` (just above `inject_ch01`): `_split_script_beats`, `_cutscene_fid`,
`_stage_beat`, `_register_chapter_map`, `_retarget_host_chapter`, `_ally_unit_entry`,
`_enemy_unit_entry`, `_prepend_defeat_quote`, `_write_chapter_title_card` -- everything
chapter-specific rides in as arguments. **New chapter injectors (ch03+) MUST build on these
seams instead of copying `inject_ch02`.** Genuinely divergent logic (cast loops, event/scene
wiring, per-beat text overrides) stays per-chapter -- where a "twin" differed at all it was
parameterized or left duplicated, never silently unified. Verified byte-identical: a one-off CI
gate built main's ROM and the refactor's ROM against the same mock base ROM -- equal SHA-1
(`0c374bc5`, PR #105 `rom-diff` run). Follow-ups deliberately out of scope: deployment-schema
normalization across chapter YAML + a generic YAML-driven `inject_chapter()` entry point.
_Decided: 2026-07-02_
