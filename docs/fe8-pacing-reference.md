# FE8 Pacing & Reward Reference

> **Purpose.** Ground Manchego Stars' 20-chapter cadence, treasure flow, and
> promotion-item placement against *Fire Emblem: The Sacred Stones* (FE8) — the
> spine of this hack (see [[feedback_fe-strictness]] / `docs/decisions.md`).
> The 20-chapter skeleton (`docs/chapter-outline.md`) is built **against this
> reference** so our cadence "feels like FE8" instead of like a D&D module cut
> into arbitrary slices.
>
> **Sourcing honesty.** Two confidence tiers are used below:
> - **[decomp]** — verified against `fireemblem8u/` this session (item names in
>   `texts/texts.txt`; class→promotion mappings in `src/data_itemuse.c`).
> - **[FE8]** — well-established FE8 community knowledge (chapter order, the
>   *chapter* each reward first appears). Pinning each item to an exact chapter
>   via the decomp's event scripts is deferred (see Open Items); treat the
>   chapter numbers as "early-teens, route-split era," not gospel ±1 chapter.

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

**Cadence takeaways for us:**
- **Roughly every 3rd map is a "big battle"** (boss or siege); the maps between
  are breathers, escorts, terrain gimmicks, or story pivots. Never two grind-y
  routs back to back.
- **A tone shift early** (FE8 Ch 4: monsters appear) re-frames the stakes after
  the human-scale opening. We already have an analogue: Ch 3's Grells / Ch 4's
  frost druid escalate past goblins-and-bandits.
- **A reversal / low point in the back third** (FE8's gauntlet into Darkling
  Woods). Our Revel's End cliffhanger at Ch 7 is *exactly* this beat, landed
  early as the MVP wall.
- **Optional dungeons** (Tower of Valni, Lagdou Ruins) exist *outside* the
  chapter count for grinding + reward farming — see §4.

---

## 2. Promotion items: what promotes what [decomp]

Verified against `src/data_itemuse.c` (FE8 class IDs) + `texts/texts.txt`.
Mapped to our D&D classes via `docs/class-mapping.md`.

| FE8 item | Promotes (FE8 classes) | Our PCs it would gate |
|---|---|---|
| **Hero Crest** | Mercenary, Myrmidon, Fighter | melee martials — Braulo (Barbarian), Marty (melee) |
| **Knight Crest** | Cavalier, Knight (Armor) | armored/mounted — Rootis (tank) |
| **Orion's Bolt** | Archer | ranged martials (if any reclass) |
| **Elysian Whip** | Pegasus Knight, Wyvern Rider | flyers (none core; NPC use) |
| **Guiding Ring** | Mage, Monk, Cleric, Shaman, Troubadour | casters — Meesmickle, Wolfram, Prof. RBG, Sclorbo |
| **Master Seal** | **any** promotable class [FE8] | universal fallback for all 7 |
| **Ocean Seal** | Pirate, (Thief) | n/a unless a PC reclasses |
| **Hammerne** | *(staff, not a seal — repairs items)* | utility; see §3 treasure |
| **Lunar/Solar Brace** | story-only lord promotion [FE8] | reserved for a "main" PC if we crown one |

