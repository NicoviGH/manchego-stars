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

**The call.** `Sight.keepMaps` (the keep every refresh in a sandbox already makes: `M.refresh`
and `aiDecide`) keeps the state words and also the three pools `RefreshEntityBmMaps` rebuilds
(`bmmap.c`: `BmMapFill` on `gBmMapUnit`, `gBmMapHidden`, `gBmMapFog`), through one helper over
that list (`Sight.keepMapPools`). Each pool is `BmMapInit`'s layout, `(w + 2) * (h + 4)` bytes
from its first row pointer; the span is that count floored to whole halfwords, as `BmMapFill`
clears it (an odd count loses its last byte). The journal puts the maps back as it puts the unit
states back. No special case in Drop: every list the game builds from the unit map (Rescue, Talk,
Take, staff targets) was reading the same wrong map after a decision.

The hidden and fog maps were first left alone ("no failure traced to them"); the reviewer was
right that the same refresh wipes them, so they are kept the same way. `gen_symbols.py` now lists
`gBmMapHidden`; a stale `symbols.lua` without it makes the keep raise, naming it. A missing symbol
or a null map pointer raises too: a refresh only runs on a loaded chapter's map, so either is a
programming error, never a thing to skip silently. The map size is read by `Board.mapSize`, the
one reader (`Board.read`, harness `mapSize`, the keep). `keep16` skips a span it already holds
whole in the same sandbox (the memo is in the sandbox's own held table, so it resets with it),
because every decision asks again.

**Proof.** `test_sight.lua` fails without the fix: the refresh test (our unit, and the hidden and
fog cells, wiped by the plan's refresh and found back by the next plan) failed on the old code
(unit cell: got 0, want 7); an odd-sized map (3 x 3) keeps 17 halfwords; a missing symbol and a
null pointer are named. `aiDecide` has no behavioural harness (it needs the game's calls); its
keep is held by the source-order test beside `keepAi`'s and `keepRide`'s, which now names
`keepMaps`. Replay, tag `dropfix1`: `b640e-cs-s4002` from its Ch19 start, attempts 2: attempt 1
won in 13 turns; attempt 2 lost on turn 11, no crash. The turn-12 Drop of the crash was not
reached, so the replay shows no regression, not the fix itself.
