# Wolfram — Lore & Flavor

> Narrative and flavor for Wolfram. **Mechanics live in [`pcs/wolfram.yaml`](../pcs/wolfram.yaml)** —
> Wolfram is a stock vanilla FE8 class with no per-character abilities. Everything below is
> story/flavor only: it does **not** drive gameplay. The ability "fantasies" are preserved here
> (migrated from pre-strip commit `e6cc7a6`) as inspiration for dialogue, sprite/palette work,
> and signature scripted moments — never as FE mechanics.

## Concept

- **Race:** Mineralscale Drakeborn
- **D&D class:** Metallurgist (School of the Smith)
- **Alignment:** chaotic_good
- **Size/age:** medium, 40

**Appearance:** Gray skin, dark eyes, hairless. Scales of living metal.

**Patron:** METALLO

## Backstory

A scaleless Drakeborn, shamed by his people for lacking scales. While wandering, he found an alien meteorite ring in the earth. METALLO — a cosmic being trillions of years old, the first entity ever to create metal — spoke to him through it and named him The First Metallurgist. His scales grew back, forged from living metal. He now serves as METALLO's Avatar in the mortal world.

## Voice

At his core, a materials-science nerd: he can smell and taste the metals and ores
around him, and nothing lights him up like a new or rare one. Friendly, works well
with the whole party — but strong-willed, and he NEVER backs down from a fight.
METALLO is backstory, not a speech pattern. (Interview with Nicolas, 2026-06-10.)

**Diction rules**
- Geeks out about metal: identifies what's in the walls/weapons/ground unprompted
  ("Iron, mostly. A vein of silver behind it."), and gets visibly excited about
  anything rare. This is his curiosity hook in any new location.
- The senses come first: he smells or tastes metal before naming it. He also EATS
  metal, casually.
- METALLO is rarely invoked — no prophet-speak, no "METALLO wills it" tic. The avatar
  business is something he carries, not something he preaches.
- Friendly and cooperative in party scenes; no lone-wolf brooding despite the shame
  backstory.
- Strong-willed: intimidation gets answered with calm escalation, not words — see the
  calibration moment. When Braulo calls for a fight over a broken deal, Wolfram is
  already stepping forward (he fought at Bremen; he was not among the abstainers).

**Calibration moment (table-derived, paraphrased)**
- Bremen: Braulo starts the fight with the speaker, who tries to intimidate the
  party. Wolfram's whole response: he steps forward and takes a bite out of his axe.
  No line needed — write the moment, not a speech.
- Register target (new location): "Wait. *(sniffs)* That's not iron ore. I've never
  smelled this before. We're digging."

**Banned:** cult zealotry or constant METALLO invocations, backing down, brooding
loner behavior, hostility toward party members, cowardice, big intimidation speeches
(he demonstrates instead).

## Ability Fantasies (flavor only — not game mechanics)

These are the D&D abilities Wolfram had on paper, kept as flavor names and story beats.
In-game Wolfram is a plain FE8 class; none of these are implemented as skills, procs, or buffs.

### Forge

The First Forge — Wolfram reshapes living metal between battles, gifting his allies armor of his own scales.

- *Former mechanic concept (now flavor):* Preparation-screen command (like a portable armory): permanently buff one ally's gear

### Breath Weapon

Flamethrower — Wolfram's chest-vents flare and he spits a gout of forge-fire.

- *Former mechanic concept (now flavor):* ranged Lance attack (his Javelin), named 'fire breath' — element is flavor only

### Enhanced Darkvision

### Conjure Elemental

### Creation

### Imprisonment

### Feral Strike: Bite

Wolfram's iron jaws snap shut on a foe right after his weapon lands.

- *Former mechanic concept (now flavor):* passive follow-up: melee hits tack on a small bonus bludgeoning bite

### Feral Strike: Claws

A raking swipe of metal claws when he needs to tear rather than crush.

- *Former mechanic concept (now flavor):* adjacent claw attack option (slashing) — folds into his action per rules-mapping §B

### Armor Lock (Shield)

Armor Lock — Wolfram's plates slam together into a seamless shell the instant a blow lands.

- *Former mechanic concept (now flavor):* +AC reaction proc (Barrier-style) — powered by Arcane Charges

### Fire Resistance

Forged in fire — Wolfram's metal scales shrug off heat that would melt anyone else.

- *Former mechanic concept (now flavor):* flavor only — fire affinity is narrative, with no mechanical effect

### Recharge

Recharge — Wolfram channels Arcane Charges inward, re-forging his own dented plating and flesh.

- *Former mechanic concept (now flavor):* self-heal (Heal-staff effect on himself), powered by Arcane Charges

### Explosive Burst

Explosive Burst — Wolfram overloads his charge vents and hurls a bursting gout of forge-fire.

- *Former mechanic concept (now flavor):* ranged Lance attack (his Javelin), flavored as an explosive forge-fire burst

### Forge Expert

Forge Expert — Wolfram smiths sturdier plate, hardening his allies against harm.

- *Former mechanic concept (now flavor):* Forge upgrade tier: armor he forges also grants a flat +DEF bonus

### Blade Forge

Blade Forge — METALLO's craft extends to weapons; Wolfram tempers an ally's blade to bite deeper.

- *Former mechanic concept (now flavor):* Forge upgrade tier: can now upgrade weapons (+Might), not just armor

### Master of the Forge

Master of the Forge — Wolfram forges adamantine and mithral, the metals of legend.

- *Former mechanic concept (now flavor):* top-tier Forge: adamantine (negates enemy crits) / mithral (no weapon-weight SPD penalty)

## Signature gear (flavor / post-MVP)

MVP loadout is a stock Iron Lance + Javelin (the Javelin is the armored unit's ranged option).
His fire/forge identity rides on the sprite art, not the item names. Named gear, post-MVP:

- **Warhammer** — his heavy personal weapon → an FE Lance (tier TBD, post-MVP).

## §Battle-anim prompt pack (#65 — run in Gemini, edit-from-concept on `References/References/PCs/Wolfram full.png`, magenta #FF00FF bg)

_Moved here from `HANDOFF.md` 2026-07-02 — per-unit art briefs live with the unit._

Preamble (every pose): *"Redraw the referenced character as a full-body Fire Emblem: Sacred Stones GBA
battle sprite — flat cel shading, hard outlines, ≤16 flat colors, three-quarter side view facing right,
flat magenta (#FF00FF) background, no effects. SIMPLIFY for small-sprite readability like a vanilla FE8
sprite: bold chunky shapes, strong clear silhouette, minimal interior detail — drop the tiny rivets,
speckled scales and fine straps, and consolidate the ice-crystal clusters into just one or two bold
accents. Keep only what reads at ~50px tall: his grey metal-scaled body, beard and topknot, the warhammer,
and one bold crystal accent; keep his colors from the reference."*

- **ready** → `Pose: Ready — neutral standing guard, warhammer held at rest in both hands across the body.`
- **windup** → `Pose: Wind-up — coiled back on the rear foot, warhammer hauled high overhead, both arms cocked, knees bent, ready to strike.`
- **peak** → `Pose: Peak — lunging forward, warhammer swung all the way down to full arm extension at the point of impact, front foot planted forward, feet near the same ground spot.`

Tips: generate **ready first**, then make windup/peak **edits of that ready frame** so the simplified design
+ palette carry over. If Gemini won't drop detail, push the simplify clause harder ("flat, almost no
interior lines, think 16-bit"). Magenta or transparent bg both fine — Claude keys the magenta before descale.
