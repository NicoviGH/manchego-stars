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

## This session (2026-07-16, Fable — Basil/Oddish art kit, parallel art branch)

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
- **Scoped #90 (enemy battle-anim import) via brainstorm** — Nicolas chose to clear ch3 before ch4,
  and ch3's only remaining work is the kobold combat anims. Design of record is captured in the
  **#90 2026-07-16 comment** (retitled: now the shared pipeline for ch1 imps + ch3 kobolds). No code
  written — implementation is the next session's job (see Next steps #1).

## NEXT SESSION — start here: #90 enemy battle-anim import (clears ch3)

Full grounded design is in the **#90 2026-07-16 comment** (read it first — it has the technical
findings so you don't re-derive). Summary: build a new importer (`feditor_to_banim.py`, under tools/) — parse a vendored FE-Repo
FEditor `.txt` + frame PNGs → decomp banim assets, reusing `ref_to_battleframe`'s emitters; command→
`banim_code_*` macro table — the vocabulary already exists in `include/banim_code.inc`) + a class-level
`AnimConf` binding in `build_campaign` driven by a new `battle_anim:` on `enemy_class_reskins`
(`ClassData.pBattleAnimDef`). **Decision = full FEditor import (not the faked-3-pose shortcut).**
**FIRST STEP: vendor the real Lenh "Lizard Brigand Wildling" anim from Klokinator/FE-Repo and inspect
its actual packaging BEFORE building the parser.** Prove on kobold-grunt Wildling → in-engine ch03
capture (`CH03BOOT=1 PT_HOST_CHAPTER=4`) → show Nicolas → then Lizardzerker → then ch1 fire imp.
Svirfneblin stays vanilla; slinger = map-sprite only. TDD; `feat/90-…` branch; ADR (no spec doc).

## Why we dropped the Ch11 map-borrow (so it isn't re-litigated)

Everything Option B wanted from the Ch11 pair — **fog, dark theme, the eruption** — is a config flag,
custom tileset, or injectable event; **none live in a map's layout**. Borrowing Ch11's layout only cost
the twins' terrain (esp. Ch5's spread two-front race, which Phantom Ship's corridor kills). So each
chapter maps 1:1 to its numeric FE8 twin (map + parity) and the theme is layered on top.

## Next steps (priority order)

1. **#90 enemy battle-anim import — clears ch3 (Nicolas: finish ch3 before ch4).** See the
   "NEXT SESSION — start here" block above + the #90 2026-07-16 design comment. Prove on the
   kobold-grunt Wildling, then Lizardzerker, then the ch1 fire imp.
2. **Build the ch04 / ch05 slices** (M3, the main line). Per-chapter vertical slice on #24 / #25.
   Author the map (Tiled retile of vanilla Ch4 / Ch5 per the map-authoring pipeline) + roster + events,
   tuned against the now-machine-checkable targets via `make difficulty` (the engine bars are complete
   now — enemy pressure + economy incl. drops #176 + dynamics incl. area/zone reinf #177). When authoring
   the roster, **tag enemy_units with `fe_base` weapons, `convertible:` (Sahnar), `arrives_turn:` (eruption
   waves), and `item_drop:` where a twin drops one** so the engine models them (right now the seeds show
   "0 enemies" = unmodeled weapons). Also wire the Lupin/Sahnar/Basil `STAT_DONOR`s so `make difficulty`
   fields the true ch05 party (they're currently invisible to it — a known lever, not headroom).
3. **#138** config-driven `inject_chapter(descriptor)` (incremental; YAML `host:` block — approved
   direction, paused for the ch04/ch05 design).
4. Then **#29** world map.

## Working tree - do not lose or revert

- `fireemblem8u` is dirty from injected/generated build artifacts. **Never commit its submodule pointer.**
- Untracked local/session files (`.agents/`, `AGENTS.md`, `skills-lock.json`) are intentionally not
  versioned; leave them alone unless Nicolas asks. `tools/key_magenta.py` is now **gitignored** (#178)
  so it no longer trips the CI drift guard.
- Everything from this session is merged to `main`; no dangling local branches.

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
