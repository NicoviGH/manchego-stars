---
id: 110
title: "What the ruling makes wrong, and therefore what it commits us to:"
date: "2026-08-22"
section: "Distribution & Scope"
issues: [302, 303]
---

# What the ruling makes wrong, and therefore what it commits us to:

- **Level shifts are DECLARED per chapter, not inherited.** FE8 implements difficulty as a
  per-chapter enemy level shift (`easyModeLevelMalus` / `normalModeLevelMalus` /
  `difficultModeLevelBonus`) plus `extraTrapsInHard`. We never set any of them, so each hosted
  chapter carries its donor host slot's numbers — tuned for a different chapter. ch03 and ch04
  both host on slot 5 and therefore **necessarily share difficulty numbers**, which cannot be
  correct for both. That collision is the founding case.
- **A parity verdict must name the mode it graded.** `difficulty.py` does not model modes and
  every playtest scenario runs one configuration, so every PARITY line this project has printed
  is Normal-only while reading as though it were general. Shipping three modes makes that an
  overstatement rather than a simplification.
- **Mode-gated CONTENT becomes a deliberate call.** `CHECK_TUTORIAL` is
  `!(gPlaySt.config.controller) && !(chapterStateBits & PLAY_FLAG_HARD)` (`eventscr.c:834`), and
  ch05's arena tutorial already rides `EventScr_CallOnTutorialMode` exactly as vanilla's does. So
  on Difficult it does not play. That is vanilla's own behaviour and probably right — but with
  three modes supported on purpose, which content disappears has to be a decision per case
  rather than something inherited unexamined.

What does NOT change: enemies come from our own event `LOAD`s (FE8 has no per-difficulty enemy
tables), and `playerUnitsInNormal`/`playerUnitsInHard` both point at our one ally table, which is
correct because our cast does not change.

_Decided: 2026-08-22 (Nicolas). Execution + the per-item checklist: #303. It is also the first
real test case for #302's "declare it in the YAML instead of inheriting it"._
