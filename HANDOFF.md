# Handoff - Manchego Stars live state

`HANDOFF.md` is live state only. Settled decisions live in `docs/decisions.md`; operating rules
live in `CLAUDE.md`/`AGENTS.md`; issue scope and backlog live in GitHub. Before a context rollover,
warn Nicolas, refresh this file, and begin a fresh instance — don't rely on auto-compaction.

## Current state

- **Environment: Nicolas is on his Mac. ROM builds, `verify_text` and mGBA playtests are LIVE.**
- **ch04 "The White Moose" (#24) — THE PARLEY NOW CONVERTS THE PACK IN PLACE (#203, `6624364`).**
  The chapter booted (#200), stopped soft-locking (#201), had its scenes watched and six defects
  fixed (`d14ee84`), became winnable with both endings filmed (#204), and this session made mercy
  mean something: Marty's Talk runs one **`CHECK_ALIVE`-guarded `CUSN` per wolf** instead of
  `DISA` + `LOAD1`, so the pack turns green **where it stands** and **the ally count scales with
  survivors** — kill two of five, get three. The old reload put the pack back on its SPAWN tiles
  and resurrected the dead ones, so shooting first cost nothing.
- **The guard is the load-bearing part, and the decomp says why.** `UnitKill` (`bmunit.c:988`)
  WIPES a non-blue unit's slot (`pCharacterData = NULL`), and a `CUSN` on an unresolvable pid
  returns **`EVC_ERROR`** — only `DISA`/`KILL` get the graceful no-op (`eventscr.c:3317`). A bare
  five-`CUSN` sweep would therefore break in exactly the kill-then-parley case the change exists
  to reward. Distinct pids are the other half: `GetUnitFromCharId` returns the FIRST match
  scanning blue→green→red, so a shared pid can only ever be converted once. `CH04_PACK_PIDS`
  draws five from the unnamed generic band `0xB0..0xB9`; a test pins their character entries as
  byte-identical to the `0xb3` slot they replaced. ADR in `decisions.md`.
- **`ch04packmath` is now a GATE, not a question** (kill 2 → must yield 3 greens), and
  `recordch04parley` asserts the "where it stands" half from the unit arrays — tiles read before
  the Talk and again right after the conversion, deliberately BEFORE the phase cycle hands the new
  greens a turn of their own (an aggressive ally walking off to fight looks exactly like a
  relocated wolf). `assert_parley_pid_unique` → `assert_pack_pids_addressable`, guarding the SET.
- **Accepted trade-off (Nicolas, 2026-08-01): the pack keeps `CLASS_MAUTHEDOOG`** in the green NPC
  palette — `CUSN` flips faction, not class. The `lycanroc-pack` reskin stays **declared but
  unworn** in `campaign.yaml` for a later class-remap hook; noted on #24 so the ticked Stage-3 art
  box does not read as "visible in play".
- **The Lonelywood village is BUILT and the Iron Axe is obtainable (#205, `52b17aa`)** — and it was
  TWO bugs, each hiding the other. FE8 gates the Visit menu item on the TERRAIN under the unit
  (`bmmenu.c:735`) *before* it consults the location event, and the snowy reskin had mapped
  vanilla's village metatile **872 -> 994 (RUINS_REGULAR)**; its own neighbours (`871->897`,
  `873->899`) show the intent was **898**, the only VILLAGE_REGULAR tile in the tileset and the one
  ch01/ch02 already use. On top of that `inject_ch04` blanked `EventListScr_Ch5_Location`. Neither
  half was visible: the cottage still DREW correctly (identical 3x3 stamp to Targos's houses).
- **The fix is a rule, not a tile.** `preserve_terrain_variants` was `[12]` (forest only, #193), so
  `preserved_terrain_targets` never checked villages; it now protects all four visitable terrains,
  and a retile that changes one FAILS THE IMPORT. Re-applying that guarantee to the committed grid
  corrected exactly two cells (a 4-byte `.mar` diff). Content-side, `assert_village_tiles_visitable`
  rejects a `villages:` entry standing on scenery. **Placement is vanilla's** (Nicolas: "we copied
  vanilla ch 4, just copy that"): `Village(0, ..., 8, 2)` = the axe; `(1,11)` is the twin's RECRUIT
  village, whose role the parley took, so that cottage stands unwired.
- **Open follow-ups from #205, both small:** the village's line is MINE and marked `visit_text:
  DRAFT` in the chapter YAML — it needs a dialogue pass with Nicolas; and vanilla house metatile
  **804 is deliberately left unmapped** in `reskin-learned.json` (nothing ships broken — our ch01 map
  is a 25x16 custom map, not a `Ch1Map` retile — and a loud rejection beats inventing a tile).
- **The snag falls into a bridge, and the Iron Axe finally has a job (#214, `d656aaf`).** Vanilla
  Ch4's village hands the axe over as the TOOL for chopping the snag at (4,8) into a crossing over
  the river at (4,9) — snags are natively attackable (`bmtrick.c` auto-adds a 20 HP obstacle), and
  only the MapChange was missing because `_retarget_host_chapter` zeroes `changeLayerId`. Vanilla's
  visited-village door flip came along in the same array. The ch03 chest/door emitter was
  GENERALISED (`map_changes_asm` + `_inject_tile_changes`), not copied.
- **The trap that cost a rebuild: a DECLARED terrain is not a PAINTED tile.** snowy-bern carries
  `TERRAIN_BRIDGE_SNAG` on metatile 36 but never painted it — using it put a BLACK SQUARE in the
  river while every terrain byte read correctly and the in-engine gate PASSED. Only looking at the
  frame caught it. `_snowy_metatile_for` now skips blank metatiles and fails loudly. **Corollary to
  "verify via data, not pixels": data proves a change FUNCTIONS, pixels prove it LOOKS like
  anything. A tile swap needs both.**
- **The village line is vanilla's `MSG_9B5` 1:1** (Nicolas 2026-08-02) — it is the tutorial for the
  snag, and the placeholder flavour line it replaced threw the function away.
- **#208 done in the same PR**: the turn-2 reveal's LOCKED dialogue moved out of
  `build_campaign.py` into the chapter YAML as a `wolf_pack_reveal` event (3 boxes per speaker, the
  2026-07-31 pass — the stubs only ever carried 1).
- **ch04's slice is now down to work that NEEDS NICOLAS**: **#206** (Lupin + Baxby battle anims —
  he is running the Gemini art himself) and **the second village's line** (see below).
- **#24's review block was STALE, not incomplete** — three boxes were done in #202 and never
  ticked (checked and ticked 2026-08-01): the no-parley speaker-coverage test
  (`test_the_no_parley_path_has_a_speaker_for_every_box`) exists and passes; message-id uniqueness
  is enforced at build time by `assert_message_ids_unique()` from `main()`; and the parley wave's
  pid is guarded (now `assert_pack_pids_addressable`, #203). **Scope note that keeps #207 alive:** the id guard
  covers scene/talk/card ids only — the goal/objective ids come from the host slot's vanilla
  chapter data and are NOT in `HOSTED_CHAPTER_MESSAGE_IDS`, which is exactly #207.
- **#206 is DECIDED and scoped up (Nicolas, 2026-08-01): do Lupin's battle anim AND Baxby's.**
  Baxby has the same defect for the same reason — he rides a Cavalier slot so the axe-beak can be
  mounted, and he is not among the eight finished PC anims, so the giant bird also fights as a man
  on a horse. Two animal mounts, one problem twice. Lupin has a free donor (`CLASS_MAUTHEDOOG`'s
  vanilla anim IS a wolf); Baxby likely needs an FE-Repo import. Per-character binding already
  exists (`pcs/pinky.yaml` `_u25`), so neither needs a new class. **Basil and Sahnar stay ch05
  work (#25)** — not part of this.
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


## This session (2026-08-01, Opus — mercy started costing something, and ch04 got its reward)

- **#205 closed (PR #212): read the SOURCE before designing.** I had rendered the map, measured
  walk-costs from the deploy zone and built a three-option placement picker — and vanilla Ch4's own
  Location list answered all of it in two lines (`Village(0, ..., 1, 11)` / `Village(0, ..., 8, 2)`),
  at the exact two tiles the retile had preserved. Nicolas: "You're overthinking this, we copied
  vanilla ch 4 just copy that." The map is a retile of its twin, so the twin owns placement.
- **A working-tree read sent me the wrong way first.** `fireemblem8u/src/events/ch4-eventinfo.h`
  shows chests+doors — because inject_ch03 hosts on slot 4 and had overwritten it. HEAD shows the
  two villages. This is the documented `vanilla_scene.py` trap, hit again: **read decomp event data
  through `git show HEAD:`, never the built tree.**
- **Two wrong hypotheses, both killed by data, in the same investigation**: "the door is one
  metatile off" (right, but I abandoned it after a full-map render made the buildings look like
  ruins), then "they're deliberate ruins" (wrong — ch02's working house is the IDENTICAL 3x3 stamp).
  A 21-of-256-pixel diff settled it. **Eyes lose to `ImageChops.difference` every time.**

## Previous session (2026-08-01, Opus — mercy started costing something)

- **#203 closed (PR #211).** The whole design was already on the issue and was NOT re-derived —
  worth repeating as a habit: a grounded design comment is worth more than a fresh investigation,
  and the session went straight to TDD from it.
- **The three decomp facts are the transferable part**, because two of them only bite in the case
  you are trying to reward: a shared pid can be found only once (`GetUnitFromCharId`, first match
  blue→green→red); `UnitKill` WIPES a non-blue slot; and `CUSN` on an unresolvable pid is
  `EVC_ERROR`, not a no-op — DISA/KILL are the only graceful ones. Kill a wolf, then parley, and a
  bare sweep errors the event engine. `CHECK_ALIVE` per unit is ch02's chwinga idiom, reused.
- **A NameError in `inject_ch04` survived a green unit suite** — `len(green_pack_rows)` in a
  verbose print. The injector's end-to-end path is not unit-tested; `make` is what catches it. Run
  the BUILD before believing a refactor of `inject_*` is done.
- **The gates now assert instead of reporting.** `ch04packmath` was written last session to ANSWER
  a balance question; it printed either answer as PASS. It is now the regression gate (kill 2 →
  must be 3 greens). A scenario that can only report is one nobody notices regressing.
- **Verify the claim, not the neighbourhood** — `recordch04parley`'s new in-place assertion had to
  sample the pack's tiles BEFORE the post-parley phase cycle, because that cycle hands the new
  greens their own turn and an aggressive ally walking off to fight is indistinguishable from a
  wolf the parley relocated. The check would have been a coin flip a few lines later.
- **Counting the right thing needed the same fix as converting the right thing**: `greenCount()`
  counted the whole green array (the white moose is green too). One pid per wolf made
  `greenPackCount()` possible — the fix for the mechanism paid for the fix to its measurement.
- Re-recorded `docs/demo/ch04-wolf-parley.gif`: the committed one still filmed the retired swap.
- **#207 closed (PR #213) — and the investigation corrected the issue twice.** ch04 inherited
  ch02's goal window AND status ids because `_retarget_host_chapter` copies the donor's whole
  `goal` block and **ch04's donor IS ch02's host slot**, already rewritten by then. The cause was
  ours, not vanilla's id pooling (ch01/ch03 were clean), and nothing was visibly corrupted: both
  chapters write the same strings, so the last writer agreed with the first. Every hosted chapter
  now DECLARES its pair, `_retarget_host_chapter` overrides the donor's, and both ids are
  registered so `assert_message_ids_unique` binds on them. Only ch04 moved (`0x9C4`/`0x9C5`).
- **Post-injection goal ids cannot be read from HEAD or the working tree.** HEAD is pre-copy
  vanilla; the working tree is whatever the last build or `git restore` left. **Run the injector
  and read the result** — this cost two wrong readings in one session.
- **A playtest FAIL is not automatically a regression: check which ROM it ran on.** `clear_ch02`
  failed on the `CH04BOOT=1` fast-boot ROM, which jumps straight into ch04, so ch02's map is
  unreachable by construction. Rebuilt without the flag it PASSes.
- **Three durable gotchas from this session are now in `decisions.md` §Operational Gotchas**, not
  here: a failing playtest may be the WRONG ROM (a `CH04BOOT=1` build cannot reach ch02's map);
  comments inside a YAML folded scalar are CONTENT; and `check.py` is ~22s clean vs ~4min on a
  freshly-built tree (restore `src/data/chapter_settings.json data/data_8B363C.s` first).

## Previous session (2026-08-01, Opus — ch04 became winnable, and both endings got filmed)

- **#204 closed (PR #209).** One root cause explained every symptom: the fog was never lifted off
  the unit GRID. See Current state above and the `decisions.md` ADR.
- **The fix ships four guards, not one**, because the same path held three more traps that produce
  the identical "bot parks somewhere useless" symptom:
  - `liftFogOntoTheGrid` zeroes the vision range, forces ONE `RefreshEntityBmMaps` by spending a
    unit's Wait, and **reports how many reds reached the grid** — 0 now fails the run loudly
    instead of grinding 16 turns.
  - `clearbot.gridHostileInReach` (pure, unit-tested) makes the bot decide from the ENGINE'S grid
    rather than the unit array, and it is checked BEFORE pressing. **This is the same class that
    bit the ch03 talk driver last session** (row 0 is Attack only when a target exists); it can no
    longer happen silently.
  - `teleportToFiringTile` uses the live `mapSize()` — it hardcoded 25x16 and parked units off
    ch04's 15x15 map, where the cursor can never reach them.
  - `chooseAttack` takes an optional `stopWhen`: a kill that ENDS the chapter starts the win event
    on the spot and the actor may never grey out, so the old 1200-frame wait A-mashed straight
    through the ending the run existed to film.
- **A win gate must match the chapter's real terminal.** `clear_ch04` demanded `chapter() ~= start`,
  which an unhosted ch05 can never satisfy: ch04's ending chains into `dev_placeholder_scene()`
  whose `MNTS(0x0)` lands on the TITLE. It was FAILing runs that had ended perfectly. `clear_ch02`
  already had the right idiom (`or procActive(gProcScr_TitleScreen)`) — precedent beat invention.
  Corollary re-learned: **never A-mash at the title** — it starts a spurious New Game, and the run
  then films the chapter's OPENING under the ending's name.
- **`clear_ch02`/`clear_ch03` are unaffected** by the shared changes: `stopWhen` defaults to nil
  (identical behaviour), and on a 25x16 map `mapSize()` bounds are byte-identical to the old
  hardcoded ones. `recordch04parley` re-run and still PASSes after its driver was extracted.
- **Then swept #24's remaining review block and found it STALE rather than open** (see Current
  state) — worth repeating as a habit: before building a checklist item, grep for the guard; three
  of four were already shipped. The fourth needed a new scenario (`ch04packmath`) and produced the
  pack-math finding above.
- **`turn()` is NOT the signal that a turn's reinforcements exist.** It ticks the moment the player
  phase ends, well before the reveal event `LOAD1`s the wave, so `waitFor(turn() >= 2)` finds an
  empty field. Wait for a UNIT from the wave (`recordch04parley` waits for Lupin) — the same
  verify-by-outcome rule that fixed the Talk-row search.

## Previous session (2026-07-31/08-01, Opus — the scenes got watched)

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

## NEXT SESSION — ch04's slice is down to work that needs Nicolas

`main` is clean and green; the #203, #205, #207 and #214/#208 branches are merged and deleted. **Start from the issues** — each carries its own diagnosis.

1. **#206 Lupin + Baxby battle anims — NICOLAS IS RUNNING THE GEMINI ART.** Decided 2026-08-02:
   Gemini-generated for BOTH, same pipeline as the eight finished PC anims. Ruled out with
   evidence (on the issue): PMD SpriteCollab's Lycanroc `sprite/0745` is real and complete but is
   dungeon-sprite art — 72x80 frames holding a ~37x28 chibi — so it reads as a different game next
   to our FE8-scale anims. Vanilla `CLASS_MAUTHEDOOG`'s anim and the FE-Repo wolf line
   (`docs/fe-repo-scouting.md`) remain fallbacks but give Lupin no glasses.
2. **The SECOND village at (1,11) has no line and no reward.** Its tile is visitable-capable but
   unwired, so FE8 offers no Visit (no location event -> `MENU_NOTSHOWN`) — the player just sees a
   cottage they cannot enter. **Vanilla's second village is PURE Lute recruit dialogue** (`9B2`/
   `9B3`/`9B4`, three variants by visitor, zero lore) so there is NOTHING to copy: whatever goes
   there is ours to write. Nicolas wants "at least a lore drop or a hint" — needs a dialogue pass.
3. **#205's other follow-up**: vanilla house metatile **804 is deliberately unmapped** in
   `reskin-learned.json`; the terrain guard will reject a `Ch1Map` import until someone picks its
   snowy-bern house tile. Nothing ships broken (our ch01 map is a 25x16 custom map).
4. Re-record the opening + reveal on the fixed ROM (winter BG, visible Lupin, winterized fog, and
   now the real 3-box reveal dialogue).

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
  ch04 scenes + the six defects above, #209 the ch04 rout + both endings (#204), #211 the in-place
  pack conversion (#203), #212 the Lonelywood village (#205), #213 the per-chapter goal ids
  (#207), #215 the snag->bridge + the reveal dialogue (#214, #208).
- Untracked local/session files (`.agents/`, `AGENTS.md`, `skills-lock.json`, `map-review/`,
  `review/`) are intentionally not versioned; leave them alone. `map-review/` is the render
  scratch Nicolas opens in Preview (see the sharing-visual-drafts habit) — deliverable art goes to
  `docs/demo/` and is COMMITTED so he can view it on GitHub. `tools/key_magenta.py` is **gitignored** (#178).
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
PT_HOST_CHAPTER=5 tools/playtest/run.sh clear_ch04        # rout -> the NO-LUPIN fallback ending
PT_HOST_CHAPTER=5 tools/playtest/run.sh clear_ch04_parley # parley, rout -> the AUTHORED ending
PT_HOST_CHAPTER=5 tools/playtest/run.sh attackprobe   # why the bot won't attack: grid, fog, the menu
PT_HOST_CHAPTER=5 tools/playtest/run.sh ch04packmath  # GATE: kill 2 wolves, parley -> must be 3 greens
PT_HOST_CHAPTER=5 tools/playtest/run.sh ch04village   # GATE: visit (8,2) -> the Iron Axe changes hands
PT_HOST_CHAPTER=5 tools/playtest/run.sh ch04snag      # GATE: chop the snag -> (4,9) becomes a bridge
make CAMPAIGN=rime-of-the-frostmaiden CH04BOOT=1 fireemblem8.gba -j$(nproc)   # ch04 fast-boot
PT_HOST_CHAPTER=5 tools/playtest/run.sh smoke_ch04                            # ch04 stability net

# Required before claiming a change is finished
python3 -m unittest discover -s tools -p 'test_*.py'
make check
git diff --check
```
