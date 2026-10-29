#!/usr/bin/env python3
"""Emit the harness symbol tables from the built ELF.

Run after every `make` (run.sh does this) -- BSS/EWRAM addresses shift when
engine code changes, so the Lua harness must never hard-code them.

Three outputs, one nm pass:

  symbols.lua   the named symbols the harness reads/scans (SYM), plus CAMPAIGN: the cast
                pids, host slots and chapter facts the scenarios read, resolved from the
                injector's own constants (`campaign_ids`)
  procscr.lua   every proc-script address -> its exact symbol (PROCSCR), so a live
                proc is identified by SCRIPT ADDRESS instead of by the PROC_NAME
                string at proc+0x10. Those strings are not unique -- the decomp
                gives gProcScr_E_FACE and gProcScr_E_FACE_ExtraFrame both
                PROC_NAME("E_FACE"), and reuses "bmenu" and "E_config" three times
                each -- which is why freeze reports could not say which proc was
                waiting (#236, blocking #232).
  symbols.json  every ROM code symbol, for inspect_state.py. Idle callbacks are ordinary
                functions (~35k of them): too many for a Lua table, so the Lua side
                dumps raw addresses and the Python renderer names them.

Resolution against these tables is EXACT-MATCH ONLY. An address that matches no
symbol is reported as unknown; a nearest-preceding guess is worse than silence.
"""
import json
import os
import re
import subprocess
import sys
from collections import namedtuple

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(REPO, 'tools'))
from inject.class_ids import DEFAULT_CAMPAIGN  # noqa: E402
from inject.decomp import DECOMP, enum_values, vanilla_decomp_text  # noqa: E402  DECOMP is the build tree (#408); the reads are HEAD
ELF = os.environ.get('PT_ELF') or os.path.join(DECOMP, 'fireemblem8.elf')   # PT_VANILLA (run.sh)
HERE = os.path.dirname(os.path.abspath(__file__))
# PT_SYMDIR: where the tables go. run.sh gives retail FE8 its own (PT_VANILLA): one shared
# set let an ours run started beside a vanilla one overwrite vanilla's addresses before its
# emulator loaded them, and the vanilla run hung in our IsCharacterForceDeployed (2026-10-29).
OUT_DIR = os.environ.get('PT_SYMDIR') or HERE
OUT = os.path.join(OUT_DIR, 'symbols.lua')
OUT_PROCSCR = os.path.join(OUT_DIR, 'procscr.lua')
OUT_JSON = os.path.join(OUT_DIR, 'symbols.json')

ROM_START = 0x08000000
ROM_END = 0x0A000000

# Proc scripts are `struct ProcCmd[]` in ROM: `ProcScr_X`, `gProcScr_X`, `sProcScr_X`, plus
# the handful named `gProc_X` / `sProc_X`. Keying by address makes a stray match inert
# (nothing looks up its address) while a missed one degrades to an honest unknown -- but
# the table is also what a human reads to learn which proc is live, so it is ANCHORED:
# unanchored, it also swept in proc.c's API (Proc_Init, Proc_Start, Proc_ForEach, ...) and
# two getters whose names merely END in ProcScript -- 30 functions that are not proc
# scripts (#241). A bare `Proc_` prefix is always a function; a script carries the g/s
# storage-class letter.
PROC_SCRIPT_RE = re.compile(r'^(?:[a-z]Proc_|[a-z]?ProcScr)')

Symbol = namedtuple('Symbol', 'name type addr')

