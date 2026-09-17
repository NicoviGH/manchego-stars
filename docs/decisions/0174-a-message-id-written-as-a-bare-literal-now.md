---
id: 174
title: "A message id written as a bare literal now registers itself"
date: "2026-09-02"
section: "Operational Gotchas (durable)"
issues: [346]
---

# A message id written as a bare literal now registers itself

`injector_message_ids` finds an id by the NAME of the constant holding it, and promised that
"registering a new one is enough -- there is no second list to remember". That was false for an id
passed as hex at the `set_message_body` call site: the prologue and ch01 write twelve, and they
reached the deadness guard only because someone grepped for them once and hand-transcribed them
into `PROLOGUE_LITERAL_MSGS` / `CH01_LITERAL_MSGS`. The next one was invisible until a human
noticed it. `0xC25` is the sharp case -- it sits `0x33` above ch05's `0xBC5-0xBF2` pool, so
extending that range upward, the obvious next move, would have been accepted by every guard and
would have overwritten Scramsax's defeat quote.

**The mechanism, not the discipline, was missing.** `inject.hosts.literal_message_ids` reads the
literals out of `build_campaign.py`'s own source through `tools/callsites.py` -- argument
BINDINGS, not text, because `msg_id` is positional at all 71 call sites and `grep msg_id=` finds
none of them -- and attributes each to the injector that writes it. `injector_message_ids` folds
them in, so deadness is checked with no human step.

**Discovery cannot invent an OWNER, so the registry stays -- but the ownership check belongs
where the registry is REAL.** `HOSTED_CHAPTER_MESSAGE_IDS` is what `assert_message_ids_unique`
collides on and what `make chapter` reads for headroom; an id spent but unclaimed reads as free
room already spent. The first cut asserted that in `check.py` by reading the registry with an AST
evaluator, and #356's review killed it: the registry is written as generators, subscripts and
tuple-unpacked constants (`*(msg for (_slot, msg, _boxes, _what) in CH05_OPENING_SLOTS)`,
`CH05_ARRIVAL_SLOT[1]`, `CH04_VILLAGE_MSG`), so the static read was wrong in **both** directions
-- it missed ch04's `0x9C3`/`0x9C6` and would have demanded a registration that makes
`assert_message_ids_unique` exit, and it swept up ch05's box counts so an unclaimed `0x13` passed.
**A hand-rolled evaluator of a data structure is a second, worse implementation of it.** Ownership
now lives in `build_campaign.assert_literals_are_claimed`, called from `main()` beside
`assert_message_ids_unique`, where the dict is a real Python object and the answer is exact.

The split that survives: **`check.py` owns DISCOVERY** -- stdlib-only, so the lean CI `checks` job
runs it for real -- and **the BUILD owns OWNERSHIP.** Discovery makes the id safe (it folds into
`injector_message_ids`, so deadness is checked with no human step); ownership makes it accountable.

The discovery guard is registered in `check.py`'s `CHECKS` tuple and pinned by a test asserting
the function object is in it, and it fails when the live scan finds zero literals -- both because
of the lesson directly above. The build-time half is pinned by a test reading
`build_campaign.main`, which has no such tuple to assert against.

