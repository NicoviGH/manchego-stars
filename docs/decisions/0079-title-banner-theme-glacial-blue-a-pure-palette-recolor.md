---
id: 79
title: "Title banner theme: \"glacial blue\", a pure PALETTE recolor (no pixel edits)."
date: "2026-06-09"
section: "Combat System"
issues: []
---

# Title banner theme: "glacial blue", a pure PALETTE recolor (no pixel edits).

The banner's whole look is palette data: letters ride `gPal_08A07C58`'s green tint
pair (Status config `0x80`; `gPal_08A07AD8` is the bonus-claim green ramp), and the
Status plaque art is a SPRITE whose leaf-green ramp lives in `Pal_PlayStatusSprites`
pal 0 (OBJ rows 8–9 — found by dumping palette RAM from the `titlecard` playtest
scenario and matching on-screen pixels; it is NOT in the BG bank or the title
palettes). `build_campaign.py:inject_title_theme` reads `title_theme.letter_colors`
(six colors, light→dark) from `campaign.yaml`, maps vanilla's six letter greens 1:1,
hue-maps every other green-dominant color (plaque leaves, dim shimmer variant) into
the same family, and repoints the three `.s` incbins at generated `.bin`s (the `.s`
files are restored each build). The in-map chapter intro uses the gray tint pair
(config 8 → +0xA0) and stays vanilla white. Chosen from 4 in-game mockups
(vanilla / glacial / glacial+snow caps / frost white); snow caps rejected as less
readable. Applies to every chapter's card automatically.
_Decided: 2026-06-09 (Nicolas picked glacial blue; plaque recolor approved on the
in-game render)_

---
