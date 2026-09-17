---
id: 29
title: "(a) `tools/check.py` runs in CI's `checks` job, which installs pyyaml and nothing else."
date: "2026-08-06"
section: "Working Conventions (Definition of Done)"
issues: [237, 239, 240, 241]
---

# (a) `tools/check.py` runs in CI's `checks` job, which installs pyyaml and nothing else.

`check_hosted_chapters_declared` imported `build_campaign` to reach the host-slot constants, and
`build_campaign` imports Pillow at module scope — so the gate would have failed *every* push with
`build_campaign does not import: No module named 'PIL'`: a red check that names the wrong problem
and teaches everyone to ignore it. The fix is structural, not a `pip install`: the host-slot
registry moved to **`tools/inject/hosts.py`**, stdlib-only like `inject/decomp.py` beside it, and
`build_campaign` re-exports it so every call site still reads `bc.CH04_HOST_INDEX`. The rule
generalises — **a lint imports the smallest module that owns the fact, or reads the source with
`ast`; it never imports the build.** `check_purple_bank_blankers_known` already said so for its own
constants; this makes it the standing rule.

Two more defects fell out of moving it. Discovery matched `CH(\d+)_HOST_INDEX`, so the **prologue
was invisible** — `PROLOGUE_HOST_INDEX = 1` was not in the collision map, and a later
`CH05_HOST_INDEX = 1` would have passed the guard and quietly overwritten the prologue's events.
And enrolment was a *convention*: `inject_ch05` with a typo'd constant is simply not discovered, and
every guard built on the registry then passes with one chapter fewer and no complaint — the exact
ch04 failure class #138 set out to close. `undeclared_injectors()` now reads `build_campaign`'s
source with `ast` and fails the build on an injector that enrols nothing.

**(b) A limit that kills everything at once must be MEASURED, not documented.** `harness.lua` sits
at Lua's 200-local ceiling, and the remaining margin was written as prose — "two free slots" — in
`harness.lua`, `check.py` and `HANDOFF.md` simultaneously. It was wrong in all three within one PR
of being written: #240 spent a slot and updated no comment. Measured, the margin was **one**.
`check_lua_local_headroom` now adds probe locals until the chunk stops compiling, prints the real
number on every `make check`, and fails at zero. Same reasoning retired the hand-written
`LUA_CHUNKS` tuple, which listed 4 of the 9 chunks `harness.lua` loads — a syntax error in
`recorder.lua` or `liveness.lua` killed every scenario with the gate green. **If a number about our
own code can be computed, compute it; a hand-maintained one is a comment that lies eventually.**
_Decided: 2026-08-06 (code review of #237/#239/#240; #241)_

---

**The controller's rule order is load-bearing, and its stall detector belongs where it can be
tested.** Three corrections to the #236/#238 contract, all from the same review (#241).

**Order: the more SPECIFIC state outranks the more general one.** `yes_no_choice` was placed above
the passive `std_event` rule (that was #232's fix) but *below* `dialogue_wait` — and that pairing is
the same bug wearing a disguise: `dialogue_wait` answers "press A", `YesNoChoice_Loop_KeyHandler`
CONSUMES that A, and the prompt is answered by accident with the run green. A live `YesNoChoice` in
its key handler owns the A button whatever else is on screen. The order is now pinned by tests
(`talk_wait`+`yes_no`, `menu`+`std_event`, `map_fade`+`std_event`), because rule order is the one
property of this design that no single rule's tests can protect.

**Liveness: `PROC_REPEAT` is how every long-running FE8 proc works, so a constant `scrCur`/`idleCb`/
`lockCnt` is not evidence of a stall.** `ProcScr_StdEventEngine`, `gProcScr_TalkWaitForInput`,
`sProcScr_BMXFADE` and `gProcScr_YesNoChoice` are all `PROC_REPEAT`, holding those three fields
constant for an entire scene; the signature can only see churn. It now includes `sleepTime` (a proc
counting down a timed wait IS progressing — and `INSPECT.snapshot`'s own `frozen` field already
compared it, so the feature held two contradictory definitions of "not moving") and the pool count.

**Placement: the thing that decides FAIL cannot live where nothing can load it.** `INSPECT.watch`
was in `harness.lua`, which only runs inside mGBA, so the most flake-prone component in the stack
had zero tests. The decision moved to `controller.lua` as `stallWatch()`/`procSignature()` — pure,
unit-tested — and the harness kept only the logging. As a bonus it calls `explain()` once per hold
instead of once per frame of a 36000-iteration loop. **General rule: pure decisions live in
controller.lua (unit-tested, no ceiling); harness.lua drives the emulator.**
_Decided: 2026-08-06 (code review of #237/#238/#240; #241)_

---
