---
id: 374
title: "A bot result is read beside vanilla's, and the bot is proven on vanilla before ours is judged"
date: "2026-10-28"
section: "Combat System"
issues: [510]
---

# A bot result is read beside vanilla's, and the bot is proven on vanilla before ours is judged

**Every result the step-9 bot produces on our ROM is read as a pair, beside the same bot on the
vanilla twin** (Nicolas, 2026-10-28). One side alone says nothing about difficulty: a careful
stall on ours could be the level or the bot, and only the twin tells them apart.

**Bot or level, decided in this order:**
1. **The bot is proven on vanilla first.** Vanilla's chapters are the reference difficulty, so a
   bot that cannot clear vanilla's twin cleanly is the thing at fault, never the twin.
2. **A failure on ours is read in its trace before it is called the level.** Vanilla only
   exercises vanilla's situations: ch03's corner Mogall found four planner faults that vanilla
   Ch3 never reached, because Seth kills Bazba in one blow and no group attack is ever needed
   there (#510 comment 6480158861). The test is whether a human would have seen a move the bot
   could not. If so, it is the bot; if not, it is the level.
3. Only then does a paired verdict (`montecarlo.py cell`) measure the level.

**After every planner change, vanilla Ch3 attempts 1-8 are the regression check** (~50 s wall,
`montecarlo.py attempts --vanilla` from the saved Ch3 start; the env recipe is in #510 comment
6478205562). It caught a fault on its first use: letting a unit plan onto an ally's tile had
replaced Eirika's free way forward instead of adding to it, and both careful attempts stalled
with the throne open.

**Attempts from one saved start are not a sample.** Each attempt loads the same start, RNG
included, so attempts of one style replay the same game: eight attempts are about three distinct
games. They show what the bot does; only a cell's seeds measure how often.
