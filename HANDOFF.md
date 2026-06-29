# Handoff — Manchego Stars · live state

The **single** live-state doc (one trunk, feature-flow — no per-lane handoffs). **What shipped** →
`git log --oneline -20` + closed issues, not here. **Backlog** → GitHub issues. **Decisions** →
`docs/decisions.md`. **Operating instructions** → `CLAUDE.md`. Run `/handoff` to refresh this file in place.

> **Last session (2026-06-29):** braulo battle anim got a revised peak frame (PR #98), the Knight/lance
> banim donor tooling landed (PR #99), and Ch3 dialogue locked (PR #97). **Wolfram's battle anim is the
> live pickup — its engine/tooling half is merged & inert; it's waiting only on art.** See §Wolfram + the
> ready-to-run prompt pack at the bottom of this file. Nicolas is mobile-only the week of 2026-06-29.

## Workflow — feature-flow
Issue → short-lived `feat/<slug>` branch off `main` → an ephemeral worktree → PR → CI + `/code-review`
→ squash-merge → drop the branch + worktree. No fixed lanes; a feature may span engine + content
(`decisions.md` → Coordination model). Hard invariants: no character/chapter/plot in `.c`/`.s`
(`check.py check_engine_campaign_agnostic`); never commit the `fireemblem8u` submodule pointer.
- **Drive integration end-to-end without asking** (Nicolas, re-emphasized 2026-06-29): cut the branch,
  commit, open the PR, watch CI, squash-merge — all unprompted. Keep branches **tidy** (one feature per
  branch; never mix unrelated WIP). Commit **tested, self-contained tooling slices on their own** the
  moment they're green — don't park finished infra in the working tree waiting on a downstream consumer.

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
- `make TESTCH=1` — Ch1 **sandbox** (whole cast + foes pre-deployed, New Game boots onto the map) for
  playtest **and battle-anim capture**. On macOS apply the shebang fix first (`build.sh` does it for
  test/dist; for a bare `make TESTCH=1`, re-run the `sed '1s|^#!/bin/python3|...'` loop from `build.sh`).

Versioning `v0.<chapters-playable>.<patch>` (`VERSION` file). **Never a bare `make` for a shippable
ROM** (the wrapper applies the decomp shebang fix; a bare `make` dies on the gfx tools on macOS).
ADR: `decisions.md` §Distribution.

## Tools (quick ref)
- `make difficulty CH=chNN` · `make difficulty-gate` (enforcing parity curve) · `make test` · `make check` (drift).
- **Battle-anim pipeline** (`tools/descale_battleframe.py`): hi-res poses → FE8-scale 64×56 frames
  (flip → uniform scale → shared feet anchor → sharpen → palette → 1px outline). **The per-unit recipe
  lives in the unit's YAML comment block** (e.g. `pcs/braulo.yaml` §Battle Animation:
  `--body 44 --sharpen 1.8 --thin-outline --flat "red:3,orange:3,grey:2,brown:3"`, with the source pose
  paths). **READ that comment before regenerating** — don't reconstruct flags from memory (cost a detour
  this session). `--flat` family palette is **crab-tuned** (warm hues: braulo); RBG (green/purple) uses
  adaptive (`--noflip --body 38`, no `--flat`).
- **`bg_to_fe8.py`** `<src-img> <out.png> [--fit crop|pad]` — any image → an FE8 event-BG source PNG
  (240×160, GBA-5bit, tile-banked mode-P, ≤8 banks; reserves transparent index 0). Feed to
  `inject_backgrounds`. Winter-BG catalogue: `map-review/iwd-bg-library.md`.
