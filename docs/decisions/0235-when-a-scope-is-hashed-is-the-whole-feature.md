---
id: 235
title: "WHEN a scope is hashed is the whole feature. Hashing at the end of the build undid it."
date: "2026-08-13"
section: "Operational Gotchas (durable)"
issues: [255]
---

# WHEN a scope is hashed is the whole feature. Hashing at the end of the build undid it.

Sticky ownership re-hashed every inherited path in `finish()` — after all steps had run. Every
chapter injector rewrites the same five whole-campaign tables, so by the end of the build that
shared file holds the LAST chapter's bytes, and `finish()` charged them to ch04, ch03, ch02 and
ch01 alike. Editing the chapter under development therefore re-ran the whole campaign's
scenarios: the measured **18 of 20**. The path-set churn the stickiness was added to fix was
real; hashing at the wrong moment quietly gave the win back.

Each scope is now fixed to the moment its own step ended (`_claim` → `_freeze`), and the
previous manifest is seeded in `__init__` rather than merged in `finish()`, because seeding
after the fact is what forced the late hash. `global` is the deliberate exception — it means
"the whole build", so its reference point is the end of it.

This is the direction that matters for how the campaign is actually built: **forward**. A ch05
edit no longer moves ch04's digest, because ch04's claim happens before ch05's step writes
anything. The reverse (editing an early chapter) still invalidates the later ones, and that is
correct-but-coarse — the shared table genuinely does carry ch02's bytes into ch05's copy. Fixing
that needs sub-file attribution, and the note above still applies: do not reach for it without a
measurement saying it pays. Editing ch02 while building ch06 is not the common case.

Cost measured in the profile: `_freeze` is 0.165s of a 70s injection, and the whole scoping
machinery 1.8s, nearly all of it the `stat` walks that were already there.
_Decided: 2026-08-13 (Claude, #255 phase 2 follow-up)._

**The playtest cache was never the biggest drag; the INJECTOR is.** Profiling
`build_campaign.py` to settle an unrelated question showed where a build's time actually goes:
of a 63s `make`, the ARM compile is **12s** and the Python injection is **51s**. It is paid on
every build whether or not a playtest ever runs, and it is single-threaded. `cProfile` (70s under
profiling overhead) puts almost all of it in two places, both of which look fixable without
touching what the injector produces:

- **`ref_to_battleframe._cell_is_empty` — ~28s, via 11 MILLION `PIL.Image.getpixel` calls.**
  180k invocations walking cells pixel-by-pixel in Python. `getpixel` per pixel is the classic
  PIL antipattern; a numpy view or `getbbox()` over the crop answers the same question in bulk.
- **YAML parsing — ~22s across 534 `safe_load` calls**, of which `_load_chapter_yaml` alone is
  9s over 62 calls, i.e. the same chapter files parsed dozens of times per build. Memoizing by
  path+mtime and using libyaml's `CSafeLoader` are both small, local changes.

Recorded here because the lesson generalises past this repo: the scenario cache was optimising
*how many scenarios re-run*, which is the visible cost, while a fixed 51s tax sat on every build
unmeasured. **Profile the thing everything waits on before optimising the thing that waits.**
_Decided: 2026-08-13 (Nicolas + Claude; measured, not estimated)._

**Honest ceiling of phase 1 alone, kept because it explains why phase 2 exists.** Keying on
`rom_input_hash` means any
`build_campaign.py` or `campaign.yaml` edit invalidates every scenario, and nearly every feature
task touches `build_campaign.py`. This phase buys doc-only changes, harness-only changes, and
repeat runs while debugging something else. Phase 2 — having the build attribute its own writes
per scope (`global` / `chapter:N`) so a ch05 edit stops re-running the prologue — is where the
ceiling lifts, and it must be DERIVED at build time from what the builder did, never a
hand-declared impact map: hand-maintained maps rot silently and let real regressions through,
which is the exact failure this exists to avoid.
_Decided: 2026-08-12 (#255 phase 1; measured: a repeat `--scenarios ch05arena` went 10s + 1 build
to 0s + 0 builds)._
