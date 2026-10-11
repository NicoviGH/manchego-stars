---
id: 92
title: "Gold availability follows vanilla FE8 — no per-chapter clear bonus"
date: "2026-06-17"
section: "Economy"
issues: []
---

# Gold availability follows vanilla FE8 — no per-chapter clear bonus

FE8 never pays a flat "chapter cleared" stipend (verified in the decomp: the prologue/Ch1/Ch2
event scripts give zero gold). Its gold comes from in-map sources, plus four SCRIPTED GIFTS
from Ch8 on, each a named patron handing over funds inside a cutscene: Ch8's ending (Hayden,
10,000), the route split (Hayden, 5,000), Ch13 Eirika route (5,000, if Dozla lives) and Ch19
Eirika route (10,000). Ours follows suit: gold-giving villages (`SVAL(EVT_SLOT_3, n)` +
`GIVEITEMTOMAIN(leader)` → "Got n gold" popup), sellable enemy drops + gems
(RedGem/BlueGem/…), chests, and a scene gift where its twin has one (ch07 carries Ch8's,
ADR 0339). Chapter YAML records gold as concrete in-map sources,
**not** an abstract `gold_reward` field. ch01 is a net wash like vanilla Ch1 (~0 gold):
the ~200g job payment for recovering the iron is immediately spent winning over Baxby (a
**free story-recruit** — FE8 shops sell items, not units, so recruitment is a unit join,
not a purchase), so nothing is added or subtracted in-game. The "two hundred gold" in the
ending dialogue is flavor only.
_Decided: 2026-06-17_

---
