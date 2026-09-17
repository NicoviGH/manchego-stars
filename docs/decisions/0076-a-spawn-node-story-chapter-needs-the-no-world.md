---
id: 76
title: "A spawn-node story chapter needs the no-world-map title fallback, not just a recomposed card."
date: "2026-07-11"
section: "Combat System"
issues: []
---

# A spawn-node story chapter needs the no-world-map title fallback, not just a recomposed card.

Writing `chap_title_<chapTitleId>.png` is necessary but **not sufficient** for a chapter whose
host slot maps to a world-map monster-spawn node. Both the intro banner (`chapterintrofx*`) and
the Status screen (`uichapterstatus`) read the title via **`GetChapterTitleWM`** (`chapter_title.c`),
which returns a **skirmish-name card** (`0x46 + i`) when the node is in `gWMMonsterSpawnLocations`
*and* `GetNextUnclearedNode(&gGMData) != unk`. Vanilla only takes that branch on a postgame revisit;
during a story playthrough the node is the next uncleared one, so it returns `chapTitleId`. Our build
has **no world map** (see the `GetBattleMapKind` STORY fallback below), so `gGMData` node states are
never populated → the branch always fires. ch01/ch02 escaped it only because their slots' nodes aren't
spawn locations; **ch03 hosts vanilla slot 4 = `WM_NODE_ZahaWoods` (the first spawn node)**, so it
rendered "Za'ha Woods" over its own card until fixed. Fix = a campaign-agnostic engine hook
(`_patch_chapter_title_wm_fallback`, sibling to the battle-map-kind fallback) neutering the guard so
`GetChapterTitleWM` always returns the ROM `chapTitleId`. Verified in-engine (`PT_HOST_CHAPTER=4
run.sh titlecard` → `docs/demo/ch03-title-card-ingame.png`). **Separately**, the borrowed slot-6
defeat_boss goal block leaked its Status *objective* text ("Defeat Saar", vanilla Ch6's boss) because
inject_ch03 set `chapTitleTextId` but not `statusObjectiveTextId` — now set to `'Defeat '+<boss fe_name>`
("Defeat Grell"), the prologue precedent (the goal WINDOW banner is a static "Defeat boss" by goal type, so
only the Status-objective text leaked). ch03 load-tests `smoke_ch03`/`clear_ch03` added (mirror ch02;
`clear_ch03` routs via real combat, wiring-not-balance, since the grell has no `CA_BOSS`).
_Decided: 2026-07-11_
