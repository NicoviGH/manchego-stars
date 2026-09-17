---
id: 87
title: "The difficulty curve projects planned chapters forward from their vanilla reference (#123)."
date: "2026-07-02"
section: "Weapon & Magic Systems"
issues: [123]
---

# The difficulty curve projects planned chapters forward from their vanilla reference (#123).

Nicolas (2026-07-02): "Can we not project forward based on vanilla?" We can — every chapter already
declares its `parity_reference`, and the #48 extractor models the VANILLA side of the comparison, so a
`status: planned` chapter's row now prints its reference's own threat/slot + clear-load/slot as its
**(target)** — the bar the authored chapter must land within the ±25% band of — instead of a blank
"not modeled" line. The whole campaign arc is visible before content exists, and authoring starts
against a known number. Mechanics: `vanilla_projection` (informational only; planned chapters never
gate); threat counts the FULL force, clear-load excludes units the fixed early-game yardstick cannot
damage at all (a promoted wall would read `inf`) and the row says how many were excluded — ch08's
Hamill Canyon bar reads huge and partly yardstick-proof, consistent with its scripted-defeat design.
Landed with it: the **FE8 Ch13 reference curated** (11 armed-RED ch13a arrays; cutscene loads excluded;
staff-only healers drop by design) and six vanilla-only weapons modeled verbatim from `data_items.c`
(steel-lance, steel-bow, slim-lance, short-spear, zanbato, elfire — elfire returns on the VANILLA-ONLY
side of the #53 seam with plain stats; the #8 effectiveness experiment stays reverted). Drop-census
verified before adding: all LOCKED references were already fully modeled, so no locked bar moved.
_Decided: 2026-07-02 (CLAUDE; #123 from Nicolas's forward-projection ask)_
