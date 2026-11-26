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

## Next session starts here (2026-11-25, night; main is 1f9d7068 + HANDOFF commits)

**The work is #764, the bot redesign** (Nicolas, 2026-11-24). Read its body, which is the plan.
R1 #765 done (PR #769); R2 #766's stage job, route loss and Talk-recruit fix merged (PR #773);
PR #777 (ADR 0473, closed #775) added the best-meeting Talk job and the Rogue's locks in the
forecast. Rennac is still missed on s4005: his Talk job dies on the corridor's danger (#766
comment 7176696969). R4 is to size that for PR #774's merge call (#767 comment).

**PR #778 merged (2026-11-25, ADR 0474, closed #742): the verdict now compares tries to the
first clean clear.** A chapter cell replays each start with memory up to the cap (12); the
verdict bounds the share of pairs where Manchego Stars needed more tries minus the share where
the twin did (ADR 0385's bounds, looks, N and margin unchanged). First-try deaths are a
reported column. Cells now cost the old cost times the mean tries; `pilot` estimates an
unmeasured start at all 12 tries, so its 8-hour refusal (SC-007) trips more often. Proof run:
vanilla Ch2 cleared on tries 1, 1, 2; Manchego Stars ch02 had no clean clear in 12 on 3 starts
(both chwinga lost every try, the known ch02 block).

**R4 #768 is done (closed): 8 of 34 clean within 3 tries, m740c 7 of 34.** Every blocker's
root cause is on the issue that owns it, and **the work order is #764's body, "After R4"**
(Nicolas, 2026-11-26: fix them all, one PR each, back to back, then one R4 set over the batch).
**Item 1 is built, not yet a PR:** branch `feat/730-forfeit-what-clean-loses`, commit fcf18766
(ADR 0475): the planner forfeits what the record's clean clear loses (a theft the game's
`AiGetItemStealRank` ranks as spoiling; an owed recruit's death whatever its Talk row). Unit
tests green; the 5 new checks fail on the old code. To finish it:
1. Read the two proof replays (started 2026-11-26, one try each, on the branch): tags
   `f475a16` (Ch16 s4005: a theft was the only spoiler there in R4) and `f475a10` (Ch10 s4003:
   Amelia killed in all 3 R4 tries). Records in `resume-runs.jsonl`; R4's are `r768a16`/`r768a10`.
   Log: the session scratchpad's `proof.log` (gone after a reboot; the records are what count).
2. Open the PR (Part of #730, #711; not Closes: #711's key items and #730's Marisa stay),
   `/code-review <PR> medium`, fix every finding, merge on CI for the head sha.

**Item 2 (next, #698):** the idle rule's march exemption (`planner.lua` ~1995, `marches`)
must count only a new low. botrun already keeps each goal's best (`lows`, `readNearest`,
botrun.lua ~1052); pass it to the planner and exempt a plan only when some unit beats its goal's
low. Change only the exemption, not `rank.progress` (that would rescore every plan).


**PR #774 (the clear job, ADR 0472) stays unmerged:** no gain on its replays and it helped kill
Amelia (#767 comment of 2026-11-25 19:31). Nicolas's merge call is still open.

**Where the traces live:** `references/sim/vanilla/c25b145e3745/traces/<tag>-b640e-cs-s400N/`.
Today's tags: `h774a` (door-hold probe), `h766a`-`h766e` (Ch14 five starts and two logged
replays), `h775a`-`h775c` (Ch14 s4005 replays of the forecast fix). Replay a start with `montecarlo.py resume --game vanilla --tag <tag> --campaigns
b640e-cs-s400N --chapter 14 --last 14 --attempts 2 --scout --jobs 1`.

**Holds to revisit:** #569 waited on R1 (read its hold comment: does it reopen?). #727 waits on
R2/R3, #639 on R4. #745 (the recorder misses a thief's drop) stays open.

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
