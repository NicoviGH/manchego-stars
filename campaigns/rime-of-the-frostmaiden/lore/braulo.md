# Braulo — Lore & Flavor

> Narrative and flavor for Braulo. **Mechanics live in [`pcs/braulo.yaml`](../pcs/braulo.yaml)** —
> Braulo is a stock vanilla FE8 class with no per-character abilities. Everything below is
> story/flavor only: it does **not** drive gameplay. The ability "fantasies" are preserved here
> (migrated from pre-strip commit `e6cc7a6`) as inspiration for dialogue, sprite/palette work,
> and signature scripted moments — never as FE mechanics.

## Concept

- **Race:** Hermit Crab
- **D&D class:** Barbarian (Path of the Berserker)
- **Alignment:** neutral
- **Size/age:** medium, 40

## Personality

- **Personality:** Thrifty and driven — always looking for the better deal, the better shell.
- **Ideal:** The Next Shell. The best one is always just over the horizon.
- **Bond:** Dosh — wealth and profit above all else.
- **Flaw:** Greed

## Backstory

A travelling merchant from the ocean floor, searching the world for his next shell. Believes the perfect shell is always just over the horizon.

## Ability Fantasies (flavor only — not game mechanics)

These are the D&D abilities Braulo had on paper, kept as flavor names and story beats.
In-game Braulo is a plain FE8 class; none of these are implemented as skills, procs, or buffs.

### Rage

Market Rage — someone undercut his price and now Braulo is a frothing, claw-snapping wall of fury.

- *Former mechanic concept (now flavor):* Rage status (consumable/command): +might and +DEF (FE-native; no ×0.5 multiplier), for the combat phase

### Frenzy

Bargaining Frenzy — Braulo presses the deal so hard he gets a second swing in.

- *Former mechanic concept (now flavor):* while Rage is active, brave-weapon-style extra attack (exhaustion cost dropped per rules-mapping §F)

### Extra Attack

Double Deal — one motion, two strikes; Braulo never sells a single when he can sell a pair.

- *Former mechanic concept (now flavor):* brave-weapon-style second hit on every attack (vanilla FE doubling is separate)

### Shell Defense

Into the Shell — Braulo yanks himself inside his prize shell and waits out the storm.

- *Former mechanic concept (now flavor):* Guard-stance command: big +AC and save advantage, but MOV 0 and no counter until he emerges

### Relentless Rage

Won't Die Broke — Braulo refuses to fall while there's still a deal on the table.

- *Former mechanic concept (now flavor):* survive-at-1-HP proc while raging (Classic-mode safety net)

### Brutal Critical

Shell-Cracker — when Braulo connects clean, he splits the target like an oyster.

- *Former mechanic concept (now flavor):* passive: critical hits roll extra weapon dice

### Primal Champion

Apex Pagurian — the biggest crab in any sea, by sheer stubborn growth.

- *Former mechanic concept (now flavor):* capstone stat cap bump (STR/CON), already baked into his end-state scores

### Retaliation

Snapback — touch the crab, lose a finger; he counters the instant he's struck.

- *Former mechanic concept (now flavor):* extra counterattack proc when hit in melee (fires before the normal counter)

### Reckless Attack

All-In — Braulo swings for everything and doesn't care what hits back.

- *Former mechanic concept (now flavor):* toggle: +hit on his attacks this turn, but enemies get +hit vs him until his next turn

### Mindless Rage

Tunnel Vision — far too angry about the markup to be scared or charmed.

- *Former mechanic concept (now flavor):* while raging, immune to charm/fear status

### Danger Sense

Crab Instinct — a lifetime of dodging predators on the seafloor; he feels the blow coming.

- *Former mechanic concept (now flavor):* +avoid / advantage on DEX saves vs AoE he can see (breath weapons, spells)

### Feral Instinct

First to the Bargain — Braulo's never caught flat-footed when there's profit to grab.

- *Former mechanic concept (now flavor):* deploys with an initiative/turn-order bonus; can't be surprised

## Signature gear (flavor / post-MVP)

In the MVP, Braulo carries stock FE weapons (Iron Axe, Hand Axe). His named gear returns
post-MVP as story-progression items, each mapped to an FE equivalent — the look (anchor/shell)
rides on the sprite art, not the item name:

- **Ole Shipwrecker** — his prized personal anchor-axe → **Killer Axe** (FE-equivalent, per Nicolas). The original; in-campaign he lost it and got a replacement ("Nu' Shipwrecker") — same weapon. Reclaimed at the Ch 10 frozen wreck (see `docs/roadmap.md`).
- **Trident** — his thrown weapon → a Hand-Axe-class throwing weapon.
