---
id: 5
title: "Content injection is decomp-native — edit the decomp's own source, NOT Event Assembler."
date: "2026-06-04"
section: "Engine & Tech Stack"
issues: []
---

# Content injection is decomp-native — edit the decomp's own source, NOT Event Assembler.

`build_campaign.py` writes our content directly into the `fireemblem8u` working tree at build time — `graphics/portrait/` (busts), `texts/texts.txt` (names/dialogue), `src/data_characters.c` (class/stats), and `src/events/<ch>-event*.h` (chapters) — then `make` compiles it. No Event Assembler / ColorzCore / `.ea` buildfiles. This is the "make a hack directly from the fireemblem8u decomp" path (FEU thread 17428). Generated files are reproducible artifacts: restore vanilla with `git -C fireemblem8u checkout <path>`.
_Decided: 2026-06-04 (supersedes the PRD's Event Assembler plan; retires the `tools/build-events.ts` idea)_
