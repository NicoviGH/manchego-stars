---
id: 18
title: "Chapter cadence taxonomy (the `cadence:` field)"
date: "2026-05-31"
section: "Documentation Model"
issues: []
---

# Chapter cadence taxonomy (the `cadence:` field)

Each chapter YAML carries a `cadence:` token; the generator maps it to one of four
FE8 pacing emoji for `CHAPTERS.md`: 🟥 big-battle/boss · 🟦 breather/intro/escort/travel ·
🟨 sidequest/gimmick · 🎬 scripted set-piece. Current tokens: `tutorial`,
`full_party_intro`, `breather_defend` (🟦); `gimmick_multilevel`, `monster_debut`
(🟨); `first_boss`, `big_battle_gray` (🟥); `marquee_setpiece`, `scripted_defeat`
(🎬). Add a new token to `CADENCE` in `tools/gen_chapter_index.py` when a new pacing
beat appears. The cadence *rules* (why this rhythm) live in `fe8-pacing-reference.md`.
_Decided: 2026-05-31_
