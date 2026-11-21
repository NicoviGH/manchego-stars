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
`arrivals_seen`, which stays the screen's own record, never a fogged arrival). A unit seen by
more than one failed attempt keeps the LATEST attempt's sighting: the freshest evidence (a
scripted arrival agrees anyway). `botrun.lua` passes to the planner those the game still owes us
(the record's `owed`, the game's own Talk list less the party) as `opts.pending`; a run whose api
has no `recruits()` cannot say what is owed, so a memory it is given is a fault and fails loudly.
`bot.lua`'s `recruitsOf` treats each as a recruit on the board that is not there yet, while no
live unit of that character is on the field (or carried) and the turn is not past the remembered
one. `arrivals_seen` records `boardTurn`, the first player turn the unit stood on the board:
T+1 for an enemy-phase arrival of turn T, T itself for a start-of-turn one. The goal holds while
the turn is before it (a record without it reads `turn + 1`). A unit not on the board by then
(killed before it, a different route) is not coming this attempt and is no goal after: that is
the decided bound, not a loose thread.

- its talkers are the units the game's own check lets Talk it (`sight.canTalk`, the Talk
  command's `CheckForCharacterEvents` on the two charIds and the event flags; it reads no unit,
  so asking it before the unit exists is the same question the game answers once it does);
- its tile is the tile a talker can walk to that is nearest where it arrived (one march field
  per talker from where it stands, `sight.march`, the game's own movement field, memoised by the
  sight per class and tile): a wyvern rider lands over a cliff no one walks to (E_13's arrival
  tile is unreachable for every foot unit), and a goal on such a tile has no chance, so no pull;
- `goals.lua` lists it as `recruit:arrival:<charId>`; the ledger, the forfeits and the Seize
  skip then treat it as any open recruit, so the win is put off by the quantity the rank already
  reads (the goal forfeited). ADR 0403's stall rule does not apply to it: a pending goal cannot
  close before its turn, so a quiet count of it (nobody can near a tile before the unit comes)
  never marks its row stalled (`goals.lua`'s ledger); the turn bound above is its end.

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
replay, per ADR 0430. It was played on the first version of the code, before the review's
changes (the board turn, the latest sighting, the talker's own march field for the meeting
tile, the stall exemption); Cormag's arrival (turn 5) and the Talk (turn 6) are not near any of
their edges, and each has a unit test that fails without it. A replay on the reviewed code
(`cormag3`, same start, attempts 2) gave the same: attempt 2 won clean on turn 7, Eirika talked
to Cormag on turn 6 and he joined. (An earlier try timed out with no result on the loaded
machine. The last fix, the board turn, cannot change this game: Cormag arrives at the start of
turn 5 and is on the board from then.) The same may help Amelia (E_9) and Marisa (E_10);
untested.
