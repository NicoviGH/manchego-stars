# Manchego Stars

> A GBA tactics ROM hack of *Fire Emblem: The Sacred Stones*, based on a D&D 5e *Rime of the Frostmaiden* campaign.

The party's *Icewind Dale* adventure — a hermit crab barbarian, a mushroom druid, a vampire warlock, a ratfolk artificer, a snowperson sorcerer, a chwinga bard, and a drakeborn metallurgist — playable as a GBA tactics game. **Combat stays vanilla Fire Emblem** (hit/avoid/might/crit); D&D is flavor on top — the characters, their classes, spells-as-tomes, and a cosmetic d20 flourish on crits. Prologue + 8 chapters, from the goblin iron quest to the Revel's End cliffhanger.

## Playtest feedback

Found a bug, balance gripe, or typo while playing? **[Open the playtest feedback form →](https://github.com/NicoviGH/manchego-stars/issues/new?template=playtest_feedback.yml)** (a free GitHub account is needed to submit).

## Prerequisites

Run `tools/setup-toolchain.sh` (macOS) — it installs everything below. In short:
- Homebrew `arm-none-eabi-gcc` (binutils as/ld), `pkg-config`, `libpng`, `coreutils`, `python@3.12` (numpy/pillow/pyyaml)
- `agbcc` (GCC 2.95.1 for GBA) — built from source into `fireemblem8u/tools/agbcc`
- Base ROM: FE8 Sacred Stones (USA) — not included, not committed
- Content injection is **decomp-native** (`tools/build_campaign.py` edits the decomp source) — no Event Assembler / devkitARM required.

## Build

```sh
git submodule update --init --recursive
./fireemblem8u/scripts/quickstart.sh --rom /path/to/baserom.gba
make CAMPAIGN=rime-of-the-frostmaiden -j$(nproc)
```

## Docs

- [`docs/PRD.md`](docs/PRD.md) — full product requirements, architecture, roadmap
- [`docs/decisions.md`](docs/decisions.md) — settled design decisions
- [`CLAUDE.md`](CLAUDE.md) — agent conventions and session guide

## License & legal

A free, non-commercial fan project — not affiliated with or endorsed by Nintendo, Intelligent Systems, or Wizards of the Coast.

- **No ROM included.** You must supply your own legal copy of *Fire Emblem: The Sacred Stones* (USA) to build or play.
- Engine code derives from the `fireemblem8u` decompilation (© its respective authors).
- *Fire Emblem* and *Rime of the Frostmaiden*, and their assets, belong to their respective owners (Nintendo / Intelligent Systems; Wizards of the Coast). Original campaign writing and art are © their creators.
