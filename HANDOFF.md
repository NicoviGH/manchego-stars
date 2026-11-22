# Handoff - Manchego Stars live state

**Read this from main** (`git show main:HANDOFF.md`): on a feature branch this file is the copy
from when the branch was cut, and may be days old.

`HANDOFF.md` is live state only: where the tree is, what is in flight, what is owed, what to do
next. **Settled decisions live in `docs/decisions.md`**; how-tos live in the files they are about;
operating rules in `CLAUDE.md`/`AGENTS.md`; findings, scope and backlog on GitHub issues. Nothing
here should still be true in a month. Before a context rollover, warn Nicolas, refresh this file,
and start a fresh instance; don't rely on auto-compaction.

**#510's work, issues and PRs, is tracked on GitHub only:** #510 and its sub-issue #640 (step 9).

**Next session starts here (2026-11-23; main is d6339c1e + this HANDOFF). All six overnight PRs are merged:** #722 (ADR 0444), the stack #723 → #725 → #726 → #728 (ADRs 0445-0448, `--merge`), and #729 (ADR 0449). Each was brought up to main, its decisions index regenerated, and merged on green CI for its new head. #721, #724 and #712 are closed; #714 and #713 stay open for the calls below. #699's status table (comment 7066011205) is current.

- **The repo deletes a head branch on merge** and GitHub retargets its children itself. A stacked PR's clean merge can still leave `docs/decisions.md` stale (the record count), so regenerate the index on every branch after its parent lands.
- **Next, once the calls are made:** one `attempts` set over the batch on #699's starts (`m699c<N>`). Open without a call: 2c (our counter kills a recruit-to-be), #727 (positional AI changes, Ch10 and 14), #711's leftovers.
- **Nicolas's calls, waiting:**
  - #714's forfeit half: a goal driven to 0 before its deadline counts in `forfeits` (comment 7075363029).
  - #713 fix 1: a ghost at the last-seen tile vs ADR 0399's live tile (7078483524).
  - #713 fix 3: sum the unseen strikes (7078468840). **New evidence for it (7079106170):** a bisect shows #711 (PR #718) made vanilla Ch19 `b640e-cs-s4003` a1 lose on turn 7 (Eirika dead); its parent won on turn 13. The prep key makes the fog chests goals, and the advance plan read fog risk 0.001. Main loses Ch19 a1 until fix 3 or a call. #718 is not reverted.
  - #717 classed: the three Ch15 "0-risk" deaths are a grading artifact (the mover plan's likeliest-way read). Your call: grade by the committed plan's weighted read (#717's last comment).
