---
id: 251
title: "A zero is a cliff, not a measurement — the aggregate reads the real article"
date: "2026-08-16"
section: "Operational Gotchas (durable)"
issues: [285]
---

# A zero is a cliff, not a measurement — the aggregate reads the real article

The parity AGGREGATE projected every unit off **class base**, dropping personal lines on both
sides. That was defensible while it was symmetric, and it stopped being symmetric the moment
either side's named units mattered. Both halves are now the real article, and the change moves
every chapter *toward* 1.00:

| chapter | threat, class base → real | clear-load, class base → real | |
|---|---|---|---|
| CH0 | x1.23 → **x1.13** | x1.07 → **x1.00** | `[locked]` |
| CH1 | x0.89 → **x0.89** | x0.97 → **x0.97** | `[locked]` |
| CH2 | x0.79 → **x0.81** | x0.75 → **x0.79** | `[locked]` |
| CH3 | x1.12 → **x1.03** | x0.99 → **x1.00** | |
| CH4 | x1.15 → **x1.15** | x1.19 → **x1.19** | |
| CH5 | x1.08 → **x1.04** | x0.84 → **x0.88** | |

**ch02 never falls to x0.64, and finding out why is what unblocked this.** That number was
measured before #284, when the tool could not see a personal line inherited from a vanilla
CHARACTER slot — so ch02's boss contributed Bazba's line to the twin's side of the comparison
and a naked Brigand to ours. With `ENEMY_BASE_SLOT` supplying the third source, ch02 reads
**x0.79**, inside the band. The blocker was the same missing mechanism that opened #284, not a
content problem and not the exclusion policy.

**The undentable problem is real, and EXCLUSION was the wrong answer to it.** Vanilla Ch5's Saar
with his own line sits at Def 13 against the yardstick's 13 attack: exactly zero damage, so
`rounds_to_kill` is `inf`. The repo's existing mechanism dropped such units from clear-load —
and dropping them is not symmetric in practice, because the two sides do not field walls in the
same places:

| | class base | real article |
|---|---|---|
| vanilla Saar | 12.9 rounds | **excluded → 0.0** |
| our Ravisin | 2.9 rounds | **13.4 rounds** |

Ravisin was *deliberately built to Saar's bar* — 13.4 against his 12.9, that is the whole point
of her personal line — and the metric counted ours in full while zeroing the twin's. On a
9-slot cap that one asymmetry is +2.9 clear-load per slot: **ch05 read x1.34 with exclusion and
nothing in the chapter had changed.** An exclusion policy cannot be fixed by applying it
"symmetrically", because symmetry in the RULE is not symmetry in the RESULT.

**So the metric floors the damage instead of dropping the unit.** `metric_rounds_to_kill()`
scores an undentable unit as if each hit chipped 1. FE8 really does deal 0 there — the floor is
a property of the measurement, not a claim about the game — and it earns its place on three
counts: every unit stays in the comparison on both sides, the load becomes **monotonic in Def**
(more armour is never less work, where `rounds_to_kill` has a cliff from 12.9 straight to
infinite), and it preserves the ordering that matters — Saar scores **22.8** against Ravisin's
**13.4**, which is the truth about which is the harder wall. ch05 lands at **x0.88**.

**The floor must carry the same accuracy divisor `rounds_to_kill` uses**, and the first
implementation did not — which broke the very property it was introduced for. Scoring `hp/hits`
instead of `hp/(hits × accuracy)` made the load jump *down* across the cliff: real Saar read
**46.8 rounds at Def 11 and 36.0 at Def 12**, a tougher unit costing less work. Worse, the test
asserting monotonicity could not fail, because its fixture had Spd 0 and Lck 0 — 100% hit chance
is the one case where the divisor-free form happens to be continuous. **A property test whose
fixture sits on the only point where the bug is invisible is not a test**; the fixture now uses a
unit that can be missed. With the divisor the floor is not merely monotonic but *continuous*: a
unit taking exactly 1 damage per hit already scores `hp/(hits × accuracy)`, so the floor meets
the last dentable value rather than stepping at it. Caught by `/code-review`, not by the suite.

That also retires the "N yardstick-proof units excluded from clear-load" note as a *mechanism*;
the count is still printed for planned chapters, because it is worth knowing that a chapter you
are about to write fields a wall, but nothing is skipped any more.

**No locked baseline goes out of band, and none needed content changes.** All three locked
chapters move toward parity. The re-baseline this issue and #284 both anticipated turned out to
be a re-reading, not a re-tuning.

**One consistency fix rode along, and it was a duplicated force builder.** `solo_contributors()`
kept its own copy of the our-side expansion, which multiplied `count` over `enemy_combatants` —
and that collapses a `composition` entry to its DISTINCT classes. On ch01 it therefore counted
six bodies where the verdict counted three, and printed *"without it the chapter is x1.14"*
directly beneath a row reading x0.89. Both now come from one `chapter_units()`. A note that
cannot reconcile with the number it explains is worse than no note, and two functions that must
agree about the same force will not stay agreeing.

_Decided: 2026-08-16 (#285). The three locked baselines were re-measured on the new footing, all
move toward parity, and none needed re-tuning — so the "locked chapters re-approved by Nicolas"
item was moot: **a sign-off that guards a scenario is not owed when the scenario does not
happen** (Nicolas, asked what there was to decide)._

---
