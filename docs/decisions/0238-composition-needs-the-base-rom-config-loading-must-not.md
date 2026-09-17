---
id: 238
title: "Composition needs the base ROM; config loading must not"
date: "2026-08-12"
section: "Operational Gotchas (durable)"
issues: [265]
---

# Composition needs the base ROM; config loading must not

CI runs `make test` **before** it mocks `baserom.gba` (the mock exists only for the link check),
so anything a unit test reaches must not open the ROM. Making `arena_presentation_config()` —
a config loader consumed by `dressed_portrait_slots()` — compose palettes against vanilla took
eleven unrelated portrait tests down with it. Validation of campaign data stays pure; composing
against vanilla bytes is deferred to build time. Assert on the *delta* in tests: it is ROM-free
and a stronger statement about the YAML than the composed result is.
_Decided: 2026-08-12 (Claude, #265)._
