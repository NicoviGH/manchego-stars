---
id: 314
title: "fe_combat reads the 2RN hit and the crit"
date: "2026-10-02"
section: "Combat System"
issues: [430]
---

# fe_combat reads the 2RN hit and the crit

ADR 0312 found that `fe_combat`'s metrics read the displayed hit and no crit, while the
cartridge rolls hit on `Roll2RN` and crit on 1RN at x3 (`BattleGenerateHitAttributes`,
bmbattle.c l.1008-1039). Every `make difficulty` reading and the parity ratio sat on that
model. #430 step 1 fixes the instrument before step 3 re-measures anything.

**One strike, in `fe_combat`.** `true_hit` and `crit_rate` moved from `danger_map` into
`fe_combat`. `expected_hits` is strikes x P(hit) on 2RN x (1 + 2 x P(crit)), and
`damage_per_round` is damage x `expected_hits`. `danger_map.strike` reads the same two
functions. Its output is byte-identical (`danger_map ch06 --boats` diffed before and after).

**The clear-load floor divides by `expected_hits`.** #285's floor scores an undentable
unit as if each hit chipped 1, and it must share `rounds_to_kill`'s divisor to stay
continuous at the damage boundary. That divisor now includes crit.

**`bulk_durability` keeps its own model.** It is the lord's worst case, every hit
connecting, and it still counts no crit.

**What moved.** A 2RN roll pulls a high displayed rate up and a low one down: 77 shown is
90% true, 45 shown is 40%. Accurate attackers gain against inaccurate heavy hitters, and
crit-weapon units gain on top. Joshua's Killing Edge takes FE8 Ch5's threat ceiling from 21.4
to 38.9. The instrument alone moves the curve's ratios by at most 0.10, before the two unit fixes
below:

| chapter | threat/slot | clear-load/slot |
|---|---|---|
| ch00 | x1.13 -> x1.23 | x1.00 -> x0.96 |
| ch03 | x1.03 -> x1.10 | x1.00 -> x1.00 |
| ch04 | x1.15 -> x1.16 | x1.19 -> x1.16 |
| ch05 | x1.04 -> x1.04 | x1.03 -> x1.05 |
| ch01, ch02, ch06 | unchanged | unchanged |

**Two units were off parity under the true model, and both now match.** Both came from the
2RN alone; neither crits.
- ch00: Sephek's Steel Sword hit the yardstick for 7 at 77 shown (90% true), 6.4 a round,
  against FE8 Prologue's ceiling, O'Neill, at 9 for 50 shown (50.5%), 4.5. That is 1.41x
  against the 1.25x outlier bar. Sephek now carries an Iron Sword: 4.0, and ch00's threat
  reads x0.99, closer than the x1.13 it was locked at. He still falls in 1.9 yardstick
  rounds.
- ch03: the Grell's Evil Eye at L12 read 8.9 against Bazba's 6.1 (1.45x). At L8 it reads
  6.8 (1.10x). Personal HP 15 -> 17 keeps him at 36 HP / Def 8, so he still takes 3.5 rounds
  to Bazba's 3.5. ch03 reads x1.02.

Restoring a measured vanilla ratio follows from FE parity, so a lock does not hold these
back.

Marty's ch06 durability falls from 1.25 to 1.18 rounds on the median line and from 1.77 to
1.55 over the dice. Ravisin against Saar stays inside its band (21.8 against 19.7, 1.10x).
