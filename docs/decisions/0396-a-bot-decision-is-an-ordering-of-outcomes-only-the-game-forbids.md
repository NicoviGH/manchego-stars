---
id: 396
title: "A bot decision is an ordering of the game's outcomes; only the game forbids"
date: "2026-11-08"
section: "Combat System"
issues: [510]
---

# A bot decision is an ordering of the game's outcomes; only the game forbids

**Decided (Nicolas, 2026-11-08: write the style down so it stops recurring), #510 step 9.** This
is how the playtest bot's decisions (`tools/playtest/planner.lua`, `bot.lua`, `sight.lua`) and
the ADRs and comments about them are written. The bot has to play the whole game in every
style. A rule written to stop one witnessed death keeps holding on every chapter after it,
and on a map nobody had in mind it can be wrong.

**Why.** On ch03 the fixes kept arriving as conditions: "a step into reach is never the
commit", "a certain death is never the commit", "never strike where the counter alone can
kill". Each was true of the board it came from, and each was a second owner (a second place
deciding what the planner's rank, ADR 0384, already decides). Nicolas, more than once: "not
the same sins as before, rules that don't scale". The research behind this record (research
record 0025) found the same split in game-AI practice. Decision logic that generalises scores
outcomes, and keeps a hard "no" for what the game itself forbids or decides. Strong Fire Emblem
players also reason in quantities: turns, threat ranges, who can strike whom.

## The rules

1. **A decision orders boards, not conditions.** It says which board after a move is preferred
   and by which quantity: the chance a protected unit dies, the chance of a game over, the
   goals forfeited, the turns gained toward a goal, the damage dealt and taken, the chance to
   win. Each one is read from the game (its forecast, its enemy phase, its objective) or
   counted by the planner. A rule that cannot name its quantity is not ready to write.
2. **Only the game says no.** A hard filter is allowed only for what the game itself forbids
   or decides: an act it does not offer, or a game over. Everything else is ordered or priced,
   and its risk goes to the style's cap.
3. **The cap is the risk a style prefers** (Nicolas, 2026-11-08; ADR 0384's amendment of that
   date, on the unmerged T100a-R branch until it lands). Over it, plans are still compared by
   how far over they go. A second, stricter ban beside it is a second owner.
4. **Waiting is a move like any other.** It is judged by what the board after it gains, not by
   which kinds of act it holds.
5. **A witnessed death is evidence about the model, not the specification.** Before a fix,
   name the model error, for example "the lookahead held the player's units still". Fix what the
   model predicts, then measure every style, the turns to win, and a second chapter or
   objective (the frozen suite, ADR 0395), not only the chapter that showed it.

## The test a new rule passes before it is written

1. It names a quantity the game produces or the planner already computes ("the change in the
   chance to die", not "steps into reach").
2. It is an ordering or a price, not "if X then never Y". The one exception is a game rule,
   cited to the function or flag that enforces it.
3. Ask whether it holds on every objective (Rout, Seize, Defeat Boss, Defend, fog) and in every
   style. If you can name one case where it is wrong, it is a special case.
4. It does not repeat an ordering that already exists. If the rank already settles it, a ban
   is a second owner.
5. Its sentence names no unit, chapter, turn or witness. Witnesses belong in the record's
   "Measured" or "Piloted" note.

## Before and after (today's text)

- "A plan that only steps into reach is never the commit." **Becomes:** a commit over the cap is
  played for what it buys (progress, goal worth, enemy HP removed), so a step that buys none of
  them ranks below holding.
- "A certain death is never the commit." **Becomes:** nothing new. ADR 0384's over-cap order
  (`M.outranks`) already puts the surest death last.
- "Waiting buys something when it gains ground, heals, takes a goal, deals a blow, or meets an
  enemy strike." **Becomes:** waiting is preferred while the judged board after it is better on
  a quantity the rank reads. A turn-start heal the judge does not model is a gap in the model
  to close, not a reason to wait.
- "Refuse every attack whose counter alone can kill (every style but greedy)." **Becomes:** an
  attack's death chance includes its counter's, and the cap judges it. **Not yet changed:**
  this one changes play (bold could then take a counter risk it never takes now), so it needs
  Nicolas's call and a pilot first. See "Known breaks" below.

## Known breaks (built before this record, each owned elsewhere)

These go against the rules above. This record does not change them. Each changes the way the
bot plays, so each is changed only with its own measure.
- `bot.lua`'s counter refusal (`spent < u.hp` in `Bot.candidates`, mirrored in `M.explain`; ADR
  0368's `GATES`, which ADRs 0384 and 0388 reason from). The cap never sees a risk that the
  candidates already refused. It is the first lead of #510's careful-on-ch03 investigation.
- `Sight.betweenMay` on the T100a-R branch inherits that refusal in the player phase the
  lookahead plays between its two enemy phases. It follows whatever the refusal becomes.
- `M.waitBuys`'s list of act kinds and `M.commits`'s line at a certain death, on the T100a-R
  branch. What happens to each is tracked on #510's plan comment (6563384310, T100a-R).

## Where it is pointed to

- The AGENTS.md Source of Truth row.
- The first lines of `planner.lua`'s header.
- A review of a bot change asks the five tests of every rule the diff adds. It finds them through
  the AGENTS.md row, which every session reads first.