# Symbols the harness reads/scans. Struct offsets live in harness.lua next to
# the decomp header they came from.
WANTED = [
    'gPlaySt',                  # chapter index / phase / turn (include/types.h)
    'gArenaState',              # accepted wager/opponent state (include/bmarena.h)
    'gFaces',                   # four struct FaceProc* slots; faceId is u16 at +0x3E.
                                # ch05arena reads the live Arena attendant, not just its art file.
    'gBmSt',                    # live map cursor (include/types.h)
    'gUnitArrayBlue',           # player units (include/bmunit.h)
    'gUnitArrayRed',            # enemy units
    'gUnitArrayGreen',          # green (ally/NPC) units (include/bmunit.h) -- the ch02 chwinga
                                # protect layer rides this array (FACTION_ID_GREEN).
    'gUnitLookup',              # struct Unit *[0xC0] (include/bmunit.h): exact live unit-id
                                # resolution for the cursor's gBmMapUnit entry.
    'gConvoyItemArray',         # the convoy (extern u16[]; include/variables.h). Low byte of
                                # each entry is the item id -- where an overflow charm-gift lands.
    'gConvoyItemCount',         # u8 count of live convoy entries (include/bmcontainer.h).
    'gAiDecision',              # struct AiDecision (include/cp_common.h): the action the AI
                                # just chose -- actor +0x01, target +0x06, item slot +0x07.
                                # ch06halberd reads which weapon the dropper swung, and at whom.
    'gItemData',                # struct ItemData[] (include/bmitem.h): per-item attributes
                                # (IA_WEAPON/IA_STAFF @ +0x08) + encodedRange (min<<4|max @ +0x19).
                                # Lets the harness read a unit's weapon reach generically.
    'sProcArray',               # proc pool: 64 x 0x6C (src/proc.c)
    'gBmMapMovement',           # u8** move-cost map, valid while a unit is selected
                                # (include/bmmap.h; < 120 = reachable)
    'gBmMapSize',               # struct Vec2 {s16 x, y} -- the LIVE map's tile dimensions
                                # (include/bmmap.h). The harness must not assume a footprint:
                                # ch04's 15x15 is smaller than the maps the drive loop was
                                # first written against.
    'gBmMapUnit',               # u8** tile->unit grid (include/bmmap.h): gBmMapUnit[y][x] is the
                                # on-tile unit id the engine uses for cursor selection. Relocating
                                # a unit must update THIS, not just its xPos/yPos.
    'gBmMapBaseTiles',          # u16** metatile grid a chest/door tile-change writes
                                # (ApplyMapChangesById, bmtrick.c). Unlike the other gBmMap*
                                # grids this one lives in ROM .data and is never reassigned:
                                # it holds a constant pointer to the sBmBaseTilesPool row
                                # array in EWRAM. It was HARD-CODED in harness.lua and the
                                # engine grew out from under it -- 0x085AF5DC held 0x000004AB
                                # rather than the pool -- so ch03door/ch03chest failed on
                                # their PRECONDITION, before pressing anything, and read as
                                # broken doors and chests for as long as that lasted. Which
                                # is the entire reason this file exists (#238).
    'gBmMapTerrain',            # u8** terrain-id grid (include/bmmap.h): gBmMapTerrain[y][x] is the
                                # TERRAIN_* id, used to build a passability map for the clear-bot's
                                # BFS march-to-boss (#60).
    'gUnitSpriteSlots',         # u8[0xD0] (src/bmudisp.c): the per-SMS-id VRAM slot cache.
                                # 0xFF = that sprite has NOT been allocated this map. Distinguishes
                                # "the engine never asked for our custom sprite" from "it asked and
                                # the 32x32 VRAM budget was exhausted".
    'gSMS32xGfxIndexCounter',   # the 32x32 map-sprite VRAM cursor (src/bmudisp.c). Grows UP from 0
                                # in steps of 4 while gSMS16xGfxIndexCounter grows DOWN from 0x3F --
                                # the two share one 0x40 slot space, so enough distinct 32x32
                                # sprites on one map starves the later ones.
    'gSMS16xGfxIndexCounter',   # the 16x16 counterpart, for the same reason.
    'gBmMapFog',                # u8** fog map (include/bmmap.h): non-zero = the player can SEE
                                # that tile this turn. A red unit standing on a zero tile is not
                                # drawn at all -- which looks exactly like a broken map sprite.
    'sMsgString',               # struct MsgBuffer (src/msg.c): buffer1 (offset 0) holds the
                                # text GetStringFromIndex last decoded (casthelp reads it)
    'sActiveMsg',               # int (src/msg.c): the message index GetStringFromIndex last
                                # DECODED into its buffer. The only witness to WHICH message a
                                # scene actually showed -- box counts cannot tell two arms of a
                                # branch apart when they render to the same number of A-presses,
                                # which ch05's Talk recruit does exactly (#25). Read it WHILE a
                                # box is up: every menu and unit name decodes through the same
                                # function and overwrites it the moment the scene ends.
    'gChapterFlagBits',         # event flags < 100, bit (flag-1) (src/eventinfo.c)
    'gPermanentFlagBits',       # event flags > 100, bit (flag-101)
    'ProcScr_GameOverScreen',   # proc script: game-over screen active
    'sProc_Menu',               # proc script: a menu is open
    'sProc_MenuMain',           # live MenuProc after sProc_Menu jumps to its input loop
    'Menu_OnIdle',              # exact standard-menu input callback
    'ProcScr_GameEarlyStartUI', # boot health/safety + publisher sequence
    'gProcScr_GameControl',     # root owner; alone means a passive boot transition
    'GameIntroHealthSafetyWaitButton', # exact health/safety input wait
    'Title_IDLE',               # exact title-screen input callback
    'ProcScr_SaveMenu',         # save/New Game menu
    # The BETWEEN-CHAPTERS save prompt is a SECOND proc script (savemenu.c) sharing the
    # same slot-select callback. Watching only ProcScr_SaveMenu left it unclassified, so
    # the ch00 -> ch01 flow parked on it forever (#232).
    'gProcScr_SaveMenuPostChapter',
    'SameMenu_CtrlLoop',        # exact save-menu input callback
    'SaveMenu_SaveSlotSelectLoop', # exact New Game save-slot input callback
    'ProcScr_NewGameDifficultySelect', # New Game difficulty menu
    'DifficultySelect_Loop_KeyHandler', # exact difficulty input callback
    'gProcScr_ChapterIntro',    # chapter-title animation owner
    'ProcScr_ChapterIntro_KeyListen', # chapter-title skip-input child
    'ChapterIntro_KeyListen_Loop', # exact chapter-title input callback
    'gProcScr_TalkWaitForInput', # dialogue waits for a real player key
    'TalkWaitForInput_OnIdle',  # exact dialogue input callback
    'gProcScr_YesNoChoice',     # in-scene Yes/No prompt (src/cgtext.c). Distinct from the
                                # page wait above: it runs INSIDE a live event scene, so
                                # without it the scene reads as a passive std_event
                                # transition and nothing ever answers -- ch01's lord-select
                                # "Will <lead> lead the party?" parked here (#232/#236).
    'YesNoChoice_Loop_KeyHandler', # exact Yes/No input callback. currentChoice is s16 at
                                # +0x2A: TALK_CHOICE_YES = 1, TALK_CHOICE_NO = 2
                                # (include/scene.h); A commits whichever is highlighted.
    'gProcScr_TalkChoice',      # scene.c inline [Yes] choice (arena wager / shop prompts)
    'gProcScr_Shop',            # bmshop.c Armory/Vendor screen; ProcShop.shopItems at +0x30
    'TalkChoice_OnIdle',        # exact inline-choice input callback; selectedChoice @ +0x2A
    'ProcScr_AtMenu',           # preparations main-menu owner
    'ProcScr_PrepMenu',         # live semantic preparations command list
    'PrepMenu_CtrlLoop',        # exact preparations input callback
    'PrepScreenMenu_OnStartPress', # main preparations Fight action
    'PrepScreenMenu_OnBPress',  # main preparations Check Map shortcut (never an exit)
    'PrepScreenMenu_OnPickUnits', # live semantic Pick Units effect
    'PrepMapMenu_OnStartPress', # View Map menu START callback (distinguishes the detour)
    'PrepMapMenu_OnBPress',     # View Map menu B callback
    'ProcPrepUnit_Idle',        # Pick Units input callback
    'gProcScr_PlayerPhase',     # player map state owner
    'PlayerPhase_MainIdle',     # empty/unit cursor input
    'PlayerPhase_RangeDisplayIdle', # selected unit + movement range input
    'PlayerPhase_WaitForUnitMovement', # movement animation/commit wait
    'sProcScr_BMXFADE',         # PlayerPhase_MainIdle suppresses A while this map-fade proc exists
    'gProcScr_TargetSelection', # live semantic map-target selector
    'TargetSelection_Loop',     # exact target-selector input callback
    'gSelectInfo_Attack',       # distinguishes attack targets from other selectors
    'gSelectInfo_Talk',         # distinguishes Talk targets from other selectors
    'gSelectInfo_Heal',         # distinguishes a healing staff's targets (bmitemuse.c)
    'gProcScr_BKSEL',           # passive battle-forecast panel owner; SelectTargetProc, not
                                # this display proc, owns the target-confirmation input
    'BattleForecast_LoopDisplay', # exact stable forecast display callback (still no legal input)
    'gProcScr_ChapterStatusScreen',  # proc script: map-menu Status screen, which
                                # draws the chapter title card (src/uichapterstatus.c)
    'gProcScr_SALLYCURSOR',     # proc script: the preparations screen
                                # (src/prep_sallycursor.c; opened by event cmd 0x3E)
    'StatScreen_OnIdle',        # the status screen's key handler (statscreen.c): R opens help, B leaves
    'gProcScr_HelpBoxMoveCtrl', # proc script: the status screen's help box (statscreen.c)
    'HbMoveCtrl_OnIdle',        # its key handler: the D-pad walks HelpBoxInfo.adj*, B or R closes
    'gProcScr_StatScreen',      # proc script: a unit's status screen (src/statscreen.c), the
                                # only place FE8 draws a unit's 96x80 BUST beside its name,
                                # class and stat line; the controller classifies it.
    'gProcScr_TitleScreen',     # proc script: the title screen (src/titlescreen.c).
                                # Active after the dev placeholder's MNTS return.
    'ProcScr_PrepUnitScreen',   # proc script: the prep "Pick Units" screen (deploy/bench).
    'gPrepUnitList',            # struct PrepUnitList (include/prepscreen.h): units[0x40] then
                                # max_num at +0x100 -- PrepGetUnitAmount(). It is what
                                # ProcPrepUnit_Idle bounds its RIGHT/DOWN moves against, so
                                # the controller reads the LIVE roster length instead of
                                # assuming the deploy list's shape (#238).
    'ProcScr_UnitListScreen_Field', # proc script: the map-menu "Unit" list, i.e. the Character
                                # screen (src/unitlistscreen.c, started by StartUnitListScreenField
                                # off gMapMenuItems[0], overrideId 0x6E). A live instance == the
                                # unit list is actually on screen -> the #218 capture point.
    'gUnknown_0200F158',        # u8: how many units the Character screen actually sorted into
                                # its roster (src/unitlistscreen.c). This -- NOT the proc's own
                                # allyCount -- is what sub_809144C bounds DOWN against, and it
                                # is the only one of the two that a FIELD-mode list ever writes:
                                # StartUnitListScreenField sets `mode` and nothing else, so
                                # allyCount is left holding whatever was in the proc slot (#238).
    'sub_8091AEC',              # the Character screen's PROC_REPEAT input loop
                                # (src/unitlistscreen.c). Unnamed in the decomp, but it is the
                                # exact callback that makes the list an INPUT state rather than
                                # a screen that happens to be up -- and its unk_29 branch says
                                # whether the row/page scroll is still animating, i.e. whether
                                # a D-pad press would be read at all (#238).
    'unit_icon_wait_table',     # UnitIconWait[] (include/unit_icon_data.h): {pattern, size, sheet}
                                # per SMS id. `size` is the UNIT_ICON_SIZE_* PutUnitSprite switches
                                # on, so reading it in-engine proves what the ROM believes about a
                                # custom slot -- not what the injector meant to write (#218).
    'ProcScr_BmSupplyScreen',   # proc script: the in-map Supply (convoy) screen, opened by
                                # the unit-menu Supply command (src/prep_itemsupply.c). A live
                                # instance == a unit actually opened the convoy on the field.
    'PrepItemSupply_Loop_GiveTakeKeyHandler', # exact convoy input callback. B leaves it
                                # (Proc_Goto 8); nothing else is ever wanted there, but it has
                                # to be a NAMED state -- blind B's into an unclassified screen
                                # cannot tell "the convoy closed" from "that also cancelled
                                # the unit's move" (#238).
    'ProcScr_BattleEventEngine',# proc script: in-battle event engine (src/event.c). Runs
                                # CallBattleQuoteEventInBattle -> the brief in-combat quotes
                                # (per-PC DEATH quotes, boss taunts). A live instance == a
                                # quote box is on screen NOW -> hold + screenshot it.
    'ProcScr_StdEventEngine',   # proc script: the standard (map) event engine. A live
                                # instance == a map cutscene/talk event is running.
    'gProc_ekrBattle',          # proc script: the on-map battle (EKR) animation engine
                                # (src/banim-ekrbattle.c). A live instance == a combat is
                                # actually animating -> used to confirm an attack committed.
    'gBattleActor',             # struct BattleUnit (include/bmbattle.h): the attacking side of
                                # the combat being resolved/animated. unit at +0x00,
                                # terrainId +0x55, weapon +0x48. Names WHO is on screen when a
                                # battle animation freezes.
    'gBattleTarget',            # struct BattleUnit: the defending side of that same combat.
    'gBattleStats',             # struct BattleStats: +00 config, BATTLE_CONFIG_REAL on a real
                                # battle (the AI's own simulations write the same arrays).
    'gBattleHitArray',          # struct BattleHit[BATTLE_HIT_MAX]: each blow of the last battle,
                                # as the game rolled it (board.lua Board.battle, the bot's trace).
    'gActionData',              # struct ActionData (include/bmunit.h): the action being played.
                                # UnitBeginAction (bmunit.c) sets +0C subjectIndex and zeroes +11
                                # unitActionType at each act's start; the act then sets the type.
    'gActiveUnitMoveOrigin',    # struct Vec2: where that act's unit started (UnitBeginAction).
    'gBanimTerrain',            # u8[2] terrain ids the battle animation resolved for the two
                                # sides (POS_L/POS_R; src/banim-ekrbattleintro.c). These are what
                                # GetBanimTerrainGround/GetBanimBackgroundIndex are indexed with.
    'gBanimDoneFlag',           # u32[2] -- the EXACT soft-lock condition. ekrBattleInRoundIdle
                                # (src/banim-ekrbattle.c) spins until both sides' flags are set,
                                # so a battle anim that never signals done wedges the whole proc
                                # tree. Which of the two is 0 names the side that hung.
    'gEkrDistanceType',         # s16 -- CLOSE/FAR/FARFAR/PROMOTION (enum in include/ekrbattle.h);
                                # picks which round-type family the anim scripts must supply.
    'gAnims',                   # struct Anim *[4] (include/anime.h). [0]/[2] are the two combat
                                # anims; currentRoundType +0x12 and state/state2/state3 say which
                                # round each side thinks it is playing.
    'gpEkrBattleUnitLeft',      # struct BattleUnit * -- the LEFT screen side of the animation
    'gpEkrBattleUnitRight',     # struct BattleUnit * -- ...and the RIGHT. Which one maps to the
                                # actor depends on faction, so print both to read a freeze.
    # sight.lua (#510 step 9 PR D) runs these game functions in a saved-and-restored state and
    # reads what they write, so the bot sees what FE8 computes and nothing re-created.
    'gBmMapRange',              # u8** range map GenerateDangerZoneRange fills (bmidoten.c)
    'gRNSeeds',                 # u16[3], FILE-STATIC in rng.c (nm: local 'b'); InitRN seeds it
    'BattleGenerateSimulation',      # the forecast's simulation (bmbattle.c)
    'InitBattleForecastBattleStats', # the forecast window's hit counts (bksel.c)
    'GenerateDangerZoneRange',  # the player phase's danger zone (bmidoten.c, playerphase.c)
    'GenerateUnitMovementMap',  # a unit's reach into gBmMapMovement (bmidoten.c)
    'GetUnitMovementCost',      # a unit's terrain cost table, -1 = impassable (bmunit.c)
    'GetAvailableTileEventCommand',  # a tile's location event; Seize = 0x11 (eventinfo.c)
    'GetROMChapterStruct',      # chapter data: the goal window type +0x8C, its turn +0x8D
    'InitRN',                   # the game's own RNG seeding (rng.c)
    # An enemy's decision: the enemy phase's per-unit setup and its decision itself (cp_decide.c
    # CpDecide_Main's loop body, AiDecideMain).
    'RefreshEntityBmMaps',      # the unit, fog and hidden maps, rebuilt from the unit structs
    'AiDecideMain',             # the AI's whole decision for the active unit: scripts A and B
    'AiUpdateNoMoveFlag',       # sets AI_FLAG_STAY from the unit's ai_config
    'AiInitDangerMap',          # the AI's danger map, which its tile choice reads
    'AiClearDecision',          # empties gAiDecision before a decision
    'gAiState',                 # struct AiState: decideState +79, dangerMapFilled +7A, unk7C, +7D
    'BattleGenerateBallistaSimulation',
    'BattleRoll1RN',            # every one-number roll of a battle: crits, skill procs (bmbattle.c)
    'BattleRoll2RN',            # the two-number hit roll; both return simResult when simulating  # a ballista's strike (bmbattle.c)
    'gActiveUnit',              # struct Unit *: the AI decides for THIS unit
    # The chapter's talks (eventinfo.c): the walk's two talk checks, caught to read each entry,
    # and the Talk command's own availability check.
    'EvCheck03_CHAR',           # an EvtListTalk entry's check
    'EvCheck04_CHARASM',        # an EvtListConditionalTalk-with-asm entry's check
    'CheckForCharacterEvents',  # whether the talk (pidA, pidB) would run now
    # A fallen unit's drop (bmmind.c BATTLE_HandleItemDrop, its popup's only caller).
    'NewPopup_GeneralItemGot',  # the item given to the blue unit that downed a dropper
    'sProcScr_CombatAction',    # the real battle's resolution, the drop included
    # An AI theft (cp_perform.c AiStartStealAction) and the rank its list gives the item.
    'AiStartStealAction',       # the steal itself: gAiDecision's target and item slot
    'AiGetItemStealRank',       # the item's place in gAiStealPriorityItemList (ADR 0379)
    'EquipUnitItemSlot',        # Weapon Select equips the weapon struck with: what it counters with
    'gActiveUnitId',            # u8, its index; read beside gActiveUnit by the AI
    # Turn events still to come (eventinfo.c): botrun's "nothing can change this board".
    'GetChapterEventDataPointer',   # the chapter's event lists; turnBasedEvents at +00
    'SearchAvailableEvent',     # the turn-event check the phase change runs
    'SearchNextAvailableEvent', # and its continuation
    'GenerateExtendedMovementMap',  # the AI's march distance to a far goal (bmidoten.c)
    'CanUnitSeize',             # who may Seize: the Seize command's own check (bmdifficulty.c)
    'GetUnitEquippedWeapon',    # the weapon BU_ISLOT_AUTO strikes with: first usable (bmitem.c)
    # Bot.team's demands (#510 step 9 PR E): what each unit answers, by the game's own checks.
    'GetUnitKeyItemSlotForTerrain',  # a key or lockpick for a chest/door (Chest/DoorCommandUsability)
    'GetUnitFogViewRange',      # how far a unit sees in fog: a thief's +5, a torch (bmunit.c)
    'CanUnitUseStaff',          # whether a unit can use a staff it holds (bmitem.c)
    # The bot's heals (#510 step 9 PR E): what a staff or a Vulnerary would do, by the game.
    'CanUnitUseItem',           # usable now; for a staff it builds the targets (bmitemuse.c)
    'GetUnitItemHealAmount',    # the HP an item restores for this unit (bmitem.c)
    'GetUnitMaxHp',             # maxHP + the equipped weapon's HP bonus, AddUnitHp's cap (bmunit.c)
    'GetSelectTargetCount',     # the target list the last builder made (uiselecttarget.c)
    'GetTarget',                # one entry of it: struct SelectTarget { x, y, uid, extra }
    'CheckForCharacterEvents',  # whether a Talk event joins two characters (eventinfo.c)
    # Villages and chests (#510 step 9): the unit menu's own checks, on the active unit.
    'VisitCommandUsability',    # Visit: a village tile whose event is open, not a Phantom (bmmenu.c)
    'ChestCommandUsability',    # Chest: a key or lockpick and CanUnitUseChestKeyItem (bmmenu.c)
    # A kept act is played on the game's word (sight.legal): the rest of the unit menu's checks.
    'TalkCommandUsability',     # Talk: MakeTalkTargetList finds a partner, not Silenced (bmmenu.c)
    'DoorCommandUsability',     # Door: a key and a door beside the unit (bmmenu.c)
    'UnitActionMenu_CanSeize',  # Seize: CanUnitSeize on the Seize tile (bmmenu.c)
    'CanUnitUseWeaponNow',      # the weapons the Attack command lists (bmitem.c)
    'MakeTargetListForWeapon',  # that weapon's targets: units not allied, and walls (bmtarget.c)
    'AttackCommandUsability',   # Attack: a weapon above with a target (bmmenu.c; the clear loop)
    'InitObstacleBattleUnit',   # a wall as gBattleTarget, for its strike's forecast (bmbattle.c)
    'GetDefeatTalkEntry',       # a unit's death quote for this chapter; flag 2 = the Defeat Boss goal (eventinfo.c)
    # The planner's enemy phase (#510 step 9): the enemy turn order, as the game builds it.
    'BuildAiUnitList',          # gAiState.units: the faction's units able to act (cp_order.c)
    'SortAiUnitList',           # that list in the order the AI moves them (cp_order.c)
    'MakePrepUnitList',         # the Pick Units roster, rebuilt into its EWRAM overlay (prepscreen.c)
    # campaign.lua (#510 step 9 PR E): between chapters, the game's own shop, rules and world map.
    'StartShopScreen',          # opens the Armory/Vendor screen for a unit over a stock list
    'Shop_Loop_BuyKeyHandler',  # the shop's item list key handler (bmshop.c)
    'sShopState',               # struct ShopState: head_loc +00, hand_loc +06, px_per_line +08,
                                # bg2_off +0C (IsShopPageScrolling compares the last two)
    'GetItemPurchasePrice',     # what the shop charges this unit for an item (Silver Card included)
    'GetPartyGoldAmount',       # what the party may spend: 0 in Ch5x (bmgold.c)
    'CanUnitUseWeapon',         # whether a unit can wield an item (bmitem.c)
    'CanUnitUsePromotionItem',  # whether a seal promotes this unit now: class and level (bmitemuse.c)
    'ProcScr_WorldMapMain',     # the world map's main proc (worldmap_main.c)
    'WorldMap_Loop',            # its free-cursor loop: L, A and the D-pad
    'gGMData',                  # struct GMapData: cursor ix/iy +08/+0C (<<8), units[0].location
                                # +11 (the lord), nodes[] state +30 (bit 0 open, 4 bytes each)
    'gWMNodeData',              # struct GMapNodeData[] (stride 0x20): armory +0C, vendor +10,
                                # secretShop +14, x +18, y +1A
    'GetNextUnclearedNode',     # the node of the next story chapter (worldmap_path.c)
    'MakeNewItem',              # an item at full uses, as the shop makes its stock (bmitem.c)
    'IsCharacterForceDeployed', # the prep screen's forced-unit check (prep_unitselect.c)
]


