---
id: 111
title: "Distribution: private, pre-patched `.gba` shared with the 7 players (no public ROM or patch)"
date: "2026-06-20"
section: "Distribution & Scope"
issues: [59]
---

# Distribution: private, pre-patched `.gba` shared with the 7 players (no public ROM or patch)

Players get a pre-patched `.gba` via a private link Nicolas shares — no public hosting of the
copyrighted ROM. The README + `docs/playtesters.md` are the tester landing page (install + carry
your save), pointing at that private link. A **public `.bps` patch was evaluated and rejected**
(#59): the `fireemblem8u` decomp build on our toolchain is **non-matching** — it does not
byte-reproduce retail FE8 (recompiled code + re-compressed graphics differ across the ROM), so a
patch from a tester's retail ROM to our build is ~ROM-sized (measured **11.4 MB, 71% of the ROM**),
a pointless download that also effectively republishes the game. A small public patch would first
require a byte-matching build (a separate toolchain effort, not planned). The pure-Python BPS
encoder (`tools/make_bps.py`, tested) stays in the repo for that future, or for small deltas between
our own consecutive builds. Non-SRD content (Artificer, Circle of Spores, homebrew races) is used
freely for this private distribution.
_Decided: May 2026; reaffirmed private-only 2026-06-20 after the public-`.bps` evaluation (#59)_

**Physical cartridges are the intended final hand-off — parked until the ROM is done (#228, 2026-08-05).**
Nicolas plans to give each player a real GBA cartridge rather than only the private `.gba` link (repro shells from
InsideGadgets). This does not change the decision above — a cart is the same private distribution in a nicer wrapper,
one per player, handed over directly. Requirements and the hardware link live on **#228**; nothing is decidable until
there is a finished ROM to flash, so it stays parked rather than scoped. The one non-obvious requirement worth
recording here: the cart must have **working SRAM save hardware** (FE8 saves to SRAM), and one test cart must be
flashed and played on real hardware before doing the rest — real-hardware timing is not mGBA, and our custom battle
anims and palette work are exactly what can differ.
