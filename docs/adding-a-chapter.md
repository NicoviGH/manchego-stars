# Runbook — Hosting a New Chapter

The repeatable recipe for putting a designed chapter into the ROM, distilled from
`inject_ch01` / `inject_ch02` / `inject_ch03` in `tools/build_campaign.py`. Follow this
instead of re-deriving the host machinery each time. **Reference implementations:**
`inject_ch03` (defeat-boss, self-registers a new tileset — the leanest) and `inject_ch02`
(defeat-all + cutscenes + green allies — the full-featured one).

## The one mental model

A campaign chapter is **hosted on a vanilla FE8 chapter slot**. Host slot index `N` uses the
decomp's vanilla **"ChN" symbol set** (event lists, unit tables, event script). We host each
chapter on the *next* slot so the previous chapter's ending `MNC2(0xN)` chains onto it:

| Our chapter | Host slot `N` | Vanilla symbols used | Constant |
|---|---|---|---|
| prologue (ch00) | 1 | `Ch1*` (via the sandbox files) | `PROLOGUE_HOST_INDEX` |
| ch01 | 2 | `Ch2*` (`UnitDef_Event_Ch2Ally`, `EventListScr_Ch2_*`) | `CH01_HOST_INDEX` |
| ch02 | 3 | `Ch3*` | `CH02_HOST_INDEX` |
| ch03 | 4 | `Ch4*` (`UnitDef_Event_Ch4Ally`, `EventListScr_Ch4_*`, `EventScr_Ch4_BeginningScene`) | `CH03_HOST_INDEX` |
| ch04 | 5 | `Ch5*` (slot 5 ships `Ch5XEvents` — retargeted to `Ch5EventData`) | `CH04_HOST_INDEX` |
| ch05 | 6 | `Ch6*` event lists only; rosters are `MS_Ch05*` | `CH05_HOST_INDEX` |

**From slot 6 on, the slot index and the vanilla symbol name disagree in the BASE GAME** (FE8
inserted Ch5x at slot 5): slot 6 ships `Ch5EventData`, slot 7 ships `Ch6Events`. So slot N carries
chapter N-1's names, and the retarget in step 4 is mandatory for every chapter from here — leaving it
would put two of our chapters on one event group. Same trap in `chapters.h`: `CHAPTER_L_5 = 0x06`, so
slot 6 is `CHAPTER_L_5` — resolve it with `chapter_label_constant(slot)`, never spell it from a number.

The **map** and the **host slot** are decoupled: you register the painted map as new asset-table
entries, then point the host slot's `map` block at them. The map can repaint *any* vanilla
geometry regardless of which slot hosts it (ch03 repaints vanilla Ch3 "Borgo" but hosts on slot 4).

## Recipe (mirror `inject_ch03`)

