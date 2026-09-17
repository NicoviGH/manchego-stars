---
id: 171
title: "A duplicate top-level `def` disables the earlier one and says nothing"
date: "2026-09-02"
section: "Operational Gotchas (durable)"
issues: []
---

# A duplicate top-level `def` disables the earlier one and says nothing

Python keeps the LAST definition. So a file can hold an edited function and a stale copy of it, the
module imports cleanly, the tests pass, and the edits do nothing -- the only symptom is a test
asserting on `inspect.getsource` that "impossibly" fails. It happened TWICE in one session to two
different guards in `check.py`, both times from a sloppy source-slicing edit that copied a region
instead of replacing it. `check_no_shadowed_definitions` now rejects it across `tools/`. Same family
as *"A guard that stops guarding fails silently"*: the failure is indistinguishable from working.
