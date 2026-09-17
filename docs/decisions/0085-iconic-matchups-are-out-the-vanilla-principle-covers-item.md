---
id: 85
title: "Iconic matchups are OUT — the vanilla principle covers item DATA, not just mechanisms (#8 reverted)."
date: "2026-07-02"
section: "Weapon & Magic Systems"
issues: [8]
---

# Iconic matchups are OUT — the vanilla principle covers item DATA, not just mechanisms (#8 reverted).

The #8 implementation (Fire/Elfire flagged `effective` vs the ice-monster classes, PR #114) used only
FE8's native effectiveness system — but Nicolas ruled (2026-07-02) that the vanilla-combat principle
extends to item *data*: stock weapons must behave exactly as a vanilla FE8 player expects, and vanilla
Fire/Elfire carry no effectiveness. The precise boundary (Nicolas, same day, sharpened once more when he
caught that even "personal bases/growths are ours" overstates it): **ALL mechanical data is vanilla —
class data verbatim, character data inherited from a class-matched vanilla DONOR, item data stock.**
`patch_character_data` copies each cast slot's growths and weapon ranks verbatim from its vanilla donor
(`GROWTH_DONOR`/`STAT_DONOR`) and lands its personal bases on the donor's own statline (an FE-strict unit
IS its donor mechanically — Rootis fights on Lute's Mage line, Wolfram on Gilliam's Knight line, renamed
and re-drawn; Baxby's YAML names Franz as his donor for when his wiring lands); enemy class clones
inherit the same way. What is genuinely ours: the donor/class *choice* per character, identity cosmetics
(names, portraits, sprites, dialogue), levels, roster composition, and placements. Nothing about a *class*
or a *stock item* changes — no custom classes, no stat/effectiveness/might edits to stock weapons. (The
YAML `fe_stats` mechanism CAN stack a deliberate divergence on the donor line; the FE-strict default is
divergence-free, and any future use of it is a per-unit balance decision, not a principle change.)
PR #114 was reverted wholesale (injector, campaign.yaml
`iconic_matchups:` block, elfire weapon model, class tags, tests, and its ADR); the 2026-05-28/06-04
"iconic matchups via effectiveness" carve-outs above are annotated superseded. Fire-vs-ice survives as
**flavor only** — item names, dialogue, and battle-anim art. Issue #8 closes as not-planned.
_Decided: 2026-07-02 (Nicolas; supersedes the 2026-05-28 iconic-matchup carve-out)_
