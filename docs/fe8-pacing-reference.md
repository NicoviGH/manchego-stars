# FE8 Pacing & Reward Reference

> **Purpose.** A pure **FE8 reference** — the chapter cadence, treasure flow, and
> promotion-item placement of *Fire Emblem: The Sacred Stones* — so Manchego Stars'
> pacing "feels like FE8" instead of like a D&D module cut into arbitrary slices
> (FE8 is the spine; see `docs/decisions.md` / memory `feedback_fe-strictness`).
>
> **This doc holds FE8 facts only.** How we *apply* them to our campaign lives
> elsewhere: the cadence taxonomy + the promotion seam in `docs/decisions.md`, the
> per-chapter index in `docs/CHAPTERS.md`, and the post-MVP scaffold in
> `docs/roadmap.md`.
>
> **Sourcing honesty.** Two confidence tiers are used below:
> - **[decomp]** — verified against `fireemblem8u/` (item names in `texts/texts.txt`;
>   class→promotion mappings in `src/data_itemuse.c`; win-conditions in each
>   chapter's `src/events/<ch>-eventinfo.h`).
> - **[FE8]** — well-established FE8 community knowledge (chapter order, the
>   *chapter* each reward first appears). Pinning each item to an exact chapter via
>   the decomp's event scripts is deferred (see Open Items); treat the chapter
>   numbers as "early-teens, route-split era," not gospel ±1 chapter.

---

## 1. FE8 chapter list & cadence (main path) [FE8]

FE8's Eirika route runs ~21 maps. The rhythm is what we copy — **not** a 1:1
plot map. **Objective column is [decomp]-verified** — read from each chapter's
`fireemblem8u/src/events/<ch>-eventinfo.h` win-condition macro (`DefeatBoss` /
`DefeatAll` / `Seize(x,y)` / `Survive`). Note FE8 has **no "Rout" verb** — the
clear-all-enemies objective is spelled `DefeatAll`.

| FE8 | Map | **Objective [decomp]** | Cadence role |
|---|---|---|---|
| Prologue | The Fall of Renais | **DefeatBoss** | tutorial / set-up |
| 1 | Escape! | **Seize** (2,2) | breather (small, teach movement) |
| 2 | The Protected | **DefeatAll** | escort / teach defending |
| 3 | The Bandits of Borgo | **Seize** (14,1) | **big battle** (Ross/recruit) |
| 4 | Ancient Horrors | **DefeatAll** | monsters introduced (tone shift) |
| 5 | The Empire's Reach | **DefeatBoss** | **big battle** |
| 5x | Unbroken Heart | **Seize** (13,7) | gaiden / breather (optional feel) |
| 6 | Victims of War | **DefeatBoss** | story pivot |
| 7 | Waterside Renvall | **Seize** (9,4) | **big battle** (siege, rescue Ephraim) |
| 8 | It's a Trap! | **Seize** (10,2) | escape / reversal |
| 9 | Distant Blade (route split) | **DefeatAll** (9a) | **big battle**, new region |
| 10 | Revolt at Carcino | **Seize** (10a) | political turn |
| 11 | Creeping Darkness / Phantom Ship | **DefeatAll** | monster set-piece |
| 12 | Village of Silence / Landing at Taizel | **DefeatAll** (12a) | breather / supply |
| 13 | Hamill Canyon / Fluorspar's Oath | **Survive** (13a) | terrain gimmick battle |
| 14 | Queen of White Dunes / Father and Son | **Seize** (14a) | **big battle** (mid-climax) |
| 15 | Scorched Sand | **DefeatAll** | routes converge, desert |
| 16 | Ruled by Madness | **Seize** (13,3) | **big battle** |
| 17 | River of Regrets | **DefeatBoss** | approach to finale |
| 18 | Two Faces of Evil | **DefeatAll** (18a) | penultimate set-up |
| 19 | Last Hope | **DefeatBoss** | **big battle** (gauntlet) |
| 20 | Darkling Woods | **Seize** (11,11) | final dungeon approach |
| Final | Sacred Stone | **DefeatBoss** (Formortiis) | final boss |

**Cadence takeaways (the rules to copy):**
- **Roughly every 3rd map is a "big battle"** (boss or siege); the maps between
  are breathers, escorts, terrain gimmicks, or story pivots. Never two grind-y
  routs back to back.
- **A tone shift early** (FE8 Ch 4: monsters appear) re-frames the stakes after
  the human-scale opening.
- **A reversal / low point in the back third** (FE8's gauntlet into Darkling
  Woods).
- **Optional dungeons** (Tower of Valni, Lagdou Ruins) exist *outside* the
  chapter count for grinding + reward farming — see §4.

---

## 1b. Vanilla field counts — deploy slots per chapter [decomp]

Drives each chapter YAML's `deploy_limit` (decisions.md §Field parity): our chapter N
fields what vanilla chapter N fields, on both sides. Player slot counts read from the
ally `UnitDefinition` array sizes in `fireemblem8u/src/events_udefs.s`
(`.size UnitDef_Event_<Ch>Ally / 20` minus the terminator); enemy counts are decoded
per-chapter from the event scripts/ROM as each chapter's slice begins (Ch1's full
table is below; the method is `git show HEAD:src/events/<ch>-eventudefs.h` for
decompiled chapters, `baserom.gba` struct reads for the rest).

