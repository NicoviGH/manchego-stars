# Handoff - Manchego Stars live state

`HANDOFF.md` is live state only: where the tree is, what is in flight, what is owed, what to do next.
**Settled decisions live in `docs/decisions.md`** — if a thing is decided, it belongs there and gets
deleted from here. Operating rules live in `CLAUDE.md`/`AGENTS.md`; scope and backlog live in GitHub
issues. Before a context rollover, warn Nicolas, refresh this file, and start a fresh instance —
don't rely on auto-compaction.

Refreshed 2026-08-07 (Opus). `main` = `cbeae9f`, level with `origin/main` — **untouched this
session.** All work sits on a branch.

## In flight

**[PR #246](https://github.com/NicoviGH/manchego-stars/pull/246) — `feat/25-ch05-map`, 4 commits,
open and unreviewed.** ch05's map plus the three tooling defects painting it exposed.

```
7f8f3ab  ch05: wire the four reward sites so the gifts actually ship
09f5d37  docs: record the three calls this retile settled
f81cb0e  ch05: two battle-anim blockers are stale -- correct them before they are inherited
39d7325  ch05: retile vanilla Ch5 as the elven tomb, and keep vanilla's terrain
```

Verified on the branch: `make test` exit 0 (36 tileset tests, 9 new), `make check` =
`drift check: clean`, compiled `.mar` round-trips byte-identical to Nicolas's export,
`terrain drift vs vanilla Ch5: 0`, submodule pointer not staged.

**Nothing has had a `/code-review ultra <PR#>` — that is user-triggered.**

## Next task

1. **Land #246.** Squash-merge, delete the branch, refresh this file on `main` after.
2. **`inject_ch05`** — the map is data now; nothing injects it. Follow
   `docs/adding-a-chapter.md`; host slot **6** → `Ch6Events` (declare both in
   `tools/inject/hosts.py` — that pair is what enrols the chapter in the guards).
   `TILESET_STEMS` already claims the stem `PortTown`; the `_register_tileset` call rides
   `inject_ch05` the way `Cave` rides `inject_ch03`.
3. Everything else owed on the chapter is the checklist on **#25**, which is the source — not
   this file.

Not scheduled: **#244** (three playtest scenarios failing outside the gate suite), **#245** (the
`TESTCH` build race), **#228** physical cartridges (after the ROM is done).

## Current state

