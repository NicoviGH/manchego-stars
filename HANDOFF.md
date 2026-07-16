# Handoff - Manchego Stars live state

`HANDOFF.md` is live state only. Settled decisions live in `docs/decisions.md`; operating rules
live in `CLAUDE.md`; issue scope and backlog live in GitHub. Before a context rollover, warn
Nicolas, refresh this file, and begin a fresh instance — don't rely on auto-compaction.

## Current state

- **Parity/difficulty engine is now three-dimensional** (`tools/difficulty.py`, all read from HEAD):
  1. **Enemy pressure** (existing) — threat/slot + clear-load/slot vs the `parity_reference` twin.
  2. **Item economy** (#170, merged #172) — `vanilla_economy()` extracts the twin's chests / gifts
     (villages/houses + conditional clear rewards) / shops, valued from `data_items.c`; printed as
     `ITEM-ECONOMY PARITY`. `chapter_economy()` reads ours from YAML.
  3. **Battlefield dynamics** (#171, merged #174) — convertibles (CHAR-macro targets, e.g. Ch5's
     Joshua) + reinforcement timing (`TurnEventPlayer` waves) auto-detected; printed as an ADDITIVE
     `BATTLEFIELD DYNAMICS` section (static verdict/gate untouched). Our YAML: `convertible:` /
     `arrives_turn:` on enemy_units.
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
- **ch03** (#23) remains down to enemy battle-anim art only (unchanged this session).

## This session (2026-07-16, Opus — engine hardening + ch04/ch05 design lock)

- Merged **#167** (spell-tint hook registration) → did **#168** as **#169** (de-overload to `gMSSpellTint`;
  full build + verify_text 3404/0 + recordanim green Flux confirmed by data: 3.51% green px in the cast
  windows vs ~0.6% idle baseline).
- **Corrected a real error, mid-design:** claimed vanilla Ch4 had "4 chests incl. a Red Gem (~6,220g)"
  — WRONG, that was our injected ch03 in the Ch4 host slot read from the working tree. True Ch4 =
  **2 villages / one Iron Axe / ~270g / 0 chests** (the original brainstorm was right). Retracted on #24.
  This motivated #170 (the tool reads HEAD, can't make that mistake).
- Built **#170 + #171** (engine dimensions above), TDD, both merged.
- **Locked ch04/ch05** (#175) — see decisions.md. The design conversation is fully captured there;
  the settled shape:
  - **ch04 = our FE8 Ch4** (Ancient Horrors) 1:1 — Rout, retiled snowy forest, **fog ON** (the hunt,
    a config flag not a map feature), lean ~270g, **wolf-pack parley** (Marty→Lupin), **Trex as the fog
    scout** (Thief +5 vision — fits Ch4's actual gimmick, the monster-debut). **No chest-race** (foreign
    to Ch4).
  - **ch05 = our FE8 Ch5** (The Empire's Reach) 1:1 — DefeatBoss(Ravisin), retile Ch5's **open spread
    field** as an open-air tomb depression (NOT a corridor — keep spread reward-sites + cavalry lanes),
    **no fog**. Rebuilds Ch5's two set-pieces: **Basil→Sahnar chaperone** (Natasha→Joshua; donors match
    exactly) and the **eruption** (`EARTHQUAKE`/`TILECHANGE`, injected) raiding spread reliquaries
    (the village-race). Ch5-magnitude economy + elven store; first chapter at the Ch5 reward tier.
- Filed engine follow-up gaps **#176** (economy drops) + **#177** (area-triggered reinforcements).

## Why we dropped the Ch11 map-borrow (so it isn't re-litigated)

Everything Option B wanted from the Ch11 pair — **fog, dark theme, the eruption** — is a config flag,
custom tileset, or injectable event; **none live in a map's layout**. Borrowing Ch11's layout only cost
the twins' terrain (esp. Ch5's spread two-front race, which Phantom Ship's corridor kills). So each
chapter maps 1:1 to its numeric FE8 twin (map + parity) and the theme is layered on top.

## Next steps (priority order)

1. **Build the ch04 / ch05 slices** (M3, the main line). Per-chapter vertical slice on #24 / #25.
   Author the map (Tiled retile of vanilla Ch4 / Ch5 per the map-authoring pipeline) + roster + events,
   tuned against the now-machine-checkable targets via `make difficulty`. When authoring the roster,
   **tag enemy_units with `fe_base` weapons, `convertible:` (Sahnar), and `arrives_turn:` (eruption
   waves)** so the engine models them (right now the seeds show "0 enemies" = unmodeled weapons).
   Also wire the Lupin/Sahnar/Basil `STAT_DONOR`s so `make difficulty` fields the true ch05 party
   (they're currently invisible to it — a known lever, not headroom).
2. **Engine parity fidelity: #176 + #177** — do before/alongside the slice tuning so the bars are
   complete (drops; area/zone-triggered reinforcements like Ch4's). Both well-specced on the issues.
3. **#138** config-driven `inject_chapter(descriptor)` (incremental; YAML `host:` block — approved
   direction, paused for the ch04/ch05 design).
4. Then next battle anim / **#29** world map.

## Working tree - do not lose or revert

- `fireemblem8u` is dirty from injected/generated build artifacts. **Never commit its submodule pointer.**
- Untracked local/session files (`.agents/`, `AGENTS.md`, `skills-lock.json`, `tools/key_magenta.py`)
  are intentionally not versioned; leave them alone unless Nicolas asks.
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
