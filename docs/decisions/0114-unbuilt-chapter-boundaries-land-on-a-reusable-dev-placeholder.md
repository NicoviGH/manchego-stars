---
id: 114
title: "Unbuilt chapter boundaries land on a reusable dev placeholder, not a vanilla map"
date: "2026-06-17"
section: "Distribution & Scope"
issues: []
---

# Unbuilt chapter boundaries land on a reusable dev placeholder, not a vanilla map

We develop chapter-by-chapter, so a finished chapter's `unlocks_chapter` often points at a
chapter that isn't hosted yet. Instead of `MNC2`'ing onto a leftover vanilla map, such a
boundary ends on the **dev placeholder** (`dev_placeholder_scene` in `tools/build_campaign.py`):
RBG delivers a cheese-pun "still under construction, thanks for playtesting" line over the
campfire BG, then `MNTS` returns to the title screen. It's a pure event scene (no map/units).
Punt it forward at each new boundary until the real next chapter lands.
_Decided: 2026-06-17_
