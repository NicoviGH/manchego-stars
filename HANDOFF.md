# Handoff - Manchego Stars live state

`HANDOFF.md` is live state only: where the tree is, what is in flight, what is owed, what to do next.
**Settled decisions live in `docs/decisions.md`** — if a thing is decided, it belongs there and gets
deleted from here. Operating rules live in `CLAUDE.md`/`AGENTS.md`; scope and backlog live in GitHub
issues. Before a context rollover, warn Nicolas, refresh this file, and start a fresh instance —
don't rely on auto-compaction.

Refreshed 2026-08-06 (Opus). `main` = `5db7878`, level with `origin/main`.
**IN FLIGHT: THREE STACKED PRs, all built and verified, none merged. MERGE IN THIS ORDER:**

| order | PR | branch | delivers |
|---|---|---|---|
| 1 | **#237** | `feat/236-state-inspector` | the state inspector. Closes #236 + #232, gate 13/14 → **14/14** |
| 2 | **#239** | `feat/138-inject-chapter` | `hosted_chapters()` — the ch04 host-slot guard now covers ch05 |
| 3 | **#240** | `feat/238-controller-contract` | the ch01 spine on the controller contract (#238, first pass) |

Each is based on the one above it, so **merging out of order will produce a mess.** `main` itself is
clean, no stashes. Squash-merge 1 → 2 → 3, delete branches, then refresh this file.
**CI never ran on ANY of them — a GitHub Actions major outage (incident opened 15:22 UTC
2026-08-06), not these branches. Do not re-diagnose it; the evidence is already a comment on #237.**
Every run on `main`
failed the same way, including doc-only commits: `The job was not acquired by Runner of type hosted`.
Re-run with `gh run rerun 31125252344` once runners recover.
**Next: land all three, then ch05 (#25). Jump to NEXT SESSION.**

## Current state

- **Environment: Nicolas is on his Mac. ROM builds, `verify_text` and mGBA playtests are LIVE.**
  Verified on this tree 2026-08-06: all `tools/test_*.py`, 8 Lua harness suites, `make check` =
  `drift check: clean`, canonical + `TESTCH=1` + `CH04BOOT=1` all build green.
- **The live regression matrix is `make matrix` (#231, merged in #233).** One command builds each ROM
  configuration at most once and prints a verdict table. **`tools/playtest/matrix.yaml` is now the
  single source of what a scenario needs** — ROM flag, `PT_HOST_CHAPTER`, checkpoint, fps/deadline —
  and `check.py check_playtest_matrix` fails the build if a `harness.lua` scenario has no row.
- **Gate status: 14/14 — the first fully green gate** (verified live 2026-08-06 on #237, and
  again on #240 after the controller-contract migration). On `main` it is still 13/14 until #237
  lands; `ch01` is the difference. Local verification is a strict SUPERSET of what CI checks — `checks.yml` is a
  deliberate lightweight drift guard that never builds the ROM — so an Actions outage blocks the
  merge button, not the evidence.
- **Cross-agent continuity:** Nicolas uses Codex only between Claude sessions. Codex must leave an
  explicit HANDOFF entry naming what it changed, the active branch/PR and commit state, verification
  actually run, and the exact next step. Codex uses ordinary short-lived feature branches in this
  checkout, one at a time — **do not create worktrees unless Nicolas explicitly changes that.**
- **ch05 "The Elven Tomb" (#25) is the only chapter with work owed.** Dialogue is complete and merged
  (PR #196): 15 slots, all `status: locked`. Still owed: map + placement, text insertion →
  `verify_text`, `--ch05-boot` playtest, `enemy_class_reskins` + FE-Repo imports, Basil/Sahnar
  STAT_DONORs, and the five no-Lupin conditionals (they ride Stage 4's `variant_beat`, not a second
  mechanism). Hosting ch05 also retires ch04's `dev_placeholder_scene()` terminator.
- **ch01–ch04 are DONE and CLOSED.** ch04 shipped in #223; its one open thread was the placeholder
  terminator above, which is ch05's to retire.

## NEXT SESSION — the agreed order (Nicolas, 2026-08-06)

**Start from the GitHub issue, not from here.** These notes only add what the issue does not say.

### 1. Land the three stacked PRs, in order  ← START HERE

**#237 → #239 → #240.** All built and verified; only the merges are owed. Re-run CI
(`gh run rerun 31125252344`), or merge on the local evidence if Actions is still out — see the
header. None has had a `/code-review`; that is user-triggered (`/code-review ultra 237`).

**Do not re-verify them.** `make matrix` was run green (14/14) on #237 and again on #240, `make
test` and `make check` are clean on all three, and #239's canonical ROM is byte-identical to its
pre-change baseline `42cd82360be3c186c60f9366d57c7608d3d83548`.

Nicolas's standing question, answered with measurements so it is not re-litigated: **the new gates
cost ~1.5s on `make check` (23.6s total) and +4% on `make matrix` (5m34s → 5m49s, almost all of it
`ch01win` 28s → 40s because it now verifies instead of mashing A).** The real cost is not seconds —
it is that a new FE8 input state must be CLASSIFIED before a scenario can drive it. ch05 will
probably surface some. That work always existed; it used to be deferred into mystery failures.
**If the stall detector ever false-positives, `TUNE.stallFrames` is the dial — do not remove it.**

What it shipped, so the next instance can USE it instead of re-deriving it:

- **A failing scenario now dumps its own diagnosis.** `inspect_state.py` (lands in `tools/playtest/`
  with #237) has `render <log>` — the verdict, the rule that produced it, every rule rejected and
  why, and the live procs named by exact symbol — and `diff <a> <b>` for the first divergence
  between two runs. **Read that before rebuilding anything** — it is the whole point.
- A verdict flagged `*** UNCLASSIFIED WAIT ***` means FE8 is waiting on something with no name yet.
  The fix is always the same four edits: `gen_symbols.py` WANTED, `CALLBACK_NAMES`,
  `observeController`, a `classify` rule — then let the SCENARIO choose the answer.
- `harness.lua` has **exactly TWO free slots** against Lua's 200-local ceiling (measured: +2
  compiles, +3 does not). Hang new helpers off an existing table (`INSPECT`, `TUNE`) rather than
  adding a top-level `local` — crossing it stops the whole file loading and every scenario dies at
  once. `check_lua_chunks_load` now fails the build on it in 0s (arrives with #239).

### 2. #238 second pass — the rest of the blind-press verdict scenarios

#240 did `ch01win` and the shared ch01 route. **Still owed: `retreat`, `lordfloor`, `ch01lord`,
`recordsupply`, and three `LORD_CANDIDATES` blind menu-walks at `harness.lua` 3122/3164/3211.**
Scope from `matrix.yaml`'s `kind`, NEVER from the scenario name — `recordsupply` and
`recordunitlist` are `kind: verdict` despite the prefix, and `recordunitlist` is in the gate.

The acceptance test for this work is the bite test, not a green run: temporarily break a
classification and confirm the scenario now FAILS. #240 proved it on `ch01win` — the same sabotage
passed before the migration.

### 3. ch05's build work (#25) — with #222 re-scoped and settled

**#222 has been re-scoped from experience and approved (2026-08-06).** Workstream 3 is closed (its
DoD was already met by #220 — only 13% of a median scenario is UI-driving) and replaced by **#238**;
workstream 4 is consolidated into **#138**. The epic closes when #138 and #238 do.

**#138 no longer gates ch05, and that correction matters for planning.** The host-slot facts were
already module constants, and the guard that mattered shipped in #239. What remains of #138 is only
the `inject_chapter(descriptor)` refactor — and measured, that is worth much less than it sounds:
**of 2,209 LOC in `inject_ch01`–`ch04`, just 123 (6%) is the host skeleton a descriptor collapses**
(~30 lines per chapter, already helper calls). The other 94% is per-chapter rosters, event scripts
and scenes. Recommendation on the issue: close #138 after #239, or shrink it to the one real
cleanup — ch03's bespoke `_inject_ch03_tile_changes` should migrate onto ch04's generic
`_inject_tile_changes`. Byte-identical baseline for any such work:
`42cd82360be3c186c60f9366d57c7608d3d83548`.

ch05 also needs a `matrix.yaml` entry — `docs/adding-a-chapter.md` step 11 has the runbook, and
`check.py` enforces it.

Then: **#29** world map.

Parked, not scheduled: **#228** physical cartridges (after the ROM is done).

## Gotchas most likely to bite next (long form in `docs/decisions.md`)

- **Read decomp data through `git show HEAD:`, never the built tree** — our injections are build
  artifacts. Applies to lints too: a check that greps the working tree for something the build patches
  out passes vacuously.
- **Post-injection SMS ids and goal ids cannot be read from HEAD or the working tree** — run the
  injector and read the result.
- **A failing playtest may be the WRONG ROM** — a `CH04BOOT=1` build cannot reach ch02's map. Boot
  flags are per-chapter, and so is `PT_HOST_CHAPTER`. `run.sh` now refuses this in 0s off
  `.build-config.json`, and `matrix.yaml` supplies the host chapter — **so do not reach for
  `MX_SKIP_ROM_CHECK=1`**; it disables the guard and hands you a bogus failure (2026-08-06: cost a
  wasted run inside the session that built the guard).
- **`harness.lua` is one Lua chunk AT the 200-local ceiling** (not near it — #236 crossed it and the
  whole file stopped loading). Hang new helpers off an existing table (`INSPECT`, `TUNE`), never a
  new top-level `local`. A `loadfile` check must ASSERT; it returns `nil, err` rather than raising.
- **Do not re-run a scenario to re-test a hypothesis the evidence already killed.** A budget-bounded
  loop exits at the same frame no matter what is on screen, so an identical frame number proves
  nothing. Instrument for the answer instead — `inspect_state.py render` is now that instrument.
- **A loop cap must never be what decides failure.** #232's ch01 was misdiagnosed for three sessions
  because a 12000-step cap expired mid-scene and reported a timeout that named nothing. Size caps
  above any real scene (`TUNE.bootSteps`) and let `INSPECT.watch` fail the run with a snapshot.
- **A `transition` is not "nothing is happening"** — it is the classifier saying it has no name for
  this. Check the snapshot's `considered` list before believing a scene is idle.
- **`turn()` is not the signal that a turn's reinforcements exist** — wait for a UNIT from the wave.
- **An `AREA` fires when an action ENDS**, so "a unit is standing in the clearing" is not a verdict.
  Stop a march on the **outcome** (the moose exists); use position only as the after-the-fact diagnostic.
- **A render from frame PNGs proves the ART; only the ROM proves the TILING and the PALETTE.**
- **Comments inside a YAML folded scalar are CONTENT** — put them above the key.
- **`tools/setup-toolchain.sh` omits upstream's helper-tool build** — a fresh checkout also needs
  `fireemblem8u/build_tools.sh` (`scaninc`, `jsonproc`). Not patched in-repo.

## Working tree - do not lose or revert

- **Three live branches, stacked, all pushed and level with their remotes:**
  `feat/236-state-inspector` (#237) → `feat/138-inject-chapter` (#239) →
  `feat/238-controller-contract` (#240). No stashes. `main` is level with `origin/main`.
  Do not rebuild or re-verify them — see NEXT SESSION §1 for what was already run green.
- **Two more gitignored `gen_symbols.py` outputs** land next to `symbols.lua` once #237 is in:
  `procscr.lua` and `symbols.json`. Regenerated after every `make`; never commit them.
- **`.build-config.json` (repo root, gitignored) records which boot flags built the ROM in the tree.**
  `build_campaign.py` writes it; the playtest tools read it to refuse a wrong-ROM run. Deleting it is
  harmless — an unknown stamp just disables the guard.
- `fireemblem8u` is dirty from injected/generated build artifacts. **Never commit its submodule
  pointer.** Restore the injected decomp files before `check.py`/the pre-commit hook so it runs in
  ~22s instead of ~4min: `git -C fireemblem8u restore src/data/chapter_settings.json data/data_8B363C.s`.
- Untracked local/session files (`.agents/`, `AGENTS.md`, `skills-lock.json`, `map-review/`,
  `review/`) are intentionally not versioned; leave them alone. `map-review/` is the render scratch
  Nicolas opens in Preview — deliverable art goes to `docs/demo/` and is COMMITTED so he can view it
  on GitHub (GIF, not MP4). `tools/key_magenta.py` is **gitignored** (#178).
- **HANDOFF.md is authored on `main` ONLY** — gated by `check.py check_handoff_only_on_main`.
  A branch may leave it untouched or sync it to main's tip; it may not author its own. If the guard
  fires: `git checkout main -- HANDOFF.md` on the branch. Refresh HANDOFF on main *after* a merge.
- **If `.git/config` ever shows `core.bare=true` or a `t`/`t@t` identity, a git-shelling test escaped
  its fixture.** Repair: `git config --local core.bare false`, `user.name "Nicolas"`,
  `user.email "nicolas.vivas94@gmail.com"`.

## Quick commands

```sh
make difficulty CH=ch04                    # parity/difficulty read (all from HEAD)

# THE GATE, one command (#231): builds each ROM config at most once, ~4-6 min, verdict table
# + results.json in /tmp/playtest-matrix. 14/14 green on feat/236-state-inspector (13/14 on main
# until #237 lands -- ch01 is the difference).
make matrix                                # SUITE=gate -- must be green before a merge
make matrix SUITE=ch03                     # one CH03BOOT=1 build, every ch03 scenario
make matrix SUITE=ch04                     # one CH04BOOT=1 build, every ch04 scenario
make matrix SUITE=all                      # every non-manual verdict scenario (long)
tools/playtest/matrix.py list --suites     # what each suite contains
tools/playtest/matrix.py run --scenarios ch04moose,ch04snag   # an ad-hoc subset

# One scenario. It takes its ROM flag + PT_HOST_CHAPTER from matrix.yaml, so DO NOT hand-set
# PT_HOST_CHAPTER any more, and it refuses outright if the tree holds a ROM that cannot host it.
tools/playtest/run.sh ch04moose
tools/playtest/make_gif.py <scenario> <tag> --name <out> --fps 14   # frames -> docs/demo/<out>.gif

make CAMPAIGN=rime-of-the-frostmaiden fireemblem8.gba -j$(nproc)              # canonical
make CAMPAIGN=rime-of-the-frostmaiden CH04BOOT=1 fireemblem8.gba -j$(nproc)   # ch04 fast-boot
make CAMPAIGN=rime-of-the-frostmaiden TESTCH=1 fireemblem8.gba -j$(nproc)     # sandbox / anim bench
PT_CHAR=baxby tools/playtest/run.sh recordanim        # any cast member's banim; then make_gif
python3 tools/split_pose_sheet.py <sheet>.png <anim>/.src idle windup hit   # sheet -> poses
python3 tools/poses_to_feditor.py <anim_dir>          # poses.yaml -> the FEditor frames
python3 tools/banim_paint.py edit|apply <anim_dir>    # hand-paint what the shrink cannot carry

# Read a failed scenario's own diagnosis BEFORE rebuilding anything (#236; arrives with #237)
#   inspect_state.py render /tmp/playtest-<scenario>/playtest.log
#   inspect_state.py diff   /tmp/playtest-<good>/playtest.log /tmp/playtest-<bad>/playtest.log

# Required before claiming a change is finished. NOTE: `unittest discover -s tools` does NOT reach
# tools/playtest/ (not an importable package) -- `make test` is the one that runs everything.
make test
make check
git diff --check
```
