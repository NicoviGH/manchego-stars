---
id: 2
title: "FE8 players reset on a death, and the RNG only advances when used, so the same moves repeat the same result"
date: "2026-10-27"
section: "FE8: between battles"
issues: [510]
tags: [resets, rng, savestate, retries]
---

# FE8 players reset on a death, and the RNG only advances when used, so the same moves repeat the same result

- **Resetting on a death is mainstream:** Intelligent Systems staff reset Classic maps when
  they lose someone (<https://kotaku.com/even-the-people-behind-fire-emblem-hit-reset-when-somet-465971876>);
  Casual Mode exists because many players do not want to (NWR,
  <https://nintendoworldreport.com/editorial/42245/fire-emblem-and-the-way-games-should-be-played>).
- **The RNG advances only when used:** hit (two numbers averaged), crit, level-ups, enemy
  stat rolls, and movement-path drawing when several paths reach a tile
  (<https://fireemblemwiki.org/wiki/Random_number_generator>, <https://tasvideos.org/3214S>).
  So the same moves give the same results, and a different order or path changes them.
  Measured on our harness (2026-10-27, #510): a restart from a chapter-start state with the
  same bot style replays the identical game. The suspend save stores the RNG (decomp
  `bmsave.c`).
