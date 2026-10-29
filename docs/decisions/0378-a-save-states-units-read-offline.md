---
id: 378
title: "A save state's units read offline, with no emulator run"
date: "2026-10-29"
section: "Operational Gotchas (durable)"
issues: [510]
---

# A save state's units read offline, with no emulator run

**An mGBA save state (`.ss`, the campaign's chapter starts) holds EWRAM at file offset
0x21000**, so any EWRAM symbol sits at `0x21000 + (address - 0x02000000)`. Measured 2026-10-29 on
`references/sim/vanilla/.../scout-vanilla/7.ss`: the offset is where the first blue unit's
character pointer resolves to Eirika in the ROM.

For the unit arrays: `gUnitArrayBlue` (0x0202BE4C on the retail ROM, `vanilla-symbols`), 0x48
bytes a unit; +0x00 the character pointer (its byte +4 in the ROM is the charId), +0x0C state
(`Board.US_*`), +0x12 / +0x13 max / current HP.

**Use it to answer "what did the game leave" without spending a run**: it is how the scout's
Ch6 start was shown to hold Joshua blue with US_DEAD (ADR 0376). It reads memory only: a
question about what the game WOULD do still runs the game (ADR 0377).
