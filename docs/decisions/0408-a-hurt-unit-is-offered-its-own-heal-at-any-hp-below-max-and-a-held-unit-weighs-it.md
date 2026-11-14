---
id: 408
title: "A hurt unit is offered its own heal at any HP below max, and a held unit weighs it"
date: "2026-11-13"
section: "Combat System"
issues: [510]
---

# A hurt unit is offered its own heal at any HP below max, and a held unit weighs it

Two gaps kept a unit from using its own Vulnerary. Both were found on vanilla runs replayed
on main (#510 comment 6866345084).

**1. The offer (bot.lua `mend`).** The planner was offered a unit's own heal only when the
unit was down at least the item's whole amount. The game allows it at any HP below max
(`CanUnitUseItem`). On vanilla Ch7, campaign 4005, the lord (Eirika, charId 1) was 9 down
with a 10-HP Vulnerary on turn 4. Every plan she was offered had her death at 71.5%, and
she died. **Now the planner's menu offers the heal whenever the game does.** `Bot.decide`
keeps its whole-amount rule.

**The price (planner.lua `score`, Nicolas approved, 2026-11-13).** HP the heal would restore
past max is thrown away with a use. It costs what a restored HP earns in the act's score
(`W.heal`). Each HP restored also closes `W.taken` of the judge's deficit, so a heal pays off
past `W.heal * amount / (2 * W.heal + W.taken)`: past 3 of a 10-HP Vulnerary for the careful
style (1.5, 2), past 3.3 for even and bold. `test_planner_prices_a_heal_thrown_away` pins it
for careful (1 and 2 HP down, kept; 4 and 6, used) and even (3 kept, 4 used).

**2. The heal swap (planner.lua, after the mend rounds).** The beam keeps the acts that
score best on their own, so a march comes first. The mend tries other acts only for a unit
at risk. So a hurt unit that a plan holds out of reach never had its heal judged. On vanilla
Ch8, campaign 4004, the thief (Colm, charId 9) was at 6 of 18 HP from turn 4. He was offered
his Vulnerary on every player phase from 5 to 16 and used it on 16. **Now one more plan, kind
`heal`, is judged:** the best plan, with each hurt unit it leaves waiting given its own heal
on the same tile, read on the HP the plan has left it so far. A unit is swapped in only where
the plan gains by it as the judge reads it (the act's score plus the deficit it closes),
the same break-even as above, and the rank decides. Each act is rebuilt through one helper
(`rebuild`), which the goal, noseize and mend plans now share. The swap costs one judged plan
in the decisions where it finds a heal: 3 of 134 judged plans on the rerun of Ch7 (`heal7b`), 6 of 162
on Ch8, 5 of 179 on Ch9.

**3. A heal earlier in the plan stays (planner.lua `score`).** Found while testing the swap.
Every act started from its unit's HP on the start board, and `extend` wrote that back. So when
a staff healed a unit earlier in the plan and the unit then waited, the plan set it back to
its old HP, and the judge read the heal as nothing. An act now starts from the HP the plan
has given its unit. An attack keeps its own reading: the counter's ways add the plan's
heals back, as before.

**ADR 0396's tests.** The quantities are the game's: the HP restored and the item's amount.
The change removes a ban the game does not make. Both parts are offers, and the rank
decides. It adds no rank key and nothing in the cap, so it does not repeat ADR 0400's freeze.
It names no unit or chapter.

**What the runs say** (one attempt each, branch against main's replay of the same start):

| Start | Main | This change |
|---|---|---|
| Ch7 4005 (tags `replay7`, `heal7`) | lost on turn 4 | won clean in 14 turns, no death |
| Ch8 4004 (`replay8`, `heal8`) | won in 16, chests `stalled` | won in 18, no death; Colm heals on turns 6 and 11 and reaches (3,16) (main stopped at (7,16)); chests `never_offered` |
| Ch9 4006 (`replay9`, `heal9`) | won in 19, Amelia `left_map` | won in 18, no death; Amelia `killed_before_talk` |

- After the review's fixes (part 3 and the swap's break-even), the three runs play the same
  acts (tags `heal7b`, `heal8b`, `heal9b`; `acts_hash` unchanged).
- On Ch8 the chests are still missed. On turn 8 every plan that sends Colm south is over the
  cap (76.7%), and he goes back north twice before the south road. The win comes 2 turns
  later because he keeps nearing his goal, so the rule of ADR 0403 does not end the wait.
- On Ch9 the lord reaches Amelia (charId 18) on turn 11. The Talk plan is judged at 87.2%,
  over the cap. Every other plan forfeits her: the planner reads a 95.8% chance that the
  lord's counter kills her.
- Both remaining misses are an enemy on the road: the escort case (item E of the #510 plan).
  This change neither causes nor fixes them.

**Untested:**
- Other styles, and the frozen suite. The suite runs before the bot's reading is next relied
  on, not for this PR (AGENTS.md).
