# Handoff - Manchego Stars live state

`HANDOFF.md` is live state only. Settled decisions live in `docs/decisions.md`; operating rules
live in `CLAUDE.md`/`AGENTS.md`; issue scope and backlog live in GitHub. Before a context rollover,
warn Nicolas, refresh this file, and begin a fresh instance — don't rely on auto-compaction.

## Current state

- **Environment: Nicolas is on his Mac. ROM builds, `verify_text` and mGBA playtests are LIVE.**
- **Cross-agent continuity:** Nicolas uses Codex only between Claude sessions. Codex must leave an
  explicit HANDOFF entry naming what it changed, the active branch/PR and commit state, verification
  actually run, and the exact next step so Claude can resume without re-deriving anything. Per
  Nicolas's request, Codex uses ordinary short-lived feature branches in this checkout, one at a
  time; **do not create worktrees unless Nicolas explicitly changes that instruction.**
- **ch04 (#24) is BUILT, WON, FILMED and CLOSED — one authored line excepted.** PR #219 and PR #221
  are merged (`fd6f34a`, `3b64ffc`); `main` carries all of it. The only ch04 work left is **the
  second village's line at (1,11)**, which needs Nicolas — #24 is reopened to hold it (item 3 below).
- **ch04's ART IS COMPLETE — #206 is closed (PR #217, `b1de7ae`).** Baxby fights as an axe-beak and
  Lupin as a wolf; **every cast member now fights as itself**, none as someone else's class.
- **The playtest driver is state-driven now (#220 → PR #221).** `tools/playtest/controller.lua` is a
  PURE classifier/legal-action enumerator (observe → classify → enumerate → one guarded input →
  verify postcondition → JSON trace); `harness.lua` owns the mGBA-facing observer. Menus are read
  semantically (`MenuProc.menuItems[] → MenuItemProc.def → MenuItemDef.overrideId`; Talk `0x5A`,
  Wait `0x6B`, End Phase `0x78`), dialogue A fires only under `gProcScr_TalkWaitForInput`, and an
  unknown state **fails closed with no recovery button**. **Standing rule from Nicolas: no
  brute-force, row-probing or cadence input in a scenario — reproducible is not the same as
  justified.** Contract ADR in `decisions.md`; retired phrasings are in `check.py DEAD_CONCEPTS`.
- **THE FIND OF THE SESSION, AND IT IS A TRAP THAT WILL RECUR: FE8 HAS A SECOND PALETTE PATH.**
  Beyond the class-keyed redirect in `GetBanimPalette` (the RBG cyan fix), there is a
  per-**CHARACTER** palette keyed on character × CLASS (`gAnimCharaPalConfig`), applied **after**
  the anim's own palette loads — so it silently overwrites it. Our cast wears vanilla character
  SLOTS, so a unit whose slot is a character vanilla gave a personal palette **for the very class
  that unit deploys as** gets repainted. Baxby rides FORDE (`[CLASS_CAVALIER -> 0x57]`) and deploys
  as a Cavalier: exact match, so his axe-beak palette was thrown away and the bird drawn in Forde's
  green. **Lupin escaped by pure luck of his slot** (Duessel's personal palettes are all magic
  classes), which is why this survived his PR. Fixed campaign-agnostically by
  `_patch_banim_unique_pal_custom_guard`; guarded by `check_engine_guards_present`. **Every future
  custom-anim unit is now covered whatever slot it lands on — #25's Basil and Sahnar included.**
  Full ADR in `decisions.md` §Art & Audio.
- **The debugging lesson is the transferable half, and it is in the ADR: SYMMETRY KILLS
  HYPOTHESES; THE SWAP LOCATES THE FAULT.** Baxby's assets verified clean at *every* offline stage
  — palette bytes, sheet PNGs, PNG→4bpp round trip, packing collisions, OAM/`attr2` ranges, mode
  tables, frame commands, and a full engine-accurate reassembly of every frame from sheet+OAM (0
  mismatched pixels, both units). None of it found the bug. What did: **giving Baxby LUPIN's assets
  and rebuilding** — the wolf rendered corrupt in Baxby's colours, proving in one run that the
  fault was the SLOT, not the art, and pointing at a palette rather than tiles. When two units
  differ only in which one works, stop auditing the broken one's data and swap them.
- **Corollary now in §Operational Gotchas: a render from the frame PNGs proves the ART; only the
  ROM proves the TILING and the PALETTE.** A preview GIF and the in-game sprite are separated by a
  whole stage (tiles → sheets → OAM → VRAM under a palette the engine chooses). "The GIF looks
  right but the ROM doesn't" is not a contradiction — it *localises* the fault to that stage.
- **Baxby's anim, for reuse:** imported path (his attack is travel), ground-aligned throughout
  (**where a wolf leaps, a bird runs**), middle pose played twice at two positions as a run-up.
  Cadence off `banim_bae_at1` (FE8's ground charger — crosses on its legs, walks back), with every
  horse sound deliberately unused. Body height **50**, Nicolas's pick from a 44/50/56 render beside
  Lupin and Pinky. Three **reserved** palette colours: unreserved, the median cut spent all 15 slots
  on one tan ramp and the saddle, crest and eye vanished.
- **`split_pose_sheet` handles CASCADED sheets** (poses overlapping on both axes with no gutter):
  splits on ink connectivity, merges detached flecks into the nearest pose, and **masks each crop
  to its own ink** — without which every pose tows a slice of its neighbour. Lupin's sheet still
  re-splits byte-identically. Rules in `decisions.md` §Art & Audio.
- **ch05 "The Elven Tomb" (#25) — DIALOGUE COMPLETE AND MERGED** (PR #196). 15 slots, all
  `status: locked`. Still owed: map + placement, text insertion → `verify_text`, `--ch05-boot`
  playtest, `enemy_class_reskins` + FE-Repo imports, Basil/Sahnar STAT_DONORs, and the five
  no-Lupin conditionals (they ride Stage 4's `variant_beat`, not a second mechanism).
- **ch04 mechanics all still hold** and are unchanged this session: the parley converts the pack
  **in place** with the ally count scaling to survivors (#203); the Lonelywood village hands over
  the Iron Axe (#205); the snag falls into a bridge (#214); per-chapter goal ids (#207); the rout
  and both endings are filmed and winnable (#204).
- Parity/difficulty engine is four-dimensional (`tools/difficulty.py`); `make difficulty CH=chNN`.
  **#24's spatial/difficulty pass must account for Lupin's leader tile moving `[0,0]` -> `[2,1]`.**
- **Winter forest fidelity is an invariant (#193).**

## NEXT SESSION — the chibi bug, then ch05

**Everything below is on a GitHub issue with its own diagnosis. Start from the issues, not here.**

1. **#218 — the whole cast's unit-list chibi portraits render solid BLACK.** Spotted by Nicolas,
   untouched so far. The asset is fine (verified: 32×32, full 16-index spread), so it is the same
   *shape* as #206 — correct data, wrong render. Check whether the unit-list screen is a **third**
   palette path before assuming an injection offset; the swap test (a vanilla character's chibi on
   the same screen) localises it in one run.
2. **ch05 "The Elven Tomb" (#25) — the build work.** Dialogue is merged; owed are map + placement,
   text insertion → `verify_text`, `--ch05-boot` playtest, `enemy_class_reskins` + FE-Repo imports,
   Basil/Sahnar STAT_DONORs, and the five no-Lupin conditionals. Hosting ch05 also retires ch04's
   `dev_placeholder_scene()` terminator.
3. **The second village at (1,11) — the one ch04 item that needs NICOLAS** (#24, reopened for it).
   Vanilla's second village is pure Lute recruit dialogue (zero lore), so **there is nothing to
   copy** — whatever goes there is ours. He wants "at least a lore drop or a hint". Mine the
   Frostmaiden book + the DM notes for Lonelywood material FIRST (`decisions.md` → story sources of
   truth), then run the `dialogue-pass` skill with him rather than drafting solo. Its cottage is
   currently unwired, so FE8 offers no Visit at all.

Then: **#222** (Codex's playtest-tooling epic — matrix runner first, and it wants a decision about
how much tooling to buy before ch05 rather than after); **#138** config-driven
`inject_chapter(descriptor)`, which ch05's hosting is the natural forcing function for; **#29** world map.

## Answered, don't re-ask

- **The wolves do NOT respawn or relocate during the parley.** A clean `recordch04parley` run sampled
  every wolf before the Talk and immediately after conversion: `0xB0 (2,0)`, `0xB1 (0,2)`,
  `0xB2 (0,0)`, `0xB4 (1,0)`, `0xB5 (0,1)` — unchanged. Later movement is the greens' own phase.

## Codex interlude (2026-08-03) — the state-driven controller (#221) + ch04's scenes re-filmed (#219)

Both PRs are **merged into `main`**; their branches are deleted. Reviewed on 2026-08-05 (Opus):
622 Python tool tests pass, `make check` is `drift check: clean`, and the two committed GIFs were
frame-sampled — the moose exits over the bridge with no void/wrapped-memory edge, and the parley
plays the real Marty/Lupin dialogue with the pack turning green.

- **#221 (closes #220)** — `controller.lua` + the harness rewrite, contract ADR in `decisions.md`,
  retired phrasings registered in `check.py DEAD_CONCEPTS`. Summary in Current state above.
- **#219 (ch04 #24)** — the four scene GIFs re-recorded on the fixed ROM, plus `recordch04moose`
  (now PASSing) and the `marchPartyToward` extraction shared with the `ch04moose` gate.
  `recordCutscene` gained `pre` returning `false, reason` and an `afterPre` cleanup whose lifecycle
  is plain-Lua tested (`recorder.lua`).
- **The moose's escape is authored scene data now, not a reachable endpoint.** `camera_at: [7,4]`
  (the 15-wide map exactly fills the viewport, so centring on the moose at x=11 renders wrapped map
  memory) and `flee_route: [9,7] → [9,8] → [14,14]` emitted as a REDA queue + `MOVE_DEFINED`. ADR in
  `decisions.md` §Operational Gotchas.
- **`test_winter_forest_backfill` no longer needs the injected-file restore** — it reads its vanilla
  inputs through `git show HEAD:`. The restore is still worth doing before `check.py` for speed.
- **One gap this review found: #24 was closed with the second village's line still unwritten.** The
  issue is reopened carrying exactly that item; everything else on ch04 is genuinely done.
- Toolchain note from the bootstrap: `tools/setup-toolchain.sh` omits upstream's helper-tool build,
  so a fresh checkout also needs `fireemblem8u/build_tools.sh` (`scaninc`, `jsonproc`). Not patched.

## This session (2026-08-03, Opus — the bird stopped fighting as a horseman, and the palette had a second door)

- **#206 CLOSED (PR #217).** State above; ADR in `decisions.md` §Art & Audio.
- **Three pipeline rules recorded** alongside it: cascaded sheets split on ink; a subject with ONE
  dominant hue must **reserve its identity colours** (reserve what carries IDENTITY, not what
  carries volume); and **read an arc's fixed points off already-approved anims** — the foe's near
  edge (x≈73) and a grounded mount's ground line (y=141) were measured off Lupin's and Pinky's
  shipped frames, not invented.
- **ch04's GIFs re-recorded** on the current build (opening, turn-2 reveal, authored parley ending);
  the committed ones filmed a chapter that no longer exists. **PR #219** (`feat/24-ch04-rerecord`)
  also lands a new `recordch04moose` and extracts `marchPartyToward`, shared by the gate and the
  recorder so they cannot disagree about how the clearing is reached.
- **A real mistake worth repeating so it isn't repeated:** the extracted march first stopped when a
  unit *entered* the clearing. An AREA is polled when an action **ENDS**, so a unit standing on the
  tile is a state the beat has not answered yet, not a verdict — stopping there raced the event and
  FAILED a chapter that works. Stop on the **outcome** (the moose exists), use position only as the
  after-the-fact diagnostic. Same family as the ch03 talk-row and `turn()` lessons.
- **Process note from Nicolas, now standing:** get something **lookable** on screen early in a long
  art/build task — don't go silent through tooling and diagnosis and reveal once.

## Previous session (2026-08-02, Opus — the wolf stopped fighting as a horseman)

- **#206's Lupin half (PR #216, `5c20321`)**: imported wolf pounce, cadence off `banim_mdg_at1`,
  **hand-painted spectacles** (`poses.yaml` carries `hand_painted: true`, so `poses_to_feditor`
  refuses to re-render without `--force`). ADR in `decisions.md` §Art & Audio.
- **Still unfilmed for Lupin:** the dodge (modes 7/8 — he one-shot the Soldier, so nothing
  countered) and the lance/unarmed slots (repointed in the same AnimConf, correct by construction).

## Previous sessions (2026-07-31 → 08-02, Opus — ch04 became playable end to end)

- #203 the in-place pack conversion, #204 the rout + both endings, #205 the Lonelywood village,
  #207 per-chapter goal ids, #214 the snag→bridge, #208 the reveal dialogue into YAML. Each closed
  with its own ADR/gotchas already moved into `docs/decisions.md` — **read them there, not here.**
- The durable ones most likely to bite again: **read decomp event data through `git show HEAD:`,
  never the built tree**; **post-injection goal ids cannot be read from HEAD or the working tree —
  run the injector and read the result**; **a failing playtest may be the WRONG ROM** (a
  `CH04BOOT=1` build cannot reach ch02's map); **`turn()` is not the signal that a turn's
  reinforcements exist** — wait for a UNIT from the wave; and **`check.py` is ~22s clean vs ~4min on
  a freshly-built tree** (restore the injected files first).

## Working tree - do not lose or revert

- **No open PRs and no live feature branch.** `main` is `fd6f34a`, level with `origin/main`.
- `fireemblem8u` is dirty from injected/generated build artifacts. **Never commit its submodule
  pointer.** Restore the injected decomp files before `check.py`/the pre-commit hook so it runs in
  ~22s instead of ~4min: `git -C fireemblem8u restore src/data/chapter_settings.json data/data_8B363C.s`.
- Untracked local/session files (`.agents/`, `AGENTS.md`, `skills-lock.json`, `map-review/`,
  `review/`) are intentionally not versioned; leave them alone. `map-review/` is the render scratch
  Nicolas opens in Preview — deliverable art goes to `docs/demo/` and is COMMITTED so he can view
  it on GitHub. `tools/key_magenta.py` is **gitignored** (#178).
- **HANDOFF.md is authored on `main` ONLY** — gated by `check.py check_handoff_only_on_main`.
  A branch may leave it untouched or sync it to main's tip; it may not author its own. If the guard
  fires: `git checkout main -- HANDOFF.md` on the branch. Refresh HANDOFF on main *after* a merge.
- **If `.git/config` ever shows `core.bare=true` or a `t`/`t@t` identity, a git-shelling test escaped
  its fixture.** Repair: `git config --local core.bare false`, `user.name "Nicolas"`,
  `user.email "nicolas.vivas94@gmail.com"`.
- **The `GIT_*`-in-a-hook footgun is fixed on both sides** (`497d8a2`): any new git-shelling test
  must use a sanitized-env helper. Recipe in `decisions.md` §Operational Gotchas.

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
