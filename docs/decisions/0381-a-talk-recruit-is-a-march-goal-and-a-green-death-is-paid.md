---
id: 381
title: "A Talk recruit is its nearest talker's march goal, and the planner pays a green unit's death as one of ours"
date: "2026-10-30"
section: "Combat System"
issues: [510]
---

# A Talk recruit is its nearest talker's march goal, and the planner pays a green unit's death as one of ours

**Decided (2026-10-30), #510 step 9 part D (Talk recruits as goals, which protect the recruit;
Nicolas picked it first of the planner's open items).** Two changes to the planner's view, no
new game read:

1. **A Talk recruit is a march goal.** Each non-blue unit the game lets one of ours Talk to
   (`sight.canTalk`, i.e. `CheckForCharacterEvents`) sends the nearest such talker, by the game's
   field from the recruit, marching on it (`exploring` in bot.lua; `nearestTalker` is shared
   with the recruit claim's rule). It comes before any village or chest. Before this the planner
   credited a Talk only once a talker happened into reach, so a recruit the march did not pass
   was never reached.
2. **A green unit's death is paid at a unit's price.** The judge plays the enemy phase against
   every green unit where it stands and pays `W.death` per unit of its chance to die, as for one
   of ours. botrun's clean clear already counts a green death as a loss (ADR 0376; vanilla
   Ch6's villagers), so the planner was blind to something the verdict counts.

**Measured in the ROM** (vanilla, New Game, seed 1, the Ch2 start this campaign reaches; saved
under the campaign id `d1-ross`):

| Run | Ch2 result |
|---|---|
| Before | No clean clear in all 6 styles: Ross (green) killed on turn 2-3 every time, so the campaign stops as a bot fault |
| Both changes | Attempt 2 (even) clean: Eirika talks Ross on turn 5, Ross is sent to Garcia and talks him on turn 6 |
| Goal only | Attempt 2 clean, the same frame count as both changes |
| Judge only | No clean clear in all 6 styles |

So the goal is what clears this start. The judge did not change this run's outcome: on attempt
1's turn 2 it priced Ross's 0.37 chance of death, but no plan the beam proposed covered him.
It is kept because it is the verdict's own definition of a loss, and its effect is proven by a
unit test (`test_planner_pays_a_green_units_death`), not by this run.

**Not decided here:** whether a careful style should spend more to save a green unit than its
own unit's death (a recruit forfeited is worth more than one loss). The weight is `W.death`
until a run shows a chapter that needs more.
