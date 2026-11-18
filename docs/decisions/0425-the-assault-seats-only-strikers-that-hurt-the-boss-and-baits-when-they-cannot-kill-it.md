---
id: 425
title: "The assault seats only strikers that hurt the boss, and baits when they cannot kill it"
date: "2026-11-18"
section: "Combat System"
issues: [641, 510]
---
# The assault seats only strikers that hurt the boss, and baits when they cannot kill it

**Accepted (2026-11-18, #641).** In vanilla E_20 the playtest bot never broke Morva (charId
0x41). Every judged throne assault seated Ross (0x07), Vanessa (0x06) and Garcia (0x0A) beside
Ephraim (0x0F). Their blows deal her nothing, and each one cost a whole death (`sum_die` 3.0).
No unit was offered a wait on her strike tile, so the plan the guide plays (stand there, let
her strike, finish her the next turn) was never judged. The diagnosis and the design are on
#641 (comments 6979929417 and 6980453726).

**The rule** (`tools/playtest/planner.lua`, the assault; `bot.lua` `M.waitAt`).
- **A striker is seated only when it deals damage:** its expected damage on the boss is above
  `M.DUST`. A blow that cannot hurt the boss buys its counter and nothing else.
- **When the seated strikers do not count the boss dead this phase, the bait is judged too.**
  The heaviest striker waits on its heaviest strike tile, and every other unit holds
  (`complete`). The plan has kind `bait`. It is one more plan for the rank, judged like any
  other: no ban, and no weight beyond its outcomes (ADR 0396). No march or hold offers that
  tile, so the planner asks `Bot.waitAt` for the wait. That wait is told its tile's ally and its
  exposure, as `Bot.mendAt`'s heal is (ADR 0408). With a single striker there is no assault
  (the beam already has that plan), but there can still be a bait.
- **The lookahead's second phase reads the win** (`M.secondRead`'s fourth value). The win is
  the boss killed by the army's reply, at the kill's chance, or felled by our counter to its own
  strike in the second phase. The same predicate as the judge's `fell` names the boss (`endsIn`:
  a Defeat Boss map's boss, or a Rout's last red unit). The win goes into the goals' own term
  (`goalTerm`) at `GAMMA` of a first-phase win: `fell' = 1 - (1 - fell)(1 - GAMMA * won)`. It
  is one owner and no new formula. `rank.complete` stays the first phase's chance.
- **No counter-damage weight.** The brief allowed one if the bait could not reach the
  lookahead. The runs did not need it. In E_20 the bait ranked first on progress (0.29 against
  0 for every hold) with no lookahead at all: Ephraim already stood inside Morva's danger zone,
  so no `boss` trigger fired. Nothing here weights counter damage.

**Proof** (vanilla, campaign `bag1-heal4-heal1-lap4e-cs-s4006` unless named; base `ddaae8c5`):
- Unit test `test_planner_assault_baits` (`test_bot.lua`): a Guard Tile boss, one striker that
  falls short of the kill, three range-2 units that deal 0. No 0-damage unit is seated, the bait
  is played, and the win row carries GAMMA of the reply's kill. It fails on `4cf39e1b` and on the
  unfixed branch, and so do the new `secondRead` checks. With the fold removed, the bait is still
  played in the test, on progress; only the win's checks fail.
- E_20, attempts 1-2, seed 1. Attempt 1 is lost on turn 3 on both (`forecast_desync`). Attempt 2
  is the same game on base and branch up to turn 41. On turn 41 the branch plays the bait:
  Ephraim waits on 11,12 at 51 HP and Morva strikes him (51 to 15, she 62 to 42). He withdraws
  and heals, and on turn 44 his Siegmund kills her at 54 HP. The branch **wins on turn 45**; base
  is `stuck` on turn 47. Both had 7 deaths. No assault was judged at `sum_die` 3.0.
- I_14 (`lap4p-cs-s4006`, from 27, attempts 1-3; only three styles exist): unchanged, no clear on
  either. On attempt 2 Ephraim baits Vigarde (0x6B) three times. Vigarde loses 17 HP, then 0, then
  17, and the throne heals 5 a turn. Every assault reads a death at 0.87-0.96. The attempt-3 crash
  (`could not perform attack`, turn 10) happens on base too.
- Ch17, seeds 1-3, 6 attempts each: 18/18 won on both. The first clean attempt is 6, 5 and none
  on both. The bait was played 5 times. Blue deaths were 6 on base and 8 on the branch. The two
  extra deaths are one game (attempt 1 has the same dice on seeds 1 and 3): Myrrh (0x1E) baits the
  boss under `bold` and dies to it at a 2.2% read (`rng_tail`).
- CPU per player phase, base and branch run back to back (load 4-6): Ch17 16.62 s and 16.62 s
  over 200 and 202 player phases. E_20 7.59 s and 7.90 s; I_14 12.32 s and 11.97 s.
