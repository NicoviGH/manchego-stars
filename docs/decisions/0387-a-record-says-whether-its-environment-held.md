---
id: 387
title: "A run's record says whether its environment held, and a bot fault is not an environment fault"
date: "2026-11-01"
section: "Combat System"
issues: [510]
---

# A run's record says whether its environment held, and a bot fault is not an environment fault

**Decided (Claude, 2026-11-01), #510 step 9 PR-A** (the plan's T008 and T009, #510 comment
6563384310). It builds the `env_status` and `instrument` fields of the plan's data model.

**The rule.** Every `BOTRUN` record carries `env_status`: `"clean"`, or `{fault,
outcome_dependent}`.
- `fault` is `crash` (the bot or the harness failed, including a Lua error), `timeout` (an enemy
  phase that never handed control back) or `watch` (a watch fault: the record misread the board,
  `watch_faults`). A worker that left no record at all is a `crash` too (`montecarlo.unread`).
- `outcome_dependent` is true once play had begun, meaning a unit was deployed. Which runs fail
  after that point can depend on what happened in them, so dropping them could bias the runs that
  remain. A fault before the first board read cannot. A worker with no record is counted as
  outcome-dependent, because nothing says when it died.

The record also names its `instrument`: the bot code's hash and the suite manifest's version
(`montecarlo.instrument_id`, passed to the harness as `PT_INSTRUMENT`).

**Why a bot fault stays out.** The plan's data model lists `bot_faults` among the sources of
`env_status`. Today `bot_faults` holds only `left_open`: a village or chest the bot could still
have used when it won. That is the bot's own play. It is what the instrument measures, and the
record is still readable. If it counted as an environment fault, a weak bot would lower the
environment-clean rate (ADR 0385's validity bar). The verdict would then be withheld for
something that is a measured result, not an unreadable one.

**Built with it (the suite manifest, plan R-6).** The frozen suite is the `instrument:` section of
`tools/playtest/matrix.yaml`, read by `montecarlo.load_suite`. Each start names the game's
chapter index, which is what the store files are named by. Ours chapter N is hosted at index N + 1
(`inject.hosts`). The scout starts "Ch10, Ch13, Ch14" are store indices 10, 13 and 14
(CHAPTER_E_9, CHAPTER_E_13, CHAPTER_E_14), because the scout's own write-up names its starts by
index (#510 comment 6484135808: Saleh's Doorkey in "Ch14"). Ours takes its twins' shops from
`campaign_env.ours_env`, which now reads a list of vanilla stores, the first holding the twin
winning. That is needed because the clean vanilla campaign stops at Ch5. `montecarlo.py suite`
refuses a start whose emulator, ROM, state path or state hash no longer matches its pin, and it
refuses any job estimated at more than 8 wall-hours (SC-007).
