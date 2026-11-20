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
5. **Memo and limits.** The read is made once per set of changes per decision (`extend` keeps
   its key, `changeKey`, as it adds a door, a wall or a kill). `extend` still keeps out a used
   unit and a taken tile. An added act carries its board (`a.map`) and what it needs of the plan
   (`a.needs`: the doors and walls opened, the enemies dead). Nothing is added for an offered
   replay (`opts.offer`) or for a sight without the read.
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

## Review of PR #669 (2026-11-19): what changed and why

A code review found six gaps; each is fixed, with a test that fails without its fix.
- **A rebuilt plan kept a stale re-listed act.** The mend, heal swap and assault rebuild a plan
  with one unit's act swapped, so a doorway act could outlive the door act it was read on. A
  re-listed act now carries `needs = { opened, gone }` (all the changes of the board it was read
  on), and `extend` rejects it unless the plan holds each one. It is the one check, in `extend`.
  Its spares carry `map` and `needs` too.
- **An uncertain kill staged a unit onto a living enemy.** A kill at chance >= `M.GONE` counts
  as dead for the beam. In a judged way where that blow missed, the enemy still stands, and the
  plan's later unit would be staged on its tile, overwriting the enemy's cell in the game's map.
  In play, `M.surprise` replans after a miss before the next act, so that unit never moves. In
  such a way (`w.gone` lacks an enemy the act `needs`), `bluesIn` now stages the unit on the tile
  it stands on now, not acted, with no counter to play. The average way the lookahead reads uses
  the same helper. Left as it was: the unit's entry in the judge's `hit` list keeps the HP its
  planned act would have left it, which is a pessimism in that way, not an overwrite.
- **The mend tried only board menus.** It reads `menusFor(base)`, so a unit at risk can try a
  doorway or freed-tile act its plan's door or kill makes. Such an act is built after the rest
  of the plan (it needs the door held first); the `needs` check keeps a rebuild honest.
- **An offered full-information replay cannot reproduce re-listed plans.** Its acts are the
  fogged board's, and a re-listing would read them on the fog-off board it plans on, which the
  fogged game never offered. Supporting it would hand the replay powers it lacks, so it keeps the
  board's menus, and the gap is loud: the `DIAG` line carries `relisted` (the baseline plan's
  re-listed acts), and `montecarlo.py`'s audit reads no verdict off a `full_info` replay whose
  plan names any, saying so in its notes (before, its different plan would have read as
  `information_unavailable`).
- **The re-list board ignores units the plan already moved: kept, by evidence (Nicolas, after
  a first build that staged them cost 54.9 s per phase, 25x main).** The read leaves a moved unit
  on its board tile. That changes nothing about legality or the final ranking: an ally never
  blocks a unit's march in FE8 (allies are passable), a tile the plan filled is rejected by
  `extend` (`st.tiles`), and the judged phase stages every moved unit where the plan puts it. A
  stale tile only affects how a unit's new acts are ordered for the `PER_UNIT` cut (their
  exposure read on the board). The staging (`sight.changed`'s `blues`) and its memo key were
  removed, so there is one board per set of changes again.
- **`menusFor` rebuilt its key per beam state.** `extend` keeps `n.changeKey` as it adds to
  `opened` or `gone`; `menusFor` reads it, and builds the moved-units part only when a change
  exists.

**Replays of the same start** (vanilla Ch8 from `e639-t639-cs-s4002/9`, attempt 1,
`PT_LEAKGUARD=1`): `relist661f` is the build that staged moved units (dropped above);
`relist661g` is the final one.

| | main (`base661`) | `relist661e` | `relist661f` | `relist661g` |
|---|---|---|---|---|
| Result | won, 57 turns, 0 deaths, not clean (2 west chests) | won clean, 16 turns, 0 deaths | won, 13 turns, 0 deaths, not clean (same chests) | won clean, 17 turns, 0 deaths |
| Turn 1's first decision | 7,127 frames | 10,141 | 38,305 | 10,043 |
| Turn 3's first decision | 4,667 | 13,480 | 85,481 | 13,480 |
| Turn 3, all decisions | 6,864 | 21,690 | 115,537 | 21,690 |
| CPU per player phase | 2.24 s | 8.27 s | 54.9 s | 8.1 s (137.7 s, 17 phases) |
| `BattleGenerateSimulation` per phase | 387 | 2,688 | 9,818 | 2,644 |
| `AiDecideMain` per phase | 519 | 1,549 | 8,896 | 1,496 |

The review's other fixes cost nothing measurable (`relist661g` sits on `relist661e`'s numbers).
The door: Lute (charId 12) opened (20,7) on turn 5, then Garcia (charId 10) and Seth (charId 2)
struck from (20,5) and (20,4); 19 of 26 judged door plans had a later act on or past the
doorway (main: 0 of 179). Kills: 33 of 278 judged plans had a later act on a tile an earlier
act's red target stood on (main: 0 of 567), and 5 of those were played. No leak was logged.

