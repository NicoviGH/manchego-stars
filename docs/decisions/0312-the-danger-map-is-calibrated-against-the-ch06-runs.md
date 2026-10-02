---
id: 312
title: "The danger map reads what the cartridge rolls, and is calibrated against the ch06 runs"
date: "2026-10-01"
section: "Combat System"
issues: [430, 367, 26]
---

# The danger map reads what the cartridge rolls, and is calibrated against the ch06 runs

`tools/danger_map.py` gives the damage a unit standing on a tile can expect on each enemy
phase. #367 proposal 2 asked for it, and #430 step 1 asked for it to be calibrated before
anyone trusts it. It reuses `foot_reach`, `ai_shape`, `firing_cells` and `fe_combat`'s
damage. The decisions below are the ones the calibration forced.

**Reds walk through reds.** `MapFloodCoreStep` (bmidoten.c) refuses a cell only when the two
units' indexes differ in bit 0x80. So an enemy's walk is blocked by blue and green units,
never by its own side. Blocking on the turn-1 red bodies kept run 1's archer from the cell it
actually fired from. `map_placement_preview.foot_reach`'s `blocked` stays right for the
player walking through the enemy line.

**Hit is 2RN, crit is 1RN, and venin poisons.** `BattleGenerateHitAttributes` rolls hit on
`Roll2RN` (47 displayed is 45% true; 80 is 92%) and crit on 1RN at x3. A venin hit deals its
damage and also poisons. The poison takes 1-3 HP at the start of each of the victim's next 5
phases (`SetUnitStatus`, `MakePoisonDamageTargetList`). Without poison, run 2's west hull
sinking on turn 5 was a sub-5% tail event. With it, 43% of simulated runs sink by turn 5.
`fe_combat` now reads the same strike for every metric (ADR 0314).

**A firing cell holds one attacker.** The attackers that can all hold a cell at once form a
transversal matroid, so taking them greedily by expected damage finds the heaviest set that
fits. ch06's east door admits one melee attacker.

**Two readings, by question.** With no targets, the map is FE's own danger zone: every
pursuer may be anywhere its walk has reached, so a tile's reading is an upper bound. With
targets (`Board(targets=...)`, the rescue hulls), a pursuer engages the first target it can
hit and advances no further. Run 2's crab worked the west door to the end; the unconstrained
walk had it cross to the east hull as well. An ACTION byte in `check.RESCUE_SAFE_ACTIONS`
spares a hull, and `DoNothing` (0x06) never attacks.

**Calibration, 2026-10-01** (the runs are on #26):

| run | what the cartridge did | what the map says |
|---|---|---|
| 2 (#366, ships) | nothing on a hull on phase 1 | nothing |
| 2 | thrower's first throw at the east hull on phase 2 | thrower, from phase 2, alone |
| 2 | crab on the west door from phase 2 | crab, from phase 2, alone |
| 2 | east hull afloat at turn 12 | 23% of runs afloat at 12; median sink turn 10 |
| 2 | west hull sank turn 5 | 43% sunk by turn 5; median 6 |
| 1 (before #366) | 3 units on the east hull on phase 1, 11 damage | 3 units (archer and knight match; it puts the fighter on the door where the run had the soldier), 15.4 expected |
| 1 | east sank turn 4 | sunk by turn 3 in ~100% of runs |

Run 1's last row is outside the forecast, and it is a known limit, not a miss. Even the three
units the run recorded would sink the hull by turn 3 99% of the time if they kept swinging at
it. After phase 1 they turned on the party. A static reading assumes every enemy wants the
tile, so a mob is an upper bound. Where only declared pursuers can reach a target, as in the
ch06 that ships, the distribution is the prediction.

**What this changes.** No game data. Three findings for #430 step 3:
- ch06's declared fuses are 7 (east) and 8 (west); the forecast medians are 10 and 6.
- `fe_combat`'s metrics, and with them every `make difficulty` reading and the parity ratio,
  used displayed hit and no crit, which undervalued accurate attacks and overvalued
  inaccurate ones. ADR 0314 fixes it.

**`rescue_forecast` asks this model.** It answered the hull question with all three errors
above: red bodies blocked, hit was displayed, and there was no poison. It now reads this
module, one (pursuer, hull) pair at a time. Its arrival is the first phase the pursuer can
strike the hull from where it can actually stand. Its sink turns are the 10th, 50th and 90th
percentiles of simulated fights. ADR 0277's `arrival_to_cells`, `sink_band` (a Wald
approximation built on displayed hit) and `concurrent_attacker_cap` are retired: this
module's walk, `simulate_sink` and the matching in `attacks_on` replace them. ch06's rows
move from turn 9 and 9 to 10 and 6, and the thrower's 2.76 dmg/phase becomes 2.62 once hit
is rolled on 2RN.
