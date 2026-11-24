---
id: 466
title: "A talker marches on a recruit our act will load"
date: "2026-11-24"
section: "Combat System"
issues: [741, 510]
---

# A talker marches on a recruit our act will load

**Decided (Claude, #741), #510 step 9.** Amends ADR 0464 (a retry remembers an arrival our own
act loaded, with `by`) and ADR 0436 (an owed recruit a retry saw arrive is a goal).

**Why.** Vanilla Ch14 (`x741c`, attempt 2): our door at (22,17) loads Rennac at (22,12). A retry
knows it and `recruitsOf` makes him a pending recruit (`arrival:28`) at his meeting tile, a goal
in the ledger. But `exploring` built its talker pairs from `ctx.onField` only, so no talker got
an `exploreGoal` toward a recruit that is not on the board yet. L'Arachel, his only talker,
waited at (18,22) on turns 2 to 4, then trailed him one or two turns behind until he left the
map on turn 12.

## What changed

`bot.lua` `recruitTargets` is the one list of the recruits a talker marches on: the field's, then
each pending one (`ctx.pendingRecruits`, at its meeting tile) in id order. `exploring`'s talker
pairs read it, through the same `claimsOn` / `talkersOf` as before (a claim's `by` still names
the talker).

Sites checked for the same cause:
- `exploring` talker pairs: fixed (above).
- `recruitFirst`: left as it is. It is `Bot.decide`'s greedy path, which never reads
  `ctx.pending` (only the planner's `candidates` does), so no pending recruit reaches it.
- `talkHabit`, `talkFrom`: a Talk needs the unit on the board; nothing to do for a pending one.
