"""Campaign-agnostic engine hooks: build-time string-replaces into the decomp C
source. Pipeline-owned (the content track never opens this file). Each hook is a
pure patch with its own `if orig not in text` guard; presence is also asserted by
tools/check.py check_engine_guards_present. See docs/decisions.md.
"""

import os
import sys

from inject.decomp import (
    DECOMP, _replace_brace_block,
    BATTLEQUOTES_C, BMUNIT_C, LORDSEL_FLAG_BASE)

# Decomp source files patched ONLY by the engine hooks below.
BMCAMADJUST_C = os.path.join(DECOMP, 'src', 'bmcamadjust.c')
BMMAP_C = os.path.join(DECOMP, 'src', 'bmmap.c')
WORLDMAP_PATH_C = os.path.join(DECOMP, 'src', 'worldmap_path.c')
BMDIFFICULTY_C = os.path.join(DECOMP, 'src', 'bmdifficulty.c')
BMMENU_C = os.path.join(DECOMP, 'src', 'bmmenu.c')
DATA_EVENT_TRIGGER_C = os.path.join(DECOMP, 'src', 'data_event_trigger.c')
EVENTINFO_C = os.path.join(DECOMP, 'src', 'eventinfo.c')
PREP_SALLYCURSOR_C = os.path.join(DECOMP, 'src', 'prep_sallycursor.c')
PREP_UNITSELECT_C = os.path.join(DECOMP, 'src', 'prep_unitselect.c')
LORDFLOOR_APPLIED_FLAG = 0xFA


def _patch_player_start_cursor_guard():
    """Guard GetPlayerStartCursorPosition against a non-deployed player leader.

    At chapter start ProcFun_ResetCursorPosition centers the cursor on the player leader:
    GetUnitFromCharId(GetPlayerLeaderPid()). FE8 assumes the leader (a LORD-class unit) is
    always deployed -- but our campaign's lords ride ordinary slots, so that lookup returns
    NULL and the original code dereferences it (`unit->xPos`), reading BIOS garbage and
    parking the cursor OFF-MAP. The off-map cursor then drives out-of-bounds map/terrain
    reads -> a runaway text decode -> gBmSt corruption (garbage band) -> crash. Watchpoint-
    confirmed root cause. Fix: if the leader isn't deployed, fall back to the first valid
    player unit, and never dereference NULL. Campaign-agnostic engine hardening.
    """
    with open(BMCAMADJUST_C, encoding='utf-8') as f:
        text = f.read()
    orig = (
        'void GetPlayerStartCursorPosition(int *px, int *py)\n'
        '{\n'
        '    struct Unit *unit;\n'
        '    if (1 == gPlaySt.chapterTurnNumber) {\n'
        '        unit = GetUnitFromCharId(GetPlayerLeaderPid());\n'
        '        gPlaySt.xCursor = unit->xPos;\n'
        '        gPlaySt.yCursor = unit->yPos;\n'
        '    }\n'
        '\n'
        '    if (1 != gPlaySt.config.autoCursor) {\n'
        '        unit = GetUnitFromCharId(GetPlayerLeaderPid());\n'
        '        *px = unit->xPos;\n'
        '        *py = unit->yPos;\n'
        '    } else {\n'
        '        *px = gPlaySt.xCursor;\n'
        '        *py = gPlaySt.yCursor;\n'
        '    }\n'
        '}')
    fixed = (
        'void GetPlayerStartCursorPosition(int *px, int *py)\n'
        '{\n'
        '    struct Unit *unit;\n'
        '    int i;\n'
        '\n'
        '    /* Leader may ride a non-LORD slot (campaign): if not deployed, fall back to\n'
        '     * the first valid player unit so the cursor never lands off-map. */\n'
        '    unit = GetUnitFromCharId(GetPlayerLeaderPid());\n'
        '    if (unit == NULL) {\n'
        '        for (i = 1; i < 0x40; ++i) {\n'
        '            struct Unit *u = GetUnit(i);\n'
        '            if (UNIT_IS_VALID(u)) {\n'
        '                unit = u;\n'
        '                break;\n'
        '            }\n'
        '        }\n'
        '    }\n'
        '    if (unit == NULL)\n'
        '        return;\n'
        '\n'
        '    if (1 == gPlaySt.chapterTurnNumber) {\n'
        '        gPlaySt.xCursor = unit->xPos;\n'
        '        gPlaySt.yCursor = unit->yPos;\n'
        '    }\n'
        '\n'
        '    if (1 != gPlaySt.config.autoCursor) {\n'
        '        *px = unit->xPos;\n'
        '        *py = unit->yPos;\n'
        '    } else {\n'
        '        *px = gPlaySt.xCursor;\n'
        '        *py = gPlaySt.yCursor;\n'
        '    }\n'
        '}')
    if orig not in text:
        sys.exit('ERROR: GetPlayerStartCursorPosition not in expected form in %s' % BMCAMADJUST_C)
    with open(BMCAMADJUST_C, 'w', encoding='utf-8') as f:
        f.write(text.replace(orig, fixed, 1))


