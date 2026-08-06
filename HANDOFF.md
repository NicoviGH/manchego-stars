# Handoff - Manchego Stars live state

`HANDOFF.md` is live state only: where the tree is, what is in flight, what is owed, what to do next.
**Settled decisions live in `docs/decisions.md`** — if a thing is decided, it belongs there and gets
deleted from here. Operating rules live in `CLAUDE.md`/`AGENTS.md`; scope and backlog live in GitHub
issues. Before a context rollover, warn Nicolas, refresh this file, and start a fresh instance —
don't rely on auto-compaction.

Refreshed 2026-08-06 (Opus). `main` = `933fee0`, level with `origin/main`.
**In flight: PR #235** (`fix/232-gate-failures`) — the #232 playtest repairs, rebased on `main`,
awaiting CI + merge. Nothing else: no other branches, no stashes.
**Next task is #236 — the playtest state inspector. Jump to NEXT SESSION.**

## Current state

- **Environment: Nicolas is on his Mac. ROM builds, `verify_text` and mGBA playtests are LIVE.**
  Verified on this tree 2026-08-06: all `tools/test_*.py`, 8 Lua harness suites, `make check` =
  `drift check: clean`, canonical + `TESTCH=1` + `CH04BOOT=1` all build green.
- **The live regression matrix is `make matrix` (#231, merged in #233).** One command builds each ROM
  configuration at most once and prints a verdict table. **`tools/playtest/matrix.yaml` is now the
  single source of what a scenario needs** — ROM flag, `PT_HOST_CHAPTER`, checkpoint, fps/deadline —
  and `check.py check_playtest_matrix` fails the build if a `harness.lua` scenario has no row.
- **Gate status: 13/14.** `ch01` is the one known red and it is tracked: it parks in the Beat-1
  Northlook cutscene (see #232 → #236). Everything else in the gate is green as of 2026-08-06.
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

### 0. First: land PR #235 if it is still open

The #232 playtest repairs, already verified live (gate 13/14). CI failed once on a GitHub Actions
outage ("Service Unavailable" in *Set up job*, before anything ran) and was re-run — check it, merge,
delete the branch, then refresh this file.

### 1. #236 — the playtest state inspector  ← START HERE

**#222 workstream 2, promoted out of "deferred" on evidence** (Nicolas, 2026-08-06: *"more
observability makes sense if it will stop future iterations from burning compute"*). #231 made
*running* the matrix cheap; diagnosing it is now the binding constraint. **Read #236 for scope and
Definition of Done.** What it does not tell you:

- **The concrete blocker is proc identity.** `freezeReport` names procs by nearest-preceding symbol,
  so three distinct scripts all print as `E_FACE`. That is why #232's last failure is still open:
  the dump cannot say which proc is waiting. Exact-match resolution, and an honest "unknown script"
  when nothing matches, is worth more than any amount of extra formatting.
- **`classify()` returning `transition` is the real blind spot.** Five of #232's six defects were
  input waits nothing had a name for; each read as a passive transition and cost a full
  build-and-run cycle to identify. Making "this is an UNCLASSIFIED wait, here is what it was
  compared against" a visible output is the highest-value part of this issue.
- **Reuse the controller observer.** `observeController()` already builds the state; the inspector
  formats and diffs it. A second state model is explicitly out of scope (#222 guardrail).
- **`ch01` is the acceptance case** — it parks in the Beat-1 Northlook cutscene with the event engine
  live and no page wait ever classified. If the inspector cannot say what that scene wants, it has
  not earned its keep; if it can, it closes the rest of #232. `reachCh01Map` is shared by
  `smoke_ch01` / `clear_ch01` / `fuzz_ch01`, so this is four scenarios, not one.

### 2. ch05's build work (#25) — with #222 still held open on purpose

**Nicolas's standing instruction: carry #222 in mind while building ch05 and re-scope it from
experience.** Workstream 2 has now been taken on exactly that basis; workstreams 3–4 (declarative
scenario manifests, static chapter lint) remain deferred and want the same evidence test. **#138**
(config-driven `inject_chapter(descriptor)`) is the natural forcing function to take *while* hosting
ch05, not before.

**Adding ch05 to the playtest matrix is now a step in the runbook** (`docs/adding-a-chapter.md`
step 11): declare `ch05boot` in `matrix.yaml` `rom_configs`, give every new scenario a row, and add a
`ch05` suite so `make matrix SUITE=ch05` runs the chapter off one build. `check.py` fails the build
if a scenario in `harness.lua` has no row, so this is enforced, not optional.

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
- **`harness.lua` is one Lua chunk near the 200-local ceiling** — put tuning in the `TUNE` table, not
  in a new top-level `local`, or the whole file stops loading and every scenario dies at once. A
  `loadfile` check must ASSERT; it returns `nil, err` rather than raising.
- **Do not re-run a scenario to re-test a hypothesis the evidence already killed.** A budget-bounded
  loop exits at the same frame no matter what is on screen, so an identical frame number proves
  nothing. Instrument for the answer instead — that is what #236 is for.
- **`turn()` is not the signal that a turn's reinforcements exist** — wait for a UNIT from the wave.
- **An `AREA` fires when an action ENDS**, so "a unit is standing in the clearing" is not a verdict.
  Stop a march on the **outcome** (the moose exists); use position only as the after-the-fact diagnostic.
- **A render from frame PNGs proves the ART; only the ROM proves the TILING and the PALETTE.**
- **Comments inside a YAML folded scalar are CONTENT** — put them above the key.
- **`tools/setup-toolchain.sh` omits upstream's helper-tool build** — a fresh checkout also needs
  `fireemblem8u/build_tools.sh` (`scaninc`, `jsonproc`). Not patched in-repo.

## Working tree - do not lose or revert

- **One open PR: #235** on `fix/232-gate-failures` (2 commits, rebased on `main`, verified live at
  gate 13/14). No stashes. `main` is `933fee0`, level with `origin/main`. #234 was the same work and
  is CLOSED — GitHub auto-closed it when #233's branch was deleted on merge; do not reopen it.
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
# + results.json in /tmp/playtest-matrix. 13/14 green; ch01 is the known red (#232 -> #236).
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

# Required before claiming a change is finished
python3 -m unittest discover -s tools -p 'test_*.py'
make check
git diff --check
```
