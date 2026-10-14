# Manchego Stars — Campaign Roadmap (ch09–ch20)

> **Where the plan lives.** Every chapter, built or planned, is a YAML file in
> `campaigns/rime-of-the-frostmaiden/chapters/`. The back half (ch09–ch20) are
> `status: planned` stubs from the #486 planning pass: each one's story job, curve twin,
> map donor, the vanilla payload it owes, the recruit roles it fills, sources, and its own
> `open_questions`. **Read them through the wiki**: `python3 tools/gen_wiki.py` writes
> `build/wiki/index.html`, one page per chapter laid out like the Fire Emblem Wiki, with
> the twin's payload read from the decomp and checked against ours, and every open
> question gathered on one page. This file keeps only what has no chapter to live in.
>
> Settled design lives in `docs/decisions.md`; the FE8 cadence rules in
> `docs/fe8-pacing-reference.md`.

**The arc (Nicolas, 2026-10-12):** one conspiracy revealed in layers, FE8's shape. From
Messie's farewell the goal is to end the Rime. Each act's summary is `campaign.yaml` →
`acts:`, and each chapter names its own `act:`; the wiki's home page reads both. Twenty
chapters: the race to the glacier takes the Darkling Woods slot, and the finale is the
two-part Final.

---

## Recruit cadence (by role) 🧩

> **Method (Nicolas, 2026-06-20):** class is the *chassis* (move/weapon/stat shape); the
> character is custom art on top ("custom art is the lever"). Each chapter **fields a vanilla-sized
> force** via `deploy_limit`, and Pick Units chooses who takes it.
>
> **How many, and when (ADR 0342, #459):** the roster keeps **vanilla's recruit cadence** on
> Eirika's route: the same number of bodies by the same chapter, each filling the role of a vanilla
> recruit we are missing, at a level fit for the chapter it joins. No Jagen (ADR 0042). Per-unit
> detail lives in `campaigns/.../{pcs,npcs}/*.yaml`; this is the schedule overview.

| Joins | Character | Chassis (FE class) | Vanilla role it fills | Skin |
|---|---|---|---|---|
| ch01 | 8 PCs | — | the core: Garcia, Gilliam, Neimi, Lute, Moulder, Vanessa + two Knolls | — |
| ch02 | **Baxby** | Cavalier | Franz | axe-beak |
| ch03 | **Trex** | Thief | Colm | winged kobold |
| ch05 | **Lupin** | Cavalier | Kyle (early) | direwolf (the wolf *is* the mount) |
| ch05 | **Sahnar** | Myrmidon | Joshua | moon-elf mummy |
| ch05 | **Basil** | Cleric | Natasha | goodberry shrub |
| ch07 end | **Meriwa** | Monk | Artur (light magic) | merfolk (Stephano's Mermaid) |
| ch07 end | **Esio Trot** | Fighter | Ross (second axe) | tortle in a pope's mitre, with an axe |
| ch08 start | **The White Moose** | Cavalier | Forde | the ch04–05 moose, freed when Ravisin dies |
| ch09 | a griffon rider *(direction)* | Pegasus Knight | Tana | griffon (Skytower Shelter, *Rime* pp.163, 198) |

That is 16 fielded in ch08 against vanilla's 17; the one short is Ephraim, who leaves after Ch8 on
Eirika's route. From ch09–10, vanilla's talk-recruit cluster (Amelia; Gerik, Innes, Marisa, Tethys)
sets the next bodies, decided chapter by chapter.

**RBG's ballistae (Pepperjack & Brie) — NOT roster recruits.** They are vanilla FE8 **map
ballistae** (siege emplacements the party mans), flavored as RBG's cannon-constructs — we don't
break from vanilla to make ballistae into units. They appear on relevant maps from the **vanilla
ballista era: FE8 Ch10 "Revolt at Carcino" → our ~Ch10 onward**. No recruit slot, no `deploy_limit`
cost. (`npcs/pepperjack.yaml`, `npcs/brie.yaml`.)

**Open items on the recruit plan:**
- **Vellynne Harpell → stays an NPC.** Recurring self-interested ally / quest + shop, not a roster unit.
- **Back half (ch10–21)** recruits follow vanilla's cadence table on #459; who fills each body is
  decided per chapter. The Arcane Brotherhood wizards (Nass, Avarice, Dzaan) are rivals and possible
  redeemed-late recruits; the goliath imprisoned in Sunblight (*Rime* p.12) is a ready-made rescue.

## Open questions

Every open question sits on its chapter as `open_questions`, and the wiki's **Open
decisions** page lists them all with Claude's pick. Settled since this file's first draft:
the lord is whoever the player crowns (ADR 0062), and each PC gets a planned legendary
weapon, handed out where vanilla hands out its own (Nicolas, 2026-10-13).

## Cross-references

- `docs/CHAPTERS.md` — the generated chapter index.
- `tools/gen_wiki.py` — the chapter wiki (`build/wiki/index.html`).
- `docs/decisions.md` — settled design.
- `docs/fe8-pacing-reference.md` — FE8 cadence/reward rules.
- Sources for the plan: the DM notes, the book OCR, the Eventyr DM bundle text, the FE8
  players guide OCR, and a local mirror of the Fire Emblem Wiki's FE8 chapter pages, all in
  `References/` (`rime-dm-bundle-eventyr.txt`, `fe8-players-guide-ocr.txt`, `fe8-wiki/`).
