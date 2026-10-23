---
id: 365
title: "Kits: the happy path is graded, the guaranteed path printed beside it"
date: "2026-10-22"
section: "Combat System"
issues: [510]
---

# Kits: the happy path is graded, the guaranteed path printed beside it

#510 step 8 (design and plan on #510, 2026-10-22). Until this step every party unit fought
with the first weapon of the kit it joined with, in every chapter, on both sides.

**Now** each unit carries what it would actually hold (`kits.py`): its joining load, plus
what the chain hands the party before the chapter. That covers scene gifts, village gifts,
chests, drops, in-map shops and world-map shops, read by the same rules on both sides.
Against each enemy it strikes with whichever carried weapon kills fastest
(`fe_combat.best_rounds_to_kill`).

Nicolas's calls:
- **The verdict reads the HAPPY path**: a careful player takes every pickup, the same stance
  as step 7. `make difficulty CH=chNN` prints the GUARANTEED path beside it, only what no
  player can miss. A wide gap marks a chapter whose difficulty hinges on optional pickups.
- **Shops count, both in-map and world-map, with no gold tracking.** Gold follows vanilla's
  (ADR 0092), our in-map shops are the map donor's (ADR 0345), and our world map is planned
  to match vanilla's. Until a `campaign.yaml` town carries a `stock:` list, our world map is
  read as the twin's, marked `projected`.
- **Out**: healing (it cancels, because the recruit schedule follows vanilla's: Sclorbo one
  chapter before Moulder, Basil with Natasha), durability (a player restocks), the arena
  (optional), stat boosters and other non-weapons (rare early and mirrored).

Claude's calls, for checking:
- A pickup is in hand from the chapter AFTER it is handed out. The exception is a scene gift,
  which is in hand in its own chapter (the Prologue's opening hands Eirika the Rapier).
- A gift's vehicle is how it is DELIVERED, on both sides. A visit (village, house, boat talk)
  is `village`, the happy path. What a scene hands out (a clear bonus, a surviving ally's gift,
  the Prologue's Rapier) is `scene`, guaranteed. The twin's gifts are split by the script block
  that gives them, never by matching items.
- A named gift goes to its first listed recipient who is present, or to nobody. A shop item
  goes to every unit that can wield it and lacks it. Any other weapon goes to the first such
  unit in join order. 5 slots, weapons only; past them, a weapon another one beats outright
  goes first.
- Ranks do not grow, on either side. Our units' ranks are their STAT_DONOR's.
- Steals and keys are no vehicle: FE8 lets a thief take only plain items (`IsItemStealable`,
  bmitem.c), so neither ever changes what a unit fights with.
- `difficulty.item_weapon` is the one item -> weapon reader. It uses the fc.W entry, or else
  reads the weapon off data_items.c, so a kit can hold a weapon fc.W never listed.

What moved (verdict diff on the PR): five cells went OFF, ch03 and ch04 on Tutorial and Normal
and ch01 on Difficult, whose ADR 0042 residual lapses (it is not widened). Pickups barely move
anything: the happy and guaranteed paths sit within 0.04 of each other. The move is vanilla's
second joining weapons. Seth's Silver Lance alone takes ch01 Normal from x1.41 to x1.56, the
party excess the step-10 baseline already named.
