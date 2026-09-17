---
id: 219
title: "A battle anim carries FOUR palettes and the engine picks one; ours are four copies"
date: "2026-08-20"
section: "Operational Gotchas (durable)"
issues: [25]
---

# A battle anim carries FOUR palettes and the engine picks one; ours are four copies

Asked directly ("do the battle anims not get the red faction palette?") and worth writing down,
because the two halves of a reskin behave oppositely and the difference is invisible until a
creature is on screen twice.

- **A MAP sprite is recoloured by the ENGINE at runtime.** `ApplyUnitSpritePalettes` loads
  `unit_icon_pal_enemy` into the sprite's OBJ bank, so one sheet reads blue as an ally and red as
  a foe. This is why a vendored sheet's own colours barely matter — `inject_enemy_class_reskins`
  only has to remap it onto the base class's SMS palette.
- **A BATTLE anim is not.** `GetBanimFactionPalette` (`banim-ekrcmd.c:115`) maps the unit's
  faction to `BANIMPAL_BLUE/RED/GREEN/PURPLE` = 0..3, and that index is an OFFSET into the
  palette buffer (`gUnknown_08802B04 + gBanimFactionPal[side] * 0x10`). So an anim's `.agbpal` is
  **128 bytes — four 16-colour banks — and the engine SELECTS one.** It transforms nothing.

Vanilla ships four genuinely different banks: `banim_arcm_ar1.agbpal`'s blue bank holds
`(216,248,112)` where its red bank holds `(168,208,248)` in the same slot.

**Ours are 128 bytes with all four banks byte-identical.** `feditor_to_banim` imports the single
palette an FEditor script carries and replicates it, so a community anim renders in its native
colours on every side. That is not a bug — it is what `recolor: enemy_red` exists to correct, and
why the kobolds declare it while the PC cast does not.

**`enemy_red` is not always the right correction.** It keys on blue-dominant colours
(`b > r + 30 and b >= g`) to catch faction-swappable cloth, and ch05's skeletons have cool bluish
BONE highlights — applying it reddens the skeleton itself rather than its armour. Checked against
the imported palettes before shipping and rejected on the picture, the same call Ravisin's palette
records: `decisions.md` → "A vendored anim's palette is a BY-EYE call". ch05's four ship NATIVE,
so its risen guard wear blue armour in the close-up and take the engine's red only on the map.
The remedy if that ever bothers anyone is a hand-edited bank via `tools/banim_palette.py`, not a
blanket hue rule.

_Recorded: 2026-08-20 (Nicolas asked; the answer was not written down anywhere)._
