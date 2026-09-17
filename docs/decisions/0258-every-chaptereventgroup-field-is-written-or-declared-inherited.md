---
id: 258
title: "Every ChapterEventGroup field is WRITTEN or DECLARED-INHERITED"
date: "2026-08-23"
section: "Operational Gotchas (durable)"
issues: [313]
---

# Every ChapterEventGroup field is WRITTEN or DECLARED-INHERITED

A hosted chapter adopts a vanilla host slot, and **every field we do not declare silently
keeps the donor's value.** That has landed five times — goal text ids (#207), battle grounds
(#289), difficulty numbers (#303), `.traps` (#306, which would have shipped vanilla Ch7's two
ballistae on ch06) — and every instance was found one at a time, by something else going wrong.
In IaC terms it is the `terraform import` problem, and the answer is never a better runbook: it
is to enumerate the attribute set and require every attribute to be accounted for.

**The instrument is the whole trick, and the obvious one is wrong.** Our injectors mostly keep
the donor's SYMBOL and rewrite what it points AT — `EventListScr_Ch6_Turn` is still called that
and contains none of vanilla's events, and #306 declared ch05's traps empty by rewriting
`TrapData_Event_Ch6` to `TRAP_NONE` without touching `.traps` at all. So comparing the group's
initializer TOKENS reports ~20 inherited fields per chapter when almost none are, and would
have demanded a written justification for each. What leaks the donor's data is a field whose
TARGET is still vanilla's, so the census resolves every field's symbol to its definition and
diffs that against HEAD. With the right instrument the answer is small and identical across
chapters: **eleven inherited fields, the same eleven every time.**

- **Five are genuinely empty in vanilla** — the SelectUnit / SelectDestination / UnitMove /
  Tutorial lists are a bare `END_MAIN`, and `extraTrapsInHard` is `TRAP_NONE`. Inheriting
  nothing is inheriting nothing. The declared reason names the *emptiness*, not the field, so
  it stops being true if vanilla ever fills one.
- **Six are the skirmish rosters**, and they are the finding.

**The ruling on the rosters, and it is a design call, not a safety call.** Nicolas, 2026-08-23:
*"Vanilla has those optional skirmishes so we also should. We can wire them when we get to the
world map body of work."* So they are DECLARED-INHERITED pending #29 and deliberately **not
nulled** — nulling would have foreclosed a feature we want. Two things #29 inherits: our own
rosters replace vanilla's, and the engine already ships `sub_8083424`, which checks all six for
NULL. Nothing in FE8 calls it (verified: no caller in any `.c`/`.h`/`.s`/`.inc`, no
literal-address reference). **Calling that "dead code" was the wrong frame** — uncalled in
vanilla is not useless to us; it is an entry point waiting for a caller, and it answers exactly
the question a world map has to ask.

**The guard found a sixth instance on the day it was written** — the first not discovered by
something else breaking. **ch02 alone inherits `miscBasedEvents`**; every other hosted chapter
writes it. Checked rather than assumed: vanilla Ch3's misc list is `CauseGameOverIfLordDies`
and nothing else, which IS ch02's declared `lose_condition`, and its `defeat_all` objective is
FE8's default when no DefeatBoss/Seize is declared. The donor's value is correct here by
coincidence of design rather than by intent — which is the part worth writing down, because
nothing would have told us if it were not.

**Unclassified fails the build**, after the injectors run, because the census reads what they
actually wrote. A field nobody has ruled on fails — including one that appears in the struct
upstream tomorrow, since the field list is read from `chapterdata.h` rather than transcribed. A
declaration for a field we actually WRITE fails too: a reason nobody needs is a reason nobody
rechecks, and left standing it is how a field keeps a stale justification after it stops being
inherited. `make chapter chNN` reports the same census the build refuses — one census, because
two would be two answers.

_Decided: 2026-08-23 (Nicolas ruled on the rosters). Proof: 15 unit tests; the guard runs in
every build; it found ch02's `miscBasedEvents` unruled on first run._
