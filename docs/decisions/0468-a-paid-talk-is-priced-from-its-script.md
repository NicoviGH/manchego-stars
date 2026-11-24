---
id: 468
title: "A paid Talk is priced from its script; a talker past the purse is no talker"
date: "2026-11-24"
section: "Combat System"
issues: [766, 764, 510]
---

# A paid Talk is priced from its script; a talker past the purse is no talker

**Decided (Claude, 2026-11-24, #766's R2, the "what each talker costs" part of #764's plan).**
ADR 0396 holds: the game refuses the hire, so the bot does not send the talker; a hire it can
pay is ranked by the style's own weights, no new one.

**Why.** On vanilla Ch14 (s4003, `r765c` attempt 2) the march gave Rennac's Talk to Eirika, the
nearer talker. Her Talk is the paid hire: her script sets slot 4 to 9,980 and reaches
`EventScr_9EEB00`, whose `CHECK_MONEY` / `BLT` refuses the hire below that, and the party had
9,420. L'Arachel, whose Talk is free, marched on the boss until Eirika's goal stalled, by when
Rennac was out of reach. The game's Talk check (`CheckForCharacterEvents`) knows no gold, and
botrun's `unpaid` learns a Talk is unpaid only after one fails (#766's root-cause comment).

## What changed

- **`sight.talkPrice(mem, script, paid)`** reads the price off the talk's script: slot 4's SVAL,
  held through the walk's CALLs, at the CALL to the paid script; nil for a free talk. It replaces
  `callsScript` (its one caller, `freeTalks`, now asks whether a talk has a price), and the
  event walk's `memo` option, which only `callsScript` used, is gone.
- **The read raises** on a paid CALL reached with slot 4 never set or set to a ROM address, and on
  a walk the budget cut short. Of vanilla's six slot-4 SVALs only E_14a's and E_14b's reach the
  paid script (through `EventScr_9EEAAC`); E_9a/b set a text id before `EventScr_089F3C34` and
  E_19a/b a UnitDefinition before `EventScr_089F82FC`, neither of which CALLs it.
- **A live Sight answers `s.talkPrice(u, t)`** (`M.pairPrice` over every entry of the
  chapter's talk table, available now or not, read once per Sight; the dearest when a pair has
  two) **and `s.gold()`**: the api's own, harness.lua `INSPECT.spendableGold`, the one owner of
  the game's `GetPartyGoldAmount` (what `CHECK_MONEY` and the shop read: 0 in Ch5x).
- **A talk whose script is the paid one itself raises**: it sets no price before it.
- **A forced Talk** rebuilt from its key in a diagnostic replay gets its hire from
  `Bot.hirePrice`, so the planner charges it the same way.
- **The march's job search** (jobs.lua) asks each (unit, job, from) once and tries each job's
  takers best first, so a search the budget cuts short keeps the greedy dive. `opts.fixed` had
  no caller and is gone (#770's review).
- **Bot:** a Talk whose price is over the party's gold is not a Talk (`talks`), so no talker
  pairing, march, menu or candidate offers it. An affordable one carries `hirePrice`.
- **The march's Talk job** (`exploring`, jobs.lua) is worth `Goals.worth` of a recruit with the
  price as negative gold: W.death − price × W.gold. A free talker outranks a paid one; a hire
  worth no more than its price to the style is no job. With Rennac's 9,980: careful 1,000 −
  399 = 601 (sent when he is the only talker); even 300 − 798 and bold 60 − 1,497 (never).
- **The planner** charges a played hire in `st.priced`, at W.gold points, as it charges weapon
  uses (#642).

## Proof

- `test_sight.lua`: the price read (through two CALLs, behind a GOTO, an ENQUEUE_CALL), the
  raises, and slot 4 set with no paid CALL read as free.
- `test_bot.lua` `test_a_paid_talker_is_priced_and_never_sent_past_the_purse`: 7 of its 8 checks
  fail on the code before this change (the eighth, careful sending the only talker, holds both
  ways).
- Lua tests, three laps each, back to back: base user 2.31 s and 2.14 s, branch 2.20 s and
  2.18 s (`bot.lua` loads the weights only when it prices a Talk).
- Replay `r766e`, vanilla Ch14 s4003, two attempts. Read off the traces, no new run. Eirika is
  never sent on Rennac. L'Arachel holds his goal from turn 3 in attempt 1 and from turn 4 in
  attempt 2. She still never Talks him: she trails him 2 to 8 tiles behind and spends turns on
  staff uses (attempt 2: turns 7 to 9), and he leaves on turn 11 (attempt 1) and turn 12
  (attempt 2). Attempt 1 won in 24 turns with 0 deaths. Attempt 2 ended `stuck` on turn 21: the
  same board from about turn 14, every unit waiting on row 1, and the boss alive at (9,5). The
  march has no job once Rennac is gone. Before this change (`r765c`) attempt 2 won in 21 turns.

## Left open

- The talker's job is now right, but the per-turn planner does not play it: she spends turns on
  her staff while Rennac walks away. That is R3 (#767).
- Attempt 2's stall at the seize: a door the planner never played from an ally's tile, fixed
  by ADR 0469 (replay `r766g`: attempt 2 won clean).
- botrun's `unpaid` (#679) stays as a fallback for a sight that cannot price a Talk.
