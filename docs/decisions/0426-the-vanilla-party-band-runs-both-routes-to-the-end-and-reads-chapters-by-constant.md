---
id: 426
title: "The vanilla party band runs both routes to the end and reads chapters by constant"
date: "2026-11-18"
section: "Combat System"
issues: [639, 510]
---
# The vanilla party band runs both routes to the end and reads chapters by constant

**Accepted (2026-11-18, #639 Part B).** `tools/exp_curve.py --route eirika|ephraim [--promote-at 10|20]`
walks FE8's own party from the Prologue to Ch21x and prints, per chapter, the deploy cap, the
enemy bodies and the exp level of the army's lord after it, as low / typical / high.

**Chapters are named by `include/constants/chapters.h`, never by `internalName`.**
`chapter_settings.json`'s E-names run one behind the chapter number from Ch12 on (`E11` is Ch12,
`E12` is Ch13 Hamill Canyon), because Ch11 sits out of line at 0x3D (Eirika, Creeping Darkness)
and 0x3E (Ephraim, Phantom Ship). `inject.decomp.chapter_enum()` is the one reader of the
header (`campaign_env` and `montecarlo` call it); `difficulty.route_chain`, `ref_stem`,
`ref_title` and `ref_mode` read through it. The route chains are the shared route (Prologue,
Ch1-Ch4, Ch5x, Ch5-Ch8, `FE8 ...` twin names), then `CHAPTER_E_9 .. CHAPTER_E_21X` or
`CHAPTER_I_9 .. CHAPTER_I_21X`, Ch11 in its place. `VANILLA_CHAIN` is not that chain (it has no
Ch5x) and does not change; the parity reads stand on it. `_vanilla_internal_name`,
`vanilla_chapter_shifts` and `vanilla_forced` still resolve by name, which reads Ch13 as Ch14
(a separate issue); that is outside this record.

**The enemy force of a chapter nobody curated is derived by the registry's own rule.**
`difficulty.derive_red_arrays(stem)`: every UnitDefinition array the chapter's eventscript loads
whose RED units include an armed one, minus the arrays loaded only to stage a scene
(`scene_only_udefs`: every LOAD sits before a CLEE) and minus the arrays loaded only in an
`*_EndingScene` (`ending_only_udefs`: the chapter is already won, so nothing loaded there is
fought). The rule reproduces the curated Ch1-Ch8 and Ch13 entries exactly (a unit test). Ch13 needed
the ending-scene clause: its ending stands Caellach up, armed, on the next chapter's map. The
Prologue stays curated: its Valter group is a scripted Seth-Valter fight in the opening scene,
which the rule cannot tell from a unit on the map. `exp_curve.py --route` lists, per chapter,
the kept arrays a script also fights or removes (`scene_suspects`), because the rule neither
drops those nor vouches for them. Registry readers see none of it: `vanilla_red_units`
and `_vanilla_red_defs` take `derive=True` and default to the curated registry.

**Where Ch5x fits.** Vanilla plays it on every route, after Ch4. Its ally list (Ephraim, Forde,
Kyle and a guest, Orson) names only characters who join in it, so it is a fixed-roster chapter
(like the Prologue): only they earn from it (`_roster_chapter`), and Eirika's party does not. On
a route chain Ephraim's band therefore joins in Ch5x at the levels its own load places them
(4, 6, 5), where `VANILLA_CHAIN` has them join in Ch8 at the same levels.

**The deploy cap is the length of the chapter's `playerUnitsInNormal` list**
(`GetChapterAllyUnitCount`, eventscr3.c:432, which `prepscreen.c` reads), counted to the first entry
with no charIndex. A run reads fewer where it owns fewer units: the bot's lap read 9 for Ephraim's
Ch9, where the list is 11, and 17 for Eirika's Ch20, where it is 18; its Eirika Ch17 and Ephraim
Ch14 read 12, the list's length. Where a hosted chapter names the twin, the walk keeps our
cap (the cap is the parity): that is Ch1, where the list is 2 (Eirika, Seth) and the scene
stands Franz and Gilliam beside them, which our 4 counts.

**Kill exp from Ch9 on.** `GetUnitKillExpBonus`'s other branch (`chapterModeIndex != 1`: target
power + 20 - actor power, no halving) applies to every route chapter; `ch8-eventscript.h` writes
mode 2 or 3 at the split. A gorgon egg pays 50 and the Demon King 0 (`ModifyUnitSpecialExp`),
both on the routes (Ch18, Ch21x).

**Away units.** From the split until the first chapter that stands the other lord up armed and
BLUE (Ch15 on both routes), the other lord's band is off the field and earns nothing: Eirika on
Ephraim's route, Ephraim, Forde and Kyle on Eirika's. Seth, Franz and the rest are on both
routes' ally lists (ch9a, ch9b).

**The band is read over the lord**, not the founding pair: Seth is a promoted Paladin from the
Prologue, so a mean over him and Eirika (L1 and 21) is a level no unit has. The lord is Eirika
to the split and the route's own from it; the step at the split is the change of lord.

**Recruits.** `vanilla_recruits(chain, slot_order=True)` walks any chain. Both routes' Ch10 recruit
orders are the player's (Eirika's Gerik and Tethys talk to each other; Ephraim's Duessel and
Cormag are independent), so the guard raises on a route chain as it must. The walk passes
`slot_order=False`: it needs who joins when (all from the next chapter), not which unit-table
slot each takes. The default is unchanged.

**Promotion** is one parameter of the walk, `promote_at` (10, 20, or None = hold at 20 as before,
the default until Part A's laps decide). A unit promotes after the chapter in which it reaches it
(ApplyUnitPromotion: level 1, exp 0, in `class_promotion`'s class) and is compared at its exp
level (`GetUnitExpLevel`: level + 20). Units with no single `.promotion` hold: the trainees, the
Monk (its Guiding Ring target is in `data_itemuse.c`, not the class), and Myrrh, whose
`.promotion` is not a promoted class. This is a model limit, not the game's rule.
