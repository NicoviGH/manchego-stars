# Handoff — Manchego Stars · live state

The **single** live-state doc (one trunk, feature-flow — no per-lane handoffs). **What shipped** →
`git log --oneline -20` + closed issues, not here. **Backlog** → GitHub issues. **Decisions** →
`docs/decisions.md`. **Operating instructions** → `CLAUDE.md`. Run `/handoff` to refresh this file in place.

> **Last session (2026-07-05, web — first Sonnet 5 session):** merged the wrap PR #129 (BG decisions +
> ch3 layout ruling + HANDOFF refresh — hit a real merge conflict in ch04's YAML that #128 had already
> half-landed; reconciled by hand, drift stayed clean). Then took the **ch03 Borgo→mine retile** partway:
> `git submodule update --init` pulled the `fireemblem8u` decomp clean (no blobless-clone workaround
> needed this time — plain init worked); reverse-engineered the decomp's vanilla Ch3 tileset (raw 4-bit
> grayscale PNG + JASC-PAL → the decomp's own `.4bpp`/`.gbapal`/`.bin` format) to read `Ch3Map`'s real
> layout + terrain bytes against `include/constants/terrains.h`'s actual enum (not guesswork). Built a
> **terrain-preserving retile onto `cave-interior`** (every cell keeps its vanilla terrain byte except
> the 12 PLAINS cells — cave-interior has no usable PLAINS graphic, borrows ROAD's look, flagged +
> Nicolas-approved) in two passes: v1 matched terrain codes correctly but patchworked unrelated tile
> families; v2 rebuilt almost the whole map from one confirmed-coherent block in the atlas (idx ~768–895:
> matching wall/floor/door/throne/barrel/damaged-wall, all one visual set) — 0 unexpected terrain
> mismatches either pass. **Validated against real vanilla ground truth:** found a genuine chapter-3
> screenshot at `fe8.triangleattack.com` (native 272×256px, no upscaling — see the new HANDOFF resource
> note below) confirming the reconstruction's structure (walls/chests/barrels/stairs/door/pond/throne
> position) was accurate; the one gap (a navy placeholder where vanilla shows an animated glowing icon)
> is a known static-tile-dump limitation, not a bug. **Parked here, deliberately:** finishing #40 needs
> Nicolas's eyes on the actual tile choices + a local mGBA load-test (no ROM/mGBA in this container, by
> design — the base ROM is local-only, never fetched/committed). Preview PNGs are pushed to
> `review/ch03-borgo-retile-preview` (not merged) — `docs/demo/ch03-retile-preview-v2.png` +
> `ch03-retile-three-way.png` (vanilla / patchwork-v1 / coherent-v2). **Next up:** Nicolas reviews the v2
> tiles locally; if approved, write the actual `.mar`/`.json` (via `map_tileset_tool.compile_layout`,
> already have the exact grid in `retile_map_v2.json`-equivalent form) and wire `ch03-*.yaml`'s `map:`
> block, then the in-engine load-test. **NEW capability carried forward:** the web container reads
> public GitHub repos fine now, including plain `git submodule update --init` when the submodule URL is
> public HTTPS (no blobless-clone dance needed unless that plain path fails).
>
> **Second half of the same session — a model-fit sweep (Sonnet-appropriate issues, no mGBA/art needed),
> in effort order, each its own PR:** **#17 done** (PR #131) — all 5 NPC/recruit YAMLs (Baxby, Trex,
> Sahnar, Lupin, Basil) already existed as stubs; filled the 4 missing `fe_stats`/`growth_rates` blocks
> with vanilla class data verbatim from `data_classes.c`, and documented WHY that's not a stat-twin bug
> (Lupin/Baxby, Basil/Sclorbo share a class+design-record but diverge in-ROM once `STAT_DONOR` wires
> their distinct personal donors — the actual differentiation mechanism, confirmed by reading
> `build_campaign.py`, not something in the YAML). **#53 turned out ALREADY DONE** (byproduct of
> #123/PR #124, never closed) — verified live (`fe_combat.W` has all the monster/extended weapons,
> `PARITY_REFERENCE_UDEFS` has Ch4/Ch6/Ch13, zero unmodeled-weapon drops) and closed with the receipts.
> **#63's issue text was stale** — M1 AND M2 are already done (dated ADRs, `test_llm_player.py` 55 green,
> `harness.lua`'s `llmDrive` scenario exists); updated the issue's checklist + added a note so nobody
> re-does that work. **#125 resolved as unreachable, no mGBA needed** (PR #132) — traced
> `CheckTradeTutorial()`'s gate to its one setter in the whole decomp (an event inside vanilla's REAL Ch1
> slot, a separate ROM asset from `PrologueEvents`, the only slot our chapter progression ever loads) —
> static proof, no emulator repro required. **Lesson recorded in decisions.md:** a live-looking msg-id
> reference can still be dead if its own trigger flag can never be set in our build's chapter-load graph.
>
> **Next up, by model fit:** (1) **Nicolas** — review the ch03 retile v2 tiles + local mGBA load-test
> (blocked on you, see above). (2) **Opus** (cross-cutting/design-sensitive lane per CLAUDE.md's Model
> Selection Guide) — **#63 M4** (soak report + `difficulty.py` hook): the only code-shaped work left on
> that epic that doesn't need mGBA (M3/M5 need a local build + live API key regardless of model); it's
> schema-design work (report shape + aggregation), which is why it's flagged Opus rather than Sonnet —
> read the freshly-updated #63 issue body first, the milestone checklist there is now accurate. Still
> open from before: Wolfram poses (art-blocked on Nicolas) · local-mGBA `clear_ch01` (#60) · desktop
> stale-branch deletion (below).

> **🛠 Desktop fix needed — branch cleanup + env policy (2026-06-29; re-probed 2026-07-02):** An audit
> found **13 stale remote branches** the squash-merge convention should have deleted. 2026-07-02 web
> re-probe: the env can now **push to branches and squash-merge PRs via the GitHub MCP** (PR #101 was
> conflict-resolved and merged from the web) — but **ref-deletes are still blocked** (`git push
> --delete` hangs at the proxy; no repo-settings API either). **To do from desktop:**
>
> 1. ~~Flip the GitHub repo setting "Automatically delete head branches"~~ — **DONE (Nicolas,
>    2026-07-02, from mobile).** Verified working: `feat/104-inject-chapter-extract` auto-deleted
>    when PR #105 squash-merged. The backlog can no longer re-accumulate; only the one-time
>    deletion of the pre-existing stale branches (step 2) remains.
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
- **Retile DONE through the preview stage (2026-07-05), PARKED awaiting Nicolas's local review.**
  Terrain-preserving retile onto `cave-interior` built and iterated to v2 (one coherent tile-family
  instead of v1's patchwork; see Last-session block for the full method). Preview PNGs live on
  `review/ch03-borgo-retile-preview` (not merged) — `docs/demo/ch03-retile-preview-v2.png` is the
  candidate; `ch03-retile-three-way.png` shows vanilla vs. v1 vs. v2. **Blocked on:** Nicolas eyeballing
  the actual tile picks + a local mGBA load-test (this container has no base ROM/mGBA, by design). If
  approved as-is: `map_tileset_tool.compile_layout` turns the retiled grid into the `.mar`/`.json`, then
  wire `ch03-the-termalaine-mine.yaml`'s `map:` block (its `size: "15×10ish"` comment is stale — the real
  vanilla Ch3 layout is 17×16, confirmed this session; fix that comment in the same commit). If tile
  picks need changes: the retile script + curated per-terrain-code tile pools are reproducible from this
  session's method (vanilla tileset reconstruction → terrain-byte read → hand-picked cave-interior
  replacements from one coherent atlas region) — re-run with different picks, no need to redo the
  reverse-engineering.
