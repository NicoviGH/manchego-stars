---
id: 191
title: "A portrait SLOT name is not a face TAG, and the near-miss is silent"
date: "2026-08-13"
section: "Operational Gotchas (durable)"
issues: [25]
---

# A portrait SLOT name is not a face TAG, and the near-miss is silent

Sephek's face is spelled two ways in this repo. `GUEST_PORTRAIT_MAP['sephek-kaltro']` says
`'O_Neill'` — a portrait-slot name, which is what dresses busts — while `PROLOGUE_SEPHEK_SLOT`
says `'ONEILL'`, and only the second is a spelling `_fid_tag` can map, because its irregulars
table keys on `ONEILL`. Routing his face through the map emits `[FID_O_Neill]`, and
`textdefs.txt` defines `[FID_ONeill]`. **Nothing downstream complains** — the same shape as the
`0x9CC` bug #276 fixed, where every text decoder was green while the wrong face was on screen.
The guard is a test that every `FID_` tag a scene emits is defined in `textdefs.txt`, checked
against `FID_ONeill` present and `FID_O_Neill` absent so the fixture cannot rot into a tautology.

_Decided: 2026-08-13 (#25, wiring ch05's opening — first scene to give Sephek a cutscene face
outside the prologue)._
