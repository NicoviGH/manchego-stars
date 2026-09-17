---
id: 127
title: "A caster clones from its OWN class; the spell tint is the flavour lever, not the donor (Rootis, #65)"
date: "2026-07-17"
section: "Art & Audio"
issues: [65]
---

# A caster clones from its OWN class; the spell tint is the flavour lever, not the donor (Rootis, #65)

Rootis (frost snowman-mage) is the first faked caster whose element is flavour-only. Two decisions
generalise from him:
- **`clone_from` = the unit's own vanilla class, chosen by weapon type — not "any magic donor".** The
  private AnimConf repoints the entry matching the donor's `wtype`, so the custom anim only binds to
  the weapon the unit actually wields. Rootis is a **Mage** (ITYPE_ANIMA), so his donor is the new
  `mage` (`CLASS_MAGE`, `0x0100 | ITYPE_ANIMA`) — **not** the shaman (ITYPE_DARK) that Marty/Meesmickle
  use. A shaman donor would repoint the DARK slot and leave his Anima casts on the vanilla mage anim.
  The `magic` motion cadence (settle → charge-hold → release) is donor-agnostic and shared. General
  rule for the next caster: pick the `BANIM_DONORS` entry whose `wtype` matches the tome the unit wields.
- **Ice/frost element = the `spell_palette_tint`, layered on the vanilla spell — do NOT swap the spell
  proc.** FE8 ships a real ice anima spell (Fimbulvetr), but wiring a per-character spell-anim *swap*
  would be new machinery and its full-screen blizzard is oversized for a basic tome. Instead Rootis
  keeps the vanilla red Fire projectile (his tome is mechanically Fire) and a `color: blue` tint
  recolours it icy-blue in-engine — the same `BanimSpellPaletteCopy` seam as Marty's green, extended
  with `BANIM_SPELL_TINT_BLUE` + `BanimSpellTintBlue` (blue channel dominant, green kept mid so it reads
  as bright cyan-white frost, not navy). The enum is honest and the recolour dispatches on the tint id;
  vanilla and unconfigured casters stay byte-vanilla. **Review order matters:** the regular (untinted)
  spell was captured in-engine and approved *before* the tint was added — never bundle the colour change
  with the first anim review (you can't tell a wrong pose from a wrong colour if both land at once).
- **Descale palette: reserve small accent colours in the ADAPTIVE path too.** Rootis is near-monochrome
  blue/white, so his orange carrot nose (a handful of px) lost the median-cut frequency contest and
  quantised out. `descale_battleframe.descale` now threads `--reserve` through to `_shared_palette`
  (it previously only reached the locked-layout path), so `--reserve 240,110,55` forces the carrot into
  the ≤15-colour palette. Row-1 look (thin outline, no sharpen, `--body 40`) chosen over the heavier
  full-outline default. Recipe recorded in `rootis.yaml`.
_Decided: 2026-07-17 (Rootis frost-mage anim, `feat/rootis-battle-anim`; in-engine `recordanim` gate)_
