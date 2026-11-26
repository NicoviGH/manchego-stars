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

## Next session starts here (2026-11-26; main is 59140fe2 + HANDOFF commits)

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

**Item 3 (#766, Rennac) is in progress. PR #781 merged (59140fe2, ADR 0477): a general
forecast fix, not yet the recruit.** Read #766's last three comments first (2026-11-26).
- **Found:** Rennac and ~10 reds start Ch14 hidden under a roof past the (22,17) door (state
  `0x81`). The door's change unroofs them (`UpdateRoofedUnits`). The sandbox skipped that, so
  every door plan was judged against an empty corridor and no plan could strike the squad.
  Fixed for any roofed room (`sight.unroof`, `Board.unroofed`, the planner's re-listing).
- **Effect (s4005 a1-a2, `q766e`):** a2 opens the door on turn 3 and strikes a revealed red the
  same turn; 16 turns, 0 deaths (18 before). a1: 21 turns, L'Arachel lost on turn 14 in a
  `FALLBACK_SACRIFICE` turn (#743's case).
- **Still lost: Rennac.** The one recruit (`r768a14` a3) had three strikers beside the door
  when it opened (3 kills that turn). In the `q766` replays the army is 4-8 tiles back then.
- **Next, keep iterating on item 3 (Nicolas, 2026-11-26: "continue iterating"):** the bot must
  gather strikers at an act memory says releases a squad before making it: multi-turn staging,
  general, no Rennac or door case (#767's stage/clear; Nicolas rejected a striker rule written
  for this door). Two measured leads on #766: the Talk job's route loss overprices a walk with
  the army around (death 0.995-1.0, 0 of 4 died; counting this turn's stop alone kept the job a
  turn longer, `q766f`), and the dropped door-waits-for-talker rule.
- **Cheap replay:** `montecarlo.py resume --game vanilla --tag <new> --campaigns b640e-cs-s4005
  --chapter 14 --last 14 --attempts 2 --scout --route 1 --seal-at 10 --jobs 1` (~15 min). Plan
  records now carry `jobs` (each job's worth, chance, loss, net, chosen).

**PR #774 (the clear job, ADR 0472) stays unmerged:** no gain on its replays and it helped kill
Amelia (#767 comment of 2026-11-25 19:31). Nicolas's merge call is still open.

**Where the traces live:** `references/sim/vanilla/c25b145e3745/traces/<tag>-b640e-cs-s400N/`.
Recent tags: `q766a`-`q766f` (item 3, Ch14 s4005), `h766a`-`h766e`, `h775a`-`h775c` (Ch14), `f475a10`/`f475a16` (item 1's proofs),
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
