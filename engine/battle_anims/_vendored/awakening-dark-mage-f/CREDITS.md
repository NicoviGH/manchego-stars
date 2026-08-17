F2U/F2E

Still by BatimatheBat.

Animation by Leo_Link.

Vendored from Klokinator/FE-Repo →
`Battle Animations/Magi - Dark-Type/[Custom DM]  Awakening Dark Mage [F] by BatimatheBat/6. Magic (Plus Sfx)`

For Ravisin, ch05's frost-druid boss (#25). Picked by Nicolas 2026-08-16 against her BUST:
loose auburn hair and no hood, and the same source game as the portrait (Garytop's Aversa,
FE13). The two rejected alternates and why: `[Custom Magi] [F] Witch {Pikmin}` (auburn hair
too, but a pointed hat her bust has not) and `[T2 Druid-Base] Vanilla FE6 [F]` (her exact
class tier, but fully hooded, so the face never shows).

There is NO Aversa battle animation in the FE-Repo -- the whole 2006-entry index was searched
(`file_urls.json` at the repo root is a complete file listing and the fast way to search it).
Her portrait is there, and an "Aversa's Night" item icon; no anim. So this is a stand-in
chosen to match the bust, not a matching rip.

Bind it PER-CHARACTER (`gUnitSpecificBanimConfigs` + `_u25`), never at `CLASS_DRUID`: the frost
druids are a recurring faction (`lore/frostmaiden-voices.md`), Sephek's defeat "only scatters
him", and a class binding would dress every future one of them as this woman. "She is the only
druid today" is the wrong test -- `decisions.md`, the moose ADR.

The ally-blue palette is the anim's native one and is NOT hers: matching it to the bust
(auburn hair, frost-pale skin, black feather mantle) is part of the wiring task, the way
`recolor: enemy_red` is for the kobolds.
