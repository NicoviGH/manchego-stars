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

## Next session starts here (2026-11-26; main is 8b2f0180 + HANDOFF commits)

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
**Item 1 is merged: PR #779 (cf4cf3ed, ADR 0475).** The planner forfeits what the clean clear
loses (a spoiling theft, an owed recruit's death whatever its Talk row). **A clean clear is the
chapter's end state** (Nicolas, 2026-11-26): the record counts a theft only if no later drop from
that same thief gave the item back, and the planner forfeits only a theft by a thief that keeps its
loot (no `US_DROP_ITEM`). The mend tries a robbed unit's way out first (its acts, every unit's
strike on its thief). Results: Ch10 s4003 Amelia no longer killed (still not recruited: every Talk
plan over the cap). **Ch16 s4005's Knight Crest is not saved:** thief 129 keeps its loot and Colm's
only escape is a dead-end corner; it needs a hand-off before turn 14 (Trade, or a mid-map convoy
give: #688, item 4; findings on #711 and #688). A move-list gate that kept Colm out of reach was
tried and dropped (ADR 0475). Not built: a job that sends the army after a thief that will drop
a spoiling item (the record judges it at the end).

**Item 2 is merged: PR #780 (b522735f, ADR 0476, closed #698).** A march under the cap is idle
unless some goal reads nearer than the army's best so far (botrun's `lows`, passed as
`opts.lows`; `Goals.nearer` is the one test, shared with botrun's progress count). Replays of
s4003 a1 (tags `n698a15`, `n698a21`): Ch15 won in 22 turns (R4 24), one death fewer; Ch21 in 33
(R4 40). Neither was a stuck try. Ch21 s4005 still waits: its only advance is a game-over assault
on Lyon; striking past the counter-kill refusal is built only if the R4 set shows it is needed.

**Item 3 (#766, Rennac) is merged: PR #782 (8b2f0180, ADR 0478).** A release is staged once
every striker the job can send is ready, so a door that brings more reds than the army can
gather never holds for good. It builds on
PR #781 (ADR 0477, roofed rooms in the forecast).
- **The rule:** memory lists each door that brought reds (`Timeline.releases`, an arrival's
  `by`) and what its units lost. A plan that opens one before enough units can strike its front
  that turn forfeits that loss; the nearest free strikers are sent to the door meanwhile. The
  reach is read on the map the door's change leaves (roofed tiles are unreached before it).
- **Replay `s766t` (Ch14 s4005 a2):** staged by turn 2, door opened turn 3, **L'Arachel talked
  Rennac over on turn 4**, won in 14 turns (`q766e` a2: 16, Rennac lost). **Not clean:** a red
  staff user berserked Cormag on turn 7, and he killed L'Arachel, Artur and Tana on turns 9-11
  in turns with no plan under the cap (line on #743).
- `s766r`/`s766s` were the first version, which read no unit as ready (shut-map fields); their
  turn-6 recruit came from the forfeit's hold alone. They showed the own-tile hold lead, now
  under #764's item 5.
- **Plan records carry `releases`** (door, need, ready, staged); a stager's goal row is `stage`.

**Item 4, keys, first half: PR #783 (Trade for keys, ADR 0479), open, reviewed (3 nits fixed),
awaiting CI and Nicolas's merge.** Ported from `../manchego-stars-wt4` (that worktree's step 1 is
now superseded; delete it once #783 merges). A teammate's key is a way, priced by the taker's walk
to the holder only: replay `t688a` priced the holder's walk too and lost Dozla and Gerik at the
(21,18) chest. Replay `t688b` (Ch21 s4009 a1): won in 19 turns, both chests opened, 2 deaths not
attributed (R4's try was an older bot). Details on #688's comment of 2026-11-26.
**Next:** one key per chest (#711 item 1), then items 5, 6, then one R4 set over the batch
(#764's body). Ch16 s4005's Knight Crest still needs a convoy Give or Steal (#688).

**PR #774 (the clear job, ADR 0472) stays unmerged:** no gain on its replays and it helped kill
Amelia (#767 comment of 2026-11-25 19:31). Nicolas's merge call is still open.

**Where the traces live:** `references/sim/vanilla/c25b145e3745/traces/<tag>-b640e-cs-s400N/`.
Recent tags: `s766r`-`s766t` (PR #782, Ch14 s4005), `q766a`-`q766f` (item 3, Ch14 s4005), `h766a`-`h766e`, `h775a`-`h775c` (Ch14), `f475a10`/`f475a16` (item 1's proofs),
`i730b`-`i730j` (Ch16 s4005 theft replays, ADR 0475). Replay a start with `montecarlo.py resume --game vanilla --tag <tag> --campaigns
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
