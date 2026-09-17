---
id: 267
title: "The FE-Repo is READ, not grepped"
date: "2026-08-29"
section: "Operational Gotchas (durable)"
issues: []
---

# The FE-Repo is READ, not grepped

Scouting the FE-Repo by keyword misses the assets that matter. ch06's search found nothing useful
until the method changed; then it found five, and every one of them **contains no word describing
what it is**:

| the asset | what it actually is | the word that would have found it |
|---|---|---|
| `[Berserker-Hawkeye] Squidsmith` | the only aquatic AXE anim | none |
| `[General-Variant] IronShell-Tiny General` | the only armour anim carrying a LANCE | none |
| `[Spider-Variant] Cavalier Rider` | mounted **sword + lance**, one palette from a crab | none |
| `[Monster-Custom] Lamia` | a mounted-footprint staff healer | none |
| `Shark Rider (M/F)` | mounted merfolk, map sprite only | "shark", by luck |

A broad aquatic keyword sweep over the same tree returned **2,966 name hits**, almost all noise --
it matches artist handles (`SeaLion`, `WAve`, `Squidaccus`, `Shark3134`) and words like "sea" and
"ice" inside unrelated filenames -- and still surfaced none of the five. Keyword search answers
"who is named like a fish", which is not the question. The question is "what can wield an axe
underwater", and only a human reading the category can answer it.

**The method that works:**

1. **Pull the git trees, per top-level directory.** The root `git/trees/HEAD?recursive=1` call
   TRUNCATES (40,326 entries, `truncated: true`) and silently drops whole categories -- its
   top-level listing stops at "Battle Animations", so `Map Sprites` never appears. Fetch the root
   tree non-recursively for the directory SHAs, then recurse each one:
   `Map Sprites` returns complete at 3,074 files, `Portrait Repository` at 17,341; `Battle
   Animations` truncates at 44,200, so fetch its 23 category subtrees individually.
2. **Read the category listing by eye.** The monster and mounted categories are short enough
   (~100-210 names each) to scan, and scanning is what surfaced every asset above.
3. **Open the mode folders before believing anything about weapons.** `docs/fe-repo-scouting.md`
   already warns that its table says where an anim LIVES, not what it does. Do not `head` the
   listing either: the Mermaid's modes were first reported off a truncated list, and the full one
   (`2. Lance`, `4. Bow`, `4. Staff`, `5/6. Magic`, `7. Staff`, `8. Refresh/Unarmed`, and NO sword
   or axe) is what actually decided the roster.
4. **Check the map-sprite half separately.** An anim without a map sprite is half an asset, and the
   reverse (Kraken, Shark, Shark Rider) is common -- they look right walking and produce a vanilla
   monster's animation the moment combat starts.

Cost is a few API calls and one pass of reading. The alternative cost ch06 an afternoon of
believing the axe block had to be redesigned around an asset gap that did not exist.

