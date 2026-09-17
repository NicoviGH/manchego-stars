---
id: 103
title: "A chapter declares its traps; `.traps` is the fourth inherited field"
date: "2026-08-22"
section: "Distribution & Scope"
issues: [302]
---

# A chapter declares its traps; `.traps` is the fourth inherited field

`.traps` is a **ChapterEventGroup** field (chapterdata.h:32), not a `chapter_settings` one. Our
injectors FILL the group but never wrote that field, so every hosted chapter kept whatever its
donor group carried — the same silent-inheritance shape as the goal window/status text ids
(#207), the battle grounds, and the difficulty numbers (#303).

**It was one chapter from biting.** ch05 fills `Ch6Events`, which is clean. But the hosting
pattern puts ch06 on slot 7 filling `Ch7EventData`, and vanilla Ch7 carries **two ballistae, at
(17,8) and (2,10)**. ch06 would have shipped with enemy ballistae at another chapter's
coordinates, in every difficulty mode, chosen by nobody and explained by nothing.

Found because Nicolas asked whether "no traps" was another *unwired is not never* case. It was
— but not where either of us was looking. The first pass checked only `extraTrapsInHard`, the
field #303's checklist happened to name, found every donor empty, and called the whole channel a
non-issue. `extraTrapsInHard` really is empty everywhere except `ruin9`. **The base `.traps`
field is the live one**, and vanilla uses it in nine groups: ballistae (ch7/ch10a/ch13a), gorgon
eggs and fire tiles (ch18a/b), gas (ruin5), fire tiles (ruin9), a light arrow (tower8).

`apply_chapter_traps` now writes each hosted chapter's declaration every build, so inheritance is
impossible by construction rather than by luck. **`traps: []` is a DECISION and reads as one**;
declaring nothing is what the guard catches, and only when the donor actually carries something —
`inherited_traps_undeclared` is a prompt, not a safety net, because keeping another chapter's
ballistae is a choice that should be made out loud.

**Two traps in the trap pass itself, both worth the entry.** The type whitelist must be what
`LoadTrapData` (bmtrap.c:245) actually PLACES, not what `bmtrick.h` names: `TRAP_OBSTACLE`,
`TRAP_TORCHLIGHT` and `TRAP_LIGHT_RUNE` have no case at all, and `TRAP_LIGHTARROW` falls
THROUGH into `AddGorgonEggTrap` because its `break` sits behind `#if BUGFIX`, which is defined
nowhere in the submodule — a declared light arrow would also hatch an undeclared gorgon egg. And
a file the build PATCHES must be in `PATCHED_DECOMP_FILES`, or the previous build's rows survive
a rehost or a branch switch: the same silent inheritance, moved one level up.

**The general rule, now with four instances: filling an event group does not empty it.** Every
field of a ChapterEventGroup our injectors do not write is inherited from whichever vanilla
chapter's group we squatted. Before hosting a new chapter, read the donor group's fields and
decide each one — do not discover them later.

_Decided: 2026-08-22 (Nicolas) — "do it, and the YAML thing too, since our next epic is chapter
as code."_
