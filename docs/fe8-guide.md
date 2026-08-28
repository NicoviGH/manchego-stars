# FE8 chapter guide — parity and playstyle reference

**Generated** by `tools/fe8_guide_mine.py`. Do not hand-edit; re-run the tool.

Source: **Fire Emblem Wiki** (<https://fireemblemwiki.org>), the independent wiki. Credited in `CREDITS.md`.

**Vanilla FE8 only.** This is the *how is it played* half of parity — the decomp already answers *what it contains*. Facts about OUR chapters live in `campaigns/<id>/chapters/*.yaml`; never source a claim about our design from here.

Enemy counts are **Normal** unless noted. In FE8 the difficulty dial is a *level shift* (`chapter_settings`: easyMalus/normalMalus/difficultBonus), not a different force — so a tier that adds or removes UNITS is a real design signal and is called out.

**Shape / Pressure / Teaches** digest each chapter's Strategy section into design vocabulary, from `docs/fe8-guide-glosses.json`. The index below is the donor-selection view.

---

## Donor-selection index

| Chapter | Objective | Enemies (N) | Shape | Pressure comes from |
|---|---|---|---|---|
| [Prologue](#prologue) | Defeat O'Neill | 3 | — | — |
| [Chapter 1](#chapter-1) | Seize the castle | 10 | Tutorial seize with a rearward ambush | A midline tripwire — crossing it drops 2 Fighters and a Soldier on your own start tile |
| [Chapter 2](#chapter-2) | Defeat all bandits | 8 | — | — |
| [Chapter 3](#chapter-3) | Seize the throne | 10 | — | — |
| [Chapter 4](#chapter-4) | Defeat all monsters | 22 | — | — |
| [Chapter 5](#chapter-5) | Defeat Saar | 23 | — | — |
| [Chapter 5x](#chapter-5x) | Seize the throne | 31 | — | — |
| [Chapter 6](#chapter-6) | Defeat Novala | 24 | Rescue on a clock, run blind under fog | Fog — the guide says it is the ONLY thing making the map hard — plus a 7-turn hostage timer, and Hard-only turn-4 cavalry spawning behind you |
| [Chapter 7](#chapter-7) | Seize the gate | 19 | Seize across open ground, past fixed ranged emplacements | Ballistae covering the approach — a positional hazard you route around rather than fight, and lethal to fliers |
| [Chapter 8](#chapter-8) | Seize the throne | 33 | — | — |
| [Chapter 9 (Eirika)](#chapter-9-eirika) | Defeat all enemies | 38 | — | — |
| [Chapter 10 (Eirika)](#chapter-10-eirika) | Seize the gate | 51 | — | — |
| [Chapter 11 (Eirika)](#chapter-11-eirika) | Defeat all enemies | 42 | — | — |
| [Chapter 12 (Eirika)](#chapter-12-eirika) | Defeat all enemies | 44 | — | — |
| [Chapter 13 (Eirika)](#chapter-13-eirika) | Survive 11 turns or defeat Aias | 58 | — | — |
| [Chapter 14 (Eirika)](#chapter-14-eirika) | Seize the throne | 68 | — | — |
| [Chapter 9 (Ephraim)](#chapter-9-ephraim) | Seize the throne | 46 | — | — |
| [Chapter 10 (Ephraim)](#chapter-10-ephraim) | Protect Duessel for 10 turns or defeat Beran | 43 | — | — |
| [Chapter 11 (Ephraim)](#chapter-11-ephraim) | Defeat all enemies | 48 | — | — |
| [Chapter 12 (Ephraim)](#chapter-12-ephraim) | Defeat boss | 51 | — | — |
| [Chapter 13 (Ephraim)](#chapter-13-ephraim) | Defeat all enemies | 58 | — | — |
| [Chapter 14 (Ephraim)](#chapter-14-ephraim) | Seize the throne | 71 | — | — |
| [Chapter 15](#chapter-15) | Defeat all enemies | 77 | — | — |
| [Chapter 16](#chapter-16) | Seize the throne | 41 | — | — |
| [Chapter 17](#chapter-17) | Defeat Lyon | 64 | — | — |
| [Chapter 18](#chapter-18) | Defeat all enemies | 46 | — | — |
| [Chapter 19](#chapter-19) | Protect Mansel for 13 turns or defeat Riev | 97 | — | — |
| [Chapter 20](#chapter-20) | Seize the gate | 122 | — | — |

---

## Prologue

- **Objective**: Defeat O'Neill  ·  **Lose**: Eirika dies
- **Difficult**: 3 enemies · avg L2.3 — 3× Fighter
- **Playstyle**: *not yet digested — `tools/fe8_guide_mine.py --strategy prologue`*

## Chapter 1

- **Objective**: Seize the castle  ·  **Lose**: Eirika dies
- **Difficult**: 10 enemies · avg L2.1 — 5× Fighter, 4× Soldier, 1× Knight
- **Shape**: Tutorial seize with a rearward ambush
- **Pressure**: A midline tripwire — crossing it drops 2 Fighters and a Soldier on your own start tile
- **Teaches**: Trading weapons between units; allied reinforcements arriving on green tiles; effective weapons (the rapier against an armoured boss)
- **Playstyle**: Barely harder than the prologue. Hand Seth's sword to Eirika first so the rapier is not wasted on ordinary infantry. Franz and Gilliam arrive turn 2 on the green tiles. Feed Eirika the Fighters and Franz or Gilliam the Soldiers if you intend to keep using them. The one trap: crossing the map's midline spawns two Fighters and a Soldier back where Seth and Eirika started, so do not leave your rear empty. Breguet is a Knight with Def 9 and Res 0 — the rapier cuts him, or lances do it the slow way. 5,000 gold on completion.

## Chapter 2

- **Objective**: Defeat all bandits  ·  **Lose**: Eirika dies
- **Easy**: 8 enemies · avg L2.6 — 7× Brigand, 1× Archer
- **Normal**: 8 enemies · avg L2.6 — 7× Brigand, 1× Archer
- **Difficult**: 8 enemies · avg L2.6 — 7× Brigand, 1× Archer
- **Playstyle**: *not yet digested — `tools/fe8_guide_mine.py --strategy ch2`*

## Chapter 3

- **Objective**: Seize the throne  ·  **Lose**: Eirika dies
- **Easy**: 10 enemies · avg L3.4 — 7× Brigand, 1× Mercenary, 1× Archer, 1× Thief
- **Normal**: 10 enemies · avg L3.4 — 7× Brigand, 1× Mercenary, 1× Archer, 1× Thief
- **Difficult**: 10 enemies · avg L3.4 — 7× Brigand, 1× Mercenary, 1× Archer, 1× Thief
- **Playstyle**: *not yet digested — `tools/fe8_guide_mine.py --strategy ch3`*

## Chapter 4

- **Objective**: Defeat all monsters  ·  **Lose**: Eirika dies
- **Deploy**: 2–9
- **Difficult**: 22 enemies · avg L1.8 — 12× Revenant, 6× Bonewalker, 3× Mogall, 1× Entombed
- **Playstyle**: *not yet digested — `tools/fe8_guide_mine.py --strategy ch4`*

## Chapter 5

- **Objective**: Defeat Saar  ·  **Lose**: Eirika dies
- **Deploy**: 2–9
- **Easy**: 23 enemies · avg L5.2 — 6× Soldier, 6× Brigand, 5× Fighter, 3× Archer, 1× Knight, 1× Mercenary
- **Normal**: 23 enemies · avg L5.2 — 6× Soldier, 6× Brigand, 5× Fighter, 3× Archer, 1× Knight, 1× Mercenary
- **Difficult**: 23 enemies · avg L5.2 — 6× Soldier, 6× Brigand, 5× Fighter, 3× Archer, 1× Knight, 1× Mercenary
- **Playstyle**: *not yet digested — `tools/fe8_guide_mine.py --strategy ch5`*

## Chapter 5x

- **Objective**: Seize the throne  ·  **Lose**: Ephraim dies
- **Easy**: 31 enemies · avg L4.5 — 9× Soldier, 5× Fighter, 4× Archer, 3× Knight, 3× Cavalier, 2× Mercenary
- **Normal**: 31 enemies · avg L4.5 — 9× Soldier, 5× Fighter, 4× Archer, 3× Knight, 3× Cavalier, 2× Mercenary
- **Difficult**: 31 enemies · avg L4.5 — 9× Soldier, 5× Fighter, 4× Archer, 3× Knight, 3× Cavalier, 2× Mercenary
- **Playstyle**: *not yet digested — `tools/fe8_guide_mine.py --strategy ch5x`*

## Chapter 6

- **Objective**: Defeat Novala  ·  **Lose**: Eirika dies
- **Deploy**: 1–10
- **Easy**: 24 enemies · avg L6.2 — 6× Soldier, 3× Fighter, 3× Knight, 3× Cavalier, 2× Mercenary, 2× Shaman
- **Normal**: 24 enemies · avg L6.2 — 6× Soldier, 3× Fighter, 3× Knight, 3× Cavalier, 2× Mercenary, 2× Shaman
- **Difficult**: 27 enemies · avg L6.2 — 6× Soldier, 6× Cavalier, 3× Fighter, 3× Knight, 2× Mercenary, 2× Shaman
- **Hard-mode delta**: {'Cavalier': 3} — a UNIT change, not just a level shift
- **Shape**: Rescue on a clock, run blind under fog
- **Pressure**: Fog — the guide says it is the ONLY thing making the map hard — plus a 7-turn hostage timer, and Hard-only turn-4 cavalry spawning behind you
- **Teaches**: Fog of war; enemies that heal; magic and poison at scale; effective weapons aimed at the player
- **Playstyle**: The fog is the entire difficulty; strip it out and this is a walkover. Vision is a purchase, not a stat — buy torches from the PREVIOUS chapter's shop and lead with the thief for his sight radius. Then it is a race: Novala is holding hostages, reach them in under 7 turns with a flier, and the guide advises sending her from turn 1 to be safe. Saving all of them pays an Orion's Bolt, the biggest reward on the map. Only then go for the boss, who is a Shaman with Def 5 — 'a very easy boss, throw physical units at him'. Tank with your one overpowered unit, park in the forests on the right to evade, and watch your rear for the Hard-mode cavalry.

## Chapter 7

- **Objective**: Seize the gate  ·  **Lose**: Eirika dies
- **Deploy**: 1–10
- **Easy**: 19 enemies · avg L7.3 — 5× Fighter, 4× Soldier, 4× Archer, 3× Mage, 2× Mercenary, 1× Cavalier
- **Normal**: 19 enemies · avg L7.3 — 5× Fighter, 4× Soldier, 4× Archer, 3× Mage, 2× Mercenary, 1× Cavalier
- **Difficult**: 19 enemies · avg L7.3 — 5× Fighter, 4× Soldier, 4× Archer, 3× Mage, 2× Mercenary, 1× Cavalier
- **Shape**: Seize across open ground, past fixed ranged emplacements
- **Pressure**: Ballistae covering the approach — a positional hazard you route around rather than fight, and lethal to fliers
- **Teaches**: Ballistae; stealing
- **Playstyle**: A simple map by the guide's own account: beat the boss, take the castle. The single real hazard is the ballistae — keep fliers entirely outside their range, or walk an armour knight into it deliberately to break the machine. Bring the thief; there is an Energy Ring to steal. Push south behind a defensive front line. Murray is another pushover and can be safely chipped from range.

## Chapter 8

- **Objective**: Seize the throne  ·  **Lose**: Eirika or Ephraim dies
- **Deploy**: 1–9
- **Easy**: 33 enemies · avg L7.2 — 9× Knight, 6× Soldier, 5× Archer, 3× Mage, 3× Cavalier, 2× Mercenary
- **Normal**: 33 enemies · avg L7.2 — 9× Knight, 6× Soldier, 5× Archer, 3× Mage, 3× Cavalier, 2× Mercenary
- **Difficult**: 38 enemies · avg L7.2 — 9× Knight, 6× Soldier, 5× Archer, 5× Mage, 3× Mercenary, 3× Shaman
- **Hard-mode delta**: {'Mercenary': 1, 'Shaman': 1, 'Mage': 2, 'Fighter': 1} — a UNIT change, not just a level shift
- **Playstyle**: *not yet digested — `tools/fe8_guide_mine.py --strategy ch8`*

## Chapter 9 (Eirika)

- **Objective**: Defeat all enemies  ·  **Lose**: Eirika dies
- **Deploy**: 2–11
- **Easy**: 38 enemies · avg L8.1 — 10× Mercenary, 8× Soldier, 5× Archer, 4× Fighter, 3× Pirate, 3× Mage
- **Normal**: 38 enemies · avg L8.1 — 10× Mercenary, 8× Soldier, 5× Archer, 4× Fighter, 3× Pirate, 3× Mage
- **Difficult**: 46 enemies · avg L8.3 — 10× Mercenary, 8× Soldier, 7× Archer, 7× Pirate, 6× Fighter, 3× Mage
- **Hard-mode delta**: {'Fighter': 2, 'Archer': 2, 'Pirate': 4} — a UNIT change, not just a level shift
- **Playstyle**: *not yet digested — `tools/fe8_guide_mine.py --strategy eirika9`*

## Chapter 10 (Eirika)

- **Objective**: Seize the gate  ·  **Lose**: Eirika dies
- **Deploy**: 1–12
- **Easy**: 51 enemies · avg L9.5 — 11× Brigand, 8× Myrmidon, 7× Soldier, 5× Mercenary, 4× Archer, 4× Pegasus Knight
- **Normal**: 51 enemies · avg L9.5 — 11× Brigand, 8× Myrmidon, 7× Soldier, 5× Mercenary, 4× Archer, 4× Pegasus Knight
- **Difficult**: 60 enemies · avg L9.6 — 11× Brigand, 8× Soldier, 8× Myrmidon, 7× Mercenary, 7× Pegasus Knight, 6× Archer
- **Hard-mode delta**: {'Archer': 2, 'Soldier': 1, 'Mercenary': 2, 'Fighter': 1, 'Pegasus Knight': 3} — a UNIT change, not just a level shift
- **Playstyle**: *not yet digested — `tools/fe8_guide_mine.py --strategy eirika10`*

## Chapter 11 (Eirika)

- **Objective**: Defeat all enemies  ·  **Lose**: Eirika dies
- **Easy**: 42 enemies · avg L8.6 — 24× Bonewalker, 4× Revenant, 4× Mogall, 4× Gargoyle, 3× Mauthe Doog, 1× Entombed
- **Normal**: 42 enemies · avg L8.6 — 24× Bonewalker, 4× Revenant, 4× Mogall, 4× Gargoyle, 3× Mauthe Doog, 1× Entombed
- **Difficult**: 54 enemies · avg L8.9 — 30× Bonewalker, 10× Revenant, 4× Mogall, 4× Gargoyle, 3× Mauthe Doog, 1× Entombed
- **Hard-mode delta**: {'Revenant': 6, 'Bonewalker': 6} — a UNIT change, not just a level shift
- **Playstyle**: *not yet digested — `tools/fe8_guide_mine.py --strategy eirika11`*

## Chapter 12 (Eirika)

- **Objective**: Defeat all enemies  ·  **Lose**: Eirika dies
- **Easy**: 44 enemies · avg L9.1 — 15× Gargoyle, 8× Bael, 8× Mauthe Doog, 4× Mogall, 3× Revenant, 2× Bonewalker
- **Normal**: 44 enemies · avg L9.1 — 15× Gargoyle, 8× Bael, 8× Mauthe Doog, 4× Mogall, 3× Revenant, 2× Bonewalker
- **Difficult**: 53 enemies · avg L9.1 — 19× Gargoyle, 9× Mauthe Doog, 8× Bael, 5× Mogall, 5× Revenant, 3× Bonewalker
- **Hard-mode delta**: {'Gargoyle': 4, 'Mauthe Doog': 1, 'Mogall': 1, 'Bonewalker': 1, 'Revenant': 2} — a UNIT change, not just a level shift
- **Playstyle**: *not yet digested — `tools/fe8_guide_mine.py --strategy eirika12`*

## Chapter 13 (Eirika)

- **Objective**: Survive 11 turns or defeat Aias  ·  **Lose**: Eirika dies
- **Deploy**: 1–12
- **Easy**: 58 enemies · avg L10.8 — 19× Cavalier, 6× Mercenary, 4× Archer, 4× Knight, 4× Fighter, 4× Brigand
- **Normal**: 58 enemies · avg L10.8 — 19× Cavalier, 6× Mercenary, 4× Archer, 4× Knight, 4× Fighter, 4× Brigand
- **Difficult**: 66 enemies · avg L10.9 — 21× Cavalier, 7× Mercenary, 6× Archer, 6× Soldier, 4× Knight, 4× Fighter
- **Hard-mode delta**: {'Archer': 2, 'Cavalier': 2, 'Soldier': 3, 'Mercenary': 1} — a UNIT change, not just a level shift
- **Playstyle**: *not yet digested — `tools/fe8_guide_mine.py --strategy eirika13`*

## Chapter 14 (Eirika)

- **Objective**: Seize the throne  ·  **Lose**: Eirika dies
- **Deploy**: 1–12
- **Easy**: 68 enemies · avg L12.2 — 16× Knight, 12× Shaman, 9× Archer, 9× Cavalier, 7× Fighter, 4× Mercenary
- **Normal**: 68 enemies · avg L12.2 — 16× Knight, 12× Shaman, 9× Archer, 9× Cavalier, 7× Fighter, 4× Mercenary
- **Difficult**: 68 enemies · avg L12.2 — 16× Knight, 12× Shaman, 9× Archer, 9× Cavalier, 7× Fighter, 4× Mercenary
- **Playstyle**: *not yet digested — `tools/fe8_guide_mine.py --strategy eirika14`*

## Chapter 9 (Ephraim)

- **Objective**: Seize the throne  ·  **Lose**: Ephraim dies
- **Deploy**: 1–11
- **Easy**: 46 enemies · avg L8.8 — 12× Cavalier, 6× Archer, 6× Knight, 5× Soldier, 4× Mage, 4× Mercenary
- **Normal**: 46 enemies · avg L8.8 — 12× Cavalier, 6× Archer, 6× Knight, 5× Soldier, 4× Mage, 4× Mercenary
- **Difficult**: 59 enemies · avg L8.9 — 23× Cavalier, 6× Archer, 6× Knight, 5× Soldier, 4× Mage, 4× Mercenary
- **Hard-mode delta**: {'Cavalier': 11, 'Shaman': 2} — a UNIT change, not just a level shift
- **Playstyle**: *not yet digested — `tools/fe8_guide_mine.py --strategy ephraim9`*

## Chapter 10 (Ephraim)

- **Objective**: Protect Duessel for 10 turns or defeat Beran  ·  **Lose**: Ephraim or Duessel dies
- **Easy**: 43 enemies · avg L9.6 — 16× Mercenary, 7× Cavalier, 3× Pirate, 3× Fighter, 3× Wyvern Rider, 2× Soldier
- **Normal**: 43 enemies · avg L9.6 — 16× Mercenary, 7× Cavalier, 3× Pirate, 3× Fighter, 3× Wyvern Rider, 2× Soldier
- **Difficult**: 49 enemies · avg L9.6 — 16× Mercenary, 9× Cavalier, 6× Pirate, 4× Fighter, 3× Wyvern Rider, 2× Soldier
- **Hard-mode delta**: {'Pirate': 3, 'Cavalier': 2, 'Fighter': 1} — a UNIT change, not just a level shift
- **Playstyle**: *not yet digested — `tools/fe8_guide_mine.py --strategy ephraim10`*

## Chapter 11 (Ephraim)

- **Objective**: Defeat all enemies  ·  **Lose**: Ephraim dies
- **Deploy**: 1–11
- **Easy**: 48 enemies · avg L8.1 — 18× Bonewalker, 10× Mogall, 10× Gargoyle, 6× Revenant, 2× Entombed, 1× Wight
- **Normal**: 48 enemies · avg L8.1 — 18× Bonewalker, 10× Mogall, 10× Gargoyle, 6× Revenant, 2× Entombed, 1× Wight
- **Difficult**: 54 enemies · avg L8.2 — 18× Bonewalker, 14× Mogall, 12× Gargoyle, 6× Revenant, 2× Entombed, 1× Wight
- **Hard-mode delta**: {'Mogall': 4, 'Gargoyle': 2} — a UNIT change, not just a level shift
- **Playstyle**: *not yet digested — `tools/fe8_guide_mine.py --strategy ephraim11`*

## Chapter 12 (Ephraim)

- **Objective**: Defeat boss  ·  **Lose**: Ephraim dies
- **Deploy**: 1–12
- **Easy**: 51 enemies · avg L10.4 — 10× Shaman, 7× Cavalier, 5× Mage, 5× Bonewalker, 4× Fighter, 4× Archer
- **Normal**: 51 enemies · avg L10.4 — 10× Shaman, 7× Cavalier, 5× Mage, 5× Bonewalker, 4× Fighter, 4× Archer
- **Difficult**: 67 enemies · avg L10.3 — 11× Bonewalker, 10× Shaman, 8× Bael, 7× Cavalier, 6× Archer, 5× Mage
- **Hard-mode delta**: {'Archer': 2, 'Mercenary': 2, 'Bonewalker': 6, 'Bael': 6} — a UNIT change, not just a level shift
- **Playstyle**: *not yet digested — `tools/fe8_guide_mine.py --strategy ephraim12`*

## Chapter 13 (Ephraim)

- **Objective**: Defeat all enemies  ·  **Lose**: Ephraim dies
- **Easy**: 58 enemies · avg L11.5 — 20× Cavalier, 10× Pegasus Knight, 6× Fighter, 3× Archer, 3× Mage, 3× Shaman
- **Normal**: 58 enemies · avg L11.5 — 20× Cavalier, 10× Pegasus Knight, 6× Fighter, 3× Archer, 3× Mage, 3× Shaman
- **Difficult**: 58 enemies · avg L11.5 — 20× Cavalier, 10× Pegasus Knight, 6× Fighter, 3× Archer, 3× Mage, 3× Shaman
- **Playstyle**: *not yet digested — `tools/fe8_guide_mine.py --strategy ephraim13`*

## Chapter 14 (Ephraim)

- **Objective**: Seize the throne  ·  **Lose**: Ephraim dies
- **Deploy**: 1–12
- **Easy**: 71 enemies · avg L12.2 — 15× Knight, 14× Shaman, 8× Fighter, 7× Mage, 6× Myrmidon, 6× Soldier
- **Normal**: 71 enemies · avg L12.2 — 15× Knight, 14× Shaman, 8× Fighter, 7× Mage, 6× Myrmidon, 6× Soldier
- **Difficult**: 81 enemies · avg L12.3 — 20× Shaman, 15× Knight, 9× Mage, 8× Fighter, 6× Myrmidon, 6× Soldier
- **Hard-mode delta**: {'Shaman': 6, 'Mage': 2, 'Priest': 2} — a UNIT change, not just a level shift
- **Playstyle**: *not yet digested — `tools/fe8_guide_mine.py --strategy ephraim14`*

## Chapter 15

- **Objective**: Defeat all enemies  ·  **Lose**: Eirika or Ephraim dies
- **Playstyle**: *not yet digested — `tools/fe8_guide_mine.py --strategy ch15`*

## Chapter 16

- **Objective**: Seize the throne  ·  **Lose**: Eirika or Ephraim dies
- **Playstyle**: *not yet digested — `tools/fe8_guide_mine.py --strategy ch16`*

## Chapter 17

- **Objective**: Defeat Lyon  ·  **Lose**: Eirika or Ephraim dies
- **Deploy**: 1–12
- **Easy**: 64 enemies · avg L8.6 — 15× Wyvern Rider, 12× Druid, 10× Warrior, 6× Cavalier, 4× Paladin, 4× Hero
- **Normal**: 64 enemies · avg L8.6 — 15× Wyvern Rider, 12× Druid, 10× Warrior, 6× Cavalier, 4× Paladin, 4× Hero
- **Difficult**: 64 enemies · avg L8.6 — 15× Wyvern Rider, 12× Druid, 10× Warrior, 6× Cavalier, 4× Paladin, 4× Hero
- **Playstyle**: *not yet digested — `tools/fe8_guide_mine.py --strategy ch17`*

## Chapter 18

- **Objective**: Defeat all enemies  ·  **Lose**: Eirika or Ephraim dies
- **Easy**: 46 enemies · avg L6.1 — 21× Gorgon, 18× Gorgon Egg, 4× Mogall, 3× Gargoyle
- **Normal**: 46 enemies · avg L6.1 — 21× Gorgon, 18× Gorgon Egg, 4× Mogall, 3× Gargoyle
- **Difficult**: 69 enemies · avg L7.4 — 27× Gorgon, 24× Gorgon Egg, 9× Bael, 5× Gargoyle, 4× Mogall
- **Hard-mode delta**: {'Gorgon': 6, 'Gorgon Egg': 6, 'Gargoyle': 2, 'Bael': 9} — a UNIT change, not just a level shift
- **Playstyle**: *not yet digested — `tools/fe8_guide_mine.py --strategy ch18`*

## Chapter 19

- **Objective**: Protect Mansel for 13 turns or defeat Riev  ·  **Lose**: Eirika , Ephraim , or Mansel dies
- **Deploy**: 1–17
- **Easy**: 97 enemies · avg L6.9 — 16× Swordmaster, 16× Warrior, 9× Hero, 7× Great Knight, 7× Mage Knight, 7× Paladin
- **Normal**: 97 enemies · avg L6.9 — 16× Swordmaster, 16× Warrior, 9× Hero, 7× Great Knight, 7× Mage Knight, 7× Paladin
- **Difficult**: 97 enemies · avg L6.9 — 16× Swordmaster, 16× Warrior, 9× Hero, 7× Great Knight, 7× Mage Knight, 7× Paladin
- **Playstyle**: *not yet digested — `tools/fe8_guide_mine.py --strategy ch19`*

## Chapter 20

- **Objective**: Seize the gate  ·  **Lose**: Eirika or Ephraim dies
- **Deploy**: 1–18
- **Easy**: 122 enemies · avg L6.3 — 30× Deathgoyle, 22× Wight, 20× Mogall, 16× Maelduin, 15× Elder Bael, 9× Cyclops
- **Normal**: 122 enemies · avg L6.3 — 30× Deathgoyle, 22× Wight, 20× Mogall, 16× Maelduin, 15× Elder Bael, 9× Cyclops
- **Difficult**: 157 enemies · avg L6.3 — 33× Deathgoyle, 22× Wight, 20× Mogall, 20× Elder Bael, 19× Maelduin, 15× Gwyllgi
- **Hard-mode delta**: {'Maelduin': 3, 'Gargoyle': 6, 'Arch Mogall': 3, 'Deathgoyle': 3, 'Elder Bael': 5, 'Gwyllgi': 15} — a UNIT change, not just a level shift
- **Playstyle**: *not yet digested — `tools/fe8_guide_mine.py --strategy ch20`*

