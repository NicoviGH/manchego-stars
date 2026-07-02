# Parked: Kitsune (fox laguz) battle animation — for Meesmickle

**Why parked here:** Meesmickle is a Vampire Tabaxi "aristocat" (FE Shaman). The GBAFE
community has **no** purpose-built sleek-cat battle animation; this **Kitsune** anim is the
closest sleek-quadruped-beast base to reskin into a black panther/cat (recolour black + add
the red cape). Stored locally because FE-Repo / community links rot.

**Source:** [\[Wolf-Variant\] \[F\] Kitsune by ZoramineFae](https://github.com/Klokinator/FE-Repo/tree/main/Battle%20Animations/Monsters%20-%20Basic%20Types/%5BWolf-Variant%5D%20%5BF%5D%20Kitsune%20by%20ZoramineFae)
**Authors / credit:** ZoramineFae, Clendo — **F2E** (free-to-edit). Credit them on use.

**Format:** standard GBAFE sheet+script (248×160 canvas) — `Monster.txt` script + `Monster Sheet 1–4.png`
+ `Monster.gif` preview. The 144 individual frame PNGs were NOT stored (derived from the sheets).

**Status:** PARKED as an *alternative* base. The battle-anim pipeline that actually shipped (#65,
2026-06: RBG + braulo) is the per-character 3-frame descaled-pose path (`build_battle_anim` +
`tools/descale_battleframe.py`), which does NOT consume full GBAFE sheets like this one — meesmickle's
planned route is the Shaman donor + 3 descaled poses (see `HANDOFF.md` §the other 5 PCs). This sheet
stays parked in case a full-sheet reskin is ever wanted instead. The Meesmickle **map sprite** uses
the FE-Repo **Tiger** (see `map_sprites/` — sandbox `meesmickle-tiger`).
