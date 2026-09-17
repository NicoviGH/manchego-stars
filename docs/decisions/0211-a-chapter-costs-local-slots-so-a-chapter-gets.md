---
id: 211
title: "A CHAPTER costs local slots, so a chapter gets its own chunk"
date: "2026-08-24"
section: "Operational Gotchas (durable)"
issues: [314]
---

# A CHAPTER costs local slots, so a chapter gets its own chunk

Lua allocates one VM register per local and caps it at **200 per function**. A `.lua` file compiles
as one function, so every top-level `local` in `harness.lua` — all 9,000+ lines of it — competes for
the same 200 slots. `check_lua_local_headroom` measures the margin by appending probe locals until
the chunk stops compiling, and fails at zero; the number is never written down, because the version
that was written down was wrong in three files at once.

**Adding a scenario is free. Adding a CHAPTER is not.** `scenarios.ch05village = function()` is a
table field and costs nothing. Of the harness's 198 top-level locals, **32 are chapter- or
cast-scoped** (`CH02_CHWINGA_PIDS`, `CHAR_BRAULO`, `reachCh02Map`, `clearCh04`) — roughly **6–7 per
chapter across the five built**. Measured against the growth curve (116 locals in June, 148 in July,
198 in August) and thirteen chapters still to build, the harness runs out during **ch06**, not at
ch18.

It had not broken yet because the pressure was venting as **duplication** rather than as a compile
error. The old rule here — *"declare it INSIDE the scenario that needs it"* — is what produced that:
**94 constant declarations inside scenario bodies, 67 distinct names, 24 of them re-typed across two
or three scenarios.** `VILLAGE_X`/`VILLAGE_Y` in two, the four reliquary `SITES` typed once in
`ch05reliquaries` and again in `ch05crest`, `PEN_X`/`PEN_Y`/`RUN_X`/`RUN_Y` in two. A ceiling that
converts itself into duplication is worse than one that fails, because nothing reports it.

**So chapter-scoped Lua lives in its own chunk, with its own fresh 200** — `tools/playtest/ch05.lua`,
returning a table the scenarios that need it `dofile`. `LUA_CHUNKS` is globbed, so a new chunk is
covered by `check_lua_chunks_load` the day it exists. `harness.lua` keeps the engine primitives and
the scenario table; what is *about a chapter* leaves.

**What this corrects.** The previous version of this entry said the harness stays whole and a new
helper should be declared inside the scenario that needs it. That was a sound call against the
future it could name — *"its only likely change is add a scenario"* — and it named the wrong one.
The recurring change is *add a chapter*, and it costs slots. The placement test in `CLAUDE.md` cited
this file as its own example and has been rewritten with it.

_Recorded: 2026-08-24 (#314). Supersedes the 2026-08 entry, which was measured against scenario
count rather than chapter count._
