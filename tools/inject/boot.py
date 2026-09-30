"""Fast boots: repointing New Game at a chapter, and the lord-select sequence.
"""
import re
import sys

from inject.decomp import _replace_brace_block
from inject.paths import BMIO_C, GAMECONTROL_C, PROLOGUE_WM_H


# New-game boots straight into the test chapter (skip the vanilla prologue) so the
# spawn is one "New Game" away. CHAPTER_L_1 = 0x01 (constants/chapters.h).
TEST_CHAPTER_INDEX = 1

# Lord select (#42): in ch01's beginning scene (after the Northlook muster, before
# preparations) the player picks the company's must-survive lead from the classed
# cast -- a route-split menu clone (cf. ch8-eventscript.h). The pick is stored as
# ONE permanent event flag per candidate (base + menu index). Permanent flags
# (ids >= 101, eventinfo.c SetFlag) ride the save file and are zeroed on New Game
# (ResetPermanentFlags, bmsave.c); vanilla scripts touch none above 0xE7, so the
# 0xF0 block is ours. Engine hooks: _inject_lord_select_engine.
# Lord survivability floor (#45 3c) "applied" flag: one permanent flag, just above the
# 0xF0..0xF9 candidate-pick block (LORDSEL_CONFIRM_MSGS caps the cast at 10), so the floor
# bakes into the chosen lead's saved stats exactly once. Permanent flags span 101..300
# (SetPermanentFlag rejects <= 100, then indexes flag-101 into 0x19 bytes = 200 bits),
# so 0xFA is in range and free.
LORDSEL_PROMPT_MSG = 0x957   # dead vanilla slot-2 scene text (cf. inject_ch01 step 6)
# Lord-select candidate pitch blurbs (#46): one dead Ch1-tutorial slot-2 id per candidate,
# PARALLEL to LORDSEL_CONFIRM_MSGS (same 10-cap), drawn by lord_select_screen.c as the
# cursor lands on each candidate. Plus a one-time explainer box shown before the screen
# ("(a) explain", feedback #4). Pool vetting (the "msg-id vetting is treacherous" gotcha):
# 0x966-0x970 are referenced ONLY by vanilla Ch2's slot-2 event scripts
# (ch2-eventscript.h) -- dead because inject_ch01 replaces the slot-2 events (NOT
# because of the prologue host); checked clean of live data_battlequotes.c
# refs (the 0x993/0x994 false-negative lesson) and of the lone live use in the range (0x980,
# bmdifficulty.c), which is excluded.
LORDSEL_EXPLAINER_MSG = 0x966


def _cut_boot_intro(montage=False):
    """Cut the pre-map boot sequences so a fresh boot lands on the title and New Game
    drops straight onto the map. Three cuts, each at the source that actually plays the
    thing (a previous single-hook attempt at GameControl_RememberChapterId was reset
    before the world-map wrapper, so the Magvel tour still ran):
      (a) gamecontrol.c: drop the boot OP anim (ProcScr_OpAnim, the character-flash +
          attract reel) so boot falls through to the title;
      (b) gamecontrol.c: skip the post-New-Game intro monologue (the "long ago..." lore
          crawl) -- GameCtrlStartIntroMonologue runs it only while chapterIndex == 0;
          force it to bail;
      (c) prologue-wm.h: gut the prologue's world-map intro (EventScrWM_Prologue_
          Beginning runs WM_TEXT(0x8DB) -- the "continent of Magvel" nation tour). The WM
          wrapper runs BEFORE the map load, so replace its body with a no-op.
    MONTAGE=1 builds (#43) keep cut (b)'s sequence: the monologue stays wired and
    inject_opening_montage replaces its seven card slides with our lore crawl, and
    skip cut (c): inject_world_tour rewrites the WM event body with the Icewind Dale
    tour instead. Cut (a) stays in all builds (the attract reel is vanilla promo
    content)."""
    with open(GAMECONTROL_C, encoding='utf-8') as f:
        gc = f.read()
    gc, n1 = re.subn(r'[ \t]*PROC_START_CHILD_BLOCKING\(ProcScr_OpAnim\),\n',
                     '', gc, count=1)
    if n1 == 0:
        sys.exit('ERROR: ProcScr_OpAnim start not found in %s' % GAMECONTROL_C)
    # With the OpAnim attract gone, nothing flips the cold-boot action from EVENT_RETURN
    # (which GameControl_PostIntro routes to the New Game/Extras save menu) to USR_SKIPPED
    # (-> LGAMECTRL_TITLE_DIRECT -> StartTitleScreen). Set it directly in StartGame so a
    # fresh boot still SHOWS the title screen (then START there proceeds to New Game as
    # usual) instead of skipping straight to the menu.
    gc, n_act = re.subn(
        r'proc->nextAction = GAME_ACTION_EVENT_RETURN;',
        'proc->nextAction = GAME_ACTION_USR_SKIPPED; '
        '/* manchego: no op-anim -> boot to the title screen */', gc, count=1)
    if n_act == 0:
        sys.exit('ERROR: StartGame cold-boot nextAction not found in %s' % GAMECONTROL_C)
    if not montage:
        gc, n2 = re.subn(r'\n(\s*)StartIntroMonologue\(proc\);',
                         r'\n\1return; /* manchego: skip intro monologue */',
                         gc, count=1)
        if n2 == 0:
            sys.exit('ERROR: StartIntroMonologue call not found in %s' % GAMECONTROL_C)
    with open(GAMECONTROL_C, 'w', encoding='utf-8') as f:
        f.write(gc)

    if not montage:
        with open(PROLOGUE_WM_H, encoding='utf-8') as f:
            wm = f.read()
        wm = _replace_brace_block(
            wm, 'EventScrWM_Prologue_Beginning[] =',
            '{\n    EVBIT_MODIFY(0x1)\n    SKIPWN\n    ENDA\n}', PROLOGUE_WM_H)
        with open(PROLOGUE_WM_H, 'w', encoding='utf-8') as f:
            f.write(wm)