**Enemy AI is BORROWED from a vanilla donor, not authored (#335)**
A chapter picks a vanilla twin so its difficulty is grounded rather than guessed, and we already
derive that twin's classes, levels, inventories and drops from its `UnitDefinition` structs. The
`.ai` field of those same structs was the one we never read. It got authored by feel through six
per-chapter `CHnn_AI` label tables, and because #48 computes threat from stats and weapons, the
drift was invisible to every gate: five chapters measured x1.00 and played nothing like their twin.

**Each enemy now names a `donor:` and the build reads that unit's four AI bytes.** There is no
label vocabulary in between, because the labels WERE the translation layer the drift lived in --
`aggressive` meant one thing in the YAML and another in five injectors, `defensive` and
`hold_position` were byte-identical under two names, and ch00's `ai_pattern:` was wired to nothing
at all (its injector emitted literals). Every chapter YAML had already named its counterpart in a
comment (`vanilla brigand @ (7,2) L3 iron-axe`) -- all 63 entries -- so `donor:` promotes prose
that was already there to data the build can read. `ai_override:` with a `why` is how a chapter
declares it means to differ.

**Three engine facts the model rests on**, all from the decomp:
- The vector is 2 script indices plus a 16-bit `ai_config` (`cp_utility.c` `LoadUnitAi`). `ai[2..3]`
  are its halves, not two bytes: bits 0-2 heal threshold, **bits 3-7 the combat weight table**
  (`cp_decide.c` -- *which enemy the unit picks*), bits 8-12 a guard-position index, bit 13
  `FLAG_STAY`. Our `aggressive` ran weight table 0 where Ch1/2/3/5 all run table 1.
- **AI scripts rewrite their own AI** (`AI_CMD_SET_AI`). `charge-after-one-turn` sets AI2 to pursue
  on turn 2; `pillage` sets it once the loot is gone. Only `AI_B_03 NeverMove` is terminal, so
  vanilla's lever is WHEN a unit activates, not whether.
- `AI_ACTION` vs `AI_ACTION_IN_PLACE` differ by one flag: the latter sets `AI_FLAG_STAY`, which
  collapses the movement map to the unit's own tile. Vanilla's static line (`{0x0,0x3,..}`) steps
  out to strike; our `defensive` (`{0x3,0x3,0x9,0x20}`) was welded twice over -- the A-script AND
  the config bit -- so we had put the throne-boss posture on every line unit in ch03/ch04/ch05.

**A donor matches where a vanilla unit FIGHTS, which is usually not where it is placed.** A
`UnitDefinition`'s `xPosition`/`yPosition` is frequently a SPAWN tile: `redas` is scripted movement
that walks the unit from there to its post, and the last REDA point is the destination. Vanilla
Ch1's entire force enters on (1,9)/(2,9) and Ch5's on (0,0)/(10,0)/(12,0), so matching a donor on
those tiles matches on "entered from the north", which is no identity at all.

This is not a detail. Matched on spawn tiles, 9 of ch05's 23 units appeared to line up with the
twin and the nine were coincidences -- one of them paired our bone-archer wave with an ARMOR_KNIGHT
boss, whose throne AI it would have inherited. Matched on POSTS it is **23 of 23**, class for class:
our mercenary stands on vanilla's mercenary's tile, our archer on its archer's. ch05's pairing is
therefore DERIVED, not assigned by hand, and it comes out matching the twin exactly.

Posts are also unique where placements are not, which retired an earlier `nth:` ordinal: Ch1's two
L2 fighters share spawn (2,9) and differ only in `redas`, but they post to (3,8) and (2,9). The
spec is still a MATCH (`at` / `class` / `level`) that resolves only when everything it matches
shares one AI, and it may be one donor PER POSITION -- a single donor per entry FLATTENS a group,
and ch04's four mogalls run three different AIs while ch05's eight tomb-reavers stand in for a
line vanilla splits 4/2/2.

**The AI_A_07 escort guard now sweeps EMITTED AI, not the label tables.** Strictly wider: it also
catches a unit that inherits `AI_A_07` from its donor, which no scan of our own vocabulary could
see. Still exactly one client, `ch05.sahnar`.

**Verification is an OUTPUT DIFF, and it earned its keep.** Every injector was re-run and
`events_udefs.c` diffed: 102 changed lines, all of them `.ai`, zero collateral. It caught a bug the
whole green test suite missed -- every injector called `enemy_ai_initialiser(chap, enemy)` without
the position index, so all eight of ch05's tomb-reavers shipped their FIRST donor's AI. YAML right,
resolver right, tests green, ROM wrong. `PerPositionAiReachesTheEmittedRows` now pins it.

ch01, ch03, ch05 and ch06 come out matching their twins exactly; ch01 emits byte-identical output
through the whole refactor, and ch06 -- the one chapter derived by hand -- reproduces byte for
byte, which is the model's proof. The only remaining differences are declared overrides: ch00's
Sephek (O'Neill's DoNothing depends on a tutorial `CHAI` we do not run) and ch04's six-wolf pack,
which is six units where vanilla loads four because #203 needs each wolf addressable by pid.
_Decided and implemented: 2026-08-29 (#335)._
**Message ids were rationed by a placeholder rule, and the pool is 528**
Every hosted chapter took "the dead block of the vanilla slot it displaces" -- ch03 got Ch4's
23 ids, ch04 got Ch5's 19, ch05 got Ch6's 18. That rule is safe with no analysis at all, since
blanking slot N's event lists kills slot N's text references, and it was the right first move.
It also caps a chapter at whatever one vanilla chapter happened to spend: **ch05 reached 0 free
and its next scene "cost a redesign, not an id"** while the id space sat 85% unspoken-for.

Measured: the table is **3404 ids**; 752 are referenced by any event script; 224 belong to the
seven slots we host in; **528 belong exclusively to chapters we never ship** -- Ch7-Ch21, the
route splits, the tower, the ruins -- in **14 contiguous runs of 16+, the largest 48 wide**, and
*none* of them referenced anywhere outside `src/events/`.

So a chapter now declares a TUPLE OF RANGES. ch02 takes `0xAC0-0xAEF` (it had no block at all,
which is why `make chapter` could not report its headroom); ch05 keeps `0x9E4-0x9F5` and gains
`0xBC5-0xBF2`. **Existing ranges are never renumbered** -- moving a shipped message id is a text
regression that surfaces only when the ROM runs.

**The guard is about OUR ids, not vanilla's.** The first version of it checked whether a range
was referenced by a chapter we host, and it flagged all three existing blocks -- correctly, and
uselessly, because those references die when we blank the slot. The real hazard is an id we have
**repurposed**: vanilla Ch2's three village texts (`0x969-0x96C`) are ch01's lord-select candidate
blurbs now, and a block drawn over them would build clean, ship, and garble a scene nobody was
looking at. `live_ids_in_declared_blocks` reads TWO sources, because neither is complete alone: the
module's `*_MSG`/`*_MSGS` constants (found by name, and a dict of them counts), and
`HOSTED_CHAPTER_MESSAGE_IDS`, which is the authoritative record of what each chapter
spends and depends on no naming convention. The name-only version shipped first and had
three blind spots, each of which would have built clean and garbled live text: ch02's hut
visits (held in `CH02_VILLAGE_SLOTS`), all 13 PC death quotes (a dict, whose name DID end
in `_MSGS`), and every chapter's objective window/status string (below an undocumented
0x300 floor). What the guard still cannot see is an id computed at inject time, and saying
so in the docstring is the point -- a guard may not rest on a convention nothing enforces.
_Decided and implemented: 2026-08-30._