1. **Module constants** — add a `CHNN_*` block next to the others (host index, **event group
   symbol** (step 4), layout `(asset_label, maps_stem)` tuple, chapter YAML name, tileset, goal donor, boss/generic PIDs,
   `CHNN_AI` byte-vectors, `CHNN_CLASS_IDS` / `CHNN_ITEM_IDS` dicts mapping our YAML ids → decomp
   enums, spawn positions, and the `ChM_EVENTINFO_H` / `ChM_EVENTSCRIPT_H` path constants for the
   host slot's vanilla `M = N` symbols).

2. **Register the tileset** (only if new) — `_register_tileset(campaign, '<tileset>', '<Stem>', comment)`.
   `_register_chapter_map` **sys.exits** if the layout's tileset isn't registered, so this comes
   first. (`snowy-bern` = 'Snow' is registered by `inject_winter_tileset`; `cave-interior` = 'Cave'
   self-registers in `inject_ch03` — the first chapter to use it.) `TILESET_STEMS` must map it.

3. **Register the map** — `indices = _register_chapter_map(maps_dir, CHNN_LAYOUT, comment)` →
   `(obj_idx, pal_idx, cfg_idx, layout_idx)`. Reads the layout `.json`'s `tileset` stamp.

4. **Retarget the host slot + pick a goal donor** —
   `host = _retarget_host_chapter(CHNN_HOST_INDEX, GOAL_DONOR, '<goal_type>', err, indices, chapter_number, CHNN_EVENT_GROUP)`.
   It points the slot's map at `indices`, **repoints the slot's `mapEventDataId` at `CHNN_EVENT_GROUP`**,
   **copies vanilla slot `GOAL_DONOR`'s goal banner** (asserting its `windowDataType == goal_type`),
   and sets `prepScreenNumber = chapter_number * 2`.

   **`CHNN_EVENT_GROUP` is the `ChapterEventGroup` symbol your injector fills, and you must name it
   — never assume the slot already points there.** Vanilla's slot index tracks the chapter number
   only up to 4: FE8 inserts chapter 5X at **slot 5**, so from there the two diverge (slot 5 ships
   pointing at `Ch5XEvents`, while a chapter hosted there writes its events into `Ch5EventData`).
   This fails *silently and totally*: retargeting the map ids alone is enough to make the chapter
   look right, so the slot presents YOUR map while running the host slot's roster and scripts —
   foreign units on coordinates off your footprint, no party deployed, no PREP. Cost when it bit
   ch04: a whole session chasing a "harness soft-lock" that was only the cursor initialising onto
   an undeployed unit's off-map sentinel. Resolve the symbol → index with
   `_asm_table_word_index(ASSET_TABLE_S, 'gChapterDataAssetTable', ...)`; `HostChapterEventGroup`
   in `tools/test_build_campaign.py` pins it.

   **You get this guard for free, and you cannot forget to opt in.** Declare `CHNN_HOST_INDEX` +
   `CHNN_EVENT_GROUP` in **`tools/inject/hosts.py`** (the registry — stdlib-only so CI can lint it
   without Pillow; `build_campaign` re-exports both). `hosted_chapters()` discovers chapters from
   that pair, so writing it is what enrols your chapter in the event-group check; there is no list
   to update. `make check` fails in 0s on a host slot with no event group, on two chapters claiming
   one slot (the prologue's slot 1 included), and — since #241 — on an `inject_chNN` that declares
   nothing at all, which used to be silently unhosted (#138).

   Pick a donor slot whose goal type matches and that our injectors don't overwrite:

   | Goal | `windowDataType` | Clean donor slots (vanilla, post-inject) |
   |---|---|---|
   | Seize | `seize` | 5 (also 1/3/8, but those get overwritten) |
   | Defeat Boss | `defeat_boss` | **6**, 7 (0 = prologue's, read-only) |
   | Rout / Defeat All | `defeat_all` | 2, 4 |

   **The goal banner only DISPLAYS the objective — it does NOT trigger the win.** The win is an
   *event macro*: `Seize(x,y)` / `DefeatBoss(scr)` / `DefeatAll(scr)` in the host slot's `Misc`
   (or `Location`) event list, plus — for defeat-boss — a **flagged defeat quote** (see step 7).

5. **Rosters** — build rows with `_ally_unit_entry` / `_enemy_unit_entry`, then **declare your own
   table** with `declare_unit_table('MS_ChNN<Role>', rows, comment)` and **point the event group at
   it**: `point_event_group_at(info, CHNN_EVENT_GROUP, 'playerUnitsInNormal'|'playerUnitsInHard',
   CHNN_ALLY_TABLE)`, then `assert_event_group_roster(...)`.

   > **Declaring the table does not wire it, and forgetting the pointer has NO symptom.** ch05
   > shipped one build where the group still named `UnitDef_Event_Ch6Ally`: the party deployed on
   > vanilla Ch6's start tiles — another map's coordinates — with PREP running, the map drawn, the
   > load-test PASSing, and four units standing inside walls. `assert_event_group_roster` now fails
   > the build instead. Verify placement from `INSPECT.units` (in `mapshot`), never from a
   > screenshot: FE8 draws a map sprite offset upward, so a unit reads a row high.

   Do NOT block-overwrite a vanilla table the stripped cutscenes left free (the old ch01–ch04 idiom;
   see `decisions.md` → "Campaign rosters live in campaign-named symbols"). Only the event-LIST
   symbols stay vanilla-named, because `chapter_settings.json` resolves the group from them.

   The roles each chapter needs (one `MS_ChNN*` table each):
   - Party → `MS_ChNNDeployCap`, the never-LOADed cap template the group points at. Real flow:
     author `deployment.deploy_slots` (== `deploy_limit` tiles) in the YAML and use
     `_deploy_cap_entries` + a `PREP` CALL. Fast-boot additionally declares `MS_ChNNBootSeed` — the
     same roster ARMED from `CLASS_LOADOUT` — and `LOAD1`s it so PREP has a party from a cold New
     Game. (`deploy_slots` is not optional: `_deploy_cap_entries` sys.exits without it.)
   - Enemies → `MS_ChNNLine`, `LOAD1`ed by the beginning scene, plus one `MS_ChNNWave<turn>` per
     reinforcement wave (each needs its own table — one table cannot serve two turns). Boss and any
     named unit take a UNIQUE pid so their flagged `gDefeatTalkList` entries key to them alone; the
     rest share the slot's generic autolevelled PID. Positions/levels/items/AI from the YAML.
   - A convertible/recruitable enemy gets its OWN table and pid even before its Talk is wired — a
     shared pid is unaddressable, which is what #203 cost ch04's wolf pack.

6. **Strip cutscenes** (`ChM_EVENTINFO_H` + `ChM_EVENTSCRIPT_H`) — empty `Turn`/`Character`/
   `Location` to `{ END_MAIN }`, set `Misc` to the win/lose machinery, empty `Tutorial` to
   `{ END_MAIN }` (**see gotcha #1**), and replace `EventScr_ChM_BeginningScene` with a bare
   `{ LOAD1(0x1, <enemies>) ENUN LOAD1(0x1, <ally>) ENUN ENDA }`.

7. **Win/lose wiring** —
   - **Defeat All:** `Misc = { DefeatAll(EventScr_...) CauseGameOverIfLordDies END_MAIN }` — engine
     rout counter drives it (see `inject_ch02`).
   - **Defeat Boss:** `Misc = { DefeatBoss(EventScr_...EndingScene) CauseGameOverIfLordDies END_MAIN }`,
     the boss on a named `CHARACTER_*` slot, and a **`gDefeatTalkList` entry** for it via
     `_prepend_defeat_quote` with `.flag = EVFLAG_DEFEAT_BOSS`, `.chapter = CHAPTER_L_N`, a death-quote
     `.msg`. **`CA_BOSS` alone triggers nothing — the flag on the defeat quote is what fires the win**
     (see `inject_prologue` step 5). Rewrite the ending-scene script the `DefeatBoss` points at.
   - **Seize:** `Seize(x,y)` (== `LOCA(EVFLAG_WIN, …, TILE_COMMAND_SEIZE)`) in the `Location` (or
     `Misc`) list; the lord seizing the tile raises `EVFLAG_WIN`.
   - Lord-death loss is always `CauseGameOverIfLordDies` (fires on `EVFLAG_GAMEOVER`, set by the
     lord's flagged defeat quote / the `_inject_lord_select_engine` hook).

7b. **Location events (villages, shops, chests, doors)** — anything the player *visits* lives in the
   host slot's `Location` list. **Leaving that list empty makes every reward on the map
   unobtainable while the map still draws it** — that is how ch04 shipped an unreachable Iron Axe,
   and ch05 currently has four reliquary villages plus an armory and a vendor sitting on intact
   tiles that nothing points at. Two guards, both cheap:
   - `assert_village_tiles_visitable` — FE8 offers Visit only on house/inn/village terrain
     (`bmmenu.c`), so a `Village()` on scenery is a reward that silently does not exist.
   - `assert_village_gifts_match_vanilla` — on a retile, **which gift sits on which tile is
     vanilla's** (`decisions.md` → "A retile inherits vanilla's GIFT PLACEMENT"). Swapping two
     keeps the item set, the total and the parity verdict identical while inverting which site is
     worth defending. Deliberate moves declare `vanilla_gift_divergence: <why>` on the village.

8. **Title + names** — `set_message_body(lines, host['chapTitleTextId'], name_message_body(title))`;
   rename any vanilla boss slot's nameplate (`vanilla_name_text_id`) so it doesn't leak; compose the
   title-card image with `_write_chapter_title_card` (add `graphics/chap_title/chap_title_N.png` to
   `PATCHED_DECOMP_FILES`).

9. **`PATCHED_DECOMP_FILES`** — add every decomp file the injector writes (`src/events/chM-eventinfo.h`,
   `src/events/chM-eventscript.h`; `events_udefs.c` + the asset-table `.s` + `chapter_settings.json`
   are already listed). Block-replacements are idempotent, but list them anyway (convention +
   clean restore each build).

10. **Wire into `main()`** — call `inject_chNN(campaign)` after the previous chapter's inject
    (order pins live in `check.py INJECTION_ORDER`; a self-registered tileset carries no cross-injector
    tileset dependency). For a **fast-boot load-test**, add a `--chNN-boot` flag + a `main()` branch
    that calls the injector and `_configure_boot(CHNN_HOST_INDEX)` (New Game reroutes 0 → N), plus a
    `Makefile` `$(if $(CHNNBOOT),--chNN-boot)`.

11. **Declare the new ROM configuration in `tools/playtest/matrix.yaml`** — add `chNNboot:
    {CHNNBOOT: 1}` to `rom_configs`. Every scenario you then write for the chapter gets a row
    (`rom: chNNboot`, `host_chapter: <slot>`), and the chapter gets a suite so `make matrix
    SUITE=chNN` runs the lot off one build. `check.py check_playtest_matrix` fails the build if a
    scenario in `harness.lua` has no row, so this is not optional bookkeeping — it is how
    `run.sh chNNsomething` knows the flag and the host slot without you typing either.
    The row's `kind` is load-bearing beyond timing: `check.py
    check_verdict_scenarios_are_guarded` requires every `kind: verdict` scenario to drive the UI
    through `guardedInput`/`selectSemantic`, never a raw `press` (#238). Capture scenarios are
    `kind: record` and stay exempt — so set `kind` by what the scenario **asserts**, never by its
    name prefix (`recordsupply` and `recordunitlist` are verdict scenarios).

## Load-test it (see the map with units)

```sh
# macOS: apply the decomp shebang fix first (tools/build.sh does it; or the sed loop from it)
make CAMPAIGN=rime-of-the-frostmaiden CH03BOOT=1 fireemblem8.gba   # re-injects + compiles
PT_HOST_CHAPTER=4 tools/playtest/run.sh mapshot                    # New Game -> map, screenshots it
open /tmp/playtest-<scenario>/*-map-loaded.png
```

`mapshot` (harness.lua) = the generic "boot to the map and screenshot the deployed field" scenario.
It is one of the two deliberately chapter-generic scenarios, so it is the one case where you still
pass `PT_HOST_CHAPTER=N` by hand (`inChapter` checks it). Every chapter-specific scenario takes its
host slot and its ROM flag from `matrix.yaml` instead — and `run.sh` refuses outright, in 0s, if the
tree holds a ROM that cannot host it rather than failing seven minutes later for the wrong reason.

Once the chapter has more than a couple of scenarios, drive them together:

```sh
make matrix SUITE=chNN     # one CHNNBOOT=1 build, every chNN scenario, one verdict table
```

## When a scenario fails, read the state before you rebuild

Every terminal controller failure and every proven stall dumps an inspector snapshot into the log
(#236). Read it first — it usually names the defect outright, and it costs no build:

```sh
tools/playtest/inspect_state.py render /tmp/playtest-<scenario>/playtest.log
tools/playtest/inspect_state.py diff /tmp/playtest-<good>/playtest.log /tmp/playtest-<bad>/playtest.log
```

`render` prints the verdict, the rule that produced it, **every rule that was rejected and why**, and
the live procs named by exact script symbol with their idle callbacks resolved. A verdict flagged
`*** UNCLASSIFIED WAIT ***` means FE8 is waiting on something the controller has no name for: add
the proc + its input callback to `gen_symbols.py`, `CALLBACK_NAMES`, `observeController` and a
`classify` rule, and let the *scenario* decide the answer. That is the whole fix for a wait, and it
is how ch01's lord-select Yes/No prompt was closed (#232).

**Naming a new state is not finished until the drivers know about it (#238).** A state that used to
fall through to `generic_menu` was cancellable by `cancelToPlayerMap` and recoverable by
`awaitControllerState`; giving it its own name silently takes that away. Wire its cancel in the same
change. And enumerate a movement action only where the engine would actually move — the bounds
belong in `controller.lua`, read off the same field the engine checks, not hand-rolled in the
scenario.

Three traps this replaces, all of which cost real sessions:

- **Do not re-run a scenario to re-test a hypothesis the evidence already killed.** A budget-bounded
  loop exits at the same frame no matter what is on screen, so an identical frame number proves
  nothing. Instrument for the answer instead.
- **A `transition` is not "nothing is happening".** It is the classifier saying it has no name for
  this. The snapshot's `considered` list tells you what it looked for.
- **A scenario that fails before it presses anything is accusing the harness, not the chapter.**
  ch03's doors and chests read as broken for as long as `baseTile` held a hard-coded address the
  engine had grown past: both scenarios died on the tile READ, before any input, and said
  "placement or gBmMapBaseTiles addr wrong". Check where in the scenario the verdict came from
  before you go looking at the map data. `check_no_hardcoded_symbol_addresses` now makes that
  particular version impossible — every address comes from `SYM` (#238).

## Gotchas (learned the hard way)

- **Tutorial-list terminator is per-chapter typed.** Slot 4's `EventListScr_ChM_Tutorial` is an
  `EventListScr[]` (struct array) → terminate with `END_MAIN`. The prologue's is a pointer array →
  `NULL`. Using the wrong one is an `int-from-pointer` compile error (`events_info.o`).
- **The goal banner ≠ the win trigger.** Copying a `seize`/`defeat_boss` goal only changes the HUD
  text; you still must place the `Seize`/`DefeatBoss` event macro (+ flagged quote) or the map never ends.
- **Register the tileset before the map** or `_register_chapter_map` sys.exits by asset label.
- **No `deployment.deploy_slots` yet?** The real PREP flow (`_deploy_cap_entries`) sys.exits without
  them — fast-boot deploys statically at an authored spawn list instead (author `deploy_slots` when
  wiring the real prep/cutscene pass).
- **Never commit the `fireemblem8u` submodule pointer** — decomp edits are build artifacts restored
  from HEAD each build.
- **Vanilla decomp reads go through HEAD**, never the (dirty) worktree — the build leaves the submodule
  patched, so `git show HEAD:<file>` is the source of truth for vanilla data.
- **Vanilla-map screenshot reference:** `fe8.triangleattack.com` hosts a native-resolution
  (272×256px, 1:1 = 17×16 metatiles, no upscaling) screenshot per vanilla chapter at a predictable
  path (`fe8.triangleattack.com/chapters/<slug>`) — useful ground truth when repainting a Borgo-style
  layout in `gen_map_editor`. Fetchable directly by slug.

## Per-chapter Definition of Done (fast-boot → full host)

- [ ] Map painted (`gen_map_editor` → `import_map_layout`) + YAML `map`/`objective`/`enemy_units` set
- [ ] `inject_chNN` fast-boot: tileset+map registered, party + enemies deploy, `--chNN-boot` load-test PASS
- [ ] Win/lose wired (goal banner + event macro + flagged boss quote if defeat-boss)
- [ ] Real PREP deploy (`deploy_slots` authored) — replaces the static fast-boot spawn
- [ ] Cutscenes (dialogue-pass on the locked beats), recruit wiring, chests/doors, reinforcements
- [ ] Title card art; boss/enemy portrait + map-sprite art
- [ ] Chained: previous chapter's ending `MNC2(0xN)` targets this slot (drop the dev placeholder)
- [ ] Load-test scenarios (`chNN` / `smoke_chNN` / `clear_chNN`) + parity (`make difficulty CH=chNN`)

> **Future refactor (noted):** `inject_ch01/02/03` still duplicate the host skeleton. A config-driven
> `inject_chapter(N)` reading a per-chapter descriptor could collapse them; the shared helpers
> (`_register_chapter_map`, `_retarget_host_chapter`, `_classed_cast`, `_enemy_unit_entry`, …) are
> already the seams. Worth doing once 4–5 chapters exist and the variation is fully mapped.
