---
id: 215
title: "A scenario written against the old design will FAIL ON SUCCESS"
date: "2026-08-14"
section: "Operational Gotchas (durable)"
issues: [25]
---

# A scenario written against the old design will FAIL ON SUCCESS

Moving Sahnar from a turn-2 riser to a turn-1 unit broke three playtest scenarios, and the
instructive one is `ch05recruit`: it waited on `turn() >= 2 and redSahnar()`. With her red from
turn 1 that is satisfied the instant the counter ticks — **before Ravisin says a word** — so the
gate would have reported *"eruption warning showed 0 boxes"* and blamed the warning. The chapter
would have been fine and the accusation would have pointed at it.

This is the standing *"a scenario can FAIL on success, and it will blame the chapter"* lesson with
a new trigger: not the scenario's own bookkeeping, but a **design change the scenario predates**.
When a placement or trigger moves, grep the harness for what waited on the old one.

The repair also split a compound assertion into two honest ones — Sahnar is RED on her post at
turn 1 (which nothing witnessed before: an empty arena passes every other ch05 scenario, and the
first symptom would be a Talk with no target), and separately the eruption's four boxes on turn 2.
