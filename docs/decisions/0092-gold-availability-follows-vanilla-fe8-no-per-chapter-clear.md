---
id: 92
title: "Gold availability follows vanilla FE8 — no per-chapter clear bonus"
date: "2026-06-17"
section: "Economy"
issues: []
---

# Gold availability follows vanilla FE8 — no per-chapter clear bonus

FE8 never pays a flat "chapter cleared" stipend. Its gold comes from in-map sources, plus four
SCRIPTED GIFTS, each a named patron handing over funds inside a scene: Castle Frelia's scene
right after Ch1 (`lordsplit`, Hayden, 5,000 -- measured on retail by `vanillagold`), Ch8's
ending (Hayden, 10,000), Ch13 Eirika route (5,000, if Dozla lives) and Ch19 Eirika route
(10,000). Ours follows suit: gold-giving villages (`SVAL(EVT_SLOT_3, n)` +
`GIVEITEMTOMAIN(leader)` → "Got n gold" popup), sellable enemy drops + gems
(RedGem/BlueGem/…), chests, and a scene gift where its twin has one, through
`economy.scene_gold` (ADR 0350): ch01 carries Ch1's 5,000, ch07 carries Ch8's (ADR 0339).
Chapter YAML records gold as concrete sources, **not** an abstract `gold_reward` field. ch01's
job pay ("two hundred gold" in the opening) is flavor: it is spent winning over Baxby, a
**free story-recruit** (FE8 shops sell items, not units, so recruitment is a unit join, not a
purchase).
_Decided: 2026-06-17_

---
