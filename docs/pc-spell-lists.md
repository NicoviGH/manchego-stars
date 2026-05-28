# PC Full Spell Lists — Picking Worksheet

> **Purpose:** The complete known/prepared spell list for each caster PC, pulled from their
> D&D Beyond sheet PDFs (`References/PCs/*.pdf`) on 2026-05-28. This is the **menu Nicolas
> picks from** — per the agreed workflow, he hand-selects which spells become FE abilities;
> Claude then converts the chosen ones (per [rules-mapping.md](rules-mapping.md)) and gates
> them by chapter (per [class-progression-tables.md](class-progression-tables.md), 1:1 curve).
>
> **Do NOT port all of these** — a level-20 Druid prepares 100+ spells; that's not Fire
> Emblem. Pick a tight signature kit (~6–10 per PC) spanning Ch 1–20. Mark picks with ✓.
>
> Spell levels below are by the sheet's section order. `[R]` = ritual. Re-extract anytime:
> `pdftotext -layout "<PC> Character Sheet.pdf" - | grep -A40 "=== CANTRIPS"`

---

## Marty — Druid (Circle of Spores), L20 — prepares from the full Druid list
**Cantrips:** Shillelagh, Poison Spray, Shape Water, Mold Earth, Chill Touch
**1st:** Entangle, Cure Wounds, Speak with Animals[R], Goodberry, Animal Friendship, Charm Person, Create or Destroy Water, Detect Magic[R], Detect Poison & Disease[R], Faerie Fire, Fog Cloud, Healing Word, Jump, Longstrider, Purify Food & Drink[R], Thunderwave, Absorb Elements, Beast Bond, Earth Tremor, Ice Knife, Protection from Evil & Good
**2nd:** Spike Growth, Pass without Trace, Heat Metal, Locate Object, Animal Messenger[R], Barkskin, Darkvision, Enhance Ability, Find Traps, Flame Blade, Flaming Sphere, Gust of Wind, Hold Person, Lesser Restoration, Locate Animals/Plants[R], Moonbeam, Protection from Poison, Beast Sense[R], Dust Devil, Earthbind, Skywrite[R], Warding Wind, Summon Beast, Air Bubble, Aid, Augury[R], Continual Flame, Enlarge/Reduce
**3rd:** Call Lightning, Freedom of the Waves, Conjure Animals, Daylight, Dispel Magic, Meld into Stone[R], Plant Growth, Protection from Energy, Sleet Storm, Speak with Plants, Water Breathing[R], Water Walk[R], Wind Wall, Feign Death[R], Erupting Earth, Flame Arrows, Tidal Wave, Wall of Water, Summon Fey, Revivify
**4th:** Control Water, Polymorph, Conjure Minor Elementals, Conjure Woodland Beings, Dominate Beast, Freedom of Movement, Giant Insect, Hallucinatory Terrain, Ice Storm, Locate Creature, Stoneskin, Stone Shape, Wall of Fire, Grasping Vine, Elemental Bane, Watery Sphere, Summon Elemental, Fire Shield, Blight, Charm Monster, Confusion, Divination[R]
**5th:** Awaken, Mass Cure Wounds, Scrying, Commune with Nature[R], Tree Stride, Freedom of the Winds, Antilife Shell, Conjure Elemental, Geas, Greater Restoration, Insect Plague, Planar Binding, Reincarnate, Wall of Stone, Control Winds, Maelstrom, Transmute Rock, Cone of Cold, Contagion
**6th:** Wind Walk, Heroes' Feast, Investiture of Wind, Conjure Fey, Find the Path, Heal, Move Earth, Sunbeam, Transport via Plants, Wall of Thorns, Bones of the Earth, Investiture of Flame, Investiture of Ice, Investiture of Stone, Primordial Ward, Flesh to Stone
**7th:** Fire Storm, Plane Shift, Mirage Arcane, Regenerate, Reverse Gravity, Whirlwind, Symbol
**8th:** Animal Shapes, Antipathy/Sympathy, Control Weather, Earthquake, Feeblemind, Sunburst, Tsunami, Incendiary Cloud
**9th:** Storm of Vengeance, Foresight, Shapechange, True Resurrection
> _Signature candidates: Halo/Symbiotic (class, not spell), Chill Touch, Conjure Animals/Elemental (summoner ID), Ice Storm, Cone of Cold, Wall of Fire, Mass Cure Wounds, Contagion, Sunburst._

