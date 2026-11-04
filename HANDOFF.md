# Handoff - Manchego Stars live state

**Read this from main** (`git show main:HANDOFF.md`): on a feature branch this file is the copy
from when the branch was cut, and may be days old.

`HANDOFF.md` is live state only: where the tree is, what is in flight, what is owed, what to do
next. **Settled decisions live in `docs/decisions.md`**; how-tos live in the files they are about;
operating rules in `CLAUDE.md`/`AGENTS.md`; findings, scope and backlog on GitHub issues. Nothing
here should still be true in a month. Before a context rollover, warn Nicolas, refresh this file,
and start a fresh instance; don't rely on auto-compaction.

Refreshed 2026-11-04 (Claude). Cut from 598 lines to live state (#572): what was history is in
ADRs 0353-0389 and on #510; the lessons moved to their files in PR #573.

## Where things stand

- **The parity model is being rebuilt: epic #510.** ch00-ch07 are unlocked and re-lock at its end
  (ADR 0354). Never widen an `accepted_residual` to get green.
- **#510 step 9, the difficulty instrument** (a bot plays the real ROM, both games; the plan is
  #510 comment 6563384310, ticked in place, spec 6563384018):
  - **Merged:** PR-A #558 (frozen suite), PR-B #559 (graded records), PR-C #560 (risk caps),
    PR-D #564 (goal ledger, no stalls), PR-E #568 (lookahead, retry memory), and #570's fix #571
    (lookahead budget 128 an attempt, so the boss fight is no longer judged one phase deep).
  - **PR-E's open items are decided** (Nicolas, 2026-11-04; ADR 0389): the hold stays, the
    budget was raised instead of narrowing the boss trigger, the breach's "first crossing" is
    not built.
  - **Suite now:** 566,389 `AiDecideMain` calls against SC-003's budget of 678,787; no decision
    skipped for budget; every one of the 52 runs has a game result.
- **On hold** (label `on-hold`, the hold comment says what reopens each): #565 (chipping a step
  back), #569 (placing a claim's wave in the lookahead).
- **Open PR #573** (#572): the moved lessons and the handoff guard's advice. Not a step 9 PR, so
  it waits for Nicolas's "merge" after its review.

## Next

1. **PR-F** (T071-T080, diagnostics): a failure gets a label only when a replay of a different
   plan avoids it. Its T079 live proof has three cases: vanilla Ch5's Gilliam death, ours ch02's
   green deaths, and ours-ch03 tuning seed 1002's unit 3, killed by the boss on turn 21 under a
   labelled fallback since #570 (did the hold cause it?). Starts from `harness.lua` (T074),
   `sight.lua` (T071/T075, spike first), `planner.lua` (T076), `montecarlo.py` (T077, reuse
   `read_trace`).
2. Then PR-G (freeze the suite), PR-H (the ours-vs-twin pilot), PR-I (validity), PR-J (polish).
   They merge after `/code-review` + CI on the head (Nicolas's standing OK for step 9).
3. Then **#510 step 10**: re-evaluate every chapter with the instrument and bring Nicolas the
   party levers (#510's checklist; #459, #547, #526 with #543 first).
4. Tell Nicolas where step 9 stands in plain words at the start of a session: he lost track of
   the series after the advisory panel.

## Parked or owed elsewhere

- **Draft PR #485** (ch07 moves to Distant Blade's map): parked until #510's difficulty and roster
  work is done (Nicolas, 2026-10-28).
- **Nicolas's next playtest** owes the items on #31.
- **Chapter work:** #27 (ch07, waits on #486), #493 (the wiki's remaining findings), #486
  (planning the rest of the campaign with Nicolas).
- **Where a chapter stands** is `make chapter CH=chNN`, never this file.

## Before you touch anything

This list is the INDEX; do not re-inline the content.

- **How to work here** → `CLAUDE.md` / `AGENTS.md`.
- **Why anything is the way it is** → `docs/decisions.md` (index; open the two or three you need).
  Most likely to bite: *"Playtest runs are the most expensive thing in this repo"*, *"A scenario
  written against the old design will FAIL ON SUCCESS"*, *"An artifact is not its inputs"*, and
  for injector work 0300 and 0304.
- **What is left to build** → GitHub issues; #20–#28 per chapter; the open epics are #510 (parity) and #302
  (chapter as code).
- **Which asset the FE-Repo has** → `docs/fe-repo-scouting.md` (its table says where an anim
  LIVES, not what it does).
