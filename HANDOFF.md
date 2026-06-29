# Handoff — Manchego Stars · live state

The **single** live-state doc (one trunk, feature-flow — no per-lane handoffs). **What shipped** →
`git log --oneline -20` + closed issues, not here. **Backlog** → GitHub issues. **Decisions** →
`docs/decisions.md`. **Operating instructions** → `CLAUDE.md`. Run `/handoff` to refresh this file in place.

## Workflow — feature-flow
Issue → short-lived `feat/<slug>` branch off `main` → an ephemeral worktree → PR → CI + `/code-review`
→ squash-merge → drop the branch + worktree. No fixed lanes; a feature may span engine + content
(`decisions.md` → Coordination model). Hard invariants: no character/chapter/plot in `.c`/`.s`
(`check.py check_engine_campaign_agnostic`); never commit the `fireemblem8u` submodule pointer.

> **Worktree friction (single-agent):** a fresh worktree's `fireemblem8u` submodule isn't provisioned
> (no `baserom.gba`, no built `scaninc`/toolchain) → builds die late. With no concurrent builds it's
> faster to work a feature branch **in the main tree** (already provisioned) than to set a worktree up.
>
> **BUT concurrent agents MUST each use their own worktree.** Separate branches alone do NOT isolate
> parallel work — the one shared working tree + index means a stray `git add -A`/commit from one agent
> sweeps the other's files into its commit (happened 2026-06-29: the #23 dialogue and #65 braulo work
> tangled on one tree; untangled with no loss, but costly). The main-tree shortcut holds ONLY for a
> single writer. Two agents at once → `git worktree add` per agent (worktree friction is acceptable for
> non-build edits like YAML/lore/docs; builds still need the submodule provisioned).

