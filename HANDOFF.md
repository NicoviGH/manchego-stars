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

## Next session starts here (2026-11-24; main is 690ab0bb + this HANDOFF)

**The work is #764, the bot redesign** (Nicolas, 2026-11-24). Read its body, which is the
plan, first. In short: one-case fixes kept trading one loss for another. The bot will:
- **R1 #765:** remember the whole visible timeline of a failed attempt;
- **R2 #766:** assign each unit a job over several turns, by deadlines and threats;
- **R3 #767:** have the per-turn planner play those jobs;
- **R4 #768:** then measure the walls.

The plan lists three calls for Nicolas: the job horizon, how a job's loss is weighed against a
death, and whether R3 touches the rank's order. None of them blocks R1.

**Open PRs, both reviewed (`review-to-clean`, every finding fixed), waiting on Nicolas's merge.**
The auto-mode check blocked `gh pr merge`.
- **PR #762** (ADR 0465, refs #730): a unit's march reads its own movement costs, so fliers are
  sent.
  - Replay `fx730a` (Ch10 s4002 a1): won in 19 turns with 0 deaths; (11,15) visited on turn 3,
    but (1,11) razed instead. Main's `i730a`: 18 turns, 1 death, (11,15) razed.
  - Same-board cost: 99 vs 105 grid builds, CPU +0.3%.
  - CI green on head e1ffb426.
- **PR #763** (ADR 0466), stacked on #762: a talker marches on a recruit our act will load.
  - Rennac still leaves (`fx741a`); #741's comments 7140569535 and 7140897445 say why: from
    turn 5 on, no talker can end a turn beside him.
  - **Merge order:** #762 first, then `gh pr edit 763 --base main`, rebase it onto main, CI, then
    merge. A stack lands with `--merge` per AGENTS.md.
  - CI has not run on head b35a163f.

**Issue record, tidied 2026-11-24** (`make tidy` clean):
- **#741 closed** into #764. Its open items moved to R1 (departures counted from appearance,
  `memory.kills`) and R2 (staging a talker, the free talker before the paid one).
- **#745 moved under R1.** #671 now has a parent (#640) and a `Bot:` title.
- **Hold comments refreshed:** #569 waits on R1, #727 on R2/R3, #639 on R4. #739 is labelled
  on-hold.
- **Order:** #742 lands before R4.

**Run tags this session** (vanilla store `references/sim/vanilla/c25b145e3745`):
- `i730a`: instrumented Ch10, `review/730-pairing-instrumentation.patch`;
- `fx730a`: PR #762's replay;
- `fx741a`: PR #763's replay;
- `i741b`: instrumented Ch14 chase, `review/741-chase-instrumentation.patch`.

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