- **NEW resource: `fe8.triangleattack.com` hosts a real, native-resolution (272×256px, 1:1 = 17×16
  metatiles, no upscaling) screenshot per vanilla chapter at a predictable path —
  `/assets/images%2Fchapters%2F<chapter_slug>.jpg` (e.g. `the_bandits_of_borgo` → `chapter3.jpg`; find the
  slug/asset name via the chapter's page at `fe8.triangleattack.com/chapters/<slug>`). Fetchable directly
  with `curl` (a browser UA header avoids a block); this is real ground truth for validating a
  reconstructed/retiled vanilla map — used 2026-07-05 to confirm the ch03 Borgo retile's terrain-code
  reconstruction was structurally accurate (walls, chests, barrels, stairs, door, water pond, throne-alcove
  position all matched). Fandom's own wiki (`fireemblem.fandom.com`) 402's programmatic fetches; go via
  triangleattack or a search engine's redirect instead.
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
  Remaining: (3) the **Borgo→mine retile** — preview done, parked on Nicolas's review (see bullet above)
  → `.mar`/`.json` → wiring → in-engine load-test. **Enemy/chest positions stay the vanilla Ch3
  coordinates** (Borgo geometry kept, so no repositioning pass; parity unchanged — same 10-unit roster on
  the cited vanilla tiles).
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
