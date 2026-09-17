---
id: 134
title: "Art: CUSTOM indexed-palette pixel art for every PC/recruit sprite part — portrait, map sprite, AND battle animation."
date: "2026-06-01"
section: "Art & Audio"
issues: []
---

# Art: CUSTOM indexed-palette pixel art for every PC/recruit sprite part — portrait, map sprite, AND battle animation.

Not recolored vanilla, and not reused vanilla class animations. Combat is pure vanilla FE8, so the art is the
single biggest lever for making the game feel like the actual D&D campaign — worth doing custom and taking the time.
Each piece is produced **faithfully from the character's clean Gemini/Nano-Banana bust reference** via tooling
(`tools/ref_to_bust.py` → `tools/portrait_tool.py`): the generative bust is the **pre-approved source art** and is
converted — not hand-pixeled (Nicolas is not a pixel artist) — into the final 16-color indexed asset. Nicolas supplies
one clean frameless **"<Name> Face Clean"** bust per character; Claude converts it. Specs: 16-color GBA palette, 8×8 tiles.
Per-unit design briefs (must-keep tells, expression, palette plan) live in each unit's YAML `art:` block
(`campaigns/.../{pcs,npcs}/*.yaml`).
**Sequencing — three waves:** (1) all 10 cast portraits, then (2) all map sprites (16×16 chibis), then (3) battle animations.
_Decided: May 2026; full-custom direction + Gemini-ref-to-asset pipeline proven 2026-06-01 (Braulo, then Prof. R.B. Geenius)._
