# Handoff — Manchego Stars · live state

The **single** live-state doc (one trunk, feature-flow — no per-lane handoffs). **What shipped** →
`git log --oneline -20` + closed issues, not here. **Backlog** → GitHub issues. **Decisions** →
`docs/decisions.md`. **Operating instructions** → `CLAUDE.md`. Run `/handoff` to refresh this file in place.

## Workflow — feature-flow
Issue → short-lived `feat/<slug>` branch off `main` → an ephemeral worktree → PR → CI + `/code-review`
→ squash-merge → drop the branch + worktree. No fixed lanes; a feature may span engine + content
(`decisions.md` → Coordination model). Hard invariants: no character/chapter/plot in `.c`/`.s`
(`check.py check_engine_campaign_agnostic`); never commit the `fireemblem8u` submodule pointer.

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
- **Playtest scenarios** `tools/playtest/run.sh <scenario>` (need a built ROM + `lua`):
  - logic/stability: `win|gameover|ch01win|clear|clear_ch01|smoke|smoke_ch01|fuzz`
  - **ch2 (#22):** `ch02` (entry asserts) · `smoke_ch02` (soft-lock net) · `clear_ch02` (rout→chain→charms) —
    all load a `ch02start` checkpoint, built once from the real ch00→ch01→ch02 chain.
  - `recordanim` (any cast battle anim on a `TESTCH=1` ROM, `PT_CHAR=<id>`) · `recordrbg` · `recordlord`.
  - `make_gif.py <scenario> <tag> --open` → review GIF.
- **Delivery to friends:** commit a **GIF** (never MP4 — a committed `.mp4` is a binary download, not
  inline on GitHub) to `docs/demo/` + push.

## Now / Next

### Content — Ch2 (#22 REOPENED 2026-06-25) — two demo-review polish items left
Build + dialogue + art + title card merged; structural load-test automated; pacing signed off. Then a
demo-GIF review surfaced two polish items, folded into **#22's vertical-slice checklist** (chapter
feedback rides the slice issue, not standalone — #81/#82 were closed into it). NOT gating Ch3:
- **opening text (`bug`/`content`)** — the "Bryn Shander" location pop-up in the **opening** cutscene
  renders **garbled text**. Check the card text (`CH02_OPENING_CARD_MSG` / `BROWNBOXTEXT` label in
  `inject_ch02`) + `tools/verify_text.py`; recapture `recordch02intro` to confirm.
- **Targos ending BG (`art`)** — the **ending** reuses the generic `BG_NORMAL_VILLAGE` (same as the
  opening). Wants a **darker/colder** distinct backdrop — **vendor a winter/dark-town BG** (FE-Repo
  `gh api … download_url` → curl, like the winter tiles), convert to FE8 BG (additive), point
  `CH02_ENDING_BG` at it. Show Nicolas before committing.
- **Demo reel** lives on the **unmerged `demo/ch2-gifs` branch** (`docs/demo/ch2-cold-welcome.md` —
  opening/map/combat/closing GIFs + the reusable `recordch02{intro,map,combat,ending}` harness
  scenarios). The opening/ending GIFs go **stale once the two items land**, so regenerate + decide
  merge-vs-drop after the fixes.

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

### Content — Ch3 "The Termalaine Mine" (#23) — chapter slice (after the anims / concurrent)
Not started. Reuse the Ch2 vertical-slice component breakdown (tracked as a checklist on the issue):
design+dialogue lock (invoke `dialogue-pass`; ground in DM notes PDF + Frostmaiden book) → map
(`#40` Tiled→`.mar` pipeline) → host on the next vanilla slot (model on `inject_ch01`/`inject_ch02`;
`MNC2(<next>)`) → units/objective/cutscenes → art per `#38/#39` → title card → load-test scenarios
(`ch03`/`smoke_ch03`/`clear_ch03`, mirroring ch02). Then chapters #24–#28 (Ch4–Ch8) follow the same slice.

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
- **Clear-bot can't fully clear a chapter yet (#60).** For helpers that must REACH a later chapter,
  don't rely on a fair-play clear: `reachCh02Map` uses a **directed ch01-seize** (frail escort +
  lord-march), and `clear_ch02` uses **frail+teleport** to rout deterministically (its job is the
  charm-wiring test, not bot combat). A fair-play `clear`/`clear_ch01` is blocked on the #60 breach work.
- **Don't reuse a playtest checkpoint across an injection/build change** — only across pure graphics-byte
  swaps; a stale save-state shows the map/menu, never the battle. Checkpoints are ROM-hash-stamped in
  `tools/playtest/states/` (gitignored); delete the `.ss`/`.romhash` to force a rebuild.
- **Additive, never global** (content art): clone classes / new terrain slots / appended `banim` rows;
  never edit a shared vanilla class/anim/terrain in place. `decisions.md` Art & Audio + the `inject_*` docstrings.
- **Engine hooks live in `tools/inject/engine_hooks.py`** (guarded by `check_engine_guards_present`); engine
  stat changes to the chosen lord go in `EndPrepScreen`, not a phase-start seam.
- **New decomp patch target → add it to `PATCHED_DECOMP_FILES`**, or the build is non-idempotent.
- **Vanilla decomp reads go through `build_campaign.vanilla_decomp_text()` (HEAD)**, never the worktree —
  it also strips inherited git env (`GIT_DIR` overrode `-C` discovery → exit 128 under the pre-commit hook
  in a worktree; don't reach for `--no-verify`).
- **`make`-green can't prove apply timing** — `tools/playtest/` is the dynamic arbiter. Scenarios need a built
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
  bodies are `make`-regenerated; gate text changes with `python3 tools/verify_text.py`.
- **`msg-id` vetting is treacherous** — `data_battlequotes.c` stores ids 4-digit zero-padded (`0x0935`);
  vet in the `0x0XXX` form, not naïve hex-grep. Long unit names overflow FE8's buffer → add a short
  `fe_name` (≤12). Reward placement follows `parity_reference`, not chapter number.
- **Chapter hosting** (model on `inject_ch01`/`inject_ch02`): each chapter rides the *next* vanilla slot
  (ch01→2, ch02→3), chained via `MNC2(<next slot>)`; new snow chapters set `battleTileSet` `0` (open) or
  `0x15` (rough).
- **Vanilla-only (monster/exotic) weapons belong in `difficulty.py`**, not the content-owned `WEAPON_ITEM_ENUM`.
- **Curation gotcha (#48):** filter `events_udefs.c` arrays to RED units that **carry weapons** (excludes
  cutscene arrays + unreferenced skirmish data).
