---
id: 74
title: "One manifest owns \"what a playtest scenario needs\"; `run.sh` and the matrix runner both read it (#231)."
date: "2026-08-05"
section: "Combat System"
issues: [222, 231]
---

# One manifest owns "what a playtest scenario needs"; `run.sh` and the matrix runner both read it (#231).

`tools/playtest/matrix.yaml` is the single source of the scenario → ROM configuration / `PT_HOST_CHAPTER` /
checkpoint / fps-vsync-deadline table. Before this, that table was split three ways — the ROM flag and host
chapter existed only in `harness.lua`'s per-scenario `Run:` comments, the checkpoint map and the timing
policy lived in two bash `case` blocks in `run.sh`, and nothing connected them — so the operator carried it
in their head and "a failing playtest may be the WRONG ROM" was the standing top gotcha. `run.sh` now
resolves through `matrix.py resolve` and keeps only its real job (run ONE scenario in mGBA);
`matrix.py run --suite <name>` groups a selection by ROM configuration, builds each **at most once**, runs
sequentially, and prints a `variant | scenario | verdict | time | artifacts` table with `results.json`
beside it. Decisions worth keeping:
- **Every scenario is enumerated in the manifest, defaults and all.** Absence is a `check.py` drift failure
  (`check_playtest_matrix`), not a silent canonical/host-1 default that fails later in the emulator.
- **Resolution is `defaults < class rules (in order) < the scenario's row`** — a direct port of `run.sh`'s
  `case` semantics, including that a later rule overrides only the keys it names. So `record*` still means
  60fps/vsync/300s, and `recordch02ending` still takes 600s on top of it, without restating either.
- **Ordering is about checkpoints, not just builds.** Save states are ROM-hash-stamped, so switching ROM
  configuration invalidates *all* of them, and `ckpt_ch02start` replays the whole ch00→ch01→ch02 chain to
  rebuild one. Inside a group, checkpointless scenarios run first (a cheap failure surfaces before a long
  checkpoint build) and checkpoint-sharing scenarios stay contiguous. The lint pins a checkpoint and its
  `ckpt_*` builder to the same ROM configuration — a mismatch is an invisible double cost, since the
  consumer would discard the state as hash-stale.
- **`build_campaign.py` stamps `.build-config.json`** (gitignored) with the boot flags that produced the ROM
  in the tree, because nothing in the `.gba` says how it was built. `run.sh` refuses a wrong-ROM run in 0s
  with the exact `make` line instead of letting mGBA time out; an unrecognised or missing stamp stays out of
  the way rather than blocking.
- **A failed build blocks only its own group**, and a failed scenario does not stop the matrix — one broken
  configuration must not hide the state of the others.
- **Builds are sequential by construction; runs are not.** Two ROM builds in one tree corrupt each other and
  the tree holds ONE `fireemblem8.gba`, so a build never overlaps anything. Scenario RUNS are independent
  processes: headless ones run concurrently (see “Headless flipped the parallel-dispatch default”, #310),
  while headed runs and checkpoint builders stay serial — they contend for the compositor and for
  `states/<name>.ss` respectively. The biggest win is still not rebuilding and not re-earning checkpoints.
- **Suites are curated, not derived.** `gate` is deliberately tight (controller contract + ch00/ch01 spine +
  SMS budget + the current chapter); the per-chapter suites are each a single ROM build; `--all` runs every
  non-manual verdict scenario. `llm` is `manual` (external sidecar) and never auto-selected.
_Decided: 2026-08-05 (CLAUDE; #231 = #222 workstream 1. Workstreams 2–4 — state inspector, declarative
scenario manifests, static chapter lint — stay deferred and get re-scoped from the ch05 build experience.)_
