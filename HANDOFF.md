# Handoff - Manchego Stars live state

`HANDOFF.md` is live state only. Settled decisions live in `docs/decisions.md`; operating rules
live in `CLAUDE.md`/`AGENTS.md`; issue scope and backlog live in GitHub. Before a context rollover,
warn Nicolas, refresh this file, and begin a fresh instance — don't rely on auto-compaction.

## Current state

- **Winter forest fidelity is an invariant (#193, merged `6a538bc`).** Snowy Bern retiles preserve the
  vanilla artists' forest sequences: the learned per-metatile map in `reskin-learned.json` is the sole
  authority, `gen_map_editor.py` refuses to generate on an unmapped forest variant, and
  `import_map_layout.py` re-checks every protected cell. Ch00–Ch02 backfilled. ADR: "Winter retiles
  preserve the vanilla artists' forest sequences…".
- **ch04 "The White Moose" (#24, branch `feat/24-ch04-map`, worktree `.claude/worktrees/ch04-map`) — combat host built; REDESIGNED 2026-07-21 into a full chapter.**
  `inject_ch04` hosts Ch4 on the vanilla Ch5 slot (15×15 snowy retile, fog 3, PREP 9-of-10, DefeatAll,
  `--ch04-boot`, `chain_ch03_to_ch04`). **This session redesigned the chapter around the wolf-parley
  REVEAL, adopted the "wolves turn the tide" difficulty model (raw fight above vanilla; parley discounts
  it back to dead-on vanilla — static ×1.15/×1.19, parley-path clear-load 2.5≈2.6), and REALIGNED the
  roster to mirror the vanilla-Ch4 twin 1:1** (Mogall×4·Revenant×12·melee Bonewalker×6·Entombed×1;
  the prior roster had drifted to D&D-monster-matched classes). Full design + staged checklist:
  **issue #24's 2026-07-21 comment** + `docs/decisions.md` ADR (on the branch). **Stage 1b is now DONE
  and committed (`cef0419`): `inject_ch04` wired to the realigned roster (added `CLASS_REVENANT` pid
  0xaa + melee `CLASS_BONEWALKER` pid 0xac / iron sword+lance; wave guard 16/4/3→10/6/7), village→Iron
  Axe, `difficulty_note`/`placement_directives` rewritten for the reveal, roster/spatial/dropper tests
  repinned. `make` + unit tests + `make check` + `git diff --check` all GREEN; parity holds (×1.15/×1.19,
  parley-path clear-load 2.5≈2.6).** Resume point = Stage 2 (see NEXT).
- **Parity/difficulty engine is three-dimensional** (`tools/difficulty.py`, all from HEAD): enemy
  pressure + item economy (#170/#172; drops #176/#178) + battlefield dynamics (convertibles + reinforcement
  timing #171/#174; area/zone #177/#178). `make difficulty CH=chNN` shows all three.
- **PC battle anims — 8 of 8 DONE** (braulo, marty, meesmickle, prof-rbg, wolfram, rootis, pinky, sclorbo).
  Sclorbo (#191) added the reusable **BISHOP dual-slot donor** (staff heal + light attack) that
  **Basil (ch05, #25) plugs into** (`battle_anim: {clone_from: bishop}` — no new donor work).
- **Enemy battle-anim import pipeline** (#90) + **per-caster charge flash** (#183) shipped; spell-palette
  tint (#168/#169) shipped. ch03 (#23) complete.
- **Recruit art shipped** (portraits + map sprites): Basil/Oddish (#179), Lupin + Sahnar (#181). Their
  build *wiring* (slot, STAT_DONOR, live `battle_anim:`) is ch04/ch05-slice work (#24/#25).

## This session (2026-07-21, Opus — landed #193, reconciled + hosted the ch04 combat slice)

- **#193 landed** (PR #194 squash-merged, CI green) after audit: strong regression coverage (forest
  counts + exact mapping + sha256-pinned non-forest cells), correct `.bin`→`.mar` format migration.
- **ch04 committed + rebased onto #193** as one clean commit (`df3183b`). #193 and ch04 were sibling
  branches that had both edited the map tooling / `reskin-learned.json` / `decisions.md`; reconciliation
  took #193's forest machinery + reskin-learned (superset), kept both ADRs and both test suites, and
  ported ch04's `review_output` (preview-beside-editor) onto #193's map editor.
- **Two agent-discipline learnings recorded in `decisions.md`** (so Codex finds them too):
  (1) *feature-flow only works if each feature LANDS before the next starts* — the parallel-unmerged-branch
  post-mortem that explains the recurring rebase; (2) an Operational Gotcha: **a `git` subprocess inside a
  git hook resolves against the outer repo unless you strip `GIT_*`** (this bit us — flipped `core.bare`
  and wrote a corrupt commit; fixed in `_vanilla_decomp_text` + the map-tileset test fixture).

## NEXT SESSION — start here: finish the ch04 slice (`feat/24-ch04-map`)

Design is LOCKED (2026-07-21). **Read issue #24's 2026-07-21 comment for the full design + staged
checklist**, and the `docs/decisions.md` ch04 ADR (both authoritative). Work in the
`.claude/worktrees/ch04-map` worktree. The staged build, `Closes #24`:

1. ~~**Stage 1b — `inject_ch04` wiring to GREEN.**~~ **DONE, committed `cef0419`** (details in Current state
   above). All required checks green; parity holds. **Resume at Stage 2.**
2. **Stage 2 — parley/convert + reveal cutscene (RESUME HERE):** Marty→Lupin `Talk` → table-swap (clear red pack + load
   green Lycanroc pack + Lupin red→grey) + the turn-2 reveal cutscene.
3. **Stage 3 — art:** green Lycanroc pack map sprite (princess-phoenix source + green palette, no glasses) +
   Lupin red/grey palettes.
4. **Stage 4 — scenes** (off the ch03 template): Lonelywood opening, moose-flees, real ending (replace
   `dev_placeholder_scene()`).
5. **Stage 5 — spatial check + `--ch04-boot` playtest** → confirm parity in-engine → open the PR.

Then: **#138** config-driven `inject_chapter(descriptor)` (approved, paused for ch04/ch05); **ch05** (#25)
grounding pass (apply the same verify-against-twin roster check); **#29** world map.

## Working tree - do not lose or revert

- `fireemblem8u` is dirty from injected/generated build artifacts. **Never commit its submodule pointer.**
  To run the map/forest tests cleanly after a build, restore the injected decomp files:
  `git -C fireemblem8u restore src/data/chapter_settings.json data/data_8B363C.s`.
- Untracked local/session files (`.agents/`, `AGENTS.md`, `skills-lock.json`) are intentionally not
  versioned; leave them alone. `tools/key_magenta.py` is **gitignored** (#178).
- `feat/24-ch04-map` (pushed) carries the ch04 slice — in progress, not stale. The old
  `feat/24-ch04-roster-grounding` branch is superseded (retire it). The realigned
  `ch04-the-white-moose.yaml` + the ch04 `docs/decisions.md` ADR are now **committed and build-green**
  (Stage 1b, `cef0419`) — no longer loose in the worktree. `review/` there is untracked session output
  (leave it; do not commit).

## Quick commands

```sh
# Parity/difficulty read (all from HEAD)
make difficulty CH=ch04

# ch04 fast-boot playtest build (New Game -> White Moose forest, party + foes deployed)
make CAMPAIGN=rime-of-the-frostmaiden CH04BOOT=1 fireemblem8.gba -j$(nproc)

# Required before claiming a change is finished
python3 -m unittest tools.test_build_campaign tools.test_difficulty
make check
git diff --check
```
