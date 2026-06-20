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
| Basil | Priest | **Bishop** / Sage | story — repotted from the Elven Tomb (Ch5) |
| Baxby | Cavalier | **Paladin** / Great Knight | — |
| Brie | TBD (post-MVP) | — | not a recruit — vanilla map ballista (RBG's siege), from ~Ch10 |
| Lupin | Cavalier | **Paladin** / Great Knight | story — Marty talks the direwolf pack into the sled team (Ch4) |
| Pepperjack | TBD (post-MVP) | — | not a recruit — vanilla map ballista (RBG's siege), from ~Ch10 |
| Pinky | Pegasus Knight | **Falcon Knight** / Wyvern Knight | available from Chapter 1 |
| Sahnar | Myrmidon | **Swordmaster** / Assassin | story — freed from the sarcophagus in the Elven Tomb (Ch5) |
| Trex | Thief | **Rogue** / Assassin | story — joins after the Termalaine mine (Ch3) |

> **Note.** `pepperjack`/`brie` carry `fe_stats.class: null` because they are NOT
> roster recruits — they are vanilla FE8 **map ballistae** (siege emplacements the
> party mans), flavored as RBG's cannon-constructs, appearing from the vanilla
> ballista era (~Ch10). Recruit class/role for Trex, Sahnar, Lupin, Basil is LOCKED
> in their unit YAML (full bases/growths authored at wiring); `docs/CHAPTERS.md`
> shows where each joins.
