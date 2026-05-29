# Manchego Stars — Campaign Brief

> Produced via interview with Nicolas (May 2026).
> Companion to `research.md`. Together these two documents feed the PRD.
>
> **Note:** this brief describes the PCs in **5e terms** (their D&D abilities, AC, saves, resistances) —
> it is the D&D-source record. In the FE adaptation, combat is **vanilla FE**: AC, saving throws,
> advantage, and damage-type resistance are flavor only (defense = FE DEF/RES + avoid; iconic matchups
> use vanilla FE weapon effectiveness). See `decisions.md` §Combat System for what's actually mechanical,
> and the chapter YAMLs / PRD §7 for the authoritative per-chapter objectives.

---

## 1. Project Identity

- **Working title:** Manchego Stars
- **Elevator pitch:** "Our D&D campaign, playable as a GBA tactics game"
- **Target audience:** Private — the 7 players from the Icewind Dale campaign only
- **Distribution:** Pre-patched ROM sent directly to the group (no public hosting, no patch file)
- **Licensing implications:** Private distribution means non-SRD content (Artificer, Circle of Spores, homebrew classes) can be used freely without OGL/SRD concerns. No need to scrub proprietary D&D content.

---

## 2. Scope

- **MVP chapter count:** 5+ chapters covering the full DM-notes arc (all 9 narrative beats, from the goblin iron quest through the Eastway ambush / Revel's End capture)
- **MVP endpoint:** The party is ambushed on the Eastway road, overwhelmed by ice trolls, and sent to Revel's End. Strong cliffhanger ending.
- **Stretch goal:** [TBD — Nicolas wants to focus on MVP first. A future writing session will outline the rest of the campaign beyond the DM notes.]
- **Hard cap:** [TBD — same as above]
- **Target ship date:** None — ship when it's ready. No external deadline.
- **Note:** The research doc recommended 3 chapters. Nicolas chose a larger MVP (all available story content). This means ~5–9 FE chapters depending on how beats are combined/split — exact chapter breakdown will be decided in Section 6 (Story Arc).

## 3. Tone & Setting

- **Setting:** Icewind Dale, Forgotten Realms — arctic survival, Ten-Towns, Auril the Frostmaiden as central antagonist. Standard published setting from *Rime of the Frostmaiden*.
- **Tone:** Balanced — heroic adventure with comedy. The campaign had genuine stakes and dramatic moments, but the party's antics (installing a plesiosaur as town Speaker, massacring a cantankerous dwarf) kept things fun. Think serious quest structure with player-driven absurdity.
- **Plot fidelity:** Followed the book's major beats, but the party frequently went off-script. The DM eventually steered them through all the published story milestones. The DM notes show the party's version of events, which diverge from the book in entertaining ways.
- **Homebrew setting overlays:** [TBD — Nicolas doesn't remember specific setting changes. The party itself is wildly non-standard (Hermit Crab, Myconid, Vampire Tabaxi, Snowperson, Chwinga, Ratfolk, Dragonborn) but the world may have been played straight.]
- **Vibe references:** Critical Role (Matt Mercer's campaigns) and Dimension 20 (Brennan Lee Mulligan / CollegeHumor) — long-form D&D actual play with dramatic stakes and comedic player energy.

## 4. The Cast — PCs

> All 7 PCs are available from Chapter 1 (they met together at The Northlook tavern in Bryn Shander).
> Recruitable units in the FE sense will be **NPC allies** picked up during the journey (see Section 5).
> Permadeath: **Player choice** — use FE8's existing Casual/Classic mode toggle. PCs and NPC allies alike are subject to the chosen mode.
> All PCs started at D&D level 1; their sheets show **end-of-campaign** stats (level 20 ceiling, except Sclorbo at 16). FE starting stats should be low, with growth toward these end-state profiles.

### Braulo
- **Race:** Hermit Crab (homebrew Tortle)
- **Class:** Barbarian — Path of the Berserker (level 20)
- **Stats snapshot:** STR 23, CON 24, HP 285, AC 17
- **Party role:** Primary tank / melee DPS. Highest HP in the party by far.
- **Signature abilities:** Rage (+4 melee damage, B/P/S resistance), Frenzy (bonus action attack), Shell Defense (+4 AC), Brutal Critical (3 extra dice), Retaliation (reaction attack when hit)
- **Signature moment:** Burst open his shackles on the Eastway road, starting the fight that got the whole party captured.
- **Notable equipment:** Nu' Shipwrecker (1d8/1d10+7, 10 ft reach), Silvered Trident
- **FE class mapping:** Pirate or Brigand → Berserker. Rage = consumable Berserk status item. Shell Defense = unique defensive command.

### Marty the Merry Mushroom
- **Race:** Sporemaster (homebrew Myconid)
- **Class:** Druid — Circle of Spores (level 20)
- **Stats snapshot:** WIS 20, DEX 18, CON 17, HP 163, AC 17
- **Party role:** Healer / debuffer / summoner. Spore AoE damage, fungal minions, full druid caster.
- **Signature abilities:** Symbiotic Entity (+80 temp HP, doubled Halo damage), Halo of Spores (reaction: 1d10 necrotic), Spreading Spores (AoE), Fungal Infestation (animate dead), Archdruid (unlimited Wild Shape)
- **Signature moment:** [TBD — Nicolas to recall]
- **Notable equipment:** Marty's Staff
- **Defenses:** Poison resistance, immune to Blinded/Crits/Deafened/Frightened/Poisoned
- **FE class mapping:** Shaman or custom Druid → Summoner. Halo of Spores = innate AoE skill. Fungal Infestation = summon mechanic.

### Meesmickle
- **Race:** Vampire Tabaxi (homebrew)
- **Class:** Warlock — The Fiend (level 20)
- **Stats snapshot:** DEX 20, CON 19, CHA 16, HP 183, AC 15
- **Party role:** Striker / blaster. Eldritch Blast spam, Fiend patron temp HP sustain.
- **Signature abilities:** Eldritch Blast (4 beams), Dark One's Blessing (23 temp HP on kill), Hurl Through Hell (10d10 psychic, 1/long rest), One with Shadows (invisibility in dim light)
- **Signature moment:** [TBD — Nicolas to recall]
- **Notable equipment:** Javelin of Lightning (1d6+4d6)
- **FE class mapping:** Shaman (Dark) → Druid / Dark Sage. Eldritch Blast = cantrip-tier dark tome.

### Prof. R.B. Geenius
- **Race:** Underfolk (homebrew Ratfolk)
- **Class:** Artificer — Artillerist (level 20)
- **Stats snapshot:** INT 20, DEX 19, CON 16, HP 163, AC 16
- **Party role:** Controller / support / ranged DPS. Turrets, utility, crafting.
- **Signature abilities:** Eldritch Cannon (Flamethrower/Force Ballista/Protector, 2 at once), Arcane Firearm (+1d8 spell damage), Flash of Genius (reaction: +5 to ally check/save), Soul of Artifice (cheat death), Infuse Item (6 objects)
- **Signature moment:** Executed a kobold at gunpoint during the "good cop, bad cop" interrogation in the Termalaine mine.
- **Notable equipment:** Fonduedler (ranged, 1d10+4), Luck E. Cheese (melee, 1d6+5, 2 wish charges)
- **FE class mapping:** Custom Artificer class (no direct FE equivalent). Eldritch Cannon = deployable ballista unit or activated skill. Closest base: Mage with custom weapon type.

### Rootis
- **Race:** Snowperson (homebrew)
- **Class:** Sorcerer — Draconic Bloodline (level 20)
- **Stats snapshot:** CON 20, DEX 18, CHA 17, HP 202, AC 17
- **Party role:** Blaster / utility caster. Metamagic, flight, Staff of Power.
- **Signature abilities:** Draconic Resilience (bonus HP, natural AC), Dragon Wings (flight), Draconic Presence (AoE fear/charm), Metamagic (Distant, Empowered, Extended, Twinned), 20 Sorcery Points
- **Signature moment:** [TBD — Nicolas to recall]
- **Notable equipment:** Staff of Power (20 charges)
- **FE class mapping:** Mage (Fire variant) → Sage. Metamagic = activated skill modifiers (Twinned = attack twice, Empowered = damage boost).

### Sclorbo
- **Race:** Chwinga (homebrew)
- **Class:** Bard — College of Lore (level 16)
- **Stats snapshot:** WIS 18, CHA 17, DEX 15, HP 99, AC 12
- **Party role:** Support / face / debuffer. Lore Bard with massive skill list, Cutting Words, Bardic Inspiration.
- **Signature abilities:** Bardic Inspiration (d12), Cutting Words (reaction: subtract die from enemy roll), Peerless Skill, Countercharm, Magical Secrets, Jack of All Trades
- **Signature moment:** [TBD — Nicolas to recall]
- **Notable equipment:** None listed
- **Level note:** Level 16 (vs 20 for others) because the player got busy and left the campaign before it ended. No in-story reason. In the hack, Sclorbo starts at the same level as everyone else; the level-16 cap may mean slightly lower endgame growth rates if the full campaign is ever built.
- **FE class mapping:** Dancer or Troubadour → custom Bard. Bardic Inspiration = Dancer's refresh action. Cutting Words = debuff skill.

### Wolfram
- **Race:** Mineralscale Drakeborn (homebrew Dragonborn)
- **Class:** Metallurgist (fully homebrew, see `Class_The_Metallurgist.pdf`)
- **Stats snapshot:** STR 20, INT 20, CON 14, HP 143, AC 26 (!!)
- **Party role:** Tank / melee striker. Highest AC in the party. STR/INT dual-stat, crafting/combat hybrid.
- **Signature abilities:** Feral Strike: Bite (1d8+5) and Claws (2d6+5) as bonus actions, Shield spell (reaction), Fire Resistance (racial), AC 26 from class features + heavy armor + shield + magic
- **Signature moment:** Used extra iron ingots to cast armored siding for the party's sled while camping in the snow (from the DM notes). Snacked on ores in the Termalaine mine. A crafter through and through.
- **Notable equipment:** Warhammer x2
- **Notable spells:** Fire Bolt, Magic Stone, Mending, Shield, Conjure Elemental, Creation, Imprisonment
- **FE class mapping:** Custom Metallurgist class (no FE equivalent). Closest base: Knight or General (heavy armor + high DEF). INT-based casting adds a mage-knight angle. Needs custom class definition.
- **Subclass:** School of the Smith — master crafter focused on upgrading armor and forging weapons. Key features: Improved Upgrade (+2 AC from armor upgrade instead of +1, half time), Forge Expert (smith any metal armor with damage resistance), Blade Forge (upgrade weapons for +1 damage die), Master of the Forge (craft Adamantine, Resistance, or Mithral armor).
- **Metallurgist base class features (relevant to FE design):** Upgrade Armor (+1 AC to metal armor), Tinkerer's Whit (INT for ranged attacks), Metal Sense (detect metal nearby), Magnetism (push/pull metal objects), Armor Savant (levitate in upgraded armor), Armor Master (flight at lvl 15), Mobile Fortress (magnetic AoE pulse at lvl 20). Hit die: d8. INT-based.
- **FE design note:** Smith subclass is a perfect fit for a Knight/General-type with a crafting twist. His AC 26 likely comes from stacked Upgrade Armor + Improved Upgrade + heavy armor + shield. In FE terms: highest DEF in the party, with a unique "Forge" ability that can upgrade allied equipment between chapters.

## 5. The Cast — NPCs & Villains

### Recruitable NPC Allies
> These fill the "recruitment" role in FE — units that join across chapters as the story progresses.

- **Baxby** — Axe-beak. Purchased by the party in Bryn Shander to pull their sled. Rideable mount unit or NPC escort. Joins early (Chapter 1–2).
- **Pinky** — Prof. R.B. Geenius's homunculus "son." Functionally an automaton/familiar, very important to RBG's character. Should be included as a companion unit tied to RBG (possibly an adjutant or pair-up unit). Available from Chapter 1 (with RBG).
- **Trex** — Kobold leader from the Termalaine mine. Slightly smarter than average, fashioned cosmetic wings for himself. Scrappy low-level recruit. Joins after the mine chapter.
- **Basil(?)** — Sentient shrub that produces Goodberries. Found at the elven tomb. Healer/support unit. Joins mid-campaign.
- **The Mummy** — Reawakened from the elven tomb sarcophagus. Happy to help the party in exchange for learning about modern druids. Tanky magic unit. Joins mid-campaign alongside Basil.

### Non-Recruitable NPCs (Cutscene / Story Role)
- **Duvessa Shane** — Speaker of Bryn Shander. Quest-giver who hires the party. Cutscene NPC only — appears in dialogue/story scenes, doesn't fight.
- **Velynne Harpell** — Arcane Brotherhood member. Asks the party to find a stolen orb. Appears early. [TBD — Nicolas doesn't remember if she becomes important later. Check against published adventure.]
- **Messie (the Maer Monster)** — Awakened plesiosaur. Became Speaker of Bremen after the party's... intervention. Non-recruitable; permanent NPC in Bremen (could run a shop or provide services — to be brainstormed).
- **The old woman Speaker of Lonelywood** — Lets the party stay the night. Minor NPC.

### Villains & Antagonists

**BBEG (full campaign):** Auril the Frostmaiden — goddess of winter, central antagonist per the published adventure. Not present in MVP scope but should be foreshadowed.

**MVP-scope antagonists:**
- **Goblins** (Chapter 1) — Stole the dwarves' iron ingot shipment. Trash mob encounter. FE: Brigand/Bandit units.
- **Kobolds + Grells** (Termalaine mine) — Kobolds occupied the mine, Grells in the vertical shaft were picking off miners and kobolds. FE: Kobold = low-tier units; Grells = mini-boss monsters.
- **Frost Druid** (elven tomb) — Fights to the death in Auril's name. Mid-tier villain, represents Auril's influence. FE: boss unit (Shaman/Druid class).
- **Dorbulgruf Shalescar** (Bremen) — Cantankerous old dwarf Speaker who refused to pay the party. Braulo took the first swing. FE: boss unit or mid-chapter event fight.
- **Easthaven Guards + Ice Trolls** (Eastway ambush) — 20+ guards plus ice trolls in Easthaven garb. This is a "lose battle" — the party is meant to be overwhelmed and captured. FE: unwinnable defense / survive-N-turns chapter ending in scripted defeat.
- **Three Dwarves** (Bryn Shander) — Quest-givers for the opening mission, not antagonists. Minor NPCs.

### Foreshadowed / Named but not yet encountered
- **Sephek Kaltro** — Auril cultist (published Ch. 1 villain). [TBD — confirm if he appeared in Nicolas's campaign]
- **Xardarok Sunblight** — Duergar warlord (published Ch. 3). [TBD — beyond MVP scope but should be foreshadowed if relevant]

## 6. Story Arc

> 7 chapters covering all 9 narrative beats from the DM notes. Ends on the Revel's End cliffhanger.

### Chapter 1: The Iron Trail
**Beat:** The party meets at The Northlook tavern in Bryn Shander. Three dwarves hire them to track a missing shipment of iron ingots. They follow the trail to a dismembered body, then find the goblin thieves.
**Who's introduced:** All 7 PCs, Baxby (purchased after this chapter or early Ch 2), Duvessa Shane (cutscene — hires them for ongoing Ten-Towns work), Velynne Harpell (brief appearance, asks about stolen orb).
**Map objective:** Seize — defeat the goblins, recover the iron ingots, and seize the camp (mirrors FE8 Ch1 "Escape!").
**Map concept:** Snowy trail leading from Bryn Shander to the goblin camp. Linear introductory map.

### Chapter 2: Cold Welcome
**Beat:** The party travels west to Targos, encountering dangers on the road. In Targos, they find a frozen body (human sacrifice to Auril), learn about frost druid activity, and hear rumors of the Maer Monster in Bremen.
**Who's introduced:** No new recruits. Frost druids foreshadowed. Baxby joins here if not in Ch 1.
**Map objective:** DefeatAll — defend the parked sled while clearing the road ambush (wolves + bandits + a raider captain; mirrors FE8 Ch2 "The Protected").
**Map concept:** Open snowy road with sled escort. Enemies attack from tree lines or snowdrifts.
**Story note:** Targos arrival is post-map cutscene (sacrifice discovery, inn scene, overheard rumors).

### Chapter 3: The Termalaine Mine
**Beat:** In Termalaine, kobolds have taken over the gemstone mine and miners are going missing. The party enters to find kobolds AND Grells in the deep shaft. Prof. RBG executes a kobold during interrogation. They meet Trex (kobold leader) and slay the Grells.
**Who's introduced:** Trex (recruited after the chapter). Pinky involved in gameplay (sent down the vertical shaft to scout the Grells).
**Map objective:** Seize — clear the mine of Grells (true threat). Optional: spare kobolds or fight them.
**Map concept:** Multi-level mine interior. Kobolds on upper levels (can be fought or bypassed), Grells as boss enemies in the lower shaft.
**Recruitment:** Trex joins after clearing the mine.

### Chapter 4: The Elven Tomb
**Beat:** The party passes through Lonelywood (brief stay with the old woman Speaker) and heads to an elven tomb where they encounter a frost druid who fights to the death. They find Basil (sentient Goodberry shrub), solve a moonlight puzzle, and awaken a mummy ally.
**Who's introduced:** Basil (recruit), The Mummy (recruit).
**Map objective:** Boss kill — defeat the frost druid. Moonlight puzzle could be a mid-map event (move units to specific tiles).
**Map concept:** Forest path leading to tomb interior. Frost druid as boss with druid/nature-themed minions.
**Recruitment:** Basil and The Mummy join after the chapter.

### Chapter 5: The Maer Monster
**Beat:** In Bremen, a plesiosaur called Messie has been capsizing fishing boats. The party is drafted onto a fishing crew and encounters Messie on the water. The fight is heavily one-sided — the party is in a small boat against a sea monster. This pushes them to use the Talk command, where Marty speaks with Messie and learns it was awakened by the frost druid and is afraid of losing its intelligence.
**Who's introduced:** Messie (non-recruitable, becomes permanent Bremen NPC). Elven wildlife researcher (minor NPC).
**Map objective:** Survive / Talk — combat starts as a heavily lopsided fight (Messie's stats are overwhelming). The intended solution is to use Talk (Marty) to resolve peacefully. Players CAN keep fighting but it should feel nearly impossible.
**Map concept:** Water map with 2 boats (small boat for most PCs, large boat for Braulo/Wolfram). Messie as a massive enemy unit that attacks both boats. Tight space, high tension.
**Design note:** This chapter teaches the Talk mechanic by making brute force clearly unviable. Classic FE "recruit the enemy" pattern, but for a boss-sized unit.

### Chapter 6: Blood in Bremen
**Beat:** The party reports to Dorbulgruf Shalescar, the cantankerous old dwarf Speaker of Bremen, who refuses to pay them. Braulo takes the first swing. After a bloody battle, the party installs Messie as the new Speaker. They leave to mixed reception.
**Who's introduced:** No new recruits. Messie's role shifts to NPC ally / town leader.
**Map objective:** DefeatBoss — defeat Dorbulgruf in or around the Speaker's hall (mirrors FE8 Ch6 "Victims of War").
**Map concept:** Town interior / hall map. Could have civilians as "don't kill" units to add complexity. Mixed reception aftermath is a post-map cutscene.

### Chapter 7: The Eastway Ambush
**Beat:** The party treks east toward Easthaven, feeling like heroes. They enter an ice canyon and are ambushed by 20+ Easthaven guards demanding their arrest for the Bremen incident. Braulo breaks his shackles and the party fights, but ice trolls in Easthaven garb swarm them with boulders. The party is overwhelmed, goes unconscious, and wakes up on the way to Revel's End.
**Who's introduced:** No new recruits. The Easthaven guards and ice trolls are the final antagonists of the MVP.
**Map objective:** Survive N turns — hold out against waves of guards and ice trolls in a narrow canyon. Scripted loss after the timer expires (boulders block the path, reinforcements overwhelm). This is an unwinnable battle by design.
**Map concept:** Narrow ice canyon with high walls. Guards attack from both sides. Ice trolls arrive as reinforcements partway through. The "Rolling Cheddar" (party's sled) is present — the party tries to get it moving but boulders block the path.
**End state:** Scripted defeat cutscene — party goes unconscious, fade to black, text: "You wake up on the road to Revel's End..." Cliffhanger ending for the MVP.

## 7. Art Direction

- **Map sprites (units on the grid):** Start with recolored vanilla FE8 sprites. Use Nanobanana 2 (AI sprite editing tool) to modify them as needed for the homebrew races and classes (e.g., Tortle shell for Braulo, mushroom features for Marty, Dragonborn look for Wolfram). This gives a fast baseline that can be iterated on.
- **Character portraits (dialogue / stat screens):** AI-generate base portraits using the D&D Beyond character art as reference, then manually clean up and convert to FE pixel art specs (GBA palette constraints, correct dimensions). The D&D Beyond portrait URLs are saved in `References/PCs/portraits.json`.
- **Enemy sprites:** Vanilla FE8 enemy sprites, recolored as needed. Custom creatures (Grells, Messie, ice trolls) may need community sprites or Nanobanana 2 edits.
- **Map tiles:** Vanilla FE8 tilesets (snow/ice tilesets exist in FE8 for the Tower of Valni area, plus community-made arctic tilesets on FEUniverse). May need custom tiles for mine interiors, the elven tomb, and water/boat maps.
- **Cutscene art:** [TBD — decide whether to include CG-style cutscene illustrations for key moments, or rely on portrait-based dialogue like vanilla FE8]

## 8. Audio Direction

- **Baseline:** Vanilla FE8 (Sacred Stones) soundtrack. It has moody, epic, and atmospheric tracks that suit an arctic adventure well enough as a starting point.
- **Stretch: Frostmaiden album + community tracks:** Nicolas mentioned a Rime of the Frostmaiden album on Spotify. The `frostmaiden-resources.md` also links 17+ community soundtrack compilations, ambient playlists, and per-location music cues — these are all fair game as source material. Converting to GBA-compatible audio (8-bit/chiptune, MIDI, or S-file format) is technically feasible but non-trivial — GBA audio is limited to ~8 channels and specific sample rates.
- **Recommendation for PRD:** Ship MVP with vanilla FE8 music as the default, but actively explore the Frostmaiden Spotify album AND the community resources from `frostmaiden-resources.md` as candidates for custom tracks. Priority candidates: boss fight themes, the Messie water encounter, the Eastway ambush, and any location-specific music that matches a chapter's mood. Keep options open — the PRD should plan for audio swaps even if the MVP ships with vanilla tracks.

## 9. Open Decisions

> Collected from TBD markers throughout the brief + research doc open questions. The PRD should present options for these rather than assuming.

### From the brief interview:
1. **Signature moments for Marty, Meesmickle, Rootis, Sclorbo** — Nicolas will recall later. Each PC should have at least one moment that gets a special in-game reference (unique dialogue, cutscene, or ability trigger).
2. **Additional signature moments beyond the DM notes** — Nicolas will think on it. There may be late-campaign moments worth referencing even in early chapters (easter eggs, foreshadowing).
3. **Wolfram's Metallurgist subclass** — Resolved: School of the Smith (see Section 4). FE class: Knight/General with unique Forge ability.
4. **Velynne Harpell's role** — Nicolas doesn't remember if she becomes important later. Check published adventure for her arc; if significant, she should be foreshadowed properly in MVP chapters.
5. **Homebrew setting overlays** — Nicolas doesn't remember specific DM changes to the Icewind Dale setting. Default assumption: standard Forgotten Realms setting with a very non-standard party.
6. **Stretch goal / hard cap for total chapters** — Deferred until a writing session covers the rest of the campaign beyond the DM notes.
7. **Messie's Bremen role** — Confirmed as non-recruitable permanent NPC. Specific function (shop, services, quest-giver) to be brainstormed.
8. **Cutscene art** — Decide whether to include CG-style illustrations for key moments or rely on portrait-based dialogue.
9. **Custom audio tracks** — Investigate Frostmaiden Spotify album AND community resources from `frostmaiden-resources.md` (17+ soundtracks/playlists) for GBA conversion. Keep options open. Stretch goal, not blocker.

### From the research doc (carried forward):
10. **D20 variance vs FE hit-rate norms** — Vanilla FE shows 70–95% hit; d20 is swingier. Research proposed three mitigations — needs playtesting to decide.
11. **GBA UI real estate** — Fitting d20 combat info (AC, to-hit, damage dice) into the ~96x40px combat preview. Needs UI prototyping.
12. **Save-file size** — Adding D&D ability scores + spell slots to unit struct may exceed FE8's per-character save budget. Audit early.
13. **Map design** — LLMs are bad at FE maps. All maps must be hand-drawn (Tiled/FEBuilder) or curated from community pool.
14. **Permadeath vs D&D revival** — Resolved: player choice via Casual/Classic toggle. But in-fiction, how are "retreats" explained for a party in arctic wilderness?
15. **Engine/content boundary** — The PRD must define the contract: what a campaign folder contains, what the engine assumes. Avoid hardcoding Frostmaiden assumptions in C.
