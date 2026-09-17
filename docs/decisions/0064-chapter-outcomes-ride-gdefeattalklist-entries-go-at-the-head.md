---
id: 64
title: "Chapter outcomes ride gDefeatTalkList; entries go at the HEAD of the table."
date: "2026-06-09"
section: "Combat System"
issues: []
---

# Chapter outcomes ride gDefeatTalkList; entries go at the HEAD of the table.

A chapter's win and lose are both event-flag watchers in `EventListScr_<Ch>_Misc`
(vanilla Prologue shape, `prologue-eventinfo.h`): `DefeatBoss(<ending scene>)` fires on
`EVFLAG_DEFEAT_BOSS` and `CauseGameOverIfLordDies` fires on `EVFLAG_GAMEOVER`. Neither
flag is set by the engine directly — **both are set by the dying unit's `gDefeatTalkList`
entry** (`.flag` on the defeat quote; `CA_BOSS` alone sets nothing — every vanilla boss
has a chapter-keyed entry with `EVFLAG_DEFEAT_BOSS`). Three traps, all hit on 2026-06-09:
- Emptying the Misc list silently removes BOTH the win and the lose condition.
- `GetDefeatTalkEntry` (eventinfo.c) returns the FIRST match, and vanilla gives every
  playable slot a generic `chapter = 0xFF` death quote mid-table — so injected
  chapter-keyed entries must go at the **head** of the list (vanilla's own ordering:
  boss entries first, generics after), or e.g. NATASHA's generic quote shadows the
  flagged one and game over never fires. Never append after the `{.pid = -1}`
  terminator either: the scan stops there.
- The goal banner ("Defeat boss" vs the host chapter's "Seize gate") is chapter DATA
  (`chapter_settings.json` `goal`), not events — copy the vanilla Prologue's block.
Boss AI gotcha: O'Neill's `.ai = {0x6, 0x3, …}` decodes to **DoNothing + NeverMove**
(`cp_data.c gAi1ScriptTable`/`gAi2ScriptTable`) — he only attacks because the vanilla
tutorial event-scripts it. For unscripted stationary-aggressive bosses copy Breguet:
`{0x3, 0x3, 0x9, 0x20}` (ActionStanding 100% + NeverMove).
_Decided: 2026-06-09 (found via the automated ch00 playtests; see Automated playtests)_
