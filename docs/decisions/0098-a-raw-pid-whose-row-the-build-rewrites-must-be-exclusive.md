---
id: 98
title: "A raw pid whose row the build rewrites must be exclusive; an untouched one need not be"
date: "2026-09-04"
section: "Distribution & Scope"
issues: [26, 364, 490]
---

# A raw pid whose row the build rewrites must be exclusive; an untouched one need not be

Our chapters put units on raw `gCharacterData` pids, and two chapters may share one quite legally
when the build leaves its row as vanilla ships it: ch04's line Mogalls ride vanilla's own generic
Mogall pid, `0xb7`, as the twin's do, and a `gDefeatTalkList` entry is keyed by **chapter** as
well as pid, so each chapter's quote finds its own unit. A chapter that NAMES its generics takes a
pid of its own (ADR 0352).

Writing anything into the row breaks that symmetry, and the reason is structural:
`gCharacterData[pid - 1]` is **one global row per pid with no chapter dimension at all**. The build
writes three things there: a name plate (`RAW_PID_PORTRAITS`), a personal stat line
(`RAW_PID_PERSONAL_SOURCES`) and a baseLevel (`RAW_PID_LEVEL_SOURCES`). Each one reaches every unit
on that pid in every chapter, and at the call site a rewritten pid and an untouched one look
identical: an entry in a dict of hex strings.

It bit twice:

- **A name plate.** ch06's two rescue boats took `0xb4`/`0xb5`, which `CH04_PACK_PIDS` already
  owned. Two of ch04's five Mauthe Doogs would have read **"Fishing Boat"**. The 0xB0-range
  occupancy lived as prose in three comments, none of them complete.
- **A stat line.** ch03's grell took `0xb7` for its boss line (#284). ch04's four Mogalls fought
  with it in the shipped ROM: 32 HP where the gate measured 15, read off the map by `ch04redstats`
  (#490). The guard of the day checked name plates only, so nothing fired. The grell now rides
  `0xbf`, an unused row with `0xb7`'s vanilla row cloned onto it (`BOSS_PID_ROW_DONORS`), so it
  keeps the Monster plate and the Mogall class.

**The prose was the bug, so prose is not the fix.** `assert_rewritten_raw_pids_are_exclusive`
(a build step) DISCOVERS every raw pid the injector claims (string, tuple and dict constants
alike, matched on `CHNN_*PID`/`PIDS`) and fails the build when a pid it rewrites is claimed by
two chapters, while deliberately permitting a shared untouched one.

_Decided: 2026-09-04 (Claude, hosting ch06), found by `/code-review` on #364; widened to stat
lines and baseLevels 2026-10-18 (#490)._
