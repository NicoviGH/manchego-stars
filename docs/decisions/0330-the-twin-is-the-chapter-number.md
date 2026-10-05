---
id: 330
title: "The twin is the chapter number, whatever map the chapter borrows"
date: "2026-10-05"
section: "Combat System"
issues: [459]
---

# The twin is the chapter number, whatever map the chapter borrows

A chapter's `parity_reference` is the vanilla chapter at the SAME position in the campaign: our
chNN is measured against FE8 ChNN. Its map may come from anywhere (`fe8_base_map`), because
the map is a layout and the twin is a difficulty bar: the party arriving at ch08 is the party
vanilla has at Ch8, not at Ch13 (Nicolas, 2026-10-05).

ch07 and ch08 predated ADR 0049's 1:1 rule and had inherited the twin of the map they borrow
(Ch6 and Ch13). They now read FE8 Ch7 and Ch8. Both were curated into the registry by its own
rule (the arrays the chapter's script loads whose RED units are armed), which reproduces the
hand-curated Ch6 entry exactly, and `VANILLA_CHAIN` runs to Ch8. The Ch13 registry entry stays
for the chapter that will one day be its number.
