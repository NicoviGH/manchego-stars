---
id: 399
title: "A retry learns what earlier attempts showed on screen, and a chapter start gets 12 tries"
date: "2026-11-10"
section: "Combat System"
issues: [510]
---

# A retry learns what earlier attempts showed on screen, and a chapter start gets 12 tries

**Decided (Nicolas, 2026-11-10), #510 PR B** (plan comment 6779357154, PR B, amended). This
reverses ADR 0386's narrowing and goes back to ADR 0376 decision 3: "a retry knows what earlier
attempts saw, and only that". In Nicolas's words: "a player learns so many things... this feels
like the hardcoding we are trying to avoid". ADR 0385 is unchanged: attempt 1, the measured one,
has no memory.

**Why.** On vanilla Ch6, 8 of 10 campaigns stopped. The bot won 31 of 38 attempts but cleared
clean only once. The retries replayed the same deaths, because a retry changed only the style:
4001 lost Lute on turn 1 in all 6 attempts. 33 of 55 blue deaths came out of the fog (#510
comment 6776176601). A player who restarts knows where the ambush came from.

## 1. What a retry remembers

From attempt 2 on, at the same chapter start, every earlier failed attempt adds to
`style.memory.enemies` (`campaign.lua`): every red unit a board showed out of fog (botrun's
`enemies_seen`), and every killer a death showed (its `killerId` and `killer`: a fight is on
screen, fog or not; its class is read from the board after the deaths, where an arrival that
struck in the phase stands, else the one before, `killerClass`). A unit killed and a later
arrival in its slot are both kept: botrun keeps what it saw by the whole key. A unit whose class
was not read is not kept: its key would match nothing. Each is
kept once by slot, character and class (`Board.memoryKey`). Every attempt loads the same start,
so a unit keeps its slot; an arrival can take a slot another unit died out of, so the character
and class must match too. The character alone is not enough: most enemies share one generic
character id. The reinforcement arrival turns (ADR 0386) are still
kept and used as before. A dice result is never remembered.

## 2. How the bot uses it

One owner: `sight.remember(enemies)` at the attempt's start, then `sight.knows(u)`. A remembered
unit counts as seen everywhere the fog alone would hide it:

- **both judged enemy phases** (`enemyPhase`, `nextPhase`): it decides and strikes;
- **the danger maps** (`danger`, `threat`): its tile is lifted out of the fog for the call, the
  one test `GenerateDangerZoneRange` skips a fogged unit by (`bmidoten.c`);
- **the candidates' exposure** (`Bot.enemiesOf`'s second list, `ctx.threats`). It is never a
  target: the game refuses to target a unit on a fogged tile (`bmtarget.c`), so attack options
  stay with the enemies in sight;
- **a key it drops** (`keySources`, ADR 0397), and **a village or chest it loots**
  (`closings`' looters, ADR 0383). These and the judged phases ask one helper,
  `Sight.playsAsSeen`;
- **the lookahead's boss trigger** (`Planner.triggers`, given `ctx.threats`): a step into a
  remembered boss's reach in fog extends the plan a second phase, as for a boss in sight;
- **the plan's enemies** (`plan.enemies`), so a death by a remembered unit is never graded `fog`.

The fog read (ADR 0400) is unchanged: its strongest enemy seen so far is this attempt's alone,
as PR A built it, so a remembered unit is not also its stand-in for what the fog may hide. The
rule "counts as seen" has one owner, `Board.playsAsSeen`: `Bot.enemiesOf` asks it from the
board's `fogged`, sight's reads from the unit's state, and the danger maps lift exactly the
fogged units it counts.

**No deadline and no guard goal** (Nicolas, 2026-11-10: "fix that", then "drop it"). Both were
checked against ADR 0396's test and fail it. A remembered green death made a deadline ("its
killer dies, or the map is won, before that turn") or a pull toward the green from turn 1. Each
names one answer where the game has several (Rescue, a heal, a body in the way, a killer that
goes elsewhere on the retry; test 3). Each prices a death the rank already prices (`green_die`,
ADRs 0381 and 0398; test 4). What the death shows is a horizon error: the planner sees a green's
death only once its killer is one enemy phase away. That is the lookahead's to fix, not a retry
rule's. So a death reaches the next attempt only through its killer.

## 3. Checked against the screen's whole record

| What the screen shows | Remembered? |
|---|---|
| Each enemy: where, class, weapons and items | Yes, by slot, character and class. The start is the same, so its class, items and stats are the live unit's. |
| The map the fog opened | Nothing to remember. FE8's fog hides units only (`RefreshUnitsOnBmMap` sets `US_BIT9` on a unit on a fogged tile); the terrain is always drawn. |
| Reinforcements | Their arrival turns (ADR 0386). Once loaded, an arrival is a remembered unit like any other. |
| Who died, where, and to what | The killer, as a remembered enemy. Where our unit stood is the play's, not the game's. |
| Doors, chests, villages | On the map in every attempt. |
| An enemy's dropped item | Yes: `keySources` asks `knows`. |

**Left out:**
- **What a village or chest gave.** A retry still values one by the mean gift (`style.villageGifts`).
- **Where a fogged enemy went in an earlier attempt.** A remembered unit is played from its live
  tile on the retry. This is slightly more than the screen showed: its path in fog may differ
  from any attempt's. A player who has seen the opening twice knows about as much.

## 4. The retry cap

> **Amended by ADR 0404 (2026-11-12):** a retry gets different dice, so a repeated try is no
> longer a replay; "a try already played is never spent again" and its stop are retired.

`MAX_ATTEMPTS` is **12 a chapter start**. It replaces "stop once every style has been tried"
(Nicolas's call, a tuning weight). When the styles run out, they are drawn again, since memory
makes a repeated style play differently. **A try already played is never spent again:** the
start state restores the game's RNG, so a style played with the same memory replays that try
move for move (9 of 22 Ch6 retries did, in PR B's first rerun). A try is keyed by its style and
the sizes of the two remembered lists, which only grow. When every style has been played with
what is remembered now, the chapter stops there. A chapter with no clean clear in 12 attempts,
or with no try left, stops: a `bot_fault` on vanilla, `infeasible` on Manchego Stars. An attempt played alone (`api.only`,
the pool) still says `no_style` past the style count: with no memory, a repeat would be a
duplicate. So an attempt alone is an independent attempt, never the campaign's k-th try: its
attempts 2 and up have no memory (ADR 0386 already made them differ by the arrival turns), and
`montecarlo.py attempts` says so.

## 5. What it never touches

Attempt 1 has no memory, so every measured cell (ADR 0385) and the frozen suite, which plays
attempt 1 only, play as before. `test_botrun.lua` pins it: with no memory the sight is told
nothing and no enemy is carried. `test_bot.lua` and `test_sight.lua` pin that, with no memory, a
fogged unit is no threat, and is not among the plan's enemies. The second measured number,
tries until the first clean clear, is a later PR. Its method goes to Nicolas as an ADR 0385
amendment before it is built.

## 6. Carrying campaigns on

`montecarlo.py resume --game <g> --tag <t> [--campaigns a,b] [--chapter i] [--last i]` carries
campaigns on from a start they saved. Each runs under a new id `<t>-<campaign>`, and its states
are copied first, because resuming re-saves the start it loads and `cell-starts.json` pins the
original by its sha1. It plays with the campaign's own seed, in sequence, so memory carries
between attempts. Its records go to `resume-runs.jsonl`. It refuses, before copying anything,
when a pinned start was rewritten, when the start is missing, or when the new id is taken.
