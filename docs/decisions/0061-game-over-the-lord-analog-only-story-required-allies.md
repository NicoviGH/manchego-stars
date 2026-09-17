---
id: 61
title: "Game over = the lord-analog only; story-required allies \"retreat\" instead."
date: "2026-06-09"
section: "Combat System"
issues: []
---

# Game over = the lord-analog only; story-required allies "retreat" instead.

A chapter's game-over trigger is the must-survive lead alone (ch00: Hlin; from Ch1
the player-chosen lord, #42) — vanilla's exact shape: only Eirika/Ephraim carry
`EVFLAG_GAMEOVER` quotes everywhere, Seth's death quote has no flag. A story-required
non-lord ally (ch00: Scramsax) gets a **flag-less defeat quote** framed as a retreat
("too weak to continue the fight"): the battle continues, and the character is out of
the fight, not dead, so later chapters can use them freely. Vanilla also supports
per-chapter `EVFLAG_GAMEOVER` for guests (Duessel Ch10, Mansel Ch19) — available if a
future chapter truly needs it, but the default is lord-only.
Mechanism note: injected `gDefeatTalkList` entries go at the **head** of the list —
see "Chapter outcomes ride gDefeatTalkList" below for why.
_Decided: 2026-06-09 (Nicolas; retreat framing is his)_
