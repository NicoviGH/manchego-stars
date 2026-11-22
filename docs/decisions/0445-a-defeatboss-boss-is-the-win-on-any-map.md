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
- `sight.lua`, `s.objective.boss`: read on every map, in the same sandbox pass as `gameOver`
  (one `GetDefeatTalkEntry` per unit), not only under a boss goal. Under a boss goal it is as
  before. On any other goal a red unit whose row raises `EVFLAG_DEFEAT_BOSS` counts only if setting
  its death flag makes the Misc list (`CHAPTER_MISC`) offer a new script whose completion flag is
  `EVFLAG_WIN` (`M.winEvent`, over `availableScripts`, the same walk `nextTurnEvent` uses). Any
  available entry is not enough: vanilla Ch1's Misc list offers `AFEV(EVFLAG_TMP(7), ...)` (and an
  `AREA` entry) for Breguet's flag, and only the Seize ends Ch1. A one-time read at chapter start,
  no per-turn cost.
- `planner.lua`, `M.winKind(objective)`: the one owner of "this boss's death is the win": `"boss"`
  when the goal is a boss goal or `objective.boss` is set, else the goal's own kind. `plan` calls
  it once, so every site that keyed on `objective == "boss"` follows: `fx.win` (the kill is the
  win, so the forfeit ledger prices it), `BOSS_WORTH` (a wound on the boss is a step to the win),
  `endsIn` (a counter that kills him ends the chapter), `advances` (a wound on him is progress). The named boss only: `M.isWinBoss(e, bossId)` compares `charId` to
  `objective.boss` (a second CA_BOSS on the map is no win; with no name, any CA_BOSS, as a boss goal
  with no row). One owner beside `winKind`, with `st.winBoss` carried in the plan state.
- Not changed, on purpose: a Rout stays a Rout (its last red unit also ends it; one kind is
  priced; known gap: a Rout map whose boss's death ends it early is priced as a plain kill); the throne assault (`M.throne` reads `kind == "seize"`); `objectiveTile` in `bot.lua`
  (where units march: on a Survive map they do not march at the boss, which is not this issue);
  the survive win itself (turn 12) is untouched.

**Proof (ADR 0430).** Unit tests that fail on main: a survive map, a DefeatBoss boss killable on
turn 4, a recruit owed on turn 5 (the kill forfeits him and is not played), `winEvent`'s cases, and
a second CA_BOSS whose kill is no win. Controls: no boss named, a boss map, Seize and special goals.
Emulator read (temporary print, reverted): vanilla Ch1 `objective.boss` is nil with this rule and
was Breguet (70) on the first draft of it (any available Misc entry); Ch13's is Aias. One replay
(PR #723): the ledger's win row on turn 3 reads 0.85 -> 1.00 (0.85 -> 0.85 on main), both
attempts won on turn 3 with 0 deaths. Cormag was not saved: attempt 1 won on turn 3 before his
turn-5 arrival, so attempt 2 has no arrival memory and no recruit goal for the kill to forfeit
(#724 is the follow-up: reading the arrival from the script).
