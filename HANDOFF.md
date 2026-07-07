# Handoff — Manchego Stars · live state

The **single** live-state doc (one trunk, feature-flow — no per-lane handoffs). **What shipped** →
`git log --oneline -20` + closed issues, not here. **Backlog** → GitHub issues. **Decisions** →
`docs/decisions.md`. **Operating instructions** → `CLAUDE.md`. Run `/handoff` to refresh this file in place.

> **Last session (2026-07-07, desktop — ch03 WIN wired + first ch03 art in-engine):** three PRs.
> **① DefeatBoss WIN (PR #143, MERGED, #23 item 1):** the Termalaine Mine now ENDS when the grell dies.
> `inject_ch03` wires `DefeatBoss(EventScr_089F19F8)` into the Ch4 Misc + a **flagged** `gDefeatTalkList`
> quote for the grell (pid `0xb7`, `CHAPTER_L_4`, `EVFLAG_DEFEAT_BOSS`, faceless shriek from the YAML
> `death_quote`) + a minimal ending (victory → dev-placeholder → title, until ch04 hosts). Verified by the
> new **`ch03win`** harness scenario (teleport grell to lord, kill, assert `EVFLAG_DEFEAT_BOSS` → ending →
> title). **Gotcha (decisions.md §Operational Gotchas):** the win fires from the FLAGGED QUOTE, not
> `CA_BOSS` — the raw-pid grell wins with **no boss HP gauge** and the generic clear-bot can't target it.
> **② Trex bust (PR #142, MERGED, #19/#23):** ref-to-bust of the winged-kobold recruit (framing A, Nicolas's
> pick), `portraits/trex.png`, recipe in `trex.yaml art.render`.
> **③ ch03 MAP SPRITES + swap tool (PR #144, CI GREEN, OPEN — merge it):** the 6 **brigand kobold grunts**
> render in-engine as red reptiles — reskin `CLASS_BRIGAND → CLASS_BLST_KILLER_EMPTY` (the last free
> ballista-empty) with the FE-Repo `Brigand (U) Lizard Wildling {Tarantino500}` sprite; enemy faction
> palette colours it red + its eyes land on the team's leftover key-green so they glow. **archer + thief
> stay VANILLA** (class read; Nicolas), grell = vanilla Mogall. **Trex map sprite** = same base recoloured
> onto the CAST palette (red-brown body, tan belly, **gold eyes** via the donor eye `#e81018`→cast idx 12,
> matching his bust). New **`tools/map_sprite_swapper.py`** (in-browser global cast-index palette-swap UI,
> idle/walk independent) + **`koboldview`** harness scenario (pull off-camera enemies next to the party).
> **④ Battle-anim GAP (honest):** there is NO FEditor→decomp importer — `inject_battle_anims` only FAKES a
> 3-frame anim from static poses (the custom-PC path). So the kobolds keep the **vanilla brigand battle
> animation** in combat (map-sprite-only, exactly like the Fire Imp goblins); importing the community Lizard
> anims (Lenh/Seliost1) is a real converter to build (~#90). **⑤ "Add a slot" is feasible (Nicolas's ask):**
> `gClassData` uses designated initialisers, class id is a `u8` with `0x80–0xFF` free, no count cap — so new
> classes can be APPENDED (not just the 3 ballista-empties). The mercenary→Lizardzerker brute will use one.
> **PROCESS SLIP (Nicolas flagged):** most of this map-sprite session ran on `main` before I branched;
> fixed by `git checkout -b` (uncommitted work follows the checkout) → all on `feat/23-ch03-map-sprites`.
> **Branch at the FIRST edit of feature work, before touching files.**

> **Prior session (2026-07-06, desktop — ch03 goes PLAYABLE):** map painted on `cave-interior`
> (`maps/ch03-the-termalaine-mine.mar`, 17×16) + map-painter upgrades (eyedropper, `--vanilla=Ch3Map`,
> engine-accurate passability proving cave floor `0x2a` walkable) via PR #139; `inject_ch03` HOSTS the map
> on slot 4 with the classed party + 10 vanilla-Ch3-parity foes, `--ch03-boot`/`mapshot` load-tested, via
> PR #140. Objective **Defeat Boss** (kill grell@14,1); grell visible turn 1; thief slot = Svirfneblin
> Skulk. **2026-07-06 narrative reframe** (feral-splinter kobolds / Trex's clear-our-name motive / Pinky
> scout → opening) in the ch03 YAML `design_notes`, still **PENDING a dialogue-pass** on the #97 beats.
> Host-a-chapter runbook **`docs/adding-a-chapter.md`**; config-driven `inject_chapter(N)` filed as #138.
> ch04 dialogue was LOCKED earlier (PRs #127/#128); `lore/lupin.md` voice bible; cutscene BGs reference-not-
> import (`bg_TargosWinter` for ch03, vanilla `House1` for ch04).

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

#### The other 5 PCs (after wolfram) — donor mapping by class
pinky = Pegasus (lance flier — reuses the lance cadence) · marty + meesmickle = Shaman (dark caster) ·
rootis = Mage (anima caster) · sclorbo = Cleric (staff — may need a heal pose). **meesmickle has a parked
vendored Kitsune anim** at `battle_anims/_parked/`. Each: one `battle_anim:` block + 3 descaled frames, one
feature-flow branch per unit (or small batch), `custom_unit` issue template.
- **Deferred polish (tracked):** braulo's white swing-arc weapon-trail → **#91**; goblin enemy class-level anim → **#90**.

### Content — Ch3 "The Termalaine Mine" (#23) — HOSTED + WIN wired + first art in-engine; cutscenes/recruit/rest remain
Vanilla-FE8-Ch3 reskin as Termalaine's kobold-overrun tourmaline mine. Teaching goal = the **thief**
(Trex = our Colm). Decisions: `decisions.md` → Ch3 ADR (four deviations + **item 4 = Defeat Boss**) + the
ch03 YAML `design_notes` (2026-07-06 narrative reframe). **Live build checklist = #23 (the source of truth);
how-to for the host machinery = `docs/adding-a-chapter.md`.**
- **DONE:** map painted + hosted on slot 4 (2026-07-06); **DefeatBoss WIN wired + `ch03win` verified**
  (PR #143); **kobold-grunt map sprite renders in-engine** (Lizard Wildling enemy reskin, PR #144); **Trex
  bust** (PR #142) + **Trex map sprite** (cast palette, gold eyes, PR #144). archer + thief kept VANILLA.
- **FIRST: land PR #144** (CI green, OPEN — ch3 map sprites + swap tool) before continuing on the branch.
- **REMAINING (unchecked on #23, priority order):**
  1. **Enemy sprites, cont'd** — `mercenary` blade kobold → **Lizardzerker {Seliost1}** on a **newly ADDED
     class slot** (extend `gClassData` past 0x7F — feasible, see last-session ⑤; the 3 ballista-empties are
     used up: soldier/fighter=fire-imp, brigand=lizard-wildling). Then `map_sprite_swapper.py` isn't needed
     (enemy uses `remap_sms_palette` onto the base's SMS roles, not the cast palette). Battle anims stay
     vanilla (importer gap, ~#90). Svirfneblin Skulk / kobold-slinger stay vanilla (Nicolas).
  2. **Trex recruit wiring** — deploy Trex as a real unit (free char slot + recruit logic + STAT_DONOR),
     which is ALSO what makes his map sprite render in-engine (`inject_map_sprites` keys off his cast slot).
     Then the cosmetic **horns/wings** pixel edit (separates him from the grunts) — `map_sprite_editor.py`.
  3. **Real PREP deploy** — author `deployment.deploy_slots` (9 tiles) + a PREP CALL; today it's the static
     fast-boot spawn (`CH03_SPAWN_POSITIONS`), which also deploys the party WEAPONLESS (`items='0'`).
  4. **Chain ch02→ch03** — point ch02's ending `MNC2(0x4)` at ch03 (drop the ch02 dev-placeholder landing).
  5. **Cutscenes** — dialogue-pass on the REFRAMED beats first (feral faction / grell visible / Pinky→opening
     / RBG executes a feral one), then wire (#58 opaque-box). Mid-map beat fires on the BRUTE (`kobold-steel`)
     defeat. Replace the minimal DefeatBoss ending with the real ending cutscene.
  6. **Chests/doors** — per-chest **`17→29` TILECHANGE**; Trex opens, key-droppers back up.
  7. **Title-card image** + full load-test scenarios `ch03`/`smoke_ch03`/`clear_ch03` (the `ch03win`/
     `koboldview` scenarios seed these; a fair-play `clear_ch03` needs a `CA_BOSS` grell or a pid-targeted bot).
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