- **Environment: Nicolas is on his Mac. ROM builds, `verify_text` and mGBA playtests are LIVE.**
- **Gate: `make matrix` was 14/14 on `main` at `6ed2903`; not re-run this session** (no ROM work
  happened — the branch is data + tooling only). A `BLOCKED` verdict is usually the `TESTCH` build
  race (#245), not the scenario.
- **ch01–ch04 are DONE and CLOSED; ch05 (#25) is the only chapter with work owed.** Its dialogue
  merged long ago (PR #196, 15 slots, all `status: locked`); its **map** is #246; its difficulty
  math is **confirmed PARITY** (`make difficulty CH=ch05`, re-run 2026-08-07).
- **Cross-agent continuity:** Nicolas uses Codex only between Claude sessions. Codex must leave an
  explicit HANDOFF entry naming what it changed, the active branch/PR and commit state, verification
  actually run, and the exact next step. Ordinary short-lived feature branches in this checkout, one
  at a time — **do not create worktrees unless Nicolas explicitly changes that.**

## Gotchas most likely to bite next (long form in `docs/decisions.md`)

The three this session added are ADRs now (a retile inherits vanilla's terrain; a layout's tileset is
resolved not inferred; unused slots are declared by `TERRAIN_NONE`). Read them before touching the
map pipeline. The standing ones:

- **Read decomp data through `git show HEAD:`, never the built tree** — our injections are build
  artifacts. Applies to lints too: a check that greps the working tree for something the build patches
  out passes vacuously. **This bit twice this session** — once reading `chapter_settings.json`, once
  hashing a tileset config against our own injected copy.
- **Before building tooling, grep for it.** `render-tmx`, `atlas`, `uniform_candidates` and
  `vanilla_layout_tileset_assets` all already existed and were hand-rolled from scratch this session;
  `decisions.md:133` states outright that tileset vendoring is a one-command import.
- **Post-injection SMS ids and goal ids cannot be read from HEAD or the working tree** — run the
  injector and read the result.
- **A failing playtest may be the WRONG ROM.** Boot flags are per-chapter, and so is
  `PT_HOST_CHAPTER`. `run.sh` refuses this in 0s off `.build-config.json` — **do not reach for
  `MX_SKIP_ROM_CHECK=1`**.
- **`harness.lua` is one Lua chunk AT the 200-local ceiling.** Hang new helpers off an existing table
  (`INSPECT`, `TUNE`), never a new top-level `local`.
- **Do not re-run a scenario to re-test a hypothesis the evidence already killed.** Instrument for the
  answer — `inspect_state.py render` is that instrument.
- **A loop cap must never be what decides failure.**
- **A `transition` is not "nothing is happening"** — check the snapshot's `considered` list.
- **`turn()` is not the signal that a turn's reinforcements exist** — wait for a UNIT from the wave.
- **An `AREA` fires when an action ENDS**, so "a unit is standing there" is not a verdict.
- **A scenario that fails BEFORE it drives any input is accusing the harness, not the chapter.**
- **Removing a blind press can remove work nobody had NAMED.**
- **A render from frame PNGs proves the ART; only the ROM proves the TILING and the PALETTE.**
- **Comments inside a YAML folded scalar are CONTENT** — put them above the key.
- **`tools/setup-toolchain.sh` omits upstream's helper-tool build** — a fresh checkout also needs
  `fireemblem8u/build_tools.sh` (`scaninc`, `jsonproc`).

## Working tree - do not lose or revert

- **`main` is clean and level with `origin/main`. One branch: `feat/25-ch05-map` (pushed, PR #246).**
  No stashes.
- **Two more gitignored `gen_symbols.py` outputs** sit next to `symbols.lua`: `procscr.lua` and
  `symbols.json`. Regenerated after every `make`; never commit them.
- **`.build-config.json` (repo root, gitignored) records which boot flags built the ROM in the tree.**
  Deleting it is harmless — an unknown stamp just disables the guard.
- `fireemblem8u` is dirty from injected/generated build artifacts. **Never commit its submodule
  pointer.** Restore the injected decomp files before `check.py`/the pre-commit hook so it runs in
  ~22s instead of ~4min: `git -C fireemblem8u restore src/data/chapter_settings.json data/data_8B363C.s`.
- Untracked local/session files (`.agents/`, `AGENTS.md`, `skills-lock.json`, `map-review/`,
  `review/`) are intentionally not versioned; leave them alone. `map-review/` is the render scratch
  Nicolas opens in Preview — deliverable art goes to `docs/demo/` and is COMMITTED (GIF, not MP4).
  `tools/key_magenta.py` is **gitignored** (#178).
- **HANDOFF.md is authored on `main` ONLY** — gated by `check.py check_handoff_only_on_main`.
  If the guard fires on a branch: `git checkout main -- HANDOFF.md`.
- **If `.git/config` ever shows `core.bare=true` or a `t`/`t@t` identity, a git-shelling test escaped
  its fixture.** Repair: `git config --local core.bare false`, `user.name "Nicolas"`,
  `user.email "nicolas.vivas94@gmail.com"`.

## Quick commands

```sh
make difficulty CH=ch05                    # parity/economy read (all from HEAD)

# Map pipeline (ch05's map is DONE; this is the recipe for the next one)
python3 tools/gen_map_editor.py --tileset=<ts> --blank=WxH --vanilla=<Layout> out.html dl.json [seed.mar]
python3 tools/map_tileset_tool.py import <config> <object.png> maps/tilesets/<name>   # vendor
python3 tools/map_tileset_tool.py render-tmx maps/tilesets/<name> <test.tmx> out.png  # PROVE the import
python3 tools/import_map_layout.py <map-stem> ~/Downloads/<stem>-layout.json          # compile

# THE GATE, one command (#231): ~4-6 min, verdict table + results.json in /tmp/playtest-matrix
make matrix                                # SUITE=gate -- must be green before a merge
make matrix SUITE=ch03|ch04|all
tools/playtest/matrix.py list --suites
tools/playtest/run.sh ch04moose            # ONE scenario; flag + host chapter come from matrix.yaml

make CAMPAIGN=rime-of-the-frostmaiden fireemblem8.gba -j$(nproc)              # canonical
make CAMPAIGN=rime-of-the-frostmaiden CH04BOOT=1 fireemblem8.gba -j$(nproc)   # ch04 fast-boot

# Read a failed scenario's own diagnosis BEFORE rebuilding anything (#236)
#   inspect_state.py render /tmp/playtest-<scenario>/playtest.log
#   inspect_state.py diff   /tmp/playtest-<good>/playtest.log /tmp/playtest-<bad>/playtest.log

# Required before claiming a change is finished. NOTE: `unittest discover -s tools` does NOT reach
# tools/playtest/ (not an importable package) -- `make test` is the one that runs everything.
make test
make check
git diff --check
```
