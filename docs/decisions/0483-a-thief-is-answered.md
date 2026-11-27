---
id: 483
title: "A thief is answered: the holder is kept back or hands the item off, the looter's death keeps its chest, and strikers meet one the calendar brings"
date: "2026-11-27"
section: "Combat System"
issues: [764, 711, 688, 510]
---

# A thief is answered: the holder is kept back or hands the item off, the looter's death keeps its chest, and strikers meet one the calendar brings

**Decided (2026-11-27, #764's fix order item 1: Ch16's east thief).** Four changes to how the
bot meets an enemy thief. Each was a separate cause of R5's unclean Ch16 tries, all from the
same thief.

1. **A key holder the thief robs is mended.** When the judged phase has a thief rob a unit of its
   last chest opener (sight's `lock` theft) in a way past `Planner.DUST`, the mend tries that
   unit's other acts, then every unit's strike on that thief. ADR 0475 already did this for a
   spoiling theft. Such a plan also keeps the mend going past round 1 (`robbed(st)`).
   Also, a unit's progress toward its assigned chest (the turns a plan cuts from its way there)
   is weighted by `st.opens`: the chance the phase leaves it alive and holding an opener. The lost
   chests were already charged in the score (ADR 0442), but the rank puts progress before the
   score, so a march that hands the thief the key outranked the stay that kept it.
2. **The looter's death keeps its chest.** `sight.closings` now names the looter that takes each
   tile (its third answer). For a closing a retry remembers, the looter is the board's red of the
   remembered closer's memory key (`Timeline.deadlines` `closers`; `sight.keyOf`, the one step that
   names a board's unit as the record does). Vanilla Ch16's two thieves share a character and class, so that pair
   alone named neither (review of PR #790); with no key to read, the one red of that pair. A goal carries
   that looter as `closer`. A plan that kills the closer reads the goal with no closing date
   (planner's `chanceOf`). Before this, the date was read once per board, so a strike on the
   looter saved nothing.
3. **A hand-off by Trade (#688's items half), offered only by the mend.** Where the mend tries a
   robbed unit (both the spoiled and the lock-robbed case), it also tries the Trades that move
   out each item its judged phase's thefts take (planner's `st.stolen`, the thefts' `item`):
   the robbed unit gives it to a teammate, or a teammate takes it (`Bot.handoffsFor`, over
   `tradeAct`). The first version read the items from a list of what a thief on the field could
   take and handed off its first. That missed a thief the calendar brings in the judged phase,
   and a holder of two items at risk handed off the wrong one (review of PR #790). No board menu offers them. The plan's Trades are staged
   in the judged phase's bags (`planner.tradesIn` → sight's `stagePhase`, through
   `sight.tradeItems`, which `moveItem` shares). So the thief steals from the bag the Trade
   leaves, and a hand-off is worth exactly the theft it moves out of reach. A plan Trade whose
   item is not where it names raises: the game could not play that plan as judged. The planner
   keeps such a plan from being built: a full-bag taker's give-back is taken once per plan, as
   the item itself is (`fx.tookBack`). A hand-off earns no
   breach weight.
4. **Strikers meet a thief the calendar brings.** From attempt 2 on, memory knows a red the game
   brought to a tile on a board turn (`Timeline.calendar`: one entry per unit key, since many
   units share a generic charId). For each such red whose class steals (`sight.steals`, the
   class's `CA_STEAL`; no vanilla character carries it and the injector writes none), Bot's
   `releasesOf` adds a release at its tile, the door's shape (ADR 0478), so the same stage job
   sends strikers beside it (`Goals.STAGE`).
   - **Enough strikers: one per thief**, the door rule's (one per red in the front).
   - A striker's gap is `strikeGap` to the tile, less the moves it has before that turn. The job
     is **due** once a move away now would make the nearest sendable striker late. It then stays
     due to the arrival (the gap falls by at most a move a turn), so a stager met early is held.
   - No forfeit: no act of the army brings the thief, so the planner's `released` never matches.
   - The record's `releases` carries `arrival` (its board turn) and `due`.

**Why.** R5, vanilla Ch16, retries of five starts (#764 comment 7224984293). Read in the traces:
- s4005, all three tries (and s4007 a1): the thief, arriving turn 11 at (21,13), stole Eirika's
  Chest Key on turn 12. Every plan had marched her into its reach from a tile out of it
  (`r5b16-…-s4005` a2, turn 12: value −1777, forfeits 0, all three (20,y) chests at 0 after).
- s4002 a1–a2, s4003 a1, s4009 a1: it looted (20,5) on phase 13 and (20,3) on phase 14.
- s4002 a3, s4003 a1, s4009 a3: it stole Colm's Lockpick or Knight Crest. He had no tile out of
  reach, and a 14-Spd thief cannot be stolen back from.

**Replays of Ch16 s4005 a1**, each with a part added:
- `l764a`, part 1 without the progress weight: the mend judged Eirika's stay (−148.5 against the
  chosen −185.3), but a turn of progress behind. She walked on and lost the key on turn 12.
- `l764b`, part 1: she kept the key on turns 12–13. The thief looted (20,5) on turn 14 and stole
  the key the same turn. Won in 18 turns, 0 deaths, 2 of 4 chests (main's try: 16 turns, 2 of 4).
- `l764c`, parts 1-3 (hand-offs on every menu): handed weapons around (off-list items read as
  spoilers; `stealSpoils` now reads AiGetItemStealRank's -1 as spoiling nothing).
- `l764d`, parts 1-3: worse than main. No thefts, but Eirika held the key at (14,10) all game,
  nobody killed the thief, and it looted all three (20,y) chests on turns 14-16 (1 of 4 chests).
  One extra death (charId 9, turn 15). Hand-offs fired on quiet turns and passed crests (items
  116, 124, 100) back and forth. Hence the hand-off moved into the mend, and part 4.

**Replay `l764e`, all four parts, Ch16 s4005 attempts 1-2, against main's R5 (`r5b16`):**

| Attempt | Run | Turns | Deaths | Chests (of 4) | Thefts |
|---|---|---|---|---|---|
| 1 | main | 16 | 0 | 2: (20,5), (3,12) | 4, Chest Key on turn 12 |
| 1 | l764e | 18 | 0 | 3: (20,5), (20,3), (3,12) | 4, no Chest Key |
| 2 | main | 18 | 2 | 0 | 2, Chest Key on turns 12, 13 |
| 2 | l764e | 21 | 2 | 2: (20,5), (20,3) | 3, no Chest Key |

- Neither try is clean, and (20,1) is missed in both. On a1 that is an opener shortage: 3
  openings for 4 chests (two Chest Keys, and a Lockpick with 2 uses spent on the (3,9) door and
  (3,12)). No Supply was offered all game, so the convoy held no key. The west thief drops its
  loot (a2: its kill dropped (3,12)'s Tomahawk), so leaving (3,12) to it would free the Lockpick
  for (20,1). That is the next item on #764, not this record's.
- Each try made one Trade, on turn 12: Eirika's Chest Key to a teammate (charId 15 in a1,
  charId 5 in a2). No crest passed back and forth.
- a2's two deaths (charIds 2 and 9, turns 5-6) are main's own, before the thief.
- a2's stage job was due on turns 10-11 and sent one striker (charId 23). It stood beside the
  thief's tile on turn 12. The plan that struck the thief was judged, but ranked a turn of
  progress behind (`behind` 1 against 0, both 0 forfeits). So the thief lived to turn 17 and
  stole from charId 5 on turns 13-15. One striker per thief was enough to be in reach. It was not
  enough to get the kill chosen. It cost nothing: all three thefts read `spoils: false`, so the
  clean clear never ranks that kill ahead of progress, and nothing is built for it.
