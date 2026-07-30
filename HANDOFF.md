# Handoff - Manchego Stars live state

`HANDOFF.md` is live state only. Settled decisions live in `docs/decisions.md`; operating rules
live in `CLAUDE.md`/`AGENTS.md`; issue scope and backlog live in GitHub. Before a context rollover,
warn Nicolas, refresh this file, and begin a fresh instance — don't rely on auto-compaction.

## Current state

- **Environment: Nicolas is on his Mac. ROM builds, `verify_text` and mGBA playtests are LIVE.**
  The ch05 sessions ran in a Linux web container without the base ROM, and everything needing one
  got parked as "ROM-gated". That was a *where*, not a permanent class — the whole parked list is
  now actionable.
- **ch05 "The Elven Tomb" (#25) — DIALOGUE COMPLETE AND MERGED** (PR #196, squash `3164bcf`).
  15 slots, all `status: locked`, no `draft_script:` left in the chapter. Roster CLOSED at PARITY,
  `deploy_limit 9`. #25 stays OPEN: map + placement, text insertion → `verify_text`, `--ch05-boot`
  playtest, `enemy_class_reskins` + FE-Repo imports, and Basil/Sahnar STAT_DONORs are all still
  owed — and all now buildable.
- **The no-Lupin branch is TEXT-COMPLETE and WIRING-INCOMPLETE.** Tracked as checklists on
  **#24** (ch04's two beats + the shared branch mechanism) and **#25** (ch05's five). Not
  restated here — issues are the backlog.
- **Winter forest fidelity is an invariant (#193, merged `6a538bc`).** Snowy Bern retiles preserve
  the vanilla artists' forest sequences: the learned per-metatile map in `reskin-learned.json` is
  the sole authority, `gen_map_editor.py` refuses to generate on an unmapped forest variant, and
  `import_map_layout.py` re-checks every protected cell. Ch00–Ch02 backfilled.
- **Warm rebuilds are ~7× faster (#197, merged `06b2fc6`).** Injection rewinds the mtime of every
  decomp file whose bytes come out identical, so `make` skips it: warm rebuild **188s → 28s**, ROM
  byte-identical across clean-without / warm-without / warm-with / clean-with. Both gates the commit
  demanded are in `docs/decisions.md` (Engine & Tech Stack) with the numbers and the staleness proof.
- **ch04 "The White Moose" (#24, branch `feat/24-ch04-map`, worktree `.claude/worktrees/ch04-map`)
  — combat host built; REDESIGNED 2026-07-21 into a full chapter. Stage 3 COMPLETE.**
  `inject_ch04` hosts Ch4 on the vanilla Ch5 slot (15×15 snowy retile, fog 3, PREP 9-of-10,
  DefeatAll, `--ch04-boot`, `chain_ch03_to_ch04`), built around the wolf-parley REVEAL on the
  "wolves turn the tide" difficulty model (raw fight above vanilla; the parley discounts it back to
  dead-on vanilla — static ×1.15/×1.19, parley-path clear-load 2.5≈2.6), with the roster mirroring
  the vanilla-Ch4 twin 1:1. Full design + staged checklist: **issue #24's 2026-07-21 comment** +
  the `docs/decisions.md` ch04 ADR (on the branch), both authoritative. Committed stages:
  - `cef0419` **Stage 1b** — `inject_ch04` wired to the twin-realigned roster.
  - `8f2f784` **Stage 2a** — reusable `recruit_initial_faction(unit)` (GREEN Colm/Trex/Basil vs RED
    Joshua/Lupin/Sahnar, opt-in via YAML `recruit.initial_faction`) + Lupin cast wiring on the
    collision-free `Duessel` slot (STAT_DONOR = Kyle).
  - `dbf86c6` **Stage 2b** — `talk_recruit_wiring` extracted out of `inject_ch03`
    (faction-parameterized; ch03 green Trex, ch04 red Lupin, ch05 Basil/Sahnar all ride it) + the
    Marty→Lupin parley + Marty force-deployed via vanilla's `ForceDeploymentEnt` data path.
  - `2253cec` **Stage 2c** — the turn-2 REVEAL cutscene (stub lines; Stage 4 finalizes).
  - `3286d4a` — the no-Lupin fallback for the ending scene (text only, see above).
  - `8cdb904` **Stage 3 — the wolf art, signed off.** The parleyed pack rides its own appended
    class `CLASS_MTD_LYCANROC_PACK` (0x83, a Mauthe Doog clone → parity untouched) wearing a
    glasses-less Lycanroc sheet; the red pack keeps `CLASS_MAUTHEDOOG`, so the swap reads as an
    upgrade, not a recolour. Lupin needed a **new reusable mechanism** — see below.
- **Parity/difficulty engine is four-dimensional now** (`tools/difficulty.py`, all read from HEAD):
  enemy pressure + item economy (#170/#172, drops #176/#178) + battlefield dynamics (convertibles +
  reinforcement timing #171/#174, area/zone #177/#178) + **per-unit ROLE check and terrain (#25)**.
  The role check exists because the aggregate hid a real inversion: ch05 read "PARITY (within band)"
  while the white moose out-threatened the boss 1.7×. `make difficulty CH=chNN` shows all of it.
- **PC battle anims — 8 of 8 DONE** (braulo, marty, meesmickle, prof-rbg, wolfram, rootis, pinky,
  sclorbo). Sclorbo (#191) added the reusable **BISHOP dual-slot donor** that **Basil (ch05) plugs
  into** (`battle_anim: {clone_from: bishop}` — no new donor work).
- **Enemy battle-anim import pipeline** (#90) + **per-caster charge flash** (#183) shipped;
  spell-palette tint (#168/#169) shipped. ch03 (#23) complete.
- **Recruit art shipped** (portraits + map sprites): Basil/Oddish (#179), Lupin + Sahnar (#181).
  Their build *wiring* (slot, STAT_DONOR, live `battle_anim:`) is ch04/ch05-slice work.

## This session (2026-07-30 pm, Opus — build-speed gates met + ch04 Stage 3 art)

- **`pre_recruit_roles` — a cast member may now wear a different look before he joins you** (the
  ch04 Stage 3 mechanism, reused by ch05's Basil/Sahnar). Nicolas's call was red while hostile,
  the finalized grey once recruited; neither existing tool does that (`FACTION_TINTED_CAST` trades
  the bespoke palette away → he'd join BLUE; `gMapPaletteOverride` is unconditional → he'd be grey
  while an enemy, which FE reads as *already acted*). One sheet can't serve both — his grey ramp
  sits on cast indices that the enemy palette turns maroon/pink/near-white and **bright green** at
  11 — and no cast-palette entry is free. So: a second standard-palette sheet, **derived at build
  time** from the cast sheet by an explicit index→SMS-role map, worn only while
  `UNIT_FACTION != FACTION_BLUE`. No committed derived asset, so pixel edits to the grey sheet flow
  into the red one. ADR in `decisions.md` (Art & Audio).
- **Two durable lessons captured** (both `decisions.md`): a **luminance recolour can collide two
  ROLES on one index** — Lupin's inner-ear wedges had been painted body-colour for weeks because the
  source's ear pink and its light fur both landed on cast 3; and **the hook/`GIT_*` footgun recurred**
  (see Working tree below).
- Fixed a latent `map_sprite_swapper` bug: the idle frame width was hardcoded to 16, so any 32×32
  idle (this sheet, Sahnar's) sliced into interleaved half-rows.

## Previous session (2026-07-30 am, Opus — ch05 red-penned, locked, merged)

- **Both endings red-penned with Nicolas over two passes, then LOCKED, then merged.** `0x9C9` is 19
  boxes, `0x9CA` 10, `0x9C6` 1. Wolfram (not RBG) repots Basil out of an elven helm salvaged from
  the arena he opened in `0x9BE`; RBG takes the told-you-so that pays ch02's locked "my rats whisper
  coin off Bremen"; the coin objection left both endings; Braulo closes on appetite, not arithmetic.
- **`vanilla_scene.py` was mining the WORKING TREE, not HEAD** (fix `46f8b12`). `texts/texts.txt` is
  the first entry in `PATCHED_DECOMP_FILES`, so after any `make` the vanilla pacing benchmark would
  hand our own injected lines back as vanilla's. Proven, not theorised: the tree's copy is
  +501/−1387 against HEAD. **Every "vanilla says…" number mined on a built tree before this fix is
  suspect** — re-mine before citing one. Test coverage had followed the bug (five tests on
  `scene_text_ids`, none on `load_messages`); two added and verified non-vacuous.
- **Three review nits cleared**: `vanilla_boss_bar()` hoisted out of the per-boss loop; `render()`
  no longer enumerates staging codes (proven behaviour-identical over all 3403 messages);
  `_apply_personal` short-circuits.
- **Branches pruned**: `feat/25-ch05-content` (merged) and the orphaned
  `claude/mobile-app-token-context-u2psep` — verified a strict ancestor of the ch05 branch first, so
  nothing was lost. The ch05 worktree is removed.

## NEXT SESSION — close out ch04 (`feat/24-ch04-map`)

Design is LOCKED. **Read issue #24's 2026-07-21 comment** + the `docs/decisions.md` ch04 ADR (both
on the branch). Work in `.claude/worktrees/ch04-map`. `Closes #24`:

1. ~~Stage 1b / 2a / 2b / 2c / 3~~ — **DONE**, see Current state.
2. **Stage 4 — RESUME HERE — scenes** (off the ch03 template): Lonelywood opening, moose-flees,
   real ending (replace `dev_placeholder_scene()`); finalize Lupin's death line + all ch04 text via
   `dialogue-pass`. **Includes wiring the no-Lupin fallback for `chapter_end` boxes 1+3.**
   Mine vanilla's pacing with `tools/vanilla_scene.py` — it (and now its tests) read HEAD, so the
   numbers are trustworthy on a built tree.
3. **Stage 5 — spatial check + `--ch04-boot` playtest** → confirm parity in-engine → PR.

Then: **ch05's now-unblocked build work** (map, placement, text insertion, playtest, reskins,
STAT_DONORs, the five no-Lupin conditionals) on #25; **#138** config-driven
`inject_chapter(descriptor)` (approved, paused for ch04/ch05); **#29** world map.

## Working tree - do not lose or revert

- `fireemblem8u` is dirty from injected/generated build artifacts. **Never commit its submodule
  pointer.** To run the map/forest tests cleanly after a build, restore the injected decomp files:
  `git -C fireemblem8u restore src/data/chapter_settings.json data/data_8B363C.s`.
- Untracked local/session files (`.agents/`, `AGENTS.md`, `skills-lock.json`) are intentionally not
  versioned; leave them alone. `tools/key_magenta.py` is **gitignored** (#178).
- **HANDOFF.md is authored on `main` ONLY** — gated by `check.py check_handoff_only_on_main`
  since 2026-07-30. A branch may leave it untouched or sync it to main's tip; it may not
  author its own. If the guard fires: `git checkout main -- HANDOFF.md` on the branch.
  Refresh HANDOFF on main *after* a merge. ADR in `decisions.md` §Working Conventions.
- **`.git/config` IS CURRENTLY DAMAGED — please repair it.** On 2026-07-30 `test_check_handoff.py`'s
  git fixture ran against the LIVE repo from inside pre-commit (the `GIT_*` footgun below), leaving:
  `core.bare=true`, `user.name=t`, `user.email=t@t`. Committing still works and every commit so far
  is correctly authored, but the next one would be attributed to `t <t@t>`. The classifier blocks
  `git config` writes, so run this by hand:
  `git config --local core.bare false && git config --local user.name "Nicolas" && git config --local user.email "nicolas.vivas94@gmail.com"`
- **The `GIT_*`-in-a-hook footgun recurred and is now fixed on both sides** (`497d8a2`): a test
  fixture written the obvious way (`subprocess.run(['git', …], cwd=repo)`) is NOT isolated —
  git exports `GIT_DIR`/`GIT_INDEX_FILE`/`GIT_WORK_TREE` during a hook and they beat `cwd`. Any new
  git-shelling test must use a sanitized-env helper (`-C <repo>`, `env` stripped of `GIT_*`,
  `-c core.hooksPath=/dev/null`); `check.py:_git` now does the same. `decisions.md` Operational
  Gotchas has the recipe and how to prove it against a decoy repo.
- **The build-speed work is MERGED** (#197 / `06b2fc6`); branch and its worktree
  `.claude/worktrees/agent-a5830560b594da84f` are stale and can be removed.

## Quick commands

```sh
make difficulty CH=ch04                    # parity/difficulty read (all from HEAD)
make CAMPAIGN=rime-of-the-frostmaiden CH04BOOT=1 fireemblem8.gba -j$(nproc)   # ch04 fast-boot

# Required before claiming a change is finished
python3 -m unittest discover -s tools -p 'test_*.py'
make check
git diff --check
```
