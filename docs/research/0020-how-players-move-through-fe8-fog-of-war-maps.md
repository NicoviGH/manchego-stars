---
id: 20
title: "How players move through FE8 fog-of-war maps"
date: "2026-10-27"
section: "FE8: whom guides field, by chapter"
issues: [510]
tags: [fog, vision, thief, torch, formation, chokepoint, baiting, chapters]
---

# How players move through FE8 fog-of-war maps

Collected by web research for the #510 step 9 bot (2026-10-27). The question is the PLAY PATTERN on a
fog map (pace, who leads, where weak units stand, how vision is spent), not the deploy list (records
0013-0017 hold that). Paraphrased; source keys are record 0012's table plus the new tags below. Pages
were read through an extraction model (WebFetch / Firecrawl "query"), not line by line.

**Headline: the FE8 walkthroughs say little about HOW to advance in fog.** They say what to bring
(thief, Torch) and where to go; a general method appears only in one FE7 Let's Play (LP-M). Every
FE8 chapter page on FEW, and SW's ch11A, has no fog method at all. Items below are what the sources
actually say; nothing is filled in.

## General pattern (GBA fog, mostly from one FE7 source)

1. **The enemy is not fogged; you are.** The AI knows every unit's position, so plan for the
   worst-case hit from units you cannot see (LP-M; single source, but it is a mechanic, not a habit).
2. **Vision updates only after a unit ACTS (waits/attacks), not while it moves.** So players move one
   unit, let the fog clear, then decide the next move; and they order moves so a target is never left
   in fog when the attacker's turn comes (LP-M, FEW-fog). Walking into a hidden enemy stops the unit
   one tile short and ends its action (LP-M, FEW-fog).
3. **Thieves see 8 tiles (others 3) and lead / scout.** FE7's Matthew asks to be put in the lead
   (FEW-fog); LR lists Vision Extend 8 for Thief/Rogue/Assassin; SW ch6, SH ch6, KE ch6 all say Colm
   lets you see further. On maps with a choosable start, players shuffle the thief along the deploy
   area in Preparations to reveal ground before turn 1 (LP-M; LP ch6 does the same with Colm).
4. **Torches.** Torch item: +vision on the user, shrinking one tile per turn; Torch staff: lights an
   area at range (LP-M, FEW-fog). Torches go to Natasha/Moulder (SW ch6, KE ch6) or onto a sturdy unit
   so it can see without a thief out front (LP ch6; single source). KE ch19: Torch staves on
   "everyone" so you can see what's coming. LR ch6/ch11A/ch19: "light" the zone before going there.
5. **Cheap units reveal, strong units strike.** Move less important units forward to uncover ground
   that the strong units then attack into (LP-M; single source).
6. **Weak units stay out of reach.** Keep fragile units about 7 movement-tiles from fogged ground or
   screened by allies (LP-M); "keep vulnerable characters in the back" (SW ch6); hide the healer in a
   forest (SH ch6). Not stated anywhere as "end the turn so only sturdy units are reachable", though
   that is the effect of these rules.
7. **Slow vs fast is CONTESTED / not stated.** KE ch6: "no rush" in this chapter. FEH-guide advice to
   advance "slowly and steadily" exists but is not a GBA source (not used). LP ch11A has Eirika tell
   Ewan to slow down (story text, not strategy). **CONTESTED:** SH ch6 and FEW ch6 push fast (Seth
   beelines Novala); LP ch19A did no scouting and lost units on turn 1 to hidden enemies. No source
   describes a deliberate "inch forward N tiles per turn" method; BR only says fog makes players
   very cautious and reset on a loss.

## Who leads, and holding a line

8. **A wall leads.** SH ch6 sends Gilliam out for his defence; LP ch6 lets Gilliam soak the enemy phase
   and forms a wall where it cannot reach every enemy; LP ch11A uses Kyle + Gerik as a doorway wall.
   KE ch19: chokepoints held by the two tankiest units with Javelins (Seth, Franz, Ephraim) and Cormag
   with a Fili Shield. FEW ch19: plug the chokepoints with durable, high-DEF units fast.
   FEW ch11A/11B recommend promoted units (Seth, Duessel), but not as a formation rule.
