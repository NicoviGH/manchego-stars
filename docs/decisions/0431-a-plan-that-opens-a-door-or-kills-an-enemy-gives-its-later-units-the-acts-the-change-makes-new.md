---
id: 431
title: "A plan that opens a door or kills an enemy gives its later units the acts the change makes new"
date: "2026-11-19"
section: "Combat System"
issues: [661, 670, 671, 510]
---
# A plan that opens a door or kills an enemy gives its later units the acts the change makes new

**Decided 2026-11-19 (#661, #670; Nicolas: "try it", then "do [the kill case] as a part of this
fix", correctness first, the cost tracked in #671).** It follows ADR 0396: an ordering of
outcomes, no new rule or weight.

**The problem.** The planner listed each unit's acts once, on the board before anyone acts
(`Bot.candidates`), and the beam combined those lists. A plan's own acts change the board.
- **A door opened or a wall broken (#661).** The judged enemy phase saw the change
  (`sight.openMap`), but no later unit in the plan got an act on the doorway or the room behind
  it. In vanilla Ch8 (seed 4002, the `dbg661` trace), 101 plans opened the door at (20,7) and none
  had a later act on or past the doorway. Every one left Lute (charId 12) beside five Armor
  Knights, over the death cap, and the bot waited at the door for 20 turns.
- **An enemy killed (#670).** A unit's end tiles leave out every tile a unit stands on, an
  enemy's too, so no later unit got the dead enemy's tile, a way through it, or a strike on what
  it shielded. In about 1,300 plans over 4 traces, no plan used an attacked enemy's tile again.

**The rule (`tools/playtest/planner.lua` `menusFor`, `sight.lua` `changed`, `bot.lua`
`opts.only`/`opts.tiles`).**
1. **The triggers.** A partial plan in the beam whose acts open doors or break walls
   (`st.opened`), or kill enemies (`st.gone`: the red units the plan already counts dead, as
   `extend` does), is read on the board those changes leave.
2. **Who is read.** Of the units the plan has not used, only those whose board reach comes
   beside a changed tile are read: the door's change tiles (`sight.mapChange`) or a dead
   enemy's tile, since a freed tile is entered from one beside it. Each of them gets one reach
   read on the changed board. A unit far from every change costs nothing.
3. **What is added.** Each unit keeps its board menu. It gains the acts from the tiles the
   change adds to its reach: waits, strikes and every other act `Bot.candidates` builds, listed
   over those tiles alone (`opts.only`, `opts.tiles`; `reachOf` filters the reach). The added
   acts get the same cut as any menu (`menusOf`). Every added act ending on a changed tile is
   also kept past `PER_UNIT`, as a step aside is: what standing in a doorway or in a dead guard's
   gap is worth is the unit it shields, and only the judged phase reads that.
4. **The changed board.** `sight.changed` applies the changes in one sandbox: the judged phase's
   journaled writes for doors and walls (`M.openAll`) and for a death (`M.takeOff`, shared with
   `enemyPhase`). The board's cached answers are fresh for the call (`M.isolated`, shared with
   `fullInfo`). Its march cost grids are kept when no terrain changed. The phase cache is kept,
   since its memos key on `mapKey` and on every unit standing. `closings`' memo now keys on the
   map too.
5. **Memo and limits.** The read is made once per set of changes per decision. `extend` still
   keeps out a used unit and a taken tile. An added act carries its board (`a.map`), so the
   exposure memo tells it apart from a board act. Nothing is added for an offered replay
   (`opts.offer`) or for a sight without the read. The mend still tries the board's menus.
6. **The trade.** A unit's board acts keep their exposure read on the unchanged board. The judged
   enemy phase plays the changed board, so the ranking stays honest. Re-listing every act on the
   changed board was the first build (below), and it cost more.

**Proof (2026-11-19).**
- **Unit tests (`test_bot.lua`).** Each fails on main's planner and passes with the change:
  - `test_a_plan_steps_through_the_door_it_opens`. Main: `2>wait@0,1 3>wait@0,2 1>wait@1,0`.
    Branch: K opens the door and D acts from the doorway. One read for the door, and F, whose
    reach the door does not change, gains no act.
  - `test_a_plan_steps_onto_the_tile_its_kill_frees`. Main: `1>attack@1,1 2>wait@0,0`. Branch:
    D strikes the boss from (2,0), through the tile K's kill frees.
  - `test_a_relisted_unit_with_only_an_allys_tile_does_not_crash`. A unit left only an ally's
    tile, or none, crashed the march and the Vulnerary in the replays `relist661c` and
    `relist661d` (turn 16, `bot.lua:852`, no result); this test fails on that code.
- **Replay** of vanilla Ch8 from `e639-t639-cs-s4002/9`, attempt 1, with `PT_LEAKGUARD=1`
  (`relist661e`), against main's `base661`:
  - **Result:** won clean in 16 turns with no deaths. Main won in 57 turns with no deaths and
    left the west chests.
  - **The door:** Lute opened (20,7) on turn 5. Garcia (charId 10) and Seth (charId 2) struck
    past it from (20,5) and (20,4). Of 28 judged plans with the door act, 19 had a later act on
    or past the doorway (main: 0 of 178).
  - **Kills:** 24 of 243 judged plans had a later act on a tile an earlier act's target stood on
    (main: 0 of 567), and 4 of those were played.
  - No leak was logged.
- **Cost (tracked in #671).**

  | | main (`base661`) | branch (`relist661e`) |
  |---|---|---|
  | Turn 1's first decision, same board | 7,127 frames | 10,141 (+42%) |
  | Turn 3's first decision | 4,667 | 13,480 |
  | Turn 3, all decisions | 6,864 | 21,690 |
  | In-game CPU per player phase | 2.24 s | 8.27 s |
  | Whole chapter | 127.9 s, 57 phases | 132.4 s, 16 phases |
  | `BattleGenerateSimulation` per phase | 387 | 2,688 |
  | `AiDecideMain` per phase | 519 | 1,549 |

  Turn 2 differs between the runs, so turn 3 is not the same board. Turn 1 is the clean
  same-board number. Most of the added cost is in the strikes the kill trigger adds: each new
  set of kills is a new board, and every strike forecast or exposure read on it is new. For the
  door alone, the first build re-listed every unit on the opened map: per phase 3.74 s, turn 3's
  first decision 7,252 frames. Re-listing only the units whose reach the door changes gave
  3.62 s and 6,102 frames (`relist661`, `relist661b`).
