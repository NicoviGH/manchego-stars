---
id: 402
title: "The team pick covers the scarcest demand first"
date: "2026-11-11"
section: "Combat System"
issues: [510]
---

# The team pick covers the scarcest demand first

**Call 4 of the fwd1 build plan (#510 comment 6810567866), approved by Nicolas on 2026-11-11
("I approve all calls").** It amends "Party selection" (#510 comment 6370592835, settled
2026-10-27; ADR 0368 points at it). The tie-break below and the dropping of the Talk demand are
Fable's, made while building it.

**The error.** After the forced units and a followed claim's, `Bot.team` took, again and
again, the unit answering the most open demands. A fighter answers three or more enemy classes;
the thief answers the chests and the doors. On vanilla Ch8 the claim units held up to 6 of the
9 slots, the fighters took the rest, and the only unit that can open a chest was benched in 30
of 68 parties (run `fwd1`, findings: #510 comment 6810177817). A chapter with chests then has
no clean clear whatever is played.

**The rule.** While a demand still needs answerers:

1. Take the open demand that the fewest units still fitting can answer.
2. Equally scarce, a demand of another kind goes before an enemy class. A demand of another
   kind (a chest, a door, a village, the fog, the healing) goes unanswered without its unit; an
   enemy class is still fought by the rest of the party. Then the first listed.
3. Of that demand's answerers, field the one answering the most open demands (the old rule,
   now the tie-break), then a carried unit, then the earlier joiner.

A demand nobody fitting can answer is passed over. Forced units and claim units still go
first, and the fill is unchanged.

**ADR 0396's tests.** The quantities are the game's (who can open, who can answer: `sight.answer`).
It is an ordering of the roster, it forbids nothing, and it names no unit, class or chapter.

**Step 2 was not in the plan.** The first build took ties in listed order, and the first
witness refuted it: on campaign 4001's Ch8 start the claims left three slots, three enemy
classes had one answerer each and were listed before the chests, and the thief stayed benched
(4 of 6 attempts over two campaigns).

**Witness** (`resume --game vanilla --tag b2 --campaigns fwd1-cs-s4001,fwd1-cs-s4004
--chapter 9 --last 9`, stopped after 6 attempts; the picks are in the attempts' `team`): the
thief is fielded in 6 of 6, each time as `covers: chests, doors`. None of the 6 is a clean
clear: the chests at (1,3) and (2,3) are still `never_offered`, and two attempts end `stuck`
(one after 406 player phases). Those are the plan's items C and E, not the pick.

**Dropped: a Talk as a demand.** The plan also made each recruit a `talk:<charId>` demand, to
field the second unit who can recruit on vanilla Ch9 (charId 4). Built and refuted on its
witness (campaign 4006's Ch9 start), by one probe at the prep screen:

- the chapter's talks name charId 18 from charIds 1 and 4, and **charId 18 is not on the board
  at the prep screen**, so nothing at the prep screen says she is a recruit and not a unit who
  arrives on our side. Vanilla Ch8's talk table holds six talks whose targets are player units
  or units who arrive as player units; with every talk taken as a demand, one of those was
  among the demands a fielded unit was picked to cover;
- charId 1 is the lord, who is forced, so a Talk demand needing one answerer is settled before
  the pick starts and cannot field charId 4.

The code was removed. Whether any fielded unit can reach her before she leaves is the plan's
item D (one instrumented run), and its calls 5 and 6.

**Scarce is a count of answerers, not answerers against the need** (review of PR #602). The
order only matters when the slots run out, and then a demand with one answerer loses all of its
cover if it is passed, while a class needing three of its three answerers loses a third of it.

**Not built: another kind before an enemy class whatever the counts** (review of PR #602). With
two units able to open the chests and enemy classes of one answerer each, the classes go first
and both openers can be benched. Replayed offline over the 9 distinct picks kept so far (28
vanilla records), that order fields the same units as this rule in all 9, and no
demand of another kind with an answerer on the roster is left without one. So it is not a rule
yet; the pick's record lists every such demand under `uncovered`, so the first real case shows
in the record.

**Proof.** `test_bot.lua` `test_team_covers_the_scarcest_demand_first`: the first, second and
fourth cases fail on the old rule; the third and fifth pass on it and pin the new rule's own
parts (step 3's tie-break, and passing over a demand nobody answers). `test_team_fill_is_the_best_answer_to_the_biggest_class` changes its
expected order (the same four units, the scarcer class's answerer first).

**The suite** (`montecarlo.py suite --held-out`, on the commit before the review's fixes, which
do not change the pick): PROMOTED. 56 runs, each with a game result; 0 regressions on the frozen
baseline; the same five deaths that lived when frozen as ADR 0401 (signals, not blockers);
held-out 4 of 28 lost, none new; 2,685,802 `AiDecideMain` calls against a budget of 2,988,937.
The suite's starts have their teams already, so it shows the pick broke nothing, not that it
helps.
