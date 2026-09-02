# Handoff - Manchego Stars live state

`HANDOFF.md` is live state only: where the tree is, what is in flight, what is owed, what to do
next. **Settled decisions live in `docs/decisions.md`** — if a thing is decided, it belongs there
and gets deleted from here. Operating rules live in `CLAUDE.md`/`AGENTS.md`; scope and backlog
live in GitHub issues. Before a context rollover, warn Nicolas, refresh this file, and start a
fresh instance — don't rely on auto-compaction.

Refreshed 2026-08-29 (Claude). Deep-cleaned 2026-08-20 at Nicolas's instruction: anything already
recorded in `docs/decisions.md`, `CLAUDE.md` or a GitHub issue was deleted from here rather than
restated. Check that a thing has a home before writing it here.

## In flight

**A five-PR stack, reviewed and fixed, waiting on ONE matrix run.** **Merge strictly in order**,
with `--merge` (not `--squash`), retargeting each child to `main` BEFORE deleting its parent branch
(`decisions.md` -> stacked PRs: deleting a base closes the PRs on it, and a closed PR cannot be
retargeted).

| order | PR | base | review |
|---|---|---|---|
| 1 | #339 ai: borrow every enemy's AI from its vanilla donor | `main` | fixed (7798a06) |
| 2 | #340 ch02: restore vanilla's decoy | #339 | clean |
| 3 | #341 ch02: point slot 3 at its own map-change layer | #340 | fixed (7cf289b) |
| 4 | #342 playtest: a scene is not a stall | #341 | fixed (dbbead6) |
| 5 | #343 docs + tooling; **closes #335** | #342 | fixed (6639431) |

All five were reviewed 2026-09-02 by a fresh reviewer per PR. **What each review found and what
was done about it is a comment on the PR itself** -- not restated here. Two were Critical: #341's
ordering guard was never registered in `check.py`'s gate and could not see ch03's wrapper, and
#342's s8 change had silently made 23 off-map guards vacuous. The stack was rebased in order and
force-pushed; every base is intact and MERGEABLE.

**#339 and #340 are ATOMIC with respect to CI.** #339 adds a gate arm that `balance_locked` ch02
cannot satisfy until #340 migrates it: `make difficulty-gate` exits 1 at #339 and 0 at #340.
Merging #339 alone leaves `main` red. Merge them back to back.

**What is owed before merging: one `SUITE=all` matrix run at the stack tip, `--jobs 1`.**
`make matrix SUITE=all` runs `matrix.py run --all`; per #345 a parallel run starves its own
scenarios and reports false failures, so serial or do not believe it. Dry-run says **50 scenarios
across 6 ROM configurations**, and `harness.lua` changed, so the verdict cache will not spare
much. It is the honest tier because #342's fix is in shared clear-bot helpers that every scenario
inherits -- no single chapter suite covers it. Everything else is verified static: full suite
green by the repo's own runner, `difficulty-gate` 0 at the tip, drift clean on every commit.

**#26 stays open**: the map and the roster are done, the chapter is not.

**The design board:** `https://claude.ai/code/artifact/6952f53d-0fde-4a0f-b07c-b8fc846d6f10`
**Asset board** (every aquatic asset in the FE-Repo, animated per weapon):
`https://claude.ai/code/artifact/d783c124-429c-4955-a575-0ae93b3cacd3`
**Issue #26 carries the checklist**, including a comment holding the two boarding scenes' decided
content. Read the issue for scope, the boards for reasoning.

## Owed, filed, not started

- **#344** -- factor AI behaviour into the difficulty metric (#335's stretch, split out). This is the
  metric that would have caught the drift #335 fixed: ch04 fielded 78% pursuers against a
  half-static twin and still measured x1.00.
- **#345** -- `SUITE=all` reports FALSE failures. Four long scenarios run concurrently and starve
  each other past their wall-clock deadlines (~15fps against a 240fps target). The verdict
  *conflation* is fixed in #342; the contention is not. Until it is, **re-run any `SUITE=all`
  failure with `--jobs 1` before believing it.**

## Next task

**Run the `SUITE=all` matrix at the stack tip (`--jobs 1`), then land the stack in order.** The
review and the fixes are done; that run is the only thing between the stack and `main`. Once #343
merges, **#335 closes itself** and the next task is **ch06 enemy POSITIONS -- bring Nicolas a
render first** (2-3 concept options, not a finished map).

Everything that decision answers to -- the measured map geometry, why neither vanilla source
transfers, the three jobs placement must serve, the donor rule that replaced `CH06_AI`, and the
build obligations `make chapter CH=ch06` cannot see -- is on **#26**, in two comments dated
2026-08-31. All of it lived HERE until then and should not have: it is true until it is done,
not live state, so it belongs on the issue.

## Map sprites — read before any art session

All of it is in `docs/decisions.md` → **"A map sprite is 32x32 or it is nothing"**: the hard engine
ceiling, why size reads as FILL, why geometry is derived from the donor and never from sheet pixels,
why a decomp sheet's palette is a meaningless leftover, what `footprint:` actually means, and the
WALK-vs-GLIDE split that decides whether PixelLab is worth paying for. Do not restate it here.

