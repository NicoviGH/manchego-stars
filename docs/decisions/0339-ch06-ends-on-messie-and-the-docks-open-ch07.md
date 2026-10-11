---
id: 339
title: "ch06 ends on Messie; the docks and the rescued crews open ch07"
date: "2026-10-10"
section: "Story & Dialogue"
issues: [26, 27]
---

# ch06 ends on Messie; the docks and the rescued crews open ch07

Nicolas, 2026-10-10. ch06 closes on Messie's "Then I will come." It's a cliffhanger, and a
dock scene after it would let the tension out. ch06 has no `chapter_end` scene.

**What the ending does after his last line.**
- **It records which hulls came home.** Two permanent flags are set: `CH06_BOAT_SURVIVED_FLAGS`,
  0xFC for the east boat and 0xFD for the west, each gated on `CHECK_ALIVE` of its hull. They
  sit after the 0xF0–0xFB block `inject.decomp` already holds. Vanilla's highest permanent flag
  is 235.
- **It pays the save-both Orion's Bolt with no ceremony.** This is vanilla Ch6's own gate
  (`CHECK_ALIVE` on both), and the item popup is the only sign of it. Nicolas: the Bolt is not
  woven into the story.
- **It fades out on Into the Shadow of Victory,** vanilla Ch6's last cue. Victory and Legacy
  belonged to vanilla's thanks and story beats, and ch06 has neither after Messie.

**ch07 opens at Bremen's docks** with whoever came home: Grynsk, Tali, both, or only Messie.
It reads the two flags. The crews' thanks, Grynsk's word that the merfolk were never this bad,
and Tali's Elvish mutter (Rime p.31) all move there.

**ch07's map is vanilla Ch7's own layout** (`Ch7Map`, 20x22), reskinned, the same way ch02,
ch04 and ch05 reuse their twins:
- **The objective is Seize at (9,4),** with Dorbulgruf on it.
- **The moat is Bremen's harbour inlet.** Messie and the surviving boats sit on it as green
  units for the whole fight.
- **The two ballistae become Bremen's harpoon launchers,** at (2,10) and (17,8).
- **The two houses and the fog stay.**

Ch7 has no shoreline. The water is a moat around a walled keep, so "docks" is a reading of the
layout, not a literal one. The hall interior is the ending's backdrop, which is vanilla's own
outside-then-inside order (Ch7 fights outside, and Orson's scene plays inside).

**`gold_reward` is retired.** ADR 0092 already said chapters pay no clear stipend: gold comes
only from in-map sources. The field had survived from the pre-0092 skeleton (ch04 200, ch05 350,
ch06 400, ch07 450). It was never injected, and it only inflated the difficulty tool's economy
readout. It is gone from every chapter, the schema and that readout, and
`check.py DEAD_CONCEPTS` lists it. ch06's open question ("400 gold vs the unpaid 300 bounty")
dissolves: the crews pay in kind (the Antitoxin and the Bolt), and the Speaker's 300 stays
unpaid, which is ch07's argument.

**ch07 pays vanilla Ch8's war funds, 10,000 gold, in its ending** (Nicolas, 2026-10-10).
Vanilla's first scripted cash gift is Hayden's, at Ch8's ending. Our ch08 is the party's
capture, which has no patron to hand it over, so it moves up a chapter to the town the party
just took. Who hands it over is the ch07 dialogue pass's call. The pick is Messie, the new
Speaker, in Hayden's seat: a ruler funding the heroes.
