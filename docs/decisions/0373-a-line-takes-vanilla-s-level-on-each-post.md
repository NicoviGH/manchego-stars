---
id: 373
title: "Line units take vanilla's levels, so the exp is spread as vanilla spread it"
date: "2026-10-28"
section: "Combat System"
issues: [545, 510]
---

# Line units take vanilla's levels, so the exp is spread as vanilla spread it

**Every non-boss enemy now carries the level of the vanilla unit it stands in for**, as a
per-body `levels:` list in `positions` order. This is the foundation, and epic #510 adjusts it
from there if its rebuilt model calls for it (Nicolas, 2026-10-28: "I'd rather work from vanilla
levels as the foundation").

**Why (Nicolas):** a line's levels are how vanilla spreads a chapter's exp across the whole party,
so every member has a fair shot at levelling. A flat line that leaves the exp to the boss defeats
that. The class swaps each chapter records (goblin-skinned Fighters for Brigands, and so on) stay
as they are: this record is about levels only.

**Found by #545**, while pricing Ravisin's kill. ch05's line was a flat `level: 5` where vanilla
Ch5 spreads it from L4 to L6, and nothing recorded why. That is the accidental drift ADR 0049
rules out. The flat line paid the party entering ch05 11.7 exp less than vanilla's, and Ravisin's
kill paid 13.8 more than Saar's, so the chapter total matched while its exp sat in the boss. A
sweep of every hosted chapter found the same drift elsewhere:

| chapter | entry | was | now (vanilla's) |
|---|---|---|---|
| ch00 | caravan-guard | 2, 2 | 1, 2 (vanilla's two Fighters) |
| ch01 | goblin-spear | 1, 1, 1 | 2, 2, 3 |
| ch01 | goblin-axe | 1, 1, 1 | 2, 2, 2 |
| ch01 | goblin-reinforcements (fighter, fighter, soldier) | 1, 1, 1 | 1, 1, 2 |
| ch04 | mogall | 1, 1, 1, 1 | 1, 2, 1, 1 |
| ch04 | bonewalker | 3, 3, 3 | 2, 3, 3 |
| ch04 | mauthedoog (the wolf pack) | 2 ×6 | 2, 2, 2, 1, 1, 1 |
| ch05 | risen-spear | 5, 5, 5, 5 | 6, 6, 5, 5 |
| ch05 | tomb-reaver | all 5 | 5, 5, 5, 5, 4, 5, 4, 5 |
| ch05 | risen-spear-reinf | 5, 5 | 4, 4 |
| ch05 | bone-archer-reinf | 5, 5 | 6, 6 |

ch01's own header claimed vanilla's line was "lv1". `ch1-eventudefs.h` says L2/L2/L3 Soldiers
and L2/L2/L2 Fighters. ch02, ch03 and ch07 already matched. ch06 matches once its class swaps are
counted: its extra Cavaliers and Soldiers carry the levels of the Fighters and Mercenaries they
replace.

**How a body's vanilla level was found.** By the vanilla unit it mirrors. In ch01, ch05 and ch00
that is the `donor:` post, unambiguous through `difficulty.resolve_donor` (ch01's reinforcement
donors and ch06's two Difficult riders were listed out of body order, so they were reordered to
match; each pair shares one AI, so the ROM is unchanged). In ch04 a donor is
borrowed for its AI, and a reinforcement's donor tile can be a line unit's post, so ch04 was
checked class by class against vanilla's whole force instead. Its reinforcement levels cite
vanilla's reinforcement arrays and already matched.

**ch04's wolf pack takes the levels of the Revenants it replaced.** Vanilla Ch4 fields 12
Revenants: L1×3, L2×7, L3×2. Ours keep 6 as Revenants (the line's two L3s, and the four L2s of
vanilla's reinforcement pack, 088B4C24), and the 6 Mauthe Doog of ADR 0049 replace the rest: the
line's three L2s, on (7,9), (5,13) and (10,12), and its three L1s, on (5,8), (0,4) and (11,4). The pack was all L2, so it now reads `levels: [2, 2, 2, 1, 1, 1]`. Its first tile
is Lupin's, and the ROM places him at his own level there, so the wolves the ROM fields are
L2, L2, L1, L1, L1 (`ch04_turn2_reveal_rows` now reads per-body levels). The pack's levels are
also its levels as parley allies, so Nicolas will revisit them with #510's model and the
custom lord classes (2026-10-28).

**What stays above vanilla on purpose is Ravisin's kill.** She is a Druid, a PROMOTED class, which
FE8's exp math counts as 20 levels higher (`GetUnitExpLevel`, `GetUnitPowerLevel`). Her kill
tops the 100-exp-per-battle cap (`GetBattleUnitExpGain`) with or without CA_BOSS (ADR 0372),
where Saar's pays about 80. Her class is settled (ADR 0043: a caster boss cannot be an armour
wall), and changing it would redo her stat line and art for about 14 exp, about 1.5% of ch05.

**Bosses keep their levels.** A boss's level carries its hand-tuned personal line (ADR 0372), so
the grell (L8 on Bazba's L6 post), Sephek and Ravisin are not moved by this record.

**What it moved.** No parity verdict changed (`make verdict-diff`). The pacing doc's exp pots:
ch00 148 → 147 (twin 147), ch01 370 → 378 (twin 378), ch05 895 → 906 (twin 893), and ch04 818 →
808, its wolf pack's three L1s. ch01, already OFF as harder than its twin, reads a
little harder: threat x1.10 → x1.14 and clear-load x1.56 → x1.62 in every mode. ch05 Tutorial's
clear-load moved x1.13 → x1.14, and ch04 Difficult's threat x2.19 → x2.16 and clear-load
x1.47 → x1.45 (the wolves).

**ch01's lord floor rises with it.** The build gives the chosen lead a chapter-start floor solved
against ch01's enemies (`inject.chapters.ch01.lord_floor_rows`, #45). Against vanilla's L2-3 line
the glass leads need more: Marty and Meesmickle +7 → +10 HP, Prof. RBG +3 → +7, Rootis +1 → +4,
Sclorbo +5 → +8, Pinky +0 → +1 HP, and Braulo now takes +1 Def. `mirror%` for ch01 goes from 3 of
10 to 10 of 10.
