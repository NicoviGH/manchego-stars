---
id: 359
title: "Strategy sections are claims the parity read checks, never an input"
date: "2026-10-21"
section: "Combat System"
issues: [510]
---

# Strategy sections are claims the parity read checks, never an input

#510 step 6 turned each Strategy section into data: the twin's (the Fire Emblem Wiki's,
vendored) in `tools/wiki/twin_strategy.yaml`, ours in each chapter's `strategy_claims:`.
Every claim cites its line verbatim, and a citation the section does not contain raises.
`tools/strategy.py` defines the kinds (`carry`, `answer`, `wall`, `threat`, `terrain`,
`unmodelled`) and prints the checks in `make difficulty CH=chNN`, beside the role findings.

**No claim feeds the model, terrain included.** The first build fed each side's `terrain`
claims into the threat read: the party stood on the named tile when those enemies attacked.
ch04, whose two sections both name forest, moved x1.10 → x1.20. The forest's +20 avoid costs
the twin's attackers more than ours, since FE8 averages two hit rolls (`Roll2RN`) and a low
displayed rate falls off fastest. ch01 moved x1.10 → x0.48 on one sentence of ours ("the
trail is dotted with forts"). The twin's section never mentions forts. Our map has 12, Escape
has 2. One side's cover was then set by whichever wiki text happened to name a tile, so
Nicolas made terrain report-only (2026-10-21, on #510). The report gives the tile count on
each side's map and what a foot unit gains there.

**Checks are findings, not a gate.** Each runs against its own side's read (our party against
our force, vanilla's against the twin's). An `answer` claim leaves bosses out of its
comparison unless it names one: "train Eirika on the Fighters" weighs them against the other
generics, not against an armoured boss her Rapier triples on.

**What it found on Normal** (read at the time, for step 10):
- ours, ch01: the strategy sends Wolfram against the Fighters, but the model does not field him.
- ours, ch02: "Wolfram and Baxby are the best walls" against the brigands; Braulo outlasts both.
- ours, ch03: the strategy says the danger is the kobolds, not the Grell, but the Grell carries
  the most summed threat.
- ours, ch06: Braulo's axe "wins the trades" against the lances, but his fastest kill is a
  shaman.
- twin, Ch4: Artur kills Bonewalkers faster than the Mogalls the wiki gives him. This is a
  MODEL gap, not a finding about the strategy: `fe_combat.triangle` reads every tome as one
  off-triangle `magic` kind, so it misses FE8's magic triangle (`sWeaponTriangleRules`, light
  beats dark: +15 hit, +1 damage for Lightning against the Mogalls' dark magic). Fixed in its
  own PR on #510.
- twin, Ch6 and Ch7: Joshua out-kills the boss's named answer (Seth, Eirika), in a near tie.

**The stopping rule does not read this step.** #510 stops when a step moves no verdict. This
step cannot move one by construction, so its zero is not evidence that the model has
converged.

`unmodelled` claims record what steps 7 (reach, time) and 8 (kits, sustain) inherit: escorts,
recruits, reinforcement timing, steals, shops, healing. `make difficulty` lists them per
step. While on this, `on_terrain` (a boss's tile) now also folds the tile's Res, which FE8 adds
against magic (`ComputeBattleUnitDefense`), and reads the Fly tables for a flier. No verdict
moved.
