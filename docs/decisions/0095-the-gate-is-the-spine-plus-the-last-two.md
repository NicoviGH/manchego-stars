---
id: 95
title: "The gate is the spine plus the last two chapters; depth lives in the chapter suite"
date: "2026-08-23"
section: "Distribution & Scope"
issues: [302]
---

# The gate is the spine plus the last two chapters; depth lives in the chapter suite

Five chapters in to an 18–20 chapter game, the merge gate had quietly become 21 scenarios and 5
builds — 6 spine, 2 ch01, **6 ch04 and 7 ch05, with ch02 and ch03 contributing nothing**. The
ageing-out was already happening; nobody had written down that it was a rule, so ch04 stayed when
ch05 landed. Extrapolated, an accumulating gate is **~130 scenarios and ~18 builds by ch18**, or
30–40 minutes — which is not a slow gate, it is an unrun one, and an unrun gate protects nothing.

**The rule: the gate carries the spine plus the two most recently hosted chapters.** `check.py
check_gate_chapter_window` derives the window from `inject/hosts.py`, the registry that ENROLS a
chapter, so hosting ch06 is what ages ch04 out — there is no list of allowed chapters to remember
to edit. That holds the gate at ~20 scenarios and ~5 builds permanently, whatever the chapter
count.

**Two chapters, not one, because the CHAIN is where the coupling lives.** `chain_ch04_to_ch05`
rewrites ch04's dev-placeholder landing; chapters share donor slots, one SMS id pool and one
message-id space; `check_injection_order` already pins a MUST-precede list because
`inject_prologue` overwrites a goal template `inject_ch01` copies. The chapter most likely to break
is the one immediately behind the one being edited.

**Depth is never deleted, it moves.** Every chapter keeps its own suite (`ch01` 13 scenarios,
`ch02` 4, `ch03` 8, `ch04` 9, `ch05` 8) — that is what you run while working it, and what a
`--all` sweep runs in full. What ages out of the gate is a scenario's membership in the MERGE
tier, not its existence.

**So the third tier is now explicit: `SUITE=all` before any playtest build we send the group, and
after a week of tooling work.** That sweep is the only thing that can catch a chapter which left
the gate breaking three chapters later — a merge gate structurally cannot, once the chapter is out
of it. This is the standard smoke → regression → release shape: a tight per-change gate, a broad
suite on a slower cadence, a full pass at a milestone. Nightly is for teams with a build farm; for
a campaign that ships to friends every few weeks, PRE-RELEASE is the real milestone.

**We already have the expensive half of what big test estates buy with machine learning.**
Meta and Google reach for predictive test selection because their dependency graphs are too
tangled to trace; #255 phase 2 gives us DETERMINISTIC test impact analysis instead — the build
records what each injection step wrote, so a ch05 YAML edit re-runs ch05's scenarios and serves
`ch01win` / `ch04moose` / `recordunitlist` from cache (`probe_invalidation.py` asserts exactly
that). Gate membership is therefore nearly free while scopes hold still. The case that is NOT free
is a GLOBAL input moving — `build_campaign.py`, `campaign.yaml`, `controller.lua`, `run.sh` — which
re-runs everything, and which is most tooling work. The window is what bounds that case.

**What we deliberately did NOT add: one smoke scenario per chapter in the gate forever.** It is the
right instinct — the standard game-dev smoke is "load every level in turn" — and `smoke_chNN`
already exists per chapter. The blocker is that each one drags its own `chNNboot` ROM build (~25s)
into the gate, so it costs BUILDS linearly even at one scenario each. **That, not the 12% it scores
today, is the real case for #309's phase 2**: a patched boot target would let every chapter's smoke
ride ONE ROM, turning per-chapter gate coverage from linear-cost into constant-cost. The trigger to
reopen it is therefore "we want per-chapter smoke in the gate", not "the gate got slow".
