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
- **ch04 "The White Moose" combat slice is hosted (#24, branch `feat/24-ch04-map`, pushed, NOT merged).**
  `inject_ch04` hosts Ch4 1:1 on the vanilla Ch5 slot: 15×15 snowy retile (vanilla geometry + forest
  sequences preserved), roster grounded to real FE8 monster classes (Mauthe Doog / Bonewalker-bow /
  Mogall / Entombed), fog 3, PREP (9 of 10), DefeatAll/Rout, 16 line + 4(t2) + 3(t3) reinforcements,
  `--ch04-boot` fast-boot, `chain_ch03_to_ch04`. Borrows Super Fields' Snag family into Snowy Bern's
  empty slots (ADR). **Full ROM build green; 230 tests + `check.py` clean.** This is a WIP checkpoint —
  see NEXT.
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

## This session (2026-07-22→29, Opus — ch05 roster, engine work, dialogue; ROM-free web sessions)

**All ch05 detail lives on issue #25** (the live tracker comment) and in the chapter YAML — not here.
Summary only:

- **Environment:** Linux web container. The base ROM lives on Nicolas's Mac and isn't committed, so ROM
  builds / `verify_text` / mGBA playtests are OFF the table. `make difficulty` IS ROM-free. One-time
  container setup: `pip install pillow pyyaml numpy`; `git submodule update --init --depth 1 fireemblem8u`.
- **Protocol cleanup:** work moved onto **`feat/25-ch05-content`** with **draft PR #196** (body + title
  current as of `e4798e9`). The orphaned `claude/mobile-app-token-context-u2psep` remote branch still
  needs deleting from the GitHub UI (the proxy 403s on ref-delete).
- **ch05 roster CLOSED** (rev.3, PARITY) and **6 of 15 dialogue slots locked** (9BB/9BC/9BD/9BE/9C2/9C3).
  → **issue #25**.
- **Difficulty engine gained three tools** (all ROM-free, all tested): a **per-unit role check**
  (`role_findings` — the aggregate averages a monster away and never compares the boss to anything;
  ch04 verified clean by it), **terrain wiring** (§Terrain — FE8's own tables + vanilla layouts), and
  **boss personal stat lines** (scoped to the role check on BOTH sides; putting them in the aggregate
  shifted every curated baseline). New tool **`tools/vanilla_scene.py`** prints any vanilla chapter's
  scenes as boxed dialogue with counts.
- **Craft law recorded** (binding in the `dialogue-pass` skill): mine the corpus BEFORE writing
  (`references/natural-speech.md`, `fe8-register.md`, `scene-pacing.md`); epigram disease; no contrasting
  clichés; draft boxed; tracker upkeep is part of the lock step. ADRs in `decisions.md`.
- **Sahnar is MISLED, not seized** (2026-07-29, reconciled repo-wide) — Ravisin wakes her and lets her
  draw the wrong conclusion; she fights of her own will, and Basil turns her by telling her the truth.
  Her voice's two temperatures are now misled → turned.
- **Marty's "spore covenant" is RETIRED** (2026-07-29) — a ch05 villain-foil thread we drifted
  away from while writing and never used in a beat. Cut from `marty.md`, registered in
  `check.py` `DEAD_CONCEPTS`. His voice is `lore/marty.md` §Voice, full stop.

## NEXT SESSION — start here (branch `feat/25-ch05-content`, draft PR #196, ROM-free)

**Read [issue #25](https://github.com/NicoviGH/manchego-stars/issues/25) first — its latest comment is the
live ch05 tracker** (settled decisions, the 15-slot scene map, which beats are written, what's next).

1. **Invoke the `dialogue-pass` skill and DO ITS STEP 0** — mine the corpus before writing a line. This is
   mandatory, not advice: 9BB burned a dozen drafts written from instinct.
2. **Next beat: 9C4 — Basil steeling himself mid-escort** (vanilla's 4-box Natasha prayer). Then **9C6,
   the recruit** — the chapter's payoff, owed by BOTH 9BB's "One day I'll give her one" and 9C3's
   certainty. Remaining after that: 9BF / 9C0 / 9C1 / 9C5 / 9C7 / 9C9.
3. **Guardrails that broke repeatedly — do not re-break:** Ravisin's motive is Auril's cosmic winter, full
   stop (no grudge/grief/revenge/pathos — banned in her bible); she is never softened or mourned. Sahnar
   knows only what Basil tells her, and is misled rather than bound. Draft BOXED (~29–30 ch/line, on-map ≤29).
4. **DoD:** locked scripts → `script:` blocks in the ch05 YAML with `LOCKED <date>`; update the #25 tracker
   comment AND the PR body in the same breath; commit ROM-free on `feat/25-ch05-content`.

## PARALLEL THREAD (ROM-gated, Nicolas's Mac): finish the ch04 slice (`feat/24-ch04-map`)

The combat slice is hosted and builds; it is **not** a complete chapter. To finish and PR-merge #24:

1. **Wolf parley + Marty-Talk teaching** — the two open events decisions in `ch04-the-white-moose.yaml`:
   parley behavior (green-and-fight vs green-and-leave) and teaching the player Marty can Talk to parley
   the Mauthe Doog pack (Lupin recruits as a non-combat NPC). `inject_ch04` currently wires combat only.
2. **Authored ending scene** — currently a `dev_placeholder_scene()`; write the real ch04→ch05 hand-off.
3. **Tiered-difficulty spatial check + playtest** — run the analyst pass on the placed map, then play the
   `--ch04-boot` build, then lock. Then open the PR (`Closes #24`).
4. Wire Basil/Lupin/Sahnar STAT_DONORs when their ch04/ch05 slices need them.

Then: **#138** config-driven `inject_chapter(descriptor)` (approved, paused for ch04/ch05); **ch05** (#25)
grounding pass; **#29** world map.

## Working tree - do not lose or revert

- `fireemblem8u` is dirty from injected/generated build artifacts. **Never commit its submodule pointer.**
  To run the map/forest tests cleanly after a build, restore the injected decomp files:
  `git -C fireemblem8u restore src/data/chapter_settings.json data/data_8B363C.s`.
- Untracked local/session files (`.agents/`, `AGENTS.md`, `skills-lock.json`) are intentionally not
  versioned; leave them alone. `tools/key_magenta.py` is **gitignored** (#178).
- `feat/24-ch04-map` (pushed) carries the ch04 combat slice — in progress, not stale. The old
  `feat/24-ch04-roster-grounding` branch is superseded (retire it).

## Quick commands

```sh
# Parity/difficulty read (all from HEAD)
make difficulty CH=ch04

# ch04 fast-boot playtest build (New Game -> White Moose forest, party + foes deployed)
make CAMPAIGN=rime-of-the-frostmaiden CH04BOOT=1 fireemblem8.gba -j$(nproc)

# Required before claiming a change is finished (468 tests; `tools/` isn't a package,
# so unittest discover can't find them -- expand the glob)
python3 -m unittest $(ls tools/test_*.py | sed 's|/|.|;s|\.py||' | tr '\n' ' ')
make check
git diff --check
# A test/build run dirties the fireemblem8u submodule with INJECTED artifacts
# (e.g. engine_hooks' MSChargeFlashArm decl). Restore, never commit:
git -C fireemblem8u status --short   # then: git -C fireemblem8u restore <files>
```
