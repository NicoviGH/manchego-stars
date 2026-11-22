---
id: 444
title: "A march also offers the nearest tile where a death is impossible"
date: "2026-11-22"
section: "Combat System"
issues: [714, 699, 510]
---

# A march also offers the nearest tile where a death is impossible

**Decided (#714), #510 step 9. Half of #714: the candidate list.** The other half (a goal driven to
0 before its deadline counting in `forfeits`, `planner.lua`, `goals.lua`) changes how every plan is
scored and stays open on the issue. The risk cap stays (Nicolas, #699 comment 7071632376): this
finds the goalward tile under it, it does not raise it. Extends ADR 0396's candidate list; its five
tests are met: the act is a `wait`, the game forbids nothing new, and no rule orders the outcomes.

**The gap.** A unit's march offered the tile nearest its goal over every tile (`open` gate) and the
`retreat` (the safest tile that gains any ground). Where the nearest is over the cap and the retreat
gains little, a tile between them that no single phase can kill the unit on was offered by neither.
Vanilla Ch10 (`b640e-cs-s4005`, turn 1): Tana (0x22), goal the village (11,15), nearest tile (14,3)
at worst sum 39 against 20 HP; (16,4) reads under 20.

**What changed.** `proposeOne` adds a second march, `march(ctx, u, GATES.careful, objective)`: the
nearest tile the `careful` gate allows (worst-case sum under HP), over every tile and over free
tiles only, as the open march is. No new helper: `march`, `gated` and `GATES` already did it. It is
added after the retreat so a tile both pick keeps the retreat's label (the planner keeps hold and
retreat through the beam's cut, `planner.lua`, and a march is not cut-proof: its own score carries
the progress and the risk, so a tile worth playing ranks in the per-unit best by itself). It carries its own `why`, `careful`, which the planner keeps through the per-unit cut as it keeps hold and
retreat: a debug replay showed the menu's PER_UNIT cut (`planner.lua`) dropped it (Tana's (16,4) ranked 6th of 8 on turn 1, own score -33.7 against -13.6 for the holds), so it never reached the beam. Where no tile
passes the gate or the unit has no goal, `march` falls back to the safest tile, the hold's
duplicate, which `add` drops. The `even` gate (no single enemy's max reaches HP) is not offered: no
data asks for it.

**Proof (ADR 0430).** `test_a_march_offers_the_nearest_tile_where_a_death_is_impossible` fails on
main. One replay, `fix714e` (`resume --game vanilla --campaigns b640e-cs-s4005 --chapter 10 --last 10
--attempts 1 --scout --route 1 --seal-at 10`): won on turn 14 with 0 deaths; Tana played the
careful march (14,4) on turn 2. The village (11,15) was still razed on turn 5: Tana mended at (14,6)
on turns 3-4 instead of going on. Without the cut-proof label (`fix714`) the plan was unchanged and
the village razed too. From (16,4) Tana is 2.29 turns from the village, the same as from the retreat
(17,5); only (14,4) is nearer (2.00). Why she mends rather than visits is the scoring half of #714
(a march earns no goal progress of its own at the menu stage), not built here.
