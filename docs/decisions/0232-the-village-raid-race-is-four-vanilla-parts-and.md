---
id: 232
title: "The village-raid race is four vanilla parts, and ch05 shipped none of them (#25)"
date: "2026-08-09"
section: "Operational Gotchas (durable)"
issues: [25]
---

# The village-raid race is four vanilla parts, and ch05 shipped none of them (#25)

ch05 declared a race for its four reliquaries since #196 — *"the eruption's dead race the party
for the spread reward-sites"*, plus a save-all bonus — and nothing on the map could reach a site
or pay for saving one. What vanilla Ch5 supplies, and what we were missing:
- **The destruction hook is already in the macro.** `Village(eid, scr, x, y)` expands to the
  `VILL` on the door *and* a `LOCA(eid, 1, x, y - 1, TILE_COMMAND_20)` one tile north.
  `AiPillageAction` calls `StartAvailableTileEvent(x, y - 1)` (`cp_perform.c`), which lands on
  that second entry and flips the tile through the chapter's MapChange array.
- **A real event id.** `location_events()` hardcoded `Village(0, ..)`, and flag 0 is
  `EVFLAG_ALWAYS_FALSE` — `CheckChapterFlag(0)` returns 0 forever, so no visit was ever recorded,
  no raider hook was ever disarmed, and nothing could be counted. ch05 takes `EVFLAG_TMP(9..12)`,
  **not** vanilla's `8..11`: its opening already ends on `ENUT(8)` (`ENUT` is `EvtSetFlag`, a
  vanilla prep idiom from ch12a/ch18a — not an un-trigger) and the Sahnar Talk holds 7.
- **MapChanges, ordered ruins-before-doors.** Four 3×2 ruins at `(doorX-1, doorY-1)` then four
  1×1 closed doors, which is vanilla's own array. `GetMapChangeIdAt` keeps the **last** region
  covering a tile (`bmtrick.c`) and the 3×2 overlaps its own door, so doors-first would make
  *visiting* a site collapse the building. The 3×2 footprint is also not decoration: the pillage
  lookup happens at `(x, y-1)`, so a change on the door alone is never found.
- **`TERRAIN_RUINS_REGULAR` is the lost state**, and the choice is load-bearing. FE8 decides both
  "can a unit Visit here" (`CanUnitVisit`) and "is this worth pillaging"
  (`gTerrainList_LootableVillages`) from the terrain. `TERRAIN_RUINS_VILLAGE` — the
  obvious-sounding pick — is in **both** lists, so a site ruined into it would be lootable again.
- **Raider AI on every wave.** All six of vanilla Ch5's reinforcements carry
  `.ai = {0x0, 0x4, 0x9, 0x0}` (AI_B_04, `AiScr_AiB_PillageThenPursue`) and nothing else does.
  Ours spawn on those same three tile-pairs, so all three eruption waves raid.

**The prize is a Guiding Ring, and the "crest of cold iron" is retired.** Vanilla Ch5 has **zero
droppers** — Saar included — and its one relic is gated on all four village ids at the ending
(`SVAL(EVT_SLOT_3, 0x68)` → `GIVEITEMTO(CHAR_EVT_PLAYER_LEADER)`). The crest was our invention
(the promotion-seam foreshadow, May 2026): it had no item id in any table, and Ravisin carried it
on a `drops:` key the injector never reads, so it was decoration that read like wiring. Items are
vanilla's unless there is a reason — the Goodberry and Tourmaline are the only renames — so the
foreshadow is now a real Guiding Ring nobody is near using, earned by saving all four sites
rather than handed over for killing the boss.

