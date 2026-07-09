# Handoff — Manchego Stars · live state

The **single** live-state doc (one trunk, feature-flow — no per-lane handoffs). **What shipped** →
`git log --oneline -20` + closed issues, not here. **Backlog** → GitHub issues. **Decisions** →
`docs/decisions.md`. **Operating instructions** → `CLAUDE.md`. Run `/handoff` to refresh this file in place.

> **Last session (2026-07-09 #2, desktop — Ch3 Trex TALK-RECRUIT wired + verified; PR #150 OPEN/green, awaits Nicolas's `gh pr merge`):**
> **#23 item 2 DONE — Trex talk-recruit (the vanilla Colm/Neimi pattern).** Trex stands GREEN; **ANY core party
> member** who **Talks** to him flips him blue via `CUSA`. Talker-agnostic + non-missable: one
> `CHAR(flag, script, <candidate>, CHARACTER_RENNAC)` per ch03 field candidate (`talk_recruiters` =
> `cast_available_at(3)`), all → ONE shared recruit script (FE8's ch14a-Rennac multi-recruiter idiom). Wiring
> repurposes dead ch4 symbols the host frees: **`EventScr_089F199C`** (was the Ch4 Turn-2 green script) + msg
> **`0x9A5`** + **`EVFLAG_TMP(9)`**. New `build_campaign` helpers (all TDD, 6 tests): `char_symbol`,
> `on_map_talk_recruits`, `talk_recruiters`, `talk_recruit_char_entries`, `talk_recruit_script`.
> **VERIFIED IN-ENGINE:** `PT_HOST_CHAPTER=4 run.sh ch03talk` **PASS** — park a candidate adjacent to green Trex →
> Talk (menu row 0) → Trex leaves the green array and lands in **`blue[09]=0x1C`**; the migrated dialogue (bounty
> framing) renders. **Gotcha:** the `blue()` harness helper scans only 8 slots (ch00 party) — ch03 deploys 9+, so
> a recruit lands at a higher index; scan the full array (`findUnit(gUnitArrayBlue, 20, …)`).
>
> **DECOUPLE (Nicolas):** Trex's entrance + recruit are split **OUT of** the RBG-execution cutscene. Colm's on-map
> appearance is a LIGHT green-NPC beat and ALL his substance rides the Talk — no second cutscene re-introduces him.
> So the ch03 **RBG-execution beat is now RBG's alone (+ Wolfram)**, and Trex's disavowal/boast/deal MOVED to the
> talk. **Why (the bug it fixes):** a freely-timed talk recruit + a fixed Brute-defeat cutscene fire in either
> order, so bolting Trex's intro onto the execution let a player who talked first recruit him *before* the cutscene
> "introduced" him. Talk line reframed to *"the wild ones — the ones your bounty names"* (accurate from turn 1,
> zero kills). ch03 YAML split into `trex_entrance` (light, Pinky telegraph + RBG "little dragon" — rides the
> Cutscenes item) + `talk_recruit` (the wired substance). ADR in `decisions.md` → Recruit wiring.
>
> **Trex iron-sword fix:** he had no YAML `inventory:`, so `difficulty.py` read "no weapon" and modeled him as a
> **staff healer (0 throughput)** — `make difficulty CH=ch03` showed `(staff)`. Added iron-sword to his YAML
> inventory (**difficulty-only**: the `inventory` field is read solely by difficulty.py; in-game deploy kit still
> comes from `CLASS_LOADOUT['CLASS_THIEF']`, unchanged). Now models as iron-sword w/ real throughput. **Confirmed
> Trex gets Colm's PERSONAL bases + growths via the donor** (BASE/GROWTH/STAT_DONOR=COLM — NOT base-thief): bases
> HP18/Pow4/Skl4/Spd10/Def3/Res1/Lck8, growths HP75/Pow40/Skl40/Spd65/Def25/Res20/Lck45. ch03 enemy parity
> unchanged (threat ×1.12, clear-load ×0.99 vs vanilla FE8 Ch3). **Open note:** arming Trex bumped him into the
> difficulty "best 9 fielded" for ch03 (over sclorbo) — the field-picker draws the full roster, so a recruit shows
> in its join chapter; the binding **enemy** parity is unaffected. Optional follow-up: filter the party metric to
> prep-availability (Trex as +1 bonus, not a deploy-slot swap).
>
> **Prior session (PRs #147 + #148, both SQUASH-MERGED):** #147 re-passed the ch03 opening + RBG-execution beats on
> the 2026-07-06 reframe (Pinky's shaft-scout folded into the opening; grell visible turn 1; **wings dropped**;
> Pinky = our "Neimi") — **LOCKED the cutscene text** the item-2/cutscene passes wire. #148 built the generic
> **`recordscene`** recorder (`PT_STATE=<ckpt> PT_TAG=<tag> PT_UNTIL=prep|title|chapter` — record ANY cutscene, no
> new Lua) — **the tool for the deferred ch03 cutscenes**. mGBA runnable here (`tools/emulator/mGBA-dev.app`;
> `/opt/homebrew/bin/lua`); its sandbox has no `os.getenv` (config via `PLAYTEST_*` wrapper globals) and a Lua
> `local function` used above its definition resolves to a nil global.

> **Prior session (2026-07-08 #3, MERGED PR #146 — recruit-persist join-LOAD):** cutscene recruits now PERSIST —
> `build_campaign.offmap_join_recruits(N)` LOADs off-map recruits (Baxby) on a free UnitDef (`088B476C`), blue,
> **before the PREP CALL** (`ch02baxby` scenario PASS). **Sprite-render gotcha:** a memory-poked force-deploy sets
> a unit's logical position but NOT its standing map sprite — only `RefreshUnitSprites` (phase transition / menu
> exit) does; cycle one phase before screenshotting. **Recruit model:** recruit = classed cast member +
> `recruit.chapter`; Trex = Colm-style TALK recruit (green + `CUSA`), recruiter = **ANY core party member**
> (telegraph Joshua-style); Baxby = real unit on Forde. Trex → #65 battle-anim reuses the brigand Wildling anim.

> **Prior sessions (all MERGED; detail in git log / closed issues):** ch03 **DefeatBoss WIN** + `ch03win`
> scenario (PR #143; **gotcha, decisions.md §Operational Gotchas:** the win fires from the FLAGGED grell quote
> pid `0xb7`/`EVFLAG_DEFEAT_BOSS`, NOT `CA_BOSS` → no boss HP gauge + the generic clear-bot can't target it).
> Trex bust (PR #142). ch03 map painted on `cave-interior` (`maps/ch03-the-termalaine-mine.mar`, 17×16) +
> hosted on slot 4 with the classed party + 10 vanilla-Ch3-parity foes (PRs #139/#140); objective **Defeat
> Boss** (grell@14,1, visible turn 1); thief slot = Svirfneblin Skulk. **2026-07-06 narrative reframe**
> (feral-splinter kobolds / Trex's clear-our-name motive / RBG executes a feral one / Pinky scout → opening)
> **now written into locked cutscene text** (this session, #147). Runbook **`docs/adding-a-chapter.md`**;
> config-driven `inject_chapter(N)` filed as #138. ch04 dialogue LOCKED (PRs #127/#128); `lore/lupin.md` voice
> bible; cutscene BGs reference-not-import (`bg_TargosWinter` for ch03).
> **VANILLA Ch3 "Bandits of Borgo" recruit wiring reference (decomp, for #23 item 2):** the thief is
> **Colm** — a **green (AI) unit** placed at chapter start (~tile 3,4), recruited when **Neimi TALKS to him**
> (`CHAR(…, NEIMI, COLM)` → `CUSA` = flip to blue). Vanilla has **no enemy thief** (our svirfneblin-skulk is
> an ADDED enemy thief). Our recruiter = ANY core party member; **Pinky delivers the talk-recruit hint line**
> ("He waved at me! Can we go say hello?" — LOCKED in the mid-map beat).

> **Branch hygiene (2026-07-09):** remotes are back to **just `main`** — no stragglers. This session dropped
> `demo/ch2-gifs` (its reusable `recordch02*` tooling salvaged into #148 first; the stale GIFs discarded) and
> closed stale PR #130 `claude/sonnet-5-exploration` (its one durable note salvaged). "Automatically delete head
> branches" is ON (Nicolas, 2026-07-02); the self-merge classifier blocks merging one's own PR without a human
> naming the merge, so a fresh PR waits on Nicolas's `gh pr merge`.
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

### Content — Ch3 "The Termalaine Mine" (#23) — HOSTED + WIN + ENEMY SPRITES + DIALOGUE + RECRUIT DONE; ⭐ prep-deploy + cutscene-wiring next; chain/chests/title/art remain
Vanilla-FE8-Ch3 reskin as Termalaine's kobold-overrun tourmaline mine. Teaching goal = the **thief**
(Trex = our Colm). Decisions: `decisions.md` → Ch3 ADR (four deviations + **item 4 = Defeat Boss**) + the
ch03 YAML `design_notes` (2026-07-06 narrative reframe). **Live build checklist = #23 (the source of truth);
how-to for the host machinery = `docs/adding-a-chapter.md`.**
- **DONE:** map painted + hosted on slot 4; **DefeatBoss WIN + `ch03win`** (PR #143); **Trex bust** (PR #142);
  **ALL enemy map sprites in-engine** — Wildling grunts (PR #144) + **Lizardzerker blade skirmisher + steel
  brute** on appended classes 0x80/0x81 (PR #145, audited via `enemycheck`). archer + thief + grell VANILLA.
  **Recruit UNITS wired (PR #146, MERGED):** reusable data-driven
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
- **DONE (this session, PR #150 OPEN/green):** ✅ **item 2 — Trex TALK-RECRUIT** (green→blue via `CUSA`; talker =
  any core party member; verified in-engine `ch03talk`) + the **decouple** (entrance/execution split; Trex's
  substance moved to the Talk) + the **Trex iron-sword** difficulty fix. See the session block up top for detail.
  Also DONE (PR #147): **Ch3 DIALOGUE LOCKED** — the 3 cutscene beats' text lives in the ch03 YAML `script:` blocks.
- **REMAINING (unchecked on #23) — ⭐ the next two are the requested handoff targets:**
  1. **⭐ NEXT-A — Real PREP deploy** (item 3). Author `deployment.deploy_slots` (9 tiles) in the ch03 YAML + wire a
     **PREP CALL** in `inject_ch03`'s beginning scene (today it's the static `CH03_SPAWN_POSITIONS` fast-boot spawn,
     party WEAPONLESS `items='0'`). **Reference impls in the SAME file:** `inject_ch01`/`inject_ch02` already emit a
     PREP flow (`_deploy_cap_entries` + the deploy-cap template + the PREP CALL); the ch02 off-map join-LOAD
     (`offmap_join_recruits` → Baxby before the PREP CALL) shows how a recruit rides the prep roster. **Cap is
     already recruit-correct:** `deploy_limit: 9` over `cast_available_at(3)` (9 units, Trex EXCLUDED — he joins
     mid-map on top, like vanilla Colm; included from ch04). Real equipping (`CLASS_LOADOUT`) lands with the prep
     flow. Verify with a new/updated scenario that the prep screen opens + Pick Units fields the roster (cf.
     `recordsupply`/`ch02` menu-driving).
  2. **⭐ NEXT-B — Cutscene wiring** (the "Cutscenes" item). Text is **LOCKED** in the ch03 YAML `events:` blocks
     (4 beats: `chapter_start` opening w/ Pinky's flyover scout; `midmap` RBG-execution-on-Brute-defeat — now
     RBG+Wolfram ONLY, Trex removed; `trex_entrance` LIGHT beat — Pinky telegraph + RBG "little dragon"; `chapter_end`
     ending). Wire each via the #58 opaque-box narration + the scene helpers (`_emit_scene_beats`/`_scenic_beat_calls`/
     `_script_to_message` — the ch01/ch02 injectors are the pattern). **Use `dialogue-pass` skill** for any text
     touch-ups and **`recordscene`** (PR #148: `PT_STATE=<ckpt> PT_TAG=<tag> PT_UNTIL=…`) to capture each beat as a
     GIF for Nicolas's motion review (deliver via `docs/demo/`). BGs: **reference `bg_TargosWinter`, don't import**
     (mid-map beats play on-map, no BG). The `talk_recruit` event is already wired (item 2) — don't re-wire it.
  3. **Chain ch02→ch03** — point ch02's ending `MNC2(0x4)` at ch03 (drop the ch02 dev-placeholder landing); replace
     the ch03 minimal DefeatBoss ending with the real ending cutscene once ch04 hosts (or park like ch02 until then).
  4. **Chests/doors** — per-chest **`17→29` TILECHANGE**; Trex opens, key-droppers back up.
  5. **Title-card image** + full load-test scenarios `ch03`/`smoke_ch03`/`clear_ch03` (the `ch03win`/`ch03talk`/
     `koboldview`/`enemycheck` scenarios seed these; a fair-play `clear_ch03` needs a `CA_BOSS` grell or a
     pid-targeted bot).
  - **Optional polish:** the recruit talk renders in the **map speech bubble** (no portrait box), canonical for
    on-map CHAR talks — switch to the full portrait box if Nicolas wants Trex's bust to show on recruit.
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
