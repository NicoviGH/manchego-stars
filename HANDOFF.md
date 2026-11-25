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

## Next session starts here (2026-11-25; main is 698657f3 + this HANDOFF)

**The work is #764, the bot redesign** (Nicolas, 2026-11-24). Read its body, which is the
plan, first.
- **R1 #765: done.** PR #769 (ADR 0467).
- **R2 #766: the stage job, route loss and the Talk-recruit fix are merged** (PR #773, ADR 0471;
  #766's comments of 2026-11-25 have the measurements):
  - A talker is sent to the tile where it meets the recruit, on the route an earlier attempt
    saw; a job is priced by the death on its road (`routeLoss` × `W.death`, no new weight).
  - A Talk's recruit is judged as a player unit on her tile (the game's `UnitChangeFaction` in
    the judged phase), and the mend tries the talker's other acts for her. This stopped Amelia's
    Ch10 deaths after early Talks (5 of 10 games on the branch before, 0 after).
  - 10 starts (Ch10 and Ch14, s4002/3/5/7/9, two attempts each): 4 cleared clean against main's
    2, and 6 deaths against 12.
  - **Left for R2:** the clear and escort jobs, and replacing `recruitFirst` and `marchGoal`'s
    per-goal choice. Cut a new branch from main.
- **Ch10 s4009 a1's loss is no bug** (#766 comment 7169573218): the 0%-for-Eirika plans each
  forfeited Amelia's recruit, and bold's cap took an 11.8% game over (read right) over a certain
  forfeit. Recommended: no rank change; the R3 rank-order question stays open on its own.
- **Also open:** Ch10 s4003/s4007 never recruit Amelia (main too), so they never clear clean.
- **R3 #767:** have the per-turn planner play those jobs (`ctx.jobs` is written for it).
- **R4 #768:** then measure the walls.

**Ch14 s4003 as it stands** (`j766c`, two attempts): won in 18 turns, then cleared clean in 17.

**Where the traces live:** `references/sim/vanilla/c25b145e3745/traces/<tag>-b640e-cs-s4003/`.
Each start is a scout lap: replay it with
`montecarlo.py resume --game vanilla --tag <tag> --campaigns b640e-cs-s4003 --chapter 14 --last 14
--attempts 2 --scout --jobs 1`.

**Holds to revisit:** #569 waited on R1 (read its hold comment: does it reopen?). #727 waits on
R2/R3, #639 on R4. #742 lands before R4. #745 (the recorder misses a thief's drop) stays open.

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
