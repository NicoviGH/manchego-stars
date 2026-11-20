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
  ends with no question.
- Otherwise it asks. Yes pays the price and the unit joins (`CUSA`).
- No, and the cannot-pay case, both end in `EventScr_EndAndResetTriggEvent`
  (`events_script_utils.c`), whose `ENUF` clears the talk's flag: the game offers the same talk
  again.
Larachel's talk to Rennac (`EventScr_089F619C`) recruits him with no question.

**The call.**
- Inside a Talk act, a question is answered Yes (`Controller.waitAnswer`, read by
  `INSPECT.answerWait` in the wait `INSPECT.awaitActed` runs for a talk). The bot chose the talk
  to recruit, and a clean clear needs every recruit; gold is not part of clean. A question
  outside a talk is still the caller's, as before.
- A Talk to an owed recruit that leaves it out of the party recruited no one (the party could
  not pay). It is not progress, and it is not offered again that attempt until the party's gold
  rises above what it held then (botrun's `unpaid`, read by Bot's `talks`). The game's Talk check
  knows no gold, so without this the talker would spend its act on the same talk every turn. A
  talk to a unit not owed (a boss's, an item's) is not judged, nor one whose party read failed:
  that is unknown, not a refusal.
- Every Talk is in the chapter record (`talks`: turn, talker, target, whether a question was
  asked, the gold it took, whether the target joined).
- The price is not weighed (Nicolas, 2026-11-20): safety comes before gold. The planner gives a
  talk no cost, so two talks that recruit the same unit (Larachel's free one, Eirika's paid one)
  tie, and the plan's risk decides between them. Larachel's is taken when she gets there
  without danger; no unit is put at risk to save the payment. A gold price on the talk was
  weighed and refused: at the styles' gold weights, `even` and `bold` would never pay and so
  never clear Ch14 clean.

**Proof.** The unit tests fail without the fix: `test_controller.lua` (`Controller.waitAnswer`),
`test_bot.lua` (an unpaid talk is not offered, to the habit or the planner), `test_botrun.lua`
(an unpaid talk is made once, not every turn, and recorded), and
`test_playtest_harness.py` (the talk flag is passed down the wait, not a global). One replay:
`b640e-cs-s4001` from its E_14 start (tag `f679`).
