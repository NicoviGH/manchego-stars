---
id: 421
title: "A struck unit no heal reaches is judged on three enemy phases"
date: "2026-11-15"
section: "Combat System"
issues: [510]
---
# A struck unit no heal reaches is judged on three enemy phases

**Decided (Nicolas, 2026-11-15, on #510 comment 6903393935): the wear, three phases, its own
budget. It amends ADR 0389.**

**The problem.** On Ephraim's Ch9 (start `lap3p-cs-s4006/23`, careful) Colm (charId 9, a thief)
went ahead of the army on his own. A Mercenary (unit 157, class 0x0F) struck him for 12 each enemy
phase. Each turn the cap (ADR 0384) read the next phase only: 27 HP survives one hit, so his
death read 0 and the march was admitted. The mend never tried his other acts, because it only
works on a unit with a death chance above 0. Among admitted plans, progress ranks before HP
left. He died on turn 17 with no safe tile left (#510 comments 6900592350, 6900703181,
6901059805). The model error: the cap assumed each turn starts fresh, which is false for a unit
whose HP nothing restores.

**The rule (`planner.lua` `carries()` in `judge()`, `wear()` in `consider()`).** Some units the
judged phase strikes have no heal that can reach them before the phase after. Each such unit is
read on `M.WEAR` = 3 enemy phases, its HP carried from each phase into the next:
- **"No heal can reach it":** it holds no item that heals itself (`sight.salve`: a heal that is
  no staff, `Board.staffRange`), and no staff user of the army can get within its staff's reach
  of it next turn (`healsNext`). The reach is the staff's own (`Board.staffRange`, Physic's
  Mag/2), the move the game's costs out from where the plan leaves the healer
  (`sight.turnsTo`, GenerateExtendedMovementMap, units not blocking). It is a yes or no one turn
  out: counting the healer's turns instead (runs `wearg1`, `wearg3`) played a healer that never
  came.
- **The second phase** is played by the game's AI after our army's reply (`sight.nextPhase`, as
  ADR 0389 plays it; with our units holding until its amendment of 2026-11-17). The third is the second again, each strike counted only while its striker
  outlives our counters before it.
