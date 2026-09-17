---
id: 206
title: "AI parity can hide in a GLOBAL table, not in the unit's own bytes"
date: "2026-08-14"
section: "Operational Gotchas (durable)"
issues: [25]
---

# AI parity can hide in a GLOBAL table, not in the unit's own bytes

Sahnar is Joshua, so she must play as Joshua plays — and half of how Joshua plays is a
**refusal**. `AI_A_07` is `gAiScript_ActionInRange_ExceptNatasha`: `AiScriptCmd_05_DoStandardAction`
routes through `AiIsUnitEnemyAndNotInScrList`, which tests each candidate's
`pCharacterData->number` against a list — and vanilla's list (`cp_data.c` `gUnknown_085A8A00`)
holds `CHARACTER_NATASHA` **literally**. That carve-out is the only reason a fragile Cleric can
walk up to a Killing Edge on the arena tile at all.

Copying `.ai = {0x7, 0x3, 0x9, 0x0}` does **not** copy it. Basil takes Natasha as a STAT_DONOR but
deploys on her own CHARACTER slot, so `0x7` silently degrades to plain `AI_A_00` and the escort is
a legal target. `repoint_escort_safe_ai_list` rewrites the list to our escort at build time.

**Safe because the list has exactly one client in all of FE8**: `.ai = {0x7,` appears once, on
`UnitDef_088B5914` — read from decomp HEAD, never the built tree. `AI_A_07` exists to serve one
unit in one chapter, and that chapter is ch05's twin. Guarded three ways: the patch hard-exits
unless it finds vanilla's form, `src/cp_data.c` joins `PATCHED_DECOMP_FILES` so it restores each
build, and `assert_escort_safe_ai_has_one_client` sweeps **every** `CH##_AI` table — scoping that
sweep to ch05 was the first cut and defeated its own purpose, since the hazard is a future chapter
reaching for `{0x7,` on its own account.

**The general shape:** a unit's behaviour is not always in its own data. Before claiming an AI
byte is copied faithfully, find what the script it selects actually READS.
