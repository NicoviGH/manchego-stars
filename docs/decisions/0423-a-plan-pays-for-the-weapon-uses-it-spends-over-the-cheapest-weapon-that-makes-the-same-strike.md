---
id: 423
title: "A plan pays for the weapon uses it spends, over the cheapest weapon that makes the same strike"
date: "2026-11-18"
section: "Combat System"
issues: [642, 510]
---
# A plan pays for the weapon uses it spends, over the cheapest weapon that makes the same strike

**Accepted (2026-11-18, #642).** Found by #641: in vanilla E_20 the bot had spent Siegmund and
Excalibur on lesser enemies before reaching Morva. A player saves a weapon like that for when it
is needed; no plan priced a use.

**The rule (ADR 0396: a price, not a ban).**
- A strike keeps the weapon expected damage picks. Each cheaper weapon of the unit that makes the
  same strike (same target, same tile) rides along as a *spare*.
- The beam never sees the price. After the judge reads the best plan, a spare step (`planner.lua`)
  judges it again with each spare swapped in; the price is charged there only, in gold through
  `W.gold`: the expected uses spent (`sight` `attackOf.uses`: blows × the 2RN hit chance, every
  blow for a weapon that does not miss) × the weapon's charge per use over the cheapest weapon
  that makes the strike (`Bot.useCharge`).
- A shop weapon's price per use is the game's `costPerUse`; between two shop weapons the charge
  is the difference. An unbreakable item (`IA_UNBREAKABLE`: `GetItemAfterUse` takes no use)
  costs nothing a use (`sight.usePriceOf`).
- A weapon the game gives no price (a Sacred Twin, Excalibur, the legendaries: `costPerUse` 0)
  is always the dearest: it costs `Bot.RARE_USE` = **300 gold** a use over the dearest shop
  weapon that makes the same strike, so over any spare at least 300, whatever that spare's shop
  price (PR #643 review: a flat 300 made a Siegmund cheaper than a 600-gold Spear, and the
  legendary rode as its spare). 300 (Nicolas, 2026-11-18, on the investigation's
  recommendation): the highest price tested where one use over a cheap spare stays under one
  death's weight in every style (12 / 24 / 45 points careful / even / bold, against a death's
  1000 / 300 / 60). That bound holds only when the strike's dearest shop weapon is cheap (a
  Steel or Silver weapon, tens of gold a use). Beside a dear one it does not: with a Spear
  (600 a use) and an Iron Lance, a Siegmund use over the Iron Lance costs 892 gold, about 134
  points under bold, more than a death. No rule that keeps the unpriced weapon the dearest can
  stay under bold's death weight there, since the Spear alone over the Iron Lance is already
  592. Untested in play; the cap still reads survival first.
  `PT_USEPRICE=off|<gold>` overrides it; `off` is the bot before #642.
- With two or more strikes that have spares, the spare step also judges each one's cheapest
  spare swapped in at once.

**Why the beam never sees it (confirmed, #642 comment 6970344369).** The first cut took the
price off a strike's own score in the beam, which keeps each unit's four best acts by that
score. `PT_SHADOW` (each decision also planned at another price, judged, never played) found 5
of 41 dropped Twin strikes where the priced plan was over the death cap and the Twin plan under
it: the beam cut the strike before the judge read the life it saved. On the spare step, 292
decisions, none.

**Measured (Ch17 from `bag1-heal4-heal1-lap4e-cs-s4006`, `attempts`, dice seeds 1-3, 18 games):**
price off 15 won, 7 player deaths, 34 Twin strikes; this rule 18 won, 8 deaths, 15 Twin strikes.
300 and 600 play the same 18 games. With the review's amendments (the unpriced weapon over the
dearest shop weapon, unbreakable items free, the all-swapped plan's cheapest spares; 73ef1d5a)
the same 18 games: 18 won, 7 deaths, 13 Twin strikes. CPU: the item's full uses are memoised (one game call per
strike weighed before), 20.1 → 17.3 s a player phase on the same 6 games.

**Not settled by it.** E_20's boss: the saved Siegmund did not break Morva; every throne assault
seats strikers that deal 0 (#641's "found instead"). In E_20 the price barely saved Excalibur
(9 strikes at 600). Prices under 300, and whether 300 keeps enough of Ch17's 30 Siegmund uses
for Morva, are untested.
