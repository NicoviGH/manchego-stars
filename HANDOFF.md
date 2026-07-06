# Handoff — Manchego Stars · live state

The **single** live-state doc (one trunk, feature-flow — no per-lane handoffs). **What shipped** →
`git log --oneline -20` + closed issues, not here. **Backlog** → GitHub issues. **Decisions** →
`docs/decisions.md`. **Operating instructions** → `CLAUDE.md`. Run `/handoff` to refresh this file in place.

> **Last session (2026-07-05→06, web→desktop — Opus reviewing Sonnet, then a live map collab):**
> Opened by **reviewing Sonnet's #131/#132** against the decomp — all four NPC class-stat blocks
> verbatim-correct vs `data_classes.c`; the 0x87 msg-id "unreachable" trace sound (clean, no fixes).
> Then a long **ch03 map/tileset** session with Nicolas:
> **① Map reskin tooling FIXED** (`7610564`): `gen_map_editor`'s winter-reskin flow hard-coded vanilla
> `TileConfiguration1` and applied `reskin-learned.json` to any `--tileset`; ch03 breaks both (Ch3Map
> rides `TileConfiguration2`; cave-interior ≠ snowy-bern). Now resolves each layout's own tile config
> from the decomp asset table + `chapter_settings.json`, and gates the learned map on a `"tileset"` stamp.
> **② Tilesets vendored on-hand** (`c0ec1f0`): FE-Repo **FF5 Caves** (WAve) + **Lava Cave** (HyperGammaSpaces)
> at `maps/tilesets/{ff5-caves,lava-cave}/` for future chapters (inert until a chapter registers them).
> **③ FF5 navy chest cherry-picked into `cave-interior`** — closed **metatile 17** / open **29**, palette
> bank 5, native CHEST terrain (0x21/0x20), pinned Test Map render unchanged. Its art is tagged OPPOSITE
> to terrain, so the graphics were swapped in `763904d` (17 = green closed, 29 = grey open).
> **④ ch03 Borgo→mine retile — WIP layout committed** (`17fe5fa`): `ch03-the-termalaine-mine.mar` + `.json`
> (17×16, cave-interior) + the **`ch03-retile.py` generator** — terrain-based reskin (cave-interior indices
> are unrelated to vanilla's, so map by terrain role), wall-rim **autotile learned from Cynon's test map**,
> **throne-dais overlay** on the O1 seize (terrain-matched to vanilla), chest 17. Furniture LOCKED: chest,
> door (812), throne (784+frame), barrel (822), pillar (739), walls, floor base.
> **⑤ Floor-detail:** built a **patch-stamp tool** that copies Cynon's hand-painted floor CLUSTERS (moss,
> crystal veins, formations) from his test map onto our galleries — Nicolas's ruling: use his art, not
> statistical scatter. **➡ NOW: Nicolas is hand-painting the ch03 floor + the still-open visuals
> (stairs / road cart-tracks / the E1 well) in his pixel editor** (`gen_map_editor.py --tileset=cave-interior
> <out.html> <dl.json> maps/ch03-the-termalaine-mine.mar` to resume on the current layout).
> **Nicolas-at-home queue:** paint ch03 map · generate **Wolfram's 3 poses** (unblocks #65).
> **Sonnet follow-ups** set up as GitHub issues (ch03 chest tile-changes + terrain parity after the
> paint; decisions.md ADR ready now).
>
> **Update (2026-07-06, desktop):** the stranded mobile-session work was landed to main via **PR #136**
> (ch03 WIP layout + `ch03-retile.py` + FF5/Lava tilesets + chest fix + reskin-flow fix) — the layout
> now lives on `main`, resume painting there. The stale-branch backlog was **deleted** (see below).

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

