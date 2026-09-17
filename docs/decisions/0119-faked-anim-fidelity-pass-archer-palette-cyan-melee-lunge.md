---
id: 119
title: "Faked anim fidelity pass: archer-palette cyan, melee lunge, record-capture (#65 M-B)"
date: "2026-06-26"
section: "Art & Audio"
issues: [65]
---

# Faked anim fidelity pass: archer-palette cyan, melee lunge, record-capture (#65 M-B)

Three faults surfaced when polishing RBG + braulo end-to-end on the `_u25` path; all fixed
campaign-agnostically.
- **RBG "cyan" was an engine bug, not the art.** `GetBanimPalette` (`banim-ekrmain.c`) loads a
  combatant's palette from `banim_data[GetBanimPalette(banim_id)]`, but for `CLASS_ARCHER/_F/
  SNIPER/_F` it returns a hardcoded canonical **bow** palette row (0x25/0x27/0x29/0x2B) *regardless
  of `banim_id`* — a vanilla palette-share that is only correct for the stock bow anim. RBG deploys
  as a real `CLASS_ARCHER` (the whole point of `_u25`: no class slot), so his custom appended banim's
  tiles got painted with the vanilla archer palette → cyan. M-A's class-clone dodged it by deploying
  as a ballista clone, not `CLASS_ARCHER`. Fix: `engine_hooks._patch_banim_palette_custom_guard`
  short-circuits `GetBanimPalette` to return `banim_id` for any **custom (appended) banim** (id ≥ the
  vanilla banim count, derived at inject time), before the vanilla switch — vanilla units byte-for-byte
  unchanged. Guarded by `check_engine_guards_present`; TDD'd. RBG also **rescaled to vanilla** (body 38).
- **Melee LUNGE lives in the frame OAM, not the script.** The Pirate's forward step is its frames'
  dx sweep (~0 → −45 → 0), but a faked anim anchors all frames to one feet point, so braulo swung on
  the spot. `build_battle_anim` now bakes a per-beat forward OAM step (`MELEE_LUNGE_DX`) for melee, and
  `_melee_mode_body` **holds** the lunged peak through the hit then eases back over a 6-tick return —
  matching the Pirate's frames 2/3/5 (forward) + 7/8 (return). DEFERRED: the white swing-arc
  weapon-trail (**#91**).
- **`recordanim` capture caught the quote, not the attack.** `captureAttack` counted entering
  `gProc_ekrBattle` as success, but a talky foe's in-battle quote (`ProcScr_BattleEventEngine`) holds
  for A and ate the budget before the swing drew. Fix: tap A while the quote box is up, screenshot
  only quote-less frames, and key the verdict on capturing real anim frames (`sawAnim`).
_Decided: 2026-06-26_
