---
id: 47
title: "Refinement (2026-07-23) — the RIGHT fix for the glassy problem is a SKIN divorce, not a composition fight: put undead skins on vanilla INFANTRY classes (the ch01 pattern), and reserve beasts for chapters where beasts are on-story."
date: "2026-07-23"
section: "Combat System"
issues: [25]
---

# Refinement (2026-07-23) — the RIGHT fix for the glassy problem is a SKIN divorce, not a composition fight: put undead skins on vanilla INFANTRY classes (the ch01 pattern), and reserve beasts for chapters where beasts are on-story.

The corollary above is correct physics but its *recommendation* (lean the spine on beasts) was a crutch. The clean fix — adopted for ch05 rev.2 — is the one Nicolas pushed: keep the vanilla FE8 twin's **living-class stats** (Soldier/Fighter/Mercenary/Archer/Armor-Knight/Myrmidon) and **reskin them undead** via `enemy_class_reskins` (exactly how ch01 ships "Vanilla Ch1 enemy table, goblin-skinned"). Then clear-load parity is *free* (living classes aren't doubled; the Armor-Knight is the Def-sink the monster palette couldn't produce) and there is no glassy fight. ch05 rev.2 (risen elven guardians on infantry classes + the lone White-Moose boss) landed threat x1.21 · **clear-load x0.97** — better-centered than rev.1's x0.81. Two further reasons this beats the beast-spine crutch: (1) **narrative variety** — ch04 IS the beast/wolf chapter (the hunt, Marty's parley); reusing wolves in ch05 makes it "ch04 indoors," so ch05's dead-tomb identity requires *not* leaning on beasts (wolves CUT; the moose stays as the ch04-quarry payoff); (2) it generalises — ch06 (Messie) and ch08 get their own on-story skins over vanilla-parity classes rather than a monster-class recomposition each time. Asset note (FE-Repo, all [U]): undead **sword/bow** skeleton anims exist off-the-shelf (Bonewalker/Specter/Stalfos, Wight Sniper); **lance/axe/armored** undead humanoids do not → those slots use frost/pale palette-swaps of the vanilla frame (an ice-locked sentinel reads better than a bone-knight anyway). The static bar is still a proxy — playtest is the arbiter.
_Decided: 2026-07-23 (Nicolas + CLAUDE; ch05 roster rev.2, #25 — "divorce skin from class; don't refight parity per chapter")_

**Recruit budget: the roster tracks vanilla's field-growth curve to a ~16–18 pool — NOT capped at Ch5.**
The binding *field* size is `deploy_limit` = vanilla chapter N's deploy-slot count (§Field parity;
table in `fe8-pacing-reference.md` §1b). That curve, [decomp]-verified through Ch14a, **climbs and
then plateaus — it never stops**: `2 → 4 → 5 → 9 → 9 → 9 → (5x:4) → 10 → 10 → 9 → 11 → 12 → 11 → 12 →
12`, holding **~12 from Ch10a through the back half** (exact Ch15–Final pin deferred, same honesty
tier as §1b — the late ally arrays are raw-address blobs; the plateau is the load-bearing fact).
Because our model **recruits the whole cast and Pick-Units deploys `deploy_limit` of them**
(§Field parity), the *roster* must sit **above** the peak field, or Pick Units is a formality and a
single permadeath drops you under the cap. Vanilla always carries a bench above the deploy cap; we
should too.
**The math that kills the old "stops at Ch5" cap:** 8 PCs + the locked Ch2–5 recruits
(Baxby/Trex/Lupin/Sahnar/Basil) = **13** — which only *barely fills* the Ch9→endgame field cap of
11–12 (bench ≈ 1). That is a forced-deploy roster with no choice and no permadeath slack. **Budget:
grow the roster to ≈ peak field + a ~4–6 bench = ~16–18 units**, i.e. **~3–5 more permanent recruits
across Ch6–21**, added as the DM notes supply bodies (which/where stays DM-notes-gated — see
`roadmap.md`). This governs **roster size, not field size** (per-chapter field stays vanilla via
`deploy_limit`), and recruits still earn their slot by **filling a role gap** (the by-role method in
`roadmap.md`) — the budget says *how many*, the role principle says *which*.
_Reconstructed: 2026-06-22 (CLAUDE, from the decomp field-growth curve at Nicolas's direction) —
superseded the then-stale `roadmap.md` "roster stops growing at Ch5" line (roadmap since fixed); the
original budget sweep was done in-session and never recorded, which this ADR fixes._

**Recruit wiring: a recruit is a classed cast member + a `recruit.chapter`; availability is data-driven; each join uses vanilla primitives per its own method — NO generic recruit engine.**
A recruitable unit is a full classed cast member — a `PORTRAIT_MAP` slot (a free vanilla character
whose files it overwrites), a `STAT_DONOR`, a `death_quote` + a dead-slot-2 msg id, its class in
`CLASS_MAP`/`CLASS_LOADOUT`, and a spawn tile per hosted chapter — exactly like a founding PC. The
**only** thing that marks it a recruit is a `recruit.chapter:` in its YAML.
**Prep availability is one shared, data-driven filter:** `build_campaign.cast_available_at(N)` =
the founding party (no `recruit:` block) + every recruit whose `recruit.chapter` is *before* chapter
N. So a recruit rides the prep/deploy roster from the chapter **after** it is recruited — which is the
whole of the "recruits the whole cast; Pick Units deploys `deploy_limit`" model (§Recruit budget).
`inject_ch0N` calls `_classed_cast(available_at=N)`; `available_at=None` (map sprites, death quotes,
stat patching) still covers every recruit.
