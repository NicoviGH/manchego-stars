---
id: 310
title: "The difficulty report fields the party that arrives, at the level it arrives at"
date: "2026-10-01"
section: "Combat System"
issues: [430, 367]
---

# The difficulty report fields the party that arrives, at the level it arrives at

`make difficulty`'s per-chapter report used to grade every chapter with the whole cast at its
join line. A ch06 cast table listed units that had not joined yet, at level 1, against enemies
at their real levels. That is #367's finding 3, and #430 step 1 fixes it.

**The party is the exp model's.** `exp_curve.entering(campaign, chapter_number)` returns the
units that have joined by that chapter and the typical (even-share) level each holds on
entering it, which is the previous hosted chapter's closing level. `load_field(leveled=True)`
fields exactly that party. The cast table prints each unit's level.

**A level becomes stats by simulating the engine's own level-ups.** `difficulty.level_up`
transcribes `CheckBattleUnitLevelUp`, including its re-roll of an empty level, which couples
the stats. `grown` runs 1001 seeded careers on the growth donor's growths, caps every level at
`CheckBattleUnitStatCaps`'s ceilings (class max, 60 HP, 30 Lck), and takes each stat's median.
Median over mean was measured (2026-10-01; Nicolas asked for the evidence rather than his
suggestion). Over 4001 simulated careers at the ch06 entry level, each stat's p10-p90 spread is
about +/-1-2 points, the distribution is close to symmetric, and mean and median sit within half
a point. The rounded mean differs from the median by a point in about one stat line in seven.
Against the metric averaged over every simulated career, the median line's durability error
averaged 0.13 rounds and the rounded mean's 0.14. Kill rates tied. The median wins narrowly, and
it is a value the dice actually produce.

**Neither point line is the metric's average near a breakpoint.** marty's ch06 durability
averages 1.77 rounds over the dice, and both point lines read 1.25. A minority of careers clear
a doubling threshold, and that minority moves the average. A per-stat median is a planning
line, and no single unit rolls exactly that.

**FE8's own party arrives the same way.** `vanilla_recruits` walks Eirika's route from the
Prologue to Ch6 and reads who joins from the decomp, assuming every recruit succeeds. A
playable character (pid 0x01-0x22) joins at its first ARMED load, because cutscene loads carry
no items. A blue load is on the field that chapter. A green or red load must be the target of a
talk event and fields from the next chapter, which is our own recruit convention too. Item grants
to a named character count (Eirika's Prologue Rapier); village gifts to whoever visits do not,
as they do not for our cast. Cross-checked against Serenes Forest's recruit, base-stat and
growth tables: all 14 recruits match on join level, bases and growths. One fine point: Lute
joins by a Ch4 village visit, and the derivation fields her for the whole of Ch4.

The exp model runs that party through vanilla's own force from each recruit's own join level
(`exp_curve.simulate`'s `vanilla_levels`). The report prints it as a cast table beside ours, and
the parity delta fields the best `deploy_limit` of each arriving party. The hand-curated
force-deploy table (Ch1 and Ch2 only) is gone.

**A recruit fights with the weapon the ROM gives it.** The unit YAML's `inventory:` where it
has one. Otherwise the placing roster entry's inventory (sahnar's Killing Edge), and otherwise
the join-LOAD's `CLASS_LOADOUT` kit (lupin's sword). Reading only the YAML scored lupin and
sahnar as weaponless. `difficulty.placed_entry` is now the one lookup for "the entry that
places this recruit". `exp_curve.join_level` reads its level from it.

**Unchanged.** The parity ratio (`enemy_pressure`) reads no party. It compares two enemy
forces against the fixed `YARDSTICK`, so this changes no verdict and no gate.
`player_combatant`'s default is still the join line, because `inject/chapters/ch01.py` sizes
the lord floor from it into the ROM, and `--lord-floor` reports that same line.
