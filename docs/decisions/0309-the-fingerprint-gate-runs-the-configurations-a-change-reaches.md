---
id: 309
title: "The fingerprint gate runs the configurations a change reaches"
date: "2026-10-01"
section: "Operational Gotchas (durable)"
issues: [424]
---

# The fingerprint gate runs the configurations a change reaches

The #409 and #410 refactors fingerprinted every ROM configuration on every change, at ~2.5 min
each. Most configurations build the default tree plus one boot step, so most of those runs
measured the same thing again. `tools/fingerprint_reach.py` now says which configurations a
change can move, and the gate runs those:

    python3 tools/fingerprint_reach.py            # against origin/main
    python3 tools/injection_fingerprint.py --write before.json --flags="<what it printed>"

The configurations are `playtest/matrix.yaml`'s `rom_configs`, so the list cannot drift from
what the matrix builds. The answer comes from the step declarations (ADR 0304):

- **The default build** is in the answer whenever a change touches anything the injection reads.
- **Another configuration** is in it when a step that runs under it reads a flag it sets, or
  runs only there, and the change lands in that step's module or in any module it imports.
  The imports are what catch `inject/montage.py`: the prologue imports it and runs in the
  default build, but with `--montage` off, so the default never runs the montage's code.
- **`inject/steps.py`, `build_campaign.py` and any non-Python ROM input reach everything.** The
  first two hold every step's `when` and `call`. No step declares what it reads, so a data file
  cannot be charged to one step.
- **Anything the build never reads reaches nothing**: docs, tests, the playtest harness.

Measured on the tree as it stands: a ch05 edit gates 7 of 14 configurations, `inject/portraits.py`
gates the default alone, and `inject/scenes.py`, which every chapter imports, gates 12.

## What it does not see

A step reads the tree that earlier steps wrote, so a flag-reading step can change what a later
flagless one produces. `inject.namespace` imports every injector module to collect constants,
and the reach does not follow that import. Both are covered by the default build, which runs
every flagless step and every registry, and which is in every non-empty answer.

## No configuration was retired

Every `rom_config` has a live consumer. `ch01boot` has no scenario that names it, but the
`rom: any` probes (`mapshot`, `difficulty`, `attackprobe`) run against whichever boot is built,
and `ch01boot` is how they see ch01 (#353). The three ch05 debug boots (`--ch05-moose` and the
`--ch05-ending` arms) were the proposed cut once ch05 was signed off. They stay, because the
films of the moose charge and the three endings are built on them. Those are the hardest scenes
in ch05 to reach, and a re-film after a dialogue change would otherwise replay the whole chapter.
Once the gate runs only what a change reaches, keeping them costs a build only when ch05's own
code moves.
