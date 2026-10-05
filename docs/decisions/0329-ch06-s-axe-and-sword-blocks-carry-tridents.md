---
id: 329
title: "ch06's axe and sword blocks carry tridents"
date: "2026-10-05"
section: "Combat System"
issues: [26]
---

# ch06's axe and sword blocks carry tridents

**ch06 re-classes five of vanilla Ch6's units so that its whole melee line fights with
tridents** (Nicolas, 2026-10-05). Vanilla's 3 Fighters become Cavaliers on N426's Shark Rider,
and its 2 Mercenaries become Soldiers in the Mermaid's spear line. Every other unit keeps
vanilla's class, and these five keep their levels, donors and AI.

Why: ch06's art is merfolk, and the only merfolk-world looks that exist are the Mermaid (lance,
bow, staff, magic) and the Shark Rider (trident). The axe and sword blocks had no look of their
own. A mounted shark on a Move-5 Fighter misleads the player about how far it reaches, and the
FE-Repo's only aquatic axe (Squidsmith) was rejected on sight.

Each weapon is swapped for its nearest lance by might: Poison Axe to Venin Lance (FE8's own
`ITEM_LANCE_VENIN`, Might 4, Hit 65, Weight 8), Steel Axe and Iron Blade to Steel Lance, and Iron
Axe and Iron Sword to Iron Lance. The Halberd and the Iron Blade stay in inventory as the last
item, so the drops are vanilla's.

Measured on instrument v2 before landing (`make difficulty CH=ch06`):

| | threat | clear-load | force vs the twin |
|---|---|---|---|
| before | x1.04 | x1.15 | x1.00 / x1.00 |
| Fighters to Cavaliers, Mercenaries to Soldiers (shipped) | x1.02 | x1.14 | x0.98 / x0.99 |
| all five to Soldiers (rejected) | x1.00 | x1.05 | x0.96 / x0.92 |

Both hold parity. The shipped option stays closest to vanilla's force. The role check is clean,
and the timeline does not move, because these units keep vanilla's hold-position AI. The mirror
falls from 27 of 27 bodies to 22 of 27, which is the declared divergence.

The re-class gave one unit a reach it did not have: as a Cavalier, `shark-rider-halberd` reaches
the east hull. `check_rescue_targets` caught it, and it takes the same AI_A_08 action as
`shark-rider-steel` beside it.