#### Map (#40) — layout RULED 2026-07-04; next beat = the Borgo→mine retile
- **Tileset DECIDED = Cynon's Mineshaft (Gray palette)** — a purpose-built cave/mine tileset (rock walls,
  cart tracks, timber supports, crystal/ore seams, water) vendored from **FE-Repo** (`Klokinator/FE-Repo`
  → `Tilesets/Caves/Cynon's Mineshaft - Tileset`; CC, Cynon endorses cross-engine use), landed in-repo as
  **`cave-interior`** (PR #111; Cynon credited in `CREDITS.md`). **NO re-palette** — native grey already
  reads as a frozen Icewind mine (Nicolas's call).
- **Layout RULED (2026-07-04, Nicolas — closes the #23 pending decision): REPAINT VANILLA BORGO.** The
  2026-06-29 proposed custom Gem-Mine blockout is **rejected** — don't fabricate map geometry when a
  vanilla-proven Seize layout exists (decisions.md ADR; consistent with "ALL mechanical data is vanilla").
  The ch03 YAML's `base_layout: Ch3Map` was never changed, so this restores the recorded design. Enemy/
  chest tiles stay the vanilla Ch3 coordinates — **the repositioning pass is no longer needed.** The book's
  Gem Mine map (`docs/demo/ch03-gem-mine-reference.png`) stays flavor reference only.
- **Retile DONE → WIP `.mar` committed (2026-07-05/06, `17fe5fa`).** Terrain-based retile of vanilla
  Ch3Map onto `cave-interior`: `maps/ch03-the-termalaine-mine.{mar,json}` + the `ch03-retile.py`
  generator (reads Ch3Map + TileConfiguration2 from the decomp submodule; re-run after edits). **Cave
  indices are unrelated to vanilla's, so the map is built by TERRAIN role, not index** — wall-rim
  **autotile learned from Cynon's Test Map** (`solid-neighbour-dir → rim tile`), **throne-dais overlay**
  (the pool structure, 784 seat on O1, terrain-matched to vanilla), FF5 navy **chest = metatile 17**
  (closed) / 29 (open). Furniture LOCKED; **floor + stairs/road/E1-well = Nicolas hand-painting now** in
  the pixel editor (seed the editor on the committed `.mar`, see the Last-session block).
- **Floor "random" texture (Nicolas's ask):** don't fake it statistically — **patch-stamp Cynon's actual
  hand-painted floor clusters** from his Test Map onto our galleries (the tool aligns our floor over his
  best-fit region and copies his tiles cell-for-cell; moss/crystal/formation clusters land intact). Built
  + previewed this session; Nicolas is painting directly, but it can seed his canvas.
- **Remaining after the paint (Sonnet-suitable):** (a) author the per-chest **`17→29` TILECHANGE** in the
  ch03 map-changes so chests open (FE8 `EventScr_OpenChest` fires a per-map tile-change; vanilla Ch3 has
  one per chest — reskin them); (b) **floor terrain parity** — the cave floor variants carry terrain
  `0x2a` (walkable) vs vanilla `FLOOR 0x17`; decide keep-vs-patch for exact parity; (c) then the chapter
  wiring below.
- ~~**Retile plan / importer notes**~~ (converter + editor support LANDED PR #111; retile LANDED `17fe5fa`).
- **Importer is a THIN converter (good #40 news).** Format decoded + validated: `mapchip_config` = **9216 B =
  exactly the decomp config** (8192 TSA + 1024 terrain); object PNG = **256×256 mode-P, 4-bit local indices**
  (pixels 0–15) + a 256-color (16-bank) palette → straight to `ObjectType.4bpp` + `MapPalette.gbapal`. A
  throwaway renderer assembled Cynon's own `Test Map.tmx` correctly →
  `map-review/ch03-tileset-candidates/mineshaft-testmap-gray.png` (= `docs/demo/ch03-mineshaft-tileset-demo.png`),
  proving tiles assemble. So #40 task 2 = a small converter, not a toolchain.
- **Build order (layout ruling applied):** ~~(1) converter~~ ~~(2) editor support~~ — **both LANDED
  2026-07-02 (PR #111):** `map_tileset_tool.py import/render-tmx`, tileset **`cave-interior`** vendored
  under `campaigns/.../maps/tilesets/` (Cynon credited in `CREDITS.md`), `gen_map_editor --tileset
  cave-interior --blank WxH [--ref img]` seeds a blank canvas, layouts carry their tileset in `.json`.
  Remaining: (3) the **Borgo→mine retile** (see Retile plan above) → `import_map_layout` → `.mar` →
  in-engine load-test. **Enemy/chest positions stay the vanilla Ch3 coordinates** (Borgo geometry kept,
  so no repositioning pass; parity unchanged — same 10-unit roster on the cited vanilla tiles).
- **Then (post-map, unchanged):** host on next vanilla slot (`MNC2`; model `inject_ch01`/`inject_ch02`) →
  units/objective/cutscene wiring (`inject_ch03` consumes the `script:` blocks; Brute-defeat trigger,
  Pinky-scout grell spawn + map-change, Trex recruit; new generic mugs `boy-crier`/`kobold-brute`/Maxol) +
  **motion-review the 4 beats** → art (Grell/Trex/kobold/giant-rat; **grell ref = book p.96**) → title card →
  load-test (`ch03`/`smoke_ch03`/`clear_ch03`, mirror ch02). Parity already verified `make difficulty CH=ch03`.
- Then chapters #24–#28 (Ch4–Ch8) follow the same slice. **Ch3/ch04 cutscene BGs DECIDED 2026-07-04
  (Nicolas): reference, don't import** — ch03 opening+ending REUSE the ch02 `bg_TargosWinter` slot
  (Termalaine street; no 2nd slot, so the `BG_RANDOM` relocation stays unneeded); ch03 mid-map beats play
  ON-MAP; ch04's cottage = VANILLA `House1` by BG id (in-ROM, free). The winter-BG library remains the
  well for genuinely-new needs (e.g. ch05 tomb exterior — Zeldacrafter's "Snowy ruins" in FE-Repo is a
  strong candidate).

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
