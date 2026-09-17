---
id: 52
title: "Ch3 \"The Termalaine Mine\" — four sanctioned deviations from strict per-chapter parity."
date: "2026-06-26"
section: "Combat System"
issues: []
---

# Ch3 "The Termalaine Mine" — four sanctioned deviations from strict per-chapter parity.

ch03 reskins vanilla FE8 Ch3 "The Bandits of Borgo" (Seize big-battle; the game's first chests +
first thief). Roster + reward footprints mirror it 1:1, with four deliberate, parity-neutral
deviations (Nicolas-directed):
1. **The boss is a real monster.** A grell IS a floating tentacled eye-aberration, so the boss slot
   (vanilla Bazba, Brigand L6) becomes a **CLASS_MOGALL** with the Evil Eye — NOT a frailty cheat.
   A same-level mogall is far weaker than a Brigand, so it carries a **level bump (L12)** to hold
   Bazba's pressure. Verified on `make difficulty CH=ch03`: clear-load ×0.99, threat ×1.12 (within
   band; the magic Evil Eye vs our low-RES melee runs intentionally hot). Parity is *measured*, not
   assumed — this is exactly the wiggle-room the difficulty engine exists to provide.
2. **Monster foe-type debut moves ch04 → ch03.** The grell is chronologically the party's first
   monster. The `introduces: monsters` ledger entry moved to ch03 (out of ch04, which stays a
   monster/fog set-piece but is no longer the *first*). Monster-effective GEAR stays deferred (none
   on the reward curve yet).
3. **The ch02↔ch03 gem/hand-axe swap.** Vanilla's single early gem (the Ch2 Red Gem) is *lent
   forward* to ch03's gem mine (it's literally a famous tourmaline mine; Trex the thief opens the
   seam). To keep wealth on-curve, vanilla Ch3's Hand Axe chest moves *back* to ch02's chwinga-mote
   gift. Net result: total wealth AND the exact item set across ch02+ch03 are identical to vanilla —
   only the chapter each of the two items appears in is swapped. (We considered keeping the gem at
   ch02 for strict per-chapter parity; chose the swap for the gem-mine payoff, since it's net-neutral
   and the Ch2 gem money is meant for world-map shopping after the chapter anyway, not the thin Ch2 armory.)
4. **Objective is Defeat Boss, not Seize (added 2026-07-06, Nicolas).** Vanilla Ch3 wins by seizing
   Bazba's tile (14,1); ours wins by **killing the grell** on that tile. Both require defeating the
   boss — Defeat Boss just drops the extra "step onto the tile" beat, which reads truer for slaying an
   aberration than capturing a throne. Mechanically near-identical (the grell sits on 14,1 regardless);
   the parity band is unchanged. (The ch03 YAML `objective.type` and `win_condition` reflect this.)
_Decided: 2026-06-26 (Nicolas + CLAUDE, Ch3 design-lock session; grounded in the FE8 decomp, the DM
notes, and the Frostmaiden book "A Beautiful Mine" pp.93–96) — item 4 added 2026-07-06. FE8 has no
multi-level maps, so the book's 3-level mine is authored as one flat walled interior (rooms via
TERRAIN_DOOR + one TILECHANGE), not a verticality gimmick — the doors make the thief (Trex) matter._

**Ch3 dialogue re-pass on the 2026-07-06 reframe (2026-07-09, Nicolas + CLAUDE).** Three fiction
changes settled while re-passing the opening + RBG-execution/Trex-recruit beats (roster/positions
unchanged; still plays like Bandits of Borgo): (a) **Trex's cosmetic wings are dropped** — the
table gave him self-fashioned wings, but they're not in his FE portrait or map sprite, so they're
cut from the fiction (his hook was always the self-taught eloquence, not the costume). This retires
`lore/trex.md`'s wings content and Meesmickle's wings-based ending button; it also moots the "wings
pixel edit" art task on #23. (b) **Pinky's shaft-scout folds into the opening cutscene** — as the
army's flier he does a flyover recon from the mine mouth; the grell is now **visible at (14,1) from
turn 1** (Bazba-style), so the old standalone `shaft_mouth_reached` beat, its scripted grell spawn,
and its "open the way down" map-change are all retired (the deep workings are pathable from the
start). The RBG/Pinky Wish-seed two-hander is preserved intact. (c) **Canon name fix:** the town
speaker is **Oarus Masthew** (book pp.93–94), not "Maxol" — corrected in the crier + ending lines.