def parse_nm(text):
    """nm output -> Symbols. Undefined entries carry no address and are dropped."""
    out = []
    for line in text.splitlines():
        parts = line.split()
        if len(parts) != 3:
            continue
        try:
            addr = int(parts[0], 16)
        except ValueError:
            continue
        out.append(Symbol(parts[2], parts[1], addr))
    return out


def wanted_symbols(symbols, wanted):
    """The named symbols, or KeyError naming every one the ELF does not have."""
    names = set(wanted)
    found = {s.name: s.addr for s in symbols if s.name in names}
    missing = [w for w in wanted if w not in found]
    if missing:
        raise KeyError('symbols not found in ELF: %s' % ', '.join(missing))
    return found



# A file-static array has no name in the ELF, so the harness can only find it through the
# linker map: the start of its object's ewram_data section, which must hold exactly what that
# file declares (`size`) or the symbol is not the only thing there. {name: (object, size)}.
STATIC_EWRAM = {
    # bmtrick.c: sTrapPool[TRAP_MAX_COUNT=64] then sTrapLast, 8 bytes each (#495, cracked walls)
    'sTrapPool': ('src/bmtrick.o', 65 * 8),
}


def static_ewram_symbols(map_text, wanted=STATIC_EWRAM):
    """{name: address} for each STATIC_EWRAM entry, read off the linker map."""
    out = {}
    for name, (obj, size) in wanted.items():
        match = re.search(r'^\s*ewram_data\s+0x([0-9a-f]+)\s+0x([0-9a-f]+)\s+%s$'
                          % re.escape(obj), map_text, re.M)
        if not match:
            raise KeyError('%s: no ewram_data section for %s in the linker map' % (name, obj))
        if int(match.group(2), 16) != size:
            raise KeyError('%s: %s ewram_data is 0x%x bytes, expected 0x%x -- the file now '
                           'declares something else beside it' % (name, obj,
                                                                    int(match.group(2), 16), size))
        out[name] = int(match.group(1), 16)
    return out


