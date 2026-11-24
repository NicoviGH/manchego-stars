---
id: 467
title: "A retry remembers the failed attempt's visible timeline"
date: "2026-11-24"
section: "Combat System"
issues: [765, 764, 510]
---

# A retry remembers the failed attempt's visible timeline

**Decided (Nicolas, 2026-11-24, #764's plan R1; built by Claude, #765).** Supersedes the memory
part of ADR 0399, 0436 and 0464 (the four lists, and 0464's drop of a loss the play brought).
ADR 0386 (only what the screen showed) and 0449 (an arrival is keyed by its turn) hold.

**Why.** A retry's memory was four lists in `style.memory` (`enemies`, `arrivals`, `closings`,
`fates`) plus `style.arrivals` for the hold, each added for one case. What a person on their
second try knows (who came when and after what, where each enemy walked, who killed whom from
where, which village went when, who left the map) had no one place. ADR 0464 then dropped any
loss by a unit our own act loaded, because its calendar date was the play's: vanilla Ch14's
Rennac, whom our door loads, is gone from the map 9 turns after he appears (`x741c`), and a retry
forgot it.

## What changed

- **`tools/playtest/timeline.lua` is the one owner.** `Timeline.recorder()` reads an attempt's
  trace events as botrun's `trace()` emits them (`Timeline.of(events)` reads a filed trace):
  every red or green unit seen out of fog (appearance with `by`/`timed`, track, how it went:
  `killed`, `left` or `turned`), every death of ours or a green with its killer and tiles and the
  plan's read, every tile another side closed, and every steal or drop. botrun hands the result
  back as `rec.timeline`; the record line does not print it (the trace holds its events).
- **The trace is complete for it:** a phase snapshot carries `fogged`, and the end record carries
  `enemies_seen` (the slot stamps a retry's `sight.knows` matches).
- **Memory is the failed attempts' timelines,** `style.memory = { attempts }`, oldest first.
  campaign.lua only carries them; a failure's record keeps its style without the memory (the
  line's earlier failures are it) and says how many it remembered (`remembered`).
- **Readers** (`Timeline.enemies`, `arrivals`, `holdTurns`, `deadlines`, `routes`, `threats`):
  - the hold, the remembered enemies and the pending recruits read as before;
  - `deadlines` dates a loss by a unit the game timed by the calendar, the earliest over the
    attempts; a loss by a unit the play brought is dated by the turns after it appeared, once it
    has appeared in this attempt (botrun's stamps, `opts.appeared`). This replaces ADR 0464's drop.
  - `routes` and `threats` are for R2's jobs (#766); R1 tests them.

## Proof

- `test_timeline.lua` on three recorded games (`tools/playtest/fixtures/`): Ch14 `x741c` attempt
  1, Rennac comes by our door on turn 2 and is gone from turn 11; Ch10 `x741d` and `fx730a`,
  (11,15) and (1,11) razed in enemy phase 5. The four tests of a brought loss's date fail when
  the 0464 drop is put back.
- Size: a timeline is 12 to 15 KB of JSON an attempt (Ch10, Ch14).