## Meesmickle — Warlock (The Fiend), L20 — known spells (Pact Magic)
**Cantrips:** Eldritch Blast, Minor Illusion, Magic Stone, Thaumaturgy, Acid Splash, Toll the Dead
**1st:** Protection from Evil & Good, Hellish Rebuke, Burning Hands, Mage Armor, Disguise Self, Jump
**2nd:** Suggestion, Levitate
**3rd:** Vampiric Touch, Fireball
**Mystic Arcanum 6th:** Eyebite · **7th:** Finger of Death · **8th:** Demiplane · **9th:** Power Word Kill
> _Note: YAML had 8th/9th right; was missing 6th (Eyebite) + 7th (Finger of Death), plus Hellish Rebuke / Vampiric Touch / Fireball / Toll the Dead._

## Prof. RBG — Artificer (Artillerist), L20 — prepares from Artificer list
**Cantrips:** Poison Spray, Mending, Shocking Grasp, Prestidigitation
**1st:** Cure Wounds, Tasha's Caustic Brew, Catapult, Alarm[R], Detect Magic[R], Disguise Self, Expeditious Retreat, Faerie Fire, False Life, Feather Fall, Grease, Identify[R], Jump, Longstrider, Purify Food & Drink[R], Sanctuary, Absorb Elements, Snare
**2nd:** Levitate, Enlarge/Reduce, Aid, Alter Self, Arcane Lock, Blur, Continual Flame, Darkvision, Enhance Ability, Heat Metal, Invisibility, Lesser Restoration, Magic Mouth[R], Magic Weapon, Protection from Poison, Rope Trick, See Invisibility, Spider Climb, Web, Pyrotechnics, Skywrite[R]
**3rd:** Ashardalon's Stride, Glyph of Warding, Fly, Dispel Magic, Protection from Energy, Haste, Revivify, Blink, Create Food & Water, Water Breathing[R], Water Walk[R], Flame Arrows, Intellect Fortress
**4th:** Arcane Eye, Fabricate, Freedom of Movement, Stoneskin, Stone Shape, Elemental Bane, Summon Construct, Leomund's Secret Chest, Mordenkainen's Faithful Hound, Mordenkainen's Private Sanctum, Otiluke's Resilient Sphere
**5th:** Animate Objects, Wall of Stone, Greater Restoration, Creation, Transmute Rock, Bigby's Hand
**9th (via Luck E. Cheese):** Wish
> _Signature candidates: Pepperjack/Brie (class), Shocking Grasp, Scorching Ray (noted in JSON), Summon Construct, Haste, Glyph of Warding, Animate Objects, Wish (super-rare)._

## Rootis — Sorcerer (Draconic White), L20 — known spells
**Cantrips:** Ray of Frost, Shape Water, Mold Earth, Chill Touch, Control Flames
**1st:** Feather Fall, Earth Tremor, Mage Armor, Detect Magic
**2nd:** Detect Thoughts
**3rd:** Major Image, Fly, Hypnotic Pattern
**5th:** Cone of Cold, Teleportation Circle, Immolation
**6th:** Globe of Invulnerability
**8th:** Sunburst, Incendiary Cloud, Abi-Dalzim's Horrid Wilting
**9th:** Meteor Swarm
> _Signature candidates: Ray of Frost, Chill Touch, Cone of Cold (iconic cold nuke), Globe of Invulnerability (defensive), Meteor Swarm (capstone). Note fire spells (Immolation, Incendiary Cloud) despite cold identity + fire vulnerability — odd, flag._

## Sclorbo — Bard (Lore), L16 real-life / L20 in-game — known spells
**Cantrips:** Dancing Lights, Mending, Vicious Mockery, Ray of Frost
**1st:** Animal Friendship, Charm Person, Cure Wounds, Heroism, Hideous Laughter, Magic Missile
**2nd:** Calm Emotions, Suggestion
**3rd:** Bestow Curse, Call Lightning, Fly, Revivify
**5th (Magical Secrets territory):** Raise Dead, Mislead, Mass Cure Wounds, Hold Monster
**6th:** Otto's Irresistible Dance
**7th:** Mordenkainen's Sword
> _Signature candidates: Vicious Mockery, Cure Wounds, Cutting Words (class), Call Lightning, Revivify, Mass Cure Wounds, Raise Dead, Mordenkainen's Sword (summon-blade), Otto's Irresistible Dance (CC)._

---
**Braulo** (Barbarian) and **Wolfram** (Metallurgist) have no spell list / armor-ability list respectively — Wolfram's "spells" are his armor abilities (see class-progression-tables.md) + the sheet spells already captured (Conjure Elemental, Creation, Imprisonment).