def _rom_code(symbols):
    return [s for s in symbols
            if s.type in ('T', 't') and ROM_START <= s.addr < ROM_END]


def _by_address(symbols):
    # Aliases put two names on one address. Prefer the shorter (then lexically first)
    # name so the table is deterministic across builds and reads as the canonical one.
    out = {}
    for s in symbols:
        prev = out.get(s.addr)
        if prev is None or (len(s.name), s.name) < (len(prev), prev):
            out[s.addr] = s.name
    return out


def proc_scripts(symbols):
    """Proc-script address -> exact symbol name."""
    return _by_address([s for s in _rom_code(symbols) if PROC_SCRIPT_RE.match(s.name)])


def code_symbols(symbols):
    """Every ROM code address -> exact symbol name (idle callbacks live here)."""
    return _by_address(_rom_code(symbols))


def _enum_values(relpath, prefix):
    """{ENUM: int} for one vanilla decomp header (HEAD, never the patched build tree)."""
    return enum_values(vanilla_decomp_text(relpath), prefix)


def village_sites(campaign, items):
    """{village id: {x, y, flag, gift?}} for every site whose Village macro carries an event id.

    The tile is the chapter YAML's, the flag the chapter injector's `CHNN_VILLAGE_FLAGS`, the
    gift `inject.villages.village_reward_item`'s. A chapter is in it when its injector
    defines that table, found by name over the host registry, so the next chapter to wire
    one needs no edit here. A raid case (`raided:`) and ch05.lua's reliquaries name a site
    and read the rest from this."""
    import importlib
    import inject.hosts as hosts
    from inject.decomp import flag_number
    from inject.hosting import _load_chapter_yaml
    from inject.villages import village_reward_item
    sites = {}
    for chapter in hosts.hosted_chapters():
        module = importlib.import_module('inject.chapters.' + chapter.name)
        prefix = chapter.name.upper()
        flags = getattr(module, prefix + '_VILLAGE_FLAGS', None)
        if flags is None:
            continue
        chap = _load_chapter_yaml(campaign, getattr(module, prefix + '_CHAPTER_YAML'))
        for v in chap['villages']:
            if v['id'] in sites:
                raise SystemExit('village id %r is declared by two chapters: CAMPAIGN.VILLAGES '
                                 'is keyed by id alone' % v['id'])
            flag = flag_number(flags[v['id']])
            if not isinstance(flag, int):
                raise SystemExit('village %r sets the named flag %r, not a numbered one -- '
                                 'eventFlag() reads a number' % (v['id'], flag))
            site = {'x': v['tile'][0], 'y': v['tile'][1], 'flag': flag}
            gift = village_reward_item(v)
            if gift:
                site['gift'] = items[gift]
            sites[v['id']] = site
    return sites


