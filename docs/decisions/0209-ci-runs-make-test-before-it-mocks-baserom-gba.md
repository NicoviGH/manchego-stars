---
id: 209
title: "CI runs `make test` BEFORE it mocks `baserom.gba` (2026-07, #23)"
section: "Operational Gotchas (durable)"
issues: [23]
---

# CI runs `make test` BEFORE it mocks `baserom.gba` (2026-07, #23)

Nothing a unit test reaches may open the ROM: in CI the mock is not in place yet when the suite
runs, so a test that touches `baserom.gba` fails there and passes locally, which is the worst
shape of failure to diagnose.

Keep config loading PURE and defer composition to build time. The rule falls out of it: a module
imported by a test may compute, but may not read the ROM at import.

_Recorded: 2026-07 (migrated out of HANDOFF 2026-08-20)._
