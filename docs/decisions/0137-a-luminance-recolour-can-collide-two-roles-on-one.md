---
id: 137
title: "A luminance recolour can collide two ROLES on one index — check the roles, not just the ramp (#24)."
date: "2026-06-16"
section: "Art & Audio"
issues: [21, 24]
---

# A luminance recolour can collide two ROLES on one index — check the roles, not just the ramp (#24).

Lupin's map sprite lost its inner-ear wedges, and it read as a drawing mistake in the hand-drawn glasses pass.
It wasn't: the shape was intact in all 18 frames. The recolour that moved the source onto the cast grey ramp
landed the inner-ear pink (`b2629c`, luma 128) and the light body fur (`719ac1`, luma 146) on the **same**
cast index 3, so the ears were painted body-colour. Caught by Nicolas comparing against the pack sprite, whose
map sent that pink to a pale index. Recovered by re-deriving the 10 px/frame from the source colour and
setting them to cast 11. **After any luminance-driven remap, list the source colours that share a target index
and check none of them are different features** — a ramp can look perfectly graded and still have eaten a
detail.
_Recorded: 2026-07-30_

**Pick a sprite already drawn in the standard SMS palette.** The first attempt (BoW "Goblin Spearman") had its own
9-colour palette, so nearest-mapping it to the standard layout collapsed it to a dark, unreadable blob (and a remap-target
bug — matching to the *player* palette while the unit displays under the *enemy* palette — turned its red pixels green by
accident). The Fire Imp is authored in the **standard SMS palette**: its body sits on the faction-colour ramp (indices
7–10), so under the enemy palette it becomes a **fully-shaded red imp** (glowing eyes, pointy ears) with zero remap
guesswork — the remap is an identity pass. Lesson: prefer FE-Repo sprites already in the standard palette; the index roles
must line up with the faction ramp or the faction recolour produces mud. **Green enemies are not practical** — green is the
NPC/ally palette (the engine applies it by allegiance, and FE's colour language reads green as friendly), and a custom
green-in-a-spare-bank would need an OBJ bank, but the one free bank (`0xB`) is already the cast's; red is the correct,
free "enemy" signal.

**`frame` override for off-size sprites.** A reskin sprite need not match the base class's SMS size: the Fire Imp is a
tall **16×32** sprite on a 16×16-combat soldier/fighter. The optional `frame: 16x32` in the reskin YAML sets the wait-row
size flag; the engine draws the taller idle correctly (same mechanism mounted 16×32 classes use) while combat stays the
base class's. Absent `frame`, the base class's own SMS geometry is used.
_Decided: 2026-06-16; shipped for the ch01 grunts (#21) as the Fire Imp, `make` green + `ch01win` PASS + in-game screenshot._
