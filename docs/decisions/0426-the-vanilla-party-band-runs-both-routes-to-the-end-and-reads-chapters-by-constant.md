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

**The field is vanilla's own, for the whole walk** (`difficulty.vanilla_field`, what the walk splits
exp across; `vanilla_arrivals` and `simulate` keep the hosted caps, so the parity reads do not move).
It is the length of the chapter's `playerUnitsInNormal` list (`GetChapterAllyUnitCount`,
eventscr3.c:432, which `prepscreen.c` reads), counted to the first entry with no charIndex, plus the
armed BLUE playable units its turn events bring in that the list does not name. Only Ch1 has any:
its list is Eirika and Seth, and `EventScr_Ch1_Turn_AllyReinforceArrive` loads Franz and Gilliam,
so four fight. The two readings agree on every chapter a hosted chapter names (a test). Checked
against the bot's own vanilla laps (`team.cap` in each trace's start line, 23 chapter indexes with
data): 22 read the list's length exactly, across Ch4-Ch19 on both routes and Ch11 on both; Eirika's
Ch20 reads 17 where the list is 18 and the team owned 17 units (`min(list, owned)`). Ephraim's Ch9
reads 11 in 41 runs. (An earlier note that it read 9 was Ch8's 9, recorded under route 2.) The
store has no start data for the Prologue, Ch1-Ch3, Ch5x or Ch21 on, so those rest on the lists.

**Kill exp from Ch9 on.** `GetUnitKillExpBonus`'s other branch (`chapterModeIndex != 1`: target
power + 20 - actor power, no halving) applies to every route chapter; `ch8-eventscript.h` writes
mode 2 or 3 at the split. A gorgon egg pays 50 and the Demon King 0 (`ModifyUnitSpecialExp`),
both on the routes (Ch18, Ch21x).

**Away units.** From the split until the first chapter whose ally list names the other lord (Ch16
on both routes; the lords meet in Ch15 as a cameo load that is not deployable), the other lord's
band is off the field and earns nothing: Eirika on Ephraim's route, Ephraim, Forde and Kyle on
Eirika's. Seth, Franz and the rest are on both
routes' ally lists (ch9a, ch9b).

**The band is read over the lord**, not the founding pair: Seth is a promoted Paladin from the
Prologue, so a mean over him and Eirika (L1 and 21) is a level no unit has. The lord is Eirika
to the split and the route's own from it; the step at the split is the change of lord. This is a
different reading from `simulate`'s founding-careers band (Manchego Stars' own unpromoted party);
the two measure different things and are not meant to agree.

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
`.promotion` is not a promoted class. This is a model limit, not the game's rule: those units stay
at level 20 whatever `promote_at` is. A recruit that joins at `promote_at` or above is promoted the
chapter it is on the field, whether or not it earns anything in it.

**Counted reinforcement loops.** An array a script reloads under `COUNTER_DEC(n)` (re-arming until
`COUNTER_CHECK(n)` reaches 0) arrives once per wave; the waves are the Normal-mode `COUNTER_SET(n, k)`
that starts the counter (`difficulty.reinforcement_waves`; a set after a `CHECK_HARD` is the hard
refill and is not counted). Ch21's three RED bodies of class 0x3 (Ephraim Master Lord, L5,
`UnitDef_088C1CE0` / `088CB524`) are fought: `EventScr_089F9448` (ch21a-eventscript.h:194) loads
them in a loop that `COUNTER_SET(0x2, 10)` starts, so thirty arrive. Chapters with counted loops
today: Ch9b, Ch14a/b, Ch16b, Ch17a/b, Ch20a/b, Ch21a/b. A loop no single Normal-mode set sizes
(none, two, or a tutorial-only one) raises naming the chapter and script. The class is named through
`inject.class_ids.vanilla_class_for_token`, which raises on an unknown or ambiguous id.
