---
id: 212
title: "The headroom guard measured one file correctly BY ACCIDENT"
date: "2026-08-24"
section: "Operational Gotchas (durable)"
issues: [327]
---

# The headroom guard measured one file correctly BY ACCIDENT

`lua_local_headroom` originally APPENDED probe locals until the chunk stopped compiling. In Lua `return` must
be the last statement in a block, so for any chunk ending `return M` the probe is an instant
syntax error and the function reported **0 free** — not "no room", a broken measurement. It only
ever ran against `harness.lua`, which ends in a callback registration rather than a return, so
the one file it measured was the one file whose shape happened to suit it.

That mattered because #314 started pushing growth INTO modules. Redirecting every new local into
files whose ceiling nobody can measure, with the same all-at-once failure and no warning, is
moving the landmine rather than clearing it. **A guard is only as trustworthy as the shapes it
was tried against**, and this one had been tried against exactly one.

Three defects, and the second two were found by the fix's own tests:

**The insertion point is chosen by the COMPILER, not by a pattern.** `ch05.lua`'s module return
spans forty lines, so a regex for a single-line `return M` missed it. The prober now tries
inserting before the last top-level `return`, then appending, and takes whichever compiles.

**The splice needs its own newline.** `test_controller.lua` ends without a trailing newline, so a
bare append produced `endlocal __headroom_probe0`: a file with 74 locals and plenty of room
reported as full, which is a build failure.

**And then the whole approach was wrong.** Each repair fixed one shape and left another. Inserting
before the last column-0 `return` misses an INDENTED one — the same "nearly empty file reported as
full" lie — and, worse, lands *inside a nested function* when that return is in one, where the
probe measures the FUNCTION's 200 rather than the chunk's. A chunk sitting at exactly 200 top-level
locals then reports full headroom and passes the guard **in silence**, which is the failure
direction that actually matters. Probing with one real local instead of zero does not help: a
function has its own budget, so the probe compiles there happily.

**So probes are PREPENDED.** A chunk is a block of statements and a local declaration is a valid
first statement, so a probe at the top is unambiguously chunk-level whatever the file ends with,
and Lua counts the 200 per function rather than per position. Every end-of-file ambiguity
disappears at once — trailing return, indented return, nested function, missing newline. The only
special case left is a `#!` line, which Lua accepts only as line 1.

The general shape: **three rounds of fixing the end of the file, and the answer was the other
end.** Each round passed its own test and the next shape broke it. What ended the loop was
enumerating the shapes first — module return, multi-line return, indented return, in-function
return, no trailing newline, shebang, at-ceiling — and requiring one insertion point to satisfy
all of them.

**And the ratchet's counter is cross-checked against the prober**, because neither is verifiable
alone. The counter reads the source, the prober asks the compiler, and `counted + free == 200` is
asserted on the live harness. The counter was wrong by one when written — `\s` matches a newline,
so `local controllerFault` merged with the `local function log` beneath it — and a counter quietly
off by one loosens the ratchet by one every time anybody re-measures.

_Recorded: 2026-08-24 (#327)._