def _redirect_new_game(chapter_index):
    """Redirect the prologue slot -> `chapter_index` at the authoritative map-load point,
    StartBattleMap (feeds gPlaySt.chapterIndex into InitChapterMap/fog/weather): if
    (chapterIndex == 0) chapterIndex = N. chapterIndex == 0 there can only be a fresh
    game's prologue (skirmishes use PLAY_FLAGs; later chapters nonzero). BOTH boot
    modes ride this: the sandbox redirects 0 -> the Ch1 slot, and the real game
    redirects 0 -> PROLOGUE_HOST_INDEX (slot 1, where the prologue is hosted --
    main() calls _configure_boot on every non-sandbox build)."""
    with open(BMIO_C, encoding='utf-8') as f:
        bmio = f.read()
    bmio, n = re.subn(
        r'(void StartBattleMap\(struct GameCtrlProc\* gameCtrl\) \{\n    int i;\n)',
        r'\1\n    if (gPlaySt.chapterIndex == 0) /* test-chapter spawn: prologue -> Ch%d */\n'
        r'        gPlaySt.chapterIndex = %d;\n' % (chapter_index, chapter_index),
        bmio, count=1)
    if n == 0:
        sys.exit('ERROR: StartBattleMap signature not found in %s' % BMIO_C)
    with open(BMIO_C, 'w', encoding='utf-8') as f:
        f.write(bmio)


def _configure_boot(new_game_target, montage=False):
    """Single owner of the boot decision. inject_prologue and inject_test_chapter each used
    to cut the intro + redirect New Game themselves -- the SAME decision scattered across two
    desks, which double-cut and crashed if both ran. Localized here: cut the attract / intro /
    world-map sequences, then point New Game at `new_game_target` (the host chapter slot the
    prologue OR the Ch1 sandbox loads through -- both PROLOGUE_HOST_INDEX). Call ONCE from
    main(), after whichever target injector ran."""
    _cut_boot_intro(montage=montage)
    _redirect_new_game(new_game_target)


def _lord_select_event_seq(bg_const, explainer_msg):
    """The #46 lord-select interaction as an event-script fragment: open the scenic BG,
    show the one-time explainer ONCE, then the LABEL(0) re-pick loop (menu -> "Will N
    lead?" confirm in EVT_SLOT_C -> BNE back to the menu on "No"). Returns the fragment
    up to and INCLUDING the BNE; callers append their own tail after it -- the real ch1
    BeginningScene does EVBIT_MODIFY(0x0)+FADI+map build, the lord-fast debug boot just
    FADI+ENDA. Single home so the debug boot can't drift from the flow it claims to verify
    (AGENTS.md design-placement rule -- one decision, one desk)."""
    return (
        '    REMOVEPORTRAITS\n'
        '    BACG(%s)\n'
        '    FADU(16)\n'
        '    EVBIT_MODIFY(0x4)\n'
        '    /* #46 (a): one-time explainer -- the chosen lead is the must-survive\n'
        '       company lead campaign-long. Shown ONCE, before the re-pick loop. */\n'
        '    TUTORIALTEXTBOXSTART\n'
        '    TEXTSHOW(0x%X)\n'
        '    TEXTEND\n'
        '    REMA\n'
        'LABEL(0x0)\n'
        '    ASMC(CallLordSelectMenu)\n'
        '    SADD(EVT_SLOT_2, EVT_SLOT_C, EVT_SLOT_0)\n'
        '    TUTORIALTEXTBOXSTART\n'
        '    SVAL(EVT_SLOT_B, 0xffffffff)\n'
        '    TEXTSHOW(0xffff) /* confirm body from slot 2: "Will N lead...?" [Yes] */\n'
        '    TEXTEND\n'
        '    REMA\n'
        '    SVAL(EVT_SLOT_7, 0x1)\n'
        '    BNE(0x0, EVT_SLOT_C, EVT_SLOT_7) /* "No" -> pick again */\n'
        % (bg_const, explainer_msg))
