---
id: 59
title: "How the deploy cap + prep screen are actually wired (the [decomp] mechanism)."
date: "2026-06-10"
section: "Combat System"
issues: []
---

# How the deploy cap + prep screen are actually wired (the [decomp] mechanism).

`hasPrepScreen` in `chapter_settings.json` is dead — "left over from FE7"
(`chapterdata.h:37`). The real gate is the `PREP` event command (0x3E,
`Event3E_PrepScreenCall` → `gProcScr_SALLYCURSOR`): every vanilla prep chapter
(Ch4+) ends its beginning scene with `CALL(EventScr_08591FD8)` (`eventscr.c:4283`,
a shared `CLEAN`/`PREP`/`CLEAN` script), and so does our ch01. The deploy cap is
the **ally `UnitDefinition` table itself**: `GetChapterAllyUnitCount()` counts its
entries (zero-terminator scan), the prep flow clamps deployment to that count
(`SortPlayerUnitsForPrepScreen`), and the table's `xPosition/yPosition` are the
deploy tiles. The table is never LOADed on a prep chapter — the whole party joins
via a separate join-LOAD in the beginning scene and the engine benches everyone
past the cap. Force-deployment = `gForceDeploymentList` (`data_event_trigger.c`,
`{pid, route, chapter}`; vanilla: Eirika/Ephraim everywhere + per-chapter joiners) —
#42's chosen-lord patch point. Prep-header cosmetics: `prepScreenNumber` in
chapter settings is a double-wide glyph index = **2 × chapter number**.
Note ch01 has a prep screen where vanilla Ch1 has none: the cap is the parity;
Pick Units only chooses *which* PCs fill it (Nicolas, 2026-06-10).
_Decided: 2026-06-10 (decomp trace, ch01 slice)_

