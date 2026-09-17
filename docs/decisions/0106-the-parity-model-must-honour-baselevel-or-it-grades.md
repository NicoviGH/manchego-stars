---
id: 106
title: "The parity model must honour baseLevel, or it grades bosses the ROM never touches"
date: "2026-08-22"
section: "Distribution & Scope"
issues: [303]
---

# The parity model must honour baseLevel, or it grades bosses the ROM never touches

`mode_stats` defaulted `base_level=1` and no caller passed anything, so the model applied the
difficulty MALUS to every unit — including bosses that `UnitAutolevelPenalty` leaves alone
(`if (level > baseLevel)`). Both sides' walls were understated in exactly the two modes where
clear-load is measured.

It reported ch05's Tutorial at clear-load **x0.69 / OFF** — a verdict about the model, not the
chapter. With real baseLevels threaded (vanilla's from `data_characters.c` by charIndex, ours from
the invariant that every boss we field is penalty-immune) the same read is x0.74, and the residual
gap turned out to be the boss's own durability, not the shift.

Nearly re-tiered a chapter's enemy levels to chase it. **Before tuning content against a model
number, confirm the model reproduces what the ROM does** — three level redistributions were tested
and moved clear-load by 0.01, which was itself the clue that levels were not the mechanism.

_Decided: 2026-08-22._
