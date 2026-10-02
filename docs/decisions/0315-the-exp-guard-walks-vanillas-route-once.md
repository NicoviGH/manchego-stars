---
id: 315
title: "The exp guard walks vanilla's route once"
date: "2026-10-02"
section: "Combat System"
issues: [430]
---

# The exp guard walks vanilla's route once

#430 step 2 asked for a campaign-wide exp guard. The per-chapter yield test compares a
chapter against its own twin, so it cannot see a twin used twice: ch07 against FE8 Ch6, which
ch06 already used, reads about x1.00 while it hands the party a chapter of exp FE8's party
never earns.

**The twin party fights each twin once.** FE8's party plays each chapter once, in order, and
`vanilla_arrivals` already walks it that way. `exp_curve.simulate`'s twin party now does too:
a chapter whose twin was already spent pays our party and not the twin's.

**Two guards, because one is not enough.**
- **The route rule** (`twin_route_findings`): hosted chapters' twins must advance through
  FE8's order. A twin already used or behind the route fails. Skipping ahead passes, since it
  only leaves the party behind (ch08 -> FE8 Ch13).
- **The exp-to-date band**: our mean exp banked to date, over the founding careers, may not
  run more than 12% ahead of the twin party's.

The two catch different things. The band fails on accumulated drift; the route rule names the
chapter that reused a twin. With the founding party handed the prologue's pay (ADR 0320), ours
reads 0.98x-1.01x of the twin party from ch00 through ch06, and a canary that points ch06 at
ch05's twin reads 1.22x, so today the band sees one reuse as well.

**ch07** still names FE8 Ch6. It is planned, not hosted, so nothing fails today. Hosting it as
written fails the route rule.
