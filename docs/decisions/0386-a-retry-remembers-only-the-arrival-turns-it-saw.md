---
id: 386
title: "A retry remembers only the reinforcement arrival turns a failed attempt showed on screen"
date: "2026-11-01"
section: "Combat System"
issues: [510]
---

# A retry remembers only the reinforcement arrival turns a failed attempt showed on screen

**Decided (Nicolas, 2026-11-01), #510 step 9.** Narrows ADR 0376 decision 3 ("a retry knows what
earlier attempts saw, and only that"), which was decided but never built. Built in PR-E of the
plan (#510 comment 6563384310); see "Built (PR-E)" below.

**The rule.** From attempt 2 at a chapter start onward, the bot knows the turns on which
reinforcements arrived in any earlier failed attempt at that start, as far as the game showed
them on screen. It remembers nothing else: no enemy's stats or items, nothing that happened in
fog, no RNG outcome. It uses them only where a guide claim would be used: as one of the
triggers for the plan's commit-time lookahead, a second enemy phase played when a plan ends a turn
on, or one turn before, a known arrival (spec FR-017, #510 comment 6563384018; its own ADR lands with that code, plan task
T067 in #510 comment 6563384310).

**Why so narrow.** A player who resets after a death remembers being ambushed (ADR 0376: "A
player trying again would have seen the map and stuff"). An arrival turn is the most
consequential thing attempt 1 cannot know, and it is easy to read off what the screen showed.
A wider memory turns a retry into a search over RNG outcomes, which no player does.

**What it never touches.** Verdicts measure attempt 1 only (ADR 0385), so retry memory never
changes a measured number. It only helps a campaign get through a chapter so the next chapter's
start can be reached. Attempts with memory are reported separately from first attempts. Retries
for campaign generation stay capped.

**Research record 0001 still holds:** the playtesting bots it surveys do not learn between
attempts, and measured attempts here do not either.

## Built (PR-E)

- **What is seen.** botrun's record carries `arrivals_seen`: `{ turn, x, y, charId }` for each red
  unit that came onto the field, read from the arrival `event`s botrun already traces, and only
  when the board that first showed it did not have it `fogged` (the game's own fog flag on the
  unit). An arrival under fog is not listed, even once it is later seen. Its turn is the one a guide
  claim would cite (player-phase turns, `difficulty._vanilla_reinforcement_turns`): the player
  phase whose board first shows it. One that acted in the enemy phase it landed in gets that
  phase's turn instead. One that landed in an enemy phase and did not act reads as the next turn's.
- **What is remembered.** `campaign.lua` keeps, per chapter start, the union of the TURNS in every
  earlier failed attempt's `arrivals_seen`, each once, in order, and from attempt 2 on hands them to
  the play as one more list in `style.arrivals`: where a reinforcements claim's turns go, read by
  `Bot.nextArrival`, so the march holds the turn before, as a claim makes it. The tile and the unit
  stay in the record and are never passed on. Attempt 1 gets nothing. It is NOT a lookahead trigger:
  that trigger was dropped (ADR 0389), because the second phase cannot place the wave, and a turn
  alone never could.
- **One consequence.** An attempt played alone (`api.only = k`, `montecarlo.py attempts`' pool) has
  no earlier result to remember: the workers run side by side. So pool attempt k plays the style and
  team the loop would after k - 1 failures, but without the memory. Attempt 1, and so every measured
  cell (ADR 0385), is the same either way (`test_campaign.lua` pins `api.only = 1`).
- **Measured (2026-11-03).** The suite's tuning seeds (26 first attempts) saw 137 arrivals on
  screen: scout-ch13 48, scout-ch10 28, scout-ch14 20, vanilla Ch4 13, Ch5 11, Ch1 5, Ch2 2, ours
  ch01 6, ch02 4, the rest none. The suite plays attempt 1 only, so none was remembered and its play
  and CPU are untouched (ADR 0389 has the suite's cost). A remembered arrival is used only on a
  campaign's retry, which no suite run makes.
