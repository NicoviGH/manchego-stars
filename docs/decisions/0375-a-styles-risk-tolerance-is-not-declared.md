---
id: 375
title: "A style's risk tolerance is not a declared value: the styles are the variation"
date: "2026-10-28"
section: "Combat System"
issues: [510]
---

# A style's risk tolerance is not a declared value: the styles are the variation

**No one picks the death chance a careful player accepts** (Nicolas, 2026-10-28: "I thought the
point of monte carlo was trying different things"). The planner's styles weigh a unit's death at
1000 (careful), 300 (even) and 60 (bold) against the damage it deals (`planner.lua`
`M.WEIGHTS`), on top of ADR 0368's gates, and each run draws its style. What one style accepts is
what that draw does.

**Why a single threshold does not matter:** FE8 players reset on a death (research 0002), so a
verdict counts clean clears, and attempts are independent draws from a varied policy (research
0001). A careful run that loses a unit at a 13% risk is one failed attempt, and the next draws
again. The verdict rests on the spread of styles, not on any one style's line.

**Found by:** vanilla Ch3 with Seth benched. Careful struck Bazba alone at the planner's own
predicted 12.7% chance of losing Franz, and lost him (#510 comment 6480158861). That is
intended behaviour, not a fault.

**The weights stay as they are; they change only on evidence** (verdicts or traces showing the
spread of styles is off from how players play). Option for later, not adopted: draw the death
weight from a continuous range instead of three points.
