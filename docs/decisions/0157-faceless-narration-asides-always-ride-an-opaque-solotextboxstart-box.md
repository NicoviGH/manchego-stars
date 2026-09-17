---
id: 157
title: "Faceless narration/asides always ride an opaque SOLOTEXTBOXSTART box, never the translucent talk window (#58)."
date: "2026-06-20"
section: "Story & Dialogue"
issues: [58]
---

# Faceless narration/asides always ride an opaque SOLOTEXTBOXSTART box, never the translucent talk window (#58).

A `narration:` (faceless) line shown via the default `Text()`/TEXTSTART path renders in the translucent
conversation window — illegible over a BACG's scene art (the brother's v0.1.0 "Marty leans in..." aside). The
engine routes text type 0 (TEXTSTART) to the faced talk system (`sub_800E210`) and type 4 (SOLOTEXTBOXSTART) to
the opaque, auto-centered BoxDialogue (`sub_800E31C`, helpbox.c) — and the opaque box draws **no faces**. So in
`build_campaign.py`, scenic beats are emitted per-beat (`_scenic_beat_calls`): a beat that is ALL faceless
narration rides `SVAL(EVT_SLOT_B,0xFF00FF) + SOLOTEXTBOXSTART` (auto-center) and is wrapped at the on-map width
(28, not the 42 scenic wrap, so the centered box fits 240px); any faced beat stays on `Text()`. Because the box
can't mix with faces, a beat mixing narration + dialogue must be **split** with a `beat_break` (e.g. ch01 ending
E2/E2b) so the aside gets its own box. Campaign-wide convention; the road-sign narration already used this.
_Decided: 2026-06-20; from the brother's v0.1.0 playtest (#58)._
