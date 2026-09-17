---
id: 120
title: "Faked battle-animation review loop: donor visuals, game-valid previews, and archive cost (#65)"
date: "2026-07-14"
section: "Art & Audio"
issues: [65, 163]
---

# Faked battle-animation review loop: donor visuals, game-valid previews, and archive cost (#65)

Meesmickle exposed four rules that apply to every remaining custom battle animation.
- **Study the donor's pictures as well as its commands.** A `motion.s` command can start an engine
  effect, play audio, or merely advance actor frames. The vanilla Shaman's visible charge is not a
  reusable Flux effect: it is drawn across roughly 35 Shaman actor frames between
  `banim_code_sound_elec_charge` and `banim_code_call_spell_anim`. A three-pose replacement can copy
  that timing and sound but cannot reproduce the visual charge unless the supplied art includes a
  charge loop. Meesmickle deliberately ships with a held wind-up pose plus the vanilla charge sound
  and Flux release; that limitation was accepted after an in-engine comparison. Future magic donors
  must classify every visible beat as actor art versus engine effect before wiring begins.
- **"Least processed" still means game-valid.** The first review image comes from cleaned alpha art,
  one shared geometry transform, hard alpha, and the final shared OBJ palette (at most 15 visible
  colours). Sharpening, outline growth, and pixel touch-up are later A/B passes. Never ask for visual
  approval on a full-colour intermediate that cannot be packed into the GBA.
- **OBJ palette index 0 is transparency, even when its RGB is black.** Opaque black therefore needs
  a duplicate nonzero palette entry; mapping it to index 0 creates holes that a desktop PNG preview
  will not reveal. Palette tests pin this, and the accepted candidate still requires a real mGBA
  capture before merge.
- **Batch art decisions before the archive rebuild.** `data_banim.o` is produced by a serial linker
  that walks all 1,507 battle-animation inputs, so a full repack takes minutes. Direct palette-valid
  previews are the fast iteration loop; pay the archive rebuild only after a candidate is selected,
  then use `recordanim` as the final visual gate. Do not describe the full repack as a normal
  per-preview step or start it before the user approves the packed-pixel preview.
_Decided: 2026-07-14 (Meesmickle review + in-engine close-out, PR #163)_
