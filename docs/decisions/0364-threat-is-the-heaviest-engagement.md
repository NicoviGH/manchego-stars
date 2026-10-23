---
id: 364
title: "Threat is the heaviest engagement"
date: "2026-10-22"
section: "Combat System"
issues: [510, 335]
---

# Threat is the heaviest engagement

#510 step 7 (design on #510, 2026-10-22). Until this step, threat summed every enemy's damage
per round on the unit FE8's AI targets, as if the whole force attacked on turn 1. FE maps are
not played that way. Now threat is the **heaviest engagement**: the largest set of enemies
the party meets together. `timeline.engagements` reads those sets, and `party_matchup` takes
the heaviest one per joint career. Both sides are read the same way.

**Waves: the enemies that come to you.** A pursuer (AI shape `pursuer`) joins the wave of the
enemy phase in which it first strikes the deploy front, with the party holding that front
(`timeline.front_contacts`). Reinforcements ride their arrival turn.

**Pockets: the enemies you trigger.** A striker or statue, or a pursuer that never reaches the
front, waits for the party. For each one, the party pulls it from the cheapest free tile in
its weapons' reach: the tile where the other waiting enemies carry the least expected damage
on the field's least durable member. This assumes a **careful player** (Nicolas: a careless
attempt ends in a restart, so the run that clears the chapter is the careful one).

**The swung weapon stays equipped.** A wave member attacks before the party fights it, so in
clear-load it defends with the weapon the AI picked against the target it picked (the step-3
open item; `ch06halberd` proves FE8 does this).

**What the engine taught the model (`ch04waves`, Normal).** The scenario holds the party on its
deploy tiles for eight enemy phases, with every unit on both sides held at full HP every frame
so nothing dies, and logs the phase each red unit first attacks. (Its first version refilled
only the party, once a phase, at 0 Pow. Counters still landed through weapon Mt and six reds
died, each freeing a tile. The verdict now fails if any red dies.) The first reading matched 18 of 23 bodies, and every miss was the model running
early. Four fixes, each grounded in the decomp, brought it to 20 of 23:
- **The party blocks.** A red walks through reds but never through a blue, and cannot stand
  on one (`danger_map.Board(blocked=)`).
- **A striker needs a firing tile of its own**, and keeps it once it has struck.
- **FE8 moves units in `SortAiUnitList` order** (cp_order.c), ascending Mov plus 20 for melee
  or 40 for ranged, stable on the table order (`timeline.ai_priority`). Table order is LOAD
  order, so a tie goes to the unit that arrived first, whatever the list says. Each unit takes
  the free tile nearest its own walk; it does not pick the tile that leaves the most for the
  rest.
- **`AI_B_11` and `AI_B_12` wait one turn** (`AI_NOP_0E`, then `AI_SET_AI2`): on their first
  phase only the action half moves them (`danger_map.WAIT_ONE_TURN`).

**Measured limit.** All 3 remaining misses are the model striking earlier than the engine. A
Mauthe Doog strikes one phase later. Two turn-3 Revenants, which the model has striking on
phases 6 and 7, never find a free tile within the eight phases. FE8's pursuit walks a unit
toward the unit it has chosen to attack, even when a tile beside another party member is free
(a Revenant stopped at (8,2) on phase 5 when (8,3) was open). Reproducing that means
simulating FE8's own path toward a chosen target, which is step 9's simulator (#456). The
twin is read with the same model, so the error runs the same way on both sides: the read is a
little early on both.

**Where a side has no board** (our map not compiled), all three reads fall back to every enemy
at once, so the two sides are never read two different ways. An unwritten chapter's target
reads its twin's engagements (ADR 0363).

**First reading** (verdict diff vs main): no verdict moves. ch04 Difficult threat goes from
x1.46 to x2.19 (already OFF): a finding for step 10, and nothing is widened. On the way, ch02
read OK → OFF at x0.74 from a tie-order bug alone. Vanilla Ch2 lists its turn-3 raiders ahead
of Bazba, so they took his tile. Nicolas caught it ("don't we have basically the exact same map
and enemies?"). With load order it reads x0.91, the same 3-body wave on both sides.
