---
id: 343
title: "Dorbulgruf fights as a Fighter, on Gheb's line"
date: "2026-10-11"
section: "Combat System"
issues: [27]
---

# Dorbulgruf fights as a Fighter, on Gheb's line

Nicolas, 2026-10-11. **ch07's boss is a Lv12 Fighter with a Steel Axe, a Hand Axe and a Hero Crest
drop**, standing in for vanilla Ch7's Murray (Lv12 Cavalier, Steel Sword, Javelin, Knight Crest).
Wolfram's axe-bite beat needs an axe, which a Cavalier cannot hold, and the dwarf stays off a horse.

**The class swap alone made him a much easier boss, so he takes Gheb's line.** He rides Murray's slot
(ENEMY_BASE_SLOT) and so inherits Murray's personal line, but that line was tuned for Cavalier bases.
On Fighter bases it is Def 3 instead of 7, and the Steel Axe's weight 15 on Con 11 cuts his attack
speed from 12 to 8, so he never doubles. Rather than invent a correction, every vanilla boss line that
fights with an axe was measured on him, against ch07's arriving party:

| line on a Lv12 Fighter, Steel Axe | party-rounds to kill | rounds to drop a unit | units dropped in one round |
|---|---|---|---|
| Murray on his own Cavalier (the twin) | 0.74 | 1.51 | 4 of 10 |
| Murray's line | 0.41 | 1.47 | 0 of 10 |
| Bone / Bazba (Ch2 Brigands) / O'Neill (Prologue Fighter) | 0.15–0.23 | 1.94–2.29 | 0 of 10 |
| Binks (promoted Warrior) | 0.63 | 1.41 | 3 of 10 |
| **Gheb (promoted Warrior), verbatim** | **0.69** | **1.50** | **4 of 10** |

No unpromoted axe boss sits at Murray's tier; Gheb's line, unchanged, lands on him (Nicolas: "it's
more native"). It makes him a slow, armoured heavy hitter (HP 46, Str 21, Def 12, Spd 7) where Murray
doubles, which suits the dwarf. A hand-tuned alternative (Murray's line plus Def+3 / Con+4, 0.75 /
1.22 / 4) measured as close but invents its numbers. ch07 holds parity at x0.95 threat and x1.09
clear-load and is locked. Gheb's own slot is untouched, free for whichever chapter fields him.

**The line reaches the ROM through `SLOT_PERSONAL_SOURCES`** (`inject/raw_pids.py`), which writes a
chapter YAML's whole `personal:` line over a vanilla slot's own. Until now a slot-riding boss could
only keep its character's line, and `check_personal_line_injection_routes` rejected a `personal:`
block on one; the gate now accepts it when the slot has that route. No weapon ranks change: FE8 takes
each rank from the class unless the character sets it (`bmunit.c` UnitLoadStatsFromCharacter), and
Murray sets only sword and lance, so the axe rank is the Fighter's D.

The slot is shared: vanilla's late-game Murray (Lv20 Cavalier, `UnitDef_088D1448`, on Lyon's side)
reads the same row, so a chapter that ever reuses that vanilla table inherits this line too. None does.
Verified in the built source: Murray's row reads Gheb's HP 17 / Pow 10 / Skl 3 / Spd 0 / Def 8 / Res 5 /
Lck 1 / Con 3, and ch07's boss deploys as `CLASS_FIGHTER` Lv12 with Steel Axe, Hand Axe, Hero Crest.
