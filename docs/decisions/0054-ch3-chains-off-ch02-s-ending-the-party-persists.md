---
id: 54
title: "Ch3 chains off ch02's ending (`MNC2(0x4)`); the party persists, no armed seed."
date: "2026-07-11"
section: "Combat System"
issues: [23]
---

# Ch3 chains off ch02's ending (`MNC2(0x4)`); the party persists, no armed seed.

ch02's ending scene now `MNC2(0x4)`s straight into ch03 (hosted on chapter slot 4 by
`inject_ch03`), replacing the dev-placeholder→title landing it parked on while ch03 was
unbuilt (the placeholder pattern is unchanged — ch03's *own* ending still parks on it until
ch04 hosts). Two coupled moves in `build_campaign.main()`: (a) `inject_ch03` is now called in
**every non-boot build** (hosted alongside inject_ch02, in the sandbox build too, so ch02's
`MNC2(0x4)` never points at an unhosted slot); (b) it's called with **`boot=False`** — the
party that persists from ch02 feeds ch03's Preparations, so the `--ch03-boot` **armed party
seed** (`UnitDef_088B47E4`, LOAD1'd only under boot) is a standalone-playtest crutch only, not
part of the real chain. Verified in-engine by `clear_ch02`, which now A-mashes the ch02 ending
until `chapter() == 4` (ch03) and FAILs if the chain doesn't land — the ch02→ch03 analogue of
the `reachCh02Map` `MNC2(0x3)` proof.
_Decided: 2026-07-11 (CLAUDE, #23 item 1 — chaining pass)._