def campaign_ids(campaign=DEFAULT_CAMPAIGN):
    """The campaign facts scenarios read, resolved from the injector's own constants.

    Every value here used to be a hand-kept literal in harness.lua or a chapter chunk, each one
    a second copy of a Python constant -- and each one a top-level local spent from a chunk's
    shared 200-local budget. The cast's pid is its PORTRAIT_MAP slot, never its STAT_DONOR:
    the harness's own comments warned about that trap three times over."""
    from inject.cast import _classed_cast, classed_cast, load_unit, PORTRAIT_MAP, RAW_PID_HELP
    from inject.text import help_text_body, slot_desc_text_id
    from inject.chapter_ids import (CH01_BOSS_SLOT, CH02_CHWINGA, CH03_BOSS_PID, CH04_MOOSE_PID,
                                    CH05_BOSS_PID, CH05_MOOSE_PID, CH06_BOAT_PIDS,
                                    PROLOGUE_HLIN_SLOT,
                                    PROLOGUE_SCRAMSAX_SLOT, PROLOGUE_SEPHEK_SLOT)
    from inject.chapters.ch01 import CH01_CHAPTER_YAML
    from inject.chapters.ch02 import CH02_CHAPTER_YAML, CH02_CLASS_IDS
    from inject.chapters.ch04 import CH04_PACK_PIDS
    from inject.chapters.ch06 import CH06_CHAPTER_YAML
    from inject.decomp import ITEM_ENUM, LORDSEL_FLAG_BASE
    from inject.hosting import _load_chapter_yaml
    from inject.scenes import scene_gold_entries
    import inject.hosts as hosts

    chars = _enum_values('include/constants/characters.h', 'CHARACTER_')
    items = _enum_values('include/constants/items.h', 'ITEM_')
    classes = _enum_values('include/constants/classes.h', 'CLASS_')

    def char(slot):
        return chars['CHARACTER_' + slot.upper()]

    def help_row(msg, text):
        return {'msg': msg, 'line1': help_text_body(text).split('[')[0]}

    cast = {uid: char(slot) for uid, slot in PORTRAIT_MAP.items()}
    cast['rbg'] = cast['prof-rbg']                    # the #65 first mover's short name
    ch01 = _load_chapter_yaml(campaign, CH01_CHAPTER_YAML)
    lords, _ = _classed_cast(campaign, available_at=ch01['chapter_number'])
    # The chwinga ON THE FIELD, in green_allies order, and the charm each survivor pays.
    field = _load_chapter_yaml(campaign, CH02_CHAPTER_YAML)['deployment']['green_allies']
    slot_of = dict(CH02_CHWINGA)
    # ch06's dropper, whose drop flips once he swings his second weapon (#495, ch06halberd).
    dropper = {e['id']: e for e in _load_chapter_yaml(campaign, CH06_CHAPTER_YAML)['enemy_units']}
    dropper = dropper['shark-rider-horseslayer']     # the id ch06.lua's DROPPER row names
    return {
        'CAST': cast,
        # The help text R on a unit's name must read, by pid: the message and its first line
        # (the words tell ours from vanilla's where the id is vanilla's own). A classed cast
        # member's is its slot's descTextId, which the names pass writes (ADR 0346); a raw
        # pid's is RAW_PID_HELP's (a chapter's generics, #493). `casthelp` and the declared
        # `help:` step both read it.
        'HELP': {**{char(slot): help_row(slot_desc_text_id(slot),
                                         load_unit(campaign, uid)['help_text'])
                    for uid, slot, _c, _ in classed_cast(campaign)},
                 **{int(pid, 16): help_row(msg, text) for pid, (msg, text) in RAW_PID_HELP.items()}},
        'LORD_CANDIDATES': len(lords),
        'LORDSEL_FLAG_BASE': LORDSEL_FLAG_BASE,
        'PROLOGUE': {'hlin': char(PROLOGUE_HLIN_SLOT), 'scramsax': char(PROLOGUE_SCRAMSAX_SLOT),
                     'sephek': char(PROLOGUE_SEPHEK_SLOT)},
        'CH01_CHIEF': char(CH01_BOSS_SLOT),
        # What ch01's scenes pay (#495): ch01gold reads it back on ch02's map.
        'CH01_SCENE_GOLD': sum(amount for _s, _a, amount in scene_gold_entries(ch01)),
        # Every hosted chapter, read off the registry: a range here went stale the day ch07 was
        # hosted and a film needed its slot.
        'HOST': {c.name: c.host_index for c in hosts.hosted_chapters() if c.name != 'prologue'},
        'CH02_CHWINGA_PIDS': [char(slot_of[g['id']]) for g in field],
        'CH02_CHARMS': [items[ITEM_ENUM[g['gift']]] for g in field],
        'CH02_ARCHER_CLASS': classes[CH02_CLASS_IDS['archer']],
        'CH04_PACK_PIDS': {int(p, 0): True for p in CH04_PACK_PIDS},   # a SET: indexed by charId
        'CH03_BOSS_PID': int(CH03_BOSS_PID, 0),
        'CH04_MOOSE_PID': int(CH04_MOOSE_PID, 0),
        'CH05_BOSS_PID': int(CH05_BOSS_PID, 0),
        'CH05_MOOSE_PID': int(CH05_MOOSE_PID, 0),
        'CH06_BOAT_PIDS': {k: int(v, 0) for k, v in CH06_BOAT_PIDS.items()},
        'CH06_DROPPER_ITEMS': [items[ITEM_ENUM[i['id']]] for i in dropper['inventory']],
        'CH06_DROPPER_DROP': items[ITEM_ENUM[dropper['item_drop']]],
        'VILLAGES': village_sites(campaign, items),
    }


