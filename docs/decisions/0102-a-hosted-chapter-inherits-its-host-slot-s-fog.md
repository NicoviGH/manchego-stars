---
id: 102
title: "A hosted chapter inherits its host slot's FOG, and nothing guards that"
date: "2026-09-03"
section: "Distribution & Scope"
issues: [26]
---

# A hosted chapter inherits its host slot's FOG, and nothing guards that

ch06 declares `fog: none` and means it: 40% of its map is concentric water with eight crossings,
so the route IS the puzzle and it is one the player has to be able to see. **Slot 7 ships
`initialFogLevel: 3`** — vanilla Ch7 is a fogged chapter — so hosting ch06 there without writing
the field would have handed the chapter three-tile vision and hidden its entire design.

This is the same shape as the goal text ids (#207), the battle grounds, the difficulty numbers
(#303) and `.traps` (#302), with one difference worth writing down: **those four now have passes
that write every hosted chapter's declaration, and fog does not.** ch04 writes `initialFogLevel`
inline because it WANTS fog; ch06 writes it inline because it does not. Two chapters, two inline
writes, no registry — which is precisely the state `.traps` was in the day before it nearly
shipped ch06 a pair of ballistae.

`inject_ch06` reads the YAML's `fog:` and refuses a value it does not know how to write, so the
declaration decides rather than the injector remembering. **The general pass is owed**, and it
should cover every `chapter_settings` field a chapter can silently inherit, not just this one.

_Decided: 2026-09-03 (Claude, hosting ch06)._
