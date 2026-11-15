---
id: 417
title: "Each saved start names the bots that played up to it, and a resume says when it is stale"
date: "2026-11-15"
section: "Combat System"
issues: [510]
---
# Each saved start names the bots that played up to it, and a resume says when it is stale

Nicolas (2026-11-15) asked that the bot be versioned, so a run shows whether it played from old
saves or an old bot version. Half of that existed: every BOTRUN record carries `instrument`
(montecarlo.py's `bot_hash` over the driver files and `harness.lua`, plus the suite manifest's
version; 745 of the vanilla store's 746 attempt records have it). A saved chapter start
(`<n>.json`) named no version at all, so a run resumed from `party1e`'s Ch15 start could not
tell that older bots had played Ch0 to Ch14.

**Decision 1: each saved start records `bots`**, the bot versions that played the chapters
before it, oldest first, each once in a row. New Game's first map has none (`[]`); every later
start a run reaches gets that run's version after its own start's list (`Campaign.withBot`); a
resumed start keeps its record's list. A start resumed from a record that never kept them stays
unknown (`bots` absent) for every start after it. The campaign learns its version from
`PT_INSTRUMENT` (montecarlo.py sets it for every task); a run without one writes "unversioned".

**Decision 2: a stale start is played, and said to be stale.** `montecarlo.py resume` reads the
start's `bots` (`start_bots`) and stamps every record of the task with `start_bots` and
`stale`: true when a version other than this run's played a chapter before it, or the list is
unknown. It prints one line for each stale start before the runs begin. It never refuses one:
Nicolas does not want a lap re-run after every change. A reading that relies on the bot (a
verdict, a refreeze, a finish-line claim) uses records with `stale` false.

**The New Game records were backfilled.** The vanilla store's 253 `0.json` records (chapter 0,
Eirika and Seth, 0 gold: New Game's start in every one, checked before writing) got `"bots":
[]`, so a lap from the prologue starts current. No other start was touched: whoever played up
to them is not on record.

**Proof.** `test_campaign.lua` (New Game's first map names no bot, the next start this run's,
each version once in a row; a resumed start keeps its list; an unknown one stays unknown),
`test_montecarlo.py` (`start_bots`: none played, this bot only, an older bot, a record with no
list, no record; the resume stamp), each failing on main.

**Untested:** the harness's `arrive` returning `bots` in the emulator; the fresh lap from the
prologue is its first run.
