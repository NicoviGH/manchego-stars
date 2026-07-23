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

## This session (2026-07-22→23, Opus — ch05 roster grounded + dialogue foundation + opening locked, ROM-free web session)

- **Environment note:** ran in a Linux web container — the base ROM lives on Nicolas's Mac and
  isn't committed, so ROM builds / `verify_text` / mGBA playtests are OFF the table here. Chose
  ROM-free work: **`make difficulty` is explicitly ROM-free** (reads YAML + decomp `HEAD`), so the
  tier-1 roster-grounding loop runs fine. (One-time container setup: `pip install pillow pyyaml
  numpy`; `git submodule update --init --depth 1 fireemblem8u`.) Branch: `claude/mobile-app-token-context-u2psep`.
- **ch05 "The Elven Tomb" roster GROUNDED to FE8-Ch5 parity — rev.2 (#25, tier-1).** The force is now
  **RISEN ELVEN TOMB-GUARDIANS on the vanilla FE8 infantry classes** (Soldier/Fighter/Mercenary/Archer/
  Armor-Knight/Myrmidon), skinned undead — the ch01 "vanilla class, our skin" (`enemy_class_reskins`)
  pattern. **Parity by construction** (living-class stats = the twin's stats): **verdict PARITY,
  threat/slot 12.5 (x1.21) · clear-load/slot 5.0 (x0.97, ≈ vanilla 5.2)** — better-centered than rev.1.
  Structure kept: 16 line + 6 eruption reinf + 1 convertible (Sahnar). **`deploy_limit: 9`** set —
  the difficulty-driven value (vanilla FE8 Ch5's 9 slots, fe8-pacing §1b; NOT map-tile-driven — the map
  is painted to fit); verdict unchanged (ratio is cap-invariant). **WOLVES CUT** (Nicolas: ch04 is
  the beast chapter; the lone beast here is the White-Moose boss = ch04 payoff). Each enemy carries a
  `skin:` field naming the intended FE-Repo asset (sword/bow = real skeleton anims Bonewalker/Specter/
  Wight-Sniper; lance/axe/armor = frost palette-swaps). `decisions.md` ADR refined: the real glassy fix
  is a SKIN divorce (undead skins on infantry classes), not a beast-spine composition fight — generalises
  to ch06/ch08. `status: planned` unchanged (flips to active only at the Lock, tier-5). 209 tests +
  `make check` + schema all green.
- **rev.1 (2026-07-22, superseded):** undead MONSTER classes (revenant/mogall/entoumbed + beasts) tuned
  to PARITY at clear-load x0.81 (band edge) — fought the "glassy" doubling problem. Replaced by rev.2.
- **FE-Repo scouting COMPLETE → `docs/fe-repo-scouting.md`** (new). Key finding: undead humanoid anims
  live on monster/sword/bow/magic frames; **lance/axe/armored undead are a gap → frost palette-swaps**
  (one lance exception: `Skeleberdier`). ch05 skins sourced (Skeleberdier/Bonewalker/Wight-Sniper/
  Specter/Gwyllgi + palette-swaps). Cross-chapter: wolf/beast anims **logged on issue #24** (ch04 pack +
  Lupin); **ch06 Messie has NO off-the-shelf sea-monster** (custom/substitute needed — flagged); ch08
  ice-troll → `Yetizerker`; undead casters (Skeleton Druid, Necromancer) exist if any chapter wants one.
- **Still owed for ch05 (later tiers):** map + placement (tier-2), spatial analyst check (tier-3),
  `--ch05-boot` playtest (tier-4), and the **enemy_class_reskins wiring + FE-Repo imports** (the art
  track) — all need the ROM/build, so NOT this environment.
- **PROTOCOL CLEANUP (2026-07-23):** work moved off the session branch onto **`feat/25-ch05-content`**
  (proper feature branch) with **draft PR #196 → `main`** (references #25, does NOT close it). Issue #25
  body corrected (stale brazier puzzle → real design) + progress comment posted. The old
  `claude/mobile-app-token-context-u2psep` remote branch is an orphaned dup the proxy blocked me from
  deleting (403 on ref-delete) — **kill it from the GitHub UI**.
- **ch05 DIALOGUE foundation + OPENING done (co-written with Nicolas).** Voice bibles finalized & hardened:
  **Ravisin** (certain, unsympathetic zealot — **pathos is BANNED in her bible; do NOT re-soften/mourn her**,
  it kept creeping back), **Sahnar** (canon-corrected: **she/her**, elven royalty, awake-for-millennia;
  bound-but-conscious, freed by Basil — no anti-human crusade), **Basil** (Groot-flavored but self-sufficient;
  canonically Ravisin's own shrub), **Marty** (the "spore covenant" in `marty.md` — composter vs taxidermist;
  it *resolves* the still-undead-Sahnar recruit instead of contradicting it). **OPENING LOCKED** in the ch05
  YAML as TWO cutscenes (vanilla rhythm): `chapter_start` pre-map (ch04 thread; Lupin/Marty/Pinky; Ravisin
  SILENT, saved) + `map_opening` on-map (Basil joins green→blue via the wolf-realization → asks for Sahnar).
  Craft learnings folded into the `dialogue-pass` skill (people-talking-not-mood-narration; draft BOXED).

## NEXT SESSION — start here (branch `feat/25-ch05-content`, draft PR #196, ROM-free): ch05 ERUPTION beat

Roster settled AND opening locked (do NOT re-litigate either — see above). Continue the **dialogue pass** on
the remaining 3 beats via the `dialogue-pass` skill (co-written WITH Nicolas; bring **BOXED** variants only
where there's a real fork; he curates; lock into the YAML `script:` blocks).

- **Read first:** the `dialogue-pass` skill (now carries the box-first + people-talking checks); the four
  finalized voice bibles (`lore/ravisin.md`, `sahnar.md`, `basil.md`, `marty.md` §spore covenant); the ch05
  YAML `events:` (opening locked; eruption/recruit/ending next).
- **BEAT 2 — the eruption (`ch05-eruption`), the loaded one:** it all converges. Ravisin's **first words**
  (hardened, pathos-free — certain, not aching); she **rips Sahnar up** (bound-but-conscious, against her will)
  as a desperate power-play, and the lesser dead erupt (reinforcements, arrives_turn 2/3/5). **Basil's break**
  — his innocent love for the witch dies ("No. Not her."), and his DEFERRED "she's a druid… she lost her way"
  lands here against what she's doing. **Marty's covenant** fires, quietly (he goes silent in violence): "She
  should be earth by now… you've kept her frozen, halfway home."
- **BEAT 3 — Sahnar recruit (`ch05-sahnar-recruit`):** Basil, escorted across, Talks/frees the bound Sahnar
  (the Joshua flip); she comes back to herself, chooses "not yet," joins.
- **BEAT 4 — ending (`ch05-ending`):** Ravisin falls **proud, not repentant** (her banned list); the party
  repots/names/adopts Basil (villain's-pet → party's-heart); turn toward Bremen (the ch06 Messie hook —
  hinted, Ravisin never named).
- **Guardrails (twice-flagged this session):** Ravisin is NEVER softened or mourned (Basil's kindness ≠ the
  story pitying her); she stays Auril's, the big bad. Draft BOXED (~29–30 ch/line, on-map ≤29) from the first
  pass — not prose.
- **DoD:** locked scripts → `script:` blocks in the ch05 YAML with `LOCKED <date>`; commit ROM-free on
  `feat/25-ch05-content` (feeds PR #196). `verify_text` + `.ea` assembly are ROM-gated (Nicolas's Mac).

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

# Required before claiming a change is finished
python3 -m unittest tools.test_build_campaign tools.test_difficulty
make check
git diff --check
```
