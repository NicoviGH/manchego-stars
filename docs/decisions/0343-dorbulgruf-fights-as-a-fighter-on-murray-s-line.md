---
id: 343
title: "Dorbulgruf fights as a Fighter, on a line that keeps him Murray"
date: "2026-10-11"
section: "Combat System"
issues: [27]
---

# Dorbulgruf fights as a Fighter, on a line that keeps him Murray

Nicolas, 2026-10-11. **ch07's boss is a Lv12 Fighter with a Steel Axe, a Hand Axe and a Hero Crest
drop**, standing in for vanilla Ch7's Murray (Lv12 Cavalier, Steel Sword, Javelin, Knight Crest).
Wolfram's axe-bite beat needs an axe, which a Cavalier cannot hold, and the dwarf stays off a horse.

**The class swap alone made him a much easier boss.** He rides Murray's slot (ENEMY_BASE_SLOT) and so
inherits Murray's personal line, but that line was tuned for Cavalier bases. On Fighter bases it is
Def 3 instead of 7, and the Steel Axe's weight 15 on Con 11 cuts his attack speed from 12 to 8, so he
never doubles. Measured against ch07's arriving party:

| | party-rounds to kill | rounds to drop a unit | units dropped in one round |
|---|---|---|---|
| Murray (twin) | 0.74 | 1.51 | 4 of 10 |
| Fighter on Murray's line | 0.41 | 1.47 | 0 of 10 |
| **Fighter, Def+3 and Con+4** | **0.75** | **1.22** | **4 of 10** |

He keeps the Steel Axe (the axe-bite beat names it) and gains Con instead of switching to an Iron
Axe: a stocky dwarf carrying an axe he can swing. He hits harder per blow than Murray, which is the
axe's trade for the sword's hit rate. ch07 holds parity at x1.00 threat and x1.10 clear-load, the
same as the twin-exact version, and is locked.

**The line reaches the ROM through `SLOT_PERSONAL_SOURCES`** (`inject/raw_pids.py`), which writes a
chapter YAML's whole `personal:` line over a vanilla slot's own. Until now a slot-riding boss could
only keep its character's line, and `check_personal_line_injection_routes` rejected a `personal:`
block on one; the gate now accepts it when the slot has that route. No weapon ranks change: FE8 takes
each rank from the class unless the character sets it (`bmunit.c` UnitLoadStatsFromCharacter), and
Murray sets only sword and lance, so the axe rank is the Fighter's D.

The slot is shared: vanilla's late-game Murray (Lv20 Cavalier, `UnitDef_088D1448`, on Lyon's side)
reads the same row, so a chapter that ever reuses that vanilla table inherits this line too. None does.
Verified in the built source: Murray's row reads HP 12 / Pow 3 / Skl 7 / Spd 5 / Def 4 / Res 6 /
Lck 7 / Con 4, and ch07's boss deploys as `CLASS_FIGHTER` Lv12 with Steel Axe, Hand Axe, Hero Crest.
