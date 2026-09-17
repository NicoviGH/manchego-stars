---
id: 252
title: "One death quote per character"
date: "2026-08-16"
section: "Operational Gotchas (durable)"
issues: [25]
---

# One death quote per character

FE8 lets a pid hold two death quotes: a chapter-keyed `gDefeatTalkList` row scans ahead of its
`chapter = 0xFF` one, and vanilla uses that for the escort a chapter is built around — Natasha
gets `MSG_9C6` in Ch5 and nobody else on the map has one but the boss. Basil is Natasha's donor
and holds exactly her role in ch05, so she inherited the slot, and both boxes shipped: the
universal *"Oh-- I'm sorry. I had more berries... I was going to..."* and the ch05 *"But I
haven't-- I still have her berry..."*

**Cut on sight** (Nicolas, on the PR): the two are the same interrupted apology about the same
undelivered berry, so the second box bought a mechanism and no line. The berry quote MOVED to
her universal one and the chapter row is gone. **We ship one death quote per character.**

Two things worth keeping from it. First, the general rule this is an instance of: *a slot vanilla
fills is not a slot we owe.* The empty `0x9C6` anatomy citation invited a second box the way a
free message id invites a scene, and the invitation was the whole reason it got written — the
line was chosen to fill a slot rather than because the character had two things to say.

Second, the hazard, because it survives the cut and will bite whoever revisits this:
`GetDefeatTalkEntry` returns the FIRST pid match, and `inject_pc_death_quotes` runs LAST in
`main()` and prepends at the head. A chapter injector that prepends its own row therefore lands
*behind* the universal rows and never matches — quote silently absent, build green,
`verify_text` green, nothing to see. If a character ever does earn a second quote, the ordering
belongs in `pc_death_quote_rows` and nowhere else; its docstring says so.

_Decided: 2026-08-16 (Nicolas). Scene 13's wiring, its host-block id `0x9F3` and the
`CHAPTER_DEATH_QUOTE_OVERRIDES` registry were all deleted rather than left unwired: this is a
retired mechanism, not a parked one._

---
