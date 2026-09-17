---
id: 26
title: "Boot decision localized; bows need a min-range in playtest targeting (the first feature-flow feature)."
date: "2026-06-24"
section: "Working Conventions (Definition of Done)"
issues: []
---

# Boot decision localized; bows need a min-range in playtest targeting (the first feature-flow feature).

The boot cut + New-Game redirect were decided in BOTH `inject_prologue` and `inject_test_chapter` (the
duplication the Coordination ADR cites). Localized to one `_configure_boot(target, montage)` owner called
once from `build_campaign.main()`; the two target injectors no longer re-decide it. This — plus two
playtest fixes — unblocks `recordrbgtest` (capture RBG's bow anim on the `make TESTCH=1` sandbox)
end-to-end: (a) `clearbot.pickTarget` takes a **`min_range`** so a 2-range-only bow isn't parked
adjacent (range 1), where there is no Attack command; (b) `captureAttack`'s target confirm is
**feedback-driven** (press A, cycle targets, until `gProc_ekrBattle` animates) because with several foes
in range the BKSEL select cursor can start off a target. Verified end-to-end on the sandbox AND on
`recordrbg` (no regression). The "menu just opened, settle before the first A" hypothesis was wrong — the
menu was responsive throughout; positioning + multi-target confirm were the real causes.
_Decided: 2026-06-24_

---
