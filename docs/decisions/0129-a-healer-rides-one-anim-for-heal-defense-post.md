---
id: 129
title: "A HEALER (staff caster) rides ONE anim for heal + defense + post-promo attack — the last PC anim (Sclorbo, #191)"
date: "2026-07-19"
section: "Art & Audio"
issues: [191]
---

# A HEALER (staff caster) rides ONE anim for heal + defense + post-promo attack — the last PC anim (Sclorbo, #191)

Sclorbo is the army's first healer (Priest → Bishop) and the first non-attacker to animate. Four things
generalise (the reusable "healer donor" — Basil, #25, uses it too):
- **Donor = BISHOP, cloned, with BOTH the STAFF and LIGHT slots repointed to one custom animId.** The
  vanilla Bishop `AnimConf` is the only healer table carrying both a staff slot (defense + heal) AND a
  light slot (post-promotion attack); Priest's has no attack slot. `banim_clone_conf` clones on the first
  wtype then `banim_repoint_conf`s the rest — the existing #90 precedent, so `BANIM_DONORS` wtype may now
  be a **list**. Because `_u25` binds the same clone to BOTH promote states, one anim covers everything;
  `call_spell_anim` resolves heal-efx vs light-efx from the *equipped item* at cast time (staff → Heal,
  Light tome → Light), so the single staff-raise **cast pose serves both**.
- **Load-bearing decomp fact: restorative staves render the ARENA.** Heal/Mend/Physic/… play a real
  battle-anim cast (`StartSpellAnimHeal`, efx `0x26`); only Warp/Rescue/Torch/Unlock force the map
  (`banim-ekrbattleintro.c:1413`, efx `-2`). So the healer's cast pose is on-screen **every heal in the
  MVP**, not just after promotion — all three poses (idle / dodge / cast) matter pre-promo. Isolation is
  airtight: `GetBattleAnimationId_WithUnique` (`banim-ekrbattleintro.c:1492`) substitutes the private
  clone only when `_u25 != 0`, so no other Bishop/Sage/multi-weapon unit is touched.
- **Per-caster charge-flash WAVEFORM (extends #183).** The #183 kernel was a shared 3-throb pulse; a
  `u8 waveform` field on `gMSChargeFlashes` now selects it (`0` = pulse, `1` = build) against a second
  const LUT (`sMSChargeFlashBuild`, one slow raised-cosine swell). Sclorbo = cyan **build** on both his
  staff and light rows; Marty/Rootis/Meesmickle default to `0` and stay byte-identical. "Slow building
  glow, not pulses" was Nicolas's call, matched to his flame pigment.
- **Match a caster's own pigment with a DEDICATED tint, not a near neighbour.** The glow blends toward a
  flat BGR555 target so it hit the flame cyan `RGB(31,219,219)/0x6F63` immediately. The **spell tint** is a
  hue-*transform*, though: reusing Rootis's `BanimSpellTintBlue` (blue-channel-dominant) read as a deeper
  blue, so `BANIM_SPELL_TINT_CYAN` / `BanimSpellTintCyan` was added — red suppressed, green AND blue both
  pinned to the highlight — applied to staff + light. Accepted coverage gap (Nicolas): the heal's white
  "recovery poof" loads via a direct `SpellFx_RegisterBgPal` that bypasses the `OBJPAL_BANIM_SPELL` tint
  hook, so it stays white; the orb/sparkles/glow go cyan and carry the identity.
- **Descale facing: a multi-pose source sheet may not face one way.** Sclorbo's source idle + cast faced
  opposite his charge/dodge; `descale_battleframe`'s flip is uniform, so two of three landed backwards —
  visible only in-engine. Fix = mirror the odd source crops *before* descaling. Rule for the next
  multi-pose art: verify all poses share a facing, or pre-mirror the outliers.
- **The `recordanim` harness now captures non-attackers:** a staff-only unit dispatches to
  `captureHealerAnim` (drive Staff→Heal a wounded ally for the cast; sit adjacent to a foe + end turn for
  the dodge) instead of bailing. The custom-vs-vanilla side-by-side was produced by toggling the
  `battle_anim` block off + rebuilding (the ROM `_u25` is `const`, so it can't be poked at runtime).
_Decided: 2026-07-19 (Sclorbo healer anim, `feat/191-sclorbo-battle-anim`; TDD + in-engine `recordanim`
gate; glow/tint/facing GIF-reviewed and approved by Nicolas — "looks perfect")_