- **Playtest scenarios** `tools/playtest/run.sh <scenario>` (need a built ROM + `lua`):
  - logic/stability: `win|gameover|ch01win|clear|clear_ch01|smoke|smoke_ch01|fuzz`
  - **ch2 (#22):** `ch02` · `smoke_ch02` · `clear_ch02` (all load a `ch02start` checkpoint).
  - **Battle-anim capture:** `PT_CHAR=<id> tools/playtest/run.sh recordanim` on a `make TESTCH=1` ROM
    (New Game → straight to a forced battle for that unit) → `tools/playtest/make_gif.py recordanim <id>
    --name <id>-anim`. `recordrbg`/`recordlord` too.
  - **ch2 cutscene GIF scenarios live on the unmerged `demo/ch2-gifs` branch:** `recordch02{intro,map,combat,ending}`.
- **Delivery to Nicolas-on-mobile:** commit a **GIF or PNG** (never MP4) to `docs/demo/` + push → he views
  the GitHub blob URL (renders inline on phone). **`make_gif.py` only writes to `map-review/` (gitignored)**
  — to share, **copy the GIF to `docs/demo/` and commit**, or the blob stays stale. In-app file-send +
  `open` in Preview don't reach his phone.

## Now / Next

### Content — Party battle animations (#65 Milestone B) — 2 of 8 PCs done; **wolfram is next, art-blocked**
**RBG + braulo are DONE & merged** (RBG/braulo #94; braulo's revised Action2 peak #98). Pipeline is FE8's
per-CHARACTER `_u25` path — no class slot per unit (`inject_battle_anims` appends the unit's `AnimConf` to
`gUnitSpecificBanimConfigs[]`, sets `_u25`; `_patch_banim_character_unique` routes combat to
`GetBattleAnimationId_WithUnique`). Working templates: `pcs/{prof-rbg,braulo}.yaml` `battle_anim:` blocks.

#### ⭐ Wolfram (#65) — engine half MERGED, waiting on 3 art poses
The **Knight/lance donor tooling is merged & inert** (PR #99): `BANIM_DONORS['knight'] →
(CLASS_ARMOR_KNIGHT, ITYPE_LANCE, melee, 'lance')` + a `lance` `_MELEE_CADENCE` (heavy armored steps +
armored leap + thrust whoosh + screen shake, studied from vanilla `banim_armm_sp1`). Nothing uses it yet —
wolfram is **pure art-in → land** once 3 poses exist. Steps:
1. **Nicolas generates 3 Gemini poses** — edit-from-concept on ref `References/References/PCs/Wolfram full.png`
   (he's a **Mineralscale Drakeborn** — grey living-metal scales, tusks, beard+topknot, frost-crystal
   accents, **warhammer**; NOT a rat — that's RBG). Magenta `#FF00FF` bg. **Prompts are at the bottom of
   this file → §Wolfram prompt pack** (his RBG/braulo template + a *simplify-for-small-sprite* clause).
2. Drop the 3 PNGs anywhere (scratchpad) as `ready/windup/peak`.
3. **Then (Claude's part):** key magenta→alpha → `descale_battleframe.py` (try **adaptive** first — wolfram
   is neutral grey + cool crystals, *not* a `--flat` warm family; compare) → review the 64×56s → add the
   `battle_anim:` block to `pcs/wolfram.yaml` (`clone_from: knight`, `motion: melee`, `cadence: lance`,
   `abbr` ≤12, `frames: [ready,windup,peak]`; **record the descale recipe in a YAML comment**) →
   `make TESTCH=1` → `PT_CHAR=wolfram recordanim` → copy GIF to `docs/demo/` + push → **SHOW Nicolas** → land.

**Motion (3-beat lance fake):** ready = guard, hammer at rest · windup = coiled back, hammer overhead (held
longest, 20t) · peak = lunge & slam to full extension, held through `hit_normal` (engine adds the −40 forward
OAM lunge; feet stay anchored in the art). 3 frames is a hard cap (script refs frames 0/1/2).

#### The other 5 PCs (after wolfram) — donor mapping by class
pinky = Pegasus (lance flier — reuses the lance cadence) · marty + meesmickle = Shaman (dark caster) ·
rootis = Mage (anima caster) · sclorbo = Cleric (staff — may need a heal pose). **meesmickle has a parked
vendored Kitsune anim** at `battle_anims/_parked/`. Each: one `battle_anim:` block + 3 descaled frames, one
feature-flow branch per unit (or small batch), `custom_unit` issue template.
- **Deferred polish (tracked):** braulo's white swing-arc weapon-trail → **#91**; goblin enemy class-level anim → **#90**.

### Content — Ch3 "The Termalaine Mine" (#23) — design LOCKED (#92) + dialogue LOCKED (#97); build beats remain
Vanilla-FE8-Ch3 reskin (Seize; first chests + first thief) as Termalaine's kobold-overrun tourmaline mine.
Teaching goal = the **thief** (Trex = our Colm). Decisions/deviations: `decisions.md` → Ch3 ADR (2026-06-26);
live build checklist on **#23**.
- **NEW (#97):** the **4 cutscene beats are written/locked** (opening / RBG-execution + Trex recruit / Pinky
  shaft-scout / Termalaine ending) co-authored via `dialogue-pass`; Trex lore + `lore/trex.md` landed.
- **Build beats remaining (unchecked on #23, priority order):** map build (`#40`; cave/interior tileset +
  doors + the "open the way down" `TILECHANGE`) → host on the next vanilla slot (`MNC2`; model on
  `inject_ch01`/`inject_ch02`) → units/objective/cutscene wiring (consume the locked `script:` beats) → art
  (Grell/Trex/kobold/giant-rat sprites; **grell ref = book p.96**) → title card → load-test scenarios
  (`ch03`/`smoke_ch03`/`clear_ch03`, mirror ch02). Parity already verified `make difficulty CH=ch03`.
- Ch3+ ending BGs: vendor from the winter-BG library via `bg_to_fe8.py` → `inject_backgrounds`.
- Then chapters #24–#28 (Ch4–Ch8) follow the same vertical-slice pattern.

### Content — Ch2 (#22) — DONE / CLOSED (2026-06-26)
All slice items merged (#85 card, #88 Targos BG + name-leak fix); #22 closed. Non-gating leftover: the demo
reel on the unmerged `demo/ch2-gifs` branch is stale vs the merged fixes — regenerate-vs-drop as a standalone
demo-asset task (ships nothing; v0.1.0 is Ch1-only).

### Parked / supporting
- Enemy/NPC art/anim → convention homes (`inject_battle_anims`/`inject_battle_platforms` docstrings +
  `decisions.md` Art & Audio + `custom_unit` template); one issue per unit.
- Supporting backlog: enemy YAML #18 · NPC stubs #17 · world-map #29 · overworld sprites #38 ·
  onboarding-parity #64 · faked battle anims epic #65.

### Pipeline — playtest / parity
- **Clear-bot #60 — partial landed (#79), STILL OPEN.** BFS distance-field march + multi-range targeting +
  stall watchdog are in; `clear` (prologue) passes fair-play. **Remaining:** the bot jams at ch01's walled
  boss-camp with a thin 2-unit deploy — last-mile breach/unjam logic. Diagnosis on #60.
- **LLM-player #63 — M2 next** (M1 landed): replay-only from a recorded transcript (deterministic, zero
  cost) → M3 live policy (`PT_MODEL`) → M4 soak→curve → M5 vanilla-FE8 validation. Swap: `clearbot.lua pickTarget`.
- **Land `balance_locked: true` on ch00/ch01** (ch02 set); the per-chapter parity gate (#48b) is enforcing
  but inert until a chapter opts in; ch00/ch01 read OK.
- #53 tail (FE8 Ch13 → our ch08): ~11 standard weapons, informational. Other leaves: d20 crit #11,
  spell-economy #9, iconic matchups #8.

## Gotchas (cross-cutting)
- **Per-unit descale recipe is recorded in the unit YAML comment** (data-is-the-doc) — read it before
  regenerating; don't guess flags. Swapping ONE pose still requires re-descaling the **whole 3-frame set
  together** (shared palette recompute shifts the other two — that's correct, not a bug).
- **Battle-anim frames are a hard 3** (ready/windup/peak; script refs frames 0/1/2; `build_battle_anim`
  rejects any other count). The "march" is faked by the per-donor sound/shake cadence + a single engine
  OAM lunge (`MELEE_LUNGE_DX` −40 on peak), not extra art frames.
- **`make_gif.py` writes only to `map-review/` (gitignored).** To share with Nicolas, copy the GIF to
  `docs/demo/` and commit — otherwise the GitHub blob stays stale (bit me this session).
- **Event BGs: vendored winter CGs → NEW `gConvoBackgroundData` slots, additive** (`bg_to_fe8.py` →
  `inject_backgrounds`). **Color index 0 is TRANSPARENT** — using it for a real colour → black holes;
  `bg_to_fe8.py` reserves it. **Only slot 0x36 is free before `BG_RANDOM` (0x37).** Verify event BGs
  **in-engine** (flat preview won't show the holes).
- **Location-card nameplate caps at ~96px** — >~12–14 chars clip silently. Keep `location_card:` short.
- **Vanilla character-slot display names leak** unless the injector overrides it:
  `set_message_body(vanilla_name_text_id(slot), name_message_body(display_name(unit)))`. Give units a short `fe_name` (≤12).
- **Clear-bot can't fully clear a chapter yet (#60).** Helpers that must REACH a later chapter use directed
  seizes / frail+teleport (`reachCh02Map`, `clear_ch02`), not fair-play clears.
- **Don't reuse a playtest checkpoint across an injection/build change** — only across pure graphics-byte
  swaps. Checkpoints are ROM-hash-stamped in `tools/playtest/states/` (gitignored); delete `.ss`/`.romhash`
  to force a rebuild. (A battle-anim frame change IS a build change → re-record from a fresh ROM.)
- **Additive, never global** (content art): clone classes / new terrain/banim/BG slots; never edit a shared
  vanilla one in place.
- **Engine hooks live in `tools/inject/engine_hooks.py`** (guarded by `check_engine_guards_present`).
- **New decomp patch target → add it to `PATCHED_DECOMP_FILES`**, or the build is non-idempotent.
- **Vanilla decomp reads go through `build_campaign.vanilla_decomp_text()` (HEAD)**, never the worktree.
- **`make`-green can't prove apply timing OR rendering** — `tools/playtest/` is the dynamic arbiter. Needs a
  built ROM + `lua`; `run.sh` regenerates `symbols.lua` after a rebuild.
- **CI unit tests run in the `build` job, not the lightweight `checks` job** (need submodule + numpy/PIL).
  mGBA playtest *scenarios* are NOT CI-gated; the `test_*.lua` cores ARE, via `make test`.
- **Distribution is the private pre-patched `.gba`** (decomp build is non-matching vs retail).
- **Save layout must stay stable for testers** (#59): `check_save_layout_stable` reds on layout drift.
- **Writing any dialogue → invoke `dialogue-pass` first.** Story bodies are `make`-regenerated; gate text
  changes with `python3 tools/verify_text.py`. Card/name text is ASCII-folded in `name_message_body`.
- **`msg-id` vetting is treacherous** — `data_battlequotes.c` stores ids 4-digit zero-padded; vet in `0x0XXX` form.
- **Chapter hosting** (model on `inject_ch01`/`inject_ch02`): each chapter rides the *next* vanilla slot,
  chained via `MNC2(<next slot>)`; new snow chapters set `battleTileSet` `0` (open) or `0x15` (rough).
- **Vanilla-only (monster/exotic) weapons belong in `difficulty.py`**, not `WEAPON_ITEM_ENUM`.

---

## §Wolfram prompt pack (run in Gemini — edit-from-concept on `References/References/PCs/Wolfram full.png`, magenta #FF00FF bg)

Preamble (every pose): *"Redraw the referenced character as a full-body Fire Emblem: Sacred Stones GBA
battle sprite — flat cel shading, hard outlines, ≤16 flat colors, three-quarter side view facing right,
flat magenta (#FF00FF) background, no effects. SIMPLIFY for small-sprite readability like a vanilla FE8
sprite: bold chunky shapes, strong clear silhouette, minimal interior detail — drop the tiny rivets,
speckled scales and fine straps, and consolidate the ice-crystal clusters into just one or two bold
accents. Keep only what reads at ~50px tall: his grey metal-scaled body, beard and topknot, the warhammer,
and one bold crystal accent; keep his colors from the reference."*

- **ready** → `Pose: Ready — neutral standing guard, warhammer held at rest in both hands across the body.`
- **windup** → `Pose: Wind-up — coiled back on the rear foot, warhammer hauled high overhead, both arms cocked, knees bent, ready to strike.`
- **peak** → `Pose: Peak — lunging forward, warhammer swung all the way down to full arm extension at the point of impact, front foot planted forward, feet near the same ground spot.`

Tips: generate **ready first**, then make windup/peak **edits of that ready frame** so the simplified design
+ palette carry over. If Gemini won't drop detail, push the simplify clause harder ("flat, almost no
interior lines, think 16-bit"). Magenta or transparent bg both fine — Claude keys the magenta before descale.
