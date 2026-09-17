---
id: 12
title: "Chapter deployment schema: ONE shape, gated (#107)."
date: "2026-07-02"
section: "Engine & Tech Stack"
issues: [107]
---

# Chapter deployment schema: ONE shape, gated (#107).

All deployment data lives inside the chapter YAML's `deployment:` block -- `deploy_limit`,
`deploy_slots`, prose `note`, `green_allies`. `player_units:` is the single alternative,
only for a fixed-roster chapter with no prep screen (the prologue). Kills the audit-2.2 drift
(four incompatible shapes across 9 files; three different access paths in code). ch01/ch02
migrated; consumers (`inject_ch01`/`inject_ch02`, `difficulty.py chapter_deploy_limit`) read
only the block. Gate: `check.py check_chapter_deployment_schema` (CI + pre-commit) --
top-level `deploy_limit`/`deploy_slots` are rejected, slots must match the limit (the slot
list IS the cap template), an `active` chapter needs a machine-readable `deploy_limit`
(prose caps are for `planned` seeds), `green_allies` entries need id/class/level/position.
The #105 hoist also finished here: `_split_event_beats`, `_require_beat_count`, `_make_fid`,
`_emit_scene_beats`, `_classed_cast`, `_deploy_cap_entries`, and `_ally_unit_entry`
parameterized over allegiance/autolevel/ai (ch02's `green_entry` copy retired). Verified:
old-vs-new injection into a clean submodule against the same mock base ROM diffs empty
(byte-identical generated sources), full test suite + drift guard green.
_Decided: 2026-07-02 (CLAUDE; audit 2.1/2.2 follow-through)_
