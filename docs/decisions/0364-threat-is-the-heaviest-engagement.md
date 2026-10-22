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
deploy tiles at 60 HP and 0 Pow for eight enemy phases, and logs the phase each red unit first
attacks. The first reading matched 18 of 23 bodies, and every miss was the model running
early. Four fixes, each grounded in the decomp, brought it to 20 of 23:
- **The party blocks.** A red walks through reds but never through a blue, and cannot stand
  on one (`danger_map.Board(blocked=)`).
- **A striker needs a firing tile of its own**, and keeps it once it has struck.
- **FE8 moves units in `SortAiUnitList` order** (cp_order.c), ascending Mov plus 20 for melee
  or 40 for ranged, stable on the table order (`timeline.ai_priority`). Each unit takes the
  free tile nearest its own walk; it does not pick the tile that leaves the most for the rest.
- **`AI_B_11` and `AI_B_12` wait one turn** (`AI_NOP_0E`, then `AI_SET_AI2`): on their first
  phase only the action half moves them (`danger_map.WAIT_ONE_TURN`).

**Measured limit.** The 3 remaining misses are each one phase early. FE8's pursuit walks a unit
toward the unit it has chosen to attack, even when a tile beside another party member is free
(a Revenant stopped at (8,2) on phase 5 when (8,3) was open). Reproducing that means
simulating FE8's own path toward a chosen target, which is step 9's simulator (#456). The
twin is read with the same model, so the error runs the same way on both sides.

**Where a side has no board** (our map not compiled), all three reads fall back to every enemy
at once, so the two sides are never read two different ways. An unwritten chapter's target
reads its twin's engagements (ADR 0363).

**First reading** (verdict diff vs main): ch02 Tutorial and Normal go OK → OFF, with threat at
x0.74 (easier). Its heaviest wave is 3 raiders, against vanilla Ch2's 4 around Bazba. ch04
Difficult reads x2.19. Both are findings for step 10, and nothing is widened.
