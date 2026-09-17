---
id: 250
title: "Riding a slot is not enough — the slot has to survive the build, and one does not."
date: "2026-08-16"
section: "Operational Gotchas (durable)"
issues: [284]
---

# Riding a slot is not enough — the slot has to survive the build, and one does not.

`inject_prologue` deliberately zeroes its guests' personal bases so they read as pure class
base, so Sephek is genuinely naked *despite* deploying on O'Neill's slot. Mapping him anyway
inflated his threat to **2.9x the Prologue's ceiling** and reddened CH0 — caught by the very
gate this issue added, on its first run. `PROLOGUE_ZEROED_GUEST_SLOTS` now names that exclusion
and an assert keeps it in step with the injector.

**ch03's grell is the one that was really wrong**, and for the opposite reason: it rides raw pid
`0xb7`, and a CharacterData gap is all zeros. It goes from 1.1 to **3.6 rounds** on an authored
line, HP 21/Def 3 → HP 36/Def 8.

**A `personal:` block is not injected by writing it.** `RAW_PID_PERSONAL_SOURCES` is what carries
one into the ROM, and it was a passenger inside the loop over `RAW_PID_PORTRAITS` — so a line
authored for a pid with no portrait binding would have been silently dropped, which is exactly
the grell's shape (it keeps the generic monster name plate on purpose). The two bindings are now
independent passes. Declaring the line in YAML and confirming the tool's number would have
"verified" a boss that never changed in the game: *a declaration is not art*, again.

**ch03 could not take any monster boss's line verbatim, and the reason generalizes.** Every
named monster in the decomp with a personal line (Maelduin, Cyclops, Wight, Deathgoyle, Gorgon)
is a **promoted late-game** unit, so all five carry Pow+5..+10. Applied to a ch03 boss they fix
durability and blow out threat — measured, at the Grell's own level: 9.6–20.0 against FE8 Ch3's
threat ceiling of **6.8**, every one of them tripping the outlier check. Dropping the Grell's
level does not rescue it (a L4 Deathgoyle line still reads 9.6). **A vanilla boss line is
calibrated against the party that faces it**, and lifting one across eight chapters imports that
calibration with it.

So the Grell takes Maelduin's **defensive half near-verbatim** (HP+15/Def+5 against its
HP+15/Def+4) and drops its offensive half. Maelduin is the decomp's one defensive monster boss,
which is what makes it the honest donor: durability was the deficit, offence never was. The
result is 3.6 rounds at HP 36/Def 8 — Bazba's bar exactly, and just inside Ravisin's 37/10 two
chapters later, so the boss curve stays monotonic. Threat is unchanged at 7.6, which matters:
the Grell hits RES with an Evil Eye in a chapter whose twin fields no magic at all, and that
hazard was a deliberate ch03 choice already shipped, not something to re-open here.

**The rule: a named boss is class base plus a personal line, and the line is what carries its
durability.** Where a level was bumped to fake one — the Grell's `level: 12` carried the comment
*"level holds boss pressure"* — the bump is offence, not survivability, and the two are not
interchangeable.

**No parity ratio moves, and that is not a bug.** The AGGREGATE resolves both sides off class
base on purpose, so a personal line is invisible to it: ch02 reads x0.79/x0.75 before and after,
ch03 x1.12/x0.99 before and after. **ch02 is `[locked]` and its lock needs no re-baseline** — the
numbers under the lock are byte-identical, so the "deliberate re-baseline, Nicolas's call" the
issue anticipated never arises here. That question belongs entirely to #285, which changes the
footing; measured on that footing the grell's line lands ch03 at x1.03/x1.00, near-centre.

**The audit the fix demanded.** Every boss was measured against its own twin's bar, on the real
article. ch00's Sephek (2.1 vs 2.2) and ch01's chief (6.2 vs 6.2) clear it — the chief on
Breguet's inherited line plus class Def 10, Sephek on class base alone against a twin whose own
boss is nearly as bare. **A personal line is the MECHANISM, not a checkbox**: a boss already at
its bar needs nothing, and the rule to write down is about the measurement, not about a required
YAML key. Two are open and belong elsewhere: ch06's Messie reads 2.7 against 12.9 but is
`status: planned` brainstorm seed, and ch08's ice troll is **undentable** (Def 15 vs the
yardstick's 13 attack) — the same `inf` that blocks #285, on our side of the table for once.
That one matters to #285 beyond ch08: the exclusion policy cannot be written as "a vanilla
quirk we tolerate" when our own content produces it too.

**The prologue is the mirror case, deliberately left alone.** Asked whether the guests need
lines to match a boss that got one, the measurement says the boss needs nothing (Sephek 2.1
against a 2.2 bar) and points at the player side instead. Vanilla's prologue pair splits in
half: **Eirika's personal line is Lck+5 and nothing else** — she is essentially class base, so
the zeroing costs Hlin nothing and her frailty is authored (`level: 3`, "the weak lead"). But
**Seth's line is most of what Seth is** (HP+7/Pow+7/Skl+9/Spd+5/Def+3/Res+5/Lck+13); stripped,
he falls from surviving 23.8 rounds to 5.5. Scramsax measures **5.7** — a Seth-analog Jeigan,
authored as one ("promoted prepromote — high stats despite low internal level (cf. Seth)"),
missing the line that makes a Jeigan one. Not changed and not filed (Nicolas, 2026-08-16): ch00
is `[locked]`, has shipped and been played, and this is the STATIC proxy, which assumes the
worst foe reaches a unit and cannot see that Hlin sits back at (8,5) while Scramsax stands
forward at (13,9). Recorded here so a prologue that ever plays wrong starts with the number.

**And the gate now reads what it had been printing.** ch03's paper boss shipped for months under
a green `--curve --check` because the aggregate sums the force and divides by the deploy cap, so
one soft unit dissolves into a 23-unit average — the same blind spot as *"One unit can BE the
parity overage"*, in the opposite direction. `role_findings()` had been emitting the warning the
entire time and **nothing consumed it**. `curve_gate_failures` now fails a `locked` chapter that
has an open role finding, and the curve prints the findings under the table. A chapter marked
balance-final with a per-unit check still complaining is a contradiction; the opt-in stays
per-chapter, so mid-authoring chapters warn without reddening CI. It earned itself immediately:
the bad Sephek mapping above was caught by this gate, not by review.

**The lesson under all of it: an issue's premise is a hypothesis too.** #284 stated a defect in
two chapters, with a measurement table, and the measurement was the thing that was broken. One
of the two chapters needed no content change at all, and authoring the "fix" it asked for would
have added a second source of truth for a line the slot already owns — agreeing with the ROM
today and free to drift from it tomorrow. Checking what the BUILT character table contains,
before changing content to match a number, is what separated the two cases.

_Decided: 2026-08-16 (#284; the grell's donor and sizing are new, ch02 turned out to need no
content change)._
