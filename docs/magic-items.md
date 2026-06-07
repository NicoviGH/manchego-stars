# PC Magic Items — Catalog & FE Conversions (first pass)

> **Status: DRAFT for review.** Pulled from the PC D&D Beyond character-sheet PDFs
> (`References/PCs/*.pdf`) on 2026-05-28. The sheets list item *names* but not full rules
> text, so standard DMG items are described from the SRD/DMG and **homebrew items are flagged
> `[VERIFY]`** — need rules text from the sheet or DM before finalizing.
>
> **Gating:** these are end-state campaign rewards, flavored onto vanilla FE items. Almost all
> are **post-MVP** (Ch 9–20) acquisitions; the **MVP (Prologue + Ch 1–8)** keeps the simple
> starting loadouts already in the PC YAMLs (see the campaign-structure memory).
>
> **Process:** review/confirm these, then slot the chosen ones into the PC YAMLs as
> chapter-gated inventory. This doc is the holding pen so the YAMLs stay clean meanwhile.

---

## Marty — Druid (Spores)
| Item | What it is (5e) | FE conversion idea | Gate |
|---|---|---|---|
| Blood Fury Tattoo | Tasha's magic tattoo — extra damage on hit, reaction attack when hurt | Passive: small bonus dmg; capped reaction counter | post-MVP |
| Masque Charm | `[VERIFY]` homebrew — likely a charm/disguise trinket | TBD on sheet detail | post-MVP |
| Witherbloom Primer | Strixhaven spellbook — grants a few extra prepared spells | Grants 1–2 extra tome slots | post-MVP |
| Leather armor, Ink | mundane | flavor / none | — |

## Meesmickle — Warlock (Fiend), Vampire Tabaxi
| Item | What it is (5e) | FE conversion idea | Gate |
|---|---|---|---|
| Javelin of Lightning | Thrown; 4d6 lightning line, 1/day recharge | Thrown weapon, 1/chapter 4d6 lightning AoE line | mid-MVP ok (iconic) |
| Rod of the Pact Keeper | +1/+2 spell atk & save DC; regain a Pact slot 1/long rest | +hit/+might to tomes (no save DCs in vanilla FE); refill 1 Pact use/chapter | post-MVP |
| Periapt of Wound Closure | Auto-stabilize; double HP from healing | Classic-mode safety + heal-received bonus | post-MVP |

## Prof. RBG — Artificer (Artillerist), Underfolk
| Item | What it is (5e) | FE conversion idea | Gate |
|---|---|---|---|
| Luck E. Cheese | `[VERIFY]` homebrew weapon — finesse 1d6+5, **2 Wish charges** | Signature sidearm; Wish charges = 2 super-rare game-changer uses (define carefully) | endgame |
| Boots of Speed | Bonus action: double speed | +MOV toggle, capped turns/chapter | post-MVP |
| Dimensional Shackles | Bind an extraplanar creature | Bind/root a summoned/extraplanar enemy | post-MVP |
| Hat of Disguise | Disguise self at will | flavor / infiltration event use | post-MVP |
| Pipes of the Sewers | Summon swarms of rats | Spawn weak temporary ally swarm | post-MVP |

## Rootis — Sorcerer (Draconic White), Snowperson
| Item | What it is (5e) | FE conversion idea | Gate |
|---|---|---|---|
| Staff of Power | +2 AC/saves/atk; stores spells; 20 charges; retributive strike | Signature staff: +stats while held; charge-spend nukes; 1-time retributive blast | post-MVP |
| Wand of Magic Detection | Detect magic 3/day | flavor / treasure-finding event | — |
| Potion of Healing ×2 | 2d4+2 heal | Vulnerary-equivalent consumable | Ch1 ok |

## Sclorbo — Bard (Lore), Chwinga
| Item | What it is (5e) | FE conversion idea | Gate |
|---|---|---|---|
| Horn of Blasting | Action: 5d6 thunder cone, 30 ft | 1/chapter thunder AoE cone | mid-MVP ok |
| Instrument of Illusions | Bardic instrument — minor illusions while playing | flavor; could tie to Dance animations | — |
| Sneezedrum | `[VERIFY]` homebrew instrument | TBD on sheet detail | post-MVP |
| Paper birds | `[VERIFY]` homebrew — likely message/scout trinket | flavor / scouting event | — |

## Braulo — Barbarian (Berserker), Hermit Crab
| Item | What it is (5e) | FE conversion idea | Gate |
|---|---|---|---|
| Ole Shipwrecker | Signature anchor-axe — 1d8/1d10+7 (sheet adds 10-ft reach) | Braulo's **prf Killer Axe** (high-crit; per `decisions.md` + `lore/braulo.md`). Same weapon as the D&D **"Nu' Shipwrecker"** — Ole is the original anchor he reclaims at the frozen wreck; "Nu'" was its in-campaign replacement. | **Ch 10** (looted at the frozen wreck — `roadmap.md` Act II) |
| Trident | Silvered, thrown 20/60, 1d8/1d10+6 | Thrown 2-range piercing | Ch1 |
| Deck of Many Things | chaos artifact (from a PC's sheet) | Likely a one-off scripted event item, not combat kit | `[VERIFY]` |

## Wolfram — Metallurgist (Smith), Mineralscale Drakeborn
| Item | What it is (5e) | FE conversion idea | Gate |
|---|---|---|---|
| Warhammer ×2 | 1d8/1d10+5 bludgeoning | Standard bludgeoning weapon (already in YAML) | Ch1 |

---

## Open Questions for the Items Pass
1. **Luck E. Cheese's "2 Wish charges"** — what did the player actually do with Wish? This is the single most powerful thing in the party. Needs a deliberate FE design (a 2-use, scripted, very-rare effect — NOT a free-form wish in tactics combat).
2. Homebrew items flagged `[VERIFY]` — get rules text from the sheets/DM (Masque Charm, Sneezedrum, Paper birds).
3. Which items are *signature/iconic* (worth FE mechanics) vs. flavor-only (mention in dialogue, no mechanic)?
4. Deck of Many Things — scripted story beat or actual item? (Likely the former.)
