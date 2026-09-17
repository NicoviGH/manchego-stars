---
id: 63
title: "Lord-select UI (#46): the existing #42 menu COMPOSED with stock components, not a bespoke screen."
date: "2026-06-24"
section: "Combat System"
issues: [42, 46]
---

# Lord-select UI (#46): the existing #42 menu COMPOSED with stock components, not a bespoke screen.

The pick screen shows each candidate's portrait + a qualitative **pitch** (strengths/weaknesses
in words; **no numeric stats** — a hand-authored `lord_pitch:` per PC YAML, Nicolas 2026-06-21)
so the choice is informed. The #42 menu already works — a candidate list over the scenic BACG
with a route-split confirm flow (pick → "Will N lead?" [Yes/No] → permanent flag
`LORDSEL_FLAG_BASE + i`, read by `LordSelect_GetPid`). #46 only adds the info panel, by
**composing ready-made components** rather than building a screen: each `MenuItemDef` gets the
engine's built-in **`onSwitchIn`** hook (`uimenu.c`), which as the cursor lands on candidate *i*
draws their **chibi face** via `PutFaceChibi` (a BG-tilemap face — it layers over the scenic
BACG, **no OBJ-vs-BG priority fight**) and their **pitch** via the stock, self-framed,
auto-wrapped **`StartHelpBox`** (one msg id per candidate, parallel to `gLordSelectCandidates[]`).
The candidate **names are the menu list itself** (the first place the game states them — the
onboarding requirement). Portrait id + name come from each pid's `CharacterData`, so nothing
depends on units being loaded at menu time. A one-time explainer text box precedes the pick loop
(feedback item #4's "(a) explain"). **Why not the earlier plans:** the first hand-built menu used
a full-bust `StartFace2` (an OBJ sprite that lost the priority fight to the scenic BACG) + custom
frames that wouldn't draw — so it was abandoned. The follow-up plan to **clone `prep_unitselect.c`**
into a dedicated `engine/lord_select_screen.c` was dropped as over-engineering (Nicolas, 2026-06-24):
the game is full of reusable boxes/menus/faces, and the eventscript TU keeps no mutable storage
(no `.bss`/`ewram_data` placement), so a Text-managing screen there is the wrong shape. Compose
`PutFaceChibi` + `StartHelpBox` + the existing menu instead. All of it lives where the #42 menu
already does (build-generated into `ch2-eventscript.h`); no new engine source, no injection hook.
Full DoD checklist lives on **#46**.
_Decided: 2026-06-24 (Nicolas; "grab reusable components, don't build bespoke"; supersedes the
2026-06-22 prep_unitselect-clone direction; tracked on #46)_
