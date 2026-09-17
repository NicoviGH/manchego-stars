---
id: 32
title: "The d20 flourish SHIPS (#11): a gold nat-20 pops at the crit flash's teardown."
date: "2026-07-02"
section: "Combat System"
issues: [11]
---

# The d20 flourish SHIPS (#11): a gold nat-20 pops at the crit flash's teardown.

Implementation seam (decomp-traced): FE8 rules a round a crit in `banim-battleparse.c`
(BATTLE_HIT_ATTR_CRIT → the crit anim modes); the C08 anim command fires the white
crit flash (`ProcScr_efxCriricalEffect*`, `banim-efxhit.c`) and never blocks the script,
and the flash's BG proc tears BG1 down after 17 frames. The hook
(`engine_hooks._inject_crit_d20_flourish`, guarded in `check_engine_guards_present`)
draws the die AT that teardown — **proc-less by design** (review-hardened): registered
once, then the vanilla effect lifecycle owns BG1 (a successor effect — a brave second
hit, a magic counter's spell background — draws over it; the scene exit resets it), so
nothing of ours can blank a newcomer's tilemap later. Covers BOTH crit-flash teardowns
(plain + pierce); Silencer is deliberately excluded — it has its own distinctive Chill
flourish, and no MVP cast member can Silencer. Neither the flash nor combat pacing
changes; FE crit math stays the sole trigger. The die is a centered HUD overlay copied
through the non-mirrored tilemap path (attacker side never mirrors the "20").
**Engine/content split:** the hook is campaign-
agnostic; the ART is the campaign's (`battle_anims/d20-crit.png`, PIL-authored gold d20)
— no asset, no flourish, pure vanilla crits. Asset pipeline: PNG → 4bpp sheet (tile 0
blank) + 16-color pal + 30×20 TSA, wrapped in stored-form GBA LZ77 (literal-only blocks
— always-valid input for `LZ77UnCompWram`, no compressor to vendor), incbin'd into
`data/data_banim.s`. `test_crit_flourish.py` decodes the injected bytes back and pins
them pixel-exact against the source PNG; the static preview Nicolas reviews is
`docs/demo/d20-crit-flourish-preview.png` (rendered FROM the injected bytes). Deferred:
map-battle (no-anim) crits — a different rendering path (`mapanim_spellassoc.c` MU
flash); and in-emulator motion review (`recordanim` on a crit) at the next capture
session.
_Decided: 2026-07-02 (CLAUDE; decomp-traced; closes #11's anim-mode scope)_
