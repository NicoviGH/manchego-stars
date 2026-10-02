---
id: 321
title: "trex and lupin join on lines that fit where they join"
date: "2026-10-02"
section: "Combat System"
issues: [403, 430]
---

# trex and lupin join on lines that fit where they join

#403's remainder, #430 step 4. #403's correction showed that FE8 recruits join at their own
`baseLevel`, with their class and personal line. Our recruits already match that, with two
exceptions. Each rode a donor's personal line on a level-1 body, and the line belonged to a
higher level than the body:

- **trex** rides Colm, whose line is his L2 line. trex joins in ch03, where vanilla's Colm
  joins at L2. **trex now joins at L2** (`fe_stats.level`), which is Colm exactly.
- **lupin** rode Kyle, whose line is his L5 Chapter 8 line, on a level-1 ch04 join. It ran hot.
  **lupin now takes Franz's L1 base line** (`BASE_DONOR`). Kyle's growths and ranks stay, so
  lupin still grows on a curve distinct from Baxby's. This is ADR 0042's shaman precedent: a
  base donor that fits the join point (Ewan over Knoll's L9 line).

Re-measured party effect (threat / clear-load): ch03 x0.92 / x1.21 → x0.89 / x1.10. ch04 is
unchanged, ch05 is x0.95 / x1.17, and ch06 is x1.04 / x1.15.
