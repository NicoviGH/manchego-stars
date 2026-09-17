---
id: 244
title: "One unit can BE the parity overage, and the band will hide it"
date: "2026-08-15"
section: "Operational Gotchas (durable)"
issues: [25]
---

# One unit can BE the parity overage, and the band will hide it

ch05 measured "PARITY (within band)" at threat/slot x1.20 with the white moose on the Gwyllgi's
own `HELLFANG`. Nicolas would not accept the verdict — *"I'm having a hard time understanding how
we realistically match parity with an extra monster"* — and the arithmetic says he was right:

| | Σ threat | /slot | vs vanilla |
|---|---|---|---|
| vanilla FE8 Ch5 (23 enemies) | 103.0 | 11.45 | — |
| ours WITHOUT the moose (22) | 99.5 | 11.06 | **x0.97** |
| ours WITH the moose (23) | 124.1 | 13.79 | **x1.20** |

**The moose was 20% of the entire force's threat and the whole overage.** Every other unit in the
chapter was already at parity. The verdict was true and misleading at once: `threat/slot` sums the
force and divides by the deploy cap, so one unit's 24.6 becomes +2.7 per slot and fits under a
±25% band with room to spare. `role_findings()` exists because this exact unit slipped through
once before; the aggregate learned nothing from that, because the aggregate cannot.

**Headcount parity is not force parity.** Both sides field exactly 23. We were not adding a body
— we were carrying vanilla's roster size with one slot holding a unit that hit 4x harder than
vanilla's hottest (24.6 against a 6.3 class-base ceiling).

**And the obvious repair moves the wrong dial.** Trimming trash to pay for a hot boss-adjacent
unit cuts CLEAR-LOAD, not threat: reavers 8→6 buys threat x1.14 but drags clear-load to x0.76,
and one more cut puts it out of band on the low side. A chapter cannot buy its way back to parity
by deleting bodies.

**The fix was the weapon, and it stayed inside the creature's own line.** `FIREFANG` is the Mauthe
Doog's, and the Mauthe Doog is the Gwyllgi's unpromoted tier — so the moose keeps its class, its
map sprite geometry, its doubling, and the distinct `cer_at1` voice, while dropping 24.6 → 11.8
and the chapter 1.20 → **x1.08** with clear-load unmoved at x0.84. Turn-1 pressure lands at 9.5
against vanilla's 9.0.

**The tool now says it for you.** `solo_contributors()` prints, under the verdict, any single
`count: 1` unit carrying =>10% of the force's threat and what the chapter measures without it —
the sentence that had to be computed by hand here. It is INFORMATION, not a gate: the two
obvious thresholds were both tried and rejected. A unit's SHARE barely moves when you
strengthen it, because it inflates the denominator too (ch05 read 16.4% with the shipped moose
and 17.2% with the rejected one), and leave-one-out by unit id just names whichever group has
the biggest `count`. It immediately surfaced ch03's Grell at **24% of its force** — a larger
share than the moose ever had, on a boss that also dies in 1.1 rounds (#284).

**Rule: when a chapter is at the edge of the band, ask WHICH UNIT is the overage before accepting
the verdict.** If one unit is a fifth of the force's threat, the band is not measuring parity, it
is absorbing an outlier. And the corollary for the metric itself: never quote a per-unit
class-base number next to a with-personal one — vanilla hides its named units' teeth in personal
lines (Saar and Joshua are both 6.2 class-base), so class-base flatters any unit whose danger
lives in class+weapon instead.

_Decided: 2026-08-15 (Nicolas)._
