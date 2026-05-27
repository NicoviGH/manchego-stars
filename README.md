# Manchego Stars

> A GBA tactics ROM hack of *Fire Emblem: The Sacred Stones*, based on a D&D 5e *Rime of the Frostmaiden* campaign.

**Private distribution only — for the 7 campaign players.**

The party's *Icewind Dale* adventure — a hermit crab barbarian, a mushroom druid, a vampire warlock, a ratfolk artificer, a snowperson sorcerer, a chwinga bard, and a drakeborn metallurgist — playable as a GBA tactics game. D&D's d20 dice mechanics replace Fire Emblem's hit-rate math. Seven chapters, from the goblin iron quest to the Revel's End cliffhanger.

## Prerequisites

- `devkitARM` (r51+)
- `agbcc` (GCC 2.95.1 for GBA)
- `ColorzCore` / Event Assembler
- Base ROM: FE8 Sacred Stones (USA) — sha1 `0x...` — not included, not committed

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

## License

Engine code is derived from `fireemblem8u` (© their respective authors). Campaign content is private and not for redistribution.
