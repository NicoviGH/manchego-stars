---
id: 187
title: "`CHECK_ALIVE` answers for a unit in ANY faction — so a recruit needs its FLAG too"
date: "2026-08-19"
section: "Operational Gotchas (durable)"
issues: [25]
---

# `CHECK_ALIVE` answers for a unit in ANY faction — so a recruit needs its FLAG too

`branch_on_check_alive`'s docstring says CHECK_ALIVE reads the ROSTER rather than the field, and
that is right as far as it goes — but "roster" is not "the player's units".
`GetUnitStructFromEventParameter` → `GetUnitFromCharId` (`bmunit.c`) sweeps unit indices
**1..0xFF**, every faction, and returns the first valid match. So CHECK_ALIVE means *does this
character exist somewhere and is it not dead*, and nothing more.

That is exactly right for Lupin and for Basil, and **wrong for Sahnar**, and the difference is
whether the unit is ever HOSTILE:

- **Basil** is a green escort who joins by `CUSA` in scene 5 and is never anyone's enemy — the
  same shape as vanilla's Natasha, whose own ending branch is a bare
  `CHECK_ALIVE(CHARACTER_NATASHA)`. A bare ALIVE is correct.
- **Lupin** is either on the ch04 carry-over roster or nowhere. A bare ALIVE is correct, and
  never-recruited collapsing with recruited-then-killed is the *point*.
- **Sahnar rises HOSTILE and only flips when Basil Talks her.** Kill Ravisin without ever
  turning her and she is alive, red, and standing on the map when the ending runs — CHECK_ALIVE
  says 1, and the berry scene plays with the party's own enemy thanking Basil by name.

The gate is therefore the **recruit flag first, then ALIVE**: `CHECK_EVENTID(EVFLAG_TMP(7))`
(set by `talk_recruit_script`'s `EVBIT_T(7)`, vanilla's own Natasha→Joshua flag) asks *was she
turned*, and `CHECK_ALIVE` then asks *is she still here*, so a Sahnar recruited and later killed
is silent too. **Vanilla chains precisely this pair** — `ch19a-eventscript.h`'s
`EventScr_089F8688` runs `CHECK_EVENTID(7)` into `CHECK_ALIVE(CHARACTER_TANA)` to pick its
ending text. Both `BEQ` to one shared label, because a beat that is SKIPPED has no second arm to
jump over; that is `save_all_bonus_script`'s shape, not `branch_on_flag`'s.

**The general rule: ask CHECK_ALIVE about a unit that could be an ENEMY and it will answer yes.**
Any conditional whose subject is an optional TALK recruit wants the flag as well.

_Recorded: 2026-08-19 (found while wiring ch05's scene 16; the first draft used a bare
CHECK_ALIVE and would have shipped it)._
