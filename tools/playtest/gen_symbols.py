#!/usr/bin/env python3
"""Emit the harness symbol tables from the built ELF.

Run after every `make` (run.sh does this) -- BSS/EWRAM addresses shift when
engine code changes, so the Lua harness must never hard-code them.

Three outputs, one nm pass:

  symbols.lua   the named symbols the harness reads/scans (SYM)
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
ELF = os.path.join(REPO, 'fireemblem8u', 'fireemblem8.elf')
HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, 'symbols.lua')
OUT_PROCSCR = os.path.join(HERE, 'procscr.lua')
OUT_JSON = os.path.join(HERE, 'symbols.json')

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
    'gProcScr_BKSEL',           # passive battle-forecast panel owner; SelectTargetProc, not
                                # this display proc, owns the target-confirmation input
    'BattleForecast_LoopDisplay', # exact stable forecast display callback (still no legal input)
    'gProcScr_ChapterStatusScreen',  # proc script: map-menu Status screen, which
                                # draws the chapter title card (src/uichapterstatus.c)
    'gProcScr_SALLYCURSOR',     # proc script: the preparations screen
                                # (src/prep_sallycursor.c; opened by event cmd 0x3E)
    'gProcScr_StatScreen',      # proc script: a unit's status screen (src/statscreen.c), the
                                # only place FE8 draws a unit's 96x80 BUST beside its name,
                                # class and stat line. `recordcast` gates its capture on this
                                # rather than a frame count -- a blind R press that landed on
                                # nothing would still shoot, handing back a picture of the map
                                # captioned "portrait".
    'gProcScr_TitleScreen',     # proc script: the title screen (src/titlescreen.c).
                                # Active after the dev placeholder's MNTS return.
    'gProcScr_OpSubtitle',      # proc script: the opening subtitle crawl (src/opsubtitle.c).
                                # In a --montage build this carries the #43 lore crawl, so a
                                # live instance == the montage opener actually played.
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
    found = {s.name: s.addr for s in symbols if s.name in set(wanted)}
    missing = [w for w in wanted if w not in found]
    if missing:
        raise KeyError('symbols not found in ELF: %s' % ', '.join(missing))
    return found


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


def render_lua(varname, mapping):
    lines = ['-- generated by gen_symbols.py from fireemblem8.elf; do not edit',
             '%s = {' % varname]
    for addr in sorted(mapping):
        lines.append('    [0x%08X] = "%s",' % (addr, mapping[addr]))
    lines.append('}')
    return '\n'.join(lines) + '\n'


def main():
    if not os.path.exists(ELF):
        sys.exit('ERROR: %s not built (run make first)' % ELF)
    nm = subprocess.run(['arm-none-eabi-nm', ELF], capture_output=True, text=True, check=True)
    symbols = parse_nm(nm.stdout)
    try:
        addrs = wanted_symbols(symbols, WANTED)
    except KeyError as missing:
        sys.exit('ERROR: %s' % missing.args[0])
    with open(OUT, 'w', encoding='utf-8') as f:
        f.write('-- generated by gen_symbols.py from fireemblem8.elf; do not edit\n')
        f.write('SYM = {\n')
        for name in WANTED:
            f.write('    %s = 0x%08X,\n' % (name, addrs[name]))
        f.write('}\n')
    print('wrote %s (%d symbols)' % (OUT, len(addrs)))

    scripts = proc_scripts(symbols)
    with open(OUT_PROCSCR, 'w', encoding='utf-8') as f:
        f.write(render_lua('PROCSCR', scripts))
    print('wrote %s (%d proc scripts)' % (OUT_PROCSCR, len(scripts)))

    code = code_symbols(symbols)
    with open(OUT_JSON, 'w', encoding='utf-8') as f:
        json.dump({'code': {'0x%08X' % a: n for a, n in code.items()}}, f,
                  indent=0, sort_keys=True)
    print('wrote %s (%d code symbols)' % (OUT_JSON, len(code)))


if __name__ == '__main__':
    main()
