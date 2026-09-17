---
id: 115
title: "Release versioning: `v0.<chapters-playable>.<patch>`, staying `0.x` until the full MVP ships as `v1.0`"
date: "2026-06-19"
section: "Distribution & Scope"
issues: []
---

# Release versioning: `v0.<chapters-playable>.<patch>`, staying `0.x` until the full MVP ships as `v1.0`

A single-line `VERSION` file at the repo root is the source of truth. `tools/build.sh dist`
reads it and stamps `dist/ManchegoStars-v<VERSION>-YYYY-MM-DD.gba`; each shipped build is tagged
`git tag v<VERSION> && git push --tags`. The middle number tracks how many chapters are
playable + balanced, so it climbs to `v0.8.x` over the MVP and the MVP release (Prologue + Ch 1–8)
is **`v1.0.0`**. "Alpha" stays as the title-screen/README *label* for the whole `0.x` phase — the
file/tag is versioned, the in-game label is not. The first build under this scheme is **`v0.1.0`**
(Prologue + Ch 1 playable, with the #45 lord-survivability floor). The pre-versioning
`ManchegoStars-Alpha-2026-06-17.gba` is **not** retro-tagged — the scheme starts clean at `v0.1.0`.
_Decided: 2026-06-19_
