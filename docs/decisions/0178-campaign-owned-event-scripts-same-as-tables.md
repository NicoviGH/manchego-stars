---
id: 178
title: "Campaign-owned EVENT SCRIPTS, same as tables"
date: "2026-08-07"
section: "Operational Gotchas (durable)"
issues: [25]
---

# Campaign-owned EVENT SCRIPTS, same as tables

`declare_event_script` is the script twin of `declare_unit_table`, for the same reason: a host slot
frees only the scripts its stripped cutscenes stop referencing (slot 6 leaves five; ch05 needs
three waves plus one per village), and `MS_Ch05VisitSouth` says what it runs where
`EventScr_089F2AE4` says nothing.

**It APPENDS, so it must run AFTER the injector's block-replacement pass**, which rewrites the same
file wholesale from a copy read earlier. Declaring first silently discards every appended script —
the Location list still names them and the externs still exist, so the only symptom is a link error
pointing at the reference rather than at the loss. `assert_event_scripts_defined` pins the ordering.