def _patch_terrain_name_guard():
    """Bounds-guard GetTerrainName against out-of-range terrain ids.

    gUnknown_0880D374 (the terrain -> name-message-id table) has only 65 entries.
    An out-of-range id -- e.g. the terrain-display window reading gBmMapTerrain at an
    OFF-MAP cursor position (which happens at chapter start when the lord rides a
    non-LORD-class slot, so the auto-cursor never centers it) -- indexes past the table,
    yielding a garbage gMsgTable[] pointer. The text decompressor then runs away and
    overruns gBmSt (camera/cursor), corrupting the screen and soft-locking. Vanilla never
    hit this because its lords are LORD-class; our campaign's aren't. Campaign-agnostic
    engine hardening: an invalid terrain id renders as terrain 0 instead of crashing.
    """
    with open(BMMAP_C, encoding='utf-8') as f:
        text = f.read()
    orig = ('char* GetTerrainName(int terrainId) {\n'
            '    return GetStringFromIndex(gUnknown_0880D374[terrainId]);\n'
            '}')
    guarded = ('char* GetTerrainName(int terrainId) {\n'
               '    /* Guard OOB ids (e.g. off-map cursor); table has 65 entries. */\n'
               '    if ((unsigned int)terrainId >= 65)\n'
               '        terrainId = 0;\n'
               '    return GetStringFromIndex(gUnknown_0880D374[terrainId]);\n'
               '}')
    if orig not in text:
        sys.exit('ERROR: GetTerrainName not in expected vanilla form in %s' % BMMAP_C)
    with open(BMMAP_C, 'w', encoding='utf-8') as f:
        f.write(text.replace(orig, guarded, 1))


def _patch_battle_map_kind_fallback():
    """A chapter load that resolves no world-map node is a STORY chapter, not a
    skirmish.

    GetBattleMapKind (worldmap_path.c) classifies most chapter slots by scanning
    gGMData's world-map node states and falls back to BATTLEMAP_KIND_SKIRMISH when
    no node matches. Vanilla can rely on that: story chapters on node slots are
    always entered THROUGH the world map, so a node always matches. Our campaign
    has no world map (boot and MNC2 go straight to the battle map), so gGMData is
    never populated and every node-slot chapter (slot 2+) misclassified as a
    SKIRMISH -- which swaps in EventScr_SkirmishCommonBeginning instead of the
    chapter's own beginning scene (bm.c CallBeginningEvents), hides the ally
    unit-definition table, and disables force-deployment. Campaign-agnostic
    hardening: the no-node fallback becomes STORY. (Skirmishes are unreachable
    without a world map, so the old fallback had no remaining legitimate hit.)
    """
    with open(WORLDMAP_PATH_C, encoding='utf-8') as f:
        text = f.read()
    orig = '    return BATTLEMAP_KIND_SKIRMISH;'
    if text.count(orig) != 1:
        sys.exit('ERROR: GetBattleMapKind fallback not in expected vanilla form in %s'
                 % WORLDMAP_PATH_C)
    patched = ('    /* No world map in this hack: a load that resolves no node is a\n'
               '       story chapter (vanilla only reached this via WM skirmishes). */\n'
               '    return BATTLEMAP_KIND_STORY;')
    with open(WORLDMAP_PATH_C, 'w', encoding='utf-8') as f:
        f.write(text.replace(orig, patched, 1))


