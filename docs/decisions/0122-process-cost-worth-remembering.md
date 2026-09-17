---
id: 122
title: "Process cost worth remembering (see decisions Operational Gotchas + [[feedback_check_precedent_before_inventing]]):"
date: "2026-07-18"
section: "Art & Audio"
issues: [190]
---

# Process cost worth remembering (see decisions Operational Gotchas + [[feedback_check_precedent_before_inventing]]):

a `recordanim` capture interleaves MULTIPLE combat beats (attack 1 · enemy counter/dodge · attack 2 on a
double) — I burned many rebuilds analyzing the WRONG frames (Pinky's 2nd-attack swoop mislabeled as the
dodge). ALWAYS identify which beat a frame window is FIRST (attacker moves toward the foe; defender dodges
away), and render an UNCROPPED full-combat GIF for review so cropping can't mislead.

Tuned entirely on the TESTCH `recordanim` capture (class 0x48); `PT_CHAR=pinky`. No lance is drawn — a
body-slam dive, matching his lanceless map sprite.
_Decided: 2026-07-18 (Pinky, PR #190)_

**Baxby's axe-beak charge, and the SECOND palette path that repaints a custom anim (#206)**
Baxby is the other half of #206: same defect (a giant bird rendering as a man on a horse), same
class (`CLASS_CAVALIER`, ridden so the mount can BE the unit), same imported path — his attack is
travel, so `descale_battleframe`'s pinned feet are wrong for him. What was NOT the same is that his
sprite came out **correctly drawn and completely miscoloured**, and finding out why took the whole
session.

- **The cause is FE8's per-CHARACTER battle palette, and it is keyed on character × CLASS.**
  `gAnimCharaPalConfig[pid][i] == jid` sets `gBanimUniquePal[pos]`, and `UpdateBanimFrame` then
  LZ77s `character_battle_animation_palette_table[...]` **over** the palette just loaded from the
  unit's own `banim_data` row. Vanilla wants that (Seth's personal Paladin colours). We do not: our
  cast wears vanilla character SLOTS, so **Baxby rides FORDE — whose row is
  `[CLASS_CAVALIER -> 0x57]` — and Baxby deploys AS a Cavalier.** Exact match, so the engine threw
  away his axe-beak palette and painted the bird in Forde's green.
- **Lupin escaped by pure luck, which is why this survived his PR.** He rides Duessel, whose
  personal palettes are all magic classes (Shaman/Druid/Summoner), so his Cavalier deployment never
  matched. The hazard is a property of the SLOT, not of the art or the pipeline.
- **This is the SECOND such path.** `_patch_banim_palette_custom_guard` (the RBG cyan fix) already
  covers the CLASS-keyed redirect in `GetBanimPalette`. This one is CHARACTER-keyed and lives in a
  different function (`banim-ekrbattleintro.c`), so the first guard could never have caught it.
  `_patch_banim_unique_pal_custom_guard` closes it the same campaign-agnostic way: the character
  palette may apply only to a VANILLA banim id (`gBanimIdx[pos] < first_custom_banim`), on both
  sides of the screen. It names no character — the condition is "is this an appended banim", not
  "is this Forde" — and vanilla units are byte-unchanged. Guarded by `check_engine_guards_present`.
- **Every future custom-anim unit is now covered**, which matters for #25: Basil and Sahnar's slots
  would each have needed this checked by hand otherwise.