| FE8 ch | Player slots | Notes |
|---|---|---|
| Prologue | 2 | Eirika + Seth, fixed |
| 1 | 2 + 2 ally arrivals = **4** | Franz/Gilliam arrive turn 2 |
| 2 | 5 | |
| 3 | 9 | |
| 4 | 9 | |
| 5 | 9 | |
| 5x | 4 | fixed cast (Ephraim gaiden) |
| 6 | 10 | |
| 7 | 10 | |
| 8 | 9 | |
| 9a | 11 | |
| 10a | 12 | |
| 11a | 11 | |
| 12a–14a | 12 | |

**Vanilla Ch1 "Escape!" full field table** (from `git show HEAD:src/events/ch1-eventudefs.h`):
- Player: Eirika (lord, Rapier) + Seth start; Franz + Gilliam ally reinforcements.
- Enemies, initial 7: Breguet (Armor Knight **lv4**, iron lance, holds the Seize
  gate, AI `{0x3,0x3,0x9,0x20}` attack-in-place/never-move) + 3 Soldiers lv1
  (iron lances) + 3 Fighters lv1 (iron axes), all autoleveled.
- Enemy reinforcements: +3 (2 Fighters, 1 Soldier), spawning on the player-start
  side of the map.
- No archers, no chests, no gimmicks; objective Seize, lose = Eirika falls.

---

## 2. Promotion items: what promotes what [decomp]

Verified against `src/data_itemuse.c` (FE8 class IDs) + `texts/texts.txt`. Our
PC→FE8-class mapping is in `docs/CLASSES.md`; how we gate promotions (the
seam) is in `docs/decisions.md`.

| FE8 item | Promotes (FE8 classes) |
|---|---|
| **Hero Crest** | Mercenary, Myrmidon, Fighter |
| **Knight Crest** | Cavalier, Knight (Armor) |
| **Orion's Bolt** | Archer |
| **Elysian Whip** | Pegasus Knight, Wyvern Rider |
| **Guiding Ring** | Mage, Monk, Cleric, Shaman, Troubadour |
| **Master Seal** | **any** promotable class [FE8] |
| **Ocean Seal** | Pirate, (Thief) |
| **Hammerne** | *(staff, not a seal — repairs items)* |
| **Lunar/Solar Brace** | story-only lord promotion [FE8] |

> **FE8 design note.** The **Master Seal promotes any promotable class**, while the
> specific crests each gate a narrow class set. That makes the Master Seal the
> low-friction universal mechanism; specific crests are most useful as *flavored*
> early single-unit promotions. (Our application of this is in `decisions.md` — the
> promotion seam.)

---

## 3. When FE8 hands out rewards [FE8]

The schedule, by era (not exact chapter — see sourcing note):

- **Early (FE8 Prologue–7):** consumables, gold, basic weapons, the occasional
  stat booster in a chest/village. **No promotion items.** Vulnerary, small gold
  purses, a Steel/secondary weapon, the first stat-booster (e.g. an Energy Ring)
  as a "reward chest" payoff. Villages give gold or a single nice item.
- **Route-split era (FE8 9–13):** **first promotion items appear** (Knight Crest,
  Hero Crest, Guiding Ring), more stat boosters, better weapons (Silver tier),
  first **Master Seal**. Secret Shops begin selling premium goods.
- **Late (FE8 14–20):** Master Seals become reliably available (Secret Shops),
  legendary/Sacred weapons appear as chest/boss drops, big gold.
- **Story-gated:** the lord's Lunar/Solar Brace promotion lands ~FE8 15–16.

**Villages, chests, secret shops, droppers:**
- **Villages**: visit for gold or one item; a thief/brigand may destroy them
  (turn pressure).
- **Chests**: need a thief or a Door/Chest Key. Big-battle maps usually hide the
  best treasure behind enemy lines — risk/reward.
- **Secret Shops**: require a Member Card; sell premium consumables + Master
  Seals. Gated mid-game.
- **Boss drops**: bosses frequently carry their weapon or a promotion item as a
  guaranteed drop — diegetic reward placement.

---

## 4. Optional dungeons (outside the chapter count) [FE8]

- **Tower of Valni** — opens ~after FE8 Ch 8; repeatable; for grinding XP and
  buying/farming promotion items + boosters.
- **Lagdou Ruins** — postgame, deep, high-tier rewards.

(Whether Manchego Stars adds a repeatable arctic Valni-equivalent is an open
post-MVP question — see `docs/roadmap.md`.)

---

## Open Items / deferred grounding

- [ ] **Pin exact promotion-item chapters** by reading FE8 event scripts in the
  decomp (`fireemblem8u/` event data) rather than community memory — upgrade the
  §3 era-buckets to exact chapters. Deferred (event-script archaeology); current
  numbers are [FE8]-tier.