- **Its death chance** is that of dying in any of them, read over each way the next phase went
  on that way's HP (the same ways its next-phase death is read over), and it replaces the
  unit's death in the plan's `protected`. A unit whose death ends the game adds its later death
  to `game_over`. Admission is asked again with the next phase's own numbers kept (`first_*`),
  so over the cap the next phase still ranks first (0389's 2026-11-08 amendment). `predict`
  stays the next phase's: botrun grades each phase against the plan made just before it.
- **Beside the lookahead:** a finalist the wear read reuses its second phase (no second call),
  and a worn unit's later phases stay the wear's reading, in its death and in the game over.
- **Only that unit** takes the later phases. Any other unit can be restored in the turn between,
  so the hold would be no reading for it. No rank key and no filter is added.
- **The mend does not try a worn unit's other acts for the wear alone.** Tried (runs `wr<ch>`),
  it lost vanilla Ch5x's two chests and its clean clear, and Joshua (charId 0x20) on `lap3e/11`.
- **Its budget is its own, beside the lookahead's:** `M.WEAR_DECISION` = 64 calls a decision and
  `M.WEAR_ATTEMPT` = 256 an attempt (botrun passes what is left as `opts.budget.wear`). The most
  seen were 57 and 122 (`lap3e/11`, run `wn11`), so neither cut a game below. A plan past the
  budget keeps the one-phase reading and is counted (`wear_skipped`). The attempt's first such
  plan is a `wear_budget` anomaly counting every one. `montecarlo.py suite` prints the wear's
  calls, CPU and skips beside the lookahead's.

**Changed after the evidence (PR #629's review).** The 31 games below ran on the prototype
(3ffc387a), which read the next phase off its likeliest way's strikes only, left the game over
out, took every staff for a reach of 1 and a staff its holder cannot use for a self-heal. The
fixed rule (35bf830f) was re-run on the 17 starts and the 14 suite runs: see "The fixed rule,
re-run" below.

**Why three.** Three is the least that reads the witness: 27 HP outlives two hits of 12. Two
phases (`wg2x23`) lose Colm on turn 17 as main does. Three cost `lap3e/9` nine turns, and the
north star is deaths, not turns (Nicolas agreed).

**ADR 0396's five tests.**
1. **It names a quantity:** the chance the unit dies over the enemy phases before a heal can
   reach it, built from the game's forecasts, its AI and its movement turns.
2. **It is a price, not a ban:** it is the cap's own death chance, read further.
3. **It holds for every objective and style:** it reads no objective, and it changed play under
   careful, even and bold. It is known to be wrong where the hold overstates the risk for a unit
   that could simply walk away.
4. **It has no second owner:** admission still decides.
5. **It names no unit, chapter or turn.**

**Evidence (attempt 1 each, all from one campaign and stale under ADR 0417: a lead with a clean
witness, not a verdict).**
- **The witness,** `lap3p-cs-s4006/23`, careful, the rule read only from turn 13:
  - Main (`door4`) won on turn 19, and Colm dies on turn 17.
  - The rule (`wg3x23`) won on turn 26 with no death. On turn 14 Seth (charId 2) kills
    Mercenary 157, and Colm opens the chest at (23,1). Four of the seven extra turns are the
    Seize waiting on the chest at (7,1).
- **17 saved starts,** seed 4006 (main `mb<ch>` / `door4`, the rule `wn<ch>`):
  - 12 play main's acts.
  - 5 change: `lap3p/23` (Colm lives), `lap3e/11` (won clean on turn 13, from turn 12 not clean),
    `lap3e/5` (clean, 18 → 17 turns), `lap3p/26` (16 turns either way) and `lap3e/9` (9 → 18
    turns, no death either way).
  - Blue deaths 14 → 13, clean clears 6 → 7, turns 197 → 213.
- **14 suite runs** (`suite --only`, seeds 1001 and 1002 of vanilla-ch3, -ch4, -ch5, scout-ch6,
  -ch10, -ch13, -ch14): all play main's acts.
- **Cost:**
  - The 17 starts: CPU 1020.1 → 1061.6 s (+4.1%), `AiDecideMain` +8.7%, mostly the longer games.
  - The 12 starts with main's acts: CPU +2.9%.
  - The 14 suite runs: CPU 591.8 → 600.7 s (+1.5%), the lookahead's calls unchanged, 123 wear
    calls.

**The fixed rule, re-run (35bf830f, tags `wy<ch>`; suite instrument `5958bfa4c3f8`).**
- **It plays the prototype's acts in 30 of the 31 games.** The witness is the same: won on turn
  26, Colm lives. All 14 suite runs play main's acts.
- **The one change is `lap3e/9`:** stuck after 21 turns. The prototype won it in 18 and main in 9,
  with no death in any of the three.
  - The split is turn 3. Read over every way the next phase goes, Forde (charId 0x10), after his
    attack on enemy 145, dies over three phases at 0.113 (cap 0.05, even). Read off the likeliest
    way alone, the prototype's reading, he dies at 0. So "advance" is not admitted, and the
    attack plan is played. Instrumented run `wd9`: the two reach tests agree on every unit, and
    only the reading over each way differs.
  - From turn 10 on the wear makes no call, and every plan judged is admitted. The stall is the
    march: the board repeats 5 times, no Seize is skipped or played, and the turn-9 arrivals never come
    into sight. Untested: why the march jams there.
- **Totals against main (17 starts):** blue deaths 14 → 13, clean clears 6 → 7, wins 16 → 15.
- **Cost against main,** measured with the CI runner building on the same machine, so the CPU is
  noisy:
  - The 17 starts: CPU 1020.1 → 1050.3 s (+3.0%), `AiDecideMain` 272,359 → 290,943 (+6.8%),
    462 wear calls taking 32.6 s.
  - The 14 suite runs: CPU 591.8 → 597.9 s (+1.0%), lookahead calls 232 → 223 (it reuses the
    wear's second phase), 123 wear calls taking 4.4 s.

**Also found, not fixed.**
- A fallback at a pessimistic two-phase read decides games on main: `lap3e/5` turn 6 opens a
  door at 0.82, `lap3e/9` turn 3 at 0.73.
- In `scout-ch14`, Colm (charId 9) dies on turn 7 at 24.5% under a labelled fallback, with and
  without the rule.
