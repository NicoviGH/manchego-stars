---
id: 487
title: "The mend tries a struck unit's own act holding the weapon that spares a recruit"
date: "2026-11-28"
section: "Combat System"
issues: [730, 764, 510]
---

# The mend tries a struck unit's own act holding the weapon that spares a recruit

**Decided (2026-11-28, #764 fix order item 2: Ch10's Amelia; #730).** Adds one act to the mend;
no scoring change, no new weight. It is ADR 0451's and ADR 0453's gentle acts, made for the act
the plan chose.

**The gap.** The menus offer `M.GENTLE` (2) gentle waits and 2 gentle strikes per unit, the
cheapest by `sparingPicks`' cost. That cost reads every enemy that reaches the tile, while the
judged phase plays the AI's real moves, so the two can disagree about which tile is good. Vanilla
Ch10 s4005 attempt 1 (R5's `r5a10`), turn 5: every admitted plan had Franz (0x04) strike the
pirate at (1,19) holding his Iron Lance (0x14). Amelia (0x12) attacked him for 0 damage, and his
counter did 16 against her 16 HP. His Iron Sword (0x01) does about 15 and does not double her.
The two gentle strikes offered were on another pirate from (2,16) and (3,17), so the sword
strike from (1,19) was never judged. The mend tried Franz's menu, and every act on it that spared
her was over the cap (0.56).

Across R5's 10 unclean Ch10 tries (a Sonnet reader, read-only), Amelia was missed in 9. Our own
counter killed her in 6 of them (Seth, 0x02, three times; Franz twice; Forde, 0x10, once, then
his attack). In 3 the talker's trip was priced away by its route loss; that is a separate fix.

**What changed.** When the mend repairs a recruit our counter may kill, each unit it strikes first
tries its own act in the plan holding the weapon whose counter spares it (`Bot.sparingTwin`), then
its menu as before. The twin is `sparingPicks` on that one spot, with no cap: the same weapon
test and cost as the menu's (the recruit's fall plus the unit's own death there, and a weapon the
attack can break is never the sparing one). A plain wait and a strike from a pick are twinned. A
gentle act (already holding a slot), a Canto wait and a wall's strike are not. The two spot
builders are shared with the menus (`M.waitSpot`, `M.strikeSpot`). They hang off M because
bot.lua's chunk has one free local slot.

**And the mend goes on past the cap while our counter may fell a recruit.** A round that brings
the plan under the cap with a recruit still felled in it is not the last, as for a theft (ADR
0483), up to `M.MEND_ROUNDS` (3). The first replay with the twin alone (`t730a`) showed why: on
turn 5 the first round started from the beam's plan, which was over the cap (0.556) for another
unit. That round made the admitted plans, all with Franz's lance strike, and judged his sword
strike only from the over-cap base (0.56, so over the cap). The round test then stopped, since
the best was admitted.

**The forfeit stays yes or no.** Any chance over `Goals.DUST` forfeits the recruit. In `t730a`
the sword strike still read forfeits 1 (which blow could still kill her, a crit or another
striker, is not read from the trace), so it forfeits her too. Among admitted plans it wins on the
plan's value (the recruit's goal chance in the goals' term), not on the forfeit count. That is
ADR 0451's reading, unchanged here.

**Cost.** At most one more judged phase per struck unit per mend round, and up to two more mend
rounds, only on a plan whose counter may fell a recruit.

**Proof.** `test_bot.lua` "sparing twin": with the cap at 0 the menu holds no gentle act. On main
the plan played strikes holding slot 0 and forfeits the recruit. Now it strikes holding slot 2
and forfeits nothing. Its second case adds a unit that dies where the beam leaves it; without the
round rule the plan played keeps the slot-0 strike. Each fails without its line. One replay of
Ch10 s4005 attempt 1: on the PR.
