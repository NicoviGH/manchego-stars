---
id: 170
title: "A guard that stops guarding fails silently, and green is what that looks like"
date: "2026-09-02"
section: "Operational Gotchas (durable)"
issues: []
---

# A guard that stops guarding fails silently, and green is what that looks like

Both Criticals found in the #335 stack review were guards that had quietly stopped holding.
Neither failed a test; a guard's whole job is to say nothing when things are fine, so a broken
one is indistinguishable from a working one until you go and check. Two distinct mechanisms,
both worth recognising on sight:

**A check that is defined and unit-tested is still not RUNNING.** `check_tile_changes_outlive_
the_retarget` was written, tested, and never added to `check.py`'s tuple in `main()`. It
executed only as a side effect of `check_tests_pass` re-invoking its test file as a
subprocess — and that no-ops when `fireemblem8u/src` is absent, i.e. exactly the lightweight
CI job it existed to protect. **Adding a check means registering it; the test proving the
check works does not prove the check runs.** The pin was a test asserting the function's NAME
appears in `main()`'s source, which a comment mentioning the check satisfies too; since #372 the
gate list is a module-level `CHECKS` tuple, so `check_every_gate_is_registered` answers this for
every check at once and a per-check pin asserts the function OBJECT is in it.

**A guard matching source text by NAME skips whatever is wrapped.** The same check searched
for the literal `_inject_tile_changes`, while ch03 calls `_inject_ch03_tile_changes`. A
skipped injector and a chapter with no map changes look identical from outside — silence
either way — so ch03 was correct by discipline, not construction. `_injection_call_sequence`
had already learned this for `_scopes.run`/`_anims.run` and says so. **Make the covered set
assertable** (`_tile_change_injectors_seen`) so "who is being checked" is a fact, not a hope.

**Changing how a field is DECODED retires every comparison written against the old
encoding.** `unitAt` moved `xPos`/`yPos` from `ru8` to `rs8` — correct, since they are `s8`
and FE8 parks an off-map unit at −1. But 23 guards in the harness tested `u.x ~= 0xFF`, the
unsigned sentinel. `rs8` cannot return 255, so 21 became vacuously TRUE and 2 vacuously
false. Deployment counters counted off-map units, `partyDeployed()` returned true for a unit
that had not been placed, and the off-map lord and Baxby checks could never fire. **When you
change an encoding, the call sites that read the old one do not error — they lie.** Grep for
the old sentinel before changing the reader, and pin the ENCODING in a test (no `.x == 0xFF`
anywhere) rather than the call sites, which the next author would have to remember to extend.

The unifying test: after any change to a check, an encoding, or a sentinel, ask *what would
now be different if this were broken?* If the answer is "nothing observable", that is the
bug, not the reassurance.

**One fact, four registries: a rom_config has to reach all of them or the wrongness is silent
(2026-09-02, #353/#357 review)**
Adding `ch01boot` meant adding `CH01BOOT` in four unrelated places, and missing any one of them
fails quietly in a different way: the **Makefile** (missing -> the config builds CANONICAL and the
scenario's verdict is about a ROM it never asked for), **`_requested_flags`** (missing -> the build
stamps itself `canonical`, so a canonical scenario is not refused against it and burns the whole
mGBA deadline, while a `rom: ch01boot` scenario is refused forever as "tree holds canonical" even
right after the correct build), **`probe_invalidation.FLAG_ARGS`** (missing -> `KeyError` the moment
a scenario uses it) and **`_boots`** (missing -> `CH01BOOT=1 CH03BOOT=1` builds happily, boots ch03,
and ships a ch01 whose opening was stripped). Three of the four were missed on the first cut and
found by review. Until they are one thing, `check_rom_configs_reach_the_build` is what keeps them
equal -- it is cheaper than the four ways of being silently wrong.
