# Handoff - Manchego Stars live state

**Read this from main** (`git show main:HANDOFF.md`): on a feature branch this file is the copy
from when the branch was cut, and may be days old.

`HANDOFF.md` is live state only: where the tree is, what is in flight, what is owed, what to do
next. **Settled decisions live in `docs/decisions.md`**; how-tos live in the files they are about;
operating rules in `CLAUDE.md`/`AGENTS.md`; findings, scope and backlog on GitHub issues. Nothing
here should still be true in a month. Before a context rollover, warn Nicolas, refresh this file,
and start a fresh instance; don't rely on auto-compaction.

**#510's work, issues and PRs, is tracked on GitHub only:** #510 → #640 (step 9) → #764 (the
redesign, worked now) and the symptom groups #752, #753, #754; step 10 is #751. The day-by-day
log that used to sit here is in this file's git history and on the issues.

## Next session starts here (2026-11-24; main is 522736d1 + this HANDOFF)

**The work is #764, the bot redesign** (Nicolas, 2026-11-24). Read its body, which is the
plan, first. In short: one-case fixes kept trading one loss for another. The bot will:
- **R1 #765: done.** PR #769 (ADR 0467): a retry's memory is each failed attempt's visible
  timeline, read off its trace by `tools/playtest/timeline.lua`.
- **R2 #766: next.** Assign each unit a job over several turns, by deadlines and threats. It
  reads `Timeline.deadlines`, `routes` and `threats`; the last two have no reader yet.
- **R3 #767:** have the per-turn planner play those jobs;
- **R4 #768:** then measure the walls.

The plan lists three calls for Nicolas: the job horizon, how a job's loss is weighed against a
death, and whether R3 touches the rank's order. R2 needs the first two: bring them as
recommendations before building.

**Merged today:** PR #762 (ADR 0465, fliers' march reads their own costs; #730 stays open, it
was only referenced), PR #763 (ADR 0466, a talker marches on a recruit our act will load), PR
#769 (R1).

**What R1's replays showed** (on PR #769):
- **Ch14 s4003 (`r765c`):** attempt 2 won, 21 turns, 0 deaths. Rennac came on turn 4; the
  planner dated his departure to turn 13 and he left on turn 13; both chests were dated to the
  phases they were lost in. Nobody could reach him or the chests in time: R2's staging.
- **Ch10 s4002 (`r765a`):** attempt 1 now visits both villages (with #762/#763). Attempt 2 lost
  two units on turn 7: the killers are in the timeline's `threats`, for R2.

**Holds to revisit now that R1 is in:** #569 waited on R1 (read its hold comment: does it
reopen?). #727 waits on R2/R3, #639 on R4. #742 lands before R4. #745 (the recorder misses a
thief's drop) is not fixed by R1 and stays open under it.

**Run tags this session** (vanilla store `references/sim/vanilla/c25b145e3745`):
- `r765a`: Ch10 s4002, two attempts; `r765c`: Ch14 s4003, two attempts (R1's replays);
- `r765b`: stopped early (ran before the review's `appeared` fix), ignore it.

**Worktrees:**
- `../manchego-stars-wt4` still holds Trade step 1 (#688), uncommitted.
- `.claude/worktrees/` holds old reviewer worktrees (untracked, deletable).

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
