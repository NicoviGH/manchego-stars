---
id: 3
title: "Engine/content split: engine in C (reusable), campaign data in YAML (swappable)"
date: "May 2026"
section: "Engine & Tech Stack"
issues: []
---

# Engine/content split: engine in C (reusable), campaign data in YAML (swappable)

All campaign-specific data (character names, chapter events, unit stats, maps, dialogue) lives in `campaigns/rime-of-the-frostmaiden/` and is injected at build time. Engine C code must be campaign-agnostic. A second campaign requires only a new `campaigns/` folder.
_Decided: May 2026_
