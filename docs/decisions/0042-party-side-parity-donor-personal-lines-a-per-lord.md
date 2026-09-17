---
id: 42
title: "Party-side parity: donor personal lines + a per-lord survivability floor — never enemy or stat inflation."
date: "2026-06-18"
section: "Combat System"
issues: []
---

# Party-side parity: donor personal lines + a per-lord survivability floor — never enemy or stat inflation.

"Field parity" (above) mirrors vanilla's enemies and deploy cap; this is the party half. Each PC
inherits its class-matched vanilla donor's **personal base stats** (`build_campaign.py` →
`BASE_DONOR`; the build already inherits that donor's growths + ranks via `STAT_DONOR`, so base
inheritance extends the same path). Shamans take **Ewan (Ch1-appropriate) bases** (Knoll's lv9 bases are too hot
for Ch1), with **growths split toward their promotions** — Marty → Knoll → Druid, Meesmickle →
Ewan → Summoner (#45). This lifts the cast off its "naked class" lines — personal bases were all 0, i.e.
generic-enemy frailty plus a Spd-0 doubling cliff — to **vanilla parity on both durability and
kill-throughput** (`tools/difficulty.py`). The player-chosen lord (#42), who must survive,
additionally gets a runtime per-lord **HP/Def top-up to a ~5-enemy-hits-to-down floor** (0 for
tanky picks, +7/+4 for the glass shamans) so no lord choice is a trap; it is **one-time** (fades as
the party levels — Jagen-style). Campaign-long strength scales by matching **vanilla's recruit
cadence** (bodies + promotions), not stat inflation; enemies stay vanilla; and there is no
Seth-tier god-unit — the cast are all player characters, all eight (**Pinky included**), and must
all matter. The per-chapter **difficulty engine** is `tools/difficulty.py` (`make difficulty
CH=chNN`), built on the tested combat core `tools/fe_combat.py` (the decomp's own formulas);
execution plan + full spec: issue #45.
_Decided: 2026-06-18 (Nicolas; difficulty analysis session — supersedes the open "Ch1 difficulty" item)_
