---
id: 45
title: "A boss is class base PLUS a personal stat line — that, not the class, is why FE8 bosses are walls."
date: "2026-07-23"
section: "Combat System"
issues: []
---

# A boss is class base PLUS a personal stat line — that, not the class, is why FE8 bosses are walls.

`CHARACTER_SAAR` is an Armor Knight *plus* HP+13/Pow+6/Skl+5/Spd+3/Def+2/Res+3/Lck+4. This retires the whole "find a tanky mage class" search: **FE8 has none** (best magic Def is 5 — Sage/Mage-Knight/Gorgon, all 10% Def growth), and the FE-Repo shares *art*, not portable class definitions (a class is just a table row each hack sets itself; our own pipeline already clones and rewrites classes). So Ravisin stays a Druid with Flux and her existing art and simply gets a `personal:` line (HP+15/Def+5 → ~13.4 rounds, Saar's bar). **Zero art cost, no custom class.**
Scope matters: personal lines are modeled **only in the role check, on both sides** — putting them in the AGGREGATE parity metric shifted every curated baseline (ch02 fell out of band) and made a Def-13 boss undentable, so the aggregate deliberately stays class-base-only on both sides. Two traps found while wiring it: **(1) personal Def and terrain STACK** — HP+15/Def+5 on a throne makes her undentable (`inf`), so it's one lever, not two (the throne is dropped, and the armour bodyguards with it — with a real boss line they were redundant scaffolding, so `frost-sentinel` was removed and `crypt-blade` 2→4 carries the clear-load); **(2) the yardstick's attack is exactly 13, so Saar-with-line takes 0 damage** — the bar therefore falls back to his class-base 12.92 **per boss**, never all-or-nothing (an undentable Saar must not hand the "bar" to Ch5's weaker dentable bandit). That undentability says more about the yardstick being a weak average unit than about the boss — the chapter hands the player an Armorslayer for exactly this.
_Decided: 2026-07-23 (Nicolas + CLAUDE; "why can't Ravisin just be a different class?")_

**Two assumptions this killed, both checked instead of guessed:** (1) **`GuardTileAI` does not mean "on a throne"** — it means "don't chase." Saar's post is plain `TERRAIN_ROAD`, so his 12.9-round wall is **100% class Defense, zero terrain**; the earlier claim that terrain widened the boss gap was wrong. (2) Terrain can't rescue a caster: a throne (+30 avo/+3 def) takes Ravisin from 2.9 → 6.8 rounds — past "folds instantly," still about half of Saar. Hence the split fix: throne **plus** distributed armour (two Armor-Knight bodyguards ≈ 11.7 rounds on the approach). This deliberately gives our boss *more* terrain help than vanilla's boss gets, compensating for Druid Def 5 vs Armor Def 11 — a documented departure, not a mirror. (Anchor regressions pin both reads: Ch5 Joshua stands on `TERRAIN_ARENA_REGULAR` — canon — and Saar on `TERRAIN_ROAD`.)
_Decided: 2026-07-23 (Nicolas + CLAUDE; ch05 boss-role post-mortem — "how did this slip past us?")_