> **Design note.** Since all 7 PCs promote post-MVP (memory:
> [[manchego-stars-campaign-structure]] — ≈Ch 9–11), the **Master Seal is the
> clean universal mechanism** and avoids the class-matching headache of the
> specific crests. Specific crests can still appear as *flavored* early finds
> (a duergar smith's "Knight Crest", a frost-druid relic "Guiding Ring") for
> players who want to promote one unit a chapter early.

---

## 3. When FE8 hands out rewards [FE8]

The schedule, by era (not exact chapter — see sourcing note):

- **Early (FE8 Pro–7 ≈ our MVP Ch 1–7):** consumables, gold, basic weapons,
  the occasional stat booster in a chest/village. **No promotion items.** Vulnerary,
  small gold purses, a Steel/secondary weapon, the first stat-booster (e.g. an
  Energy Ring) as a "reward chest" payoff. Villages give gold or a single nice item.
- **Route-split era (FE8 9–13 ≈ our Ch 9–13):** **first promotion items appear**
  (Knight Crest, Hero Crest, Guiding Ring), more stat boosters, better weapons
  (Silver tier), first **Master Seal**. Secret Shops begin selling premium goods.
- **Late (FE8 14–20 ≈ our Ch 14–20):** Master Seals become reliably available
  (Secret Shops), legendary/Sacred weapons appear as chest/boss drops, big gold.
- **Story-gated:** the lord's Lunar/Solar Brace promotion lands ~FE8 15–16.

**Villages, chests, secret shops, droppers:**
- **Villages**: visit for gold or one item; a thief/brigand may destroy them
  (turn pressure). Our "town" maps (Bremen Ch 6, the Ten-Towns) are natural
  village-equivalents.
- **Chests**: need a thief or a Door/Chest Key. Big-battle maps usually hide the
  best treasure behind enemy lines — risk/reward.
- **Secret Shops**: require a Member Card; sell premium consumables + Master
  Seals. Gated mid-game.
- **Boss drops**: bosses frequently carry their weapon or a promotion item as a
  guaranteed drop — diegetic reward placement.

---

## 4. Optional dungeons (outside the chapter count) [FE8]

- **Tower of Valni** — opens ~after FE8 Ch 8; repeatable; for grinding XP and
  buying/farming promotion items + boosters. Our arctic theme already borrows the
  Valni tileset (`docs/PRD.md §8`).
- **Lagdou Ruins** — postgame, deep, high-tier rewards.

> **Our stance:** MVP (Ch 1–7) ships **without** an optional dungeon (scope).
> A Valni-equivalent "repeatable arctic ruin" is a strong **post-MVP** add when
> promotions go live (Ch 9–11) — it solves grind-for-promotion without
> bloating the mainline chapter count. Flag for the Ch 8–20 design pass.

---

## 5. How this maps onto Manchego Stars

- **Cadence:** apply the "every-3rd-map is a big battle" rule across all 20
  chapters; keep the MVP front-loaded with breathers/tutorials (Ch 1–2) and one
  real boss (Ch 4 frost druid) + a marquee set-piece (Ch 5 Messie) before the
  Ch 7 reversal. See `docs/chapter-outline.md` for the per-chapter tags.
- **Promotion seam:** **no promotion items in MVP Ch 1–7.** The **first
  Master-Seal-equivalent** lands at the **Ch 7→8 seam** (diegetically: looted at
  Revel's End or earned in the prison-break chapter), and should be **foreshadowed
  in MVP** (an NPC line, a locked "relic" chest the party can't yet use). This
  matches FE8 holding promotions until the route-split era and honors
  [[manchego-stars-campaign-structure]] (promotions ≈ Ch 9–11, PCs play MVP
  entirely unpromoted).
- **Reward curve in MVP:** consumables + gold + one stat-booster reward chest;
  weapons stay Iron/Steel-tier; the "wow" treasure is a flavored relic that
  *foreshadows* post-MVP power rather than granting it early.

---

## Open Items / deferred grounding

- [ ] **Pin exact promotion-item chapters** by reading FE8 event scripts in the
  decomp (`fireemblem8u/` event data) rather than community memory — upgrade the
  §3 era-buckets to exact chapters. Deferred this session (event-script
  archaeology); current numbers are [FE8]-tier.
- [ ] Confirm whether we crown a "main lord" PC (enables the Lunar/Solar Brace
  story-promotion beat) or keep the party flat (all promote via Master Seal).
  Affects Ch 15–16 design. Surfaced to Nicolas.
- [ ] Decide the post-MVP Tower-of-Valni-equivalent (repeatable arctic ruin).
