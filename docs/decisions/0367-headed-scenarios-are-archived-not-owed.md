---
id: 367
title: "Headed scenarios are archived, not owed: a scene is filmed when it changes"
date: "2026-10-24"
section: "Operational Gotchas (durable)"
issues: [538, 531]
---

# Headed scenarios are archived, not owed: a scene is filmed when it changes

Nicolas, 2026-10-24: "I am not running 45 headed scenarios ever ... We only need to run them if
we change something about those scenes anyway." A `kind: record` or `diagnostic` scenario needs
a window and his attention, and keeping 65 of them live made every harness change owe him a
headed run that was never going to happen. A list of runs nobody will make is not a safety net.

**The rule.** A headed scenario is not kept live in the harness. Film a scene when it changes,
with the generic tools, or restore the specific recorder for that one run.

**Archived by #538** (harness.lua, matrix.yaml, the chapter YAMLs, and every helper only they
reached; the last commit that has them is **f4ff003**): `attackprobe`, `bootobserve`, `ch02aidiag`, `ch04sprites`, `ch07titlecard`, `difficulty`, `enemycheck`, `koboldview`, `lzview`, `mapfull`, `mapfullch05`, `record`, `recordanim`, `recordcast`, `recordch01`, `recordch01trail`, `recordch02combat`, `recordch02ending`, `recordch02huts`, `recordch02intro`, `recordch02map`, `recordch02turn1`, `recordch03midmap`, `recordch03open`, `recordch03talk`, `recordch03win`, `recordch04cottage`, `recordch04moose`, `recordch04open`, `recordch04reveal`, `recordch04snag`, `recordch05combatquotes`, `recordch05ending`, `recordch05endingbasildied`, `recordch05endingnosahnar`, `recordch05eruption`, `recordch05join`, `recordch05joinlupin`, `recordch05moose`, `recordch05opening`, `recordch05openinglupin`, `recordch05platform`, `recordch05ravisindeath`, `recordch05recruit`, `recordch06ice`, `recordch06messie`, `recordch06nerradeath`, `recordch06opening`, `recordchain`, `recordending`, `recordenemy`, `recordfix`, `recordlord`, `recordlordfast`, `recordopening`, `recordprep`, `recordravisin`, `recordrbg`, `recordrbgtest`, `recordrescue`, `recordtrade`, `scenes`, `scenesch01`, and the checkpoint builder
`ckpt_rbgch01`. Restore one with `git show f4ff003:tools/playtest/harness.lua` plus its row.

**Kept**, each because a workflow calls it:
- `recordscene` films any dialogue scene from env vars.
- `mapshot` is the load-test step in `docs/adding-a-chapter.md`.
- `vanillagold`'s retail boot and world-map path are reused by #510 step 9.
- `recordunitlist` and `recordsupply` are verdict kind.
- The checkpoints `prep`, `seize` and `ch02intro` are what recordscene loads.
- The `TESTCH`/`BENCH` sandbox build stays, so restoring a battle-anim recorder costs nothing.

Gone with them: `check_recordenemy_knows_every_raw_pid`, `RESKIN_CLASS` in symbols.lua, and the
`PT_CHAR`/`PT_ROUNDS` plumbing, which had no other reader. harness.lua went from about 10,500
lines to about 7,600, and from 167 top-level locals to 158.
