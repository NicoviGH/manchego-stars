---
id: 483
title: "A thief is answered: the holder is kept back or hands the item off, and the looter's death keeps its chest"
date: "2026-11-27"
section: "Combat System"
issues: [764, 711, 688, 510]
---

# A thief is answered: the holder is kept back or hands the item off, and the looter's death keeps its chest

**Decided (2026-11-27, #764's fix order item 1: Ch16's east thief).** Three changes to how the
planner meets an enemy thief. Each was a separate cause of R5's unclean Ch16 tries, all from the
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
   tile (its third answer). For a closing a retry remembers, the looter is the board's one red of
   the remembered closer's character and class (`Timeline.deadlines` `closers`). A goal carries
   that looter as `closer`. A plan that kills the closer reads the goal with no closing date
   (planner's `chanceOf`). Before this, the date was read once per board, so a strike on the
   looter saved nothing.
3. **A hand-off by Trade (#688's items half).** When a red with `CA_STEAL` is on the field,
   `sight.atRisk(u)` lists the items of `u` a theft would cost: a spoiler (`stealSpoils`, the
   record's line) first, then a chest opener. Bot offers a Trade that gives the first of them to
   a teammate within its move and one, or takes a teammate's (`handoff`). The plan's Trades are
   staged in the judged phase's bags (`planner.tradesIn` → sight's `stagePhase`, through
   `sight.tradeItems`, which `moveItem` now shares). So the thief steals from the bag the Trade
   leaves, and a hand-off is worth exactly the theft it moves out of reach. A hand-off earns no
   breach weight and survives the per-unit menu cut, as a Rescue does.

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
- `l764c`, all three: see the PR.