## Current release
**v0.1.0** friend release — Ch1 playable. Builds:
- `tools/build.sh dist` — **the friend build** (with the #43 opening montage), stamped into `dist/`.
- `tools/build.sh test` — lean dev build (straight-to-map boot).
- `make TESTCH=1` — Ch1 **sandbox** (whole cast + foes pre-deployed, New Game boots onto the map) for playtest.

Versioning `v0.<chapters-playable>.<patch>` (`VERSION` file). **Never a bare `make` for a shippable
ROM** (the wrapper applies the decomp shebang fix; a bare `make` dies on the gfx tools on macOS).
ADR: `decisions.md` §Distribution.

## Tools (quick ref)
- `make difficulty CH=chNN` · `make difficulty-gate` (enforcing parity curve) · `make test` · `make check` (drift).
- **`bg_to_fe8.py`** (new in `tools/`, lands with **PR #88**) `<src-img> <out.png> [--fit crop|pad]` —
  any image → an FE8 event-BG source PNG (240×160, GBA-5bit, **tile-banked** mode-P, ≤8 banks; reserves
  transparent index 0). Feed the output to `inject_backgrounds` (the campaign's `backgrounds/<stem>.png`).
  Winter-BG catalogue: `map-review/iwd-bg-library.md` (FE-Repo shortlist, downloaded to `map-review/iwd-bg-candidates/`).
- **Playtest scenarios** `tools/playtest/run.sh <scenario>` (need a built ROM + `lua`):
  - logic/stability: `win|gameover|ch01win|clear|clear_ch01|smoke|smoke_ch01|fuzz`
  - **ch2 (#22):** `ch02` (entry asserts) · `smoke_ch02` (soft-lock net) · `clear_ch02` (rout→chain→charms) —
    all load a `ch02start` checkpoint, built once from the real ch00→ch01→ch02 chain.
  - **GIF/record scenarios live on the unmerged `demo/ch2-gifs` branch:** `recordch02{intro,map,combat,ending}`
    (+ a 126-line `harness.lua` addition). To re-capture from a feature branch, pull just those two files:
    `git checkout demo/ch2-gifs -- tools/playtest/harness.lua tools/playtest/run.sh` (don't commit them).
    A ROM change re-stamps the checkpoint → a full ch00→ch01→ch02 chain rebuild per capture (~minutes).
  - `recordanim` (any cast battle anim on a `TESTCH=1` ROM, `PT_CHAR=<id>`) · `recordrbg` · `recordlord`.
  - `make_gif.py <scenario> <tag> --open` → review GIF.
- **Delivery to friends / Nicolas-on-mobile:** commit a **GIF or PNG** (never MP4 — a committed `.mp4`
  is a binary download, not inline on GitHub) to `docs/demo/` + push → he views the GitHub blob URL.
  Inline renders + `open` in Preview don't reach him on his phone.

## Now / Next

### Content — Ch2 (#22) — DONE / CLOSED (2026-06-26)
Both demo-review polish items merged (PR #85 ASCII-fold opening card; PR #88 Targos winter BG +
Bazba/Bone→Halvar/Grukk name-leak fix), all slice checklist items checked → **#22 closed**, stale
`blocked` label removed.
- **Non-gating leftover:** the demo reel on the unmerged `demo/ch2-gifs` branch (`docs/demo/ch2-cold-welcome.md`)
  is now **stale** vs the merged fixes → decide regenerate-vs-drop as a standalone demo-asset task. NOT part
  of the slice DoD, ships nothing (v0.1.0 is Ch1-only). Scratch review images live on `review/ch02-ending-bg`
  (not for merge).

### Content — Party battle animations (#65 Milestone B) — 2 of 8 done; NEXT = the other 6 PCs
**RBG + braulo are DONE & merged (PR #94).** The pipeline is FE8's per-CHARACTER `_u25` path — **no
class slot per unit**: `inject_battle_anims` appends the unit's `AnimConf` to `gUnitSpecificBanimConfigs[]`
and sets the character's `_u25`; the `_patch_banim_character_unique` engine hook routes combat to
`GetBattleAnimationId_WithUnique`. Working templates: `campaigns/.../pcs/{prof-rbg,braulo}.yaml`
`battle_anim:` blocks; the `inject_battle_anims` + `_melee_mode_body` docstrings (how) + `decisions.md`
Art & Audio (two 2026-06-26 ADRs, why). **6 PCs still have NO `battle_anim:` block** — do the rest:
- **Per PC:** add a `battle_anim:` block (`clone_from` donor class · `motion: ranged|melee` · `abbr` stem
  ≤12 · `frames: [ready, windup, peak]` — **exactly 3, enforced**). Generate the 3 frames with
  `tools/descale_battleframe.py` from hi-res concept poses (CLAUDE generates art via tooling — Nicolas
  can't draw). **Palette: `--flat` only for warm-hued units (braulo); omit it (adaptive) or pass a
  custom hue spec for green/blue/purple units (RBG) — the default `--flat` families are crab-tuned**
  (see `descale_battleframe.py` FLAT_SPEC). Review: `PT_CHAR=<uid> tools/playtest/run.sh recordanim` → `make_gif.py recordanim <id>
  --name <id>-anim`, commit the GIF to `docs/demo/` + push (GitHub blob = the mobile-review channel).
  **SHOW Nicolas before committing art.**
- **Melee units get the LUNGE free:** `motion: melee` auto-bakes the Pirate-style forward step
  (`MELEE_LUNGE_DX`) + held-peak cadence. New melee donors just need their cadence in `_melee_mode_body`
  if it differs from the axe. Ranged units keep the static anchor (the projectile travels, not the body).
- **Donor mapping by class** (3 poses are archetype-specific, the cadence is the donor's):
  wolfram = Knight (lance melee) · pinky = Pegasus (lance, flier) · marty + meesmickle = Shaman (dark
  caster) · rootis = Mage (anima caster) · sclorbo = Cleric (staff — non-attacker, may need a heal pose).
  **meesmickle has a parked vendored Kitsune anim** at `battle_anims/_parked/`.
- **Deferred polish (tracked, not blocking):** braulo's white swing-arc weapon-trail → **#91**; goblin
  enemy class-level anim → **#90**.
- One feature-flow branch per unit (or a small batch); use the `custom_unit` issue template per PC.

### Content — Ch3 "The Termalaine Mine" (#23) — DESIGN + DIALOGUE LOCKED; map IN PROGRESS (#40, PAUSED on blockout OK)
Design slice merged (PR #92); **all 4 cutscene beats now written + merged (PR #97, dialogue-pass w/ Nicolas).**
Decisions/deviations: `decisions.md` → Ch3 ADR; live build checklist on **#23**.
- **Dialogue DONE (PR #97):** the 4 beats are recorded as `script:` blocks in
  `chapters/ch03-the-termalaine-mine.yaml` (opening / mid-map execution+Trex recruit / Pinky shaft-scout /
  ending). New voice bible `lore/trex.md` (self-taught winged-kobold negotiator; module ghost-possession
  dropped). ch02 ending seeded with RBG's avarice routing the party through Termalaine (motivates the stop).
  **Not host-wired yet** → scripts validated by YAML-parse + drift only; **in-game MOTION REVIEW of all 4
  beats (+ the ch02 seed line) is still owed — it happens at the cutscene-wiring beat, not before.**
- **Mid-map cutscene fires on the BRUTE miniboss's DEFEAT** (the `kobold-steel` "Icewind Brute" slot): flag
  it the miniboss + position it mid-galleries at units/objective wiring. The beaten Brute lunges at Pinky
  (Pinky = RBG's METAL homunculus — claws ring off, no harm) → RBG executes. Pinky-is-metal is load-bearing there.
- **Identity/structure/enemies** (design-locked): Seize big-battle, thief/chests/doors lesson (Trex = our
  Colm); rooms-on-ONE-flat-map (walls + `TERRAIN_DOOR` + one "open the way down" `TILECHANGE`); 1:1 10-slot
  force, **Grell (Mogall L12, Evil Eye)** boss, parity-verified (`make difficulty CH=ch03`). 3 net-neutral
  deviations (monster boss / monster-debut moved ch04→ch03 / ch02↔ch03 gem-hand-axe swap) in the Ch3 ADR.

#### Map (#40) — IN PROGRESS, decisions made 2026-06-29; PAUSED awaiting Nicolas's blockout OK
Two decisions this session change the earlier "reskin vanilla Borgo on a winter tileset" plan:
- **Tileset DECIDED = Cynon's Mineshaft (Gray palette)** — a purpose-built cave/mine tileset (rock walls,
  cart tracks, timber supports, crystal/ore seams, water) vendored from **FE-Repo** (`Klokinator/FE-Repo`
  → `Tilesets/Caves/Cynon's Mineshaft - Tileset`; CC, Cynon endorses cross-engine use). Staged at
  `map-review/ch03-tileset-candidates/cynon-mineshaft-src/` (`.mapchip_config` + Gray object PNG + CREDITS).
  **NO re-palette** — native grey already reads as a frozen Icewind mine (Nicolas's call; the old winter
  re-palette trick is NOT needed for a tileset that's already cave-themed). At build: **credit Cynon in `CREDITS.md`**.
- **Layout PIVOT — author a CUSTOM layout from the book's "Gem Mine" map, NOT a Borgo reskin.** Reference =
  *Frostmaiden* book Map 1.19 "Gem Mine" (printed p.97 = PDF p.98), cropped to
  `map-review/ch03-tileset-candidates/REF-gem-mine-map.png` and `docs/demo/ch03-gem-mine-reference.png`.
  3 levels → ONE flat plane (FE8 has no z-levels), organic caves → 16px grid, ~40sq wide → ~22. A **flattened
  blockout** (book rooms M1–M8 → our chapter beats: M1 tool-room deploy, mid-gallery Brute choke, M3 river
  pinch, M5/M6 sealed shaft = Pinky-scout map-change, M8 grell-lair seize) is **posted on issue #23** and is
  **the pending decision** — Nicolas reviews on mobile this week before any painting starts.
- **Importer is a THIN converter (good #40 news).** Format decoded + validated: `mapchip_config` = **9216 B =
  exactly the decomp config** (8192 TSA + 1024 terrain); object PNG = **256×256 mode-P, 4-bit local indices**
  (pixels 0–15) + a 256-color (16-bank) palette → straight to `ObjectType.4bpp` + `MapPalette.gbapal`. A
  throwaway renderer assembled Cynon's own `Test Map.tmx` correctly →
  `map-review/ch03-tileset-candidates/mineshaft-testmap-gray.png` (= `docs/demo/ch03-mineshaft-tileset-demo.png`),
  proving tiles assemble. So #40 task 2 = a small converter, not a toolchain.
- **Build order once the blockout is OK'd:** (1) write the `mapchip_config`+object-PNG → `.4bpp/.gbapal/.bin`
  converter; vendor as tileset **`cave-interior`** under `campaigns/.../maps/tilesets/`. (2) Seed a paint
  canvas on it from the blockout (extend `gen_map_editor` to load a vendored tileset + a custom/blank layout —
  today it only reskins a vanilla layout on `snowy-bern`). (3) Paint against the reference →
  `import_map_layout` → `.mar` → in-engine load-test. **Enemy/chest positions move off the old Borgo coords
  onto the new layout** (parity unchanged — same 10-unit roster, just repositioned; re-finalize in the map tool).
- **Then (post-map, unchanged):** host on next vanilla slot (`MNC2`; model `inject_ch01`/`inject_ch02`) →
  units/objective/cutscene wiring (`inject_ch03` consumes the `script:` blocks; Brute-defeat trigger,
  Pinky-scout grell spawn + map-change, Trex recruit; new generic mugs `boy-crier`/`kobold-brute`/Maxol) +
  **motion-review the 4 beats** → art (Grell/Trex/kobold/giant-rat; **grell ref = book p.96**) → title card →
  load-test (`ch03`/`smoke_ch03`/`clear_ch03`, mirror ch02).
- Then chapters #24–#28 (Ch4–Ch8) follow the same slice. Ch3+ ending BGs: vendor from the **winter-BG library**
  (`map-review/iwd-bg-library.md`) via `bg_to_fe8.py` → `inject_backgrounds` (relocate `BG_RANDOM` once a 2nd slot is needed).

### Parked / supporting
- Enemy/NPC art/anim → the **convention homes** (`inject_battle_anims`/`inject_battle_platforms`
  docstrings + `decisions.md` Art & Audio + the `custom_unit` issue template); one issue per unit. (The
  PARTY anims are the active next pickup above.)
- Supporting backlog: enemy YAML #18 · NPC stubs #17 · world-map #29 · overworld sprites #38 ·
  onboarding-parity #64 · faked battle anims epic #65.

### Pipeline — playtest / parity
- **Clear-bot #60 — partial landed (#79, 2026-06-25), STILL OPEN.** BFS distance-field march
  (`pathing.lua` + `gBmMapTerrain`), multi-range targeting, a stall watchdog, and a title=loss
  bugfix are in; `clear` (prologue) passes fair-play. **Remaining:** the bot jams at ch01's walled
  boss-camp with a thin 2-unit deploy — last-mile **breach/unjam** logic (field more units / slip a
  chokepoint / focus-fire the nearest reachable straggler). Precise diagnosis on issue #60.
- **LLM-player #63 — M2 next** (M1 landed): sidecar + `llmDrive` handshake, **replay-only** from a
  recorded transcript on a built ROM (deterministic, zero LLM cost). Then M3 live policy (`PT_MODEL`,
  per `claude-api` skill) → M4 soak→curve → M5 vanilla-FE8 validation. Swap point: `clearbot.lua pickTarget`.
- **Land `balance_locked: true` on ch00/ch01** (ch02 already set) — the per-chapter parity gate (#48b)
  is enforcing but inert until a chapter opts in; ch00/ch01 read OK on the curve.
- #53 tail (FE8 Ch13 ref → our ch08): ~11 standard weapons to model; informational (ch08 is
  scripted-defeat, never CI-gated) — do only if idle. Other mechanics leaves: d20 crit #11,
  spell-economy #9, iconic matchups #8.

## Gotchas (cross-cutting)
- **Event BGs: vendored winter CGs → NEW `gConvoBackgroundData` slots, additive.** `bg_to_fe8.py`
  (any image → 240×160 tile-banked PNG) → `inject_backgrounds` (copies to `graphics/bg/`, appends the
  enum id `backgrounds.h` + extern decls `bg.h` + table row `eventscr2.c` + incbin symbols `data_bg.s`;
  make's generic gbagfx/FETSATOOL rules build the bins). The 4 patched files are in `PATCHED_DECOMP_FILES`.
  **Only slot 0x36 is free before `BG_RANDOM` (0x37)** — a 2nd campaign BG must relocate BG_RANDOM first
  (verify nothing hardcodes 0x37 in-engine).
- **Event-BG color index 0 is TRANSPARENT** — a GBA BG renders index-0 pixels as the backdrop (FE8 sets
  it black). A converter that uses local index 0 for a real colour → **black holes** wherever that colour
  appears (the bright sky/snow speckled black on the first Targos capture). `bg_to_fe8.py` reserves
  index 0 (colours start at local 1). A flat-quant *preview* won't show this — **verify event BGs in-engine.**
- **Location-card nameplate caps at ~96px** — `BROWNBOXTEXT`/`StartBrownTextBox` draws the card text as
  exactly 3×32px sprites (`popup.c` `BrownTextBox_Loop`); the border grows but the text region is fixed,
  so >~12–14 chars clip silently. Keep `location_card:` to short place names ("Targos", "Bryn Shander");
  push detail into the scene/dialogue. Companion to the text terminator-parity gotcha (`decisions.md`).
- **Vanilla character-slot display names leak.** A boss/miniboss riding a vanilla slot (Bazba/Bone/
  Breguet/O'Neill) shows the *vanilla* name on the unit window + death quote unless the chapter injector
  overrides it: `set_message_body(vanilla_name_text_id(slot), name_message_body(display_name(unit)))`
  (see `inject_ch01`/`inject_ch02`). Give the unit a short `fe_name` (≤12).
- **Clear-bot can't fully clear a chapter yet (#60).** For helpers that must REACH a later chapter,
  don't rely on a fair-play clear: `reachCh02Map` uses a **directed ch01-seize** (frail escort +
  lord-march), and `clear_ch02` uses **frail+teleport** to rout deterministically (its job is the
  charm-wiring test, not bot combat). A fair-play `clear`/`clear_ch01` is blocked on the #60 breach work.
- **Don't reuse a playtest checkpoint across an injection/build change** — only across pure graphics-byte
  swaps; a stale save-state shows the map/menu, never the battle. Checkpoints are ROM-hash-stamped in
  `tools/playtest/states/` (gitignored); delete the `.ss`/`.romhash` to force a rebuild.
- **Additive, never global** (content art): clone classes / new terrain slots / appended `banim` rows /
  appended BG slots; never edit a shared vanilla class/anim/terrain/BG in place. `decisions.md` Art & Audio
  + the `inject_*` docstrings.
- **Engine hooks live in `tools/inject/engine_hooks.py`** (guarded by `check_engine_guards_present`); engine
  stat changes to the chosen lord go in `EndPrepScreen`, not a phase-start seam.
- **New decomp patch target → add it to `PATCHED_DECOMP_FILES`**, or the build is non-idempotent.
- **Vanilla decomp reads go through `build_campaign.vanilla_decomp_text()` (HEAD)**, never the worktree —
  it also strips inherited git env (`GIT_DIR` overrode `-C` discovery → exit 128 under the pre-commit hook
  in a worktree; don't reach for `--no-verify`).
- **`make`-green can't prove apply timing OR rendering** — `tools/playtest/` is the dynamic arbiter
  (apply timing, soft-locks, **and BG/sprite rendering** — see the index-0 holes). Scenarios need a built
  ROM + `lua` (`brew install lua`); regenerate `symbols.lua` (auto by `run.sh`) after a rebuild.
- **CI unit tests run in the `build` job, not the lightweight `checks` job** (they need the submodule +
  numpy/PIL); a new test needing a new lib → add it to the `build` job's deps. Playtest *scenarios* (mGBA)
  are NOT CI-gated; the pure `test_*.lua` cores (incl. `test_pathing.lua`, `test_ch02check.lua`) ARE, via `make test`.
- **Distribution is the private pre-patched `.gba`** — the decomp build is non-matching vs retail (~67% of
  bytes differ), so no small public patch exists. `tools/make_bps.py` is correct but intentionally unwired.
- **Save layout must stay stable for testers** (#59): `check_save_layout_stable` reds on a `BWL_ARRAY_NUM`/
  `WIN_ARRAY_NUM`/`SAVEMAGIC` drift → that drop needs a per-release starter `.sav`.
- **Writing any dialogue → invoke `dialogue-pass` first** (voice grounding: per-NPC `lore/*.md` §Voice +
  `frostmaiden-voices.md`; story sources: the DM-notes PDF + the Frostmaiden book via `pdftoppm`). Story
  bodies are `make`-regenerated; gate text changes with `python3 tools/verify_text.py`. **Card/name text
  from YAML is ASCII-folded centrally in `name_message_body`** (em-dash → `--`), so keep authored unicode.
- **`msg-id` vetting is treacherous** — `data_battlequotes.c` stores ids 4-digit zero-padded (`0x0935`);
  vet in the `0x0XXX` form, not naïve hex-grep. Long unit names overflow FE8's buffer → add a short
  `fe_name` (≤12). Reward placement follows `parity_reference`, not chapter number.
- **Chapter hosting** (model on `inject_ch01`/`inject_ch02`): each chapter rides the *next* vanilla slot
  (ch01→2, ch02→3), chained via `MNC2(<next slot>)`; new snow chapters set `battleTileSet` `0` (open) or
  `0x15` (rough).
- **Vanilla-only (monster/exotic) weapons belong in `difficulty.py`**, not the content-owned `WEAPON_ITEM_ENUM`.
- **Curation gotcha (#48):** filter `events_udefs.c` arrays to RED units that **carry weapons** (excludes
  cutscene arrays + unreferenced skirmish data).