9. **Baiting** is named by KE ch6 only (Franz with a lance/javelin baits the front enemies; growth units
   bait the rest) (single source). LP-M has a blocker stand on the one tile an archer could shoot from.
10. **Let them come** is a chapter call, not a fog habit: SH ch11B "stay close on 1 ship and let the
    enemy come to you"; LR ch11B gather and wait for the ship on turn 2; SH ch19 sit by Mansel and
    survive the 13 turns. **CONTESTED:** LP ch11B advanced because the enemies would not come.

## Per chapter, what is actually said about moving

- **Ch6 Victims of War:** go east and light it (LR); Colm + Torch staff on Moulder for the far east,
  no rush, bait with Franz (KE); healer in a forest, Gilliam out front, no Lv20 unit on the front (SH);
  forests for cover, Gilliam soaks (LP). FEW's strategy says nothing about fog.
- **Ch11A Creeping Darkness:** torches and a thief "for sure"; two groups, Eirika + thief + average
  units south, strong units east, regroup mid-map (SH; single source); "use Torches to light your
  way" (LR). SW, KE, FEW: nothing usable on movement.
- **Ch11B Phantom Ship:** wait for the ship (LR, SH); most units east with a paladin carrying Ephraim, a
  few behind for reinforcements, then regroup and let them come (SH); gargoyles hit from fog (LP).
- **Ch19 Last Hope:** light the southwest first, clear it quickly, then hold the entrance (LR); Torch
  staves, tanks on the west/southwest chokepoints (KE, FEW); Colm/Rennac spot after the chests (FEW).

| Tag | Source | URL |
|---|---|---|
| FEW-fog | Fire Emblem Wiki, "Fog of war" article (mechanics across the series; no formation advice) | https://fireemblemwiki.org/wiki/Fog_of_war |
| FEW | FEW chapter pages: Victims_of_War, Creeping_Darkness, Phantom_Ship, Last_Hope (Strategy sections) | https://fireemblemwiki.org/wiki/Last_Hope |
| SW | StrategyWiki ch6 (ch11 page has no movement advice) | https://strategywiki.org/wiki/Fire_Emblem:_The_Sacred_Stones/Chapter_6:_Victims_of_War |
| KE | GameFAQs katieelizabeth (/chapters-act-1, /chapters-act-3; act-2 ch11A yielded nothing) | https://gamefaqs.gamespot.com/gba/921183-fire-emblem-the-sacred-stones/faqs/80374 |
| LR | GameFAQs LRAPHQ | https://gamefaqs.gamespot.com/gba/921183-fire-emblem-the-sacred-stones/faqs/36079 |
| SH | GameFAQs Shaneth21 | https://gamefaqs.gamespot.com/gba/921183-fire-emblem-the-sacred-stones/faqs/39385 |
| LP | Let's Play Archive, Blastinus FE8 (ch6 Update 08, ch11A 15, ch11B 39, ch19A 23) | https://lparchive.org/Fire-Emblem-The-Sacred-Stones/ |
| LP-M | Let's Play Archive, Melth FE7, "War Room Part 13: Dealing With Fog of War" (FE7, same engine family) | https://lparchive.org/Fire-Emblem-Blazing-Sword-(by-Melth)/Update%2017/ |
| BR | Boss Rush, "Fog of war levels are the worst" (says fog makes players very cautious; resets on loss) | https://bossrush.net/2024/04/17/boss-rush-banter-fog-of-war-levels-are-the-worst-in-fire-emblem-games/ |

Tried and unusable: Reddit (blocked to the search tool); no Serenes Forest forum thread on fog method
surfaced; a FEH (Fire Emblem Heroes) fog guide was found but discarded as not GBA.
