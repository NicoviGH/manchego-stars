---
id: 436
title: "An owed recruit a retry saw arrive is a goal before it arrives"
date: "2026-11-20"
section: "Combat System"
issues: [510, 683]
---

# An owed recruit a retry saw arrive is a goal before it arrives

**Decided (the #683 fix, #640 batch lap), #510 step 9.** Extends ADR 0386 (a retry remembers what
earlier attempts showed on screen) and ADR 0399 (`style.memory`).

**The fault.** The planner builds a recruit goal only for a unit on the board (`goals.lua`). A
recruit that arrives mid-chapter (vanilla Eirika-route E_13's Cormag, turn 5, Talk by Eirika
only) therefore gave no reason to put the Defeat Boss win off, and 45 of 85 games won before he
came.

**The rule.** From attempt 2 on, `campaign.lua` hands the play `style.memory.arrivals`: each unit
an earlier failed attempt of this chapter start saw arrive, once (`charId`, tile, turn: botrun's
`arrivals_seen`, which stays the screen's own record, never a fogged arrival). `botrun.lua`
passes to the planner those the game still owes us (the record's `owed`, the game's own Talk
list less the party) as `opts.pending`. `bot.lua`'s `recruitsOf` treats each as a recruit on the
board that is not there yet, while no unit of that character is on the board and the turn is
before the remembered one:

- its talkers are the units the game's own check lets Talk it (`sight.canTalk`, the Talk
  command's `CheckForCharacterEvents` on the two charIds and the event flags; it reads no unit,
  so asking it before the unit exists is the same question the game answers once it does);
- its tile is the tile a talker can walk to that is nearest where it arrived (the game's own
  movement field, `sight.turnsTo`): a wyvern rider lands over a cliff no one walks to (E_13's
  arrival tile is unreachable for every foot unit), and a goal on such a tile has no chance, so
  no pull;
- `goals.lua` lists it as `recruit:arrival:<charId>`; the ledger, the forfeits and the Seize
  skip then treat it as any open recruit, so the win is put off by the quantity the rank already
  reads (the goal forfeited), with no new rule.

Attempt 1, and any attempt played alone, has no memory and is unchanged (ADR 0385: verdicts
measure attempt 1 only).

**Against ADR 0396's five tests.** (1) The quantity is the recruit goal's chance and its
forfeit, both already computed. (2) An ordering, not a ban: a plan that closes the goal ranks
lower. The one game rule used is the Talk check, cited above. (3) Every objective: a pending
recruit is an open goal on Rout, Seize, Defend or fog alike. (4) It repeats no ordering: no goal
existed before the unit did. (5) No unit, chapter or turn is named in the code; they are the
data.

**Measured (2026-11-20).** Vanilla E_13, campaign `cs-s4008` from its chapter-13 start,
attempts 2 (`resume --tag cormag1b`). Before: attempt 2 won on turn 4 with Cormag never reached
(`cormag1`). After: attempt 2 won clean on turn 7, Eirika talking to Cormag on turn 6. A single
replay, per ADR 0430. The same may help Amelia (E_9) and Marisa (E_10); untested.
