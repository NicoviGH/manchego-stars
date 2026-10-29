---
id: 379
title: "A theft spoils a clean clear only when the thief took something it ranks above the stat boosters"
date: "2026-10-29"
section: "Combat System"
issues: [510]
---

# A theft spoils a clean clear only when the thief took something it ranks above the stat boosters

**Decided (Nicolas, 2026-10-29), for #510 step 9's clean clear (ADR 0376):** every theft is
recorded, and only a theft of an item FE8's own AI ranks above the stat boosters spoils the clear.

**What a thief takes is the game's own list.** An AI thief (its class has `CA_STEAL`, and it has a
free item slot) weighs a steal before any attack (`cp_battle.c:44-52`). It steals only from an
enemy it can stand beside this turn whose Spd is not above its own, and it takes the single
highest-ranked item among every unit it can reach (`AiAttemptStealActionWithinMovement`,
`cp_battle.c:377`). The rank is the item's place in `gAiStealPriorityItemList` (`cp_data.c:921`,
read by `AiGetItemStealRank`); an item not on it is never stolen. In the list's order:
1. Member Card, Silver Card
2. Hoplon Shield, Delphi Shield
3. Lockpick, Metis's Tome
4. Master Seal, Hero Crest, Knight Crest, Orion's Bolt, Elysian Whip, Guiding Ring, Heaven Seal
   (and `ITEM_UNK_C1`, which the list holds between Heaven Seal and White Gem)
5. White Gem, Filla's Might, Ninis's Grace, Thor's Ire, Set's Litany
6. the stat boosters (Skl first), Juna Fruit, Blue Gem, Red Gem
7. Elixir, Chest Key, Door Key, Pure Water, Torch, Vulnerary, Antitoxin, Mine, Light Rune

**A stolen item never comes back.** `ActionSteal` (`bmmind.c:363`) gives the thief the item with
`UnitAddItem`; only the item-got popup marks a red unit `US_DROP_ITEM` (`popup.c:505`), so a thief
killed after a theft drops nothing (unless the item already was a drop). Seen in the ROM: vanilla
Ch3, a Thief stole two Vulneraries from Seth on turns 6-7, fell to him on turn 8, and gave no drop.

**The rule.** A theft of an item in groups 1-5, i.e. ranked before `ITEM_BOOSTER_SKL` in the
game's list (the line is that item's rank, read from the list, never a copied number), spoils the
clean clear: a player resets for a lost Master Seal. A theft from groups 6-7 is recorded in the
BOTRUN record (item, rank, from whom, turn) and noted in montecarlo's summary, but the clear
stays clean: a lost Vulnerary is an annoyance, not a reset.
