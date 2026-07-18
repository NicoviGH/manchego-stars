# Handoff - Manchego Stars live state

`HANDOFF.md` is live state only. Settled decisions live in `docs/decisions.md`; operating rules
live in `CLAUDE.md`; issue scope and backlog live in GitHub. Before a context rollover, warn
Nicolas, refresh this file, and begin a fresh instance — don't rely on auto-compaction.

## Current state

- **Parity/difficulty engine is now three-dimensional** (`tools/difficulty.py`, all read from HEAD):
  1. **Enemy pressure** (existing) — threat/slot + clear-load/slot vs the `parity_reference` twin.
  2. **Item economy** (#170, merged #172; **drops added #176, merged #178**) — `vanilla_economy()`
     extracts the twin's chests / gifts (villages/houses + conditional clear rewards) / shops / enemy
     **drops** (a red unit flagged `.itemDrop` drops its LAST item, folded into `total_gold`), valued
     from `data_items.c`; printed as `ITEM-ECONOMY PARITY`. `chapter_economy()` reads ours from YAML.
  3. **Battlefield dynamics** (#171, merged #174; **area/zone reinforcements added #177, merged #178**)
     — convertibles (CHAR-macro targets, e.g. Ch5's Joshua) + reinforcement timing auto-detected:
     `TurnEventPlayer` AND raw `TURN(…,FACTION_BLUE)` waves, plus flag-gated / `AREA`-triggered
     zone-entry spawns (Ch4 now reads 16 line + 7 reinf). Printed as an ADDITIVE `BATTLEFIELD DYNAMICS`
     section (static verdict/gate untouched). Our YAML: `convertible:` / `arrives_turn:` on enemy_units.
  - `make difficulty CH=chNN` now shows all three. Everything reads via `vanilla_decomp_text`
    (`git show HEAD:`) — **immune to the working-tree injection** (our ch03 is injected into the Ch4
    host slot; hand-reading the tree there reports our chests as vanilla Ch4's — the bug that started
    this session).
- **ch04/ch05 design LOCKED** (#175, merged; ADR in `decisions.md` "ch04 and ch05 each map 1:1…").
  Retired the "split old Ch4" framing AND the brainstormed Ch11-map-borrow (Option B). Both are still
  `status: planned` seeds — targets set; map + roster build at each slice (M3). See "Next steps".
- **Spell-palette tint** finished: dedicated `gMSSpellTint` overlay global replaced the
  `gEfxSpellAnimExists` overload (#168, merged #169), after #167 registered the hook. Green Flux
  gated in-engine (`PT_CHAR=marty recordanim`).
- **ch03** (#23) is **complete** — the enemy battle-anim art (the last gap) landed via **#90**.
  (Earlier: corrected a stale #23 checklist — **Real PREP deploy** + the **"Defeat Saar" objective
  leak** are already wired in `inject_ch03`, see the #23 2026-07-16 comment.)
- **Enemy battle-anim import pipeline SHIPPED (#90, 2026-07-17):** reskinned enemy CLASSES now animate
  as real FE-native community anims in the close-up (not just the map sprite). `tools/feditor_to_banim.py`
  imports an FEditor `.txt` + frame PNGs → decomp banim; `build_campaign.inject_enemy_class_battle_anims`
  binds it per-class via `ClassData.pBattleAnimDef` (driven by a `battle_anim:` block on
  `enemy_class_reskins`). Wired: kobold-grunt (Wildling), kobold-blade/brute (Lizardzerker), both fire-imp
  goblins (Goblin Spearman, native palette). ADR in decisions.md "Imported enemy battle anims". Testing is
  unified on TESTCH: the sandbox deploys one hostile per reskin slot; `PT_CHAR=<name> recordenemy` baits it.
- **Basil's art kit is SHIPPED** (#179, merged 2026-07-16): portrait + SMS/MU map sprites +
  battle-anim frames, all adopted from Oddish sprite art (PMD SpriteCollab / gen3 FRLG — pipeline
  ADR in decisions.md "Adopting non-FE sprite sources"). His build **wiring** (slot, Natasha
  STAT_DONOR, injection, a `priest` staff/heal BANIM_DONORS row — NOT shaman) is a checklist on the
  ch05 slice **#25**; a live `battle_anim:` block in basil.yaml waits on that donor row.
- **Lupin + Sahnar art SHIPPED** (#181, merged 2026-07-17):
  - **Lupin** (ch04) — direwolf **map sprite** (stand + walk) from the Midday **Lycanroc** overworld
    sheet (princess-phoenix, CC-BY 3.0), recolored to the cast grey ramp to match his portrait, with
    **hand-drawn hipster glasses** tracked to the eye across every walk frame. `base: Gwyllgi` geometry.
    Battle anim NOT done — deferred, source = **PMD SpriteCollab Lycanroc #0745** (pointer on #24).
  - **Sahnar** (ch05) — hooded **spectral-skeleton** blademaster (the "mummy" was dropped: no elegant
    mummy art exists anywhere, only skeletal undead — skeleton reads cleaner + the trio matches).
    **Portrait** = Glaceo "Skeleton (Assassin)" bust (hood recolored to the map cloak slate); **map
    sprite** = Alexsplode "Specter" (cast-palette slate, spectral glow dropped). Battle anim decided
    (Alexsplode's matching Specter sword anim, **native palette — do not recolor**) but deferred (#25).
  - Both recruits' build **wiring** (slot, STAT_DONOR, injection, live `battle_anim:`) is ch04/ch05-slice
    work (#24/#25), same scoping as Basil. Pipeline learnings: decisions.md "Adopting sprites, part 2".

## This session (2026-07-18, Opus — per-caster charge flash SHIPPED, #183)

- **#183 shipped** (squash `5a0ed1e`, merged; ADR in decisions.md "Per-caster charge flash"). Each custom
  caster's sprite pulses its signature colour on the wind-up beat — **Rootis blue · Marty green ·
  Meesmickle purple** — validated in-engine (`recordanim`), all approved. One YAML line per caster
  (`charge_flash: {color}`); a new colour = one line in `CHARGE_FLASH_RGB`.
- **Reusable engine kernel (see ADR — copy for any per-caster actor-visual effect):** arm from an
  EXISTING banim command (`start-attack`, `case 0x07` in `banim-main.c`) so the donor-matched animation
  is untouched; a raised-cosine LUT ramps from 0 so the pulse blooms on the arm-raise; identify the
  attacker via `gpEkrBattleUnitLeft/Right` + `GetItemType`; pulse the actor OBJ palette
  `PAL_OBJ(0x7/0x9)` from a `PROC_REPEAT` proc, restore at the end. Timing = `_CHARGE_FLASH_FRAMES/_THROBS`.
- **Two build gotchas the ADR pins (cost a rebuild each):** a new hook-target file MUST be in
  `PATCHED_DECOMP_FILES` (else the injection guard skips re-injection and stale code persists); and **no
  `.bss` statics in banim TUs** (mutable state lives in the proc struct, not a `static` global).
- **A flash is a WASH toward a bright colour, not a hue-transform** — a caster already near the hue
  barely shifts. All 6 PCs with anims now also have a charge tell if configured (3 casters wired).

## Prior session (2026-07-17, Opus — ch04 roster grounded + tiered-difficulty ADR)

- **ch04 roster grounded (step 1 of the ch04 slice #24; PR #186 open, feat/24-ch04-roster-grounding).**
  The seed's 8 unmodeled enemies → a 23-unit force (16 line + 7 reinf) mirroring the vanilla Ch4 twin.
  Hybrid palette (decisions.md): `mauthedoog` wolves (parley pack, `convertible`) + vanilla
  `bonewalker-bow`/`mogall`/`entoumbed` for banshees/wisps/tank; weapons via `inventory.fe_base`,
  reinforcements via `arrives_turn`, one `item_drop`. `make difficulty CH=ch04` → PARITY (threat/slot
  8.1 x1.12, clear-load 2.9 x1.23; turn-1 clear-load ties vanilla 2.3 after the parley discount).
- **New ADR (decisions.md §Combat): difficulty is checked in fidelity tiers** — roster ballpark
  (`make difficulty`, aspatial) → author map+placement → **spatial check** → runtime play → lock; the
  roster↔map loop is **bidirectional**. The spatial check = deterministic facts fed to an LLM
  **analyst**, NOT an LLM playing the game (LLMs play FE badly; they read facts well). Validated by a
  Haiku analyst that reproduced the tool's verdict on vanilla Ch4, *found the Mogall crossfire cluster
  the aspatial tool can't see*, and flagged terrain as the #1 missing input. YAGNI: no
  reachability-metric extractor until its absence is felt.
- **ch04 `placement_directives`** written into the map notes (cluster wisps, tree-gate the crossfire,
  deep tank, later waves, near-woods parley pack) — waiting for the map step (step 2).
- **STILL OPEN (events layer, on #24):** (1) parley behavior — green-and-fight (current
  `convertible: true`, matches Nicolas's "turn the tide") vs green-and-leave; (2) teaching the player
  Marty can Talk to parley the wolves (onboarding beat). Both are map/events decisions, not roster.
- Also cleaned up 4 stale worktrees (squash-merged, remotes gone) at session start.

## Prior session (2026-07-17, Opus — Rootis frost-mage battle anim SHIPPED)

- **#184 shipped** (squash `74b8252`, merged; ADR in decisions.md "A caster clones from its OWN class;
  the spell tint is the flavour lever, not the donor"). Rootis's faked 3-pose caster anim (frost snowman)
  + icy-blue spell. Key decisions, reusable for the next caster:
  - **`clone_from` = the unit's OWN class, picked by weapon type.** New `mage` donor (`CLASS_MAGE`,
    ITYPE_ANIMA); the private `_u25` AnimConf repoints the ANIMA slot, so the anim binds to the tome the
    unit actually wields. Marty/Meesmickle's shaman (dark) donor would miss an Anima mage.
  - **Element = colour-only spell tint, NOT a spell-proc swap.** Kept the vanilla red Fire projectile and
    added `BANIM_SPELL_TINT_BLUE` + `BanimSpellTintBlue` (blue-dominant, green mid → cyan-white frost),
    scoped to his Anima tomes via `spell_palette_tint` — same seam as Marty's green Flux. Declined the
    real Fimbulvetr blizzard (oversized for a basic tome). **Reviewed the regular red spell in-engine
    BEFORE tinting** — never bundle a colour change with the first anim review.
  - **Descale:** threaded `--reserve` through the ADAPTIVE palette path (was locked-layout only) so
    Rootis's orange carrot nose survives quantization in his near-monochrome blue/white frame. Row-1
    look (thin outline, no sharpen, `--body 40`) chosen via an A/B ladder. Recipe in `rootis.yaml`.
  - Verified in-engine (`recordanim`, class 0x25, `_u25[23]`); 99 tests green, `check.py` clean.
- **New backlog: #183** — per-caster charge-flash effect (Marty green · Rootis blue · Meesmickle purple),
  a visible charge tell on the magic wind-up beat, reusing this per-caster colour scoping. Seed only —
  brainstorm when picked up. **6 of 8 PCs now have battle anims** (braulo, marty, meesmickle, prof-rbg,
  wolfram, rootis); sclorbo + pinky remain.

## Prior session (2026-07-17, Fable→Opus — Lupin + Sahnar recruit art)

- **#181 shipped** (squash `9792bb6`, merged): Lupin direwolf map sprite (Lycanroc + hand-drawn glasses)
  + Sahnar spectral-skeleton portrait + map sprite. Detail above + on #24/#25. Reusable learnings in
  decisions.md "Adopting sprites, part 2": DeviantArt oEmbed for signed image URLs; hand-drawn details
  anchored to a detected eye pixel so they track the walk-bob; the community has NO mummy (only skeletal
  undead) so spectral-skeleton is the cohesive route; palette-lock the portrait robe to the map sprite's
  *dominant* cloak shade; keep adopted battle anims in their native palette. Both deferred battle anims
  now ride the #90 import pipeline.

## Prior session (2026-07-17, Opus — #90 enemy battle anims SHIPPED, ch03 complete)

- **#90 shipped** (squash `35666c3`, pushed; ADR "Imported enemy battle anims"). New
  `tools/feditor_to_banim.py` imports FEditor community anims → decomp banim; class-bound via
  `pBattleAnimDef`. Wired all 5 reskins (grunt/blade/brute + 2 goblins). 22 TDD tests. Also: **landed
  the stranded Braulo refresh** (`feat/braulo-battle-art-refresh` was never merged → the build showed
  the old Braulo; now on main `ee48b63`), re-slotted kobold-grunt to its own appended class, unified
  battle-anim testing on TESTCH (`recordenemy`). The stranded branch + its worktree are cleaned up.

## Prior session (2026-07-16, Fable — Basil/Oddish art kit, parallel art branch)

- Full detail on PR **#179** + the #25 checklist comment. Reusable bits: PMD SpriteCollab is the
  side-view sprite goldmine (8-direction sheets; W row faces left = FE8 player side); ffmpeg ships
  hqx/xbr pixel-art rescalers; `map_sprite_swapper.py` grew `--idle-frame-h 32` for 16×32 idle
  sheets. Full pipeline + gotchas: decisions.md §Art & Audio ADR.

## Prior session (2026-07-16, Opus — closed engine parity gaps #176 + #177)

- **Closed both parity-engine v1 gaps** (PR **#178**, squash-merged; ADR in decisions.md
  "Parity-engine v1 gaps closed"). TDD; 174/0 tests, `make check` clean, parity gate green.
  - **#176 (economy drops):** `vanilla_unit_defs` captures the `.itemDrop` bit; a flagged red unit
    drops its LAST item (`US_DROP_ITEM`, the final inventory slot per `statscreen.c:726`). New
    `vanilla_drops()` values each via `item_gold_value`; `vanilla_economy` folds a `drops` channel into
    `total_gold` + the print. Ch4/Ch5 twins carry NONE (lock unchanged); Ch2 Vulnerary / Ch3 keys /
    Ch13 crests now counted.
  - **#177 (area/zone reinforcements):** `_vanilla_reinforcement_turns` matched only the
    `TurnEventPlayer` macro. It now also reads the raw `TURN(…,FACTION_BLUE)` expansion, and treats any
    temp-flag-gated turn event (or `AREA`/`AFEV` script that LOADs a force) as a zone-entry reinforcement
    (`_ZONE_ENTRY_TURN`, > turn 1). Ch4 "Ancient Horrors" now reads 16 line + 7 reinforcements
    (3 Bonewalkers turn-2 + 4 Revenants zone-entry); Ch5's 2/6/8 detection unchanged.
- **Fixed a pre-existing CI blocker** (same PR): `HANDOFF.md` references `tools/key_magenta.py`, an
  intentionally-untracked local tool — `check.py`'s tool-ref drift guard reddened on EVERY PR in CI
  (committed files only) while passing locally (file present). Gitignored it, matching check.py's
  documented "gitignored target = declared artifact" exception (like `symbols.lua`). Was broken on
  `main`, unrelated to #176/#177.
- **Scoped #90 (enemy battle-anim import) via brainstorm** — design of record was the #90 2026-07-16
  comment; **implemented + shipped 2026-07-17** (see this-session note above).

## NEXT SESSION — start here: ch04 MAP (step 2), then ch05 slice (M3, the main line)

**ch04 roster is now grounded (step 1 done, PR #186 — merge it first).** Per the new tiered-difficulty
flow (decisions.md §Combat), the next step is **ch04's MAP (step 2): the Tiled retile of vanilla Ch4**,
honouring the `placement_directives` now in `ch04-the-white-moose.yaml` (cluster the will-o'-wisps into
one crossfire pocket, tree-gate the approach, deep tank, later reinforcement waves, near-woods parley
pack). Then **re-run the spatial check** — feed the placed map's positions/AI/terrain to an LLM analyst
(the ch04 experiment brief is the template: `scratchpad/ch4_facts_brief.md`), adjust placement *or*
roster (the loop is bidirectional), and only then build+play for the real difficulty read. Two ch04
events-layer decisions are still open (see this-session note): parley behavior + teaching the parley.

ch05 is the same shape but not started (`status: planned`, roster still 8-enemy seed / unmodeled —
same grounding pass ch04 just had). Basil's build **wiring** is a checklist on the ch05 slice **#25**
(needs a `priest` staff/heal BANIM_DONORS row — NOT shaman — before his `battle_anim:` block goes live).

## Why we dropped the Ch11 map-borrow (so it isn't re-litigated)

Everything Option B wanted from the Ch11 pair — **fog, dark theme, the eruption** — is a config flag,
custom tileset, or injectable event; **none live in a map's layout**. Borrowing Ch11's layout only cost
the twins' terrain (esp. Ch5's spread two-front race, which Phantom Ship's corridor kills). So each
chapter maps 1:1 to its numeric FE8 twin (map + parity) and the theme is layered on top.

## Next steps (priority order)

1. **Build the ch04 / ch05 slices** (M3, the main line). Per-chapter vertical slice on #24 / #25,
   run through the tiered-difficulty flow (decisions.md §Combat): roster ballpark → map+placement →
   spatial check → play → lock.
   - **ch04: roster GROUNDED (PR #186).** Next = the **map** (step 2) per its `placement_directives`,
     then the spatial check + build/play. Two open events decisions (parley behavior + teaching it).
   - **ch05: not started.** Same grounding pass ch04 just had — tag enemy_units with `fe_base`
     weapons, `convertible:` (Sahnar), `arrives_turn:` (eruption waves), `item_drop:` where a twin
     drops one (right now the seed shows "0 enemies" = unmodeled). Also wire the Lupin/Sahnar/Basil
     `STAT_DONOR`s so `make difficulty` fields the true ch05 party (currently invisible to it — a
     known lever, not headroom).
2. **#138** config-driven `inject_chapter(descriptor)` (incremental; YAML `host:` block — approved
   direction, paused for the ch04/ch05 design).
3. Then **#29** world map.

## Working tree - do not lose or revert

- `fireemblem8u` is dirty from injected/generated build artifacts. **Never commit its submodule pointer.**
- Untracked local/session files (`.agents/`, `AGENTS.md`, `skills-lock.json`) are intentionally not
  versioned; leave them alone unless Nicolas asks. `tools/key_magenta.py` is now **gitignored** (#178)
  so it no longer trips the CI drift guard.
- Everything is merged to `main` (pushed); no dangling local branches or worktrees from this session.

## Quick commands

```sh
# Parity/difficulty read (enemy pressure + economy #170 + dynamics #171), all from HEAD
make difficulty CH=ch05            # or ch04, etc.

# Battle-animation capture (requires a TESTCH ROM)
PT_CHAR=marty tools/playtest/run.sh recordanim

# Required before claiming a change is finished
python3 -m unittest tools.test_build_campaign tools.test_difficulty
make check
git diff --check
```
