---
id: 102
title: "Hosting ch06 on a FOGGED slot is what found the fifth inheritable field"
date: "2026-09-03"
section: "Distribution & Scope"
issues: [26]
---

# Hosting ch06 on a FOGGED slot is what found the fifth inheritable field

ch06 declares `fog: none` and means it: 40% of its map is concentric water with eight crossings,
so the route IS the puzzle and it is one the player has to be able to see. **Slot 7 ships
`initialFogLevel: 3`** — vanilla Ch7 is a fogged chapter — so hosting ch06 there without writing
the field would have handed the chapter three-tile vision and hidden its entire design.

This is the same shape as the goal text ids (#207), the battle grounds, the difficulty numbers
(#303) and `.traps` (#302) — the fifth instance of one failure: **a hosted chapter squats a
vanilla slot, so every field it does not write, it keeps.** When this was found, fog was still
being written by hand in two injectors, ch04 because it WANTS fog and ch06 because it does not,
which is precisely the state `.traps` was in the day before it nearly shipped ch06 a pair of
ballistae at another chapter's coordinates.

`apply_chapter_fog` is the pass that closed it (#365, ADR 0290): every hosted chapter declares
`fog:` and the pass writes all of them, so neither injector holds a literal any more. The sixth
instance is the open question, and the census that would answer it once instead of five more
times is #396.

_Decided: 2026-09-03 (Claude, hosting ch06); the pass it called for landed 2026-09-17 (#365)._
