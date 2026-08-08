# Handoff - Manchego Stars live state

`HANDOFF.md` is live state only: where the tree is, what is in flight, what is owed, what to do next.
**Settled decisions live in `docs/decisions.md`** — if a thing is decided, it belongs there and gets
deleted from here. Operating rules live in `CLAUDE.md`/`AGENTS.md`; scope and backlog live in GitHub
issues. Before a context rollover, warn Nicolas, refresh this file, and start a fresh instance —
don't rely on auto-compaction.

Refreshed 2026-08-08 (Opus). `main` = `952ca51`, level with `origin/main`. **No branches, no
stashes, nothing in flight** — **#252 landed** (Basil is a Cleric; the Basil→Sahnar recruit is
wired). Clean point for a `/clear`.

## In flight

**Nothing.** `origin` has only `main`.

**Nothing has had a `/code-review ultra <PR#>` — that is user-triggered.** #252 had a normal
`/code-review high`, which caught a real defect (below); its four findings are fixed and in the
squash.

## Next task

**ch05 is playable end to end and its recruit works in-engine** (`make matrix` 16/16). Everything
owed is the checklist on **#25**, which is the source — not this file. What is left is the
**dialogue pass**, and it is bigger than "write some prose":

1. **It owes an ID ALLOCATION, not just text.** Every ch05 beat we write needs an id from ch05's
   own block (vanilla Ch6, `0x9E4..0x9F5`). The chapter YAML's `slot: "vanilla 0x9CC"` labels are
   ANATOMY REFERENCES to the chapter we mine — ch04 hosts on slot 5 and owns `0x9BA..0x9C6`
   outright. Budget fits: 16 free ids against ~14 that need writing. `assert_message_id_unclaimed`
   now fails the build if a beat points at an id another chapter writes.
