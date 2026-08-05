# Handoff - Manchego Stars live state

`HANDOFF.md` is live state only. Settled decisions live in `docs/decisions.md`; operating rules
live in `CLAUDE.md`/`AGENTS.md`; issue scope and backlog live in GitHub. Before a context rollover,
warn Nicolas, refresh this file, and begin a fresh instance — don't rely on auto-compaction.

Refreshed 2026-08-05 (Opus) after merging #224 (#218) and #226 (#225). `main` = `5e8c1cf`, level
with `origin/main`, no open PRs, no live feature branch.

## Current state

- **Environment: Nicolas is on his Mac. ROM builds, `verify_text` and mGBA playtests are LIVE.**
  Verified on this tree 2026-08-05: 641 Python tool tests pass, the 8 Lua harness suites pass,
  `make check` is `drift check: clean`, and a full ROM build is green.
- **Cross-agent continuity:** Nicolas uses Codex only between Claude sessions. Codex must leave an
  explicit HANDOFF entry naming what it changed, the active branch/PR and commit state, verification
  actually run, and the exact next step. Per Nicolas's request, Codex uses ordinary short-lived
  feature branches in this checkout, one at a time; **do not create worktrees unless Nicolas
  explicitly changes that instruction.**
- **ch04 (#24) is DONE and CLOSED** (PR #223, 2026-08-05). The parley converts the pack in place
  with allies scaling to survivors (#203); both villages are wired and speak (#205, #24); the snag
  falls into a bridge (#214); goal ids are per-chapter (#207); the rout and both endings are
  winnable and filmed (#204); every cast member fights as itself (#206). `make difficulty CH=ch04`
  reads **PARITY**, so Nicolas's standing condition on Lupin's leader tile moving `[0,0] → [2,1]`
  is satisfied. The only ch04 thread still open is `dev_placeholder_scene()` terminating the
  chapter, which is blocked on ch05 hosting (#25), not on ch04.
- **Two rules came out of #223 and both generalise — full ADRs in `decisions.md`.** (1) **A
  village's line is dialogue**, so `visit_text` is a LIST, one entry per GBA box; a flowed scalar
  is rejected, not reflowed. It had been silently reflowing the axe village's *vanilla-1:1* text
  from vanilla's four sentence-broken boxes into three that buttoned mid-sentence. (2) **A reused
  vanilla BG is a CLIMATE CLAIM** — both villages were playing over `BG_NORMAL_VILLAGE`, a
  temperate green town, in a snowbound fog chapter. Check every backdrop against the map it plays
  over, never inherit it because the vanilla scene being copied used it. **`CH04_ENDING_BG` is
  still vanilla `BG_FOREST` and has NOT been checked against that rule** — Nicolas was told; it is
  his call, not a defect to fix unasked.
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
- **#218 is DONE and CLOSED** (PR #224, 2026-08-05). The Character list drew the whole cast as
  correctly shaped BLACK SILHOUETTES: `UnitList_Init` calls `ApplyUnitSpritePalettes()` (which loads
  our cast palette into purple OBJ bank `0x0B`) and then immediately **zeroes that bank** — the same
  vanilla idiom already patched out of `prep_unitselect.c`, spelled `gPaletteBuffer + 0x1B0` instead
  of `PAL_OBJ(0x0B)`, which is why the Pick Units fix never generalised. Both sites now live in
  `build_campaign.PURPLE_BANK_BLANKERS`. **Signature worth memorising: shape correct + colour absent
  ⇒ the bank was blanked, not the sprite mis-injected.** Nicolas's 32x32-vs-16x16 read and a VRAM
  starvation theory were both measured and ruled out (sizes are declared correctly from donor
  geometry; the counters land at 32x=26 vs 16x=57, 31 slots spare). ADR in `decisions.md` §Art & Audio.
- **STILL OPEN from #218, and it is Nicolas's call, not a defect to fix unasked:** five cast members
  legitimately declare `UNIT_ICON_SIZE_32x32` (Braulo, Wolfram, Meesmickle, Baxby, Lupin — monster
  donors). `PutUnitSprite` draws a 32x32 at `y-16`, so in the unit list's 16px row pitch their art
  reaches into the row above (visible on the fixed frames). Vanilla never hits this — no vanilla
  PLAYER unit is 32x32. Cosmetic only.
- **The custom SMS id budget is nearly gone — guarded, not raised (#225, PR #226).** `GetInfo` masks every id with `0x7F`,
  so an id ≥ 128 silently renders a VANILLA sprite — and the mask is NOT the array bound
  (`gUnitSpriteSlots` is `u8[0xD0]`), so nothing downstream can catch it. Vanilla ships 107 rows and
  `CUSTOM_SMS_BASE = 107` ⇒ the whole budget is ids **107–127**. **Live: 126 used, 2 left**, and
  **ch05's Basil + Sahnar are exactly those two.** `_append_wait_rows` is now the only way to add a
  wait row; it fails the build naming the id + unit, and prints headroom. Raising the ceiling for
  real is deliberately NOT done — that means widening the mask and auditing every `UseUnitSprite` /
  `StartUiSMS` / `StartWorldMapSMS` caller.
- **`recordunitlist` is the new fast boot for roster screens** (#218). `tools/playtest/run.sh
  recordunitlist` on a `make TESTCH=1` ROM opens the Character list ~30s from New Game, navigates
  semantically off `gMapMenuItems[0]` (overrideId `0x6E`), shoots every page, and dumps SMS geometry
  + the shared 0x40-slot VRAM budget on both sides. FAILs if the two `UseUnitSprite` counters cross.
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

### 1. #222 workstream 1 ONLY — the playtest matrix runner

Codex's tooling epic. **Agreed scope: take workstream 1 (one command runs the live regression
matrix, each ROM config built at most once, compact verdict table, artifacts on disk) and defer
workstreams 2–4** (state inspector, declarative scenario manifests, pre-build validation). ch05 will
run that matrix repeatedly, which is what justifies buying it now.

### 2. ch05's build work (#25) — with #222 held open on purpose

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

- **No open PRs and no live feature branch.** `main` is `5e8c1cf`, level with `origin/main`.
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
PT_HOST_CHAPTER=5 tools/playtest/run.sh ch04cottage        # GATE: visit (1,11) -> line plays, door shuts
PT_HOST_CHAPTER=5 tools/playtest/run.sh recordch04cottage  # the cottage's 5 boxes, in motion
PT_HOST_CHAPTER=5 tools/playtest/run.sh ch04snag           # GATE: chop the snag -> (4,9) is a bridge
tools/playtest/run.sh controller_turn                      # GATE: the #220 controller contract
tools/playtest/make_gif.py <scenario> <tag> --name <out> --fps 14   # frames -> docs/demo/<out>.gif

make CAMPAIGN=rime-of-the-frostmaiden CH04BOOT=1 fireemblem8.gba -j$(nproc)   # ch04 fast-boot
make CAMPAIGN=rime-of-the-frostmaiden TESTCH=1 fireemblem8.gba -j$(nproc)     # the battle-anim bench
tools/playtest/run.sh recordunitlist                  # GATE: the Character list + the SMS budget
PT_CHAR=baxby tools/playtest/run.sh recordanim        # any cast member's banim; then make_gif
python3 tools/split_pose_sheet.py <sheet>.png <anim>/.src idle windup hit   # sheet -> poses
python3 tools/poses_to_feditor.py <anim_dir>          # poses.yaml -> the FEditor frames
python3 tools/banim_paint.py edit|apply <anim_dir>    # hand-paint what the shrink cannot carry

# Required before claiming a change is finished
python3 -m unittest discover -s tools -p 'test_*.py'
make check
git diff --check
```
