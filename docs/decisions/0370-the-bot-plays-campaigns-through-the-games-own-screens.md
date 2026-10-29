---
id: 370
title: "The bot plays chapter to chapter through the game's own screens, and shops at the world map's open stock"
date: "2026-10-27"
section: "Combat System"
issues: [510]
---

# The bot plays chapter to chapter through the game's own screens, and shops at the world map's open stock

#510 step 9 PR E. `tools/playtest/campaign.lua` plays a campaign from New Game: it rides the game
to each chapter's start, saves a state there, and attempts the chapter until it clears with
everyone alive. It is pure (tested with a fake api, `test_campaign.lua`); harness.lua's
`INSPECT.campaignApi` is its only window on the ROM, and **every rule in it is the game's** (the
standing rule of ADR 0369: never re-create vanilla).

**Restarts (the amendment on #510).** A failed attempt -- lost, stuck, or won with a death -- loads
the chapter-start state back and draws a NEW style (aggression uniform, the deploy order a
uniform shuffle of the non-forced roster, each claim followed with p = 0.5). The RNG is never
re-seeded: FE8 seeds it once at power-on and a suspend save stores it, so a restart differs only by
the bot's play. The campaign seeds the game once, at the first chapter. At most 300 attempts, then
the chapter is reported `infeasible` and the campaign stops (no clean run reached anything later).
A `crashed` attempt is the harness failing, never the bot: it stops the campaign and is never
retried, so it cannot hide behind a restart. The route (1 or 2) is drawn once per campaign.

**Between chapters, all through the game's own screens:**

| step | how |
|---|---|
| world map | the game's free cursor (`WorldMap_Loop`): L moves the cursor to the next open node until it is on `GetNextUnclearedNode` (run in the sandbox), A walks the lord there, A again enters the chapter. It never enters any other node, so never a skirmish, the Tower or the Ruins |
| deploy | the Pick Units screen: the cap is its own `max_counter`; `Bot.team`'s list is picked row by row (benching first, so the cap never blocks), then Fight! The roster is the game's own `MakePrepUnitList`, run in the sandbox (`gPrepUnitList` is an EWRAM overlay other prep screens reuse), while `ProcScr_AtMenu` owns Preparations |
| team | `Bot.team` over what the map asks (`Sight.demands`, read once per chapter start) and how each unit answers it (`Sight.answer`: the forecast, `GetUnitKeyItemSlotForTerrain`, `GetUnitFogViewRange`, `CanUnitUseStaff`, `GenerateExtendedMovementMap` for villages); each unit's group from `team_groups.py`; the cleared team carried to the next chapter. The record names each pick's reason |
| lead | ours: ADR 0062's ch01 menu answered with the campaign's `lord` row (`INSPECT.pickMenuRow`, shared with `reachCh01`), then its Yes. Vanilla's route is the campaign's `route` setting, never drawn, answered on Ch8's route split menu (`MenuDef_RouteSplit`: row 0 Eirika, row 1 Ephraim) by the same picker, then its Yes |
| shops | `StartShopScreen(unit, stock, type, the player phase)` as a **kept** call (sight.lua's sandbox with the registers put back and the RAM kept), then the shop's own list, prompts and exit by their keys, one purchase per opening. Priced by `GetItemPurchasePrice` on the map, never during prep (it charges half again while `BM_FLAG_PREPSCREEN` is set). Which units may wield what is `CanUnitUseWeapon` |
| seals | the unit's Item command, the seal's row, Use; who a seal promotes is `CanUnitUsePromotionItem`. A branched promotion takes the first class the game's menu offers |

**Which shops (Nicolas, 2026-10-27).** Both games shop on the chapter's first player phase, at
every Armory and Vendor of every world map node the game has OPEN (`gGMData.nodes[]`
`GM_NODE_STATE_VALID`), from the node's own stock (`gWMNodeData`). The lord is not walked to
them: walking could start a skirmish, and opening the screen directly gives both games one path.
**Ours has no world map yet (ADR 0060), so it gets the twin's at the same point:** the vanilla
campaign writes the open nodes into each chapter-start record, and `campaign_env.py` hands ours
the twin's (`difficulty.VANILLA_CHAIN[N]`, the chain the kit model reads, ADR 0365). Our ROM holds
the same `gWMNodeData` and stock lists, so ours opens the same lists through its own shop screen.
When our world map lands, ours reads its own and nothing else changes. Secret shops (they need a
Member Card) are not visited.

**What a run leaves.** `references/sim/<game>/<rom-hash>/states/<campaign-id>/<chapter>.ss` (the
chapter-start state, written from `emu:saveStateBuffer`: mgba-headless's `saveStateFile` writes
zeros) and `<chapter>.json` (party, gold, items, open shop nodes: what the game gave). Each
attempt prints its `BOTRUN` line (with `campaign` and `attempt`), each chapter a `CAMPAIGN` line
(attempts, every failed attempt's style, outcome and deaths), and the campaign a last one.

**A kept call is safe at a frame boundary (measured).** The harness's frame callback finds the CPU
in the BIOS halt loop (ARM, System mode, pc 0x1F8). mGBA's pc write refills the pipeline, so a pc
written back reads one instruction (4 bytes) ahead; writing `pc - delta` puts it back exactly, and
the game runs on (`Sight.machine(cpu, true)` measures the delta on every restore and raises if it
does not land).
