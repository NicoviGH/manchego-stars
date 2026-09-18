# Handoff - Manchego Stars live state

`HANDOFF.md` is live state only: where the tree is, what is in flight, what is owed, what to do
next. **Settled decisions live in `docs/decisions.md`** — if a thing is decided, it belongs there
and gets deleted from here. Operating rules live in `CLAUDE.md`/`AGENTS.md`; scope and backlog
live in GitHub issues. Before a context rollover, warn Nicolas, refresh this file, and start a
fresh instance — don't rely on auto-compaction.

Refreshed 2026-09-18 (Claude), after #402/#404/#405/#406 landed. Deep-cleaned 2026-08-20 at Nicolas's
instruction: anything already recorded in `docs/decisions.md`, `CLAUDE.md` or a GitHub issue was
deleted from here rather than restated. Check that a thing has a home before writing it here.

## In flight

**Nothing. No open PRs, no branches.**

**Nicolas's 2026-09-18 instruction is SPENT.** *"the fresh instance will pick up the issues you
filed and proposal 3"* — #367's proposal 3 (#402), #393 (#404) and #396 (#405) are all merged,
and #398 closed before them. ADRs 0295 and 0296 carry the two that needed one; nothing below
restates them.

⚠️ **Three things a fresh session needs before writing anything near this machinery.** All
three were review findings on those PRs, and all three will recur:

- **Our own scenes are named `MS_*`, and a vanilla-spelled symbol filter walks straight past
  them.** The first cut of #401's reachability walk reported ch05 reaching 26 scripts; it
  reaches **40**. #337's first cut made the identical mistake at the write hook. Any new code
  that matches `EventScr_` must ask whether it also means `MS_`.
- **A guard that claims to MEASURE something must be watched failing.** #405's camera-bounds
  check read a JSON key the map layouts do not carry, so it returned "nothing out of bounds"
  without ever finding a map, and its test passed vacuously. Same shape as #404's, where a
  dead-vocabulary sweep swapped characters for pixels and kept four conclusions the retired
  rule had produced. ADR 0296 is the long form.
- **`make chapter CH=ch06` is still the state of ch06**, and it is HOSTED, not FINISHED: 3
  declared scenes with no script, 8 free message ids in `0x9F6-0x9FF`, nerra with no portrait,
  map sprite or battle anim.

## Next up

| | work | effort | what it is |
|---|---|---|---|
| 1 | **#26 — ch06's own body** | L | The dialogue pass is no longer gated (#337 landed), and ch06's fuse is answered. Read `make chapter CH=ch06` for what is declared-but-unbuilt rather than any list written here. ⚠️ **Tali and the boat crews have no voice** — that blocker is Nicolas's, below — but the reskins, the boarding pass and nerra's art need none of it and can all proceed first. |
| 2 | **#335** | M | The AI audit opened 2026-08-29: #48 measures STATS, so behavioural drift is invisible to every gate, and ch00–ch06 are biased toward aggression. It carries its own evidence and proposes the guard (an `ai_divergence:` allowlist, modelled on `terrain_divergence`). |
| 3 | **#135** | S | Real v0.1.0 playtester feedback on art consistency and difficulty, **never triaged** — the only open item that is player-facing. |

**#389's remainder** stays open and unscheduled: decompose `build_campaign.py` cluster by
cluster, each move wrapped in `injection_fingerprint`, clustering by **dependency and not by
banner** (ADR 0287). ch06 is extracted LAST, after it ships.

