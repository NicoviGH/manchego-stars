---
id: 438
title: "The game's end is a won chapter"
date: "2026-11-21"
section: "Working Conventions (Definition of Done)"
issues: [696, 510]
---

# The game's end is a won chapter

**Decided (the #696 fix), #510 step 9.** Extends ADR 0370 (the bot plays chapter to chapter).

**The fault.** The harness called a chapter won when `gPlaySt` chapter index moved off the start.
The last chapter's boss kill does not move it: vanilla Eirika-route E_21x (and Ephraim-route
I_21x) run the ending scene and then `MNC4` (`eventscr.c`), which sets `save_menu_type = 3` and
`GAME_ACTION_PLAYED_THROUGH` and no next chapter. The game goes to the post-chapter save menu
(`gamecontrol.c`, label 16). Nothing counted that as a win, so `api.act`'s wait ran out and the
run crashed on a game the bot had beaten.

**The rule.** One owner, `Controller.won(start, now, finished)` (`controller.lua`, unit-tested):
won is the chapter index having moved, or the game finished. `harness.lua`'s
`INSPECT.chapterWon(start)` reads the two facts (`gPlaySt` chapter; the
`gProcScr_SaveMenuPostChapter` proc being active) and every waiter's `won` calls it, the bot api's
and the clear drivers'. `botrun.lua` then records the chapter as won with its clean-clear fields,
and `campaign.lua` ends the campaign `done` through the path it already had (`cfg.last`, vanilla's
two final chapters, so `arrive` answers "end"); `montecarlo.py` already counts a campaign's `done`
as its own answer. Neither needed a change.

**Why the proc and not `save_menu_type`.** The proc is a symbol the harness already reads. The
post-chapter save menu on any other chapter's own index would be the unused debug menu
(`bmmenu.c`); the ordinary one comes up after the chapter index has moved on, which already counts.
