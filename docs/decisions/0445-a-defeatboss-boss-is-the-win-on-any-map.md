---
id: 445
title: "A DefeatBoss boss is the win on any map"
date: "2026-11-22"
section: "Combat System"
issues: [721, 699, 510]
---

# A DefeatBoss boss is the win on any map

**Decided (#721), #510 step 9.** A rule the game sets; no weight. The bot read a boss's death as
the win only under a Defeat Boss goal. Vanilla Ch13 (E_13) has a Survive goal window but its Misc
list carries `DefeatBoss(EventScr_Ch13a_EndingScene)` (`ch13a-eventinfo.h:25`), so the game ends
the chapter when Aias dies. The bot priced that kill as a plain kill (win chance 0, so
`Goals.forfeited` shut nothing) and killed him on turn 4, before Cormag arrives on turn 5, or
while Cormag was on the map (`m699c13`: Cormag missed in 15 of 15 attempts).

**The game's rule (decomp, read).** `DefeatBoss(scr)` is `AFEV(EVFLAG_WIN, scr,
EVFLAG_DEFEAT_BOSS)` (`Main_Code_Helpers.h:27`). A unit's death sets the flag of its
`GetDefeatTalkEntry` row (`SetPidDefeatedFlag`), and `RunWaitEvents` (`eventinfo.c`) searches the
Misc list after each action. The flag alone ends nothing: 31 rows carry `EVFLAG_DEFEAT_BOSS`
(Ch3's Bazba, Ch8's Tirado, ...) on chapters whose Misc list has no `DefeatBoss`.

**What changed.**
- `sight.lua`, `s.objective.boss`: read on every map, not only under a boss goal. Under a boss goal
  it is as before. On any other goal a red unit whose row raises the flag counts only if the game's
  own Misc search, run with that flag set in a sandbox, finds an event (`CHAPTER_MISC`). A one-time
  read at chapter start (a few game calls per red unit), not per turn.
- `planner.lua`, `M.winKind(objective)`: the one owner of "this boss's death is the win": `"boss"`
  when the goal is a boss goal or `objective.boss` is set, else the goal's own kind. `plan` calls
  it once, so every site that keyed on `objective == "boss"` follows: `fx.win` (the kill is the
  win, so the forfeit ledger prices it), `BOSS_WORTH` (a wound on the boss is a step to the win),
  `endsIn` (a counter that kills him ends the chapter), `advances` (a wound on him is progress).
- Not changed, on purpose: a Rout stays a Rout (its last red unit also ends it; one kind is
  priced); the throne assault (`M.throne` reads `kind == "seize"`); `objectiveTile` in `bot.lua`
  (where units march: on a Survive map they do not march at the boss, which is not this issue);
  the survive win itself (turn 12) is untouched.

**Proof (ADR 0430).** A unit test that fails on main (`test_a_defeat_boss_boss_is_the_win_on_a_survive_map`):
a survive map, a DefeatBoss boss killable on turn 4, a recruit owed on turn 5: the kill forfeits
the recruit and is not played. Controls: no boss named, the kill is no win; a boss map as before.
One replay: see PR #721's description.
