---
id: 470
title: "The death cap reads the next enemy phase and the wear, never the lookahead's second phase"
date: "2026-11-24"
section: "Combat System"
issues: [766, 743, 510]
---

# The death cap reads the next enemy phase and the wear, never the lookahead's second phase

**Decided (Nicolas, 2026-11-24, on #766, option A).** This amends ADR 0389 and ADR 0384. ADR 0421
(the wear) stands.

**Why.** Vanilla Ch14 s4003, run `r766i`, attempt 2, turn 11:
- The lookahead (ADR 0389) sent its four finalists to a second enemy phase. All four were copies
  of one plan, and all four were under the cap on the next enemy phase.
- The second phase read Colm (charId 9) at 0.835 to die. Admission read both phases, so all four
  became inadmissible.
- The pick after the lookahead looks only among the finalists. The admitted beam plans had never
  been read on a second phase, so they could not win. The bot played a plan the record called
  over the cap. Colm did not die.

How often the second phase is right, over the last 300 stored traces in the vanilla store
(`c25b145e3745`): for every played plan the lookahead read, the protected units read at 0.05 or
more to die over both phases.
- Plans played over the cap while an admitted plan was offered (263 of 8,397 decisions, 3.1%):
  the readings summed to 166 expected deaths; 14 of those units died that turn or the next.
- Every other played plan the lookahead read: 179 expected deaths, 40 died.
- Readings of 0.90 or more: 3 deaths in 115.
- **Caveat:** plans the lookahead kept from being played were never played, so their outcomes
  cannot be checked.

The second phase has our army stand still or play one reply, while the bot replans every turn.
ADR 0389 already found its readings far too high on Manchego Stars ch03 (0 of 8 came true) and
ranks the next phase first among plans over the cap. Admission was the one place it still ruled.

## What changed

- **`planner.lua` `admit()`:** a plan is admitted when each protected unit's `pr.capDie` is within
  the cap. That is its death chance before the lookahead raised `pr.die`: the next enemy phase,
  plus the wear's three phases for a unit no heal reaches (ADR 0421, unchanged).
- The idle rule's two cap checks (ADR 0439, 0441: an under-cap march is not idle; a wound-only
  advance counts only under the cap) read the same excess (`st.capExceed`).
- The lookahead still runs, and its reading still counts in the rank: `max_die`, `sum_die`,
  `max_exceed`, `sum_exceed`, `hp_left`, `game_over` and `value` all take it. It only breaks ties,
  after progress among admitted plans.
- **Consequence:** the bot will march a unit into a death read as certain two enemy phases out,
  when the next phase is safe (Nicolas agreed knowing this).

## Proof

- `test_bot.lua`: eight lookahead assertions rewritten to the new rule; each fails on the old
  admission. The wear tests (`wear: ... A stays out`) pass unchanged; they fail if the wear is
  dropped from the cap with the second phase.
- Replay `a470a`, vanilla Ch14 s4003, two attempts: see #766.