def lua_literal(value, indent=1):
    """A Python dict/list/int/str/True as a Lua table constructor (keys sorted: a stable file)."""
    pad = '    ' * indent
    if value is True:
        return 'true'
    if isinstance(value, str):
        return '"%s"' % value.replace('\\', '\\\\').replace('"', '\\"')
    if isinstance(value, bool) or not isinstance(value, (dict, list, int)):
        raise TypeError('no Lua literal for %r' % (value,))
    if isinstance(value, int):
        return '0x%02X' % value
    if isinstance(value, list):
        return '{ ' + ', '.join(lua_literal(v, indent + 1) for v in value) + ' }'
    rows = ['%s[%s] = %s,' % (pad, '"%s"' % k if isinstance(k, str) else lua_literal(k),
                              lua_literal(value[k], indent + 1))
            for k in sorted(value)]
    return '{\n' + '\n'.join(rows) + '\n' + '    ' * (indent - 1) + '}'


def render_lua(varname, mapping):
    lines = ['-- generated by gen_symbols.py from fireemblem8.elf; do not edit',
             '%s = {' % varname]
    for addr in sorted(mapping):
        lines.append('    [0x%08X] = "%s",' % (addr, mapping[addr]))
    lines.append('}')
    return '\n'.join(lines) + '\n'


