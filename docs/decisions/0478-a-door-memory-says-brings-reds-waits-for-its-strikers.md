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
  march cost from the door to it plus from the door to the tile, one field from the door's tile
  read on the map the door's change leaves (a roofed room's tiles are unreached before it),
  units not blocking, against its MOV and the Weapon Select list's longest reach). Opening
  the door spends its opener's act, so when every unit that can open it this turn (lacks nothing
  for it, `lockAt`, and stands about a move from it) is among the ready, one fewer counts.
  `staged` = ready >= need, or every striker the stage job could send is ready (none still on its
  way): a door that brings more reds than the army can gather is opened with what it has, never
  held for good (with the objective behind it, the chapter would stall).
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

## What it did (replays of Ch14 s4005, attempts 1-2)

Attempt 1 has no memory and played as `q766e` a1 in every replay: won in 21 turns, L'Arachel
lost on turn 14.

- **`s766r` and `s766s` (the first version):** no unit ever read as ready (`ready 0` on every
  record of `s766s`), so no stage job was set. The corridor's tiles are roofed until the door's
  change, and a field read on the shut map does not reach them. The forfeit alone held the door
  from turn 3 to turn 5. L'Arachel talked Rennac over on turn 6, then died in that enemy phase:
  the Talk plan had Rennac stay on (22,9) and read her death at 0, and once he joined, his replan
  offered him no hold on his own tile (`propose` gives a unit its three safest hold tiles, its own
  only on a tie). That is a lead for #766, seen once.
- **`s766t` (this rule, gaps read on the opened map):** the turn-1 record read the door
  unstaged (ready 1 of 4) and sent four stagers. By turn 2 six units were ready. Colm opened it
  on turn 3, and **L'Arachel talked Rennac over on turn 4**, and lived through that turn. The
  game was won in 14 turns (`q766e` a2: 16, Rennac lost). **Not clean:** a red staff user
  berserked Cormag on turn 7 at (18,3), where the army had not reached by that turn in any earlier
  replay, and he killed L'Arachel, Artur and Tana on turns 9-11, each in a turn with no plan
  under the cap (#743's case).

## Against ADR 0396's five tests

(1) It reads memory the bot already keeps and the game's own march map; no weight. (2) The
order comes from the existing forfeit. (3) Every door any attempt opened onto reds. (4) No
ordering repeats another. (5) No unit, chapter or tile is named in the code.

## Proof

- `test_a_door_memory_says_brings_reds_waits_for_its_strikers` (bot) fails without the forfeit
  and the stage job, and its armed-opener, beside-the-door and gathered-what-it-can checks fail without those parts;
  the `releases` case in `test_timeline`; the `released` case in `test_goals`.
- Replays `s766r`, `s766s` and `s766t` above.
