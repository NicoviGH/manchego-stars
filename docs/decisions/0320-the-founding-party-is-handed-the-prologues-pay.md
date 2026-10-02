---
id: 320
title: "The founding party is handed the prologue's pay"
date: "2026-10-02"
section: "Combat System"
issues: [430, 403]
---

# The founding party is handed the prologue's pay

#430 step 4. ch00 is fought by guests: Hlin and Scramsax never join, so nobody in the party
banks its exp. FE8's Prologue pays Eirika and Seth, who stay. Our founding party therefore
entered ch01 a chapter behind its twins and stayed behind, at 0.55x of the twin party's exp
after ch01, rising to 0.89x after ch06 (ADR 0315).

**Each founding PC is handed what the twin pays it for the prologue.**
`exp_curve.founding_grant` reads it off the simulation. The twin party fights FE8's Prologue
over its two-unit field, and each founding career's gain is its grant: 72 exp, or 81 for
Sclorbo, whose Priest class power earns more. The model banks the grant at ch00. The exp-to-date
band now reads 0.98x-1.01x from ch00 through ch06, and the party enters ch02 at L2, as Eirika
does.

**The engine hands the same numbers over** (patch 0015). ch01's injector writes
`gFoundingExpGrants[]`, { pid, exp } byte pairs from `founding_grant`.
`FoundingExp_ApplyOnce` runs at the prep Fight!, right after the lord floor. That seam is where
the roster is final (ADR 0057). It raises every blue unit with a listed pid, benched included,
to its grant if that unit is still level 1 and below it. Permanent flag `0xFB` makes it
once-only, and the flag is spent only when a row found its unit. The `lordfloor` scenario
asserts Marty's 72 at ch01 turn 1, and a test pins its literal to the model.

**It is exp, not a level.** A level-2 join would overshoot by about 28 exp. It would also add
either nothing (`.autolevel = 0` keeps the stats and only costs exp per kill) or a full
level's average growth. `founding_grant` refuses a grant of a level or more, because the hook
levels nobody up.

**Recruits are unchanged here.** #403's correction showed they already join at the level
vanilla's equivalents do. lupin's and trex's donor lines are a separate step-4 fix.
