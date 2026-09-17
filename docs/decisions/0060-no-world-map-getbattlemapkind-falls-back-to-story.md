---
id: 60
title: "No world map ⇒ `GetBattleMapKind()` falls back to STORY (engine hardening)."
date: "2026-06-10"
section: "Combat System"
issues: []
---

# No world map ⇒ `GetBattleMapKind()` falls back to STORY (engine hardening).

Vanilla classifies most chapter slots (slot 2 onward — `CHAPTER_L_2`...) by scanning
`gGMData` world-map node state and falls back to `BATTLEMAP_KIND_SKIRMISH` when no
node matches; entering through the world map guarantees a node match. Our boot and
`MNC2` chapter hand-offs never populate `gGMData`, so every node-slot chapter was
misclassified as a skirmish — which swaps the beginning scene for
`EventScr_SkirmishCommonBeginning` (black-screen hang; `bm.c CallBeginningEvents`),
hides the ally unit table, and disables force-deploy. Patched in
`build_campaign._patch_battle_map_kind_fallback`: the no-node fallback returns
STORY. Skirmishes are unreachable without a world map, so nothing legitimate hits
the old fallback. Slot 1 (ch00's host) never needed this — it's in the function's
hardcoded STORY list, which is why the prologue worked and ch01 didn't.
_Decided: 2026-06-10 (ch01 slice debugging; found via proc-table dump → `evStart =
EventScr_SkirmishCommonBeginning`)_
