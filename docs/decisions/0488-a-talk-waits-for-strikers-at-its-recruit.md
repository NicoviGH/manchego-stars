---
id: 488
title: "A Talk waits for strikers at its recruit"
date: "2026-11-27"
section: "Combat System"
issues: [764, 730, 510]
---

# A Talk waits for strikers at its recruit

**Decided (2026-11-27, #764 fix order item 2, second half: Ch10's Amelia; #730).** The stage
job (ADR 0478) gets one more kind of release: a Talk. No scoring change and no new weight.

**Why.** Replay `d730c` (Ch10 s4005 attempt 1, with a temporary log of every Talk plan's
protected deaths) showed that in all 34 Talk plans the death over the cap was the recruit's own
(Amelia, 0x12, 0.75 to 0.98), not the talker's. A Talk turns her blue on her own tile, and the
planner protects her under the cap from that phase (#766, planner `recruited`). Three ambush
Mages stood beside her from turn 5, so the cap was right to refuse every Talk. But no job sent
the army to kill them first: on turns 8 and 10 the talker was 10 to 12 tiles away, and she was
lost when the script took her on turn 11. A person kills what would strike the recruit, then
Talks (#764: "sends a strong unit in first to kill that enemy").

## The rule

- **`Bot.joinsOf`**, read with the releases (`releasesOf`) once a decision, on the board now
  (the reds are in sight, so no memory is needed): for each red recruit on the field that a blue
  may Talk over, its `front` is each red whose threat reaches her tile: not she, nor another
  recruit, nor a loose one (owed, no one may Talk it yet, ADR 0452: still a recruit, never a foe
  to kill). Only a tile the one-grid danger read covers has its reds' threat grids read, so a
  recruit no red reaches costs nothing more. With a front, it is a release in the door's shape, keyed `join:<id>`: `need` is the
  front's size, `strikers` each unit's `strikeGap` from her tile to the front, `ready` those at
  0 or less, `full` = ready >= need.
- **The stage job** (`sendStagers`) sends the `need` nearest free strikers to her, met beside
  her, as it does to a door. The talker keeps its own Talk job.
- **No forfeit.** The cap already judges the Talk: while the front stands, a Talk reads over it.
  This only brings the strikers whose kills bring the Talk under it.

Nothing names a unit, a tile or a chapter.

## Against ADR 0396's five tests

(1) It reads the game's own threat map and march fields. (2) It sends units; the order comes from
the existing cap. (3) Any objective, any style: a recruit with reds in reach of her tile. (4) No
ordering repeats another. (5) No unit, chapter or tile is named in the code.

## Proof

- `test_bot.lua` "a talk waits for strikers at its recruit", run against the reverted lines:
  without `M.joinsOf`, four checks fail (the release read, the striker's gap, the striker sent,
  and the staged release read); without the loose-recruit skip, "a loose recruit is no front"
  fails. The other checks expect no release, so they hold either way.
- Replay `j764a` (Ch10 s4005 attempt 1, the game `t730b` lost her in):

| Run | Code | Amelia | Turns | Deaths |
|---|---|---|---|---|
| `t730b` | ADR 0487 | every Talk over the cap; lost on turn 11 | 15 | 0 |
| `j764a` | this rule | stagers sent turns 5-11 (7 at first), front 8 reds down to 1; Franz Talked her on turn 11 (plan admitted, max death 0); she lived to the end | 17 | 0 |

  Not clean: the Mercenary closed the (11,15) village (#764 comment 7232245754's other loss).