**Second review (2026-11-19), four more fixes, each with a test that fails without it.**
- A unit whose act follows an unplayed one and ends on that unit's board tile stays put too in
  a way where a needed kill missed (`bluesIn`, in plan order), so two blues never share a tile.
- The heal swap's act inherits `map` and `needs` from the re-listed wait it replaces.
- A force replay of a re-listed act is read like a `full_info` one: no verdict, with a note
  (the DIAG `relisted` keys), not a missing action.
- The mend puts a re-listed act in right after the act that completes the changes it needs, the
  rest of the plan after it, and last only if it does not fit there, so another unit cannot take
  its tile first.

**Amendment 2026-11-19 (#671): the same plans for less CPU, three changes.** A profile of turns
1-3 (vanilla Ch8, `e639-t639-cs-s4002/9`, attempt 1) put 35% of the re-list in board reads and a
Talk scan per change key. Each change leaves the listed plans as they were:
- **The board is read once per changed board.** `Sight.changed` reads the units after its
  doors and kills are applied and hands them to `seen.units`; `keptRead` kept no read inside a
  sandbox, so `fieldUnit`, `mapChange`, strike, `keySources`, `retreatOver`, `wallsOnWays` and
  `march` read the whole board per call (6,834 reads). A nested sandbox is no new risk: on the live
  board every nested sandbox already finds `refresh()`'s read cached, and `fullInfo` takes a fresh
  `seen` of its own.
- **The re-list shares the board's Talk memo** (`opts.talks` into `Bot.candidates`). A pair's answer
  is its two charIds and the event flags, which no door or kill moves. A dead red is not on the
  re-list's board (`menusFor` drops `gone` from it), so none of its pairs is asked.
- **A kill-only change keeps the danger and threat grids** (`Sight.freshSeen`), as it keeps
  the march cost grids. `GenerateDangerZoneRange` skips only a fogged or roofed unit, not a hidden
  one (bmidoten.c), and no red blocks a red, so a kill moves neither grid. One exception: a killed
  enemy the retry remembers. `liftRemembered` lifts only a unit that is not hidden, so its death
  changes the grid on a fogged tile; that change rebuilds them.

Proof: all 125 decision records of turns 1-3 equal main's but for `frames` (turn 1's first
decision 10,041 to 7,995); the whole chapter with `PT_LEAKGUARD=1` won clean in 17 turns with no
leak, as `relist661g` did. CPU for turns 1-3: 28.2 s to 23.6 s (-16%).

**Amendment 2026-11-19 (#671): a strike is keyed by the reds it can read.** The strike memo
keyed every on-field unit, so each re-listed board (a plan's kills) missed every strike. A strike
read is the game's own AI for enemy `e` against our unit on a tile. Diagnosed on vanilla Ch8
(`e639-t639-cs-s4002/9`, 12,908 reads): with the map and every non-red unit equal, reads differed
only by which reds were present, and the game's code explains each difference:
- the AI skips a candidate strike tile with a unit on it (`AiSimulateBestBattleAgainstTarget`,
  cp_battle.c), and the candidates are within `e`'s weapon range of the target;
- the tile's score counts units within 3 of it (`AiGetFriendZoneCombatPositionScoreComponent`,
  called by `AiGetCombatPositionScore`);
- its danger map skips allies, so reds do not enter it (`AiFillDangerMap`, cp_0803E2F4.c; the
  player's `GenerateDangerZoneRange` counting a hidden unit is the bot's own grid, not this read).

So a red beyond `e`'s max weapon range + 3 of the struck tile cannot change the strike. The key
(`strikeKey`, `strikeRadius`) holds every unit that is not red, `e`, and the reds within that
distance. An enemy whose range is unknown (no weapon on the list: a dancer, a ballista's rider),
or with a staff of its own (a heal reaches an ally anywhere in its movement), keys the whole
board as before. Radius 3 gave 3 wrong merges in the diagnosis, radius 4 with reach-1 enemies 0.

`PT_STRIKECHECK=1` (run.sh) is the guard: each memo hit also runs the strike and logs a read that
differs, which fails the attempt as a leak does. Unproven: a rank-locked or magic-sealed weapon
the AI counts and `sight.weapons` does not (the guard is the check on the replays we run).
