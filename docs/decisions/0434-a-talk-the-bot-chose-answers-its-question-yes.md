---
id: 434
title: "A talk the bot chose answers its question Yes"
date: "2026-11-20"
section: "Combat System"
issues: [679, 640, 510]
---
# A talk the bot chose answers its question Yes

**Decided 2026-11-20 (#679).**

**The problem.** A talk can ask the player a yes/no question. The harness pressed through a
talk's dialogue but never answered a question, so the act timed out and the run crashed. Seen
in vanilla E_14 (`b640e-cs-s4001`, attempt 7, turn 7): Eirika (charId 0x01) talked to Rennac
(0x1C).

**What the game does (decomp).** Eirika's talk (`ch14a-eventscript.h` `EventScr_089F61C4`)
calls the paid-recruit script `EventScr_9EEB00` (`common-events.h`):
- If the party holds less than the price (9,980 gold for Rennac), the game says so and the talk
  ends with no question. It can be offered again (`EventScr_EndAndResetTriggEvent`).
- Otherwise it asks. Yes pays the price and the unit joins (`CUSA`). No ends the talk.
Larachel's talk to Rennac (`EventScr_089F619C`) recruits him with no question.

**The call.** Inside a Talk act, a question is answered Yes (`Controller.waitAnswer`, read by
`INSPECT.answerWait` while `INSPECT.inTalk` is set). The bot chose the talk to recruit, and a
clean clear needs every recruit; gold is not part of clean. The price spent is not weighed
against what the gold would buy later: the planner gives the talk no cost. A question outside a
talk is still the caller's, as before.

**Proof.** The unit test in `test_controller.lua` fails without `Controller.waitAnswer`. One
replay: `b640e-cs-s4001` from its E_14 start (tag `f679`).
