# Handoff — Manchego Stars · live state

The **single** live-state doc (one trunk, feature-flow — no per-lane handoffs). **What shipped** →
`git log --oneline -20` + closed issues, not here. **Backlog** → GitHub issues. **Decisions** →
`docs/decisions.md`. **Operating instructions** → `CLAUDE.md`. Run `/handoff` to refresh this file in place.

> **Last session (2026-06-29):** braulo battle anim got a revised peak frame (PR #98), the Knight/lance
> banim donor tooling landed (PR #99), and Ch3 dialogue locked (PR #97). **Wolfram's battle anim is the
> live pickup — its engine/tooling half is merged & inert; it's waiting only on art.** See §Wolfram; the
> ready-to-run prompt pack is in `lore/wolfram.md`. **Ch3 map (#40) also moved:** tileset decided
> (Cynon's Mineshaft, Gray) + layout pivot to a custom Gem-Mine plan — **flattened blockout posted on #23,
> awaiting Nicolas's OK** (see §Map (#40)). Nicolas is mobile-only the week of 2026-06-29.

> **🛠 Desktop fix needed — branch cleanup + env policy (2026-06-29; re-probed 2026-07-02):** An audit
> found **13 stale remote branches** the squash-merge convention should have deleted. 2026-07-02 web
> re-probe: the env can now **push to branches and squash-merge PRs via the GitHub MCP** (PR #101 was
> conflict-resolved and merged from the web) — but **ref-deletes are still blocked** (`git push
> --delete` hangs at the proxy; no repo-settings API either). **To do from desktop:**
>
> 1. **Flip the GitHub repo setting "Automatically delete head branches"** (Settings → General →
>    Pull Requests; mobile-reachable). That sweeps every squash-merged branch on merge so this
>    backlog can't re-accumulate. **After flipping, squash-merging this PR will auto-delete
>    `claude/branch-cleanup-1c1081`** — one less branch to chase manually.
> 2. **Delete the stale branches.** From a local checkout:
>    ```sh
>    git push origin --delete \
>      claude/audit-open-branches-5suz48 claude/content-track-review-5rpjy8 \
>      docs/descale-palette-guidance docs/handoff-65-mb-done docs/handoff-ch3-map-pickup \
>      feat/19-vellynne-portrait feat/22-ch02-dialogue-reground feat/22-title-card \
>      feat/38-chwinga-map-sprites feat/39-chwinga-portraits feat/engine-name-check \
>      review/ch02-ending-bg
>    ```
>    (`docs/handoff-ch3-map-pickup` joined the list when PR #101 squash-merged, 2026-07-02.)
>    **`demo/ch2-gifs` is deliberately NOT on the list** — it still holds the only copy of the
>    unmerged `recordch02*` cutscene-GIF scenarios; decide regenerate-vs-drop first (§Ch2), then delete.
> 3. **Fix the Claude-Code-on-the-web env so future sessions can delete refs themselves.** Two checks:
>    (a) **github.com/settings/installations → Claude** — confirm *Contents* is read-and-write and
>    this repo is in the access list; (b) the env's network policy in claude.com/code → this
>    environment's settings — bump to a policy that allows full GitHub write (see
>    https://code.claude.com/docs/en/claude-code-on-the-web for policy names). Verify by asking the
>    next web session to delete a throwaway branch end-to-end.

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
   accents, **warhammer**; NOT a rat — that's RBG). Magenta `#FF00FF` bg. **Prompts:
   `lore/wolfram.md` → §Battle-anim prompt pack** (his RBG/braulo template + a *simplify-for-small-sprite* clause).
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
- **Wiring notes owed later:** in-game **MOTION REVIEW of all 4 beats** (+ the ch02 seed line) happens at
  the cutscene-wiring beat. **Mid-map cutscene fires on the BRUTE miniboss's DEFEAT** (the `kobold-steel`
  "Icewind Brute" slot): flag it the miniboss + position it mid-galleries at units/objective wiring
  (Pinky-is-metal is load-bearing in that beat).

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
  **the pending decision** — Nicolas reviews on mobile before any painting starts.
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
  load-test (`ch03`/`smoke_ch03`/`clear_ch03`, mirror ch02). Parity already verified `make difficulty CH=ch03`.
- Then chapters #24–#28 (Ch4–Ch8) follow the same slice. Ch3+ ending BGs: vendor from the **winter-BG library**
  (`map-review/iwd-bg-library.md`) via `bg_to_fe8.py` → `inject_backgrounds` (relocate `BG_RANDOM` once a 2nd slot is needed).

### Content — Ch2 (#22) — DONE / CLOSED (2026-06-26)
All slice items merged (#85 card, #88 Targos BG + name-leak fix); #22 closed. Non-gating leftover: the demo
reel on the unmerged `demo/ch2-gifs` branch is stale vs the merged fixes — regenerate-vs-drop as a standalone
demo-asset task (ships nothing; v0.1.0 is Ch1-only). Scratch review images live on `review/ch02-ending-bg`
(not for merge).

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

**Moved (2026-07-02 audit): the durable gotcha list lives in `docs/decisions.md` → §Operational
Gotchas.** Read it at session start alongside this file. Only *session-scoped* gotchas belong here.
