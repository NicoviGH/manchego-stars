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
- **Ravisin RE-CENTERED on Auril (4th fix).** Her bible kept sliding back to a loggers-grudge/revenge plot;
  now rewritten so her motive is **Auril's cosmic winter, full stop** (acolyte snuffing warmth for the
  goddess; loggers = incidental warmth), with grudge/grievance/revenge added to her banned list. Then started
  **BEAT 2 (the eruption)** — structure agreed but **lines not landing yet** (see NEXT). Fixed a consistency
  bug in passing: Ravisin **SEIZES** the already-undead Sahnar, she does NOT reanimate her (sahnar.md/marty.md/
  narrative aligned).
- **DIFFICULTY-ENGINE work (2026-07-23) — a boss-role post-mortem that grew three tools.** Triggered by
  Nicolas asking how the ch05 boss inversion slipped past a PARITY verdict:
  1. **PER-UNIT ROLE CHECK** (`role_findings`, printed by `make difficulty`): the aggregate averages a
     monster away and never compares the boss to anything. Now flags threat outliers vs the twin's ceiling,
     a boss out-threatened by its own line, a boss that folds faster than half the twin's boss, and >1
     `is_boss`. Convertibles are exempt from the inversion check (neutralized, not ground down).
     **ch04 verified CLEAN by it** — its extremes track vanilla Ch4 and, like its twin, it fields no boss.
  2. **TERRAIN wired** (§Terrain): FE8's own `TerrainTable_Avo/Def_Common` + terrain enum parsed from HEAD,
     tile→terrain via `map_tileset_tool.vanilla_layout_data()`. A unit declares `tile_terrain:`. Killed two
     of my assumptions: `GuardTileAI` means "don't chase," NOT "on a throne" (Saar stands on plain
     `TERRAIN_ROAD` — his wall is 100% class Def), and `.xPosition` is a SPAWN point (`.redas` walks a unit
     to its real post; Saar spawns (13,0), posts (13,1)).
  3. **BOSS PERSONAL LINES** (`personal:` / `vanilla_personal_line`): FE8 bosses are walls because of a
     personal stat line (Saar = Armor Knight **plus** HP+13/Def+2/…), not their class. Scoped to the role
     check **on both sides** — putting it in the aggregate shifted every curated baseline (**ch02 briefly
     fell out of band; caught via `git stash`, reverted — ch02 itself is fine, just sits on the ±25% edge**)
     and made a Def-13 boss undentable. `vanilla_boss_bar()` falls back to class base **per boss**.
  ch05 outcomes: **moose → named miniboss + convertible** (killing Ravisin breaks her hold; its 14-threat is
  now an "avoid me" hazard, and gwyllgi can't be nerfed — Spd 14 doubles even at L2); **Ravisin gets a
  `personal:` line** (HP+15/Def+5 → ~13.4 rounds = Saar's bar) so she stays a Druid with Flux and her art —
  **FE8 has no tanky mage class** (best magic Def is 5) and the FE-Repo shares art, not class definitions;
  **throne DROPPED** (personal Def + terrain stack to undentable — one lever, not two) and the **frost-sentinels
  REMOVED** with it (Nicolas: redundant once she carries her own fight).
- **COMPOSITION lesson (bit twice, now an ADR).** Both the sentinels and a crypt-blade 2→4 bump were "tune the
  count to move the number" — vanilla Ch5 fields **one** Mercenary and its only Armor Knight **is the boss**.
  Fixed: the mix now matches Ch5 exactly on Soldier 6 / Archer 3 / Mercenary 1 / Myrmidon 1, axe block 10 of 23
  (~43% vs vanilla's ~48%) — **Ch5 is an axe-heavy map and the weapon triangle is invisible to the per-slot
  averages.** Parity improved doing it: **x1.11 threat / x0.84 clear-load.** All six chapters PARITY; 226 tests.

## NEXT SESSION — start here (branch `feat/25-ch05-content`, draft PR #196, ROM-free): ch05 ERUPTION beat

**Roster is CLOSED (rev.3), opening is LOCKED, and the difficulty engine work is DONE — do not re-litigate
any of it** (see above; all six chapters PARITY, 226 tests green). The only ch05 work left in this environment
is **dialogue**. Continue the **dialogue pass** on the remaining 3 beats via the `dialogue-pass` skill
(co-written WITH Nicolas; bring **BOXED** variants only where there's a real fork; he curates; lock into the
YAML `script:` blocks).

- **Read first:** the `dialogue-pass` skill (now carries the box-first + people-talking checks); the four
  finalized voice bibles (`lore/ravisin.md`, `sahnar.md`, `basil.md`, `marty.md` §spore covenant); the ch05
  YAML `events:` (opening locked; eruption/recruit/ending next).
- **BEAT 2 — the eruption (`ch05-eruption`) — IN PROGRESS; lines NOT landing (this is why we handed off).**
  Structure agreed with Nicolas: keep it **Ravisin-FORWARD**. She's pressed, escalates, and **SEIZES the
  tomb's ancient guardian Sahnar** — who is ALREADY undead (awake millennia), so she *puppets an existing
  bound soul*, she does NOT reanimate a fresh corpse. The lesser dead rouse as reinforcements (arrives_turn
  2/3/5). **Sahnar gets NO line — a body Ravisin takes; do NOT spotlight her** (Nicolas: "don't draw more
  attention to Sahnar"). **Basil's break + Marty's covenant are PULLED OUT** of this beat to keep it hers —
  at most one small quiet Basil beat; Marty's covenant likely moves to the recruit.
  - **Ravisin's DOCTRINE (use this — research-grounded):** the **purification / "blight"** doctrine. Warm
    humanity is **the blight / sickness / fever**; Auril's winter is the **cure / cleansing / salvation**
    (the world was clean-white-still once; warmth is the corruption); she **cleanses, does not kill**.
    ⚠️ Community DM-note finding: the book Ravisin's rich material is almost ALL **sister-revenge/grief** (a
    guide literally says she's grief-driven "rather than ideological commitment to Auril") — which we CUT.
    Blight/cure/cleanse is the strongest Auril-only vein; do NOT re-import grief.
  - **The lore drop (her job in the beat):** she's **one of Auril's legion; the cold outlasts her** — killing
    her ends nothing. Keep it GENERIC so the player connects it themselves to the prologue frost-druid
    **Sephek Kaltro** (Auril's servant who escaped; recurring Act-II villain — the Children-of-Auril thread is
    ALREADY seeded, not a new "Circle of Winter" to invent). Build it to ECHO Sephek's line *"You cut the ice…
    not the cold that made it…"* → e.g. "you cut one servant, not the cold behind it," "you cannot kill a season."
  - **THE OPEN PROBLEM — Ravisin's lines keep reading FLAT.** Theme is right, craft isn't. Several rounds
    were rejected; the pattern in all of them was **doctrine STATEMENTS and one flat emotional temperature**,
    not a person. REJECTED so far: "warm things / her things dead"; "you are the blight / the winter is the
    cure / I cleanse"; "you cut one servant / her hands are legion"; and a calm-monotone pass ("Easy now.
    It's only people." / "Others came before you." / "Elves keep their dead close." / "Winter is patient.")
    which Nicolas called terrible — *"where did all the interesting go."*
  - **⚠️ TWO CRAFT RULES LEARNED THE HARD WAY (both now in the skill; obey them from line one):**
    (a) **No contrasting clichés** — no "not X, but Y", no then/now antithesis, no defining by negation. My
    whole Ravisin voice had been built on it ("that's not life, it's fever" / "I don't kill, I cleanse" /
    "you grew things once, now nothing grows"), which is *why* every character sounded identical.
    (b) But over-correcting into flat declaratives produced **monotone** — the rejected calm pass. Vary
    rhythm and temperature; let lines surprise.
  - **RESEARCH DONE — how FE8 villains actually speak** (pulled from `fireemblem8u/texts/texts.txt`; do not
    redo this). Valter: *"Ha ha… She's a ripe little peach… I can feel my blood rushing at the thought. This
    might be fun after all."* / *"You will call me the Moonstone. I'll save you worthless dogs from your own
    incompetence. **You'll thank me later.**"* Riev: *"Like rats in a sack, as they say. Heh heh heh…"*
    Selena: *"What idiotic wretches you are… Prepare yourselves to be destroyed utterly!"* **The pattern:**
    they address the party DIRECTLY with an insult-name (dogs/wretches/rats), they RELISH it, they use dark
    irony (Valter frames butchery as a favour — that is Ravisin's "frost is mercy" belief with swagger
    instead of a sermon), they announce what's coming, short sentences, heavy `…`.
  - **LAST VERSION ON THE TABLE (untested — we diverted to mechanics before Nicolas ruled on it).** One
    strong idea instead of a safe one: **she loves the things she wakes like her own children and treats
    living people as weather** — warm to the dead, absent to the living; defectors don't anger her, she's
    *fond* of them, which is worse. Sample beats: grooming the moose mid-battle (*"Hold still, love. You've
    ice in your ear."*), hospitably telling the party *"Come down. Mind the steps."*, greeting Lupin as
    *"My finest voice, that one."* and patting away his name with *"You always did wander."*, calling Basil
    *"my little garden. Come here."*, raising an army with *"…Up you get."*, and buttoning on *"Come along,
    children."* Nicolas's own suggested opener — **"so you followed my moose home"** — should survive in
    some form.
  - **Pitfall:** do NOT have her reference **fire** the party carries — nobody wields fire and **Rootis is a
    snow/cold sorcerer**. Frame the party as **warm / alive** (breath, blood-heat, fever), never fire-bearers.
- **BEAT 3 — Sahnar recruit (`ch05-sahnar-recruit`):** Basil, escorted across, Talks/frees the bound Sahnar
  (the Joshua flip); she comes back to herself, chooses "not yet," joins.
- **BEAT 4 — ending (`ch05-ending`):** Ravisin falls **proud, not repentant** (her banned list); the party
  repots/names/adopts Basil (villain's-pet → party's-heart); turn toward Bremen (the ch06 Messie hook —
  hinted, Ravisin never named).
- **Guardrails (flagged 3× this session — do NOT re-break):** Ravisin's motive is **Auril's cosmic winter,
  full stop** — she's the Frostmaiden's acolyte snuffing warmth for the goddess. **NO loggers-grudge, NO
  grievance/revenge, NO grief, NO tragic/sympathetic framing** (all banned in `ravisin.md`); the loggers are
  incidental warmth, never a wronged party. She's never softened or mourned (Basil's kindness ≠ the story
  pitying her). Draft BOXED (~29–30 ch/line, on-map ≤29) from the first pass — not prose.
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
