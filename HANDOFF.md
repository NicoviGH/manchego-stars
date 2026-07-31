# Handoff - Manchego Stars live state

`HANDOFF.md` is live state only. Settled decisions live in `docs/decisions.md`; operating rules
live in `CLAUDE.md`/`AGENTS.md`; issue scope and backlog live in GitHub. Before a context rollover,
warn Nicolas, refresh this file, and begin a fresh instance — don't rely on auto-compaction.

## Current state

- **Environment: Nicolas is on his Mac. ROM builds, `verify_text` and mGBA playtests are LIVE.**
- **ch04 "The White Moose" (#24) — the chapter BOOTS AND PLAYS for the first time (#200,
  merged `87cfc8c`).** It never had: the slot presented our 15×15 map while running vanilla
  chapter **5X**'s roster and scripts underneath it. FE8 inserts ch5X at **slot 5**, so the slot
  index stops tracking the chapter number there — slot 5 ships `mapEventDataId` → `Ch5XEvents`,
  while `inject_ch04` fills the `Ch5*` symbols. `_retarget_host_chapter` rewrote the map ids and
  never the event data id. Now verified in-engine on `--ch04-boot`: PREP opens, 9 units deploy on
  exactly the authored `deploy_slots`, the 10-unit monsters-only opening loads in its authored
  positions, turns advance and enemy phases resolve. ADR in `decisions.md` (Operational Gotchas);
  the runbook step is in `docs/adding-a-chapter.md`.
- **ch04's remaining defect: a turn-4 SOFT-LOCK inside an enemy-phase battle animation**
  (Revenant / Rotten Claw vs Wolfram). State freezes at f020279 and never resumes — confirmed over
  66k further frames, so it is not a slow fog phase. Only reachable now that ch04's own units load.
  Separate root cause from #200; **this is the next debugging task.** Checklisted on #24.
- **`feat/24-ch04-scenes` is OUTSTANDING and needs a rebase onto the new `main`.** Three commits,
  pushed, no PR: the Wyrdeer moose art, Stage 4's authored scenes (Lonelywood opening, parley,
  moose-flees, the branched ending + `variant_beat`), and the `smoke_ch04` stability net. That work
  is good and was never reset — it simply could never run, because ch04 wasn't executing its own
  events. **`smoke_ch04`'s commit message records a WRONG lead** (blaming a party unit on the
  harness's hardcoded `EMPTY_TILE (2,2)`); instrumenting `endTurn` proved (2,2) empty and the cursor
  pinned off-map at y=18 — the real cause was #200. Don't re-follow that lead.