def _inject_lord_select_engine():
    """Lord select (#42), engine side: make the player-chosen lead real.

    The ch01 menu (inject_ch01) records the pick as permanent flag
    LORDSEL_FLAG_BASE + menu index. Six campaign-agnostic hooks consume it:
      1. LordSelect_GetPid (new, eventinfo.c): scan the flags over the
         build-generated gLordSelectCandidates pid table (events_udefs.c);
         fallback = first candidate while nothing is set, so a debug entry
         straight into a chapter never soft-locks (issue #42's requirement).
      2. IsCharacterForceDeployed_ (eventinfo.c): the chosen lead is always
         fielded by the prep flow.
      3. CanUnitSeize (bmdifficulty.c): Seize belongs to the chosen lead
         (vanilla hardcoded Eirika/Ephraim by route/chapter).
      4. UnitKill (bmunit.c): the chosen lead's death raises EVFLAG_GAMEOVER --
         caught by each chapter's CauseGameOverIfLordDies AFEV -- whatever the
         death path. The vanilla route-wide Eirika/Ephraim defeat entries
         (chapter 0xFF + EVFLAG_GAMEOVER, data_battlequotes.c) are demoted to
         plain quotes: the cast members riding those slots must be able to die
         like anyone else when they are not the chosen lead.
      5. SupplyUsability (bmmenu.c): convoy/supply access belongs to the chosen
         lead (vanilla hardcoded Eirika/Ephraim by route) -- otherwise a cast
         member on the Eirika slot inherits free convoy access.
      6. gForceDeploymentList (data_event_trigger.c): cleared. Vanilla's static
         by-slot force-deploy table would force-field cast riding those slots
         (e.g. whoever rides CHARACTER_EIRIKA in COMMON mode, every chapter) on top of hook 2's
         chosen lead. Hook 2 is now the ONLY force-deploy.
    """
    # 1 + 2: eventinfo.c -- GetPid above the force-deploy lookup, hook inside it.
    with open(EVENTINFO_C, encoding='utf-8') as f:
        text = f.read()
    orig = ('//! FE8U = 0x08084800\n'
            'bool IsCharacterForceDeployed_(u16 pid)\n'
            '{\n'
            '    struct ForceDeploymentEnt * it;\n'
            '\n'
            '    for (it = gForceDeploymentList; it->pid != (u16)-1; it++)\n')
    if text.count(orig) != 1:
        sys.exit('ERROR: IsCharacterForceDeployed_ not in expected vanilla form in %s'
                 % EVENTINFO_C)
    hooked = (
        '/* Lord select (campaign engine, #42): resolve the player-chosen lead.\n'
        '   gLordSelectCandidates (events_udefs.c, build-generated) lists the cast\n'
        '   pids in menu order; the ch01 menu records the pick as permanent flag\n'
        '   0x%X + index (saved with the file; zeroed on New Game by\n'
        '   ResetPermanentFlags). Fallback while nothing is set (debug entry\n'
        '   before the menu has run): the first candidate. */\n'
        'u16 LordSelect_GetPid(void)\n'
        '{\n'
        '    extern const u16 gLordSelectCandidates[];\n'
        '    int i;\n'
        '\n'
        '    for (i = 0; gLordSelectCandidates[i] != 0xFFFF; i++) {\n'
        '        if (CheckFlag(0x%X + i)) {\n'
        '            return gLordSelectCandidates[i];\n'
        '        }\n'
        '    }\n'
        '\n'
        '    return gLordSelectCandidates[0];\n'
        '}\n'
        '\n'
        '//! FE8U = 0x08084800\n'
        'bool IsCharacterForceDeployed_(u16 pid)\n'
        '{\n'
        '    struct ForceDeploymentEnt * it;\n'
        '\n'
        '    /* Lord select (campaign engine, #42): the chosen lead is always\n'
        '       fielded. */\n'
        '    if (pid == LordSelect_GetPid())\n'
        '        return true;\n'
        '\n'
        '    for (it = gForceDeploymentList; it->pid != (u16)-1; it++)\n'
        % (LORDSEL_FLAG_BASE, LORDSEL_FLAG_BASE))
    with open(EVENTINFO_C, 'w', encoding='utf-8') as f:
        f.write(text.replace(orig, hooked, 1))

    # 3: bmdifficulty.c -- Seize gate.
    with open(BMDIFFICULTY_C, encoding='utf-8') as f:
        text = f.read()
    orig = ('s8 CanUnitSeize(struct Unit* unit) {\n'
            '    int leaderId;\n'
            '\n'
            '    switch (gPlaySt.chapterModeIndex) {\n'
            '        case 2: // Eirika\n'
            '            leaderId = CHARACTER_EIRIKA;\n'
            '            break;\n'
            '        case 1: // tutorial (chapter 0-8)\n'
            '            leaderId = CHARACTER_EIRIKA;\n'
            '            break;\n'
            '        case 3: // Ephraim\n'
            '            leaderId = CHARACTER_EPHRAIM;\n'
            '            break;\n'
            '    }\n'
            '\n'
            '    if (gPlaySt.chapterIndex == 5) {\n'
            '        leaderId = CHARACTER_EPHRAIM;\n'
            '    }\n'
            '\n'
            '    return unit->pCharacterData->number == leaderId;\n'
            '}')
    if text.count(orig) != 1:
        sys.exit('ERROR: CanUnitSeize not in expected vanilla form in %s'
                 % BMDIFFICULTY_C)
    patched = ('s8 CanUnitSeize(struct Unit* unit) {\n'
               '    /* Lord select (campaign engine, #42): Seize belongs to the\n'
               '       player-chosen lead (vanilla hardcoded Eirika/Ephraim by\n'
               '       route/chapter). */\n'
               '    extern u16 LordSelect_GetPid(void);\n'
               '\n'
               '    return unit->pCharacterData->number == LordSelect_GetPid();\n'
               '}')
    with open(BMDIFFICULTY_C, 'w', encoding='utf-8') as f:
        f.write(text.replace(orig, patched, 1))

    # 4a: bmunit.c -- death hook.
    with open(BMUNIT_C, encoding='utf-8') as f:
        text = f.read()
    orig = ('        else {\n'
            '            unit->state |= US_DEAD | US_HIDDEN;\n'
            '            InitUnitsupports(unit);\n'
            '        }\n')
    if text.count(orig) != 1:
        sys.exit('ERROR: UnitKill blue-death branch not in expected vanilla form in %s'
                 % BMUNIT_C)
    hooked = ('        else {\n'
              '            /* Lord select (campaign engine, #42): the chosen lead\'s\n'
              '               fall ends the run whatever killed them -- raise the\n'
              '               game-over flag the chapter Misc AFEV\n'
              '               (CauseGameOverIfLordDies) fires on. */\n'
              '            extern u16 LordSelect_GetPid(void);\n'
              '            extern void SetFlag(int flag);\n'
              '\n'
              '            if (UNIT_CHAR_ID(unit) == LordSelect_GetPid())\n'
              '                SetFlag(0x65); /* EVFLAG_GAMEOVER */\n'
              '\n'
              '            unit->state |= US_DEAD | US_HIDDEN;\n'
              '            InitUnitsupports(unit);\n'
              '        }\n')
    with open(BMUNIT_C, 'w', encoding='utf-8') as f:
        f.write(text.replace(orig, hooked, 1))

    # 4b: data_battlequotes.c -- demote the route-wide lord game-over entries.
    with open(BATTLEQUOTES_C, encoding='utf-8') as f:
        text = f.read()
    for msg in ('0x0C23', '0x0C24'):  # vanilla Eirika / Ephraim farewell quotes
        orig = ('        .flag    = EVFLAG_GAMEOVER,\n'
                '        .msg     = %s,\n' % msg)
        if text.count(orig) != 1:
            sys.exit('ERROR: route-wide lord defeat entry (%s) not in expected '
                     'vanilla form in %s' % (msg, BATTLEQUOTES_C))
        text = text.replace(orig, (
            '        .flag    = 0x0000, /* lord select (#42): game over is keyed\n'
            '                              to the chosen lead (UnitKill hook), not\n'
            '                              this slot; quote stays */\n'
            '        .msg     = %s,\n' % msg), 1)
    with open(BATTLEQUOTES_C, 'w', encoding='utf-8') as f:
        f.write(text)

    # 5: bmmenu.c -- convoy/supply gate. SupplyUsability hardcodes the route lord
    #    (Eirika/Ephraim) as the unit that can open the supply anywhere; a cast member
    #    riding that slot (e.g. CHARACTER_EIRIKA) inherits free convoy access.
    #    Route it through the chosen lead instead (mirrors the Seize gate).
    with open(BMMENU_C, encoding='utf-8') as f:
        text = f.read()
    orig = ('    switch (gPlaySt.chapterModeIndex)\n'
            '    {\n'
            '        case CHAPTER_MODE_EIRIKA:\n'
            '            pid = CHARACTER_EIRIKA;\n'
            '            break;\n'
            '\n'
            '        case CHAPTER_MODE_EPHRAIM:\n'
            '            pid = CHARACTER_EPHRAIM;\n'
            '            break;\n'
            '\n'
            '        default:\n'
            '            pid = CHARACTER_EIRIKA;\n'
            '            break;\n'
            '    }\n')
    if text.count(orig) != 1:
        sys.exit('ERROR: SupplyUsability lord switch not in expected vanilla form in %s'
                 % BMMENU_C)
    patched = ('    /* Lord select (campaign engine, #42): convoy access belongs to the\n'
               '       player-chosen lead (vanilla hardcoded Eirika/Ephraim by route). The\n'
               '       cast ride ordinary slots, so a unit on the Eirika slot must NOT get\n'
               '       free supply unless they ARE the chosen lord. */\n'
               '    {\n'
               '        extern u16 LordSelect_GetPid(void);\n'
               '        pid = LordSelect_GetPid();\n'
               '    }\n')
    with open(BMMENU_C, 'w', encoding='utf-8') as f:
        f.write(text.replace(orig, patched, 1))

    # 6: data_event_trigger.c -- the vanilla static force-deploy table. It hard-fields
    #    Eirika/Ephraim (and later-route units) BY SLOT; our cast ride those slots, so
    #    e.g. CHARACTER_EIRIKA in COMMON mode force-fields whoever rides it every chapter, on top
    #    of the player's chosen lead. Clear it: the ONLY forced unit is the chosen lead
    #    (the IsCharacterForceDeployed_ hook, #2 above). Any future per-chapter forced
    #    unit is added our way, not via this vanilla table.
    with open(DATA_EVENT_TRIGGER_C, encoding='utf-8') as f:
        text = f.read()
    cleared = ('{\n'
               '    /* Lord select (campaign engine, #42): cleared -- the chosen lead is\n'
               '       force-fielded by IsCharacterForceDeployed_; vanilla\'s by-slot\n'
               '       entries would wrongly force cast members riding those slots. */\n'
               '    {-1, 0, 0},\n'
               '}')
    text = _replace_brace_block(text, 'gForceDeploymentList[] =', cleared,
                                DATA_EVENT_TRIGGER_C)
    with open(DATA_EVENT_TRIGGER_C, 'w', encoding='utf-8') as f:
        f.write(text)


