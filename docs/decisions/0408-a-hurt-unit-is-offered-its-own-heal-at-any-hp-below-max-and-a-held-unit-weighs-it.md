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
past max is thrown away with a use. It costs what a restored HP earns (`W.heal`). Unpriced,
the new offer spent three uses for 9 HP in a design probe run (tag `wprobeB`, read by the designing subagent, not re-read here). With the price, the PR's Ch7 run
plays 7 heals that restore 65 of 70 HP, and no single heal throws away more than 2.

**2. The heal swap (planner.lua, after the mend rounds).** The beam keeps the acts that
score best on their own, so a march comes first. The mend tries other acts only for a unit
at risk. So a hurt unit that a plan holds out of reach never had its heal judged. On vanilla
Ch8, campaign 4004, the thief (Colm, charId 9) was at 6 of 18 HP from turn 4. He was offered
his Vulnerary on every player phase from 5 to 16 and used it on 16. **Now one more plan, kind
`heal`, is judged:** the best plan, with each hurt unit it leaves waiting given its own heal
on the same tile. A unit is swapped in only where the heal's own score is above zero, and
the rank decides. This costs one judged plan in the decisions where a swap exists: 2 of 133
judged plans on the PR's Ch7 run, 7 of 163 on Ch8, 5 of 179 on Ch9.

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

- On Ch8 the chests are still missed. On turn 8 every plan that sends Colm south is over the
  cap (76.7%), and he goes back north twice before the south road. The win comes 2 turns
  later because he keeps nearing his goal, so the rule of ADR 0403 does not end the wait.
- On Ch9 the lord reaches Amelia (charId 18) on turn 11. The Talk plan is judged at 87.2%,
  over the cap. Every other plan forfeits her: the planner reads a 95.8% chance that the
  lord's counter kills her.
- Both remaining misses are an enemy on the road: the escort case (item E of the #510 plan).
  This change neither causes nor fixes them.

**Untested:** other styles, and the frozen suite, which runs before the bot's reading is
next relied on, not for this PR (AGENTS.md).