def write_atomic(path, text):
    """Write `text` to `path` through a temp file in the same directory, then rename.

    Every `run.sh` regenerates these three tables, and since #310 four scenarios start at
    once -- so a sibling can be reading `symbols.lua` while this process rewrites it. A
    rename is atomic on the same filesystem: a reader sees either the old table or the new
    one, never half of either, and a writer that dies leaves the last good file in place.
    """
    tmp = '%s.%d.tmp' % (path, os.getpid())
    try:
        with open(tmp, 'wb') as fh:
            fh.write(text.encode('utf-8'))
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            os.remove(tmp)


def main():
    if not os.path.exists(ELF):
        sys.exit('ERROR: %s not built (run make first)' % ELF)
    os.makedirs(OUT_DIR, exist_ok=True)
    nm = subprocess.run(['arm-none-eabi-nm', ELF], capture_output=True, text=True, check=True)
    symbols = parse_nm(nm.stdout)
    try:
        addrs = wanted_symbols(symbols, WANTED)
        link_map = os.path.splitext(ELF)[0] + '.map'
        if os.path.exists(link_map):        # a PT_ELF build may ship no map; SYM then lacks them
            with open(link_map, encoding='utf-8') as fh:
                addrs.update(static_ewram_symbols(fh.read()))
        facts = campaign_ids()
    except KeyError as missing:
        sys.exit('ERROR: %s' % missing.args[0])
    write_atomic(OUT, ''.join(
        ['-- generated by gen_symbols.py from fireemblem8.elf; do not edit\n', 'SYM = {\n']
        + ['    %s = 0x%08X,\n' % (name, addrs[name])
           for name in WANTED + list(STATIC_EWRAM) if name in addrs]
        + ['}\n', 'CAMPAIGN = %s\n' % lua_literal(facts)]))
    print('wrote %s (%d symbols)' % (OUT, len(addrs)))

    scripts = proc_scripts(symbols)
    write_atomic(OUT_PROCSCR, render_lua('PROCSCR', scripts))
    print('wrote %s (%d proc scripts)' % (OUT_PROCSCR, len(scripts)))

    code = code_symbols(symbols)
    write_atomic(OUT_JSON, json.dumps(
        {'code': {'0x%08X' % a: n for a, n in code.items()}}, indent=0, sort_keys=True))
    print('wrote %s (%d code symbols)' % (OUT_JSON, len(code)))


if __name__ == '__main__':
    main()
