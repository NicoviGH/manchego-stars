---
id: 316
title: "Parity measures each force against the party that meets it"
date: "2026-10-02"
section: "Combat System"
issues: [430]
---

# Parity measures each force against the party that meets it

#430 step 2b, layer 1. The enemy-pressure ratio used to score both forces against one
invented swordsman (`YARDSTICK`). That read the weapon triangle from a sword's side only, had
one Res and one Spd breakpoint, and could not see the party at all. A chapter that copies its
twin's force read x1.00 whatever party walked in.

**The headline is (our force vs our arriving party) / (the twin's force vs vanilla's arriving
party),** threat and clear-load (`difficulty.chapter_matchup`). Each party is the one the exp
model says arrives (`exp_curve.entering`), over the dice-averaged careers (ADR 0311). Each
side fields its best `deploy_limit` units by `_best_field`'s rule and is normalised by its own
field. Vanilla's prologue fields two units and ours fielded eight, so dividing both by one
shared cap was wrong. A fixed-roster chapter fields its `player_units`: ch00's guests fight at
bare class base, because the prologue injector zeroes their lines and emits no `.autolevel`.

- **Threat** is each enemy's damage per round against the unit FE8's AI would attack, per
  unit fielded. `ai_target.py` ports `AiComputeCombatScore` (cp_battle.c) with its
  coefficient tables read from `cp_data.c`, and each unit's own combat-weight table comes
  from its AI bytes. The positional terms (friend zone, danger) are left out, so this models
  whom a unit attacks, not where it stands.
- **Clear-load** is the party-rounds the field needs to clear the force: per enemy, 1 / the
  field's combined kill rate. A member who cannot dent it adds no rate.
  `metric_rounds_to_kill`'s floor applies only when nobody fielded can dent it.
- **`YARDSTICK` stays** only for a twin off `VANILLA_CHAIN` (ch08 -> FE8 Ch13), whose party is
  not simulated. The row says so, as does a planned chapter's target.

**First reading** (authored table):

| ch | threat | clear-load | yardstick before |
|---|---|---|---|
| ch00 | x3.45 | x3.00 | x0.99 / x0.97 |
| ch01 | x1.06 | x1.36 | x0.89 / x0.97 |
| ch02 | x1.21 | x1.67 | x1.00 / x1.00 |
| ch03 | x0.87 | x1.25 | x1.02 / x1.00 |
| ch04 | x1.06 | x1.23 | x1.14 / x1.15 |
| ch05 | x1.00 | x1.30 | x1.04 / x1.05 |
| ch06 | x1.00 | x1.12 | x1.00 / x1.00 |

Two things drive the clear-load column, and step 3 separates them. Vanilla's field carries
Seth, and ADR 0042 chose no Seth-tier unit. Our party also runs behind vanilla's curve
(ADR 0295). ch00 is a different case: Scramsax is our Seth by design (its difficulty_note),
yet he fights at a bare Hero base (22 HP, 6 Pow, 8 Def) against Seth's 30/14/11.

**ch00, ch01 and ch02 are no longer `balance_locked`.** A chapter locks when its re-measure
holds parity (#430 step 6). Under this instrument none of the three does, and a lock on a
chapter the gate reads as off-parity would only turn CI red.

**Two tests changed meaning.** A mode read is no longer verdict-invariant. The party does not
shift with the mode, so a kill threshold or an AI target can flip, and ch04 on Difficult moves
threat by 0.21. The test now bounds the drift instead of pinning OK. ch05's "in band in every
mode" pinned a yardstick verdict, so it went. Ravisin's bar against Saar is still pinned.
