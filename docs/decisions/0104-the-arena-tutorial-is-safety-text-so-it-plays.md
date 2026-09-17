---
id: 104
title: "The arena tutorial is safety text, so it plays in every mode"
date: "2026-08-22"
section: "Distribution & Scope"
issues: [303]
---

# The arena tutorial is safety text, so it plays in every mode

Vanilla wraps its arena tutorial in `EventScr_CallOnTutorialMode`, and `CHECK_TUTORIAL` is
`!config.controller && !(chapterStateBits & PLAY_FLAG_HARD)` (eventscr.c:834) — true for
difficulty menu option 0 ONLY. So in vanilla the arena tutorial never plays on Normal or
Difficult, and most players pick Normal.

**We keep vanilla's anatomy and drop that one gate**, because of what the two boxes say: a loss
means the unit *"will not be able to fight in any future battles"*, and B concedes for the fee.
That is a permadeath warning plus its escape hatch — safety information, not a flavour beat. A
Normal player who never sees it can lose a unit permanently to a mechanic nobody explained.

It also makes the arena consistent rather than exceptional: every other teaching beat we ship is
plain dialogue that already played in all three modes (ch02's `fliers-vs-bows`, RBG warning Pinky
off the archer). This was the ONLY `EventScr_CallOnTutorialMode` call in the build, so the change
is exactly this one script and nothing else becomes mode-gated or un-gated with it. The FACTION
gate and the one-shot flag both stay.

_Decided: 2026-08-22 (Nicolas) — "the arena tutorial and the crit warning ship on Normal, the rest
of tutorial mode does not."_
