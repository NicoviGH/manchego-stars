---
id: 425
title: "The assault seats only strikers that hurt the boss, and baits when they cannot kill it"
date: "2026-11-18"
section: "Combat System"
issues: [641, 510]
---
# The assault seats only strikers that hurt the boss, and baits when they cannot kill it

**Accepted (2026-11-18, #641; amended the same day by the review of PR #646 and by the win floor below).** In vanilla E_20
the playtest bot never broke Morva (charId 0x41), who holds the seize tile (E_20 is a Seize
map). Every judged throne assault seated Ross (0x07), Vanessa (0x06) and Garcia (0x0A) beside
Ephraim (0x0F). Their blows deal her nothing, and each one cost a whole death (`sum_die` 3.0).
No unit was offered a wait on her strike tile, so the plan the guide plays (stand there and let
her strike into the counter) was never judged. The diagnosis and the design are on #641
(comments 6979929417 and 6980453726).

**The rule** (`tools/playtest/planner.lua`, the assault; `bot.lua` `M.baitAt`).
- **The boss.** The assault's boss is the enemy whose death ends the chapter (`M.endsIn`: a
  Defeat Boss map's boss, a Rout's last red unit) or the seize tile's holder (`M.throne`).
- **A striker is seated only when it deals damage:** its expected damage on the boss is above
  `M.DUST`. A blow that cannot hurt the boss buys its counter and nothing else.
- **When the strikers do not count the boss dead, the bait is judged too** (kind `bait`). The
  heaviest striker waits on one of its strike tiles, holding that strike's weapon. The rest hold.
  It is one more plan for the rank, judged like any other: no ban, and no weight beyond its
  outcomes (ADR 0396). With a single striker there is no assault (the beam already has that
  plan). That striker's own kill chance (`kill >= 0.5`, as `score` counts a target gone) decides
  whether there is a bait.
- **The tile** is the first of the striker's strike tiles, heaviest first, that `Bot.baitAt`
  accepts. The unit must be allowed to strike the boss from it (`strikeTiles`: the throne's rule
  and the avoid claims, as for the strike itself). The boss must be read to strike it (the
  unit's exposure there, with that weapon held), and the counter to take HP off the boss. This
  rules out a range-2 tile against a range-1 boss. No style gate is asked: the strikes the bait
  stands for are offered ungated (`priced`, ADR 0396), and the cap judges the plan.
- **The weapon** is the strike's bag slot. It is the act's `slot` and part of its key (`#n`); a
  slot 0 weapon is already the one the unit fights with, so that is a plain Wait. The judged
  phase arms the unit with it (`stageWear`, as for a planned attack). The harness equips it
  before the Wait (`INSPECT.equipSlot`: Item, the weapon, Equip — `ItemSubMenu_EquipItem` calls
  `EquipUnitItemSlot` and goes back to the inventory list — then B to the unit menu, as
  `ItemMenu_ButtonBPressed` does). The controller names Equip by its menu id 0x35 (`equip_item`).
  Without it, Ephraim countered Morva with the lance in front of his bag (item 25, 15 a blow),
  not Siegmund (item 146).
- **A plan with the bait meets the lookahead's second phase** (trigger `bait`, beside ADR 0389's
  `boss` and `breach`). Its worth is the next turn, and in E_20 Ephraim baited from inside
  Morva's danger zone, so no `boss` trigger fired.
