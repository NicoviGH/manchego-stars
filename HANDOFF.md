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

## Next session starts here (2026-11-27; main is 38e65889 + HANDOFF commits)

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

**Item 4, keys, first half is merged: PR #783 (44b1f008, ADR 0479), Trade for keys.** A Chest
Key on a teammate is a way only once its holder's own trip to that chest stalled
(`Goals.spareKey`; never a door's), priced by the taker's walk alone; a unit a teammate spares
the key pairs with the own-key openers. Replays of Ch21 s4009 a1 against main's control
`c688m` (30 turns, 0 deaths, (2,18) stalled): `t688d` is main's game to turn 21, then makes real
Trades; same result. The earlier versions (`t688a`, `t688b`) lost units: table in the PR.
**Next:** (2,18) on that start is missed for causes outside Trade (#688 comment of 2026-11-26):
Eirika's job reads loss 0 behind a Draco Zombie that one-shots her (lead, untested: `routeLoss`
returns 0 with no field through the shut (4,18) door), and the chest stalls only on turn 21
because `goalQuiet` counts only event-free phases. Test the route-loss lead first, then one key
per chest (#711 item 1), then items 5, 6, then one R4 set over the batch (#764's body).

**PR #784 is merged (5c1e8f40, ADR 0480): a job's way through a door is priced leg by leg.**
A job behind a shut door read loss 0, because its field never reached the unit. Now the loss is
read along the march's own chain (`chainTo`/`breachFor` take a start). It does not save (2,18):
replays `r688a`/`r688b` won in 38 turns with 0 deaths (main's `c688m`: 30 turns), chest still missed.

**2026-11-27 (night): item 1 (Ch16's east thief) in progress on `feat/764-lock-theft-mend`
(75cf19cd, ADR 0483, not pushed, no PR).** Status and replay table: #764 comment 7228174747.
Built: the mend for a key holder, the looter's kill keeping its chest, hand-off by Trade (only in
the mend, #688's items half), strikers at a thief's timed arrival, `stealSpoils` off-list fix.
Replay `l764e` beats main on chests (3 vs 2, 2 vs 0) and loses no key, but is not clean.
**Next on the branch:** the thief-kill plan ranks a turn of progress behind (`behind` 1 vs 0)
and is not chosen (attempt 2, turn 12); then why (20,1) is skipped. Then review, PR, and item 2.

**2026-11-27 (late): R5 sized, the green rule merged. Next: the fix order on #764 (comment
7226248041), Ch16's east thief first.**
- **R5: 11/34 clean vs R4's 8/34** (#764 comment 7223186698). Merged today: PRs #785, #786,
  #787 (Ch14's talker), and **PR #789** (38e65889, ADR 0482, #788).
- **Sizing (After R5 item 2) is done:** one Sonnet trace reader per chapter, table on #764
  comment 7224984293. Largest blockers: Ch16's east thief (8/9 tries), Ch10's Amelia (Talk route
  loss read from enemies' current tiles, 8/9), Ch13 (no plan declines a boss kill while Cormag is
  owed), Ch21 (Lyon assaulted with Ephraim hurt; (21,18) chest job dropped), Ch15 (Sleep staff).
- **The clean rule (Nicolas, 2026-11-27):** every recruit, no blue death, no reward missed; a
  green's death counts only if the green gates a reward, read from the ROM (the ending's
  `CHECK_ALIVE`s). The planner charges greens the same way. Ch19 s4002 a1: 5 blue deaths -> 3
  (`g788a` -> `g788e`); Ch19 is still unclean on blue deaths and chests (53 of 90 emptied by
  thieves on phases 7-9).
- **Next:** item 1 of #764's fix order (Ch16's east thief, and Ch19's chests: same cause), one PR
  each down the list, then R6; Ch19's blue deaths are re-sized on R6 (#764 comment of 2026-11-27).
- **Lessons:** a closed lid sleeps the Mac and pauses runs (pmset log); it is not a hang. Long runs
  go under `caffeinate -i` with the lid open. Never edit bot files while a replay plays from this
  checkout: each attempt loads them fresh.

**PR #774 (the clear job, ADR 0472) was closed unmerged** (Nicolas, 2026-11-27); R3 makes
clear-blocker jobs on top of the stage job instead.

**Where the traces live:** `references/sim/vanilla/c25b145e3745/traces/<tag>-b640e-cs-s400N/`.
Recent tags: `s766r`-`s766t` (PR #782, Ch14 s4005), `q766a`-`q766f` (item 3, Ch14 s4005), `h766a`-`h766e`, `h775a`-`h775c` (Ch14), `f475a10`/`f475a16` (item 1's proofs),
`i730b`-`i730j` (Ch16 s4005 theft replays, ADR 0475). Replay a start with `montecarlo.py resume --game vanilla --tag <tag> --campaigns
b640e-cs-s400N --chapter 14 --last 14 --attempts 2 --scout --jobs 1`.

**Holds to revisit:** #569 waited on R1 (read its hold comment: does it reopen?). #727 waits on
R2/R3, #639 on R4. #745 (the recorder misses a thief's drop) stays open.

**Worktrees:**
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
