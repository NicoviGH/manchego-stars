---
id: 459
title: "A wounded unit is read on the phases after the next, and a sandbox strike equips its weapon"
date: "2026-11-23"
section: "Combat System"
issues: [743, 510]
---

# A wounded unit is read on the phases after the next, and a sandbox strike equips its weapon

**Decided (Nicolas, 2026-11-23, #743 comment 7113868739: "Yes, build it"), #510 step 9.** Amends
ADR 0421 (the wear) and ADR 0389 (the second phase), both unchanged in how a later phase is played
and counted.

**The problem.** Of 101 deaths over the cap in run m740c, 79 had no read past the first phase: 40
were struck in it and not read (the wear exempted a unit a heal could reach), 39 were not struck
in it (the counts are #743 comment 7113644701's). The wear already plays the later phases
(`sight.nextPhase`) and its reading already replaces the unit's death in `protected`, so in admission. A second mechanism would copy it.

**1. Who is read (`planner.lua` `carries()` and `judge()`'s `st.worn`).** A unit is read when it
is wounded: struck in the judged phase, or left at or under half its max HP by the plan. Then:
- no heal of the army's can reach it (ADR 0421's test, unchanged): `M.WEAR` = 3 phases;
- a heal can reach it (its own item, or a staff a turn away): 2 phases, the next and the one
  after. The read plays no heal between them, so it is pessimistic for that unit. Whether it
  over-reads is for the calibration, not this PR.
Counting is unchanged: the multi-phase death replaces `die`, admission is asked on it, and over
the cap the `first_*` keys still rank first (0389's 2026-11-08 amendment). The trace's `wear` and
`phases` read 2 for such a unit. The budget stays `M.WEAR_DECISION` / `M.WEAR_ATTEMPT`.

**2. The weapon order (`sight.lua` `M.strikeLedger`, the enemy's sandbox strike).** The game
equips the weapon it strikes with (`EquipUnitItemSlot` reorders the bag); the sandbox's strike
wore the ledger and never equipped, so the second phase read slot 1 as the Steel Lance. Ch13's
enemy 138 alternates a Steel and a Killer Lance (22, 26, 22, 26 over turns 6 to 11), and the real
kill was a Killer Lance crit. The strike now equips `side.slot` through `M.equip`, the ledger's
rows follow the item (`M.equipRows`), and its uses come off where the equip put it
(`M.strikeWear`'s `armed`, `M.afterEquip`). A ballista shot (slot 0xFF) and a strike with no slot
or from slot 0 equip nothing, nor does our own berserked unit's strike (`t.berserk`): the army's
reply picks its weapon by the slot the board lists (`s.weapons`), which a reordered bag would
give another item.

**Out of scope, and why it matters.** The fog gap (no Ch19 death was read) and the average-HP gap
(the first phase's spread is not carried into the second) stay as the #743 diagnosis left them.

**Proof (ADR 0430).** Unit tests that fail without each part (`test_bot.lua` wear tests,
`test_sight.lua` strikeLedger), and one replay of vanilla Ch14 `b640e-cs-s4007` attempt 1
(m740c: the lord, charId 1, died on turn 7). **The replay did not change**: same acts hash
(2ba6882f), lost on turn 7, the lord dead. Why: the played plan left the lord at full HP
(20 of 20) and no enemy struck him in the first phase, so he is not wounded by this rule; the
second phase would kill him at 0.887 (the probe's read), from enemies that arrive after the first
phase. The wounded rule cannot reach that death. It reads other turn-6 plans' units (82 wear
calls, no budget skips) and the lord on turn 7, where the chapter was already lost to the
fallback. Whether a "wounded" rule is the right trigger for this class of death is #743's open
question.

**Known divergence, vanilla Ch21 `b640e-cs-s4007` attempt 1, turn 2 (not a defect found).** On
main the best plan (`2>attack@4,13>146#1 ... 4>attack@18,16>139#0`, judged 167.38, slot 1,
`useCost` 0) was admitted and played. On this branch it and the other `#1`/`#2` variants read
`game_over` 0.575 / 0.446 and were not admitted; the plain-weapon plan (133.416, slot 0,
`useCost` 444) was played, and `lookahead.wear` rose from 7 to 11 calls. An instrumented replay of
that turn found the source: unit 2 (charId 15, a unit whose death ends the game, 45 HP, struck for
18.2 on average by enemies 132 and 157 in the next phase) is read on 2 phases because a heal can
reach it. Its death in the next phase is 0.0; in the phase after it is 0.575 (`#1`) and 0.446
(`#2`), against 0.0 with the weapon it already holds. So the whole 0.575 is the phase-after-next
read of a struck unit that a heal can reach. It is not the half-HP trigger (unit 2 was read
because it was struck) and not the enemy-strike equip (which touches the enemy's bag; the plans
differ only in unit 2's own weapon). Why the cheaper `#1` weapon reads worse than slot 0 (a weaker
counter leaving the enemies it fights alive into the second phase is the likely cause) was not
measured. The read plays no heal between the two phases (section 1), so it may over-read for a
unit a heal reaches; the trace cannot say how much. This is the designed pessimism, left as
decided; whether to soften it is Nicolas's call (the calibration of #743).
