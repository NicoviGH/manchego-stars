---
id: 401
title: "On a Defeat Boss map a boss the party knows of is the march goal, in sight or remembered"
date: "2026-11-11"
section: "Combat System"
issues: [510]
---

# On a Defeat Boss map a boss the party knows of is the march goal, in sight or remembered

**The principle is Nicolas's (2026-11-11), #510:** "it depends on the level's stated win
condition: 'defeat boss' vs 'defeat all' should behave differently". **The call below applies it
and is Fable's**, made under his word that day to take the approach in hand; PR #600 puts it to
him. The march already followed the principle for a boss in sight. This closes the one hole:
a boss the fog hides and a retry remembers (ADR 0399) was a danger the cap read, and never a
goal.

**The error.** `Bot.objectiveTile` looked for the boss among the enemies in sight only. On a
fogged Defeat Boss map a retry therefore marched each unit on its nearest known enemy, and
with memory there are more of those, nearer. The retries got slower where a player's get
faster.

**The evidence (vanilla Ch6, every record, bot versions pooled, so patterns and not rates).**

- The Civilians are a clock. Of 192 wins they all lived in 13 of 13 wins of 8 turns or fewer,
  5 of 20 of 9 turns, 0 of 159 of 10 or more; the first one dies on turn 8 in 156 of the 174
  wins that lost one.
- Memory slowed the retries. First attempts (no memory): 53 wins, median about 10 turns.
  Retries before ADR 0399: 34 wins, median 10, Civilians alive in 9. Retries with memory: 105
  wins, median 12 to 13.5, Civilians alive in 1.
- The time is lost on the approach, not at the boss: in most wins the boss falls the turn a
  unit reaches it. Style and start do not separate fast wins from slow ones.

**The call.** On a Defeat Boss map the march goal of a unit with no goal of its own is the boss
once the party knows where it stands: in sight, or in fog and remembered (`ctx.threats`). The
boss is the unit the objective names (`sight.objective.boss`, whose death ends the chapter):
another `CA_BOSS` unit is no goal beside it, in sight or remembered; with none named, the
first `CA_BOSS` unit known, as before. A boss no attempt showed is no goal: the march heads for
the nearest enemy in sight, or pushes
the fog back, as before. A Rout map is unchanged. A unit sent to a recruit, village or chest
still goes there first (`goalFor`), a plan that ends the chapter with a goal open still pays
its worth (`goalTerm`), and a clear with a reward untaken is still not clean.

**ADR 0396's five tests.** 1 The objective's kind and the boss are the game's (the chapter's
goal byte, the unit whose death raises the goal's flag); what a retry knows is ADR 0399's.
2 It picks a march goal and forbids nothing. 3 It is the Defeat Boss case of "the win
condition says what the march is for": Seize marches on its tile, Rout on the nearest enemy,
Survive holds. 4 No second owner: the one place the march goal is chosen, widened from "in
sight" to "known". 5 Its sentence names no unit, chapter or turn.

**What it changes.** Retries on a fogged Defeat Boss map, from the attempt that remembers the
boss on. A first attempt (ADR 0385's measured one) only where a second `CA_BOSS` unit stands
in sight on a Defeat Boss map whose objective names its boss: the march no longer heads for
it. The suite below shows no start where that happens.

**Its limit.** A remembered boss is aimed at where it stands now, not where an attempt last
showed it: ADR 0399 reads every remembered unit from its live tile, and this takes that read
as it is. A boss that walks under fog is therefore followed, which is more than the screen
showed. The bosses the bot meets today hold their tile; a chapter whose boss roams in fog is
where this would need the tile it was last seen on.

**No kept retry guard.** The frozen suite plays first attempts, so nothing kept plays this on
the ROM. The unit test pins the goal and the step the unit takes toward it; the ROM witness
is the run below (`resume --game vanilla --campaigns cs-s4001,... --chapter 7 --last 7`).

**Witness (`resume --tag kb1`, and `kb2` on the reviewed code with the same result attempt for
attempt; the eight vanilla campaigns stopped at Ch6, 2026-11-11).**
Before: none of the eight cleared Ch6 clean in 6 styles (`cell-starts.json`: `bot_fault`).
After: **8 of 8 clear it clean**, seven on attempt 2 and one on attempt 3, in 4 to 6 turns.
Attempts 1 play as before (8 to 12 turns, 1 to 5 deaths). The one attempt 2 that was not
clean (4007) lost a player unit on turn 2 and won in 4 turns; no win left a reward untaken.

**The suite (`suite --held-out`, 2026-11-11, run again on the reviewed code): promoted, 0
regressions.** Every number is ADR
0400's final run's: 2,685,802 `AiDecideMain` calls (SC-003: within, +7.8% on the frozen
2,490,781), the same five deaths that lived when frozen (signals, not blockers), held-out 4 of
28 lost, none new since the freeze. First attempts play as on main.

**Not in this change.** The look (#510 comment 6786548233, branch `feat/510-w1-look-shadow`)
stays in shadow, unmerged: Ch6 did not need its deeper phases, the walker's guards or its
allowance.