- **Dressing a portrait slot and NORMALIZING its mouth/eye window are two steps, and missing the
  second is silent** (2026-08-09, #25). `patch_portrait_geometry` only knew about `PORTRAIT_MAP`
  and the guests, so any other dressed slot kept the VANILLA character's mouth coordinates and the
  engine painted its blink/talk overlay at the old face's position -- smearing a block of skull
  across the eye sockets and doubling the teeth. Green build, passing scenario, corrupted face.
  Three of the four ch05 residents shipped that way, and the ch02 chwinga had been shipping it
  unnoticed since June; the fourth resident looked fine only because its donor slot's mouth
  happened to sit where ours does. `dressed_portrait_slots()` is now the single answer to "which
  slots do we overwrite" and a test asserts every dressed slot lands in it. **Three data checks
  (clip model, on-disk sheet decode, OAM probe) all passed while the face was visibly wrong --
  the corruption happens at DRAW time from a different table. Look at the rendered face.**

- **The matrix's speed problem was BUILDS, not scenarios -- and parallelism made it worse**
  (2026-08-09). A full run cost 7-9 minutes, enough that it gets skipped or over-run. Two fixes
  were tried; keep the first, do not retry the second without new hardware:
  - **ROM CACHE (kept).** Every configuration rebuilt every run even when nothing feeding a ROM
    had changed, because the tree holds one `fireemblem8.gba` and each group's `make` overwrites
    the last. ROMs are now snapshotted per (configuration, input digest) and copied back: a
    chapter suite went **37s -> 11s**, a full matrix skips ~170s of builds. The digest covers what
    the ROM is built FROM (campaign data, engine, injectors, Makefile, make flags, decomp HEAD)
    and deliberately EXCLUDES `harness.lua`/`matrix.py`/`matrix.yaml`, which drive the emulator --
    those are exactly the edits it makes free. **The ROM builds INSIDE the submodule** while the
    config stamp sits at the repo root; getting that pair wrong caches nothing, silently.
  - **PARALLEL SCENARIOS (measured, rejected, left off).** Scenarios run mGBA at `fps: 240`,
    deliberately unthrottled, so each already saturates a core; this box has 4 performance cores.
    At `jobs=4` individual scenarios went **10s -> 67s**, total wall did **not** move (444s vs
    439s), and four scenarios blew their wall-clock deadlines and reported ERROR/FAIL. Contention
    became false red, which is worse than slow. The knob survives with the numbers in
    `execute()`'s docstring so nobody re-runs the experiment blind.
  - **The real win is `SUITE=`.** A chapter suite is ~11s cached against ~6min for the full gate.
    Iterate on the chapter suite; the full matrix is the push gate, not the edit loop.

- **`harness.lua` is ONE Lua chunk against a 200-local ceiling — new top-level `local`s can stop
  the whole file loading** (2026-08-06, #232). Five new constants pushed the main function over
  Lua's limit and `harness.lua` stopped parsing outright: every scenario dies at once, and no
  source-text assertion notices, so a whole matrix run reported meaningless verdicts. Tuning lives
  in the single `TUNE` table for this reason — add to it rather than declaring another top-level
  local. `test_playtest_harness.py` now genuinely **compiles** the file, so `make test` catches it
  before anything reaches the emulator; a `loadfile` check must ASSERT, since it returns `nil, err`
  rather than raising (that is exactly how this slipped past a manual check).

- **Removing a blind input cadence can break waits that were silently relying on it** (2026-08-06,
  #232). #220 replaced cadence input with observed guarded input, which is right — but `waitFor`'s
  50-frame A-mash had been *load-bearing*: it advanced in-battle quote text, blew through the
  post-chapter save prompt, and re-sent presses FE8 drops during window fade-ins. Six waits had been
  sized or written around it and broke silently, unnoticed for weeks because the ch00/ch01 scenarios
  are not in the hand-run gate list and playtests have no CI. Two durable rules came out of it:
  **size a budget for the un-skipped case** (the ch00 boss animation measures 1238 frames against
  the old 1200 budget), and **prefer progress to wall-clock** — a running event engine is productive
  work and must not burn a stall budget, with a ceiling so a wedged one still fails closed.

- **A single guarded press can be LOST: FE8 drops input while a window animates in** (2026-08-06,
  #232). A press swallowed by a battle-forecast fade meant the wait burned its whole budget on a
  state nothing would move, and the run stayed wedged in `target_selection` for the rest of the
  scenario. `guardedInput` re-presses, but only while the state and the legal action are unchanged,
  and the FIRST attempt keeps the caller's whole budget so anything that already worked is
  untouched. Splitting that budget across attempts is a real hazard, not a hypothetical: it makes
  the first press give up early and fire a SECOND real action (it walked Marty off his parley tile).

- **A render from the frame PNGs proves the ART; only the ROM proves the TILING and the PALETTE**
  (2026-08-03, #206). A preview GIF built from `poses_to_feditor`'s output and the in-game sprite
  are separated by a whole stage — the frames are chopped into 8x8 tiles, packed into sheets, and
  described by an OAM list the engine reassembles in VRAM under a palette it chooses. So "the GIF
  looks right but the ROM doesn't" is not a contradiction to explain away; it *localises* the fault
  to that stage and rules out the art in one step. Read it as a bisect, not a mystery.

- **A scan bound is a property of the ENGINE, never of the current content** (2026-08-02, #206).
  `harness.lua`'s `blue()` searched **8** unit slots — correct back when the cast *was* 8 — so
  `recordanim` reported "lupin not deployed" for a wolf standing on the map, and the first
  instinct was to go hunting in the ROM. The TESTCH sandbox deploys 11 now. Bounds come from the
  decomp (`bmunit.h`: `blue[62]` / `red[50]` / `green[20]`). Any array walk sized to today's
  roster is a bug with a delay fuse.
- **A human's hand-edit of a GENERATED artifact must be the source of truth, or be replayable —
  otherwise it will be regenerated away** (2026-08-02, #206). Lupin's hand-painted spectacles
  nearly died twice in one session, from two directions: the frames were re-rendered underneath
  them (palette change), and the editor's sheet — being *derived from* those frames — was rebuilt
  on every open. Both routes are guarded now (`hand_painted:` + `prepare_sheet` keeping an
  existing sheet), but the general shape recurs anywhere a pipeline has a manual step: name which
  file is authoritative, and make every generator that could overwrite it refuse or replay.
- **A failing playtest may be the wrong ROM, not a regression** (2026-08-02, #207). `clear_ch02`
  FAILed with "never reached the map" during a goal-id change — on a `CH04BOOT=1` fast-boot ROM,
  which jumps New Game straight into ch04, so ch02's map is unreachable by construction. Rebuilt
  without the flag it PASSes. **Before believing a scenario failure, check which ROM it ran on:**
  the boot flags are per-chapter, and a scenario for an earlier chapter cannot pass on a later
  chapter's fast-boot build. The same applies in reverse to `PT_HOST_CHAPTER`.
  **Mechanised since 2026-08-06 (#231/#232):** `build_campaign.py` stamps `.build-config.json` with
  the flags that produced the ROM in the tree, `matrix.yaml` declares what each scenario needs, and
  `run.sh` refuses a mismatch in 0s with the exact `make` line. So this should no longer be a
  judgement call — but `MX_SKIP_ROM_CHECK=1` disables the guard and puts you straight back here
  (which is exactly what happened once inside the session that built it).
- **A guard that lists what it covers stops covering things** (2026-08-06, #138). The
  `HostChapterEventGroup` test was written after the ch04 disaster — a host slot retargeted by map
  ids alone, presenting our map while running the host slot's roster — and it iterated a
  hand-written tuple of `(HOST_INDEX, EVENT_GROUP)` pairs. It was correct and useless going
  forward: **ch05 would have been the first chapter not covered by the very test written to prevent
  its failure mode**, and ch05 hosts deeper into the divergence than ch04 did, because vanilla's
  slot index stops tracking chapter number at 4. `build_campaign.hosted_chapters()` now DISCOVERS
  chapters from `CHNN_HOST_INDEX` + `CHNN_EVENT_GROUP`, so declaring the constants is what enrols a
  chapter; it refuses a host slot with no named event group, and refuses two chapters claiming one
  slot. The general rule: **when a guard enumerates its subjects, derive the list from the data the
  subjects are already made of — never restate it.** A hand-maintained list of what to check is a
  second source of truth that silently drifts the moment someone adds the thing you were guarding.
- **The host-slot facts were already data; the refactor was not what made them lintable**
  (2026-08-06, #138). Worth recording because the epic's re-scope argued the opposite and was
  wrong: `CHNN_HOST_INDEX` / `CHNN_EVENT_GROUP` / `CHNN_GOAL_DONOR` have been module constants all
  along, so the lint never needed config-driven `inject_chapter(N)` to exist. Config-driven hosting
  is still worth doing — 2,626 LOC across five per-chapter functions with a 15-helper shared spine —
  but it is a *readability and repetition* argument, not a prerequisite for validation. Check what a
  refactor actually unblocks before sequencing work behind it.
  **What the repetition argument is actually worth, measured:** of 2,209 LOC in
  `inject_ch01`–`ch04`, just **123 (6%)** is the host skeleton a descriptor would collapse — roughly
  30 lines a chapter, and already helper calls. The other 94% is per-chapter rosters, event scripts
  and scenes, which no descriptor absorbs. So the idea is **not scheduled** and should not be
  re-opened without new evidence; it was never *rejected on principle*, it just does not pay for
  itself at this size. The one real cleanup inside it, deliberately not filed as its own issue:
  ch03's bespoke `_inject_ch03_tile_changes` should migrate onto ch04's generic
  `_inject_tile_changes` — a ~20-line change that a future chapter's tile-change work sits next to
  anyway. Byte-identical baseline to diff against if you do it:
  `42cd82360be3c186c60f9366d57c7608d3d83548`.
- **A proc's identity is its script ADDRESS, never its `PROC_NAME` string** (2026-08-06, #236).
  Freeze reports named a proc from the string pointer at proc+0x10, and that string is not an
  identity: the decomp gives `gProcScr_E_FACE` and `gProcScr_E_FACE_ExtraFrame` the same
  `PROC_NAME("E_FACE")`, and reuses `"bmenu"` and `"E_config"` three times each. Live capture was
  worse still — the field goes stale, so the proc actually running `gProcScr_Talk` printed as
  `E_FACE`, `ProcScr_StdEventEngine` printed as `MAPTASK`, and `gProcScr_TalkSkipListener` printed
  as `ekrBattleEnding`. `gen_symbols.py` now emits `procscr.lua` (952 script addresses → their
  exact symbols) and `symbols.json` (every ROM code symbol, for `inspect_state.py` to name idle
  callbacks). **Resolution is exact-match only, and an unmatched address prints
  `unknown@0x…`** — silence beats a confident wrong name, which is what cost #232 its last failure.
- **An unclassified `transition` must say what it rejected** (2026-08-06, #236). `classify()` is
  an ordered rule table, and `explain()` runs the same rules to return the verdict *plus* every
  rule considered and the predicate that failed. Five of #232's six defects were input waits
  nothing had a name for; each read as a passive transition and cost a full build-and-run cycle
  to identify. The classification is now the cheap half: `INSPECT.watch` arms only on an
  *unclassified* transition holding a byte-identical proc pool, and dumps the snapshot the moment
  the stall is provable.
- **A loop budget must not be the thing that decides failure** (2026-08-06, #232/#236). `ch01`
  stayed open for three sessions on a diagnosis that turned out to be wrong — "no page wait is
  ever classified as `dialogue_wait`, so nothing advances it". The inspector disproved it in one
  run: page waits were classified and advanced **74 times**, all passing, and the flow was still
  advancing 263 frames before the old 12000-step cap expired. A cap that fires mid-scene reports
  a timeout that names nothing, and a budget-bounded loop exits at the same frame whatever is on
  screen — so the number looks like evidence and is not. Caps are now sized far above any real
  scene (`TUNE.bootSteps`), and `INSPECT.watch` is the failure oracle.
- **A Yes/No prompt inside a scene is its own input state** (2026-08-06, #232). With the above in
  place the real `ch01` blocker took one run to name: `gProcScr_YesNoChoice` in
  `YesNoChoice_Loop_KeyHandler` — lord select's "Will \<lead\> lead the party?". It runs *inside* a
  live event scene, so the `std_event` passive rule swallowed it as a transition and nothing ever
  answered. It is classified as `yes_no_choice` and ordered above the passive rules;
  `currentChoice` (s16 @ +0x2A, `TALK_CHOICE_YES`=1/`NO`=2) decides which answer carries `A`, and
  the *scenario* chooses the answer — the controller only says what is legal.
- **Comments inside a YAML folded scalar are CONTENT, not comments** (2026-08-02, #214). Authoring
  a chapter's `visit_text: >` with `#` lines indented underneath silently folded them into the
  string, and the chapter YAML then failed to load for every test that reads it. Comments belong
  ABOVE the key. Cheap to hit, instant to diagnose once seen — the parse error names the file, not
  the line.
- **`tools/check.py` is ~22s on a clean tree and ~4 minutes on a freshly BUILT one** (measured
  2026-08-02). `check_tests_pass` runs each `tools/test_*.py` as its own process, and the heavy
  ones re-read the injected decomp. The pre-commit hook runs the same thing, so a commit right
  after `make` can appear to hang. **Restore the injected decomp files first** —
  `git -C fireemblem8u restore src/data/chapter_settings.json data/data_8B363C.s`. Not a
  regression; just know it. (`test_winter_forest_backfill` no longer needs that restore to PASS:
  since 2026-08-03 / #221 it reads its vanilla inputs through `git show HEAD:`, the same doctrine
  as the event-data rule above. The remaining decomp-reading tests still read the working tree,
  so the timing claim stands.)

- **A host slot's index stops tracking the chapter number at 5, and a hosted chapter must name the
  `ChapterEventGroup` it fills** (2026-07-31, ch04 #24). FE8 inserts chapter 5X at **slot 5**, so
  `chapter_settings.json` slot 5 ships with `mapEventDataId` → `Ch5XEvents` while a chapter hosted
  there writes its events into the `Ch5*` symbols (`Ch5EventData`). Slots 1–4 are correct only by
  the coincidence that index == chapter number there. `_retarget_host_chapter` therefore takes a
  mandatory `event_group` and repoints `mapEventDataId` itself, so map and events stay ONE decision;
  `HostChapterEventGroup` in `tools/test_build_campaign.py` pins both the trap and the repoint.
  **Why this one is worth a durable entry: it fails silently and totally.** Retargeting the map ids
  alone makes the chapter *look* injected — correct `gBmMapSize`, correct tileset, correct goal
  banner — while the slot runs the host's roster and scripts underneath. The observable symptoms all
  point away from the cause: foreign units on coordinates off your footprint, a party that never
  deploys, no PREP, and a cursor initialised onto an undeployed unit's `x=255` sentinel, which
  presents as the *playtest harness* wedging. Diagnose it by reading `gBmMapSize` and the live unit
  arrays in-engine (data, not screenshots — the map is genuinely yours, so pixels mislead) and by
  resolving the slot's `mapEventDataId` through `gChapterDataAssetTable`.

- **A scripted `MOVE` to good terrain still hangs the chapter if the unit cannot WALK there —
  connectivity is the test, not the tile.** `MOVE(...)` + `ENUN` waits on a path; when none
  exists the event engine never returns and the chapter freezes with the unit standing where it
  loaded. ch04's white moose fled to `(14, 0)`, the map's NE corner: `TERRAIN_PLAINS`, cost 1,
  entirely reasonable-looking — and sealed off from its own clearing by a wall of
  `TERRAIN_CLIFF`. `make` was green, the map was correct, and the beat wedged the game the first
  time a party unit triggered it. `assert_scripted_move_reachable` now fails the BUILD on it: it
  flood-fills the map's terrain (resolved through the layout's own tileset table, read from the
  **campaign** asset — the decomp's copy is the untracked artifact injection writes) with the
  unit's class movement-cost row, and names the nearest legal destination in the error. Two traps
  live inside that check: the cost rows in `data_terrains.c` are **designated initializers keyed
  by terrain NAME**, so reading them positionally yields a plausible-looking table where
  everything is walkable (the names carry digits — `TERRAIN_C_ROOM_09`, `TERRAIN_TILE_2E` — that a
  naive number scan eats as costs); and `data_terrains.c` is a PATCHED file, so it must be read
  at HEAD through `vanilla_decomp_text`. Covered by `ch04moose` (in-engine, both halves) and two
  unit tests — one pinning today's tile, one pinning that the OLD corner is walkable-but-cut-off,
  because "is it good terrain" is exactly the check that passes while the game hangs.
  _Recorded: 2026-07-31 (ch04 #24 Stage 4)._

- **A reachable endpoint does not define a staged escape — route and camera framing are authored
  scene data.** A single `MOVE` from the white-moose clearing to `(14,14)` was technically reachable,
  so FE8 legitimately chose its shortest path straight south; `CAMERA2(14,14)` then made `REMA`
  restore the camera over the map boundary, exposing the engine's gray out-of-map tile grid behind
  RBG's portrait. The intended beat is now explicit in the chapter YAML: `flee_route` crosses the east
  bridge at `(9,7)`, reaches the far bank at `(9,8)`, and exits southeast at `(14,14)`. The injector
  emits that as a vanilla REDA queue plus `MOVE_DEFINED`, preserving continuous normal-unit walking
  between authored waypoints, and validates every waypoint as reachable. The 15-tile-wide map exactly
  fills the GBA viewport, so centering `CAMERA2` on the moose at x=11 scrolls past the real right edge
  and renders wrapped map memory. The YAML therefore authors `camera_at: [7,4]`, the map-width center
  that pins camera x=0 while framing the clearing and bridge. Script tests pin the camera, queue, bridge
  tiles, and endpoint; the motion GIF remains the
  visual acceptance gate because reachability cannot judge composition.
  _Recorded: 2026-08-03 (Nicolas + Codex, ch04 #24 / PR #219 visual review)._

- **An `AREA` event is not "a player unit steps here" — it is "whichever unit last acted is
  standing here," and a bare abort spends the one-shot forever.** FE8 polls the Misc event list at
  the end of EVERY unit's action — `playerphase.c` and `cp_perform.c` (the AI mover) both
  `PROC_CALL_2(RunPotentialWaitEvents)` — and `EvCheck0B_AREA` (`eventinfo.c`) tests
  `gActiveUnit`'s position with **no faction check**. So an AREA drawn over ground the enemy also
  walks fires on the ENEMY phase: ch04's moose-sighting rect `(8,2)-(14,7)` is exactly where the
  turn-1 monster line stands, and a Revenant ending its move there played RBG's "After it!" to an
  empty clearing on turn 1. The second half of the trap is `StartEventFromInfo`, which
  `SetFlag(info->flag)`s the AREA's one-shot **before** it `CallEvent`s the script — so guarding
  with an early `ENDA` still burns the beat permanently. Vanilla ships the whole answer:
  `SVAL(EVT_SLOT_2, FACTION_ID_BLUE)` + `CALL(EventScr_UnTriggerIfNotFaction)` (`eventcall.h`;
  ch13b/ch15b use it verbatim), which clears the *triggered* event id — re-arming the AREA — and
  `ENDB`s the whole event rather than just its own frame. Put the guard FIRST, before any `LOAD1`
  or camera seize. **How it was caught matters more than the fix: by filming it**
  (`recordch04reveal`), not by reading the script — the wiring is correct FE8 in isolation, and
  `smoke_ch04` stayed green throughout, because a beat firing at the wrong moment is not a
  soft-lock. _Recorded: 2026-07-31 (ch04 #24 Stage 4)._

- **A chapter's message text lives in TWO decomp files, in TWO channels — a partial scan reads as
  proof that vanilla lacks a beat.** `src/events/<ch>-eventscript.h` holds the scenes, mixing
  `TEXTSHOW` (on-map, units staged by `LOAD1`, bubbles wrap at 29 chars) with
  `Text_BG(BG_*, id)` (a still backdrop, ~42 chars) — and vanilla uses the backdrop for scenes set
  ELSEWHERE, so the channel also tells you where a scene happens. Separately,
  `src/data_battlequotes.c` holds boss taunts, boss death quotes and chapter-specific unit death
  quotes, which appear in **no** eventscript. Both traps fired on ch05: `vanilla_scene.py` matched
  `TEXTSHOW` only and reported Ch5's 11-message opening as 8, hiding the exact two backdrop scenes
  our 9BC/9BD are modelled on; and a caveat was written claiming `0x9C6`/`0x9C7`/`0x9C8` "appear
  nowhere in the decomp" when all three are battle-quote entries — `0x9C6` being the escort's death
  quote, which then turned out to be a slot we owed Basil. Grep **both** files before concluding an
  id is unused, and prefer the tool (now channel-aware, guarded by `tools/test_vanilla_scene.py`).
  _Recorded: 2026-07-29 (ch05 dialogue pass)._

- **A `git` subprocess run inside a git hook resolves against the OUTER repo unless you strip `GIT_*`.**
  Git exports `GIT_DIR`/`GIT_INDEX_FILE`/`GIT_WORK_TREE` while a hook runs (pre-commit drift → `check.py`
  → the `test_*.py` suite). Any tool or **test fixture** that then shells out to `git` — `git -C <dir> …`,
  a throwaway `git init`/`commit` in a tempdir, `_vanilla_decomp_text`'s `git show HEAD:` — has its
  `-C`/cwd **overridden** by the ambient `GIT_DIR` and silently operates on the real repo. On 2026-07-21
  this flipped `core.bare=true` on the live repo and wrote a corrupt commit before it was caught. **Always
  pass a sanitized env** — `{k: v for k, v in os.environ.items() if not k.startswith('GIT_')}` — to any
  `git` subprocess that must target a specific repo, and add `-c core.hooksPath=/dev/null` to fixture
  commits so they can't re-enter the outer hook. Fixed in `_vanilla_decomp_text` + `test_map_tileset.py`.
  **It recurred on 2026-07-30** in `test_check_handoff.py` — a new fixture, written the obvious way
  (`subprocess.run(['git', ...], cwd=repo)`), which under pre-commit ran its throwaway `init`/`config`/
  `add`/`commit` against the live repo: `core.bare` flipped to `true`, `user.name`/`user.email` were
  overwritten with the fixture's `t`/`t@t`, and `HANDOFF.md` was left staged mid-commit (surfacing as a
  bogus HANDOFF-guard violation, which is what led back to it). `cwd=` is NOT a defence — the ambient
  `GIT_DIR` beats it. So: **any new test that shells out to `git` must go through a sanitized-env helper**
  — target the repo with `-C`, pass `env=` stripped of `GIT_*`, and add `-c core.hooksPath=/dev/null`. Verify
  it by running the fixture with `GIT_DIR` pointed at a decoy repo and asserting the decoy is untouched;
  the pre-fix helper corrupts the decoy, the fixed one doesn't.
- **Per-unit descale recipe is recorded in the unit YAML comment** (data-is-the-doc) — read it before
  regenerating; don't guess flags. Swapping ONE pose still requires re-descaling the **whole 3-frame set
  together** (shared palette recompute shifts the other two — that's correct, not a bug).
- **Battle-anim frames are a hard 3** (ready/windup/peak; script refs frames 0/1/2; `build_battle_anim`
  rejects any other count). The "march" is faked by the per-donor sound/shake cadence + a single engine
  OAM lunge (`MELEE_LUNGE_DX` −40 on peak), not extra art frames.
- **`make_gif.py` writes to `docs/demo/` on the active feature branch.** Show that committed GIF
  in the GitHub PR; remove it before merge once the review is complete, unless a live document
  deliberately links to it as durable evidence. Do not accumulate local review archives.
- **Event BGs: vendored winter CGs → NEW `gConvoBackgroundData` slots, additive** (`bg_to_fe8.py` →
  `inject_backgrounds`). **Color index 0 is TRANSPARENT** — using it for a real colour → black holes;
  `bg_to_fe8.py` reserves it. Slots are appended past `BG_RANDOM` at **0x38+**, so they don't run out.
  Verify event BGs **in-engine** (a flat preview won't show the holes).
- **Cutscene faces: `Text()` self-`REMA`s (clears ALL portraits); to hold one speaker while another
  exits, author raw + a per-podium `[ClearFace]`.** `Text(msg)` = `TEXTSTART TEXTSHOW TEXTEND REMA`
  (`Convo_Helpers.h`), so every beat fades out every face at its end. For a "one speaker leaves mid-scene,
  a co-speaker holds through a pause" beat (ch03 opening: Pinky scouts, RBG waits at the mine mouth):
  emit **raw `TEXTSTART/TEXTSHOW/TEXTEND` (no `REMA`)** and append **`[OpenX][ClearFace]`** to that beat's
  message body — `[ClearFace]` fades only `faces[activeFaceSlot]` (`scene.c`), leaving the others up.
  The next beat's `Text()` opens with `TEXTSTART`; because `Event1A_TEXTSTART` skips its face-clear when
  the sub-type **equals the still-active** type (`subcode == proc->activeTextType`), the held face carries
  through and its re-`[LoadFace]` early-returns on the occupied slot (`TalkLoadFace`, no reflicker). Hook:
  `_script_to_message(trailing=...)` / `_emit_scene_beats(trailings=[...])`. There is **no event-level
  single-face-remove command** — only `REMA` (all) and `FACE_SHOW`/`EvtDisplayFace` (add one); the
  per-face *fade-out* is a message text-code, not an event opcode. Verify in-engine (`recordch03open`).
- **Location-card nameplate caps at ~96px** — >~12–14 chars clip silently. Keep `location_card:` short.
- **Vanilla character-slot display names leak** unless the injector overrides it:
  `set_message_body(vanilla_name_text_id(slot), name_message_body(display_name(unit)))`. Give units a short `fe_name` (≤12).
- **Clear-bot can't fully clear a chapter yet (#60).** Helpers that must REACH a later chapter use directed
  seizes / frail+teleport (`reachCh02Map`, `clear_ch02`), not fair-play clears.
- **DefeatBoss fires from the FLAGGED defeat quote, not `CA_BOSS`** (`eventinfo.c`: `SetPidDefeatedFlag`
  runs for ANY unit whose pid matches a `gDefeatTalkList` entry on death — no boss-attribute gate). So a
  boss on a **raw pid with no `gCharacterData` entry** (ch03's grell = `0xb7`, chosen to avoid leaking a
  vanilla boss's name/face/quote) still wins the map via a head-of-list quote keyed to `(pid, CHAPTER_L_N,
  EVFLAG_DEFEAT_BOSS)`. **Trade-off:** with no `CA_BOSS` it shows **no boss HP gauge** and the generic
  clear-bot/`findBoss()` (reads `CA_BOSS`) can't target it — so a per-boss load-test must reach it by
  pid+tile (`ch03win`: teleport the grell to the lord and strike), and a future `clear_chNN` needs either a
  `CA_BOSS` character entry for the boss or a pid-targeted bot. Verified in-engine (`ch03win`, 2026-07-07).
- **A mid-map death-triggered cutscene (miniboss) = the same silent-flagged-quote idiom + a tmp-flag `AFEV`,
  NOT `DefeatBoss`.** ch03's RBG-execution beat fires when the *Icewind Brute* dies (not the boss). Recipe
  (mirror of the win, keyed to a temporary flag so the chapter continues): (1) give the miniboss a **unique
  raw pid** distinct from the shared generic AND the boss (ch03 Brute = `0xb6`, sibling of the grell's `0xb7`;
  `0xB0–0xB9` are unnamed → no name/face leak), so its flagged quote keys the trigger to it alone — reusing the
  generic `0xaa` would fire on *any* trash mob's death; (2) a **silent** (`.msg = 0`) `gDefeatTalkList` entry
  `(pid, CHAPTER_L_N, EVFLAG_TMP(a))` — `SetPidDefeatedFlag` sets the flag with no portrait to render;
  (3) a Misc `AFEV(EVFLAG_TMP(b), midmap_script, EVFLAG_TMP(a))` — `EvCheck01_AFEV` runs the script when flag
  `a` is set and marks itself done with the **ent-flag `b`** (set AFTER the script's `ENDA`), so it fires
  **exactly once** (an ent-flag of `0` would re-fire every turn once `a` is set). The vanilla ch1 idiom
  (`AFEV(EVFLAG_TMP(7), …, EVFLAG_DEFEAT_BOSS)`). Data-driven via a per-enemy `is_miniboss:` YAML flag +
  `build_campaign.midmap_minibosses`/`flag_defeat_quote`/`midmap_afev`. Verified in-engine (`ch03midmap`:
  kill the Brute → `EVFLAG_TMP(10)` → the AFEV runs the 3 on-map beats → `EVFLAG_TMP(11)` → chapter continues).
- **Don't reuse a playtest checkpoint across an injection/build change** — only across pure graphics-byte
  swaps. Checkpoints are ROM-hash-stamped in `tools/playtest/states/` (gitignored); delete `.ss`/`.romhash`
  to force a rebuild. (A battle-anim frame change IS a build change → re-record from a fresh ROM.)
- **Additive, never global** (content art): clone classes / new terrain/banim/BG slots; never edit a shared
  vanilla one in place.
- **Engine hooks live in `tools/inject/engine_hooks.py`** (guarded by `check_engine_guards_present`).
- **Turning fog OFF takes TWO steps: the vision range AND a map refresh** (2026-08-01, #204). Fog
  does two independent things, and zeroing `gPlaySt.chapterVisionRange` only undoes one of them.
  `bmtarget.c` gates target-picking on the vision range, so zeroing it does re-open targeting — but
  `RefreshUnitsOnBmMap` (`bmmap.c`) is what writes units into the tile→unit grid `gBmMapUnit`, and it
  **skips a red standing in fog entirely**, filing it under `gBmMapHidden` with `US_BIT9` instead.
  Nothing recomputes that grid on a memory poke, so until the engine's next `RefreshEntityBmMaps`
  the enemies are simply *not on the map*: `gBmMapUnit` holds none of them no matter what the unit
  array says. Any refresh fixes it — one unit's action (`MapMain_ResumeFromAction`) or a phase change
  is enough, and the refresh also refills `gBmMapFog` itself (`BmMapFill(gBmMapFog, !visionRange)`),
  so the fog map never needs poking. **Why this is worth a durable entry: every symptom points at the
  wrong layer.** `clear_ch04` sat at 10 live enemies for 16 turns with zero kills; the enemies were
  visibly on screen, the unit array listed all ten with correct coordinates, and the vision range
  read 0 — so fog looked handled. What actually happened is that the clear-bot teleported "adjacent"
  to foes the engine could not see, got a command menu with **no Attack row**, and its blind row-0
  press opened **Item** and Used a Goodberry at full HP, forever. The lesson generalises past fog:
  **the grid, not the unit array, is what the engine acts on** — so a bot must decide from
  `gBmMapUnit` (`clearbot.gridHostileInReach`) and never assume command-menu row 0 is Attack.
- **New decomp patch target → add it to `PATCHED_DECOMP_FILES`**, or the build is non-idempotent.
- **Vanilla decomp reads go through `build_campaign.vanilla_decomp_text()` (HEAD)**, never the worktree.
- **`make`-green can't prove apply timing OR rendering** — `tools/playtest/` is the dynamic arbiter. Needs a
  built ROM + `lua`; `run.sh` regenerates `symbols.lua` after a rebuild.
- **CI unit tests run in the `tests` job, not the lightweight `checks` job** (need submodule + numpy/PIL). They ran in the `build` job until #382 split them out.
  mGBA playtest *scenarios* are NOT CI-gated; the `test_*.lua` cores ARE, via `make test`.
- **Distribution is the private pre-patched `.gba`** (decomp build is non-matching vs retail).
- **Save layout must stay stable for testers** (#59): `check_save_layout_stable` reds on layout drift.
- **Writing any dialogue → invoke `dialogue-pass` first.** Story bodies are `make`-regenerated; gate text
  changes with `python3 tools/verify_text.py`. Card/name text is ASCII-folded in `name_message_body`.
- **`msg-id` vetting is treacherous** — `data_battlequotes.c` stores ids 4-digit zero-padded; vet in `0x0XXX` form.
- **Chapter hosting** (model on `inject_ch01`/`inject_ch02`): each chapter rides the *next* vanilla slot,
  chained via `MNC2(<next slot>)`; new snow chapters set `battleTileSet` `0` (open) or `0x15` (rough).
- **Vanilla-only (monster/exotic) weapons belong in `difficulty.py`**, not `WEAPON_ITEM_ENUM`.
- **Never a bare `make` for a shippable ROM** — `tools/build.sh` applies the decomp shebang fix; a bare
  `make` dies on the gfx tools on macOS (`decisions.md` §Distribution).
- **The FE Wiki is a CROSS-REFERENCE, never an authority** (2026-08-07). The decomp stays the source
  of truth for every FE8 claim (`CLAUDE.md`), but the wiki's per-chapter pages are worth a read when
  mining a vanilla chapter, because they state things in a form that *prompts the question* the
  decomp answers. Concretely: it says "village to the southeast → Dragonshield". The decomp says
  `SVAL(EVT_SLOT_3, 0xe)` inside one of four separately-named scripts, and nothing in it invites you
  to ask whether our pairing matches. That is exactly how ch05's swapped reliquary gifts were caught
  — **wiki raised it, decomp settled it**, which is the only order that is ever correct.
  **Fetching it:** the rendered page is blocked (403 to curl, 402 to WebFetch). Use the MediaWiki API:
  ```sh
  curl -sL -A "Mozilla/5.0" "https://fireemblem.fandom.com/api.php?action=parse\
&page=The%20Empire%27s%20Reach&prop=wikitext&format=json&formatversion=2"
  ```
