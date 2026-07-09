# Handoff — Manchego Stars · live state

The **single** live-state doc (one trunk, feature-flow — no per-lane handoffs). **What shipped** →
`git log --oneline -20` + closed issues, not here. **Backlog** → GitHub issues. **Decisions** →
`docs/decisions.md`. **Operating instructions** → `CLAUDE.md`. Run `/handoff` to refresh this file in place.

> **Last session (2026-07-08 #2, desktop — recruit UNITS + a reusable recruit model; PR #146 OPEN, not merged):**
> **① Reusable recruit model (decisions.md → "Recruit wiring" ADR):** a recruit is just a **classed cast
> member + a `recruit.chapter:`** in its YAML — no generic recruit engine (explicitly rejected). Prep
> availability is one data-driven filter, **`cast_available_at(N)`** = founding party + recruits whose recruit
> chapter is *before* N (replaces the old `starting_only` flag; `inject_ch01/02/03` call it; `available_at=None`
> = everyone, for sprites/stats/death-quotes). Each JOIN uses vanilla FE8 primitives **per its own method**.
> **② Trex** = real unit on the **Rennac** slot (Colm donor), placed **GREEN** on the ch03 map = a **Colm-style
> TALK recruit** (`CHAR`+`CUSA`, cf. `EventScr_Ch3_Talk_NeimiColm`). On talk, `CUSA` flips him to player faction
> → he renders in the **cast OBJ palette** (NOT vanilla blue). **③ Baxby** = promoted from cutscene-face
> (`GUEST_PORTRAIT_MAP`) to a **real unit** on the **Forde** slot (Franz donor, Cavalier). His hand-painted
> 32×32 axe-beak map sprite injects on the **standard cast pattern** — `base: Gargoyle` (32×32 3-frame GEOMETRY
> token, NOT the FE-Repo source string) + synth MU, exactly like braulo/wolfram/meesmickle. (Gotcha I hit: I
> briefly "parked" it citing a bogus geometry mismatch — the fix was just the right `base:` token. **Check a
> sibling YAML for the pattern before inventing.**) **④** New **`ch03` playtest scenario** (PASS): `blue[08]=0x10`
> Baxby + `green Trex 0x1C @ (10,6)`. 55 unit tests green, verify_text clean, `make CH03BOOT=1` green.
> **⑤ LOCKED (Nicolas):** Trex's recruiter = **ANY core party member** (he's the only thief → must be
> non-missable; guarantees the force-deployed *chosen* lord works; a static `CHAR` entry can't name the runtime
> lord). Telegraph **Joshua-style** (hint line + FE8's auto Talk prompt).
> **⚠ GAP FOUND & EMPIRICALLY CONFIRMED (the next task):** cutscene-recruited units **do not persist** into
> later chapters. ch02 **persists** the party from ch01 and the availability filter only sizes the deploy **cap
> template (never LOADed)** — nothing LOADs Baxby, so the ch02 `ch02` scenario blue array is `0x01..0x08`, **no
> Baxby (0x10)**. Only affects **cutscene** recruits (Baxby); **talk** recruits (Trex) are fine — `CUSA` joins
> them directly. Fix = a per-chapter **join-LOAD of newly-available cutscene recruits** (see Now/Next).

> **Prior sessions (all MERGED; detail in git log / closed issues):** ch03 **DefeatBoss WIN** + `ch03win`
> scenario (PR #143; **gotcha, decisions.md §Operational Gotchas:** the win fires from the FLAGGED grell quote
> pid `0xb7`/`EVFLAG_DEFEAT_BOSS`, NOT `CA_BOSS` → no boss HP gauge + the generic clear-bot can't target it).
> Trex bust (PR #142). ch03 map painted on `cave-interior` (`maps/ch03-the-termalaine-mine.mar`, 17×16) +
> hosted on slot 4 with the classed party + 10 vanilla-Ch3-parity foes (PRs #139/#140); objective **Defeat
> Boss** (grell@14,1, visible turn 1); thief slot = Svirfneblin Skulk. **2026-07-06 narrative reframe**
> (feral-splinter kobolds / Trex's clear-our-name motive / RBG executes a feral one / Pinky scout → opening)
> in the ch03 YAML `design_notes`, still **PENDING a dialogue-pass** on the #97 beats. Runbook
> **`docs/adding-a-chapter.md`**; config-driven `inject_chapter(N)` filed as #138. ch04 dialogue LOCKED
> (PRs #127/#128); `lore/lupin.md` voice bible; cutscene BGs reference-not-import (`bg_TargosWinter` for ch03).
> **VANILLA Ch3 "Bandits of Borgo" recruit reference (decomp, for the dialogue repass):** the thief is
> **Colm** — a **green (AI) unit** placed at chapter start (~tile 3,4), recruited when **Neimi TALKS to him**
> (`CHAR(…, NEIMI, COLM)` → `CUSA` = flip to blue). Vanilla has **no enemy thief** (our svirfneblin-skulk is
> an ADDED enemy thief). **Open creative fork for the repass:** who is our "Neimi" — the party member who
> Talks to recruit **Trex**?

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
- **Map-sprite tooling (#38 art loop):** `tools/map_sprite_tool.py` (validate/`recolour`/`remap_sms_palette`/
  preview) · `tools/map_sprite_editor.py <sheet> <pal> --donor X [--mu]` (in-browser PIXEL editor) ·
  **`tools/map_sprite_swapper.py --trex` (NEW, PR #144)** — in-browser GLOBAL cast-index palette-swap UI
  (idle/walk independent sets, live preview, Apply-to-files). Enemy reskin = raw FE-Repo sprite → bg-index-0
  → `map_sprites/<sprite>.png`+`_mu.png` → `campaign.yaml enemy_class_reskins`; PC = recolour onto cast palette.
- **FE-Repo vendoring:** `gh api repos/Klokinator/FE-Repo/git/trees/main?recursive=1` is TRUNCATED — navigate
  via `contents/<dir>` then `curl` the `download_url` (never submodule the 2.3GB repo). Map sprites live under
  `Map Sprites/Infantry - (Axe) Brigs, Pirates, Zerkers/`.
- **Playtest scenarios** `tools/playtest/run.sh <scenario>` (need a built ROM + `lua`):
  - logic/stability: `win|gameover|ch01win|clear|clear_ch01|smoke|smoke_ch01|fuzz`
  - **ch3 (#23):** `PT_HOST_CHAPTER=4 run.sh mapshot` (map+units) · **`ch03win`** (kill grell → assert
    `EVFLAG_DEFEAT_BOSS` → ending) · **`koboldview`** (pull off-camera enemies next to the party) — all on a
    `make CH03BOOT=1` ROM (macOS: apply the `build.sh` shebang-fix loop first).
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

#### The other 5 PCs + Trex (after wolfram) — donor mapping by class
pinky = Pegasus (lance flier — reuses the lance cadence) · marty + meesmickle = Shaman (dark caster) ·
rootis = Mage (anima caster) · sclorbo = Cleric (staff — may need a heal pose) · **trex = Thief but
reuses the **brigand Wildling** anim (Nicolas, 2026-07-08 — the ch03 kobold reskin, NOT myrmidon/thief);
ch03 recruit, added to #65**.
**meesmickle has a parked vendored Kitsune anim** at `battle_anims/_parked/`. Each: one `battle_anim:` block
+ 3 descaled frames, one feature-flow branch per unit (or small batch), `custom_unit` issue template.
- **Deferred polish (tracked):** braulo's white swing-arc weapon-trail → **#91**; goblin enemy class-level anim → **#90**.

### Content — Ch3 "The Termalaine Mine" (#23) — HOSTED + WIN + ENEMY SPRITES DONE; recruit/prep/chain/cutscenes/chests remain
Vanilla-FE8-Ch3 reskin as Termalaine's kobold-overrun tourmaline mine. Teaching goal = the **thief**
(Trex = our Colm). Decisions: `decisions.md` → Ch3 ADR (four deviations + **item 4 = Defeat Boss**) + the
ch03 YAML `design_notes` (2026-07-06 narrative reframe). **Live build checklist = #23 (the source of truth);
how-to for the host machinery = `docs/adding-a-chapter.md`.**
- **DONE:** map painted + hosted on slot 4; **DefeatBoss WIN + `ch03win`** (PR #143); **Trex bust** (PR #142);
  **ALL enemy map sprites in-engine** — Wildling grunts (PR #144) + **Lizardzerker blade skirmisher + steel
  brute** on appended classes 0x80/0x81 (PR #145, audited via `enemycheck`). archer + thief + grell VANILLA.
  **Recruit UNITS wired on `feat/23-trex-recruit-unit` (PR #146, OPEN — not merged):** reusable data-driven
  recruit model (`decisions.md` → **Recruit wiring** ADR) — a recruit = a classed cast member + a
  `recruit.chapter`; `cast_available_at(N)` = founding + recruits recruited before N. **Trex** = real unit
  (Rennac slot, Colm donor) placed **GREEN** on the ch03 map (Colm-style talk recruit; joins via `CUSA` →
  cast OBJ palette). **Baxby** = promoted from cutscene-face to a real unit (Forde slot, Franz donor); his
  hand-painted axe-beak sprite injects on the standard **32×32 cast pattern** (`base: Gargoyle` GEOMETRY
  token + synth MU, like braulo/wolfram/meesmickle). Verified in-engine: **`ch03` scenario** PASS
  (`blue[08]=0x10` Baxby + `green Trex 0x1C @ (10,6)`); 55 tests + verify_text green. **Trex talker LOCKED =
  ANY core party member.** **Audit:** Lupin/Sahnar/Basil (ch04/ch05) are in the SAME "authored-YAML, no unit"
  state — wire each per its slice.
  **✅ DONE — cutscene recruits now PERSIST (2026-07-08, on PR #146):** off-map recruit join-LOAD wired.
  `build_campaign.offmap_join_recruits(N)` returns the recruits newly available at N that join off-map
  (`recruit.via` not `story`/`talk`); `inject_ch02` LOADs them (Baxby) on a free vanilla-Ch3 UnitDef symbol
  (`088B476C`), blue, before the PREP CALL → he enters the saved party. **Empirically verified in-engine:**
  `tools/playtest/run.sh ch02baxby` PASS — Baxby at `blue[8]=0x10` in the prep roster AND deployable +
  fighting on the ch02 map (killed a raider in melee). Existing `ch02` scenario still PASS (deploy cap 5).
  3 new unit tests (58 total green). Talk recruits (Trex) still self-join via `CUSA`.
- **REMAINING (unchecked on #23, priority order):**
  2. **Trex talk-recruit event** — the `CHAR(flag, script, <every core-party candidate>, CHARACTER_RENNAC)` +
     `CUSA(RENNAC)` talk trigger + a Joshua-style hint line (talker = ANY core party, LOCKED). Part of the ch3
     dialogue pass (his recruit line). Then the cosmetic **horns/wings** pixel edit — `map_sprite_editor.py`.
  2. **Real PREP deploy** — author `deployment.deploy_slots` (9 tiles) + a PREP CALL; today it's the static
     fast-boot spawn (`CH03_SPAWN_POSITIONS` = `cast_available_at(3)` = 8 founding + Baxby), party WEAPONLESS
     (`items='0'`).
  3. **Chain ch02→ch03** — point ch02's ending `MNC2(0x4)` at ch03 (drop the ch02 dev-placeholder landing).
  4. **Cutscenes** — dialogue-pass on the REFRAMED beats first (feral faction / grell visible / Pinky→opening
     / RBG executes a feral one), then wire (#58 opaque-box). Mid-map beat fires on the BRUTE (`kobold-steel`)
     defeat. Replace the minimal DefeatBoss ending with the real ending cutscene.
  5. **Chests/doors** — per-chest **`17→29` TILECHANGE**; Trex opens, key-droppers back up.
  6. **Title-card image** + full load-test scenarios `ch03`/`smoke_ch03`/`clear_ch03` (the `ch03win`/
     `koboldview`/`enemycheck` scenarios seed these; a fair-play `clear_ch03` needs a `CA_BOSS` grell or a
     pid-targeted bot).
- **Cutscene BGs DECIDED (Nicolas): reference, don't import** — reuse `bg_TargosWinter`; mid-map beats on-map.
- Then chapters #24–#28 follow the same slice via `docs/adding-a-chapter.md`.

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
