---
id: 78
title: "Seize-map legibility: the seize tile must read as a seize point and the boss sits on it — a level-design checkpoint"
date: "2026-06-19"
section: "Combat System"
issues: [56, 57]
---

# Seize-map legibility: the seize tile must read as a seize point and the boss sits on it — a level-design checkpoint

Vanilla FE8 doesn't *prompt* a seize. The goal window for `GOAL_TYPE_SEIZE` prints a static
label and returns with no counter ([player_interface.c:1585-1592](../blob/main/fireemblem8u/src/player_interface.c#L1585-L1592)); the actual teaching is **spatial** — the Seize command is tile-gated to a
`TERRAIN_THRONE`/`TERRAIN_GATE` tile (`UnitActionMenu_CanSeize` → `TILE_COMMAND_SEIZE`,
`src/bmmenu.c`), that tile is a visually unmistakable throne/gate, and the **boss conventionally
stands on it**, so kill → obvious empty special tile → Seize is one square. There is no
auto-tutorial (only the player-initiated Guide, `src/bmguide.c`). The label alone does **not**
carry it. So every Seize-objective map must pass a **design-review checkpoint**, verified per map
as a line on the chapter's vertical-slice checklist and re-checked at playtest:
- **(a)** the seize tile uses distinct Seize terrain (throne/gate-style) so it reads as a special
  tile *and* the tile-info readout is not "Plain"; and
- **(b)** the boss is placed **on** the seize tile (or the tile is otherwise made unmistakable the
  moment the boss dies), so killing the boss self-evidently reveals where to go.

A dialogue nudge is at most belt-and-suspenders, never the fix. Applies to every Seize-objective
map — in the MVP that's **Ch1 (#57/#21)** and **Ch3 — The Termalaine Mine (#23)**; re-check any
future Seize map. (The Prologue is `defeat_boss`, not Seize, so it's out of scope.)
_Decided: 2026-06-19; from the brother's v0.1.0 playtest (#56 → #57)._

**Ch1 resolution (2026-06-20, #57).** The camp seize tile [21,7] is now the snowy-bern castle-gate
metatile 938 (`TERRAIN_GATE_CASTLE`) — reads unmistakably as a Seize point (criterion a), with the
chief on it (criterion b). This also **restores vanilla Ch1's gate bonus (+20 avo / +3 def)** to the
boss: the v0.1.0 tile was a deliberate bonus-free "ruins arch" deviation, now reverted to full
"Seize the gate" field parity (the deviation was the outlier, not the bonus). ⚠ The boss is
correspondingly tankier — flagged to the pipeline/difficulty track so its ch01 parity bar accounts
for the terrain. Ch3's seize tile still needs the same pass.
