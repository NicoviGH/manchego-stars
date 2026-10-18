---
id: 351
title: "The White Moose is a Cavalier on Forde's line, as enemy and as recruit"
date: "2026-10-18"
section: "Combat System"
issues: [502, 25, 28]
---

# The White Moose is a Cavalier on Forde's line, as enemy and as recruit

The moose joins at ch08 in Forde's role (ADR 0342), and FE8 never changes a unit's class when it
joins: Joshua is a Myrmidon on both sides, Rennac a Rogue. So the moose is a **Cavalier
everywhere**: ch04's fleeing quarry, ch05's miniboss and the ch08 recruit. The beast is the
mount, as with Lupin (direwolf) and Baxby (axe-beak). Nicolas, 2026-10-18.

**One unit on both sides.** The ch05 moose is L6, Forde's join level, carries an Iron Lance (its
antlers, under the item's vanilla name) and fights on Forde's personal line. The recruit joins at
L6 with Forde as its stat donor (#28). The enemy's line is a YAML `personal:` block, because a
raw-pid enemy's stats come from there; a test holds it to Forde's vanilla line. Forde does not go
into `STAT_DONOR` until #28 builds the recruit, because `difficulty.py` reads that table as the
playable roster.

**Simulated before it was made.** Three versions of ch05 went through the difficulty model:

| Moose as | Threat | Clear-load |
|---|---|---|
| Gwyllgi L6, Fire Fang (before) | x0.99 | x1.19 |
| Cavalier L6, Iron Lance | x0.94 | x1.16 |
| **Cavalier L6, Iron Lance, Forde's line** | **x0.99** | **x1.24** |

The third keeps ch05's threat where it was and makes the moose the force's third-heaviest unit
(12%), a real miniboss. The built ROM measures the same. Clear-load sits just under the band's
1.25 edge, so ch05 has little room left to grow harder. ch04 does not move: its moose is a
scripted neutral outside the force.

**Its art is unchanged; only the binding moved.** The Wyrdeer map sprite is its own 32x32 entry,
so the class does not size it, and its 32x480 moving sheet fits the Cavalier's layout as Lupin's
does. Its battle anim (Nicolas's three poses) binds through the Cavalier row, so sword, lance and
unarmed all draw the moose. It keeps the **beast cadence** (`cadence: beast`, Nicolas's
2026-08-15 call): the Cavalier row's own cadence is the Armor Knight's leap and blade whoosh.
Lupin never used it, since his pounce is imported and carries its own timing.

**What stops the class drifting again.** Movement tables come from a unit's class
(`inject.terrain.class_movement`), never from a hardcoded table name, so the routes the moose
walks are checked on the class it actually loads as. ch04 reads the moose's class from its YAML.
