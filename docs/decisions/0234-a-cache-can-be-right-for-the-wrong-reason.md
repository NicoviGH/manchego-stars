---
id: 234
title: "A cache can be right for the wrong reason, and only the artifact says which."
date: "2026-08-13"
section: "Operational Gotchas (durable)"
issues: [255]
---

# A cache can be right for the wrong reason, and only the artifact says which.

The invalidation probe's `prologue` case went red in the most alarming way available: bumping
`level: 5 → 6` under the ch00 YAML's `enemy_units` — real, chapter-scoped content — moved **no**
scope digest in any of the four ROM configurations, so nothing re-ran. That is the exact
signature of a stale-PASS hole, and the manifest is precisely the wrong place to investigate it,
because the manifest is the thing under suspicion.

Settled by building the prologue ROM **twice**, edited and not: identical sha256. Then tighter,
by hashing all 20,263 files of the decomp tree after an injector-only run in each state: **zero**
differed. So the cache was correct, and correct for a reason nobody had written down —
`inject_prologue` emitted its two `UnitDefinition` rosters as **C literals**, under a comment
that said "Positions/levels/items from the chapter YAML". Only the boss's *weapon* was ever
wired (#52). Every literal matched the YAML by hand, so the chapter file looked authoritative
and the built ROM agreed with it; a rebalance authored in YAML would simply never have shipped,
with no symptom anywhere. The same three levels were hardcoded a **second** time in step 4b's
`guest_patch` (`baseLevel` in `data_characters.c`), so the two encodings of one number could
have drifted apart as well.

`_prologue_roster_blocks` now sources levels, positions, the guard head-count and the enemy
weapons from the chapter YAML, and `guest_patch` reads the same field the roster does. The
rewiring was verified **byte-neutral** — same ROM sha256 as before the change — which is the
proof that it is a plumbing fix and not a balance change. The probe is now green at **7 run, 13
cached**: the prologue is *hosted on chapter 1*, so `ch01`, `ch01win`, `controller_turn`,
`gameover`, `lordfloor`, `retreat` and `win` share its data and correctly move with it.

Three durable rules:

- **A comment claiming a value is data-driven is testimony, not proof.** This one had been
  false for months and read as true because the literals agreed with the data.
- **When the cache and the content disagree, the ARTIFACT arbitrates.** Two builds and a
  byte-compare cost ten minutes, need no emulator, and cannot be argued with. Reasoning from
  the manifest would have "confirmed" whichever answer was reached first.
- **A red probe case is worth more than a green one, and the fix is upstream more often than
  it looks.** The expectation was right (`win` *should* re-run on a prologue edit); what was
  broken was the pipeline that made it true. Adjusting the expectation would have closed the
  ticket and left the bug.
_Decided: 2026-08-13 (Claude, #255; the probe's first genuine catch)._