## Recently landed — do not redo

**#334 (2026-08-29) — ch06's roster, and Messie stops being a fight.** Two ADRs in
`docs/decisions.md` carry the whole reasoning: *"Messie is a cutscene, not a boss"* and *"The AI is
in the UnitDefs, so it is DERIVED"*. The one-line version: the merfolk are the enemy, Messie
arrives in the boss-death cutscene, the objective is plain `defeat_boss`, and the boss rides
`CHARACTER_NOVALA` via `ENEMY_BASE_SLOT` so she inherits his real line. Parity is **x1.00 threat /
x1.00 clear-load** against FE8 Ch6, role check clean.

⚠️ **The lesson that outlives ch06: #48 measures STATS, so behavioural drift is invisible to every
gate.** ch06's first draft measured x1.00 while fielding 13 pursuers against a twin that fields
two. An audit found ch00-ch05 have the same gap, biased toward aggression — **issue #335**, which
also proposes the guard (an `ai_divergence:` allowlist, modelled on `terrain_divergence`).

**#336 (2026-08-29) — two campaign-wide rules, both ADRs in `docs/decisions.md`.** *"Permadeath is
a combat rule, not a narrative one"*: the eight PCs appear in every cutscene alive or dead, because
the player picks their own lord and there is no always-present character to hand a dead PC's lines
to the way vanilla hands Artur's to Eirika — and these scenes record a campaign that happened. The
invariant is **a cutscene LOADs its actors** (guard proposed in **#337**). And *"The FE-Repo is
READ, not grepped"*: pull the git trees per directory and read the categories, because every asset
ch06 needed is named `Squidsmith` / `IronShell-Tiny General` / `[Spider-Variant] Cavalier Rider`
and no keyword sweep finds those.

**#331 (2026-08-28) — ch06's map is painted, compiled and committed.** Detail in `docs/decisions.md`
→ *"ch06 departs from its donor's terrain in 21 declared cells"* and *"The DONOR and the BAR are
different chapters"*.

### Earlier



DONE and merged. One line each, so a fresh session does not reopen one. **The detail is in the
named `docs/decisions.md` ADR or on the issue — deliberately not restated here.** Where no ADR is
named, the issue is the record.

**The #302 epic — playtest cost and chapter tooling. All merged:**

| | ADR in `docs/decisions.md` |
|---|---|
| #308 verdict scenarios run headless | *A verdict scenario needs no pixels, so it runs HEADLESS* |
| #309 a config switch is 25s, not 50s | *A build is 50 seconds, and 26 of them were the same battle anims every time* |
| #310 parallel dispatch + the `pkill` that sabotaged it | *A blanket `pkill` is a serial-world habit, and parallel dispatch turned it into a saboteur* |
| #311 `make scene` — a scene without a ROM | *A scene is readable without a ROM, and a press count is read off the BODY* |
| #312 `make chapter` — status is derived | *A chapter's status is DERIVED, and HANDOFF stops carrying it* |
| #313 the ChapterEventGroup census guard | *Every ChapterEventGroup field is WRITTEN or DECLARED-INHERITED* |
| #314 a chapter declares its own scenarios | *A scenario is DECLARED by the chapter it tests* |
| #327 the Lua local-slot ceiling, measured then frozen | *The headroom guard measured one file correctly BY ACCIDENT* + *A CHAPTER is not what was filling harness.lua* |
| #302 the merge gate is bounded | *The gate is the spine plus the last two chapters; depth lives in the chapter suite* |

**ch05 is complete** (#25 and children): dialogue all 17 scenes (#295), enemy reskins (#296), the
no-Lupin Talk arm (#297), all three ending arms filmed (#299), the Arena (#265/#268), the
village-raid race and save-all payout (#254), Ravisin end-to-end (#259, #261, #263, #286, #290-292),
per-chapter battle grounds (#289), the ch01/ch07 winter CGs (#256). Reskin board:
`https://claude.ai/code/artifact/6a05e1ff-8938-49ed-8927-631d0e4dc6bd`

**Also landed:** #298 dialogue wraps by PIXELS (ADR *We wrapped on-map talk at 29 CHARACTERS; the
engine measures PIXELS*) · #300/#301 `tools/callsites.py` — **use it before changing any signature,
and especially before changing what a parameter MEANS** · #303/#304 all three difficulty modes
(ADR *Vanilla ships three difficulty modes, so we ship three*) · #306 traps are declared, not
inherited · #329 a donor is derived, not labelled (ADR *A base-map LABEL is prose — the donor is
DERIVED*) · #330 the drift lint now scans `.github/` and `.claude/skills/`.

⚠️ **Not landed, and it was buried in this list as though it were:** the **encounter-choice fields**
(`playerUnits/enemyUnitsChoice{1,2,3}InEncounter`) are still inherited on ch03 and ch05 — six vanilla
skirmish rosters each, dormant only while we expose no world map. Owed on #302.

## Current state

- **Where a chapter stands is `make chapter CH=chNN`** (#312) — scenes declared vs written vs
  previewable, message-id headroom, art per named unit, which scenarios cover it and what each
  last said, and everything declared but unbuilt. `make chapter` with no `CH=` is all nine at a
  glance. **Do not write any of that into this file again**: it is derived on demand, so a
  generated answer cannot go stale and prose someone has to remember to update always does.
  Two things it says today that nobody had computed: **ch05's message block is FULL**
  (`0x9E4-0x9F5`, all 18 spent — the next ch05 scene costs a redesign, not an id), and **ch01
  declares five events and has written two.**
- **Backlog swept 2026-08-22** — do NOT re-survey it by issue title or checkbox. ch03 taught that
  an unchecked box records what someone intended, not what the repo contains: #23 read as "7 open
  items" while git history and the live YAML showed the work shipped long ago. Cross-reference the
  artifact. Closed in the sweep: #303, #23, #133, #244. Still open and each carrying its own fresh
  evidence: **#335** (the AI audit) and **#337** (the cutscene-actor guard), both opened
  2026-08-29, **#135** (real v0.1.0 playtester feedback on art consistency and difficulty, never
  triaged) and **#30** (`campaign.yaml`'s `chapters:` block omits the prologue and is off-by-one
  from ch04 on — nothing reads it, so it misleads rather than breaks). #30 is now cheap: since
  #312 there is one reader for the chapter YAML (`tools/campaign_chapters.py`), so that block
  can be derived from it rather than hand-kept.
- ⚠️ **Branch BEFORE editing, and check whether a file's "stale" content is already fixed on an
  unmerged branch.** 2026-08-28 cost a rework round: ch06's `parity_reference` read `FE8 Ch5` on
  `main`, so it got "fixed" there — while PR #331 had already corrected it on its branch. A whole
  session's work then had to be rebased off `main` and reconciled. `git branch --all --contains`
  and a look at open PRs answer this in seconds.
- **Environment: Nicolas is on his Mac. ROM builds, `verify_text` and mGBA playtests are LIVE.**
- **Checkout: `/Users/Yonick/Projects/manchego-stars`, the ONE tree** (#267). It is clean except
  for the intentionally dirty `fireemblem8u` submodule and the untracked `.agents/`,
  `map-review/` and `review/` — preserve those and **stage paths explicitly**. (`AGENTS.md` was
  untracked here until #343 commits it; it is no longer in the tree on `main`.)
- **Two sandbox false negatives on this Mac, neither a real failure.** `gh auth status` reports
  the saved token invalid because a restricted process cannot read the macOS Keychain — run `gh`
  with escalation rather than asking Nicolas to log in again. And an mGBA GUI crash with an AppKit
  registration abort happened BEFORE the ROM ran; escalated emulator runs are normal, so diagnose
  ROM state only once it actually boots.
- **Cross-agent continuity:** Nicolas uses Codex only between Claude sessions. Codex must leave an
  explicit HANDOFF entry naming what it changed, the branch/PR and commit state, verification
  actually run, and the exact next step. Short-lived feature branches in this checkout, one at a
  time — **no worktrees unless Nicolas says otherwise**.

## Before you touch anything

Everything below used to be spelled out here and is now in its real home. This list is the INDEX;
do not re-inline the content.

- **How to work here** (the matrix rule, the boundary rule, feature-flow, the tool table) →
  `CLAUDE.md`.
- **Why anything is the way it is** → `docs/decisions.md`, 55 dated entries. The ones most likely
  to bite an unfamiliar session: *"Playtest runs are the most expensive thing in this repo"*,
  *"A scenario written against the old design will FAIL ON SUCCESS"*, *"An artifact is not its
  inputs"*, *"A community map sprite is keyed on GREEN, not on index 0"*, *"The TESTCH bench is
  bounded by SMS VRAM"*, *"A battle anim carries FOUR palettes and the engine picks one"*.
- **What is left to build** → GitHub issues, #20–#28 per chapter; **#302** is the live epic.
- **Before a wide mechanical edit** → `tools/callsites.py`, then diff the OUTPUT. Three bugs
  shipped in one day from a regex sweep that all 546 tests passed through, and what caught them
  was rendering every message body under both versions and diffing (`decisions.md` → "We wrapped
  on-map talk at 29 CHARACTERS", §HOW THE ROLLOUT MUST BE GATED). Run that diff BEFORE the suite.
- **Which asset the FE-Repo has** → `docs/fe-repo-scouting.md`. ⚠️ Its table says where an anim
  LIVES, not what it does; open a candidate's mode folders before believing a gap.

Two live workflow facts that are not decisions and have nowhere better to sit:

- **After any ROM build, `make check` fails `test_difficulty` + `test_map_tileset` together.**
  That pair is the signature of reading the BUILT decomp tree. Fix, don't debug:
  `git -C fireemblem8u restore src/data/chapter_settings.json data/data_8B363C.s`.
- **`HANDOFF.md` is authored on `main` ONLY**, gated by `check.py check_handoff_only_on_main`. If
  the guard fires on a branch: `git checkout main -- HANDOFF.md`.
