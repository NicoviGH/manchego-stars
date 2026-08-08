# Handoff - Manchego Stars live state

`HANDOFF.md` is live state only: where the tree is, what is in flight, what is owed, what to do next.
**Settled decisions live in `docs/decisions.md`** — if a thing is decided, it belongs there and gets
deleted from here. Operating rules live in `CLAUDE.md`/`AGENTS.md`; scope and backlog live in GitHub
issues. Before a context rollover, warn Nicolas, refresh this file, and start a fresh instance —
don't rely on auto-compaction.

Refreshed 2026-08-07 (Opus). `main` = `ade07d6`, level with `origin/main`. **No branches, no
stashes, nothing in flight** — #246, #247, #248 and #249 all landed this session.

## In flight

**Nothing.** `origin` has only `main`.

**Nothing has had a `/code-review ultra <PR#>` — that is user-triggered.**

## Next task

**ch05 is HOSTED, playable, and its rewards are reachable** (`--ch05-boot` load-test PASS,
`ch05village` PASS, `make matrix` 14/14). Everything owed is the checklist on **#25**, which is the
source — not this file. No live defects remain on it; what is left is authoring work:

1. **Basil→Sahnar Talk recruit.** She has no `PORTRAIT_MAP` slot and carries `recruit.via: story`,
   so she is on the field on her own pid (`0xba`) and cannot yet be turned. `recruit_initial_faction`
   already returns RED for her, so the flow exists — she needs an identity.
2. **The dialogue pass.** ch05's cutscenes are LOCKED (PR #196) and unwired, and the four reliquary
   visits currently show **vanilla's** prose on ids `0x9CD`–`0x9D0`, which we deliberately do not
   write. Replacing one is writing our body at the same id — not a rewire (`decisions.md` →
   "Vanilla prose is a legitimate PLACEHOLDER").
3. **Converge ch03/ch04 onto the campaign-owned tables** (`decisions.md` → "Campaign rosters live
   in campaign-named symbols"). Five symbols still squat on vanilla:
   `CH03_TREX_GREEN_SYMBOL`, `CH03_BOOT_SEED_SYMBOL`, `CH04_INITIAL_ENEMY_SYMBOL`,
   `CH04_BOOT_SEED_SYMBOL`, `CH04_MOOSE_SYMBOL`. Fold in the `_inject_ch03_tile_changes` →
   generic `_inject_tile_changes` migration #138 left behind. **Verify with `make matrix`, not
   byte-identity** — appending tables legitimately changes the ROM.

Not scheduled: **#244** (three playtest scenarios failing outside the gate suite), **#245** (the
`TESTCH` build race), **#228** physical cartridges (after the ROM is done).

## Current state

- **Environment: Nicolas is on his Mac. ROM builds, `verify_text` and mGBA playtests are LIVE.**
- **Gate: `make matrix` 14/14 on `main` at `ade07d6`** (re-run after every merge this session).
  A `BLOCKED` verdict is usually the `TESTCH` build race (#245), not the scenario — it fired once
  this session and passed on a plain retry, which is how you tell it apart from a real break.
- **OPEN CALL for Nicolas: `ch05village` is not in the gate suite.** It lives in `SUITE=ch05` and
  passes there. The gate carries the ACTIVE chapter's scenarios (six ch04 rows, no ch03), so ch05
  belongs in it on that pattern — but `ch05boot` would be a fourth ROM build, ~2 more minutes on
  every merge. Options put to him: add just `ch05village`; add it and trim ch04's six now that
  ch04 is closed (keeps gate time flat); or leave it deliberate-run-only.
- **ch01–ch04 are DONE and CLOSED; ch05 (#25) is the only chapter with work owed.** Its dialogue
  merged long ago (PR #196, 15 slots, all `status: locked`); its map, its host and its difficulty
  math are all in (`make difficulty CH=ch05` = PARITY). It is now `status: active`, so it is inside
  the parity gate rather than exempt from it.
- **Cross-agent continuity:** Nicolas uses Codex only between Claude sessions. Codex must leave an
  explicit HANDOFF entry naming what it changed, the active branch/PR and commit state, verification
  actually run, and the exact next step. Ordinary short-lived feature branches in this checkout, one
  at a time — **do not create worktrees unless Nicolas explicitly changes that.**

## Gotchas most likely to bite next (long form in `docs/decisions.md`)

The six this session added are ADRs now — read them before hosting another chapter. Four are one
idea wearing different hats, and it bit three separate times in one session: **declaring a thing is
not wiring it, and the gap has no symptom.** (Campaign rosters live in campaign-named symbols;
owning the symbol means owning the POINTER; campaign-owned EVENT SCRIPTS must be declared AFTER the
block-replacement pass or the appends are discarded; a `CHAPTER_L_*` label is resolved by VALUE.)
The other two: a retile inherits vanilla's GIFT PLACEMENT; vanilla prose is a legitimate
placeholder but vanilla wiring is not. The standing ones:

- **Read decomp data through `git show HEAD:`, never the built tree** — our injections are build
  artifacts. Applies to lints too: a check that greps the working tree for something the build patches
  out passes vacuously. **It bit twice more this session**, both times as `make check` failing on
  `test_difficulty` + `test_map_tileset` straight after a ROM build — that pair failing together is
  the signature. Fix, don't debug: `git -C fireemblem8u restore src/data/chapter_settings.json
  data/data_8B363C.s`.
- **Before building tooling, grep for it.** `render-tmx`, `atlas`, `uniform_candidates` and
  `vanilla_layout_tileset_assets` all already existed and were hand-rolled from scratch this session;
  `decisions.md:133` states outright that tileset vendoring is a one-command import.
- **Post-injection SMS ids and goal ids cannot be read from HEAD or the working tree** — run the
  injector and read the result.
- **A failing playtest may be the WRONG ROM.** Boot flags are per-chapter, and so is
  `PT_HOST_CHAPTER`. `run.sh` refuses this in 0s off `.build-config.json` — **do not reach for
  `MX_SKIP_ROM_CHECK=1`**. **Exception: `mapshot`/`mapfull` are chapter-GENERIC, so run.sh cannot
  refuse them** and they fail as "never reached the map" instead. `make matrix` rebuilds the tree's
  ROM, so a `mapshot` run right after one is on the matrix's last config, not yours — check
  `.build-config.json` first (this cost a rebuild this session).
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

- **`main` is clean and level with `origin/main`. No branches (`origin` has only `main`), no
  stashes.**
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