- **The second phase reads the win** (`M.secondRead`'s fourth value). It is the boss killed by
  the army's reply at the kill's chance, or felled by our counter to its own strike. Each counts
  only as far as its unit lives the first phase (`alive`, the judge's). The enemies the first
  phase's counters removed (`sight.nextPhase`'s new `.fell`) and the reply's kills are gone
  before the next is read, so a Rout's last enemy is counted on the board the second phase has.
  The win goes into the goals' own term (`goalTerm`) at `GAMMA` of a first-phase win:
  `M.either(fell, GAMMA * won)`, where `M.either` is the one owner of `1 - (1 - a)(1 - b)` and
  `winOf` uses it too. It adds to the rank's `value` only. `judged` and `goalWorth` stay the
  first phase's, as botrun grades them. The record keeps the second phase's win apart
  (`lookWin = { won, gain, worth }` on the plan, its `considered` entry and the trace's
  `look_win`). The judge's `fell` and this read share `M.fellBy` and `M.endsIn`.
- **A Seize map's holder is not a win** (ADR 0405: the Seize is the win). Its death opens the
  Seize and ends nothing, so on E_20 and I_14 the lookahead credits no win for it. Whether the
  objective's chance should know that the holder blocks the tile is open; it is not modelled
  here.
- **No counter-damage weight.** The bait is played on what the rank already reads.
- **The rank's win leads only at `M.GONE`** (`M.outranks`; ADR 0384's `complete`). A plan's win
  chance ranks ahead of progress and value only where it is at least `M.GONE` (0.5), the one
  constant `score` counts a target gone at (a kill), the judge a composed kill and the assault
  a lone strike. Under it the chance does not lead. Derivation: the rank had no floor, so a
  0.09% win chance (Ch17 seed 2 attempt 4, turn 9) outranked plans worth about 340 more in
  `value`. The chance is not lost under the floor: `goalTerm` puts `pWin` into `value` (the
  objective goal's worth, `c = pWin + (1 - pWin) * chance`, and `W.death * pWin * (1 - GAMMA)`),
  and the lookahead's second-phase win goes in the same way. The floor was taken from the line
  the planner already draws between "done" and "not done", not fitted: 0.5 fixed the loss and
  kept E_20, so no lower floor was tried. Two plans both at or above it still order by the
  likelier win.

**Proof** (vanilla, campaign `bag1-heal4-heal1-lap4e-cs-s4006` unless named; base `ddaae8c5`):
- **Unit tests** (`test_planner_assault_baits`, the `secondRead`/`endsIn`/`either` checks,
  `test_controller`'s Equip). Each check of a fix fails on the commit before it (57fc75a4);
  the two-striker check makes the seating test assert something, and passes there too.
  - The bait is played, and no 0-damage unit is seated.
  - A second damaging striker makes an assault that seats exactly those two.
  - The bait holds slot 2, in the act and in the judged phase.
  - Against a range-1 boss the bait takes the tile the boss strikes.
  - The bait triggers the second phase.
  - The reply's win is discounted by the killer's survival, and `goalWorth` stays the first
    phase's.
  - A Rout's last enemy counts the first phase's removals.
- **E_20** (attempts 1-2, seed 1):
  - Attempt 1 is lost on turn 3 on both (`forecast_desync`).
  - Attempt 2 is the same game on both up to turn 41.
  - On turn 41 Ephraim equips Siegmund and waits on 11,12. Morva strikes him (51 to 15). His
    counter crits her dead (62 to 0); the judged phase read the counter kill as sure. Eirika
    (0x01) seizes on turn 42: **won on turn 42**. Base is `stuck` on turn 47.
- **I_14** (`lap4p-cs-s4006` from 27, attempts 1-3): unchanged, no clear on either.
  - On attempt 2 Ephraim baits Vigarde (0x6B) on turns 29-31, and the throne's +5 a turn
    outpaces the chip.
  - The attempt-3 harness crash happens on base too.
- **Ch17** (style seeds 1-3, 6 attempts each, 13 distinct games: the seed does not move the dice, #647; before the floor): 17/18 won, base 18/18. First clean
  attempt 6, 5, none on both.
  - Seed 2, attempt 4 was **lost**: Eirika (0x01) died on turn 9 to a unit the board never
    showed (`unrevealed_killer`, 0% read).
  - That turn, plans built from the bait (charId 0x14 waiting on the boss's tile) outranked
    plans worth about 340 more in `value`, on a 0.09% first-phase win chance
    (`lookWin.won` 0.0008).
- **Ch17 with the win floor** (same start, seeds and attempts): **18/18 won**. Seed 2 attempt 4
  is now won on turn 12 (3 deaths, none of them Eirika; base: won turn 12, 3 deaths). First clean
  attempt 6, 5, none, as base. Seeds 1 and 3 were rerun and also won 6/6.
- **E_20** (attempt 2, seed 1) with the floor: **won on turn 42**, 335.3 CPU s (917387 frames).
  Attempt 1 is lost on turn 3 (`forecast_desync`) as on base.
- The unit test (`test_bot.lua`, rank block) fails on 6ec00962 and passes with the floor: a
  0.09% win chance does not outrank a plan worth 340 more, a win at `M.GONE` does, and above
  `M.GONE` the likelier win still leads.
- **CPU per player phase**, base and branch back to back (load 2.5-5):
  - E_20 attempt 1, the same game: 13.97 s on the branch, 14.03 s on base.
  - E_20 attempt 2: 331.4 s over 42 phases on the branch, 339.4 s over 46 on base. The
    branch's last turns run the bait's second phase.
  - Ch17 seed 1: 15.95 s on the branch, 17.15 s on base.
  - With the floor (2026-11-18, load 2-5): E_20 attempt 2 335.3 s (branch before: 331.4 s);
    Ch17 seed 2 attempts 1-6: 238.7, 128.2, 158.1, 147.3, 124.1, 160.1 s (base 261.5, 149.8, 174.0,
    170.6, 144.4, 182.7). Load differed between runs, so these are not paired.
