# Handoff — Manchego Stars · live state

The **single** live-state doc (one trunk, feature-flow — no per-lane handoffs). **What shipped** →
`git log --oneline -20` + closed issues, not here. **Backlog** → GitHub issues. **Decisions** →
`docs/decisions.md`. **Operating instructions** → `CLAUDE.md`. Run `/handoff` to refresh this file in place.

> **Last session (2026-07-06, desktop — ch03 goes PLAYABLE in-engine):** the Termalaine Mine is now
> painted, hosted, and load-tested. Merged via **PR #139** (editor) + **PR #140** (host).
> **① Map painted + imported.** Nicolas hand-painted the ch03 floor/entrance on `cave-interior` in the
> editor → `import_map_layout` → `maps/ch03-the-termalaine-mine.mar` (17×16, 210/272 cells changed).
> **② Map-painter upgraded (PR #139, #40):** right pane is now an **eyedropper demo-map** (click a tile
> off Cynon's mineshaft → brush); **`--vanilla=Ch3Map`** renders the real Borgo reference (resolves the
> layout's OWN tileset by backward-scanning the asset table); thinner 1px gridlines; and an
> **engine-accurate passability overlay** — the green/red WALK set now reads FE8's own move-cost table
> (`data_terrains.s`), which proved the cave floor `0x2a`=SHIP_FLAT is walkable (cost 1). The map was
> never broken; the old hardcoded snow WALK list just mislabeled it.
> **③ ch03 HOSTED on slot 4 (PR #140, #23):** `inject_ch03` registers the cave tileset + layout, deploys
> the classed party at the left entrance + the **10 vanilla-Ch3-parity foes** at their vanilla tiles.
> **`--ch03-boot`** (`make CH03BOOT=1`) + the reusable **`mapshot`** scenario (`PT_HOST_CHAPTER=4`)
> LOAD-TESTED in mGBA → chapter 4, units deployed, **"Defeat boss"** banner. Shot:
> `docs/demo/ch03-loadtest-map.png` (regenerate: `PT_HOST_CHAPTER=4 tools/playtest/run.sh mapshot`).
> **④ Design calls (Nicolas):** objective **Seize → Defeat Boss** (kill the grell; decisions.md item 4);
> grell **visible from turn 1**; vanilla thief slot → **Svirfneblin Skulk** (NOT a rat — RBG & Pinky are
> the party's rats); enemy positions/items filled 1:1 from the decomp. A **2026-07-06 narrative reframe**
> — enemy kobolds are a FERAL splinter Trex is purging to clear his warren's name; RBG executes a feral
> one; Pinky's scout folds into the OPENING — is captured in the ch03 YAML `design_notes`, **PENDING a
> dialogue-pass** on the #97 beats (they now partially disagree with it).
> **⑤ Repeatable process (Nicolas's ask):** **`docs/adding-a-chapter.md`** — the host-a-chapter runbook
> (slot mapping, goal donors, win-wiring, gotchas, per-chapter DoD), linked from CLAUDE.md. Config-driven
> `inject_chapter(N)` refactor filed as **#138**. **ch04 is now a doc-follow, not a rediscovery.**
> **Nicolas-at-home queue:** generate **Wolfram's 3 poses** (unblocks #65 — the last art-blocker).
> **Remaining ch03 build beats = the #23 checklist** (win-wiring, PREP, cutscenes, art, chaining; see §Ch3).

> **Prior session (2026-07-03→04, web/mobile — Nicolas co-writing from his phone):** a full
> dialogue-pass + rulings session, merged via PRs #127 #128 (+ a BG/ruling PR at wrap):
> **ch04 "The White Moose" dialogue LOCKED** — all 4 beats co-written, review-trimmed (all Ravisin
> dread consolidated into Lupin's single ending line), recorded in the ch04 YAML `script:` blocks.
> **`lore/lupin.md` voice bible NEW** (blunt pack-pragmatist; table-canon wolf grounded in the book's
> awaken magic). **Lonelywood Speaker = Nimsy Huddle** (book name, table's deaf-granny performance;
> voices doc §Per-town). **Lupin portrait SHIPPED** (`portraits/lupin.png` + `lupin_darken.py` hand
> pass; original ref vendored in-repo — TotalityDesigns Redbubble find, credited). **Reference-don't-
> import principle extended twice (Nicolas rulings):** Nimsy's mug = the VANILLA old-lady generic by
> portrait id (an FE-Repo import was drafted and rejected), and cutscene BGs = reuse `bg_TargosWinter`
> for ch03 Termalaine + vanilla `House1` by id for ch04's cottage; ch03 mid-map beats play on-map.
> **Ch3 layout RULED (the #23 pending decision):** the proposed custom Gem-Mine blockout is REJECTED —
> **repaint vanilla Borgo geometry with the `cave-interior` tiles** (decisions.md ADR 2026-07-04; the
> ch03 YAML's `base_layout: Ch3Map` was never actually changed). **NEW capability:** this web container
> CAN read public GitHub repos via `git clone --filter=blob:none --no-checkout` + raw.githubusercontent
> (only api.github.com/web-UI are proxy-gated; cross-owner `add_repo` unsupported) — FE-Repo asset
> vendoring and decomp layout reads work from the web now; scratchpad clones of `FE-Repo` + `fireemblem8u`
> were used this session. **Next up: the ch03 Borgo→mine retile** (fetch `Ch3Map` layout + vanilla
> village tile config from the decomp clone, terrain-preserving retile onto `cave-interior`, PNG
> preview to Nicolas). Still open from before: Wolfram poses (art-blocked on Nicolas) · local-mGBA
> `clear_ch01` (#60) + `llm --record` (#63) · #125 msg-id risk · desktop stale-branch deletion (below).

> **Branch hygiene (resolved 2026-07-06, desktop):** the stale-branch backlog is **cleared** — all 14
> dead remotes deleted (the 12 audited + `claude/branch-cleanup-1c1081` + `review/ch03-borgo-retile-preview`,
> plus the fully-merged `claude/compound-engineering-plugin-37vinv`). "Automatically delete head branches"
> is ON (Nicolas, 2026-07-02) so the backlog can't re-accumulate. Remotes now = `main`, `demo/ch2-gifs`
> (**deliberately kept** — only copy of the unmerged `recordch02*` cutscene-GIF scenarios; decide
> regenerate-vs-drop per §Ch2 before deleting), and any live PR branch.
> **Residual (web-env only):** Claude-Code-on-the-web still can't `git push --delete` (proxy-gated) — desktop
> sessions can. If future web sessions need self-serve ref-deletes, bump the env network policy to full
> GitHub write (claude.com/code → env settings; https://code.claude.com/docs/en/claude-code-on-the-web).

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
  - **LLM commander (#63):** `llm` — needs the sidecar running (`llm_player.py serve`; see run.sh header).
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

### Content — Ch3 "The Termalaine Mine" (#23) — map BUILT + HOSTED + load-tested; win/cutscenes/art remain
Vanilla-FE8-Ch3 reskin as Termalaine's kobold-overrun tourmaline mine. Teaching goal = the **thief**
(Trex = our Colm). Decisions: `decisions.md` → Ch3 ADR (four deviations + **item 4 = Defeat Boss**) + the
ch03 YAML `design_notes` (2026-07-06 narrative reframe). **Live build checklist = #23 (the source of truth);
how-to for the host machinery = `docs/adding-a-chapter.md`.**
- **DONE (2026-07-06):** map painted on `cave-interior` (Cynon's Mineshaft, Gray; credited) + imported;
  `inject_ch03` hosts vanilla **slot 4** (Ch4 symbols), deploys party at the left entrance + 10 foes at
  vanilla-Ch3 tiles (grell@14,1); `--ch03-boot` + `mapshot` load-test PASS. Objective = **Defeat Boss**;
  grell visible turn 1; vanilla thief slot = **Svirfneblin Skulk**; positions/items 1:1 from the decomp.
- **REMAINING (unchecked on #23, priority order):**
  1. **DefeatBoss WIN wiring** — `DefeatBoss(grell)` in the Ch4 Misc list + a flagged `EVFLAG_DEFEAT_BOSS`
     grell defeat quote + an ending scene (pattern: `inject_prologue`; recipe: runbook step 7). Today the
     banner reads "Defeat boss" but **nothing ends the map** (Misc = only `CauseGameOverIfLordDies`).
  2. **Real PREP deploy** — author `deployment.deploy_slots` (9 tiles) in the ch03 YAML + a PREP CALL;
     today it's a static fast-boot spawn (`CH03_SPAWN_POSITIONS`, left entrance).
  3. **Chain ch02→ch03** — point ch02's ending `MNC2(0x4)` at ch03 (drop the ch02 dev-placeholder landing).
  4. **Cutscenes** — run a **dialogue-pass on the REFRAMED beats first** (feral faction / grell visible /
     Pinky→opening / RBG executes a feral one), then wire (#58 opaque-box). Mid-map cutscene fires on the
     BRUTE miniboss (`kobold-steel`) defeat — flag it miniboss + position mid-galleries at wiring
     (Pinky-is-metal is load-bearing there). Motion-review all beats in-engine at wiring.
  5. **Chests/doors** — per-chest **`17→29` TILECHANGE** (FE8 `EventScr_OpenChest`; vanilla Ch3 has one per
     chest); Trex opens, the two key-droppers are backup. (Floor-terrain parity is a non-issue — `0x2a` is
     walkable, confirmed via the move-cost table.)
  6. **Art** — Grell (Mogall reskin, book p.96) · Trex (winged kobold) · Icewind kobold + **Svirfneblin
     Skulk** sprites; show Nicolas before commit.
  7. **Title-card image** ("Ch.3: The Termalaine Mine", vanilla letterforms) + **load-test scenarios**
     `ch03`/`smoke_ch03`/`clear_ch03` (mirror ch02). Parity already PASS (`make difficulty CH=ch03`).
- **Cutscene BGs DECIDED 2026-07-04 (Nicolas): reference, don't import** — ch03 opening+ending reuse the
  ch02 `bg_TargosWinter` slot; mid-map beats play ON-MAP. (ch04's cottage = vanilla `House1` by BG id.)
- Then chapters #24–#28 (Ch4–Ch8) follow the same slice — now via **`docs/adding-a-chapter.md`**.

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
- **Clear-bot #60 — code complete (PR #116), needs a local `clear_ch01` mGBA confirm to close.**
  `pickMove` march core (field-first, claimed-tile avoidance, cork-jam fallback) + the root-cause fix:
  `selectAndReach`'s default 15×10 window clipped ch01 reach at x=14 — bounds now threaded.
- **LLM-player #63 — M1+M2 landed (PR #118), M3 next.** Sidecar file-handshake + `llm` scenario +
  provider-agnostic policy (`PT_PROVIDER=openai` + local Ollama = free Llama/Gemma; anthropic/Sonnet
  default per the epic). First local run: sidecar `--record` to mint `transcripts/prologue.json`, then
  replay is free forever. M3 = staff driving + multi-target disambiguation → M4 soak→curve → M5 vanilla-FE8.
- **`balance_locked: true` is LIVE on ch00/ch01/ch02** — the per-chapter parity gate (#48b,
  `make difficulty-gate`, in CI) actively enforces all three; new chapters opt in as their enemy
  inventories are authored and playtested.
- #53 tail (FE8 Ch13 → our ch08): ~11 standard weapons, informational. Former leaves settled 2026-07-02:
  d20 crit #11 ✓ · iconic matchups #8 **reverted + closed not-planned** (vanilla principle covers item
  data; flavor only) · spell-economy #9 = vanilla behavior incl. break-and-rebuy (content lands per-chapter).

## Gotchas (cross-cutting)

**Moved (2026-07-02 audit): the durable gotcha list lives in `docs/decisions.md` → §Operational
Gotchas.** Read it at session start alongside this file. Only *session-scoped* gotchas belong here.
