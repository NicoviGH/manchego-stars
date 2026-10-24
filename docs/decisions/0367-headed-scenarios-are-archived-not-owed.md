---
id: 367
title: "Record and diagnostic scenarios are archived, not owed: a scene is filmed when it changes"
date: "2026-10-24"
section: "Operational Gotchas (durable)"
issues: [538, 531]
---

# Record and diagnostic scenarios are archived, not owed: a scene is filmed when it changes

Nicolas, 2026-10-24: "I am not running 45 headed scenarios ever ... We only need to run them if
we change something about those scenes anyway." A `kind: record` scenario films a scene, and a
`kind: diagnostic` one answers one question once. Neither carries a verdict. Keeping 65 of them
live made every harness change owe a run that was never going to happen, and a list of runs
nobody will make is not a safety net. Diagnostics go too, headless ones included (`ch02aidiag`):
once its question is answered, a diagnostic is history, and keeping it live only means
maintaining it.

**The rule.** No record or diagnostic scenario stays live in the harness unless a workflow calls
it. Film a scene when it changes, with the generic tools, or restore the specific recorder for
that one run.

**Archived by #538.** The last commit that has all of it is **f4ff003**:
- The scenarios: `attackprobe`, `bootobserve`, `ch02aidiag`, `ch04sprites`, `ch07titlecard`, `difficulty`, `enemycheck`, `koboldview`, `lzview`, `mapfull`, `mapfullch05`, `record`, `recordanim`, `recordcast`, `recordch01`, `recordch01trail`, `recordch02combat`, `recordch02ending`, `recordch02huts`, `recordch02intro`, `recordch02map`, `recordch02turn1`, `recordch03midmap`, `recordch03open`, `recordch03talk`, `recordch03win`, `recordch04cottage`, `recordch04moose`, `recordch04open`, `recordch04reveal`, `recordch04snag`, `recordch05combatquotes`, `recordch05ending`, `recordch05endingbasildied`, `recordch05endingnosahnar`, `recordch05eruption`, `recordch05join`, `recordch05joinlupin`, `recordch05moose`, `recordch05opening`, `recordch05openinglupin`, `recordch05platform`, `recordch05ravisindeath`, `recordch05recruit`, `recordch06ice`, `recordch06messie`, `recordch06nerradeath`, `recordch06opening`, `recordchain`, `recordending`, `recordenemy`, `recordfix`, `recordlord`, `recordlordfast`, `recordopening`, `recordprep`, `recordravisin`, `recordrbg`, `recordrbgtest`, `recordrescue`, `recordtrade`, `scenes`, `scenesch01`.
- The checkpoint builders only they used: `ckpt_rbgch01`, `ckpt_prep` and `ckpt_seize`.

**Restoring one** means taking from f4ff003 everything it needs:
- its `scenarios.X` body, and every helper it reaches that is gone (`git show
  f4ff003:tools/playtest/harness.lua`);
- its matrix.yaml row, and its checkpoint builder if it loads one. Its ROM configuration is still
  in matrix.yaml: every build flag keeps one, because the injection fingerprint enumerates them;
- for a battle-anim recorder (`recordanim`, `recordcast`, `recordenemy`): run.sh's
  `PLAYTEST_CHAR`/`PLAYTEST_ROUNDS` wrapper lines and their `PLAYTEST_ENV_KEYS` entries in
  matrix.py. For `recordenemy`, also gen_symbols.py's `RESKIN_CLASS` table
  (`reskin_classes`) and `check_recordenemy_knows_every_raw_pid`.

The `TESTCH`/`BENCH` sandbox build, the debug boot flags and their ROM configurations stay, so
the build side needs no restoring.

**Kept**, each because a workflow calls it:
- `recordscene` films any dialogue scene a checkpoint reaches, from env vars.
- `ckpt_ch02intro` is the checkpoint its documented example loads.
- `mapshot` is the load-test step in `docs/adding-a-chapter.md`.
- `vanillagold`'s retail boot and world-map path are reused by #510 step 9.
- `recordunitlist` and `recordsupply` are verdict kind (`ckpt_lordpinky` feeds recordsupply).

harness.lua went from about 10,500 lines to about 7,500, and from 167 top-level locals to 156.
