---
id: 249
title: "A boss on a vanilla SLOT already has its line — measure what deploys"
date: "2026-08-16"
section: "Operational Gotchas (durable)"
issues: [284]
---

# A boss on a vanilla SLOT already has its line — measure what deploys

#284 opened on a measurement, not on the game: *"ch02's and ch03's bosses carry no personal
line, so they are naked class bases and fold in about a third of the time their vanilla
counterparts take."* Half of that was true. **ch02's was never wrong at all.**

FE8 builds a named boss as **class base plus a personal stat line** — vanilla Bazba is a L6
Brigand *plus* HP+5/Pow+3/Skl+4/Spd+2/Def+2/Res+2/Lck+1, and that line is most of why he reads
as a wall. Halvar **deploys on the Bazba slot**, and nothing in the build patches it (only
`PORTRAIT_MAP` cast slots get rewritten), so the ROM has been adding Bazba's line to him the
whole time. He fights at HP 29/Def 6 — **3.6 rounds, the bar exactly**. What folded in 1.2
rounds was `difficulty.py`'s model of him, which projected every enemy off naked class base
because it had no idea which character slot the unit rides.

**The tool knew two of the three ways a personal line reaches a unit.** `unit_real_article()`
read `personal:` in the chapter YAML (Ravisin) and `BASE_DONOR` for a cast member deployed
hostile (Sahnar on Joshua's). The third — an enemy deployed on a vanilla CHARACTER slot — had
no representation at all. `ENEMY_BASE_SLOT` is now that third source, and each entry points at
the constant the injector already builds the unit from, so the slot name is written once.

Verified against the **built** character table rather than by reading the injector, because the
question is what survives the build:

| our unit | slot | personal bases after injection | measured |
|---|---|---|---|
| ch01 `goblin-chief` | BREGUET | unchanged: HP+3/Pow+3/Spd+1/Lck+2 | 5.2 → **6.2 rounds** (bar 6.2) |
| ch02 `raider-captain` | BAZBA | unchanged: Bazba's full line | 1.2 → **3.6 rounds** (bar 3.6) |
| ch02 `raider-bruiser` | BONE | unchanged: HP+3/Pow+1/Skl+3/Def+1 | — |
| ch00 `sephek-kaltro` | ONEILL | **zeroed by the build** | 2.1 rounds (bar 2.2) |
