---
id: 71
title: "Playtest controller contract = observe, classify, enumerate, guard one input, verify, trace (#220)."
date: "2026-08-03"
section: "Combat System"
issues: [63, 220]
---

# Playtest controller contract = observe, classify, enumerate, guard one input, verify, trace (#220).

**Standing rule, in Nicolas's words: no brute-force, row-probing or cadence input in a scenario —
reproducible is not the same as justified.** Timing and plausible-looking button sequences are not game-state evidence. The shared mGBA driver reads
FE8U memory directly and turns exact Proc scripts/current callbacks plus live engine structures into a named
state. Standard menus are actionable only when their Proc is unlocked, not frozen, and neither ending nor
doomed; commands come from
`MenuProc.menuItems[] -> MenuItemProc.def -> MenuItemDef.overrideId`. Preparations commands come from the
live `ProcPrepMenu` items and callbacks. The minimum stable semantic ids are Talk `0x5A`, Wait `0x6B`, and
End Phase `0x78`; existing shared paths also use semantic Attack/weapon/target, Seize, Visit, and Status
where needed. Fight leaves the main Preparations menu through its live
`PrepScreenMenu_OnStartPress`/START callback—never B/Check Map or the View Map menu. This agrees with the
[official FE8 manual](https://www.nintendo.com/eu/media/downloads/games_8/emanuals/game_boy_advance_8/Manual_GameBoyAdvance_FireEmblemTheSacredStones_EN_DE_FR_ES_IT.pdf),
but live decomp state is authoritative.

The pure `tools/playtest/controller.lua` owns classification and legal-action enumeration. The mGBA-facing
observer/driver in `harness.lua` may execute **one** input only when that action is legal in the current
state; it then waits for a documented postcondition. Unknown, malformed, locked, frozen, or mismatched
states fail closed without a recovery button. Dialogue A is legal only under
`gProcScr_TalkWaitForInput` + `TalkWaitForInput_OnIdle`. Every attempted input emits a JSON transition record
containing frame-adjacent before/after observations, prior state, legal intentions, chosen intention/key,
expected postcondition, and verdict; failures retain the raw Proc inventory and produce a screenshot.
Map selection mirrors `GetPlayerSelectKind` from live `gUnitLookup` state/status/attributes, and movement A
requires both the engine movement map and an unoccupied `gBmMapUnit` tile. Unknown standard menus expose at
most their currently highlighted enabled item, and only when its live `onSelected` callback exists; choosing
that item is scenario policy, not a controller guess. Open Preparations help is passive and receives no input.

Scenarios own goals, assertions, and deterministic policy; the controller owns reusable UI mechanics.
Random actions remain confined to named fuzz scenarios. This does not require rewriting every historical
chapter-specific recorder in one patch, but any path migrated to the controller may not reintroduce row
guesses, cadence dialogue, or unrelated fallback inputs. The unlocked/not-frozen menu check was
cross-checked against the CC0 portions of
[GBA Fire Emblem for Screen Readers](https://github.com/StanHash/GBA-Fire-Embem-for-Screen-Readers);
addresses remain generated from our ELF rather than copied. The same semantic observer is intentionally a
future seam for replay, accessibility narration, dialogue transcript verification, target/forecast
inspection, and external policies—those products are follow-ups, not controller responsibilities.
_Decided: 2026-08-03 (#220; supersedes timing/row-driven common harness mechanics and #63 M2's blind Attack
executor limitation)_

**A scenario that produces a VERDICT may not drive the UI with a raw `press` — enforced, not
reviewed (#238).** #220 set the contract but migrated only the shared paths; the historical
verdict scenarios kept their blind cadences, and a blind cadence makes a green run worthless as
evidence. `ch01win` was the proof: it rode straight through the lord-select Yes/No prompt that
cost #232 three sessions, mashing A at a prompt it never saw, and passed. `check.py
check_verdict_scenarios_are_guarded` now fails the build on one, scoping from **`matrix.yaml`'s
`kind`** and following harness.lua's call graph, with a small named allowlist
(`BLIND_PRESS_ALLOWED`) carrying each exception's reason. `record`/`diagnostic` scenarios stay
blind by design — nothing is asserted there, so nothing can pass for the wrong reason.

Three lessons from the migration, all of which cost real evidence:

- **Count presses by ENCLOSING FUNCTION, never by distance to the next `scenarios.X`.** Splitting
  harness.lua on scenario definitions charges every intervening `local function` helper to
  whichever scenario sits above it. #238's own scope list was built that way and was wrong in both
  directions: it named `retreat` (which has none of its own) and missed `reachRbgCh01` (8) — a
  fifth hand-rolled copy of the ch01 lead route nobody knew was there.
- **A fixed press count is not a walk to a row.** FE8 menus WRAP, so `rows - 1` DOWNs land on the
  last candidate only if the menu opened on row 0. Walk off the LIVE cursor, stop when it arrives,
  and ASSERT where it landed — otherwise picking a different lord than the one the scenario names
  passes silently.
- **Watch the field the engine's key handler actually moves.** `recordunitlist` stopped its roster
  walk on `unk_2c` (the on-screen row, which CLAMPS as the list scrolls under it) and `+0x38`
  (untouched by the D-pad) instead of `unk_30`, so it could capture a fraction of the roster and
  still report PASS.

**Two of these blind presses turned out to be LOAD-BEARING, and only running the scenarios
found them.** Removing a cadence is not a no-op, and neither was worth a guess:

- **`clear_ch02`'s A-mash was answering a prompt the scenario never knew existed.** The ch02
  ending's third charm-gift lands on a full inventory, so FE8 raises
  `gSendToConvoyMenuItems` — "which item goes to the convoy" — and the entire MNC2 chain
  stops until it is answered. The mash resolved it by accident; drive the ending on observed
  state without naming that prompt and the run sits behind it for its whole budget and reports
  "2/3 charms" on a chapter that never left slot 3. That verdict's green had been resting on a
  stray press. The chooser is now a classified `send_to_convoy` state.
- **A scenario's own comment is not evidence.** `recordsupply` claimed "a NON-lord deployed
  unit's action menu has NO Supply row". `SupplyUsability` (bmmenu.c) returns `MENU_ENABLED`
  for the lead **or** for anyone `IsAdjacentForSupply` finds orthogonally beside them — so the
  claim is false for a neighbour, and the first deployed non-lord spawns right next to Pinky.
  The assertion caught the comment, not a defect. Contrast assertions have to be written
  against the engine's rule, not the prose around them.
