---
id: 451
title: "A wait holding the weapon whose counter spares a recruit"
date: "2026-11-22"
section: "Combat System"
issues: [730, 699, 510]
---

# A wait holding the weapon whose counter spares a recruit

**Decided (#730 fix 1), #510 step 9.** Adds acts only; no scoring change, no new weight. Part of
#699's cause 2c.

**The gap.** In the recorded vanilla lap pool, 104 of 159 deaths of a recruit-to-be were our own
counter in the enemy phase (Amelia, charId 18: 49 of 51). In 52 of the 104 the chosen plan was
admitted, priced the recruit's death at 0.4 to 1.0, and no considered plan forfeited less. The
cause is in the acts: the game counters with the first usable weapon in the bag
(`GetUnitEquippedWeapon`), and no wait act carried a weapon slot except the boss bait
(`Bot.baitAt`, ADR for #641). The mend loop's comment promised a wait "holding no weapon that
answers it"; that act did not exist.

**What changed.** `Bot.candidates` offers, per unit, a `gentle` wait (`sparingWaits`): for each
tile a wait of the unit already ends on where a recruit (`ctx.recruits`) can strike it, the same
wait holding the weapon in another bag slot, when that weapon's counter fells the recruits that
reach the tile less than the weapon held now (`counterDist` against the recruit's HP, summed;
the least wins, the lower slot on a tie). A weapon that cannot answer the recruit's strike (a
bow against a melee strike) fells 0, so it is the no-counter choice. The game never lets a unit
hold no weapon: FE8 has no unequip, so a unit with one usable weapon has no such wait.

It reuses the bait's whole path: the act's `slot` and `slotKey` (its key's `#slot`), `exposed`
reads the unit's exposure with that weapon held, the judged phase arms the unit with it
(`planned.slot`), and the harness equips it before the Wait (`INSPECT.equipSlot`, the same
`M.equip`, which already `keep16`s the bag). No new write to unit memory, so no new `keep16`.

The planner's per-unit cut keeps every `gentle` act (`menusOf`): its own score never sees the
forfeit it avoids, so it could rank below `PER_UNIT` and never be judged (#722's lesson). The
mend's `tries(p)` for a recruit then finds it on the menu of the unit the recruit strikes; the
stale comment there now says so.

**What it does not do.** It does not price anything new; the chosen plan is still whichever the
judged phase ranks first. It does not cover a unit that attacks and is then struck (its counter
weapon is the attack's), a recruit out of every tile's reach (that is moving away), or a recruit
with no blue talker yet (#730 fix 2, a new price: Nicolas's call).

**Proof.** `test_bot.lua`: a unit whose only tile is in the recruit's reach, first weapon fells
it, second spares it. On main the plan forfeits the recruit; now the menu offers the wait with the
sparing slot, it is the plan played with no forfeit and a recruit death of about nothing, at
`PER_UNIT` 4 and at 0 (the cut test fails without the cut's `gentle` line).
