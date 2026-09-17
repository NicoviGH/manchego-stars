---
id: 279
title: "A check that could not RUN is not a check that passed"
date: "2026-09-15"
section: "Operational Gotchas (durable)"
issues: [372]
---

# A check that could not RUN is not a check that passed

`check.py`'s `main()` ran its 39 checks in a bare `for check in (...): check(fail)`. One check
raising took down the whole drift guard and every check queued behind it, with a raw traceback and
a non-zero exit that named nothing — so `make check`'s answer to "is this repo drifted?" was
decided by whichever guard crashed first, and the ~29 gates behind it neither passed nor ran.

**That loop is why a wrong assumption inside any single guard was severe.** Five review rounds on
#371 each found a defect, and after the first, every one was in code written to make ONE
`check.py` guard defensive: a `TypeError` comparing an unfiltered `None`, then two wrong
discriminators (`except FileNotFoundError`, which a missing tileset *directory* also raises; then
a sidecar-only existence test, when `load_map` opens the `.mar` too), then an `AttributeError`
escaping a two-type `except` because `null` / `[]` / `"str"` are all valid JSON without `.get`.
With no isolation every guard is load-bearing for the entire gate, so each of those was an outage
rather than a line of output.

**An errored check goes into `fail`.** This was the call to make before writing the loop, because
it sets `make check`'s exit semantics, and the alternatives are worse in the direction that
matters. Printing and continuing without failing gives a green CI on a gate that silently did not
run — the exact failure mode #371 kept hitting. Letting it propagate is the outage. So a check
that raises is reported as drift, attributed to itself by name, and the run continues: `fail` gets
one scannable line (flattened, because a `SyntaxError`'s `str()` is multi-line and `fail` prints
as a bullet list), and the full traceback goes to stderr where it stays fixable without burying
the report. `BaseException` is deliberately not caught — a Ctrl-C is the operator talking, not a
check failing.

**Isolation lowers the blast radius; it does not relieve a guard of knowing what it was
reading.** "check_documented_tileset could not run" names no file, and the guard that was
opening the sidecar can. So the per-guard error handling #371 added stays exactly as it was, and
its rationale is now the message quality rather than the survival of the run.

**The old behaviour was written down nine times as load-bearing rationale** — four comments in
`check.py`, one in `build_campaign.map_tileset`, and four test docstrings, each explaining why a
guard handles its own errors the way it does. All nine are rewritten, and the retired claim is
registered in `DEAD_CONCEPTS` in the same commit (registry discipline; the same shape as the
29-character wrap that was written down three times and survived its own correction). Review
caught the ninth and a stale prescription in this log — *"a test asserting the function appears in
`main()`'s source is the cheap pin"* — which #372 replaces with the tuple and its own gate.

The list itself moved out of `main()` to a module-level `CHECKS`, so there is one authoritative
gate list and one loop that runs it; `main()` is now `fail = run_checks(CHECKS)` plus the report.
That also fixed how "is this check registered?" is asked. Four tests answered it by grepping
`inspect.getsource(check.main)` for the check's NAME — a substring of the source, which a comment
mentioning the check would satisfy just as well. They now assert the function OBJECT is in
`CHECKS`, which is the thing that actually runs. The question is worth asking at all because
defined-but-unregistered is how `check_tile_changes_outlive_the_retarget` shipped — and it is now
asked once for every check rather than four times by hand: `check_every_gate_is_registered` reds
the build when a `check_*` defined in the file is missing from the tuple. Thirty-five of the
thirty-nine had no pin at all, and writing thirty-five more of them would have been the wrong
shape; a module-level list makes it one guard.
