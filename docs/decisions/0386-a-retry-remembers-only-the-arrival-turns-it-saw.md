---
id: 386
title: "A retry remembers only the reinforcement arrival turns a failed attempt showed on screen"
date: "2026-11-01"
section: "Combat System"
issues: [510]
---

# A retry remembers only the reinforcement arrival turns a failed attempt showed on screen

**Decided (Nicolas, 2026-11-01), #510 step 9.** Narrows ADR 0376 decision 3 ("a retry knows what
earlier attempts saw, and only that"), which was decided but never built. **Not built yet:**
`campaign.lua`'s attempts still never read a result, and PR-E of the plan on #510 builds this.

**The rule.** From attempt 2 at a chapter start onward, the bot knows the turns on which
reinforcements arrived in any earlier failed attempt at that start, as far as the game showed
them on screen. It remembers nothing else: no enemy's stats or items, nothing that happened in
fog, no RNG outcome. It uses them only where a guide claim would be used: as one of the
triggers for the plan's commit-time lookahead, a second enemy phase played when a plan ends a turn
on, or one turn before, a known arrival (spec FR-017 on #510; its own ADR lands with that code,
plan task T067).

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
