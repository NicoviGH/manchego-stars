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

**The rule.** One owner, `Controller.won(start, now, finished)` (`controller.lua`, unit-tested with
stubbed reads): won is the chapter index having moved, or the game finished. The game is
finished only when the post-chapter save menu (`gProcScr_SaveMenuPostChapter`) is up AND
`gPlaySt.save_menu_type` is 3, the value only `MNC4` sets (`eventscr.c`: `MNCH` 1, `MNC2` 2;
`worldmap_main.c` 1; the prep screen's `StartPrepSaveScreen` 2 or 4; `bmdebug.c` 2). The menu
proc alone is not the end: the same proc is the prep screen's Save on the chapter's own index
(`prep_sallycursor.c` ~1201), and is also started by `GameControl_CallPostChapterSaveMenu`
(`gamecontrol.c`, after the index has moved), `EventBF_` (`eventscr_gmap.c`), `sub_8086928`
(`code_8086934.c`) and a debug command (`bmmenu.c`). `save_menu_type` is `gPlaySt` +0x4A bits
1-3 (`types.h` `struct PlaySt`; the offset was checked by compiling the struct, 0x4C bytes, and a
unit test pins the field order). `harness.lua`'s `INSPECT.chapterWon(start)` reads it through
`Controller.chapterWon`, and every waiter's `won` calls it: the bot api's, the clear drivers',
the fuzz and smoke drivers', `runEnemyPhase`'s in-loop exit (the final boss dying to a counter)
and `until_ = "chapter"`. `INSPECT.chapterWonOrTitle` is the one predicate for "won, or the
unhosted next chapter's title" (clear_ch02, clearCh04). A start is sampled through
`INSPECT.startChapter()`, which raises if the finished menu is already up, so a run never reads
as won from its first call. A unit test fails any `chapter() ~=` comparison with a start sample
left in `harness.lua`.

**Callers that needed no change.** `botrun.lua` records the chapter as won from `api.won()`
(`botrun.lua:1425` player phase, `:1976` enemy phase) with its clean-clear fields; `campaign.lua`
ends `done` on `arrive` answering "end" (`campaign.lua:416`), which `harness.lua`'s `api.arrive`
answers when the chapter played is in `cfg.last` (vanilla's two final chapters); `montecarlo.py`
already counts a campaign's `done` as its own answer.
