---
id: 264
title: "The AI is in the UnitDefs, so it is DERIVED"
date: "2026-08-29"
section: "Operational Gotchas (durable)"
issues: []
---

# The AI is in the UnitDefs, so it is DERIVED

ch06's first roster authored its `ai_pattern` labels by feel and got the chapter backwards -- 13
pursuing units where vanilla Ch6 fields two. `src/events_udefs.c` answers it unit by unit:
17 `AttackInRangeAI` (ActionInRange + NeverMove), 4 on `AI_B_12 MoveToEnemyAfterOneTurn` (the three
Cavaliers **and** the Troubadour -- vanilla's healer rides with its cavalry), 2 with no `.ai` block
at all (= pursue), the boss on `GuardTileAI`, and 3 Hard-only Cavaliers on `{DefaultAI, 0x1, 0x0}`
loaded by `CALL(EventScr_LoadReinforceHardMode)`.

**Vanilla Ch6 is a static map.** Nothing charges on turn 1 but two units and a Bael; the player
advances into fixed threat ranges. That is *why* its difficulty was the hostage clock and the fog
rather than an enemy tide -- and it is the shape our two marooned boats inherit.

The general lesson, and why this is an ADR rather than a chapter note: **#48's threat and
clear-load are computed from stats and weapons, so a chapter can measure x1.00 and still play like
a different map.** No gate catches behavioural drift. An audit of ch00-ch05 against their twins
found the same gap almost everywhere, biased toward aggression (ch04 fields 78% pursuers against a
half-static twin); ch05's `raider` and `duelist_hold` are the exceptions, derived exactly. Tracked
with a guard proposal in issue #335.
