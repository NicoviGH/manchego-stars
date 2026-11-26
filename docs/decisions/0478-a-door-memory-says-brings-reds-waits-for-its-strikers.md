---
id: 478
title: "A door memory says brings reds waits for its strikers"
date: "2026-11-26"
section: "Combat System"
issues: [766, 764, 767, 510]
---

# A door memory says brings reds waits for its strikers

**Decided (#764's "After R4" item 3, Nicolas 2026-11-26: "continue iterating"; the bot gathers
strikers at an act memory says releases a squad before making it, general, no door case).**
The first piece of R2's stage job (#764) that moves the army, not only a talker.

**Why.** Vanilla Ch14's (22,17) door brings four Fighters and Rennac (0x1C) into the corridor he
leaves by. The one R4 try that recruited him (`r768a14` s4005 a3) had Saleh, Innes and Franz
within two tiles of the door when Colm opened it: Saleh killed the first Fighter, and the other
two went through the gap and killed two more that turn. In replay `q766e` a2 the strikers stood
4-8 tiles back, Artur alone reached a red on the door's turn, and L'Arachel stayed a turn
behind Rennac until he was gone. Memory already knew the door brought them (each arrival's
`by`, botrun's `triggerOf`); nothing read it.

## The rule

- **`Timeline.releases(memory)`** (one owner): each act by our army that brought reds, by act and
  tile; its `front` (the reds it brought on the act's own board turn, from the latest attempt
  that made it, less any that left or turned: a recruit is a goal, not a foe); and what its
  units lost in any attempt (`tiles` they closed, units that `gone` left the map).
- **`Bot` `releasesOf`**, once a decision on the board before anyone acts: each such door still
  shut whose losses hold something still open here (the `stake`). Its `need` is the front's size.
  A unit is `ready` when it can strike a front tile the turn the door opens (`strikeGap`: the
  march cost from the door to it plus from the door to the tile, one field from the door's tile,
  units not blocking, against its MOV and the Weapon Select list's longest reach). Opening
  the door spends its opener's act, so when every unit able to act that opens doors is among the
  ready, one fewer counts. `staged` = ready >= need.
- **The planner's forfeit** (`Goals.forfeited`'s `released`, `Goals.released`): a plan that
  opens a door whose release is not staged forfeits the stake: the recruit memory saw walk off
  (by character; recruit goals now carry `charId`) and the tiles its units closed. A ranking,
  not a ban (ADR 0396): the forfeit is the rank's first term, as every forfeit is.
- **The stage job** (`sendStagers`): each unstaged release sends its `need` nearest strikers
  with no other job to the door (never a unit whose loss ends the game, `sendOpeners`' reason,
  nor one the stuck record bars from it). The job is met beside the door (`Goals.STAGE` is a
  beside kind), so a keyless striker marches up to it rather than off to fetch a key.
- **The record**: each plan carries `releases` (door, need, ready, staged), and a stager's
  `goals` row is marked `stage`.

Nothing names a unit, a door, a tile or a chapter. A first attempt has no memory and plays as
before.

## What it did (replay `s766r`, Ch14 s4005, attempts 1-2)

- **Attempt 1** (no memory) played as `q766e` a1: won in 21 turns, L'Arachel lost on turn 14.
- **Attempt 2:** the door waited from turn 3 to turn 5 (it opened on turn 3 in `q766e` a2). On
  turn 4 Saleh, Innes and Cormag moved within three tiles of it. Tana opened it on turn 5, and Artur, Innes
  and Cormag killed three of the four Fighters it brought that turn. L'Arachel went in behind
  them, and **talked Rennac over on turn 6**, the first recruit in these replays.
- **Not clean:** L'Arachel died in turn 6's enemy phase (won in 23 turns, 1 death; `q766e` a2:
  16 turns, 0 deaths, Rennac lost). The Talk plan read her death at 0: it had Rennac, still on
  (22,9) beside her, take the reds' strikes. Once he joined, his replan judged four moves, all
  off (22,9), each with her at 0.397. Holding his own tile was never offered: `propose` gives a
  unit its three safest hold tiles, and its own tile only on a tie. That is the next fix (#766).

## Against ADR 0396's five tests

(1) It reads memory the bot already keeps and the game's own march map; no weight. (2) The
order comes from the existing forfeit. (3) Every door any attempt opened onto reds. (4) No
ordering repeats another. (5) No unit, chapter or tile is named in the code.

## Proof

- `test_a_door_memory_says_brings_reds_waits_for_its_strikers` (bot) fails without the forfeit
  and the stage job, and its armed-opener and beside-the-door checks fail without those parts;
  the `releases` case in `test_timeline`; the `released` case in `test_goals`.
- Replay `s766r` above.