def _inject_lord_select_prep_mode():
    """Lord select (#46), UI: run the REAL prep "Pick Units" screen as a one-shot
    "choose your lead" picker, reusing its polished list + live portrait + panel
    instead of a hand-built menu (Nicolas 2026-06-25).

    StartLordSelectPrep(parent) flips a resident mode flag and Proc_StartBlocking's the
    vanilla ProcScr_PrepUnitScreen. The cast must already be loaded -- the prep list
    builds purely from loaded units (MakePrepUnitList -> GetUnit + IsUnitInCurrentRoster),
    so no prep-menu (ProcAtMenu) context is needed; the mode flag guards the few spots
    that would otherwise reach into that parent. A on a candidate records the pick as the
    permanent lord flag (LORDSEL_FLAG_BASE + index over gLordSelectCandidates, the same
    flag LordSelect_GetPid reads) and exits the screen. Campaign-agnostic: candidate pids
    come from the build-generated gLordSelectCandidates table.
    """
    # 1. Resident mode flag in bmunit.c (its ewram_data section is linked; the prep TU's
    #    is not). Sits beside gActiveUnitId.
    with open(BMUNIT_C, encoding='utf-8') as f:
        text = f.read()
    orig = 'EWRAM_DATA u8 gActiveUnitId = 0;\n'
    if text.count(orig) != 1:
        sys.exit('ERROR: gActiveUnitId anchor not found in %s' % BMUNIT_C)
    text = text.replace(
        orig,
        orig + '/* Lord select (#46): 1 while the prep screen runs as the lord picker. */\n'
        'EWRAM_DATA u8 gLordSelectPrepMode = 0;\n', 1)
    with open(BMUNIT_C, 'w', encoding='utf-8') as f:
        f.write(text)

    with open(PREP_UNITSELECT_C, encoding='utf-8') as f:
        text = f.read()

    # 2. OnInit: in lord mode skip the ProcAtMenu parent reads (there is no such parent).
    orig = ('    proc->max_counter = ((struct ProcAtMenu *)(proc->proc_parent))->max_counter;\n'
            '    proc->cur_counter = ((struct ProcAtMenu *)(proc->proc_parent))->cur_counter;\n'
            '    proc->yDiff_cur = ((struct ProcAtMenu *)(proc->proc_parent))->yDiff;\n')
    if text.count(orig) != 1:
        sys.exit('ERROR: ProcPrepUnit_OnInit parent reads not in expected form in %s'
                 % PREP_UNITSELECT_C)
    text = text.replace(orig,
        '    if (gLordSelectPrepMode) {\n'
        '        proc->max_counter = 99; /* lord pick: no deploy cap */\n'
        '        proc->cur_counter = 0;\n'
        '        proc->yDiff_cur = 0;\n'
        '    } else {\n'
        '        proc->max_counter = ((struct ProcAtMenu *)(proc->proc_parent))->max_counter;\n'
        '        proc->cur_counter = ((struct ProcAtMenu *)(proc->proc_parent))->cur_counter;\n'
        '        proc->yDiff_cur = ((struct ProcAtMenu *)(proc->proc_parent))->yDiff;\n'
        '    }\n', 1)

    # 3. OnEnd: in lord mode skip the parent writeback + clear the mode flag.
    orig = ('void ProcPrepUnit_OnEnd(struct ProcPrepUnit *proc)\n'
            '{\n'
            '    ((struct ProcAtMenu *)(proc->proc_parent))->yDiff = proc->yDiff_cur;\n')
    if text.count(orig) != 1:
        sys.exit('ERROR: ProcPrepUnit_OnEnd not in expected form in %s' % PREP_UNITSELECT_C)
    text = text.replace(orig,
        'void ProcPrepUnit_OnEnd(struct ProcPrepUnit *proc)\n'
        '{\n'
        '    if (gLordSelectPrepMode) {\n'
        '        gLordSelectPrepMode = 0;\n'
        '        EndMuralBackground_();\n'
        '        return;\n'
        '    }\n'
        '    ((struct ProcAtMenu *)(proc->proc_parent))->yDiff = proc->yDiff_cur;\n', 1)

    # 4. HandlePressA: in lord mode A anoints the lead (sets the lord flag) and exits.
    orig = ('s8 PrepUnit_HandlePressA(struct ProcPrepUnit *proc)\n'
            '{\n'
            '    struct Unit *unit = GetUnitFromPrepList(proc->list_num_cur);\n')
    if text.count(orig) != 1:
        sys.exit('ERROR: PrepUnit_HandlePressA head not in expected form in %s'
                 % PREP_UNITSELECT_C)
    text = text.replace(orig,
        orig +
        '\n'
        '    if (gLordSelectPrepMode) {\n'
        '        /* Lord select (#46): record the pick as permanent flag\n'
        '           LORDSEL_FLAG_BASE + index over gLordSelectCandidates (events_udefs.c),\n'
        '           read back by LordSelect_GetPid. Clear any prior pick first. */\n'
        '        extern const u16 gLordSelectCandidates[];\n'
        '        extern void SetFlag(int flag);\n'
        '        extern void ClearFlag(int flag);\n'
        '        int i;\n'
        '        int pid = unit->pCharacterData->number;\n'
        '\n'
        '        for (i = 0; gLordSelectCandidates[i] != 0xFFFF; i++)\n'
        '            ClearFlag(0x%X + i);\n'
        '        for (i = 0; gLordSelectCandidates[i] != 0xFFFF; i++) {\n'
        '            if (gLordSelectCandidates[i] == pid) {\n'
        '                SetFlag(0x%X + i);\n'
        '                break;\n'
        '            }\n'
        '        }\n'
        '        PlaySoundEffect(SONG_SE_SYS_WINDOW_SELECT1);\n'
        '        Proc_Goto(proc, PROC_LABEL_PREPUNIT_PRESS_B); /* fade out + end */\n'
        '        return 0;\n'
        '    }\n'
        % (LORDSEL_FLAG_BASE, LORDSEL_FLAG_BASE), 1)

    # 5. Idle: in lord mode START must not "Fight" -- the only exit is A (pick a lead).
    orig = ('        if (START_BUTTON & gKeyStatusPtr->newKeys) {\n'
            '            if (0 == proc->cur_counter) {\n')
    if text.count(orig) != 1:
        sys.exit('ERROR: ProcPrepUnit_Idle START handler not in expected form in %s'
                 % PREP_UNITSELECT_C)
    text = text.replace(orig,
        '        if (START_BUTTON & gKeyStatusPtr->newKeys) {\n'
        '            if (gLordSelectPrepMode || 0 == proc->cur_counter) {\n', 1)

    # 6. Entry point, appended after the proc script (which it references).
    text += (
        '\n'
        '/* Lord select (#46): launch THIS screen as the lord picker. The cast must be\n'
        '   loaded already (the prep list builds from loaded units). */\n'
        'extern u8 gLordSelectPrepMode;\n'
        '\n'
        'void StartLordSelectPrep(ProcPtr parent)\n'
        '{\n'
        '    gLordSelectPrepMode = 1;\n'
        '    Proc_StartBlocking(ProcScr_PrepUnitScreen, parent);\n'
        '}\n')

    # Externs needed in the few patched functions (gLordSelectPrepMode is defined in
    # bmunit.c). Declare it once near the top, after the includes block.
    inc_anchor = '#include "constants/songs.h"\n'
    if text.count(inc_anchor) != 1:
        sys.exit('ERROR: include anchor not found in %s' % PREP_UNITSELECT_C)
    text = text.replace(
        inc_anchor,
        inc_anchor + '\nextern u8 gLordSelectPrepMode; /* lord select (#46) */\n', 1)

    with open(PREP_UNITSELECT_C, 'w', encoding='utf-8') as f:
        f.write(text)

    # 7. Declare StartLordSelectPrep for the eventscripts that ASMC it (cross-TU), in the
    #    vanilla home for event-callable functions (beside CallRouteSplitMenu).
    eventcall_h = os.path.join(DECOMP, 'include', 'eventcall.h')
    with open(eventcall_h, encoding='utf-8') as f:
        text = f.read()
    orig = 'void CallRouteSplitMenu(ProcPtr proc);\n'
    if text.count(orig) != 1:
        sys.exit('ERROR: CallRouteSplitMenu decl anchor not found in %s' % eventcall_h)
    text = text.replace(
        orig, orig + 'void StartLordSelectPrep(ProcPtr proc); /* lord select (#46) */\n', 1)
    with open(eventcall_h, 'w', encoding='utf-8') as f:
        f.write(text)