- **ch05 "The Elven Tomb" (#25) — DIALOGUE COMPLETE AND MERGED** (PR #196, squash `3164bcf`).
  15 slots, all `status: locked`, no `draft_script:` left. Roster CLOSED at PARITY, `deploy_limit 9`.
  #25 stays OPEN: map + placement, text insertion → `verify_text`, `--ch05-boot` playtest,
  `enemy_class_reskins` + FE-Repo imports, and Basil/Sahnar STAT_DONORs are all still owed.
- **The no-Lupin branch is TEXT-COMPLETE and WIRING-INCOMPLETE.** Tracked as checklists on
  **#24** (ch04's two beats + the shared branch mechanism) and **#25** (ch05's five). Stage 4 built
  `variant_beat` as the reusable half — ch05's five ride it, not a second mechanism.
- **Winter forest fidelity is an invariant (#193, merged `6a538bc`).** Snowy Bern retiles preserve
  the vanilla artists' forest sequences: the learned per-metatile map in `reskin-learned.json` is
  the sole authority, `gen_map_editor.py` refuses to generate on an unmapped forest variant, and
  `import_map_layout.py` re-checks every protected cell. Ch00–Ch02 backfilled.
- **Warm rebuilds are ~7× faster (#197, merged `06b2fc6`).** Injection rewinds the mtime of every
  decomp file whose bytes come out identical, so `make` skips it: warm rebuild **188s → 28s**, ROM
  byte-identical across clean-without / warm-without / warm-with / clean-with. Both gates the commit
  demanded are in `docs/decisions.md` (Engine & Tech Stack) with the numbers and the staleness proof.
- **Parity/difficulty engine is four-dimensional now** (`tools/difficulty.py`, all read from HEAD):
  enemy pressure + item economy (#170/#172, drops #176/#178) + battlefield dynamics (convertibles +
  reinforcement timing #171/#174, area/zone #177/#178) + **per-unit ROLE check and terrain (#25)**.
  `make difficulty CH=chNN` shows all of it.
- **PC battle anims — 8 of 8 DONE** (braulo, marty, meesmickle, prof-rbg, wolfram, rootis, pinky,
  sclorbo). Sclorbo (#191) added the reusable **BISHOP dual-slot donor** that **Basil (ch05) plugs
  into** (`battle_anim: {clone_from: bishop}` — no new donor work).
- **Enemy battle-anim import pipeline** (#90) + **per-caster charge flash** (#183) shipped;
  spell-palette tint (#168/#169) shipped. ch03 (#23) complete.
- **Recruit art shipped** (portraits + map sprites): Basil/Oddish (#179), Lupin + Sahnar (#181).
  Their build *wiring* (slot, STAT_DONOR, live `battle_anim:`) is ch04/ch05-slice work.

## This session (2026-07-31, Opus — ch04 finally runs)

- **Diagnosed and fixed the host-slot event-data bug (#200).** Method matters for the next one:
  the ROM state was read as **data, not pixels** — `gBmMapSize` (15×15, so the map really was ours
  and the screenshot misled), the live `gUnitArray{Blue,Red,Green}`, and `mapEventDataId` resolved
  through `gChapterDataAssetTable`. The giveaways were `blue [4]` at `x=255` (FE8's not-on-map
  sentinel) and 24 foreign `0x80` reds on coordinates off a 15×15 footprint.
- **`_retarget_host_chapter` now takes a mandatory `event_group`** and repoints `mapEventDataId`
  itself, so a hosted chapter's map and events stay ONE decision instead of two that can silently
  disagree. All four hosted chapters name the group they fill; ch01–ch03 are provably unchanged
  (their explicit value equals vanilla's — asserted), slot 5 is the only one that moves.
  `HostChapterEventGroup` in `tools/test_build_campaign.py` pins the trap and the repoint.
- **The harness no longer hardcodes an "empty" tile.** `endTurn` resolves one against the live map
  via `gBmMapUnit` (the engine's own tile→unit grid, so green bodies count) bounded by `gBmMapSize`.
  The old constant `(2,2)` was only ever true for ch00 and is one of ch04's nine deploy slots — a
  hazard that became real the moment the party started deploying. `gBmMapSize` added to
  `gen_symbols.py`; the `mapUnit*` readers hoisted to their first use rather than duplicated.
- Regression held: `smoke_ch03` still PASSes (clean loss, 21822f). 532 tests, `make check` clean.

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

## NEXT SESSION — ch04's turn-4 soft-lock, then close out the slice

**Read issue #24** (its checklist is the backlog) + the `docs/decisions.md` ch04 ADR.

1. **Debug the turn-4 battle-animation soft-lock** (fresh context recommended — it is a different
   domain: battle anims, platforms, monster classes). Repro:
   `make CAMPAIGN=rime-of-the-frostmaiden CH04BOOT=1 fireemblem8.gba -j$(nproc)` then
   `PT_HOST_CHAPTER=5 tools/playtest/run.sh smoke_ch04` **on the rebased scenes branch** (that is
   where `smoke_ch04` lives). Freeze is a Revenant (Rotten Claw, pid `0xaa`) vs Wolfram exchange;
   all ch04 classes are plain vanilla monster classes with no `skin:`. Worth checking early:
   `battleTileSet 0x15` on slot 5 vs what monster combat expects.
2. **Rebase `feat/24-ch04-scenes` onto `main`** and open its PR — the scenes have still never been
   seen running, because the chapter wasn't executing its own events until #200.
3. **Stage 5** — spatial check + `--ch04-boot` playtest → confirm parity in-engine → PR
   (`Closes #24`). The remaining #198-review guard (message-id uniqueness) must land **before**
   ch05's text insertion (#25), or a double-claim overwrites silently and stays green.

Then: **ch05's now-unblocked build work** (map, placement, text insertion, playtest, reskins,
STAT_DONORs, the five no-Lupin conditionals) on #25; **#138** config-driven
`inject_chapter(descriptor)` (approved, paused for ch04/ch05); **#29** world map.

## Working tree - do not lose or revert

- `fireemblem8u` is dirty from injected/generated build artifacts. **Never commit its submodule
  pointer.** To run the map/forest tests cleanly after a build, restore the injected decomp files:
  `git -C fireemblem8u restore src/data/chapter_settings.json data/data_8B363C.s`.
  (`test_winter_forest_backfill` fails on a built tree without this — it is the documented
  artifact, not a regression.)
- **`feat/24-ch04-scenes` is the one outstanding branch** (3 commits, pushed, no PR) and needs a
  rebase onto `main`. `.claude/worktrees/` is empty. Everything else is merged: #197 build-speed,
  #198 ch04 Stages 1–3, #199 review cleanups, #200 the host-slot fix.
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
make CAMPAIGN=rime-of-the-frostmaiden CH04BOOT=1 fireemblem8.gba -j$(nproc)   # ch04 fast-boot
PT_HOST_CHAPTER=5 tools/playtest/run.sh smoke_ch04                            # ch04 stability net

# Required before claiming a change is finished
python3 -m unittest discover -s tools -p 'test_*.py'
make check
git diff --check
```
