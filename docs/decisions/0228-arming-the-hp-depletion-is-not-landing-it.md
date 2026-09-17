---
id: 228
title: "Arming the HP depletion is not LANDING it"
date: "2026-08-08"
section: "Operational Gotchas (durable)"
issues: [25]
---

# Arming the HP depletion is not LANDING it

#24/#201 established that an imported mode which swings (C03) must ARM the depletion (C04/C05),
because the opponent's dodge mode waits bare on C01. Sahnar's Specter armed correctly and still
soft-locked combat: its mode 1 is `C03 C07 C04 ... C01` with **no hit code**, so it waits on a
depletion nothing ever started. The battle parks in `ekrBattleInRoundIdle` and every proc freezes.
Vanilla's own `banim_myrm_sw1` is the reference shape: `prepare_hp_deplete -> hit_normal ->
wait_hp_deplete`.

**Why it survived a green capture, a green gate and a review.** FE8 resolves damage in DATA
regardless of the animation — the foe dies, the HP bar is right, every frame looks correct, and
the hang only appears on the NEXT input. A one-round capture never asks for a next input. It took
filming FOUR rounds, then a control run on a known-good unit (Braulo 2/2, Sahnar dead at round 2),
to separate "my capture loop is wrong" from "this animation is broken".

**Mode 12 is exempt, and that exemption is the load-bearing part.** Slot 12 is `attack_miss`
(`ref_to_battleframe._MODE_ORDER`): armed-but-hitless by design, keeping C04 precisely so the
opponent's C01 still returns. Every anim we ship — Pinky, Lupin, Baxby, the wildling and
lizardzerker reskins — is shaped that way and correct to be. The first version of this rule
rejected all of them, and "fixed" Sahnar's mode 12 into a bug. **When a new lint fires on most of
the existing corpus, the lint is the thing that is wrong.** `test_every_shipped_anim_passes_the_
arming_rules` now runs the rule over every committed `.txt` so the next tightening is measured
against real assets, not fixtures.