def _inject_lord_floor_engine():
    """Lord survivability floor (#45 3c), engine side: bake the player-chosen lead's
    base-level top-up into its stats ONCE, the first player phase it is fielded.

    Consumes the build-generated gLordFloorDeltas[] table (inject_ch01, events_udefs.c):
    one { +maxHP, +Def, +Res } row per candidate, parallel to gLordSelectCandidates[]. Two
    campaign-agnostic hooks (string-replace + count-guard, like _inject_lord_select_engine,
    which MUST run first -- this anchors on its injected LordSelect_GetPid):

      1. LordFloor_ApplyOnce (new, eventinfo.c): find the chosen lead's index via the
         lord-select flags, look up its floor row, add it to maxHP/curHP/def/res, then set a
         permanent "applied" flag. No-op once applied; no-op until a pick exists (prologue:
         nothing chosen -> skip) and the lead is on the field. The applied flag is spent ONLY
         on a real application, so it can never be consumed early -> the floor always lands.

      2. EndPrepScreen (prep_sallycursor.c): call it once the prep "Fight!" has finalized
         deployment (right after ShrinkPlayerUnits compacts the roster). The chosen lead is
         deployed + VALID here and the pick is already recorded (the menu runs earlier, in the
         beginning scene). Phase-start seams (BmMain_StartPhase, the cursor reset) fire BEFORE
         prep deployment finalizes on turn 1 -- the lead isn't findable yet, so the floor lands
         a phase late (ch01 verified -- tools/playtest lordfloor showed +7 at turn 2, not turn
         1). Lord-select is always a prep chapter, so this single deployment seam suffices; the
         apply-once flag covers later Fight!s.
    """
    # 1: eventinfo.c -- LordFloor_ApplyOnce, right after the injected LordSelect_GetPid.
    with open(EVENTINFO_C, encoding='utf-8') as f:
        text = f.read()
    anchor = ('    return gLordSelectCandidates[0];\n'
              '}\n')
    if text.count(anchor) != 1:
        sys.exit('ERROR: LordSelect_GetPid tail not found in %s -- '
                 '_inject_lord_floor_engine must run after _inject_lord_select_engine'
                 % EVENTINFO_C)
    floor_fn = (
        '    return gLordSelectCandidates[0];\n'
        '}\n'
        '\n'
        '/* Lord survivability floor (campaign engine, #45 3c): once, at the first\n'
        '   player phase the chosen lead is fielded, add its base-level top-up\n'
        '   (gLordFloorDeltas, events_udefs.c -- { +maxHP, +Def, +Res } per candidate,\n'
        '   parallel to gLordSelectCandidates) to maxHP/curHP/Def/Res. A permanent\n'
        '   "applied" flag makes it happen exactly once and bake into the save, then\n'
        '   fade as the unit levels (Jagen-style). No-op until the ch01 menu has\n'
        '   recorded a pick (prologue: skip, flag stays clear) and the lead is on the\n'
        '   map -- the applied flag is spent ONLY on a real application, never early. */\n'
        'void LordFloor_ApplyOnce(void)\n'
        '{\n'
        '    extern const u16 gLordSelectCandidates[];\n'
        '    extern const s8 gLordFloorDeltas[];\n'
        '    struct Unit * unit;\n'
        '    int i;\n'
        '\n'
        '    if (CheckFlag(0x%X))\n'
        '        return;\n'
        '\n'
        '    /* the ch01 menu records the pick as permanent flag 0x%X + menu index */\n'
        '    for (i = 0; gLordSelectCandidates[i] != 0xFFFF; i++) {\n'
        '        if (CheckFlag(0x%X + i))\n'
        '            break;\n'
        '    }\n'
        '    if (gLordSelectCandidates[i] == 0xFFFF)\n'
        '        return; /* no pick yet (prologue) -- retry next chapter */\n'
        '\n'
        '    unit = GetUnitFromCharId(gLordSelectCandidates[i]);\n'
        '    if (unit == NULL)\n'
        '        return; /* chosen lead not on the field yet -- retry, flag stays clear */\n'
        '\n'
        '    unit->maxHP += gLordFloorDeltas[i * 3 + 0];\n'
        '    unit->curHP += gLordFloorDeltas[i * 3 + 0];\n'
        '    unit->def   += gLordFloorDeltas[i * 3 + 1];\n'
        '    unit->res   += gLordFloorDeltas[i * 3 + 2];\n'
        '\n'
        '    SetFlag(0x%X);\n'
        '}\n'
        % (LORDFLOOR_APPLIED_FLAG, LORDSEL_FLAG_BASE, LORDSEL_FLAG_BASE,
           LORDFLOOR_APPLIED_FLAG))
    with open(EVENTINFO_C, 'w', encoding='utf-8') as f:
        f.write(text.replace(anchor, floor_fn, 1))

    # 2: prep_sallycursor.c -- call it at the END of EndPrepScreen, right after
    #    ShrinkPlayerUnits() has compacted the deployed roster. This is the deployment-
    #    finalization point on the prep "Fight!" path: the chosen lead is force-deployed and
    #    VALID here, and the ch01 lord-select menu (which runs earlier, in the beginning scene)
    #    has already recorded the pick. Phase-start seams (BmMain_StartPhase, the cursor reset)
    #    fire BEFORE prep deployment finalizes on turn 1, so the lead isn't yet findable and
    #    the floor lands a phase late (ch01 verified via tools/playtest lordfloor: those seams
    #    gave +7 at turn 2, not turn 1). Lord-select is always a prep chapter, and the
    #    apply-once flag covers every later Fight!, so this single seam suffices.
    with open(PREP_SALLYCURSOR_C, encoding='utf-8') as f:
        text = f.read()
    orig = ('    ShrinkPlayerUnits();\n'
            '    Proc_EndEach(gProcScr_SALLYCURSOR);\n')
    if text.count(orig) != 1:
        sys.exit('ERROR: EndPrepScreen ShrinkPlayerUnits tail not in expected vanilla form '
                 'in %s' % PREP_SALLYCURSOR_C)
    hooked = ('    ShrinkPlayerUnits();\n'
              '\n'
              '    /* Lord survivability floor (campaign engine, #45 3c): now that the chosen\n'
              '       lead is deployed and the roster is finalized, bake its base-level top-up\n'
              '       in once. Apply-once flag makes later prep Fight!s no-ops. */\n'
              '    {\n'
              '        extern void LordFloor_ApplyOnce(void);\n'
              '        LordFloor_ApplyOnce();\n'
              '    }\n'
              '\n'
              '    Proc_EndEach(gProcScr_SALLYCURSOR);\n')
    with open(PREP_SALLYCURSOR_C, 'w', encoding='utf-8') as f:
        f.write(text.replace(orig, hooked, 1))
