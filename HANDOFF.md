# Handoff - Manchego Stars live state

`HANDOFF.md` is live state only: where the tree is, what is in flight, what is owed, what to do next.
**Settled decisions live in `docs/decisions.md`** — if a thing is decided, it belongs there and gets
deleted from here. Operating rules live in `CLAUDE.md`/`AGENTS.md`; scope and backlog live in GitHub
issues. Before a context rollover, warn Nicolas, refresh this file, and start a fresh instance —
don't rely on auto-compaction.

Refreshed 2026-08-05 (Opus). `main` = `e0b61bd`, level with `origin/main`.
**Nothing is in flight: no open PRs, no feature branches, no stashes.**
**Next task is #222 workstream 1 — the playtest matrix runner. Jump to NEXT SESSION.**

## Current state

- **Environment: Nicolas is on his Mac. ROM builds, `verify_text` and mGBA playtests are LIVE.**
  Verified on this tree 2026-08-05: 657 Python tests, 8 Lua harness suites, `make check` =
  `drift check: clean`, both ROM flavours build green.
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

## NEXT SESSION — the agreed order (Nicolas, 2026-08-05)

**Start from the GitHub issue, not from here.** These notes only add what the issue does not say.

### 1. #222 workstream 1 ONLY — the playtest matrix runner  ← START HERE

**Agreed scope: workstream 1 only** (one command runs the live regression matrix, each ROM config
built at most once, compact verdict table, artifacts on disk); **defer workstreams 2–4** (state
inspector, declarative scenario manifests, pre-build validation). ch05 will run that matrix
repeatedly, which is what justifies buying it now. **#222 is current — read it for scope and
Definition of Done.** What it does not tell you:

- **`run.sh` does not build anything.** It hard-fails with `ROM not built; run make first`
  (`tools/playtest/run.sh:143`). Building each configuration once is therefore *new* orchestration the
  matrix runner owns, not something to refactor out of run.sh.
- **The ROM configurations are `make` flags**: canonical (no flag), `TESTCH=1` (Ch1 sandbox — whole
  cast + one of each reskinned foe pre-deployed), `CH03BOOT=1`, `CH04BOOT=1`, `LORDBOOT=1`,
  `MONTAGE=1`. Scenarios also need `PT_HOST_CHAPTER` (1 / 4 / 5) and sometimes `PT_CHAR`, or
  `PT_STATE`/`PT_TAG`/`PT_UNTIL`.
- **Two thirds of the manifest already exists as bash `case` blocks in `run.sh`** — port them, do not
  re-derive: the scenario→checkpoint map (~lines 200–216), the fps/vsync/deadline policy per scenario
  class (`record*` = 60fps, else 240fps, longer deadlines for `smoke_*`/`fuzz_*`/`clear_ch02`), and
  the per-scenario header comments naming each one's ROM flag + `PT_HOST_CHAPTER`.
- **Checkpoints are ROM-hash-stamped** (`tools/playtest/states/<name>.ss` + `.romhash`, gitignored)
  and auto-rebuilt when stale. So grouping by ROM configuration is not only about avoiding rebuilds —
  **switching configuration invalidates every checkpoint**, and `ckpt_ch02start` replays the whole
  ch00→ch01→ch02 chain to rebuild one. Bad ordering costs far more than a duplicate build.
- **The scenario list is `harness.lua`'s `scenarios` table (~90 entries) — that is authoritative**, not
  run.sh's header comment.

### 2. ch05's build work (#25) — with #222 held open on purpose

**Nicolas's explicit instruction: carry #222 in mind while building ch05 and re-scope it from
experience.** If a deferred workstream turns out to be what actually hurts, widen #222 and take it; if
workstream 1 proves sufficient, narrow the epic and say so on the issue. Do not treat the deferral as
settled — ch05 is the evidence-gathering run. **#138** (config-driven `inject_chapter(descriptor)`) is
the natural forcing function to take *while* hosting ch05, not before.

Then: **#29** world map.

Parked, not scheduled: **#228** physical cartridges (after the ROM is done).

## Gotchas most likely to bite next (long form in `docs/decisions.md`)

- **Read decomp data through `git show HEAD:`, never the built tree** — our injections are build
  artifacts. Applies to lints too: a check that greps the working tree for something the build patches
  out passes vacuously.
- **Post-injection SMS ids and goal ids cannot be read from HEAD or the working tree** — run the
  injector and read the result.
- **A failing playtest may be the WRONG ROM** — a `CH04BOOT=1` build cannot reach ch02's map. Boot
  flags are per-chapter, and so is `PT_HOST_CHAPTER`.
- **`turn()` is not the signal that a turn's reinforcements exist** — wait for a UNIT from the wave.
- **An `AREA` fires when an action ENDS**, so "a unit is standing in the clearing" is not a verdict.
  Stop a march on the **outcome** (the moose exists); use position only as the after-the-fact diagnostic.
- **A render from frame PNGs proves the ART; only the ROM proves the TILING and the PALETTE.**
- **Comments inside a YAML folded scalar are CONTENT** — put them above the key.
- **`tools/setup-toolchain.sh` omits upstream's helper-tool build** — a fresh checkout also needs
  `fireemblem8u/build_tools.sh` (`scaninc`, `jsonproc`). Not patched in-repo.

## Working tree - do not lose or revert

- **No open PRs, no live feature branch, no stashes.** `main` is `e0b61bd`, level with `origin/main`.
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
tools/playtest/run.sh controller_turn                      # GATE: the #220 controller contract
tools/playtest/run.sh recordunitlist                       # GATE: Character list + the SMS budget
PT_HOST_CHAPTER=5 tools/playtest/run.sh ch04moose          # GATE: the sighting is player-only
PT_HOST_CHAPTER=5 tools/playtest/run.sh ch04packmath       # GATE: kill 2 wolves, parley -> 3 greens
PT_HOST_CHAPTER=5 tools/playtest/run.sh ch04village        # GATE: visit (8,2) -> the Iron Axe
PT_HOST_CHAPTER=5 tools/playtest/run.sh ch04cottage        # GATE: visit (1,11) -> line plays, door shuts
PT_HOST_CHAPTER=5 tools/playtest/run.sh ch04snag           # GATE: chop the snag -> (4,9) is a bridge
PT_HOST_CHAPTER=5 tools/playtest/run.sh clear_ch04_parley  # parley, rout -> the AUTHORED ending
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
