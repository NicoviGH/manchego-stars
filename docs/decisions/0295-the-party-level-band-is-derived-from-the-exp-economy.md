---
id: 295
title: "The party-level band is DERIVED from the exp economy, and the prologue pays it nothing"
date: "2026-09-18"
section: "Combat System"
issues: [367]
---

# The party-level band is DERIVED from the exp economy, and the prologue pays it nothing

`docs/fe8-pacing-reference.md` carried an expected-party-level table that opened *"Not derived,
and it cannot be"*, on the grounds that vanilla's ally `UnitDefinition` level is read only on a
unit's first load, so IS never states what its own party is by Ch6.

That is true about vanilla's **ally tables** and false about the question. A party's level is
not a stated fact anywhere; it is the **integral of the exp its chapters pay**, and every term
of that integral is data we already hold — FE8's exp formulas in `src/bmbattle.c`, and the real
per-chapter rosters on both sides. `tools/exp_curve.py` transcribes the four functions
(`GetUnitRoundExp` / `GetUnitPowerLevel` / `GetUnitKillExpBonus` / `GetBattleUnitExpGain`, the
term that does the work being `classRelativePower`) and runs them over `difficulty`'s own
roster readers. The band is now generated into that doc between fences and held fresh by
`tools/test_exp_curve.py`.

**Only the COMMON-route branch of the kill bonus exists for us.** `GetUnitKillExpBonus` splits
on `(gBmSt.gameStateBits & 0x40) || (gPlaySt.chapterModeIndex != 1)`; the else — mode 1 —
halves the killer's power-level penalty when the target is weaker. `savemenu.c:537` starts every
new game at mode 1 and only `ch8-eventscript.h`'s route split ever writes another value, which
needs a world map we do not have. So mode 1 is our whole campaign, and it is equally FE8's own
Prologue–Ch8, which is every twin we measure against.

**What it says.** Entering ch07 the founding party is **L6** typical — L3 for a unit on the
bench, L12 for one fed every kill, and **L1 for anything recruited into it** — and the same cast fed each chapter's vanilla twin instead of ours
reaches the same level over the same span. Every chapter's exp yield is within ±12% of its
twin, which `tools/test_exp_curve.py` asserts, because exp is the only quantity in this repo
that **integrates across chapters**: no per-chapter gate can see a chapter reusing a twin an
earlier chapter already spent (ch07 is planned against FE8 Ch6, which ch06 already banked).

**The prologue pays the party nothing, and its twin pays vanilla's party a full chapter.** ch00
is a fixed-roster chapter whose two units are guests — Hlin and Scramsax never join — so its
exp is banked by nobody, while FE8's prologue pays Eirika and Seth, who stay for the whole game.
The two curves converge anyway, because FE8 pays a lower-level unit more for the same body; that
convergence is the cross-check that makes the absolute number usable rather than a coincidence.

**A unit earns from the chapter after it JOINS, and every recruit joins at level 1.** The
first cut ran all thirteen roster members from ch01 and handed four of them an exp history
they never had. Availability is `recruit_chapter_number`, the same answer `cast_available_at`
sizes the deploy caps from. It also splits the band's population from the recruit floor: the
three share columns describe the FOUNDING party, because mixing a ch05 recruit into the low
edge pins it at L1 for every chapter after a recruitment — which stops being a statement about
how much a unit is fed and becomes one about when it joined. The recruit floor gets its own
column, and it is the number a chapter's survivability has to clear.

**A body's field count is what the chapter FIELDS, not what the roster holds.** `deploy_limit`
answers it wherever there is Pick Units; a fixed-roster chapter has none, and falling through to
the whole roster split the prologue thirteen ways and understated its twin six-fold.

**CA_BOSS is a question about the SLOT, and `ENEMY_BASE_SLOT` was the wrong table to ask.** The
kill bonus pays +40 off `CA_BOSS`, which lives on CharacterData. `ENEMY_BASE_SLOT` maps our
enemy ids to the vanilla slots whose **stat line** they inherit, and it deliberately excludes
`inject_prologue`'s guests, whose personal bases are zeroed — but zeroing a stat line does not
clear an attribute, and Sephek's DefeatBoss fires precisely because he keeps ONEILL's CA_BOSS.
Reading the boss question off the stat table underpaid the whole prologue by a 40-exp kill bonus
and read ch00 at x0.76 against its twin. `build_campaign.ENEMY_CHARACTER_SLOT` is now the table
for the attribute question, and it is derived from the stats one rather than repeating it.

**Not modelled, on purpose.** Stat *growth* (growths are random; a projected stat line is a
precision the dice do not support — #367 says so explicitly). Chip damage that does not kill,
staff exp, arena exp, and anything the player farms: all of them ADD, on both sides, so the
typical column is a floor rather than a forecast. And `difficulty.py` still does not read any of
this — `player_combatant` resolves the cast at base level on purpose, because the parity ratio
cancels an understated party on both sides and a projected level fed to one side only would
break that cancellation rather than improve it.
