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

### Content — Party battle animations (#65 Milestone B) — NEXT SESSION pickup (Nicolas)
RBG validated the faked-anim pipeline end-to-end (#65 **Milestone A**, merged): donor-prime, additive,
3 static AI frames (Ready / Wind-up / Peak) cloned onto a donor class's cadence — see
`campaigns/.../pcs/prof-rbg.yaml` `battle_anim:` block as the working template, and the
`inject_battle_anims` docstring (how) + `decisions.md` Art & Audio (why). **7 party members still have NO
`battle_anim:` block** — do the rest:
- **Per PC:** add a `battle_anim:` block (clone_from donor class · clone_into an additive `*_EMPTY`
  CLONE class slot · `abbr` stem ≤12 · `frames: [ready, windup, peak]`); generate frames with
  `tools/ref_to_battleframe.py` (concept ref → 16-colour indexed sheet + OAM + palette — Nicolas can't
  draw, CLAUDE generates via tooling); `inject_battle_anims` appends one `banim_data[]` row + repoints
  the class; review with `tools/playtest/run.sh recordanim PT_CHAR=<uid>` → `make_gif.py recordanim <id>
  --open`. **Custom art is the lever — go custom per concept art; SHOW Nicolas before committing.**
- **Donor mapping by class** (the 3 poses are archetype-specific, the cadence is the donor's):
  braulo = Fighter (axe melee) · wolfram = Knight (lance melee) · pinky = Pegasus (lance, flier) ·
  marty + meesmickle = Shaman (dark caster) · rootis = Mage (anima caster) · sclorbo = Cleric (staff).
- One feature-flow branch per unit (or a small batch); use the `custom_unit` issue template per PC.

### Content — Ch3 "The Termalaine Mine" (#23) — DESIGN LOCKED (PR #92 merged 2026-06-26); build beats remain
The full design slice is regrounded, parity-verified, and merged. Decisions/deviations live in
`decisions.md` → **Ch3 ADR (2026-06-26)**; the live build checklist is on **#23**. State of the design:
- **Identity:** reskins **vanilla FE8 Ch3 "The Bandits of Borgo"** (Seize big-battle; FE8's first chests +
  first thief) as Termalaine's kobold-overrun tourmaline mine. Teaching goal = the **thief** (Trex = our
  Colm), made to matter by door/chest-gated rooms. Grounded in the DM notes + the Frostmaiden book
  "A Beautiful Mine" (pp.93–96).
- **Structure:** rooms-on-ONE-flat-map (FE8 has no z-levels) — walls + `TERRAIN_DOOR` + one scripted
  "open the way down" `TILECHANGE`. (Multi-level/Tower-Ruins structure reserved for a future prison-break.)
- **Enemies:** 1:1 reskin of vanilla Ch3's 10-slot force — kobolds + a giant rat + the **Grell (Mogall L12,
  Evil Eye)** as boss. **Parity verified** `make difficulty CH=ch03` (clear-load ×0.99, threat ×1.12, in band).
- **3 deviations (net-neutral, ADR):** boss is a real monster (Mogall, not a frailty cheat); monster-debut
  moved ch04→ch03 (`introduces` ledger); ch02↔ch03 gem/hand-axe swap (ch02 chwinga-mote now gifts a Hand Axe,
  the Red Gem moved to a ch03 tourmaline chest — total wealth unchanged).
- **Recruit:** Trex (canon winged kobold leader) defects mid-map.
- **Build beats remaining (unchecked on #23, priority order):** `dialogue-pass` for the 4 cutscene beats
  (opening / RBG-execution + Trex recruit / Pinky shaft-scout reveal / Termalaine ending) → map build
  (`#40`; cave/interior tileset + doors + the map-change) → host on the next vanilla slot (`MNC2`; model on
  `inject_ch01`/`inject_ch02`) → units/objective/cutscene wiring → art (Grell/Trex/kobold/giant-rat sprites;
  **grell ref = book p.96**) → title card → load-test scenarios (`ch03`/`smoke_ch03`/`clear_ch03`, mirror ch02).
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
