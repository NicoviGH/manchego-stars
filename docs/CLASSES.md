# Manchego Stars — Unit Roster & Class Index

<!-- GENERATED FILE — do not edit by hand.
     Source:     campaigns/rime-of-the-frostmaiden/{pcs,npcs}/*.yaml
     Regenerate: python3 tools/gen_class_index.py
     Class/promotion facts live in the unit YAML; this table is derived from it. -->

Every unit is a **stock vanilla FE8 class** (bases/growths/caps verbatim from
`fireemblem8u/src/data_classes.c`); D&D is flavor only. The *rationale* for each
mapping and the promotion seam live in `docs/decisions.md` — this is just the
roster derived from the unit YAML.

## Player characters

| PC | D&D source | FE base | Promotion (player picks; **default** bold) |
|---|---|---|---|
| Braulo | Barbarian (Path of the Berserker) — Hermit Crab | Pirate | **Berserker** / Warrior |
| Marty the Merry Mushroom | Druid (Circle of Spores) — Sporemaster | Shaman | **Druid** / Summoner |
| Meesmickle | Warlock (The Fiend) — Vampire Tabaxi | Shaman | **Summoner** / Druid |
| Prof. R.B. Geenius | Artificer (Artillerist) — Underfolk | Archer | **Sniper** / Ranger |
| Rootis | Sorcerer (Draconic Bloodline) — Snowperson | Mage (Ice) | **Sage** / Mage Knight |
| Sclorbo | Bard (College of Lore) — Chwinga | Priest | **Bishop** / Sage |
| Wolfram | Metallurgist (School of the Smith) — Mineralscale Drakeborn | Knight | **General** / Great Knight |

## Recruits & NPCs

| Unit | FE base | Promotion | Joins via |
|---|---|---|---|
| Baxby | Cavalier | **Paladin** / Great Knight | — |
| Brie | TBD (post-MVP) | — | story — Prof. R.B. Geenius builds Brie (a later chapter) |
| Pepperjack | TBD (post-MVP) | — | story — Prof. R.B. Geenius builds Pepperjack |
| Pinky | Pegasus Knight | **Falcon Knight** / Wyvern Knight | available from Chapter 1 |

> **Note.** `pepperjack`/`brie` carry `fe_stats.class: null` — their FE-legal
> class is a deliberate post-MVP TBD. Other recruits referenced in the chapters
> (Baxby, Trex, Sahnar, Lupin, Basil) do not yet have unit YAML; see the chapter
> files and `docs/CHAPTERS.md` for where they join.