**The race also has to be SAID.** Vanilla spends its turn-2 box on the raiders' intent ("steal our
way through this pathetic town"); ours said only that more dead were coming, so the first warning
the player got was the engine's "The village was destroyed." popup, after a site was gone.
The beat mined from vanilla `0x9C5` now names the reliquaries. Its YAML slot label is anatomy only:
ch04 writes literal `0x9C5` as its Status objective, while ch05 hosts through `Ch6Events` and writes
the warning at its own `0x9E4`. That id is named and registered in `HOSTED_CHAPTER_MESSAGE_IDS`, so
the ownership guard fails before any later scene can double-claim it. "Houses" and "mausoleums"
were both tried and both collide with the fiction: the west resident calls the whole tomb *"this
house"*, and only Orem is buried here.
_Implemented: 2026-08-11 (#260)._

**Two scenarios, because one run cannot walk both paths.** `ch05raid` idles and proves a site is
LOST (terrain `0x03 → 0x25`, no gift, event id still unset — `TILE_COMMAND_20` changes the tile
and sets nothing, which is exactly why a sacked site cannot count). `ch05crest` saves all four,
kills Ravisin, and proves the ring lands. Neither `ch05village` nor `ch05reliquaries` could ever
have seen any of this: they walk a unit to a door and read what it hands over.
_Decided: 2026-08-09 (Nicolas: "we do what vanilla does"; all three open questions answered by
mining vanilla Ch5 rather than by choosing)._

---

**Playtest runs are the most expensive thing in this repo, and the human WATCHES them**
Nicolas, 2026-08-10, after a session that ran scenarios fourteen times: *"I am watching right now
as you run scenarios again and again... I am tired of it."* Two rules, because there are two
separate wastes and only one of them is about suite size.

**1. Run the smallest set that covers what changed.**
- Touched one chapter's constants → that chapter's suite (`SUITE=ch05`, ~11s cached).
- Touched an arbitrary subset → `matrix.py run --scenarios a,b,c`.
- Touched a SHARED helper (`location_events`, `collectedItems`, `village_script`, anything in
  `harness.lua`'s common section) → name the affected chapters' scenarios explicitly.
- **Do not run the full `make matrix` gate locally** (Nicolas, 2026-08-10: *"I dont want you to
  run the 7 min gate thing anymore"*). The verdict cache below now means a green scenario whose
  inputs are unchanged does not re-run — but it keys on `rom_input_hash`, so any
  `build_campaign.py` or campaign-data edit invalidated every row. Phase 2 scopes that to what
  the build actually wrote (a ch05 edit: 6 of 20). **The ban is permanent — it is a habit, not
  a feature waiting to be built.** #255 closed 2026-08-13 having deliberately dropped the code
  that would have retired it: what replaces the gate is "run your chapter's suite while
  developing (ch05 = 6 scenarios, one ROM build), never the gate". A scenario audit found
  nothing to retire either — 98 scenarios, and the gate's 20 are a curated union of the ch01
  spine + `recordunitlist` + ch04 + ch05, each pinning a distinct engine hook. The real problem
  is GROWTH (~6 per chapter), which scoping addresses and deletion does not.
  CI cannot take the gate either: CI builds against a MOCK base ROM
  (`head -c 16M /dev/urandom`), because the real FE8 ROM is copyrighted and not in the repo, and
  random bytes do not boot in mGBA.
- **`matrix.py run --suite X --dry-run` costs nothing and says what would actually run.** Reach
  for it before deciding a run is needed at all.
- **Never after a merge.** CI has already built and checked; a run whose result cannot change a
  decision is pure cost. If the result would not change what you do next, do not run it.
- The chapter suites are a SINGLE SOURCE and they go stale: `ch05` still listed `ch05village`
  alone long after three more ch05 scenarios landed in `gate`. Adding a scenario means adding it
  to its chapter suite too, not just to `gate`.

**2. When a scenario fails, spend ONE run learning, not one run per guess.**
This is the expensive half and it is not about suites. `ch05crest` failed four times in a row,
each run revealing exactly one blocker — a hidden striker, then a missing melee weapon, then a
combat wait that never ends — because each run only logged enough to test the hypothesis in hand.
All three were visible in the same memory at the same moment. The rule: on the first failure,
dump the whole neighbourhood of state the next three hypotheses could possibly need (every
candidate unit's `state`, its grid cell, its weapon range, whether the engine calls the action
legal), read it, then fix everything it shows. `inspect_state.py render` is the first stop, not
the last. A generalisation of the standing rule "do not re-run to re-test a hypothesis the
evidence already killed" — re-running to test a *new* hypothesis one at a time costs the same.

**3. A beat at the END of a long scene gets a DEBUG BOOT before it gets a film.**
Nicolas, 2026-08-15, stopping a run himself mid-scene: *"you're filming the wrong scene... that's
the chapter intro not the moose thing we're working on."* ch05's scene 7 is the last beat of a
~52-A-press opening, so `recordch05join` replayed four backdrop scenes, Preparations, the join
and Sahnar's monologue — **4m33s of footage he had already signed off — to reach ten seconds of
moose.** Three times. The rules above are about which scenarios to run; this is about what a
single run costs before it reaches the thing under review, and it is the same waste wearing a
different hat.

The fix is a boot that LANDS on the beat: `--ch05-moose` replaces the whole beginning scene with
scene 7 and the two LOAD1s it cannot do without, so New Game → title → chapter intro → the beat.
**4m33s → 34s**, and iteration becomes compile-time only. It is cheap — the block was already
factored (`ch05_moose_charge_block`), so the debug script is that call plus `LOMA` — and it
should be built BEFORE the first film of a late beat, not after the third.

Two things to get right, both learned by getting them wrong:
- **`bootToMap()` is the wrong driver on a debug boot**, because it drives to `player_map_idle`
  and on such a ROM the beginning scene IS the beat — so it mashes A through the whole thing and
  hands the film an idle map (measured: 3000 frames of nothing). Stop at `chapter_intro_input`,
  spend its one press, and let the film open on the `FADU` so the camera move and the hold are
  in shot.
- **The debug flag must not touch the shipping script.** `--ch05-moose` is a branch at the top of
  `ch05_beginning_script` and nothing else; a test asserts the real opening still carries prep
  and scenes 5–7.

**4. `run.sh` does not BUILD, and `make` can inject without relinking.**
Two runs on 2026-08-15 were spent on a ROM ten minutes older than the change under test, and
Nicolas reported the truth both times — *"sounded like the same rumble"*, then *"nothing changed
in that last run"* — because nothing had. `matrix.py` builds and then runs; `run.sh` only runs,
and reaching for it directly (to get `PT_SOUND`) silently tests the previous binary. `check-rom`
could not see it: the FLAGS matched exactly, only the code was stale.

Worse, the obvious fix hides a second trap. `make` re-ran injection and did **not** relink — the
ROM was three minutes older than the sources it was supposedly built from — and the check that
"confirmed" the sound was in it grepped the injected `ch6-eventscript.h`, i.e. an INPUT to the
build rather than its output. That is "an artifact is not its inputs" one layer down.

`run.sh` now refuses when `build_campaign.py` or `campaigns/**` is newer than the `.gba`, naming
the offending files. Verify a ROM against the ROM.
