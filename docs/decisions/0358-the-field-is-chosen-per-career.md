---
id: 358
title: "The parity read fields its team per career, forced units first, in the ROM's unit order"
date: "2026-10-21"
section: "Combat System"
issues: [510]
---

# The parity read fields its team per career, forced units first, in the ROM's unit order

Until now the parity read chose each side's team once. It ranked every arriving unit on its
median line (best single-target kill rate against the enemy line), kept the top `deploy_cap`,
and read all of their careers. A unit that makes the cut in most careers but not all was
fielded in every one, and a unit that would make it in a good career never was (#510 step 5).

- **Each joint career fields its own team** (`difficulty._fielded`). Same rule, read on that
  career's own lines and that career's rolled enemies (ADR 0357). `party_matchup` takes the
  arriving party and the cap, and reports each unit's fielded share.
- **Force-deployed units are always fielded.** Vanilla's come from `gForceDeploymentList`
  through `IsCharacterForceDeployed_`'s route and chapter test (`vanilla_forced`): Eirika
  everywhere on the common route, Artur in Ch4, Natasha in Ch5. On our side the only forced
  unit is the lead the player picks in ch01 (#42), which the model cannot know, so ours fields
  on merit. That assumes a lead the player would deploy anyway; `lord_team_sweep` reads the
  other leads.
- **Units sit in the ROM's unit-table order**, the order the AI breaks a target tie in (ADR
  0356's `>=`). `SortPlayerUnitsForPrepScreen` (prepscreen.c) puts force-deployed units first,
  then everyone else in their existing order (`_map_order`). For our cast, that order is the
  build's load order (`inject.cast.load_order`): ch01's founding join-LOAD in PORTRAIT_MAP
  order, then each recruit by recruit chapter. The arriving party's own order was not this.
- **One representative team remains** for readers that want one (the timeline, the boss checks
  against the party's median lines, the report's field line): the team picked most often
  across the careers (`fielded_careers`).

**Proof in the engine:** `ch07blueorder` logs the blue unit table in slot order after prep
(headless, on the ch07 boot). It read braulo, marty, wolfram, meesmickle, prof-rbg, rootis,
sclorbo, pinky, baxby, trex. That is `load_order` exactly. The arriving order the model used
before had wolfram/meesmickle and trex/baxby the other way round. That boot fields all 10 units
it carries, so it shows the slot order but not a bench. Vanilla's forced list is read from the
decomp, which is what the vanilla ROM runs.

**Why join order is slot order, on both sides:** a unit takes the first free blue slot at the
moment it joins. A LOAD goes through `GetFreeBlueUnit`, and a recruit turning blue goes through
`UnitChangeFaction` -> `GetFreeUnit` (bmunit.c). So a chapter's blue LOADs come first, in script
order, and its recruits follow as they turn blue. Two recruits of one chapter could depend on
the player. In practice none do (2026-10-21):
- **Vanilla's early chain:** every talk recruit hangs off another (Ross recruits Garcia).
  `vanilla_recruits` used to list a chapter's talk recruits mid-scan, putting Ross and Garcia
  ahead of Moulder, who loads in Ch2's opening; it now lists LOADs first. No verdict moved.
- **Ours:** ch05's pair is fixed by its script. Basil is made blue in the opening beat, and
  Sahnar joins by Basil's Talk. `test_every_pair_of_same_chapter_recruits_has_a_known_order`
  fails on any new pair until its order is established.

**What moved:** one verdict. ch01 Difficult goes OFF -> OK: its party half reads x1.407 against
ADR 0042's x1.41 ceiling, where it read x1.415. Its team is the same in every career, so the tie
order alone moved it, and it sits 0.003 inside the ceiling. That is an edge, not an
improvement. Natasha's forced slot moves ch05's clear-load from x1.17 to x1.08 on Normal (vanilla
spends a slot on a unit that cannot attack). Per-career fielding and the tie order move the rest:
ch02 Difficult threat goes x0.95 -> x1.09, ch06 Normal clear-load x0.96 -> x1.11, and ch07
Tutorial clear-load x0.93 -> x1.02. The model is not settled while a step moves verdicts, so
step 6 follows.
