---
id: 72
title: "What the contract costs, measured, so it is not re-litigated (Nicolas's standing question)."
date: "2026-08-06"
section: "Combat System"
issues: [220, 238]
---

# What the contract costs, measured, so it is not re-litigated (Nicolas's standing question).

The gates cost **~1.5s on `make check`** and a few percent on `make matrix` (4–6 min warm, 14/14).
The real cost is not seconds: it is that a new FE8 input state must be CLASSIFIED before a scenario
can drive it. #238 named six in one pass — the inventory list, the send-to-convoy chooser, the
Character screen, the Pick Units grid, the in-map convoy, and four unit commands — and each new
chapter will surface more. That work always existed; the cadence deferred it into mystery failures
instead of paying it. **If the stall detector ever false-positives, `TUNE.stallFrames` is the dial
— do not remove it.**

**The acceptance test for a migrated scenario is the BITE TEST, not a green run.** Break a
classification deliberately and confirm the scenario now FAILS. A migration's whole claim is
"this run means something now", and only a sabotage proves it — #240 established this on
`ch01win` (the same sabotage passed before the migration), and #238 repeated it on the
Character screen (`fail:state-timeout` where the old code, which consulted no classification
at all, could not have noticed) and on the lead-menu walk landing one row short.

**Naming a new state is not finished until the DRIVERS know about it.** Code review caught two
instances on this branch. `item_list` and `send_to_convoy` had classified as `generic_menu`
before they were named, so `cancelToPlayerMap` could back out of both; giving them their own
states silently removed that — and that function is the recovery path #238 had just put behind
`ch01win`'s post-seize menu surprise. `awaitControllerState`'s recovery had the same gap for
`supply_screen`/`unit_list_screen`. **A classification change is a change to what the harness
can escape from**, so a new state ships with its cancel wired in the same commit.

**Enumerate a movement action only where the engine would actually move.** The Character
screen's UP at row 0 is not a no-op: `sub_809144C` sets `unk_29 = 3`, routing into
`sub_80917D8`, the sort-column mode — a persistent input state the observer reports as
`scrolling`, i.e. as a transition offering nothing. Advertising UP there hands a driver an
action that walks it somewhere it has no enumerated way out of, to sit until the stall watch
fires on a wait the controller itself caused. Both ends of that walk are now bounded off
`gUnknown_0200F158`, the same field the engine bounds against — the rule `prep_pick_units`
already followed.

**An absence assertion must assert the state first.** `legalActions` returns `nil` when
`classify` finds no state, and `findAction(nil, …)` is `nil` — so "the command was not offered"
and "we could not tell what was on screen" were indistinguishable. `recordsupply`'s contrast
check now requires a live `unit_command_menu` before concluding Supply is absent.

Also: **a budget must not count the frames a screen spends TEARING DOWN.** `cancelToPlayerMap`
looped eight times total, and the convoy's fade-out held a `transition` for far longer than
that, so the cap decided the failure — the trap `docs/decisions.md` already records from #232.
It now counts CANCELS, with a separate `TUNE.cancelFrames` ceiling for transitions.

Newly classified for it, by the usual four-edit recipe (`gen_symbols.py` WANTED → `CALLBACK_NAMES`
→ `observeController` → a `classify` rule): unit commands Chest `0x5D`, Door `0x5E`, Item `0x67`
and Supply `0x69`; the **inventory list** a unit's Item command opens (`gItemSelectMenuItems`,
`0x43`–`0x47`); the **send-to-convoy chooser** (`gSendToConvoyMenuItems`, `0x2A`–`0x2F`); the
map-menu **Character screen** (`ProcScr_UnitListScreen_Field`); the **Pick Units** deploy grid;
and the in-map **convoy** (`ProcScr_BmSupplyScreen`). The inventory list needed its own state
because `MENU_DISABLED` means something different there: `ItemSelectMenu_Usability` greys any
item the unit cannot *use* — a weapon, a vulnerary at full HP — but `Menu_OnIdle`'s A path never
consults availability and `ItemSelectMenu_Effect` opens the submenu regardless. A greyed row is
still a live row; reading it as a command menu reported "unsupported standard menu" the moment
every item happened to be unusable, which is Hlin's whole inventory at ch00 turn 1. Two ordering rules came
with them. The Character screen and the convoy sit **above `player_phase`** — the map is still in
the proc pool underneath, and `player_map_idle` would offer cursor moves that go nowhere. And each
of the three screens reports a **transition while its own scroll animates** (`unk_29` on the
Character screen, `list_num_pre != list_num_cur` on Pick Units): FE8's key handler does not run in
that window, so an input sent then is lost outright, and calling it an input state is how a press
goes missing. Pick Units' legal moves mirror `ProcPrepUnit_Idle`'s TWO-COLUMN bounds exactly (LEFT
only from an odd index, RIGHT only from an even one short of the end, UP/DOWN by two) — a press
outside them moves nothing, and a driver that assumed a straight list would go on to act on
whoever it was still parked on.
_Decided: 2026-08-06 (#238; extends #220's contract from the shared paths to every verdict scenario)_

**A multi-page screen is driven one guarded press PER PAGE, and the gap between pages is a
real transition — do not classify it away.** `ch05arena` drove the Arena's two pre-fight
dialogue pages with a single press on an 1800-frame budget and reached combat only through
`guardedInput`'s lost-input re-press: a pass by accident, which #255's verdict cache would have
frozen. The fix is a loop that waits for each page to reach its own input wait, presses once with
its own postcondition, and **counts the pages** — so the run asserts the screen's anatomy (the two
`PROC_CALL`s of `gProcScr_ArenaUiMain`, msgs `0x8D5` and `0x8D3`) instead of merely arriving.

The inherited diagnosis was wrong and cost nothing only because it was instrumented before it was
believed. #269 recorded that a bounded loop of presses failed `not-legal` on a `transition` and
concluded `controller.lua` must learn to classify the Arena dialogue state. It already does: an
instrumented run logs `dialogue_wait(talk_wait in talk_wait_input) -> transition(player_phase
idle=nil is not a known callback) -> dialogue_wait -> transition`. Each page classifies correctly;
the `transition` is the gap where the talk proc is still PRINTING and no `gProcScr_TalkWaitForInput`
exists — there is genuinely nothing to advance there, and teaching the classifier to offer
`advance_dialogue` in it would have manufactured exactly the lost press #238 warns about. The loop
that fails is the one that presses without waiting. **A `not-legal` on a `transition` usually means
the driver pressed too early, not that the classifier is missing a state.** Scenarios that walk a
multi-page screen carry a state TRAIL in their log for this reason: the first run then diagnoses
itself, instead of costing a second one.
_Decided: 2026-08-12 (#269; the ch05arena press, measured in-engine — the diagnosis it corrects
came from the issue itself)_
