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
tile a wait of the unit already ends on where our counter would fell a recruit (`ctx.recruits`;
the chance past `Goals.DUST`), the same wait holding another bag slot, when that weapon's cost is
less than the held one's: the recruits' chance to fall (`counterDist` against their HP, summed)
plus our unit's own chance to die there (`takenDist` against its HP; a weapon that spares the
recruit and gets the unit killed is no gain). The least cost wins per tile, and the best
`Bot.GENTLE` (2) over all tiles are offered, since each act the mend tries is a judged enemy phase.
A weapon that cannot answer the recruit's strike (a bow against a melee strike) fells 0, so it is
the no-counter choice. The game never lets a unit hold no weapon: FE8 has no unequip, so a unit
with one usable weapon has no such wait.

It shares the bait's owners: `counterOn` (the exposure read of a held weapon's counter) and
`waitHolding` (the act with its `slot` and `slotKey`). The judged phase arms the unit with the slot
(`planned.slot`) and the harness equips it before the Wait (`INSPECT.equipSlot`, the same
`M.equip`, which already `keep16`s the bag). No new write to unit memory, so no new `keep16`.
`botrun`'s `actOf` now records a wait's `slot`, so a trace shows the weapon a gentle wait equipped.

The planner's per-unit cut keeps every `gentle` act (`menusOf`): its own score never sees the
forfeit it avoids, so it could rank below `PER_UNIT` and never be judged (#722's lesson). The
mend's `tries(p)` for a recruit then finds it on the menu of the unit the recruit strikes; the
stale comment there now says so.

**What it does not do.** It prices nothing new; the chosen plan is whichever the judged phase ranks
first. The forfeit is yes or no, so a weapon that only lowers the recruit's chance to fall changes
no plan until it spares it. It does not cover a unit that has acted (it holds the weapon it
equipped; 46 of the 106 recorded recruit counter deaths were such units, the unit having acted
earlier in the turn), one that attacks and is then struck (its counter weapon is the attack's;
34), or one that uses an item (8), nor a recruit no talker can reach by its deadline (it has no
ledger row, so its death forfeits nothing: ADR 0450's reach read; #730 fix 2 is the price for
that, Nicolas's call). The weaker weapon stays at the bag's front after the wait (the game's
Equip moves it there); later turns read the real bag, so they price it as it is, but the unit
fights with it until something equips another.

**Proof.** `test_bot.lua`: a unit with four waits (three holds and a march) on a column in the
recruit's reach, first weapon fells it, the second spares it on one tile. On main the plan
forfeits the recruit; now the menu offers the wait with the sparing slot, it is the plan played with
no forfeit and a recruit death of about nothing, at `PER_UNIT` 3 (where only the cut's `gentle` line
keeps it) and at 0. A second scene: slot 2 spares the recruit but kills our unit, slot 3 spares it
and lives; only slot 3 is offered and played. The cap, and a unit that has acted, are tested too.
No emulator probe was added: the path from the act to the game (`equipSlot`, the Wait) is the
bait's (#641), unchanged here, and not separately run for a gentle wait; a probe is a scenario of
its own.