⚠️ **`tools/injection_fingerprint.py` is the tool to reach for on ANY mechanical change.**
#405 used it again to prove a new build-time guard writes nothing (975 files, ~70s): `--write
before.json`, change, `--check before.json`. It is what turns "this should be equivalent" into
a measurement.

**Where the party's LEVEL comes from, now that it is derived:** `python3 tools/exp_curve.py`
(and `--write` regenerates the block in `docs/fe8-pacing-reference.md`). Read that rather than
any number written down here — the same rule `make chapter` already earns.

## Owed by NICOLAS, not by the next session

- **#367's proposal 4** — lock ch03–ch06, or accept the gate is decorative for them. The rest
  of #367 is answered (its 2026-09-04 comment, superseded on ch02 by the 2026-09-05 one, and
  proposal 3 by #402). ⚠️ Not the mechanical yes it looks like: the same investigation finds
  the parity ratio converging on a tautology, and ch06 reads a perfect x1.00 because it
  reproduces 100% of FE8 Ch6's force — a checksum on the donor pipeline, not a measurement.
  Locking ch06 would gate it on a number #367 says means nothing there. Ask; do not infer.
- **#403's REMAINDER.** The issue as filed was wrong on both halves and is corrected on the
  issue itself (#406): sahnar joins at **L5**, placed by ch05's own roster at Joshua's level,
  and vanilla does not scale its recruits either — Natasha joins Ch5 at L1 and Seth is a L1
  Paladin. What is left is one narrow question, and it is yours: **lupin and trex inherit a
  mid-game donor's personal line (Kyle L6, Colm L2) while declaring level 1**, so those lines
  run HOT, not cold. Same shape ADR 0042 ruled on once, when Knoll's L9 bases were too hot for
  the shamans and the fix was a different BASE donor rather than a different level.
- **The boat crews have no voice.** No file in `campaigns/rime-of-the-frostmaiden/lore/` names
  Tali or either crew, and Tali carries ch06's plot-critical hint.

## PARKED — nothing. ch06's fuse is answered and fixed

**ch06's east pursuer could not reach its hull at all**, which is why its declared fuse of 7
described a unit that never arrived. `merfolk-thrower` at (14,9) was corked by two of its own
allies; both were nudged off the corridor (#370, Nicolas's call: move the line, not the
thrower) and it now reaches `(15,12)` on turn 2 for a forecast sink around turn 9. Both hulls
have an engaging pursuer. `tools/rescue_forecast.py ch06` prints the current numbers -- read
that rather than any figure written down here.

⚠️ **An earlier HANDOFF claimed the two hulls differ 3x in melee throughput (east 4 cells/1
door, west 8/3). That was wrong** -- it came from measuring the west hull at a coordinate that
is not its tile. Both hulls have exactly ONE melee door, as their YAML always declared. The
real asymmetry was reachability, not geometry.

## Map sprites — read before any art session

All of it is in `docs/decisions.md` → **"A map sprite is 32x32 or it is nothing"**: the hard engine
ceiling, why size reads as FILL, why geometry is derived from the donor and never from sheet pixels,
why a decomp sheet's palette is a meaningless leftover, what `footprint:` actually means, and the
WALK-vs-GLIDE split that decides whether PixelLab is worth paying for. Do not restate it here.

## Recently landed — do not redo

**#405 (2026-09-18) — the ROMChapterData census (#396).** Every one of `chapter_settings.json`'s
98 leaf fields is WRITTEN, owned by a named pass, or declared-inherited with a reason that cites
its engine reader — so the five fields found one at a time (goal text ids #207, battle grounds
#289, difficulty #303, `.traps` #302, fog #365) have no sixth to be found that way. Runs last in
the injection sequence, like #313's. ⚠️ Two things it added that a later session will meet:
ownership is **chapter-aware** (the prologue calls none of `_retarget_host_chapter`, so it has
its own rulings), and `intro_camera_out_of_bounds()` is the one ruling that is a measurement —
a hosted chapter inherits its intro camera tile from its host SLOT while its map is a DONOR's
geometry, and nothing else compares those two.

**#406 (2026-09-18) — a recruit starts at the level its CHAPTER places it at (#403).** The
join level is read from the placing entry across every roster key (`PLACED_ROSTER_KEYS` — GREEN
is the default recruit flavour, so the enemy keys alone are not the roster), and falls back to
the unit YAML only for a recruit nothing places. sahnar enters ch07 at L5, not L2. ⚠️ Two
review findings worth carrying: **a generated block cannot hold a hand-written number** — the
freshness test compares the doc against the same renderer, so it is structurally blind to one —
and the band's recruit column is a MINIMUM, now named `lowest`, because "newest" and "lowest"
stopped being the same unit the moment a recruit could join above L1.

**#404 (2026-09-18) — the chapter YAML joined the drift scan (#393).** ADR 0296 carries the
lesson and is deliberately not restated: a `DEAD_CONCEPTS` pattern is keyed on the UNIT, not on
the sentence that happened to survive. The issue measured 8 hits; there were **21**, five of them
in `build_campaign.py`, which had been scanned all along. Also landed: `DEAD_CONCEPT_CITATIONS`,
so citing the record that retired a concept stops being flagged as restating it.

**#402 (2026-09-18) — the party-level band is DERIVED (#367 proposal 3).** ADR 0295 carries it.
`tools/exp_curve.py` transcribes FE8's four exp functions and runs them over `difficulty.py`'s
roster readers; the band is generated into `docs/fe8-pacing-reference.md` and held fresh by
`tools/test_exp_curve.py`, which also asserts every chapter within ±12% of its twin — **the only
quantity in this repo that integrates across chapters.** ⚠️ **ch07 is where that alarm will
fire**: it is planned against FE8 Ch6, which ch06 already banked. Also found: `CA_BOSS` is a
question about the SLOT's attributes and `ENEMY_BASE_SLOT` is the stat table, so
`build_campaign.ENEMY_CHARACTER_SLOT` now answers the attribute one.

**#401 (2026-09-18) — #398's audit, and the guard that keeps its answer true.** ADR 0294
carries it and is deliberately not restated. ⚠️ **Two review findings a fresh session should
know before writing any graph-walking guard**: our own scenes are `MS_*`, so a vanilla-spelled
symbol filter silently walks past half the graph (ch05: 26 reported, 40 real); and a walk must
read its edges from CODE with comments stripped, or a sentence naming a retired scene stops the
build. Also: a caller that LOADs the actor is REPORTED on the finding, never subtracted — "some
caller loads it" is not "every path does".

**#372 / #374 / #373 (2026-09-16) — the three follow-ups off #371, all merged.** Three ADRs in
`docs/decisions.md` carry them and are deliberately not restated: *"A check that could not RUN is
not a check that passed"*, *"The tileset's one home had three more callers, and they were the ones
writing TILES"*, and *"Three routes to one sidecar, and the fix is that they must AGREE"*.
⚠️ **Two things a fresh session should know before writing a new guard**, both from the reviews:
a `check_*` is now registered in a module-level `CHECKS` tuple that `check_every_gate_is_registered`
polices, so a per-check "is it registered" test is no longer worth writing; and **a guard that
imports `build_campaign` or `map_placement_preview` cannot run on the CI `checks` job** — pyyaml
only, no submodule — which is where `tools/check.py` actually runs. Read from source, like
`_injection_call_sequence` and `map_donor` do.

**#369 / #370 / #371 (2026-09-15) — the rescue-fuse forecast, ch06's east pursuer, and the
tileset's one home.** Three ADRs in `docs/decisions.md` carry all of it and are deliberately
not restated: *"A rescue-fuse FORECAST is the reusable question, and it is not a danger grid"*,
*"A map's tileset has one home, and it is the one the BUILD reads"*, plus the ch06 placement
fix on #370. One-line version: `tools/rescue_forecast.py` answers *which enemy can get a firing
position on a protected tile, when, for how much, so when does it die* -- reusing `foot_reach`,
`difficulty`'s stat resolution and `fe_combat`, never a second combat model. The full danger
GRID was explicitly cut from scope (Nicolas, 2026-09-05); the narrow question is what chapters
actually ask.

⚠️ **The lesson that outlives these: a gate must ASK the reader, never re-derive its
preconditions.** `check.py` guessed twice at what `load_map` needs -- by exception type, then by
testing for the sidecar -- and both drifted from what it actually opens. `MapNotCompiled` now
lives with the reader. Five review rounds on #371, and after the first, every finding was in
code written to make a `check.py` guard defensive -- which is why #372 landed first.

**#368 (2026-09-05, MERGED `7786bc5`) — mirror%, and ch02 was never counting its own wave.**
One ADR in `docs/decisions.md` carries it: *"A parity ratio does not say how much of the twin it
COPIED, so mirror% says it"*. Every ratio now prints the share of the twin's force the chapter
reproduces exactly. ⚠️ **It found a shipped bug on a `balance_locked` chapter on day one**: our
side read only `enemy_units` while the twin's curated arrays fold their reinforcement waves in,
so ch02 compared 7 bodies against 9 (both at L1, its declared `levels: [2, 3]` unread).
**ch02 is x1.00/x1.00 and 100% mirror, not x0.81/x0.79 and 78%** — a second copy chapter, so
ch06 is not the first. Verdict never changed, which is how it survived four chapters.
`ENEMY_ROSTER_KEYS` / `chapter_roster_entries` / `entry_body_levels` now live on
`build_campaign`'s desk and nine readers use them; four were silent gate holes.

**#366 (2026-09-04, MERGED `eaedac5`) — the AI vector has two halves, and we were reading
one.** Five ADRs in `docs/decisions.md` carry it. The first three: *"AI_B is the APPROACH and AI_A is the ACTION"*,
*"A reach number measured on an EMPTY MAP is a claim about terrain, not about the chapter"*, and
*"A rescue clock is a HIT RATE, so a scenario MEASURES it and never asserts it"*. The one-line
version: `never-move` names only the approach byte, so 48 of the 51 units our reports called static
will step out and strike — which is how four merfolk mobbed a boat the chapter had nowhere near
them. `make chapter` now prints both halves and a three-way shape, reach is measured with the
enemy line standing on it, and two new guards (`check_rescue_targets`, `check_chapter_lua_facts`)
hold both.

The review added two more ADRs, both gates that had been passing for the wrong reason:
*"Two do-not-attack lists are not one mechanism, and they have different invariants"* (AI_A_07's
list names ch05's escort, so it never licensed anything at a ch06 hull -- and AI_A_08 had no
client sweep at all) and *"A reachability gate that skips reinforcements is grading the opening
board"* (ch06's three Difficult-only turn-4 crab riders reach the west hull and were invisible;
they now carry their siblings' `ai_override`, ACTION byte only). Also fixed: `BEHAVIOUR_COLOUR`
still keyed on the retired approach-family vocabulary, so every ch06 marker drew grey while the
legend advertised four colours -- **the placement picture was mis-stating behaviour, which is the
picture ch06's clock was designed on.**

**#364 (2026-09-04) — ch06 is hosted on slot 7, and the asset table hit its 8-bit CEILING.** Five
ADRs in `docs/decisions.md` carry all of it and are deliberately not restated here: *"The asset
table is addressed by a u8…"*, the fog one (which became #365, closed 2026-09-17), *"A
load-test that reads the roster before PREP settles is a diagnostic that LIES"*, *"A NAMED raw pid
must be exclusive; a GENERIC one need not be"*, and *"The parity model prices the YAML; only the
EMITTED ROWS are the ROM"*.

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
invariant is **a cutscene LOADs its actors**, and #337 landed the guard for it 2026-09-17
(ADR 0292 -- scoped to the PCs, because they are the only actors the chapter cannot
guarantee). And *"The FE-Repo is
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
  artifact. The two it surfaced (#335, #135) are now items 2 and 3 in the Next-up table.
- ⚠️ **Branch BEFORE editing, and check whether a file's "stale" content is already fixed on an
  unmerged branch.** 2026-08-28 cost a rework round: ch06's `parity_reference` read `FE8 Ch5` on
  `main`, so it got "fixed" there — while PR #331 had already corrected it on its branch. A whole
  session's work then had to be rebased off `main` and reconciled. `git branch --all --contains`
  and a look at open PRs answer this in seconds.
- **Environment: Nicolas is on his Mac. ROM builds, `verify_text` and mGBA playtests are LIVE.**
- **Primary checkout: `/Users/Yonick/Projects/manchego-stars`** (#267), which holds `main`. It is clean except
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
  time. **One task at a time = a plain BRANCH in this tree.** Flow: branch → PR →
  `/code-review` → squash-merge → delete the branch. A worktree buys build isolation between
  CONCURRENT workers (two ROM builds in one tree corrupt each other) — working serially it buys
  nothing and costs setup, so don't (Nicolas, 2026-09-02). `tools/worktree-setup.sh` is there for
  when work really is parallel.

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
- **A commit takes ~45 SECONDS** (it was 6-10 minutes until #380/#382 on 2026-09-17). The
  pre-commit hook still runs the full `tools/check.py` -- coverage is unchanged -- but the
  decomp reads are memoised and the test files run in parallel through `tools/run_tests.py`.
  Backgrounding a commit is no longer necessary. Still commit with a message FILE
  (`git commit -F <file>`), never a heredoc -- a heredoc's stdin has hung the hook. Killing a
  commit mid-hook is safe (nothing is written until it passes).
- **A SUBAGENT is not woken by its own background task.** One ended its turn waiting on a
  backgrounded `make check`, stalled, and on resume raced a commit the main session had already
  started -- two `git commit` processes on one repo. If you dispatch one, tell it to run long
  commands in the FOREGROUND and absorb the wall-clock.
