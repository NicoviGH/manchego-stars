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

## Next session starts here (2026-11-25, late night; main is 698657f3 + HANDOFF commits)

**The work is #764, the bot redesign** (Nicolas, 2026-11-24). Read its body, which is the plan.
R1 #765 done (PR #769); R2 #766's stage job, route loss and Talk-recruit fix merged (PR #773).

**PR #777 waits for Nicolas's "merge"** (branch `feat/775-talk-best-meeting`, ADR 0473, closes
#775). It holds the best-meeting Talk job and the forecast's Rogue fix: `sight.closings`' replay
now plays `AI_ACTION_PICK` (door opens, chest empties, its item fills the bag). Replay `h775c`
(Ch14 s4005): Rennac's forecast walk matches his real one tile for tile, but he is still not
recruited (the per-turn play's gap, #767). `/code-review medium` done, every finding fixed, one
scoped re-review done; CI was running at handoff. The door hold was dropped (never fired). One
open question is on #766 (comment 7176696969: 20 reads sent him south on a2 turn 6).

**Order Nicolas set (2026-11-25): #775 (done in PR #777), then #776, then the R4 runs (#768).**

1. **#776: a step safe now that leaves no safe tile next turn** (sub-issue of #743; Tana in Ch14
   s4002, Amelia in Ch10 s4007). **Answer its question before building:** #743's probe found
   the second-phase read no guide, so first check on the recorded boards whether a "safe tile
   next turn" check would flag those deaths at t-1 and not the units that lived.
2. **R4 #768:** one attempts set repeating `m740c` exactly: `resume --chapter N --last N
   --attempts 3 --scout --route 1 --seal-at 10`, Ch10, 13, 14, 15, 16, 19 on
   b640e-cs-s4002/3/5/7/9 and Ch21 on s4003/5/7/9 (34 starts; `m740c`: 7 of 34 clean; #699
   comment 7093112364). Run in the background, after PR #777 lands.

**PR #774 (the clear job, ADR 0472) stays unmerged:** no gain on its replays and it helped kill
Amelia (#767 comment of 2026-11-25 19:31). Nicolas's merge call is still open.

**Where the traces live:** `references/sim/vanilla/c25b145e3745/traces/<tag>-b640e-cs-s400N/`.
Today's tags: `h774a` (door-hold probe), `h766a`-`h766e` (Ch14 five starts and two logged
replays), `h775a`-`h775c` (Ch14 s4005 replays of the forecast fix). Replay a start with `montecarlo.py resume --game vanilla --tag <tag> --campaigns
b640e-cs-s400N --chapter 14 --last 14 --attempts 2 --scout --jobs 1`.

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
