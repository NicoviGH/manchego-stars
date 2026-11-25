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

## Next session starts here (2026-11-24; main is 64060b87 + this HANDOFF)

**The work is #764, the bot redesign** (Nicolas, 2026-11-24). Read its body, which is the
plan, first. In short: one-case fixes kept trading one loss for another. The bot will:
- **R1 #765: done.** PR #769 (ADR 0467).
- **R2 #766: part 1 merged** (PR #770, ADR 0468 and 0469), **and PR #770's two loose ends are
  closed** (#766's comments of 2026-11-24 have the detail):
  - PR #771: a step-aside test built from Ch14's real corridor (`r766f` turn 13) fails without
    the step aside at the default beam. The beam's "carry a fully placed plan" rule stays held by
    reading: four boards and beam widths 1 to 16 never showed it doing anything (ADR 0469).
  - PR #772, ADR 0470 (Nicolas chose option A): the death cap reads the next enemy phase and the
    wear, never the lookahead's second phase, which only breaks ties now. Deaths are graded
    against the same number (botrun `deathRead`, montecarlo `death_read`). Replay `a470a` of Ch14
    s4003 is move-for-move identical to `r766i`. **Not measured:** how often A changes play
    (when a lookahead finalist read as dying two turns out now wins on progress). Measure it on
    the next lap of games over the R2/R3 batch, not alone (ADR 0430).
  - **Left for R2:** the stage, clear and escort jobs, and replacing `recruitFirst` and
    `marchGoal`'s per-goal choice (#766's first progress comment). Cut a new branch from main.
- **R3 #767:** have the per-turn planner play those jobs (`ctx.jobs` is written for it). The
  Ch14 replays show why: L'Arachel holds Rennac's job but spends turns on her staff.
- **R4 #768:** then measure the walls.

The one call still open for Nicolas is whether R3 touches the rank's order (before R3).

**Ch14 s4003 as it stands** (`a470a`, two attempts): both won (22 and 21 turns). In attempt 2
Rennac dies on turn 13 where no plan was under the cap even on the next phase (0.536 at best):
#743's ground, the wounded unit with no safe tile.

**Where the traces live:** `references/sim/vanilla/c25b145e3745/traces/<tag>-b640e-cs-s4003/`.
Ch14 s4003's start is a scout lap: replay it with
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
