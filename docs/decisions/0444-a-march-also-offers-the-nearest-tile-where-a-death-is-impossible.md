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
the progress and the risk, so a tile worth playing ranks in the per-unit best by itself). It has no
`why` of its own, because the planner does not need to tell it from the open march. Where no tile
passes the gate or the unit has no goal, `march` falls back to the safest tile, the hold's
duplicate, which `add` drops. The `even` gate (no single enemy's max reaches HP) is not offered: no
data asks for it.

**Proof (ADR 0430).** `test_a_march_offers_the_nearest_tile_where_a_death_is_impossible` fails on
main (the tile between the march and the retreat is not offered). One replay, `fix714`
(`resume --game vanilla --campaigns b640e-cs-s4005 --chapter 10 --last 10 --attempts 1 --scout
--route 1 --seal-at 10`): won on turn 15 with 1 death (Rennac, 0x12, turn 10), the village
(11,15) razed on turn 5 as before. A debug print confirmed the candidate: turn 1 Tana is offered
(16,4) (open march (14,3), goal (11,15)), turn 2 (14,4). The plan played is unchanged through turn
4 (Tana retreat (17,5) then hold (15,0); Vanessa march (15,2) then mend (14,0)): the tile is
offered and not chosen. Why the beam or the judge prefers the others is untested here, and is the
second half of #714 (what a goal driven to 0 costs a plan). Planning frames, turns 1-4, same
boards: 27,041 against 26,999 on `m699c10`'s record, +0.2%.