2. **All 15 slots are already WRITTEN and locked** (PR #196) — the pass is wiring them, not
   drafting them. The genuinely unwritten prose is the **four reliquary visit lines** and
   **Ravisin's death quote `0x9C8`**.
3. **Basil's join beat is SILENT** until it gets an id. Its locked text exists; it just has
   nowhere legal to live yet. Reading vanilla prose as a placeholder is still legal and in use
   (`0x9CC`, `0x9CD..0x9D0` — unclaimed by every chapter).
4. **The no-Lupin fallback branch** — text chosen, conditional not built; reuse ch04's mechanism.

Not scheduled: **#244** (three playtest scenarios failing outside the gate suite), **#228**
physical cartridges (after the ROM is done).

## Current state

- **Environment: Nicolas is on his Mac. ROM builds, `verify_text` and mGBA playtests are LIVE.**
- **Gate: `make matrix` 16/16 on `main` at `952ca51`**, four builds, ~7m. `ch05village` AND the new
  `ch05recruit` are both in it; ch04's six stay, because they cover MECHANISMS ch05 reuses.
- **`ch05recruit` is the recruit's only witness.** `ch05village` was green across versions of the
  opening where Basil never joined at all — it leaves prep with START and walks a different unit
  to a door. If you touch ch05's opening, that is the scenario that will tell you.
- **Art review is a two-command bench, and BOTH belong to any new unit.** `PT_CHAR=<id> run.sh
  recordcast` shoots the bust + map sprite; `recordanim` shoots the battle anim (`PT_ROUNDS=N` for
  several engagements). Checklist: the `custom_unit` issue template.
- **A `BLOCKED` verdict means something.** Treat it as real until proven otherwise; do not reach
  for a retry to make it go away.
- **ch01–ch04 are DONE and CLOSED; ch05 (#25) is the only chapter with work owed.**
- **Cross-agent continuity:** Nicolas uses Codex only between Claude sessions. Codex must leave an
  explicit HANDOFF entry naming what it changed, the active branch/PR and commit state, verification
  actually run, and the exact next step. Ordinary short-lived feature branches in this checkout, one
  at a time — **do not create worktrees unless Nicolas explicitly changes that.**

## Gotchas most likely to bite next (long form in `docs/decisions.md`)

**This session's headline, and it is a new shape of the old lesson: a message id can be VALID,
UNIQUE, and still belong to somebody else.** ch05's join beat pointed at `0x9C2` — which ch04
owns and writes — so it would have played ch04's no-parley ending, in ch04's voice, with ch04's
faces. Green build. Passing `ch05recruit` (it reads factions, not text). Nothing caught it but a
code review. Displaying an UNWRITTEN vanilla id is a legitimate placeholder; displaying one another
chapter WRITES is a bug, and the two are indistinguishable at the call site — hence
`assert_message_id_unclaimed`.

**The runner-up: `ch05village` passed for months while proving nothing about the recruit.** A
scenario's verdict only covers what it actually reads. Before trusting a green gate on a feature,
check that some scenario reads the feature's OWN state.

**And a self-inflicted one worth remembering: `ch05recruit` failed its first run for the wrong
reason** — it reported "the CUSA did not fire" when the CUSA was fine, because the scene runs
vanilla's 32-box `0x9CC` and the loop capped at 3600 frames. *A loop cap must never be what decides
failure*, and a verdict must tell "still running" from "finished and wrong".

The standing ones:

- **Read decomp data through `git show HEAD:`, never the built tree** — our injections are build
  artifacts. **It bit twice more this session**, both times as `make check` failing on
  `test_difficulty` + `test_map_tileset` straight after a ROM build (once mid-commit, blocking the
  pre-commit hook) — that pair failing together is the signature. Fix, don't debug:
  `git -C fireemblem8u restore src/data/chapter_settings.json data/data_8B363C.s`.
- **Before building tooling, grep for it.** `talk_recruit_wiring` already named ch05 in its
  docstring; the recruit needed no new machinery, only `ch04_parley_recruiters` generalised.
- **A HANDOFF lead is a hypothesis.** The previous entry said "wire his Talk" and "force-deploy the
  recruiter"; both were wrong for Basil, who joins in the OPENING (no CHAR entry) and is not on the
  prep roster (nothing to bench). The YAML and vanilla's own event list were the truth.
- **Post-injection SMS ids and goal ids cannot be read from HEAD or the working tree** — run the
  injector and read the result.
- **A failing playtest may be the WRONG ROM.** Boot flags are per-chapter, and so is
  `PT_HOST_CHAPTER`. `run.sh` refuses this in 0s off `.build-config.json` — **do not reach for
  `MX_SKIP_ROM_CHECK=1`**. **Exception: `mapshot`/`mapfull` are chapter-GENERIC**, so run.sh cannot
  refuse them. `make matrix` rebuilds the tree's ROM, so check `.build-config.json` first.
- **`harness.lua` is one Lua chunk AT the 200-local ceiling** (2 slots free). Hang new helpers off
  an existing table (`INSPECT`, `TUNE`) or inside the scenario, never a new top-level `local`.
- **Do not re-run a scenario to re-test a hypothesis the evidence already killed.** Instrument for
  the answer — `inspect_state.py render` is that instrument.
- **A `transition` is not "nothing is happening"** — check the snapshot's `considered` list.
- **`turn()` is not the signal that a turn's reinforcements exist** — wait for a UNIT from the wave.
- **An `AREA` fires when an action ENDS**, so "a unit is standing there" is not a verdict.
- **A scenario that fails BEFORE it drives any input is accusing the harness, not the chapter.**
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

# THE GATE, one command (#231): ~7 min, verdict table + results.json in /tmp/playtest-matrix
make matrix                                # SUITE=gate -- must be green before a merge
make matrix SUITE=ch03|ch04|all
tools/playtest/matrix.py list --suites
tools/playtest/run.sh ch05recruit          # ONE scenario; flag + host chapter come from matrix.yaml

make CAMPAIGN=rime-of-the-frostmaiden fireemblem8.gba -j$(nproc)              # canonical
make CAMPAIGN=rime-of-the-frostmaiden CH05BOOT=1 fireemblem8.gba -j$(nproc)   # ch05 fast-boot

# Read a failed scenario's own diagnosis BEFORE rebuilding anything (#236)
#   inspect_state.py render /tmp/playtest-<scenario>/playtest.log
#   inspect_state.py diff   /tmp/playtest-<good>/playtest.log /tmp/playtest-<bad>/playtest.log

# Required before claiming a change is finished. NOTE: `unittest discover -s tools` does NOT reach
# tools/playtest/ (not an importable package) -- `make test` is the one that runs everything.
make test
make check
git diff --check
```