- **Lessons from the night (how to work):**
  - Every issue claim was checked before building, and three were wrong:
    - #714's "a turn to spare": the village has none.
    - #713's "last-seen tile": no such tile exists; the board reads every enemy's true tile.
    - #717's "read at 0": the grader read the wrong plan.
  - A new candidate act can be offered and still never judged: the planner's per-unit cut (`PER_UNIT`) dropped #722's careful march. Check that an act reaches the beam, not only the candidate list.
  - A replay that shows no change is not proof that a fix does nothing. Read the trace for why. Ch13 needed three PRs (#723, #725, #726) before Cormag's goal held the win.
- **Run tags:** `fix714*`, `fix721`, `fix724*`, `fix712*`, `fix713*`, `iso711`, `isomain`, `bis0-2`.

*Before that (2026-11-22; main was d7892189 + HANDOFF).* Four #699 blockers merged today, one PR each, built by Sonnet subagents and reviewed by them (`review-to-clean`). Next was #714 (a march offers only the nearest and the safest tile). The status table on #699 (comment 7066011205) is current. After #714 the order is 2a/2b, then #712, #713 and #717. Then one `attempts` set over the batch, on the #699 measurement's starts (`m699c<N>`).

- **Merged:**
  - **PR #715 (#710, ADR 0440).** A recruit standing on a locked tile is talked to from beside it. The chance, the planner and the march all read it that way.
    - Rennac (0x1C) is still missed in Ch14: every approach is over the cap. That is #714's pattern; the witness is #714 comment 7071832697.
  - **PR #716 (#709, ADR 0441).** Terrain healing is modelled everywhere a human sees it: the judged enemy phase, the lookahead, our own and green units' phases, and `W.dealt`.
    - Nicolas's progress rule: under the risk cap, any wound that outlasts the heal is progress. Over the cap, a wound counts only with a kill chance.
    - Ch15 proof (`p709b`, 5 campaigns x 3 attempts): 3 of 5 campaigns clean against 0; deaths 55 to 28; stuck 5 to 2.
    - Cost: +1.7% planning frames on identical boards.
  - **PR #718 (#711 parts 1 and 3, ADR 0442).** Prep takes one Chest Key per reachable chest; a Lockpick's uses are shared across chests and doors.
    - The judged phase plays the game AI's steal, and the planner prices the chance of losing the last opener.
    - The emulator probe `PT_VANILLA=1 PT_LEAKGUARD=1 tools/playtest/run.sh stealprobe` passes. With the bag keeps removed it reports 4 leaks.
  - **PR #720 (#719, ADR 0443).** A chest goes first to a unit that opens it itself. A stalled sent pair is re-paired, each unit tried once per quiet spell.
    - Ch16 `b640e-cs-s4009` attempt 1: stuck on turn 34 (`fix711c`) before, won on turn 19 after (`fix719c`).
- **Open, filed:**
  - **#717:** 3 Ch15 deaths to Caellach at 0 predicted risk.
  - **#711, still open:**
    - ADR 0442's price is yes or no on the last opener, so a stolen Lockpick beside a single-use key prices at zero (comment 7074603493). Fix: price the chests left unopenable, by uses.
    - A thief carrying a stolen item is not a goal yet.
    - Doors and the lookahead's thefts are not priced.
    - Part 2 (buying keys) is with #693.
  - **#719's sweep:** the pairing pattern showed in 72 attempts, most in ch23 (41, 13 of them stuck). Whether ch23's stalls are fixed by #720 is untested.
- **How to work (Nicolas, this session):**
  - Don't trust your own assumptions. Settle a "why" with a cheap read-only subagent on the trace and the code before building. Twice the subagent overturned the plan: #719's first fix, and the Ch15 assault cause.
  - A fix that adds a game call writing unit memory needs `api.keep16` and an emulator smoke run. Unit tests missed both #716's turn-1 crash (a `Board.bind` export) and #718's sandbox leak.
  - Usage ran out once mid-session (5-hour limit). A stopped subagent resumes with SendMessage.
- **Run tags in the vanilla store:**
  - Ch15: `fix709c/d/e`, `diag709b`, `p709b`, `t709base`/`t709br`.
  - Ch16: `fix711`, `fix711c/d`, `fix719`, `fix719b/c`.
  - Ch21: `fix711b`.

*Before that (2026-11-21, night; main was 062e8801 + HANDOFFs): #699's measurement is done (comment 7071434440): the five merged fixes gave no measurable gain (1 of 34 clean against the lap's 2). Every blocker is root-caused and filed as a sub-issue of #699: #709-#714. The status table (7066011205) gives the order: #710 (a certain bug), #709 (this week's #702 regression on Ch15), #711, #714, then 2a/2b, then #712/#713. Nicolas: the cap stays as it is, and the next session works #709-#714 one PR at a time on Sonnet subagents (the plan is on #699, the comment after 7071434440). Run tags `m699c<N>` and `probe699*` are in the vanilla store.**

*Before that (2026-11-21, late; main is 062e8801 + HANDOFF): the work is the measurement on #699 (comment 7069149395).** #699's plan comment (7066011205) opens with a status table; keep it current. The GitHub tidy-up #706 is closed. Its guard `make tidy` (#707, PR #708) is in the session-start checklist: run it and fix every finding. `../manchego-stars-wt2` is deleted; `../manchego-stars-wt4` still holds Trade (#688), uncommitted. Bot issues should carry a bot title prefix (`Bot`, `#510`, `Harness`, ...) so the orphan check sees them (`tools/gh_tidy.py` docstring).

*Before that (2026-11-21, afternoon):* The work is #699: its plan comment (7066011205), Nicolas's calls after it, and the progress comment (7067278347). #700-#703 are merged. #704 was measured and closed; #705 (chest keys and door openers) is merged. The state is on #699's latest comments.



*Earlier (2026-11-21, evening of the lap):* Next session starts here (2026-11-21, evening; main is a9a3bff2 + HANDOFF). No runs are going. The work is #699: read its plan comment (7066011205) and Nicolas's calls (the comment after it) first.**

- **#699 (sub-issue of #640) ranks what stops clean clears**, from the `b640e` lap (6 of 10 campaigns finished the game, none clean throughout; tables on #640, `review/640-batch/analysis-{losses,growth}.md`, gitignored). **Do the work in this order:**
  1. **Fix 3: the recorder error.** A two-way party conversation (Duessel and Cormag) is listed as an owed recruit (`harness.lua` ~3691). It changes no play.
  2. **Fix 1: recruit deadlines (2a-2c).** Rennac (0x1C) leaves Ch14 by turn 10, and L'Arachel, who recruits him free, was benched in all 131 attempts. Cormag (0x0E) arrives on turn 5 but Ch13 is won on turns 2-4. Amelia and Marisa are mostly killed by our own counters.
  3. **The cap fix (3a-3b).** Nicolas: holding still is not a viable choice (paralysis by analysis; only real baiting is an exception), so a plan making no progress does not pass the cap by default. It includes #698 (the Lyon assault always seats the lords, so it always reads as game over) and #688's risk-blind goal pricing.
  4. **The ally ruling (clarification, not a new definition; amend ADR 0376).** A green's death breaks clean only if it is recruitable, gates a reward (like Ch6's children), or ends the game (an escort such as Mansel 0xC8). Check each chapter's greens in the decomp first: Ch19's armor knights 0xCD, then Ch17.
  5. **Trade (#688)**, wherever it fits best, expected after the cap fix. Its work is UNCOMMITTED in `../manchego-stars-wt4` (feat/688-trade, which also holds #687's port).
  - **Running alongside, on cheap subagents (Haiku or Sonnet): root-cause cause 5** (56% of player deaths happen on turns where every plan was over the cap), using each hypothesis's test, to a confirmed or refuted verdict. Nicolas: never leave a cause "unconfirmed"; measure it. The same goes for the plan's other untested lines: a Lyon attack without the lords, the other 62 stuck Ch15 attempts, L'Arachel's benching, Mansel's deaths.
  - Each fix ships with a unit test that fails on main and one replay (ADR 0430). Step-9 PRs merge after review and CI.
- **Usage (Nicolas, 2026-11-21): no fan-outs of Opus or Fable subagents.** Use one strong agent at most, and have it send cheap subagents for the details. Fable was out of credits on 2026-11-21.
- **Closed:** #662 (strength does not predict clean clears). **Merged:** PR #697 (#696, ADR 0438): the game's end counts as a won chapter.
- **#689** is the parent issue for every choice a human player has, with sub-issues #688 and #690-#695. #690 and #694 need his calls.
- **Worktrees:** `../manchego-stars-wt2` is deleted (2026-11-21). Each worktree needs `tools/emulator` copied in to run games. Reviewers must work in a worktree, never in this checkout (one once left it detached at a PR head while runs went from it).
- **Open, to file or look into:** E_21's deploy benches Colm (0x09); Joshua (0x20) listed as a thief in the deploy record; friendly fire on Cormag; Ephraim's over-cap death in #687's `chest2` replay (folds into cause 5).

**2026-11-19, night (main was ea12724e). #639 (promote at L10 or L20) is on hold** (comment 7011738055 says why and what reopens it).

- **#671 (re-list cost): two PRs merged, both listing the same plans as before** (#671 comments 7029490721, 7031190932).
  - PR #677: the board is read once per re-list, the Talk check is reused, and the danger grids are kept on a kill. −16% CPU on Ch8 turns 1-3.
  - PR #678: a strike is keyed only by the reds the game's AI can read, ADR 0431. −13% more. Guard `PT_STRIKECHECK=1` (no mismatch on two chapters).
  - Skipping used units in the re-list was measured (−14%) but not shipped: not provably the same plans (risk raised by Nicolas 2026-11-20; stash kept). Next: the batch run (step 4).
- **The batch lap starts without the frozen suite first** (recommended 2026-11-20, Nicolas asked why the suite should go first): L10 vs L20 is paired on one bot, and every failure is traced to its cause. The suite runs before the L10/L20 verdict is drawn or acted on, over every change since 704bf738.

- **How we work now (Nicolas, 2026-11-19; AGENTS.md, ADR 0430):**
  - A bot PR proves its fix with a unit test that fails without it, plus ONE replay of the game that showed the problem.
  - Timings only when a change adds planning work to every turn, or touches tests or CI.
  - Fixes land back to back. Games are played when a batch of fixes has a real chance of a better result.
  - Correctness first: a slowdown may go to its own issue (#671), by Nicolas's call.
  - Clean still means every chest, village and recruit, with no loss. No line of work is parked for lack of movement.
- **Merged last: PR #676, which closes #663 (ADR 0427 amended).** Vanilla Ch8's west chests sit behind the (1,5) door; `wallsOnWays` read a wall only against the goal's own field, which stops at a door, so the cracked wall at (4,8) left every strike list once Colm (charId 9) turned for the chests. It now also reads each wall against each obstacle on the unit's cheapest chain.
  - Proof: the new unit test (and its guard) fail without the fix. One replay of `t639-cs-s4003` Ch8 a1 (`fix663-…`): won clean in 19 turns, no deaths; Forde (0x10) broke the wall, Colm took both chests. Main: Colm dead, both chests missed. One game only.
  - Review: 3 findings (a guard case, a comment wrap, the ADR's proof wording) and a scoped re-review, all fixed.
- **Merged before it: PR #675, which closes #674 (ADR 0433).** The judged enemy phase now plays an enemy's status staff (Berserk, Sleep, Silence). The game's AI decides the cast; the bot reads the hit chance with the game's `GetOffensiveStaffAccuracy` on the tile the AI casts from.
  - In the judged phase the hit is a way of its own, split like a counter kill. One turn ahead (`nextPhase`) a hit of even odds or better lands, so a unit berserked in the first phase moves in the second phase's berserk phase. The army's reply between the phases leaves a sleeping or berserked unit where it stands (`Sight.heldAtReply`).
  - Proof: unit tests that fail on main, and the manual probe `PT_VANILLA=1 tools/playtest/run.sh staffprobe` (Prologue, an enemy handed a Berserk staff beside Eirika): PASS, FAIL on main. Sleep and Silence share the same path but are not probed in the emulator; ADR 0433 says why. The Ch14 game could not be replayed (old instrument).
  - Review: 8 findings and a scoped re-review, all fixed.
- **Merged before it: PR #673, which closes #660 (ADR 0432).** The judged enemy phase now plays the game's berserk phase first: the player's berserked units decide with the game's berserked AI, then the enemy phase is ordered on the board they leave. A death to a berserked player unit is flagged `berserk` (not a separate cause, unlike the issue's wording: the cause still says whether the plan read it).
  - Proof: unit tests that fail on main, and the manual emulator probe `PT_VANILLA=1 tools/playtest/run.sh berserkprobe` (Prologue, Seth berserked beside Eirika): PASS, FAIL on main. The Ch14 game itself could not be replayed (old instrument). `suite --only scout-ch14/1001` on the fix: won on turn 21, no deaths; the staff missed, so the berserk phase was not exercised there.
  - Review: 15 findings and a scoped re-review, all fixed; the PR body lists them. The gap it left, #674, is closed by PR #675 above.
- **Merged earlier tonight: PR #672, which closes #664 (ADR 0409 amended).**
  - A scout lap gives a chapter every attempt up to the cap (12) for a clean clear. Only then does it carry on, from its best unclean win: the fewest player units lost, then the fewest recruits and rewards missed, then the earliest.
  - Each unclean win's end state is kept in memory (harness `api.keep`, only the best so far) and put back at the cap (`api.restore`). Nothing is played again. The restore checks the turn and dice it kept and refuses a mismatch as a crash.
  - A scouted chapter's line has `attempts` = the cap and `scouted_from` = the attempt carried on from.
  - Proof: the unit tests fail on the old rule. Replays `p664c` and `p664d` (vanilla Ch8 from `t639-cs-s4003/9`, `--attempts 2`): both attempts won with one unit lost, attempt 1 was restored, and the run ended `done`.
  - Cost: a chapter the bot cannot clear clean now plays 12 attempts in a scout lap, where it played 1 to 4.
  - Review: 12 findings and a scoped re-review (2 notes), all fixed; the PR body lists them.
- **Work in order (all under #640):**
  1. ~~#662~~ done for now (2026-11-19): three planner experiments (rank order, chip-then-finish, a price on forgone experience) did not raise the bench's levels, and two lost Ephraim in Ch5x. None merges (local branches `exp/662-*`). Nicolas: the bench's levels matter only if they cost a clean clear. #662 stays open on that question, answered by step 4's failures. Comments 7027586654, 7028056654, 7028303067.
  2. ~~#663~~ done (PR #676).
  3. ~~#671~~ two PRs merged (#677, #678); open with leads, Nicolas's call whether to go on.
  4. Then one batch run: an `attempts` set or a fresh lap from the prologue, L10 and L20, measured on clean clears at any attempt plus attempts to clean. The frozen suite on main still owes a run before the bot's reading is relied on.
- **Kept, not merged:** stash `661 escort price (unproven, kept)` and the local branch `feat/661-escort-leaves-the-openers-tile`. It is the price for an escort with no key standing on the opener's tile. It did not stop Eirika's squat in `fix661` a4, and why is untested. Drop it if Ch8's squats are gone on #669's code.
- **Also open:** #652 (the vanilla Ch3 stall, not re-checked), #657, #658 (a weight call), #651 (on hold). The Dance act is missing from the bot (Tethys); no issue is filed yet.
- **Disk:** about 22 GB free after the 2026-11-19 cleanup.

**2026-11-19, night (main was 1cf686b6). Merged: PR #669 (ADR 0431), which closes #661 and #670.**

- When a plan opens a door, breaks a wall or kills an enemy, the units still to act gain the acts that change makes new.
- #661's first diagnosis was wrong. The unit on the door tile was Lute (charId 12), who holds a Door Key. Every plan that opened the door was over the cap, because no later unit could step into the doorway or strike past it (101 door plans, 0 follow-ups). Comments 7019945016 and 7020038218 have the details.
- Vanilla Ch8, `e639-t639-cs-s4002/9` attempt 1: main won in 57 turns, not clean. The branch won clean in 16 and 17 turns, with no deaths (`relist661e`, `relist661g`). These were the first clean Ch8 clears; 48 earlier games had none. One game only.
- **Cost (#671):** 8.1 s of CPU per player phase, against main's 2.24 s. Turn 1's first decision is 10,043 frames against 7,127. Most of it is the kill trigger. The lead and the numbers are on #671.

**2026-11-18, late. In flight then: #639, "is the bot's party strong enough past Ch8? Vanilla band to Ch20, and promote at L10 or L20."** Read #639's plan comment (6992662334) and its progress comment (6998840930) first; they hold everything below in full.

- **Merged today for #639:** PR #650 (`resume --seal-at`), PR #653 (the vanilla band to Ch21 on both routes, ADR 0426), PR #656 (#654: the Ch2 Drop crash; `Sight.asActive` no longer erases an ally).
- **In progress: #655, vanilla Ch8's chests** (every trunk lap stopped at Ch8 on them). The design and Nicolas's two calls are on #655 (comment 6996120769):
  - the wall's fall time counts strikers where the plan puts them;
  - wall strikes lose the flat breach weight.
  - The work is on `feat/655-walls-costed-by-the-army` (WIP 59ae1304, not for merge), built by an Opus subagent that stopped at the usage limit.
  - Next on it: check the new tests fail on main's code, make the "goal looks barred" rule (`stepsToward`) honest about a wall still waiting to fall, the ADR, the Ch8 replays (`t639-cs-s4003`, `-s4001` and `-s4007` attempt 1), `suite --only vanilla-ch3/1001,scout-ch10/1001,scout-ch13/1001,scout-ch14/1001` beside main, then the PR, `/code-review medium`, CI and merge. Nicolas allowed merging #655's fix after review and CI.
- **Then:**
  1. The frozen suite on main. The last run (704bf738) refused promotion on 3 stall regressions; the vanilla one is bisected to #628 and filed as #652.
  2. Resume the forks from the trunk's saved Ch8 starts (`t639-cs-s40NN`, index 9): `--tag e639 --route 1` and `--tag i639 --route 2`, plus campaign 4005 from its saved Ch2 start.
  3. The L20 forks from each branch's first seal.
  4. The table and the verdict: 15 of 20 pairs.
- **Filed today:** #651 (the Ch13 mis-index; on hold, Manchego Stars only), #652, #654, #655, #657 (a legality check on freshly planned first acts), #658 (the door and key double reward). All are under #640.

**Earlier the same day.** Three #510 PRs merged, each after `/code-review`, its fixes and CI:

- **#643 (#642, ADR 0423): a plan pays for the weapon uses it spends.** A legendary use costs 300 gold over the dearest shop weapon that makes the same strike; the price is charged on the judged plan only, never in the beam. Ch17 seeds 1-3: 18/18 won, Twin strikes 34 → 13.
- **#645 (#644, ADR 0424): the simulated enemy phase plays each weapon at the uses it will have** (a weapon that breaks mid-phase is gone for the rest of it). +0.4% CPU.
- **#646 (#641, ADR 0425): the throne assault seats only strikers that hurt the boss, and baits when they cannot kill it** (the heaviest striker waits on its strike tile holding the weapon, so the boss's attack eats its counter). Also: a plan's win chance ranks it first only at 0.5 or better (`M.GONE`); below that it counts through value. E_20 (Morva) is now **won on turn 42** (Ephraim baits with Siegmund, his counter kills her, Eirika seizes); base was stuck on turn 47. Ch17 18/18. Runs: `review/641-runs/`, `review/642-runs/` (gitignored).
- **Still open:** I_14 (Ephraim route, Vigarde on the throne): no clear. The bait chips him for less than the throne heals (+5 a turn); a strength wall, which is what #639 checks. A Seize objective's win chance does not count the holder blocking the tile (ADR 0425, open).
- **#647 (closed by PR #648):** a game's dice come from the campaign seed (once, at New Game) and the retry within a chapter; `attempts --seed` only changes the bot's style. `attempts --seed 1-3` now ends with `N games, M distinct`, so a report says how many different games it played. Open threads are listed on #640 (comment 6990674702).
- **AGENTS.md** now holds the model rule: every subagent starts with its model set explicitly, Sonnet by default (Opus burned the usage limit). Codex is retired.

**Before that (same day): PR #638 is merged** (Nicolas: "Merge it", 2026-11-17): E_20's crash was a healer listing itself for Physic. The game makes every unit-menu list with the acting unit off the unit map (`UnitBeginAction`), so a staff never heals its holder; the bot's sandbox stood the healer on its tile. `Sight.asActive` now stages the unit as the game does, and `s.heals` and `canAttack` use it. E_20 attempt 1 replayed on the fix (tag `selfheal2`): no crash, 48 turns, ended `stuck`, 6 deaths (not looked into). Before that, **PR #637 was merged** (ADR 0389 amended): the lookahead's and the wear's second phase now read the **army's reply** between the two enemy phases (every kill at even odds or better, then each other unit to its safest free tile) instead of our units holding. `PT_REPLY=hold` is the control. Read #510 comments 6960188976, 6962994569 (results, corrected count) and 6961789474 (the misses, a lead) first.

- **What it did** (same 32 starts, attempts and dice; Ch8 ×6 pinned campaigns, E_15 from `lap4e`,
  I_13 from `lap4p`): won 17 → 20, lost 2 → 0, deaths 38 → 30, fallback plans 182 → 98. One
  game a pair: a lead. The frozen suite has not been run on it (it runs before the bot's
  reading is relied on, over every change since the last one).
- **The reply's blind spot (open):** it assumes a turn the bot does not then play. Of 9 deaths
  after a lookahead, 4 were by an enemy the reply had counted killed (3 at 100%), none of them
  attacked that turn; others were steps the bot did not take. Untested: why the next plan
  passes up a sure kill the reply found (#510 comment 6962994569 names the four decisions).
  139 of 431 reply kills were at 50-99% and taken as made; untested whether their misses
  change a plan.
- **Lead kept (#510 comment 6961789474):** the next phase's simulation sends an enemy at a
  different unit than the game does (`aiDecide`'s target choice; two decisions named there).
- **Party strength (Nicolas asked; checked at Ch8 only):** entering Ch8 the bot's deployed party
  has a median of about L4 against the derived band's typical L7 (`docs/fe8-pacing-reference.md`);
  Eirika L3. At I_13 (Ephraim route) Ephraim/Seth L12, Kyle L11, the rest L8-9 or below,
  only Lute promoted. The band stops at Ch8, so "under-strength later" is a lead. Likely cause,
  untested: Seth (promoted) takes the kills.
- **Next, in order:** (1) #639, extend the level band (`tools/exp_curve.py`) to the route chapters and compare the bot's
  party chapter by chapter, who takes the experience; (2) laps again from the prologue.
- **CI:** the runner's default Python moved to 3.13 today and dropped `aifc`; main's `tests` job
  had failed since. #637 pins 3.12 on the `tests` and `verdict-diff` jobs (the ROM build keeps
  the system Python its decomp scripts' `#!/bin/python3` runs).
- **Where the laps stopped** (states in the vanilla store):
  - Eirika: `bag1-heal4-heal1-lap4e-cs-s4006`, E_20. The turn-24 crash is fixed (PR #638);
    attempt 1 replayed as `selfheal2-…` ends `stuck` after 48 turns with 6 deaths (no
    progress in 16 player phases). Its throne assault is root-caused in #641 (Morva's counter;
    the Twins already spent).
  - Ephraim: `lap4p-cs-s4006`, **I_14 (Seize, Vigarde charId 0x6B on the throne): no clear in
    12 attempts.** A strength wall, not a missing plan: `feat/510-throne-assault` (unshipped)
    builds the assault on the throne's holder, and every assault reads a unit dying at about
    99%. Same 12 games move for move.
- **Found, not fixed:** E_19's losses are mostly its green civilians (charId 0xCD, 7 to 18
  deaths an attempt). Kept from before: `story` names every
  generic enemy "the Knight"; rejected plans record only `max_die`; `scout-ch6` turn 2 at a 0%
  read; Colm in `scout-ch14`.
- **Kept states:** the overnight tags (`lap4e`, `lap4p`, `heal1`-`heal4`, `canto1`, `vac1`,
  `bag1`, `throne1`) are probes on branch code, never a proof base. Today's: `reply1*` (the
  hold, shadow), `replyon1*` (first cut), `replyfix1*` (#637's code). Open from before: slow
  pre-commit timing; whether verdicts should leave out `stale` runs (Nicolas's call).

**PR #608 is merged** (43468046; Nicolas: "Yes merge when able and handoff", 2026-11-13; ADR 0407).
- A simulated enemy phase and a single strike now start as the game's phase does
  (`Sight.aiPhaseStart`: `AiPhaseInit`'s fields and its two calls, the faction red). That was
  finding 6.
- **It was the cause of the looting read's last open lead (confirmed):** once every player
  unit had acted, `gAiState.flags` read `AI_FLAG_BERSERKED` and every simulated enemy decided
  as a berserked unit. Ch9 4006 attempt 1: 104 of 320 looter decisions attacked a red unit
  without the fix, none with it.
- That attempt is a loss on turn 10 without the fix and a win in 19 turns with no death with
  it (tags `phstart1ctl`, `phstart1`, `phstart3`). One game: a lead. The village and the
  recruit are still missed.
- Cost level with main (the ADR has the table and the three changes that got it there). The
  three suite runs played keep main's acts; no leak.
- Review: `/code-review 608 medium` (11 findings) and one scoped re-review (6 notes), all
  fixed; CI green on the head.
- **Untested (ADR 0407 lists them):** that no AI path reads the scratch maps a later strike on
  a board no longer refills; the looting read's `bestBlueMov` of 0; what else the phase start
  decides (turn order after a wound, enemy healers, the AI's keys on turn 1).

**PR #606 is merged** (b869fce5; Nicolas: "merge", 2026-11-13), no open PR of this work.
- What it is now: a simulated enemy decision puts back what the game wrote on unit structs.
  Four leaks, each with a unit test that fails without its fix: the AI bytes (`Sight.keepAi`,
  once a sandbox, every unit), the fog bits a map refresh rewrites (`keepFog` / `refresh`;
  vanilla Ch6 turn 2), a ballista's rider stepped off by the AI's attack decision and the
  redraw's map-sprite pointers (`keepRide`; vanilla Ch13 scout, seed 2002, turn 11).
- **`PT_LEAKGUARD=1`** (off by default, about a fifth slower): a nested sandbox that leaves a
  unit struct or the trap pool changed is logged, put back and played on; the attempt ends
  `crashed` with every leak in its record's `leaks` (PR #607, ADR 0406). It found the last
  three leaks. Set it for one run after any change to what a sandbox calls.
- Review: `/code-review 606 medium` by a fresh subagent (9 findings) and one scoped re-review
  (4 notes), all applied; the PR body lists them with the proofs and the back-to-back timings.
- Frozen suite with held-out seeds on f7e1e002, guard on: **PROMOTED, 0 regressions, 0 runs
  without a result, no leak raised** (instrument `70cb82b1f331+v2`). All 56 runs play the acts
  of the PR's earlier suite, so the fog and ballista fixes moved no suite game; 45 of 56 are
  main's.
- Campaign 4006's Ch9 attempt 1 is a win in 19 turns on main and a loss on turn 10 on this
  PR (the lord dies on a plan over the cap); so it was before the review (tags `keepai1` to
  `keepai6`). Not looked into.
- Finding 6 and the looting read's last lead are closed by PR #608 (above).

**PR #607 is merged** (cd2a2458; Nicolas: "Merge when green", 2026-11-13; ADR 0406).
- `montecarlo.py suite --only <start>[/<seed>],...` plays only those runs, checks only those
  starts' pins, and judges nothing; a held-out run prints only its `held_out_tag`. One vanilla
  `scout-ch6` run: 12 s against the suite's 16 minutes.
- `PT_LEAKGUARD=1` lists every leak in one run (control: `keepFog` off, 9 leaks, the same
  11297 frames played to the same end).
- Review: `/code-review 607 medium` (10 findings) and one scoped re-review (1 new bug: a word
  leaked to 1 broke the leak line), all fixed; CI green on the head.

**The march from each unit's own turns was built and is NOT shipped** (branch
`feat/510-own-march`, ad247931, local only). On Ch7 it ends the 28-turn pocket and splits the
army from the lord, who then dies alone (tags `ownmarch1` against `ownmarch1ctl`). With PR
#604's dice main clears Ch7 clean on attempt 2 from both starts: Ch7 is no longer a wall.
The pocket itself is terrain: the river at (5,14) costs the lord her whole move (inferred from
her reach), so (5,15) is her only way in, and an ally stood on it. **Step 2 of the agreed
order is therefore the wrong base for item E; Nicolas has not been asked yet.** My
recommendation, his call (it is a weight): on a Seize map count the seizing unit's progress
above an escort's, so the plan that clears her tile wins.

**Probes are throwaway and gone** (written to the session scratchpad); the tags above are in
the vanilla store's `resume-runs.jsonl`. `story` names every enemy "the Archer" on vanilla Ch7
(seen, not looked into).

**PR #605 is merged** (2aa69c3c; Nicolas: "yeah merge", 2026-11-13), no open PR of this work.
ADR 0405 has the tables; the results are also a #510 comment of 2026-11-13.
- **What it does:** a judged plan for each ledger goal's offered Talk, Visit or chest no plan
  holds (`goal`); two plans without the Seize while a goal is `feasible` and every plan seizes
  (`noseize`: the first plan less its Seize, and every unit holding); and **no enemy phase is
  judged after the Seize**, nor the lookahead's. That last one was a judge error older than
  the PR: a unit at risk anywhere put the win over the cap.
- **What the runs say:** the beam no longer hides the act (confirmed on Ch9 4006 turn 11 and
  Ch8 4001 turn 16), and **neither chapter's result is better**. Ch9: the Talk plan is over
  the cap (30.8% the lord dies after it), same games as main's before. Ch8 4001 attempt 1: the
  bot waits turns 16 to 18 for the thief (Colm, charId 9) and seizes on turn 19 when he is at
  63.5%; 19 turns against 16, the same one death, the chests still missed. The other three Ch8
  attempts are the same games as before (the chests were already `stalled`).
- **The suite** on the final code: PROMOTED, 0 regressions (instrument `2374a75d5563+v2`, not
  refrozen); 7 of 56 runs play different acts, each with the same outcome, deaths and missed
  rewards.
- **Found, not built:** the ledger does not know a recruit can leave. Ch9's recruit (Amelia,
  charId 18) left the map in the enemy phase of turn 11 (`missed_recruits`: `left_map`); her
  row had no `closes_on`, so the plan played read `forfeits` 0.
- **Untested:** whether the judge error was behind the earlier late deaths on Ch8 (Colm,
  turns 17 to 23).
- **Names:** a unit is named from the decomp's `constants/characters.h` by its charId before
  any pronoun is used (the thief was written "she" for a day; Nicolas caught it).

**Item D's leads still open** (#510 comment 6842371541 has all of them): Ch7's pocket (4007):
the march's field is the lord's for every unit, so an ally sits on her one nearer tile for 22
turns. Ch8's west chests: the thief (Colm) is sent alone and stops short with enemy id 142 on his
road. Ch7 4005 turn 3 and the Ch9 flyer on turn 2: under the cap this phase, wounded and alone
the next (item F's case). Ch9's village: `closings` has an empty looter list from turn 2 on.
**The dump is kept, not merged:** local branch `probe/510-fwd1-d` (c7c27494), `PT_DPROBE=1`
before `montecarlo.py resume`; `DPROBE <json>` lines land in `workers/*.log`. Rebase it before
reuse.

**PR #604 is merged** (Nicolas: "Merge and handoff", 2026-11-12), no open PR of this work.
- Attempt k of a chapter start has the game's RNG moved on (k - 1) * 1009 draws, no re-seed;
  attempt 1 moves none. The stop "every style played" is gone: a chapter stops at the cap of
  12. `resume --attempts N` bounds it, and a run that hits a lowered cap ends `capped`.
- **One draw was not enough** (the first build): the game gave it back in turn 1 (59 draws
  against 60) and played the same game. The PR body has the tables. What drew one fewer is a
  lead only (the die per tied path direction, bmidoten.c:218-226). Not proven: that a
  1009-draw lead can never be given back. Nicolas was told both stay open (not item D's).
- The dice are in the record: `dice_advanced`, `dice_start`, and `rn` on each player phase's
  `progress` trace line.
- The frozen suite was NOT run, on purpose: it plays only attempt 1, which was frame-identical
  to main's in runs `call1c` and `call1d`.
- With different dice, vanilla Ch8 (campaigns 4001 and 4004, three attempts each) still has
  no clean clear: 5 won and 1 lost, none taking the chests.

**PR #603 (item C, ADR 0403) is merged** (Nicolas: "merge", 2026-11-12), no open PR of this work.
- CI green on its head, `/code-review` (high) and one scoped re-review applied,
  `suite --held-out` PROMOTED with 0 regressions.
- What it does: a progress record per player phase (a kill made in the player phase, a Visit,
  a Talk, a chest, a door or wall opened, the Seize, or a new low in turns for the objective's
  nearest unit or an open ledger goal's best taker); a ledger goal nobody nears over three
  WAITING player phases has a `stalled` row that no longer holds the win; sixteen player
  phases in a row with no progress end the attempt `stuck` (N = 16: Nicolas left the number to
  Fable); the Seize is always judged when the game offers it.
- Evidence (the PR body has the tables): vanilla Ch8, 24 attempts, went from 13 won and 10
  stuck to 20 won and 3 stuck, with half the emulated frames; no offered Seize is skipped
  without a reason. The frozen suite was not refrozen.
- **Nicolas has not confirmed one narrowing:** call 3 said "three phases"; the rule counts only
  waiting phases (no event, nobody nearer to anything), because counting every phase cost
  vanilla Ch4 seed 1001 its clean clear in the first suite run. He was told; no answer yet.

**What item C does NOT fix: no vanilla Ch8 attempt is a clean clear** (0 of 24, four runs).
- Every win misses the chests at (1,3) and (2,3), behind the door at (1,5): `never_offered`
  to any unit, or `stalled`. The door opens to the thief's Lockpick or to the Door Key the
  armor knight at (20,10) drops; no Chest Key is on the map (decomp, read by a subagent; lines
  in #510 comment 6828202335). Read the door first.
- 12 of the 13 wins that were already wins lose a unit, most often charId 9 late (turn 17 to
  23) on a plan over the cap, and charId 10 on turn 10 or 11.
- Three attempts still end `stuck` with the boss alive (campaign 4001 attempts 7 and 10,
  campaign 4004 attempt 2): no plan that kills the boss is under the cap.

**Next steps, in order.**
1. The phase-start AI setup in judged phases (finding 6), its own PR; prove it on single runs
   (`--only`, `PT_LEAKGUARD=1`), no suite; test the end-of-phase looting read against it.
2. Ask Nicolas about the seizer's progress weight (below), then size item E on the shared
   field, not on per-unit marches. Item F's test as the plan wrote it.

**Three calls waiting for Nicolas.**
- Put one vanilla Ch8 start in the frozen suite, so a change to the wait rules needs one run,
  not two. Recommended. It changes what the suite measures.
- Fold the `idle_3` stall event into the new definition of progress (it still counts the
  lord's moves). Recommended, as its own PR: it changes what the suite's stall count means.
- The narrowing of call 3 above.

**Found while running, not looked into.**
- The suite's promotion check does not block a lost clean clear: the Ch4 village was found only
  by comparing `acts_hash` and `missed_rewards` with main's kept run of the same seed.
- A replay of a trace kept from before #603 can differ from its original under the new rules
  and then reports `matched = false` (read from the replay code by a subagent, not run).
- The five "dies, and lived when frozen" signals in the suite (`ours-ch02/1001`, `ours-ch03/1001`
  twice, `vanilla-ch5/1002` twice) are the same games as on main (`acts_hash` equal), not #603's.

**Not looked into.**
- The replay of campaign 4006's Ch9 start on #601 plays the same acts as run `fwd1`'s (four
  attempts compared act for act) but its frame counts differ a little (505261 against 505263;
  2354316 against 2353490). The suite's frames are identical.
- `tools/test_verdict_diff.py` failed twice on a clean local `main` (it lists the `tools`
  folder as an unlisted input) and passed on a later run; CI on main is green.

**Run `fwd1` (2026-11-11), for reference.** The eight vanilla campaigns all clear Ch6 and none
gets past chapter index 10: Ch7 (index 8) stops 4005 and 4010 (the lord dies on turn 4), Ch8
(index 9) stops 4001, 4004, 4007, 4009 (and 4002, whose "crash" was the lord's player-phase
death #601 now records as `lost`), Ch9 (index 10) stops 4006 (recruit and village missed).
Older scout walls still stand: `scout-ch13` loses 108 of 161, `scout-ch14` ends `stuck` on
turn 19, Ch5x (4003) stalls on turn 33.

**Key files:** `tools/playtest/sight.lua` (`s.look`, `s.walkers`, `s.reveals`, `s.after`,
`s.staged`), `tools/playtest/planner.lua` (the look block after "The look, in shadow";
`opts.unjudged`; `M.joinTurn`), `tools/playtest/bot.lua` (`M.explain`),
`tools/playtest/montecarlo.py` (`look_table`, `resume`, `story --why`), `tools/playtest/botrun.lua`
(`readNearest`, `closePhase`, `M.QUIET_BOUND`, `M.GOAL_QUIET`), `tools/playtest/goals.lua`
(`M.ledger`'s `stalled` rows), tests in
`test_bot.lua`, `test_sight.lua`, `test_montecarlo.py`. A Ch6 retry pair:
`montecarlo.py resume --game vanilla --tag <new> --campaigns cs-s4001 --chapter 7 --last 7`
(`--attempts N` caps it); `montecarlo.py look <trace dirs>` reads it.

- **Lessons:**
  - A plan kept in a trace's `considered` has its `rank` and `acts`: "was the plan judged, and
    why was it refused" is a read of the trace (`kind`, `rejected`, `rank.max_die`), no run.
  - The judge plays `sight.enemyPhase` on every plan it is not told to skip: when a plan's
    act ends the chapter, check the phase is not charged to it.
  - Stopping a run worked this session: `pkill -f "montecarlo.py suite"`, then `run.sh` and
    `mgba-headless`; a stopped suite leaves part of an instrument's runs in `runs.jsonl`.
  - Three runs at once (the suite and two `resume`s, 10 emulators) gave the same games as
    alone (`acts_hash` equal); they take longer, not timed.
  - The game's dice at a phase start are in the trace (`rn` on `progress` lines): "same dice?"
    and "how many draws did a turn take" are a read, not a run (count NextRN steps between two
    phases' words).
  - A harness change has no unit test: after one, replay a kept attempt and compare frames
    (`resume --campaigns fwd1-cs-s4001 --chapter 9 --last 9 --attempts 2`, about 10 minutes).
  - The frozen suite plays only attempt 1 (`chapter_tasks`): a change that only touches
    attempt 2 on cannot move it.
  - Start a `resume` and the suite at the same time: each works in its own `/tmp` folders and
    the suite's budget is counted in calls, not seconds (done once on 2026-11-12, no run without
    a game result). On a bot change run the suite FIRST: it is the shorter one (22 to 37
    minutes against 46 or more for the Ch8 set) and it caught what the Ch8 runs could not.
  - After a suite run, compare each tuning run's `acts_hash` and `missed_rewards` with main's
    kept run of that seed (`references/sim/<game>/<rom>/runs.jsonl`, the same `campaign`,
    `chapter`, `seed`, the older `instrument`): PROMOTED does not mean no clean clear was lost.
  - A subagent's test can pass on a hand-written row the real code never produces (#603: a
    ledger row with `unitId`): have the re-review check each fake's shape against its producer.
  - The Ch8 `resume` set is `--campaigns fwd1-cs-s4001,fwd1-cs-s4004 --chapter 9 --last 9`;
    its four kept runs are tags `fwd1c` to `fwd1c4` in `resume-runs.jsonl`.
  - A campaign's resumable start lives under the campaign that reached it: Ch8 and Ch9 starts
    are `fwd1-cs-s<seed>`, not `cs-s<seed>` (`resume` refuses and lists the indexes it has).
  - While a `resume` runs, a worker's live output is `/tmp/playtest-campaign@pool-*/`
    (`playtest.log`, and `mgba-stdout.log` for the BOTRUN lines); `workers/*.log` is written
    at the end. `resume` has no attempts cap on main: to read only the picks, stop it and kill
    `run.sh` and `mgba-headless`.
  - The chapter's talks (`Sight.talks`) are not its recruits: vanilla Ch8's six are
    conversations with player units or units who arrive on our side.
  - A worker log is megabytes of JSON lines: `grep` it, never `sed -n` a range of it.
  - The team pick's reasons are only in `references/sim/<game>/<rom>/workers/*.log`
    (`campaign: team`), not in the records or traces.
  - A trace keeps 5 to 7 plans a decision and no per-act offers: "was it offered" needs an
    instrumented run, not a read.
  - A record's `wall_s` is the campaign's; an attempt's is `run_s`. Equal `frames` on two
    attempts of one start means an exact replay.
  - **A probe's Lua table with both string keys and [1..n] is written as a JSON array**, the
    string keys lost: keep a probe's lists under a named key.
  - The beam's score gives a march no credit for ground gained: anything that picks "the
    beam's best" without the rank holds where the bot marches.
  - The look's enemy phase leaves red the active faction (`aiOrder`); set `PLAY_FACTION` back
    to blue before reading the board as our phase (bmidoten.c:780).
  - A function or constant board.lua adds must go in `Board.bind` too.
  - `sight.staged` isolates `seen`, `s.cache`, answer()'s village race and closings()' replays.
  - Prose check: "one of our units", never "one of ours"; "our units", never "ours".
  - In the turn between, a unit the plan holds has NO act in `st.acts`: "units still to act"
    is `ctx.actors` minus the acted, never "acts left".
  - Check a shadow step's result against what would refute it before building the next step.
  - A campaign builds a fresh bot for each attempt (`campaignApi`'s `api.play`): a switch set
    on the campaign's api never reaches botrun. Check a new switch's mark in the run's record.
  - A stopped `montecarlo.py` leaves its `run.sh` and `mgba-headless` workers running: kill
    those too, and check with `pgrep -fl mgba`.
  - Stopping a run with `pkill` is refused by the permission check in auto mode: before a
    long run, be sure the commit is the one to measure (review first, then the suite).
  - A commit's pre-commit takes over two minutes: run `git commit` in the background.
  - A playtest run reads the working tree's Lua: never edit Lua or switch branches while one
    runs. HANDOFF goes to main by plumbing (the branch's pre-commit refuses it).
- **From PR B (#599, merged), still open:** vanilla `scout-ch14` ends `stuck` on turn 19 in all
  16 kept runs (no deaths), untracked; Ch5x (4003) stalls on turn 33; Ch8's chests at (1,3)
  and (2,3) are never reached. None are deaths, so W1-W3 do not cover them (the design's "Not
  covered"). The campaigns' saved starts are untouched (`resume` copies them first).

## Where things stand

- **The parity model is being rebuilt: epic #510.** ch00-ch07 are unlocked and re-lock at its end
  (ADR 0354). Never widen an `accepted_residual` to get green.
- **#510 step 9, the difficulty instrument** (a bot plays the real ROM, both games; the plan is
  #510 comment 6563384310, ticked in place, spec 6563384018):
  - **Merged:** PR-A #558 (frozen suite), PR-B #559 (graded records), PR-C #560 (risk caps),
    PR-D #564 (goal ledger, no stalls), PR-E #568 (lookahead, retry memory), #570's fix #571
    (lookahead budget 128 an attempt, so the boss fight is no longer judged one phase deep), and
    PR-F #576 (a failure label needs a replayed witness: `montecarlo.py replay` / `audit`, ADR 0392).
    PR-F's answer to ours-ch03 seed 1002 unit 3: no evidence the hold caused it; every judged plan
    was over the cap, and the best alternative traded the death to unit 5. **PR-G #581** (ADR
    0395): the instrument is frozen in `tools/playtest/suite-frozen.json`. `suite` judges the
    tuning runs on it; `--held-out` adds the held-out seeds as counts plus the promotion result;
    `--freeze` refreezes; `--kept` re-judges kept runs. The fog start (vanilla Ch6) was added and
    three failing-decision snapshots load back to their boards in a fresh emulator. The
    surprise-replan rule stayed strict (no bot change). **PR-H #582** (ADR 0385, "Built
    (PR-H)"): `paired_verdict` now judges any protected death on attempt 1 with exact bounds
    (N = 24 in `instrument.cells`, ±10 margin); chapter cells, `pilot` and `cell`. The pilot
    (Manchego Stars ch03 vs vanilla Ch3, Nicolas's pick): Manchego Stars lost someone on 18 of
    50 first attempts, the twin on 0 of 50. Every death was a careful-style run; 6 of 50 (12%) were blind-spot
    deaths, over PR-I's 10% validity bar; and a seed only draws the style, so 50 seeds made 30
    distinct plays an arm. **PR-I #593** (ADR 0385, "Built (PR-I)") weighs both: a cell is
    NOT READABLE when a validity invariant fails.
  - **PR-E's open items are decided** (Nicolas, 2026-11-04; ADR 0389): the hold stays, the
    budget was raised instead of narrowing the boss trigger, the breach's "first crossing" is
    not built.
  - **Frozen suite** (instrument `ce1e3adb8c57+v2`, PR #587; same play as #585's): 14 starts, 56 runs, 25 min
    wall on 8 workers, 2,490,781 `AiDecideMain` calls (SC-003's baseline; the jump from 567,629
    is T100b's counter branches, accepted by Nicolas); every run has a game result; 4 of 28
    held-out runs lost. A bot change makes a new instrument: run `suite --held-out` and read its
    promotion line before trusting it.
- **On hold** (label `on-hold`, the hold comment says what reopens each): #565 (chipping a step
  back), #569 (placing a claim's wave in the lookahead).
- **Merged 2026-11-08:** #583 (ADR 0396: a bot decision is an ordering of the game's outcomes;
  only the game forbids), on Nicolas's "merge".
- **Merged 2026-11-07 after review, every finding fixed:**
  - **#578** (closed #577, ADR 0393): agent teams only for a named reason;
    `.claude/settings.json` holds the subagent prompt cache for an hour
    (`subagentPromptCacheTtl`, documented in Claude Code's settings reference).
  - **#580** (closed #579, ADR 0394): the pre-commit hook runs only the unit tests a staged
    path can reach. `run_tests.ReadRecorder` (audit hook) records each test's reads under
    `build/test-reads/`; a record whose reads moved since (mtime, size), a failing test, or an
    opaque one (a process it cannot see into) always runs. `test_difficulty.py` is dealt
    across three shards. A HANDOFF-only commit runs 22 of 130 test files. `make test`,
    `make check` and CI still run all of them. If the hook ever lets a broken test through,
    suspect a read the recorder does not see, and look at ADR 0394 first.
- **#574 merged (PR #575, ADR 0391):** a passing tagged run's `/tmp/playtest-<scenario>@<tag>`
  is deleted once its records are written; failing ones are kept (marked `FAILED`, newest 20);
  the per-run ROM is an APFS clone. The matrix drops a green verdict run's `/tmp` dir once the
  verdict cache holds it. If `/tmp` fills again, look there first.

## Next

0. **#510 PR A, first attempts**: merged (PR #598, ADR 0400).
1. **#510 PR B merged (#599).** **PR #600** (the boss goal, above) is open; **the look
   (W1-W3: comment 6786548233) is parked**. The bot plays vanilla forward first (above). Then tries to the first
   clean clear (its method goes to Nicolas as an ADR 0385 amendment first), **PR C** (a cell's
   dice, expected losses; small, no suite run) before any cell verdict, **#510 step 10** after.
   Still owed from PR-I:
   - **The pilot is ch02, not ch03**: no Manchego Stars campaign reaches ch03 (every one stops at
     ch02 on the chwinga finding), so `pilot --chapter 3` is refused. ch02 vs vanilla Ch2: every
     validity check holds; Manchego Stars lost someone 10 of 50, the twin 3 of 50; 0.63 CPU-h.
     `build/report-9d0b15b542e2-v2.md` predates #594 (it still prints the canary and human
     lines): regenerate it with `montecarlo.py report --post`, and **post it to #510 only on
     Nicolas's go-ahead** (T107). Clean clears in that pilot: Manchego Stars 0 of 50 (two chwinga die and
     the village at (12,3) is closed in every play), vanilla 35 of 50.
   - **Bot hash drift**: main's bot hash is `9d0b15b542e2`, the frozen suite's `ce1e3adb8c57`;
     #589's comment-only edits to the Lua moved it. Play is unchanged; a `suite --held-out`
     would refreeze it under the new hash.
2. **Chapter findings the bot made are owned by #510 step 10** (ch02's green chwinga, ch03's
   boss: bullets in the issue body; evidence in comment 6752603255 and on #547). Stop chasing
   them in the bot.
3. **#592** (found by #591): the ROM names ch03's grell boss (0xBF) and Icewind Brute (0xB6)
   "Monster"; the build writes no "Grell" text. Not checked in the emulator.
4. **Names in a story:** `montecarlo.py story`/`audit` read them from the build tree and print a
   note when the run played another ROM; build that ROM to read its names.
5. **Nicolas's stance (2026-11-09): stop chasing single deaths.** Judge a bot change by rates (the
   held-out counts, the pilot's Manchego Stars-vs-twin numbers), crashes, stalls and cost.
   **Decided:** a tuning-seed death flip is a signal, not a promotion blocker (T107a on the plan
   comment, built in PR-I with ADR 0395's amendment). Still to log on #510 as open: the over-cap
   order question (game over strictly first).
6. **Shelved, local:** `feat/510-t100b-counter-outcomes` (the reseat; its 162aa67c,
   `considered[].dies`, is worth porting), `feat/510-t100a-r`, `feat/510-lookahead-between-turn`
   (honest turn-between: right numbers, 4.6x cost), `park/510-t100a-pullback`.
7. Tell Nicolas where step 9 stands in plain words at the start of a session.

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
