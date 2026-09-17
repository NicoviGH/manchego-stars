---
id: 221
title: "`mapfull` was chapter-generic in name and ch03-shaped in fact"
date: "2026-08-20"
section: "Operational Gotchas (durable)"
issues: [25]
---

# `mapfull` was chapter-generic in name and ch03-shaped in fact

Its grid was the literals `{0,8,15} x {0,8,16}` — exactly ch03's 17x16 map — while the scenario
was described and used as chapter-generic. On ch05 (15x21) that walked the cursor to x=16, off
the map, and the run reported `FAIL: controller fault: cursor_right` AFTER capturing every tile it
wanted: a verdict accusing the chapter of something the scenario did to itself.

The worse half is silent. Those stops cover rows 0-15 of a 21-row map, so it would have produced a
confident "full-map grid captured" that was missing the bottom quarter — including ch05's deploy
pocket. **A check that cannot see what it is missing is not a check.**

The grid now derives from `mapSize()`, stepping a screenful (15x10) and always finishing on the
far edge. Two further things the ch05 pan taught, both cheap and both about COST rather than
correctness:

- **Poking fast config before the boot does NOTHING, and the timeouts are not root-caused.**
  It was added claiming to fix them; `bootToMap` goes through New Game and `InitPlayConfig`
  (`bmio.c:936`) `CpuFill16`s `gPlaySt` to zero and sets `textSpeed = 1`, so a pre-boot poke is
  wiped. An earlier run had already passed without it in 22s, so the two timeouts are flake or
  something not yet found — recorded as open rather than closed, because a false cause in a
  comment is worse than none.
- **`--ch05-moose` is the WRONG shortcut for it**, tempting as it looks: `recordch05moose`
  documents that `bootToMap` is the wrong driver on that ROM, because there the beginning script
  IS the beat.

_Recorded: 2026-08-20 (three runs spent on one screenshot; the grid, the speed, and the boot)._
