---
id: 409
title: "The scout lap carries a campaign past a chapter it cannot clear clean"
date: "2026-11-13"
section: "Combat System"
issues: [510, 664]
---

# The scout lap carries a campaign past a chapter it cannot clear clean

The finish line for #510 is the whole vanilla game beaten clean (Nicolas, 2026-11-13). A
campaign stops at the first chapter it cannot clear clean (`bot_fault`), so every wall after
it is unseen: 22 of vanilla's 38 story maps have never been loaded, and every record is
Eirika's route (#510 comment 6872554917).

**Decision.** `montecarlo.py resume --scout` carries a campaign on past such a chapter. A
chapter first gets every attempt for a clean clear (the cap, `--attempts` or 12); only then
does the lap carry on, from its best win: the fewest player units lost, then the earliest
(amended 2026-11-19, #664; below). A win that lost only a green (an ally the player does not
control) counts as one with no player unit lost. A chapter so passed says `scouted`, never
`cleared`, and `scouted_from` names the attempt carried on from; every line of the campaign
says `scout`; the dead are not carried. A chapter with no win in the cap still stops
it. `resume --route 1|2` picks the branch at Ch8's split (Ephraim's route had no way in).

**Amended 2026-11-19 (#664, Nicolas): every attempt for a clean clear, then the best win.**
The first version took the first win with no player unit lost, and from attempt 4 the first win
of any kind (`SCOUT_PATIENCE`), because going back to an earlier attempt's end meant playing it
again. Nicolas's call: the bot's capability is a clean clear on any attempt within the cap
(first-attempt clean clears are rare for people too), and attempts-to-clean is a metric. A lap
that moved on at attempt 1-3 never tried for the clean clears that would have come later, so
scout laps undercounted them (#639's laps hit this).

- Going back is now cheap: each unclean win's end state is kept in memory (harness `api.keep`,
  the emulator's state buffer; only the best so far, so at most one held) and put back at the
  cap (`api.restore`), as `api.load` puts back a chapter's start. Nothing is played again.
- Best = fewest player units lost, because the lap carries on with the survivors; then the
  earliest, so a tie never saves a state for nothing. A chapter's line keeps that win's turns,
  deaths, misses and team.
- Cost: a chapter the bot cannot clear clean now plays the whole cap (12) where it played 1 to
  4. That is the price of counting clean clears on later attempts.
- Test: `test_campaign.lua`'s two scout tests; both fail on the first version's rule.
- Proof in the game (2026-11-19): `resume --scout --attempts 2 --route 1` from
  `t639-cs-s4003/9` (vanilla Ch8). Both attempts won with one unit lost (attempt 1 in 18 turns,
  attempt 2 in 12). The lap kept attempt 1 (the tie goes to the earlier), restored it at the cap
  and finished `done`. `api.restore` checks the turn and the dice against what `api.keep` read,
  and refuses a state that differs (tag `p664c`).

**What it is not.** A scout campaign's party is smaller than a clean one's, so a late board
is harder than the real one. Its records say where the bot fails and why; they never feed a
difficulty verdict, a suite fixture or a pinned start. A scout lap's states folder holds a `SCOUT` file, and `resume` refuses to carry it on
without `--scout`. `--route` is refused on Manchego Stars. Only a clean lap meets the finish line.