**Ch2 "Cold Welcome" hosting (#22): slot 3, party-persist, DefeatAll — simpler than ch01.**
ch02 rides the *next* vanilla slot after ch01 (slot 2 → slot 3, `CHAPTER_L_3`), reached by
ch01's ending `MNC2(0x3)` (was the dev placeholder). Three ways it diverges from `inject_ch01`,
all because the slice is mid-campaign rather than the cast's first chapter:
(1) **Party persists** — no *founding-cast* join-LOAD; the saved roster carries over and the prep
flow fields 5 of it (cap = `UnitDef_Event_Ch3Ally` entry count). The one exception is an **off-map
recruit** who joined in a cutscene and was never a unit (Baxby, ch01 ending): he gets a small
between-chapter join-LOAD before PREP so he enters the saved party — see the Recruit-wiring ADR. (2) **No lord-select** — the lead was
chosen in ch01; the flag-driven `IsCharacterForceDeployed_` hook auto-force-deploys it in *any*
later chapter with zero per-chapter wiring (only `CauseGameOverIfLordDies`, already vanilla in
`EventListScr_Ch3_Misc`, is needed). (3) **DefeatAll, not Seize** — the slot-3 host `goal` is
swapped to vanilla **slot-4's `defeat_all` template** (`windowDataType: defeat_all`), and the
vanilla Ch3 `Seize(14,1)` + chests/doors are dropped from `EventListScr_Ch3_Location`, so the
engine's `CountRedUnits()` rout-win is the only path.
**The combat is a faithful reskin of vanilla FE8 Ch2 "The Protected" (the parity_reference).**
The RED band (`UnitDef_088B463C`, Beginning-scene `LOAD1`) is vanilla Ch2's exact count/level/mix —
4 generic Brigand (L3, L3-drops-Vulnerary, L3, L2) + 1 Archer (L1) + Bone (named L4, fixed) + Bazba
(named L6, Steel Axe), grounded in decomp tables `UnitDef_088B4344` + `UnitDef_088B44AC` —
**reflavored as chardalyn berserkers** (Auril-maddened humans; real axes/bow = zero reskin stretch, so
balance is exactly vanilla's). Halvar rides the Bazba slot, Grukk the Bone slot. The turn-3
reinforcement pair (vanilla `UnitDef_088B4470`: L2 + L3 Brigand) rides `UnitDef_088B4758` (the empty
vanilla table), freeing `UnitDef_088B4718` for the protect layer.
**The protect layer = three GREEN chwinga, with a per-unit soft-fail charm-gift (the chapter's
signature beat).** Replaces the abandoned sled-defend idea. The chwinga are harmless snow-spirits
(book: "Starting Quest: Nature Spirits", p25–26) on the **Pegasus chassis** (`CLASS_PEGASUS_KNIGHT`) —
the verified balance match to vanilla's green Ross+Garcia (3 pegs ≈ 9–11 output vs 12; Mage over-shoots
Res≈0 brigands, Myrmidon wildly over). They LOAD GREEN from `UnitDef_088B4718` (vanilla Ch3's Colm
green table, repurposed), ride three distinct minor NPC slots (DARA/KLIMT/MANSEL) so each is
individually trackable, and the **single enemy Archer hard-counters the fliers** — that bow IS the
protect tension. The mechanic is the idiomatic FE8 survival idiom, NOT a death-flag: at the ending
scene each chwinga's survival is read with `CHECK_ALIVE` → `BEQ(skip, EVT_SLOT_C, EVT_SLOT_0)` →
`SVAL(EVT_SLOT_3, <charm>)` + `GIVEITEMTO(player leader)`. A fallen chwinga simply forfeits its own
charm — never a game over. The three charms are vanilla Ch2's three village gifts 1:1 —
**Red Gem `0x76` / Elixir `0x6D` / Pure Water `0x6E`** (in-budget by the Reward ADR; no boosters/promos).
No on-map chest and `gold_reward: 0` — vanilla Ch2 has neither (the gifts ARE the loot).
**Two non-obvious gotchas this surfaced:**
• **The winter map is a faithful reskin — walkability ≈ vanilla FE8 Ch2.** A cell-by-cell terrain
diff (our `.mar` vs vanilla `Ch2Map`, terrain bytes off each tileset's `.bin`) differs on **2 of 225
cells** (the two village tiles). So positions are authored on the built `.mar`'s walkable tiles
(plains/forest), verified in-bounds. Two real traps: (1) author against the committed **`.mar`**, NOT
an ephemeral editor-export grid — that review grid disagrees with the build on ~5 cells; (2) positions echo
vanilla Ch2's geography (boss/archer/Bone east, the lone Vulnerary-dropper on vanilla's SW `(6,10)`
tile, chwinga + party NW) but stay on distinct walkable cells — vanilla stacks several units on shared
spawn tiles via REDA entry-paths, which our `redaCount: 0` direct placement can't. (The parity the gate
enforces is the enemy *count/level* mix, not exact tiles.)
• **Ch2 cutscene msg-id pool = dead vanilla Ch3 scene texts** `0x98b–0x992, 0x995–0x99a`
(referenced only by the `ch3-eventscript.h` scenes our host overwrites). **`0x993`/`0x994` are LIVE
battle quotes in `data_battlequotes.c`** and are deliberately excluded — the exact false-negative
the handoff warns hex-grep produces.
**Deferred (flagged in code, not in this pass):** the **dialogue reground** — the LOCKED 2026-06-19
cutscene text still frames the dropped sled (Wolfram's rear-bark "…the sled"; the ending narration
"…ringing the sled") and the reinforcements as "Snow Wolves", and the opening lacks a chwinga intro
beat; this is a Nicolas co-write via the `dialogue-pass` skill (chwinga intro beat + de-sled the
bark/ending), wired as placeholder meanwhile. Also deferred: the **chwinga art** — map-sprite reskin +
portraits + name-text (`Mote/Rime/Glimmer`) over the DARA/KLIMT/MANSEL placeholder slots (#38/#39);
Vellynne's cutscene bust (#19 — placeholder `FID_Ismaire` face meanwhile); the chardalyn map-sprite
reskin (vanilla brigand sprite for now); the "Chapter 2" title-card glyphs (atlas lacks C/W/d/m); and
the in-game load-test. The chapter builds green, decodes clean (`verify_text` 0 runaway), holds
difficulty parity, and chains ch01 → ch02 → ch03 (`MNC2(0x4)`; see the Ch3-chains ADR above —
the ch02 ending's original dev-placeholder landing was retired when ch03 landed).
_Implemented: 2026-06-22 (CLAUDE; content track — host wiring + cutscenes, build-green). Reground
2026-06-22 (CLAUDE) — vanilla-Ch2 enemy parity (chardalyn berserkers), 3 green chwinga + per-unit
soft-fail charm-gifts, sled dropped._
