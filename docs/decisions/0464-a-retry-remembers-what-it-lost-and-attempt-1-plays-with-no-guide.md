---
id: 464
title: "A retry remembers what it lost and what our acts loaded; attempt 1 plays with no guide"
date: "2026-11-23"
section: "Combat System"
issues: [741, 510]
---

# A retry remembers what it lost and what our acts loaded; attempt 1 plays with no guide

**Decided (Nicolas, 2026-11-23, #741), #510 step 9.** Amends ADR 0399 (a retry learns what
earlier attempts showed) and ADR 0436 (an owed recruit a retry saw arrive is a goal). In
Nicolas's words: "if the second attempt doesn't remember those details, that's a gap between the
bot and a person playing". His call on the guide: "it's ok because if the first attempt on
Manchego Stars also has no guide then it's equal".

**Why.** In the `m740c` traces attempts 2 and 3 replayed attempt 1's losing race. Vanilla Ch14's
door at (22,18) loads Rennac (0x1C) and a squad on whatever turn we open it (turns 2, 4, 6 in
s4003's three attempts), and those turns were remembered as timed waves: `style.arrivals` grew to
[2..8], so the march held on almost every turn (`bot.lua` `holding`). Ch10's (11,15) village was
razed in 13 of 15 attempts, and no retry knew when.

## 1. What a failed attempt adds to `style.memory`

One owner, `style.memory` (`campaign.lua`), built from the failed attempt's record:

- **`arrivals[i].by = { act, x, y }`**: an arrival that first stands on the board read right
  after our door, chest or village act is that act's effect (`botrun.lua` `M.triggerOf`; the
  tile is the door's own, else where the unit stands). A turn event loads its units on the
  phase's first board, before any act we make, so the two are told apart on every board. Each
  arrival also keeps `boardTurn` and `classId` now (the copy into a retry dropped `boardTurn`,
  so a start-of-turn arrival's goal ended a turn late).
- **`closings["x,y"] = { phase, closerChar, closerClass }`**: each reward tile a looter or an
  event closed (the record's `explore` rows: `closed_phase`, the closer's enemy phase, else the
  phase before the first player phase that no longer listed it). The EARLIEST phase over the
  attempts is kept: it is a deadline, and Ch10's raze came anywhere from turn 4 to 10 with our
  play.
- **`fates`, a list of `{ charId, boardTurn, x, y }`** (a list: the record is JSON, whose keys are strings): an owed recruit that left the map (`missed_recruits`
  with `left_map`), the first player turn it was gone on, the earliest. A recruit we or the enemy
  killed is the play's, never the game's, and is not kept. This is its own table, not a field on
  `arrivals` as the design comment had it: a recruit on the map from the start (Ch10's Amelia)
  has no arrival to hang it on.

Fogged arrivals stay out, as ADR 0386 has it: only what the screen showed.

## 2. How it is read

- **The hold** (`style.arrivals`) takes only a turn's arrivals: one with `by` comes when we act.
- **A pending recruit with `by`** (`bot.lua` `recruitsOf`) is a goal on no turn bound, and
  `botrun.lua` drops any remembered arrival whose character has come this attempt (`cameChars`),
  so Rennac pulls a talker toward his tile until the door loads him, and never after.
- **`Goals.closings`** takes the earlier of the simulated closing and the remembered one (enemy
  phase 1 is this turn's); a remembered phase already past closes nothing, since this attempt has
  kept the tile so far. Every reader of a tile's `closes` (the goals, `Goals.forfeited`, the
  exploring ranks) gets it.
- **`Goals.scriptedCloses`** treats a remembered departure as a script's removal, the earlier of
  the two.

## 3. The guide's `reinforcements` claims are not played

`campaign_env.resolve` sends every `reinforcements` claim (the 19 in `twin_strategy.yaml`, and any
in our chapters' `strategy_claims`) as kind `unresolved`, so the run reports it unplayed; the
bot's `reinforcements` behaviour and `difficulty.arrival_waves` are removed. Attempt 1 plays as a
first-time player in both games alike. `style.waves` is now set by no one; it stays as the slot
#569's remembered waves would fill. The YAML keeps the claims as wiki text.

**What moves.** Attempt 1 of vanilla Prologue to Ch8 and Ch13, and of every Manchego Stars
chapter whose twin's guide warned of waves, no longer holds before an arrival turn nor knows a
wave's looters. That is Nicolas's call: it changes what attempt 1 measures, in both games alike.

## 4. Not in this change

Item 4 of the design (`memory.kills`, a danger term on the tile a unit died on) touches a planner
weight, so it is measured before it is kept, and lands apart.

**Against ADR 0396's five tests.** (1) The quantities are ones the planner already reads: a
tile's deadline, a recruit's removal, the hold's turns, a pending goal. (2) Orderings: a plan
that misses a deadline ranks lower; nothing is banned. (3) Every objective alike. (4) It repeats
no ordering: a remembered date replaces nothing, it takes the earlier. (5) No unit, chapter or
turn is named in the code; they are the record's.
