---
id: 273
title: "Two do-not-attack lists are not one mechanism, and they have different invariants"
date: "2026-09-04"
section: "Operational Gotchas (durable)"
issues: [26]
---

# Two do-not-attack lists are not one mechanism, and they have different invariants

`AI_A_07` and `AI_A_08` look interchangeable. Both run the standard offensive action through
`AiIsUnitEnemyAndNotInScrList`, so a unit carrying either fights the player normally and simply
will not swing at whatever its list names. `check_rescue_targets` accepted **either** as proof
that a unit could not sink a hull.

It is not proof, because the **lists are different and each names one thing**. AI_A_07's is
repointed at ch05's escort (`repoint_escort_safe_ai_list`) and never at a boat pid, so a ch06
unit carrying `{0x7, ...}` politely refuses to attack Basil — who is not in the chapter — and
sinks the hull on schedule. The gate would have called it licensed. Only `AI_A_08` is repointed
at the hulls, so only `AI_A_08` licenses anything here.

**The invariants also differ, and the difference is not an oversight.** AI_A_07's is one **UNIT**:
vanilla ships exactly one client (Ch5's Joshua), so a second silently inherits our escort's
immunity — `assert_escort_safe_ai_has_one_client` sweeps every chapter for it. AI_A_08's is one
**CHAPTER**: vanilla ships *no* clients at all, so the chapter that claims the list may spend it
on as many of its own units as it likes (ch06 spends it on ten), and the hazard is a *different*
chapter picking the byte up for its own reasons — inheriting immunity to pids it has never heard
of, and standing in the way of the next chapter that wants the list for its own rescue targets.
`assert_boat_safe_ai_is_single_chapter` is that sweep, and both now run through one
`safe_ai_clients(ai_index)` implementation. Having only one of the two lists swept is exactly how
the second came to be spent with no sweep at all.

_Found by `/code-review` on #366 (2026-09-04)._
