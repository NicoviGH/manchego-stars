---
id: 62
title: "Player-chosen lord (#42): route-split menu between the Northlook muster and preps."
date: "2026-06-10"
section: "Combat System"
issues: [42]
---

# Player-chosen lord (#42): route-split menu between the Northlook muster and preps.

The player picks the company's must-survive lead — presumably the PC they played in
the campaign — once, in ch01's beginning scene, *after* the muster (the bar-scene
beat) and *before* the prep screen locks them into the field (placement: Nicolas,
2026-06-10). UI is a clone of vanilla's post-Ch8 route-split menu
(`CallRouteSplitMenu`, `ch8-eventscript.h`): `ASMC` opens a `StartMenu` over the
map, each pick shows a per-candidate confirm text whose `[Yes]` answer lands in
`EVT_SLOT_C`, and "No" loops back to the menu. Candidates = the classed cast in
`PORTRAIT_MAP` order; menu defs, candidate table, and confirm texts are
build-generated (no character names in C).
**Persistence:** one *permanent* event flag per candidate, `0xF0 + menu index` —
permanent flags (ids ≥ 101) ride the save file, `ResetPermanentFlags` (`bmsave.c`)
zeroes them on New Game, and vanilla scripts touch none above `0xE7`, so the 0xF0
block is ours. `LordSelect_GetPid` (injected, `eventinfo.c`) scans the flags;
fallback while unset = first candidate (Braulo), so a debug entry straight into a
chapter never soft-locks.
**Hooks** (campaign-agnostic, `build_campaign._inject_lord_select_engine`):
`IsCharacterForceDeployed_` — the chosen lead is always fielded by the prep flow;
`CanUnitSeize` — Seize belongs to the chosen lead (vanilla hardcoded
Eirika/Ephraim); `UnitKill` — the chosen lead's death raises `EVFLAG_GAMEOVER`
(caught by each chapter's `CauseGameOverIfLordDies` AFEV) whatever the death path;
and the vanilla **route-wide** Eirika/Ephraim `EVFLAG_GAMEOVER` defeat entries are
demoted to flag-less quotes so the PCs riding those slots can die like anyone else
when not chosen. Scene gotcha: chapter loads come up black — the menu needs the
vanilla `FADU(16)`-after-LOAD idiom (cf. Ch4) or it runs invisibly.
Verified by the `ch01lord` playtest: pick the last candidate (benched by default
under the 4-cap) → flag set, force-deployed with the cap intact, death = game-over
screen; ch00 gameover/retreat semantics unchanged.
_Decided: 2026-06-10 (placement Nicolas; mechanism decomp-traced; closes #42)_
