---
id: 473
title: "A Talk job is worth its best meeting, and the forecast plays a Rogue's locks"
date: "2026-11-25"
section: "Combat System"
issues: [766, 775, 764, 510]
---

# A Talk job is worth its best meeting, and the forecast plays a Rogue's locks

**Decided (2026-11-25, #766 and its sub-issue #775, R2 in #764's plan).** It builds on ADR 0471
(the stage job: a talker is sent where it meets the recruit on his way).

## The Talk job is worth its best meeting, not its first (#766)

**Why.** ADR 0471 priced the Talk job at the first tile where the talker could meet the
recruit. In vanilla Ch14, Rennac (charId 28) is first met in the corridor the enemy holds. The
death on the way there cost as much as the job was worth, so the job was dropped. Nobody went
for the safe meeting at the map's edge, where he leaves (`h766c`, s4002).

**What changed.**
- **`Goals.meetings`** lists every meeting a talker can make on the recruit's walk: its tile,
  its player phase, and its chance. Each turn until the Talk costs one gamma, and the wait at
  the tile counts too, so a later meeting is never worth more just for being nearer.
  `Goals.meeting` (first meeting only) is gone.
- **`bot.lua` `talkWorth`**: the Talk job is worth its best meeting, the recruit's worth less the
  hire, times that meeting's chance, less the death on the way there (`lossOf`). The talker is
  sent to that tile. With no meeting before he is removed, there is no job (#764).

**Not kept: a door hold.** A hold on the act that loads a recruit was built on the same branch.
It made the act wait while no talker would have a Talk job if he came now. It never fired in any
run (`h766b`, `h766d`), and a hold on distance alone won s4002 but lost s4003 and s4009
(`h774a`, `h766a`). It was removed before the PR.

## The forecast plays a Rogue's door and chests (#775)

**Why.** Once Rennac was on the board, every meeting was priced on the tile he stood on, turn
after turn: (22,9) on turn 3, (22,5) on turn 4, (22,3) on turn 5 (`h766e`). In fact he walks
north through the (22,8) door to the two chests, then west along row 1 to his exit. The forecast
(`sight.closings`) plays the game's own AI forward, but it played only a looter's pillage. A
Rogue opening a door or chest is a different action, `AI_ACTION_PICK` (13). The decomp's
Ch14-only Rogue routine (`cpextra_80407F0.c` `sub_8040C5C`) names the lock in the decision's
`xTarget`/`yTarget`, and `ActionPick` (`bmusemind.c`) runs that tile's door or chest event.
Unplayed, the door stayed shut. He picked it again every phase and read as standing still.
Because the forecast covers his whole stay, `runOn` never read the remembered route past it
(ADR 0471: "the forecast's phases stand").

A second gap showed once the door opened (`h775b`). After the chests, the forecast sent him
back south toward the other doors. In the game, the chests fill his bag: 3 items, then 4 at
(22,5), then 5 at (22,3), in every recorded game. With a full bag the same routine turns him
from locks to his exit. In the forecast's replay, no item went into his bag.

**What changed.**
- **`Sight.playPick`**: a pick plays as `ActionPick` does. The door opens as its map change
  draws it (`M.openMap`, journaled). A chest is emptied, and its item goes into the Rogue's bag
  through the game's own `MakeNewItem` and `UnitAddItem`, with the bag kept first (as `moveItem`
  keeps a theft's). Both of the forecast's looks play it. A chest the Rogue takes also closes
  as a goal, at that phase, in the first look.
- **`s.chestItem`**: a chest's item is read from its location entry (`SearchAvailableEvent`,
  `EventInfo` +0x14 `givenItem`, through the same `locationAt` that `isHouse` now uses). Gold
  gives no item. A `givenItem` of 0 rolls from the table at its script, and the table's first
  entry stands in for the roll: the AI only reads that the bag is one item fuller. The items are
  read before the forecast's sandbox, so the replay never borrows the AI's scratch.
- **`Board.AI_ACTION_PICK`**, `AI_DEC.X_TARGET`/`Y_TARGET`, on the board API too. A constant
  missing there compares nil to the action and never matches, as `AI_ACTION_ESCAPE`'s once did
  (#699).

This is fix 1 of the two #775 named (the forecast plays what he does). ADR 0471's rule stands:
the forecast's phases outrank the memory. Fix 2, memory over forecast, was not needed.

## Proof

- Unit tests that fail without their change: `test_bot`
  (`test_a_talk_job_is_worth_its_best_meeting`); `test_sight`
  (`test_play_pick_opens_what_the_rogue_picked`: the door opens, the chest empties, its item goes
  into the bag, a non-pick changes nothing, the replay calls it, and the board API carries the
  constant).
- **Ch14 five starts, best meeting (`h766d`, before #775):** Rennac recruited on 3 of 5 (main
  2), clean clears 2 of 5 (main 2). s4002 won him at the safe intercept at his exit.
- **Replay `h775c`, Ch14 s4005, two attempts, with a temporary log of every meeting priced for
  L'Arachel (not committed).** From every tile he stood on, the forecast's path now matched his
  real walk tile for tile: (22,9) → (22,5) → (22,3) → (18,1) → (12,1) → (6,1) → (1,2) → (1,8).
  L'Arachel's meetings were priced along row 1. On `h766e` they were priced only on his current
  tile. One read is still unexplained: in attempt 2, on the turn he stood at
  (22,3), 20 reads sent him south. It is on #766 (comment 7176696969) with the test that would
  settle it.
- **Outcome on that replay:** both attempts won with 0 deaths (`h766e`: a1 lost Innes, charId
  11). Rennac was still not recruited, and his two chests closed (taken by him). Pricing the
  meetings on his real walk did not make L'Arachel get there. That is the per-turn play's gap
  (R3, #767), not the forecast's.
- **PR #777 review.** A meeting past the end of his walk (no removal) is met when the talker
  arrives, never in an earlier phase. Before, a talker 8 turns away read a negative wait and a
  chance near 1 (`test_goals` `test_meetings_price_each_meeting_on_its_wait` fails without the
  fix). The trip's clock (`trip`) is one helper, read by `meetEach`, `arrive`, `Goals.meetings`
  and `Goals.chance`. The forecast reads chest items from the memo alone, never in a sandbox
  nested in its replay.
- **Planning cost.** A pick is one more branch on a decision the replay already reads. The chest
  items are read once per game. No new search or simulated phase, so no timing (ADR 0430).
