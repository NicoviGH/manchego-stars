---
id: 311
title: "The difficulty report reads its absolute metrics over the dice"
date: "2026-10-01"
section: "Combat System"
issues: [430]
---

# The difficulty report reads its absolute metrics over the dice

ADR 0310 grows a levelled unit to a per-stat median line. That line is a planning number, and
no single unit rolls it. Near a doubling breakpoint it misreads the metric a party actually
meets: marty's ch06 durability is 1.25 rounds on the line and about 1.77 averaged over the
dice. A minority of careers clear the breakpoint, and they move the average.

**Every absolute metric is scored once per simulated career.** `careers` returns the
GROWTH_TRIALS stat lines `grown` takes its medians from, from the same seeded RNG, so the
median line has not moved. `dice_profile` scores one unit per career: durability on open
ground and in a forest, best kill rate against the line, fastest kill of any boss.
`dice_party` combines the fielded units career by career into throughput, min durability and
carry. Before pairing, it shuffles each unit's careers on a seed of its own name. The units
share the growth RNG's seed, so pairing career i with career i would correlate their luck. A
unit that has not levelled has one career, and it appears in every pairing.

**Each reading is an average plus a bad-luck figure.** Bad luck is the career that 10% of
careers do worse than (`BAD_LUCK_PERCENTILE`): the low end for durability and kill rate, the
high end for rounds to kill a boss. The cast tables, the party line and the vanilla parity
delta print both. The delta compares averages.

**What stays on the median line.** The stat columns of the cast tables, the choice of which
units field (`_best_field`), the unit named as carry, and the lord x team sweep. Those are
planning reads. `--lord-floor` and the injector still read the join line (ADR 0310).

**Precision.** 1001 careers give marty's ch06 average a standard error of 0.017 rounds. The
seeded reading is 1.74; at 4001 careers it reads 1.76 to 1.77 depending on the seed. The
report prints one decimal, so 1001 careers is enough.

**Cost.** Most careers repeat stats, though rarely a whole line, so `dice_profile` keys each
half of the fight on the stats `fe_combat` reads for it. Being hit reads Def, Res, Spd, Con
and Lck, and HP only divides. Hitting reads Pow, Skl, Spd, Con and Lck. A ch06 report takes
about 7 s, against about 4 s on the median line and about 19 s unkeyed.
`test_the_keyed_profile_matches_the_plain_metrics` fails if `fe_combat` starts reading another
stat.

**Where the dice moved a reading (ch00-ch06, 2026-10-01).** ch00 and ch01 do not move,
because nobody has levelled yet. ch03's throughput was understated: 5.78 on the line, 6.10
averaged. In ch06, vanilla's min durability falls from 1.1 to 1.0, with a bad-luck figure of
0.7. Our margin over vanilla on that metric widens from +0.1 to +0.4. No verdict or gate
changes, because `enemy_pressure` reads no party.
