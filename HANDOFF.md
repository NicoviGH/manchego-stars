# Handoff - Manchego Stars live state

`HANDOFF.md` is live state only. Settled decisions live in `docs/decisions.md`; operating rules
live in `CLAUDE.md`/`AGENTS.md`; issue scope and backlog live in GitHub. Before a context rollover,
warn Nicolas, refresh this file, and begin a fresh instance — don't rely on auto-compaction.

## Current state

- **Environment: Nicolas is on his Mac. ROM builds, `verify_text` and mGBA playtests are LIVE.**
- **ch04 "The White Moose" (#24) — its scenes have now been WATCHED, and that is what mattered.**
  The chapter booted (#200) and stopped soft-locking (#201) in the previous session; this one
  filmed the beats and found **six defects that `smoke_ch04` could never see**, because an idling
  party never triggers them and a beat firing at the wrong moment is not a soft-lock. All six are
  fixed and merged (`d14ee84`), each behind a guard that fails the BUILD rather than a playtest:
  the moose sighting firing for MONSTERS (AREA has no faction check); the moose then HANGING the
  chapter on a cliff-sealed flee tile; the moose rendering as a stock hound (its art was declared,
  committed, and injected by nobody); Lupin rendering as NOTHING (correct at every layer, standing
  on the one pack tile outside fog vision); fogged map tiles showing summer grass; and the goal
  banner overflowing. Three beat GIFs are in `docs/demo/`.
- **The method is the transferable part: read DATA, not frames.** `ch04sprites` prints the unit
  arrays, `gBmMapFog`, `gUnitSpriteSlots[]` and the SMS VRAM cursors — that one scenario separated
  "wrong sprite" from "never injected" from "never drawn" in a single run, after cropped frames had
  twice pointed the wrong way. `assert_scripted_move_reachable`, `assert_declared_map_sprites_injected`
  and `goal_window_body` now catch those three classes at build time.
- **ch04 is NOT finished. Six issues carry the rest**: **#203** the parley re-loads the pack on its
  spawn tiles instead of converting it in place (diagnosed: five generics share one pid, and
  `GetUnitFromCharId` returns the first match scanning blue->green->red, so repeated `CUSN` re-finds
  the wolf already converted — the fix is distinct pids); **#204** `clear_ch04` never routs, so
  **neither ending branch has been filmed**; **#205** the village is unbuilt and ch04's Iron Axe is
  unobtainable, leaving the chapter with no material reward; **#206** Lupin has no battle anim and
  fights as a stock red Cavalier; **#207** hosted chapters share vanilla's goal message ids, so ch02
  and ch04 overwrite each other's objective text TODAY; **#208** the locked reveal dialogue still
  lives in `build_campaign.py`.
- **#206 is DECIDED and scoped up (Nicolas, 2026-08-01): do Lupin's battle anim AND Baxby's.**
  Baxby has the same defect for the same reason — he rides a Cavalier slot so the axe-beak can be
  mounted, and he is not among the eight finished PC anims, so the giant bird also fights as a man
  on a horse. Two animal mounts, one problem twice. Lupin has a free donor (`CLASS_MAUTHEDOOG`'s
  vanilla anim IS a wolf); Baxby likely needs an FE-Repo import. Per-character binding already
  exists (`pcs/pinky.yaml` `_u25`), so neither needs a new class. **Basil and Sahnar stay ch05
  work (#25)** — not part of this.
- **One decision still Nicolas's**: whether #203's in-place conversion may drop the green Lycanroc
  class upgrade (in-place `CUSN` changes faction, not class, so the pack would stay Mauthe Doogs
  wearing the green NPC palette).
- **ch05 "The Elven Tomb" (#25) — DIALOGUE COMPLETE AND MERGED** (PR #196). 15 slots, all
  `status: locked`. Still owed: map + placement, text insertion → `verify_text`, `--ch05-boot`
  playtest, `enemy_class_reskins` + FE-Repo imports, Basil/Sahnar STAT_DONORs, and the five
  no-Lupin conditionals (they ride Stage 4's `variant_beat`, not a second mechanism).
- **Winter forest fidelity is an invariant (#193).** Note the sibling lesson from this session: the
  invariant covered the LIT half of the tileset palette only.
- Parity/difficulty engine is four-dimensional (`tools/difficulty.py`); `make difficulty CH=chNN`.
  **#24's spatial/difficulty pass must account for Lupin's leader tile moving `[0,0]` -> `[2,1]`**
  (Nicolas's condition on approving that swap).
- **PC battle anims — 8 of 8 DONE** for the founding cast. Lupin is NOT among them (#206).
- **Recruit art shipped** (portraits + map sprites): Basil/Oddish (#179), Lupin + Sahnar (#181).
  Basil and Sahnar are marked `wiring: pending` in YAML so the new sprite guard can tell a tracked
  deferral from a silent one; their wiring is #25 work.


## This session (2026-07-31/08-01, Opus — the scenes got watched)

- **Filmed the opening, the turn-2 reveal and the wolf parley** (`recordch04open`,
  `recordch04reveal`, `recordch04parley`), plus `ch04moose`, `ch04sprites` and `clear_ch04`.
  `make_gif` grew `--from-shot/--to-shot` to trim a no-checkpoint recording's boot lead-in.
- **Every defect this session came from watching, and three came from being WRONG first.** Worth
  repeating because each was a confident wrong turn:
  - a cropped frame twice suggested a sprite was broken when it was never *drawn*; the unit arrays
    settled it in one run.
  - the ch03 talk driver was copied blind and took command-menu row 0 — correct only because ch03's
    Trex is GREEN. Lupin is a RED adjacent enemy, so row 0 is ATTACK, and the first parley run
    filmed Marty duelling the wolf he is meant to talk to.
  - gating "the Talk started" on `ProcScr_StdEventEngine` produced a confident false positive; that
    proc is live during ALL map/turn event processing (harness.lua says so in its own comment). The
    search now verifies by OUTCOME (Lupin flips blue) and reports a different row.
- **A background task exiting 0 is NOT `make` succeeding.** Reported a build as done when it had
  failed on `undefined reference to MapPaletteSnow` — a fog-palette change that skipped the
  palette's symbol registration along with its copy. Check the tool's own output, not the wrapper's.
- **Restored vanilla's objective wording** (Nicolas: "it should never have been altered in the first
  place"). FE8 never prints "rout" as an objective — its vocabulary is Defeat/Seize/Survive, and the
  word only appears as "Route +/-" and "en route". Importing community vocabulary also overran a
  window vanilla had sized at 12 chars for its own words.
- **Moose flees SOUTHEAST** now — away from the party (Nicolas's call), with all seven direction
  references reconciled including two lines of locked dialogue.


## Previous session (2026-07-30 pm, Opus — build-speed gates met + ch04 Stage 3 art)

- **`pre_recruit_roles` — a cast member may wear a different look before he joins you** (the ch04
  Stage 3 mechanism, reused by ch05's Basil/Sahnar): red while hostile, the finalized grey once
  recruited. A second standard-palette sheet **derived at build time** from the cast sheet by an
  explicit index→SMS-role map, worn only while `UNIT_FACTION != FACTION_BLUE`. No committed derived
  asset, so pixel edits to the grey sheet flow into the red one. ADR in `decisions.md` (Art & Audio).
- **Two durable lessons captured** (both `decisions.md`): a **luminance recolour can collide two
  ROLES on one index** (Lupin's inner-ear wedges were body-coloured for weeks); and the
  **hook/`GIT_*` footgun** (see Working tree below).
- Fixed a latent `map_sprite_swapper` bug: the idle frame width was hardcoded to 16, so any 32×32
  idle (this sheet, Sahnar's) sliced into interleaved half-rows.
- **`vanilla_scene.py` was mining the WORKING TREE, not HEAD** (fix `46f8b12`). **Every "vanilla
  says…" number mined on a built tree before that fix is suspect** — re-mine before citing one.

## NEXT SESSION — finish ch04's slice; the beats that remain are the ones that end it

`main` is clean and green; `feat/24-ch04-scenes` is merged and deleted. **Start from the issues,
not from this file** — #203-#208 each carry their own diagnosis so none of it has to be re-derived.

1. **#204 `clear_ch04`** first: it blocks BOTH endings, the last unwatched beats, and one of them
   (the no-Lupin fallback) is the path the difficulty model explicitly prices. Fog is already
   handled (`bmtarget.c` gates targeting on `gBmMapFog`; the scenario zeroes
   `chapterVisionRange`), and that did NOT fix it — instrument `teleportToFiringTile` /
   `chooseAttack` next.
2. **#203 the pack conversion** — visible in the shipped parley GIF, and fully diagnosed.
3. **#205 the village** — ch04 currently has no material reward at all.
4. **#207 the goal-id collision** — it is corrupting ch02's objective text right now, and it is
   cross-chapter, so it grows with every rout chapter added.
5. **#206 Lupin + Baxby battle anims** — decided and wanted; start with Lupin's free Mauthe Doog
   donor to prove the per-character binding, then Baxby.
6. Then **#208**, and re-record the opening + reveal on the fixed ROM (winter BG, visible Lupin,
   winterized fog).

Then: **ch05's build work** on #25; **#138** config-driven `inject_chapter(descriptor)`; **#29**
world map.


## Working tree - do not lose or revert

- `fireemblem8u` is dirty from injected/generated build artifacts. **Never commit its submodule
  pointer.** To run the map/forest tests cleanly after a build, restore the injected decomp files:
  `git -C fireemblem8u restore src/data/chapter_settings.json data/data_8B363C.s`.
  (`test_winter_forest_backfill` fails on a built tree without this — it is the documented
  artifact, not a regression.)
- **No outstanding branches.** `.claude/worktrees/` is empty. Merged: #197 build-speed, #198 ch04
  Stages 1–3, #199 review cleanups, #200 the host-slot fix, #201 the banim arming fix, #202 the
  ch04 scenes + the six defects above.
- Untracked local/session files (`.agents/`, `AGENTS.md`, `skills-lock.json`) are intentionally not
  versioned; leave them alone. `tools/key_magenta.py` is **gitignored** (#178).
- **HANDOFF.md is authored on `main` ONLY** — gated by `check.py check_handoff_only_on_main`.
  A branch may leave it untouched or sync it to main's tip; it may not author its own. If the guard
  fires: `git checkout main -- HANDOFF.md` on the branch. Refresh HANDOFF on main *after* a merge.
  ADR in `decisions.md` §Working Conventions.
- **If `.git/config` ever shows `core.bare=true` or a `t`/`t@t` identity, a git-shelling test escaped
  its fixture** — that is the signature. `core.bare=true` makes the main tree refuse `git add` with
  "must be run in a work tree". Repair: `git config --local core.bare false`,
  `user.name "Nicolas"`, `user.email "nicolas.vivas94@gmail.com"`.
- **The `GIT_*`-in-a-hook footgun is fixed on both sides** (`497d8a2`): a test fixture written the
  obvious way (`subprocess.run(['git', …], cwd=repo)`) is NOT isolated — git exports
  `GIT_DIR`/`GIT_INDEX_FILE`/`GIT_WORK_TREE` during a hook and they beat `cwd`. Any new git-shelling
  test must use a sanitized-env helper (`-C <repo>`, `env` stripped of `GIT_*`,
  `-c core.hooksPath=/dev/null`); `check.py:_git` does the same. `decisions.md` Operational Gotchas
  has the recipe and how to prove it against a decoy repo.

## Quick commands

```sh
make difficulty CH=ch04                    # parity/difficulty read (all from HEAD)
PT_HOST_CHAPTER=5 tools/playtest/run.sh ch04sprites   # WHO is on the map: unit arrays, fog, SMS slots
PT_HOST_CHAPTER=5 tools/playtest/run.sh ch04moose     # the sighting is player-only, both halves
PT_HOST_CHAPTER=5 tools/playtest/run.sh recordch04parley  # the wolf parley, in motion
make CAMPAIGN=rime-of-the-frostmaiden CH04BOOT=1 fireemblem8.gba -j$(nproc)   # ch04 fast-boot
PT_HOST_CHAPTER=5 tools/playtest/run.sh smoke_ch04                            # ch04 stability net

# Required before claiming a change is finished
python3 -m unittest discover -s tools -p 'test_*.py'
make check
git diff --check
```
