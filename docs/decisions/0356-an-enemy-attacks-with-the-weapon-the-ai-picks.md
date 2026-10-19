---
id: 356
title: "An enemy attacks with the weapon the AI picks against that target"
date: "2026-10-19"
section: "Combat System"
issues: [510]
---

# An enemy attacks with the weapon the AI picks against that target

FE8's AI chooses a weapon and a target together. `AiAttemptOffensiveAction` (cp_battle.c) loops
over the unit's items (outer loop) and over every target it reaches (inner loop). It scores each
pair (`AiComputeCombatScore`) and keeps a candidate when `tmpResult.score >= finalResult.score`.
The parity model used to arm every enemy with its first weapon (#510 step 3).

- **Each unit records every weapon it carries** (`Combatant.arsenal`, filled where the unit is
  loaded). `fe_combat.arms` gives one armed copy per weapon, in inventory order. The parity
  model, the danger map and the timeline all read it. The latter two each kept their own copy of
  that list before.
- **It attacks with the best-scoring pair** (`ai_target.pick_attack`, and the same loop in
  `party_matchup`). It **defends** with its equipped weapon, the first one, so how fast the party
  clears it is unchanged.
- **A tie goes to the later candidate**: the later weapon first, then the later target. The model
  had this backwards ("the first highest"), which the decomp's `>=` contradicts.

**In-engine proof:** `ch06halberd` (#495, ADR 0329). ch06's Fighter carries {Iron Lance,
Horseslayer} and swings the Horseslayer only at a mounted target, which `pick_attack` now
predicts (`test_ai_target`).

**What moved:** no verdicts. ch06 goes from threat x0.96 to x1.05 on Normal, from its
Horseslayers. ch02 goes from x1.22 to x0.94 on Tutorial and Normal, entirely from the tie rule.
So many of ch02's AI target choices are ties, which FE8 breaks by unit order, meaning deployment
order. Whether the model's party order matches the ROM's is open (logged on #510).
