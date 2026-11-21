---
id: 435
title: "A sandbox that refreshes the maps puts the unit map back"
date: "2026-11-20"
section: "Combat System"
issues: [681, 640, 510]
---
# A sandbox that refreshes the maps puts the unit map back

**Decided 2026-11-20 (#681).**

**The problem.** In vanilla E_19 the bot chose a Drop onto a tile the live game's drop list did
not offer, and the harness crashed (`b640e-cs-s4002` attempt 2 turn 12: unit 0x01 stays on
(6,2), Drop at (5,2), the game offers only (6,3); `b640e-cs-s4008` attempt 6 the same).

**Cause (measured, replay tag `dropdbg2`).** An ally (0x0C) stood on (5,2) and another (0x05)
on (7,2). The Drop list is `MakeDropTargetList` / `TryAddToDropTargetList` (`bmtarget.c`): a
tile is offered when `gBmMapUnit` is 0 there and the carried unit can cross its terrain. The
bot read `gBmMapUnit[2][5] == 0` while the unit structs still put 0x0C on (5,2). The wipe came
from `s.closings` (`sight.lua`), a sandbox that hides our units from the AI and runs
`aiDecide`, whose call list holds `RefreshEntityBmMaps` (`bmmap.c`): it clears `gBmMapUnit`
and refills it, leaving out every `US_HIDDEN` unit. The sandbox's journal puts the unit
structs back, never the game's own writes to the map, so every read after it in the same
batch saw the board with no blue units on it. The next read that refreshed (`learningAs`'s)
filled it again, which is why the live check (`s.legal`, run in its own sandbox) refused the
act and the next plan offered it again.

**The call.** `Sight.keepFog` (the keep every refresh in a sandbox already makes: `M.refresh`
and `aiDecide`) also keeps `gBmMapUnit`'s bytes (`Sight.keepUnitMap`: the
`(w + 2) * (h + 4)` span `BmMapInit` lays out), so the journal puts the map back as it puts
the unit states back. No special case in Drop: every list the game builds from the unit map
(Rescue, Talk, Take, staff targets) was reading the same wrong map after a decision.

Untested, not changed: `RefreshEntityBmMaps` also rewrites `gBmMapFog` and `gBmMapHidden`;
no failure has been traced to them.

**Proof.** `test_sight.lua` (the refresh test: a unit our plan's refresh wipes off the map is
back for the next plan) fails without the fix. One replay: `b640e-cs-s4002` from its E_19
start.
