---
id: 409
title: "The scout lap carries a campaign past a chapter it cannot clear clean"
date: "2026-11-13"
section: "Combat System"
issues: [510]
---

# The scout lap carries a campaign past a chapter it cannot clear clean

The finish line for #510 is the whole vanilla game beaten clean (Nicolas, 2026-11-13). A
campaign stops at the first chapter it cannot clear clean (`bot_fault`), so every wall after
it is unseen: 22 of vanilla's 38 story maps have never been loaded, and every record is
Eirika's route (#510 comment 6872554917).

**Decision.** `montecarlo.py resume --scout` carries a campaign on past such a chapter. It
takes the first win with no player unit lost, and from attempt `M.SCOUT_PATIENCE` (4) on, the
first win of any kind. A chapter so passed says `scouted`, never `cleared`; every line of the
campaign says `scout`; the dead are not carried. A chapter with no win in the cap still stops
it. `resume --route 1|2` picks the branch at Ch8's split (Ephraim's route had no way in).

**Why first win and not the best of several.** Going back to an earlier attempt's end means
playing it again; the lap is for finding walls and harness faults, not for measuring them.

**What it is not.** A scout campaign's party is smaller than a clean one's, so a late board
is harder than the real one. Its records say where the bot fails and why; they never feed a
difficulty verdict, a suite fixture or a pinned start. Only a clean lap meets the finish line.
