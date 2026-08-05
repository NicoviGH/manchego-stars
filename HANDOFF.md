# Handoff - Manchego Stars live state

`HANDOFF.md` is live state only. Settled decisions live in `docs/decisions.md`; operating rules
live in `CLAUDE.md`/`AGENTS.md`; issue scope and backlog live in GitHub. Before a context rollover,
warn Nicolas, refresh this file, and begin a fresh instance — don't rely on auto-compaction.

Refreshed 2026-08-05 (Opus) after reviewing Codex's merged work. `main` = `fc1300e`, level with
`origin/main`, no open PRs, no live feature branch.

## Current state

- **Environment: Nicolas is on his Mac. ROM builds, `verify_text` and mGBA playtests are LIVE.**
  Verified on this tree 2026-08-05: 622 Python tool tests pass, `make check` is `drift check: clean`.
- **Cross-agent continuity:** Nicolas uses Codex only between Claude sessions. Codex must leave an
  explicit HANDOFF entry naming what it changed, the active branch/PR and commit state, verification
  actually run, and the exact next step. Per Nicolas's request, Codex uses ordinary short-lived
  feature branches in this checkout, one at a time; **do not create worktrees unless Nicolas
  explicitly changes that instruction.**
- **ch04 (#24) is BUILT, WON, FILMED — one authored line short of done.** The parley converts the
  pack in place with allies scaling to survivors (#203); the Lonelywood village hands over the Iron
  Axe (#205); the snag falls into a bridge (#214); goal ids are per-chapter (#207); the rout and both
  endings are winnable and filmed (#204); every cast member fights as itself (#206). `make difficulty
  CH=ch04` reads **PARITY**, no threat outliers, boss is the chapter's hardest hitter — so Nicolas's
  standing condition on Lupin's leader tile moving `[0,0] → [2,1]` is **satisfied, not outstanding**.
  The single remaining item is the second village's line (#24, reopened; step 1 below).
- **The playtest driver is state-driven (#220 → PR #221).** `tools/playtest/controller.lua` is a PURE
  classifier + legal-action enumerator (observe → classify → enumerate → **one** guarded input →
  verify postcondition → JSON trace); `harness.lua` owns the mGBA-facing observer. Menus are read
  semantically (`MenuProc.menuItems[] → MenuItemProc.def → MenuItemDef.overrideId`; Talk `0x5A`,
  Wait `0x6B`, End Phase `0x78`), dialogue A fires only under `gProcScr_TalkWaitForInput`, and an
  unknown/locked/frozen state **fails closed with no recovery button**. **Standing rule from Nicolas:
  no brute-force, row-probing or cadence input in a scenario — reproducible is not the same as
  justified.** Contract ADR in `decisions.md`; retired phrasings live in `check.py DEAD_CONCEPTS`.
- **ch05 "The Elven Tomb" (#25) — DIALOGUE COMPLETE AND MERGED** (PR #196). 15 slots, all
  `status: locked`. Still owed: map + placement, text insertion → `verify_text`, `--ch05-boot`
  playtest, `enemy_class_reskins` + FE-Repo imports, Basil/Sahnar STAT_DONORs, and the five
  no-Lupin conditionals (they ride Stage 4's `variant_beat`, not a second mechanism).
- **FE8 has TWO palette paths, and the second one is a recurring trap.** Beyond the class-keyed
  redirect in `GetBanimPalette`, a per-**CHARACTER** palette keyed on character × CLASS
  (`gAnimCharaPalConfig`) is applied **after** the anim's own palette loads and silently overwrites
  it. Fixed campaign-agnostically by `_patch_banim_unique_pal_custom_guard`, guarded by
  `check_engine_guards_present`, so every future custom-anim unit is covered whatever slot it lands
  on — #25's Basil and Sahnar included. Full ADR in `decisions.md` §Art & Audio.
- **Winter forest fidelity is an invariant (#193).** Parity/difficulty engine is four-dimensional
  (`tools/difficulty.py`); `make difficulty CH=chNN`.

## NEXT SESSION — the agreed order (Nicolas, 2026-08-05)

**Everything below is on a GitHub issue with its own diagnosis. Start from the issues, not here.**

### 1. ch04's second village (#24, reopened) — the true last ch04 item

The cottage at **(1,11)** is visitable-capable but unwired, so FE8 offers no Visit at all — the
player sees a house they cannot enter. Vanilla's second village is pure Lute recruit dialogue
(`9B2`/`9B3`/`9B4`, zero lore) and our Lupin parley already covers the recruit role, so **there is
nothing to copy — whatever goes there is ours.** Nicolas wants "at least a lore drop or a hint".

**Method, in order:** mine the Frostmaiden book + the DM notes for Lonelywood material FIRST
(`decisions.md` → story sources of truth; the book scan is image-only, PDF page = printed + 1), read
every speaker's voice bible and the roster, **then** run the `dialogue-pass` skill *with Nicolas* —
do not draft solo and do not ask him what the sources already answer. Wiring mirrors #205/#212: a
`villages:` entry whose door tile is visitable (guarded by `assert_village_tiles_visitable`). The
reward can be the line alone — ch04's economy is deliberately Ch4-lean (~270g magnitude, one Iron
Axe, no chests). Any text change means `python3 tools/verify_text.py` before claiming done.

### 2. #218 — the unit-list sprites (RETITLE IT: they are MAP SPRITES, not chibi portraits)

**Nicolas's correction, 2026-08-05, and it changes the diagnosis:** the Character/unit-list screen
draws each unit's **map sprite**, not the chibi portrait the issue currently describes. His read is
that **some of our units are 32x32 where the table expects 16x16, so entries overlap.** The decomp
supports it — do not chase a "third palette path".

Grounding already gathered (verify, don't re-derive):

- `src/unitlistscreen.c` draws rows via `PutUnitSprite(4, 8, 56 + i*16 + r8, ...)` — a **16px row
  pitch** — after `ForceSyncUnitSpriteSheet()`.
- `PutUnitSprite` (`src/bmudisp.c:1261`) switches on **`GetInfo(id).size`**: `UNIT_ICON_SIZE_16x16`
  draws `gObject_16x16` at `y`; `16x32` draws at `y-16`; `32x32` draws `gObject_32x32` at
  `x-8, y-16`. A 32x32 entry therefore bleeds a full 16px into the neighbouring row, and its chr
  allocation is 4× a 16x16's.
- Our wait sheets genuinely mix all three size classes (`campaigns/rime-of-the-frostmaiden/map_sprites/`):
  **16x48** = 3×16x16 (marty, pinky, prof-rbg, rootis, sahnar, sclorbo, trex, hlin-trollbane);
  **16x96** = ambiguous, 6×16x16 **or** 3×16x32 (basil, fire-imp, lizard-wildling, lizardzerker);
  **32x96** = 3×32x32 (baxby, braulo, lupin, meesmickle, wolfram, white-moose, lycanroc-pack).
- `tools/map_sprite_tool.py` already knows this ambiguity and says so at its line ~55: 16x96 fits
  both, "**and only the wait table says which**" — the caller should pass `expect` from the decomp.
  **That is the most likely defect site:** what size does our custom SMS slot (`CUSTOM_SMS_BASE =
  107`+, `inject_map_sprites` in `tools/build_campaign.py:2505`) declare per unit, and does it match
  the sheet's real geometry?

**First move:** read what the injector writes into the wait/info table for each custom id and compare
it against the sheet geometry above — a mismatch there explains a cast-wide failure (one oversize
entry tramples the shared sheet region) far better than any per-unit asset defect. Then confirm
in-engine rather than by reasoning ([[feedback_verify_in_engine]]): the unit list is a late screen,
so **build a TESTCH-style fast boot straight to it** instead of grinding a playthrough per capture.
Cast-wide, cosmetic, but a screen players open constantly.

### 3. #222 workstream 1 ONLY — the playtest matrix runner

Codex's tooling epic. **Agreed scope: take workstream 1 (one command runs the live regression
matrix, each ROM config built at most once, compact verdict table, artifacts on disk) and defer
workstreams 2–4** (state inspector, declarative scenario manifests, pre-build validation). ch05 will
run that matrix repeatedly, which is what justifies buying it now.

### 4. ch05's build work (#25) — with #222 held open on purpose

**Nicolas's explicit instruction: carry #222 in mind while building ch05, and re-scope it from
experience.** If a deferred workstream turns out to be what actually hurts, widen #222 and take it;
if workstream 1 proves sufficient, narrow the epic and say so on the issue. Do not treat the
deferral as settled — ch05 is the evidence-gathering run. Hosting ch05 also retires ch04's
`dev_placeholder_scene()` terminator, and **#138** (config-driven `inject_chapter(descriptor)`) is
the natural forcing function to take *while* hosting it, not before.

Then: **#29** world map.

## Answered — don't re-ask, don't re-derive

- **The wolves do NOT respawn or relocate during the parley.** A clean `recordch04parley` sampled
  every wolf before the Talk and immediately after conversion: `0xB0 (2,0)`, `0xB1 (0,2)`,
  `0xB2 (0,0)`, `0xB4 (1,0)`, `0xB5 (0,1)` — unchanged. Later movement is the greens' own phase.
- **ch04's difficulty condition is met** — `make difficulty CH=ch04` reads PARITY (see Current state).
- **The parleyed wolves stay `CLASS_MAUTHEDOOG` in the green NPC palette.** `CUSN` changes faction,
  not class; Nicolas accepted this 2026-08-01/02 ("We can do green mouthdoogs for now"). The
  `lycanroc-pack` reskin is declared-but-unworn until a class-remap hook exists.

## Gotchas most likely to bite next (long form in `docs/decisions.md`)

- **Read decomp data through `git show HEAD:`, never the built tree** — our injections are build
  artifacts. (`test_winter_forest_backfill` was moved onto this doctrine by #221 and no longer needs
  a manual restore.)
- **Post-injection goal ids cannot be read from HEAD or the working tree** — run the injector and
  read the result.
- **A failing playtest may be the WRONG ROM** — a `CH04BOOT=1` build cannot reach ch02's map. Boot
  flags are per-chapter, and so is `PT_HOST_CHAPTER`.
- **`turn()` is not the signal that a turn's reinforcements exist** — wait for a UNIT from the wave.
- **An `AREA` fires when an action ENDS**, so "a unit is standing in the clearing" is not a verdict.
  Stop a march on the **outcome** (the moose exists), use position only as the after-the-fact
  diagnostic.
- **A render from frame PNGs proves the ART; only the ROM proves the TILING and the PALETTE.**
- **Comments inside a YAML folded scalar are CONTENT** — put them above the key.
- **`tools/setup-toolchain.sh` omits upstream's helper-tool build** — a fresh checkout also needs
  `fireemblem8u/build_tools.sh` (`scaninc`, `jsonproc`). Not patched in-repo.

## Working tree - do not lose or revert

- **No open PRs and no live feature branch.** `main` is `fc1300e`, level with `origin/main`.
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
PT_HOST_CHAPTER=5 tools/playtest/run.sh recordch04parley   # the wolf parley, in motion
PT_HOST_CHAPTER=5 tools/playtest/run.sh recordch04moose    # the moose sighting, in motion
PT_HOST_CHAPTER=5 tools/playtest/run.sh ch04moose          # GATE: the sighting is player-only
PT_HOST_CHAPTER=5 tools/playtest/run.sh clear_ch04_parley  # parley, rout -> the AUTHORED ending
PT_HOST_CHAPTER=5 tools/playtest/run.sh ch04packmath       # GATE: kill 2 wolves, parley -> 3 greens
PT_HOST_CHAPTER=5 tools/playtest/run.sh ch04village        # GATE: visit (8,2) -> the Iron Axe
PT_HOST_CHAPTER=5 tools/playtest/run.sh ch04snag           # GATE: chop the snag -> (4,9) is a bridge
tools/playtest/run.sh controller_turn                      # GATE: the #220 controller contract
tools/playtest/make_gif.py <scenario> <tag> --name <out> --fps 14   # frames -> docs/demo/<out>.gif

make CAMPAIGN=rime-of-the-frostmaiden CH04BOOT=1 fireemblem8.gba -j$(nproc)   # ch04 fast-boot
make CAMPAIGN=rime-of-the-frostmaiden TESTCH=1 fireemblem8.gba -j$(nproc)     # the battle-anim bench
PT_CHAR=baxby tools/playtest/run.sh recordanim        # any cast member's banim; then make_gif
python3 tools/split_pose_sheet.py <sheet>.png <anim>/.src idle windup hit   # sheet -> poses
python3 tools/poses_to_feditor.py <anim_dir>          # poses.yaml -> the FEditor frames
python3 tools/banim_paint.py edit|apply <anim_dir>    # hand-paint what the shrink cannot carry

# Required before claiming a change is finished
python3 -m unittest discover -s tools -p 'test_*.py'
make check
git diff --check
```
