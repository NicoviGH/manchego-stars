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

**Decision 1: each saved start records `bots`**, the bot versions (montecarlo.py's instrument)
that played the chapters before it, oldest first, each once in a row. New Game's first map has
none (`[]`); every later start a run reaches gets that run's version after its own start's list
(`Campaign.withBot`); a resumed start keeps its record's list. A start resumed from a record
that never kept them stays unknown (`bots` absent) for every start after it. The campaign reads
its version where botrun does (`INSPECT.instrument`, from `PT_INSTRUMENT`, which montecarlo.py
sets for every task); a run without one writes "unversioned" into the list, the one place a
missing version needs a name.

**Decision 2: every record says whether its start was stale; a stale start is still played.**
Each chapter line carries `start_bots`, and `records_of` judges each BOTRUN record of that
chapter `stale` (`stale_start`): true when a bot whose code differs from the one that played
the attempt played a chapter before its start, or who did is unknown. Only the bot hash is
compared; a suite manifest version (`+vN`) changes no play. The campaign's end record keeps its
first start's `start_bots` and `stale`, which every later start has behind it. This covers
every run kind that plays through the campaign (resume, attempts, cells, the suite), not only
resume. Nothing is refused: Nicolas does not want a lap re-run after every change. `resume`
prints a line for each stale start before it plays, and a chapter cell prints how many of its
starts are stale under its verdict. Which verdicts should leave stale runs out is not decided
here: the records now say it, and the call is Nicolas's.

**The New Game records were backfilled.** The vanilla store's 253 `0.json` records (chapter 0,
Eirika and Seth, 0 gold: New Game's start in every one, checked before writing) got `"bots":
[]`, so a lap from the prologue starts current. No other start was touched: whoever played up
to them is not on record.

**Proof.** `test_campaign.lua` (New Game's first map names no bot, the next start this run's,
each version once in a row; a resumed start keeps its list; an unknown one stays unknown; each
chapter line carries its start's list) and `test_montecarlo.py` (`start_bots`: none played,
this bot only, an older bot, a manifest version alone, a list that is not one, no record; the
stale line resume prints and the count a chapter cell prints; each record judged from its
chapter line, a chapter with none and an end with none as stale, the end from the first start
against the version its attempts played), each failing on main. Three fresh runs of campaign
`cs-s4006`, about 11 s each, every chapter won clean: `vers2` (from the prologue through Ch1,
after the review) saved `0.json` with `bots: []` and `1.json` with this bot's version, and its
records say `stale: false`; `vers3` (from the old Ch2 start copied into `vers2`, which has no
list) printed "stale start vers2-cs-s4006/2: played up to by an unrecorded bot", and its
records say `stale: true`; `vers1` was the same check before the review.

**Untested:** the chapter cell's stale count in a real cell (its line is unit-tested).
