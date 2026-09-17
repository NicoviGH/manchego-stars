---
id: 107
title: "A raw-pid boss must declare baseLevel, or difficulty wipes its stat line"
date: "2026-08-22"
section: "Distribution & Scope"
issues: [303]
---

# A raw-pid boss must declare baseLevel, or difficulty wipes its stat line

`UnitAutolevelPenalty` (bmunit.c) fires only `if (level > unit->pCharacterData->baseLevel)`.
**Every vanilla named boss ships `baseLevel` >= the level it deploys at** — Saar 8/8, Breguet
4/4, Bazba 6/6, Novala 10/7, Murray 12/9. That is not decoration: it is how vanilla protects a
hand-authored boss line, so the same stats reach the map in all three difficulty modes.

Our bosses on vanilla `CHARACTER_` slots inherit that for free. The four on RAW pids sat in
`gCharacterData` GAPS where `baseLevel` reads 1, so the penalty always fired — resetting the
unit to class base and rebuilding it from class growths, silently discarding the `personal:`
line the chapter YAML authored.
