---
id: 245
title: "The role check has to read the personal line; the aggregate cannot yet"
date: "2026-08-15"
section: "Operational Gotchas (durable)"
issues: [25]
---

# The role check has to read the personal line; the aggregate cannot yet

`role_findings()` collected each unit's `personal:` line and then used it for exactly ONE of its
three checks — boss durability, under the comment *"this is the one place the real article is
compared."* Its two THREAT checks ran on class base. That is defensible for the AGGREGATE (a sum
over 23 units, symmetric on both sides) and wrong for a check whose stated job is *"compare the
EXTREMES unit-to-unit"*, because FE8 puts a named unit's teeth in its personal line. Both halves
of the bias pushed the same way:

- **Our boss was understated.** Ravisin reads 8.4 class-base and 12.5 real, so the moose's 11.8
  "out-threatened" a boss that actually out-threatens it.
- **The twin's ceiling excluded the twin's own named units.** `max(vanilla_enemies())` is the top
  CLASS-BASE threat — 6.3, a generic Soldier — while vanilla Ch5 fields Joshua at 21.4. Measuring
  our named units against a bar built only from THEIR generics flags every named unit we field.

**A personal line reaches our units from two places, and the check knew one.** A raw-pid enemy
carries `personal:` in the chapter YAML (Ravisin); a CAST member deployed hostile carries it via
`BASE_DONOR`, written into its character slot by the build (Sahnar rides Joshua's, Lupin rides
Kyle's). Reading only the first made ch05's red Myrmidon measure **6.2** against the **21.4** she
actually fights at. `unit_real_article()` resolves both; `vanilla_threat_ceiling()` includes the
twin's named units. All three of ch05's standing warnings clear, correctly — and a true inversion
still fires, which is the guard test.

**The AGGREGATE stays class-base, and not for want of trying.** Measured both ways, threat
improves everywhere (ch01 x1.15→x1.08, ch03 x1.12→x1.03, ch05 x1.08→x1.04) — but CLEAR-LOAD
breaks on a real FE8 fact: **Saar's personal line puts him at Def 13 against the yardstick's 13
attack, so he takes zero damage and `rounds_to_kill` is infinite.** A ratio against infinity is
meaningless. The repo already has the mechanism (ch08 excludes "yardstick-proof units" from
clear-load), but applying it symmetrically re-baselines every curated chapter, and on the real
article **ch02's clear-load falls to x0.64 — out of band.** That is either ch02 genuinely
under-loaded with the class-base metric hiding it, or an artifact of the exclusion policy. It
needs its own investigation and its own issue; it is not a change to make in passing.

_Decided: 2026-08-15 (Nicolas asked why personal stats were being ignored)._
