---
id: 108
title: "Measured in-engine, before the fix (ch05, three runs):"
date: "2026-08-22"
section: "Distribution & Scope"
issues: [303]
---

# Measured in-engine, before the fix (ch05, three runs):

| unit | tutorial | normal | difficult |
|---|---|---|---|
| Ravisin | 39 | 40 | **35** |
| white moose | 28 | 29 | **23** |

Difficult was the WEAKEST — an inversion. The cause is an asymmetry between the two paths:
`UnitAutolevelPenalty` re-runs **full `UnitAutolevel`**, which for a `CA_PROMOTED` unit first
applies `GetCurrentPromotedLevelBonus()` (+9 levels, +19 on Hard); `UnitApplyBonusLevels` with a
POSITIVE count calls `UnitAutolevelCore` directly and never reaches that branch. So the easier
modes handed our two promoted ch05 bosses +9 levels of growth they were never authored with,
while Difficult added only its +3. The community documents the same routine from the other side
— when the penalty's target falls at/below `baseLevel` the recalculation is skipped entirely,
which is the known "weak promoted enemies on easy/normal" bug in the localized ROM
(feuniverse.us/t/fe7-fe8-difficulty-stat-changes/1295).

**Fix: `RAW_PID_LEVEL_SOURCES` writes `baseLevel` = the level the unit deploys at**, read from
the chapter YAML so it cannot drift from the level itself. After it, measured:

| unit | tutorial | normal | difficult |
|---|---|---|---|
| Ravisin (class base 19 + personal 15 = 34) | 34 | 34 | **35** |
| white moose (class base 21) | 21 | 21 | **23** |

Tutorial and Normal now ship the authored line exactly; Difficult is the strongest. Generics are
untouched (20/22/26 before and after) — they are autolevelled and `baseLevel` 1 is correct for
them, matching vanilla's own generics.

**The general rule: a unit on a raw pid inherits a GAP, and a gap is all zeros.** Riding one is
not a neutral act — every field vanilla would have filled is silently 0/1, and `baseLevel` is the
one that decides whether the engine keeps your stat line or throws it away. Guarded by
`unregistered_raw_pid_bosses()`, because nothing about the failure is loud: the boss simply
fights with different numbers than the YAML says.

⚠️ Every playtest before this graded Tutorial (the menu defaults to option 0), so ch03's and
ch05's bosses were measured in their reset-and-rebuilt form, not their authored one.

_Decided: 2026-08-22. Found by running the #303 mode probe in all three modes; the inversion was
not predicted by the static model, which does not model the promoted branch._
